# Climate risk + resilience: sources and method labels

Files: `alviso.json`, `novva.json`. Every value is `{value, unit, source, method, scenario, year}` (+ optional `note`).

- `method: climada` - output of SeaBridgeAI `climada-stack/climada_workers/*` (CLIMADA data API, locally cached hazard sets), driven by `run_climada.py`. Screening numbers: percentiles of hazard cells within a radius (0.25 deg river flood, 0.5 deg wildfire), not point values. USD `aai_agg` uses a default exposure value and is deliberately NOT reported.
- `method: cited` - public source, repo-cached public layer, or public model API (URL in `source`). `heat_openmeteo.py` computes days Tmax>35C from the Open-Meteo Climate API (CMIP6 HighResMIP, 4 models, raw/no bias correction; 1995-2014 vs 2036-2050, SSP5-8.5). It is labelled `cited` because the numbers come from a public model service, not CLIMADA.
- `method: assumed` - our assumption, inference, or unverified placeholder. Includes WRI Aqueduct water stress (Atlas not reachable in the time available), N-1 headroom ratings (OSM-derived MVA), NOVVA zero N-1 headroom, qualitative cooling-load text.

## CLIMADA runs
Env: miniforge `climada-env`; data cache `~/climada/data` (local, ~45 GB; not committed). Cases: `historical/2025` and `SSP245/2050`.

| Worker | Result |
|---|---|
| river_flood | ok. 2050 uses cached rcp60 2050-2070 (worker maps SSP2-4.5 to rcp60; CLIMADA has no rcp45). |
| wildfire | ok, historical 2001-2020 only; scenario run is identical baseline. Values are fire-pixel brightness (K), not probabilities. |
| coastal_surge | Alviso baseline returns a far-field TC artefact (not decision-grade); 2050 empty. Inland NOVVA: empty. TC wind-surge only; no tide/SLR. |
| seasonal_heat | empty for both sites: Copernicus CDS processing failed here; worker also lacks future years. |
| tropical_cyclone, crop_hail | not run (not meaningful for these sites with the cached sets). |

## Public / repo sources
- FEMA NFHL via Esri Living Atlas reduced set (point query 2026-11-08); Alviso from `data/l2/site_risk.json`, NOVVA queried fresh (no polygon returned, consistent with Zone X, NOT confirmed on the FEMA MSC panel).
- CPUC HFTD v22_3 via PG&E GRIP layer 18 (`data/l2/site_risk.json`).
- PG&E PSPS page and CPUC 2024-11-05 post-event report (event list and the 21,357-customer figure from search snippets; not downloaded).
- Grid: `data/l2/l3_inputs.json` (GRIP, OSM transmission, assumed MVA); `data/shared/novva/novva_facts.json`; `data/shared/socio/novva.json` (CSU Large Load Rate, search snippet).
- Open-Meteo Climate API: https://open-meteo.com/en/docs/climate-api
- Front Range 95F reference: https://5280.com/climate-change-a-matter-of-degree/
- WRI Aqueduct 4.0: https://www.wri.org/applications/aqueduct/water-risk-atlas/ (not queried).

## Known limits
- Raw CMIP6 grid-cell heat is biased low at Colorado Springs (1,830 m); baseline 0.1 d/yr understates observed. Use the delta qualitatively.
- Waldo Canyon / Black Forest mention is from general knowledge, not fetched.
- Directional screening only; not a utility, FEMA, or engineering determination.
