# Nature & climate layer: sources and method labels

Files: `alviso.json`, `novva.json` (built by `build_nature.py` from `measurements.json`, which `measure_nature.py` writes).
Each indicator: `{name, modality, value, unit, rag, rule, source, method, date, line}`; `line` is the plain-English sentence for the UI.
Overall `nature_rag` = worst indicator RAG, with a 6-word `headline`.

**Change 2026-11-08: CLIMADA removed.** `data/shared/climate/` (including `run_climada.py` and all `hazards_climada` values) was deleted.
Consumers read `data/shared/nature/` instead. The cited Open-Meteo heat-days script moved here as `heat_openmeteo.py`;
FEMA flood and CPUC HFTD values are carried over (cited, from `data/l2/site_risk.json`).

## Methods (all SeaBridgeAI code or services, no CLIMADA)
- `alphageo`: Google Earth Engine through SeaBridgeAI `GEERestAdapter` (seabridge_ai gis adapters, service-account auth loaded at runtime from the backend `.env`; no key in this repo).
  - AlphaEarth annual satellite embeddings `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL`, 2017 vs 2024, cosine similarity per 10 m pixel within 500 m; "changed" = cosine < 0.8.
  - ESA WorldCover v200 class shares within 1 km; Sentinel-2 SR NDVI (Jun-Aug 2024 median) within 500 m; MODIS MOD11A2 daytime land surface temperature (Jun-Aug 2024 mean).
- `openaccess`: public services used by SeaBridgeAI open-access modules.
  - WDPA protected-area polygons (via Earth Engine `WCMC/WDPA/current/polygons`): nearest within 20 km.
  - USFWS National Wetlands Inventory REST (`openaccess_native_nwi_wetland_context`): vegetated wetland acres within 500 m / 2 km. Not a jurisdictional delineation.
  - FEMA National Risk Index census-tract ratings, December 2025 (`openaccess_native_fema_nri_context`): heat wave, drought, riverine flood, coastal flood, hurricane, strong wind, tornado, hail, wildfire, landslide, earthquake. Tract-level, not parcel-level.
- `cited`: FEMA NFHL zone and CPUC HFTD (`data/l2/site_risk.json`); Open-Meteo CMIP6 hot days (`heat_openmeteo.py`); burrowing owl / Santa Clara Valley Habitat Plan (not re-fetched today).
- `assumed`: water stress category (SeaBridgeAI `nature_aqueduct_local` reader exists but the Aqueduct 4.0 file is not on this machine); NOVVA species and WUI notes.

## Rerun
```
<backend>/venv/Scripts/python.exe data/shared/nature/measure_nature.py   # needs GEE service account via backend .env
python data/shared/nature/build_nature.py                               # offline
python ui/build_decision.py
```

## Not covered
Sea-level rise beyond FEMA coastal-flood rating, land subsidence (no platform layer), WRI Aqueduct flood depth (platform reader needs its range-read pipeline), Rothermel fire spread (needs fuel + weather inputs).
