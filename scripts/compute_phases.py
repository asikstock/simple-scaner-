#!/usr/bin/env python3
"""প্রতিদিনের স্ক্যান: docs/data/prices.csv (+ fundamentals.csv, থাকলে) পড়ে প্রতিটি কোডের আজকের ফেজ ও ট্রেড-প্ল্যান বের করে
docs/data/phases.json লেখে। নিয়মগুলো scripts/phase_engine.py-তে (রিপোর্ট অনুযায়ী)। চালাতে: python3 -I scripts/compute_phases.py"""
import csv, json, os, sys
from datetime import datetime, timezone
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from phase_engine import Cfg, PHASES, build_panel, classify, load_all_prices, cfg_dict  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'docs', 'data')


def rnd(x, n=2):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), n)


def read_csv_rows(path):
    if not os.path.exists(path):
        return []
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def load_fund():
    """fundamentals.csv, তার ওপর fundamentals_manual.csv (হাতে দেওয়া মান অগ্রাধিকার পায়)।"""
    d = {}
    for name in ('fundamentals.csv', 'fundamentals_manual.csv'):
        for r in read_csv_rows(os.path.join(DATA, name)):
            k = (r.get('SYMBOL') or '').strip().upper()
            if not k:
                continue
            cur = d.setdefault(k, {'paidup_mn': np.nan, 'pe': np.nan, 'cat': ''})
            for src, dst in (('PAIDUP_MN', 'paidup_mn'), ('PE', 'pe')):
                try:
                    cur[dst] = float(r[src]) if (r.get(src) or '').strip() != '' else cur[dst]
                except ValueError:
                    pass
            if (r.get('CATEGORY') or '').strip():
                cur['cat'] = r['CATEGORY'].strip()
    df = pd.DataFrame([{'code': k, **v} for k, v in d.items()], columns=['code', 'paidup_mn', 'pe', 'cat'])
    return df


def main():
    prices = load_all_prices(ROOT)
    cfg = Cfg()
    fund = load_fund()
    have_fund = len(fund) > 0 and fund['paidup_mn'].notna().any()
    F = classify(build_panel(prices, cfg, horizons=()), cfg, fund if have_fund else None)
    last = F['date'].max()
    sectors = {r['SYMBOL'].strip().upper(): r['SECTOR'].strip() for r in read_csv_rows(os.path.join(DATA, 'sectors.csv'))}
    cats = dict(zip(fund['code'], fund['cat'])) if have_fund else {}
    rows = []
    for code, g in F.groupby('code'):
        g = g.reset_index(drop=True)
        if g['date'].iloc[-1] != last:        # আজ যার ডেটা নেই (বন্ধ/ডিলিস্টেড), বাদ
            continue
        r = g.iloc[-1]
        ph = r['phase'] if isinstance(r['phase'], str) else None
        flags = [k for k, c in (('SC', 'e_sc'), ('SPRING', 'e_spring'), ('SOS', 'e_sos'), ('BC', 'e_bc'), ('UTAD', 'e_utad'), ('SOW', 'e_sow'),
                                ('STEALTH', 'e_stealth')) if bool(g[c].tail(5).any())]
        lowcap = bool(r['lowcap']) if have_fund and r['paidup_mn'] == r['paidup_mn'] else None
        zone = ''.join(k for k, c in (('F', 'z_fib'), ('O', 'z_ob'), ('G', 'z_fvg')) if bool(r[c]))
        rows.append({
            'c': code, 's': sectors.get(code, ''), 'p': ph, 'sc': int(r['score']) if ph else 0, 'd': int(r['days']) if ph else 0,
            'cl': rnd(r['close']), 'ch': rnd(r['chg']), 'v': int(r['volume']), 'val': rnd(r['value20'] / 1e6, 1),
            'm20': rnd(r['sma20']), 'm50': rnd(r['sma50']), 'm100': rnd(r['sma100']),
            'vr': rnd(r['vr']), 'vr5': rnd(r['vr5']), 'sq': rnd(r['atr_ratio']), 'vb': rnd(r['vb']),
            'w': rnd(r['width_r'] * 100, 1) if r['width_r'] == r['width_r'] else None, 'lo': rnd(r['lo_r']), 'hi': rnd(r['hi_r']),
            'tr': int(r['trend']), 'ca': int(r['choch_age']) if r['choch_age'] == r['choch_age'] else None,
            'z': zone, 'uc': int(r['uc10']),
            'pu': rnd(r['paidup_mn'], 1) if have_fund else None, 'pe': rnd(r['pe'], 1) if have_fund else None,
            'cat': cats.get(code, ''), 'lc': lowcap, 'pe40': bool(r['pe_high']) if have_fund and r['pe'] == r['pe'] else None,
            'pl': r['plan'] or None, 'st': r['setup_type'] or None, 'ok': bool(r['setup']),
            'en': rnd(r['close']) if r['plan'] else None, 'sl': rnd(r['stop']), 'tg': rnd(r['target']), 'rr': rnd(r['rrr'], 1),
            'al': int(r['alloc']), 'ac': r['act'] or None, 'late': bool(r['late']), 'fl': flags,
            'wl': bool(lowcap) if lowcap is not None else ('STEALTH' in flags),
            'lq': bool(r['liquid']), 'sp': [rnd(x) for x in g['close'].tail(50).tolist()],
        })
    order = {p: i for i, p in enumerate(PHASES)}
    rows.sort(key=lambda x: (order.get(x['p'], 9), -x['sc'], x['c']))
    liq = [x for x in rows if x['lq']]
    out = {'updated_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'last_date': last,
           'config': cfg_dict(cfg), 'have_fund': bool(have_fund), 'n_all': len(rows), 'n_liquid': len(liq),
           'counts_liquid': {p: sum(1 for x in liq if x['p'] == p) for p in PHASES},
           'counts_all': {p: sum(1 for x in rows if x['p'] == p) for p in PHASES},
           'n_setup_liquid': sum(1 for x in liq if x['ok']), 'stocks': rows}
    with open(os.path.join(DATA, 'phases.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
    print(f"phases.json: {len(rows)} কোড ({len(liq)} লিকুইড), তারিখ {last}, fundamentals: {'আছে' if have_fund else 'নেই'}")
    print({p: out['counts_liquid'][p] for p in PHASES}, 'অনির্দিষ্ট (লিকুইড):', sum(1 for x in liq if not x['p']), '| সেটআপ:', out['n_setup_liquid'])


if __name__ == '__main__':
    main()
