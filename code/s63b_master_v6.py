# -*- coding: utf-8 -*-
"""V6 s63b: 构建 v6 主分析表
变更（回应 R5 P0-1/P0-2）:
  地形/景观列 = s10b（data/morphology_terrain_v6.csv，canonical 坐标、欧氏环带、tSVF截断）；
  肌理列 = s62b（data/morphology_fabric_v6.csv，圆域分母、4-连通斑块）；
  热/无线列沿用 v4 不变（s56/s20b 本就用 canonical 坐标，无需重跑）。
  snap_m 与组分口径 built_ha 退役；新增 water_src / built_wc_ha。
输出: data/v3_master_v6.csv
"""
import pandas as pd

m4 = pd.read_csv("data/v3_master_v4.csv")
s10b = pd.read_csv("data/morphology_terrain_v6.csv")
fab = pd.read_csv("data/morphology_fabric_v6.csv")

TERRAIN = ["elev_m", "relief_m", "slope_deg", "southness", "ns_asym_m", "tsvf",
           "forest_ring_pct", "water_mean_m", "water_min_m", "water_src",
           "built_wc_ha", "built_dom_ha"]
FABRIC = ["built_fd_ha", "n_built_px", "cover_dom_pct", "elong_fd", "compact_fd",
          "perim_m", "edge_den_m_ha", "n_patches", "patch_den", "lps_pct"]

base = m4[["village", "lon", "lat"] +
          [c for c in m4.columns if c.startswith(("lst_abs", "dlst_", "cov", "rsrp"))]]
out = (base
       .merge(s10b[["village", "county"] + TERRAIN], on="village", how="left")
       .merge(fab[["village"] + FABRIC], on="village", how="left"))
front = ["village", "county", "lon", "lat"] + TERRAIN + FABRIC
cols = front + [c for c in out.columns
                if c.startswith(("lst_abs", "dlst_", "cov", "rsrp")) and c not in front]
out = out[cols]
out.to_csv("data/v3_master_v6.csv", index=False, encoding="utf-8-sig")
print(out.shape)
print(out[["village", "elev_m", "tsvf", "forest_ring_pct", "water_min_m",
           "built_dom_ha", "cover_dom_pct", "compact_fd", "lst_abs", "cov85_4p"]].head(6).to_string())
# 一致性检查: 坐标必须与 v4（=canonical）逐村一致
import numpy as np
j = out.merge(m4[["village", "lon", "lat"]], on="village", suffixes=("", "_m4"))
assert np.allclose(j.lon, j.lon_m4) and np.allclose(j.lat, j.lat_m4), "coordinate drift!"
print("coordinate check OK (v6 == v4 == canonical)")
print("\nsaved data/v3_master_v6.csv")
print("ALL S63B DONE")
