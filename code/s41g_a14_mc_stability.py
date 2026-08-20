# -*- coding: utf-8 -*-
"""V6 s41g: A14 蒙特卡洛稳定性（R5-P0-6 修复）
对 14 个 headline 对 × 6 种区组设计（0.10/0.15/0.20° × 2 原点），
用 20 个不同 seed 重复区组 bootstrap（B=999），报告:
  n_seed_excl0   20 个 seed 中 95% CI 排除 0 的个数
  ci_lo_min/max  ci_hi_min/max  跨 seed 的区间端点范围
并标注 borderline（0 < n_seed_excl0 < 20，即零界上不稳）。
输出: tables/TableA14b_mc_stability.csv；更新 data/stats_v6.json 的 a14_mc 键。
"""
import json
import math

import numpy as np
import pandas as pd
from scipy import stats

B_MC = 999
SEEDS = list(range(101, 121))   # 20 seeds

df = pd.read_csv("data/v3_master_v6.csv")

HEAD = [("tsvf", "lst_abs"), ("tsvf", "cov85_4p"), ("tsvf", "rsrp_p10_4p"),
        ("forest_ring_pct", "cov85_4p"), ("forest_ring_pct", "lst_abs"),
        ("slope_deg", "cov85_4p"), ("relief_m", "lst_abs"), ("relief_m", "dlst_v3m"),
        ("water_min_m", "lst_abs"), ("built_dom_ha", "lst_abs"),
        ("cover_dom_pct", "lst_abs"), ("cover_dom_pct", "cov85_4p"),
        ("compact_fd", "dlst_v3m"), ("edge_den_m_ha", "cov85_4p")]


def make_blocks(size=0.15, origin=(0.0, 0.0)):
    bl = {}
    for i, (lo, la) in enumerate(zip(df.lon, df.lat)):
        key = (int((lo - origin[0]) / size), int((la - origin[1]) / size))
        bl.setdefault(key, []).append(i)
    return list(bl.values())


def spear_stat(x, y):
    rx = stats.rankdata(x); ry = stats.rankdata(y)
    rx = rx - rx.mean(); ry = ry - ry.mean()
    den = math.sqrt((rx @ rx) * (ry @ ry))
    return float((rx @ ry) / den) if den > 0 else np.nan


def boot_ci(x, y, blocks, b, rng):
    x = np.asarray(x, float); y = np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    blk_ids = [np.array([i for i in bl if ok[i]]) for bl in blocks]
    blk_ids = [bb for bb in blk_ids if len(bb) > 0]
    boots = np.empty(b)
    for bi in range(b):
        pick = rng.integers(0, len(blk_ids), size=len(blk_ids))
        sel = np.concatenate([blk_ids[j] for j in pick])
        if len(np.unique(sel)) < 4:
            boots[bi] = np.nan
            continue
        boots[bi] = spear_stat(x[sel], y[sel])
    boots = boots[np.isfinite(boots)]
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return float(lo), float(hi)


import os

PART = "tables/_a14mc_partial.csv"
done = set()
rows = []
if os.path.exists(PART):
    _old = pd.read_csv(PART).drop_duplicates(subset=["pair", "block_deg", "origin"],
                                             keep="first")
    rows = _old.to_dict("records")
    # 注意: pandas 会把 "+0.0"/"+0.05" 读成浮点，done 键统一用数值原点
    done = {(r["pair"], float(r["block_deg"]), float(r["origin"])) for r in rows}
    print(f"resume: {len(done)} design rows already done")

for c, t in HEAD:
    for size in [0.10, 0.15, 0.20]:
        for origin in [(0.0, 0.0), (0.05, 0.05)]:
            if (f"{c}~{t}", float(size), float(origin[0])) in done:
                continue
            bl = make_blocks(size, origin)
            los, his = [], []
            for sd in SEEDS:
                lo, hi = boot_ci(df[c].values, df[t].values, bl, B_MC,
                                 np.random.default_rng(sd))
                los.append(lo); his.append(hi)
            nex = int(sum(1 for lo, hi in zip(los, his) if lo > 0 or hi < 0))
            rows.append(dict(pair=f"{c}~{t}", block_deg=size, origin=f"+{origin[0]}",
                             n_blocks=len(bl), n_seed_excl0=nex,
                             ci_lo_min=round(min(los), 3), ci_lo_max=round(max(los), 3),
                             ci_hi_min=round(min(his), 3), ci_hi_max=round(max(his), 3),
                             borderline=bool(0 < nex < len(SEEDS))))
    # 每个 headline 对完成后落盘（断点续跑）
    pd.DataFrame(rows).to_csv(PART, index=False, encoding="utf-8-sig")
    print(f"MC done+checkpoint: {c}~{t} ({len(rows)}/84)", flush=True)

if len(rows) < 84:
    print(f"PARTIAL: {len(rows)}/84 rows — rerun to continue")
    raise SystemExit(0)

out = pd.DataFrame(rows)
out.to_csv("tables/TableA14b_mc_stability.csv", index=False, encoding="utf-8-sig")

with open("data/stats_v6.json", encoding="utf-8") as f:
    S = json.load(f)
S["a14_mc"] = dict(n_seeds=len(SEEDS), b_per_seed=B_MC,
                   n_rows=len(out),
                   n_stable_excl0=int((out.n_seed_excl0 == len(SEEDS)).sum()),
                   n_stable_incl0=int((out.n_seed_excl0 == 0).sum()),
                   n_borderline=int(out.borderline.sum()),
                   borderline_pairs=sorted(out.loc[out.borderline, "pair"].unique().tolist()))
with open("data/stats_v6.json", "w", encoding="utf-8") as f:
    json.dump(S, f, ensure_ascii=False, indent=1)

print("\nborderline pairs:", S["a14_mc"]["borderline_pairs"])
print("stable excl0 / incl0 / borderline:", S["a14_mc"]["n_stable_excl0"],
      S["a14_mc"]["n_stable_incl0"], S["a14_mc"]["n_borderline"])
print("ALL S41G DONE")
