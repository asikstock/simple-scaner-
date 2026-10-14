#!/usr/bin/env python3
"""প্রতিদিনের স্ক্যান: docs/data/prices.csv পড়ে প্রতিটি কোডের আজকের ফেজ বের করে docs/data/phases.json লেখে।
শুধু দাম, ভলিউম ও SMA20/50/100 ব্যবহার হয়। চালাতে: python3 -I scripts/compute_phases.py"""
import csv, json, os, sys
from datetime import datetime, timezone
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from phase_engine import Cfg, PHASES, build_panel, classify, load_prices, cfg_dict  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'docs', 'data')


def rnd(x, n=2):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), n)


def main():
    prices = load_prices(os.path.join(DATA, 'prices.csv'))
    cfg = Cfg()
    F = classify(build_panel(prices, horizons=()), cfg)
    last = F['date'].max()
    sectors = {}
    p = os.path.join(DATA, 'sectors.csv')
    if os.path.exists(p):
        with open(p, newline='', encoding='utf-8') as f:
            for r in csv.DictReader(f):
                sectors[r['SYMBOL'].strip().upper()] = r['SECTOR'].strip()
    rows = []
    for code, g in F.groupby('code'):
        g = g.reset_index(drop=True)
        if g['date'].iloc[-1] != last:        # আজ যার ডেটা নেই (বন্ধ/ডিলিস্টেড), বাদ
            continue
        r = g.iloc[-1]
        tail = g['close'].tail(50).tolist()
        ph = r['phase'] if isinstance(r['phase'], str) else None
        rows.append({
            'c': code, 's': sectors.get(code, ''), 'p': ph, 'sc': int(r['score']) if ph else 0, 'd': int(r['days']) if ph else 0,
            'cl': rnd(r['close']), 'ch': rnd(r['chg']), 'v': int(r['volume']), 'val': rnd(r['value20'] / 1e6, 1),
            'm20': rnd(r['sma20']), 'm50': rnd(r['sma50']), 'm100': rnd(r['sma100']),
            'vb': rnd(r['vb'], 2), 'w': rnd(r['width'] * 100, 1) if r['width'] == r['width'] else None,
            'lo': rnd(r['lo']), 'hi': rnd(r['hi']), 'pr': rnd(r['prior_ret'] * 100, 1) if r['prior_ret'] == r['prior_ret'] else None,
            'lq': bool(r['liquid']), 'sp': [rnd(x) for x in tail],
        })
    order = {p: i for i, p in enumerate(PHASES)}
    rows.sort(key=lambda x: (order.get(x['p'], 9), -x['sc'], x['c']))
    liq = [x for x in rows if x['lq']]
    out = {'updated_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'last_date': last,
           'config': cfg_dict(cfg), 'n_all': len(rows), 'n_liquid': len(liq),
           'counts_liquid': {p: sum(1 for x in liq if x['p'] == p) for p in PHASES},
           'counts_all': {p: sum(1 for x in rows if x['p'] == p) for p in PHASES},
           'stocks': rows}
    with open(os.path.join(DATA, 'phases.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
    print(f"phases.json: {len(rows)} কোড ({len(liq)} লিকুইড), তারিখ {last}")
    print({p: out['counts_liquid'][p] for p in PHASES}, 'অনির্দিষ্ট (লিকুইড):', sum(1 for x in liq if not x['p']))


if __name__ == '__main__':
    main()
