# -*- coding: utf-8 -*-
"""V3 s40: LST v2 重建 —— QA_PIXEL 云掩膜 + 中位数合成 + 观测计数 + 场景清单
用法: python s40_lst_v2.py <pathrow|combine>
  每帧: 逐景读取 lwir11(ST)+qa_pixel，掩膜后存 data/lst_v2_scenes/<id>.npy
  combine: 全部场景 -> 逐像元中位数 + 观测数 -> 村级 lst_v2/lst_bg2/dlst_v2
"""
import json
import os
import sys
import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.windows import from_bounds

REGION_TIF = "data/lst_grid_ref.tif"   # 目标网格（UTM/100m）
SCENE_DIR = "data/lst_v2_scenes"
os.makedirs(SCENE_DIR, exist_ok=True)

with rasterio.open(REGION_TIF) as s:
    prof = s.profile.copy()
    H, W = s.height, s.width
    dst_tr = s.transform
    bounds = s.bounds

from pyproj import Transformer
inv = Transformer.from_crs(32650, 4326, always_xy=True)
lon0, lat0 = inv.transform(bounds.left, bounds.bottom)
lon1, lat1 = inv.transform(bounds.right, bounds.top)
pad = 0.05

items = json.load(open("data/lst_items.json", encoding="utf-8"))


def stac_sign(frames):
    import pystac_client
    import planetary_computer as pc
    cat = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1")
    out = {}
    for fr in frames:
        p_, r_ = fr[:3], fr[3:]
        sr = cat.search(collections=["landsat-c2-l2"],
                        query={"platform": {"in": ["landsat-8", "landsat-9"]},
                               "landsat:wrs_path": {"eq": int(p_)},
                               "landsat:wrs_row": {"eq": int(r_)}},
                        datetime="2018-06-01/2025-09-30", max_items=100)
        for it in sr.items():
            out[it.id.replace("_ST_UR", "").split("_02")[0] if False else it.id] = pc.sign(it)
    return out


def load_scene(fr):
    """返回该帧签名后的 item 字典 {scene_id: item}"""
    p_, r_ = fr[:3], fr[3:]
    import pystac_client
    import planetary_computer as pc
    cat = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1")
    ids = [it["id"] for it in items if it["path"] == p_ and it["row"] == r_]
    sr = cat.search(collections=["landsat-c2-l2"], ids=ids)
    return {it.id: pc.sign(it) for it in sr.items()}


def read_masked(item):
    """读 ST+QA 窗口，重投影到区域网格，返回 (lst°C float32 含nan, valid bool)"""
    env = rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                       CPL_VSIL_CURL_USE_HEAD="FALSE", VSI_CACHE="TRUE")
    with env:
        with rasterio.open(item.assets["lwir11"].href) as s:
            tfw = Transformer.from_crs(4326, s.crs, always_xy=True)
            x0, y0 = tfw.transform(lon0 - pad, lat0 - pad)
            x1, y1 = tfw.transform(lon1 + pad, lat1 + pad)
            win = from_bounds(x0, y0, x1, y1, s.transform)
            win = win.round_offsets().round_lengths()
            st = s.read(1, window=win).astype("float32")
            wtr = s.window_transform(win)
            crs = s.crs
        with rasterio.open(item.assets["qa_pixel"].href) as s:
            qa = s.read(1, window=win)
        lst = np.full((H, W), np.nan, dtype="float32")
        reproject(st, lst, src_transform=wtr, src_crs=crs, dst_transform=dst_tr,
                  dst_crs="EPSG:32650", resampling=Resampling.bilinear, dst_nodata=np.nan)
        qam = np.zeros((H, W), dtype="uint16")
        reproject(qa, qam, src_transform=wtr, src_crs=crs, dst_transform=dst_tr,
                  dst_crs="EPSG:32650", resampling=Resampling.nearest)
    # QA_PIXEL 位掩膜：0 fill,1 dilated,2 cirrus,3 cloud,4 shadow,5 snow
    bad = np.zeros((H, W), bool)
    for bit in (0, 1, 2, 3, 4, 5):
        bad |= (qam & (1 << bit)) > 0
    lst = lst * 0.00341802 + 149.0 - 273.15
    valid = (~bad) & np.isfinite(lst) & (lst >= 10.0) & (lst <= 60.0)
    return np.where(valid, lst, np.nan).astype("float32")


if sys.argv[1] != "combine":
    fr = sys.argv[1]
    scenes = load_scene(fr)
    todo = [it for it in items if it["path"] == fr[:3] and it["row"] == fr[3:]
            and not os.path.exists(f"{SCENE_DIR}/{it['id']}.npy")]
    print(fr, "scenes todo:", len(todo))

    from concurrent.futures import ThreadPoolExecutor

    def work(it):
        item = scenes.get(it["id"])
        if item is None:
            return it["id"], "STAC miss"
        arr = read_masked(item)
        np.save(f"{SCENE_DIR}/{it['id']}.npy", arr)
        return it["id"], f"{it['date']} cloud {it['cloud']} valid% {100 * float(np.isfinite(arr).mean()):.1f}"

    with ThreadPoolExecutor(max_workers=5) as ex:
        for sid, msg in ex.map(work, todo):
            print(sid, msg, flush=True)
    sys.exit(0)

# ---------- combine ----------
stack = []
used = []
for it in items:
    f = f"{SCENE_DIR}/{it['id']}.npy"
    if os.path.exists(f):
        stack.append(np.load(f))
        used.append(it)
cube = np.stack(stack)  # (n, H, W)
print("cube", cube.shape)
cnt = np.isfinite(cube).sum(0).astype("uint8")
med = np.nanmedian(np.where(np.isfinite(cube), cube, np.nan), axis=0).astype("float32")
med[cnt == 0] = np.nan

prof.update(dtype="float32", nodata=np.nan)
with rasterio.open("data/lst_summer_median.tif", "w", **prof) as f:
    f.write(med, 1)
prof2 = prof.copy()
prof2.update(dtype="uint8", nodata=None)
with rasterio.open("data/lst_obs_count.tif", "w", **prof2) as f:
    f.write(cnt, 1)

man = pd.DataFrame(used)[["id", "date", "cloud", "path", "row"]]
man.to_csv("data/lst_scene_manifest.csv", index=False)
print("manifest:", len(man), "scenes; median valid%:", round(100 * float(np.isfinite(med).mean()), 1))

# ---------- 村级指标 ----------
built = rasterio.open("data/built_utm30.tif").read(1)
left30, top30, res30 = np.load("data/utm30_grid.npy")
built100 = np.zeros((H, W), dtype="uint8")
with rasterio.open("data/built_utm30.tif") as s:
    reproject(s.read(1), built100, src_transform=s.transform, src_crs=s.crs,
              dst_transform=dst_tr, dst_crs="EPSG:32650", resampling=Resampling.nearest)

m = pd.read_csv("data/v3_master.csv")
tf = Transformer.from_crs(4326, 32650, always_xy=True)
left, top, res = bounds.left, bounds.top, 100.0
rows = []
for _, v in m.iterrows():
    cx, cy = tf.transform(v.lon, v.lat)
    cols = np.arange(max(0, int((cx - 2000 - left) / res)), min(W, int((cx + 2000 - left) / res) + 1))
    rws = np.arange(max(0, int((top - cy - 2000) / res)), min(H, int((top - cy + 2000) / res) + 1))
    RR, CC = np.meshgrid(rws, cols, indexing="ij")
    X = left + (CC + 0.5) * res
    Y = top - (RR + 0.5) * res
    d2 = (X - cx) ** 2 + (Y - cy) ** 2
    core = d2 <= 500 ** 2
    ring = (d2 > 1000 ** 2) & (d2 <= 2000 ** 2) & (built100[RR, CC] == 0)
    zc = med[RR, CC][core]
    zb = med[RR, CC][ring]
    cc_ = cnt[RR, CC][core]
    rows.append(dict(village=v.village,
                     lst_v2=round(float(np.nanmean(zc)), 2) if np.isfinite(zc).any() else np.nan,
                     lst_bg2=round(float(np.nanmean(zb)), 2) if np.isfinite(zb).any() else np.nan,
                     dlst_v2=round(float(np.nanmean(zc) - np.nanmean(zb)), 2)
                     if np.isfinite(zc).any() and np.isfinite(zb).any() else np.nan,
                     obs_min=int(cc_.min()), obs_med=int(np.median(cc_))))
out = pd.DataFrame(rows)
out.to_csv("data/lst_village_v2.csv", index=False)
old = m[["village", "lst_v", "dlst"]].merge(out, on="village")
old["shift"] = (old.lst_v2 - old.lst_v).round(2)
print(out.to_string(index=False))
print("mean|shift| vs v1:", round(float(old["shift"].abs().mean()), 2),
      "max|shift|:", round(float(old["shift"].abs().max()), 2))
