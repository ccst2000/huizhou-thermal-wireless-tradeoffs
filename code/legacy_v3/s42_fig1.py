# -*- coding: utf-8 -*-
"""V3 s42: Fig1 研究区图重制（回应审稿：补比例尺/指北针/经纬网/位置插图）
底图：Esri World Imagery XYZ 瓦片（缓存 data/tiles/）
输出：figures/Fig1_study_area_EN.png
"""
import io
import math
import os

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import requests
from PIL import Image
import matplotlib.patheffects as pe

TILE = 256
UA = {"User-Agent": "Mozilla/5.0 (research; contact: author)"}
os.makedirs("data/tiles", exist_ok=True)


def lonlat2tile(lon, lat, z):
    n = 2 ** z
    x = (lon + 180) / 360 * n
    la = math.radians(lat)
    y = (1 - math.log(math.tan(la) + 1 / math.cos(la)) / math.pi) / 2 * n
    return x, y


def tile2wm(x, y, z):
    """瓦片角点 -> Web Mercator 米"""
    n = 2 ** z
    lon = x / n * 360 - 180
    my = 6378137 * math.pi * (1 - 2 * y / n)
    return lon * 6378137 * math.pi / 180, my


def fetch(z, x, y):
    fp = f"data/tiles/z{z}_{x}_{y}.jpg"
    if not os.path.exists(fp):
        url = ("https://server.arcgisonline.com/ArcGIS/rest/services/"
               f"World_Imagery/MapServer/tile/{z}/{y}/{x}")
        r = requests.get(url, headers=UA, timeout=40)
        r.raise_for_status()
        open(fp, "wb").write(r.content)
    return np.array(Image.open(fp).convert("RGB"))


def mosaic(lon0, lat0, lon1, lat1, z):
    """lon0<lon1, lat0<lat1；返回 image, (x0_wm, x1_wm, y0_wm, y1_wm)"""
    x0f, y0f = lonlat2tile(lon0, lat1, z)   # 左上
    x1f, y1f = lonlat2tile(lon1, lat0, z)   # 右下
    X0, Y0, X1, Y1 = int(x0f), int(y0f), int(x1f), int(y1f)
    rows = []
    for ty in range(Y0, Y1 + 1):
        rows.append(np.hstack([fetch(z, tx, ty) for tx in range(X0, X1 + 1)]))
    img = np.vstack(rows)
    wx0, wy1 = tile2wm(X0, Y0, z)
    wx1, wy0 = tile2wm(X1 + 1, Y1 + 1, z)
    return img, (wx0, wx1, wy0, wy1)


def ll2wm(lon, lat):
    x = 6378137 * math.radians(lon)
    y = 6378137 * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    return x, y


# ---------------- 数据 ----------------
v = pd.read_csv("data/village_sample_v2.csv")
v["name"] = [s.split()[0] for s in v.village]
v["idx"] = range(1, len(v) + 1)   # 编号与 Table 1 行序一致

pad_lon, pad_lat = 0.10, 0.08
lon0, lon1 = v.lon.min() - pad_lon, v.lon.max() + pad_lon
lat0, lat1 = v.lat.min() - pad_lat, v.lat.max() + pad_lat

img, ext = mosaic(lon0, lat0, lon1, lat1, 11)
lat_mid = (lat0 + lat1) / 2

# ---------------- 画布 ----------------
fig = plt.figure(figsize=(13.2, 7.2))
gs = fig.add_gridspec(1, 2, width_ratios=[2.75, 1.0], wspace=0.04)
ax = fig.add_subplot(gs[0])
ax.imshow(img, extent=[ext[0], ext[1], ext[2], ext[3]], aspect="auto", zorder=1)

# 村点
for _, r in v.iterrows():
    x, y = ll2wm(r.lon, r.lat)
    ax.scatter(x, y, s=90, marker="o", facecolors="#ff4d4f", edgecolors="white",
               linewidths=1.0, zorder=4, alpha=0.92)
    ax.text(x, y, str(r.idx), ha="center", va="center", fontsize=6.5,
            color="white", fontweight="bold", zorder=5)

# 经纬网（每 0.2°）
xt = np.arange(math.floor(lon0 * 5) / 5, lon1 + 0.01, 0.2)
yt = np.arange(math.floor(lat0 * 5) / 5, lat1 + 0.01, 0.2)
ax.set_xticks([ll2wm(lo, lat_mid)[0] for lo in xt])
ax.set_xticklabels([f"{lo:.1f}°E" for lo in xt], fontsize=7.5)
ax.set_yticks([ll2wm(lon0, la)[1] for la in yt])
ax.set_yticklabels([f"{la:.1f}°N" for la in yt], fontsize=7.5)
ax.tick_params(length=0, pad=2)
for s in ax.spines.values():
    s.set_linewidth(0.8)

# 比例尺 20 km（Web Mercator 需按纬度修正）
mpp = 156543.03392 * math.cos(math.radians(lat_mid)) / 2 ** 11  # m/px(屏幕坐标系换算略)
bar_m = 20000.0
bx0 = ext[0] + 0.04 * (ext[1] - ext[0])
by0 = ext[2] + 0.05 * (ext[3] - ext[2])
ax.plot([bx0, bx0 + bar_m], [by0, by0], color="white", lw=4.5, zorder=6,
        solid_capstyle="butt", path_effects=[])
ax.plot([bx0, bx0 + bar_m], [by0, by0], color="k", lw=2.2, zorder=7, solid_capstyle="butt")
ax.text(bx0 + bar_m / 2, by0 + 0.018 * (ext[3] - ext[2]), "20 km", ha="center",
        fontsize=8.5, color="white", zorder=7,
        path_effects=[pe.withStroke(linewidth=2.2, foreground="black")])

# 指北针
nx = ext[1] - 0.055 * (ext[1] - ext[0])
ny = ext[3] - 0.10 * (ext[3] - ext[2])
ax.annotate("", xy=(nx, ny + 0.055 * (ext[3] - ext[2])), xytext=(nx, ny),
            arrowprops=dict(arrowstyle="-|>", color="white", lw=2.2,
                            mutation_scale=16), zorder=7)
ax.text(nx, ny + 0.068 * (ext[3] - ext[2]), "N", ha="center", fontsize=10,
        color="white", fontweight="bold", zorder=7)

ax.set_title("Study area and village sample (n = 29), southern Anhui, China",
             fontsize=11, loc="left", fontweight="bold", pad=6)

# 位置插图：中国范围 z4
axin = ax.inset_axes([0.015, 0.60, 0.22, 0.30])
img_cn, ext_cn = mosaic(97.0, 17.0, 126.0, 42.0, 4)
axin.imshow(img_cn, extent=[ext_cn[0], ext_cn[1], ext_cn[2], ext_cn[3]], aspect="auto")
rx0, ry0 = ll2wm(lon0, lat0)
rx1, ry1 = ll2wm(lon1, lat1)
axin.add_patch(Rectangle((rx0, ry0), rx1 - rx0, ry1 - ry0,
                         fill=False, edgecolor="red", lw=1.6))
axin.set_xticks([]); axin.set_yticks([])
for s in axin.spines.values():
    s.set_linewidth(1.0)
axin.text(0.5, -0.07, "Location in China", transform=axin.transAxes,
          ha="center", fontsize=7.5, color="0.15")

# ---------------- 右侧索引 ----------------
axi = fig.add_subplot(gs[1])
axi.axis("off")
axi.set_title("Village index", fontsize=10, fontweight="bold", loc="left")
col1, col2 = v.iloc[:15], v.iloc[15:]
for j, (cc, xpos) in enumerate([(col1, 0.02), (col2, 0.55)]):
    for i, (_, r) in enumerate(cc.iterrows()):
        axi.text(xpos, 0.925 - i * 0.0605, f"{r.idx}. {r['name']}",
                 transform=axi.transAxes, fontsize=8.2, va="top")

fig.savefig("figures/Fig1_study_area_EN.png", dpi=300, bbox_inches="tight")
print("saved figures/Fig1_study_area_EN.png", img.shape)
