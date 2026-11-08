"""One-shot cache builder for data/l1/ (L1). Run: python grid/fetch_data.py [osm|hifld|wri|eia ...]

Patterns copied from SeaBridgeAI manageesg-backend app/services/esg_data/power_grid.py (not imported).
Writes GeoJSON next to this repo's data/l1/ so L2 and the offline demo can use it without the network.
"""
from __future__ import annotations

import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

DATA = Path(__file__).resolve().parents[1] / "data" / "l1"
CENTER = (37.43, -121.97)  # Alviso / North San Jose, per the case study
RADIUS_KM = 25.0
UA = {"User-Agent": "QSiteProof-hackday/0.1 (SeaBridgeAI L1)"}
OVERPASS = ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
            "https://overpass.private.coffee/api/interpreter")
HIFLD_TRANSMISSION = ("https://services1.arcgis.com/Hp6G80Pky0om7QvQ/arcgis/rest/services/"
                      "Electric_Power_Transmission_Lines/FeatureServer/0/query")
KEEP = ("name", "operator", "power", "voltage", "substation", "circuits", "cables", "ref", "telecom", "building")


def bbox(center=CENTER, km=RADIUS_KM):
    lat, lon = center
    dlat, dlon = km / 111.0, km / (111.0 * math.cos(math.radians(lat)))
    return (lat - dlat, lon - dlon, lat + dlat, lon + dlon)  # S, W, N, E


def _write(name, features, source, extra=None):
    DATA.mkdir(parents=True, exist_ok=True)
    fc = {"type": "FeatureCollection", "features": features,
          "properties": {"source": source, "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         "bbox_swne": bbox(), **(extra or {})}}
    (DATA / name).write_text(json.dumps(fc), encoding="utf-8")
    print(f"wrote data/l1/{name}: {len(features)} features")


def overpass(query):
    for attempt in range(3):  # public mirrors rate-limit (429); back off between rounds
        for url in OVERPASS:
            try:
                r = requests.post(url, data={"data": query}, headers=UA, timeout=90)
                r.raise_for_status()
                return r.json().get("elements", [])
            except (requests.RequestException, ValueError) as e:
                print(f"  overpass {url.split('/')[2]} failed: {type(e).__name__}")
        time.sleep(15)
    raise RuntimeError("all Overpass endpoints failed")


def _feature(el):
    tags = {k: v for k, v in (el.get("tags") or {}).items() if k in KEEP}
    tags["osm_id"] = f"{el['type']}/{el['id']}"
    if el["type"] == "node":
        geom = {"type": "Point", "coordinates": [el["lon"], el["lat"]]}
    elif el.get("geometry"):
        geom = {"type": "LineString", "coordinates": [[p["lon"], p["lat"]] for p in el["geometry"]]}
    elif el.get("center"):
        geom = {"type": "Point", "coordinates": [el["center"]["lon"], el["center"]["lat"]]}
    else:
        return None
    return {"type": "Feature", "properties": tags, "geometry": geom}


def fetch_osm():
    s, w, n, e = bbox()
    box = f"({s},{w},{n},{e})"
    osm = "OpenStreetMap (Overpass API), (c) OpenStreetMap contributors, ODbL-1.0"
    for name, sel, out in (
        ("osm_substations_alviso.geojson", f'nwr["power"="substation"]{box}', "center tags 1000"),
        ("osm_power_lines_alviso.geojson", f'way["power"="line"]{box}', "geom tags 2000"),
        ("osm_datacenters_alviso.geojson",
         f'nwr["telecom"="data_center"]{box};nwr["building"="data_center"]{box};nwr["industrial"="data_centre"]{box}',
         "center tags 500"),
    ):
        try:
            els = overpass(f"[out:json][timeout:80];({sel};);out {out};")
        except RuntimeError as e:
            print(f"{name} FAILED: {e}")
            continue
        _write(name, [f for f in map(_feature, els) if f], osm)
        time.sleep(5)


def fetch_hifld():
    s, w, n, e = bbox()
    params = {"where": "1=1", "geometry": f"{w},{s},{e},{n}", "geometryType": "esriGeometryEnvelope", "inSR": 4326,
              "spatialRel": "esriSpatialRelIntersects", "outFields": "*", "outSR": 4326, "f": "geojson",
              "resultRecordCount": 500}
    r = requests.get(HIFLD_TRANSMISSION, params=params, headers=UA, timeout=60)
    r.raise_for_status()
    body = r.json()
    if "features" not in body:
        raise RuntimeError(f"HIFLD returned no features key: {str(body)[:200]}")
    _write("hifld_transmission_alviso.geojson", body["features"], "HIFLD Transmission Lines (ArcGIS FeatureServer)")


STEPS = {"osm": fetch_osm, "hifld": fetch_hifld}
# WRI Aqueduct (service gone from the ArcGIS org, 400 Invalid URL) and EIA-860 (v2 API has no county/lat-lon) skipped, see SOURCES.md

if __name__ == "__main__":
    for step in sys.argv[1:] or STEPS:
        try:
            STEPS[step]()
        except Exception as e:  # keep going: one dead source must not block the others
            print(f"{step} FAILED: {type(e).__name__}: {str(e).split('api_key=')[0][:200]}")
