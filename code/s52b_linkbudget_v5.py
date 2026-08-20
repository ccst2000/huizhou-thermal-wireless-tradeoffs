# -*- coding: utf-8 -*-
"""V5 s52b: worked link budget（Table A12），与 v4 主模型逐行一致（回应 R4 P0-11）
对 3 个代表村（开阔盆地/中间/深谷）取 phase(0,0)、2.6 GHz、NLOS 截断主模型下的
最强【可服务】链路（PL 有限），逐项报告：站点/目标的 DSM 地表高程、天线绝对高程、
d2D、Δz、d3D、dBP、LOS 判定、PL_LOS/PL_NLOS/PL_used、EPRE、RSRP。
输出: tables/TableA12_link_budget.csv
"""
import math
import sys

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer

sys.path.insert(0, "src")
from geo_utils import rma_pl

FC = 2.6
HB, HUT = 30.0, 1.5
H_ENV, W_ENV = 5.0, 20.0
EIRP = 46 - 10 * math.log10(1200) + 17 - 2   # 30.21 dBm per-RE EPRE
R_ASSIGN = 10000.0

built = rasterio.open("data/built_utm30.tif").read(1)
dem = rasterio.open("data/dem_utm30.tif").read(1)
left, top, res = np.load("data/utm30_grid.npy")
m = pd.read_csv("data/v3_master_v5.csv")
sts = pd.read_csv("data/stations_p0_0_v4.csv")
tf = Transformer.from_crs(4326, 32650, always_xy=True)


def los_scalar(sz_abs, tz_abs, sx, sy, tx_, ty_):
    """与 s20b 一致的仰角法 LOS：路径上最大地形仰角 vs 链路仰角。"""
    d = math.hypot(tx_ - sx, ty_ - sy)
    K = int(d // res)
    maxang = -1e9
    for k in range(1, K):
        dist = k * res
        px = sx + (tx_ - sx) / d * dist
        py = sy + (ty_ - sy) / d * dist
        rr, cc = int((top - py) / res - 0.5), int((px - left) / res - 0.5)
        if 0 <= rr < dem.shape[0] and 0 <= cc < dem.shape[1] and np.isfinite(dem[rr, cc]):
            maxang = max(maxang, (dem[rr, cc] - sz_abs) / dist)
    return (tz_abs - sz_abs) / max(d, 1e-9) >= maxang - 1e-9


def village_targets(cx, cy, r=500.0):
    cols = np.arange(int((cx - r - left) / res), int((cx + r - left) / res) + 1)
    rws = np.arange(int((top - cy - r) / res), int((top - cy + r) / res) + 1)
    RR, CC = np.meshgrid(rws, cols, indexing="ij")
    X = left + (CC + 0.5) * res
    Y = top - (RR + 0.5) * res
    mk = (X - cx) ** 2 + (Y - cy) ** 2 <= r * r
    ok = mk & (built[RR, CC] == 1) & np.isfinite(dem[RR, CC])
    tx, ty = X[ok], Y[ok]
    if len(tx) < 30:
        g = np.arange(-r, r + 1, 150.0)
        GX, GY = np.meshgrid(g, g)
        m2 = (GX ** 2 + GY ** 2) <= r * r
        tx, ty = cx + GX[m2], cy + GY[m2]
    tz = dem[((top - ty) / res - 0.5).astype(int), ((tx - left) / res - 0.5).astype(int)]
    return tx, ty, tz


EX = ["Hongcun 宏村", "Huansha 环砂", "Zuyuan 祖源"]
lb_rows = []
for vname in EX:
    v = m[m.village == vname].iloc[0]
    cx, cy = tf.transform(v.lon, v.lat)
    tx, ty, tz = village_targets(cx, cy)
    near = sts[np.hypot(sts.x - cx, sts.y - cy) <= R_ASSIGN]
    best = (-1e9, None)
    for _, s in near.iterrows():
        sz_abs = s.z + HB
        d2d_all = np.hypot(tx - s.x, ty - s.y)
        j = int(np.argmin(d2d_all))
        d2d = float(d2d_all[j])
        tz_abs = float(tz[j] + HUT)
        los = los_scalar(sz_abs, tz_abs, s.x, s.y, tx[j], ty[j])
        d3d = math.sqrt(d2d ** 2 + (sz_abs - tz_abs) ** 2)   # v4 真实三维距离
        pl = float(rma_pl(np.array([d2d]), np.array([d3d]), np.array([los]),
                          FC, HB, HUT, H_ENV, W_ENV, NLOS_CAP=True)[0])
        if not np.isfinite(pl):
            continue                                         # NLOS 超 5km 不适用
        rsrp = EIRP - pl
        if rsrp > best[0]:
            best = (rsrp, (s.site, float(s.z), d2d, d3d, los, float(tz[j]), j))
    rsrp, (site, zsurf_s, d2d, d3d, los, zsurf_t, jt) = best
    d_bp = 2 * math.pi * HB * HUT * FC * 1e9 / 3e8
    pl_los = float(rma_pl(np.array([d2d]), np.array([d3d]), np.array([True]), FC, HB, HUT, H_ENV, W_ENV, False)[0])
    pl_nlos = float(rma_pl(np.array([d2d]), np.array([d3d]), np.array([False]), FC, HB, HUT, H_ENV, W_ENV, False)[0])
    lb_rows.append(dict(village=vname, site=site,
                        surface_z_site_m=round(zsurf_s, 1), surface_z_target_m=round(zsurf_t, 1),
                        ant_abs_site_m=round(zsurf_s + HB, 1), ant_abs_target_m=round(zsurf_t + HUT, 1),
                        d2D_m=round(d2d), delta_z_m=round(zsurf_s + HB - zsurf_t - HUT, 1),
                        d3D_m=round(d3d), dBP_m=round(d_bp),
                        link="LOS" if los else "NLOS",
                        PL_LOS_dB=round(pl_los, 1), PL_NLOS_dB=round(pl_nlos, 1),
                        PL_used_dB=round(EIRP - rsrp, 1),
                        EPRE_dBm=round(EIRP, 2), RSRP_dBm=round(rsrp, 1)))
a12 = pd.DataFrame(lb_rows)
a12.to_csv("tables/TableA12_link_budget.csv", index=False, encoding="utf-8-sig")
print("=== Table A12 worked link budget (v4 main model, phase 0,0) ===")
print(a12.to_string(index=False))
print("\nALL S52B DONE")
