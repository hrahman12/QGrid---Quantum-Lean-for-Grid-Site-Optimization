#!/usr/bin/env python3
"""
fetch_osm.py -- pull real transmission/distribution grid geometry for the
North San Jose / Alviso study area from the OpenStreetMap Overpass API and
write a compact, render-ready JSON (data/osm_grid_alviso.json).

Discipline (QSiteProof / CryoLean rule): every coordinate and tag in the output
comes verbatim from OpenStreetMap (ODbL). Nothing is invented. Fields that OSM
does not carry are emitted as null, never guessed. Unit conversions (feet ->
metres for height tags) are flagged in the output.

Usage:
    python tools/fetch_osm.py            # fetch (uses raw cache if present)
    python tools/fetch_osm.py --refresh  # ignore cache, re-query Overpass

Raw Overpass responses are cached in data/osm_raw/<feature>.json so the build
is reproducible offline.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
VIZ = os.path.dirname(HERE)
DATA = os.path.join(VIZ, "data")
RAW = os.path.join(DATA, "osm_raw")
OUT = os.path.join(DATA, "osm_grid_alviso.json")

# Study bbox (south, west, north, east) -- set by the QSiteProof task spec.
BBOX = (37.33, -122.06, 37.52, -121.85)
SITE = {"lat": 37.4275, "lon": -121.9650, "note": "QSiteProof 150 MW candidate site (task spec)"}

MIRRORS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]
UA = "QSiteProof-hack/0.1 (research prototype)"

B = "{},{},{},{}".format(*BBOX)
# Small, feature-split queries (keeps each request light on public mirrors).
QUERIES = {
    "lines": f'[out:json][timeout:120];way["power"~"^(line|cable|minor_line)$"]({B});out body geom;',
    "towers": f'[out:json][timeout:120];node["power"~"^(tower|pole)$"]({B});out body;',
    "substations": f'[out:json][timeout:120];(way["power"="substation"]({B});relation["power"="substation"]({B}););out body geom;',
    "transformers": f'[out:json][timeout:120];nwr["power"="transformer"]({B});out body center;',
    "data_centers": f'[out:json][timeout:120];(nwr["building"~"^data_cent(er|re)$"]({B});nwr["telecom"~"^data_cent(er|re)$"]({B}););out body geom;',
    "plants": f'[out:json][timeout:120];nwr["power"="plant"]({B});out body geom;',
    "generators": f'[out:json][timeout:120];nwr["power"="generator"]({B});out body center;',
}

failures: list[str] = []


# ----------------------------------------------------------------------------
# Fetch
# ----------------------------------------------------------------------------
def overpass(name: str, query: str, refresh: bool) -> dict | None:
    os.makedirs(RAW, exist_ok=True)
    cache = os.path.join(RAW, f"{name}.json")
    if not refresh and os.path.exists(cache):
        with open(cache, "r", encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict) and "elements" in d:
            print(f"[cache] {name}: {len(d['elements'])} elements")
            return d
    body = urllib.parse.urlencode({"data": query}).encode()
    for attempt in range(3):
        for url in MIRRORS:
            try:
                req = urllib.request.Request(url, data=body, headers={
                    "User-Agent": UA,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                })
                with urllib.request.urlopen(req, timeout=180) as r:
                    raw = r.read().decode("utf-8")
                d = json.loads(raw)  # raises on HTML error pages
                if "elements" not in d:
                    raise ValueError("no 'elements' key")
                if d.get("remark") and "error" in d["remark"].lower():
                    raise ValueError("overpass remark: " + d["remark"][:200])
                d["_fetched_from"] = url
                d["_query"] = query
                with open(cache, "w", encoding="utf-8") as f:
                    json.dump(d, f)
                print(f"[ok]    {name}: {len(d['elements'])} elements from {url}")
                return d
            except (urllib.error.URLError, urllib.error.HTTPError, ValueError,
                    json.JSONDecodeError, TimeoutError, OSError) as e:
                msg = f"{name} attempt {attempt + 1} {url}: {type(e).__name__}: {str(e)[:160]}"
                print("[fail]  " + msg, file=sys.stderr)
                failures.append(msg)
        time.sleep(5 * (2 ** attempt))  # 5 s, 10 s, 20 s backoff
    failures.append(f"{name}: ALL MIRRORS FAILED after retries -- feature omitted, nothing fabricated")
    return None


# ----------------------------------------------------------------------------
# Parsing helpers (no guessing: unparsable -> None)
# ----------------------------------------------------------------------------
def parse_kv(v: str | None) -> list[float]:
    """OSM voltage tag is volts, ';'-separated for multiple circuits."""
    if not v:
        return []
    out = []
    for p in re.split(r"[;,]", v):
        p = p.strip()
        try:
            kv = float(p) / 1000.0
            out.append(int(kv) if kv.is_integer() else round(kv, 3))
        except ValueError:
            pass
    return sorted(set(out), reverse=True)


def parse_int_list(v: str | None):
    if v is None:
        return None
    vals = []
    for p in re.split(r"[;,]", v):
        try:
            vals.append(int(p.strip()))
        except ValueError:
            return v  # keep raw string rather than invent
    return vals[0] if len(vals) == 1 else vals


def parse_height(v: str | None):
    """Return (metres, note). OSM default unit is metres; feet are converted."""
    if not v:
        return None, None
    s = v.strip().lower()
    m = re.fullmatch(r"([0-9]*\.?[0-9]+)\s*(m|meters?|metres?)?", s)
    if m:
        return float(m.group(1)), None
    m = re.fullmatch(r"([0-9]*\.?[0-9]+)\s*(ft|feet|')", s)
    if m:
        return round(float(m.group(1)) * 0.3048, 2), f"converted from '{v}' (ft x 0.3048)"
    m = re.fullmatch(r"(\d+)'\s*(\d+)\"?", s)
    if m:
        return round(int(m.group(1)) * 0.3048 + int(m.group(2)) * 0.0254, 2), f"converted from '{v}'"
    return None, f"unparsed height tag '{v}'"


def hav_km(a, b):
    R = 6371.0088
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def polyline_km(coords):
    return sum(hav_km(coords[i], coords[i + 1]) for i in range(len(coords) - 1))


def geom_coords(geom):
    return [[round(g["lat"], 7), round(g["lon"], 7)] for g in geom if g]


def stitch_outer(members):
    """Stitch relation 'outer' member ways into closed rings (largest first)."""
    segs = [geom_coords(m.get("geometry", [])) for m in members
            if m.get("type") == "way" and m.get("role", "outer") in ("outer", "") and m.get("geometry")]
    rings = []
    while segs:
        ring = segs.pop(0)
        changed = True
        while changed and ring[0] != ring[-1]:
            changed = False
            for i, s in enumerate(segs):
                if s[0] == ring[-1]:
                    ring += s[1:]
                elif s[-1] == ring[-1]:
                    ring += s[::-1][1:]
                elif s[-1] == ring[0]:
                    ring = s[:-1] + ring
                elif s[0] == ring[0]:
                    ring = s[::-1][:-1] + ring
                else:
                    continue
                segs.pop(i)
                changed = True
                break
        rings.append(ring)
    rings.sort(key=len, reverse=True)
    return rings


def point_in_poly(lat, lon, poly):
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        yi, xi = poly[i]
        yj, xj = poly[j]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-15) + xi):
            inside = not inside
        j = i
    return inside


def centroid(poly):
    if not poly:
        return None
    return [round(sum(p[0] for p in poly) / len(poly), 7), round(sum(p[1] for p in poly) / len(poly), 7)]


def elem_point(e):
    if e["type"] == "node":
        return e.get("lat"), e.get("lon")
    c = e.get("center")
    if c:
        return c["lat"], c["lon"]
    g = e.get("geometry")
    if g:
        cc = centroid(geom_coords(g))
        return cc[0], cc[1]
    b = e.get("bounds")
    if b:
        return (b["minlat"] + b["maxlat"]) / 2, (b["minlon"] + b["maxlon"]) / 2
    return None, None


def elem_polygon(e):
    if e["type"] == "way" and e.get("geometry"):
        return geom_coords(e["geometry"])
    if e["type"] == "relation":
        rings = stitch_outer(e.get("members", []))
        return rings[0] if rings else []
    return []


def pick(tags, keys):
    return {k: tags[k] for k in keys if k in tags}


# ----------------------------------------------------------------------------
# Build
# ----------------------------------------------------------------------------
def build(refresh: bool):
    raw = {k: overpass(k, q, refresh) for k, q in QUERIES.items()}
    E = {k: (v["elements"] if v else []) for k, v in raw.items()}

    # ---- lines ----
    node_to_lines: dict[int, list[int]] = defaultdict(list)
    lines = []
    for w in E["lines"]:
        if w["type"] != "way":
            continue
        t = w.get("tags", {})
        coords = geom_coords(w.get("geometry", []))
        nodes = w.get("nodes", [])
        for n in nodes:
            node_to_lines[n].append(w["id"])
        lines.append({
            "osm_id": w["id"],
            "power": t.get("power"),
            "kv": parse_kv(t.get("voltage")),
            "voltage_raw": t.get("voltage"),
            "circuits": parse_int_list(t.get("circuits")),
            "cables": parse_int_list(t.get("cables")),
            "wires": t.get("wires"),
            "frequency": t.get("frequency"),
            "name": t.get("name"),
            "operator": t.get("operator"),
            "ref": t.get("ref"),
            "line": t.get("line"),            # e.g. busbar / bay
            "location": t.get("location"),    # e.g. underground / overhead
            "layer": t.get("layer"),
            "length_km": round(polyline_km(coords), 4),
            "coords": coords,
            "node_ids": nodes,
            "tags": pick(t, ["design", "structure", "material", "cables", "wires", "line_management",
                              "note", "description", "source", "start_date", "operator:short"]),
        })

    # ---- towers / poles ----
    towers = []
    height_notes = []
    for n in E["towers"]:
        if n["type"] != "node":
            continue
        t = n.get("tags", {})
        h, hn = parse_height(t.get("height"))
        if hn:
            height_notes.append({"osm_id": n["id"], "note": hn})
        towers.append({
            "osm_id": n["id"],
            "lat": round(n["lat"], 7),
            "lon": round(n["lon"], 7),
            "type": t.get("power"),
            "design": t.get("design"),
            "structure": t.get("structure"),
            "material": t.get("material"),
            "height_m": h,
            "height_raw": t.get("height"),
            "line_attachment": t.get("line_attachment"),
            "line_management": t.get("line_management"),
            "ref": t.get("ref"),
            "operator": t.get("operator"),
            "line_ids": sorted(set(node_to_lines.get(n["id"], []))),
        })
    tower_ids = {tw["osm_id"] for tw in towers}
    for ln in lines:
        ln["tower_node_ids"] = [nid for nid in ln["node_ids"] if nid in tower_ids]
        del ln["node_ids"]

    # ---- transformers (assigned to substations by point-in-polygon) ----
    xfmrs = []
    for e in E["transformers"]:
        t = e.get("tags", {})
        lat, lon = elem_point(e)
        if lat is None:
            continue
        xfmrs.append({
            "osm_id": e["id"], "osm_type": e["type"], "lat": round(lat, 7), "lon": round(lon, 7),
            "kv": parse_kv(t.get("voltage")), "voltage_raw": t.get("voltage"),
            "rating": t.get("rating"), "transformer": t.get("transformer"),
            "phases": t.get("phases"), "name": t.get("name"), "ref": t.get("ref"),
            "frequency": t.get("frequency"),
        })

    # ---- substations ----
    substations = []
    for e in E["substations"]:
        t = e.get("tags", {})
        poly = elem_polygon(e)
        inside = [x for x in xfmrs if poly and point_in_poly(x["lat"], x["lon"], poly)]
        for x in inside:
            x["substation_osm_id"] = e["id"]
        substations.append({
            "osm_id": e["id"], "osm_type": e["type"],
            "name": t.get("name"), "ref": t.get("ref"),
            "kv": parse_kv(t.get("voltage")), "voltage_raw": t.get("voltage"),
            "substation": t.get("substation"), "operator": t.get("operator"),
            "location": t.get("location"),
            "centroid": centroid(poly),
            "area_m2": round(poly_area_m2(poly), 1) if len(poly) > 2 else None,
            "polygon": poly,
            "transformers": inside,
        })

    # ---- data centers ----
    data_centers = []
    for e in E["data_centers"]:
        t = e.get("tags", {})
        lat, lon = elem_point(e)
        poly = elem_polygon(e)
        h, hn = parse_height(t.get("height"))
        data_centers.append({
            "osm_id": e["id"], "osm_type": e["type"], "name": t.get("name"),
            "operator": t.get("operator"), "building": t.get("building"), "telecom": t.get("telecom"),
            "height_m": h, "height_raw": t.get("height"), "height_note": hn,
            "levels": t.get("building:levels"),
            "lat": round(lat, 7) if lat else None, "lon": round(lon, 7) if lon else None,
            "footprint_m2": round(poly_area_m2(poly), 1) if len(poly) > 2 else None,
            "polygon": poly,
            "addr": " ".join(filter(None, [t.get("addr:housenumber"), t.get("addr:street"), t.get("addr:city")])) or None,
        })

    # ---- plants + generators ----
    plants = []
    for e in E["plants"]:
        t = e.get("tags", {})
        lat, lon = elem_point(e)
        poly = elem_polygon(e)
        plants.append({
            "osm_id": e["id"], "osm_type": e["type"], "kind": "plant", "name": t.get("name"),
            "operator": t.get("operator"), "source": t.get("plant:source"), "method": t.get("plant:method"),
            "output_electricity": t.get("plant:output:electricity"),
            "lat": round(lat, 7) if lat else None, "lon": round(lon, 7) if lon else None,
            "polygon": poly,
        })
    generators = []
    for e in E["generators"]:
        t = e.get("tags", {})
        lat, lon = elem_point(e)
        generators.append({
            "osm_id": e["id"], "osm_type": e["type"], "kind": "generator", "name": t.get("name"),
            "operator": t.get("operator"), "source": t.get("generator:source"),
            "method": t.get("generator:method"),
            "output_electricity": t.get("generator:output:electricity"),
            "lat": round(lat, 7) if lat else None, "lon": round(lon, 7) if lon else None,
        })

    # ---- stats ----
    kv_count, kv_km = Counter(), Counter()
    for ln in lines:
        key = "/".join(str(k) for k in ln["kv"]) if ln["kv"] else "untagged"
        kv_count[key] += 1
        kv_km[key] += ln["length_km"]
    by_name = defaultdict(lambda: {"segments": 0, "km": 0.0, "kv": set(), "operator": None})
    for ln in lines:
        if ln["name"]:
            r = by_name[ln["name"]]
            r["segments"] += 1
            r["km"] += ln["length_km"]
            r["kv"].update(ln["kv"])
            r["operator"] = r["operator"] or ln["operator"]
    top_named = sorted(by_name.items(), key=lambda kv: -kv[1]["km"])[:10]

    stats = {
        "lines_total": len(lines),
        "lines_by_power": dict(Counter(l["power"] for l in lines)),
        "lines_km_total": round(sum(l["length_km"] for l in lines), 2),
        "lines_by_kv_count": dict(sorted(kv_count.items(), key=lambda x: -x[1])),
        "lines_by_kv_km": {k: round(v, 2) for k, v in sorted(kv_km.items(), key=lambda x: -x[1])},
        "lines_with_circuits_tag": sum(1 for l in lines if l["circuits"] is not None),
        "lines_with_cables_tag": sum(1 for l in lines if l["cables"] is not None),
        "lines_with_name": sum(1 for l in lines if l["name"]),
        "lines_underground_or_cable": sum(1 for l in lines if l["power"] == "cable" or l["location"] == "underground"),
        "towers_total": len(towers),
        "towers_by_type": dict(Counter(t["type"] for t in towers)),
        "towers_on_fetched_lines": sum(1 for t in towers if t["line_ids"]),
        "towers_with_design": sum(1 for t in towers if t["design"]),
        "towers_with_height": sum(1 for t in towers if t["height_m"] is not None),
        "towers_with_structure": sum(1 for t in towers if t["structure"]),
        "towers_with_material": sum(1 for t in towers if t["material"]),
        "towers_with_line_attachment": sum(1 for t in towers if t["line_attachment"]),
        "tower_design_values": dict(Counter(t["design"] for t in towers if t["design"]).most_common(15)),
        "tower_structure_values": dict(Counter(t["structure"] for t in towers if t["structure"]).most_common(15)),
        "tower_material_values": dict(Counter(t["material"] for t in towers if t["material"]).most_common(15)),
        "tower_height_m_min_max": (
            [min(h for h in hs), max(h for h in hs)] if (hs := [t["height_m"] for t in towers if t["height_m"] is not None]) else None),
        "height_unit_notes": height_notes[:50],
        "substations_total": len(substations),
        "substations_named": sum(1 for s in substations if s["name"]),
        "substations_with_polygon": sum(1 for s in substations if len(s["polygon"]) > 2),
        "transformers_total": len(xfmrs),
        "transformers_inside_substations": sum(1 for x in xfmrs if "substation_osm_id" in x),
        "transformers_with_rating": sum(1 for x in xfmrs if x["rating"]),
        "data_centers_total": len(data_centers),
        "data_centers_with_height_or_levels": sum(1 for d in data_centers if d["height_m"] or d["levels"]),
        "plants_total": len(plants),
        "generators_total": len(generators),
        "generators_by_source": dict(Counter(g["source"] for g in generators)),
        "top10_named_lines_by_km": [
            {"name": n, "segments": r["segments"], "km": round(r["km"], 2),
             "kv": sorted(r["kv"], reverse=True), "operator": r["operator"]} for n, r in top_named],
        "fetch_failures": failures,
    }

    timestamps = {k: (v.get("osm3s", {}).get("timestamp_osm_base") if v else None) for k, v in raw.items()}
    mirrors_used = {k: (v.get("_fetched_from") if v else None) for k, v in raw.items()}
    out = {
        "source": "OpenStreetMap contributors, ODbL (https://www.openstreetmap.org/copyright)",
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "osm_base_timestamps": timestamps,
        "mirrors_used": mirrors_used,
        "bbox": {"south": BBOX[0], "west": BBOX[1], "north": BBOX[2], "east": BBOX[3]},
        "site": SITE,
        "provenance_notes": [
            "All geometry and tags are verbatim OSM; no coordinates, voltages or ratings are synthesised.",
            "kv = OSM 'voltage' tag / 1000 (OSM stores volts). Empty list = untagged in OSM, not zero.",
            "height_m: OSM default unit is metres; feet values converted x0.3048 and listed in stats.height_unit_notes.",
            "Fields absent from OSM are null. OSM completeness for tower design/height in this area is partial; "
            "use stats.towers_with_* to see coverage before drawing per-tower 3D models.",
            "Line geometry is the full way (may extend past bbox); towers are only those inside bbox.",
            "Transformers are linked to substations by point-in-polygon on the substation outer ring.",
            "OSM is not a utility record: absence of a feature does not mean it does not exist.",
        ],
        "lines": lines,
        "towers": towers,
        "substations": substations,
        "transformers": xfmrs,
        "data_centers": data_centers,
        "plants": plants + generators,
        "stats": stats,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
    return out


def poly_area_m2(poly):
    """Shoelace on a local equirectangular projection (fine at substation scale)."""
    if len(poly) < 3:
        return 0.0
    lat0 = math.radians(sum(p[0] for p in poly) / len(poly))
    R = 6371008.8
    xy = [(math.radians(p[1]) * R * math.cos(lat0), math.radians(p[0]) * R) for p in poly]
    a = 0.0
    for i in range(len(xy)):
        x1, y1 = xy[i]
        x2, y2 = xy[(i + 1) % len(xy)]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="ignore raw cache and re-query Overpass")
    args = ap.parse_args()
    o = build(args.refresh)
    s = o["stats"]
    print(json.dumps({k: v for k, v in s.items() if k != "height_unit_notes"}, indent=1, default=str))
    print(f"wrote {OUT} ({os.path.getsize(OUT) / 1e6:.2f} MB)")
    if s["fetch_failures"]:
        print(f"WARNING: {len(s['fetch_failures'])} fetch failure messages (see stats.fetch_failures)", file=sys.stderr)
