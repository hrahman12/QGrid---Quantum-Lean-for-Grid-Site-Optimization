# PG&E GRIP distribution capacity near Alviso (shared data pack)

**Caveat: GRIP values are directional, not guaranteed. This is not a PG&E approval, interconnection study or service commitment.**
Rebuild offline: `python build_grip_capacity.py` (reads `raw/`, writes `grip_capacity.json`). Refresh: `python fetch_grip.py` (needs network).

## Source
- PG&E Grid Resource and Integration Planning (GRIP) public ArcGIS FeatureServer, no login:
  `https://services2.arcgis.com/mJaJSax0KPHoCNB6/arcgis/rest/services/DRPComplianceRelProd/FeatureServer`
- Fetched: 2026-11-08. Source rows were last updated on the map Aug-Sep 2026 (ICA analysis date "Aug 2026").
- Query per layer: `/<layer>/query?where=1=1&geometry=-122.02,37.36,-121.88,37.46&geometryType=esriGeometryEnvelope&inSR=4326&outSR=4326&spatialRel=esriSpatialRelIntersects&outFields=*&f=geojson`, paged with `resultOffset` (nothing exceeded the 2000 limit except layer 3, which paged).
- Layer ids differ from the brief's guess; actual ids used:

| Cached file | Layer | Rows | Use |
|---|---|---|---|
| `raw/layer_0.geojson` | 0 EDSubstations | 9 | substation id, name, lat/lon |
| `raw/layer_2.geojson` | 2 FeederDetail | 97 | feeder list (geometry dropped) |
| `raw/layer_3.geojson` | 3 LineDetail | 16780 | per line section `LoadCapacity_kW` + limiting month/hour (geometry dropped, 12 of 29 fields kept) |
| `raw/layer_18.geojson` | 18 HighFireThreatDistricts | 2 | both Zone 1 / CPUC Tier 1 (context only) |
| `raw/layer_25.json` | 25 SubstationLoadProfile (table) | 2304 | month/hour high/low profile, filtered `subid IN (the 9 layer-0 ids)`; cached, not used in `grip_capacity.json` (units not documented) |
| `raw/layer_31.geojson` | 31 DFSubstationArea___PeakFacilityLoadingPercent | 105 | 24 BANK + 81 FEEDER rows: `facilityratingmw`, `facilityloadingmw2026..2040`, `peakfacilityloadingpercent` |
| `raw/layer_33.geojson` | 33 PendingLoad | 7 | pending load by feeder (geometry dropped) |

Polyline geometry was dropped from layers 2, 3, 33 because layer 3 alone is ~31 MB with it; attributes are unmodified apart from the layer-3 field subset.

## Field meanings
- `rating_mw`: bank/feeder facility rating (`facilityratingmw`). `forecast_load_mw[year]`: PG&E forecast peak loading of that facility (`facilityloadingmwYYYY`).
- `headroom_mw` (bank) = max(0, rating - forecast 2028). Pending load in GRIP is per feeder, so it is subtracted at substation level: substation `headroom_mw` = max(0, sum of per-bank floored headroom - sum of known pending MW).
- `pending_load_mw`: sum of `Expected_Load__Amount_MW` over the feeder's pending records. **All 7 records are -99.99 (amount withheld), so pending is null everywhere and not subtracted.** Headroom is therefore an upper bound on this axis.
- Feeder `max_load_hosting_mw` = **max over the feeder's line sections** of `LoadCapacity_kW` / 1000 (layer 3). GRIP does not flag the feeder-head section, so this is the best case somewhere on the feeder, not a guaranteed value at an arbitrary point. `limiting_month`/`limiting_hour`/`limiting_criteria` come from the section achieving that max (ties prefer a single-hour section). When the limit is shared by many hours (e.g. zero capacity all year) month/hour are null and `limiting_n_hours` gives the count.
- `feeder_rating_mw`, `feeder_forecast_2026_mw`, `feeder_forecast_2028_mw`: feeder-head facility values from layer 31 FEEDER rows (null when absent/withheld).
- `max_forecast_loading_pct_2026_2040`: max forecast loading over 2026-2040 / rating (computed here); `peak_loading_pct` is GRIP's own `peakfacilityloadingpercent`.
- -99.99 means withheld/missing and becomes null. Negative or null `LoadCapacity_kW` is treated as missing.

## Join
Feeder id = substation id (5 chars) + 4-digit circuit, e.g. feeder `083611104` -> substation `08361` BRITTON. Banks join on `substationid`; feeder-head rows on `idnumber == FeederID`.
- 97 feeders touch the bbox; **82 joined** to the 9 layer-0 substations, **15 failed** (their substations sit outside the box: 08219, 08226, 08299, 08300, 08353, 08363, 08385, 08387; kept in `unjoined_feeders`, excluded from headlines).
- Substation `08379` SIGNETICS has no bank rows and 1 feeder, so rating/headroom are null.
- 6 of 24 banks (NORTECH 3, DIXON LANDING 3, TRIMBLE 1/2/5, MILPITAS 6) have rating but a withheld forecast: headroom null and excluded from sums (`n_banks_without_forecast`). Totals are therefore partial, and TRIMBLE and NORTECH are mostly unknown rather than zero.

## Headline numbers (bbox -122.02,37.36,-121.88,37.46; 2028 forecast)
- Total distribution headroom near Alviso: **38.79 MW**, partial (18 banks with a forecast: rating 805.24 MW vs forecast 852.06 MW; Lawrence 21.5, Montague 6.0, Dixon Landing 5.8, Britton 5.49 MW; River Oaks, Trimble, Milpitas, Nortech 0).
- Feeders: **97** in the box; **82** joined to a substation, of which **79** have a hosting value (the stats below use those 79).
- Feeder hosting (max over sections): median **5.09 MW**, max **14.31 MW**, 4 feeders at 0.
- Transformer banks forecast >100% loaded: **16 of 24** by GRIP `peakfacilityloadingpercent` (**17** counting any year 2026-2040; 6 banks unknown).
- Pending load: 7 records, 0 with a disclosed amount.
