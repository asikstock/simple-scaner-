"""রিপোর্ট-সূত্রের টেস্ট: VR, RRR, CHOCH/OB/FVG, ভবিষ্যৎ-না-দেখা, ফান্ডামেন্টাল ফিল্টার, পার্সার।  চালান: python tests/test_phase_engine.py"""
import os, sys
import numpy as np
import pandas as pd
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from phase_engine import Cfg, PHASES, base_features, build_panel, classify, load_prices, smc_structure, ALLOC  # noqa: E402


def frame(n, close=None, vol=None):
    d = pd.DataFrame({'date': pd.date_range('2024-01-01', periods=n, freq='B').strftime('%Y-%m-%d')})
    c = np.full(n, 100.0) if close is None else np.asarray(close, float)
    d['open'], d['close'] = c, c
    d['high'], d['low'] = c * 1.01, c * 0.99
    d['volume'] = np.full(n, 1000.0) if vol is None else np.asarray(vol, float)
    return d


# ১. VR = V_t ÷ গড়(V_{t-1..t-20}); আজকের ভলিউম গড়ে নেই
v = np.full(60, 1000.0); v[-1] = 3000.0
f = base_features(frame(60, vol=v))
assert abs(f['vr'].iloc[-1] - 3.0) < 1e-9, f['vr'].iloc[-1]
v2 = np.arange(1, 61) * 100.0                      # বাড়ন্ত ভলিউম: গড়ে আজ বাদ
f2 = base_features(frame(60, vol=v2))
expect = v2[-1] / v2[-21:-1].mean()
assert abs(f2['vr'].iloc[-1] - expect) < 1e-9

# ২. CHOCH/OB: লেখা জিগজ্যাগ — নিচের দিকে (lower-high, lower-low), তারপর সর্বশেষ সুইং হাই ভেঙে ওপরে
c = np.array([100, 99, 98, 99, 100, 99, 98, 97, 96, 95, 96, 97, 96, 95, 94, 93, 92, 91, 90, 91, 92, 93, 92, 91, 90.5, 91, 92, 93, 94, 95, 96, 97, 99], float)
o = np.r_[c[0], c[:-1]]
jit = np.random.RandomState(1).uniform(0, 0.05, len(c))        # সমান wick-এর টাই এড়াতে (আসল ডেটায় এমন হয় না)
h, l = np.maximum(o, c) + 0.2 + jit, np.minimum(o, c) - 0.2 - jit[::-1]
s = smc_structure(o, h, l, c, k=3)
brk = int(np.argmax(s['leg_ok']))
assert s['leg_ok'][brk] and s['choch_age'][brk] == 0, 'CHOCH ধরা পড়েনি'
assert s['trend'][brk] == 1 and s['trend'][brk - 1] == -1
j = int(np.argmin(l[:brk + 1]))
assert abs(s['leg_lo'][brk] - l[j]) < 1e-9                       # লেগ-লো = সর্বনিম্ন low
assert not np.isnan(s['ob_lo'][brk]) and s['ob_hi'][brk] > s['ob_lo'][brk]    # অর্ডার ব্লক আছে
# OB = ব্রেকের আগের উর্ধ্ব-রানের আগের শেষ ডাউন-ক্যান্ডেল (close < open)
q = [i for i in range(j, brk + 1) if c[i] < o[i]][-1]
assert abs(s['ob_lo'][brk] - l[q]) < 1e-9 and abs(s['ob_hi'][brk] - h[q]) < 1e-9
# লেগ-লো-র নিচে ক্লোজ করলে লেগ বাতিল
c2 = np.r_[c, 80.0]; o2 = np.r_[o, c[-1]]
s2 = smc_structure(o2, np.maximum(o2, c2) + .2, np.minimum(o2, c2) - .2, c2, k=3)
assert not s2['leg_ok'][-1]

# ৩. FVG: তিন-ক্যান্ডেলে low[i] > high[i-2]; এই সিরিজে ব্রেকের দিনেই গ্যাপ আছে
fv = [q for q in range(brk, j + 1, -1) if l[q] > h[q - 2]][0]
assert abs(s['fvg_lo'][brk] - h[fv - 2]) < 1e-9 and abs(s['fvg_hi'][brk] - l[fv]) < 1e-9 and s['fvg_hi'][brk] > s['fvg_lo'][brk]

# ৪. আসল ডেটায়: সূত্র ও ফেজের অসঙ্গতি নেই
P = load_prices(os.path.join(ROOT, 'docs', 'data', 'prices.csv'))
codes = sorted(P['code'].unique())[::25]
G = P[P['code'].isin(codes)]
F = classify(build_panel(G, horizons=()))
assert set(F['phase'].dropna()) <= set(PHASES)
assert F['score'].between(0, 100).all()
r = F[F['rrr'].notna()]
assert len(r) > 0
calc = (r['target'] - r['close']) / (r['close'] - r['stop'])
assert np.allclose(r['rrr'], calc, atol=1e-6), 'RRR সূত্র মেলেনি'
s_ok = F[F['setup']]
assert (s_ok['rrr'] >= 3.0 - 1e-9).all(), 'সেটআপে RRR < ৩'
assert (s_ok['stop'] < s_ok['close']).all() and (s_ok['target'] > s_ok['close']).all()
assert not s_ok['phase'].isin(['Distribution', 'Markdown']).any()
assert (s_ok['chg'] < Cfg().uc_pct).all()                                    # আপার সার্কিটের দিনে সেটআপ নয়
assert (F.loc[F['phase'] == 'Phase E', 'alloc'] == 100).all()
assert set(F.loc[F['setup'], 'alloc'].unique()) <= set(ALLOC.values())
assert (F.loc[F['phase'].isin(['Phase A', 'Phase B', 'Distribution', 'Markdown']) & ~F['setup'], 'alloc'] == 0).all()
# স্টপ = স্প্রিং/লেগ-লো-র ০.৫% নিচে (Phase C / SMC)
cs = F[F['setup'] & (F['setup_type'] == 'C')]
if len(cs):
    assert (cs['stop'] < cs['spr_low']).all()

# ৫. ভবিষ্যৎ না দেখা: শেষ ৩০ দিন কেটে ফেললে আগের দিনগুলোর ফল একই
for code in codes[:4]:
    g = P[P['code'] == code]
    full = classify(build_panel(g, horizons=()))
    cut = classify(build_panel(g.iloc[:-30], horizons=()))
    cols = ['phase', 'score', 'rrr', 'setup', 'trend', 'vr']
    a = full.iloc[:len(cut)][cols].reset_index(drop=True).fillna(-1)
    b = cut[cols].reset_index(drop=True).fillna(-1)
    assert a.equals(b), f'{code}: ভবিষ্যৎ-নির্ভর'

# ৬. Paid-up < ৫০ কোটি (৫০০ মিলিয়ন) ও P/E > ৪০ ফ্ল্যাগ; স্কোরে Paid-up-এর ২০ পয়েন্ট
base = build_panel(G[G['code'] == codes[0]], horizons=())
fund_low = pd.DataFrame({'code': [codes[0]], 'paidup_mn': [300.0], 'pe': [55.0]})
fund_big = pd.DataFrame({'code': [codes[0]], 'paidup_mn': [900.0], 'pe': [12.0]})
lo, bg = classify(base, fund=fund_low), classify(base, fund=fund_big)
assert lo['lowcap'].all() and lo['pe_high'].all() and not bg['lowcap'].any() and not bg['pe_high'].any()
m = lo['phase'].isin(['Phase A', 'Phase B', 'Phase C', 'Phase D', 'Phase E'])
if m.any():
    assert ((lo.loc[m, 'score'] - bg.loc[m, 'score']) >= 19).all()

# ৭. DSE কোম্পানি-পেজ পার্সার (নকল HTML)
from update_fundamentals import parse_company  # noqa: E402
r1 = parse_company('<table><tr><th>Authorized Capital (mn)</th><th>Paid-up Capital (mn)</th></tr><tr><td>5,000.00</td><td>1,234.50</td></tr></table>'
                   '<table><tr><td>Market Category</td><td>A</td></tr><tr><td>P/E Ratio</td><td>18.2</td></tr></table>')
assert r1 == {'PAIDUP_MN': 1234.5, 'PE': 18.2, 'CATEGORY': 'A'}, r1
assert parse_company('<html></html>')['PAIDUP_MN'] is None
# ৮. ওয়াইকফ গঠন-যাচাই (SC → AR → ST): স্তর, বাতিল, ভবিষ্যৎ-না-দেখা, আয়না (BC)
from wyckoff_struct import wyckoff_struct  # noqa: E402
n_ = 200
c_ = np.full(n_, 120.0); h_ = c_ * 1.01; l_ = c_ * 0.99; v_ = np.full(n_, 1000.0)
c_[100], l_[100], h_[100], v_[100] = 101, 100, 105, 10000                     # সেলিং ক্লাইম্যাক্স
for i_, x_ in zip(range(101, 109), [108, 114, 120, 126, 132, 136, 139, 138]):  # AR: পতনের (২০০−১০০) ৪০% ফেরত
    c_[i_], h_[i_], l_[i_] = x_, x_ + 1, x_ - 1
for i_ in range(109, 125):
    c_[i_] = 138 - (i_ - 108) * 2.2; h_[i_] = c_[i_] + 1; l_[i_] = c_[i_] - 1
c_[125], l_[125], h_[125], v_[125] = 104, 102, 106, 3000                       # ST: লো-র কাছে, ভলিউম ≤ ০.৬ × SC
for i_ in range(126, 150):
    c_[i_], h_[i_], l_[i_] = 110, 111, 109
sc_ = np.zeros(n_, bool); sc_[100] = True
z_ = np.zeros(n_, bool)
H120, L120 = np.full(n_, 200.0), np.full(n_, 50.0)
w = wyckoff_struct(h_, l_, c_, v_, sc_, z_, H120, L120)
assert w['gacc_lvl'][99] == 0 and np.isnan(w['gacc_age'][99])                  # SC-র আগে কিছু নেই
assert w['gacc_lvl'][104] == 0                                                 # AR এখনও ৩০%-এ পৌঁছায়নি (০.২৭)
assert w['gacc_lvl'][114] == 1 and w['gacc_lvl'][120] == 1                     # SC + AR, ST এখনও নয়
assert w['gacc_lvl'][125] == 2 and w['gacc_st'][125] and w['gacc_lvl'][149] == 2   # ST-র পর নিশ্চিত
c2_, l2_, h2_ = c_.copy(), l_.copy(), h_.copy()
c2_[150:], l2_[150:], h2_[150:] = 90, 89, 91                                   # SC লো-র ৫%-এর বেশি নিচে ক্লোজ
w2 = wyckoff_struct(h2_, l2_, c2_, v_, sc_, z_, H120, L120)
assert w2['gacc_lvl'][155] == 0                                                # গঠন বাতিল
w3 = wyckoff_struct(h2_[:130], l2_[:130], c2_[:130], v_[:130], sc_[:130], z_[:130], H120[:130], L120[:130])
assert np.array_equal(w2['gacc_lvl'][:130], w3['gacc_lvl'])                    # ভবিষ্যৎ বদলালে অতীত বদলায় না
bc_ = np.zeros(n_, bool); bc_[100] = True                                      # আয়না: দাম উল্টে দিলে BC-গঠন
w4 = wyckoff_struct(300 - l_, 300 - h_, 300 - c_, v_, z_, bc_, np.full(n_, 250.0), np.full(n_, 100.0))
assert w4['gdist_lvl'][125] == 2 and w4['gdist_st'][125]
# ইঞ্জিনে: গঠন-কলাম যোগ হলেও বিদ্যমান dist_age ইত্যাদি ওভাররাইট হয়নি, আর ফেজ-নির্ধারণ একই
assert {'gacc_lvl', 'gdist_lvl', 'glvl', 'gage', 'gbal', 'dist_age', 'dist_hi'} <= set(F.columns)
assert F['glvl'].dropna().isin([0, 1, 2]).all()
assert F.loc[F['phase'] == 'Markdown', 'glvl'].isna().all()

# ৯. নতুন ফিল্টার ১: e_dryup — ভলিউম ড্রাই-আপ + ছোট বডি
# শর্ত: (vdry <= 0.75) & (body_atr <= 0.5) & (atr_ratio <= 0.85)
# গত ৫ দিনের মধ্যে অন্তত ৩ দিন শর্ত পূরণ হলে e_dryup = True
n_ = 120
c_ = np.full(n_, 100.0); o_ = c_.copy()
h_ = c_ + 1.0; l_ = c_ - 1.0
v_ = np.full(n_, 10000.0)
v_[-10:] = 2000.0
o_[-5:] = 100.0; c_[-5:] = 100.1
h_[-20:] = c_[-20:] + 0.25; l_[-20:] = c_[-20:] - 0.25
df_dry = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=n_, freq="B").strftime("%Y-%m-%d"),
                       "open": o_, "high": h_, "low": l_, "close": c_, "volume": v_})
f_dry = base_features(df_dry)
assert f_dry["e_dryup"].iloc[-1] == True, "ফিল্টার ১: e_dryup সত্য হয়নি"

df_dry_fail = frame(n_, close=np.linspace(100, 200, n_), vol=np.full(n_, 10000.0))
f_dry_fail = base_features(df_dry_fail)
assert f_dry_fail["e_dryup"].iloc[-1] == False, "ফিল্টার ১: e_dryup মিথ্যা হওয়া উচিত ছিল"

# ১০. নতুন ফিল্টার ২: e_divergence — সেক্টর/ইনডেক্স ডাইভার্জেন্স
# fallback: শেয়ারের ১-দিনের রিটার্ন >= ৫%, ভলিউম রেশিও >= ৩.০
n_ = 60
c_ = np.full(n_, 100.0); v_ = np.full(n_, 1000.0)
c_[-1] = 106.0; v_[-1] = 4000.0
df_div = frame(n_, close=c_, vol=v_)
f_div = base_features(df_div)
assert f_div["e_divergence"].iloc[-1] == True, "ফিল্টার ২: e_divergence fallback সত্য হয়নি"

c_fail = c_.copy(); c_fail[-1] = 102.0
df_div_fail = frame(n_, close=c_fail, vol=v_)
f_div_fail = base_features(df_div_fail)
assert f_div_fail["e_divergence"].iloc[-1] == False, "ফিল্টার ২: e_divergence chg < 5% মিথ্যা হওয়া উচিত ছিল"

# পূর্ণ সংস্করণ (DSEX ও সেক্টর ইনডেক্স থাকলে)
df_div_full = frame(n_, close=c_, vol=v_)
df_div_full["dsex_chg"] = 0.5
df_div_full["sector_chg"] = 0.2
f_div_full = base_features(df_div_full)
assert f_div_full["e_divergence"].iloc[-1] == True, "ফিল্টার ২: e_divergence পূর্ণ সংস্করণ সত্য হয়নি"

df_div_full_fail = frame(n_, close=c_, vol=v_)
df_div_full_fail["dsex_chg"] = 2.5
df_div_full_fail["sector_chg"] = 0.2
f_div_full_fail = base_features(df_div_full_fail)
assert f_div_full_fail["e_divergence"].iloc[-1] == False, "ফিল্টার ২: e_divergence বাজার অস্থিরতায় মিথ্যা হওয়া উচিত ছিল"

# ১১. নতুন ফিল্টার ৩: e_uc_lowvol — সার্কিট ব্রেকার + কম ভলিউম
# শর্ত: uc == 1 (chg >= 9.5%) এবং (vr < 1.0 অথবা vdry < 0.8)
n_ = 70
c_ = np.full(n_, 100.0); v_ = np.full(n_, 1000.0)
c_[-1] = 109.8; v_[-1] = 500.0
df_uc = frame(n_, close=c_, vol=v_)
f_uc = base_features(df_uc)
assert f_uc["e_uc_lowvol"].iloc[-1] == True, "ফিল্টার ৩: e_uc_lowvol (vr < 1.0) সত্য হয়নি"

v2_ = np.full(n_, 10000.0); v2_[-10:] = 2000.0; v2_[-1] = 2500.0
df_uc2 = frame(n_, close=c_, vol=v2_)
f_uc2 = base_features(df_uc2)
assert f_uc2["e_uc_lowvol"].iloc[-1] == True, "ফিল্টার ৩: e_uc_lowvol (vdry < 0.8) সত্য হয়নি"

v3_ = np.full(n_, 1000.0); v3_[-1] = 3500.0
df_uc3 = frame(n_, close=c_, vol=v3_)
f_uc3 = base_features(df_uc3)
assert f_uc3["e_uc_lowvol"].iloc[-1] == False, "ফিল্টার ৩: e_uc_lowvol উচ্চ ভলিউমে মিথ্যা হওয়া উচিত ছিল"

c4_ = np.full(n_, 100.0); c4_[-1] = 102.0
df_uc4 = frame(n_, close=c4_, vol=v_)
f_uc4 = base_features(df_uc4)
assert f_uc4["e_uc_lowvol"].iloc[-1] == False, "ফিল্টার ৩: e_uc_lowvol সার্কিট ছাড়া মিথ্যা হওয়া উচিত ছিল"

print('সব টেস্ট পাস (নতুন ৩টি ফিল্টারের টেস্টসহ)')

