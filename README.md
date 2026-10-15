# সিম্পল স্ক্যানার (DSE) — অপারেটর-প্রবণতা স্ক্যানার

গবেষণা-রিপোর্ট "বাংলাদেশের শেয়ার বাজারে অপারেটর-চালিত প্রবণতা বিশ্লেষণ ও ট্রেন্ড ট্রেডিং কৌশল"-এর সূত্র ও লজিক অনুযায়ী। পেজ: `docs/index.html` (GitHub Pages)।

ট্যাব: **এন্ট্রি-যোগ্য সেটআপ** · Phase A · B · C · D · E · Distribution · Markdown · **অপারেটর ওয়াচ** · মোট। প্রতি ট্যাবে স্কোর বেশি থেকে কম ক্রমে (সেটআপ ট্যাবে RRR অনুযায়ী)।

## রিপোর্টের কোন অংশ কোথায়
| রিপোর্ট | বাস্তবায়ন |
|---|---|
| ভলিউম রেশিও `VR = V_t ÷ গড়(V_{t-1..t-20})`, VR ≥ ২.৫ | `phase_engine.py` → `vr` |
| VR ≥ ২.৫ + ছোট বডি + সংকুচিত ATR (Volatility Squeeze) | `e_stealth` (বডি ≤ ০.৫×ATR14, ATR14 ÷ ৬০ দিনের গড় ≤ ০.৮৫ — এই দুই সংখ্যা আমাদের) |
| ওয়াইকফ Phase A (SC), B, C (স্প্রিং), D (SOS/LPS), E; Distribution (BC/UTAD/SOW); Markdown | `classify()` |
| সুইং, BOS, CHOCH, অর্ডার ব্লক, FVG, ০.৫–০.৬১৮ ফিবো মিটিগেশন জোন | `smc_structure()` |
| ব্রেকআউট/আপার-সার্কিটের দিনে কেনা নয়, CHOCH-এর পর প্রথম রিট্রেসে কম ভলিউমে এন্ট্রি | `smc_entry`, `lps`, `not_chase` |
| `RRR = (P_target − P_entry) ÷ (P_entry − P_stop)`, ন্যূনতম ১:৩ | `rrr`, `setup` |
| স্টপ = স্প্রিং লো-র ০.৫% নিচে; পজিশন C ৩০%, D ৭০%, E ১০০% হোল্ড, Distribution ০% | `stop`, `alloc` |
| Paid-up < ৫০ কোটি = ওয়াচলিস্ট; P/E > ৪০ = মার্জিন বন্ধ সতর্কতা; সার্কিট ±১০% | `update_fundamentals.py`, `lowcap`, `pe_high`, `uc` |

রিপোর্টে যে সীমার সংখ্যা নেই (রেঞ্জ প্রস্থ, স্প্রিংয়ের গভীরতা, SOS-এর ভলিউম ইত্যাদি) সেগুলো `Cfg`-এ আছে ও পেজের "রিপোর্টের সূত্র ও নিয়ম" অংশে লেখা। এগুলো ব্যাকটেস্টে টিউন করা হয়নি।

## ফাইল
- `scripts/update_data.py` — DSE থেকে দৈনিক ডেটা (`docs/data/prices.csv`)
- `scripts/update_fundamentals.py` — Paid-up ও P/E (`docs/data/fundamentals.csv`, সপ্তাহে একবার); হাতে দিতে চাইলে `docs/data/fundamentals_manual.csv` (`SYMBOL,PAIDUP_MN,PE,CATEGORY`), এটি অগ্রাধিকার পায়
- `scripts/phase_engine.py` — সব নিয়ম (ব্যাকটেস্ট ও দৈনিক স্ক্যান একই কোড, ভবিষ্যৎ দেখে না)
- `scripts/compute_phases.py` — আজকের ফেজ/প্ল্যান → `docs/data/phases.json`
- `tools/backtest.py` — রিপোর্টের নিয়ম যেমন আছে তেমন ব্যাকটেস্ট + সেটআপের ট্রেড-সিমুলেশন → `docs/data/backtest.json`
- `.github/workflows/update.yml` — Sun–Thu বাজার বন্ধের পর দিনে কয়েকবার অটো আপডেট

## হাতে চালানো
```
python scripts/update_data.py
python scripts/update_fundamentals.py     # Paid-up, P/E
python -I scripts/compute_phases.py
python -I tools/backtest.py               # ~১০ সেকেন্ড
python tests/test_update_data.py
python tests/test_phase_engine.py
```

> শিক্ষামূলক টুল, বিনিয়োগ পরামর্শ নয়। ব্যাকটেস্টের সৎ ফল পেজের নিচে আছে; ১৩ বছরের ডেটায় অধিকাংশ ফেজে টেকসই সুবিধা দেখা যায়নি।
