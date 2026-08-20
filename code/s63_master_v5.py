# -*- coding: utf-8 -*-
"""V5 s63: 构建 v5 主分析表
变更（回应 R4 P0-9）:
  地形/景观列全部切换为 s10 全脚本化重实现（data/morphology_terrain_v4.csv），
  旧 morphology_table.csv（不可恢复栅格状态）降为 legacy 敏感性对照；
  肌理列切换为 s62（data/morphology_fabric_v5.csv，含修正周长与新肌理指标）；
  热/无线列沿用 v4（lst_abs, dlst_v1/v2/v3m, cov85_4p 等）不变。
输出: data/v3_master_v5.csv
"""
import pandas as pd

m4 = pd.read_csv("data/v3_master_v4.csv")
s10 = pd.read_csv("data/morphology_terrain_v4.csv")
fab = pd.read_csv("data/morphology_fabric_v5.csv")

TERRAIN = ["snap_m", "built_ha", "elev_m", "relief_m", "slope_deg", "southness",
           "ns_asym_m", "tsvf", "forest_ring_pct", "water_mean_m", "water_min_m",
           "built_dom_ha"]
FABRIC = ["built_fd_ha", "n_built_px", "cover_dom_pct", "elong_fd", "compact_fd",
          "perim_m", "edge_den_m_ha", "n_patches", "patch_den", "lps_pct"]

base = m4[["village", "lon", "lat"] +
          [c for c in m4.columns if c.startswith(("lst_abs", "dlst_", "cov", "rsrp"))]]
out = (base
       .merge(s10[["village"] + TERRAIN], on="village", how="left")
       .merge(fab[["village"] + FABRIC], on="village", how="left"))
# 保留 county 便于抽样框描述
cnty = s10[["village", "county"]]
out = out.merge(cnty, on="village", how="left")
cols = ["village", "county", "lon", "lat"] + TERRAIN + FABRIC + \
       [c for c in out.columns if c.startswith(("lst_abs", "dlst_", "cov", "rsrp"))]
out = out[cols]
out.to_csv("data/v3_master_v5.csv", index=False, encoding="utf-8-sig")
print(out.shape)
print(out[["village", "elev_m", "tsvf", "forest_ring_pct", "water_min_m",
           "built_dom_ha", "cover_dom_pct", "compact_fd", "lst_abs", "cov85_4p"]].head(6).to_string())
print("\nsaved data/v3_master_v5.csv")
print("ALL S63 DONE")
