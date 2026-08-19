# -*- coding: utf-8 -*-
"""V3 s22: Fig5 核心权衡图（2x2 散点：tSVF / forest_ring × LST / cov85）
v2 修正：统计用全样本配对；祖源/木梨硔纳入（点尺寸用中位数）；标注防重叠规则
输出：figures/Fig5_tradeoff.png
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

plt.rcParams.update({"font.size": 9, "axes.linewidth": 0.8})

m = pd.read_csv("data/v3_master.csv")
m = m.merge(pd.read_csv("data/lst_village_v2.csv"), on="village") \
     .merge(pd.read_csv("data/built_domain_area.csv"), on="village")

panels = [
    ("tsvf", "lst_v2", "Topographic openness (tSVF)", "Village summer LST (°C)", "ext"),
    ("tsvf", "cov85_4p", "Topographic openness (tSVF)", "Good coverage cov$_{85}$ (%)", "low2"),
    ("forest_ring_pct", "lst_v2", "Forest ring share (%)", "Village summer LST (°C)", "ext"),
    ("forest_ring_pct", "cov85_4p", "Forest ring share (%)", "Good coverage cov$_{85}$ (%)", "low2"),
]

fig, axes = plt.subplots(2, 2, figsize=(9.2, 8.2))
labels = "abcd"
for ax, (x, y, xl, yl, mode), lab in zip(axes.flat, panels, labels):
    d = m[[x, y, "built_dom_ha", "village"]].dropna(subset=[x, y]).copy()
    r, p = stats.spearmanr(d[x], d[y])
    sizes = 25 + 5.0 * d["built_dom_ha"]
    ax.scatter(d[x], d[y], s=sizes, c="white", edgecolors="0.25",
               linewidths=0.9, zorder=3)
    k, b = stats.theilslopes(d[y], d[x])[:2]
    xs = np.linspace(d[x].min(), d[x].max(), 50)
    ax.plot(xs, k * xs + b, color="#c0392b", lw=1.4, zorder=2)
    ax.margins(x=0.07, y=0.12)

    # 选点标注
    if mode == "ext":
        idxs = [d[y].idxmax(), d[y].idxmin()]
    else:  # low2: cov 最低两村
        idxs = list(d[y].nsmallest(2).index)
    xr = d[x].max() - d[x].min()
    yr = d[y].max() - d[y].min()
    for idx in idxs:
        px, py = d.loc[idx, x], d.loc[idx, y]
        xf = (px - d[x].min()) / xr
        yf = (py - d[y].min()) / yr
        dxpt, ha = (7, "left")
        if xf > 0.86:
            dxpt, ha = (-8, "right")
        dypt = 6
        if yf > 0.80:
            dypt = -13
        name = str(d.loc[idx, "village"]).split()[0]
        ax.annotate(name, (px, py), textcoords="offset points",
                    xytext=(dxpt, dypt), ha=ha, fontsize=7.5, color="0.15", zorder=4)

    sig = "p < 0.001" if p < 0.001 else f"p = {p:.3f}"
    ax.text(0.03, 0.97, f"({lab})  ρ = {r:+.2f}, {sig}, n = {len(d)}",
            transform=ax.transAxes, va="top", ha="left", fontsize=9, fontweight="bold")
    ax.set_xlabel(xl)
    ax.set_ylabel(yl)
    ax.grid(alpha=0.25, lw=0.5)
    ax.set_axisbelow(True)

hs = [plt.scatter([], [], s=25 + 5.0 * v, c="white", edgecolors="0.25")
      for v in (5, 25, 50)]
fig.legend(hs, ["5 ha", "25 ha", "50 ha"], title="Built-up area in 500-m domain",
           loc="lower center", ncol=4, frameon=False, fontsize=8,
           title_fontsize=8.5, bbox_to_anchor=(0.5, -0.005))
fig.suptitle("Morphology-driven trade-offs: thermal environment vs. wireless coverage",
             fontsize=11, y=0.995)
fig.tight_layout(rect=[0, 0.035, 1, 0.98])
fig.savefig("figures/Fig5_tradeoff.png", dpi=300, bbox_inches="tight")
print("saved figures/Fig5_tradeoff.png")
