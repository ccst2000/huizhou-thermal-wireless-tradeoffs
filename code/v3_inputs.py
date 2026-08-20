# -*- coding: utf-8 -*-
"""v3_inputs.py — shared public-input fetcher for the reproducibility pipeline.

Downloads the required public raster tiles once into data/external/ and returns
local paths. Sources (both public, no authentication):
  - Copernicus GLO-30 DEM: copernicus-dem-30m public COG bucket (AWS)
  - ESA WorldCover 2021 v200: esa-worldcover public bucket (AWS)
"""
import os
import urllib.request

EXT = os.path.join("data", "external")

_DEM_URL = ("https://copernicus-dem-30m.s3.amazonaws.com/"
            "Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM/"
            "Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM.tif")
_WC_URL = ("https://esa-worldcover.s3.eu-central-1.amazonaws.com/"
           "v200/2021/map/ESA_WorldCover_10m_2021_v200_N{lat:02d}E{lon:03d}_Map.tif")


def _fetch(url, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path) and os.path.getsize(path) > 1 << 20:
        return path
    print("downloading", url)
    tmp = path + ".part"
    urllib.request.urlretrieve(url, tmp)
    os.replace(tmp, path)
    return path


def dem_tile(lat, lon):
    """Copernicus GLO-30 tile covering N{lat}E{lon} (1°×1°)."""
    return _fetch(_DEM_URL.format(lat=lat, lon=lon),
                  os.path.join(EXT, f"dem_N{lat:02d}E{lon:03d}.tif"))


def wc_tile(lat, lon=117):
    """ESA WorldCover 2021 v200 tile (3°×3°) covering N{lat}E{lon}."""
    return _fetch(_WC_URL.format(lat=lat, lon=lon),
                  os.path.join(EXT, f"wc_N{lat:02d}E{lon:03d}.tif"))
