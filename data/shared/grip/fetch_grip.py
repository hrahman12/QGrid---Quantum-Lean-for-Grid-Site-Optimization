"""Cache PG&E GRIP layers near Alviso into raw/ (run once online; build_grip_capacity.py is offline)."""
import json, urllib.parse, urllib.request
from pathlib import Path

BASE = "https://services2.arcgis.com/mJaJSax0KPHoCNB6/arcgis/rest/services/DRPComplianceRelProd/FeatureServer"
BBOX = "-122.02,37.36,-121.88,37.46"
SPATIAL = [0, 2, 3, 18, 31, 33]  # layer 0 must stay first (its ids filter table 25)
#  # layers filtered by bbox
RAW = Path(__file__).parent / "raw"


KEEP3 = ["FeederId", "FeederName", "CSV_LineSection", "LoadCapacity_kW", "voltage_kv", "phase_cnt", "limiting_month_hour",
         "limiting_criteria", "ICA_Analysis_Date", "GenCapacity_kW", "ScreenL", "Division"]
NOGEOM = {2, 3, 33}  # polylines: geometry dropped to keep the repo small (layer 3 alone is ~31 MB with geometry)


def get(layer, spatial, where="1=1"):
    feats, off = [], 0
    while True:
        p = {"where": where, "outFields": "*", "f": "geojson", "resultOffset": off} if spatial else \
            {"where": where, "outFields": "*", "f": "json", "resultOffset": off}
        if spatial:
            p.update(geometry=BBOX, geometryType="esriGeometryEnvelope", inSR=4326, outSR=4326,
                     spatialRel="esriSpatialRelIntersects")
        d = json.load(urllib.request.urlopen(f"{BASE}/{layer}/query?" + urllib.parse.urlencode(p), timeout=120))
        page = d["features"]
        feats += page
        if not page or not (d.get("exceededTransferLimit") or d.get("properties", {}).get("exceededTransferLimit")):
            return feats
        off += len(page)


subs = {}
for L in SPATIAL:
    f = get(L, True)
    if L in NOGEOM:
        for x in f:
            x["geometry"] = None
            if L == 3:
                x["properties"] = {k: x["properties"].get(k) for k in KEEP3}
    if L == 0:
        subs = [int(x["properties"]["SubstationID"]) for x in f]
    (RAW / f"layer_{L}.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": f}, separators=(",", ":")))
    print(L, len(f))
# non-spatial table: filter server-side by the substation ids found in layer 0
f = get(25, False, "subid IN (%s)" % ",".join(map(str, subs)))
(RAW / "layer_25.json").write_text(json.dumps({"features": f}, separators=(",", ":")))
print(25, len(f))
