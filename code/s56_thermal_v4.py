# -*- coding: utf-8 -*-
"""V3 s56 (Round-3 revision, P0-1 + P0-2): 热链重算
- 同平台+同 path+同日期 的相邻 WRS row 资产按过境合并（像元级镶嵌：双有效取均值）
- near-zero 过境对 (2020-06-27, 两 path) 主分析剔除，敏感性保留
- 三种 core/ring 定义：
  V1 site-domain: core=500m 域（掩水体）；ring=1-2km 非建成、掩水体
  V2 fabric:      core=500m 域内建成像元（掩水体）；ring 同 V1
  V3 matched:     core 同 V1；ring 在 V1 基础上按 (海拔, 坡度, 树冠比例) 贪婪 1:1 匹配
- 区块 bootstrap：以独立过境（日期）为重抽单元，B=10000，seed=7
- 有效像元阈值：主分析 >=5 px/区；敏感性 >=25% 区覆盖率
输出:
  data/dlst_overpass_matrix_v4.csv  村 x 过境 x 变体 长表
  data/lst_village_v4.csv           村 x 变体 汇总 (mean/CI/p_pos/n_over)
  data/lst_abs_village_v4.csv       村域绝对 LST（V1 域，过境去重均值+CI）
  data/thermal_zone_coverage.csv    每村各区像元规模
用法: python s56_thermal_v4.py
"""
import os
import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.windows import from_bounds
from pyproj import Transformer
from scipy import stats

RNG = np.random.default_rng(7)
B = 10000
V2DAT = "../v2-paper/data"

# ---------- 100m LST 网格 ----------
with rasterio.open("data/lst_summer_mean.tif") as s:
    H, W = s.height, s.width
    dst_tr = s.transform
    bounds = s.bounds
res = 100.0
left, top = bounds.left, bounds.top
print(f"LST grid: {W}x{H} @100m")

# ---------- 协变量：海拔/坡度 (dem_utm30 -> 100m) ----------
with rasterio.open("data/dem_utm30.tif") as s:
    dem30 = s.read(1)
    tr30 = s.transform
# 30m 坡度
gy, gx = np.gradient(dem30, 30.0)
slope30 = np.degrees(np.arctan(np.hypot(gx, gy))).astype("float32")

def to100(src, srctr, resampling=Resampling.bilinear):
    dst = np.full((H, W), np.nan, dtype="float32")
    reproject(src, dst, src_transform=srctr, src_crs="EPSG:32650",
              dst_transform=dst_tr, dst_crs="EPSG:32650", resampling=resampling, dst_nodata=np.nan)
    return dst

elev100 = to100(dem30, tr30, Resampling.bilinear)
slope100 = to100(slope30, tr30, Resampling.bilinear)
print("elev100/slope100 done. elev range %.0f-%.0f m" % (np.nanmin(elev100), np.nanmax(elev100)))

# ---------- 协变量：WorldCover 类别比例 (10m geographic -> 100m UTM) ----------
inv = Transformer.from_crs(32650, 4326, always_xy=True)
lon0, lat0 = inv.transform(bounds.left, bounds.bottom)
lon1, lat1 = inv.transform(bounds.right, bounds.top)
pad = 0.02
wc = np.zeros((H, W), dtype="uint8")  # placeholder for shape
fracs = {}
for code, name in [(10, "tree"), (50, "built"), (80, "water")]:
    acc = np.zeros((H, W), dtype="float64")
    cnt = np.zeros((H, W), dtype="float64")
    for n in (27, 30):
        p = f"{V2DAT}/wc_N{n}E117.tif"
        with rasterio.open(p) as s:
            b = s.bounds
            l0, r1 = max(lon0 - pad, b.left), min(lon1 + pad, b.right)
            b0, t1 = max(lat0 - pad, b.bottom), min(lat1 + pad, b.top)
            if l0 >= r1 or b0 >= t1:
                continue
            win = from_bounds(l0, b0, r1, t1, s.transform).round_offsets().round_lengths()
            arr = s.read(1, window=win)
            wtr = s.window_transform(win)
            onehot = (arr == code).astype("float32")
            del arr
            tmp = np.full((H, W), np.nan, dtype="float32")
            reproject(onehot, tmp, src_transform=wtr, src_crs=s.crs,
                      dst_transform=dst_tr, dst_crs="EPSG:32650",
                      resampling=Resampling.average, dst_nodata=np.nan)
            del onehot
            acc = np.where(np.isfinite(tmp), np.nan_to_num(tmp) + np.nan_to_num(acc), acc)
            cnt = np.where(np.isfinite(tmp), cnt + 1, cnt)
            print(f"  WC class {code} tile N{n}: window {arr_shape(arr) if False else ''}done")
    fracs[name] = np.where(cnt > 0, acc / np.maximum(cnt, 1), np.nan).astype("float32")
    print(f"{name}_frac100 done")
tree100, built100f, water100 = fracs["tree"], fracs["built"], fracs["water"]

# ---------- 村域掩膜 ----------
m = pd.read_csv("data/v3_master.csv")
tf = Transformer.from_crs(4326, 32650, always_xy=True)

def greedy_match(core_idx, pool_idx, feats):
    """core_idx/pool_idx: (rows, cols); feats: list of 2D arrays。1:1 无放回贪婪匹配。"""
    Xc = np.column_stack([f[core_idx] for f in feats])
    Xp = np.column_stack([f[pool_idx] for f in feats])
    mu, sd = np.nanmean(Xc, axis=0), np.nanstd(Xc, axis=0) + 1e-9
    Zc = (Xc - mu) / sd
    Zp = (Xp - mu) / sd
    # 距离矩阵 (core x pool)
    D = np.sqrt(((Zc[:, None, :] - Zp[None, :, :]) ** 2).sum(axis=2))
    order = np.dstack(np.unravel_index(np.argsort(D, axis=None), D.shape))[0]
    used_c, used_p = set(), set()
    pick = []
    for ci, pi in order:
        if ci in used_c or pi in used_p:
            continue
        used_c.add(ci); used_p.add(pi)
        pick.append(pi)
        if len(used_c) == len(Zc):
            break
    pr, pc = pool_idx
    return (pr[pick], pc[pick])

masks = {}
cov_rows = []
for _, v in m.iterrows():
    cx, cy = tf.transform(v.lon, v.lat)
    cols = np.arange(max(0, int((cx - 2200 - left) / res)), min(W, int((cx + 2200 - left) / res) + 1))
    rws = np.arange(max(0, int((top - cy - 2200) / res)), min(H, int((top - cy + 2200) / res) + 1))
    RR, CC = np.meshgrid(rws, cols, indexing="ij")
    X = left + (CC + 0.5) * res
    Y = top - (RR + 0.5) * res
    d2 = (X - cx) ** 2 + (Y - cy) ** 2
    water_ok = (water100[RR, CC] <= 0.5)          # 显式水体掩膜
    dom = d2 <= 500 ** 2
    core_dom = dom & water_ok
    core_blt = dom & water_ok & (built100f[RR, CC] > 0.5)
    ring_bas = (d2 > 1000 ** 2) & (d2 <= 2000 ** 2) & (built100f[RR, CC] <= 0.05) & (water100[RR, CC] <= 0.05)
    # 匹配环：非建成、非水体、且地形/植被可匹配
    pool = ring_bas & np.isfinite(elev100[RR, CC]) & np.isfinite(slope100[RR, CC])
    cd_idx = (RR[core_dom], CC[core_dom])
    pool_idx = (RR[pool], CC[pool])
    if len(cd_idx[0]) >= 5 and len(pool_idx[0]) >= 5:
        m_idx = greedy_match(cd_idx, pool_idx, [elev100, slope100, tree100])
    else:
        m_idx = (np.array([], dtype=int), np.array([], dtype=int))
    masks[v.village] = dict(V1=(cd_idx, (RR[ring_bas], CC[ring_bas])),
                            V2=((RR[core_blt], CC[core_blt]), (RR[ring_bas], CC[ring_bas])),
                            V3=(cd_idx, m_idx))
    cov_rows.append(dict(village=v.village,
                         n_core_dom=len(cd_idx[0]), n_core_built=int(core_blt.sum()),
                         n_ring_base=int(ring_bas.sum()), n_ring_matched=len(m_idx[0]),
                         water_share_ring=round(float(np.nanmean(water100[RR[(d2 > 1000 ** 2) & (d2 <= 2000 ** 2)], CC[(d2 > 1000 ** 2) & (d2 <= 2000 ** 2)]])), 4)))
    print(f"  {v.village}: core_dom={len(cd_idx[0])} core_blt={int(core_blt.sum())} ring={int(ring_bas.sum())} matched={len(m_idx[0])}")
pd.DataFrame(cov_rows).to_csv("data/thermal_zone_coverage.csv", index=False)

# ---------- 过境合并：同 platform+path+date 的 row 39/40 像元级镶嵌 ----------
man = pd.read_csv("data/lst_scene_manifest.csv")
man["platform"] = man["id"].str[:4]
man["opid"] = man.platform + "_" + man.path.astype(str) + "_" + man.date
ops = {}
for opid, g in man.groupby("opid"):
    arrs = []
    for sid in g.id:
        f = f"data/lst_v2_scenes/{sid}.npy"
        if os.path.exists(f):
            arrs.append(np.load(f))
    if not arrs:
        continue
    st = np.stack(arrs).astype("float32")
    op_arr = np.nanmean(np.where(np.isfinite(st), st, np.nan), axis=0)
    ops[opid] = (op_arr, g.date.iloc[0])
print(f"overpasses: {len(ops)} (from {len(man)} scene assets)")

NEAR_ZERO_DATES = {"2020-06-27"}   # 两 path 各 ~0.01% 有效像元

def village_series(vname, variant, exclude_nearzero=True, min_px=5, min_cov=0.0):
    """返回 (date, dlst, n_core, n_ring, core_mean_abs) 列表"""
    core_idx, ring_idx = masks[vname][variant]
    out = []
    core_full = max(1, int(core_idx[0].size))  # 本分变体 core 总像元用于覆盖率口径
    for opid, (arr, date) in ops.items():
        if exclude_nearzero and date in NEAR_ZERO_DATES:
            continue
        zc = arr[core_idx]; zb = arr[ring_idx]
        zc = zc[np.isfinite(zc)]; zb = zb[np.isfinite(zb)]
        if len(zc) >= max(min_px, min_cov * core_full) and len(zb) >= min_px:
            out.append((date, float(zc.mean() - zb.mean()), len(zc), len(zb), float(zc.mean())))
    return out

# ---------- 汇总 + 过境区块 bootstrap ----------
rows = []
mat_rows = []
for vname in m.village:
    for variant in ["V1", "V2", "V3"]:
        ser = village_series(vname, variant)
        # 阈值敏感性：>=25% 覆盖
        ser25 = village_series(vname, variant, min_cov=0.25)
        # near-zero 保留敏感性
        ser_nz = village_series(vname, variant, exclude_nearzero=False)
        for date, d, nc, nb, cm in ser:
            mat_rows.append(dict(village=vname, overpass_date=date, variant=variant,
                                 dlst=round(d, 3), n_core=nc, n_ring=nb, core_lst=round(cm, 2)))
        x = np.array([d for _, d, _, _, _ in ser])
        n = len(x)
        if n >= 3:
            boots = RNG.choice(x, size=(B, n), replace=True).mean(axis=1)
            lo, hi = np.percentile(boots, [2.5, 97.5])
            row = dict(village=vname, variant=variant, dlst=round(float(x.mean()), 2),
                       sd=round(float(x.std(ddof=1)), 2), n_over=n,
                       ci_lo=round(float(lo), 2), ci_hi=round(float(hi), 2),
                       p_pos=round(float((boots > 0).mean()), 4), sig_pos=bool(lo > 0))
        else:
            row = dict(village=vname, variant=variant, dlst=np.nan, sd=np.nan, n_over=n,
                       ci_lo=np.nan, ci_hi=np.nan, p_pos=np.nan, sig_pos=False)
        row["dlst_cov25"] = round(float(np.mean([d for _, d, _, _, _ in ser25])), 2) if len(ser25) >= 3 else np.nan
        row["n_over_cov25"] = len(ser25)
        row["dlst_with_nearzero"] = round(float(np.mean([d for _, d, _, _, _ in ser_nz])), 2) if len(ser_nz) >= 3 else np.nan
        rows.append(row)

lv4 = pd.DataFrame(rows)
lv4.to_csv("data/lst_village_v4.csv", index=False)
pd.DataFrame(mat_rows).to_csv("data/dlst_overpass_matrix_v4.csv", index=False)

# ---------- 村域绝对 LST（V1 域，过境级，供 tsvf~lst 相关与表格使用） ----------
abs_rows = []
for vname in m.village:
    ser = village_series(vname, "V1")
    xa = np.array([cm for _, _, _, _, cm in ser])
    n = len(xa)
    if n >= 3:
        boots = RNG.choice(xa, size=(B, n), replace=True).mean(axis=1)
        lo, hi = np.percentile(boots, [2.5, 97.5])
        abs_rows.append(dict(village=vname, lst_abs=round(float(xa.mean()), 2),
                             ci_lo=round(float(lo), 2), ci_hi=round(float(hi), 2),
                             sd=round(float(xa.std(ddof=1)), 2), n_over=n))
    else:
        abs_rows.append(dict(village=vname, lst_abs=np.nan, ci_lo=np.nan, ci_hi=np.nan,
                             sd=np.nan, n_over=n))
absdf = pd.DataFrame(abs_rows)
absdf.to_csv("data/lst_abs_village_v4.csv", index=False)
print("\n村域绝对 LST（V1 域, 过境去重均值）: mean %.2f, range [%.2f, %.2f]" % (
    absdf.lst_abs.mean(), absdf.lst_abs.min(), absdf.lst_abs.max()))

print("\n=== V4 主结果（过境去重 + 区块 bootstrap）===")
for variant in ["V1", "V2", "V3"]:
    sub = lv4[lv4.variant == variant]
    ok = sub.dropna(subset=["dlst"])
    print(f"{variant}: n={len(ok)} villages, mean {ok.dlst.mean():.2f}, range [{ok.dlst.min():.2f}, {ok.dlst.max():.2f}], "
          f"positive {int((ok.dlst > 0).sum())}/{len(ok)}, CI>0 {int(ok.sig_pos.sum())}/{len(ok)}")
    neg = ok[ok.dlst <= 0]
    if len(neg):
        print("   非正点估计:", neg.village.tolist(), neg.dlst.tolist())

# 与 v3 对照
old = pd.read_csv("data/lst_village_v3.csv")
cmp_ = lv4[lv4.variant == "V1"].merge(old[["village", "dlst_v3"]], on="village")
cmp_["delta"] = (cmp_.dlst - cmp_.dlst_v3)
print("\nV1(去重) vs v3(未去重) 最大变化: %.2f °C (%s)" % (
    cmp_.delta.abs().max(), cmp_.loc[cmp_.delta.abs().idxmax(), "village"]))
print("rank corr:", round(stats.spearmanr(cmp_.dlst, cmp_.dlst_v3).statistic, 3))
print("\nALL S56 DONE")
