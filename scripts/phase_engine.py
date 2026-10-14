"""
সরল ফেজ ইঞ্জিন: শুধু দাম, ভলিউম আর মুভিং এভারেজ (SMA20/50/100)। আর কোনো ইন্ডিকেটর নেই।

ছয়টি ফেজ:
  Accumulation    : আগে নামার পর সাইডওয়ে রেঞ্জ, ভলিউম কেনার দিকে (আপ-ডে ভলিউম > ডাউন-ডে ভলিউম)
  Markup          : MA সাজানো ঊর্ধ্বমুখী (দাম > SMA20 > SMA50, SMA50 ওঠা), ভলিউম কেনার দিকে
  Re-accumulation : আগে ওঠার পর সাইডওয়ে বিরতি, ভলিউম এখনও কেনার দিকে
  Distribution    : আগে ওঠার পর সাইডওয়ে রেঞ্জ, ভলিউম বেচার দিকে
  Markdown        : MA সাজানো নিম্নমুখী (দাম < SMA20 < SMA50, SMA50 নামা), ভলিউম বেচার দিকে
  Re-distribution : আগে নামার পর সাইডওয়ে বাউন্স, ভলিউম বেচার দিকে

প্রতিটি সিদ্ধান্ত শুধু সেই দিন পর্যন্ত ডেটা দেখে নেওয়া হয় (ভবিষ্যৎ দেখা নেই), তাই একই কোডে আজকের স্ক্যান আর ব্যাকটেস্ট দুটোই চলে।
"""
from dataclasses import dataclass, asdict
import numpy as np
import pandas as pd

PHASES = ["Accumulation", "Markup", "Re-accumulation", "Distribution", "Markdown", "Re-distribution"]
BULL = {"Accumulation", "Markup", "Re-accumulation"}
BEAR = {"Distribution", "Markdown", "Re-distribution"}


@dataclass
class Cfg:
    win: int = 40               # রেঞ্জ মাপার দিন
    prior: int = 60             # রেঞ্জের আগের ট্রেন্ড মাপার দিন
    prior_pct: float = 0.10     # আগের ট্রেন্ড কমপক্ষে এত % হলে "ওঠা/নামা" ধরা হয় (ব্যাকটেস্টে TRAIN অংশ দেখে বাছা)
    max_width: float = 0.20     # রেঞ্জের প্রস্থ (উচ্চ−নিম্ন ÷ মধ্য) সর্বোচ্চ (TRAIN দেখে বাছা)
    vb_min: float = 0.0         # ভলিউম-ব্যালান্স সীমা: (আপ−ডাউন)÷(আপ+ডাউন), বুলিশে ≥ এটি, বেয়ারিশে ≤ −এটি
    slope_min: float = 0.005    # Markup/Markdown-এ SMA50-এর ১০ দিনের ঢাল সর্বনিম্ন
    min_score: int = 0          # এর নিচের স্কোরের ফেজ "অনির্দিষ্ট" ধরা হয় (পেজে ০: সব শেয়ার ফেজ পায়, স্কোরে সাজানো)
    strong_score: int = 65      # স্কোর এর ওপরে হলে "শক্তিশালী" চিহ্ন (ব্যাকটেস্টে TRAIN দেখে বাছা সীমা)
    min_value: float = 3e6      # ২০ দিনের গড় দৈনিক লেনদেন (টাকা): এর নিচে অলিকুইড
    max_zero_days: int = 4      # শেষ ৪০ দিনে ভলিউম-শূন্য দিন সর্বোচ্চ কয়টি


def clean(df):
    """ট্রেড-না-হওয়া দিনে OPEN খালি থাকে: ওপেন = আগের ক্লোজ ধরা হয়, High/Low ওপেন-ক্লোজ ছুঁতে বাধ্য।"""
    df = df.sort_values("date").reset_index(drop=True).copy()
    df["open"] = df["open"].fillna(df["close"].shift()).fillna(df["close"])
    df["high"] = df[["high", "open", "close"]].max(axis=1)
    df["low"] = df[["low", "open", "close"]].min(axis=1)
    df["volume"] = df["volume"].fillna(0)
    return df


def base_features(df, win=40, prior=60):
    """একটি কোডের প্রতিটি দিনের জন্য কাঁচা বৈশিষ্ট্য (সবই ট্রেইলিং, ভবিষ্যৎ ছাড়া)।"""
    df = clean(df)
    c, v = df["close"], df["volume"]
    pc = c.shift()
    f = pd.DataFrame({"date": df["date"], "open": df["open"], "close": c, "volume": v, "chg": (c / pc - 1) * 100})
    f["sma20"] = c.rolling(20).mean()
    f["sma50"] = c.rolling(50).mean()
    f["sma100"] = c.rolling(100).mean()
    f["slope"] = f["sma50"] / f["sma50"].shift(10) - 1
    f["hi"] = df["high"].rolling(win).max()
    f["lo"] = df["low"].rolling(win).min()
    mid = (f["hi"] + f["lo"]) / 2
    f["width"] = (f["hi"] - f["lo"]) / mid
    f["drift"] = (c / c.shift(win - 1) - 1).abs()
    f["pos"] = (c - f["lo"]) / (f["hi"] - f["lo"]).replace(0, np.nan)
    f["prior_ret"] = c.shift(win) / c.shift(win + prior) - 1
    up = v.where(c > pc, 0).rolling(20).sum()
    dn = v.where(c < pc, 0).rolling(20).sum()
    f["vb"] = ((up - dn) / (up + dn).replace(0, np.nan))
    f["vratio"] = v.rolling(20).mean() / v.rolling(60).mean().replace(0, np.nan)
    f["value20"] = (c * v).rolling(20).mean()
    f["zero_days"] = (v == 0).astype(int).rolling(win).sum()
    f["sma20_up"] = f["sma20"] >= f["sma20"].shift(5)
    return f


def classify(F, cfg=Cfg()):
    """প্যানেল (সব কোড একসঙ্গে) নিয়ে phase, score, days_in_phase, liquid কলাম যোগ করে ফেরত দেয়।"""
    F = F.copy()
    ok = F[["sma100", "vb", "width", "drift", "prior_ret", "slope", "vratio"]].notna().all(axis=1)
    is_range = (F["width"] <= cfg.max_width) & (F["drift"] <= 0.5 * F["width"])
    prior_dir = np.where(F["prior_ret"] >= cfg.prior_pct, 1,
                np.where(F["prior_ret"] <= -cfg.prior_pct, -1,
                np.where(F["sma50"] > F["sma100"], 1, -1)))
    up_trend = (F["close"] > F["sma20"]) & (F["sma20"] > F["sma50"]) & (F["slope"] > cfg.slope_min) & ~is_range
    dn_trend = (F["close"] < F["sma20"]) & (F["sma20"] < F["sma50"]) & (F["slope"] < -cfg.slope_min) & ~is_range
    bull_vol = F["vb"] > cfg.vb_min
    bear_vol = F["vb"] < -cfg.vb_min

    ph = pd.Series(None, index=F.index, dtype=object)
    ph[ok & up_trend & bull_vol] = "Markup"
    ph[ok & dn_trend & bear_vol] = "Markdown"
    r = ok & is_range & ph.isna()
    ph[r & (prior_dir == -1) & bull_vol] = "Accumulation"
    ph[r & (prior_dir == -1) & ~bull_vol] = "Re-distribution"
    ph[r & (prior_dir == 1) & ~bear_vol] = "Re-accumulation"
    ph[r & (prior_dir == 1) & bear_vol] = "Distribution"

    # ---- স্কোর (০–১০০): ফেজটা কতটা স্পষ্ট ----
    bull = ph.isin(BULL)
    sgn = np.where(bull, 1.0, -1.0)
    vb_s = np.clip(F["vb"].abs() / 0.5, 0, 1) * 30                     # ভলিউমের একমুখিতা
    ma_bull = (F["close"] > F["sma20"]) * 10 + (F["close"] > F["sma50"]) * 10 + (F["sma20"] > F["sma50"]) * 10
    ma_bear = (F["close"] < F["sma20"]) * 10 + (F["close"] < F["sma50"]) * 10 + (F["sma20"] < F["sma50"]) * 10
    ma_s = np.where(bull, ma_bull, ma_bear)                              # MA-র সাজানো
    flat = 1 - (F["drift"] / (0.5 * F["width"]).replace(0, np.nan)).clip(0, 1)
    tight = 1 - (F["width"] / cfg.max_width).clip(0, 1)
    shape_range = (0.6 * flat + 0.4 * tight).fillna(0) * 20              # রেঞ্জ কতটা পরিষ্কার
    shape_trend = (F["slope"].abs() / 0.05).clip(0, 1) * 20              # ট্রেন্ডের ঢাল
    shape = np.where(ph.isin(["Markup", "Markdown"]), shape_trend, shape_range)
    contr = np.where(ph.isin(["Accumulation", "Re-accumulation"]), (F["vratio"] < 1.0),
            np.where(ph.isin(["Distribution", "Re-distribution"]), (F["vratio"] > 1.0),
                     F["vratio"] > 1.0)) * 10                            # ভলিউমের আচরণ
    score = (vb_s + ma_s + shape + contr).fillna(0)
    # বাকি ১০ পয়েন্ট: একই ফেজে টানা কত দিন (নিচে)
    F["phase"], F["score_raw"] = ph, score

    # টানা কত দিন একই ফেজে: কোড ধরে রান-লেংথ
    def runlen(s):
        key = s.fillna("∅")
        grp = (key != key.shift()).cumsum()
        return key.groupby(grp).cumcount() + 1
    F["days"] = F.groupby("code", group_keys=False)["phase"].apply(runlen)
    F["score"] = (F["score_raw"] + np.minimum(F["days"], 10)).round().clip(0, 100)
    F.loc[F["phase"].isna(), ["score", "days"]] = [0, 0]
    if cfg.min_score:
        weak = F["score"] < cfg.min_score
        F.loc[weak, "phase"] = None
        F.loc[weak, ["score", "days"]] = [0, 0]
    F["liquid"] = (F["value20"] >= cfg.min_value) & (F["zero_days"] <= cfg.max_zero_days)
    return F


def build_panel(prices, win=40, prior=60, cost=0.005, horizons=(10, 20, 40)):
    """prices: কলাম date, code, open, high, low, close, volume। সব কোডের বৈশিষ্ট্য + ভবিষ্যৎ রিটার্ন (শুধু ব্যাকটেস্টের জন্য)।"""
    parts = []
    for code, g in prices.groupby("code", sort=True):
        if len(g) < 120:
            continue
        f = base_features(g, win, prior)
        f.insert(1, "code", code)
        entry = f["open"].shift(-1)                           # পরদিনের OPEN-এ ঢোকা
        for h in horizons:
            f[f"r{h}"] = f["close"].shift(-h) / entry - 1 - cost
        parts.append(f)
    return pd.concat(parts, ignore_index=True)


def load_prices(path):
    d = pd.read_csv(path)
    d = d.rename(columns={"DATE": "date", "TRADING CODE": "code", "OPENP": "open", "HIGH": "high",
                          "LOW": "low", "CLOSEP": "close", "VOLUME": "volume"})
    d = d.drop(columns=["YCP"], errors="ignore")
    for k in ("open", "high", "low", "close", "volume"):
        d[k] = pd.to_numeric(d[k], errors="coerce")
    d = d[d["close"] > 0]
    return d


def cfg_dict(cfg):
    return asdict(cfg)
