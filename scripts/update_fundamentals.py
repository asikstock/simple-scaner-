#!/usr/bin/env python3
"""
কোম্পানি-ভিত্তিক মৌলিক তথ্য: Paid-up Capital (মিলিয়ন টাকা), P/E, মার্কেট ক্যাটাগরি → docs/data/fundamentals.csv

রিপোর্ট অনুযায়ী ফিল্টারগুলো এখান থেকে আসে:
  * Paid-up Capital < ৫০ কোটি টাকা (= ৫০০ মিলিয়ন)  → অপারেটর-ওয়াচলিস্ট
  * P/E > ৪০ → BSEC-র মার্জিন-ঋণ বন্ধ, সতর্কতা

উৎস: DSE-র প্রতিটি কোম্পানির পেজ (displayCompany.php?name=CODE)। এগুলো ধীরে বদলায়, তাই ফাইল ৭ দিনের বেশি পুরনো না হলে আবার আনা হয় না।
পেজের গঠন বদলালে বা কিছু না পেলে সেই কোডের ঘর ফাঁকা থাকে এবং পুরনো মান (থাকলে) রেখে দেওয়া হয়। হাতে ঠিক করতে চাইলে
docs/data/fundamentals_manual.csv (SYMBOL,PAIDUP_MN,PE,CATEGORY) বানান; সেটি সবসময় অগ্রাধিকার পায়।

চালাতে: python scripts/update_fundamentals.py [--force] [--codes GP,BATBC] [--max-age-days 7]
"""
import argparse, csv, os, re, sys, time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from update_data import BASES, DATA_DIR, TableParser, http_get, log  # noqa: E402

FUND_PATH = os.path.join(DATA_DIR, 'fundamentals.csv')
FIELDS = ['SYMBOL', 'PAIDUP_MN', 'PE', 'CATEGORY', 'FETCHED']
NUM = re.compile(r'^-?[\d,]*\.?\d+$')


def num(s):
    s = (s or '').strip().replace(',', '')
    return float(s) if NUM.match(s) else None


def find_value(tables, label_re, numeric=True):
    """যেকোনো টেবিলে লেবেল-সেল খুঁজে তার ডানের সেল (না হলে ঠিক নিচের সারির একই কলামের সেল) থেকে মান নেয়।"""
    rx = re.compile(label_re, re.I)
    for rows in tables:
        for ri, r in enumerate(rows):
            for j, cell in enumerate(r):
                if not rx.search(cell):
                    continue
                cands = []
                if j + 1 < len(r):
                    cands.append(r[j + 1])
                if ri + 1 < len(rows) and j < len(rows[ri + 1]):
                    cands.append(rows[ri + 1][j])
                for v in cands:
                    if not numeric:
                        if v and not rx.search(v):
                            return v.strip()
                    elif num(v) is not None:
                        return num(v)
    return None


def parse_company(html):
    p = TableParser()
    p.feed(html)
    t = p.tables
    paid = find_value(t, r'paid[\s-]*up\s*capital')
    pe = find_value(t, r'(^|\b)p\s*/\s*e(\s*ratio)?\b')
    cat = find_value(t, r'market\s*category', numeric=False)
    return {'PAIDUP_MN': paid, 'PE': pe, 'CATEGORY': (cat or '')[:3]}


def load_existing():
    out = {}
    if os.path.exists(FUND_PATH):
        with open(FUND_PATH, newline='', encoding='utf-8') as f:
            for r in csv.DictReader(f):
                out[r['SYMBOL']] = r
    return out


def save(rows):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(FUND_PATH, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for k in sorted(rows):
            w.writerow({x: rows[k].get(x, '') for x in FIELDS})


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument('--force', action='store_true')
    a.add_argument('--codes', default='')
    a.add_argument('--max-age-days', type=float, default=7)
    a.add_argument('--sleep', type=float, default=0.6)
    a = a.parse_args()
    if not a.force and os.path.exists(FUND_PATH) and not a.codes:
        age = (time.time() - os.path.getmtime(FUND_PATH)) / 86400
        if age < a.max_age_days:
            log(f'fundamentals.csv মাত্র {age:.1f} দিনের পুরনো; আবার আনা হচ্ছে না (--force দিলে আনবে)')
            return 0
    if a.codes:
        codes = [c.strip().upper() for c in a.codes.split(',') if c.strip()]
    else:
        pr = os.path.join(DATA_DIR, 'prices.csv')
        with open(pr, newline='', encoding='utf-8') as f:
            last = None
            codes = set()
            rows = list(csv.DictReader(f))
        last = max(r['DATE'] for r in rows)
        codes = sorted({r['TRADING CODE'] for r in rows if r['DATE'] == last})
    old = load_existing()
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    ok = fail = 0
    for i, code in enumerate(codes, 1):
        got = None
        for base in BASES:
            try:
                got = parse_company(http_get(f'{base}/displayCompany.php?name={code}', retries=2))
                break
            except Exception as e:
                err = e
        if got is None:
            fail += 1
            log(f'[{i}/{len(codes)}] {code}: ব্যর্থ ({err})')
        else:
            prev = old.get(code, {})
            rec = {'SYMBOL': code, 'FETCHED': now,
                   'PAIDUP_MN': got['PAIDUP_MN'] if got['PAIDUP_MN'] is not None else prev.get('PAIDUP_MN', ''),
                   'PE': got['PE'] if got['PE'] is not None else prev.get('PE', ''),
                   'CATEGORY': got['CATEGORY'] or prev.get('CATEGORY', '')}
            old[code] = rec
            ok += 1
            if got['PAIDUP_MN'] is None:
                log(f'[{i}/{len(codes)}] {code}: Paid-up পাওয়া যায়নি (পেজের গঠন বদলাতে পারে)')
        if i % 50 == 0:
            save(old)
        time.sleep(a.sleep)
    save(old)
    log(f'সংরক্ষিত: {len(old)} কোড (এবার সফল {ok}, ব্যর্থ {fail})')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
