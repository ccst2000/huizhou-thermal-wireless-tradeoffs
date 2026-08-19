# -*- coding: utf-8 -*-
"""V3 s41: 统计重算 v2（回应审稿意见）
- 目标变量改用 LST v2（QA掩膜+中位数）与四相位覆盖均值
- 规模控制改用 built_dom_ha（域内建成面积），built_comp_ha 作对照
- FDR 分两族：F1=48 原始 Spearman（12形态×4结果）；F2=44 偏相关（11形态×4结果）
- 敏感性：剔除祖源+木梨硔（覆盖列）、剔除渔梁（全部）、留一县（4个头条关联）
- 频段稳健性：700MHz vs 2.6GHz（phase 0_0）
输出：data/stats_v2.json, tables/Table1_sample.csv, tables/Table2_correlation.csv, tables/TableA1_full.csv
"""
import json
import math

import numpy as np
import pandas as pd
from scipy import stats

# ---------- 数据合并 ----------
m = pd.read_csv("data/v3_master.csv")
lv = pd.read_csv("data/lst_village_v2.csv")
bd = pd.read_csv("data/built_domain_area.csv")
cv = pd.read_csv("data/village_sample_v2.csv")[["village", "county"]]
df = m.merge(lv, on="village").merge(bd, on="village").merge(cv, on="village")
assert len(df) == 29

MORPH = [("built_dom_ha", "Built-up area (domain)"), ("elong", "Elongation"),
         ("compact", "Compactness"), ("elev_m", "Elevation"), ("relief_m", "Relief"),
         ("slope_deg", "Slope"), ("southness", "Southness"), ("ns_asym_m", "N-S asymmetry"),
         ("tsvf", "tSVF"), ("forest_ring_pct", "Forest ring"),
         ("water_mean_m", "Water dist. (mean)"), ("water_min_m", "Water dist. (min)")]
TARGETS = [("lst_v2", "LST"), ("dlst_v2", "dLST"), ("cov85_4p", "cov85"), ("rsrp_p10_4p", "RSRP p10")]
CTRL = "built_dom_ha"


def bh_fdr(pvals):
    """Benjamini-Hochberg，返回 q 值数组。"""
    p = np.asarray(pvals, float)
    n = len(p)
    order = np.argsort(p)
    q = np.empty(n)
    prev = 1.0
    for i in range(n - 1, -1, -1):
        rank = i + 1
        val = p[order[i]] * n / rank
        prev = min(prev, val)
        q[order[i]] = prev
    return np.minimum(q, 1.0)


def pcorr_rank(x, y, ctrl, data):
    d = data[[x, y, ctrl]].dropna()
    rx = stats.rankdata(d[x]); ry = stats.rankdata(d[y]); rc = stats.rankdata(d[ctrl])
    rx_ = rx - np.polyval(np.polyfit(rc, rx, 1), rc)
    ry_ = ry - np.polyval(np.polyfit(rc, ry, 1), rc)
    r, p = stats.pearsonr(rx_, ry_)
    return r, p, len(d)


def spear(x, y, data):
    d = data[[x, y]].dropna()
    r, p = stats.spearmanr(d[x], d[y])
    return r, p, len(d)


# ---------- F1: 原始相关 12x4 ----------
raw_rows = []
for c, cn in MORPH:
    for t, tn in TARGETS:
        r, p, n = spear(c, t, df)
        raw_rows.append(dict(metric=c, target=t, rho=r, p=p, n=n))
raw = pd.DataFrame(raw_rows)
raw["q"] = bh_fdr(raw.p.values)
raw["survive"] = raw.q < 0.05

# ---------- F2: 偏相关 11x4（控制 built_dom_ha）+ 对照（控制 built_comp_ha）----------
part_rows, part_rows_alt = [], []
for c, cn in MORPH:
    if c == CTRL:
        continue
    for t, tn in TARGETS:
        r, p, n = pcorr_rank(c, t, CTRL, df)
        part_rows.append(dict(metric=c, target=t, rho=r, p=p, n=n))
        r2, p2, _ = pcorr_rank(c, t, "built_comp_ha", df)
        part_rows_alt.append(dict(metric=c, target=t, rho=r2, p=p2))
part = pd.DataFrame(part_rows)
part["q"] = bh_fdr(part.p.values)
part["survive"] = part.q < 0.05
part_alt = pd.DataFrame(part_rows_alt)

# ---------- 敏感性 A：覆盖目标剔除祖源+木梨硔（WorldCover 漏检回退网格）----------
sens_wc = {}
sub = df[~df.village.isin(["Zuyuan 祖源", "Mulihong 木梨硔"])]
for c, cn in MORPH:
    for t in ["cov85_4p", "rsrp_p10_4p"]:
        r, p, n = spear(c, t, sub)
        sens_wc[f"{c}~{t}"] = dict(rho=round(r, 3), p=round(p, 4), n=n)

# ---------- 敏感性 B：剔除渔梁（极端规模离群）----------
sens_yl = {}
sub2 = df[df.village != "Yuliang 渔梁"]
for c, cn in MORPH:
    for t, tn in TARGETS:
        r, p, n = spear(c, t, sub2)
        sens_yl[f"{c}~{t}"] = dict(rho=round(r, 3), p=round(p, 4), n=n)

# ---------- 敏感性 C：留一县（4 个头条关联）----------
HEAD = [("tsvf", "lst_v2"), ("tsvf", "cov85_4p"),
        ("forest_ring_pct", "lst_v2"), ("forest_ring_pct", "cov85_4p")]
loco = {}
for c, t in HEAD:
    full_r, full_p, _ = spear(c, t, df)
    runs = {}
    for ct in sorted(df.county.unique()):
        s = df[df.county != ct]
        if s[c].nunique() < 3:
            continue
        r, p, n = spear(c, t, s)
        runs[ct] = dict(rho=round(r, 3), p=round(p, 4), n=n)
    loco[f"{c}~{t}"] = dict(full_rho=round(full_r, 3), full_p=round(full_p, 4), leave_one_out=runs)

# ---------- 频段稳健性：700MHz vs 2.6GHz（phase 0_0）----------
a26 = pd.read_csv("data/coverage_p0_0.csv")
a07 = pd.read_csv("data/coverage_p0_0_f0.7.csv")
mm = a26.merge(a07, on="village", suffixes=("_26", "_07"))
freq = {}
for col in ["cov85", "cov95", "rsrp_mean", "rsrp_p10"]:
    r, p = stats.spearmanr(mm[f"{col}_26"], mm[f"{col}_07"])
    freq[col] = dict(spearman=round(r, 3), p=round(p, 5),
                     mean_26=round(float(mm[f"{col}_26"].mean()), 1),
                     mean_07=round(float(mm[f"{col}_07"].mean()), 1))

# ---------- 正文关键数字 ----------
S = {}
S["n_villages"] = int(len(df))
S["eirp_dbm"] = 30.21
hot = df.nlargest(5, "lst_v2")[["village", "lst_v2"]]
cold = df.nsmallest(5, "lst_v2")[["village", "lst_v2"]]
S["hottest5"] = [f"{v} {t:.1f}" for v, t in zip(hot.village, hot.lst_v2)]
S["coolest5"] = [f"{v} {t:.1f}" for v, t in zip(cold.village, cold.lst_v2)]
S["n_above40"] = int((df.lst_v2 > 40).sum())
S["n_below34"] = int((df.lst_v2 < 34).sum())
S["lst_v2_range"] = [round(float(df.lst_v2.min()), 1), round(float(df.lst_v2.max()), 1)]
S["dlst_v2_range"] = [round(float(df.dlst_v2.min()), 2), round(float(df.dlst_v2.max()), 2)]
S["dlst_v2_all_positive"] = bool((df.dlst_v2 > 0).all())
S["lst_v1_v2_meanabsdiff"] = round(float((df.lst_v2 - df.lst_v).abs().mean()), 2)
S["lst_obs_min_range"] = [int(df.obs_min.min()), int(df.obs_min.max())]
S["lst_obs_med_range"] = [int(df.obs_med.min()), int(df.obs_med.max())]

# 渔梁四相位
ph = {}
for tag in ["0_0", "0_1250", "1250_0", "1250_1250"]:
    d = pd.read_csv(f"data/coverage_p{tag}.csv")
    row = d[d.village == "Yuliang 渔梁"].iloc[0]
    ph[tag] = round(float(row.cov85), 1)
S["yuliang_cov85_phases"] = ph
S["yuliang_cov85_4p"] = round(float(df.loc[df.village == "Yuliang 渔梁", "cov85_4p"].iloc[0]), 1)
S["yuliang_built_dom_ha"] = round(float(df.loc[df.village == "Yuliang 渔梁", "built_dom_ha"].iloc[0]), 1)
S["zuyuan_tsvf"] = round(float(df.loc[df.village == "Zuyuan 祖源", "tsvf"].iloc[0]), 3)
S["built_dom_range"] = [round(float(df.built_dom_ha.min()), 1), round(float(df.built_dom_ha.max()), 1)]
_corr = df[["built_dom_ha", "built_comp_ha"]].dropna()
S["corr_built_dom_comp"] = round(float(stats.spearmanr(_corr.built_dom_ha, _corr.built_comp_ha)[0]), 3)
S["built_comp_ha_n_missing"] = int(df.built_comp_ha.isna().sum())

# elongation 权衡（审稿 M7）
r_t, p_t, _ = spear("elong", "lst_v2", df)
r_c, p_c, _ = spear("elong", "cov85_4p", df)
S["elong_tradeoff"] = dict(elong_lst=dict(rho=round(r_t, 3), p=round(p_t, 4)),
                           elong_cov85=dict(rho=round(r_c, 3), p=round(p_c, 4)))

# 头条关联（含 q）
head_out = {}
for c, t in HEAD:
    row = raw[(raw.metric == c) & (raw.target == t)].iloc[0]
    prow = part[(part.metric == c) & (part.target == t)]
    head_out[f"{c}~{t}"] = dict(rho=round(row.rho, 3), p=round(row.p, 5), q=round(row.q, 4),
                                survive=bool(row.survive),
                                partial_rho=round(float(prow.rho.iloc[0]), 3) if len(prow) else None,
                                partial_q=round(float(prow.q.iloc[0]), 4) if len(prow) else None)
S["headline"] = head_out
S["f1_n"] = int(len(raw)); S["f1_n_survive"] = int(raw.survive.sum())
S["f2_n"] = int(len(part)); S["f2_n_survive"] = int(part.survive.sum())
S["freq_700mhz"] = freq
S["sens_excl_wc_fallback"] = sens_wc
S["sens_excl_yuliang"] = sens_yl
S["leave_one_county"] = loco

with open("data/stats_v2.json", "w", encoding="utf-8") as f:
    json.dump(S, f, ensure_ascii=False, indent=1)

# ---------- Table 1 ----------
t1 = df[["village", "county", "lon", "lat", "built_dom_ha", "elev_m", "relief_m", "tsvf",
         "forest_ring_pct", "lst_v2", "dlst_v2", "cov85_4p", "cov95_4p", "rsrp_p10_4p"]].copy()
t1.columns = ["Village", "County", "Lon", "Lat", "Built-up in domain (ha)", "Elev (m)",
              "Relief (m)", "tSVF", "Forest ring (%)", "LST (degC)", "dLST (degC)",
              "cov85 4p-mean (%)", "cov95 4p-mean (%)", "RSRP p10 (dBm)"]
t1 = t1.round({"Lon": 4, "Lat": 4, "Built-up in domain (ha)": 1, "Elev (m)": 0, "Relief (m)": 0,
               "tSVF": 3, "Forest ring (%)": 0, "LST (degC)": 1, "dLST (degC)": 1,
               "cov85 4p-mean (%)": 1, "cov95 4p-mean (%)": 1, "RSRP p10 (dBm)": 1})
t1.to_csv("tables/Table1_sample.csv", index=False, encoding="utf-8-sig")

# ---------- Table 2（q 值标注，†=BH 存活）----------
def fmt(r, p, q):
    star = "***" if p < 0.001 else ("**" if p < 0.01 else ("*" if p < 0.05 else ""))
    dag = "†" if q < 0.05 else ""
    return f"{r:+.2f}{star}{dag}"


rows = []
for c, cn in MORPH:
    row = {"Morphological metric": cn}
    for t, tn in TARGETS:
        x = raw[(raw.metric == c) & (raw.target == t)].iloc[0]
        row[f"rho {tn}"] = fmt(x.rho, x.p, x.q)
    rows.append(row)
    if c == CTRL:
        continue
    row2 = {"Morphological metric": cn + " (ctrl size)"}
    for t, tn in TARGETS:
        x = part[(part.metric == c) & (part.target == t)].iloc[0]
        row2[f"rho {tn}"] = fmt(x.rho, x.p, x.q)
    rows.append(row2)
pd.DataFrame(rows).to_csv("tables/Table2_correlation.csv", index=False, encoding="utf-8-sig")

# ---------- 附录全量表 A1 ----------
ph_all = {}
for tag in ["0_0", "0_1250", "1250_0", "1250_1250"]:
    d = pd.read_csv(f"data/coverage_p{tag}.csv")[["village", "cov85"]].rename(
        columns={"cov85": f"cov85_p{tag}"})
    ph_all[tag] = d
a1 = df[["village", "county", "built_dom_ha", "built_comp_ha", "elong", "compact", "elev_m",
         "relief_m", "slope_deg", "southness", "ns_asym_m", "tsvf", "forest_ring_pct",
         "water_mean_m", "water_min_m", "lst_v2", "lst_bg2", "dlst_v2", "obs_min", "obs_med",
         "cov85_4p", "cov95_4p", "rsrp_mean_4p", "rsrp_p10_4p"]]
for tag in ["0_0", "0_1250", "1250_0", "1250_1250"]:
    a1 = a1.merge(ph_all[tag], on="village")
a1.to_csv("tables/TableA1_full.csv", index=False, encoding="utf-8-sig")

# ---------- 摘要打印 ----------
print("=== F1 raw 48: survive", S["f1_n_survive"], "===")
print(raw[raw.survive][["metric", "target", "rho", "p", "q"]].to_string(index=False))
print("\n=== F2 partial 44: survive", S["f2_n_survive"], "===")
print(part[part.survive][["metric", "target", "rho", "p", "q"]].to_string(index=False))
print("\nheadline:", json.dumps(head_out, ensure_ascii=False, indent=1))
print("\nelong tradeoff:", S["elong_tradeoff"])
print("hottest5:", S["hottest5"])
print("coolest5:", S["coolest5"])
print("yuliang phases:", S["yuliang_cov85_phases"], "4p=", S["yuliang_cov85_4p"])
print("freq:", json.dumps(freq, indent=1))
