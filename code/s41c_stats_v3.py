# -*- coding: utf-8 -*-
"""V3 s41c (Round-2): 统计重算 v3
- dLST 改用 scene-matched 逐景 anomaly 均值 (dlst_v3, s50)，附 bootstrap CI/P(>0)
- LST 绝对值保留 lst_v2 作描述；Table1 增加 dLST CI 列；A1 增加 v3 列
- 新增补充表: A3 exact p/q/CI 全表, A4 jackknife 全表, A5 Moran 全表,
  A6 700MHz 四相位, A7 NLOS5km 敏感性, A8 场景构成
输出：data/stats_v3.json, tables/Table1_sample.csv, Table2_correlation.csv,
      TableA1_full.csv, TableA3..A8
"""
import json
import math

import numpy as np
import pandas as pd
from scipy import stats

# ---------- 数据合并 ----------
m = pd.read_csv("data/v3_master.csv")
lv = pd.read_csv("data/lst_village_v3.csv")     # <- v3: scene-matched + bootstrap
bd = pd.read_csv("data/built_domain_area.csv")
cv = pd.read_csv("data/village_sample_v2.csv")[["village", "county"]]
mf = pd.read_csv("data/morphology_framed.csv")[["village", "elong_fd", "compact_fd", "built_fd_ha"]]
df = m.merge(lv, on="village").merge(bd, on="village").merge(cv, on="village").merge(mf, on="village")
assert len(df) == 29

MORPH = [("built_dom_ha", "Built-up area (domain)"), ("elong_fd", "Elongation"),
         ("compact_fd", "Compactness"), ("elev_m", "Elevation"), ("relief_m", "Relief"),
         ("slope_deg", "Slope"), ("southness", "Southness"), ("ns_asym_m", "N-S asymmetry"),
         ("tsvf", "tSVF"), ("forest_ring_pct", "Forest ring"),
         ("water_mean_m", "Water dist. (mean)"), ("water_min_m", "Water dist. (min)")]
TARGETS = [("lst_v2", "LST"), ("dlst_v3", "dLST"), ("cov85_4p", "cov85"), ("rsrp_p10_4p", "RSRP p10")]
CTRL = "built_dom_ha"


def bh_fdr(pvals):
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


def fisher_ci(r, n):
    if n < 4 or abs(r) >= 1:
        return (np.nan, np.nan)
    z = math.atanh(r)
    se = 1.0 / math.sqrt(n - 3)
    lo, hi = z - 1.96 * se, z + 1.96 * se
    return (round(math.tanh(lo), 3), round(math.tanh(hi), 3))


# ---------- F1: 原始相关 12x4 ----------
raw_rows = []
for c, cn in MORPH:
    for t, tn in TARGETS:
        r, p, n = spear(c, t, df)
        raw_rows.append(dict(metric=c, target=t, rho=r, p=p, n=n))
raw = pd.DataFrame(raw_rows)
raw["q"] = bh_fdr(raw.p.values)
raw["survive"] = raw.q < 0.05

# ---------- F2: 偏相关 11x4 ----------
part_rows = []
for c, cn in MORPH:
    if c == CTRL:
        continue
    for t, tn in TARGETS:
        r, p, n = pcorr_rank(c, t, CTRL, df)
        part_rows.append(dict(metric=c, target=t, rho=r, p=p, n=n))
part = pd.DataFrame(part_rows)
part["q"] = bh_fdr(part.p.values)
part["survive"] = part.q < 0.05

# ---------- 敏感性 A/B ----------
sens_wc = {}
sub = df[~df.village.isin(["Zuyuan 祖源", "Mulihong 木梨硔"])]
for c, cn in MORPH:
    for t in ["cov85_4p", "rsrp_p10_4p"]:
        r, p, n = spear(c, t, sub)
        sens_wc[f"{c}~{t}"] = dict(rho=round(r, 3), p=round(p, 4), n=n)

sens_yl = {}
sub2 = df[df.village != "Yuliang 渔梁"]
for c, cn in MORPH:
    for t, tn in TARGETS:
        r, p, n = spear(c, t, sub2)
        sens_yl[f"{c}~{t}"] = dict(rho=round(r, 3), p=round(p, 4), n=n)

# ---------- 敏感性 C：留一县 ----------
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

# ---------- 频段稳健性 ----------
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
# v3 dLST
S["dlst_v3_range"] = [round(float(df.dlst_v3.min()), 2), round(float(df.dlst_v3.max()), 2)]
S["dlst_v3_mean"] = round(float(df.dlst_v3.mean()), 2)
S["dlst_v3_all_positive"] = bool((df.dlst_v3 > 0).all())
S["dlst_v3_n_sig_pos"] = int((df.ci_lo > 0).sum())
S["dlst_v3_n_estimable"] = int((df.n_scenes >= 3).sum())
S["dlst_v3_p_pos_min"] = round(float(df.p_pos.min()), 3)
old2 = pd.read_csv("data/lst_village_v2.csv")
S["dlst_v2_v3_rank"] = round(float(stats.spearmanr(old2.dlst_v2, df.dlst_v3).statistic), 3)
S["lst_obs_min_range"] = [int(df.obs_min.min()), int(df.obs_med.max())]

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
_corr = df[["built_dom_ha", "built_fd_ha"]].dropna()
S["corr_built_dom_fd"] = round(float(stats.spearmanr(_corr.built_dom_ha, _corr.built_fd_ha)[0]), 3)
S["shape_n"] = int(df.elong_fd.notna().sum())

# elongation 权衡（Frame-D 口径, round-2）
r_t, p_t, _ = spear("elong_fd", "lst_v2", df)
r_c, p_c, _ = spear("elong_fd", "cov85_4p", df)
S["elong_tradeoff"] = dict(elong_lst=dict(rho=round(r_t, 3), p=round(p_t, 4)),
                           elong_cov85=dict(rho=round(r_c, 3), p=round(p_c, 4)))

head_out = {}
for c, t in HEAD:
    row = raw[(raw.metric == c) & (raw.target == t)].iloc[0]
    prow = part[(part.metric == c) & (part.target == t)]
    ci = fisher_ci(row.rho, row.n)
    head_out[f"{c}~{t}"] = dict(rho=round(row.rho, 3), p=round(row.p, 5), q=round(row.q, 4),
                                survive=bool(row.survive), ci95=[ci[0], ci[1]],
                                partial_rho=round(float(prow.rho.iloc[0]), 3) if len(prow) else None,
                                partial_q=round(float(prow.q.iloc[0]), 4) if len(prow) else None)
S["headline"] = head_out
S["f1_n"] = int(len(raw)); S["f1_n_survive"] = int(raw.survive.sum())
S["f2_n"] = int(len(part)); S["f2_n_survive"] = int(part.survive.sum())
S["freq_700mhz"] = freq
S["sens_excl_wc_fallback"] = sens_wc
S["sens_excl_yuliang"] = sens_yl
S["leave_one_county"] = loco

# Moran 全表（继承 s41b 结果）
s2 = json.load(open("data/stats_v2.json", encoding="utf-8"))
if "spatial_moran" in s2:
    S["spatial_moran"] = s2["spatial_moran"]

with open("data/stats_v3.json", "w", encoding="utf-8") as f:
    json.dump(S, f, ensure_ascii=False, indent=1)

# ---------- Table 1（精简列；坐标与 cov95 见补充表 A1 CSV）----------
t1 = df[["village", "county", "built_dom_ha", "elev_m", "relief_m", "tsvf",
         "forest_ring_pct", "lst_v2", "dlst_v3", "ci_lo", "ci_hi", "cov85_4p",
         "rsrp_p10_4p"]].copy()
t1["dLST (degC) [95% CI]"] = t1.apply(
    lambda r: f"{r.dlst_v3:.2f} [{r.ci_lo:.2f}, {r.ci_hi:.2f}]", axis=1)
t1 = t1[["village", "county", "built_dom_ha", "elev_m", "relief_m", "tsvf",
         "forest_ring_pct", "lst_v2", "dLST (degC) [95% CI]", "cov85_4p", "rsrp_p10_4p"]]
t1.columns = ["Village", "County", "Built-up in domain (ha)", "Elev (m)",
              "Relief (m)", "tSVF", "Forest ring (%)", "LST (degC)",
              "dLST (degC) [95% CI]", "cov85 4p-mean (%)", "RSRP p10 (dBm)"]
t1 = t1.round({"Built-up in domain (ha)": 1, "Elev (m)": 0, "Relief (m)": 0,
               "tSVF": 3, "Forest ring (%)": 0, "LST (degC)": 1,
               "cov85 4p-mean (%)": 1, "RSRP p10 (dBm)": 1})
t1.to_csv("tables/Table1_sample.csv", index=False, encoding="utf-8-sig")

# ---------- Table 2 ----------
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

# ---------- A1 全量（Frame-D 口径 + v3 列 + 相位）----------
ph_all = {}
for tag in ["0_0", "0_1250", "1250_0", "1250_1250"]:
    d = pd.read_csv(f"data/coverage_p{tag}.csv")[["village", "cov85"]].rename(
        columns={"cov85": f"cov85_p{tag}"})
    ph_all[tag] = d
a1 = df[["village", "county", "lon", "lat", "built_dom_ha", "built_fd_ha", "elong_fd",
         "compact_fd", "elev_m", "relief_m", "slope_deg", "southness", "ns_asym_m",
         "tsvf", "forest_ring_pct", "water_mean_m", "water_min_m", "lst_v2", "lst_bg2",
         "dlst_v3", "dlst_sd", "n_scenes", "ci_lo", "ci_hi", "p_pos", "obs_min", "obs_med",
         "cov85_4p", "cov95_4p", "rsrp_mean_4p", "rsrp_p10_4p"]]
for tag in ["0_0", "0_1250", "1250_0", "1250_1250"]:
    a1 = a1.merge(ph_all[tag], on="village")
a1.to_csv("tables/TableA1_full.csv", index=False, encoding="utf-8-sig")

# ---------- A3: exact rho/p/q/CI 全表（F1+F2）----------
a3_rows = []
for _, x in raw.iterrows():
    ci = fisher_ci(x.rho, x.n)
    a3_rows.append(dict(family="F1 raw", metric=x.metric, target=x.target,
                        rho=round(x.rho, 3), p=round(x.p, 6), q=round(x.q, 4),
                        ci_lo=ci[0], ci_hi=ci[1], n=x.n, survive_fdr=bool(x.survive)))
for _, x in part.iterrows():
    ci = fisher_ci(x.rho, x.n)
    a3_rows.append(dict(family="F2 partial (ctrl domain built-up)", metric=x.metric, target=x.target,
                        rho=round(x.rho, 3), p=round(x.p, 6), q=round(x.q, 4),
                        ci_lo=ci[0], ci_hi=ci[1], n=x.n, survive_fdr=bool(x.survive)))
pd.DataFrame(a3_rows).to_csv("tables/TableA3_exact_stats.csv", index=False, encoding="utf-8-sig")

# ---------- A4: jackknife 全表 ----------
jk_rows = []
for pair, dd in loco.items():
    jk_rows.append(dict(pair=pair, dropped_county="(full sample)", rho=dd["full_rho"],
                        p=dd["full_p"], n=29))
    for cty, rr in dd["leave_one_out"].items():
        jk_rows.append(dict(pair=pair, dropped_county=cty, rho=rr["rho"], p=rr["p"], n=rr["n"]))
pd.DataFrame(jk_rows).to_csv("tables/TableA4_jackknife.csv", index=False, encoding="utf-8-sig")

# ---------- A5: Moran 全表 ----------
if "spatial_moran" in s2:
    a5 = pd.DataFrame([dict(variable=k, I=v["I"], p=v["p"], n=v.get("n", 29))
                       for k, v in s2["spatial_moran"].items()])
    a5.to_csv("tables/TableA5_moran.csv", index=False, encoding="utf-8-sig")

# ---------- A6: 700MHz 四相位 / A7: NLOS5km / A8: 场景构成（s50 已产 CSV，复制入 tables/）----------
import shutil
for src_f, dst_f in [("data/coverage_700mhz_4phase.csv", "tables/TableA6_700mhz_4phase.csv"),
                     ("data/sens_nlos5k.csv", "tables/TableA7_nlos5k.csv"),
                     ("data/village_scene_composition.csv", "tables/TableA8_scene_composition.csv")]:
    shutil.copy(src_f, dst_f)

# ---------- 摘要打印 ----------
print("=== F1 raw 48: survive", S["f1_n_survive"], "===")
print(raw[raw.survive][["metric", "target", "rho", "p", "q"]].to_string(index=False))
print("\n=== F2 partial 44: survive", S["f2_n_survive"], "===")
print(part[part.survive][["metric", "target", "rho", "p", "q"]].to_string(index=False))
print("\nheadline:", json.dumps(head_out, ensure_ascii=False, indent=1))
print("\ndlst_v3: range", S["dlst_v3_range"], "mean", S["dlst_v3_mean"],
      "sig_pos", S["dlst_v3_n_sig_pos"], "/", S["dlst_v3_n_estimable"],
      "rank vs v2", S["dlst_v2_v3_rank"])
print("elong tradeoff:", S["elong_tradeoff"])
print("hottest5:", S["hottest5"])
print("coolest5:", S["coolest5"])
