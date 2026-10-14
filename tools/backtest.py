"""
ফেজ স্ক্যানারের walk-forward ব্যাকটেস্ট + থ্রেশহোল্ড বাছাই (train/test ভাগে)।

পদ্ধতি
  * প্রতিটি কোডের প্রতিটি দিনে শুধু সেই দিন পর্যন্ত ডেটা দিয়ে ফেজ ধরা হয় (scripts/phase_engine.py, ভবিষ্যৎ দেখা নেই)।
  * নমুনা = কোনো কোড একটি ফেজে "নতুন ঢুকল" (টানা দিনের প্রথম দিন), শুধু লিকুইড কোড (২০ দিনের গড় লেনদেন ≥ ৩০ লাখ)।
  * এন্ট্রি = পরদিনের OPEN, এক্সিট = ১০/২০/৪০ দিন পরের ক্লোজ, খরচ ০.৫% (আসা-যাওয়া মিলিয়ে)।
  * "অতিরিক্ত" = ট্রেডের নেট রিটার্ন − সেই দিনের সব লিকুইড কোডের গড় নেট রিটার্ন (বাজারের গড়ের চেয়ে কতটা বেশি)।
  * t-মান মাসভিত্তিক ক্লাস্টার করে (একই মাসের ট্রেডগুলো আলাদা প্রমাণ নয়): কড়া, কিন্তু সৎ।
  * সংকেতের সময়কালকে তারিখের মধ্যমায় TRAIN (আগের অর্ধ) ও TEST (পরের অর্ধ) ভাগ করা হয়। থ্রেশহোল্ড শুধু TRAIN দেখে বাছা হয়, TEST-এ শুধু যাচাই।

চালাতে:  python3 -I tools/backtest.py
আউটপুট: docs/data/backtest.json (পেজ এটা দেখায়)
"""
import itertools, json, os, sys
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from phase_engine import Cfg, PHASES, BULL, BEAR, build_panel, classify, load_prices, cfg_dict  # noqa: E402

H = (10, 20, 40)
COST = 0.005
MIN_N = 30   # বাছাইয়ের জন্য TRAIN-এ বুলিশ ও বেয়ারিশ দুই দিকে অন্তত এত ইভেন্ট লাগবে


def month_t(d, col):
    """মাসভিত্তিক ক্লাস্টার t-মান।"""
    if len(d) < 5:
        return float("nan")
    m = d.groupby(d["date"].str[:7])[col].mean()
    if len(m) < 3 or m.std(ddof=1) == 0:
        return float("nan")
    return float(m.mean() / (m.std(ddof=1) / np.sqrt(len(m))))


def block(d, h):
    d = d[d[f"r{h}"].notna()]
    if d.empty:
        return {"n": 0}
    ex = f"x{h}"
    return {"n": int(len(d)), "net": float(d[f"r{h}"].mean() * 100), "med": float(d[f"r{h}"].median() * 100),
            "excess": float(d[ex].mean() * 100), "hit": float((d[ex] > 0).mean() * 100), "t": month_t(d, ex)}


def prepare(prices):
    panel = build_panel(prices, cost=COST, horizons=H)
    for h in H:   # সেই দিনের লিকুইড কোডের গড়, বেসলাইন
        pass
    return panel


def add_excess(F):
    liq = F[F["liquid"]]
    for h in H:
        base = liq.groupby("date")[f"r{h}"].mean().rename(f"b{h}")
        F = F.join(base, on="date")
        F[f"x{h}"] = F[f"r{h}"] - F[f"b{h}"]
    return F


def split_date(F):
    d = F[F["liquid"] & F["phase"].notna() & F["r20"].notna()]["date"].sort_values()
    return d.iloc[len(d) // 2]


def events(F):
    return F[F["liquid"] & F["phase"].notna() & (F["days"] == 1)]


def spread(ev, h=20):
    """বুলিশ ফেজের গড় অতিরিক্ত − বেয়ারিশ ফেজের গড় অতিরিক্ত (বেশি = ফেজ-লেবেল বেশি কার্যকর)।"""
    b = ev[ev["phase"].isin(BULL) & ev[f"x{h}"].notna()]
    r = ev[ev["phase"].isin(BEAR) & ev[f"x{h}"].notna()]
    if len(b) < MIN_N or len(r) < MIN_N:
        return None, len(b), len(r)
    return float((b[f"x{h}"].mean() - r[f"x{h}"].mean()) * 100), len(b), len(r)


def main():
    prices = load_prices(os.path.join(ROOT, "docs", "data", "prices.csv"))
    panel = build_panel(prices, cost=COST, horizons=H)
    last_date = panel["date"].max()
    print(f"ডেটা: {prices['date'].min()} থেকে {last_date}, {prices['code'].nunique()} কোড")

    # বেসলাইন (লিকুইড কোডের গড় নেট রিটার্ন) নির্ধারণের জন্য liquid দরকার, যা Cfg-র min_value/max_zero_days থেকে আসে (বাছাইয়ে বদলায় না)
    F0 = add_excess(classify(panel, Cfg(max_width=0.30, prior_pct=0.15, vb_min=0.0, min_score=0)))  # প্রাথমিক নিয়ম, শুধু ভাগের তারিখ ঠিক করতে
    cut = split_date(F0)
    print("TRAIN/TEST ভাগের তারিখ:", cut)

    grid = {"max_width": [0.20, 0.30, 0.40], "prior_pct": [0.10, 0.15, 0.25],
            "vb_min": [0.0, 0.15], "min_score": [0, 50, 65]}
    rows = []
    for mw, pp, vb, ms in itertools.product(*grid.values()):
        cfg = Cfg(max_width=mw, prior_pct=pp, vb_min=vb, min_score=ms)
        F = add_excess(classify(panel, cfg))
        ev = events(F)
        tr, te = ev[ev["date"] < cut], ev[ev["date"] >= cut]
        s_tr, nb, nr = spread(tr)
        s_te, nb2, nr2 = spread(te)
        rows.append({"max_width": mw, "prior_pct": pp, "vb_min": vb, "min_score": ms,
                     "train_spread": s_tr, "test_spread": s_te, "train_n": [nb, nr], "test_n": [nb2, nr2]})
        print(f"w={mw} p={pp} vb={vb} s={ms}  TRAIN {s_tr if s_tr is None else round(s_tr,2)}  TEST {s_te if s_te is None else round(s_te,2)}", flush=True)
    G = pd.DataFrame(rows)
    valid = G[G["train_spread"].notna()].sort_values("train_spread", ascending=False)
    best = valid.iloc[0]
    chosen = Cfg(max_width=float(best["max_width"]), prior_pct=float(best["prior_pct"]),
                 vb_min=float(best["vb_min"]), min_score=int(best["min_score"]))
    default_row = G[(G.max_width == 0.30) & (G.prior_pct == 0.15) & (G.vb_min == 0.0) & (G.min_score == 0)].iloc[0]
    print("\nTRAIN-এ সেরা:", cfg_dict(chosen))
    out = {"generated_for": last_date, "split_date": cut, "cost_pct": COST * 100, "config": cfg_dict(chosen),
           "n_codes": int(prices["code"].nunique()), "first_date": prices["date"].min(),
           "grid_size": int(len(G)), "grid_top": valid.head(5).to_dict("records"),
           "grid_default": default_row.to_dict(),
           "grid_median_test": float(valid["test_spread"].median()) if valid["test_spread"].notna().any() else None}

    def table(cfg):
        F = add_excess(classify(panel, cfg))
        ev = events(F)
        res = {}
        for ph in PHASES:
            e = ev[ev["phase"] == ph]
            tr, te = e[e["date"] < cut], e[e["date"] >= cut]
            rec = {"events": int(len(e)), "all": {f"h{h}": block(e, h) for h in H},
                   "train": {"h20": block(tr, 20)}, "test": {"h20": block(te, 20)}}
            # স্কোর ক্রম কাজ করে কি? সব-দিনের নমুনায় স্কোর ≥ মধ্যমা বনাম < মধ্যমা (২০ দিন)
            a_ = F[F["liquid"] & (F["phase"] == ph) & F["x20"].notna()]
            if len(a_) >= 100:
                med = a_["score"].median()
                hi, lo = a_[a_["score"] >= med], a_[a_["score"] < med]
                rec["score_split"] = {"median": float(med), "hi_excess": float(hi["x20"].mean() * 100),
                                      "lo_excess": float(lo["x20"].mean() * 100), "hi_n": int(len(hi)), "lo_n": int(len(lo))}
            res[ph] = rec
        return F, ev, res

    F, ev, out["phases"] = table(chosen)                                   # শক্তিশালী স্তর (বাছা সীমা, স্কোর ≥ strong)
    from dataclasses import replace
    _, ev0, out["phases_all"] = table(replace(chosen, min_score=0))        # সব ফেজ-লেবেল (পেজের ট্যাবে যা দেখানো হয়)
    liq = F[F["liquid"]]
    out["baseline"] = {f"h{h}": float(liq[f"r{h}"].mean() * 100) for h in H}
    out["spread_all_levels"] = spread(ev0)[0]
    sp, nb, nr = spread(ev)
    out["spread_all"] = sp
    path = os.path.join(ROOT, "docs", "data", "backtest.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=lambda o: None if (isinstance(o, float) and np.isnan(o)) else o)
    print("সংরক্ষিত:", path)

    # পড়ার সুবিধার সারণি
    print("\nফেজ            ইভেন্ট  | ২০দিন net  অতিরিক্ত  hit%   t   | TRAIN অতি  TEST অতি | ৪০দিন অতি")
    for ph in PHASES:
        r = out["phases"][ph]; a20 = r["all"]["h20"]; a40 = r["all"]["h40"]
        trx = r["train"]["h20"].get("excess"); tex = r["test"]["h20"].get("excess")
        f = lambda x: "  -  " if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:+.2f}"
        print(f"{ph:<16}{r['events']:>5}  | {f(a20.get('net'))}  {f(a20.get('excess'))}  {a20.get('hit', 0):.0f}  {f(a20.get('t'))} | {f(trx)} (n={r['train']['h20']['n']})  {f(tex)} (n={r['test']['h20']['n']}) | {f(a40.get('excess'))}")
    print("বেসলাইন (লিকুইড গড় নেট):", {k: round(v, 2) for k, v in out["baseline"].items()})
    print("বুলিশ−বেয়ারিশ স্প্রেড (২০ দিন, সব সময়):", sp)
    print("\nগ্রিডের সেরা ৫ (TRAIN) ও তাদের TEST:")
    print(valid.head(5)[["max_width", "prior_pct", "vb_min", "min_score", "train_spread", "test_spread"]].to_string(index=False))
    print("ডিফল্ট কনফিগ:", default_row[["train_spread", "test_spread"]].to_dict())
    print("সব বৈধ কনফিগের TEST-স্প্রেডের মধ্যমা:", out["grid_median_test"])


if __name__ == "__main__":
    main()
