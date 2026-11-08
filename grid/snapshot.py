"""Live grid snapshot around a site (L1): OSM substations + assumed ties + live ISO signal.

Substation/query logic adapted from SeaBridgeAI manageesg-backend app/services/esg_data/power_grid.py
(fetch_osm_power, _osm_feature); copied, not imported. Data (c) OpenStreetMap contributors, ODbL-1.0.
Every fetched response is cached under data/l1/ and read back when the network fails (demo runs offline).

ASSUMPTIONS (OSM has no ratings; none of these are measured):
  assumed_mva   from the highest OSM voltage via MVA_BY_KV (typical firm substation transformer capacity)
  headroom_mw   = assumed_mva * PF * (1 - UTIL): we assume 65% existing utilization at PF 0.95
  lines         NOT read from OSM: each substation is tied to its nearest neighbours (MST + 2nd-nearest),
                kV = lower of the two ends, rating from LINE_MVA_BY_KV, length = straight line * ROUTE_FACTOR
shortcut: ties are inferred, not traced from OSM power=line ways; upgrade by snapping OSM lines to substations.
"""
from __future__ import annotations

import csv
import json
import math
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

import requests

from .distribution import edge_sites, load_grip

DATA = Path(__file__).resolve().parents[1] / "data" / "l1"
OVERPASS = ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
            "https://overpass.private.coffee/api/interpreter")
UA = {"User-Agent": "QSiteProof-hackday/0.1 (SeaBridgeAI L1)"}
RADIUS_KM, MAX_SUBS, MIN_KV = 25.0, 5, 60.0
L2_RATINGS = Path(__file__).resolve().parents[1] / "data" / "l2" / "substation_ratings.json"
DLR_UPLIFT_PCT_DEFAULT = 15.0  # assumed when no L2 ratings exist for the site
PF, UTIL, ROUTE_FACTOR = 0.95, 0.65, 1.25
MVA_BY_KV = {66: 60, 69: 75, 115: 150, 138: 200, 230: 300, 345: 500, 500: 750}
LINE_MVA_BY_KV = {66: 80, 69: 90, 115: 200, 138: 250, 230: 450, 345: 900, 500: 1500}
ISO_TIMEOUT_S = 45


def _near(table, kv):
    return table[min(table, key=lambda k: abs(k - kv))]


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def _parse_kv(voltage):
    """OSM voltage is volts, possibly 'a;b'. Return the max in kV or None."""
    vals = [int(v) for v in re.findall(r"\d+", voltage or "")]
    return max(vals) / 1000 if vals else None


def _fetch_osm_substations(site):
    """Overpass substations within RADIUS_KM -> GeoJSON FeatureCollection; cached in data/l1/."""
    cache = DATA / f"osm_substations_{site['id']}.geojson"
    dlat = RADIUS_KM / 111.0
    dlon = RADIUS_KM / (111.0 * math.cos(math.radians(site["lat"])))
    box = f"({site['lat']-dlat},{site['lon']-dlon},{site['lat']+dlat},{site['lon']+dlon})"
    query = f'[out:json][timeout:25];nwr["power"="substation"]{box};out center tags 400;'
    for url in OVERPASS:
        try:
            r = requests.post(url, data={"data": query}, headers=UA, timeout=40)
            r.raise_for_status()
            feats = []
            for el in r.json().get("elements", []):
                c = el if el["type"] == "node" else el.get("center")
                if not c:
                    continue
                tags = {k: v for k, v in (el.get("tags") or {}).items()
                        if k in ("name", "operator", "voltage", "substation", "ref")}
                tags["osm_id"] = f"{el['type']}/{el['id']}"
                feats.append({"type": "Feature", "properties": tags,
                              "geometry": {"type": "Point", "coordinates": [c["lon"], c["lat"]]}})
            fc = {"type": "FeatureCollection", "features": feats,
                  "properties": {"source": "OpenStreetMap (Overpass API)", "license": "ODbL-1.0",
                                 "attribution": "(c) OpenStreetMap contributors",
                                 "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds")}}
            DATA.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(fc), encoding="utf-8")
            return fc, f"overpass:{url.split('/')[2]}"
        except (requests.RequestException, ValueError):
            continue
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8")), f"cache:{cache.name}"
    raise RuntimeError(f"Overpass failed on all endpoints and no cache at {cache}")


def _l2_ratings(site):
    """L2's substation_ratings.json when it covers this site (read-only; owned by lane L2), else None."""
    try:
        d = json.loads(L2_RATINGS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if d.get("site_id") == site["id"] else None


def pick_substations(fc, site, l2=None):
    """Nearest MAX_SUBS substations with a parsable voltage >= MIN_KV within RADIUS_KM; near-duplicates merged."""
    cands = []
    for f in fc["features"]:
        kv = _parse_kv(f["properties"].get("voltage"))
        lon, lat = f["geometry"]["coordinates"]
        d = haversine_km(site["lat"], site["lon"], lat, lon)
        if kv and kv >= MIN_KV and d <= RADIUS_KM:
            cands.append((d, -kv, f["properties"], lat, lon, kv))
    picked = []
    for d, _, props, lat, lon, kv in sorted(cands, key=lambda c: (c[0], c[1])):
        if any(haversine_km(lat, lon, p["lat"], p["lon"]) < 0.15 for p in picked):
            continue  # same physical yard mapped twice
        sid = "osm-" + props["osm_id"].replace("/", "-")  # same id scheme as data/l2/substation_ratings.json
        mva = _near(MVA_BY_KV, kv)
        picked.append({"id": sid, "name": props.get("name") or props.get("operator") or f"OSM substation {props['osm_id']}",
                       "lat": round(lat, 5), "lon": round(lon, 5), "kv": kv, "assumed_mva": mva,
                       "distance_km": round(d, 2), "headroom_mw": round(mva * PF * (1 - UTIL), 1)})
        if l2 and sid in l2:  # L2 ratings win; the table above only covers substations L2 lacks
            r = l2[sid]
            picked[-1].update(name=r["name"], assumed_mva=r["assumed_mva"], headroom_mw=r["headroom_mw"],
                              headroom_mw_n1_firm=r["headroom_mw_n1_firm"], rating_source="data/l2/substation_ratings.json")
        if len(picked) == MAX_SUBS:
            break
    return picked


def infer_lines(subs):
    """MST over distance plus each node's second-nearest neighbour (so single-line outages leave a path)."""
    n = len(subs)

    def dist(i, j):
        return haversine_km(subs[i]["lat"], subs[i]["lon"], subs[j]["lat"], subs[j]["lon"])

    edges, seen = set(), {0}
    while len(seen) < n:  # Prim
        i, j = min(((i, j) for i in seen for j in range(n) if j not in seen), key=lambda e: dist(*e))
        edges.add(tuple(sorted((i, j))))
        seen.add(j)
    for i in range(n):
        for j in sorted((j for j in range(n) if j != i), key=lambda j: dist(i, j))[:2]:
            edges.add(tuple(sorted((i, j))))
    lines = []
    for i, j in sorted(edges):
        kv = min(subs[i]["kv"], subs[j]["kv"])
        lines.append({"id": f"L-{subs[i]['id'][4:]}-{subs[j]['id'][4:]}", "from": subs[i]["id"], "to": subs[j]["id"],
                      "kv": kv, "rating_mva": _near(LINE_MVA_BY_KV, kv),
                      "length_km": round(max(0.1, dist(i, j) * ROUTE_FACTOR), 2)})
    return lines


def _try(fn):
    try:
        return fn()
    except Exception:  # gridstatus raises many types (HTTP, parsing); caller falls back to cache
        return None


def _with_timeout(fn, seconds):
    box = {}
    t = threading.Thread(target=lambda: box.update(v=_try(fn)), daemon=True)
    t.start()
    t.join(seconds)
    return box.get("v")


def _live_iso(iso_name):
    import gridstatus  # lazy: slow import, offline runs may not need it
    iso = getattr(gridstatus, iso_name)()
    load = iso.get_load("latest")
    row = load.iloc[-1]
    col = "Load" if "Load" in load.columns else [c for c in load.columns if c not in ("Time", "Interval Start", "Interval End")][0]
    out = {"load": float(row[col]), "timestamp": row["Time"].tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"), "lmp": None}
    try:
        lmp = iso.get_lmp("latest", market="REAL_TIME_5_MIN")
        out["lmp"] = float(lmp["LMP"].mean())
    except Exception:  # LMP is best-effort; some ISOs need location filters or keys
        pass
    return out


def iso_signal(iso_name):
    """Latest ISO load (MW) and LMP ($/MWh) via gridstatus; cached CSV when live fails."""
    import gridstatus
    cache = DATA / f"iso_{iso_name}_latest.csv"
    offline = os.environ.get("QSITE_OFFLINE") == "1"  # skip live calls; read caches only
    live = None if offline or not hasattr(gridstatus, iso_name) else _with_timeout(lambda: _live_iso(iso_name), ISO_TIMEOUT_S)
    if live:
        DATA.mkdir(parents=True, exist_ok=True)
        with cache.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["timestamp", "load", "lmp", "source"])
            w.writeheader()
            w.writerow({**live, "source": f"gridstatus:{iso_name}"})
        return {**live, "source": f"gridstatus:{iso_name}"}
    if cache.exists():
        with cache.open(encoding="utf-8") as f:
            row = next(csv.DictReader(f))

        def num(v):
            return float(v) if v not in ("", None) else None

        return {"lmp": num(row["lmp"]), "load": num(row["load"]), "timestamp": row["timestamp"],
                "source": f"cache:{cache.name} (originally {row['source']})"}
    return {"lmp": None, "load": None, "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": f"unavailable:{iso_name} (no live data, no cache)"}


def _l2_as_fc(l2):
    feats = [{"type": "Feature", "properties": {"osm_id": s["id"].replace("osm-", "", 1).replace("-", "/", 1),
                                                "name": s["name"], "voltage": str(int(max(s["voltages_kv"]) * 1000))},
              "geometry": {"type": "Point", "coordinates": [s["lon"], s["lat"]]}} for s in l2["substations"]]
    return {"type": "FeatureCollection", "features": feats}, "data/l2/substation_ratings.json (OSM substations)"


def get_snapshot(site):
    """site -> grid_snapshot (contracts/grid_snapshot.schema.json), plus an `assumptions` list."""
    l2 = _l2_ratings(site)
    if os.environ.get("QSITE_OFFLINE") == "1" or l2:  # L2 already holds the OSM pool for its site; no network needed
        cache = DATA / f"osm_substations_{site['id']}.geojson"
        fc, osm_src = _l2_as_fc(l2) if l2 else (json.loads(cache.read_text(encoding="utf-8")), f"cache:{cache.name}")
    else:
        fc, osm_src = _fetch_osm_substations(site)
    subs = pick_substations(fc, site, {s["id"]: s for s in l2["substations"]} if l2 else None)
    if not subs:
        raise RuntimeError(f"no OSM substations >= {MIN_KV} kV within {RADIUS_KM} km of {site['id']}")
    grip = load_grip()
    return {
        "site_id": site["id"], "substations": subs, "lines": infer_lines(subs) if len(subs) > 1 else [],
        "iso": iso_signal(site["iso"]),
        "dlr_uplift_pct": l2["dlr_uplift_pct"]["mid"] if l2 else DLR_UPLIFT_PCT_DEFAULT,
        **({"distribution": edge_sites(grip, site["requested_mw"])} if grip else {}),
        "assumptions": [
            f"substations: {osm_src}; (c) OpenStreetMap contributors (ODbL)",
            ("assumed_mva/headroom_mw from data/l2/substation_ratings.json (ASSUMED planning values, see its disclaimer); "
             if l2 else "") + f"fallback table {MVA_BY_KV}; headroom_mw = assumed_mva*{PF}*(1-{UTIL}) (assumed {UTIL:.0%} utilization)",
            "iso.lmp = mean of the ISO's real-time 5-min LMPs returned by gridstatus (CAISO: NP15/SP15/ZP26 hubs); load = latest system load MW",
            f"lines inferred (MST + 2nd-nearest), rating from kV table {LINE_MVA_BY_KV}, length = straight line x {ROUTE_FACTOR}",
        ],
    }
