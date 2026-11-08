"""Measure nature indicators for the two sites with SeaBridgeAI code (no CLIMADA).

AlphaGeo path: SeaBridgeAI GEERestAdapter (seabridge_ai/.../gee_rest_adapter.py) sends Earth Engine
expressions to value:compute with the backend service account. Open-access path: USFWS NWI REST
(same service as app/services/openaccess_native_nwi_wetland_context.py) and SeaBridgeAI local
Aqueduct 4.0 reader (app/services/nature_aqueduct_local.py) when its GDB is present.

Run with the backend venv (has earthengine-api):
  <backend>/venv/Scripts/python.exe data/shared/nature/measure_nature.py
Credentials come only from <backend>/.env loaded into this process; nothing secret is printed or written.
Writes data/shared/nature/measurements.json; build_nature.py turns it into RAG files.
"""
import asyncio, json, os, sys, urllib.parse, urllib.request
from pathlib import Path

BACKEND = Path(os.environ.get("SEABRIDGE_BACKEND", "C:/Users/adelm/SeaBridgeAI/manageesg-backend"))
SITES = {"alviso": (37.4265, -121.975), "novva": (39.0130, -104.8164)}
OUT = Path(__file__).with_name("measurements.json")
NWI = "https://fwspublicservices.wim.usgs.gov/wetlandsmapservice/rest/services/Wetlands/MapServer/0/query"


def load_env():
    from dotenv import load_dotenv
    load_dotenv(BACKEND / ".env", override=False)
    key = os.environ.get("GEE_SERVICE_ACCOUNT_KEY", "")
    if key and not os.path.isabs(key):  # relative paths in .env are relative to the backend
        os.environ["GEE_SERVICE_ACCOUNT_KEY"] = str(BACKEND / key)
    sys.path[:0] = [str(BACKEND / "seabridge_ai" / "src"), str(BACKEND)]


async def gee(lat, lon):
    from sustainability_ai.gis.adapters.earth_observation.gee_rest_adapter import GEERestAdapter
    a = GEERestAdapter()
    await a.initialize()
    ee = a._ee
    # earthengine-api 1.x refuses to build expressions before Initialize; reuse the adapter's SA credentials
    ee.Initialize(a._http.auth._credentials, project=a._project)
    pt = ee.Geometry.Point([lon, lat])
    out = {}
    async def run(name, expr):
        try:
            out[name] = await a._compute_expression(expr)
        except Exception as e:  # keep going; record the failure class only (no response bodies)
            out[name] = {"error": type(e).__name__}
    emb = ee.ImageCollection("GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL").filterBounds(pt)
    e17 = emb.filterDate("2017-01-01", "2018-01-01").mosaic()
    e24 = emb.filterDate("2024-01-01", "2025-01-01").mosaic()
    dot = e17.multiply(e24).reduce(ee.Reducer.sum()).rename("cos")  # unit-length 64-D vectors -> cosine
    img = dot.addBands(dot.lt(0.8).rename("changed"))
    await run("embedding_2017_2024", img.reduceRegion(ee.Reducer.mean(), pt.buffer(500), 10, maxPixels=1e8))
    wc = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map")
    await run("worldcover_1km", wc.reduceRegion(ee.Reducer.frequencyHistogram(), pt.buffer(1000), 10, maxPixels=1e8))
    s2 = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(pt)
          .filterDate("2024-06-01", "2024-09-01").filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20)).median())
    await run("ndvi_500m", s2.normalizedDifference(["B8", "B4"]).rename("ndvi")
              .reduceRegion(ee.Reducer.mean(), pt.buffer(500), 10, maxPixels=1e8))
    lst = (ee.ImageCollection("MODIS/061/MOD11A2").filterDate("2024-06-01", "2024-09-01")
           .select("LST_Day_1km").mean().multiply(0.02).subtract(273.15))
    await run("lst_summer_day_c", lst.reduceRegion(ee.Reducer.mean(), pt.buffer(1000), 1000))
    wd = ee.FeatureCollection("WCMC/WDPA/current/polygons").filterBounds(pt.buffer(20000))
    wd = wd.map(lambda f: f.set("dist_m", f.geometry().distance(pt, 10)))
    near = ee.Feature(wd.sort("dist_m").first())
    await run("wdpa_20km", ee.Algorithms.If(wd.size().gt(0), ee.Dictionary({
        "n": wd.size(), "dist_m": near.get("dist_m"), "name": near.get("NAME"),
        "desig": near.get("DESIG_ENG"), "iucn": near.get("IUCN_CAT")}), ee.Dictionary({"n": 0})))
    await a.__aexit__()
    return out


def nwi(lat, lon, radius_m):
    q = {"f": "json", "geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "inSR": 4326,
         "distance": radius_m, "units": "esriSRUnit_Meter", "spatialRel": "esriSpatialRelIntersects",
         "outFields": "WETLAND_TYPE,ACRES", "returnGeometry": "false", "resultRecordCount": 2000}
    try:
        body = json.load(urllib.request.urlopen(NWI + "?" + urllib.parse.urlencode(q), timeout=60))
    except Exception as e:
        return {"error": type(e).__name__}
    acres = {}
    for f in body.get("features", []):
        a = f["attributes"]
        t = a.get("Wetlands.WETLAND_TYPE") or a.get("WETLAND_TYPE") or "?"
        acres[t] = round(acres.get(t, 0) + (a.get("Wetlands.ACRES") or a.get("ACRES") or 0), 1)
    return {"n": len(body.get("features", [])), "acres_by_type": acres, "exceeded": body.get("exceededTransferLimit", False)}


NRI = "https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/National_Risk_Index_Census_Tracts/FeatureServer/0/query"
NRI_CODES = ("HWAV", "DRGT", "IFLD", "CFLD", "HRCN", "WFIR", "HAIL", "LNDS", "ERQK", "SWND", "TRND")


def nri(lat, lon):
    """FEMA National Risk Index tract record (same service as app/services/openaccess_native_fema_nri_context.py)."""
    fields = ["TRACTFIPS", "NRI_VER", "RISK_RATNG", "RISK_SCORE"] + [c + s for c in NRI_CODES for s in ("_RISKR", "_RISKS")]
    q = {"f": "json", "geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "inSR": 4326,
         "spatialRel": "esriSpatialRelIntersects", "outFields": ",".join(fields), "returnGeometry": "false"}
    try:
        return json.load(urllib.request.urlopen(NRI + "?" + urllib.parse.urlencode(q), timeout=60))["features"][0]["attributes"]
    except Exception as e:
        return {"error": type(e).__name__}


def aqueduct(lat, lon):
    try:
        from app.services import nature_aqueduct_local as aq
        st = aq.status()
        if not st["configured"]:
            return {"error": st["reason"]}
        r = aq.read_for_point(lat, lon)
        rows = r.get("baseline") or []
        return {"state": r.get("state"), "bws": [{k: v for k, v in row.items() if "bws" in k} for row in rows][:1]}
    except Exception as e:
        return {"error": type(e).__name__}


def main():
    load_env()
    res = json.loads(OUT.read_text()) if os.environ.get("NRI_ONLY") else {}
    for s, (lat, lon) in SITES.items():
        if os.environ.get("NRI_ONLY"):  # refresh only the FEMA NRI block (no GEE call)
            res[s]["nri"] = nri(lat, lon)
            continue
        try:
            g = asyncio.run(gee(lat, lon))
        except Exception as e:
            g = {"error": type(e).__name__}
        res[s] = {"gee": g, "nwi_500m": nwi(lat, lon, 500), "nwi_2km": nwi(lat, lon, 2000), "aqueduct": aqueduct(lat, lon), "nri": nri(lat, lon)}
    OUT.write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str)[:4000])


if __name__ == "__main__":
    main()
