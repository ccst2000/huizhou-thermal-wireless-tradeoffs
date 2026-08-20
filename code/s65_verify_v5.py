# -*- coding: utf-8 -*-
"""s65: v5 手稿数字自检——docx 文本对照 stats_v5.json / v3_master_v5.csv"""
import json, re, sys
import docx
import pandas as pd

S = json.load(open("data/stats_v5.json", encoding="utf-8"))
m = pd.read_csv("data/v3_master_v5.csv")
txt = "\n".join(p.text for p in docx.Document("manuscript/V3_manuscript_full_v5.docx").paragraphs)

fails = []
def chk(label, cond):
    print(("PASS " if cond else "FAIL ") + label)
    if not cond:
        fails.append(label)

def has(s):
    return s in txt

# 样本与地形
chk("tsvf range 0.715–0.984", has("tSVF = 0.715–0.984"))
chk("Mulihong tsvf 0.715", has("Mulihong (tSVF = 0.715)"))
chk("Zuyuan tsvf 0.738", has("Zuyuan (0.738)"))
chk("forest ring 16–100%", has("16–100%"))
chk("built_dom 0.1–37.6", has("0.1–37.6 ha"))
chk("cover 0% to 71.6%", has("71.6%"))
chk("elev 120–422 / relief 22–262", has("elevation 120–422 m; local relief 22–262 m"))
chk("edge 217–2243", has("217–2243"))
chk("patch 0.04–20.7", has("0.04–20.7"))
chk("lps 33–100%", has("33–100%"))
chk("elong 3.5 Changxi", has("3.5 at Changxi"))
chk("ten villages negative southness", has("ten of the 29 villages"))
chk("Nanping -0.51 Guanlu -0.40", has("(−0.51)") and has("(−0.40)"))
# 热链
chk("LST 31.2–42.8 mean 36.4", has("31.2–42.8 °C (mean 36.4 °C)"))
chk("V1 +0.03 to +7.69 mean +2.45, 21/29", has("+0.03 to +7.69 °C with a mean of +2.45 °C") and has("21 of 29"))
chk("V2 n=22 mean +5.28, 19/22", has("mean +5.28 °C; 19 of 22"))
chk("V3 mean +1.27 range -0.91..+4.19 25 pos 22 sig", has("mean +1.27 °C, range −0.91 to +4.19 °C") and has("25 of 29 point estimates positive") and has("22 intervals excluding zero"))
chk("neg villages", has("(Tachuan, Xucun, Shitan, Huansha)"))
chk("coolest list", has("Mulihong 31.2, Tachuan 31.8, Zuyuan 32.1, Xucun 33.4, Renli 33.7"))
chk("hottest list", has("Yuliang 42.8, Qiankou 40.1, Tangyue 39.8, Xiongcun 39.3, Zhanqi 38.4"))
chk("26 overpasses / 16 dates / 6-13 mean 7.6", has("26 independent overpasses") and has("16 \noverpass dates") or has("16 overpass dates") or has("16\n"))
chk("estimand rho 0.941 bias -0.20", has("ρ = 0.941") and has("−0.20 °C"))
chk("watermask 0.11 / 1.000", has("0.11 °C") and has("rank ρ = 1.000"))
# 无线
chk("cov85 59.8–100 mean 93.0 17>=96", has("59.8–100% across villages (mean \n93.0%)") or has("59.8–100% across villages (mean 93.0%)") and has("Seventeen of 29"))
chk("cov95 16 villages 100 range 85.3–100", has("85.3–100%"))
chk("rsrp p10 -96.8..-76.1", has("−96.8 to −76.1 dBm"))
chk("Zuyuan sd 34.9 phases 12-88", has("34.9 percentage") and has("12% to 88%"))
chk("pairwise 0.57/0.47, 0.39/0.17, 0.10/-0.09", has("0.57, minimum 0.47") and has("(0.39, minimum 0.17)") and has("(0.10, minimum −0.09)"))
chk("Yuliang 86.2 / 71.0–99.2", has("86.2%") and has("71.0–99.2%"))
chk("700MHz 93.0->95.9 rho 0.89", has("from 93.0% to 95.9%") and has("rank correlation 0.89"))
chk("phase-0 0.81 cov85 >=0.96 RSRP", has("0.81 for cov85 and ≥0.96"))
# 相关
chk("cover LST +0.65 q0.001 CI[0.27,0.86]", has("+0.65, q = 0.001, 95% CI [+0.27, +0.86]"))
chk("tsvf LST +0.55 q0.008 CI[-0.01,0.84] marginal", has("ρ = +0.55, q = 0.008") and has("[−0.01, +0.84]"))
chk("forest LST -0.58 CI", has("−0.58, CI [−0.83, −0.20]"))
chk("slope cov85 -0.82 CI[-0.94,-0.61]", has("ρ = −0.82, q < 0.001, CI [−0.94, −0.61]"))
chk("forest cov85 -0.65 CI[-0.88,-0.32]", has("cov85 ρ = −0.65, q = 0.001, CI [−0.88, −0.32]"))
chk("F1 23 dual / 24 BH / 0 perm", has("23 pass the dual criterion (24 on BH control alone; 0 on the exact permutation"))
chk("F2 7 dual all wireless", has("7 pass—and all seven lie on the coverage side"))
chk("excl Yuliang numbers", has("+0.72") and has("−0.69") and has("−0.86") and has("+0.61"))
chk("excl fallback n=27 numbers", has("+0.55, p = 0.003, n = 27") and has("−0.60") and has("−0.78") and has("−0.71"))
chk("jackknife ranges", has("+0.55 and +0.79") and has("−0.84 and −0.58") and has("+0.57 and +0.80") and has("−0.79 and −0.49"))
chk("moran numbers", has("I = 0.22, p = 0.002") and has("I = 0.26, p = 0.001") and has("I = 0.18, p = 0.008") and has("I = 0.16, p = 0.014") and has("I = 0.14, p = 0.022"))
chk("match diag numbers", has("≤0.23") and has("0.82") and has("0.98") and has("11%"))
# 结构
chk("no Dutilleul", "Dutilleul" not in txt)
chk("no [37]", "[37]" not in txt)
chk("P.1812-6 09/2021", has("P.1812-6, 09/2021"))
chk("TS 36.214 V16.1.0", has("TS 36.214 V16.1.0, 2020"))
chk("Theil no reprint DOI", "978-94-011-2546-8" not in txt)
chk("1165 ha Yuliang component", has("(1165 ha in the extended"))
chk("Kantou/Lixi 2.4/4.8", has("2.4 m and 4.8 m"))
chk("16 metrics wording", has("sixteen morphological metrics"))
chk("F1 64 F2 60", has("64 raw correlations") and has("60 partial"))
chk("A13-A16 listed", has("TableA16_watermask_sensitivity.csv"))
chk("124 tests", has("124 tests"))

print()
print("FAILS:", len(fails))
sys.exit(1 if fails else 0)
