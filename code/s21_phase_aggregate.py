# -*- coding: utf-8 -*-
"""V3 s21: 四相位聚合 + 排名稳健性 + 主表更新 + 耦合/偏相关重算
输出：data/coverage_4phase.csv（逐相位+均值）, 更新 data/v3_master.csv
"""
import numpy as np
import pandas as pd
from scipy import stats

phases = [(0, 0), (1250, 0), (0, 1250), (1250, 1250)]
dfs = []
for dx, dy in phases:
    d = pd.read_csv(f"data/coverage_p{dx}_{dy}.csv")
    d["phase"] = f"p{dx}_{dy}"
    dfs.append(d)
allp = pd.concat(dfs)
met = ["cov85", "cov95", "rsrp_mean", "rsrp_p10"]

# 逐村四相位均值
mean_df = allp.groupby("village")[met].mean().round(2).reset_index()
std_df = allp.groupby("village")[met].std().round(2).reset_index()

# 相位间排名稳健性：两两 Spearman
print("=== 相位两两排名相关（稳健性）===")
for m in met:
    wide = allp.pivot(index="village", columns="phase", values=m)
    rs = []
    cols = wide.columns.tolist()
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            rs.append(stats.spearmanr(wide[cols[i]], wide[cols[j]])[0])
    print(f"{m:10s} mean pairwise rho = {np.mean(rs):.3f}  (min {np.min(rs):.3f})")

wide_cov = allp.pivot(index="village", columns="phase", values="cov85").round(1)
print("\n=== cov85 逐相位 ===")
print(wide_cov.to_string())

# 更新主表
m = pd.read_csv("data/v3_master.csv")
m = m.drop(columns=[c for c in ["cov95", "rsrp_mean"] if c in m.columns])
m = m.merge(mean_df.rename(columns={c: c + "_4p" for c in met}), on="village", how="left")
m.to_csv("data/v3_master.csv", index=False)
print("\n主表已更新:", m.shape)

# ---- 耦合相关重算 ----
morph = ["built_ha", "elong", "compact", "elev_m", "relief_m", "slope_deg",
         "southness", "ns_asym_m", "tsvf", "forest_ring_pct", "water_mean_m", "water_min_m"]
targets = ["lst_v", "dlst", "cov85_4p", "cov95_4p", "rsrp_mean_4p", "rsrp_p10_4p"]
print("\n=== 全样本 Spearman（四相位均值指标）===")
res_tab = {}
for t in targets:
    rr = []
    for v in morph:
        sub = m[[v, t]].dropna()
        r, p = stats.spearmanr(sub[v], sub[t])
        rr.append((v, r, p))
    res_tab[t] = rr
    top = sorted(rr, key=lambda x: -abs(x[1]))[:4]
    print(f"\n-- {t}")
    for v, r, p in top:
        print(f"   {v:16s} rho={r:+.3f} p={p:.4f} {'*' if p < 0.05 else ''}")

# ---- 偏相关（控制 built_ha，秩）----
def pcorr(x, y, ctrl, data):
    d = data[[x, y, ctrl]].dropna()
    dx = stats.rankdata(d[x]); dy = stats.rankdata(d[y]); dc = stats.rankdata(d[ctrl])
    rx_ = dx - np.polyval(np.polyfit(dc, dx, 1), dc)
    ry_ = dy - np.polyval(np.polyfit(dc, dy, 1), dc)
    r, p = stats.pearsonr(rx_, ry_)
    return len(d), r, p

print("\n=== 控制 built_ha 偏相关 ===")
for x, y in [("tsvf", "lst_v"), ("tsvf", "cov85_4p"), ("tsvf", "rsrp_mean_4p"),
             ("tsvf", "rsrp_p10_4p"), ("relief_m", "cov85_4p"), ("relief_m", "rsrp_mean_4p"),
             ("forest_ring_pct", "lst_v"), ("forest_ring_pct", "cov85_4p")]:
    n, r, p = pcorr(x, y, "built_ha", m)
    print(f"{x:16s} -> {y:14s} n={n:2d} partial_r={r:+.3f} p={p:.4f} {'*' if p < 0.05 else ''}")
