# -*- coding: utf-8 -*-
"""V3 s53 (Round-2): 10m WorldCover 逐村组分重建 + elong/compact 定义校准 + 水体占比
输出: data/morph_calib_10m.csv (校准对比), data/water_share_ring.csv (背景环水体占比)
"""
import math
import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.windows import from_bounds
from scipy import ndimage, stats
from pyproj import Transformer

import pystac_client
import planetary_computer as pc

cat = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1")
sr = cat.search(collections=["esa-worldcover"], bbox=[117.2, 29.5, 119.0, 30.4],
                datetime="2021-01-01/2021-12-31")
items = list(sr.items())
print("tiles found:", [it.id for it in items])
# 按 3° tile 网格选择: 如 ESA_WorldCover_10m_2021_v200_N30E117
import re
tile_map = {}
for it in items:
    mm_ = re.search(r"N(\d+)E(\d+)", it.id)
    if mm_:
        tile_map[(int(mm_.group(1)), int(mm_.group(2)))] = pc.sign(it).assets["map"].href

def tile_href(lon, lat):
    key = (int(lat // 3 * 3), int(lon // 3 * 3))
    return tile_map.get(key)

m = pd.read_csv("data/v3_master.csv")
mo = pd.read_csv("data/morphology_table.csv")
tf = Transformer.from_crs(4326, 32650, always_xy=True)
inv = Transformer.from_crs(32650, 4326, always_xy=True)

WC_RES = 10.0  # m nominal


def fetch_village_wc(cx, cy, half=1600.0):
    """以村心为中心的 10m WorldCover 窗口 (UTM 裁剪)"""
    href = tile_href(*inv.transform(cx, cy))
    if href is None:
        return None, None
    x0, y0 = inv.transform(cx - half, cy - half)
    x1, y1 = inv.transform(cx + half, cy + half)
    env = rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                       CPL_VSIL_CURL_USE_HEAD="FALSE", VSI_CACHE="TRUE")
    with env:
        with rasterio.open(href) as s:
            tfw = Transformer.from_crs(4326, s.crs, always_xy=True)
            wx0, wy0 = tfw.transform(x0, y0)
            wx1, wy1 = tfw.transform(x1, y1)
            win = from_bounds(wx0, wy0, wx1, wy1, s.transform)
            win = win.round_offsets().round_lengths()
            arr = s.read(1, window=win)
            tr = s.window_transform(win)
    return arr, tr


rows = []
water_rows = []
for _, v in m.iterrows():
    cx, cy = tf.transform(v.lon, v.lat)
    arr, tr = fetch_village_wc(cx, cy)
    if arr is None:
        print("no tile:", v.village)
        rows.append(dict(village=v.village))
        continue
    Hh, Ww = arr.shape
    # 像元中心经纬度 -> UTM（src 为 EPSG:4326）
    cols = np.arange(Ww); rws = np.arange(Hh)
    XX, YY = np.meshgrid(cols, rws)
    lon_g = tr.c + (XX + 0.5) * tr.a
    lat_g = tr.f + (YY + 0.5) * tr.e
    gx, gy = tf.transform(lon_g.ravel(), lat_g.ravel())
    gx = gx.reshape(Hh, Ww); gy = gy.reshape(Hh, Ww)
    d2 = (gx - cx) ** 2 + (gy - cy) ** 2
    # 该纬度下单像元实际面积（米制）
    lat0 = math.radians(v.lat)
    dx_m = abs(tr.a) * 111320.0 * math.cos(lat0)
    dy_m = abs(tr.e) * 110540.0
    PX_A = dx_m * dy_m
    built_m = arr == 50  # WorldCover built-up class
    # 组分：含最近建成像元的组分（500m 内）
    lab, n = ndimage.label(built_m, structure=np.ones((3, 3)))
    near = np.where((d2 < 500 ** 2) & (lab > 0), lab, 0)
    ids, cnts = np.unique(near[near > 0], return_counts=True)
    if len(ids) == 0:
        rows.append(dict(village=v.village))
        continue
    # 选含"离村心最近建成像元"的组分
    d2b = np.where(built_m, d2, np.inf)
    jmin = np.unravel_index(np.argmin(d2b), d2b.shape)
    cid = lab[jmin]
    mask = lab == cid
    A = mask.sum() * PX_A
    ys, xs = np.nonzero(mask)
    pts = np.column_stack([xs * dx_m, ys * dy_m]).astype(float)
    # 周长（逐暴露边）
    b = mask.astype(np.uint8)
    P = float(((b[:, :-1] != b[:, 1:]).sum() + (b[:-1, :] != b[1:, :]).sum()
               + b[0, :].sum() + b[-1, :].sum() + b[:, 0].sum() + b[:, -1].sum()) * (dx_m + dy_m) / 2)
    covm = np.cov(pts.T)
    ev = np.linalg.eigvalsh(covm)[::-1]
    elong_pca = math.sqrt(ev[0] / ev[1]) if ev[1] > 0 else np.nan
    vecs = np.linalg.eigh(covm)[1]
    pro = pts @ vecs
    L1 = pro[:, 1].max() - pro[:, 1].min()
    L2 = pro[:, 0].max() - pro[:, 0].min()
    elong_mbr = L1 / max(L2, 1e-9)
    isoq = 4 * math.pi * A / P ** 2
    try:
        from scipy.spatial import ConvexHull
        hull = ConvexHull(pts)
        solidity = A / (hull.volume)  # 2D: volume == area (pts 已是米制)
    except Exception:
        solidity = np.nan
    rows.append(dict(village=v.village, A_ha=A / 1e4, P_km=P / 1000,
                     elong_pca=round(elong_pca, 3), elong_mbr=round(elong_mbr, 3),
                     isoq=round(isoq, 4), solidity=round(solidity, 4)))
    # 水体占比：1-2km 环内 water class==80，剔除 built
    ring = (d2 > 1000 ** 2) & (d2 <= 2000 ** 2)
    ring_nonbuilt = ring & ~built_m
    water = ring_nonbuilt & (arr == 80)
    water_rows.append(dict(village=v.village,
                           ring_cells=int(ring_nonbuilt.sum()),
                           water_cells=int(water.sum()),
                           water_pct=round(100 * water.sum() / max(ring_nonbuilt.sum(), 1), 2)))

cal = pd.DataFrame(rows).merge(mo[["village", "elong", "compact", "built_ha"]], on="village", how="inner")
cal.to_csv("data/morph_calib_10m.csv", index=False)
pd.DataFrame(water_rows).to_csv("data/water_share_ring.csv", index=False)

print("\n=== 10m 重建组分 vs 现存值 ===")
ok = cal.dropna(subset=["elong_pca"])
print("n matched:", len(ok))
for cn, co in [("elong_pca", "elong"), ("elong_mbr", "elong"),
               ("isoq", "compact"), ("solidity", "compact")]:
    sp = stats.spearmanr(ok[cn], ok[co]).statistic
    lr = stats.linregress(ok[cn], ok[co])
    print(f"{cn:10s} vs {co:8s}: spearman={sp:.3f} pearson={lr.rvalue:.3f} slope={lr.slope:.3f} int={lr.intercept:.4f}")
print("\nbuilt_ha vs A_ha:", "spearman", round(stats.spearmanr(ok.built_ha, ok.A_ha).statistic, 3))
print(ok[["village", "built_ha", "A_ha", "elong", "elong_pca", "elong_mbr", "compact", "isoq", "solidity"]].head(15).to_string(index=False))
w = pd.DataFrame(water_rows)
print("\nwater share in background ring: mean %.2f%%, max %.2f%% (%s)" % (
    w.water_pct.mean(), w.water_pct.max(),
    w.loc[w.water_pct.idxmax(), "village"]))
