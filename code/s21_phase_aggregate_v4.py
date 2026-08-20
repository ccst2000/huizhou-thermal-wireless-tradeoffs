# -*- coding: utf-8 -*-
"""V3-R3 s21 v4: 四相位聚合（d3D+NLOS 截断主模型）+ v3_master_v4.csv 组装
输入: data/coverage_p{dx}_{dy}_v4.csv (2.6GHz), data/coverage_p{dx}_{dy}_f0.7_v4.csv (0.7GHz)
输出:
  data/coverage_4phase_v4.csv       逐相位+均值 (2.6GHz 主模型)
  data/coverage_4phase_v4_f07.csv   逐相位+均值 (0.7GHz 敏感性)
  data/v3_master_v4.csv             村级主表（形态/地形/热v4/覆盖v4 全更新）
用法: python s21_phase_aggregate_v4.py
"""
import numpy as np
import pandas as pd
from scipy import stats

phases = [(0, 0), (1250, 0), (0, 1250), (1250, 1250)]
met = ["cov85", "cov95", "rsrp_mean", "rsrp_p10"]


def load_phase_stack(tag):
    dfs = []
    for dx, dy in phases:
        d = pd.read_csv(f"data/coverage_p{dx}_{dy}{tag}.csv")
        d["phase"] = f"p{dx}_{dy}"
        dfs.append(d)
    return pd.concat(dfs)


for tag, out in [("_v4", "data/coverage_4phase_v4.csv"),
                 ("_f0.7_v4", "data/coverage_4phase_v4_f07.csv")]:
    allp = load_phase_stack(tag)
    allp.to_csv(out, index=False)
    wide = allp.pivot(index="village", columns="phase", values="cov85")
    rs = [stats.spearmanr(wide[a], wide[b])[0]
          for i, a in enumerate(wide.columns) for b in wide.columns[i + 1:]]
    print(f"{tag}: cov85 相位两两 rho mean={np.mean(rs):.3f} min={np.min(rs):.3f}")

# ---------- 组装 v3_master_v4 ----------
m = pd.read_csv("data/v3_master.csv")
m = m.drop(columns=[c for c in ["lst_v", "lst_bg", "dlst",
                                "cov85_4p", "cov95_4p", "rsrp_mean_4p", "rsrp_p10_4p"] if c in m.columns])

# Frame-D 形态（基线口径）
fd = pd.read_csv("data/morphology_framed.csv")[["village", "built_fd_ha", "elong_fd", "compact_fd"]]
m = m.merge(fd, on="village", how="left")

# 热链 v4：绝对 LST + 三变体 ΔLST
la = pd.read_csv("data/lst_abs_village_v4.csv")[["village", "lst_abs"]]
m = m.merge(la, on="village", how="left")
lv = pd.read_csv("data/lst_village_v4.csv")
for v, col in [("V1", "dlst_v1"), ("V2", "dlst_v2"), ("V3", "dlst_v3m")]:
    s = lv[lv.variant == v][["village", "dlst", "ci_lo", "ci_hi", "n_over", "sig_pos"]]
    s = s.rename(columns={"dlst": col, "ci_lo": col + "_lo", "ci_hi": col + "_hi",
                          "n_over": col + "_n", "sig_pos": col + "_sig"})
    m = m.merge(s, on="village", how="left")

# 覆盖 v4：2.6GHz 主 + 0.7GHz 敏感性
for tag, suf, out in [("_v4", "", "data/coverage_4phase_v4.csv"),
                      ("_f0.7_v4", "_f07", "data/coverage_4phase_v4_f07.csv")]:
    allp = pd.read_csv(out)
    mean_df = allp.groupby("village")[met].mean().round(2).reset_index()
    sd_df = allp.groupby("village")[["cov85"]].std().round(2).reset_index()
    mean_df = mean_df.rename(columns={c: c + "_4p" + suf for c in met})
    sd_df = sd_df.rename(columns={"cov85": "cov85_4p" + suf + "_sd"})
    m = m.merge(mean_df, on="village", how="left").merge(sd_df, on="village", how="left")

m.to_csv("data/v3_master_v4.csv", index=False)
print("\nv3_master_v4:", m.shape)
print(m.columns.tolist())

# ---------- headline 耦合相关速览（正式统计在 s41c v4） ----------
pairs = [("tsvf", "lst_abs"), ("tsvf", "dlst_v1"), ("tsvf", "dlst_v3m"),
         ("tsvf", "cov85_4p"), ("forest_ring_pct", "cov85_4p"),
         ("slope_deg", "cov85_4p"), ("relief_m", "dlst_v3m"), ("elev_m", "dlst_v3m"),
         ("elong_fd", "cov85_4p"), ("compact_fd", "dlst_v3m")]
print("\n=== headline 速览（Spearman, v4 数据）===")
for x, y in pairs:
    sub = m[[x, y]].dropna()
    r, p = stats.spearmanr(sub[x], sub[y])
    print(f"{x:16s} ~ {y:12s} n={len(sub):2d} rho={r:+.3f} p={p:.4f}")
