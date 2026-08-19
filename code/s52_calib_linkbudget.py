# -*- coding: utf-8 -*-
"""V3 s52 (Round-2): (a) elong/compact 定义逆向校准与可复现重算; (b) 链路预算示例表 A9
(a) 从 built_utm30.tif 连通组分重算 elong/compact，校准到 morphology_table.csv 的现存口径
(b) 3 条代表链路（开放/中间/深谷村）phase-0 最强链路逐步链路预算
"""
import math
import numpy as np
import pandas as pd
import rasterio
from scipy import ndimage

built = rasterio.open("data/built_utm30.tif").read(1)
left, top, res = np.load("data/utm30_grid.npy")
m = pd.read_csv("data/v3_master.csv")
mo = pd.read_csv("data/morphology_table.csv")

from pyproj import Transformer
tf = Transformer.from_crs(4326, 32650, always_xy=True)

lab, n = ndimage.label(built, structure=np.ones((3, 3)))
print("components:", n)

def comp_metrics(mask):
    """返回多种候选定义下的 (elong, compact)"""
    ys, xs = np.nonzero(mask)
    pts = np.column_stack([xs, ys]).astype(float)
    A = mask.sum() * res * res
    # 周长：组分边界边数（4-邻域暴露边）
    er = ndimage.binary_erosion(mask, structure=np.ones((3, 3)))
    perim_edges = (mask & ~er).sum()  # 边界像元数近似
    P1 = perim_edges * res
    # 更精确周长：逐边计数
    b = mask.astype(np.uint8)
    P2 = float(((b[:, :-1] != b[:, 1:]).sum() + (b[:-1, :] != b[1:, :]).sum()
                + b[0, :].sum() + b[-1, :].sum() + b[:, 0].sum() + b[:, -1].sum()) * res)
    # PCA 主轴比
    covm = np.cov(pts.T)
    ev = np.linalg.eigvalsh(covm)[::-1]
    elong_pca = math.sqrt(ev[0] / ev[1]) if ev[1] > 0 else np.nan
    # 最小外接矩形（旋转卡壳近似：用 PCA 轴投影）
    v = np.linalg.eigh(covm)[1]
    pro = pts @ v
    L1 = (pro[:, 1].max() - pro[:, 1].min()) * res
    L2 = (pro[:, 0].max() - pro[:, 0].min()) * res
    elong_mbr = L1 / max(L2, 1e-9)
    return dict(A_ha=A / 1e4, P1=P1, P2=P2, elong_pca=elong_pca, elong_mbr=elong_mbr,
                isoq1=4 * math.pi * A / P1 ** 2, isoq2=4 * math.pi * A / P2 ** 2,
                pa1=A / P1, pa2=P2 / A)

rows = []
for _, v in m.iterrows():
    cx, cy = tf.transform(v.lon, v.lat)
    r0, c0 = int((top - cy) / res - 0.5), int((cx - left) / res - 0.5)
    cid = lab[r0, c0]
    if cid == 0:  # 质心落在非建成像元，取 2km 内最大组分
        yy, xx = np.mgrid[0:built.shape[0], 0:built.shape[1]]
        d2 = ((xx + 0.5) * res + left - cx) ** 2 + (top - (yy + 0.5) * res - cy) ** 2
        cand = np.where((d2 < 2000 ** 2) & (lab > 0), lab, 0)
        ids, cnts = np.unique(cand[cand > 0], return_counts=True)
        cid = int(ids[np.argmax(cnts)]) if len(ids) else 0
    if cid == 0:
        rows.append(dict(village=v.village))
        continue
    mm_ = comp_metrics(lab == cid)
    mm_["village"] = v.village
    rows.append(mm_)

cal = pd.DataFrame(rows).merge(mo[["village", "elong", "compact", "built_ha"]], on="village", how="inner")
cal = cal.dropna(subset=["elong_pca"])
from scipy import stats
print("\n=== 候选定义 vs 现存值（Spearman / Pearson 线性） ===")
for c_new, c_old in [("elong_pca", "elong"), ("elong_mbr", "elong"),
                     ("isoq1", "compact"), ("isoq2", "compact"), ("pa2", "compact")]:
    sp = stats.spearmanr(cal[c_new], cal[c_old]).statistic
    lr = stats.linregress(cal[c_new], cal[c_old])
    print(f"{c_new:10s} vs {c_old:8s}: spearman={sp:.3f} pearson={lr.rvalue:.3f} slope={lr.slope:.3f} int={lr.intercept:.3f}")
print("\nsample rows:")
print(cal[["village", "elong", "elong_pca", "elong_mbr", "compact", "isoq1", "isoq2", "built_ha", "A_ha"]].head(12).to_string(index=False))

# ---------- (b) 链路预算 A9 ----------
import importlib.util
spec = importlib.util.spec_from_file_location("s20b", "src/s20b_coverage.py")

FC = 2.6
HB, HUT = 30.0, 1.5
H_ENV, W_ENV = 5.0, 20.0
EIRP = 46 - 10 * math.log10(1200) + 17 - 2

def rma_pl_scalar(d2d, los):
    d2d = max(d2d, 10.0)
    d_bp = 2 * math.pi * HB * HUT * FC * 1e9 / 3e8
    d3d = math.sqrt(d2d ** 2 + (HB - HUT) ** 2)
    t1 = min(0.03 * H_ENV ** 1.72, 10)
    t2 = min(0.044 * H_ENV ** 1.72, 14.77)
    t3 = 0.002 * math.log10(H_ENV)
    pl1 = 20 * math.log10(40 * math.pi * d3d * FC / 3) + t1 * math.log10(d3d) - t2 + t3 * d3d
    pl2 = (20 * math.log10(40 * math.pi * d_bp * FC / 3) + t1 * math.log10(d_bp) - t2
           + t3 * d_bp + 40 * math.log10(d3d / d_bp))
    pl_los = pl1 if d2d <= d_bp else pl2
    pl_nlos = (161.04 - 7.1 * math.log10(W_ENV) + 7.5 * math.log10(H_ENV)
               - (24.37 - 3.7 * (H_ENV / HB) ** 2) * math.log10(HB)
               + (43.42 - 3.1 * math.log10(HB)) * (math.log10(d3d) - 3)
               + 20 * math.log10(FC) - (3.2 * (math.log10(11.75 * HUT)) ** 2 - 4.97))
    return (pl_los if los else max(pl_los, pl_nlos)), d3d, d_bp, pl_los, pl_nlos

# 用 s20b 的站网与 LOS 逻辑复算 3 村最强链路
sys_path_setup = None
import sys
sys.argv = ["s20b", "0", "0"]  # 防止参数误读
# 直接内联：读站网、逐村目标、最强链路
dem = rasterio.open("data/dem_utm30.tif").read(1)
sts = pd.read_csv("data/stations_p0_0.csv")

def los_scalar(sx, sy, sz, tx_, ty_, tz_):
    d = math.hypot(tx_ - sx, ty_ - sy)
    K = int(d // res)
    maxang = -1e9
    for k in range(1, K):
        dist = k * res
        px = sx + (tx_ - sx) / d * dist
        py = sy + (ty_ - sy) / d * dist
        rr, cc = int((top - py) / res - 0.5), int((px - left) / res - 0.5)
        if 0 <= rr < dem.shape[0] and 0 <= cc < dem.shape[1] and np.isfinite(dem[rr, cc]):
            maxang = max(maxang, (dem[rr, cc] - sz) / dist)
    return (tz_ - sz) / max(d, 1e-9) >= maxang - 1e-9

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
    tz = dem[((top - ty) / res - 0.5).astype(int), ((tx - left) / res - 0.5).astype(int)] + HUT
    return tx, ty, tz

EX = ["Hongcun 宏村", "Huansha 环砂", "Zuyuan 祖源"]
lb_rows = []
for vname in EX:
    v = m[m.village == vname].iloc[0]
    cx, cy = tf.transform(v.lon, v.lat)
    tx, ty, tz = village_targets(cx, cy)
    near = sts[np.hypot(sts.x - cx, sts.y - cy) <= 10000]
    best = (-1e9, None, None)  # rsrp, site, d2d, los
    for _, s in near.iterrows():
        # 仅检查该村目标点的中位数目标（代表性链路：取 RSRP 中位数目标点）
        pass
    # 简化：对最强链路（max RSRP over site×target）
    best_rsrp, best_info = -1e9, None
    for _, s in near.iterrows():
        d2d_all = np.hypot(tx - s.x, ty - s.y)
        j = int(np.argmin(d2d_all))  # 最近目标点
        los = los_scalar(s.x, s.y, s.z + HB, tx[j], ty[j], tz[j])
        pl, d3d, d_bp, pl_los, pl_nlos = rma_pl_scalar(d2d_all[j], los)
        rsrp = EIRP - pl
        if rsrp > best_rsrp:
            best_rsrp, best_info = rsrp, (s.site, d2d_all[j], d3d, d_bp, los, pl_los, pl_nlos, pl)
    site, d2d, d3d, d_bp, los, pl_los, pl_nlos, pl = best_info
    lb_rows.append(dict(village=vname, site=site, d2D_m=round(d2d), d3D_m=round(d3d),
                        dBP_m=round(d_bp), link="LOS" if los else "NLOS",
                        PL_LOS_dB=round(pl_los, 1), PL_NLOS_dB=round(pl_nlos, 1),
                        PL_used_dB=round(pl, 1), EPRE_dBm=round(EIRP, 1),
                        RSRP_dBm=round(EIRP - pl, 1)))
a9 = pd.DataFrame(lb_rows)
a9.to_csv("tables/TableA9_link_budget.csv", index=False, encoding="utf-8-sig")
print("\n=== Table A9 link budget ===")
print(a9.to_string(index=False))
