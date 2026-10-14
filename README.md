# সিম্পল স্ক্যানার (DSE)

শুধু **দাম, ভলিউম ও মুভিং এভারেজ (SMA20/50/100)** দিয়ে প্রতিটি শেয়ারের ছয় ওয়াইকফ ফেজ নির্ধারণ: Accumulation, Markup, Re-accumulation, Distribution, Markdown, Re-distribution। পেজ: `docs/index.html` (GitHub Pages)। ৬টি ফেজ-ট্যাব + একটি "মোট" ট্যাব; প্রতি ট্যাবে স্কোর বেশি থেকে কম ক্রমে।

## ফাইল
- `scripts/update_data.py` — DSE থেকে দৈনিক ডেটা (`docs/data/prices.csv`, সর্বোচ্চ ৫৬০ ট্রেডিং-দিন ≈ ২ বছর ২ মাস)
- `scripts/phase_engine.py` — ফেজের নিয়ম ও স্কোর (ব্যাকটেস্ট ও দৈনিক স্ক্যান একই কোড)
- `scripts/compute_phases.py` — আজকের ফেজ → `docs/data/phases.json`
- `tools/backtest.py` — walk-forward ব্যাকটেস্ট + থ্রেশহোল্ড বাছাই (train/test) → `docs/data/backtest.json`
- `.github/workflows/update.yml` — Sun–Thu বাজার বন্ধের পর দিনে কয়েকবার অটো আপডেট

## হাতে চালানো
```
python scripts/update_data.py
python -I scripts/compute_phases.py
python -I tools/backtest.py        # ~৩০ সেকেন্ড
python tests/test_update_data.py
```

## ফেজের নিয়ম (সংক্ষেপে)
রেঞ্জ = শেষ ৪০ দিনের প্রস্থ ≤ ২০% ও নেট ড্রিফট কম; আগের ট্রেন্ড = রেঞ্জের আগের ৬০ দিনের রিটার্ন (±১০%); ভলিউম-ব্যালান্স = শেষ ২০ দিনে (আপ-ডে − ডাউন-ডে ভলিউম) ÷ মোট। Markup/Markdown = দাম, SMA20, SMA50 সাজানো + SMA50-এর ঢাল + ভলিউমের দিক; বাকি চারটি রেঞ্জের ভেতরে আগের ট্রেন্ড ও ভলিউমের দিক দেখে।

> শিক্ষামূলক টুল, বিনিয়োগ পরামর্শ নয়। ব্যাকটেস্টের সৎ ফল পেজের নিচে আছে: শুধু Markdown "এড়ানোর" ধারা মোটামুটি টেকসই, বাকিগুলো নিশ্চিত নয়।
