# -*- coding: utf-8 -*-
"""V6 s66: 附录表 A8 / A11 生成器（R5-P0-7：此前无生成器，属孤儿表）
  TableA8_scene_composition.csv  <- data/village_scene_composition.csv
      每村 Landsat 场景数（L8/L9 分列）、年份范围、WRS-2 帧
  TableA11_sampling_frame.csv    <- data/village_sample_v2.csv
      抽样框：村名、县、坐标、坐标来源、核验状态、备注
坐标列以 canonical（village_geometry_v6.csv）为准并标注来源差异。
"""
import pandas as pd

sc = pd.read_csv("data/village_scene_composition.csv")
a8 = sc.rename(columns=dict(village="Village", n_scenes="Scenes (n)",
                            n_l8="Landsat 8 (n)", n_l9="Landsat 9 (n)",
                            year_min="First year", year_max="Last year",
                            frames="WRS-2 path/row"))
a8.to_csv("tables/TableA8_scene_composition.csv", index=False, encoding="utf-8-sig")

geo = pd.read_csv("data/village_geometry_v6.csv")
smp = pd.read_csv("data/village_sample_v2.csv")
a11 = geo[["village", "county", "lon", "lat"]].merge(
    smp[["village", "lon", "lat", "coord_source", "verified_status", "note"]],
    on="village", suffixes=("_canonical", "_register"))
a11["coord_delta_m"] = (
    ((a11.lon_canonical - a11.lon_register) * 111320.0) ** 2 +
    ((a11.lat_canonical - a11.lat_register) * 110540.0) ** 2) ** 0.5
a11 = a11[["village", "county", "lon_canonical", "lat_canonical",
           "coord_source", "verified_status", "coord_delta_m", "note"]]
a11.columns = ["Village", "County", "Lon (canonical)", "Lat (canonical)",
               "Register coord source", "Register status",
               "Canonical vs register (m)", "Note"]
a11 = a11.round({"Canonical vs register (m)": 1})
a11.to_csv("tables/TableA11_sampling_frame.csv", index=False, encoding="utf-8-sig")

print("A8 rows:", len(a8), "| A11 rows:", len(a11))
print("canonical vs register delta (m): max", a11["Canonical vs register (m)"].max())
print("ALL S66 DONE")
