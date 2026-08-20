# -*- coding: utf-8 -*-
"""s65b: v6 手稿数字自检——docx 文本对照 stats_v6.json / v3_master_v6.csv
尽量从数据计算期望值，再断言手稿文本包含该字符串。"""
import json, sys
import docx
import pandas as pd

S = json.load(open("data/stats_v6.json", encoding="utf-8"))
m = pd.read_csv("data/v3_master_v6.csv")
txt = "\n".join(p.text for p in docx.Document("manuscript/V3_manuscript_full_v6.docx").paragraphs)

fails = []
def chk(label, cond):
    print(("PASS " if cond else "FAIL ") + label)
    if not cond:
        fails.append(label)

def has(s):
    return s in txt

def sg(x, d=2):
    """手稿的有符号两位小数格式（unicode minus）"""
    s = f"{x:+.{d}f}".replace("-", "−")
    return s

# ---------- 描述性范围（从 master 表计算） ----------
tsvf_rng = f"{m.tsvf.min():.3f}–{m.tsvf.max():.3f}"
chk(f"tSVF range {tsvf_rng}", has(tsvf_rng))
chk("Zuyuan 0.735", has(f"Zuyuan (tSVF = {S['zuyuan_tsvf']:.3f})"))
fr = f"{m.forest_ring_pct.min():.0f}–{m.forest_ring_pct.max():.0f}%"
chk(f"forest ring {fr} of 500–800-m annulus", has(f"{fr} of the 500–800-m annulus"))
bd = f"{m.built_dom_ha.min():.0f}–{m.built_dom_ha.max():.1f}"
chk(f"built_dom {bd} ha", has(f"{bd} ha"))
chk("cover max 71.6%", has(f"{m.cover_dom_pct.max():.1f}%"))
chk("relief 22–320 m", has(f"from {m.relief_m.min():.0f} m") and has(f"{m.relief_m.max():.0f} m"))
ed = f"{m.edge_den_m_ha.min():.1f}–{m.edge_den_m_ha.max():.0f}"
chk(f"edge_den {ed}", has(ed))
pd_rng = f"{m.patch_den.min():.2f}–{m.patch_den.max():.2f}"
chk(f"patch_den {pd_rng}", has(pd_rng))
chk("lps 33–100%", has(f"{m.lps_pct.min():.0f}–{m.lps_pct.max():.0f}%"))
n_neg_south = int((m.southness < 0).sum())
chk(f"southness negative n={n_neg_south} -> 'nine of the 29'", n_neg_south == 9 and has("nine of the 29"))
chk("Nanping/Guanlu −0.51/−0.40", has("(−0.51)") and has("(−0.40)"))
chk("elong 3.5 at Changxi", has("elongation up to 3.5 at Changxi"))

# ---------- 热链（JSON 驱动） ----------
chk("LST range+mean", has(f"{S['lst_range'][0]:.1f}–{S['lst_range'][1]:.1f} °C (mean 36.4 °C)"))
chk("V1 stats", has(f"+{S['dlst_v1_range'][0]:.2f} to +{S['dlst_v1_range'][1]:.2f} °C with a mean of +{S['dlst_v1_mean']:.2f} °C")
    and has(f"{S['dlst_v1_n_sig']} of 29"))
chk("V2 stats", has(f"mean +{S['dlst_v2_mean']:.2f} °C; {S['dlst_v2_n_sig']} of {S['dlst_v2_n']}"))
chk("V3 stats", has(f"mean +{S['dlst_v3m_mean']:.2f} °C, range −0.91 to +4.19 °C")
    and has(f"{S['dlst_v3m_n_pos']} of 29 point estimates positive")
    and has(f"{S['dlst_v3m_n_sig']} intervals excluding zero"))
chk("V3 neg villages", has("(Tachuan, Xucun, Shitan, Huansha)"))
chk("coolest5", has("Mulihong 31.2, Tachuan 31.8, Zuyuan 32.1, Xucun 33.4, Renli 33.7"))
chk("hottest5", has("Yuliang 42.8, Qiankou 40.1, Tangyue 39.8, Xiongcun 39.3, Zhanqi 38.4"))
chk("estimand rho/bias", has("ρ = 0.941") and has("−0.20 °C"))
chk("watermask sens", has("0.11 °C") and has("rank ρ = 1.000"))
chk("A17 vintage/DOY", has("ρ ≥ 0.98"))

# ---------- 无线链 ----------
chk("cov85 range/mean", has("59.8–100%") and has("93.0%"))
chk("cov95 range", has("85.3–100%"))
chk("rsrp p10 range", has("−96.8 to −76.1 dBm"))
chk("Zuyuan phase dispersion", has("34.9 percentage") and has("12% to 88%"))
chk("phase pairwise", has("mean pairwise rank correlation 0.57, minimum 0.47"))
chk("Yuliang 4-phase", has(f"{S['yuliang_cov85_4p']:.1f}%") and has("71.0–99.2%"))
chk("700MHz uplift", has("from 93.0% to 95.9%") and has("rank correlation 0.89"))

# ---------- 相关族（JSON 驱动四舍五入核对） ----------
hl = S["headline"]
def ci_str(pair):
    return f"[{sg(pair[0])}, {sg(pair[1])}]"
chk("cover~LST headline", has("+0.65, q = 0.001, 95% CI [+0.27, +0.86]"))
chk("tsvf~LST borderline CI", has(ci_str(hl["tsvf~lst_abs"]["ci95"])))
chk("forest~LST −0.68", has("−0.68"))
chk("slope~cov85 " + sg(hl["slope_deg~cov85_4p"]["rho"]), has(sg(-0.847)))
chk("forest~cov85 −0.74", has(sg(-0.739)))
chk("tsvf~cov85 +0.57", has(sg(0.573)))
chk("F1 64/24/23", has("64 raw tests") and has("24 pass the dual criterion")
    and has("23 on the non-spatial permutation baseline"))
chk("F2 60/7 relief", has("60 size-controlled partial tests") and has("7 pass—six on the coverage side")
    and has("plus relief against LST"))
chk("A14b 58/19/7", has("58 intervals exclude zero under all 20 seeds, 19 include zero under all 20 seeds, and 7 are seed-sensitive"))
chk("124 tests / sixteen metrics", has("124 tests") and has("sixteen morphological metrics"))

# ---------- Moran ----------
chk("Moran I values", has("I = 0.22, p = 0.002") and has("I = 0.26, p = 0.001")
    and has("I = 0.18, p = 0.008") and has("I = 0.17, p = 0.004"))

# ---------- 敏感性 ----------
chk("excl Yuliang", has("+0.64") and has("−0.83") and has("−0.86") and has("+0.61"))
chk("excl fallback n=27", has("n = 27") and has("−0.68") and has("−0.81") and has("−0.71"))
chk("jackknife ranges", has("+0.51 and +0.63") and has("−0.89") and has("+0.57 and +0.80") and has("−0.84 and −0.60"))

# ---------- 结构与文献 ----------
chk("P.1812-8 09/2025 6000MHz", has("P.1812-8") and has("09/2025") and has("6 000 MHz"))
chk("TS 36.214 V16.1.0", has("TS 36.214 V16.1.0, 2020"))
chk("supplementary v6 files", has("TableA14b_mc_stability.csv") and has("TableA17_year_doy_sensitivity.csv")
    and has("village_geometry_v6.csv") and has("block_membership_0p15.csv")
    and has("worldcover_year_compare_v6.csv") and has("dlst_doy_adjust_v6.csv"))
chk("base-station snap heuristic kept", has("each site snapped to the highest surface-model cell"))
chk("A13 comparison table described", has("component-based morphology table retained for comparison"))

# ---------- 负向检查（旧术语/已删除表述） ----------
chk("no Frame O", "Frame O" not in txt)
chk("no cyclic", "cyclic" not in txt)
chk("no 300-m ring", "300-m" not in txt)
chk("no Dutilleul", "Dutilleul" not in txt)
chk("no 'To isolate morphology'", "To isolate morphology" not in txt)
chk("no exact shift-permutation claim", "shift-permutation" not in txt and "shift permutation" not in txt)

print()
print("FAILS:", len(fails))
sys.exit(1 if fails else 0)
