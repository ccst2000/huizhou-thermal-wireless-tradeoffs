# -*- coding: utf-8 -*-
"""V3-R3 s58: M4 地形产品交叉核验 —— COP-DEM (DSM) vs NASADEM (DSM)
目的：发现粗差/验证村级地形指标在两个独立产品间的一致性；
     两者均为雷达 DSM，均含冠层/建筑表面信号——此局限写入手稿。
指标：村心高程（最邻近像元）、500m 域 relief（max-min），COP 由本地 dem_utm30.tif 重算
输出: tables/TableA10_dsm_crosscheck.csv；打印 Spearman/RMSE
用法: python s58_dsm_crosscheck.py
"""
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds
from pyproj import Transformer
import pystac_client
import planetary_computer as pc
from scipy import stats

m = pd.read_csv("data/v3_master_v4.csv")
tf = Transformer.from_crs(4326, 32650, always_xy=True)
inv = Transformer.from_crs(32650, 4326, always_xy=True)

# ---------- COP-DEM（本地 30m UTM） ----------
with rasterio.open("data/dem_utm30.tif") as s:
    dem = s.read(1)
    tr_cop = s.transform


def cop_stats(lon, lat):
    cx, cy = tf.transform(lon, lat)
    res = tr_cop.a
    Rp = int(np.ceil(500 / res)) + 1
    r0 = int((tr_cop.f - cy) / res - 0.5)
    c0 = int((cx - tr_cop.c) / res - 0.5)
    win = dem[r0 - Rp:r0 + Rp + 1, c0 - Rp:c0 + Rp + 1]
    yy, xx = np.mgrid[-Rp:Rp + 1, -Rp:Rp + 1]
    inD = (xx ** 2 + yy ** 2) <= (500 / res) ** 2
    z = np.where(inD & np.isfinite(win), win, np.nan)
    return float(dem[r0, c0]), float(np.nanmax(z) - np.nanmin(z))


# ---------- NASADEM（Planetary Computer STAC, 1 arcsec） ----------
cat = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1")
bbox = [float(m.lon.min() - 0.05), float(m.lat.min() - 0.05),
        float(m.lon.max() + 0.05), float(m.lat.max() + 0.05)]
sr = cat.search(collections=["nasadem"], bbox=bbox)
tiles = []
for it in sr.items():
    href = pc.sign(it).assets["elevation"].href
    tiles.append(href)
tiles = sorted(set(tiles))
print(f"NASADEM tiles: {len(tiles)}")


def nasa_stats(lon, lat, half=0.012):
    z_c, rel = np.nan, np.nan
    for href in tiles:
        try:
            with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                              CPL_VSIL_CURL_USE_HEAD="FALSE", VSI_CACHE="TRUE"):
                with rasterio.open(href) as s:
                    b = s.bounds
                    if not (b.left <= lon <= b.right and b.bottom <= lat <= b.top):
                        continue
                    win = from_bounds(lon - half, lat - half, lon + half, lat + half,
                                      s.transform).round_offsets().round_lengths()
                    arr = s.read(1, window=win).astype("float32")
                    wtr = s.window_transform(win)
                    arr[arr < -500] = np.nan
                    H, W = arr.shape
                    cols, rws = np.meshgrid(np.arange(W), np.arange(H))
                    lon_g = wtr.c + (cols + 0.5) * wtr.a
                    lat_g = wtr.f + (rws + 0.5) * wtr.e
                    gx, gy = tf.transform(lon_g.ravel(), lat_g.ravel())
                    gx = gx.reshape(H, W); gy = gy.reshape(H, W)
                    cx, cy = tf.transform(lon, lat)
                    inD = (gx - cx) ** 2 + (gy - cy) ** 2 <= 500.0 ** 2
                    zz = np.where(inD, arr, np.nan)
                    rel = float(np.nanmax(zz) - np.nanmin(zz))
                    i = np.nanargmin((lon_g - lon) ** 2 + (lat_g - lat) ** 2)
                    z_c = float(arr.ravel()[i])
                    break
        except Exception as e:
            print("  tile err:", e)
    return z_c, rel


rows = []
for _, v in m.iterrows():
    zc_cop, rel_cop = cop_stats(v.lon, v.lat)
    zc_nasa, rel_nasa = nasa_stats(v.lon, v.lat)
    rows.append(dict(village=v.village, elev_cop=round(zc_cop, 1), elev_nasadem=round(zc_nasa, 1),
                     d_elev=round(zc_cop - zc_nasa, 1),
                     relief_cop=round(rel_cop, 1), relief_nasadem=round(rel_nasa, 1),
                     d_relief=round(rel_cop - rel_nasa, 1)))
    print(f"{v.village:28s} elev {zc_cop:7.1f}/{zc_nasa:7.1f}  relief {rel_cop:6.1f}/{rel_nasa:6.1f}", flush=True)

out = pd.DataFrame(rows)
out.to_csv("tables/TableA10_dsm_crosscheck.csv", index=False, encoding="utf-8-sig")
r1 = stats.spearmanr(out.elev_cop, out.elev_nasadem)
r2 = stats.spearmanr(out.relief_cop, out.relief_nasadem)
rmse = float(np.sqrt(np.mean(out.d_elev ** 2)))
print(f"\nelev: Spearman {r1[0]:.3f}, RMSE {rmse:.1f} m, mean diff {out.d_elev.mean():.1f} m")
print(f"relief: Spearman {r2[0]:.3f}, mean diff {out.d_relief.mean():.1f} m, "
      f"max |diff| {out.d_relief.abs().max():.1f} m ({out.loc[out.d_relief.abs().idxmax(), 'village']})")
