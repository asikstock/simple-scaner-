"""
রিপোর্ট-ভিত্তিক স্ক্যানারের walk-forward ব্যাকটেস্ট।

গুরুত্বপূর্ণ: রিপোর্টের নিয়ম যেমন আছে তেমন চালানো হয় — কোনো থ্রেশহোল্ড টিউন/গ্রিড-সার্চ নেই, তাই ওভারফিটিংয়ের সুযোগও নেই।

পদ্ধতি
  * প্রতিটি কোডের প্রতিটি দিনে শুধু সেই দিন পর্যন্ত ডেটা দিয়ে ফেজ/সেটআপ ধরা হয় (scripts/phase_engine.py, ভবিষ্যৎ দেখা নেই)।
  * ফেজ-ইভেন্ট = কোনো কোড একটি ফেজে "নতুন ঢুকল" (টানা দিনের প্রথম দিন); শুধু লিকুইড কোড।
    এন্ট্রি = পরদিনের OPEN, এক্সিট = ১০/২০/৪০ দিন পরের ক্লোজ, খরচ ০.৫% (আসা-যাওয়া মিলিয়ে)।
    "অতিরিক্ত" = ট্রেডের নেট রিটার্ন − সেই দিনের সব লিকুইড কোডের গড় নেট রিটার্ন। t-মান মাসভিত্তিক ক্লাস্টার করে।
  * সেটআপ-সিমুলেশন = সেটআপ প্রথম দেখা দিলে পরদিন OPEN-এ এন্ট্রি; রিপোর্টের স্টপ ও টার্গেট; একই দিনে দুটোই ছুঁলে স্টপ;
    সর্বোচ্চ ৪০ দিন, তারপর ক্লোজে এক্সিট। ফল ঝুঁকির (এন্ট্রি−স্টপ) গুণিতক R-এ, খরচ বাদে।
  * সময়কালকে তারিখের মধ্যমায় TRAIN ও TEST ভাগ করে দেখানো হয় (থ্রেশহোল্ড বাছাইয়ের জন্য নয়, শুধু স্থিতিশীলতা দেখতে)।

চালাতে:  python3 -I tools/backtest.py
আউটপুট: docs/data/backtest.json (পেজ এটা দেখায়)
"""
import json, os, sys
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from phase_engine import Cfg, PHASES, build_panel, classify, load_prices, cfg_dict  # noqa: E402

H = (10, 20, 40)
COST = 0.005
HOLD = 40


def month_t(d, col):
    """মাসভিত্তিক ক্লাস্টার t-মান।"""
    if len(d) < 5:
        return float("nan")
    m = d.groupby(d["date"].str[:7])[col].mean()
    if len(m) < 3 or m.std(ddof=1) == 0:
        return float("nan")
    return float(m.mean() / (m.std(ddof=1) / np.sqrt(len(m))))


def block(d, h):
    d = d[d[f"r{h}"].notna() & d[f"x{h}"].notna()]
    if d.empty:
        return {"n": 0}
    ex = f"x{h}"
    return {"n": int(len(d)), "net": float(d[f"r{h}"].mean() * 100), "med": float(d[f"r{h}"].median() * 100),
            "excess": float(d[ex].mean() * 100), "hit": float((d[ex] > 0).mean() * 100), "t": month_t(d, ex)}


def add_excess(F):
    liq = F[F["liquid"]]
    for h in H:
        base = liq.groupby("date")[f"r{h}"].mean().rename(f"b{h}")
        F = F.join(base, on="date")
        F[f"x{h}"] = F[f"r{h}"] - F[f"b{h}"]
    return F


def simulate(F, ev):
    """সেটআপ-ইভেন্টের ট্রেড-সিমুলেশন। ফেরত: প্রতি ট্রেডে (date, type, R, exit)।"""
    F = F.reset_index(drop=True)
    start = F.groupby("code").cumcount()
    first = (F.index.to_series() - start).to_numpy()          # প্রতি সারির কোডের শুরুর ইনডেক্স
    ends = F.groupby("code")["date"].transform("size").to_numpy() + first
    O, Hh, L, C = (F[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    out = []
    for i in ev.index:
        e0 = i + 1
        if e0 >= ends[i]:
            continue
        stop, tgt = F.at[i, "stop"], F.at[i, "target"]
        entry = O[e0]
        if not (stop < entry < tgt):
            continue
        risk = entry - stop
        exit_p, why = None, None
        last = min(i + HOLD, ends[i] - 1)
        for k in range(e0, last + 1):
            if L[k] <= stop:
                exit_p, why = min(O[k], stop), "sl"
                break
            if Hh[k] >= tgt:
                exit_p, why = max(O[k], tgt), "tp"
                break
        if exit_p is None:
            if last - i < HOLD:                             # ডেটা শেষ, ট্রেড এখনও খোলা: বাদ (পক্ষপাত এড়াতে)
                continue
            exit_p, why = C[last], "time"
        out.append((F.at[i, "date"], F.at[i, "setup_type"], (exit_p - entry) / risk - COST * entry / risk, why))
    return pd.DataFrame(out, columns=["date", "type", "R", "why"])


def sim_stats(t, cut):
    if t.empty:
        return {"n": 0, "win": None, "avg_r": None, "med_r": None, "tp": None, "sl": None, "time": None,
                "train": {"n": 0, "avg_r": None}, "test": {"n": 0, "avg_r": None}}
    tr, te = t[t["date"] < cut], t[t["date"] >= cut]
    return {"n": int(len(t)), "win": float((t["R"] > 0).mean() * 100), "avg_r": float(t["R"].mean()), "med_r": float(t["R"].median()),
            "tp": float((t["why"] == "tp").mean() * 100), "sl": float((t["why"] == "sl").mean() * 100), "time": float((t["why"] == "time").mean() * 100),
            "train": {"n": int(len(tr)), "avg_r": float(tr["R"].mean()) if len(tr) else None},
            "test": {"n": int(len(te)), "avg_r": float(te["R"].mean()) if len(te) else None}}


def main():
    cfg = Cfg()
    prices = load_prices(os.path.join(ROOT, "docs", "data", "prices.csv"))
    F = add_excess(classify(build_panel(prices, cfg, cost=COST, horizons=H), cfg))
    last_date = F["date"].max()
    print(f"ডেটা: {prices['date'].min()} থেকে {last_date}, {prices['code'].nunique()} কোড")

    liq = F["liquid"]
    ev = F[liq & F["phase"].notna() & (F["days"] == 1)]
    cut = ev[ev["r20"].notna()]["date"].sort_values().iloc[len(ev[ev["r20"].notna()]) // 2]
    print("TRAIN/TEST ভাগের তারিখ:", cut)

    out = {"generated_for": last_date, "split_date": cut, "cost_pct": COST * 100, "config": cfg_dict(cfg),
           "n_codes": int(prices["code"].nunique()), "first_date": prices["date"].min()}
    out["phases"] = {}
    for ph in PHASES:
        e = ev[ev["phase"] == ph]
        tr, te = e[e["date"] < cut], e[e["date"] >= cut]
        out["phases"][ph] = {"events": int(len(e)), "all": {f"h{h}": block(e, h) for h in H},
                             "train": {"h20": block(tr, 20)}, "test": {"h20": block(te, 20)}}
    out["baseline"] = {f"h{h}": float(F[liq][f"r{h}"].mean() * 100) for h in H}

    # --- সেটআপ: প্রথম-দিন ইভেন্ট ও ট্রেড-সিমুলেশন
    prev = F.groupby("code")["setup"].shift().fillna(False).astype(bool)
    sev = F[liq & F["setup"] & ~prev]
    sims = simulate(F, sev)
    out["setups"] = {"ALL": sim_stats(sims, cut)}
    for k in ("D", "SMC", "C"):
        out["setups"][k] = sim_stats(sims[sims["type"] == k], cut)

    # --- STEALTH সংকেত (রিপোর্টের কেন্দ্রীয় দাবি: VR ≥ ২.৫ + ছোট বডি/সংকুচিত ATR = অ্যাকিউমুলেশন)
    st = F[liq & F["e_stealth"] & ~(F.groupby("code")["stealth_age"].shift() <= 5)]
    out["stealth"] = {"all": {f"h{h}": block(st, h) for h in H},
                      "train": {"h20": block(st[st["date"] < cut], 20)}, "test": {"h20": block(st[st["date"] >= cut], 20)}}

    # --- স্বয়ংক্রিয় মন্তব্য (সংখ্যা বদলালে নিজে বদলায়)
    notes = []
    robust, weak = [], []
    for ph in PHASES:
        r = out["phases"][ph]
        a, te = r["all"]["h20"], r["test"]["h20"]
        if a.get("n", 0) < 30 or a.get("t") is None or np.isnan(a.get("t", np.nan)):
            weak.append(f"{ph} (ইভেন্ট কম)")
        elif abs(a["t"]) >= 2 and te.get("n", 0) >= 15 and np.sign(te["excess"]) == np.sign(a["excess"]):
            robust.append(f"{ph} ({a['excess']:+.1f}%, t = {a['t']:.1f})")
        else:
            weak.append(ph)
    notes.append("<b>টেকসই ধারা (|t| ≥ ২ ও TEST-এ একই দিক; ঋণাত্মক = বাজারের গড়ের চেয়ে খারাপ):</b> " + (", ".join(robust) if robust else "কোনোটিই নয়") + "।")
    if weak:
        notes.append("<b>ভরসাযোগ্য কিছু বলা যায় না:</b> " + ", ".join(weak) + " (t-মান ছোট বা ইভেন্ট কম, বা এক অর্ধে ভালো তো অন্য অর্ধে উল্টো)।")
    s = out["setups"]["ALL"]
    if s["n"]:
        notes.append(f"<b>এন্ট্রি-যোগ্য সেটআপ:</b> {s['n']}টি ট্রেডে গড় {s['avg_r']:+.2f}R, জেতার হার {s['win']:.0f}%। "
                     "প্রতিটি ট্রেডে ১:৩-এর পরিকল্পনা থাকলেও বাস্তবে টার্গেটে পৌঁছানোর হার কত তা ওপরের সারণিতে (টার্গেট/স্টপ/সময়)।")
    out["notes"] = notes

    path = os.path.join(ROOT, "docs", "data", "backtest.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=lambda o: None if (isinstance(o, float) and np.isnan(o)) else o)
    print("সংরক্ষিত:", path)

    fx = lambda x: "  -  " if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:+.2f}"
    print("\nফেজ            ইভেন্ট  | ২০দিন net  অতিরিক্ত  hit%   t   | TRAIN অতি  TEST অতি | ৪০দিন অতি")
    for ph in PHASES:
        r = out["phases"][ph]; a20 = r["all"]["h20"]; a40 = r["all"]["h40"]
        print(f"{ph:<14}{r['events']:>6}  | {fx(a20.get('net'))}  {fx(a20.get('excess'))}  {a20.get('hit', 0):.0f}  {fx(a20.get('t'))} | "
              f"{fx(r['train']['h20'].get('excess'))} (n={r['train']['h20'].get('n', 0)})  {fx(r['test']['h20'].get('excess'))} (n={r['test']['h20'].get('n', 0)}) | {fx(a40.get('excess'))}")
    print("বেসলাইন (লিকুইড গড় নেট):", {k: round(v, 2) for k, v in out["baseline"].items()})
    print("\nসেটআপ-সিমুলেশন:")
    for k, v in out["setups"].items():
        print(k, {a: (round(b, 2) if isinstance(b, float) else b) for a, b in v.items()})
    print("STEALTH ২০ দিন:", {a: (round(b, 2) if isinstance(b, float) else b) for a, b in out["stealth"]["all"]["h20"].items()},
          "TEST:", {a: (round(b, 2) if isinstance(b, float) else b) for a, b in out["stealth"]["test"]["h20"].items()})
    for n in notes:
        print("-", n)


if __name__ == "__main__":
    main()
