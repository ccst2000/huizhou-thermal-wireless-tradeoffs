# -*- coding: utf-8 -*-
"""V3 s55 (Round-2): Frame-D 建成斑聚合形态指标（消灭 Frame O 形状依赖，回应 M7）
定义（写进手稿）:
  输入: ESA WorldCover 2021 v200 (10 m), built-up = class 50, 村心 500 m 圆域 (Frame D)
  elong   = 域内建成像元中心(米制) PCA 主轴比 sqrt(λ1/λ2)  (建成斑 ≥10 像元)
  compact = 4πA/P², 域内建成斑聚合等周商; P = 域内建成像元暴露边总长(米制, 含内边界)
  built_fd_ha = 域内建成总面积 (与 built_dom_ha 30m 口径并列核验)
输出: data/morphology_framed.csv
"""
import math
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds
from scipy import stats
from pyproj import Transformer
import pystac_client
import planetary_computer as pc
import re

cat = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1")
sr = cat.search(collections=["esa-worldcover"], bbox=[117.2, 29.5, 119.0, 30.4],
                datetime="2021-01-01/2021-12-31")
tile_map = {}
for it in sr.items():
    mm_ = re.search(r"N(\d+)E(\d+)", it.id)
    if mm_:
        tile_map[(int(mm_.group(1)), int(mm_.group(2)))] = pc.sign(it).assets["map"].href

m = pd.read_csv("data/v3_master.csv")
mo = pd.read_csv("data/morphology_table.csv")
tf = Transformer.from_crs(4326, 32650, always_xy=True)

def fetch(lon, lat, half_deg=0.012):
    href = tile_map.get((int(lat // 3 * 3), int(lon // 3 * 3)))
    if href is None:
        return None, None
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                      CPL_VSIL_CURL_USE_HEAD="FALSE", VSI_CACHE="TRUE"):
        with rasterio.open(href) as s:
            win = from_bounds(lon - half_deg, lat - half_deg, lon + half_deg, lat + half_deg,
                              s.transform).round_offsets().round_lengths()
            return s.read(1, window=win), s.window_transform(win)

rows = []
for _, v in m.iterrows():
    cx, cy = tf.transform(v.lon, v.lat)
    arr, tr = fetch(v.lon, v.lat)
    if arr is None:
        print("no tile:", v.village); continue
    Hh, Ww = arr.shape
    cols = np.arange(Ww); rws = np.arange(Hh)
    XX, YY = np.meshgrid(cols, rws)
    lon_g = tr.c + (XX + 0.5) * tr.a
    lat_g = tr.f + (YY + 0.5) * tr.e
    gx, gy = tf.transform(lon_g.ravel(), lat_g.ravel())
    gx = gx.reshape(Hh, Ww); gy = gy.reshape(Hh, Ww)
    d2 = (gx - cx) ** 2 + (gy - cy) ** 2
    lat0 = math.radians(v.lat)
    dx_m = abs(tr.a) * 111320.0 * math.cos(lat0)
    dy_m = abs(tr.e) * 110540.0
    inD = d2 <= 500.0 ** 2
    b = (arr == 50) & inD
    nb = int(b.sum())
    if nb < 10:
        rows.append(dict(village=v.village, built_fd_ha=round(nb * dx_m * dy_m / 1e4, 2),
                         n_built_px=nb, elong_fd=np.nan, compact_fd=np.nan))
        print(f"{v.village:24s} built px={nb:4d} (<10, shape n/a)", flush=True)
        continue
    ys, xs = np.nonzero(b)
    pts = np.column_stack([xs * dx_m, ys * dy_m]).astype(float)
    A = nb * dx_m * dy_m
    bb = b.astype(np.uint8)
    P = float(((bb[:, :-1] != bb[:, 1:]).sum() + (bb[:-1, :] != bb[1:, :]).sum()) * (dx_m + dy_m) / 2
              + (bb[0, :].sum() + bb[-1, :].sum()) * dx_m + (bb[:, 0].sum() + bb[:, -1].sum()) * dy_m)
    covm = np.cov(pts.T)
    ev = np.linalg.eigvalsh(covm)[::-1]
    elong = math.sqrt(ev[0] / ev[1]) if ev[1] > 0 else np.nan
    compact = 4 * math.pi * A / P ** 2 if P > 0 else np.nan
    rows.append(dict(village=v.village, built_fd_ha=round(A / 1e4, 2), n_built_px=nb,
                     elong_fd=round(elong, 3), compact_fd=round(compact, 4)))
    print(f"{v.village:24s} px={nb:5d} A={A/1e4:7.2f}ha elong={elong:6.2f} compact={compact:.4f}", flush=True)

nv = pd.DataFrame(rows)
out = nv.merge(mo[["village", "elong", "compact"]], on="village", how="left")
out.to_csv("data/morphology_framed.csv", index=False)

# ---- 新口径下核心结论速检 ----
lv = pd.read_csv("data/lst_village_v3.csv")
bd = pd.read_csv("data/built_domain_area.csv")
vm = m[["village", "cov85_4p", "rsrp_p10_4p"]]
df = nv.merge(lv[["village", "dlst_v3", "lst_v2"]], on="village").merge(bd, on="village").merge(vm, on="village")

def pcorr(x, y, z):
    rx, ry, rz = stats.rankdata(x), stats.rankdata(y), stats.rankdata(z)
    AA = np.column_stack([rz, np.ones_like(rz)])
    rxr = rx - AA @ np.linalg.lstsq(AA, rx, rcond=None)[0]
    ryr = ry - AA @ np.linalg.lstsq(AA, ry, rcond=None)[0]
    return stats.pearsonr(rxr, ryr)

print("\n=== Frame-D 口径核心结论 ===")
d = df.dropna(subset=["compact_fd", "dlst_v3", "built_dom_ha"])
r = stats.spearmanr(d.compact_fd, d.dlst_v3); pp = pcorr(d.compact_fd, d.dlst_v3, d.built_dom_ha)
print("compact_fd~dlst_v3: raw %.3f (p=%.4f) | partial %.3f (p=%.4f) n=%d" % (r.statistic, r.pvalue, pp.statistic, pp.pvalue, len(d)))
d = df.dropna(subset=["compact_fd", "lst_v2", "built_dom_ha"])
r = stats.spearmanr(d.compact_fd, d.lst_v2); pp = pcorr(d.compact_fd, d.lst_v2, d.built_dom_ha)
print("compact_fd~lst_v2 : raw %.3f (p=%.4f) | partial %.3f (p=%.4f) n=%d" % (r.statistic, r.pvalue, pp.statistic, pp.pvalue, len(d)))
d = df.dropna(subset=["elong_fd", "cov85_4p"])
r = stats.spearmanr(d.elong_fd, d.cov85_4p); r2 = stats.spearmanr(d.elong_fd, d.rsrp_p10_4p)
print("elong_fd~cov85    : raw %.3f (p=%.4f) | rsrp_p10 %.3f (p=%.4f) n=%d" % (r.statistic, r.pvalue, r2.statistic, r2b.pvalue if False else r2.pvalue, len(d)))
d = df.dropna(subset=["elong_fd", "lst_v2"])
r = stats.spearmanr(d.elong_fd, d.lst_v2)
print("elong_fd~lst_v2   : raw %.3f (p=%.4f) n=%d" % (r.statistic, r.pvalue, len(d)))
d = df.dropna(subset=["elong_fd", "dlst_v3"])
r = stats.spearmanr(d.elong_fd, d.dlst_v3)
print("elong_fd~dlst_v3  : raw %.3f (p=%.4f) n=%d" % (r.statistic, r.pvalue, len(d)))
ok = df.dropna(subset=["elong_fd"])
print("\nbuilt_fd_ha vs built_dom_ha: spearman %.3f" % stats.spearmanr(df.built_fd_ha, df.built_dom_ha).statistic)
print("n with shape metrics:", int(df.elong_fd.notna().sum()), "/29")
