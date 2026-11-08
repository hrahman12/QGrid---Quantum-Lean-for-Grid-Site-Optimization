"""Build data/l2/l3_inputs.json: one joined, offline input for L3 search (quantum/search.py) and Lean rules.

Joins (all cached on main):
  data/shared/grip/grip_capacity.json   feeders (hosting MW, limiting month/hour), banks (rating, 2028 forecast)
  data/l2/flex_headroom.json            bank cap at each curtailment % + curtailed (month, hour) cells
  data/l2/site_risk.json                FEMA flood zone / HFTD per GRIP substation
  data/l2/substation_ratings.json       transmission-level OSM substations (for the MW that cannot go on distribution)
  data/l2/ciso_2025_stress.json         system stress window (context; the Lean curtailment rule uses the LOCAL bank window)

Feeder -> bank: SOURCED from GRIP layer 31 FEEDER rows (field `bankname`, e.g. BRITTON 1104 -> BRITTON BANK 1),
data/shared/grip/raw/layer_31.geojson. Feeders without a layer-31 row get bank_id null (unknown).

Usage: python data/l2/build_l3_inputs.py
"""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SITE = json.loads((ROOT / "fixtures" / "site.json").read_text(encoding="utf-8"))
GRIP = json.loads((ROOT / "data" / "shared" / "grip" / "grip_capacity.json").read_text(encoding="utf-8"))
FLEX = json.loads((HERE / "flex_headroom.json").read_text(encoding="utf-8"))
RISK = json.loads((HERE / "site_risk.json").read_text(encoding="utf-8"))
RATINGS = json.loads((HERE / "substation_ratings.json").read_text(encoding="utf-8"))
STRESS = json.loads((HERE / "ciso_2025_stress.json").read_text(encoding="utf-8"))
L31 = ROOT / "data" / "shared" / "grip" / "raw" / "layer_31.geojson"
OUT = HERE / "l3_inputs.json"


def feeder_banks():
    rows = [f["properties"] for f in json.loads(L31.read_text(encoding="utf-8"))["features"]]
    bank_id = {r["gnafacilityname"].strip().upper(): r["idnumber"] for r in rows if r.get("facilitytype") == "BANK"}
    return {r["idnumber"]: bank_id.get((r.get("bankname") or "").strip().upper())
            for r in rows if r.get("facilitytype") == "FEEDER"}

MIN_SITE_MW, MAX_SITE_MW = 0.5, 10.0  # organizers' edge-site range (Track 1)
CURTAIL_PCTS = ["0", "1", "2", "5", "10"]


def km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return round(2 * 6371 * math.asin(math.sqrt(a)), 2)


def main():
    risk = {p["id"]: p for p in RISK["points"]}
    flex = {s["id"]: s for s in FLEX["substations"]}
    fbank = feeder_banks()
    banks, feeders = [], []
    for s in GRIP["substations"]:
        r = risk.get(s["id"], {})
        flood = r.get("flood", {})
        dist = km(SITE["lat"], SITE["lon"], s["lat"], s["lon"])
        fx = flex.get(s["id"])
        fx_banks = {pct: {b["id"]: b for b in fx["by_curtailment_pct"][pct]["banks"]} for pct in CURTAIL_PCTS} if fx else {}
        bank_ids = {b["id"] for b in s["banks"]}
        for b in s["banks"]:
            f28 = (b.get("forecast_load_mw") or {}).get("2028")
            caps = {pct: (fx_banks[pct][b["id"]]["flex_headroom_mw"] if fx and b["id"] in fx_banks[pct] else None) for pct in CURTAIL_PCTS}
            banks.append({
                "bank_id": b["id"], "bank": b["name"], "substation_id": s["id"], "substation": s["name"],
                "lat": s["lat"], "lon": s["lon"], "distance_km": dist,
                "rating_mw": b.get("rating_mw"), "forecast_2028_mw": f28,
                "has_forecast": f28 is not None,
                "cap_mw_by_curtailment_pct": caps,
                "curtail_cells_by_pct": {pct: fx["by_curtailment_pct"][pct]["curtail_cells"] for pct in CURTAIL_PCTS} if fx else None,
                "curtail_hours_by_pct": {pct: fx["by_curtailment_pct"][pct]["curtail_hours_per_year"] for pct in CURTAIL_PCTS} if fx else None,
                "flood_zone": flood.get("zone"), "flood_sfha": flood.get("sfha", False), "flood_bfe_ft": flood.get("bfe_ft"),
            })
        for f in s["feeders"]:
            bid = fbank.get(f["feeder_id"])
            host = f.get("max_load_hosting_mw")
            feeders.append({
                "feeder_id": f["feeder_id"], "feeder": f["name"], "substation_id": s["id"], "substation": s["name"],
                "bank_id": bid if bid in bank_ids else None,
                "bank_id_status": "SOURCED (GRIP layer 31 bankname)" if bid in bank_ids else "unknown (no layer-31 feeder row)",
                "lat": s["lat"], "lon": s["lon"], "distance_km": dist,
                "hosting_mw": host,
                "edge_site_max_mw": None if host is None else round(min(host, MAX_SITE_MW), 3),
                "eligible_edge_site": host is not None and host >= MIN_SITE_MW,
                "limiting_month": f.get("limiting_month"), "limiting_hour": f.get("limiting_hour"),
                "limiting_criteria": f.get("limiting_criteria"),
                "flood_sfha": flood.get("sfha", False),
            })
    feeders.sort(key=lambda x: (-(x["edge_site_max_mw"] or 0), x["distance_km"]))
    trans = [{k: s[k] for k in ("id", "name", "kv", "distance_km", "assumed_mva", "headroom_mw", "headroom_mw_n1_firm", "operator")}
             for s in RATINGS["substations"] if s["kv"] >= 115][:8]
    elig = [f for f in feeders if f["eligible_edge_site"]]
    doc = {
        "site": SITE,
        "disclaimer": "Directional inputs for search and Lean rules. GRIP is not guaranteed; pending load withheld; not a PG&E approval.",
        "search_space": {
            "split_step_pct": 25,
            "dlr": {"options": [False, True], "uplift_pct_mid": RATINGS["dlr_uplift_pct"]["mid"], "applies_to": "transmission lines"},
            "battery_mw": [0, 25, 50],
            "curtailment_pct": [0, 5, 10],
            "curtailment_pct_also_available": [1, 2],
            "edge_site_mw_range": [MIN_SITE_MW, MAX_SITE_MW],
            "note": "From ORCH 13:24 / L3 brief. Bank caps exist for every curtailment_pct listed.",
        },
        "rule_inputs": {
            "R_bank_cap": "sum(MW on feeders with the same bank_id) <= banks[].cap_mw_by_curtailment_pct[c] (feeder hosting is NOT additive)",
            "R_feeder_cap": "edge site MW <= feeders[].edge_site_max_mw and >= 0.5",
            "R_curtail_window": "a plan with curtailment c commits to banks[].curtail_cells_by_pct[c] (local Aug-Sep afternoons), not the CAISO system window",
            "R_flood": "flood_sfha true -> permit/cost condition (equipment above BFE), not auto-RED",
            "R_transmission": "MW not placed on distribution needs transmission service: 7-10 years (organizers) > deadline " + SITE["deadline"] + " -> RED for that share unless deadline relaxed",
        },
        "summary": {
            "banks": len(banks), "banks_with_forecast": sum(b["has_forecast"] for b in banks),
            "feeders": len(feeders), "eligible_edge_feeders": len(elig),
            "distribution_cap_mw_by_curtailment_pct": {pct: round(sum(b["cap_mw_by_curtailment_pct"][pct] or 0 for b in banks), 2) for pct in CURTAIL_PCTS},
            "sum_feeder_edge_site_max_mw": round(sum(f["edge_site_max_mw"] or 0 for f in elig), 2),
            "feeders_with_bank_id": sum(f["bank_id"] is not None for f in feeders),
        },
        "banks": banks,
        "feeders": feeders,
        "transmission_candidates": trans,
        "system_stress_2025": {"window": "net_load_top2pct", "hours_by_month": STRESS["curtailment_windows"]["net_load_top2pct"]["hours_by_month"]},
        "sources": ["data/shared/grip/grip_capacity.json", "data/l2/flex_headroom.json", "data/l2/site_risk.json",
                    "data/l2/substation_ratings.json", "data/l2/ciso_2025_stress.json"],
    }
    OUT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(doc["summary"], indent=1))


if __name__ == "__main__":
    main()
