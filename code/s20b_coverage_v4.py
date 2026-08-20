# -*- coding: utf-8 -*-
"""V3-R3 s20b v4: 标准化虚拟站网 + 逐村覆盖评估（审稿 R3 P0-3 修正版）

相对 v3 的两处实质修正：
  1) d3D 三维几何修正：RMa 路径损耗中的 d3d 改用站与目标点的绝对三维距离
     sqrt(d2d^2 + (z_site + HB - z_tgt - HUT)^2)，替代旧版恒定天线高差 (HB-HUT)。
     山地链路中两者相差可达数百米，直接影响路径损耗。
  2) NLOS 适用域截断升为主模型：TR 38.901 RMa NLOS 公式适用上限 d2D=5km，
     超出视为不适用（不给连接）。旧版不截断结果保留为敏感性变体（argv[4]="nocap"）。

站网：2.5km 网格（相位平移）+ 600m 山顶吸附 + 去重，30m 桅杆
目标点：村域 500m AOI 内 WorldCover 建成区 30m 像元（<30 个则回退 150m 均匀网格）
输出：data/stations_p{dx}_{dy}{f_tag}_v4.csv, data/coverage_p{dx}_{dy}{f_tag}_v4.csv
用法：python s20b_coverage_v4.py [dx dy [fc [nocap]]]
"""
import math
import sys
import numpy as np
import pandas as pd
import rasterio

FC = float(sys.argv[3]) if len(sys.argv) > 3 else 2.6  # GHz（敏感性：0.7）
NLOS_CAP = not (len(sys.argv) > 4 and sys.argv[4] == "nocap")  # v4: 截断为默认主模型
HB, HUT = 30.0, 1.5                   # 站高 m, 用户高 m
H_ENV, W_ENV = 5.0, 20.0              # RMa 乡村建筑高/街宽
EIRP = 46 - 10 * math.log10(1200) + 17 - 2   # =30.21 dBm (per-RE EPRE，见手稿 2.4)
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


# ---------- 1. 标准化站网（同 v3） ----------
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


# ---------- 2. RMa 传播（d3d 由调用方按真实三维几何传入；实现见 geo_utils，含单元测试） ----------
sys.path.insert(0, "src")
from geo_utils import rma_pl as _rma_pl


def rma_pl(d2d, d3d, los):
    return _rma_pl(d2d, d3d, los, FC, HB, HUT, H_ENV, W_ENV, NLOS_CAP)


# ---------- 3. 视线路径判定（同 v3，绝对高程步进） ----------
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


# ---------- 4. 村域目标点（同 v3） ----------
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
v_tag = "_v4" if NLOS_CAP else "_v4nocap"
sts = make_stations(dx_phase, dy_phase)
sts.to_csv(f"data/stations_p{int(dx_phase)}_{int(dy_phase)}{f_tag}{v_tag}.csv", index=False)
print(f"stations: {len(sts)} (phase dx={dx_phase}, dy={dy_phase}, fc={FC} GHz, nlos_cap={NLOS_CAP})")

rows = []
for i, v in df.iterrows():
    cx, cy = vxy[i]
    tx, ty, tz = village_targets(cx, cy)
    d2st = np.hypot(sts.x - cx, sts.y - cy)
    near = sts[d2st <= R_ASSIGN]
    best = np.full(len(tx), -140.0)
    for _, s in near.iterrows():
        sz = s.z + HB                       # 站天线绝对高程
        los = los_to_targets(s.x, s.y, sz, tx, ty, tz)
        d2d = np.hypot(tx - s.x, ty - s.y)
        d3d = np.sqrt(d2d ** 2 + (tz - sz) ** 2)   # P0-3 修正：真实三维距离
        rsrp = EIRP - rma_pl(d2d, d3d, los)
        best = np.maximum(best, rsrp)
    cov95 = 100.0 * np.mean(best >= COV_TH)
    cov85 = 100.0 * np.mean(best >= COV_TH_GOOD)
    rows.append(dict(village=v.village, cov85=round(cov85, 1), cov95=round(cov95, 1),
                     rsrp_mean=round(float(best.mean()), 1),
                     rsrp_p10=round(float(np.percentile(best, 10)), 1),
                     n_sites=len(near), n_tgt=len(tx)))
    print(f"{v.village:28s} cov85={cov85:5.1f}%  cov95={cov95:5.1f}%  rsrp={best.mean():6.1f}  p10={np.percentile(best,10):6.1f}  sites={len(near):3d} tgt={len(tx):4d}")

out = pd.DataFrame(rows)
out.to_csv(f"data/coverage_p{int(dx_phase)}_{int(dy_phase)}{f_tag}{v_tag}.csv", index=False)

# ---------- 6. 与旧版（恒定 d3d、不截断）对比 ----------
try:
    old = pd.read_csv(f"data/coverage_p{int(dx_phase)}_{int(dy_phase)}{f_tag}.csv")
    cmp = out.merge(old, on="village", suffixes=("_new", "_old"))
    cmp["d_cov85"] = (cmp.cov85_new - cmp.cov85_old).round(1)
    cmp["d_rsrp"] = (cmp.rsrp_mean_new - cmp.rsrp_mean_old).round(1)
    print("\n=== 与 v3 旧版对比（同相位同频段）===")
    print(cmp[["village", "cov85_old", "cov85_new", "d_cov85", "rsrp_mean_old", "rsrp_mean_new", "d_rsrp"]].to_string(index=False))
    from scipy import stats
    print("rank corr cov85:", round(stats.spearmanr(cmp.cov85_old, cmp.cov85_new)[0], 3),
          " rsrp:", round(stats.spearmanr(cmp.rsrp_mean_old, cmp.rsrp_mean_new)[0], 3))
except FileNotFoundError:
    pass
