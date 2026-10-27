#!/usr/bin/env python3
"""প্রতিদিনের স্ক্যান: docs/data/prices.csv (+ fundamentals.csv, থাকলে) পড়ে প্রতিটি কোডের আজকের ফেজ ও ট্রেড-প্ল্যান বের করে
docs/data/phases.json লেখে। নিয়মগুলো scripts/phase_engine.py-তে (রিপোর্ট অনুযায়ী)। চালাতে: python3 -I scripts/compute_phases.py"""
import csv, json, os, sys
from datetime import datetime, timezone
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from phase_engine import Cfg, PHASES, build_panel, classify, load_all_prices, cfg_dict  # noqa: E402
from pressure_engine import PCfg, load_prices_ycp, pressure_latest, pcfg_dict  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'docs', 'data')


def rnd(x, n=2):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), n)


def read_csv_rows(path):
    if not os.path.exists(path):
        return []
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def compute_market_regime(data_dir):
    """DSE Analyst কোয়ান্ট মডেল: DSEX সূচকের ২৬-সপ্তাহ (১৩০ দিন) গড়ের ভিত্তিতে বাজার রেজিম নির্ণয়।"""
    dsex_path = os.path.join(data_dir, 'dsex.csv')
    if not os.path.exists(dsex_path):
        return None
    try:
        with open(dsex_path, 'r', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        closes = [float(r['dsex_close']) for r in rows if r.get('dsex_close') and r['dsex_close'].strip()]
        if not closes:
            return None
        latest = closes[-1]
        win = min(130, len(closes))
        sma26 = sum(closes[-win:]) / win
        diff_pct = round((latest / sma26 - 1) * 100, 2)
        is_bull = latest >= sma26
        return {
            'close': round(latest, 1),
            'sma26': round(sma26, 1),
            'diff_pct': diff_pct,
            'regime': 'BULL' if is_bull else 'DEFENSE',
            'title': 'বুলিশ মোমেন্টাম রেজিম (DSEX > ২৬-সপ্তাহ SMA)' if is_bull else 'বেয়ারিশ ডিফেন্সিভ রেজিম (DSEX < ২৬-সপ্তাহ SMA)',
            'action_bn': 'বাজারের সামগ্রিক গতিধারা ইতিবাচক। ব্রেকআউট (Phase D/SOS) ও মোমেন্টাম সেটআপে ঐতিহাসিক সাফল্যের হার বেশি।' if is_bull else 'বাজার দীর্ঘমেয়াদি গড়ের নিচে থাকায় ব্রেকআউট ফেইলিওরের ঝুঁকি বেশি। শুধুমাত্র ভলিউম ড্রাই-আপ, গভীর সাপোর্ট এবং ওভারসোল্ড রিভার্সাল অগ্রাধিকার দিন।',
            'washout_edge': '+0.5% (সাধারণ)' if is_bull else '+15.7% (ঐতিহাসিকভাবে উচ্চ উইন)'
        }
    except Exception as e:
        print('Regime calculation notice:', e)
        return None


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
    pcfg = PCfg()
    PR = pressure_latest(load_prices_ycp(ROOT), pcfg)           # বাইং/সেলিং প্রেসার (scripts/pressure_engine.py)
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
                                ('STEALTH', 'e_stealth'), ('EARLY', 'e_early'), ('DRYUP', 'e_dryup'), ('DIV', 'e_divergence'), ('UC_LOWVOL', 'e_uc_lowvol')) if bool(g[c].tail(5).any())]
        lowcap = bool(r['lowcap']) if have_fund and r['paidup_mn'] == r['paidup_mn'] else None
        zone = ''.join(k for k, c in (('F', 'z_fib'), ('O', 'z_ob'), ('G', 'z_fvg')) if bool(r[c]))
        pr = PR.loc[code] if code in PR.index and PR.loc[code, 'date'] == last else None
        pv = (lambda k, n=0: rnd(pr[k], n) if pr is not None else None)

        # DSE Analyst Style: Price Extension over SMA50 / SMA20
        c_price = float(r['close']) if r['close'] is not None and np.isfinite(r['close']) else 0.0
        m50_val = float(r['sma50']) if r['sma50'] is not None and np.isfinite(r['sma50']) else None
        m20_val = float(r['sma20']) if r['sma20'] is not None and np.isfinite(r['sma20']) else None

        ext_pct = round((c_price / m50_val - 1) * 100, 1) if (m50_val and m50_val > 0) else (round((c_price / m20_val - 1) * 100, 1) if (m20_val and m20_val > 0) else 0.0)
        ext20_pct = round((c_price / m20_val - 1) * 100, 1) if (m20_val and m20_val > 0) else ext_pct

        if ext_pct >= 50.0 or ext20_pct >= 35.0:
            rt = 1
            rt_label = 'Tier 1 (Extreme)'
            rt_desc = 'চরম ঝুঁকি · ৫.৪x ড্রপ রেট'
        elif ext_pct >= 30.0 or ext20_pct >= 20.0:
            rt = 2
            rt_label = 'Tier 2 (High)'
            rt_desc = 'উচ্চ ঝুঁকি · ৩.০x ড্রপ রেট'
        elif ext_pct >= 15.0 or ext20_pct >= 10.0:
            rt = 3
            rt_label = 'Tier 3 (Elevated)'
            rt_desc = 'সতর্ক জোন · ১.৮x ড্রপ রেট'
        else:
            rt = 4
            rt_label = 'Tier 4 (Baseline)'
            rt_desc = 'নিরাপদ বেসলাইন · সাধারণ ড্রপ রেট'

        # DSE Analyst Style: Multi-tier Confirmation Score (Confluence Tier)
        sig_cnt = len(flags)
        if r['vr'] is not None and r['vr'] >= 2.0:
            sig_cnt += 1
        if zone:
            sig_cnt += 1
        if r['atr_ratio'] is not None and r['atr_ratio'] <= 0.85:
            sig_cnt += 1
        conf = 3 if sig_cnt >= 3 else (2 if sig_cnt == 2 else 1)

        rows.append({
            'pbuy': pv('bp'), 'psell': pv('sp'), 'pscore': pv('ps'), 'pst': (pr['state'] or None) if pr is not None else None,
            'gn': (pr['gone'] or None) if pr is not None else None,          # up / dn / None: নাগালের বাইরে কোন দিকে
            'fw3': pv('flow3', 2), 'bal': pv('bal10', 2), 'ab': pv('abs3', 2),
            'r3': rnd(pr['ret3'] * 100, 1) if pr is not None else None,
            'r5': rnd(pr['ret5'] * 100, 1) if pr is not None else None,
            'dev': rnd(pr['dev20'] * 100, 1) if pr is not None else None,
            'idle': int(pr['idle']) if pr is not None else 0,                # টানা কত দিন ভলিউম ০ (১ = আজই নিষ্ক্রিয়)
            'lk': ('up' if bool(pr['lock_up']) else 'dn' if bool(pr['lock_dn']) else None) if pr is not None else None,
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
            'gl': int(r['glvl']) if r['glvl'] == r['glvl'] else None, 'ga': int(r['gage']) if r['gage'] == r['gage'] else None,
            'gb': int(r['gbal']) if r['gbal'] == r['gbal'] else None,
            'ea': bool(r['early']) if 'early' in r else False,
            'e_dryup': bool(r['e_dryup']) if 'e_dryup' in r else False,
            'e_divergence': bool(r['e_divergence']) if 'e_divergence' in r else False,
            'e_uc_lowvol': bool(r['e_uc_lowvol']) if 'e_uc_lowvol' in r else False,
            'ext': ext_pct, 'rt': rt, 'rtl': rt_label, 'rtd': rt_desc, 'conf': conf,
            'lq': bool(r['liquid']), 'sp': [rnd(x) for x in g['close'].tail(50).tolist()],
        })
    order = {p: i for i, p in enumerate(PHASES)}
    rows.sort(key=lambda x: (order.get(x['p'], 9), -x['sc'], x['c']))
    liq = [x for x in rows if x['lq']]
    regime_info = compute_market_regime(DATA)
    risk_summary = {
        'tier1_extreme': sum(1 for x in rows if x.get('rt') == 1),
        'tier2_high': sum(1 for x in rows if x.get('rt') == 2),
        'tier3_elevated': sum(1 for x in rows if x.get('rt') == 3),
        'tier4_baseline': sum(1 for x in rows if x.get('rt') == 4)
    }
    out = {'updated_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'last_date': last,
           'market_regime': regime_info, 'risk_summary': risk_summary,
           'config': cfg_dict(cfg), 'pconfig': pcfg_dict(pcfg), 'have_fund': bool(have_fund), 'n_all': len(rows), 'n_liquid': len(liq),
           'counts_liquid': {p: sum(1 for x in liq if x['p'] == p) for p in PHASES},
           'counts_all': {p: sum(1 for x in rows if x['p'] == p) for p in PHASES},
           'n_setup_liquid': sum(1 for x in liq if x['ok']), 'stocks': rows}
    with open(os.path.join(DATA, 'phases.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
    print(f"phases.json: {len(rows)} কোড ({len(liq)} লিকুইড), তারিখ {last}, fundamentals: {'আছে' if have_fund else 'নেই'}, রেজিম: {regime_info['regime'] if regime_info else 'N/A'}")
    print({p: out['counts_liquid'][p] for p in PHASES}, 'অনির্দিষ্ট (লিকুইড):', sum(1 for x in liq if not x['p']), '| সেটআপ:', out['n_setup_liquid'])
    print('রিস্ক টিয়ার সামারি:', risk_summary)


if __name__ == '__main__':
    main()
