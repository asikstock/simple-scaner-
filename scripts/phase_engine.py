"""
রিপোর্ট-ভিত্তিক ফেজ ইঞ্জিন: "বাংলাদেশের শেয়ার বাজারে অপারেটর-চালিত প্রবণতা বিশ্লেষণ ও ট্রেন্ড ট্রেডিং কৌশল"।

রিপোর্টের সূত্র ও নিয়ম যেভাবে আছে সেভাবে বসানো হয়েছে (কোন সংখ্যা রিপোর্টের, কোনটা আমাদের অপারেশনালাইজেশন, তা নিচে চিহ্নিত):

  ১. ভলিউম রেশিও   VR = V_t / ( (1/N) Σ_{i=1..N} V_{t-i} ),  N = ২০               [রিপোর্ট]
       VR ≥ ২.৫ (২৫০%) + ছোট ক্যান্ডেল-বডি/সংকুচিত ATR (Volatility Squeeze) = গোপন অ্যাকিউমুলেশন সংকেত [রিপোর্ট; "ছোট বডি"/"সংকুচিত"-এর সংখ্যা আমাদের]
  ২. ওয়াইকফ ফেজ   A (SC + এক্সট্রিম ভলিউম), B (কম অস্থিরতা, কম ভলিউম), C (স্প্রিং: লো-ভলিউম ব্রেকডাউন + দ্রুত রিকভারি),
                    D (SOS ভলিউম সহ ব্রেকআউট + LPS রিটেস্ট), E (মার্কআপ: উচ্চ ভলিউম/আপার সার্কিট),
                    Distribution (BC / UTAD / SOW), Markdown                         [রিপোর্ট; সীমাগুলো আমাদের]
  ৩. স্মার্ট মানি   সুইং হাই/লো, BOS, CHOCH, বুলিশ অর্ডার ব্লক (ব্রেকের আগের শেষ ডাউন-ক্যান্ডেল), তিন-ক্যান্ডেল FVG,
                    মিটিগেশন জোন = ০.৫–০.৬১৮ ফিবো / FVG / OB                         [রিপোর্ট]
  ৪. এন্ট্রি নিয়ম  ব্রেকআউট/আপার-সার্কিটের দিন কেনা নয়; CHOCH-এর পর প্রথম রিট্রেসে জোনে ঢুকলে ও ভলিউম কমলে এন্ট্রি [রিপোর্ট]
  ৫. রিস্ক-রিওয়ার্ড RRR = (P_target − P_entry) / (P_entry − P_stop), ন্যূনতম ১:৩ বাধ্যতামূলক      [রিপোর্ট]
       স্টপ = স্প্রিং/সুইপ লো-র ০.৫% নিচে; টার্গেট = রেঞ্জের রেজিস্ট্যান্স/আগের ডিস্ট্রিবিউশন হাই
  ৬. পজিশন সাইজ    Phase C ৩০%, Phase D ৭০%, Phase E ১০০% হোল্ড (নতুন এন্ট্রি নয়), Distribution ০%     [রিপোর্ট]
  ৭. নিয়ন্ত্রক     সার্কিট ±১০% (আপার-সার্কিট দিন চেনা), P/E > ৪০ হলে মার্জিন বন্ধ (সতর্কতা), Paid-up < ৫০ কোটি = ওয়াচলিস্ট [রিপোর্ট]

প্রতিটি সিদ্ধান্ত শুধু সেই দিন পর্যন্ত ডেটা দেখে নেওয়া হয় (সুইং কেবল ৩ দিন পরে নিশ্চিত হয়), তাই আজকের স্ক্যান আর ব্যাকটেস্ট একই কোড।
"""
from dataclasses import dataclass, asdict
import glob
import os
import numpy as np
import pandas as pd

PHASES = ["Phase A", "Phase B", "Phase C", "Phase D", "Phase E", "Distribution", "Markdown"]
BULL = {"Phase A", "Phase B", "Phase C", "Phase D", "Phase E"}
BEAR = {"Distribution", "Markdown"}
ALLOC = {"C": 30, "D": 70, "SMC": 70}          # রিপোর্টের ক্যাপিটাল-এলোকেশন সারণি (SMC = CHOCH-পরবর্তী মিটিগেশন এন্ট্রি, Phase D-র সমতুল্য ধরা)


@dataclass
class Cfg:
    # ---- রিপোর্টের সংখ্যা ----
    vr_n: int = 20               # VR-এর N
    vr_thr: float = 2.5          # VR ≥ ২৫০%
    rrr_min: float = 3.0         # ন্যূনতম ১:৩
    fib_lo: float = 0.5          # মিটিগেশন জোন ০.৫–০.৬১৮
    fib_hi: float = 0.618
    stop_buf: float = 0.005      # স্টপ = স্প্রিং লো-র ০.৫% নিচে
    uc_pct: float = 9.5          # আপার সার্কিট দিন: দৈনিক বৃদ্ধি ≥ ৯.৫% (সার্কিট ১০%, টিক-রাউন্ডিংয়ের জন্য সামান্য কম)
    lowcap_mn: float = 500.0     # Paid-up < ৫০ কোটি টাকা = ৫০০ মিলিয়ন
    pe_limit: float = 40.0       # P/E > ৪০ = মার্জিন বন্ধ
    # ---- রিপোর্টে সংখ্যা নেই, আমাদের অপারেশনাল সংজ্ঞা ----
    atr_n: int = 14
    squeeze_ratio: float = 0.85  # ATR14 ÷ (গত ৬০ দিনের ATR14 গড়) ≤ এটি = সংকুচিত অস্থিরতা
    small_body: float = 0.5      # ক্যান্ডেল বডি ≤ ০.৫ × ATR14 = ছোট বডি
    stealth_win: int = 5         # গোপন-অ্যাকিউমুলেশন সংকেত কতদিন "সাম্প্রতিক"
    win: int = 40                # ট্রেডিং রেঞ্জ মাপার দিন
    gap: int = 6                 # রেঞ্জ থেকে শেষ ৬ দিন বাদ (স্প্রিং/ব্রেকআউট যেন নিজের সাপোর্ট/রেজিস্ট্যান্স না বদলায়)
    max_width: float = 0.25      # রেঞ্জ প্রস্থ (উচ্চ−নিম্ন ÷ মধ্য) সর্বোচ্চ
    prior: int = 60
    prior_pct: float = 0.10      # আগের ট্রেন্ড ±১০%
    dd_pct: float = 0.20         # ১২০ দিনের উচ্চ থেকে ২০% নিচে = "দীর্ঘস্থায়ী পতন"
    swing_k: int = 3             # সুইং হাই/লো: দুই পাশে ৩ দিন
    sc_win: int = 20             # SC-র পর Phase A কতদিন
    sc_dd: float = 0.15
    spring_win: int = 5          # স্প্রিংয়ের পর Phase C কতদিন
    spring_vr_max: float = 1.2   # স্প্রিং-দিনের VR ≤ এটি = লো-ভলিউম
    spring_depth: float = 0.10   # সাপোর্টের ১০%-এর বেশি নিচে গেলে স্প্রিং নয়, ব্রেকডাউন
    sos_vr: float = 1.5          # SOS: ব্রেকআউটে VR ≥ এটি (ভলিউম বৃদ্ধি)
    sos_win: int = 15            # SOS-এর পর Phase D কতদিন
    e_win: int = 60
    e_ext: float = 0.10          # ব্রেকআউট লেভেলের ১০% ওপরে গেলে Phase E
    e_late_ext: float = 0.50     # লেভেলের ৫০% ওপরে বা টানা আপার সার্কিট ≥ ৩ = দেরি/ঝুঁকিপূর্ণ
    dist_win: int = 10
    dist_vr: float = 2.0         # UTAD/SOW-এ "উচ্চ ভলিউম": VR ≥ ২.০
    smc_win: int = 30            # CHOCH-এর পর কতদিন পর্যন্ত মিটিগেশন এন্ট্রি বৈধ
    # ---- তারল্য ----
    min_value: float = 3e6       # ২০ দিনের গড় দৈনিক লেনদেন (টাকা): এর নিচে অলিকুইড
    max_zero_days: int = 4
    strong_score: int = 65


def clean(df):
    """ট্রেড-না-হওয়া দিনে OPEN খালি থাকে: ওপেন = আগের ক্লোজ ধরা হয়, High/Low ওপেন-ক্লোজ ছুঁতে বাধ্য।"""
    df = df.sort_values("date").reset_index(drop=True).copy()
    df["open"] = df["open"].fillna(df["close"].shift()).fillna(df["close"])
    df["high"] = df[["high", "open", "close"]].max(axis=1)
    df["low"] = df[["low", "open", "close"]].min(axis=1)
    df["volume"] = df["volume"].fillna(0)
    return df


# ---------------------------------------------------------------- ইভেন্ট-হেল্পার (সবই ট্রেইলিং)
def _age(flag):
    """সর্বশেষ ইভেন্টের কত দিন আগে (আজ = ০); আগে ইভেন্ট না থাকলে NaN।"""
    n = len(flag)
    out = np.full(n, np.nan)
    last = -1
    for i in range(n):
        if flag[i]:
            last = i
        if last >= 0:
            out[i] = i - last
    return out


def _val_at_last(flag, val, maxage):
    """সর্বশেষ ইভেন্ট-দিনের মান (maxage দিনের মধ্যে), না হলে NaN।"""
    n = len(flag)
    out = np.full(n, np.nan)
    last = -1
    for i in range(n):
        if flag[i]:
            last = i
        if last >= 0 and i - last <= maxage:
            out[i] = val[last]
    return out


def _min_since(flag, low, maxage):
    """ইভেন্টের দিন থেকে আজ পর্যন্ত সর্বনিম্ন low (স্প্রিং লো), maxage দিনের মধ্যে।"""
    n = len(flag)
    out = np.full(n, np.nan)
    cur, last = np.nan, -1
    for i in range(n):
        if flag[i]:
            cur = low[i] if (last < 0 or i - last > maxage) else min(cur, low[i])
            last = i
        elif last >= 0 and i - last <= maxage:
            cur = min(cur, low[i])
        if last >= 0 and i - last <= maxage:
            out[i] = cur
    return out


# ---------------------------------------------------------------- স্মার্ট মানি কাঠামো
def smc_structure(o, h, l, c, k=3):
    """সুইং হাই/লো (দুই পাশে k দিন, k দিন পরে নিশ্চিত), BOS/CHOCH (ক্লোজ দিয়ে ভাঙা), বুলিশ অর্ডার ব্লক, FVG।
    CHOCH(বুলিশ) = বেয়ারিশ কাঠামোতে সর্বশেষ সুইং হাই ক্লোজে ভাঙা। তখন:
      লেগ-লো = ভাঙা সুইং হাইয়ের আগের সুইং হাই থেকে আজ পর্যন্ত সর্বনিম্ন low (স্প্রিং/সুইপ পয়েন্ট),
      OB = ব্রেকের আগের শেষ ডাউন-ক্যান্ডেল (উর্ধ্ব-রানের ঠিক আগে),
      FVG = লেগের ভেতরে সর্বশেষ তিন-ক্যান্ডেল বুলিশ গ্যাপ (low[i] > high[i−2])।
    লেগ বাতিল হয় যদি ক্লোজ লেগ-লো-র নিচে যায় বা বেয়ারিশ CHOCH হয়।"""
    n = len(c)
    nan = np.nan
    out = {k_: np.full(n, nan) for k_ in ("choch_age", "leg_lo", "leg_hi", "ob_lo", "ob_hi", "fvg_lo", "fvg_hi", "last_sl", "last_sh")}
    out["trend"] = np.zeros(n, dtype=int)
    out["leg_ok"] = np.zeros(n, dtype=bool)
    state = 0
    sh = sh_prev = sl = None  # [দাম, ইনডেক্স, ভাঙা-কি-না]
    ch_idx = -1
    llo = lhi = obl = obh = fl = fh = nan
    ok = False
    for t in range(n):
        i = t - k
        if i >= k:
            if h[i] > h[i - k:i].max() and h[i] >= h[i + 1:t + 1].max():
                sh_prev, sh = sh, [h[i], i, False]
            if l[i] < l[i - k:i].min() and l[i] <= l[i + 1:t + 1].min():
                sl = [l[i], i, False]
        if sh is not None and not sh[2] and c[t] > sh[0]:
            sh[2] = True
            if state == -1:                                   # CHOCH (বুলিশ)
                j0 = sh_prev[1] if sh_prev is not None else sh[1]       # ভাঙা সুইং হাইয়ের আগের হাই থেকে: মাঝের সর্বনিম্ন low-ই স্প্রিং/সুইপ পয়েন্ট
                j = j0 + int(np.argmin(l[j0:t + 1]))
                llo, lhi, ch_idx, ok = l[j], h[j:t + 1].max(), t, True
                q = t
                while q >= j and c[q] >= o[q]:
                    q -= 1
                obl, obh = (l[q], h[q]) if q >= j else (nan, nan)
                fl = fh = nan
                for q in range(t, j + 1, -1):
                    if l[q] > h[q - 2]:
                        fl, fh = h[q - 2], l[q]
                        break
            state = 1
        if sl is not None and not sl[2] and c[t] < sl[0]:
            sl[2] = True
            if state == 1:
                ok = False                                    # CHOCH (বেয়ারিশ): বুলিশ লেগ শেষ
            state = -1
        if ok:
            if c[t] < llo:
                ok = False
            else:
                lhi = max(lhi, h[t])
        out["trend"][t] = state
        out["leg_ok"][t] = ok
        if ok:
            out["choch_age"][t] = t - ch_idx
            out["leg_lo"][t], out["leg_hi"][t] = llo, lhi
            out["ob_lo"][t], out["ob_hi"][t], out["fvg_lo"][t], out["fvg_hi"][t] = obl, obh, fl, fh
        if sl is not None:
            out["last_sl"][t] = sl[0]
        if sh is not None:
            out["last_sh"][t] = sh[0]
    return out


# ---------------------------------------------------------------- বৈশিষ্ট্য
def base_features(df, cfg=Cfg()):
    """একটি কোডের প্রতিটি দিনের কাঁচা বৈশিষ্ট্য ও ইভেন্ট (সবই ট্রেইলিং, ভবিষ্যৎ ছাড়া)।"""
    df = clean(df)
    o, h, l, c, v = df["open"], df["high"], df["low"], df["close"], df["volume"]
    pc = c.shift()
    f = pd.DataFrame({"date": df["date"], "open": o, "high": h, "low": l, "close": c, "volume": v, "chg": (c / pc - 1) * 100})
    f["sma20"], f["sma50"], f["sma100"] = c.rolling(20).mean(), c.rolling(50).mean(), c.rolling(100).mean()
    f["ema9"] = c.ewm(span=9, adjust=False).mean()
    f["slope"] = f["sma50"] / f["sma50"].shift(10) - 1

    # --- ATR ও ক্যান্ডেল আকার
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    atr = tr.rolling(cfg.atr_n).mean()
    f["atr"] = atr
    f["atr_ratio"] = atr / atr.rolling(60).mean().replace(0, np.nan)
    body = (c - o).abs()
    f["body_atr"] = body / atr.replace(0, np.nan)
    spread = (h - l).replace(0, np.nan)
    f["close_pos"] = (c - l) / spread
    upper_wick = h - pd.concat([o, c], axis=1).max(axis=1)

    # --- ভলিউম রেশিও: VR = V_t / গড়(V_{t-1..t-N})  (আজকের ভলিউম গড়ে নেই)
    f["vr"] = v / v.shift(1).rolling(cfg.vr_n).mean().replace(0, np.nan)
    f["vr5"] = f["vr"].rolling(5).max()
    f["vdry"] = v.rolling(10).mean() / v.rolling(60).mean().replace(0, np.nan)
    up = v.where(c > pc, 0).rolling(20).sum()
    dn = v.where(c < pc, 0).rolling(20).sum()
    f["vb"] = (up - dn) / (up + dn).replace(0, np.nan)               # ২০ দিনের ভলিউম-ব্যালান্স (সহায়ক)
    f["value20"] = (c * v).rolling(20).mean()
    f["zero_days"] = (v == 0).astype(int).rolling(cfg.win).sum()

    # --- রেঞ্জ (শেষ gap দিন বাদ), প্রসঙ্গ
    f["hi_r"] = h.shift(cfg.gap).rolling(cfg.win).max()
    f["lo_r"] = l.shift(cfg.gap).rolling(cfg.win).min()
    mid = (f["hi_r"] + f["lo_r"]) / 2
    f["width_r"] = (f["hi_r"] - f["lo_r"]) / mid
    f["h120"] = h.rolling(120).max()
    f["dd120"] = c / f["h120"] - 1
    f["prior_ret"] = c.shift(cfg.win) / c.shift(cfg.win + cfg.prior) - 1
    f["uc"] = (f["chg"] >= cfg.uc_pct).astype(int)
    f["uc10"] = f["uc"].rolling(10).sum()
    down_ctx = (f["prior_ret"] <= -cfg.prior_pct) | (f["dd120"] <= -cfg.dd_pct)
    up_ctx = (f["prior_ret"] >= cfg.prior_pct) | ((c >= 0.85 * f["h120"]) & (c >= 1.3 * l.rolling(120).min()))
    f["down_ctx"], f["up_ctx"] = down_ctx, up_ctx
    rng_ok = f["width_r"] <= cfg.max_width

    # --- ইভেন্ট ফ্ল্যাগ
    vr = f["vr"]
    stealth = (vr >= cfg.vr_thr) & (f["body_atr"] <= cfg.small_body) & (f["atr_ratio"] <= cfg.squeeze_ratio)
    sc = (vr >= cfg.vr_thr) & (c < f["sma50"]) & (f["dd120"] <= -cfg.sc_dd) & (l <= l.rolling(60).min() * 1.02)
    spring = ((l < f["lo_r"]) & (l >= f["lo_r"] * (1 - cfg.spring_depth)) & (l.shift() >= f["lo_r"])      # প্রথমবার সাপোর্ট ভাঙা, খুব গভীর নয়
              & (vr <= cfg.spring_vr_max) & down_ctx & rng_ok)
    sos = (c > f["hi_r"]) & (pc <= f["hi_r"]) & (vr >= cfg.sos_vr) & rng_ok & down_ctx     # অ্যাকিউমুলেশন (দীর্ঘ পতনের পর) শেষের ব্রেকআউট
    bc = (vr >= cfg.vr_thr) & (h >= h.shift().rolling(60).max() * 0.98) & (f["close_pos"] <= 0.5) & up_ctx
    utad = (h > f["hi_r"]) & (c <= f["hi_r"]) & (vr >= cfg.dist_vr) & up_ctx
    sow = (((vr >= 2.0) & (upper_wick >= 2 * body) & (f["close_pos"] <= 1 / 3) & up_ctx)
           | ((c < f["lo_r"]) & (vr >= cfg.dist_vr) & up_ctx & rng_ok))
    ev = lambda s: s.fillna(False).to_numpy(dtype=bool)
    for nm, fl_ in (("e_stealth", stealth), ("e_sc", sc), ("e_spring", spring), ("e_sos", sos), ("e_bc", bc), ("e_utad", utad), ("e_sow", sow)):
        f[nm] = ev(fl_)
    ha, la, ca = h.to_numpy(float), l.to_numpy(float), c.to_numpy(float)
    f["stealth_age"] = _age(ev(stealth))
    f["sc_age"] = _age(ev(sc))
    f["sc_low"] = _val_at_last(ev(sc), la, cfg.sc_win)
    f["spr_age"] = _age(ev(spring))
    f["spr_lvl"] = _val_at_last(ev(spring), f["lo_r"].to_numpy(float), cfg.spring_win)
    f["spr_low"] = _min_since(ev(spring), la, cfg.spring_win)
    f["sos_age"] = _age(ev(sos))
    f["sos_lvl"] = _val_at_last(ev(sos), f["hi_r"].to_numpy(float), cfg.e_win)
    d_evt = ev(bc | utad | sow)
    f["dist_age"] = _age(d_evt)
    f["dist_hi"] = _val_at_last(d_evt, ha, cfg.dist_win)

    # --- স্মার্ট মানি কাঠামো
    s = smc_structure(df["open"].to_numpy(float), ha, la, ca, cfg.swing_k)
    for k_, a in s.items():
        f[k_] = a
    return f


def classify(F, cfg=Cfg(), fund=None):
    """প্যানেল (সব কোড একসঙ্গে) নিয়ে ফেজ, স্কোর, ট্রেড-প্ল্যান ইত্যাদি কলাম যোগ করে ফেরত দেয়।
    fund: ঐচ্ছিক DataFrame (code, paidup_mn, pe)। ব্যাকটেস্টে নেই (ঐতিহাসিক Paid-up জানা নেই)।"""
    F = F.copy()
    if fund is not None and len(fund):
        F = F.merge(fund[["code", "paidup_mn", "pe"]], on="code", how="left")
    else:
        F["paidup_mn"], F["pe"] = np.nan, np.nan
    c, buf = F["close"], cfg.stop_buf
    F["lowcap"] = F["paidup_mn"] < cfg.lowcap_mn
    F["pe_high"] = F["pe"] > cfg.pe_limit

    ok = F[["sma100", "vr", "hi_r", "lo_r", "atr_ratio", "prior_ret", "h120", "slope"]].notna().all(axis=1)
    up_trend = (c > F["sma20"]) & (F["sma20"] > F["sma50"]) & (F["slope"] > 0)
    dn_trend = (c < F["sma20"]) & (F["sma20"] < F["sma50"]) & (F["slope"] < 0)
    rng_ok = F["width_r"] <= cfg.max_width
    in_rng = (c >= F["lo_r"] * 0.98) & (c <= F["hi_r"])

    is_dist = (F["dist_age"] <= cfg.dist_win) & (c <= F["dist_hi"])
    is_E = (F["sos_age"] <= cfg.e_win) & (c > F["sos_lvl"] * (1 + cfg.e_ext)) & up_trend
    is_D = (F["sos_age"] <= cfg.sos_win) & (c <= F["sos_lvl"] * (1 + cfg.e_ext)) & (c >= F["sos_lvl"] * 0.97)
    is_C = (F["spr_age"] <= cfg.spring_win) & (c > F["spr_lvl"])
    is_B = rng_ok & in_rng & F["down_ctx"] & (F["atr_ratio"] <= cfg.squeeze_ratio) & (F["vdry"] <= 1.0)
    is_A = (F["sc_age"] <= cfg.sc_win) & (c > F["sc_low"])
    conds = [ok & dn_trend, ok & is_dist, ok & is_E, ok & is_D, ok & is_C, ok & is_B, ok & is_A]
    names = ["Markdown", "Distribution", "Phase E", "Phase D", "Phase C", "Phase B", "Phase A"]
    ph = pd.Series(np.select(conds, names, default=""), index=F.index).replace("", None)
    F["phase"] = ph

    # --- স্মার্ট-মানি মিটিগেশন এন্ট্রি
    lo, hi = F["leg_lo"], F["leg_hi"]
    rg = hi - lo
    F["fib50"], F["fib618"] = hi - cfg.fib_lo * rg, hi - cfg.fib_hi * rg
    fib_hit = F["leg_ok"] & (F["low"] <= F["fib50"]) & (c >= F["fib618"])
    ob_hit = F["leg_ok"] & (F["low"] <= F["ob_hi"]) & (c >= F["ob_lo"])
    fvg_hit = F["leg_ok"] & (F["low"] <= F["fvg_hi"]) & (c >= F["fvg_lo"])
    F["z_fib"], F["z_ob"], F["z_fvg"] = fib_hit, ob_hit, fvg_hit
    F["z_n"] = fib_hit.astype(int) + ob_hit.astype(int) + fvg_hit.astype(int)
    not_chase = (F["chg"] < cfg.uc_pct) & (F["choch_age"] >= 1)                # ব্রেক-ক্যান্ডেল/আপার সার্কিটে কেনা নয়
    smc_entry = F["leg_ok"] & (F["choch_age"] <= cfg.smc_win) & (F["z_n"] > 0) & (F["vr"] < 1.0) & not_chase

    # --- ট্রেড প্ল্যান (এন্ট্রি = আজকের ক্লোজ; বাস্তবে পরদিন ওপেনে)
    def rrr(tg, st):
        risk = c - st
        return np.where((risk > 0) & tg.notna() & (tg > c), (tg - c) / risk.where(risk > 0), np.nan)
    stC, tgC = F["spr_low"] * (1 - buf), F["hi_r"]
    ob_good = F["ob_lo"].notna() & (F["ob_lo"] < c)
    stD = pd.Series(np.where(ob_good, F["ob_lo"] * (1 - buf), F["sos_lvl"] * 0.97), index=F.index)
    tgD = F["h120"]
    stS, tgS = lo * (1 - buf), pd.concat([F["h120"], hi], axis=1).max(axis=1)
    rC, rD, rS = rrr(tgC, stC), rrr(tgD, stD), rrr(tgS, stS)
    lps = (ph == "Phase D") & (F["low"] <= F["sos_lvl"] * 1.03) & (F["vr"] < 1.0) & (F["sos_age"] >= 1) & (F["chg"] < cfg.uc_pct)
    vD = lps & (rD >= cfg.rrr_min)
    vS = smc_entry & (rS >= cfg.rrr_min)
    vC = (ph == "Phase C") & (rC >= cfg.rrr_min)
    kind = np.select([vD, vS, vC, ph == "Phase C", ph == "Phase D", F["leg_ok"]], ["D", "SMC", "C", "C", "D", "SMC"], default="")
    F["plan"] = kind
    F["stop"] = np.select([kind == "D", kind == "SMC", kind == "C"], [stD, stS, stC], default=np.nan)
    F["target"] = np.select([kind == "D", kind == "SMC", kind == "C"], [tgD, tgS, tgC], default=np.nan)
    F["rrr"] = np.select([kind == "D", kind == "SMC", kind == "C"], [rD, rS, rC], default=np.nan)
    bear_ph = ph.isin(list(BEAR))                                               # Distribution/Markdown-এ নতুন এন্ট্রি নয়
    vD, vS, vC = vD & ~bear_ph, vS & ~bear_ph, vC & ~bear_ph
    F["setup"] = vD | vS | vC
    stype = np.select([vD, vS, vC], ["D", "SMC", "C"], default="")
    F["setup_type"] = stype
    F["alloc"] = np.where(F["setup"], pd.Series(stype).map(ALLOC).fillna(0).to_numpy(), 0)
    F.loc[ph == "Phase E", "alloc"] = 100                                       # চলমান পজিশন হোল্ড (নতুন এন্ট্রি নয়)
    late = (F["uc10"] >= 3) | (c > F["sos_lvl"] * (1 + cfg.e_late_ext))
    F["late"] = (ph == "Phase E") & late

    # --- করণীয় (কী) কোড; বাংলা লেখা পেজে
    F["act"] = np.select(
        [ph == "Markdown", ph == "Distribution", (ph == "Phase E") & late, ph == "Phase E",
         vD, ph == "Phase D", lps, vC, ph == "Phase C", ph == "Phase B", ph == "Phase A", vS],
        ["avoid", "exit", "e_late", "e_hold", "d_full", "d_wait", "d_rrr", "c_scale", "c_wait", "b_watch", "a_obs", "smc_in"], default="")
    # d_wait/d_rrr ক্রম: lps থাকলে (কিন্তু RRR<৩) d_rrr, না থাকলে d_wait — np.select প্রথম মিল নেয় বলে ঠিক ক্রমে আছে
    F.loc[(F["act"] == "d_wait") & lps, "act"] = "d_rrr"

    # --- স্কোর (০–১০০)
    vrs = np.clip(F["vr5"] / cfg.vr_thr, 0, 1) * 25
    sq = np.clip((1.0 - F["atr_ratio"]) / 0.3, 0, 1) * 15
    st_ = (F["trend"] == 1) * 5 + (F["leg_ok"] & (F["choch_age"] <= cfg.smc_win)) * 10
    bull_s = (vrs + sq + np.clip(F["vb"], 0, 0.5) / 0.5 * 15 + st_ + F["setup"] * 10 + F["lowcap"] * 20).fillna(0)
    ma_bear = (c < F["sma20"]) * 5 + (c < F["sma50"]) * 5 + (c < F["sma100"]) * 5
    bear_s = (np.clip(-F["vb"], 0, 0.5) / 0.5 * 30 + vrs + ma_bear + (F["trend"] == -1) * 15 + F["lowcap"] * 15).fillna(0)
    F["score"] = np.where(ph.isin(list(BULL)), bull_s, np.where(ph.isin(list(BEAR)), bear_s, 0)).round().clip(0, 100)
    F["stealth"] = F["stealth_age"] <= cfg.stealth_win

    key = F["phase"].fillna("∅")
    grp = (key != key.shift()).cumsum()
    grp = grp + F["code"].ne(F["code"].shift()).cumsum() * 1_000_000          # কোড বদলালে নতুন গ্রুপ
    F["days"] = key.groupby(grp).cumcount() + 1
    F.loc[F["phase"].isna(), ["score", "days"]] = [0, 0]
    F["liquid"] = (F["value20"] >= cfg.min_value) & (F["zero_days"] <= cfg.max_zero_days)
    return F


def build_panel(prices, cfg=Cfg(), cost=0.005, horizons=(10, 20, 40)):
    """prices: কলাম date, code, open, high, low, close, volume। সব কোডের বৈশিষ্ট্য + ভবিষ্যৎ রিটার্ন (শুধু ব্যাকটেস্টের জন্য)।"""
    parts = []
    for code, g in prices.groupby("code", sort=True):
        if len(g) < 130:
            continue
        f = base_features(g, cfg)
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


def load_all_prices(root):
    """ইতিহাস/ ফোল্ডারের CSV এবং বর্তমান docs/data/prices.csv একত্রে পড়ে। বর্তমান ডেটা ডুপ্লিকেট হলে অগ্রাধিকার পায়।"""
    paths = sorted(glob.glob(os.path.join(root, "history", "*.csv")))
    current = os.path.join(root, "docs", "data", "prices.csv")
    if os.path.exists(current):
        paths.append(current)
    if not paths:
        raise FileNotFoundError("কোনো price CSV পাওয়া যায়নি")
    frames = [load_prices(path) for path in paths]
    d = pd.concat(frames, ignore_index=True)
    d["date"] = d["date"].astype(str).str.strip()
    d["code"] = d["code"].astype(str).str.strip().str.upper()
    d = d.drop_duplicates(subset=["date", "code"], keep="last")
    return d.sort_values(["code", "date"]).reset_index(drop=True)


def cfg_dict(cfg):
    return asdict(cfg)
