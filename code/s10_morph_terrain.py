# -*- coding: utf-8 -*-
"""V3-R4 s10: 形态指标全链（从原始栅格端到端重建 morphology_table，回应 P0-6）
输入:
  data/village_sample_v2.csv   名义村点（含 coord_source/verified_status）
  data/dem_utm30.tif           30m DSM（s20a 产物, UTM50N）
  data/utm30_grid.npy          网格 [left, top, res]
  ESA WorldCover 2021 v200     10m（Planetary Computer STAC 在线窗口读取）
定义（手稿 2.3 节）:
  咬合: 距名义点最近建成像元所属 8-连通组分的质心；搜索窗 1700m→3500m；无组分则保持名义点
  Frame D: 咬合点 500m 圆域
  elev_m   = 域内 DSM 均值        relief_m = 域内 max-min
  slope_deg= 域内平均坡度(度)      southness = 域内 mean(-cos(aspect)), aspect=下坡向(北0°顺时针)
  ns_asym_m= 北半域均值 - 南半域均值
  tSVF     = 1 - (1/72)Σsin(γ_i), γ_i 为咬合点 2500m 视距内地平线仰角(30m DSM)
  forest_ring_pct = Frame-O 组分 300m 环带(扣除组分)内树冠(class 10)占比
  water_mean/min_m = 组分建成像元到最近水体(class 80)的欧氏距离(米)均值/最小值
  built_ha = 组分面积(10m 口径)   built_dom_ha = 30m 建成栅格域内面积
输出:
  data/morphology_terrain_v4.csv  全指标重建表
  打印: 与 data/morphology_table.csv 的逐指标 Spearman 秩相关核验
用法: python s10_morph_terrain.py
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
GRID = np.load("data/utm30_grid.npy")  # [left, top, res]
BUILT30 = "data/built_utm30.tif"
SAMPLE = "data/village_sample_v2.csv"
REF = "data/morphology_table.csv"
OUT = "data/morphology_terrain_v4.csv"

tf = Transformer.from_crs(4326, 32650, always_xy=True)
inv = Transformer.from_crs(32650, 4326, always_xy=True)

cat = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1")
sr = cat.search(collections=["esa-worldcover"], bbox=[117.2, 29.5, 119.0, 30.4],
                datetime="2021-01-01/2021-12-31")
tile_map = {}
for it in sr.items():
    mm_ = re.search(r"N(\d+)E(\d+)", it.id)
    if mm_:
        tile_map[(int(mm_.group(1)), int(mm_.group(2)))] = pc.sign(it).assets["map"].href


def fetch_wc(lon, lat, half_deg=0.04):
    """读取覆盖村点的 WorldCover 窗口；返回 (arr, tr)。瓦片为 3°×3°。"""
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
    """把窗口像元中心转为 UTM50N 米制坐标网格；返回 gx, gy, dx_m, dy_m。"""
    Hh, Ww = arr.shape
    cols, rws = np.meshgrid(np.arange(Ww), np.arange(Hh))
    lon_g = tr.c + (cols + 0.5) * tr.a
    lat_g = tr.f + (rws + 0.5) * tr.e
    gx, gy = tf.transform(lon_g.ravel(), lat_g.ravel())
    dx_m = abs(tr.a) * 111320.0 * math.cos(math.radians(lat0))
    dy_m = abs(tr.e) * 110540.0
    return gx.reshape(Hh, Ww), gy.reshape(Hh, Ww), dx_m, dy_m


def snap_to_component(built, gx, gy, x0, y0):
    """返回 (cx, cy, snap_m, comp_mask or None)。组分=距名义点最近建成像元所属 8-连通组分。"""
    d2 = (gx - x0) ** 2 + (gy - y0) ** 2
    if not built.any():
        return x0, y0, np.nan, None
    d2b = np.where(built, d2, np.inf)
    idx = np.unravel_index(np.argmin(d2b), d2b.shape)
    if not np.isfinite(d2b[idx]) or math.sqrt(d2b[idx]) > 3500.0:
        return x0, y0, np.nan, None
    lab, _ = ndimage.label(built, structure=np.ones((3, 3), int))
    comp = lab == lab[idx]
    ys, xs = np.nonzero(comp)
    cx, cy = float(gx[ys, xs].mean()), float(gy[ys, xs].mean())
    return cx, cy, round(math.sqrt((cx - x0) ** 2 + (cy - y0) ** 2), 1), comp


# ---------- 30m DSM 域内指标 ----------
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

# 坡度/坡向（中心差分）
gz_row, gz_col = np.gradient(dem, res)
dzdx = gz_col
dzdy = -gz_row                       # 行向下为南，取负得北向梯度
slope_deg = np.degrees(np.arctan(np.hypot(dzdx, dzdy)))
aspect = (np.degrees(np.arctan2(-dzdx, -dzdy)) + 360.0) % 360.0   # 下坡向，北0°顺时针
south_pix = -np.cos(np.radians(aspect))                            # 南坡为正


def domain_mask(cx, cy, r=500.0):
    return (X30 - cx) ** 2 + (Y30 - cy) ** 2 <= r * r


def tsvf_at(cx, cy, n_az=72, horizon=2500.0, step=30.0):
    """地形天空可视因子（手稿式(1)）：1 - mean(sin(γ_i))。"""
    z0 = ndimage.map_coordinates(
        dem, [[(dem_tr.f - cy) / res - 0.5], [(cx - dem_tr.c) / res - 0.5]],
        order=1, mode="nearest")[0]
    ds = np.arange(step, horizon + 1e-6, step)
    gam = np.full(n_az, -np.pi / 2)
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
        gam[i] = np.arctan2(z - z0, ds[ok]).max()
    return float(1.0 - np.sin(gam).mean())


# ---------- 森林环带 / 水体距离（10m WorldCover 口径） ----------
def ring_forest_and_water(comp, arr, gx, gy, dx_m, dy_m):
    """组分 300m 环带树冠占比 + 组分建成像元到最近水体的米制距离。"""
    if comp is None:
        return np.nan, np.nan, np.nan
    dil = ndimage.binary_dilation(comp, iterations=int(round(300.0 / min(dx_m, dy_m))))
    ring = dil & ~comp
    forest = 100.0 * float(((arr == 10) & ring).sum()) / max(1, int(ring.sum()))
    dist = ndimage.distance_transform_edt(arr != 80, sampling=(dy_m, dx_m))
    d_comp = dist[comp]
    return round(forest, 1), round(float(d_comp.mean()), 1), round(float(d_comp.min()), 1)


# ---------- 主循环 ----------
sample = pd.read_csv(SAMPLE)
rows = []
for _, v in sample.iterrows():
    name = v.village
    x0, y0 = tf.transform(v.lon, v.lat)
    half_deg = 0.0176   # 1700m 起（s54 口径）
    comp = None
    for _try in range(2):
        arr, tr = fetch_wc(v.lon, v.lat, half_deg=half_deg)
        if arr is None:
            break
        gx, gy, dx_m, dy_m = wc_metric_grid(arr, tr, v.lat)
        cx, cy, snap_m, comp = snap_to_component(arr == 50, gx, gy, x0, y0)
        touch = comp is not None and (
            comp[0, :].any() or comp[-1, :].any() or comp[:, 0].any() or comp[:, -1].any())
        if not touch:
            break
        half_deg = 0.0363   # 组分触边界：扩至 3500m（仍触边界即截断，与 s54 口径一致）
    if arr is None:
        print("no WorldCover tile:", name)
        continue

    D = domain_mask(cx, cy)
    elev_m = float(dem[D].mean())
    relief_m = float(dem[D].max() - dem[D].min())
    sl = float(slope_deg[D].mean())
    so = float(south_pix[D].mean())
    north = D & (Y30 > cy)
    south = D & (Y30 <= cy)
    ns = float(dem[north].mean() - dem[south].mean())
    tsvf = tsvf_at(cx, cy)
    forest, wmean, wmin = ring_forest_and_water(comp, arr, gx, gy, dx_m, dy_m)
    built_ha = round(float(comp.sum()) * dx_m * dy_m / 1e4, 2) if comp is not None else np.nan
    built_dom = round(float((b30[D] > 0).sum()) * res * res / 1e4, 2)
    lon_s, lat_s = inv.transform(cx, cy)
    rows.append(dict(village=name, county=v.county, lon=round(lon_s, 5), lat=round(lat_s, 5),
                     snap_m=snap_m, built_ha=built_ha, elev_m=round(elev_m, 1),
                     relief_m=round(relief_m, 0), slope_deg=round(sl, 1), southness=round(so, 3),
                     ns_asym_m=round(ns, 1), tsvf=round(tsvf, 3), forest_ring_pct=forest,
                     water_mean_m=wmean, water_min_m=wmin, built_dom_ha=built_dom))
    print(f"{name:22s} snap={snap_m} elev={elev_m:6.1f} tsvf={tsvf:.3f}", flush=True)

out = pd.DataFrame(rows)
out.to_csv(OUT, index=False, encoding="utf-8-sig")
print("\nsaved", OUT)

# ---------- 与参照表核验 ----------
if os.path.exists(REF):
    ref = pd.read_csv(REF)
    j = out.merge(ref, on="village", suffixes=("_new", "_ref"))
    print("\n=== 与 morphology_table.csv 核验（Spearman ρ / 平均绝对差）===")
    for c in ["snap_m", "built_ha", "elev_m", "relief_m", "slope_deg", "southness",
              "ns_asym_m", "tsvf", "forest_ring_pct", "water_mean_m", "water_min_m"]:
        a, b = j[f"{c}_new"], j[f"{c}_ref"]
        ok = a.notna() & b.notna()
        rho = stats.spearmanr(a[ok], b[ok])[0] if ok.sum() > 3 else np.nan
        mad = float((a[ok] - b[ok]).abs().mean())
        print(f"{c:16s} n={int(ok.sum()):2d}  rho={rho:.4f}  MAD={mad:.2f}")
print("\nALL S10 DONE")
