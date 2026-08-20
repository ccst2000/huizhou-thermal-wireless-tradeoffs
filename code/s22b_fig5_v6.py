# -*- coding: utf-8 -*-
"""V3-R3 s22 v4: Fig5 核心权衡图（2x2：tSVF / forest_ring × lst_abs / cov85）
R3 修订:
  - 数据全面换 v4（lst_abs / cov85_4p 主模型）
  - cov85 饱和处理：Theil–Sen 拟合线截断于物理上界 100%，面板内标注天花板村数
  - 面板统计升级为：Spearman ρ + within-family BH-FDR q（ESS 修正）+ 控建成面积偏相关 ρ_partial
  - 图内数字与 tables/_F1_v4.csv / _F2_v4.csv 完全一致（不自算）
输出：figures/Fig5_tradeoff.png
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

plt.rcParams.update({"font.size": 9, "axes.linewidth": 0.8})

m = pd.read_csv("data/v3_master_v6.csv")
f1 = pd.read_csv("tables/_F1_v6.csv").set_index(["metric", "target"])
f2 = pd.read_csv("tables/_F2_v6.csv").set_index(["metric", "target"])

panels = [
    ("tsvf", "lst_abs", "Terrain-horizon openness (tSVF)", "Village summer LST (°C)", "ext", None, (0.03, 0.97, "left")),
    ("tsvf", "cov85_4p", "Terrain-horizon openness (tSVF)", "Good coverage cov$_{85}$ (%)", "low2", (0.97, 0.04), (0.03, 0.97, "left")),
    ("forest_ring_pct", "lst_abs", "Forest ring share (%)", "Village summer LST (°C)", "ext", None, (0.97, 0.97, "right")),
    ("forest_ring_pct", "cov85_4p", "Forest ring share (%)", "Good coverage cov$_{85}$ (%)", "low2", (0.50, 0.04), (0.97, 0.97, "right")),
]

fig, axes = plt.subplots(2, 2, figsize=(9.2, 8.6))
labels = "abcd"
for ax, (x, y, xl, yl, mode, note_loc, stat_loc), lab in zip(axes.flat, panels, labels):
    d = m[[x, y, "built_dom_ha", "village"]].dropna(subset=[x, y]).copy()
    sizes = 25 + 5.0 * d["built_dom_ha"]
    ax.scatter(d[x], d[y], s=sizes, c="white", edgecolors="0.25", linewidths=0.9, zorder=3)
    k, b = stats.theilslopes(d[y], d[x])[:2]
    xs = np.linspace(d[x].min(), d[x].max(), 50)
    ys = k * xs + b
    if "cov85" in y:  # 物理上界截断（饱和结局）
        okc = ys <= 100.0
        ax.plot(xs[okc], ys[okc], color="#c0392b", lw=1.4, zorder=2)
        if not okc.all():
            ax.plot([xs[okc][-1], xs[-1]], [100, 100], color="#c0392b", lw=1.0, ls=":", zorder=2)
        n_ceil = int((d[y] >= 99.9).sum())
        nx, ny = note_loc
        ax.text(nx, ny, f"{n_ceil}/{len(d)} villages at 100% ceiling;\nfit truncated at physical bound",
                transform=ax.transAxes, ha="right" if nx > 0.6 else ("center" if nx > 0.4 else "left"),
                va="bottom", fontsize=7, color="0.35")
    else:
        ax.plot(xs, ys, color="#c0392b", lw=1.4, zorder=2)
    ax.margins(x=0.07, y=0.12)

    if mode == "ext":
        idxs = [d[y].idxmax(), d[y].idxmin()]
    else:
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

    row1 = f1.loc[(x, y)]
    star1 = "***" if row1.p < 0.001 else ("**" if row1.p < 0.01 else ("*" if row1.p < 0.05 else ""))
    dag1 = "†" if row1.survive_dual else ""
    txt = (f"({lab})  ρ = {row1.rho:+.2f}{star1}{dag1}\n"
           f"block-boot 95% CI [{row1.ci_lo:+.2f}, {row1.ci_hi:+.2f}], n = {int(row1.n)}")
    if (x, y) in f2.index:
        row2 = f2.loc[(x, y)]
        txt += (f"\nρ$_{{partial|size}}$ = {row2.rho:+.2f} "
                f"(CI [{row2.ci_lo:+.2f}, {row2.ci_hi:+.2f}])")
    sx, sy, sha = stat_loc
    ax.text(sx, sy, txt, transform=ax.transAxes, va="top", ha=sha,
            fontsize=8.5, fontweight="bold",
            bbox=dict(facecolor="white", alpha=0.88, edgecolor="none", pad=2.5))
    ax.set_xlabel(xl)
    ax.set_ylabel(yl)
    ax.grid(alpha=0.25, lw=0.5)
    ax.set_axisbelow(True)

hs = [plt.scatter([], [], s=25 + 5.0 * v, c="white", edgecolors="0.25")
      for v in (5, 25, 50)]
fig.legend(hs, ["5 ha", "25 ha", "50 ha"], title="Built-up area in 500-m domain",
           loc="lower center", ncol=4, frameon=False, fontsize=8,
           title_fontsize=8.5, bbox_to_anchor=(0.5, -0.005))
fig.tight_layout(rect=[0, 0.035, 1, 1.0])
fig.savefig("figures/Fig5_tradeoff.png", dpi=300, bbox_inches="tight")
print("saved figures/Fig5_tradeoff.png")
