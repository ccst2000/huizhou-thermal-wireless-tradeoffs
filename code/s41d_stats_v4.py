# -*- coding: utf-8 -*-
"""V3-R3 s41d: 统计重算 v4（P0-4 空间稳健推断版）
输入: data/v3_master_v4.csv（s21 v4 组装）, data/village_sample_v2.csv（county）,
      data/built_domain_area.csv
推断三层:
  1) naive Spearman p（参考）
  2) Moran-I 有效样本量修正 p（Clifford–Richardson–Hémon / Dutilleul 型近似，
     n_eff = n*(1-Ix)(1-Iy)，t 近似；对 Spearman rho 同法处理）
  3) 空间块 bootstrap 95% CI（0.15° 经纬网格块整体重抽，B=4999，seed=11；
     percentile CI；p_boot = 2*min(P(rho*<=0), P(rho*>=0))）
FDR: BH 在家族内分别作用于 naive p 与 ESS p（within-family BH-FDR，不再称 family-wise error control）
家族: F1 raw 12 形态/地形指标 x 4 结局 (lst_abs, dlst_v3m, cov85_4p, rsrp_p10_4p)
      F2 partial 11 x 4（控制 built_dom_ha，秩偏相关）
      dlst_v1/dlst_v2 为次要结局，只入附录 A9
敏感性: 排除渔梁 / 留一县 jackknife / 逐相位 rho 范围 / 700MHz / NLOS 截断对照
输出: data/stats_v4.json, tables/Table1_sample.csv, Table2_correlation.csv,
      TableA1_full.csv, A3 exact, A4 jackknife, A5 moran, A6 700MHz, A7 nloscap, A9 dlst_variants
用法: python s41d_stats_v4.py
"""
import json
import math
import shutil

import numpy as np
import pandas as pd
from scipy import stats

RNG = np.random.default_rng(11)
B = 2999

# ---------- 数据 ----------
m = pd.read_csv("data/v3_master_v4.csv")
cv = pd.read_csv("data/village_sample_v2.csv")[["village", "county"]]
bd = pd.read_csv("data/built_domain_area.csv")
df = m.merge(cv, on="village").merge(bd, on="village")
assert len(df) == 29

MORPH = [("built_dom_ha", "Built-up area (domain)"), ("elong_fd", "Elongation"),
         ("compact_fd", "Compactness"), ("elev_m", "Elevation"), ("relief_m", "Relief"),
         ("slope_deg", "Slope"), ("southness", "Southness"), ("ns_asym_m", "N-S asymmetry"),
         ("tsvf", "tSVF"), ("forest_ring_pct", "Forest ring"),
         ("water_mean_m", "Water dist. (mean)"), ("water_min_m", "Water dist. (min)")]
TARGETS = [("lst_abs", "LST"), ("dlst_v3m", "dLST-matched"), ("cov85_4p", "cov85"), ("rsrp_p10_4p", "RSRP p10")]
CTRL = "built_dom_ha"

# ---------- 空间权重（村心反距离，行标准化） ----------
from pyproj import Transformer
_tf = Transformer.from_crs(4326, 32650, always_xy=True)
_xy = np.array([_tf.transform(lo, la) for lo, la in zip(df.lon, df.lat)])
_D = np.hypot(_xy[:, 0][:, None] - _xy[:, 0][None, :], _xy[:, 1][:, None] - _xy[:, 1][None, :])
_W = np.where(_D > 0, 1.0 / np.maximum(_D, 1.0), 0.0)
_Wrs = _W / _W.sum(axis=1, keepdims=True)


def _w_subset(ok):
    W = _W[np.ix_(ok, ok)]
    s = W.sum(axis=1, keepdims=True)
    return W / np.where(s > 0, s, 1.0)


def moran_i(x, ok=None):
    x = np.asarray(x, float)
    if ok is None:
        ok = np.isfinite(x)
    xx = x[ok]
    Wrs = _w_subset(ok)
    z = xx - xx.mean()
    S0 = Wrs.sum()
    return float((len(xx) / S0) * (z @ Wrs @ z) / (z @ z))


def moran_perm_p(x, nperm=999):
    x = np.asarray(x, float)
    ok = np.isfinite(x)
    xx = x[ok]
    Wrs = _w_subset(ok)

    def mi(v):
        z = v - v.mean()
        return float((len(v) / Wrs.sum()) * (z @ Wrs @ z) / (z @ z))

    i0 = mi(xx)
    cnt = 1
    for _ in range(nperm):
        if abs(mi(RNG.permutation(xx))) >= abs(i0):
            cnt += 1
    return i0, cnt / (nperm + 1)


def ess_pvalue(r, n, ix, iy):
    """Moran-I 有效样本量修正（近似）：n_eff=n*(1-Ix)(1-Iy)，t 近似"""
    n_eff = max(3.0, n * (1 - ix) * (1 - iy))
    if abs(r) >= 1:
        return 0.0, n_eff
    t = abs(r) * math.sqrt((n_eff - 2) / max(1e-12, 1 - r ** 2))
    return float(2 * stats.t.sf(t, n_eff - 2)), n_eff


# ---------- 空间块 bootstrap ----------
_blocks = {}
for i, (lo, la) in enumerate(zip(df.lon, df.lat)):
    _blocks.setdefault((int(lo / 0.15), int(la / 0.15)), []).append(i)
BLK = list(_blocks.values())
print(f"spatial blocks: {len(BLK)} (villages/block: {[len(b) for b in BLK]})")


def block_boot_ci(x, y, stat_fn, c=None, b=B):
    x = np.asarray(x, float); y = np.asarray(y, float)
    cc = np.asarray(c, float) if c is not None else None
    ok = np.isfinite(x) & np.isfinite(y) & (np.isfinite(cc) if cc is not None else True)
    blk_ids = [np.array([i for i in bl if ok[i]]) for bl in BLK]
    blk_ids = [b_ for b_ in blk_ids if len(b_) > 0]
    r_obs = stat_fn(x[ok], y[ok]) if cc is None else stat_fn(x[ok], y[ok], cc[ok])
    boots = np.empty(b)
    for bi in range(b):
        pick = RNG.integers(0, len(blk_ids), size=len(blk_ids))
        sel = np.concatenate([blk_ids[j] for j in pick])
        if len(np.unique(sel)) < 4:
            boots[bi] = np.nan
            continue
        boots[bi] = stat_fn(x[sel], y[sel]) if cc is None else stat_fn(x[sel], y[sel], cc[sel])
    boots = boots[np.isfinite(boots)]
    lo, hi = np.percentile(boots, [2.5, 97.5])
    p_boot = 2 * min((boots <= 0).mean(), (boots >= 0).mean())
    return r_obs, float(lo), float(hi), float(min(p_boot, 1.0))


def spear_stat(x, y):
    rx = stats.rankdata(x); ry = stats.rankdata(y)
    rx = rx - rx.mean(); ry = ry - ry.mean()
    den = math.sqrt((rx @ rx) * (ry @ ry))
    return float((rx @ ry) / den) if den > 0 else np.nan


def pcorr_rank_arr(x, y, c):
    rx, ry, rc = stats.rankdata(x), stats.rankdata(y), stats.rankdata(c)
    A = np.column_stack([rc, np.ones_like(rc)])
    rx_ = rx - A @ np.linalg.lstsq(A, rx, rcond=None)[0]
    ry_ = ry - A @ np.linalg.lstsq(A, ry, rcond=None)[0]
    rx_ = rx_ - rx_.mean(); ry_ = ry_ - ry_.mean()
    den = math.sqrt((rx_ @ rx_) * (ry_ @ ry_))
    return float((rx_ @ ry_) / den) if den > 0 else np.nan


def pcorr_p(x, y, c):
    d = pd.DataFrame(dict(x=x, y=y, c=c)).dropna()
    rx, ry, rc = stats.rankdata(d.x), stats.rankdata(d.y), stats.rankdata(d.c)
    A = np.column_stack([rc, np.ones_like(rc)])
    rx_ = rx - A @ np.linalg.lstsq(A, rx, rcond=None)[0]
    ry_ = ry - A @ np.linalg.lstsq(A, ry, rcond=None)[0]
    r, p = stats.pearsonr(rx_, ry_)
    return r, p, len(d)


def bh_fdr(pvals):
    p = np.asarray(pvals, float)
    n = len(p)
    order = np.argsort(p)
    q = np.empty(n)
    prev = 1.0
    for i in range(n - 1, -1, -1):
        prev = min(prev, p[order[i]] * n / (i + 1))
        q[order[i]] = prev
    return np.minimum(q, 1.0)


# ---------- Moran 全表 ----------
moran_rows = []
for c, _ in MORPH + TARGETS:
    v = df[c].values.astype(float)
    ok = np.isfinite(v)
    I, p = moran_perm_p(v)
    moran_rows.append(dict(variable=c, I=round(I, 3), p=round(p, 4), n=int(ok.sum())))
moran_df = pd.DataFrame(moran_rows)
moran_df.to_csv("tables/TableA5_moran.csv", index=False, encoding="utf-8-sig")
print(moran_df.to_string(index=False))

# ---------- F1 ----------
raw_rows = []
for c, cn in MORPH:
    for t, tn in TARGETS:
        sub = df[[c, t]].dropna()
        x, y = sub[c].values, sub[t].values
        n = len(sub)
        r, p = stats.spearmanr(x, y)
        ok = np.isfinite(df[c].values.astype(float)) & np.isfinite(df[t].values.astype(float))
        ix = moran_i(df[c].values.astype(float), ok)
        iy = moran_i(df[t].values.astype(float), ok)
        p_ess, n_eff = ess_pvalue(r, n, ix, iy)
        _, ci_lo, ci_hi, p_boot = block_boot_ci(df[c].values, df[t].values, spear_stat)
        raw_rows.append(dict(metric=c, target=t, rho=round(r, 3), p=p, p_ess=p_ess,
                             n=n, n_eff=round(n_eff, 1), ci_lo=round(ci_lo, 3),
                             ci_hi=round(ci_hi, 3), p_boot=round(p_boot, 4)))
    print(f"F1 done: {c}", flush=True)
raw = pd.DataFrame(raw_rows)
raw["q"] = bh_fdr(raw.p.values)
raw["q_ess"] = bh_fdr(raw.p_ess.values)
raw["survive"] = raw.q < 0.05
raw["survive_ess"] = raw.q_ess < 0.05

# ---------- F2 ----------
part_rows = []
for c, cn in MORPH:
    if c == CTRL:
        continue
    for t, tn in TARGETS:
        r, p, n = pcorr_p(df[c].values, df[t].values, df[CTRL].values)
        x = df[c].values.astype(float); y = df[t].values.astype(float)
        ok = np.isfinite(x) & np.isfinite(y)
        ix, iy = moran_i(x, ok), moran_i(y, ok)
        p_ess, n_eff = ess_pvalue(r, n, ix, iy)
        _, ci_lo, ci_hi, p_boot = block_boot_ci(df[c].values, df[t].values,
                                                pcorr_rank_arr, c=df[CTRL].values)
        part_rows.append(dict(metric=c, target=t, rho=round(r, 3), p=p, p_ess=p_ess,
                              n=n, n_eff=round(n_eff, 1), ci_lo=round(ci_lo, 3),
                              ci_hi=round(ci_hi, 3), p_boot=round(p_boot, 4)))
part = pd.DataFrame(part_rows)
part["q"] = bh_fdr(part.p.values)
part["q_ess"] = bh_fdr(part.p_ess.values)
part["survive"] = part.q < 0.05
part["survive_ess"] = part.q_ess < 0.05

print("\n=== F1 (naive q<.05):", int(raw.survive.sum()), "  (ESS q<.05):", int(raw.survive_ess.sum()), "===")
print(raw[raw.survive_ess][["metric", "target", "rho", "p", "p_ess", "q_ess", "ci_lo", "ci_hi"]].to_string(index=False))
print("\n=== F2 (naive q<.05):", int(part.survive.sum()), "  (ESS q<.05):", int(part.survive_ess.sum()), "===")
print(part[part.survive_ess][["metric", "target", "rho", "p", "p_ess", "q_ess", "ci_lo", "ci_hi"]].to_string(index=False))

raw.to_csv("tables/_F1_v4.csv", index=False, encoding="utf-8-sig")
part.to_csv("tables/_F2_v4.csv", index=False, encoding="utf-8-sig")

import os

# ---------- 敏感性：逐相位 headline rho 范围 ----------
ph4 = pd.read_csv("data/coverage_4phase_v4.csv")
per_phase = {}
for x in ["slope_deg", "forest_ring_pct", "tsvf", "relief_m"]:
    rr = []
    for ph, g in ph4.groupby("phase"):
        dd = g[["village", "cov85"]].merge(df[["village", x]], on="village").dropna()
        rr.append(round(stats.spearmanr(dd[x], dd.cov85)[0], 3))
    per_phase[f"{x}~cov85"] = dict(per_phase=rr, rho_4p=float(raw[(raw.metric == x) & (raw.target == "cov85_4p")].rho.iloc[0]))

# ---------- 敏感性：排除渔梁 ----------
sens_yl = {}
sub2 = df[df.village != "Yuliang 渔梁"]
for c, cn in MORPH:
    for t, tn in TARGETS:
        ss = sub2[[c, t]].dropna()
        r, p = stats.spearmanr(ss[c], ss[t])
        sens_yl[f"{c}~{t}"] = dict(rho=round(r, 3), p=round(p, 4))

# ---------- 留一县 jackknife（headline） ----------
HEAD = [("tsvf", "lst_abs"), ("tsvf", "cov85_4p"), ("forest_ring_pct", "cov85_4p"),
        ("slope_deg", "cov85_4p"), ("relief_m", "dlst_v3m"), ("tsvf", "rsrp_p10_4p")]
loco = {}
for c, t in HEAD:
    dd0 = df[[c, t]].dropna()
    full_r, full_p = stats.spearmanr(dd0[c], dd0[t])
    runs = {}
    for ct in sorted(df.county.unique()):
        s = df[df.county != ct][[c, t]].dropna()
        if s[c].nunique() < 3:
            continue
        r, p = stats.spearmanr(s[c], s[t])
        runs[ct] = dict(rho=round(r, 3), p=round(p, 4), n=len(s))
    loco[f"{c}~{t}"] = dict(full_rho=round(full_r, 3), full_p=round(full_p, 5), leave_one_out=runs)

a4_rows = []
for pair, dd in loco.items():
    a4_rows.append(dict(pair=pair, dropped_county="(full sample)", rho=dd["full_rho"], p=dd["full_p"], n=29))
    for cty, rr in dd["leave_one_out"].items():
        a4_rows.append(dict(pair=pair, dropped_county=cty, rho=rr["rho"], p=rr["p"], n=rr["n"]))
pd.DataFrame(a4_rows).to_csv("tables/TableA4_jackknife.csv", index=False, encoding="utf-8-sig")

# ---------- 频段稳健性（v4） ----------
a26 = pd.read_csv("data/coverage_p0_0_v4.csv")
a07 = pd.read_csv("data/coverage_p0_0_f0.7_v4.csv")
mm = a26.merge(a07, on="village", suffixes=("_26", "_07"))
freq = {}
for col in ["cov85", "cov95", "rsrp_mean", "rsrp_p10"]:
    r, p = stats.spearmanr(mm[f"{col}_26"], mm[f"{col}_07"])
    freq[col] = dict(spearman=round(r, 3), p=round(p, 5),
                     mean_26=round(float(mm[f"{col}_26"].mean()), 1),
                     mean_07=round(float(mm[f"{col}_07"].mean()), 1))
shutil.copy("data/coverage_4phase_v4_f07.csv", "tables/TableA6_700mhz_4phase.csv")

# ---------- A7: NLOS 截断 + d3D 修正 敏感性 ----------
a7_rows = []
for tag in ["0_0", "0_1250", "1250_0", "1250_1250"]:
    capf, ncf = f"data/coverage_p{tag}_v4.csv", f"data/coverage_p{tag}_v4nocap.csv"
    if os.path.exists(capf) and os.path.exists(ncf):
        j = pd.read_csv(capf).merge(pd.read_csv(ncf), on="village", suffixes=("_cap", "_nocap"))
        a7_rows.append(dict(comparison=f"phase {tag}: NLOS cap vs nocap",
                            cov85_stat=round(float((j.cov85_cap - j.cov85_nocap).abs().max()), 2),
                            cov95_stat=round(float((j.cov95_cap - j.cov95_nocap).abs().max()), 2),
                            rsrp_stat=round(float((j.rsrp_mean_cap - j.rsrp_mean_nocap).abs().max()), 2),
                            note="max abs diff (pct-pts / dB)"))
for tag in ["0_0", "0_1250", "1250_0", "1250_1250"]:
    oldf, newf = f"data/coverage_p{tag}.csv", f"data/coverage_p{tag}_v4.csv"
    if os.path.exists(oldf) and os.path.exists(newf):
        j = pd.read_csv(oldf).merge(pd.read_csv(newf), on="village", suffixes=("_old", "_v4"))
        a7_rows.append(dict(comparison=f"phase {tag}: v3 (const-d3D, uncapped) vs v4",
                            cov85_stat=round(float(stats.spearmanr(j.cov85_old, j.cov85_v4)[0]), 3),
                            cov95_stat=round(float(stats.spearmanr(j.cov95_old, j.cov95_v4)[0]), 3),
                            rsrp_stat=round(float(stats.spearmanr(j.rsrp_mean_old, j.rsrp_mean_v4)[0]), 3),
                            note="rank corr"))
pd.DataFrame(a7_rows).to_csv("tables/TableA7_nlos_d3d_sensitivity.csv", index=False, encoding="utf-8-sig")

# ---------- A9: ΔLST 三变体全表 ----------
lv4 = pd.read_csv("data/lst_village_v4.csv")
a9 = lv4.pivot_table(index="village", columns="variant",
                     values=["dlst", "ci_lo", "ci_hi", "n_over", "p_pos",
                             "dlst_cov25", "dlst_with_nearzero"], aggfunc="first")
a9.columns = [f"{a}_{b}" for a, b in a9.columns]
a9 = a9.reset_index()
a9.to_csv("tables/TableA9_dlst_variants.csv", index=False, encoding="utf-8-sig")

# ---------- 正文关键数字 S ----------
S = {}
S["n_villages"] = int(len(df))
S["eirp_dbm"] = 30.21
hot = df.nlargest(5, "lst_abs")[["village", "lst_abs"]]
cold = df.nsmallest(5, "lst_abs")[["village", "lst_abs"]]
S["hottest5"] = [f"{v} {t:.1f}" for v, t in zip(hot.village, hot.lst_abs)]
S["coolest5"] = [f"{v} {t:.1f}" for v, t in zip(cold.village, cold.lst_abs)]
S["n_above40"] = int((df.lst_abs > 40).sum())
S["n_below34"] = int((df.lst_abs < 34).sum())
S["lst_range"] = [round(float(df.lst_abs.min()), 1), round(float(df.lst_abs.max()), 1)]
for v, key in [("V1", "v1"), ("V2", "v2"), ("V3", "v3m")]:
    s = lv4[lv4.variant == v].dropna(subset=["dlst"])
    S[f"dlst_{key}_mean"] = round(float(s.dlst.mean()), 2)
    S[f"dlst_{key}_range"] = [round(float(s.dlst.min()), 2), round(float(s.dlst.max()), 2)]
    S[f"dlst_{key}_n"] = int(len(s))
    S[f"dlst_{key}_n_pos"] = int((s.dlst > 0).sum())
    S[f"dlst_{key}_n_sig"] = int(s.sig_pos.sum())
S["dlst_v3m_neg_villages"] = lv4[(lv4.variant == "V3") & (lv4.dlst <= 0)].village.tolist()
S["n_overpasses"] = int(pd.read_csv("data/dlst_overpass_matrix_v4.csv").overpass_date.nunique())
S["per_phase_headline"] = per_phase
S["yuliang_cov85_phases"] = {ph: round(float(g.cov85.iloc[0]), 1) for ph, g in
                             ph4[ph4.village == "Yuliang 渔梁"].groupby("phase")}
S["yuliang_cov85_4p"] = round(float(df.loc[df.village == "Yuliang 渔梁", "cov85_4p"].iloc[0]), 1)
S["zuyuan_tsvf"] = round(float(df.loc[df.village == "Zuyuan 祖源", "tsvf"].iloc[0]), 3)
S["built_dom_range"] = [round(float(df.built_dom_ha.min()), 1), round(float(df.built_dom_ha.max()), 1)]
_cx = df[["built_dom_ha", "built_fd_ha"]].dropna()
S["corr_built_dom_fd"] = round(float(stats.spearmanr(_cx.built_dom_ha, _cx.built_fd_ha)[0]), 3)
S["shape_n"] = int(df.elong_fd.notna().sum())

_d1 = df[["elong_fd", "lst_abs"]].dropna()
_d2 = df[["elong_fd", "cov85_4p"]].dropna()
r_t, p_t = stats.spearmanr(_d1.elong_fd, _d1.lst_abs)
r_c, p_c = stats.spearmanr(_d2.elong_fd, _d2.cov85_4p)
S["elong_tradeoff"] = dict(elong_lst=dict(rho=round(r_t, 3), p=round(p_t, 4)),
                           elong_cov85=dict(rho=round(r_c, 3), p=round(p_c, 4)))

head_out = {}
for c, t in HEAD:
    row = raw[(raw.metric == c) & (raw.target == t)].iloc[0]
    prow = part[(part.metric == c) & (part.target == t)]
    head_out[f"{c}~{t}"] = dict(rho=round(row.rho, 3), p=float(f"{row.p:.3e}"),
                                p_ess=float(f"{row.p_ess:.3e}"), q_ess=round(row.q_ess, 4),
                                ci95=[row.ci_lo, row.ci_hi], n=int(row.n), n_eff=float(row.n_eff),
                                survive_ess=bool(row.survive_ess),
                                partial_rho=round(float(prow.rho.iloc[0]), 3) if len(prow) else None,
                                partial_q_ess=round(float(prow.q_ess.iloc[0]), 4) if len(prow) else None)
S["headline"] = head_out
S["f1_n"] = int(len(raw)); S["f1_n_survive"] = int(raw.survive.sum()); S["f1_n_survive_ess"] = int(raw.survive_ess.sum())
S["f2_n"] = int(len(part)); S["f2_n_survive"] = int(part.survive.sum()); S["f2_n_survive_ess"] = int(part.survive_ess.sum())
S["freq_700mhz"] = freq
S["sens_excl_yuliang"] = sens_yl
S["leave_one_county"] = loco
S["spatial_moran"] = {r.variable: dict(I=r.I, p=r.p, n=int(r.n)) for r in moran_df.itertuples()}
S["cov85_phase_sd_mean"] = round(float(df.cov85_4p_sd.mean()), 2)
S["cov85_phase_sd_max"] = round(float(df.cov85_4p_sd.max()), 1)
w = ph4.pivot(index="village", columns="phase", values="cov85")
ph_rho = [stats.spearmanr(w[a], w[b])[0] for i, a in enumerate(w.columns) for b in w.columns[i + 1:]]
S["cov85_phase_pairwise_rho"] = [round(float(np.mean(ph_rho)), 3), round(float(np.min(ph_rho)), 3)]
wr = ph4.pivot(index="village", columns="phase", values="rsrp_mean")
ph_rho2 = [stats.spearmanr(wr[a], wr[b])[0] for i, a in enumerate(wr.columns) for b in wr.columns[i + 1:]]
S["rsrp_phase_pairwise_rho"] = [round(float(np.mean(ph_rho2)), 3), round(float(np.min(ph_rho2)), 3)]

def _clean(o):
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


with open("data/stats_v4.json", "w", encoding="utf-8") as f:
    json.dump(_clean(S), f, ensure_ascii=False, indent=1)

# ---------- Table 1 ----------
t1 = df[["village", "county", "built_dom_ha", "elev_m", "relief_m", "tsvf",
         "forest_ring_pct", "lst_abs", "dlst_v1", "dlst_v1_lo", "dlst_v1_hi",
         "dlst_v3m", "dlst_v3m_lo", "dlst_v3m_hi", "cov85_4p", "cov85_4p_sd",
         "rsrp_p10_4p"]].copy()
t1["dLST-V1 (degC) [95% CI]"] = t1.apply(lambda r: f"{r.dlst_v1:.2f} [{r.dlst_v1_lo:.2f}, {r.dlst_v1_hi:.2f}]", axis=1)
t1["dLST-matched (degC) [95% CI]"] = t1.apply(
    lambda r: f"{r.dlst_v3m:.2f} [{r.dlst_v3m_lo:.2f}, {r.dlst_v3m_hi:.2f}]" if np.isfinite(r.dlst_v3m) else "n/a", axis=1)
t1["cov85 4p-mean (sd) (%)"] = t1.apply(lambda r: f"{r.cov85_4p:.1f} ({r.cov85_4p_sd:.1f})", axis=1)
t1 = t1[["village", "county", "built_dom_ha", "elev_m", "relief_m", "tsvf",
         "forest_ring_pct", "lst_abs", "dLST-V1 (degC) [95% CI]",
         "dLST-matched (degC) [95% CI]", "cov85 4p-mean (sd) (%)", "rsrp_p10_4p"]]
t1.columns = ["Village", "County", "Built-up in domain (ha)", "Elev (m)", "Relief (m)",
              "tSVF", "Forest ring (%)", "LST (degC)", "dLST-V1 (degC) [95% CI]",
              "dLST-matched (degC) [95% CI]", "cov85 4p-mean (sd) (%)", "RSRP p10 (dBm)"]
t1 = t1.round({"Built-up in domain (ha)": 1, "Elev (m)": 0, "Relief (m)": 0,
               "tSVF": 3, "Forest ring (%)": 0, "LST (degC)": 1, "RSRP p10 (dBm)": 1})
t1.to_csv("tables/Table1_sample.csv", index=False, encoding="utf-8-sig")

# ---------- Table 2（星号=naive p，†=within-family BH-FDR on ESS-adjusted p） ----------
def fmt2(r, p, qe):
    star = "***" if p < 0.001 else ("**" if p < 0.01 else ("*" if p < 0.05 else ""))
    dag = "†" if qe < 0.05 else ""
    return f"{r:+.2f}{star}{dag}"


rows2 = []
for c, cn in MORPH:
    row = {"Morphological metric": cn}
    for t, tn in TARGETS:
        x = raw[(raw.metric == c) & (raw.target == t)].iloc[0]
        row[f"rho {tn}"] = fmt2(x.rho, x.p, x.q_ess)
    rows2.append(row)
    if c == CTRL:
        continue
    row2 = {"Morphological metric": cn + " (ctrl size)"}
    for t, tn in TARGETS:
        x = part[(part.metric == c) & (part.target == t)].iloc[0]
        row2[f"rho {tn}"] = fmt2(x.rho, x.p, x.q_ess)
    rows2.append(row2)
pd.DataFrame(rows2).to_csv("tables/Table2_correlation.csv", index=False, encoding="utf-8-sig")

# ---------- A1 全量 ----------
ph_all = {}
for tag in ["0_0", "0_1250", "1250_0", "1250_1250"]:
    ph_all[tag] = pd.read_csv(f"data/coverage_p{tag}_v4.csv")[["village", "cov85"]].rename(
        columns={"cov85": f"cov85_p{tag}"})
a1 = df[["village", "county", "lon", "lat", "built_dom_ha", "built_fd_ha", "elong_fd",
         "compact_fd", "elev_m", "relief_m", "slope_deg", "southness", "ns_asym_m",
         "tsvf", "forest_ring_pct", "water_mean_m", "water_min_m", "lst_abs",
         "dlst_v1", "dlst_v1_lo", "dlst_v1_hi", "dlst_v1_n", "dlst_v2", "dlst_v2_n",
         "dlst_v3m", "dlst_v3m_lo", "dlst_v3m_hi", "dlst_v3m_n",
         "cov85_4p", "cov85_4p_sd", "cov95_4p", "rsrp_mean_4p", "rsrp_p10_4p",
         "cov85_4p_f07", "rsrp_mean_4p_f07"]]
for tag in ["0_0", "0_1250", "1250_0", "1250_1250"]:
    a1 = a1.merge(ph_all[tag], on="village")
a1.to_csv("tables/TableA1_full.csv", index=False, encoding="utf-8-sig")

# ---------- A3 exact 全表 ----------
a3_rows = []
for _, x in raw.iterrows():
    a3_rows.append(dict(family="F1 raw", metric=x.metric, target=x.target, rho=x.rho,
                        p=round(x.p, 6), p_ess=round(x.p_ess, 6), q=round(x.q, 4), q_ess=round(x.q_ess, 4),
                        ci_lo=x.ci_lo, ci_hi=x.ci_hi, n=x.n, n_eff=x.n_eff,
                        survive_fdr=bool(x.survive), survive_fdr_ess=bool(x.survive_ess)))
for _, x in part.iterrows():
    a3_rows.append(dict(family="F2 partial (ctrl domain built-up)", metric=x.metric, target=x.target,
                        rho=x.rho, p=round(x.p, 6), p_ess=round(x.p_ess, 6), q=round(x.q, 4),
                        q_ess=round(x.q_ess, 4), ci_lo=x.ci_lo, ci_hi=x.ci_hi, n=x.n, n_eff=x.n_eff,
                        survive_fdr=bool(x.survive), survive_fdr_ess=bool(x.survive_ess)))
pd.DataFrame(a3_rows).to_csv("tables/TableA3_exact_stats.csv", index=False, encoding="utf-8-sig")

print("\n=== S saved to data/stats_v4.json ===")
print("headline:", json.dumps(head_out, ensure_ascii=False, indent=1))
print("dlst means v1/v2/v3m:", S["dlst_v1_mean"], S["dlst_v2_mean"], S["dlst_v3m_mean"])
print("tables written: Table1, Table2, A1, A3, A4, A5, A6, A7, A9")
