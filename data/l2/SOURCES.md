# L2 data sources (data/l2/)

Every number in `substation_ratings.json` is either **SOURCED** (quoted from a document below) or **ASSUMED** (labelled as such in the file). These are illustrative planning assumptions, not real PG&E or Silicon Valley Power substation ratings, and not a utility capacity determination.

## substation_ratings.json

Rebuild offline with `.venv/bin/python data/l2/build_substation_ratings.py`. It reads only `data/l2/cache/` and checks each substation against the `grid_snapshot` substation schema.

| What | Status | Source |
|---|---|---|
| Substation names, locations, voltages, operators | SOURCED | OpenStreetMap `power=substation` within 25 km of 37.4265, -121.9750, pulled 2026-11-08 via Overpass API; cached in `cache/osm_substations_alviso_25km.json` (ODbL) |
| 115/21 kV bank = 45 MVA, 2 banks installed (3 at build-out) | SOURCED for Nortech only; ASSUMED for other 115 kV substations | [CPUC Nortech Negative Declaration](https://ia.cpuc.ca.gov/Environment/Info/esa/nortech/nortech_negdec.htm) |
| Los Esteros has 3 x 230/115 kV banks (4th planned) | SOURCED (count only) | [CPUC Northeast San Jose project description](https://ia.cpuc.ca.gov/Environment/info/aspen/nesanjo/description.html) |
| 230/115 kV bank = 420 MVA | ASSUMED | No public per-bank rating found |
| 60/12 kV bank = 25 MVA, 2 banks | ASSUMED | No public rating found |
| 500/230 kV bank = 1000 MVA, 2 banks | ASSUMED | Not used: no 500 kV substation within 25 km |
| Existing load = 50 / 65 / 80 % of rating (low/mid/high) | ASSUMED | No public loading data; mid is used for `headroom_mw` |
| Power factor 0.95 | ASSUMED | |
| DLR uplift = 6 / 10 / 14 % on lines | Range SOURCED; applying it here is ASSUMED | [DOE Oncor DLR case study](https://www.energy.gov/sites/prod/files/2014/08/f18/Oncor-SGIG-case-study-May2014.pdf): 6-14% on 345 kV, 8-12% on 138 kV, available 84-91% of the time |

## Derived fields

- `assumed_mva` = banks x MVA per bank for the substation's highest voltage class.
- `headroom_mw` = `assumed_mva` x 0.95 x (1 - 0.65).
- `headroom_mw_n1_firm` = capacity with the largest bank out, minus mid existing load, floored at 0. Much smaller than `headroom_mw`; use it for an N-1 view.
- `dlr_uplift_pct` applies to `grid_snapshot.lines[].rating_mva`, not to transformers.

## Skipped OSM elements

Unnamed substations, elements without a voltage tag or below 60 kV, and rail traction substations (Caltrain, BART) are dropped. The counts are in `skipped_osm_elements`. Ids are `osm-<type>-<id>`, so they can be joined to L1's OSM export once `data/l1/` lands.

## queue_hints.json

Rebuild offline with `.venv/bin/python data/l2/build_queue_hints.py` (add `--refresh` to re-download the queue).

| What | Status | Source |
|---|---|---|
| Queue projects (id, location, type, MW, status, proposed COD) | SOURCED | CAISO public interconnection queue (`PublicQueueReport.xlsx`) via `gridstatus` 0.37.0 `CAISO().get_interconnection_queue()`, pulled 2026-11-08, filtered to Santa Clara, Alameda and San Mateo counties; cached in `cache/caiso_queue_bay_counties_2026-11-08.csv` |
| Match to nearby substations | Method | Substation name (suffix stripped) as a whole word in `Interconnection Location`. Projects on a line or tap are tagged `"at": "line"` and left out of `active_mw_at_substation` |
| Utility territory = PG&E | ASSUMED | The site is in the City of San Jose; Silicon Valley Power serves the City of Santa Clara. Not checked against a territory map |
| Hosting capacity | Not cached | PG&E's ICA / hosting-capacity map needs a PG&E login |

Caveat: the CAISO queue holds generation and storage requests only. Data-center load requests go through PG&E and are not in it, so these are competition and flexibility hints, not available capacity. Example: Los Esteros has 323 MW of active requests (including 200 MW of storage at 230 kV, proposed 2027-12-15) and 5 withdrawals.

## iso.py and caiso_<date>.csv

`latest_signal("CAISO")` returns `{lmp, load, load_mw, timestamp, source, ...}`, matching `grid_snapshot.iso`. It tries a live gridstatus pull (60 s budget) and falls back to the newest `data/l2/caiso_*.csv`. `QSITE_OFFLINE=1` (or `QSP_OFFLINE=1`) forces the cache, and `source` says which one was used (`gridstatus:CAISO` or `cache:data/l2/...`).

| What | Status | Source |
|---|---|---|
| CAISO system load, 5-min averaged to hourly | SOURCED | CAISO via `gridstatus` 0.37.0 `CAISO().get_load()` |
| Day-ahead hourly LMP, `TH_NP15_GEN-APND` (NP15 hub, reported as `lmp`) | SOURCED | CAISO OASIS `PRC_LMP` DAM via `gridstatus` `get_lmp(market="DAY_AHEAD_HOURLY")` |
| Day-ahead hourly LMP, `DLAP_PGAE-APND` (PG&E load zone) | SOURCED | same |
| NP15 / DLAP as the price for an Alviso load | ASSUMED | No public nodal price is defined for the site; these are the nearest public hub and zone |
| Stress hours = hours per day above the 7-day 90th-percentile NP15 price | Derived | from the cached CSV |

`grid/snapshot.py` `iso_signal()` calls `latest_signal` for CAISO and falls back to its own gridstatus path. A live pull is reused in-process for 60 min, so many search rounds don't re-fetch. Refresh: `.venv/bin/python data/l2/iso.py --refresh`. Cache pulled 2026-11-08: 168 hourly rows (2026-11-02 to 2026-11-08 PT).

## ciso_2025_stress.json (2025 curtailment windows)

Rebuild offline with `.venv/bin/python data/l2/build_ciso_stress.py`. `iso.latest_signal()` returns the default window as `stress_2025`.

| What | Status | Source |
|---|---|---|
| CAISO (CISO) hourly demand, solar and wind, 2025 | SOURCED | US EIA Form 930 through the hack-day event pack, [`us_grid_hourly_2025.csv`](https://github.com/arhamshah08/energy-hack/blob/main/data/grid-hourly-2025/us_grid_hourly_2025.csv), `ba == CISO`, 8,760 rows; cached in `cache/ciso_hourly_2025_eia930.csv` (public domain) |
| Stress = top 2% (and 5%) of 2025 hours by demand and by net load (demand - solar - wind) | Derived | Top 2% = 176 h/yr = 97.99% availability, matching the organizers' "~98% availability" framing |
| Hours per day above the 2025 p90 of demand (31,205 MW) | Derived | 876 h/yr; 97 stress days at about 9 h each; mean 2.4 h/day overall, 12.1 h/day in August, 0 from October to April (`demand_p90_hours_per_day`) |
| Month and hour cells | Derived | Local (Pacific) month 1-12 and hour-beginning 0-23, the same convention as GRIP `limiting_month` / `limiting_hour` |

2025 result: the net-load top 2% falls on evenings from May to September (mostly 18:00-23:00, peaking in August and September). The demand top 2% falls in July to September, 17:00-21:00. This is system-level CAISO stress; pair it with the GRIP feeder limiting hour for local stress. EIA-930 has no prices, so these windows come from load, not price.

## flex_headroom.json (distribution MW vs curtailment hours)

Rebuild offline with `.venv/bin/python data/l2/build_flex_headroom.py`. It reads `data/shared/grip/` and `ciso_2025_stress.json`.

| What | Status | Source |
|---|---|---|
| Bank rating and 2028 forecast | SOURCED (directional) | `data/shared/grip/grip_capacity.json` (PG&E GRIP layer 31) |
| Substation load shape by month and hour (`high`) | SOURCED, units undocumented, so only the shape is used | `data/shared/grip/raw/layer_25.json` (GRIP SubstationLoadProfile) |
| Each month's `high` day repeats on every day of that month | ASSUMED (conservative: overstates curtailment hours) | |
| The substation's shape applies to each of its banks | ASSUMED | |

Method: curtail the highest month-hour cells up to a budget of X% of 2028 hours. Then flex headroom = rating - forecast_2028 × (highest remaining shape value), floored at 0. With X = 0 this reproduces GRIP firm headroom (38.79 MW).

Result (directional, an upper bound because GRIP pending load is withheld):

| Curtailment (% of hours) | 0 | 1 | 2 | 5 | 10 |
|---|---|---|---|---|---|
| Distribution MW near Alviso | 38.8 | 40.7 | 47.6 | 66.2 | 90.6 |

Local bank peaks fall on August-September afternoons (13:00-18:00). The 2025 CAISO net-load stress falls in the evenings (18:00-23:00), and the two windows barely overlap.

## site_risk.json (flood and wildfire flags)

Rebuild offline with `.venv/bin/python data/l2/build_site_risk.py`.

| What | Status | Source |
|---|---|---|
| FEMA flood zone at the site and at the 9 GRIP substations | SOURCED | FEMA NFHL via Esri Living Atlas "USA Flood Hazard Areas" (`USA_Flood_Hazard_Reduced_Set_gdb/FeatureServer/0`), point queries pulled 2026-11-08; cached in `cache/flood_points_alviso.json`. `hazards.fema.gov` itself failed the TLS handshake from the VM |
| High Fire-Threat Districts | SOURCED | PG&E GRIP layer 18 (CPUC HFTD, Cal Fire v22_3), `data/shared/grip/raw/layer_18.geojson`, GRIP bbox only |

Result: the Alviso site is in **Zone AE (SFHA, 1% annual chance, BFE 12 ft)**, as are the Nortech and Dixon Landing substations. No point is inside a fire-threat district (the nearest polygon is 8.7 km from the site, and both polygons in the bbox are CPUC Tier 1). Suggested rule: an SFHA location is a permit and cost condition (elevate equipment above the BFE), not an automatic RED.

## l3_inputs.json (joined input for L3 search and Lean rules)

Rebuild offline with `.venv/bin/python data/l2/build_l3_inputs.py`. It joins GRIP banks and feeders, `flex_headroom.json`, `site_risk.json`, `substation_ratings.json` (transmission candidates) and `ciso_2025_stress.json`, and adds the discrete search space and the rule inputs (`rule_inputs`).

| What | Status | Source |
|---|---|---|
| Feeder -> bank | SOURCED | GRIP layer 31 FEEDER rows, field `bankname` (e.g. BRITTON 1104 -> BRITTON BANK 1), `data/shared/grip/raw/layer_31.geojson`; 81 of 82 feeders (SIGNETICS 1101 has no row). This replaces an earlier circuit-number guess that was wrong |
| Everything else | as in the sections above | |

Key fact for the Lean bank rule: the edge-site maxima of the 73 eligible feeders sum to 430.6 MW, but the bank caps sum to 38.8 MW (0% curtailment). Feeder hosting is not additive: e.g. MONTAGUE 2101 can host 10 MW, but its bank (0838901) has only 3.18 MW of headroom, shared with the bank's other feeders (25.9 MW of feeder maxima).
