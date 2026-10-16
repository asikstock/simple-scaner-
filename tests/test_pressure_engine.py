"""প্রেসার ইঞ্জিনের টেস্ট: CLV, রেঞ্জ-লক, ভলিউম ০, ভবিষ্যৎ-না-দেখা, স্কোরের সীমা, নাগালের বাইরে।  চালান: python tests/test_pressure_engine.py"""
import os, sys
import numpy as np
import pandas as pd
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from pressure_engine import PCfg, load_prices_ycp, pressure_panel, pressure_latest  # noqa: E402


def frame(n, close=None, high=None, low=None, vol=None, ycp=None, code='AAA'):
    d = pd.DataFrame({'date': pd.date_range('2024-01-01', periods=n, freq='B').strftime('%Y-%m-%d')})
    c = np.full(n, 100.0) if close is None else np.asarray(close, float)
    d['code'] = code
    d['open'], d['close'] = c, c
    d['high'] = c * 1.01 if high is None else np.asarray(high, float)
    d['low'] = c * 0.99 if low is None else np.asarray(low, float)
    d['volume'] = np.full(n, 1000.0) if vol is None else np.asarray(vol, float)
    d['ycp'] = np.r_[c[0], c[:-1]] if ycp is None else np.asarray(ycp, float)
    return d


# ১. CLV = ((C−L) − (H−C)) ÷ (H−L): ক্লোজ হাই-তে = +১, লো-তে = −১, মাঝে = ০ → ফ্লো ঠিক সেই মান
n = 60
for close_frac, expect in ((1.0, 1.0), (0.0, -1.0), (0.5, 0.0)):
    lo, hi = np.full(n, 99.0), np.full(n, 101.0)
    c = lo + (hi - lo) * close_frac
    d = frame(n, close=c, high=hi, low=lo)
    d['open'] = c                                           # ওপেন ক্লোজের সমান, যাতে রেঞ্জ না বদলায়
    P = pressure_panel(d)
    assert abs(P['clv'].iloc[-1] - expect) < 1e-9, (close_frac, P['clv'].iloc[-1])
    assert abs(P['flow10'].iloc[-1] - expect) < 1e-9

# ২. রেঞ্জ-লক (H = L), আপার সার্কিট: ভলিউম থাকলে CLV = +১ ও লক-আপ; ভলিউম ০ হলে চাপ ০ ও নিষ্ক্রিয়-দিন গোনা
c = np.full(n, 100.0); c[-1] = 110.0
d = frame(n, close=c, high=c, low=c, ycp=np.r_[100.0, c[:-1]])
P = pressure_panel(d)
assert P['lock_up'].iloc[-1] and not P['lock_dn'].iloc[-1] and P['clv'].iloc[-1] == 1.0
assert P['gone'].iloc[-1] == 'up'                               # আপার সার্কিট = নাগালের বাইরে
v = np.full(n, 1000.0); v[-3:] = 0
P = pressure_panel(frame(n, vol=v))
assert list(P['idle'].iloc[-4:]) == [0, 1, 2, 3] and P['clv'].iloc[-1] == 0.0

# ৩. স্কোরের সীমা ও অবস্থা: সারাক্ষণ রেঞ্জের মাথায় বন্ধ + বাড়তি ভলিউম = বাইং হাই; উল্টো = সেলিং হাই; সমতল = নিউট্রাল
lo, hi = np.full(n, 99.0), np.full(n, 101.0)
vol = np.full(n, 1000.0)
Pb = pressure_panel(frame(n, close=hi - 0.1, high=hi, low=lo, vol=vol)).iloc[-1]
Ps = pressure_panel(frame(n, close=lo + 0.1, high=hi, low=lo, vol=vol)).iloc[-1]
Pn = pressure_panel(frame(n, close=(hi + lo) / 2, high=hi, low=lo, vol=vol)).iloc[-1]
assert Pb['state'] == 'buy' and Ps['state'] == 'sell' and Pn['state'] == 'neutral', (Pb['state'], Ps['state'], Pn['state'])
for r in (Pb, Ps, Pn):
    assert 0 <= r['bp'] <= 100 and 0 <= r['sp'] <= 100 and 0 <= r['ps'] <= 100
assert Pb['ps'] > 50 > Ps['ps'] and abs(Pn['ps'] - 50) < 1e-9
assert Pb['sp'] == 0 and Ps['bp'] == 0                           # একদিকের চাপ থাকলে উল্টো দিকের উপাদান শূন্য

# ৪. ভবিষ্যৎ দেখে না: শেষ k দিন বদলে/কেটে দিলেও আগের দিনগুলোর স্কোর অপরিবর্তিত
rs = np.random.RandomState(7)
cl = 100 * np.cumprod(1 + rs.normal(0, 0.02, 120))
hh, ll = cl * (1 + rs.uniform(0, 0.02, 120)), cl * (1 - rs.uniform(0, 0.02, 120))
vv = rs.randint(500, 5000, 120).astype(float)
full = frame(120, close=cl, high=hh, low=ll, vol=vv)
cut = full.iloc[:90].copy()
alt = full.copy(); alt.loc[90:, 'close'] *= 1.5; alt.loc[90:, 'volume'] *= 7
cols = ['bp', 'sp', 'ps', 'gone']
A, B, C = (pressure_panel(x).iloc[:90][cols].reset_index(drop=True) for x in (full, cut, alt))
assert np.allclose(A[['bp', 'sp', 'ps']].to_numpy(float), B[['bp', 'sp', 'ps']].to_numpy(float), equal_nan=True)
assert np.allclose(A[['bp', 'sp', 'ps']].to_numpy(float), C[['bp', 'sp', 'ps']].to_numpy(float), equal_nan=True)
assert (A['gone'] == B['gone']).all() and (A['gone'] == C['gone']).all()

# ৫. কাটা-ডেটায় (tail) গণনা পুরো ইতিহাসের সমান ফল দেয় (দৈনিক স্ক্যান দ্রুত রাখার শর্ত)
long = pd.concat([frame(400, close=100 * np.cumprod(1 + rs.normal(0, 0.02, 400)), vol=rs.randint(500, 5000, 400).astype(float), code=k) for k in ('X', 'Y')], ignore_index=True)
long['high'], long['low'] = long['close'] * 1.01, long['close'] * 0.99
L1 = pressure_panel(long).sort_values(['code', 'date']).groupby('code').tail(1).set_index('code')
L2 = pressure_latest(long)
assert np.allclose(L1[['bp', 'sp', 'ps']].to_numpy(float), L2.loc[L1.index, ['bp', 'sp', 'ps']].to_numpy(float), equal_nan=True)

# ৬. আসল ডেটা: সীমা ও অবস্থার মান ঠিক
P = load_prices_ycp(ROOT)
codes = sorted(P['code'].unique())[::25]
R = pressure_panel(P[P['code'].isin(codes)])
v = R[R['state'] != '']
assert len(v) > 0 and set(v['state']) <= {'buy', 'sell', 'neutral'} and set(R['gone']) <= {'', 'up', 'dn'}
assert v[['bp', 'sp', 'ps']].stack().between(0, 100).all()
assert ((v['bp'] - v['sp']).abs() < PCfg().state_gap).eq(v['state'] == 'neutral').all()
print('test_pressure_engine: সব ঠিক')
