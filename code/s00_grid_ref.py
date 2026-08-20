# -*- coding: utf-8 -*-
"""V5 s00: 生成 100m UTM50N 分析网格模板 data/lst_grid_ref.tif

历史原因，s40/s56/s59/s64 曾以 v2 遗留文件 lst_summer_mean.tif 作为网格模板，
该文件不在仓库内，构成可复现性缺口（R4-P0-8）。本脚本消除该缺口：

优先路径：以仓库随附的 data/lst_summer_median_v4.tif（与历史模板同网格）
克隆其 profile，写出全 NaN 的 float32 模板——与原网格逐像元一致。
回退路径（全新环境、无随附合成栅格时）：由 village_sample_v2.csv 的村点
外包络 + 13 km 余量定义 100 m UTM50N 网格；此时逐像元采样可能与随附结果
存在亚像元级差异，属已记录行为（README §网格模板）。
"""
import os
import sys

import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import from_origin
from pyproj import Transformer

OUT = "data/lst_grid_ref.tif"
SRC = "data/lst_summer_median_v4.tif"

if os.path.exists(SRC):
    with rasterio.open(SRC) as s:
        prof = s.profile.copy()
    prof.update(dtype="float32", count=1, nodata=np.nan)
    grid = np.full((prof["height"], prof["width"]), np.nan, dtype="float32")
    print("grid cloned from", SRC, f"({prof['width']}x{prof['height']})")
else:
    df = pd.read_csv("data/village_sample_v2.csv")
    tf = Transformer.from_crs(4326, 32650, always_xy=True)
    xs, ys = tf.transform(df.lon.values, df.lat.values)
    M = 13000.0
    res = 100.0
    left, right = xs.min() - M, xs.max() + M
    bottom, top = ys.min() - M, ys.max() + M
    W = int(np.ceil((right - left) / res))
    H = int(np.ceil((top - bottom) / res))
    prof = dict(driver="GTiff", height=H, width=W, count=1, dtype="float32",
                crs="EPSG:32650", transform=from_origin(left, top, res, res),
                nodata=np.nan, compress="deflate")
    grid = np.full((H, W), np.nan, dtype="float32")
    print("grid derived from village bbox (fallback):", f"{W}x{H}", file=sys.stderr)

prof.setdefault("compress", "deflate")
with rasterio.open(OUT, "w", **prof) as f:
    f.write(grid, 1)
print("saved", OUT)
