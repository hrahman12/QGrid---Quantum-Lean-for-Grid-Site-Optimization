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

## iso.py and caiso_<date>.csv

`latest_signal("CAISO")` returns `{lmp, load, load_mw, timestamp, source, ...}`, matching `grid_snapshot.iso`. It tries a live gridstatus pull (60 s budget) and falls back to the newest `data/l2/caiso_*.csv`. `QSP_OFFLINE=1` forces the cache, and `source` says which one was used (`gridstatus:CAISO` or `cache:data/l2/...`).

| What | Status | Source |
|---|---|---|
| CAISO system load, 5-min averaged to hourly | SOURCED | CAISO via `gridstatus` 0.37.0 `CAISO().get_load()` |
| Day-ahead hourly LMP, `TH_NP15_GEN-APND` (NP15 hub, reported as `lmp`) | SOURCED | CAISO OASIS `PRC_LMP` DAM via `gridstatus` `get_lmp(market="DAY_AHEAD_HOURLY")` |
| Day-ahead hourly LMP, `DLAP_PGAE-APND` (PG&E load zone) | SOURCED | same |
| NP15 / DLAP as the price for an Alviso load | ASSUMED | No public nodal price is defined for the site; these are the nearest public hub and zone |
| Stress hours = hours per day above the 7-day 90th-percentile NP15 price | Derived | from the cached CSV |

Refresh: `.venv/bin/python data/l2/iso.py --refresh`. Cache pulled 2026-11-08: 168 hourly rows (2026-11-02 to 2026-11-08 PT).
