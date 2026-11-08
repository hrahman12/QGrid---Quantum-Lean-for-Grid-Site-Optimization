"""Candidate compute sites (L1). Run `python site/sites.py` to write data/l1/sites.json and data/l1/site.json.

Do not `import site.sites`: `site` is also a stdlib module name and wins on sys.path. Load data/l1/sites.json
(or use `python site/sites.py`) instead.

requested_mw and deadline are ASSUMED scenario inputs, not facts about any operator's real request.
Coordinates are public map locations; where marked "approx" they are the centre of a data-center cluster,
not a surveyed facility.
"""
import json
from pathlib import Path

SITES = [
    {   # PRIMARY: Hannah's case study (README) and fixtures/site.json. 150 MW is the README's illustrative request.
        # Location: North San Jose / Alviso; OSM telecom=data_center objects exist here (data/l1/osm_datacenters_alviso.geojson).
        "id": "nsj-alviso-150", "name": "North San Jose / Alviso compute site (illustrative 150 MW)",
        "lat": 37.4265, "lon": -121.9750, "requested_mw": 150, "deadline": "2028-06-30", "iso": "CAISO",
    },
    {   # NOVVA Colorado Springs, already mapped in SeaBridgeAI (PowerInfrastructureMapTab). Colorado Springs Utilities
        # is not in a gridstatus ISO, so the live ISO signal is unavailable ("NONE"). requested_mw assumed.
        "id": "novva-colorado-springs", "name": "NOVVA Colorado Springs data center (assumed 40 MW request)",
        "lat": 39.0130, "lon": -104.8164, "requested_mw": 40, "deadline": "2027-12-31", "iso": "NONE",
    },
    {   # Ashburn, VA "Data Center Alley" cluster, PJM. Approx cluster centre from OSM/public maps; request assumed.
        "id": "ashburn-va-100", "name": "Ashburn VA Data Center Alley (approx, assumed 100 MW request)",
        "lat": 39.0300, "lon": -77.4700, "requested_mw": 100, "deadline": "2028-03-31", "iso": "PJM",
    },
    {   # Plano / Richardson (DFW) colocation corridor, ERCOT. Approx cluster centre; request assumed.
        "id": "dfw-plano-60", "name": "Dallas-Fort Worth Plano colocation corridor (approx, assumed 60 MW request)",
        "lat": 33.0200, "lon": -96.7000, "requested_mw": 60, "deadline": "2027-09-30", "iso": "ERCOT",
    },
    # International (grid/adapters global_osm). `country` = ISO-3166 alpha-2; omitted means "US".
    {   # EU: Frankfurt am Main data-center cluster (Ostend / Hanauer Landstrasse, DE-CIX hub). Approx cluster centre
        # from public maps; TSO Amprion/TenneT, DSO Syna/Mainova. requested_mw ASSUMED.
        "id": "frankfurt-de-120", "name": "Frankfurt am Main data-center cluster (approx, assumed 120 MW request)",
        "lat": 50.1150, "lon": 8.7300, "requested_mw": 120, "deadline": "2028-12-31", "iso": "ENTSOE:DE-LU",
        "country": "DE", "grid_operator": "Amprion / TenneT (TSO), Mainova/Syna (DSO)",
    },
    {   # Non-EU: Johor, Malaysia (Sedenak Tech Park / Kulai data-center corridor). Approx centre from public maps;
        # utility TNB (single buyer, no LMP market). requested_mw ASSUMED.
        "id": "johor-my-100", "name": "Johor Sedenak/Kulai data-center corridor (approx, assumed 100 MW request)",
        "lat": 1.6300, "lon": 103.5800, "requested_mw": 100, "deadline": "2028-06-30", "iso": "TNB:Peninsular",
        "country": "MY", "grid_operator": "Tenaga Nasional Berhad (TNB)",
    },
]

if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "data" / "l1"
    out.mkdir(parents=True, exist_ok=True)
    (out / "sites.json").write_text(json.dumps(SITES, indent=2), encoding="utf-8")
    (out / "site.json").write_text(json.dumps(SITES[0], indent=2), encoding="utf-8")
    for s in SITES:
        if "country" in s:  # international sample sites get their own site file for `pipeline.py data/l1/site_<id>.json`
            (out / f"site_{s['id']}.json").write_text(json.dumps(s, indent=2), encoding="utf-8")
    print(f"wrote {len(SITES)} sites to {out}")
