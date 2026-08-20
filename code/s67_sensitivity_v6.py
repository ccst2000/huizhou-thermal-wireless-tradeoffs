# -*- coding: utf-8 -*-
"""V6 s67: 新增敏感性（R5-P0-9 轻量版）-> Table A17
A) WorldCover 年份敏感性: 同管道换 2020 年版(v100)重算 cover_dom_pct，
   与 2021 年版(v200) 的 Spearman 秩相关 + 平均绝对差。
B) ΔLST 的过境日(DOY)敏感性: 对 V1 逐村-逐过境 dlst 记录，
   以 dlst ~ DOY + 帧(path/row)虚拟变量 的村中心化回归提取 DOY 调整项，
   比较调整前后村级均值的秩相关与最大偏移。
输出: tables/TableA17_year_doy_sensitivity.csv；更新 data/stats_v6.json。
"""
import json
import math
import re

import numpy as np
import pandas as pd
import rasterio
import pystac_client
import planetary_computer as pc
from rasterio.windows import from_bounds
from pyproj import Transformer
from scipy import stats

DOMAIN_HA = math.pi * 500.0 ** 2 / 1e4
geo = pd.read_csv("data/village_geometry_v6.csv")
tf = Transformer.from_crs(4326, 32650, always_xy=True)

# ---------- A) WorldCover 2020 vs 2021 ----------
def cover_for_year(year, collection_ver):
    cat = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1")
    sr = cat.search(collections=["esa-worldcover"], bbox=[117.2, 29.5, 119.0, 30.4],
                    datetime=f"{year}-01-01/{year}-12-31")
    tile_map = {}
    for it in sr.items():
        mm_ = re.search(r"N(\d+)E(\d+)", it.id)
        if mm_:
            tile_map[(int(mm_.group(1)), int(mm_.group(2)))] = pc.sign(it).assets["map"].href
    out = {}
    for _, v in geo.iterrows():
        href = tile_map.get((int(v.lat // 3 * 3), int(v.lon // 3 * 3)))
        if href is None:
            continue
        cx, cy = tf.transform(v.lon, v.lat)
        hd = 0.012
        with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                          CPL_VSIL_CURL_USE_HEAD="FALSE", VSI_CACHE="TRUE"):
            with rasterio.open(href) as s:
                win = from_bounds(v.lon - hd, v.lat - hd, v.lon + hd, v.lat + hd,
                                  s.transform).round_offsets().round_lengths()
                arr = s.read(1, window=win)
                tr = s.window_transform(win)
        Hh, Ww = arr.shape
        cols, rws = np.meshgrid(np.arange(Ww), np.arange(Hh))
        lon_g = tr.c + (cols + 0.5) * tr.a
        lat_g = tr.f + (rws + 0.5) * tr.e
        gx, gy = tf.transform(lon_g.ravel(), lat_g.ravel())
        gx = gx.reshape(Hh, Ww); gy = gy.reshape(Hh, Ww)
        dx_m = abs(tr.a) * 111320.0 * math.cos(math.radians(v.lat))
        dy_m = abs(tr.e) * 110540.0
        inD = (gx - cx) ** 2 + (gy - cy) ** 2 <= 500.0 ** 2
        a_ha = float(((arr == 50) & inD).sum()) * dx_m * dy_m / 1e4
        out[v.village] = round(a_ha / DOMAIN_HA * 100, 2)
        print(f"WC{year} {v.vid}: {out[v.village]:.2f}%", flush=True)
    return out


cov2020 = cover_for_year(2020, "v100")

fab = pd.read_csv("data/morphology_fabric_v6.csv")[["village", "cover_dom_pct"]]
cmpA = pd.DataFrame(dict(village=list(cov2020.keys()), cover_2020=list(cov2020.values()))
                    ).merge(fab.rename(columns={"cover_dom_pct": "cover_2021"}), on="village")
rhoA = float(stats.spearmanr(cmpA.cover_2020, cmpA.cover_2021)[0])
madA = float((cmpA.cover_2020 - cmpA.cover_2021).abs().mean())
print(f"\nWorldCover 2020 vs 2021 cover_dom_pct: rho={rhoA:.3f}, MAD={madA:.2f} pct-pts")

# ---------- B) ΔLST 逐过境 DOY 调整敏感性 ----------
op = pd.read_csv("data/dlst_overpass_matrix_v4.csv")
op = op[op.variant == "V1"].copy()
op["doy"] = pd.to_datetime(op.overpass_date).dt.dayofyear
op["year"] = pd.to_datetime(op.overpass_date).dt.year
# 帧由村庄决定（同一村可能跨两帧）；模型: dlst ~ C(village) + doy + doy^2（村内去均值后）
adj = {}
for vname, g in op.groupby("village"):
    if len(g) < 5:
        continue
    X = np.column_stack([g.doy - g.doy.mean(), (g.doy - g.doy.mean()) ** 2,
                         np.ones(len(g))])
    beta = np.linalg.lstsq(X, g.dlst.values, rcond=None)[0]
    g2 = g.assign(dlst_adj=g.dlst.values - (X[:, :2] @ beta[:2]))
    adj[vname] = dict(doy_slope=round(float(beta[0]), 4),
                      dlst_raw=round(float(g.dlst.mean()), 3),
                      dlst_adj=round(float(g2.dlst_adj.mean()), 3))
cmpB = pd.DataFrame(adj).T.reset_index().rename(columns={"index": "village"})
rhoB = float(stats.spearmanr(cmpB.dlst_raw, cmpB.dlst_adj)[0])
maxdB = float((cmpB.dlst_raw - cmpB.dlst_adj).abs().max())
print(f"DOY-adjusted vs raw village dLST(V1): rho={rhoB:.3f}, max|shift|={maxdB:.2f} degC")

# ---------- 汇总表 ----------
a17 = pd.concat([
    pd.DataFrame(dict(item=["WorldCover year (2020 vs 2021): cover_dom_pct"],
                      statistic=["Spearman rho"], value=[round(rhoA, 3)],
                      detail=[f"MAD={madA:.2f} pct-pts; n={len(cmpA)}"])),
    pd.DataFrame(dict(item=["WorldCover year (2020 vs 2021): cover_dom_pct"],
                      statistic=["mean abs diff (pct-pts)"], value=[round(madA, 2)],
                      detail=["same pipeline, esa-worldcover v100 vs v200"])),
    pd.DataFrame(dict(item=["dLST-V1 DOY adjustment (within-village quadratic)"],
                      statistic=["Spearman rho (raw vs adjusted village means)"],
                      value=[round(rhoB, 3)],
                      detail=[f"max village shift={maxdB:.2f} degC; n={len(cmpB)}"])),
    pd.DataFrame(dict(item=["dLST-V1 DOY adjustment (within-village quadratic)"],
                      statistic=["max village mean shift (degC)"], value=[round(maxdB, 2)],
                      detail=["overpass dates span multiple years/seasons"])),
], ignore_index=True)
a17.to_csv("tables/TableA17_year_doy_sensitivity.csv", index=False, encoding="utf-8-sig")

cmpA.to_csv("data/worldcover_year_compare_v6.csv", index=False, encoding="utf-8-sig")
cmpB.to_csv("data/dlst_doy_adjust_v6.csv", index=False, encoding="utf-8-sig")

with open("data/stats_v6.json", encoding="utf-8") as f:
    S = json.load(f)
S["worldcover_year_check"] = dict(rank_rho=round(rhoA, 3), mad=round(madA, 2), n=int(len(cmpA)))
S["dlst_doy_adjust"] = dict(rank_rho=round(rhoB, 3), max_shift=round(maxdB, 2), n=int(len(cmpB)),
                            doy_slope_median=round(float(cmpB.doy_slope.median()), 4))
with open("data/stats_v6.json", "w", encoding="utf-8") as f:
    json.dump(S, f, ensure_ascii=False, indent=1)
print("\nALL S67 DONE")
