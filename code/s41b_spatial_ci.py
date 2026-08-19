# -*- coding: utf-8 -*-
"""V3 s41b: 统计补遗——Moran's I 空间自相关 + 头条相关 95% CI（Fisher z）
结果并入 data/stats_v2.json 的 "spatial" 与 "headline_ci" 字段
"""
import json

import numpy as np
import pandas as pd
from scipy import stats

m = pd.read_csv("data/v3_master.csv").merge(pd.read_csv("data/lst_village_v2.csv"), on="village") \
    .merge(pd.read_csv("data/built_domain_area.csv"), on="village")
xy = m[["lon", "lat"]].values

# 反距离权重（行标准化）；用经纬度近似（区域小，变形可忽略）
d = np.sqrt(((xy[:, None, :] - xy[None, :, :]) ** 2).sum(-1))
W = 1.0 / np.maximum(d, 1e-3)
np.fill_diagonal(W, 0.0)
W = W / W.sum(1, keepdims=True)


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
for col in ["lst_v2", "dlst_v2", "cov85_4p", "rsrp_p10_4p", "tsvf", "built_dom_ha"]:
    dd = m[["lon", "lat", col]].dropna()
    ddxy = dd[["lon", "lat"]].values
    dd_d = np.sqrt(((ddxy[:, None, :] - ddxy[None, :, :]) ** 2).sum(-1))
    Wd = 1.0 / np.maximum(dd_d, 1e-3)
    np.fill_diagonal(Wd, 0.0)
    Wd = Wd / Wd.sum(1, keepdims=True)
    I, p = moran_i(dd[col].values, Wd)
    spatial[col] = dict(I=round(float(I), 3), p=round(float(p), 4), n=int(len(dd)))

# 头条相关 Fisher z 95% CI
def fisher_ci(r, n):
    z = np.arctanh(r)
    se = 1.0 / np.sqrt(n - 3)
    lo, hi = z - 1.96 * se, z + 1.96 * se
    return round(float(np.tanh(lo)), 3), round(float(np.tanh(hi)), 3)


HEAD = [("tsvf", "lst_v2"), ("tsvf", "cov85_4p"), ("forest_ring_pct", "lst_v2"),
        ("forest_ring_pct", "cov85_4p"), ("compact", "dlst_v2"), ("elong", "cov85_4p"),
        ("relief_m", "lst_v2"), ("slope_deg", "cov85_4p")]
ci = {}
for c, t in HEAD:
    dd = m[[c, t]].dropna()
    r, p = stats.spearmanr(dd[c], dd[t])
    lo, hi = fisher_ci(r, len(dd))
    ci[f"{c}~{t}"] = dict(rho=round(r, 3), p=round(p, 5), n=int(len(dd)), ci95=[lo, hi])

S = json.load(open("data/stats_v2.json", encoding="utf-8"))
S["spatial_moran"] = spatial
S["headline_ci"] = ci
json.dump(S, open("data/stats_v2.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

print("Moran's I:")
for k, v in spatial.items():
    print(f"  {k:14s} I={v['I']:+.3f} p={v['p']}")
print("\n95% CI:")
for k, v in ci.items():
    print(f"  {k:28s} rho={v['rho']:+.3f} [{v['ci95'][0]:+.3f},{v['ci95'][1]:+.3f}] p={v['p']} n={v['n']}")
