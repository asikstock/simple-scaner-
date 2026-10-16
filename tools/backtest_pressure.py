#!/usr/bin/env python3
"""প্রেসার স্কোর পরদিন/পরের কয়েক দিনের রিটার্নের কোনো আভাস দেয় কি? (শুধু সেই দিন পর্যন্ত ডেটা দিয়ে স্কোর; ফল পরে মাপা)
থ্রেশহোল্ড বা ওজন এই ফল দেখে বদলানো হয়নি। চালাতে: python3 -I tools/backtest_pressure.py  → docs/data/pressure_backtest.json"""
import json, os, sys
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
from pressure_engine import PCfg, load_prices_ycp, pressure_panel, pcfg_dict  # noqa: E402
from phase_engine import Cfg, build_panel, classify, load_all_prices  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COST = 0.005


def add_forward(F):
    """চেইনড রিটার্ন chg (= ক্লোজ ÷ YCP) দিয়ে, যাতে ডিভিডেন্ড/রেকর্ড-ডেটের সমন্বয়ে ভুয়া পতন না আসে।"""
    out = []
    for _, g in F.groupby('code', sort=False):
        g = g.copy()
        lr = np.log1p((g['chg'].fillna(0) / 100).clip(-0.5, 0.5))
        cs = lr.cumsum()
        g['r1'] = np.expm1(cs.shift(-1) - cs)                       # আজ ক্লোজ → কাল ক্লোজ (আজ ক্লোজে কেনা সম্ভব নয়; পরদিনের দিক মাপার জন্য)
        for h in (3, 5, 10):
            g[f'e{h}'] = np.expm1(cs.shift(-(1 + h)) - cs.shift(-1)) - COST   # কাল ক্লোজে কিনে h দিন ধরে রাখলে (কাল ঢোকার বাস্তব উপায়)
        g['nz'] = (g['volume'].shift(-1) == 0)                      # পরদিন ভলিউম ০ (নিষ্ক্রিয়/হল্ট-সদৃশ)
        g['nvol'] = g['volume'].shift(-1)
        out.append(g)
    return pd.concat(out, ignore_index=True)


def cluster(df, col, mask):
    """তারিখভিত্তিক গড় অতিরিক্ত রিটার্ন (ঐ দিনের সব লিকুইড-গড়ের চেয়ে), মাস ধরে ক্লাস্টার করা t।"""
    d = df[mask & df[col].notna()]
    if len(d) == 0:
        return {'n': 0}
    day = d.groupby('date')['x_' + col].mean()
    mon = day.groupby(day.index.str[:7]).mean()
    t = mon.mean() / (mon.std(ddof=1) / np.sqrt(len(mon))) if len(mon) > 2 and mon.std(ddof=1) > 0 else np.nan
    return {'n': int(len(d)), 'raw': round(float(d[col].mean() * 100), 3), 'excess': round(float(day.mean() * 100), 3),
            'hit': round(float((d[col] > 0).mean() * 100), 1), 't': None if not np.isfinite(t) else round(float(t), 2)}


def main():
    prices = load_prices_ycp(ROOT)
    P = pressure_panel(prices)
    # ওয়াইকফ ফেজ যোগ (ফেজ-ইঞ্জিন একই কোড)
    ph = classify(build_panel(load_all_prices(ROOT), Cfg(), horizons=()), Cfg(), None)[['date', 'code', 'phase']]
    P = P.merge(ph, on=['date', 'code'], how='left')
    F = add_forward(P)
    F = F[F['liquid'] & F['state'].ne('') & F['r1'].notna()].copy()
    cols = ['r1', 'e3', 'e5', 'e10']
    for c in cols:
        F['x_' + c] = F[c] - F.groupby('date')[c].transform('mean')       # ঐ দিনের সব লিকুইড শেয়ারের গড়ের চেয়ে কত বেশি
    dates = sorted(F['date'].unique())
    split = dates[len(dates) // 2]
    F['half'] = np.where(F['date'] < split, 'train', 'test')
    out = {'first_date': dates[0], 'last_date': dates[-1], 'split_date': split, 'n_rows': int(len(F)), 'cost_pct': COST * 100,
           'config': pcfg_dict(PCfg()), 'by_state': {}, 'by_decile': {}, 'by_phase': {}, 'halt': {}}
    reach = F['gone'].eq('')
    for key, m0 in (('reach', reach), ('gone', ~reach)):
        out['by_state'][key] = {}
        for st in ('buy', 'neutral', 'sell'):
            m = m0 & F['state'].eq(st)
            out['by_state'][key][st] = {'all': {c: cluster(F, c, m) for c in cols},
                                        'test': {c: cluster(F, c, m & F['half'].eq('test')) for c in cols}}
    # স্কোর-ডেসাইল (নাগালের ভেতরে, প্রতি দিনের ক্রস-সেকশনে ১০ ভাগ)
    R = F[reach].copy()
    R['dec'] = R.groupby('date')['ps'].rank(pct=True).mul(10).apply(np.ceil).clip(1, 10)
    for d in range(1, 11):
        m = R['dec'].eq(d)
        out['by_decile'][str(d)] = {c: cluster(R, c, m) for c in cols}
    # সহনশীলতা-যাচাই: ছোট দামের শেয়ারে টিক-সাইজ/বিড-আস্ক বাউন্সের কারণে ভুয়া রিভার্সাল আসতে পারে; তাই দাম ও লেনদেন বাড়িয়ে আবার মাপা
    out['robust'] = {}
    for name, sm in (('সব লিকুইড', R['close'] > 0), ('দাম ≥ ২০ টাকা', R['close'] >= 20), ('গড় লেনদেন ≥ ২ কোটি টাকা', R['value20'] >= 2e7),
                     ('দাম ≥ ২০ ও লেনদেন ≥ ২ কোটি', (R['close'] >= 20) & (R['value20'] >= 2e7))):
        out['robust'][name] = {}
        for lab, m in (('ডেসাইল ১ (সর্বোচ্চ সেলিং ঝোঁক)', R['dec'].eq(1)), ('ডেসাইল ১০ (সর্বোচ্চ বাইং ঝোঁক)', R['dec'].eq(10)),
                       ('বাইং হাই', R['state'].eq('buy')), ('সেলিং হাই', R['state'].eq('sell'))):
            out['robust'][name][lab] = {'all': {c: cluster(R, c, sm & m) for c in ('r1', 'e5')},
                                        'test': {c: cluster(R, c, sm & m & R['half'].eq('test')) for c in ('r1', 'e5')}}
    # ফেজের ভেতরে প্রেসার বাড়তি কিছু দেয় কি?
    for p in ('Phase A', 'Phase B', 'Phase C', 'Phase D', 'Phase E', 'Distribution', 'Markdown'):
        out['by_phase'][p] = {}
        for st in ('buy', 'neutral', 'sell'):
            m = reach & F['phase'].eq(p) & F['state'].eq(st)
            out['by_phase'][p][st] = {c: cluster(F, c, m) for c in ('r1', 'e5')}
    # হল্ট-সদৃশ (পরদিন ভলিউম ০) আগাম আঁচ করা যায় কি? আজ ট্রেড হয়েছে এমন লিকুইড শেয়ারে
    H = F[F['volume'] > 0]
    base = H['nz'].mean() * 100
    def lift(mask, name):
        s = H[mask]
        out['halt'][name] = {'n': int(len(s)), 'rate_pct': round(float(s['nz'].mean() * 100), 2) if len(s) else None}
    out['halt']['base_rate_pct'] = round(float(base), 2)
    lift(H['chg'] >= 9.5, 'আপার সার্কিট দিন')
    lift(H['chg'] <= -9.5, 'লোয়ার সার্কিট দিন')
    lift(H['lock_up'] | H['lock_dn'], 'রেঞ্জ-লক (H=L) দিন')
    lift(H['vr'] >= 2.5, 'VR ≥ ২.৫')
    lift(H['vr'] >= 4, 'VR ≥ ৪')
    lift(H['volume'] > 0, 'সব')
    lift(H['idle'].shift(0) == 0, 'নিয়মিত')
    with open(os.path.join(ROOT, 'docs', 'data', 'pressure_backtest.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
    pr = lambda k, d: print(f"  {k:8s}", {c: (d[c].get('n'), d[c].get('excess'), d[c].get('hit'), d[c].get('t')) for c in cols if d.get(c)})
    print('ফর্ম্যাট: (n, অতিরিক্ত%, জেতা%, t)  | বিভাজন', split)
    for key in ('reach', 'gone'):
        print(key)
        for st in ('buy', 'neutral', 'sell'):
            pr(st, out['by_state'][key][st]['all'])
            pr(st + '/TEST', out['by_state'][key][st]['test'])
    print('decile (নাগালের ভেতরে)')
    for d in range(1, 11):
        pr(str(d), out['by_decile'][str(d)])
    print('robust (n, excess%, hit%, t)')
    for name, v in out['robust'].items():
        print(' ', name)
        for lab, r in v.items():
            print('    ', lab, '| ALL', {c: (r['all'][c].get('n'), r['all'][c].get('excess'), r['all'][c].get('t')) for c in ('r1', 'e5')},
                  '| TEST', {c: (r['test'][c].get('n'), r['test'][c].get('excess'), r['test'][c].get('t')) for c in ('r1', 'e5')})
    print('phase × state (r1, e5: n, excess, t)')
    for p, v in out['by_phase'].items():
        print(' ', p, {st: {c: (x.get('n'), x.get('excess'), x.get('t')) for c, x in d.items()} for st, d in v.items()})
    print('halt', out['halt'])


if __name__ == '__main__':
    main()
