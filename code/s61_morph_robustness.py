# -*- coding: utf-8 -*-
"""V3-R4 s61: 形态链稳健性检验（P0-6 配套）
用意：morphology_table.csv 的原始栅格处理状态已不可恢复（v2 期 DEM 镶嵌）。
     本脚本用 s10 的脚本化重实现指标替换发表表中的对应列，重跑 headline 相关，
     证明论文结论对形态链重实现不敏感（秩层面保持）。
输出: tables/TableA13_morph_robustness.csv + 控制台对比
用法: python s61_morph_robustness.py
"""
import numpy as np
import pandas as pd
from scipy import stats

PUB = "data/v3_master_v4.csv"          # 发表分析表
NEW = "data/morphology_terrain_v4.csv"  # s10 重实现
OUT = "tables/TableA13_morph_robustness.csv"

m = pd.read_csv(PUB)
# built_dom_ha 在发表链中由 built_domain_area.csv 并入（见 s41d），此处对齐
bd = pd.read_csv("data/built_domain_area.csv")
if "built_dom_ha" not in m.columns:
    m = m.merge(bd[["village", "built_dom_ha"]], on="village", how="left")
n = pd.read_csv(NEW)[["village", "elev_m", "relief_m", "slope_deg", "southness",
                      "ns_asym_m", "tsvf", "forest_ring_pct", "water_mean_m",
                      "water_min_m", "built_dom_ha"]].rename(columns={"built_dom_ha": "built_dom_ha_new"})
m2 = m.drop(columns=[c for c in ["elev_m", "relief_m", "slope_deg", "southness", "ns_asym_m",
                                 "tsvf", "forest_ring_pct", "water_mean_m", "water_min_m"]
                     if c in m.columns])
m2 = m2.merge(n, on="village", how="left")
# built_dom_ha 替换为 s10 重实现值（同一 30m 栅格口径）
m2["built_dom_ha"] = m2["built_dom_ha_new"]
m2 = m2.drop(columns=["built_dom_ha_new"])

PAIRS = [("tsvf", "lst_abs"), ("tsvf", "cov85_4p"), ("tsvf", "rsrp_p10_4p"),
         ("forest_ring_pct", "cov85_4p"), ("forest_ring_pct", "rsrp_p10_4p"),
         ("forest_ring_pct", "lst_abs"), ("slope_deg", "cov85_4p"), ("slope_deg", "rsrp_p10_4p"),
         ("relief_m", "lst_abs"), ("relief_m", "cov85_4p"), ("relief_m", "dlst_v3m"),
         ("elev_m", "lst_abs"), ("built_dom_ha", "lst_abs"), ("built_dom_ha", "dlst_v3m"),
         ("water_min_m", "lst_abs"), ("water_min_m", "dlst_v3m"),
         ("southness", "lst_abs"), ("ns_asym_m", "lst_abs")]

rows = []
print(f"{'pair':34s} {'published':>10s} {'reimpl':>10s}  sign kept")
for c, t in PAIRS:
    a = m[[c, t]].dropna()
    b = m2[[c, t]].dropna()
    r1, p1 = stats.spearmanr(a[c], a[t])
    r2, p2 = stats.spearmanr(b[c], b[t])
    keep = "yes" if np.sign(r1) == np.sign(r2) else "NO"
    rows.append(dict(pair=f"{c}~{t}", rho_published=round(r1, 3), p_published=round(p1, 4),
                     rho_reimpl=round(r2, 3), p_reimpl=round(p2, 4), sign_kept=keep))
    print(f"{c+'~'+t:34s} {r1:+10.3f} {r2:+10.3f}  {keep}")

pd.DataFrame(rows).to_csv(OUT, index=False, encoding="utf-8-sig")
print("\nsaved", OUT)
print("ALL S61 DONE")
