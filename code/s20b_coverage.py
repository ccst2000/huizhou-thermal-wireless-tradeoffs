# -*- coding: utf-8 -*-
"""V3 s20b: 标准化虚拟站网 + 逐村覆盖评估（可复现版本，参数全部显式化）
站网：2.5km 网格（原点显式给定，可加相位平移）+ 600m 山顶吸附 + 去重，30m 桅杆
目标点：村域 500m AOI 内 WorldCover 建成区 30m 像元（<30 个则回退 150m 均匀网格）
传播：3GPP TR 38.901 RMa，LOS/NLOS 由 30m DEM 视线路径步进判定（逻辑同 V2 s07）
输出：data/stations_p{dx}_{dy}.csv, data/coverage_p{dx}_{dy}.csv
用法：python s20b_coverage.py [dx dy]   （默认 0 0）
"""
import math
import sys
import numpy as np
import pandas as pd
import rasterio

FC = float(sys.argv[3]) if len(sys.argv) > 3 else 2.6  # GHz（敏感性：0.7）
HB, HUT = 30.0, 1.5                   # 站高 m, 用户高 m
H_ENV, W_ENV = 5.0, 20.0              # RMa 乡村建筑高/街宽
EIRP = 46 - 10 * math.log10(1200) + 17 - 2   # =30.21 dBm (EPRE，带宽无关)
COV_TH = -95.0                        # 基本覆盖门限 dBm
COV_TH_GOOD = -85.0                   # 良好覆盖门限 dBm（可靠数据业务）
R_ASSIGN = 10000.0                    # 站-村分配半径 m
SPACING = 2500.0                      # 站网网格间距 m
SNAP_R = 600.0                        # 山顶吸附半径 m
MARGIN = 3000.0                       # 站网外扩 m
AOI_R = 500.0                         # 村域圆半径 m
MIN_BUILT_TGT = 30                    # 建成区目标点最少数量

dx_phase = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0
dy_phase = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0

left, top, res = np.load("data/utm30_grid.npy")
dem = rasterio.open("data/dem_utm30.tif").read(1)
built = rasterio.open("data/built_utm30.tif").read(1)
H, W = dem.shape

df = pd.read_csv("data/v3_master.csv")
from pyproj import Transformer
tf = Transformer.from_crs(4326, 32650, always_xy=True)
vxy = np.array([tf.transform(lo, la) for lo, la in zip(df.lon, df.lat)])
minx, miny = vxy.min(0)
maxx, maxy = vxy.max(0)


def rc(x, y):
    return int((top - y) / res - 0.5), int((x - left) / res - 0.5)


# ---------- 1. 标准化站网 ----------
def make_stations(pdx, pdy):
    gx0 = math.floor((minx - MARGIN) / SPACING) * SPACING + pdx
    gy0 = math.floor((miny - MARGIN) / SPACING) * SPACING + pdy
    Rp = int(np.ceil(SNAP_R / res))
    yy, xx = np.mgrid[-Rp:Rp + 1, -Rp:Rp + 1]
    disc = (xx ** 2 + yy ** 2) <= Rp ** 2
    cells = {}
    for gx in np.arange(gx0, maxx + MARGIN, SPACING):
        for gy in np.arange(gy0, maxy + MARGIN, SPACING):
            r0, c0 = rc(gx, gy)
            if r0 - Rp < 0 or c0 - Rp < 0 or r0 + Rp >= H or c0 + Rp >= W:
                continue
            win = dem[r0 - Rp:r0 + Rp + 1, c0 - Rp:c0 + Rp + 1]
            z = np.where(disc & np.isfinite(win), win, -np.inf)
            if not np.isfinite(z).any():
                continue
            i = int(np.argmax(z))
            rr, cc = r0 - Rp + i // z.shape[1], c0 - Rp + i % z.shape[1]
            cells[(rr, cc)] = None
    sts = []
    for i, (rr, cc) in enumerate(sorted(cells)):
        sts.append(dict(site=f"V{i + 1:04d}", x=left + (cc + 0.5) * res,
                        y=top - (rr + 0.5) * res, z=float(dem[rr, cc])))
    return pd.DataFrame(sts)


# ---------- 2. RMa 传播（同 V2 s07）----------
def rma_pl(d2d, los):
    d2d = np.maximum(d2d, 10.0)
    d_bp = 2 * math.pi * HB * HUT * FC * 1e9 / 3e8
    d3d = np.sqrt(d2d ** 2 + (HB - HUT) ** 2)
    t1 = min(0.03 * H_ENV ** 1.72, 10)
    t2 = min(0.044 * H_ENV ** 1.72, 14.77)
    t3 = 0.002 * math.log10(H_ENV)
    pl1 = 20 * np.log10(40 * math.pi * d3d * FC / 3) + t1 * np.log10(d3d) - t2 + t3 * d3d
    pl2 = (20 * math.log10(40 * math.pi * d_bp * FC / 3) + t1 * math.log10(d_bp) - t2
           + t3 * d_bp + 40 * np.log10(d3d / d_bp))
    pl_los = np.where(d2d <= d_bp, pl1, pl2)
    pl_nlos = (161.04 - 7.1 * math.log10(W_ENV) + 7.5 * math.log10(H_ENV)
               - (24.37 - 3.7 * (H_ENV / HB) ** 2) * math.log10(HB)
               + (43.42 - 3.1 * math.log10(HB)) * (np.log10(d3d) - 3)
               + 20 * math.log10(FC) - (3.2 * (math.log10(11.75 * HUT)) ** 2 - 4.97))
    return np.where(los, pl_los, np.maximum(pl_los, pl_nlos))


# ---------- 3. 视线路径判定（站→目标点集，向量化步进）----------
def los_to_targets(sx, sy, sz, tx, ty, tz):
    dx = tx - sx
    dy = ty - sy
    d = np.hypot(dx, dy)
    n = len(tx)
    maxang = np.full(n, -1e9)
    ux = dx / np.maximum(d, 1e-9)
    uy = dy / np.maximum(d, 1e-9)
    K = int(np.ceil(d.max() / res))
    for k in range(1, K):
        dist = k * res
        act = dist < d - res * 0.5
        if not act.any():
            break
        idx = np.where(act)[0]
        px = sx + ux[idx] * dist
        py = sy + uy[idx] * dist
        rr = ((top - py) / res - 0.5).astype(int)
        cc = ((px - left) / res - 0.5).astype(int)
        ok = (rr >= 0) & (rr < H) & (cc >= 0) & (cc < W)
        z = dem[rr[ok], cc[ok]]
        ang = (z - sz) / dist
        cur = maxang[idx[ok]]
        maxang[idx[ok]] = np.where(np.isnan(z), cur, np.maximum(cur, ang))
    return (tz - sz) / np.maximum(d, 1e-9) >= maxang - 1e-9


# ---------- 4. 村域目标点 ----------
def village_targets(cx, cy):
    r = AOI_R
    cols = np.arange(int((cx - r - left) / res), int((cx + r - left) / res) + 1)
    rows = np.arange(int((top - cy - r) / res), int((top - cy + r) / res) + 1)
    RR, CC = np.meshgrid(rows, cols, indexing="ij")
    X = left + (CC + 0.5) * res
    Y = top - (RR + 0.5) * res
    m = (X - cx) ** 2 + (Y - cy) ** 2 <= r * r
    ok = m & (built[RR, CC] == 1) & np.isfinite(dem[RR, CC])
    tx, ty = X[ok], Y[ok]
    if len(tx) < MIN_BUILT_TGT:  # 回退：150m 均匀网格
        g = np.arange(-r, r + 1, 150.0)
        GX, GY = np.meshgrid(g, g)
        m2 = (GX ** 2 + GY ** 2) <= r * r
        tx, ty = cx + GX[m2], cy + GY[m2]
    rr = ((top - ty) / res - 0.5).astype(int)
    cc = ((tx - left) / res - 0.5).astype(int)
    tz = dem[rr, cc] + HUT
    ok = np.isfinite(tz)
    return tx[ok], ty[ok], tz[ok]


# ---------- 5. 逐村覆盖 ----------
f_tag = "" if abs(FC - 2.6) < 1e-9 else f"_f{FC:g}"
sts = make_stations(dx_phase, dy_phase)
sts.to_csv(f"data/stations_p{int(dx_phase)}_{int(dy_phase)}{f_tag}.csv", index=False)
print(f"stations: {len(sts)} (phase dx={dx_phase}, dy={dy_phase}, fc={FC} GHz)")

rows = []
for i, v in df.iterrows():
    cx, cy = vxy[i]
    tx, ty, tz = village_targets(cx, cy)
    d2st = np.hypot(sts.x - cx, sts.y - cy)
    near = sts[d2st <= R_ASSIGN]
    best = np.full(len(tx), -140.0)
    for _, s in near.iterrows():
        los = los_to_targets(s.x, s.y, s.z + HB, tx, ty, tz)
        d2d = np.hypot(tx - s.x, ty - s.y)
        rsrp = EIRP - rma_pl(d2d, los)
        best = np.maximum(best, rsrp)
    cov95 = 100.0 * np.mean(best >= COV_TH)
    cov85 = 100.0 * np.mean(best >= COV_TH_GOOD)
    rows.append(dict(village=v.village, cov85=round(cov85, 1), cov95=round(cov95, 1),
                     rsrp_mean=round(float(best.mean()), 1),
                     rsrp_p10=round(float(np.percentile(best, 10)), 1),
                     n_sites=len(near), n_tgt=len(tx)))
    print(f"{v.village:28s} cov85={cov85:5.1f}%  cov95={cov95:5.1f}%  rsrp={best.mean():6.1f}  p10={np.percentile(best,10):6.1f}  sites={len(near):3d} tgt={len(tx):4d}")

out = pd.DataFrame(rows)
out.to_csv(f"data/coverage_p{int(dx_phase)}_{int(dy_phase)}{f_tag}.csv", index=False)

# ---------- 6. 与旧结果对比 ----------
try:
    old = pd.read_csv("data/coverage_village.csv")
    cmp = out.merge(old, on="village", suffixes=("_new", "_old"))
    cmp["d_cov"] = (cmp.cov95_new - cmp.cov95_old).round(1)
    cmp["d_rsrp"] = (cmp.rsrp_mean_new - cmp.rsrp_mean_old).round(1)
    print("\n=== 与旧版对比 ===")
    print(cmp[["village", "cov95_old", "cov95_new", "d_cov", "rsrp_mean_old", "rsrp_mean_new", "d_rsrp"]].to_string(index=False))
    from scipy import stats
    print("rank corr cov95:", round(stats.spearmanr(cmp.cov95_old, cmp.cov95_new)[0], 3),
          " rsrp:", round(stats.spearmanr(cmp.rsrp_mean_old, cmp.rsrp_mean_new)[0], 3))
except FileNotFoundError:
    pass
