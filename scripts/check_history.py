#!/usr/bin/env python3
"""history/*.csv ফাইলগুলো যাচাই করে (কিছু বদলায় না)।

চালান:  python scripts/check_history.py
ভুল পেলে exit code 1 দেয়, তাই Actions-এও ব্যবহার করা যায়।
"""
import glob
import os
import re
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQUIRED = ["DATE", "TRADING CODE", "OPENP", "HIGH", "LOW", "CLOSEP", "YCP", "VOLUME"]
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def main():
    files = sorted(glob.glob(os.path.join(ROOT, "history", "*.csv")))
    if not files:
        print("history/ ফোল্ডারে কোনো CSV নেই")
        return 0

    errors, warnings = [], []
    frames = []
    for path in files:
        name = os.path.basename(path)
        try:
            d = pd.read_csv(path)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: পড়া যায়নি ({e})")
            continue
        d.columns = [str(c).strip() for c in d.columns]
        missing = [c for c in REQUIRED if c not in d.columns]
        if missing:
            errors.append(f"{name}: কলাম নেই {missing} (আছে: {list(d.columns)})")
            continue
        dates = d["DATE"].astype(str).str.strip()
        bad = dates[~dates.str.match(ISO)]
        if len(bad):
            errors.append(f"{name}: {len(bad)}টি তারিখ YYYY-MM-DD নয়, যেমন {bad.iloc[0]!r}")
            continue
        close = pd.to_numeric(d["CLOSEP"], errors="coerce")
        if (close.fillna(0) <= 0).mean() > 0.2:
            warnings.append(f"{name}: ২০%-এর বেশি সারিতে CLOSEP ০ বা ফাঁকা (এগুলো বাদ যাবে)")
        d = d.assign(DATE=dates, CODE=d["TRADING CODE"].astype(str).str.strip().str.upper(), _file=name)
        print(f"{name}: {len(d):>7} সারি, {d['DATE'].min()} → {d['DATE'].max()}, {d['CODE'].nunique()} কোড")
        frames.append(d)

    if frames:
        all_h = pd.concat(frames, ignore_index=True)
        dup = all_h.duplicated(subset=["DATE", "CODE"], keep=False)
        if dup.any():
            warnings.append(f"history-র ভেতরেই {int(dup.sum())}টি ডুপ্লিকেট (DATE, CODE) আছে — শেষেরটি রাখা হবে")
        cur_path = os.path.join(ROOT, "docs", "data", "prices.csv")
        if os.path.exists(cur_path):
            cur = pd.read_csv(cur_path)
            cmin = str(cur["DATE"].min())
            hmax = all_h["DATE"].max()
            print(f"বর্তমান prices.csv শুরু: {cmin}; history শেষ: {hmax}")
            if hmax < cmin:
                gap = (pd.to_datetime(cmin) - pd.to_datetime(hmax)).days
                if gap > 7:
                    warnings.append(f"history শেষ ({hmax}) ও prices.csv শুরু ({cmin})-র মাঝে {gap} দিনের ফাঁক")

    for w in warnings:
        print("সতর্কতা:", w)
    for e in errors:
        print("ভুল:", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
