"""
বাইং/সেলিং প্রেসার ইঞ্জিন — শুধু দৈনিক দাম-ভলিউম (OHLCV + YCP) থেকে, প্রতিটি সিদ্ধান্ত সেই দিন পর্যন্ত ডেটা দেখে।

ধারণা (ওয়াইকফের "Effort vs Result"): ভলিউম = প্রচেষ্টা, দামের চলন ও ক্লোজের অবস্থান = ফল।
  ১. ফ্লো      দিনের ক্লোজ রেঞ্জের কোথায় (CLV = ((C−L) − (H−C)) ÷ (H−L)) × ভলিউম; ৩ ও ১০ দিনে ভলিউম-ভারিত গড়, −১..+১
  ২. ভলিউম-ব্যালান্স  YCP-র ওপরে বন্ধ হওয়া দিনের ভলিউম বনাম নিচে বন্ধ হওয়া দিনের ভলিউম (১০ দিন), −১..+১
  ৩. শোষণ (absorption)  উচ্চ VR কিন্তু দাম প্রায় নড়েনি: ক্লোজ ওপরের দিকে = কেউ চুপচাপ কিনছে (+), নিচের দিকে = চুপচাপ বেচছে (−)
  রেঞ্জ-লক (H = L) দিনে: YCP-র ওপরে = ক্রেতার লাইন (+১), নিচে = বিক্রেতার লাইন (−১); ভলিউম ০ = কোনো চাপ নেই।

BP (বাইং চাপ) ও SP (সেলিং চাপ) আলাদা ০–১০০; পার্থক্য (BP − SP) থেকে তিন অবস্থা:
  বাইং হাই / সেলিং লো · সেলিং হাই / বাইং লো · নিউট্রাল
প্রেসার স্কোর = ৫০ + (BP − SP) ÷ ২ (০–১০০; ৫০ = ভারসাম্য)।

"নাগালের বাইরে" = ইতিমধ্যে এত দূর গেছে যে আজকের ক্লোজে ঢোকা মানে পিছু ধাওয়া (আপার-সার্কিট দিন, ৩ দিনে ≥ ১২%, ৫ দিনে ≥ ১৮%, SMA20-র ২৫% ওপরে; নিচের দিকে একই সীমা উল্টো)।
সীমাগুলো ও ওজন আমাদের অপারেশনাল সংজ্ঞা; ব্যাকটেস্টের ফল দেখে বদলানো হয়নি।
"""
from dataclasses import dataclass, asdict
import glob
import os
import numpy as np
import pandas as pd


@dataclass
class PCfg:
    w_flow: float = 0.45
    w_bal: float = 0.35
    w_abs: float = 0.20
    flow_full: float = 0.5        # ফ্লো ±০.৫ = পূর্ণ স্কোর
    bal_full: float = 0.5
    abs_full: float = 0.3
    state_gap: float = 15.0       # |BP − SP| ≥ এটি হলে একদিকে ঝুঁকে আছে, নইলে নিউট্রাল
    abs_vr_full: float = 2.5      # VR ≥ ২.৫ = পূর্ণ "প্রচেষ্টা"
    atr_n: int = 14
    # নাগালের বাইরে
    uc_pct: float = 9.5
    ext3: float = 0.12
    ext5: float = 0.18
    ext_sma20: float = 0.25
    # হল্ট/নিষ্ক্রিয়তা
    idle_long: int = 5            # টানা এতদিন ভলিউম ০ = দীর্ঘ নিষ্ক্রিয়


def load_prices_ycp(root):
    """ইতিহাস/ + docs/data/prices.csv (বর্তমান অগ্রাধিকার পায়); YCP সহ।"""
    paths = sorted(glob.glob(os.path.join(root, "history", "*.csv")))
    cur = os.path.join(root, "docs", "data", "prices.csv")
    if os.path.exists(cur):
        paths.append(cur)
    frames = []
    for p in paths:
        d = pd.read_csv(p)
        d = d.rename(columns={"DATE": "date", "TRADING CODE": "code", "OPENP": "open", "HIGH": "high", "LOW": "low",
                              "CLOSEP": "close", "YCP": "ycp", "VOLUME": "volume"})
        if "ycp" not in d.columns:
            d["ycp"] = np.nan
        for k in ("open", "high", "low", "close", "ycp", "volume"):
            d[k] = pd.to_numeric(d[k], errors="coerce")
        frames.append(d[["date", "code", "open", "high", "low", "close", "ycp", "volume"]])
    d = pd.concat(frames, ignore_index=True)
    d = d[d["close"] > 0]
    d["date"] = d["date"].astype(str).str.strip()
    d["code"] = d["code"].astype(str).str.strip().str.upper()
    d = d.drop_duplicates(subset=["date", "code"], keep="last")
    return d.sort_values(["code", "date"]).reset_index(drop=True)


def _one(g, cfg):
    g = g.sort_values("date").reset_index(drop=True)
    c = g["close"]
    v = g["volume"].fillna(0)
    h = g[["high", "close"]].max(axis=1)
    l = g[["low", "close"]].min(axis=1)
    o = g["open"].fillna(c.shift()).fillna(c)
    h, l = pd.concat([h, o], axis=1).max(axis=1), pd.concat([l, o], axis=1).min(axis=1)
    pc = g["ycp"].where(g["ycp"] > 0, c.shift())              # YCP না থাকলে আগের ক্লোজ
    pc = pc.fillna(c.shift())
    f = pd.DataFrame({"date": g["date"], "code": g["code"], "close": c, "high": h, "low": l, "volume": v})
    f["chg"] = (c / pc - 1) * 100
    rng = (h - l)
    clv = np.where(rng > 0, ((c - l) - (h - c)) / rng.where(rng > 0, 1), np.sign(c - pc))
    clv = np.where(v > 0, clv, 0.0)                           # ভলিউম ০ = কোনো চাপ নেই
    f["clv"] = clv
    mf = pd.Series(clv, index=g.index) * v
    # উইন্ডোতে মোট ভলিউম ০ (বা দাম অপরিবর্তিত) = চাপ ০, অনির্ধারিত নয়; শুধু ইতিহাস কম থাকলে (উইন্ডো পূর্ণ নয়) NaN
    def _ratio(num, den):
        r = num / den.replace(0, np.nan)
        return r.where(den.isna(), r.fillna(0.0))
    f["flow3"] = _ratio(mf.rolling(3).sum(), v.rolling(3).sum())
    f["flow10"] = _ratio(mf.rolling(10).sum(), v.rolling(10).sum())
    up = v.where(c > pc, 0).rolling(10).sum()
    dn = v.where(c < pc, 0).rolling(10).sum()
    f["bal10"] = _ratio(up - dn, up + dn)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    atr = tr.rolling(cfg.atr_n).mean()
    vr = v / v.shift(1).rolling(20).mean().replace(0, np.nan)
    f["vr"] = vr
    effort = np.clip(vr / cfg.abs_vr_full, 0, 1)
    result = 1 - np.clip((c - pc).abs() / atr.replace(0, np.nan), 0, 1)
    ab_day = (effort * result * pd.Series(clv, index=g.index)).fillna(0)
    f["abs3"] = ab_day.rolling(3).mean()
    # নাগালের হিসাব
    f["ret3"] = c / c.shift(3) - 1
    f["ret5"] = c / c.shift(5) - 1
    f["sma20"] = c.rolling(20).mean()
    f["dev20"] = c / f["sma20"] - 1
    f["lock_up"] = (rng == 0) & (v > 0) & (c > pc) & (f["chg"] >= cfg.uc_pct)
    f["lock_dn"] = (rng == 0) & (v > 0) & (c < pc) & (f["chg"] <= -cfg.uc_pct)
    f["value20"] = (c * v).rolling(20).mean()
    f["zero_days"] = (v == 0).astype(int).rolling(40).sum()
    zero = (v == 0).to_numpy()
    streak = np.zeros(len(zero), dtype=int)
    for i in range(len(zero)):
        streak[i] = (streak[i - 1] + 1 if i else 1) if zero[i] else 0
    f["idle"] = streak
    return f


def pressure_panel(prices, cfg=PCfg()):
    parts = [_one(g, cfg) for _, g in prices.groupby("code", sort=True) if len(g) >= 40]
    F = pd.concat(parts, ignore_index=True)
    return score(F, cfg)


def score(F, cfg=PCfg()):
    F = F.copy()
    flow = 0.5 * F["flow3"] + 0.5 * F["flow10"]
    bal, ab = F["bal10"], F["abs3"]
    comp = lambda x, full, sgn: np.clip((x * sgn).clip(lower=0) / full, 0, 1)
    F["bp"] = (100 * (cfg.w_flow * comp(flow, cfg.flow_full, 1) + cfg.w_bal * comp(bal, cfg.bal_full, 1) + cfg.w_abs * comp(ab, cfg.abs_full, 1)))
    F["sp"] = (100 * (cfg.w_flow * comp(flow, cfg.flow_full, -1) + cfg.w_bal * comp(bal, cfg.bal_full, -1) + cfg.w_abs * comp(ab, cfg.abs_full, -1)))
    valid = F[["flow3", "flow10", "bal10", "abs3"]].notna().all(axis=1) & (F["volume"] > 0)    # আজ ট্রেড না হলে আজকের চাপ মাপা যায় না
    F.loc[~valid, ["bp", "sp"]] = np.nan
    F["ps"] = (50 + (F["bp"] - F["sp"]) / 2).clip(0, 100)           # প্রেসার স্কোর ০–১০০ (৫০ = ভারসাম্য)
    gap = F["bp"] - F["sp"]
    F["state"] = np.select([gap >= cfg.state_gap, gap <= -cfg.state_gap], ["buy", "sell"], default="neutral")
    F.loc[~valid, "state"] = ""
    up_gone = (F["chg"] >= cfg.uc_pct) | F["lock_up"] | (F["ret3"] >= cfg.ext3) | (F["ret5"] >= cfg.ext5) | (F["dev20"] >= cfg.ext_sma20)
    dn_gone = F["lock_dn"] | (F["chg"] <= -cfg.uc_pct) | (F["ret3"] <= -cfg.ext3) | (F["ret5"] <= -cfg.ext5) | (F["dev20"] <= -cfg.ext_sma20)
    F["gone"] = np.select([up_gone, dn_gone], ["up", "dn"], default="")
    F["liquid"] = (F["value20"] >= 3e6) & (F["zero_days"] <= 4)
    return F


def pressure_latest(prices, cfg=PCfg(), tail=150):
    """দৈনিক স্ক্যানের জন্য: প্রতি কোডের শুধু শেষ ~tail দিন নিয়ে গণনা, শেষ সারি ফেরত।
    (সব রোলিং উইন্ডো ≤ ৪০ দিন, তাই tail=150 পুরো ইতিহাসের সমান ফল দেয়।)"""
    P = pressure_panel(prices.groupby("code", sort=True, group_keys=False).tail(tail), cfg)
    return P.sort_values(["code", "date"]).groupby("code").tail(1).set_index("code")


def pcfg_dict(cfg):
    return asdict(cfg)
