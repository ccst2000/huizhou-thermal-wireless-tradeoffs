# -*- coding: utf-8 -*-
"""V3 s41c2 (Round-2): Moran's I 空间自相关 + 头条相关 95% CI —— v3 数据版
改动: 权重矩阵改用 UTM-50N 米制反距离（回应审稿人"经纬度近似"批评）;
      dLST 用 scene-matched dlst_v3; 结果写入 data/stats_v3.json
"""
import json

import numpy as np
import pandas as pd
from scipy import stats
from pyproj import Transformer

m = pd.read_csv("data/v3_master.csv").merge(pd.read_csv("data/lst_village_v3.csv"), on="village") \
    .merge(pd.read_csv("data/built_domain_area.csv"), on="village") \
    .merge(pd.read_csv("data/morphology_framed.csv")[["village", "elong_fd", "compact_fd"]], on="village")
tf = Transformer.from_crs(4326, 32650, always_xy=True)
xy = np.array([tf.transform(lo, la) for lo, la in zip(m.lon, m.lat)])  # UTM meters


def build_w(xy_):
    d = np.sqrt(((xy_[:, None, :] - xy_[None, :, :]) ** 2).sum(-1))
    W = 1.0 / np.maximum(d, 100.0)   # 米制反距离; 100m 下限防除零
    np.fill_diagonal(W, 0.0)
    return W / W.sum(1, keepdims=True)


def moran_i(x, W, n_perm=9999, seed=7):
    x = np.asarray(x, float)
    n = len(x)
    z = x - x.mean()
    den = (z ** 2).sum()
    I = n / W.sum() * (z @ W @ z) / den
    rng = np.random.default_rng(seed)
    cnt = 0
    for _ in range(n_perm):
        zp = rng.permutation(z)
        Ip = n / W.sum() * (zp @ W @ zp) / den
        if abs(Ip) >= abs(I):
            cnt += 1
    return I, (cnt + 1) / (n_perm + 1)


spatial = {}
for col in ["lst_v2", "dlst_v3", "cov85_4p", "rsrp_p10_4p", "tsvf", "built_dom_ha"]:
    sub = m[["lon", "lat", col]].dropna()
    xy_ = np.array([tf.transform(lo, la) for lo, la in zip(sub.lon, sub.lat)])
    Wd = build_w(xy_)
    I, p = moran_i(sub[col].values, Wd)
    spatial[col] = dict(I=round(float(I), 3), p=round(float(p), 4), n=int(len(sub)))
spatial["_weights"] = "row-standardized inverse-distance, UTM Zone 50N meters, floor 100 m"


def fisher_ci(r, n):
    z = np.arctanh(r)
    se = 1.0 / np.sqrt(n - 3)
    lo, hi = z - 1.96 * se, z + 1.96 * se
    return round(float(np.tanh(lo)), 3), round(float(np.tanh(hi)), 3)


HEAD = [("tsvf", "lst_v2"), ("tsvf", "cov85_4p"), ("forest_ring_pct", "lst_v2"),
        ("forest_ring_pct", "cov85_4p"), ("compact_fd", "dlst_v3"), ("elong_fd", "cov85_4p"),
        ("relief_m", "lst_v2"), ("slope_deg", "cov85_4p")]
ci = {}
for c, t in HEAD:
    dd = m[[c, t]].dropna()
    r, p = stats.spearmanr(dd[c], dd[t])
    lo, hi = fisher_ci(r, len(dd))
    ci[f"{c}~{t}"] = dict(rho=round(r, 3), p=round(p, 5), n=int(len(dd)), ci95=[lo, hi])

S = json.load(open("data/stats_v3.json", encoding="utf-8"))
S["spatial_moran"] = spatial
S["headline_ci"] = ci
json.dump(S, open("data/stats_v3.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# 覆盖 s41c 写的 A5（用 UTM 版 Moran）
a5 = pd.DataFrame([dict(variable=k, I=v["I"], p=v["p"], n=v["n"])
                   for k, v in spatial.items() if not k.startswith("_")])
a5.to_csv("tables/TableA5_moran.csv", index=False, encoding="utf-8-sig")

print("Moran's I (UTM weights):")
for k, v in spatial.items():
    if not k.startswith("_"):
        print(f"  {k:14s} I={v['I']:+.3f} p={v['p']}")
print("\n95% CI:")
for k, v in ci.items():
    print(f"  {k:28s} rho={v['rho']:+.3f} [{v['ci95'][0]:+.3f},{v['ci95'][1]:+.3f}] p={v['p']} n={v['n']}")
