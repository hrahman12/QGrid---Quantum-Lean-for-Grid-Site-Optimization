"""measurements.json (+ cited FEMA/HFTD from data/l2/site_risk.json) -> alviso.json, novva.json with RED/AMBER/GREEN.
Usage: python data/shared/nature/build_nature.py   (no network, no credentials)"""
import json
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[2]
DATE = "2026-11-08"
ORDER = {"GREEN": 0, "AMBER": 1, "RED": 2}
NATURAL = {"10": "tree", "20": "shrub", "30": "grass", "90": "herbaceous wetland", "95": "mangrove"}
VEG_WETLAND = ("Estuarine and Marine Wetland", "Freshwater Emergent Wetland", "Freshwater Forested/Shrub Wetland", "Freshwater Pond")
GEE = "Google Earth Engine via SeaBridgeAI GEERestAdapter (seabridge_ai/src/sustainability_ai/gis/adapters/earth_observation/gee_rest_adapter.py)"
NWI = "USFWS National Wetlands Inventory REST (service of SeaBridgeAI app/services/openaccess_native_nwi_wetland_context.py)"
SITES = {
    "alviso": {"id": "nsj-alviso-150", "name": "Alviso / North San Jose, CA (illustrative 150 MW)", "lat": 37.4265, "lon": -121.975,
               "headline": "Refuge beside site; very high flood",
               "species": ("Western burrowing owl (CA Species of Special Concern; CESA candidate 2024) uses ruderal grassland in "
                           "Alviso / North San Jose; covered species of the Santa Clara Valley Habitat Plan, so pre-construction "
                           "surveys and fees likely apply.", "AMBER", "cited",
                           "Santa Clara Valley Habitat Plan https://www.scv-habitatagency.org/ ; CDFW burrowing owl status (not re-fetched today)"),
               "water": ("High (unverified)", "RED"),
               "heat_days": 9.2},
    "novva": {"id": "novva-colorado-springs", "name": "NOVVA Colorado Springs, CO (650 Sybilla Ln)", "lat": 39.0130, "lon": -104.8164,
              "headline": "Low change; high wildfire and hail",
              "species": ("No species screen run. Preble's meadow jumping mouse (ESA threatened) has riparian habitat along "
                          "El Paso County Front Range creeks; check USFWS IPaC before ground disturbance.", "AMBER", "assumed",
                          "our inference; USFWS IPaC https://ipac.ecosphere.fws.gov/ not queried"),
              "water": ("Medium-High to High (unverified)", "AMBER"),
              "heat_days": 1.4},
}


def ind(name, modality, value, unit, rag, rule, source, method, note=None):
    d = {"name": name, "modality": modality, "value": value, "unit": unit, "rag": rag, "rule": rule,
         "source": source, "method": method, "date": DATE}
    if note:
        d["note"] = note
    return d


def band(x, amber, red, higher_is_worse=True):
    if not higher_is_worse:
        x, amber, red = -x, -amber, -red
    return "RED" if x >= red else "AMBER" if x >= amber else "GREEN"


NRI_SRC = ("FEMA National Risk Index, census-tract rating (method of SeaBridgeAI "
           "app/services/openaccess_native_fema_nri_context.py)")
NRI_HAZ = [("HWAV", "Extreme heat (heat waves)"), ("DRGT", "Drought"), ("IFLD", "Riverine flooding"),
           ("CFLD", "Coastal flooding (storm surge, high tides)"), ("HRCN", "Hurricane wind"), ("SWND", "Strong wind / storms"),
           ("TRND", "Tornado"), ("HAIL", "Hail"), ("WFIR", "Wildfire"), ("LNDS", "Landslide"), ("ERQK", "Earthquake")]
NRI_RAG = {"Very High": "RED", "Relatively High": "AMBER", "Relatively Moderate": "AMBER"}


def nri_indicators(n):
    out = []
    for code, name in NRI_HAZ:
        r = n.get(f"{code}_RISKR")
        if r is None:
            continue
        sc = n.get(f"{code}_RISKS")
        out.append(ind(f"{name} (FEMA risk index)", "vector", r, f"FEMA NRI rating; score {round(sc) if sc is not None else 'n/a'}/100 vs US tracts",
                       NRI_RAG.get(r, "GREEN"), "RED Very High, AMBER Relatively High or Moderate, GREEN Low / Very Low / No Rating / Not Applicable",
                       NRI_SRC + f", tract {n.get('TRACTFIPS')}, {n.get('NRI_VER')}", "openaccess",
                       "tract-level expected-loss index, not a parcel or engineering assessment"))
        out[-1]["score"] = round(sc or 0, 1)
    return out


SPECIES_LINE = {"Western burr": "Burrowing owls, a protected species, use grassland around Alviso, so surveys and habitat-plan fees likely apply.",
                "No species s": "No species check was run; a protected meadow mouse lives along nearby creeks, so check with US Fish and Wildlife first."}
VERDICT = {"RED": "a serious issue for this site", "AMBER": "manageable, but plan for it", "GREEN": "not a concern here"}


def line(i):
    """One plain-English sentence per indicator."""
    n, v, r = i["name"], i["value"], i["rag"]
    if "(FEMA risk index)" in n:
        h = n.replace(" (FEMA risk index)", "")
        if v in ("Not Applicable", "No Rating"):
            return f"{h}: FEMA does not rate this hazard for the area, so treat it as low."
        return f"{h}: FEMA rates the risk for this neighbourhood as {v.lower()}, {VERDICT[r]}."
    if n.startswith("Land-surface change"):
        return f"Satellite embeddings show {v}% of the ground within 500 m changed since 2017, so little recent disturbance."
    if n.startswith("Natural land cover"):
        return f"{v}% of the land within 1 km is trees, grass, shrubs or wetland; {i['note']}."
    if n.startswith("Vegetation greenness"):
        return f"The site area is sparsely vegetated (greenness {v} on a 0-1 scale), so clearing removes little plant cover."
    if n.startswith("Summer daytime land"):
        return f"Summer ground surface reaches about {v} C in the day, which trims free-cooling hours."
    if n.startswith("Distance to nearest protected"):
        return f"The nearest protected area, {i['note'].split(' (')[0]}, is {v} km away."
    if n.startswith("Mapped vegetated wetlands"):
        return f"About {v} acres of mapped wetland lie within 500 m, so wetland permits and buffers are likely." if r == "RED" else                f"Little mapped wetland right at the site; {i['note'].split(';')[0]}."
    if n.startswith("Sensitive species"):
        return SPECIES_LINE[v[:12]]
    if n.startswith("Baseline water stress"):
        return f"Local water supply stress is likely {v.split(' (')[0].lower()} (not yet checked against WRI data), so water-free cooling matters."
    if n.startswith("FEMA flood zone"):
        return ("The site sits in FEMA's 1-in-100-year flood zone; equipment must be raised above flood level." if r == "AMBER"
                else "The site is outside FEMA's mapped 1-in-100-year flood zone.")
    if n.startswith("CPUC High Fire"):
        return f"Not in a California high-fire-threat district (nearest is {v} km away), so planned power shutoffs are less likely."
    if n.startswith("Wildfire (WUI)"):
        return "The site is in a wildland-urban edge area; no parcel-level wildfire score was pulled."
    if n.startswith("Hot days"):
        return f"Climate models project about {v} days a year above 35 C by 2036-2050."
    return f"{n}: {v}."


def build(key, m, risk_point):
    s, g = SITES[key], m["gee"]
    out = []
    e = g["embedding_2017_2024"]
    chg = round(100 * e["changed"], 1)
    out.append(ind("Land-surface change 2017->2024 (AlphaEarth embeddings)", "imagery-embedding", chg, "% of 10 m pixels within 500 m with cosine < 0.8",
                   band(chg, 10, 25), "GREEN <10%, AMBER 10-25%, RED >=25%",
                   "GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL 2017 vs 2024; " + GEE, "alphageo",
                   f"mean cosine similarity {e['cos']:.3f}"))
    wc = {k: v for k, v in g["worldcover_1km"]["Map"].items()}
    tot = sum(wc.values())
    nat = round(100 * sum(v for k, v in wc.items() if k in NATURAL) / tot, 1)
    built = round(100 * wc.get("50", 0) / tot, 1)
    out.append(ind("Natural land cover within 1 km", "raster", nat, "% (tree+shrub+grass+wetland)", band(nat, 30, 60),
                   "GREEN <30%, AMBER 30-60%, RED >=60%", "ESA WorldCover v200 (2021, 10 m); " + GEE, "alphageo",
                   f"built-up {built}%, water {round(100 * wc.get('80', 0) / tot, 1)}%"))
    ndvi = round(g["ndvi_500m"]["ndvi"], 2)
    out.append(ind("Vegetation greenness (NDVI) within 500 m", "raster", ndvi, "NDVI, Sentinel-2 Jun-Aug 2024 median",
                   band(ndvi, 0.3, 0.5), "GREEN <0.30, AMBER 0.30-0.50, RED >=0.50", "COPERNICUS/S2_SR_HARMONIZED; " + GEE, "alphageo"))
    lst = round(g["lst_summer_day_c"]["LST_Day_1km"], 1)
    out.append(ind("Summer daytime land surface temperature", "raster", lst, "degC, MODIS MOD11A2 Jun-Aug 2024 mean (1 km)",
                   band(lst, 30, 38), "GREEN <30, AMBER 30-38, RED >=38 degC", "MODIS/061/MOD11A2; " + GEE, "alphageo",
                   "surface (not air) temperature; affects dry-cooler and economizer hours"))
    wd = g["wdpa_20km"]
    km = round(wd["dist_m"] / 1000, 2) if wd.get("n") else None
    out.append(ind("Distance to nearest protected area", "vector", km, "km",
                   "GREEN" if km is None else band(km, 5, 1, higher_is_worse=False), "RED <1 km, AMBER 1-5 km, GREEN >=5 km",
                   "WDPA current polygons (WCMC/WDPA/current/polygons); " + GEE, "openaccess",
                   f"{wd.get('name')} ({wd.get('desig')}, IUCN {wd.get('iucn')}); {wd.get('n', 0)} protected areas within 20 km"))
    w5 = sum(v for k, v in m["nwi_500m"]["acres_by_type"].items() if k in VEG_WETLAND)
    w2 = sum(v for k, v in m["nwi_2km"]["acres_by_type"].items() if k in VEG_WETLAND)
    out.append(ind("Mapped vegetated wetlands within 500 m", "vector", round(w5, 1), "acres (NWI, excl. deepwater/lake/river)",
                   "RED" if w5 >= 5 else "AMBER" if w2 >= 10 else "GREEN",
                   "RED >=5 ac within 500 m, AMBER >=10 ac within 2 km, else GREEN", NWI, "openaccess",
                   f"{round(w2, 1)} ac within 2 km; NWI is not a jurisdictional delineation"))
    sp = s["species"]
    out.append(ind("Sensitive species / habitat", "text", sp[0], "text", sp[1], "AMBER when a listed or special-concern species is likely on or near site",
                   sp[3], sp[2]))
    out.append(ind("Baseline water stress", "text", s["water"][0], "WRI Aqueduct 4.0 category", s["water"][1],
                   "RED High/Extremely High, AMBER Medium-High, GREEN Low/Low-Medium",
                   "WRI Aqueduct 4.0 https://www.wri.org/applications/aqueduct/water-risk-atlas/ (not queried)", "assumed",
                   "SeaBridgeAI nature_aqueduct_local reader present but its Aqueduct 4.0 GDB is not on this machine"))
    fl = risk_point["flood"] if risk_point else None
    if fl:
        out.append(ind("FEMA flood zone", "vector", fl["zone"], "FEMA NFHL zone", "AMBER" if fl["sfha"] else "GREEN",
                       "AMBER in SFHA (permit condition: equipment above BFE), GREEN outside", "data/l2/site_risk.json (FEMA NFHL via Esri Living Atlas)", "cited",
                       f"BFE {fl['bfe_ft']} ft"))
        fi = risk_point["fire"]
        out.append(ind("CPUC High Fire Threat District", "vector", fi["nearest_hftd_km"], "km to nearest HFTD",
                       "AMBER" if fi["in_hftd_tier2_3"] else "GREEN", "AMBER inside Tier 2/3 (PSPS exposure), else GREEN",
                       "data/l2/site_risk.json (CPUC HFTD v22_3 via PG&E GRIP)", "cited", f"nearest: {fi['nearest_hftd']['cpuc_fire_map']}"))
    else:
        out.append(ind("FEMA flood zone", "vector", "not in mapped SFHA", "FEMA NFHL zone", "GREEN", "AMBER in SFHA, GREEN outside",
                       "FEMA NFHL via Esri Living Atlas reduced set, point query 2026-11-08 (no polygon returned)", "cited",
                       "Zone X not confirmed on the FEMA MSC panel"))
        out.append(ind("Wildfire (WUI)", "text", "Colorado Springs WUI region; no parcel-level hazard layer retrieved", "text", "AMBER",
                       "AMBER in a wildland-urban interface region without a parcel hazard score", "our inference", "assumed"))
    out.append(ind("Hot days 2036-2050 (Tmax > 35 C)", "raster", s["heat_days"], "days/yr, SSP5-8.5, 4-model mean",
                   band(s["heat_days"], 5, 30), "GREEN <5, AMBER 5-30, RED >=30 days/yr",
                   "Open-Meteo Climate API (CMIP6 HighResMIP), heat_openmeteo.py", "cited"))
    out += nri_indicators(m["nri"])
    for i in out:
        i["line"] = line(i)
    rag = max((i["rag"] for i in out), key=ORDER.get)
    # measured first, then worst RAG; FEMA hazards ranked by national score, other measured indicators ahead of them on ties
    top = sorted(out, key=lambda i: (i["method"] == "assumed", i["name"].startswith("Earthquake"),  # not a climate/nature item
                                       -ORDER[i["rag"]], i["modality"] == "raster", -i.get("score", 100)))[:3]
    assert len(s["headline"].split()) == 6, s["headline"]
    return {"site": {k: s[k] for k in ("id", "name", "lat", "lon")}, "generated": DATE,
            "nature_rag": rag, "headline": s["headline"],
            "rule": "overall = worst indicator RAG; hazards from FEMA NRI tract ratings, nature from AlphaEarth/GEE, WDPA, NWI; modality: imagery-embedding|raster|vector|text; method: alphageo|openaccess|cited|assumed",
            "top3": [i["name"] for i in top], "indicators": out}


def main():
    m = json.loads((HERE / "measurements.json").read_text())
    risk = json.loads((ROOT / "data/l2/site_risk.json").read_text())
    site_pt = next(p for p in risk["points"] if p["kind"] == "site")
    for key in SITES:
        d = build(key, m[key], site_pt if key == "alviso" else None)
        (HERE / f"{key}.json").write_text(json.dumps(d, indent=1) + "\n")
        print(key, d["nature_rag"], d["headline"])
        for i in d["indicators"]:
            print(f"  {i['rag']:5} {i['modality']:17} {i['method']:10} {i['name']}: {i['value']} {i['unit']}")


if __name__ == "__main__":
    main()
