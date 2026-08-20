# -*- coding: utf-8 -*-
"""V3 s50 (Round-2 revision): 审稿人 M1/M4/M6/M8/M9 响应计算
输出:
  data/dlst_scene_matrix.csv      村 x 景 逐景 anomaly 矩阵 (M4 scene-matched)
  data/lst_village_v3.csv         村级 v3 指标: scene-matched dlst + bootstrap CI/P(>0) (M6)
  data/coverage_700mhz_4phase.csv 700MHz 四相位全表 (M8)
  data/sens_nlos5k.csv            NLOS>5km 截断敏感性对比 (M1)
  data/village_scene_composition.csv 每村场景构成 (M4)
用法: python s50_round2.py
"""
import json
import os
import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import reproject, Resampling
from scipy import stats

RNG = np.random.default_rng(7)
B = 10000

with rasterio.open("data/lst_summer_mean.tif") as s:
    H, W = s.height, s.width
    dst_tr = s.transform
    bounds = s.bounds
res = 100.0
left, top = bounds.left, bounds.top

# ---------- 村域 core/ring 掩膜（与 s40 相同定义）----------
built = rasterio.open("data/built_utm30.tif").read(1)
built100 = np.zeros((H, W), dtype="uint8")
with rasterio.open("data/built_utm30.tif") as s:
    reproject(s.read(1), built100, src_transform=s.transform, src_crs=s.crs,
              dst_transform=dst_tr, dst_crs="EPSG:32650", resampling=Resampling.nearest)

m = pd.read_csv("data/v3_master.csv")
from pyproj import Transformer
tf = Transformer.from_crs(4326, 32650, always_xy=True)

masks = {}
for _, v in m.iterrows():
    cx, cy = tf.transform(v.lon, v.lat)
    cols = np.arange(max(0, int((cx - 2000 - left) / res)), min(W, int((cx + 2000 - left) / res) + 1))
    rws = np.arange(max(0, int((top - cy - 2000) / res)), min(H, int((top - cy + 2000) / res) + 1))
    RR, CC = np.meshgrid(rws, cols, indexing="ij")
    X = left + (CC + 0.5) * res
    Y = top - (RR + 0.5) * res
    d2 = (X - cx) ** 2 + (Y - cy) ** 2
    core = d2 <= 500 ** 2
    ring = (d2 > 1000 ** 2) & (d2 <= 2000 ** 2) & (built100[RR, CC] == 0)
    masks[v.village] = (RR[core], CC[core], RR[ring], CC[ring])

# ---------- 逐景 anomaly 矩阵 (M4) ----------
man = pd.read_csv("data/lst_scene_manifest.csv")
man["platform"] = man["id"].str[:4].map({"LC08": "L8", "LC09": "L9"})
man["year"] = man["date"].str[:4].astype(int)
man["month"] = man["date"].str[5:7].astype(int)

scene_ids = [sid for sid in man["id"] if os.path.exists(f"data/lst_v2_scenes/{sid}.npy")]
print(f"valid scenes on disk: {len(scene_ids)} / {len(man)}")

mat = pd.DataFrame(np.nan, index=m.village, columns=scene_ids)
for sid in scene_ids:
    arr = np.load(f"data/lst_v2_scenes/{sid}.npy")
    for vname, (rc_, cc_, rr_, cr_) in masks.items():
        zc = arr[rc_, cc_]
        zb = arr[rr_, cr_]
        zc = zc[np.isfinite(zc)]
        zb = zb[np.isfinite(zb)]
        if len(zc) >= 5 and len(zb) >= 5:   # 至少 5 个有效像元（≈5% 域）才计入该景
            mat.loc[vname, sid] = zc.mean() - zb.mean()
mat.index.name = "village"
mat.round(3).to_csv("data/dlst_scene_matrix.csv")

# ---------- 村级 v3: scene-matched 均值 + bootstrap (M6) ----------
rows = []
for vname in m.village:
    x = mat.loc[vname].dropna().to_numpy()
    n = len(x)
    if n >= 3:
        boots = RNG.choice(x, size=(B, n), replace=True).mean(axis=1)
        lo, hi = np.percentile(boots, [2.5, 97.5])
        p_pos = float((boots > 0).mean())
        rows.append(dict(village=vname, dlst_v3=round(float(x.mean()), 2),
                         dlst_sd=round(float(x.std(ddof=1)), 2), n_scenes=n,
                         ci_lo=round(float(lo), 2), ci_hi=round(float(hi), 2),
                         p_pos=round(p_pos, 4),
                         sig_pos=bool(lo > 0)))
    else:
        rows.append(dict(village=vname, dlst_v3=np.nan, dlst_sd=np.nan, n_scenes=n,
                         ci_lo=np.nan, ci_hi=np.nan, p_pos=np.nan, sig_pos=False))
lv3 = pd.DataFrame(rows)
old = pd.read_csv("data/lst_village_v2.csv")
cmp_ = lv3.merge(old[["village", "dlst_v2", "lst_v2", "lst_bg2"]], on="village")
lv3 = lv3.merge(old[["village", "lst_v2", "lst_bg2", "obs_min", "obs_med"]], on="village")
lv3.to_csv("data/lst_village_v3.csv", index=False)
print("\n=== scene-matched dlst_v3 vs composite dlst_v2 ===")
print(cmp_[["village", "dlst_v2", "dlst_v3", "n_scenes", "ci_lo", "ci_hi", "p_pos"]].to_string(index=False))
print("rank corr dlst_v2 vs dlst_v3:",
      round(stats.spearmanr(cmp_.dlst_v2, cmp_.dlst_v3).statistic, 3))
print("villages with CI_lo>0:", int(lv3.sig_pos.sum()), "/", int((lv3.n_scenes >= 3).sum()))
print("mean dlst_v3:", round(float(lv3.dlst_v3.mean()), 2),
      "| min:", round(float(lv3.dlst_v3.min()), 2), "| max:", round(float(lv3.dlst_v3.max()), 2))

# ---------- 每村场景构成 (M4) ----------
comp_rows = []
for vname in m.village:
    used = man[man.id.isin(mat.columns[mat.loc[vname].notna()])]
    comp_rows.append(dict(village=vname, n_scenes=len(used),
                          n_l8=int((used.platform == "L8").sum()),
                          n_l9=int((used.platform == "L9").sum()),
                          year_min=int(used.year.min()) if len(used) else -1,
                          year_max=int(used.year.max()) if len(used) else -1,
                          frames=";".join(sorted({f"{p}/{r}" for p, r in zip(used.path, used.row)}))))
pd.DataFrame(comp_rows).to_csv("data/village_scene_composition.csv", index=False)
print("\nscene composition written:", len(comp_rows), "villages")

# ---------- C1: NLOS>5km 截断敏感性 (M1) ----------
base = pd.read_csv("data/coverage_p0_0.csv")
cap = pd.read_csv("data/coverage_p0_0_nlos5k.csv")
cc = base.merge(cap, on="village", suffixes=("_base", "_cap"))
for col in ["cov85", "cov95", "rsrp_mean", "rsrp_p10"]:
    cc[f"d_{col}"] = (cc[f"{col}_cap"] - cc[f"{col}_base"]).round(2)
sens = cc[["village", "cov85_base", "cov85_cap", "d_cov85", "cov95_base", "cov95_cap",
           "d_cov95", "rsrp_mean_base", "rsrp_mean_cap", "d_rsrp_mean"]]
sens.to_csv("data/sens_nlos5k.csv", index=False)
print("\n=== NLOS 5km cap sensitivity ===")
print("cov85 mean: %.1f -> %.1f (delta %.1f pp)" % (cc.cov85_base.mean(), cc.cov85_cap.mean(), cc.d_cov85.mean()))
print("cov95 mean: %.1f -> %.1f" % (cc.cov95_base.mean(), cc.cov95_cap.mean()))
print("rank corr cov85:", round(stats.spearmanr(cc.cov85_base, cc.cov85_cap).statistic, 3),
      "| cov95:", round(stats.spearmanr(cc.cov95_base, cc.cov95_cap).statistic, 3),
      "| rsrp_mean:", round(stats.spearmanr(cc.rsrp_mean_base, cc.rsrp_mean_cap).statistic, 3))
print("villages with cov85 change >= 5pp:", int((cc.d_cov85.abs() >= 5).sum()),
      "->", cc.loc[cc.d_cov85.abs() >= 5, "village"].tolist())
# 关键相关在截断版下是否保持 (tsvf/forest/slope ~ cov85_cap)
master = pd.read_csv("data/v3_master.csv")
jj = master.merge(cap[["village", "cov85"]].rename(columns={"cov85": "cov85_cap"}), on="village")
for x, lbl in [("tsvf", "tsvf"), ("forest_ring_pct", "forest"), ("slope_deg", "slope")]:
    r0 = stats.spearmanr(master[x], master.cov85_4p)
    r1 = stats.spearmanr(jj[x], jj.cov85_cap)
    print(f"  {lbl}~cov85: base rho={r0.statistic:.3f} -> cap rho={r1.statistic:.3f}")

# ---------- C3: 700MHz 四相位全表 (M8) ----------
ph = {}
for tag in ["p0_0_f0.7", "p0_1250_f0.7", "p1250_0_f0.7", "p1250_1250_f0.7"]:
    ph[tag] = pd.read_csv(f"data/coverage_{tag}.csv").set_index("village")
t7 = pd.DataFrame({tag: ph[tag].cov85 for tag in ph})
t7.columns = ["cov85_p0_0", "cov85_p0_1250", "cov85_p1250_0", "cov85_p1250_1250"]
t7["cov85_mean"] = t7.mean(axis=1).round(2)
t7["cov85_sd"] = t7[["cov85_p0_0", "cov85_p0_1250", "cov85_p1250_0", "cov85_p1250_1250"]].std(axis=1, ddof=1).round(2)
t7p10 = pd.DataFrame({tag: ph[tag].rsrp_p10 for tag in ph})
t7p10.columns = ["p10_p0_0", "p10_p0_1250", "p10_p1250_0", "p10_p1250_1250"]
t7 = t7.join(t7p10.round(2)).reset_index()
t7.to_csv("data/coverage_700mhz_4phase.csv", index=False)
print("\n=== 700 MHz four-phase ===")
print("cov85_4p mean:", round(float(t7.cov85_mean.mean()), 1),
      "| within-village phase sd: mean", round(float(t7.cov85_sd.mean()), 2),
      "max", round(float(t7.cov85_sd.max()), 2))
cols = ["cov85_p0_0", "cov85_p0_1250", "cov85_p1250_0", "cov85_p1250_1250"]
rk = [stats.spearmanr(t7[a], t7[b]).statistic for i, a in enumerate(cols) for b in cols[i + 1:]]
print("pairwise rank corr cov85 (700MHz):", [round(r, 3) for r in rk], "mean", round(float(np.mean(rk)), 3))
rk26 = [0.57]  # 2.6GHz 均值（来自 stats_v2.json，仅打印参照）
print("(2.6GHz reference: mean pairwise 0.57)")
# 700MHz 排名 vs 2.6GHz 排名
m4p = pd.read_csv("data/v3_master.csv")[["village", "cov85_4p"]].merge(
    t7[["village", "cov85_mean"]], on="village")
print("rank corr 700MHz mean vs 2.6GHz mean cov85:",
      round(stats.spearmanr(m4p.cov85_4p, m4p.cov85_mean).statistic, 3))

# ---------- C4 辅助: jackknife / Moran 全表导出 (M9) ----------
s2 = json.load(open("data/stats_v2.json", encoding="utf-8"))
jk_rows = []
for pair, dd in s2.get("leave_one_county", {}).items():
    for cty, rr in dd.get("leave_one_out", {}).items():
        jk_rows.append(dict(pair=pair, dropped_county=cty, rho=rr["rho"], p=rr["p"], n=rr["n"]))
pd.DataFrame(jk_rows).to_csv("data/jackknife_full.csv", index=False)
print("\njackknife_full.csv:", len(jk_rows), "rows")
print("\nALL S50 DONE")
