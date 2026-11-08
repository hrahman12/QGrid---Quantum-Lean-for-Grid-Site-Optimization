"""Build data/l2/site_risk.json: flood and wildfire flags at the Alviso site and nearby GRIP substations.

Offline from caches:
  data/l2/cache/flood_points_alviso.json   FEMA flood zones (NFHL) via Esri Living Atlas
      "USA Flood Hazard Areas" (USA_Flood_Hazard_Reduced_Set_gdb FeatureServer/0), point queries,
      pulled 2026-11-08. hazards.fema.gov itself failed the TLS handshake from this host.
  data/shared/grip/raw/layer_18.geojson    PG&E GRIP High Fire-Threat Districts in the GRIP bbox
      (-122.02,37.36,-121.88,37.46), CPUC/Cal Fire HFTD

Flags (for an optional Lean rule; context, not a permit decision):
  flood.sfha            True if FEMA Special Flood Hazard Area (zones A*, V*): equipment must sit above
                        the base flood elevation (BFE) -> permit/cost condition, not an automatic block
  fire.in_hftd_tier2_3  True if inside CPUC HFTD Tier 2 or 3 (elevated/extreme): PSPS shutoff exposure
  fire.in_hftd_any      True if inside any HFTD polygon in the bbox (Tier 1 = Zone 1 HHZ is not elevated)

Usage: python data/l2/build_site_risk.py
"""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FLOOD = HERE / "cache" / "flood_points_alviso.json"
HFTD = ROOT / "data" / "shared" / "grip" / "raw" / "layer_18.geojson"
OUT = HERE / "site_risk.json"


def in_ring(lon, lat, ring):
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def polygons(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    if geom["type"] == "MultiPolygon":
        return geom["coordinates"]
    return []


def in_geom(lon, lat, geom):
    return any(in_ring(lon, lat, p[0]) and not any(in_ring(lon, lat, h) for h in p[1:]) for p in polygons(geom))


def km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(a))


def nearest_km(lat, lon, geom):
    return min(km(lat, lon, y, x) for p in polygons(geom) for ring in p for x, y in ring)


def flood_flags(features):
    if not features:
        return {"zone": None, "sfha": False, "bfe_ft": None, "label": "not in a mapped FEMA flood hazard area (reduced set omits minimal-risk Zone X)"}
    a = max(features, key=lambda f: f.get("SFHA_TF") == "T")  # worst zone if several
    return {"zone": a.get("FLD_ZONE"), "subtype": a.get("ZONE_SUBTY"), "sfha": a.get("SFHA_TF") == "T",
            "bfe_ft": a.get("STATIC_BFE") if a.get("STATIC_BFE") not in (None, -9999) else None,
            "label": a.get("esri_symbology"), "dfirm_id": a.get("DFIRM_ID")}


def main():
    flood = json.loads(FLOOD.read_text(encoding="utf-8"))
    hftd = json.loads(HFTD.read_text(encoding="utf-8"))["features"]
    points = []
    for p in flood["points"]:
        fire_hits = [f["properties"] for f in hftd if f.get("geometry") and in_geom(p["lon"], p["lat"], f["geometry"])]
        near = [(nearest_km(p["lat"], p["lon"], f["geometry"]), f["properties"]) for f in hftd if f.get("geometry")]
        d, props = min(near, key=lambda t: t[0]) if near else (None, {})
        tiers = [h.get("cpuc_tier") for h in fire_hits]
        fl = flood_flags(p["features"])
        points.append({
            "kind": p["kind"], "id": p["id"], "name": p["name"], "lat": p["lat"], "lon": p["lon"],
            "flood": fl,
            "fire": {"in_hftd_any": bool(fire_hits), "in_hftd_tier2_3": any(t in (2, 3) for t in tiers),
                     "tiers": tiers, "nearest_hftd_km": None if d is None else round(d, 2),
                     "nearest_hftd": {k: props.get(k) for k in ("hftd", "cpuc_tier", "cpuc_fire_map")} if props else None},
            "flags": [f for f, on in (("FLOOD_SFHA", fl["sfha"]), ("FIRE_HFTD_TIER2_3", any(t in (2, 3) for t in tiers))) if on],
        })
    site = points[0]
    doc = {
        "site_id": site["id"],
        "summary": {
            "site_flood_zone": site["flood"]["zone"], "site_in_sfha": site["flood"]["sfha"], "site_bfe_ft": site["flood"]["bfe_ft"],
            "site_in_hftd": site["fire"]["in_hftd_any"], "site_nearest_hftd_km": site["fire"]["nearest_hftd_km"],
            "grip_substations_in_sfha": [p["name"] for p in points[1:] if p["flood"]["sfha"]],
            "grip_substations_in_hftd_tier2_3": [p["name"] for p in points[1:] if p["fire"]["in_hftd_tier2_3"]],
        },
        "lean_rule_hint": ("FLOOD_SFHA -> permit condition: equipment elevated above BFE (+ freeboard), cost adder, not an automatic RED. "
                           "FIRE_HFTD_TIER2_3 -> PSPS shutoff exposure: availability < 100%. Neither is a utility determination."),
        "sources": {
            "flood": "FEMA NFHL flood hazard zones via Esri Living Atlas 'USA Flood Hazard Areas' (" + flood["source"] + "), point queries pulled " + flood["pulled"] + "; cached data/l2/cache/flood_points_alviso.json",
            "fire": "PG&E GRIP layer 18 HighFireThreatDistricts (CPUC HFTD, Cal Fire v22_3) in bbox -122.02,37.36,-121.88,37.46; cached data/shared/grip/raw/layer_18.geojson",
        },
        "caveats": [
            "Fire polygons cover only the GRIP bbox; Tier 2/3 areas in the eastern foothills lie outside it, so nearest_hftd_km is within the bbox only.",
            "Point checks at substation coordinates; an edge site on a feeder may sit in a different zone.",
            "hazards.fema.gov failed TLS from the VM, so the Esri mirror of NFHL was used.",
        ],
        "points": points,
    }
    OUT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(doc["summary"], indent=1))
    for p in points:
        print(f"  {p['name'][:30]:30} flood {p['flood']['zone']} sfha={p['flood']['sfha']} | fire in={p['fire']['in_hftd_any']} nearest {p['fire']['nearest_hftd_km']} km | {p['flags']}")


if __name__ == "__main__":
    main()
