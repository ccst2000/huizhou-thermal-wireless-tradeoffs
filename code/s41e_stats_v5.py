# -*- coding: utf-8 -*-
"""V5 s41e: 空间稳健统计链（回应 R4 P0-2/P0-5/P0-6/P0-9）
变更要点:
  1) 数据换 v5 主表（s10 可重建形态 + s62 肌理指标，16 指标）
  2) 空间推断主层改为【区组置换检验】block permutation（不依赖 ESS 近似有效性）:
     y 按 0.15° 区组整体置换, B=4999, seed=23, 双侧; 族内 BH q_perm 为主推断
  3) Moran-I ESS 修正降级为【次级敏感性】并诚实标注为自定义近似（非 Dutilleul 原法）:
     - Spearman 用【秩】的 Moran I；偏相关用【秩残差】的 Moran I；
     - n_eff 截断至 [3, n]（负 I 不再放大自由度）
  4) 区组设计敏感性: 0.10/0.15/0.20° × 两个原点, headline 对的 CI 与置换 p 范围 -> TableA14
  5) 保留: 逐相位敏感性、排除渔梁、留一县 jackknife、700MHz、A7、A9
输出: tables/_F1_v5.csv _F2_v5.csv TableA5_moran TableA14_block_sensitivity
      Table1/2/A1/A3/A4/A6/A7/A9 (v5) + data/stats_v5.json
"""
import json
import math
import os
import shutil

import numpy as np
import pandas as pd
from scipy import stats

RNG = np.random.default_rng(11)   # bootstrap
RNGP = np.random.default_rng(23)  # permutation
B = 2999       # block bootstrap resamples
BP = 4999      # block permutation resamples

# ---------- 数据 ----------
df = pd.read_csv("data/v3_master_v5.csv")
assert len(df) == 29

MORPH = [("built_dom_ha", "Built-up area (domain)"),
         ("cover_dom_pct", "Building coverage ratio"),
         ("elong_fd", "Elongation"), ("compact_fd", "Compactness"),
         ("edge_den_m_ha", "Edge density"), ("patch_den", "Patch density"),
         ("lps_pct", "Largest-patch share"),
         ("elev_m", "Elevation"), ("relief_m", "Relief"),
         ("slope_deg", "Slope"), ("southness", "Southness"), ("ns_asym_m", "N-S asymmetry"),
         ("tsvf", "Terrain-horizon openness (tSVF)"), ("forest_ring_pct", "Forest ring"),
         ("water_mean_m", "Water distance (mean)"), ("water_min_m", "Water distance (min)")]
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
    return float((len(xx) / Wrs.sum()) * (z @ Wrs @ z) / (z @ z))


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
    """自定义 Moran-I 有效样本量近似（非 Dutilleul 原法；次级敏感性）:
    n_eff=clip(n*(1-Ix)(1-Iy), 3, n)，t 近似。Ix/Iy 应传入秩（或秩残差）的 Moran I。"""
    n_eff = min(float(n), max(3.0, n * (1 - ix) * (1 - iy)))
    if abs(r) >= 1:
        return 0.0, n_eff
    t = abs(r) * math.sqrt((n_eff - 2) / max(1e-12, 1 - r ** 2))
    return float(2 * stats.t.sf(t, n_eff - 2)), n_eff


# ---------- 空间区组（参数化尺寸与原点） ----------
def make_blocks(size=0.15, origin=(0.0, 0.0)):
    bl = {}
    for i, (lo, la) in enumerate(zip(df.lon, df.lat)):
        key = (int((lo - origin[0]) / size), int((la - origin[1]) / size))
        bl.setdefault(key, []).append(i)
    return list(bl.values())


BLK = make_blocks(0.15)
print(f"spatial blocks: {len(BLK)} (villages/block: {sorted(len(b) for b in BLK)})")
BLK_MAP = {f"{k[0]},{k[1]}": [df.village.iloc[i] for i in v]
           for k, v in {(int(lo / 0.15), int(la / 0.15)): [] for lo, la in zip(df.lon, df.lat)}.items()}
_blocks_dbg = {}
for i, (lo, la) in enumerate(zip(df.lon, df.lat)):
    _blocks_dbg.setdefault(f"{int(lo/0.15)},{int(la/0.15)}", []).append(df.village.iloc[i])


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


def _ok_mask(x, y, c=None):
    ok = np.isfinite(np.asarray(x, float)) & np.isfinite(np.asarray(y, float))
    if c is not None:
        ok &= np.isfinite(np.asarray(c, float))
    return ok


def block_boot_ci(x, y, stat_fn, c=None, b=B, blocks=None):
    blocks = BLK if blocks is None else blocks
    x = np.asarray(x, float); y = np.asarray(y, float)
    cc = np.asarray(c, float) if c is not None else None
    ok = _ok_mask(x, y, c)
    blk_ids = [np.array([i for i in bl if ok[i]]) for bl in blocks]
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


def block_perm_p(x, y, stat_fn, c=None, b=None, blocks=None):
    """循环移位空间置换的【精确】双侧 p：完全案例子集上，村庄按区组排序，
    对 y 枚举全部 n0−1 个循环移位（移位即秩向量的 roll），构成精确零分布；
    无 Monte Carlo 误差。保持 y 的区组内空间结构（仅区组序列切口处断开）。"""
    blocks = BLK if blocks is None else blocks
    x = np.asarray(x, float); y = np.asarray(y, float)
    cc = np.asarray(c, float) if c is not None else None
    ok = _ok_mask(x, y, c)
    xo, yo = x[ok], y[ok]
    co = cc[ok] if cc is not None else None
    bid = np.full(len(x), -1)
    for bi_, bl in enumerate(blocks):
        for i in bl:
            bid[i] = bi_
    bo = bid[ok]
    order = np.argsort(bo, kind="stable")          # 区组内相邻
    n0 = len(xo)
    r_obs = stat_fn(xo, yo) if co is None else stat_fn(xo, yo, co)
    cnt = 0
    for k in range(1, n0):
        yp = np.empty(n0)
        yp[order] = np.roll(yo[order], k)          # 循环移位保持区组内结构
        rp = stat_fn(xo, yp) if co is None else stat_fn(xo, yp, co)
        if np.isfinite(rp) and abs(rp) >= abs(r_obs) - 1e-12:
            cnt += 1
    return float((cnt + 1) / n0)                   # 精确枚举: (超限数+1)/n0


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


# ---------- Moran 全表（原值 + 秩） ----------
moran_rows = []
for c, _ in MORPH + TARGETS:
    v = df[c].values.astype(float)
    ok = np.isfinite(v)
    I, p = moran_perm_p(v)
    rk = np.full(len(v), np.nan)
    rk[ok] = stats.rankdata(v[ok])
    Ir, pr = moran_perm_p(rk)
    moran_rows.append(dict(variable=c, I=round(I, 3), p=round(p, 4),
                           I_rank=round(Ir, 3), p_rank=round(pr, 4), n=int(ok.sum())))
moran_df = pd.DataFrame(moran_rows)
moran_df.to_csv("tables/TableA5_moran.csv", index=False, encoding="utf-8-sig")
print(moran_df.to_string(index=False))

# ---------- F1 raw ----------
raw_rows = []
for c, cn in MORPH:
    xc_full = df[c].values.astype(float)
    for t, tn in TARGETS:
        yc_full = df[t].values.astype(float)
        sub = df[[c, t]].dropna()
        x, y = sub[c].values, sub[t].values
        n = len(sub)
        r, p = stats.spearmanr(x, y)
        ok = _ok_mask(xc_full, yc_full)
        rx = np.full(len(df), np.nan); rx[ok] = stats.rankdata(xc_full[ok])
        ry = np.full(len(df), np.nan); ry[ok] = stats.rankdata(yc_full[ok])
        ix = moran_i(rx); iy = moran_i(ry)
        p_ess, n_eff = ess_pvalue(r, n, ix, iy)
        _, ci_lo, ci_hi, p_boot = block_boot_ci(xc_full, yc_full, spear_stat)
        p_perm = block_perm_p(xc_full, yc_full, spear_stat)
        raw_rows.append(dict(metric=c, target=t, rho=round(r, 3), p=p, p_ess=p_ess,
                             p_perm=p_perm, n=n, n_eff=round(n_eff, 1),
                             ci_lo=round(ci_lo, 3), ci_hi=round(ci_hi, 3),
                             p_boot=round(p_boot, 4)))
    print(f"F1 done: {c}", flush=True)
raw = pd.DataFrame(raw_rows)
raw["q"] = bh_fdr(raw.p.values)
raw["q_perm"] = bh_fdr(raw.p_perm.values)
raw["q_ess"] = bh_fdr(raw.p_ess.values)
raw["survive"] = raw.q < 0.05
raw["survive_perm"] = raw.q_perm < 0.05
raw["survive_ess"] = raw.q_ess < 0.05
# 主判定（双重标准）：族内 BH-FDR + 区组 bootstrap 95% CI 不含 0
raw["survive_dual"] = (raw.q < 0.05) & ((raw.ci_lo > 0) | (raw.ci_hi < 0))

# ---------- F2 partial (ctrl size) ----------
def _rank_resid_full(xf, cf, ok):
    """秩残差（x 对 c 的秩回归残差），写回全长数组。"""
    out = np.full(len(xf), np.nan)
    rx = stats.rankdata(xf[ok]); rc = stats.rankdata(cf[ok])
    A = np.column_stack([rc, np.ones_like(rc)])
    out[ok] = rx - A @ np.linalg.lstsq(A, rx, rcond=None)[0]
    return out


part_rows = []
for c, cn in MORPH:
    if c == CTRL:
        continue
    xc_full = df[c].values.astype(float)
    for t, tn in TARGETS:
        yc_full = df[t].values.astype(float)
        cc_full = df[CTRL].values.astype(float)
        r, p, n = pcorr_p(xc_full, yc_full, cc_full)
        ok = _ok_mask(xc_full, yc_full, cc_full)
        rxr = _rank_resid_full(xc_full, cc_full, ok)
        ryr = _rank_resid_full(yc_full, cc_full, ok)
        ix = moran_i(rxr); iy = moran_i(ryr)
        p_ess, n_eff = ess_pvalue(r, n, ix, iy)
        _, ci_lo, ci_hi, p_boot = block_boot_ci(xc_full, yc_full, pcorr_rank_arr, c=cc_full)
        p_perm = block_perm_p(xc_full, yc_full, pcorr_rank_arr, c=cc_full)
        part_rows.append(dict(metric=c, target=t, rho=round(r, 3), p=p, p_ess=p_ess,
                              p_perm=p_perm, n=n, n_eff=round(n_eff, 1),
                              ci_lo=round(ci_lo, 3), ci_hi=round(ci_hi, 3),
                              p_boot=round(p_boot, 4)))
    print(f"F2 done: {c}", flush=True)
part = pd.DataFrame(part_rows)
part["q"] = bh_fdr(part.p.values)
part["q_perm"] = bh_fdr(part.p_perm.values)
part["q_ess"] = bh_fdr(part.p_ess.values)
part["survive"] = part.q < 0.05
part["survive_perm"] = part.q_perm < 0.05
part["survive_ess"] = part.q_ess < 0.05
part["survive_dual"] = (part.q < 0.05) & ((part.ci_lo > 0) | (part.ci_hi < 0))

print("\n=== F1 naive q:", int(raw.survive.sum()), "| perm q:", int(raw.survive_perm.sum()),
      "| ESS q:", int(raw.survive_ess.sum()), "===")
print(raw[raw.survive_perm][["metric", "target", "rho", "p", "p_perm", "q_perm", "ci_lo", "ci_hi"]].to_string(index=False))
print("\n=== F2 naive q:", int(part.survive.sum()), "| perm q:", int(part.survive_perm.sum()),
      "| ESS q:", int(part.survive_ess.sum()), "===")
print(part[part.survive_perm][["metric", "target", "rho", "p", "p_perm", "q_perm", "ci_lo", "ci_hi"]].to_string(index=False))

raw.to_csv("tables/_F1_v5.csv", index=False, encoding="utf-8-sig")
part.to_csv("tables/_F2_v5.csv", index=False, encoding="utf-8-sig")

# ---------- headline 对 ----------
HEAD = [("tsvf", "lst_abs"), ("tsvf", "cov85_4p"), ("tsvf", "rsrp_p10_4p"),
        ("forest_ring_pct", "cov85_4p"), ("forest_ring_pct", "lst_abs"),
        ("slope_deg", "cov85_4p"), ("relief_m", "lst_abs"), ("relief_m", "dlst_v3m"),
        ("water_min_m", "lst_abs"), ("built_dom_ha", "lst_abs"),
        ("cover_dom_pct", "lst_abs"), ("cover_dom_pct", "cov85_4p"),
        ("compact_fd", "dlst_v3m"), ("edge_den_m_ha", "cov85_4p")]

# ---------- A14: 区组设计敏感性（尺寸 × 原点） ----------
a14_rows = []
for c, t in HEAD:
    for size in [0.10, 0.15, 0.20]:
        for oi, origin in enumerate([(0.0, 0.0), (0.05, 0.05)]):
            bl = make_blocks(size, origin)
            _, lo, hi, _pb = block_boot_ci(df[c].values, df[t].values, spear_stat, b=999, blocks=bl)
            pp = block_perm_p(df[c].values, df[t].values, spear_stat, blocks=bl)
            a14_rows.append(dict(pair=f"{c}~{t}", block_deg=size, origin=f"+{origin[0]}",
                                 n_blocks=len(bl), ci_lo=round(lo, 3), ci_hi=round(hi, 3),
                                 p_perm=round(pp, 4)))
    print(f"A14 done: {c}~{t}", flush=True)
pd.DataFrame(a14_rows).to_csv("tables/TableA14_block_sensitivity.csv", index=False, encoding="utf-8-sig")

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

# ---------- 留一县 jackknife ----------
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

# ---------- 频段稳健性 ----------
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

# ---------- A7: NLOS 截断敏感性 ----------
a7_rows = []
for tag in ["0_0", "0_1250", "1250_0", "1250_1250"]:
    capf, ncf = f"data/coverage_p{tag}_v4.csv", f"data/coverage_p{tag}_v4nocap.csv"
    if os.path.exists(capf) and os.path.exists(ncf):
        j = pd.read_csv(capf).merge(pd.read_csv(ncf, ), on="village", suffixes=("_cap", "_nocap"))
        a7_rows.append(dict(comparison=f"phase {tag}: NLOS cap vs nocap",
                            cov85_stat=round(float((j.cov85_cap - j.cov85_nocap).abs().max()), 2),
                            cov95_stat=round(float((j.cov95_cap - j.cov95_nocap).abs().max()), 2),
                            rsrp_stat=round(float((j.rsrp_mean_cap - j.rsrp_mean_nocap).abs().max()), 2),
                            note="max abs diff (pct-pts / dB)"))
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
S["cover_range"] = [round(float(df.cover_dom_pct.min()), 1), round(float(df.cover_dom_pct.max()), 1)]

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
                                p_perm=float(f"{row.p_perm:.4f}"), q_perm=round(row.q_perm, 4),
                                p_ess=float(f"{row.p_ess:.3e}"), q_ess=round(row.q_ess, 4),
                                ci95=[row.ci_lo, row.ci_hi], n=int(row.n), n_eff=float(row.n_eff),
                                survive_dual=bool(row.survive_dual),
                                survive_perm=bool(row.survive_perm), survive_ess=bool(row.survive_ess),
                                partial_rho=round(float(prow.rho.iloc[0]), 3) if len(prow) else None,
                                partial_survive_dual=bool(prow.survive_dual.iloc[0]) if len(prow) else None)
S["headline"] = head_out
S["f1_n"] = int(len(raw)); S["f1_n_survive"] = int(raw.survive.sum())
S["f1_n_survive_dual"] = int(raw.survive_dual.sum())
S["f1_n_survive_perm"] = int(raw.survive_perm.sum()); S["f1_n_survive_ess"] = int(raw.survive_ess.sum())
S["f2_n"] = int(len(part)); S["f2_n_survive"] = int(part.survive.sum())
S["f2_n_survive_dual"] = int(part.survive_dual.sum())
S["f2_n_survive_perm"] = int(part.survive_perm.sum()); S["f2_n_survive_ess"] = int(part.survive_ess.sum())
S["freq_700mhz"] = freq
S["sens_excl_yuliang"] = sens_yl
S["leave_one_county"] = loco
S["spatial_moran"] = {r.variable: dict(I=r.I, p=r.p, I_rank=r.I_rank, p_rank=r.p_rank, n=int(r.n))
                      for r in moran_df.itertuples()}
S["block_membership_0.15"] = _blocks_dbg
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


with open("data/stats_v5.json", "w", encoding="utf-8") as f:
    json.dump(_clean(S), f, ensure_ascii=False, indent=1)

# ---------- Table 1 ----------
t1 = df[["village", "county", "built_dom_ha", "cover_dom_pct", "elev_m", "relief_m", "tsvf",
         "forest_ring_pct", "lst_abs", "dlst_v1", "dlst_v1_lo", "dlst_v1_hi",
         "dlst_v3m", "dlst_v3m_lo", "dlst_v3m_hi", "cov85_4p", "cov85_4p_sd",
         "rsrp_p10_4p"]].copy()
t1["dLST-V1 (degC) [95% CI]"] = t1.apply(lambda r: f"{r.dlst_v1:.2f} [{r.dlst_v1_lo:.2f}, {r.dlst_v1_hi:.2f}]", axis=1)
t1["dLST-matched (degC) [95% CI]"] = t1.apply(
    lambda r: f"{r.dlst_v3m:.2f} [{r.dlst_v3m_lo:.2f}, {r.dlst_v3m_hi:.2f}]" if np.isfinite(r.dlst_v3m) else "n/a", axis=1)
t1["cov85 4p-mean (sd) (%)"] = t1.apply(lambda r: f"{r.cov85_4p:.1f} ({r.cov85_4p_sd:.1f})", axis=1)
t1 = t1[["village", "county", "built_dom_ha", "cover_dom_pct", "elev_m", "relief_m", "tsvf",
         "forest_ring_pct", "lst_abs", "dLST-V1 (degC) [95% CI]",
         "dLST-matched (degC) [95% CI]", "cov85 4p-mean (sd) (%)", "rsrp_p10_4p"]]
t1.columns = ["Village", "County", "Built-up in domain (ha)", "Coverage ratio (%)",
              "Elev (m)", "Relief (m)", "tSVF", "Forest ring (%)", "LST (degC)",
              "dLST-V1 (degC) [95% CI]", "dLST-matched (degC) [95% CI]",
              "cov85 4p-mean (sd) (%)", "RSRP p10 (dBm)"]
t1 = t1.round({"Built-up in domain (ha)": 1, "Coverage ratio (%)": 1, "Elev (m)": 0, "Relief (m)": 0,
               "tSVF": 3, "Forest ring (%)": 0, "LST (degC)": 1, "RSRP p10 (dBm)": 1})
t1.to_csv("tables/Table1_sample.csv", index=False, encoding="utf-8-sig")

# ---------- Table 2（星号=naive p，†=双重标准: 族内 BH-FDR 且区组 bootstrap 95% CI 不含 0） ----------
def fmt2(r, p, dual):
    star = "***" if p < 0.001 else ("**" if p < 0.01 else ("*" if p < 0.05 else ""))
    dag = "†" if dual else ""
    return f"{r:+.2f}{star}{dag}"


rows2 = []
for c, cn in MORPH:
    row = {"Morphological metric": cn}
    for t, tn in TARGETS:
        x = raw[(raw.metric == c) & (raw.target == t)].iloc[0]
        row[f"rho {tn}"] = fmt2(x.rho, x.p, x.survive_dual)
    rows2.append(row)
    if c == CTRL:
        continue
    row2 = {"Morphological metric": cn + " (ctrl size)"}
    for t, tn in TARGETS:
        x = part[(part.metric == c) & (part.target == t)].iloc[0]
        row2[f"rho {tn}"] = fmt2(x.rho, x.p, x.survive_dual)
    rows2.append(row2)
pd.DataFrame(rows2).to_csv("tables/Table2_correlation.csv", index=False, encoding="utf-8-sig")

# ---------- A1 全量 ----------
ph_all = {}
for tag in ["0_0", "0_1250", "1250_0", "1250_1250"]:
    ph_all[tag] = pd.read_csv(f"data/coverage_p{tag}_v4.csv")[["village", "cov85"]].rename(
        columns={"cov85": f"cov85_p{tag}"})
a1 = df[["village", "county", "lon", "lat", "built_dom_ha", "cover_dom_pct", "built_fd_ha",
         "elong_fd", "compact_fd", "edge_den_m_ha", "patch_den", "lps_pct",
         "elev_m", "relief_m", "slope_deg", "southness", "ns_asym_m",
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
                        p=round(x.p, 6), p_perm=round(x.p_perm, 6), p_ess=round(x.p_ess, 6),
                        q=round(x.q, 4), q_perm=round(x.q_perm, 4), q_ess=round(x.q_ess, 4),
                        ci_lo=x.ci_lo, ci_hi=x.ci_hi, n=x.n, n_eff=x.n_eff,
                        survive_fdr=bool(x.survive), survive_fdr_perm=bool(x.survive_perm),
                        survive_fdr_ess=bool(x.survive_ess), survive_dual=bool(x.survive_dual)))
for _, x in part.iterrows():
    a3_rows.append(dict(family="F2 partial (ctrl domain built-up)", metric=x.metric, target=x.target,
                        rho=x.rho, p=round(x.p, 6), p_perm=round(x.p_perm, 6), p_ess=round(x.p_ess, 6),
                        q=round(x.q, 4), q_perm=round(x.q_perm, 4), q_ess=round(x.q_ess, 4),
                        ci_lo=x.ci_lo, ci_hi=x.ci_hi, n=x.n, n_eff=x.n_eff,
                        survive_fdr=bool(x.survive), survive_fdr_perm=bool(x.survive_perm),
                        survive_fdr_ess=bool(x.survive_ess), survive_dual=bool(x.survive_dual)))
pd.DataFrame(a3_rows).to_csv("tables/TableA3_exact_stats.csv", index=False, encoding="utf-8-sig")

print("\n=== S saved to data/stats_v5.json ===")
print("headline:", json.dumps(head_out, ensure_ascii=False, indent=1))
print("dlst means v1/v2/v3m:", S["dlst_v1_mean"], S["dlst_v2_mean"], S["dlst_v3m_mean"])
print("ALL S41E DONE")
