# -*- coding: utf-8 -*-
"""V3-R6 s10b: 地形/场地指标 v6（单一 canonical 坐标，不再咬合）
相对 s10 的实质修改（回应 R5 审稿 P0-1 / P0-2 / P0-12）:
  1) 坐标: 读取 data/village_geometry_v6.csv（= v3_master.csv 的唯一坐标集），
     不再做组分咬合(snap)；全部域指标锚定在 canonical 点 500m 圆域(Frame D)。
  2) 森林环带: 改为以村点为圆心的 500–800m 欧几里得环带内树冠(class 10)占比，
     替代原"组分 300m 环带"（原定义用曼哈顿结构元 dilation 且锚定组分，
     在部分村落到界/无组分时不可比）。
  3) 水体距离: 500m 域内建成(class 50)像元到最近水体(class 80)的欧氏距离；
     域内无建成像元时退化为域心到最近水体距离（water_*_m 同口径标注）。
  4) tSVF: 地平线仰角 γ_i 截断至 >=0（负地平线不降低 SVF）；无有效射线的方位剔除。
输出: data/morphology_terrain_v6.csv
打印: 与 data/morphology_terrain_v4.csv 的秩相关核验（数值预期漂移，属本次重建目的）
用法: python s10b_morph_terrain_v6.py
"""
import math
import os
import re
import numpy as np
import pandas as pd
import rasterio
import pystac_client
import planetary_computer as pc
from rasterio.windows import from_bounds
from pyproj import Transformer
from scipy import ndimage, stats

DEM = "data/dem_utm30.tif"
BUILT30 = "data/built_utm30.tif"
GEO = "data/village_geometry_v6.csv"
REF = "data/morphology_terrain_v4.csv"
OUT = "data/morphology_terrain_v6.csv"

tf = Transformer.from_crs(4326, 32650, always_xy=True)

cat = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1")
sr = cat.search(collections=["esa-worldcover"], bbox=[117.2, 29.5, 119.0, 30.4],
                datetime="2021-01-01/2021-12-31")
tile_map = {}
for it in sr.items():
    mm_ = re.search(r"N(\d+)E(\d+)", it.id)
    if mm_:
        tile_map[(int(mm_.group(1)), int(mm_.group(2)))] = pc.sign(it).assets["map"].href


def fetch_wc(lon, lat, half_deg=0.02):
    """读取覆盖村点的 WorldCover 窗口；0.02°≈2km 半径，覆盖 800m 环带。"""
    href = tile_map.get((int(lat // 3 * 3), int(lon // 3 * 3)))
    if href is None:
        return None, None
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                      CPL_VSIL_CURL_USE_HEAD="FALSE", VSI_CACHE="TRUE"):
        with rasterio.open(href) as s:
            win = from_bounds(lon - half_deg, lat - half_deg, lon + half_deg, lat + half_deg,
                              s.transform).round_offsets().round_lengths()
            return s.read(1, window=win), s.window_transform(win)


def wc_metric_grid(arr, tr, lat0):
    Hh, Ww = arr.shape
    cols, rws = np.meshgrid(np.arange(Ww), np.arange(Hh))
    lon_g = tr.c + (cols + 0.5) * tr.a
    lat_g = tr.f + (rws + 0.5) * tr.e
    gx, gy = tf.transform(lon_g.ravel(), lat_g.ravel())
    dx_m = abs(tr.a) * 111320.0 * math.cos(math.radians(lat0))
    dy_m = abs(tr.e) * 110540.0
    return gx.reshape(Hh, Ww), gy.reshape(Hh, Ww), dx_m, dy_m


# ---------- 30m DSM 全域派生层 ----------
with rasterio.open(DEM) as s:
    dem = s.read(1).astype("float64")
    dem_tr = s.transform
res = abs(dem_tr.a)
HH, WW = dem.shape
r30, c30 = np.meshgrid(np.arange(HH), np.arange(WW), indexing="ij")
X30 = dem_tr.c + (c30 + 0.5) * res
Y30 = dem_tr.f - (r30 + 0.5) * res
with rasterio.open(BUILT30) as s:
    b30 = s.read(1)

gz_row, gz_col = np.gradient(dem, res)
dzdx = gz_col
dzdy = -gz_row
slope_deg = np.degrees(np.arctan(np.hypot(dzdx, dzdy)))
aspect = (np.degrees(np.arctan2(-dzdx, -dzdy)) + 360.0) % 360.0
south_pix = -np.cos(np.radians(aspect))


def domain_mask(cx, cy, r=500.0):
    return (X30 - cx) ** 2 + (Y30 - cy) ** 2 <= r * r


def tsvf_at(cx, cy, n_az=72, horizon=2500.0, step=30.0):
    """地形天空可视因子：1 - mean(sin(γ_i))；γ_i 截断至 [0, π/2]，无效方位剔除。"""
    z0 = ndimage.map_coordinates(
        dem, [[(dem_tr.f - cy) / res - 0.5], [(cx - dem_tr.c) / res - 0.5]],
        order=1, mode="nearest")[0]
    ds = np.arange(step, horizon + 1e-6, step)
    gam = np.full(n_az, np.nan)
    for i in range(n_az):
        a = math.radians(i * 360.0 / n_az)
        xs = cx + ds * math.sin(a)
        ys = cy + ds * math.cos(a)
        rr = (dem_tr.f - ys) / res - 0.5
        cc = (xs - dem_tr.c) / res - 0.5
        ok = (rr >= 0) & (rr <= HH - 1) & (cc >= 0) & (cc <= WW - 1)
        if not ok.any():
            continue
        z = ndimage.map_coordinates(dem, [rr[ok], cc[ok]], order=1, mode="nearest")
        gam[i] = max(0.0, float(np.arctan2(z - z0, ds[ok]).max()))
    return float(1.0 - np.nanmean(np.sin(gam)))


def ring_forest_and_water(arr, gx, gy, dx_m, dy_m, cx, cy):
    """500–800m 欧氏环带树冠占比 + 域内建成像元/域心到最近水体距离。"""
    dc = np.sqrt((gx - cx) ** 2 + (gy - cy) ** 2)
    ring = (dc > 500.0) & (dc <= 800.0)
    forest = 100.0 * float(((arr == 10) & ring).sum()) / max(1, int(ring.sum()))
    dist_w = ndimage.distance_transform_edt(arr != 80, sampling=(dy_m, dx_m))
    built_dom = (arr == 50) & (dc <= 500.0)
    if built_dom.any():
        d = dist_w[built_dom]
        wmean, wmin = float(d.mean()), float(d.min())
        wsrc = "built-in-domain"
    else:
        rr = np.array([(dist_w.shape[0] - 1) / 2.0])  # 近似域心: 用最近像元
        i0 = int(np.argmin((gx - cx) ** 2 + (gy - cy) ** 2) // dist_w.shape[1])
        j0 = int(np.argmin((gx - cx) ** 2 + (gy - cy) ** 2) % dist_w.shape[1])
        wmean = wmin = float(dist_w[i0, j0])
        wsrc = "domain-centre"
    built_wc_ha = round(float(built_dom.sum()) * dx_m * dy_m / 1e4, 2)
    return round(forest, 1), round(wmean, 1), round(wmin, 1), wsrc, built_wc_ha


# ---------- 主循环 ----------
geo = pd.read_csv(GEO)
rows = []
for _, v in geo.iterrows():
    x0, y0 = tf.transform(v.lon, v.lat)
    arr, tr = fetch_wc(v.lon, v.lat, half_deg=0.02)
    if arr is None:
        print("no WorldCover tile:", v.village)
        continue
    gx, gy, dx_m, dy_m = wc_metric_grid(arr, tr, v.lat)

    D = domain_mask(x0, y0)
    elev_m = float(dem[D].mean())
    relief_m = float(dem[D].max() - dem[D].min())
    sl = float(slope_deg[D].mean())
    so = float(south_pix[D].mean())
    north = D & (Y30 > y0)
    south = D & (Y30 <= y0)
    ns = float(dem[north].mean() - dem[south].mean())
    tsvf = tsvf_at(x0, y0)
    forest, wmean, wmin, wsrc, built_wc_ha = ring_forest_and_water(
        arr, gx, gy, dx_m, dy_m, x0, y0)
    built_dom = round(float((b30[D] > 0).sum()) * res * res / 1e4, 2)
    rows.append(dict(vid=v.vid, village=v.village, county=v.county,
                     lon=v.lon, lat=v.lat,
                     elev_m=round(elev_m, 1), relief_m=round(relief_m, 0),
                     slope_deg=round(sl, 1), southness=round(so, 3),
                     ns_asym_m=round(ns, 1), tsvf=round(tsvf, 3),
                     forest_ring_pct=forest, water_mean_m=wmean, water_min_m=wmin,
                     water_src=wsrc, built_wc_ha=built_wc_ha, built_dom_ha=built_dom))
    print(f"{v.vid:14s} elev={elev_m:6.1f} tsvf={tsvf:.3f} forest={forest:5.1f} "
          f"wmean={wmean:6.1f} ({wsrc})", flush=True)

out = pd.DataFrame(rows)
out.to_csv(OUT, index=False, encoding="utf-8-sig")
print("\nsaved", OUT)

if os.path.exists(REF):
    ref = pd.read_csv(REF)
    j = out.merge(ref, on="village", suffixes=("_v6", "_v4"))
    print("\n=== 与 morphology_terrain_v4.csv 核验（Spearman ρ / 平均绝对差；漂移属预期）===")
    for c in ["elev_m", "relief_m", "slope_deg", "southness", "ns_asym_m", "tsvf",
              "forest_ring_pct", "water_mean_m", "water_min_m"]:
        a, b = j[f"{c}_v6"], j[f"{c}_v4"]
        ok = a.notna() & b.notna()
        rho = stats.spearmanr(a[ok], b[ok])[0] if ok.sum() > 3 else np.nan
        mad = float((a[ok] - b[ok]).abs().mean())
        print(f"{c:16s} n={int(ok.sum()):2d}  rho={rho:.4f}  MAD={mad:.2f}")
print("\nALL S10B DONE")
