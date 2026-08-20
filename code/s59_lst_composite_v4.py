# -*- coding: utf-8 -*-
"""V3-R3 s59: 过境去重后的夏季 LST 合成图（P0-1 图件更新）
逻辑同 s56：同 platform+path+date 的相邻 row 资产像元级合并为一次过境；
再对全部过境取像元 nanmedian / nanmean。
输出: data/lst_summer_median_v4.tif, data/lst_summer_mean_v4.tif,
      data/wrs_footprints.json（各 path/row 有效像元 bbox, UTM）
用法: python s59_lst_composite_v4.py
"""
import json
import os

import numpy as np
import pandas as pd
import rasterio

with rasterio.open("data/lst_summer_mean.tif") as s:
    profile = s.profile
    H, W = s.height, s.width
    tr = s.transform

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
    ops[opid] = np.nanmean(np.where(np.isfinite(st), st, np.nan), axis=0)
print(f"overpasses: {len(ops)} (from {len(man)} scene assets)")

stack = np.stack(list(ops.values()))
med = np.nanmedian(np.where(np.isfinite(stack), stack, np.nan), axis=0).astype("float32")
mea = np.nanmean(np.where(np.isfinite(stack), stack, np.nan), axis=0).astype("float32")

profile.update(dtype="float32", count=1, compress="deflate")
with rasterio.open("data/lst_summer_median_v4.tif", "w", **profile) as d:
    d.write(med, 1)
with rasterio.open("data/lst_summer_mean_v4.tif", "w", **profile) as d:
    d.write(mea, 1)

# 各 path/row 有效像元 bbox（Fig3a 框用）
fp = {}
for (plat, path, row_), g in man.groupby(["platform", "path", "row"]):
    arrs = [np.load(f"data/lst_v2_scenes/{sid}.npy") for sid in g.id
            if os.path.exists(f"data/lst_v2_scenes/{sid}.npy")]
    if not arrs:
        continue
    anyv = np.any(np.stack([np.isfinite(a) for a in arrs]), axis=0)
    rr, cc = np.nonzero(anyv)
    if len(rr) == 0:
        continue
    x0 = tr.c + cc.min() * tr.a
    x1 = tr.c + (cc.max() + 1) * tr.a
    y1 = tr.f + rr.min() * tr.e
    y0 = tr.f + (rr.max() + 1) * tr.e
    fp[f"p{path}r{row_:02d}"] = dict(platform=plat, path=int(path), row=int(row_),
                                     bbox_utm=[x0, y0, x1, y1])
with open("data/wrs_footprints.json", "w") as f:
    json.dump(fp, f, indent=1)
print("footprints:", {k: [round(x) for x in v["bbox_utm"]] for k, v in fp.items()})
print("median range: %.1f-%.1f" % (np.nanmin(med), np.nanmax(med)))
print("saved lst_summer_median_v4.tif / mean_v4.tif / wrs_footprints.json")
