# -*- coding: utf-8 -*-
"""V3 s20a: 构建研究区统一栅格底座
- UTM50N / 30m DEM 镶嵌（GLO-30 四瓦片重投影）
- 建成区掩膜（ESA WorldCover 2021 class 50 → 30m nearest）
范围：29村 bbox + 13km（供覆盖模型 10km 分配半径 + 余量）
输出：data/dem_utm30.tif, data/built_utm30.tif, data/utm30_grid.npy [left, top, res]
"""
import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_origin
from rasterio.windows import from_bounds
from pyproj import Transformer

from v3_inputs import dem_tile, wc_tile

df = pd.read_csv("data/v3_master.csv")
tf = Transformer.from_crs(4326, 32650, always_xy=True)
vxy = np.array([tf.transform(lo, la) for lo, la in zip(df.lon, df.lat)])
minx, miny = vxy.min(0)
maxx, maxy = vxy.max(0)
M = 13000.0
left, right, bottom, top = minx - M, maxx + M, miny - M, maxy + M
res = 30.0
W = int(np.ceil((right - left) / res))
H = int(np.ceil((top - bottom) / res))
tr = from_origin(left, top, res, res)
print(f"UTM grid: {W} x {H} = {W*H/1e6:.1f}M px, left={left:.0f} top={top:.0f}")

# ---- DEM 镶嵌 ----
dem = np.full((H, W), np.nan, dtype="float32")
for n in (29, 30):
    for e in (117, 118):
        p = dem_tile(n, e)
        with rasterio.open(p) as s:
            src = s.read(1).astype("float32")
            if s.nodata is not None:
                src[src == s.nodata] = np.nan
            tmp = np.full((H, W), np.nan, dtype="float32")
            reproject(src, tmp, src_transform=s.transform, src_crs=s.crs,
                      dst_transform=tr, dst_crs="EPSG:32650",
                      resampling=Resampling.bilinear, dst_nodata=np.nan)
        np.copyto(dem, tmp, where=np.isnan(dem))
        print(p, "valid share:", round(float(np.isfinite(dem).mean()), 3))

# ---- WorldCover 建成区掩膜（窗口读取避免整幅3度瓦片入内存）----
inv = Transformer.from_crs(32650, 4326, always_xy=True)
lon0, lat0 = inv.transform(left, bottom)
lon1, lat1 = inv.transform(right, top)
pad = 0.03
built = np.zeros((H, W), dtype="uint8")
for n in (27, 30):
    p = wc_tile(n, 117)
    with rasterio.open(p) as s:
        b = s.bounds  # 必须先裁剪到瓦片范围内，越界窗口会导致 GDAL 行错位
        l0, r1 = max(lon0 - pad, b.left), min(lon1 + pad, b.right)
        b0, t1 = max(lat0 - pad, b.bottom), min(lat1 + pad, b.top)
        win = from_bounds(l0, b0, r1, t1, s.transform)
        win = win.round_offsets().round_lengths()
        arr = s.read(1, window=win)
        wtr = s.window_transform(win)
        tmp = np.zeros((H, W), dtype="uint8")
        reproject((arr == 50).astype("uint8"), tmp, src_transform=wtr, src_crs=s.crs,
                  dst_transform=tr, dst_crs="EPSG:32650", resampling=Resampling.nearest)
        built |= tmp
        print(p, "window", arr.shape, "built px so far:", int(built.sum()))

# ---- 落盘 ----
prof = dict(driver="GTiff", height=H, width=W, count=1, dtype="float32",
            crs="EPSG:32650", transform=tr, nodata=np.nan, compress="deflate")
with rasterio.open("data/dem_utm30.tif", "w", **prof) as f:
    f.write(dem, 1)
prof.update(dtype="uint8", nodata=None)
with rasterio.open("data/built_utm30.tif", "w", **prof) as f:
    f.write(built, 1)
np.save("data/utm30_grid.npy", np.array([left, top, res]))
print("saved: data/dem_utm30.tif, data/built_utm30.tif, data/utm30_grid.npy")
