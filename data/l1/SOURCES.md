# data/l1 sources (lane L1)

All files are cached responses so the demo runs offline. No API keys are stored here.

| File | Source | Notes |
|---|---|---|
| osm_substations_alviso.geojson, osm_power_lines_alviso.geojson, osm_datacenters_alviso.geojson | OpenStreetMap via Overpass API, (c) OpenStreetMap contributors, ODbL-1.0 | bbox = 25 km around (37.43, -121.97); fetched 2026-11-08 by grid/fetch_data.py. Tags trimmed to name/operator/voltage/etc. |
| osm_substations_nsj-alviso-150.geojson | same | snapshot cache written by grid/snapshot.py |
| iso_CAISO_latest.csv | gridstatus (CAISO OASIS / outlook) | latest system load MW and mean real-time 5-min hub LMP; overwritten on each live run |
| sites.json, site.json | hand-built, see site/sites.py | requested_mw and deadline are assumed scenario inputs |

Not yet cached: HIFLD transmission lines, WRI Aqueduct, EIA-860 plants (see PR for status).
