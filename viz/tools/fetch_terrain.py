"""Fetch real terrain for the QSiteProof Alviso / North San Jose scene.

Source: AWS Terrain Tiles (Mapzen / Tilezen "terrarium" encoding), public S3 bucket
  https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png
  Docs + attribution: https://github.com/tilezen/joerd/blob/master/docs/formats.md
                      https://github.com/tilezen/joerd/blob/master/docs/attribution.md
  Decode: elevation_m = R*256 + G + B/256 - 32768
  In CONUS the underlying data is USGS 3DEP / NED (1/3 arc-second, ~10 m) where available.

Output: viz/data/terrain/heightmap.json, a regular grid in local ENU metres centred on the site.
Projection: local equirectangular about the site origin (x east, y north), using the WGS84
meridional / prime-vertical radii of curvature at the origin latitude. Over an ~20 km box the
distortion vs. true ENU is well under 0.1 % (small compared to the ~70 m cell size).

Resampling: bilinear interpolation in Web-Mercator pixel space of the zoom-Z mosaic.

Validation (printed + stored in "validation"): site elevation, Mission Peak, global min/max,
and the highest grid cell. The USGS EPQS point service is queried as an independent cross-check
at the site and Mission Peak (best effort; skipped if offline).

Usage:  python tools/fetch_terrain.py [--zoom 13] [--n 256]
Only standard library + numpy + Pillow.
"""
from __future__ import annotations

import argparse
import io
import json
import math
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

import numpy as np
from PIL import Image

UA = "QSiteProof-hack/0.1 (research prototype)"
TILE_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
EPQS_URL = "https://epqs.nationalmap.gov/v1/json?x={lon}&y={lat}&wkid=4326&units=Meters&includeDate=false"

# Bounding box requested by the pipeline (degrees, WGS84)
BBOX = dict(south=37.33, west=-122.06, north=37.52, east=-121.85)
# Site origin (150 MW data-center site, North San Jose / Alviso)
ORIGIN = dict(lat=37.4275, lon=-121.9650)
# Validation points
MISSION_PEAK = dict(lat=37.5125, lon=-121.8805)  # summit ~2,517 ft = 767 m (USGS GNIS)

WATER_THRESHOLD_M = 0.5  # cells at or below this are flagged "water" (salt ponds / Bay / sloughs)

# WGS84
A = 6378137.0
F = 1 / 298.257223563
E2 = F * (2 - F)

HERE = os.path.dirname(os.path.abspath(__file__))
VIZ = os.path.dirname(HERE)
CACHE = os.path.join(VIZ, "data", "terrain", "cache")
OUT = os.path.join(VIZ, "data", "terrain", "heightmap.json")


def radii(lat_deg: float):
    """Meridional (M) and prime-vertical (N) radii of curvature, metres."""
    s = math.sin(math.radians(lat_deg))
    w = math.sqrt(1 - E2 * s * s)
    M = A * (1 - E2) / w ** 3
    N = A / w
    return M, N


M0, N0 = radii(ORIGIN["lat"])
COS0 = math.cos(math.radians(ORIGIN["lat"]))


def ll_to_enu(lat, lon):
    x = math.radians(lon - ORIGIN["lon"]) * N0 * COS0
    y = math.radians(lat - ORIGIN["lat"]) * M0
    return x, y


def enu_to_ll(x, y):
    lat = ORIGIN["lat"] + np.degrees(y / M0)
    lon = ORIGIN["lon"] + np.degrees(x / (N0 * COS0))
    return lat, lon


def lonlat_to_globalpx(lon, lat, z):
    """Web-Mercator global pixel coords (256 px tiles)."""
    n = 256 * 2 ** z
    px = (np.asarray(lon) + 180.0) / 360.0 * n
    lat_r = np.radians(np.asarray(lat))
    py = (1.0 - np.log(np.tan(lat_r) + 1.0 / np.cos(lat_r)) / math.pi) / 2.0 * n
    return px, py


def fetch(url: str, timeout=30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            if attempt == 3:
                raise
            print(f"  retry {attempt + 1} for {url}: {e}", file=sys.stderr)
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("unreachable")


def get_tile(z, x, y) -> np.ndarray:
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"terrarium_{z}_{x}_{y}.png")
    if not os.path.exists(path):
        data = fetch(TILE_URL.format(z=z, x=x, y=y))
        with open(path, "wb") as f:
            f.write(data)
    img = Image.open(path).convert("RGB")
    a = np.asarray(img, dtype=np.float64)
    return a[..., 0] * 256.0 + a[..., 1] + a[..., 2] / 256.0 - 32768.0


def build_mosaic(z, lon_min, lat_min, lon_max, lat_max):
    px0, py0 = lonlat_to_globalpx(lon_min, lat_max, z)  # top-left
    px1, py1 = lonlat_to_globalpx(lon_max, lat_min, z)  # bottom-right
    tx0, ty0 = int(px0 // 256), int(py0 // 256)
    tx1, ty1 = int(px1 // 256), int(py1 // 256)
    tiles = [(tx, ty) for ty in range(ty0, ty1 + 1) for tx in range(tx0, tx1 + 1)]
    print(f"zoom {z}: tiles x {tx0}..{tx1}, y {ty0}..{ty1} ({len(tiles)} tiles)")
    H = (ty1 - ty0 + 1) * 256
    W = (tx1 - tx0 + 1) * 256
    mosaic = np.zeros((H, W), dtype=np.float64)
    for tx, ty in tiles:
        mosaic[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = get_tile(z, tx, ty)
    return mosaic, tx0 * 256, ty0 * 256, tiles


def bilinear(mosaic, gx, gy):
    H, W = mosaic.shape
    # pixel centres are at +0.5
    fx = np.clip(gx - 0.5, 0, W - 1.000001)
    fy = np.clip(gy - 0.5, 0, H - 1.000001)
    x0 = np.floor(fx).astype(int)
    y0 = np.floor(fy).astype(int)
    dx = fx - x0
    dy = fy - y0
    v00 = mosaic[y0, x0]
    v10 = mosaic[y0, x0 + 1]
    v01 = mosaic[y0 + 1, x0]
    v11 = mosaic[y0 + 1, x0 + 1]
    return (v00 * (1 - dx) * (1 - dy) + v10 * dx * (1 - dy) + v01 * (1 - dx) * dy + v11 * dx * dy)


def epqs(lat, lon):
    try:
        raw = fetch(EPQS_URL.format(lat=lat, lon=lon), timeout=20)
        j = json.loads(raw)
        v = float(j.get("value"))
        return None if v < -1000 else v
    except Exception as e:  # noqa: BLE001
        print(f"  EPQS cross-check unavailable at ({lat},{lon}): {e}", file=sys.stderr)
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zoom", type=int, default=13)
    ap.add_argument("--n", type=int, default=256)
    ap.add_argument("--no-epqs", action="store_true")
    args = ap.parse_args()
    z, n = args.zoom, args.n

    mosaic, gx_off, gy_off, tiles = build_mosaic(z, BBOX["west"], BBOX["south"], BBOX["east"], BBOX["north"])

    def sample(lat, lon):
        gx, gy = lonlat_to_globalpx(lon, lat, z)
        return bilinear(mosaic, np.asarray(gx) - gx_off, np.asarray(gy) - gy_off)

    # ENU extents: the largest axis-aligned ENU rectangle inside the lat/lon bbox
    xw, _ = ll_to_enu(ORIGIN["lat"], BBOX["west"])
    xe, _ = ll_to_enu(ORIGIN["lat"], BBOX["east"])
    _, ys = ll_to_enu(BBOX["south"], ORIGIN["lon"])
    _, yn = ll_to_enu(BBOX["north"], ORIGIN["lon"])
    x_min, x_max, y_min, y_max = xw, xe, ys, yn

    xs = np.linspace(x_min, x_max, n)
    ys_ = np.linspace(y_max, y_min, n)  # row 0 = north edge
    X, Y = np.meshgrid(xs, ys_)
    LAT, LON = enu_to_ll(X, Y)
    Z = sample(LAT, LON)

    water = Z <= WATER_THRESHOLD_M

    # tile ground resolution at origin latitude
    tile_res = 2 * math.pi * A * COS0 / (256 * 2 ** z)

    # validation
    site_z = float(sample(ORIGIN["lat"], ORIGIN["lon"]))
    mp_inside = BBOX["south"] <= MISSION_PEAK["lat"] <= BBOX["north"] and BBOX["west"] <= MISSION_PEAK["lon"] <= BBOX["east"]
    mp_z = float(sample(MISSION_PEAK["lat"], MISSION_PEAK["lon"])) if mp_inside else None
    # Peak of the native mosaic within 1 km of Mission Peak (grid cell may straddle the summit)
    mpx, mpy = lonlat_to_globalpx(MISSION_PEAK["lon"], MISSION_PEAK["lat"], z)
    r = int(math.ceil(1000 / tile_res))
    cx, cy = int(mpx - gx_off), int(mpy - gy_off)
    win = mosaic[max(cy - r, 0):cy + r + 1, max(cx - r, 0):cx + r + 1]
    mp_native_max = float(win.max()) if win.size else None

    imax = np.unravel_index(np.argmax(Z), Z.shape)
    imin = np.unravel_index(np.argmin(Z), Z.shape)
    hi = dict(lat=round(float(LAT[imax]), 5), lon=round(float(LON[imax]), 5),
              x=round(float(X[imax]), 1), y=round(float(Y[imax]), 1), z=round(float(Z[imax]), 1))
    lo = dict(lat=round(float(LAT[imin]), 5), lon=round(float(LON[imin]), 5),
              x=round(float(X[imin]), 1), y=round(float(Y[imin]), 1), z=round(float(Z[imin]), 1))

    epqs_site = epqs_mp = None
    if not args.no_epqs:
        epqs_site = epqs(ORIGIN["lat"], ORIGIN["lon"])
        epqs_mp = epqs(MISSION_PEAK["lat"], MISSION_PEAK["lon"])

    validation = {
        "site": {**ORIGIN, "z_m": round(site_z, 1), "usgs_epqs_z_m": None if epqs_site is None else round(epqs_site, 1)},
        "mission_peak": {**MISSION_PEAK, "inside_bbox": mp_inside,
                          "z_m_bilinear": None if mp_z is None else round(mp_z, 1),
                          "z_m_native_max_within_1km": None if mp_native_max is None else round(mp_native_max, 1),
                          "usgs_epqs_z_m": None if epqs_mp is None else round(epqs_mp, 1),
                          "reference": "Mission Peak summit 2,517 ft (767 m), USGS GNIS / https://en.wikipedia.org/wiki/Mission_Peak"},
        "grid_max": hi,
        "grid_min": lo,
        "water_cells": int(water.sum()),
        "water_fraction": round(float(water.mean()), 4),
    }

    out = {
        "source": "AWS Terrain Tiles (Tilezen/Mapzen terrarium PNG), " + TILE_URL.replace("{z}", str(z)) +
                  "; decoded elevation = R*256 + G + B/256 - 32768 (metres). In this area the underlying "
                  "dataset is USGS 3DEP/NED (Tilezen source list: https://github.com/tilezen/joerd/blob/master/docs/data-sources.md)",
        "license/attribution": "Terrain Tiles: USGS 3DEP/NED (public domain, U.S. Government); compiled by Mapzen/Tilezen, "
                               "hosted on AWS Open Data (https://registry.opendata.aws/terrain-tiles/). Attribution per "
                               "https://github.com/tilezen/joerd/blob/master/docs/attribution.md",
        "fetched_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tiles": {"zoom": z, "count": len(tiles), "list": [f"{z}/{x}/{y}" for x, y in tiles],
                  "native_ground_res_m_at_origin": round(tile_res, 2)},
        "bbox_deg": BBOX,
        "origin": ORIGIN,
        "projection": "local ENU equirectangular, x east m, y north m",
        "projection_detail": "x = dlon_rad * N(lat0) * cos(lat0); y = dlat_rad * M(lat0); WGS84 radii at lat0 "
                             f"(M={M0:.1f} m, N={N0:.1f} m). Grid is the ENU rectangle spanning the bbox edges through the origin.",
        "vertical_datum": "As delivered by Terrain Tiles (3DEP is NAVD88, metres); treat as approximate orthometric height. "
                          "Bay/salt-pond surfaces are encoded near 0 m; values are bare-earth/water-surface, not buildings.",
        "resampling": "bilinear in Web-Mercator pixel space of the zoom-%d mosaic" % z,
        "layout": "row-major, row 0 = north edge (y = y_max), column 0 = west edge (x = x_min); "
                  "heights[r*nx + c] at x = x_min + c*dx, y = y_max - r*dy",
        "nx": n, "ny": n,
        "dx_m": round((x_max - x_min) / (n - 1), 3),
        "dy_m": round((y_max - y_min) / (n - 1), 3),
        "x_min": round(x_min, 1), "x_max": round(x_max, 1),
        "y_min": round(y_min, 1), "y_max": round(y_max, 1),
        "z_min": round(float(Z.min()), 1), "z_max": round(float(Z.max()), 1),
        "water_threshold_m": WATER_THRESHOLD_M,
        "water_note": "water = elevation <= 0.5 m. ASSUMED heuristic: flags Bay, salt ponds and sloughs encoded near "
                      "sea level; also flags any dry land at <= 0.5 m (levee-protected marsh), so it is an approximate "
                      "shoreline mask, not a surveyed one.",
        "validation": validation,
        "heights": [round(float(v), 1) for v in Z.ravel()],
        "water": [bool(v) for v in water.ravel()],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, separators=(",", ":"))

    print(json.dumps({k: out[k] for k in ("nx", "ny", "dx_m", "dy_m", "x_min", "x_max", "y_min", "y_max",
                                           "z_min", "z_max")}, indent=1))
    print(json.dumps(validation, indent=1))
    print("wrote", OUT, f"({os.path.getsize(OUT) / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
