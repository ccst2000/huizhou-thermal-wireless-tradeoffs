# -*- coding: utf-8 -*-
"""V6 s64b: 热链诊断（v6 口径；R5-P0-7 路径参数化）
a) V3 匹配诊断: 每村匹配前后标准化均差(SMD)、z 空间匹配距离、caliper(0.5/0.25 SD)失配率
b) 水体掩膜阈值统一性: 核心像元水占比 (0.05,0.5] 的份额; V1-strict(≤0.05) ΔLST 敏感性
c) 绝对 LST estimand: 过境去重均值(主) vs 去重中位合成栅格直接提取(敏感性), 同 V1 掩膜
变更: 读 data/v3_master_v6.csv；WorldCover 瓦片经 code/v3_inputs.wc_tile 获取
      （首次运行自动从 ESA 公开桶下载到 data/external/）；
      汇总写入 data/stats_v6.json。
输出:
  tables/TableA15_match_diagnostics.csv
  tables/TableA16_watermask_sensitivity.csv
  data/lst_abs_composite_v6.csv
"""
import os
import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.windows import from_bounds
from pyproj import Transformer
from scipy import stats

from v3_inputs import wc_tile

# ---------- 网格与协变量（同 s56） ----------
with rasterio.open("data/lst_grid_ref.tif") as s:
    H, W = s.height, s.width
    dst_tr = s.transform
    bounds = s.bounds
res = 100.0
left, top = bounds.left, bounds.top

with rasterio.open("data/dem_utm30.tif") as s:
    dem30 = s.read(1)
    tr30 = s.transform
gy, gx = np.gradient(dem30, 30.0)
slope30 = np.degrees(np.arctan(np.hypot(gx, gy))).astype("float32")


def to100(src, srctr, resampling=Resampling.bilinear):
    dst = np.full((H, W), np.nan, dtype="float32")
    reproject(src, dst, src_transform=srctr, src_crs="EPSG:32650",
              dst_transform=dst_tr, dst_crs="EPSG:32650", resampling=resampling, dst_nodata=np.nan)
    return dst


elev100 = to100(dem30, tr30, Resampling.bilinear)
slope100 = to100(slope30, tr30, Resampling.bilinear)

inv = Transformer.from_crs(32650, 4326, always_xy=True)
lon0, lat0 = inv.transform(bounds.left, bounds.bottom)
lon1, lat1 = inv.transform(bounds.right, bounds.top)
pad = 0.02
fracs = {}
for code, name in [(10, "tree"), (50, "built"), (80, "water")]:
    acc = np.zeros((H, W), dtype="float64")
    cnt = np.zeros((H, W), dtype="float64")
    for n in (27, 30):
        p = wc_tile(n)
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
            tmp = np.full((H, W), np.nan, dtype="float32")
            reproject(onehot, tmp, src_transform=wtr, src_crs=s.crs,
                      dst_transform=dst_tr, dst_crs="EPSG:32650",
                      resampling=Resampling.average, dst_nodata=np.nan)
            acc = np.where(np.isfinite(tmp), np.nan_to_num(tmp) + np.nan_to_num(acc), acc)
            cnt = np.where(np.isfinite(tmp), cnt + 1, cnt)
    fracs[name] = np.where(cnt > 0, acc / np.maximum(cnt, 1), np.nan).astype("float32")
tree100, built100f, water100 = fracs["tree"], fracs["built"], fracs["water"]
print("grids done", flush=True)

m = pd.read_csv("data/v3_master_v6.csv")
tf = Transformer.from_crs(4326, 32650, always_xy=True)


def greedy_match_diag(core_idx, pool_idx, feats):
    """1:1 无放回贪婪匹配 + 诊断: 返回 matched pool idx, z距离列表, 每维特征值"""
    Xc = np.column_stack([f[core_idx] for f in feats])
    Xp = np.column_stack([f[pool_idx] for f in feats])
    mu, sd = np.nanmean(Xc, axis=0), np.nanstd(Xc, axis=0) + 1e-9
    Zc = (Xc - mu) / sd
    Zp = (Xp - mu) / sd
    D = np.sqrt(((Zc[:, None, :] - Zp[None, :, :]) ** 2).sum(axis=2))
    order = np.dstack(np.unravel_index(np.argsort(D, axis=None), D.shape))[0]
    used_c, used_p = set(), set()
    pick, dists = [], []
    for ci, pi in order:
        if ci in used_c or pi in used_p:
            continue
        used_c.add(ci); used_p.add(pi)
        pick.append(pi); dists.append(float(D[ci, pi]))
        if len(used_c) == len(Zc):
            break
    pr, pc = pool_idx
    return (pr[pick], pc[pick]), np.array(dists), Zc, Zp, pick, D


diag_rows = []
water_rows = []
masks_strict = {}
masks_v1 = {}
for _, v in m.iterrows():
    cx, cy = tf.transform(v.lon, v.lat)
    cols = np.arange(max(0, int((cx - 2200 - left) / res)), min(W, int((cx + 2200 - left) / res) + 1))
    rws = np.arange(max(0, int((top - cy - 2200) / res)), min(H, int((top - cy + 2200) / res) + 1))
    RR, CC = np.meshgrid(rws, cols, indexing="ij")
    X = left + (CC + 0.5) * res
    Y = top - (RR + 0.5) * res
    d2 = (X - cx) ** 2 + (Y - cy) ** 2
    dom = d2 <= 500 ** 2
    core_dom = dom & (water100[RR, CC] <= 0.5)
    core_strict = dom & (water100[RR, CC] <= 0.05)
    ring_bas = (d2 > 1000 ** 2) & (d2 <= 2000 ** 2) & (built100f[RR, CC] <= 0.05) & (water100[RR, CC] <= 0.05)
    pool = ring_bas & np.isfinite(elev100[RR, CC]) & np.isfinite(slope100[RR, CC])
    cd_idx = (RR[core_dom], CC[core_dom])
    pool_idx = (RR[pool], CC[pool])
    masks_v1[v.village] = cd_idx
    masks_strict[v.village] = (RR[core_strict], CC[core_strict])
    # 水体阈值: 核心像元中水占比 (0.05, 0.5] 的份额
    wcore = water100[cd_idx]
    water_rows.append(dict(village=v.village, n_core=len(wcore),
                           n_core_strict=int(core_strict.sum()),
                           share_mid=round(float(((wcore > 0.05) & (wcore <= 0.5)).mean()), 4)))
    if len(cd_idx[0]) >= 5 and len(pool_idx[0]) >= 5:
        m_idx, dists, Zc, Zp, pick, D = greedy_match_diag(cd_idx, pool_idx,
                                                          [elev100, slope100, tree100])
        feats = dict(elev=(elev100, ), slope=(slope100, ), tree=(tree100, ))
        row = dict(village=v.village, n_core=len(cd_idx[0]), n_matched=len(pick),
                   fail_rate=round(1 - len(pick) / len(cd_idx[0]), 4),
                   dist_mean=round(float(dists.mean()), 3), dist_max=round(float(dists.max()), 3))
        # caliper 失配率
        for cal in (0.5, 0.25):
            row[f"over_caliper_{cal}"] = round(float((dists > cal * np.sqrt(3)).mean()), 4)
        # SMD before/after
        for fi, fname in enumerate(["elev", "slope", "tree"]):
            f = feats[fname][0]
            xc = f[cd_idx]; xp = f[pool_idx]; xm = f[m_idx]
            sd0 = np.sqrt((np.nanvar(xc) + np.nanvar(xp)) / 2) + 1e-9
            row[f"smd_{fname}_before"] = round(float((np.nanmean(xc) - np.nanmean(xp)) / sd0), 3)
            row[f"smd_{fname}_after"] = round(float((np.nanmean(xc) - np.nanmean(xm)) / sd0), 3)
        diag_rows.append(row)
    print(f"diag {v.village}", flush=True)

pd.DataFrame(diag_rows).to_csv("tables/TableA15_match_diagnostics.csv", index=False, encoding="utf-8-sig")

# ---------- 过境镶嵌（同 s56） ----------
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
    ops[opid] = (np.nanmean(np.where(np.isfinite(st), st, np.nan), axis=0), g.date.iloc[0])
print(f"overpasses: {len(ops)}", flush=True)

NEAR_ZERO = {"2020-06-27"}
ring_cache = {}
for _, v in m.iterrows():
    cx, cy = tf.transform(v.lon, v.lat)
    cols = np.arange(max(0, int((cx - 2200 - left) / res)), min(W, int((cx + 2200 - left) / res) + 1))
    rws = np.arange(max(0, int((top - cy - 2200) / res)), min(H, int((top - cy + 2200) / res) + 1))
    RR, CC = np.meshgrid(rws, cols, indexing="ij")
    X = left + (CC + 0.5) * res
    Y = top - (RR + 0.5) * res
    d2 = (X - cx) ** 2 + (Y - cy) ** 2
    ring = (d2 > 1000 ** 2) & (d2 <= 2000 ** 2) & (built100f[RR, CC] <= 0.05) & (water100[RR, CC] <= 0.05)
    ring_cache[v.village] = (RR[ring], CC[ring])

# ---------- V1-strict 水体掩膜敏感性 ----------
lv1 = pd.read_csv("data/lst_village_v4.csv")
v1_main = lv1[lv1.variant == "V1"].set_index("village").dlst
strict_rows = []
for vname in m.village:
    cs = masks_strict[vname]
    rb = ring_cache[vname]
    ds = []
    for opid, (arr, date) in ops.items():
        if date in NEAR_ZERO:
            continue
        zc = arr[cs]; zb = arr[rb]
        zc = zc[np.isfinite(zc)]; zb = zb[np.isfinite(zb)]
        if len(zc) >= 5 and len(zb) >= 5:
            ds.append(float(zc.mean() - zb.mean()))
    d_strict = float(np.mean(ds)) if len(ds) >= 3 else np.nan
    strict_rows.append(dict(village=vname, dlst_v1_strict=round(d_strict, 3) if np.isfinite(d_strict) else np.nan,
                            n_over=len(ds), dlst_v1_main=float(v1_main.get(vname, np.nan))))
sr = pd.DataFrame(strict_rows)
cmp_ = sr.dropna()
rank_r = stats.spearmanr(cmp_.dlst_v1_main, cmp_.dlst_v1_strict).statistic
print(f"\nV1 strict-water-mask sensitivity: rank rho={rank_r:.3f}, "
      f"max|delta|={np.abs(cmp_.dlst_v1_main - cmp_.dlst_v1_strict).max():.2f} degC")
wm = pd.DataFrame(water_rows).merge(sr[["village", "dlst_v1_strict"]], on="village")
wm.to_csv("tables/TableA16_watermask_sensitivity.csv", index=False, encoding="utf-8-sig")

# ---------- 绝对 LST estimand: 合成栅格直接提取 ----------
with rasterio.open("data/lst_summer_median_v4.tif") as s:
    comp = s.read(1).astype("float32")
    assert (s.width, s.height) == (W, H), "composite grid mismatch"
comp = np.where(comp > 0, comp, np.nan)
comp_rows = []
for vname in m.village:
    cd = masks_v1[vname]
    z = comp[cd]
    z = z[np.isfinite(z)]
    comp_rows.append(dict(village=vname, lst_abs_composite=round(float(z.mean()), 2) if len(z) >= 5 else np.nan,
                          n_px=len(z)))
la = pd.DataFrame(comp_rows).merge(pd.read_csv("data/lst_abs_village_v4.csv")[["village", "lst_abs"]], on="village")
cmp2 = la.dropna()
r2 = stats.spearmanr(cmp2.lst_abs, cmp2.lst_abs_composite).statistic
bias = float((cmp2.lst_abs - cmp2.lst_abs_composite).mean())
print(f"absolute LST estimands: overpass-mean vs composite-median-extract: "
      f"rank rho={r2:.3f}, mean bias={bias:+.2f} degC, n={len(cmp2)}")
la.to_csv("data/lst_abs_composite_v6.csv", index=False)

# 汇总进 stats_v6
import json
with open("data/stats_v6.json", encoding="utf-8") as f:
    S = json.load(f)
S["lst_abs_estimand_check"] = dict(rank_rho=round(float(r2), 3), mean_bias=round(bias, 2), n=int(len(cmp2)))
S["v1_watermask_strict"] = dict(rank_rho=round(float(rank_r), 3),
                                max_abs_delta=round(float(np.abs(cmp_.dlst_v1_main - cmp_.dlst_v1_strict).max()), 2),
                                n=int(len(cmp_)))
dd = pd.DataFrame(diag_rows)
S["match_diag"] = dict(smd_elev_after_max=round(float(dd.smd_elev_after.abs().max()), 3),
                       smd_slope_after_max=round(float(dd.smd_slope_after.abs().max()), 3),
                       smd_tree_after_max=round(float(dd.smd_tree_after.abs().max()), 3),
                       dist_mean_median=round(float(dd.dist_mean.median()), 3),
                       over_caliper_05_median=round(float(dd["over_caliper_0.5"].median()), 4))
with open("data/stats_v6.json", "w", encoding="utf-8") as f:
    json.dump(S, f, ensure_ascii=False, indent=1)
print("\nALL S64B DONE")
