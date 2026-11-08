"""Build data/l2/substation_ratings.json from the cached OSM pull plus a stated assumption table.

OSM gives location and voltage only. Transformer MVA, existing load and DLR uplift are NOT public
per substation, so every such number below is either tied to a cited source or labelled ASSUMED.
These are illustrative planning assumptions, not real PG&E substation ratings.

Usage: python data/l2/build_substation_ratings.py   (offline; reads data/l2/cache/)
"""
import json
import math
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
CACHE = HERE / "cache" / "osm_substations_alviso_25km.json"
OUT = HERE / "substation_ratings.json"

SITE = json.loads((ROOT / "fixtures" / "site.json").read_text(encoding="utf-8"))
RADIUS_KM = 25.0
POWER_FACTOR = 0.95  # ASSUMED, used to turn MVA into MW

SRC = {
    "osm": "OpenStreetMap power=substation via Overpass API, around:25000 of 37.4265,-121.9750, pulled 2026-11-08 (cache/osm_substations_alviso_25km.json), ODbL",
    "cpuc_nortech": "CPUC Negative Declaration, PG&E Nortech Substation: 'three 45 MVA 115 kV - 21 kV transformers' at full build-out, two installed in 1999. https://ia.cpuc.ca.gov/Environment/Info/esa/nortech/nortech_negdec.htm",
    "cpuc_losesteros": "CPUC Northeast San Jose Transmission Reinforcement project description: Los Esteros 'initially ... three 230/115 kV transmission transformers', 'ultimately, a fourth'; no MVA given. https://ia.cpuc.ca.gov/Environment/info/aspen/nesanjo/description.html",
    "doe_oncor_dlr": "DOE Smart Grid case study, Oncor DLR: 6-14% capacity above ambient-adjusted rating on 345 kV lines, 8-12% on 138 kV, available 84-91% of the time. https://www.energy.gov/sites/prod/files/2014/08/f18/Oncor-SGIG-case-study-May2014.pdf",
}

# Per voltage class: the transformation found at that class and the per-bank MVA we assume.
# 'status' is SOURCED only when the number is quoted from a document for that class.
VOLTAGE_CLASSES = {
    "500": {
        "transformation": "500/230 kV",
        "mva_per_bank": 1000, "banks": 2, "status": "ASSUMED",
        "basis": "Order-of-magnitude placeholder. No 500 kV substation lies within 25 km of the site, so it does not enter the snapshot.",
        "source": None,
    },
    "230": {
        "transformation": "230/115 kV",
        "mva_per_bank": 420, "banks": 3, "status": "ASSUMED",
        "basis": "Bank COUNT is sourced for Los Esteros (3 banks, 4th planned). Per-bank MVA is ASSUMED: no public per-bank rating found; 420 MVA is a planning placeholder for a large 230/115 kV bank.",
        "source": "cpuc_losesteros",
    },
    "115": {
        "transformation": "115/21 kV (distribution)",
        "mva_per_bank": 45, "banks": 2, "status": "SOURCED",
        "basis": "45 MVA per 115/21 kV bank quoted for PG&E Nortech (North San Jose, ~2 km from the site); 2 banks = initial install. Applied to every 115 kV substation, which is an ASSUMPTION outside Nortech.",
        "source": "cpuc_nortech",
    },
    "60": {
        "transformation": "60/12 kV (distribution)",
        "mva_per_bank": 25, "banks": 2, "status": "ASSUMED",
        "basis": "Placeholder: smaller than the sourced 115/21 kV 45 MVA bank. No public rating found.",
        "source": None,
    },
}

EXISTING_LOAD_PCT = {"low": 50, "mid": 65, "high": 80, "status": "ASSUMED",
                     "basis": "Existing load as % of transformer rating. No public loading data; mid case is used for headroom_mw."}
DLR_UPLIFT_PCT = {"low": 6, "mid": 10, "high": 14, "status": "SOURCED-RANGE",
                  "basis": "Range from the Oncor DOE DLR case study (lines, not transformers). Applying it to lines near Alviso is ASSUMED.",
                  "source": "doe_oncor_dlr"}

EXCLUDE_OPERATORS = {"Caltrain", "San Francisco Bay Area Rapid Transit District"}


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def parse_kv(voltage):
    out = []
    for v in (voltage or "").split(";"):
        try:
            out.append(int(v.strip()) / 1000)
        except ValueError:
            pass
    return sorted(set(out), reverse=True)


def class_for(kv):
    for c in ("500", "230", "115", "60"):
        if kv >= int(c) * 0.9:
            return c
    return None


def build():
    raw = json.loads(CACHE.read_text(encoding="utf-8"))["elements"]
    subs, skipped = [], {"unnamed": 0, "no_voltage_or_below_60kv": 0, "traction_or_rail": 0, "outside_radius": 0}
    for el in raw:
        t = el.get("tags", {})
        lat = el.get("lat", el.get("center", {}).get("lat"))
        lon = el.get("lon", el.get("center", {}).get("lon"))
        kvs = parse_kv(t.get("voltage"))
        if t.get("substation") == "traction" or t.get("operator") in EXCLUDE_OPERATORS:
            skipped["traction_or_rail"] += 1
            continue
        if not t.get("name"):
            skipped["unnamed"] += 1
            continue
        if not kvs or kvs[0] < 54:
            skipped["no_voltage_or_below_60kv"] += 1
            continue
        dist = haversine_km(SITE["lat"], SITE["lon"], lat, lon)
        if dist > RADIUS_KM:
            skipped["outside_radius"] += 1
            continue
        cls = class_for(kvs[0])
        vc = VOLTAGE_CLASSES[cls]
        mva = vc["mva_per_bank"] * vc["banks"]
        load_frac = EXISTING_LOAD_PCT["mid"] / 100
        headroom = mva * POWER_FACTOR * (1 - load_frac)
        n1_firm = vc["mva_per_bank"] * (vc["banks"] - 1) * POWER_FACTOR - mva * POWER_FACTOR * load_frac
        subs.append({
            # grid_snapshot.substations fields
            "id": f"osm-{el['type']}-{el['id']}",
            "name": t["name"],
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "kv": kvs[0],
            "assumed_mva": mva,
            "distance_km": round(dist, 2),
            "headroom_mw": round(headroom, 1),
            # extra L2 fields (ignored by the snapshot schema)
            "voltages_kv": kvs,
            "operator": t.get("operator"),
            "voltage_class": cls,
            "transformation": vc["transformation"],
            "banks_assumed": vc["banks"],
            "mva_per_bank_assumed": vc["mva_per_bank"],
            "mva_status": vc["status"] if not (cls == "115" and t["name"] != "Nortech Substation") else "ASSUMED",
            "existing_load_pct": {"low": EXISTING_LOAD_PCT["low"], "mid": EXISTING_LOAD_PCT["mid"], "high": EXISTING_LOAD_PCT["high"], "status": "ASSUMED"},
            "headroom_mw_n1_firm": round(max(n1_firm, 0.0), 1),
            "dlr_uplift_pct": {"low": DLR_UPLIFT_PCT["low"], "mid": DLR_UPLIFT_PCT["mid"], "high": DLR_UPLIFT_PCT["high"], "status": "ASSUMED (range from source)"},
            "source": "osm",
            "osm_url": f"https://www.openstreetmap.org/{el['type']}/{el['id']}",
        })
    subs.sort(key=lambda s: s["distance_km"])
    return subs, skipped


def main():
    subs, skipped = build()
    schema = json.loads((ROOT / "contracts" / "grid_snapshot.schema.json").read_text(encoding="utf-8"))
    item = schema["properties"]["substations"]["items"]
    errs = [f"{s['id']}: {e.message}" for s in subs for e in Draft202012Validator(item).iter_errors(s)]
    if errs:
        raise SystemExit("schema errors:\n" + "\n".join(errs))
    doc = {
        "site_id": SITE["id"],
        "site": {"lat": SITE["lat"], "lon": SITE["lon"]},
        "radius_km": RADIUS_KM,
        "disclaimer": "Illustrative planning assumptions. Not real PG&E/SVP substation ratings and not a utility capacity determination. Every MVA, load and DLR number is SOURCED (quoted) or ASSUMED as labelled.",
        "method": {
            "assumed_mva": "banks_assumed x mva_per_bank_assumed for the substation's highest voltage class",
            "headroom_mw": f"assumed_mva x power_factor ({POWER_FACTOR}, ASSUMED) x (1 - existing_load_pct.mid/100)",
            "headroom_mw_n1_firm": "capacity with the largest bank out, minus existing load (mid), floored at 0",
            "dlr": "dlr_uplift_pct applies to line ratings (rating_mva) in grid_snapshot.lines, not to transformers",
        },
        "power_factor": {"value": POWER_FACTOR, "status": "ASSUMED"},
        "voltage_classes": VOLTAGE_CLASSES,
        "existing_load_pct": EXISTING_LOAD_PCT,
        "dlr_uplift_pct": DLR_UPLIFT_PCT,
        "sources": SRC,
        "skipped_osm_elements": skipped,
        "substations": subs,
    }
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(subs)} substations, skipped {skipped}")


if __name__ == "__main__":
    main()
