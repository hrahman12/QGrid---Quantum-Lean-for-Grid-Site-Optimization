# NOVVA data sources

| File | Origin | Notes |
|---|---|---|
| `osm_novva_colorado_springs_buildings.geojson` | Copied from the SeaBridgeAI repo: `seabridge-ai-oss/publish-oss-console/docs/physical-world-risk/extracts/osm_novva_colorado_springs_buildings.geojson` (copied 2026-11-08) | 46 OSM building footprints (`osm_id`, `osm_type`, `building` tags) near 39.01 N, -104.81 W. Data (c) OpenStreetMap contributors, ODbL: https://www.openstreetmap.org/copyright. Scanned before copying: no keys, tokens, or credentials. Only geometry and OSM ids. Original query date and bbox not recorded in the file (UNKNOWN). |
| `novva_facts.json` | Web research 2026-11-08 | Each fact has source URLs and an evidence label (fetched / company claim / search snippet only / conflicting). Capacity figures conflict between sources; see the `assessment` field. |

Not included: any SeaBridgeAI proprietary data other than the public OSM extract.
