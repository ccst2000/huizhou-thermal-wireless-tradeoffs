# -*- coding: utf-8 -*-
"""V5 s62: Frame-D 建成肌理指标（建筑学尺度增补，回应 R4-P0 范围门槛 / 折中方案）
定义（全部来自 ESA WorldCover 2021 v200 10m 公开栅格，村心 500m 圆域 = site domain）:
  built_fd_ha   域内建成总面积
  cover_dom_pct 建筑覆盖率 = 建成面积 / 圆域面积(78.5398 ha) ×100
  elong_fd      建成像元中心 PCA 主轴比 sqrt(λ1/λ2)
  compact_fd    聚合等周商 4πA/P²（P 由 geo_utils.aggregate_perimeter 各向异性加权）
  edge_den_m_ha 边缘密度 = P / A (m/ha)
  n_patches     域内建成斑块数（4-连通）
  patch_den     斑块密度 = n_patches / 建成面积 (个/ha)
  lps_pct       最大斑块占比 = 最大斑块面积 / 建成总面积 ×100
输出: data/morphology_fabric_v5.csv
"""
import math
import re
import sys

import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds
from pyproj import Transformer
import pystac_client
import planetary_computer as pc
from scipy import ndimage

sys.path.insert(0, "src")
from geo_utils import aggregate_perimeter

DOMAIN_HA = math.pi * 500.0 ** 2 / 1e4  # 78.5398

cat = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1")
sr = cat.search(collections=["esa-worldcover"], bbox=[117.2, 29.5, 119.0, 30.4],
                datetime="2021-01-01/2021-12-31")
tile_map = {}
for it in sr.items():
    mm_ = re.search(r"N(\d+)E(\d+)", it.id)
    if mm_:
        tile_map[(int(mm_.group(1)), int(mm_.group(2)))] = pc.sign(it).assets["map"].href

m = pd.read_csv("data/v3_master_v4.csv")[["village", "lon", "lat"]]
tf = Transformer.from_crs(4326, 32650, always_xy=True)


def fetch(lon, lat, half_deg=0.012):
    href = tile_map.get((int(lat // 3 * 3), int(lon // 3 * 3)))
    if href is None:
        return None, None
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                      CPL_VSIL_CURL_USE_HEAD="FALSE", VSI_CACHE="TRUE"):
        with rasterio.open(href) as s:
            win = from_bounds(lon - half_deg, lat - half_deg, lon + half_deg, lat + half_deg,
                              s.transform).round_offsets().round_lengths()
            return s.read(1, window=win), s.window_transform(win)


rows = []
for _, v in m.iterrows():
    cx, cy = tf.transform(v.lon, v.lat)
    arr, tr = fetch(v.lon, v.lat)
    if arr is None:
        print("no tile:", v.village)
        continue
    Hh, Ww = arr.shape
    cols = np.arange(Ww)
    rws = np.arange(Hh)
    XX, YY = np.meshgrid(cols, rws)
    lon_g = tr.c + (XX + 0.5) * tr.a
    lat_g = tr.f + (YY + 0.5) * tr.e
    gx, gy = tf.transform(lon_g.ravel(), lat_g.ravel())
    gx = gx.reshape(Hh, Ww)
    gy = gy.reshape(Hh, Ww)
    d2 = (gx - cx) ** 2 + (gy - cy) ** 2
    lat0 = math.radians(v.lat)
    dx_m = abs(tr.a) * 111320.0 * math.cos(lat0)
    dy_m = abs(tr.e) * 110540.0
    inD = d2 <= 500.0 ** 2
    b = (arr == 50) & inD
    nb = int(b.sum())
    A = nb * dx_m * dy_m
    if nb < 10:
        rows.append(dict(village=v.village, built_fd_ha=round(A / 1e4, 2), n_built_px=nb,
                         cover_dom_pct=round(A / 1e4 / DOMAIN_HA * 100, 2),
                         elong_fd=np.nan, compact_fd=np.nan, perim_m=np.nan,
                         edge_den_m_ha=np.nan, n_patches=np.nan, patch_den=np.nan,
                         lps_pct=np.nan))
        print(f"{v.village:24s} built px={nb:4d} (<10, shape n/a)", flush=True)
        continue
    ys, xs = np.nonzero(b)
    pts = np.column_stack([xs * dx_m, ys * dy_m]).astype(float)
    bb = b.astype(np.uint8)
    P = aggregate_perimeter(bb, dx_m, dy_m)
    lab, ncomp = ndimage.label(bb, structure=np.ones((3, 3), dtype=int))
    # 说明：8-连通标记斑块（对角相连视为同斑），与建成区连续性的直觉一致
    sizes = ndimage.sum(np.ones_like(lab), lab, index=np.arange(1, ncomp + 1))
    lps = float(sizes.max() / nb * 100) if nb > 0 else np.nan
    covm = np.cov(pts.T)
    ev = np.linalg.eigvalsh(covm)[::-1]
    elong = math.sqrt(ev[0] / ev[1]) if ev[1] > 0 else np.nan
    compact = 4 * math.pi * A / P ** 2 if P > 0 else np.nan
    A_ha = A / 1e4
    rows.append(dict(village=v.village, built_fd_ha=round(A_ha, 2), n_built_px=nb,
                     cover_dom_pct=round(A_ha / DOMAIN_HA * 100, 2),
                     elong_fd=round(elong, 3), compact_fd=round(compact, 4),
                     perim_m=round(P, 1), edge_den_m_ha=round(P / A_ha, 1),
                     n_patches=int(ncomp), patch_den=round(ncomp / A_ha, 2),
                     lps_pct=round(lps, 1)))
    print(f"{v.village:24s} px={nb:5d} A={A_ha:6.2f}ha cover={A_ha/DOMAIN_HA*100:5.1f}% "
          f"elong={elong:5.2f} compact={compact:.4f} edge={P/A_ha:6.1f}m/ha "
          f"patches={ncomp:3d} lps={lps:4.1f}%", flush=True)

pd.DataFrame(rows).to_csv("data/morphology_fabric_v5.csv", index=False)
print("\nsaved data/morphology_fabric_v5.csv")
print("ALL S62 DONE")
