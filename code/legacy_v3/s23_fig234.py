# -*- coding: utf-8 -*-
"""V3 s23: Fig2 形态刻画 / Fig3 夏季LST / Fig4 无线覆盖（全英文期刊版式）
底图：dem_utm30.tif 山体阴影；LST：lst_summer_mean.tif (UTM/100m)
输出：figures/Fig2_morphology.png, Fig3_lst.png, Fig4_coverage.png
"""
import numpy as np
import pandas as pd
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource
from pyproj import Transformer

plt.rcParams.update({"font.size": 9, "axes.linewidth": 0.8})

left, top, res = np.load("data/utm30_grid.npy")
dem = rasterio.open("data/dem_utm30.tif").read(1)
H, W = dem.shape
extent = [left, left + W * res, top - H * res, top]

# 降采样山体阴影（30m→150m 显示）
step = 5
dem_s = dem[::step, ::step]
ext_s = [extent[0], extent[0] + dem_s.shape[1] * res * step,
         extent[3] - dem_s.shape[0] * res * step, extent[3]]
ls = LightSource(azdeg=315, altdeg=45)
hs = ls.hillshade(dem_s, vert_exag=2.0, dx=res * step, dy=res * step)

m = pd.read_csv("data/v3_master.csv")
m = m.merge(pd.read_csv("data/lst_village_v3.csv"), on="village") \
     .merge(pd.read_csv("data/built_domain_area.csv"), on="village") \
     .merge(pd.read_csv("data/morphology_framed.csv")[["village", "elong_fd", "compact_fd"]], on="village")
tf = Transformer.from_crs(4326, 32650, always_xy=True)
mx, my = zip(*[tf.transform(lo, la) for lo, la in zip(m.lon, m.lat)])
mx, my = np.array(mx), np.array(my)


def base_map(ax, title):
    ax.imshow(hs, extent=ext_s, cmap="gray", vmin=0.2, vmax=1.0, aspect="auto")
    ax.set_title(title, fontsize=10, loc="left", fontweight="bold")
    ax.set_xticks([]); ax.set_yticks([])
    # 20km 比例尺
    x0 = extent[0] + 0.04 * (extent[1] - extent[0])
    y0 = extent[2] + 0.05 * (extent[3] - extent[2])
    ax.plot([x0, x0 + 20000], [y0, y0], color="k", lw=2.5)
    ax.text(x0 + 10000, y0 + 0.022 * (extent[3] - extent[2]), "20 km",
            ha="center", fontsize=8)


# ================= Fig2 形态刻画 =================
fig = plt.figure(figsize=(13.5, 5.2))
gs = fig.add_gridspec(1, 3, width_ratios=[1, 1, 1.05], wspace=0.34)

ax = fig.add_subplot(gs[0])
base_map(ax, "(a) Topographic openness (tSVF)")
sc = ax.scatter(mx, my, c=m.tsvf, s=14 + 4.0 * m.built_dom_ha,
                cmap="viridis", vmin=0.89, vmax=1.0,
                edgecolors="white", linewidths=0.7, zorder=5)
fig.colorbar(sc, ax=ax, label="tSVF", orientation="horizontal", shrink=0.62, pad=0.03)

ax = fig.add_subplot(gs[1])
base_map(ax, "(b) Forest ring share (%)")
sc = ax.scatter(mx, my, c=m.forest_ring_pct, s=14 + 4.0 * m.built_dom_ha,
                cmap="YlGn", vmin=30, vmax=100, edgecolors="white", linewidths=0.7, zorder=5)
fig.colorbar(sc, ax=ax, label="%", orientation="horizontal", shrink=0.62, pad=0.03)

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
ax.text(1.0, 1.04, "n = 29; n = 28 for Elongation, Compactness; n = 27 for Forest ring",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=7, color="0.35")
fig.savefig("figures/Fig2_morphology.png", dpi=300, bbox_inches="tight")
plt.close(fig)
print("Fig2 saved")

# ================= Fig3 夏季LST =================
lst = rasterio.open("data/lst_summer_median.tif")
la = lst.read(1)
lb = lst.bounds
fig = plt.figure(figsize=(13.5, 4.9))
gs = fig.add_gridspec(1, 3, width_ratios=[1.15, 1, 0.9], wspace=0.15)

ax = fig.add_subplot(gs[0])
ax.imshow(hs, extent=ext_s, cmap="gray", vmin=0.2, vmax=1.0, aspect="auto")
im = ax.imshow(la, extent=[lb.left, lb.right, lb.bottom, lb.top], cmap="inferno",
               vmin=28, vmax=45, alpha=0.82, aspect="auto")
ax.scatter(mx, my, s=10, facecolors="none", edgecolors="white", linewidths=0.6, zorder=5)
fig.colorbar(im, ax=ax, label="LST (°C)", shrink=0.75, pad=0.015)
ax.set_title("(a) Summer LST median composite (2019–2025)", fontsize=10, loc="left", fontweight="bold")
ax.set_xticks([]); ax.set_yticks([])

ax = fig.add_subplot(gs[1])
d = m[["village", "lst_v2", "lst_bg2"]].dropna().sort_values("lst_v2").reset_index(drop=True)
x = np.arange(len(d))
ax.scatter(x, d.lst_bg2, s=22, facecolors="none", edgecolors="0.45", label="Background ring (1–2 km)", zorder=3)
ax.scatter(x, d.lst_v2, s=26, color="#c0392b", label="Village core (500 m)", zorder=4)
for i in range(len(d)):
    ax.plot([i, i], [d.lst_bg2[i], d.lst_v2[i]], color="0.7", lw=0.7, zorder=2)
ax.set_xticks(x[::4])
ax.set_xticklabels([str(v).split()[0] for v in d.village[::4]], rotation=45, ha="right", fontsize=7)
ax.set_ylabel("LST (°C)")
ax.legend(fontsize=8, frameon=False, loc="upper left")
ax.set_title("(b) Village vs. background LST", fontsize=10, loc="left", fontweight="bold")

ax = fig.add_subplot(gs[2])
dl = m.dlst_v3.dropna()
n_sig = int((m.ci_lo > 0).sum())
bins = np.arange(0.0, 7.5, 0.5)
cnt, _, _ = ax.hist(dl, bins=bins, color="#e67e22", edgecolor="white", lw=0.7)
ax.axvline(dl.mean(), color="k", lw=1.2, ls="--")
ax.text(dl.mean() + 0.08, ax.get_ylim()[1] * 0.86, f"mean = +{dl.mean():.1f} °C", fontsize=8.5)
ax.text(0.03, 0.92, f"n = {len(dl)}, bin width = 0.5 °C", transform=ax.transAxes, fontsize=8)
ax.text(0.03, 0.82, f"{n_sig}/{len(dl)} villages: bootstrap 95% CI > 0", transform=ax.transAxes, fontsize=8)
ax.set_xlabel("ΔLST scene-matched (village − background, °C)")
ax.set_ylabel("Villages")
ax.set_title("(c) Heat anomaly distribution", fontsize=10, loc="left", fontweight="bold")
print(f"Fig3c histogram: total count = {int(cnt.sum())} (must be 29), mean = {dl.mean():.2f}")
fig.savefig("figures/Fig3_lst.png", dpi=300, bbox_inches="tight")
plt.close(fig)
print("Fig3 saved")

# ================= Fig4 无线覆盖 =================
sts = pd.read_csv("data/stations_p0_0.csv")
fig = plt.figure(figsize=(13.5, 4.9))
gs = fig.add_gridspec(1, 2, width_ratios=[1.25, 1], wspace=0.08)

ax = fig.add_subplot(gs[0])
base_map(ax, "(a) Standardized deployment and village coverage")
ax.scatter(sts.x, sts.y, s=1.5, color="0.45", alpha=0.5, zorder=4, label="Virtual site (phase 0)")
sc = ax.scatter(mx, my, c=m.cov85_4p, s=30, cmap="RdYlGn", vmin=55, vmax=100,
                edgecolors="k", linewidths=0.5, zorder=5)
fig.colorbar(sc, ax=ax, label="cov$_{85}$ 4-phase mean (%)", shrink=0.75, pad=0.015)

ax = fig.add_subplot(gs[1])
phases = [(0, 0), (1250, 0), (0, 1250), (1250, 1250)]
allp = pd.concat([pd.read_csv(f"data/coverage_p{a}_{b}.csv") for a, b in phases])
g = allp.groupby("village").cov85
mv, sd = g.mean(), g.std()
ax.scatter(mv, sd, s=26, color="#2980b9", zorder=3)
for v in sd[sd > 15].index:
    name = str(v).split()[0]
    ax.annotate(name, (mv[v], sd[v]), textcoords="offset points", xytext=(6, 4), fontsize=7.5)
ax.set_xlabel("Mean cov$_{85}$ across 4 grid phases (%)")
ax.set_ylabel("Std across phases (pct. pts)")
ax.set_title("(b) Deployment-phase sensitivity", fontsize=10, loc="left", fontweight="bold")
ax.grid(alpha=0.25, lw=0.5)
ax.set_axisbelow(True)
fig.savefig("figures/Fig4_coverage.png", dpi=300, bbox_inches="tight")
plt.close(fig)
print("Fig4 saved")
