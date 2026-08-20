# -*- coding: utf-8 -*-
"""V3-R3 s23 v4: Fig2 形态 / Fig3 夏季LST（过境去重+CI）/ Fig4 覆盖（v4 主模型）
R3 修订:
  Fig2c 注记移出图面（进图注）；Fig2a/b 加点径图例
  Fig3a 用去重 median 合成 + WRS 框 + 来源注记；(b) 消除重复 y 轴标签，
       改 v4 lst_abs 与背景环 (lst_abs - dlst_v1)；(c) 逐村 ΔLST 点+CI（V1 与 matched 并列）
  Fig4a 站点加深；(b) 逐村四相位 min-max 区间图
输出：figures/Fig2_morphology.png, Fig3_lst.png, Fig4_coverage.png
"""
import json

import numpy as np
import pandas as pd
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.colors import LightSource
from pyproj import Transformer

plt.rcParams.update({"font.size": 9, "axes.linewidth": 0.8})

left, top, res = np.load("data/utm30_grid.npy")
dem = rasterio.open("data/dem_utm30.tif").read(1)
H, W = dem.shape
extent = [left, left + W * res, top - H * res, top]

step = 5
dem_s = dem[::step, ::step]
ext_s = [extent[0], extent[0] + dem_s.shape[1] * res * step,
         extent[3] - dem_s.shape[0] * res * step, extent[3]]
ls = LightSource(azdeg=315, altdeg=45)
hs = ls.hillshade(dem_s, vert_exag=2.0, dx=res * step, dy=res * step)

m = pd.read_csv("data/v3_master_v4.csv")
m = m.merge(pd.read_csv("data/built_domain_area.csv"), on="village")
lv = pd.read_csv("data/lst_village_v4.csv")
tf = Transformer.from_crs(4326, 32650, always_xy=True)
mx, my = zip(*[tf.transform(lo, la) for lo, la in zip(m.lon, m.lat)])
mx, my = np.array(mx), np.array(my)


def base_map(ax, title):
    ax.imshow(hs, extent=ext_s, cmap="gray", vmin=0.2, vmax=1.0, aspect="auto")
    ax.set_title(title, fontsize=10, loc="left", fontweight="bold")
    ax.set_xticks([]); ax.set_yticks([])
    x0 = extent[0] + 0.04 * (extent[1] - extent[0])
    y0 = extent[2] + 0.05 * (extent[3] - extent[2])
    ax.plot([x0, x0 + 20000], [y0, y0], color="k", lw=2.5)
    ax.text(x0 + 10000, y0 + 0.022 * (extent[3] - extent[2]), "20 km",
            ha="center", fontsize=8)


def size_legend(ax, vals=(5, 25, 50), loc="lower right"):
    hs_ = [plt.scatter([], [], s=14 + 4.0 * v, c="0.55", edgecolors="white", linewidths=0.7)
           for v in vals]
    ax.legend(hs_, [f"{v} ha" for v in vals], title="Built-up in domain",
              loc=loc, frameon=True, framealpha=0.75, fontsize=7, title_fontsize=7.5,
              borderpad=0.6, labelspacing=0.9)


# ================= Fig2 形态刻画 =================
fig = plt.figure(figsize=(13.5, 5.2))
gs = fig.add_gridspec(1, 3, width_ratios=[1, 1, 1.05], wspace=0.34)

ax = fig.add_subplot(gs[0])
base_map(ax, "(a) Topographic openness (tSVF)")
sc = ax.scatter(mx, my, c=m.tsvf, s=14 + 4.0 * m.built_dom_ha,
                cmap="viridis", vmin=0.89, vmax=1.0,
                edgecolors="white", linewidths=0.7, zorder=5)
fig.colorbar(sc, ax=ax, label="tSVF", orientation="horizontal", shrink=0.62, pad=0.03)
size_legend(ax)

ax = fig.add_subplot(gs[1])
base_map(ax, "(b) Forest ring share (%)")
sc = ax.scatter(mx, my, c=m.forest_ring_pct, s=14 + 4.0 * m.built_dom_ha,
                cmap="YlGn", vmin=30, vmax=100, edgecolors="white", linewidths=0.7, zorder=5)
fig.colorbar(sc, ax=ax, label="%", orientation="horizontal", shrink=0.62, pad=0.03)
size_legend(ax)

ax = fig.add_subplot(gs[2])
vars_ = [("built_dom_ha", "Built-up (domain)"), ("elong_fd", "Elongation"), ("compact_fd", "Compactness"),
         ("relief_m", "Relief"), ("slope_deg", "Slope"), ("tsvf", "tSVF"),
         ("forest_ring_pct", "Forest ring"), ("water_min_m", "Water dist.")]
Z = []
for c, _ in vars_:
    v = m[c].astype(float)
    Z.append((v - v.mean()) / v.std())
pos = np.arange(len(vars_), 0, -1)
for p, z in zip(pos, Z):
    ax.boxplot(z.dropna(), positions=[p], vert=False, widths=0.55,
               boxprops=dict(lw=0.8), medianprops=dict(color="#c0392b", lw=1.4),
               whiskerprops=dict(lw=0.7), capprops=dict(lw=0.7), showfliers=False)
    ax.scatter(z, np.full(len(z), p) + np.random.default_rng(7).uniform(-0.16, 0.16, len(z)),
               s=6, color="0.3", alpha=0.55, zorder=3)
ax.set_yticks(pos)
ax.set_yticklabels([n for _, n in vars_], fontsize=8.5)
ax.axvline(0, color="0.6", lw=0.7, ls="--")
ax.set_xlabel("Standardized value (z-score)")
ax.set_title("(c) Metric distributions", fontsize=10, loc="left", fontweight="bold")
fig.savefig("figures/Fig2_morphology.png", dpi=300, bbox_inches="tight")
plt.close(fig)
print("Fig2 saved")

# ================= Fig3 夏季LST（v4 去重） =================
lst = rasterio.open("data/lst_summer_median_v4.tif")
la = lst.read(1)
lb = lst.bounds
fp = json.load(open("data/wrs_footprints.json"))
fig = plt.figure(figsize=(13.5, 4.9))
gs = fig.add_gridspec(1, 3, width_ratios=[1.15, 1, 0.95], wspace=0.18)

ax = fig.add_subplot(gs[0])
ax.imshow(hs, extent=ext_s, cmap="gray", vmin=0.2, vmax=1.0, aspect="auto")
im = ax.imshow(la, extent=[lb.left, lb.right, lb.bottom, lb.top], cmap="inferno",
               vmin=28, vmax=45, alpha=0.82, aspect="auto")
ax.scatter(mx, my, s=10, facecolors="none", edgecolors="white", linewidths=0.6, zorder=5)
for k, v in fp.items():
    x0, y0, x1, y1 = v["bbox_utm"]
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False,
                           edgecolor="cyan", lw=0.9, ls=(0, (4, 3)), zorder=4))
    ax.text(x0 + 3000, y1 - 9000, k.replace("p", "p").replace("r", "/r"),
            fontsize=6.5, color="cyan", zorder=4)
fig.colorbar(im, ax=ax, label="LST (°C)", shrink=0.75, pad=0.015)
ax.set_title("(a) Summer LST median, 26 deduplicated overpasses",
             fontsize=9.5, loc="left", fontweight="bold")
ax.text(0.975, 0.025, "L8/L9 C2 L2 ST, WRS-2 p120–121/r39–40, Jun–Sep 2019–2025",
        transform=ax.transAxes, fontsize=6.5, color="white", ha="right",
        path_effects=[__import__("matplotlib.patheffects", fromlist=["withStroke"]).withStroke(linewidth=2, foreground="black")])
ax.set_xticks([]); ax.set_yticks([])

ax = fig.add_subplot(gs[1])
d = m[["village", "lst_abs", "dlst_v1"]].dropna().copy()
d["bg"] = d.lst_abs - d.dlst_v1
d = d.sort_values("lst_abs").reset_index(drop=True)
x = np.arange(len(d))
ax.scatter(x, d.bg, s=22, facecolors="none", edgecolors="0.45", label="Background ring (1–2 km)", zorder=3)
ax.scatter(x, d.lst_abs, s=26, color="#c0392b", label="Village core (500 m)", zorder=4)
for i in range(len(d)):
    ax.plot([i, i], [d.bg[i], d.lst_abs[i]], color="0.7", lw=0.7, zorder=2)
ax.set_xticks(x[::4])
ax.set_xticklabels([str(v).split()[0] for v in d.village[::4]], rotation=45, ha="right", fontsize=7)
ax.set_yticks([32, 34, 36, 38, 40, 42])
ax.legend(fontsize=8, frameon=False, loc="upper left")
ax.set_title("(b) Village vs. background LST", fontsize=9.5, loc="left", fontweight="bold")

ax = fig.add_subplot(gs[2])
v1 = lv[lv.variant == "V1"].set_index("village")
v3m = lv[lv.variant == "V3"].set_index("village")
dd = v1.join(v3m, lsuffix="_v1", rsuffix="_v3m").dropna(subset=["dlst_v1"])
dd = dd.sort_values("dlst_v1", ascending=True).reset_index()
ypos = np.arange(len(dd))
ax.axvline(0, color="0.5", lw=0.8, ls="--")
ax.errorbar(dd.dlst_v1, ypos - 0.20, xerr=[dd.dlst_v1 - dd.ci_lo_v1, dd.ci_hi_v1 - dd.dlst_v1],
            fmt="o", ms=4, color="#e67e22", ecolor="#e67e22", elinewidth=0.9, capsize=2,
            zorder=3, label="V1 site-domain vs. non-built ring")
ok = dd.dropna(subset=["dlst_v3m"])
ax.errorbar(ok.dlst_v3m, ypos[ok.index] + 0.20, xerr=[ok.dlst_v3m - ok.ci_lo_v3m, ok.ci_hi_v3m - ok.dlst_v3m],
            fmt="s", ms=3.5, color="#2c3e50", ecolor="#7f8c8d", elinewidth=0.8, capsize=2,
            zorder=4, alpha=0.85, label="V3 terrain/land-cover matched")
ax.set_yticks(ypos)
ax.set_yticklabels([str(v).split()[0] for v in dd.village], fontsize=6)
ax.set_ylim(-0.7, len(dd) - 0.3)
ax.set_xlabel("ΔLST (village − background, °C)")
ax.set_title("(c) Per-village heat anomaly, bootstrap 95% CI", fontsize=9.5, loc="left", fontweight="bold")
ax.legend(fontsize=7, frameon=False, loc="lower right")
ax.grid(axis="x", alpha=0.25, lw=0.5)
ax.set_axisbelow(True)
fig.savefig("figures/Fig3_lst.png", dpi=300, bbox_inches="tight")
plt.close(fig)
print("Fig3 saved; V1 mean %.2f (all %d pos), V3 mean %.2f (%d/%d pos)" % (
    dd.dlst_v1.mean(), (dd.dlst_v1 > 0).sum(), dd.dlst_v3m.mean(),
    (dd.dlst_v3m > 0).sum(), dd.dlst_v3m.notna().sum()))

# ================= Fig4 无线覆盖（v4 主模型） =================
sts = pd.read_csv("data/stations_p0_0_v4.csv")
fig = plt.figure(figsize=(13.5, 4.9))
gs = fig.add_gridspec(1, 2, width_ratios=[1.25, 1], wspace=0.10)

ax = fig.add_subplot(gs[0])
base_map(ax, "(a) Standardized deployment and village coverage (v4)")
ax.scatter(sts.x, sts.y, s=4, color="0.20", alpha=0.75, zorder=4,
           label="Virtual site (grid phase 0)")
sc = ax.scatter(mx, my, c=m.cov85_4p, s=34, cmap="RdYlGn", vmin=55, vmax=100,
                edgecolors="k", linewidths=0.5, zorder=5)
fig.colorbar(sc, ax=ax, label="cov$_{85}$ 4-phase mean (%)", shrink=0.75, pad=0.015)
ax.legend(fontsize=7.5, frameon=True, framealpha=0.75, loc="lower right")

ax = fig.add_subplot(gs[1])
allp = pd.read_csv("data/coverage_4phase_v4.csv")
wide = allp.pivot(index="village", columns="phase", values="cov85")
stat = pd.DataFrame(dict(mean=wide.mean(axis=1), lo=wide.min(axis=1), hi=wide.max(axis=1)))
stat = stat.sort_values("mean").reset_index()
ypos = np.arange(len(stat))
ax.hlines(ypos, stat.lo, stat.hi, color="0.6", lw=1.1, zorder=2)
ax.scatter(stat["mean"], ypos, s=20, color="#2980b9", zorder=3)
iy = stat.index[stat.village.str.contains("Yuliang")][0]
ax.scatter(stat["mean"][iy], ypos[iy], s=42, facecolors="none", edgecolors="#c0392b",
           linewidths=1.6, zorder=4)
ax.annotate("Yuliang", (stat["mean"][iy], ypos[iy]), textcoords="offset points",
            xytext=(8, -3), fontsize=7.5, color="#c0392b")
ax.set_yticks(ypos)
ax.set_yticklabels([str(v).split()[0] for v in stat.village], fontsize=6)
ax.set_xlabel("cov$_{85}$ across 4 deployment phases (%)")
ax.set_title("(b) Four-phase coverage intervals (min–mean–max)", fontsize=10, loc="left", fontweight="bold")
ax.grid(axis="x", alpha=0.25, lw=0.5)
ax.set_axisbelow(True)
fig.savefig("figures/Fig4_coverage.png", dpi=300, bbox_inches="tight")
plt.close(fig)
print("Fig4 saved")
