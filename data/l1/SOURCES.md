# data/l1 sources (lane L1)

All files are cached responses so the demo runs offline. No API keys are stored here.

| File | Source | Notes |
|---|---|---|
| osm_substations_alviso.geojson, osm_power_lines_alviso.geojson, osm_datacenters_alviso.geojson | OpenStreetMap via Overpass API, (c) OpenStreetMap contributors, ODbL-1.0 | bbox = 25 km around (37.43, -121.97); fetched 2026-11-08 by grid/fetch_data.py. Tags trimmed to name/operator/voltage/etc. |
| osm_substations_nsj-alviso-150.geojson | same | snapshot cache written by grid/snapshot.py |
| iso_CAISO_latest.csv | gridstatus (CAISO OASIS / outlook) | latest system load MW and mean real-time 5-min hub LMP; overwritten on each live run |
| sites.json, site.json | hand-built, see site/sites.py | requested_mw and deadline are assumed scenario inputs |

| hifld_transmission_alviso.geojson | HIFLD Electric Power Transmission Lines (ArcGIS FeatureServer) | bbox 25 km around (37.43, -121.97), max 500 records |

Skipped, with reasons (checked 2026-11-08):
- WRI Aqueduct: the SeaBridgeAI endpoint (`aqueduct40_baseline_annual_y2023m07d05`) now returns 400 Invalid URL; the service is no longer listed in that ArcGIS org.
- EIA-860: the EIA v2 `operating-generator-capacity` API (works with a free key) has no county or lat/lon fields, so plants cannot be selected near Alviso from it. A plant list needs the EIA-860 plant file (lat/lon) instead.

Derived, not fetched: `distribution_map.html` (grid/map.py) is built from the PG&E GRIP cache in `data/shared/grip/` (owned by the data-grip branch). It sums feeder hosting capacity, each edge site capped at 10 MW and limited by the substation bank headroom. Directional only.
