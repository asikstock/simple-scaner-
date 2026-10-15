"""ওয়াইকফ গঠনের ধারাবাহিকতা যাচাই (SC → AR → ST এবং BC → AR → ST)।

ফেজ-লেবেল (phase_engine.classify) আলাদা আলাদা ক্যান্ডেল-প্যাটার্ন ধরে। এই মডিউল জিজ্ঞেস করে: সেই প্যাটার্নের আগে
ওয়াইকফ-বর্ণিত গঠন আসলেই তৈরি হয়েছিল কি? শুধু ট্রেইলিং ডেটা ব্যবহার করে (ভবিষ্যৎ দেখে না); প্রতিটি দিনে ঠিক ততদিনের ডেটাই।

অ্যাকিউমুলেশন (দীর্ঘ পতনের পর)
  SC  = phase_engine-এর e_sc ইভেন্ট (উচ্চ ভলিউমে নতুন নিম্ন)।
  AR  = SC-র পর AR_WIN দিনের মধ্যে ওঠা; SC-র আগের পতনের (১২০ দিনের উচ্চ − SC লো) অন্তত AR_MIN অংশ ফিরে এলে বৈধ।
  ST  = AR-এর পর (AR_WIN দিন শেষ হলে) আবার SC লো-র ±ST_BAND-এর মধ্যে নামা, আর সেদিনের ভলিউম SC-র ভলিউমের ST_VOL গুণের মধ্যে।
  বাতিল = SC লো-র BREAK-এর বেশি নিচে ক্লোজ করলে গঠন ভেঙে গেল (নতুন SC না আসা পর্যন্ত স্তর ০)।
ডিস্ট্রিবিউশন একই যুক্তি উল্টো দিক থেকে, BC (e_bc) থেকে শুরু: AR = নিচে নামা, ST = BC হাই-এর কাছে ফেরা।

স্তর: ০ = গঠন নেই বা বাতিল; ১ = SC/BC + AR আছে, ST এখনও নয়; ২ = SC/BC + AR + ST (গঠন নিশ্চিত)।
সহায়ক: অ্যাকিউমুলেশনে AR-এর পর থেকে আজ পর্যন্ত আপ-ডে ভলিউম ≥ ডাউন-ডে ভলিউম (চাহিদা সরবরাহের চেয়ে কম নয়),
ডিস্ট্রিবিউশনে উল্টো।

এই সংখ্যাগুলো (০.৩০, ১৫, ০.৬, ০.০৫, ০.০৫, ১৫০) আমাদের নিজস্ব অপারেশনাল সংজ্ঞা। রিপোর্ট বা ওয়াইকফের কোনো ধ্রুব সংখ্যা নয়,
এবং ব্যাকটেস্টের ফল দেখে বদলানো হয়নি।
"""
import numpy as np

AR_WIN = 15
AR_MIN = 0.30
ST_VOL = 0.6
ST_BAND = 0.05
BREAK = 0.05
MAX_AGE = 150


def _side(h, l, c, v, flag, ref_extreme, accumulate, ar_win, ar_min, st_vol, st_band, brk, max_age):
    """একদিকের গঠন। accumulate=True: SC-র গঠন (লো-ভিত্তিক); False: BC-র গঠন (হাই-ভিত্তিক)।
    ref_extreme = প্রতি দিনের ১২০ দিনের উচ্চ (acc) বা নিম্ন (dist), অর্থাৎ SC/BC-র আগের চলনের শুরু।"""
    n = len(c)
    lvl = np.zeros(n)
    age = np.full(n, np.nan)
    ar_frac = np.full(n, np.nan)
    st_ok = np.zeros(n, dtype=bool)
    bal = np.full(n, np.nan)                       # AR-এর পর থেকে ভলিউম-ভারসাম্য
    dem = np.full(n, np.nan)

    pc = np.r_[c[0], c[:-1]]
    up_v = np.where(c > pc, v, 0.0)
    dn_v = np.where(c < pc, v, 0.0)
    cu, cd = np.cumsum(up_v), np.cumsum(dn_v)

    active = False
    s = ar_i = -1
    anchor = anchor_v = move = 0.0
    ar_ext = np.nan
    st = invalid = False
    for t in range(n):
        if flag[t]:
            ext = l[t] if accumulate else h[t]
            newer = (not active) or (ext < anchor if accumulate else ext > anchor)
            mv = (ref_extreme[t] - ext) if accumulate else (ext - ref_extreme[t])
            if newer and mv > 0:
                active, s, anchor, anchor_v, move = True, t, ext, v[t], mv
                ar_i, ar_ext, st, invalid = -1, np.nan, False, False
                age[t] = 0
                continue
        if not active:
            continue
        a = t - s
        if a > max_age:
            active = False
            continue
        age[t] = a
        if accumulate:
            if c[t] < anchor * (1 - brk):
                invalid = True
            if a <= ar_win and (ar_i < 0 or h[t] > ar_ext):
                ar_ext, ar_i = h[t], t
            frac = (ar_ext - anchor) / move if ar_i >= 0 else np.nan
        else:
            if c[t] > anchor * (1 + brk):
                invalid = True
            if a <= ar_win and (ar_i < 0 or l[t] < ar_ext):
                ar_ext, ar_i = l[t], t
            frac = (anchor - ar_ext) / move if ar_i >= 0 else np.nan
        ar_frac[t] = frac
        ar_ok = ar_i >= 0 and frac >= ar_min
        if ar_ok and not st and not invalid and a > ar_win and t >= ar_i + 3:
            near = (abs(l[t] / anchor - 1) <= st_band) if accumulate else (abs(h[t] / anchor - 1) <= st_band)
            if near and v[t] <= st_vol * anchor_v:
                st = True
        st_ok[t] = st
        if invalid or not ar_ok:
            lvl[t] = 0
        else:
            lvl[t] = 2 if st else 1
        if ar_i >= 0 and t - ar_i >= 5:
            u, d = cu[t] - cu[ar_i], cd[t] - cd[ar_i]
            tot = u + d
            if tot > 0:
                bal[t] = (u - d) / tot
                dem[t] = float(bal[t] >= 0) if accumulate else float(bal[t] <= 0)
    return lvl, age, ar_frac, st_ok, dem


def wyckoff_struct(h, l, c, v, sc, bc, h120, lo120, cfg=None):
    """ফেরত: dict — gacc_lvl, gacc_age, gacc_ar, gacc_st, gacc_dem, gdist_lvl, gdist_age, gdist_ar, gdist_st, gdist_sup (g = গঠন; phase_engine-এর বিদ্যমান dist_age ইত্যাদির সাথে নাম যেন না মেলে) (সব n-দৈর্ঘ্যের array)।"""
    g = lambda k, d: getattr(cfg, k, d) if cfg is not None else d
    p = dict(ar_win=g("ar_win", AR_WIN), ar_min=g("ar_min", AR_MIN), st_vol=g("st_vol", ST_VOL),
             st_band=g("st_band", ST_BAND), brk=g("struct_brk", BREAK), max_age=g("struct_age", MAX_AGE))
    h, l, c, v = (np.asarray(x, float) for x in (h, l, c, v))
    sc, bc = np.asarray(sc, bool), np.asarray(bc, bool)
    al, aa, ar, ast, adem = _side(h, l, c, v, sc, np.asarray(h120, float), True, **p)
    dl, da, dr, dst, dsup = _side(h, l, c, v, bc, np.asarray(lo120, float), False, **p)
    return {"gacc_lvl": al, "gacc_age": aa, "gacc_ar": ar, "gacc_st": ast, "gacc_dem": adem,
            "gdist_lvl": dl, "gdist_age": da, "gdist_ar": dr, "gdist_st": dst, "gdist_sup": dsup}
