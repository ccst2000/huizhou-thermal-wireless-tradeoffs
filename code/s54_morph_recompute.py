# -*- coding: utf-8 -*-
"""V3 s54 (Round-2): elong/compact 精确定义重算（可复现管线，回应 M7）
定义（写进手稿）:
  输入: ESA WorldCover 2021 v200 (10 m, EPSG:4326), built-up = class 50
  预处理: 3x3 形态学闭运算一次（连接巷道/街道缝隙）
  组分: 8-邻域连通; 取含"距村心最近建成像元"的组分;
        窗口半宽 1700 m 起, 组分触边界则扩至 3500 m; 仍触边界记 truncated=True
  elong   = sqrt(λ1/λ2), 组分像元中心(米制)坐标协方差矩阵的 PCA 主轴比
  compact = 4πA/P² 等周商, P 为组分逐暴露边计数周长(米制); 圆形=1, 越紧凑越大
输出: data/morphology_v2.csv (含旧值对比与秩相关)
"""
import math
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds
from scipy import ndimage, stats
from pyproj import Transformer
import pystac_client
import planetary_computer as pc

cat = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1")
sr = cat.search(collections=["esa-worldcover"], bbox=[117.2, 29.5, 119.0, 30.4],
                datetime="2021-01-01/2021-12-31")
import re
tile_map = {}
for it in sr.items():
    mm_ = re.search(r"N(\d+)E(\d+)", it.id)
    if mm_:
        tile_map[(int(mm_.group(1)), int(mm_.group(2)))] = pc.sign(it).assets["map"].href
print("tiles:", list(tile_map.keys()))

m = pd.read_csv("data/v3_master.csv")
mo = pd.read_csv("data/morphology_table.csv")
tf = Transformer.from_crs(4326, 32650, always_xy=True)
inv = Transformer.from_crs(32650, 4326, always_xy=True)


def tile_href(lon, lat):
    return tile_map.get((int(lat // 3 * 3), int(lon // 3 * 3)))


def fetch(lon, lat, half):
    href = tile_href(lon, lat)
    if href is None:
        return None, None
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                      CPL_VSIL_CURL_USE_HEAD="FALSE", VSI_CACHE="TRUE"):
        with rasterio.open(href) as s:
            win = from_bounds(lon - 0.03, lat - 0.03, lon + 0.03, lat + 0.03, s.transform)
            # 先粗读窗口边界，再按 half 精裁（度）
            win = from_bounds(*inv_bounds(lon, lat, half, s.crs), s.transform)
            win = win.round_offsets().round_lengths()
            return s.read(1, window=win), s.window_transform(win)


def inv_bounds(lon, lat, half, crs):
    return (lon - 0.035, lat - 0.035, lon + 0.035, lat + 0.035)


def village_metrics(v, half):
    arr, tr = fetch(v.lon, v.lat, half)
    if arr is None:
        return None
    cx, cy = tf.transform(v.lon, v.lat)
    Hh, Ww = arr.shape
    cols = np.arange(Ww); rws = np.arange(Hh)
    XX, YY = np.meshgrid(cols, rws)
    lon_g = tr.c + (XX + 0.5) * tr.a
    lat_g = tr.f + (YY + 0.5) * tr.e
    gx, gy = tf.transform(lon_g.ravel(), lat_g.ravel())
    gx = gx.reshape(Hh, Ww); gy = gy.reshape(Hh, Ww)
    d2 = (gx - cx) ** 2 + (gy - cy) ** 2
    lat0 = math.radians(v.lat)
    dx_m = abs(tr.a) * 111320.0 * math.cos(lat0)
    dy_m = abs(tr.e) * 110540.0
    b = ndimage.binary_closing(arr == 50, structure=np.ones((3, 3)))
    lab, _ = ndimage.label(b, structure=np.ones((3, 3)))
    d2b = np.where(lab > 0, d2, np.inf)
    if not np.isfinite(d2b).any():
        return dict(village=v.village, n_comp=0)
    j = np.unravel_index(np.argmin(d2b), d2b.shape)
    mask = lab == lab[j]
    touch = mask[0, :].any() or mask[-1, :].any() or mask[:, 0].any() or mask[:, -1].any()
    ys, xs = np.nonzero(mask)
    pts = np.column_stack([xs * dx_m, ys * dy_m]).astype(float)
    A = mask.sum() * dx_m * dy_m
    bb = mask.astype(np.uint8)
    P = float(((bb[:, :-1] != bb[:, 1:]).sum() + (bb[:-1, :] != bb[1:, :]).sum()) * (dx_m + dy_m) / 2
              + (bb[0, :].sum() + bb[-1, :].sum()) * dx_m + (bb[:, 0].sum() + bb[:, -1].sum()) * dy_m)
    if len(pts) >= 3:
        covm = np.cov(pts.T)
        ev = np.linalg.eigvalsh(covm)[::-1]
        elong = math.sqrt(ev[0] / ev[1]) if ev[1] > 0 else np.nan
    else:
        elong = np.nan
    compact = 4 * math.pi * A / P ** 2 if P > 0 else np.nan
    return dict(village=v.village, elong2=round(elong, 3) if np.isfinite(elong) else np.nan,
                compact2=round(compact, 4) if np.isfinite(compact) else np.nan,
                comp_ha=round(A / 1e4, 2), truncated=touch, half_m=half)


rows = []
for _, v in m.iterrows():
    r = village_metrics(v, 1700.0)
    if r and r.get("truncated"):
        r2 = village_metrics(v, 3500.0)
        if r2:
            r = r2
    if r:
        rows.append(r)
        print(f"{v.village:24s} elong2={r.get('elong2')} compact2={r.get('compact2')} "
              f"A={r.get('comp_ha')}ha truncated={r.get('truncated')}", flush=True)

nv = pd.DataFrame(rows)
cal = nv.merge(mo[["village", "elong", "compact", "built_ha"]], on="village", how="left")
cal.to_csv("data/morphology_v2.csv", index=False)
ok = cal.dropna(subset=["elong2"])
print("\nn =", len(ok))
print("elong2 vs old elong: spearman =", round(stats.spearmanr(ok.elong2, ok.elong).statistic, 3))
print("compact2 vs old compact: spearman =", round(stats.spearmanr(ok.compact2, ok.compact).statistic, 3))
print("comp_ha vs old built_ha: spearman =", round(stats.spearmanr(ok.comp_ha, ok.built_ha).statistic, 3))
