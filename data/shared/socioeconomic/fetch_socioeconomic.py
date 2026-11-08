#!/usr/bin/env python3
"""Build alviso.json / novva.json (socioeconomic layer). No secrets are written.

Run:  python fetch_socioeconomic.py [--lead-dir DIR]
Env:  EIA_API_KEY (read at runtime, never printed) or EIA_ENV_FILE=path to a .env containing it.
      If neither is set, EIA rows already in the existing output are kept.
LEAD (DOE energy burden) needs the ~1GB OpenEI state zips (https://data.openei.org/files/6219/CA-2022-LEAD-data.zip, CO likewise);
pass --lead-dir with them downloaded, otherwise LEAD rows already in the existing output are kept.
"""
import time, argparse, collections, csv, datetime as dt, io, json, os, re, urllib.parse, urllib.request, zipfile
from pathlib import Path

OUT = Path(__file__).resolve().parent
TODAY = dt.date.today().isoformat()
ACS_YEAR = 2024  # ACS 5-year 2020-2024

SITES = {
    "alviso": dict(name="Alviso / North San Jose, CA", lat=37.4265, lon=-121.975, state="CA", st="06", county="085",
                   county_name="Santa Clara County", city="San Jose"),
    "novva": dict(name="NOVVA Colorado Springs, CO", lat=39.0130, lon=-104.8164, state="CO", st="08", county="041",
                  county_name="El Paso County", city="Colorado Springs"),
}


def jget(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "qgrid-socioeconomic/1.0"})
    for attempt in range(5):  # data.census.gov intermittently answers 204 (empty body)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
        if body:
            return json.loads(body)
        time.sleep(2 * (attempt + 1))
    raise RuntimeError("empty response: " + url.split("api_key=")[0][:120])


def ind(name, value, unit, plain, rag, rule, source, method, date=TODAY, scored=True, note=None):
    d = dict(name=name, value=value, unit=unit, plain_english=plain, rag=rag, rag_rule=rule, source=source,
             method=method, date=date, scored=scored)
    if note:
        d["note"] = note
    return d


def band(v, green_lt, red_ge):
    return "GREEN" if v < green_lt else ("RED" if v >= red_ge else "AMBER")


def acs_profile(geoid_param):
    """ACS 5-yr data profile via the data.census.gov table API (api.census.gov now demands a key)."""
    vals = {}
    for t in ("DP03", "DP04", "DP05"):
        data = jget(f"https://data.census.gov/api/access/data/table?id=ACSDP5Y{ACS_YEAR}.{t}&g={geoid_param}")["response"]["data"]
        vals.update(dict(zip(data[0], data[1])))
    f = lambda k: float(vals[k])
    return dict(pop=f("DP05_0001E"), age=f("DP05_0018E"), income=f("DP03_0062E"), poverty=f("DP03_0128PE"),
                unemp=f("DP03_0009PE"), renters=f("DP04_0047PE"))


def eia_prices(state):
    key = os.environ.get("EIA_API_KEY")
    envf = Path(os.environ.get("EIA_ENV_FILE", "/nonexistent"))
    if not key and envf.is_file():
        m = re.search(r"^EIA_API_KEY=(.+)$", envf.read_text(encoding="utf-8", errors="ignore"), re.M)
        key = m.group(1).strip().strip("\"'") if m else None
    if not key:
        return {}
    out = {}
    for sec in ("COM", "IND"):
        q = (f"https://api.eia.gov/v2/electricity/retail-sales/data/?api_key={key}&frequency=annual&data[0]=price"
             f"&facets[stateid][]={state}&facets[sectorid][]={sec}&sort[0][column]=period&sort[0][direction]=desc&length=1")
        rows = jget(q)["response"]["data"]
        if rows:
            out[sec] = (float(rows[0]["price"]), rows[0]["period"])
    return out


def calenviroscreen(tract):
    u = ("https://services.arcgis.com/yq3FgOI44hYHAFVZ/ArcGIS/rest/services/CES4_Percentile/FeatureServer/0/query?"
         + urllib.parse.urlencode(dict(where=f"Tract={int(tract)}", outFields="CIscoreP,Pollution_Pctl,PopCharP,ApproxLoc",
                                       returnGeometry="false", f="json")))
    return jget(u)["features"][0]["attributes"]


def co_enviroscreen(geoid):
    u = ("https://services3.arcgis.com/66aUo8zsujfVXRIT/ArcGIS/rest/services/ColoradoEnviroScreen_v2_Tract_24118_Final/"
         "FeatureServer/0/query?" + urllib.parse.urlencode(dict(where="GEOID='%s'" % geoid, outFields="ES_S_,Envrnmnt_2,D_S_P",
                                                                 returnGeometry="false", f="json")))
    return jget(u)["features"][0]["attributes"]


def lead_burden(zp, state, st, county, tract_fips):
    """Aggregate energy cost / aggregate income (electric+gas+other fuel), all households and <=80% AMI."""
    z = zipfile.ZipFile(zp)
    res = {}
    for scope, fn, key in (("county", f"{state} AMI Counties 2022.csv", str(int(st + county))),
                           ("tract", f"{state} AMI Census Tracts 2022.csv", str(int(tract_fips)))):
        S = collections.defaultdict(lambda: [0.0, 0.0])
        with z.open(fn) as f:
            for row in csv.DictReader(io.TextIOWrapper(f, "utf-8-sig")):
                if row["FIP"].lstrip("0") != key:
                    continue
                try:
                    inc = float(row["HINCP*UNITS"])
                    en = sum(float(row[k] or 0) for k in ("ELEP*UNITS", "GASP*UNITS", "FULP*UNITS"))
                except ValueError:
                    continue
                keys = ("all", "low") if row["AMI150"] in ("0-30%", "30-60%", "60-80%") else ("all",)
                for k in keys:
                    S[k][0] += inc
                    S[k][1] += en
        res[scope] = {k: round(v[1] / v[0] * 100, 2) for k, v in S.items() if v[0]}
    return res


def build(slug, s, lead_dir, prev):
    geo = jget(f"https://geo.fcc.gov/api/census/block/find?latitude={s['lat']}&longitude={s['lon']}&format=json")
    block = geo["Block"]["FIPS"]
    tract = block[:11]
    assert block[:5] == s["st"] + s["county"], "FCC county mismatch"
    tr = acs_profile(f"1400000US{tract}")
    co = acs_profile(f"0500000US{s['st']}{s['county']}")
    us = acs_profile("0100000US")
    acs_src = (f"US Census Bureau ACS 5-year {ACS_YEAR-4}-{ACS_YEAR} Data Profiles DP03/DP04/DP05, tract {tract}, via "
               f"data.census.gov table API (https://data.census.gov/api/access/data/table?id=ACSDP5Y{ACS_YEAR}.DP03&g=1400000US{tract})")
    vint = f"ACS {ACS_YEAR-4}-{ACS_YEAR}"
    I = []
    I.append(ind("Population (census tract)", tr["pop"], "people", f"About {tr['pop']:,.0f} people live in the neighbourhood tract around the site.",
                 "GREEN", "context only, not scored", acs_src, "api", vint, scored=False))
    r = tr["income"] / us["income"]
    I.append(ind("Median household income (tract)", tr["income"], "USD/yr",
                 f"A typical household here earns about ${tr['income']:,.0f} a year ({r*100:.0f}% of the US median ${us['income']:,.0f}).",
                 "GREEN" if r >= 1 else ("AMBER" if r >= .75 else "RED"),
                 "tract median / US median: >=100% GREEN, 75-100% AMBER, <75% RED (low-income areas feel power-bill and rent pressure more)", acs_src, "api", vint))
    I.append(ind("Poverty rate (tract)", tr["poverty"], "% of people",
                 f"About {tr['poverty']:.0f} in 100 people live below the federal poverty line.",
                 band(tr["poverty"], 10, 15), "<10% GREEN, 10-15% AMBER, >=15% RED", acs_src, "api", vint))
    I.append(ind("Unemployment rate (tract)", tr["unemp"], "% of labour force",
                 f"About {tr['unemp']:.1f} in 100 people in the labour force are out of work.",
                 band(tr["unemp"], 4, 7), "<4% GREEN (tight labour market, hard to hire), 4-7% AMBER, >=7% RED (community need, jobs promises scrutinised)", acs_src, "api", vint))
    I.append(ind("Renter households (tract)", tr["renters"], "% of homes",
                 f"About {tr['renters']:.0f} in 100 homes are rented, so more neighbours are exposed to rent and bill changes.",
                 band(tr["renters"], 35, 55), "<35% GREEN, 35-55% AMBER, >=55% RED (renters have less control over costs and less stake in property-tax gains)", acs_src, "api", vint))
    I.append(ind("Median age (tract)", tr["age"], "years", f"Half the residents are younger than {tr['age']:.0f}.",
                 "GREEN" if 30 <= tr["age"] <= 50 else "AMBER", "30-50 GREEN else AMBER; context, not scored", acs_src, "api", vint, scored=False))
    I.append(ind(f"Median household income ({s['county_name']})", co["income"], "USD/yr",
                 f"Across {s['county_name']}, a typical household earns about ${co['income']:,.0f}.", "GREEN", "context only, not scored",
                 acs_src.replace(f"tract {tract}", f"county {s['st']}{s['county']}").replace(f"1400000US{tract}", f"0500000US{s['st']}{s['county']}"),
                 "api", vint, scored=False))
    p = eia_prices(s["state"])
    if p:
        sec_name = {"COM": "commercial", "IND": "industrial"}
        for sec, (price, per) in p.items():
            I.append(ind(f"Retail electricity price, {sec_name[sec]} ({s['state']})", round(price, 2), "cents/kWh",
                         f"Businesses in {s['state']} pay about {price:.1f} cents per kWh for power ({sec_name[sec]} customers).",
                         ("RED" if price >= 12 else "AMBER" if price >= 7 else "GREEN") if sec == "IND"
                         else ("RED" if price >= 15 else "AMBER" if price >= 9 else "GREEN"),
                         "industrial: <7 GREEN, 7-12 AMBER, >=12 RED; commercial: <9 GREEN, 9-15 AMBER, >=15 RED (operating-cost risk, not community risk)",
                         "EIA Electricity retail-sales API v2 (https://api.eia.gov/v2/electricity/retail-sales/), state annual average price",
                         "api", per, scored=(sec == "IND")))
    elif prev:
        I.extend(i for i in prev if i["name"].startswith("Retail electricity price"))
    z = Path(lead_dir or ".") / f"{s['state']}-2022-LEAD-data.zip"
    if z.is_file():
        lb = lead_burden(z, s["state"], s["st"], s["county"], tract)
        c_low, c_all, t_low = lb["county"].get("low"), lb["county"].get("all"), lb["tract"].get("low")
        I.append(ind(f"Energy burden, low-income households ({s['county_name']})", c_low, "% of income",
                     f"Lower-income households here spend about {c_low:.0f}% of their income on home energy (6% or more is considered high).",
                     "RED" if c_low >= 6 else "AMBER" if c_low >= 4 else "GREEN", "DOE high-burden threshold 6%: >=6 RED, 4-6 AMBER, <4 GREEN",
                     "DOE/NREL LEAD Tool 2022 data (OpenEI submission 6219, https://data.openei.org/submissions/6219), ACS-based; computed here as "
                     "sum(energy cost)/sum(income) over households at <=80% area median income",
                     "cited", "2022 (LEAD 2022 update)",
                     note=f"all households in county: {c_all}%; low-income households in the tract: {t_low}% (small ACS sample, noisy)"))
    elif prev:
        I.extend(i for i in prev if i["name"].startswith("Energy burden"))
    if slug == "alviso":
        e = calenviroscreen(tract)
        v = round(e["CIscoreP"], 1)
        I.append(ind("CalEnviroScreen 4.0 overall percentile (tract)", v, "percentile (100 = most burdened in CA)",
                     f"This neighbourhood is more pollution-burdened and vulnerable than about {v:.0f}% of California neighbourhoods.",
                     "RED" if v >= 75 else "AMBER" if v >= 50 else "GREEN",
                     ">=75 (state 'disadvantaged community' line, SB 535) RED, 50-75 AMBER, <50 GREEN; high burden = community-acceptance risk",
                     "OEHHA CalEnviroScreen 4.0, CalEPA/OEHHA ArcGIS layer CES4_Percentile (https://oehha.ca.gov/calenviroscreen/report/calenviroscreen-40)",
                     "api", "2021-10 (CES 4.0 release)",
                     note=f"pollution-burden percentile {e['Pollution_Pctl']:.0f}, population-characteristics percentile {e['PopCharP']:.0f}; locale {e['ApproxLoc']}"))
    else:
        e = co_enviroscreen(tract)
        v = round(e["ES_S_"], 1)
        I.append(ind("Colorado EnviroScreen v2 overall percentile (tract)", v, "percentile (100 = most burdened in CO)",
                     f"This neighbourhood is more pollution-burdened and vulnerable than about {v:.0f}% of Colorado neighbourhoods.",
                     "RED" if v >= 80 else "AMBER" if v >= 60 else "GREEN",
                     ">=80 (Colorado 'disproportionately impacted' line, CDPHE) RED, 60-80 AMBER, <60 GREEN; high burden = community-acceptance risk",
                     "CDPHE/CSU Colorado EnviroScreen v2.0 census-tract layer (https://cdphe.colorado.gov/enviroscreen)", "api", "2024-11 (v2.0 release)",
                     note=f"environmental exposures percentile {e['Envrnmnt_2']:.0f}, demographics percentile {e['D_S_P']:.0f}. EPA EJScreen was taken offline in 2025, so CDPHE EnviroScreen is used instead."))
    I.append(ind("Permanent data-center jobs per 100 MW", "20-40", "jobs per 100 MW (estimate)",
                 "A 100 MW data center employs only about 20-40 people once built.", "AMBER",
                 "<50 permanent jobs per 100 MW = AMBER (small direct local employment benefit)",
                 "Hamm Institute data-center workforce forecast, Nov 2025 (20-30 per 100 MW) and Latitude Media benchmark (25-40 per 100 MW for automated campuses); both seen via a secondary roundup, not re-verified",
                 "cited", "2025-11", note="estimate; Uptime Institute figures cited elsewhere are higher (100-200 ops roles per 100 MW hyperscale campus)"))
    I.append(ind("Peak construction workers per 100 MW", "70-200", "workers per 100 MW (estimate)",
                 "Building 100 MW needs roughly 70-200 workers on site at the busiest point, for about 1.5-3 years.", "GREEN",
                 "temporary jobs, informational only (not scored)",
                 "Chmura Economics article citing a workforce study of 0.7-2.0 peak direct construction workers per MW (underlying study not located; unverified)",
                 "cited", "2026", scored=False,
                 note="Apollo Technical 2026 tracker reports ~4.1 per MW at campus peak (median of 19 campuses), so the real number could be about 2x higher"))
    if slug == "alviso":
        pt = ("California: 1% Prop 13 base rate plus voter-approved debt, about 1.15% of assessed value in San Jose Unified (Santa Clara County Assessor "
              "tax-rate compilation); Prop 13 limits assessed value to purchase price +2%/yr. Assumes $1.0B taxable value per 100 MW (illustrative, not sourced).", 11.5)
    else:
        pt = ("Colorado: 25% non-residential assessment rate (El Paso County Assessor, 2026) x ~67 mills (unverified aggregator estimate; varies by taxing district) "
              "= ~1.7% of market value. Assumes $1.0B taxable value per 100 MW (illustrative, not sourced).", 17.0)
    I.append(ind("Property-tax contribution per 100 MW (estimate)", pt[1], "USD million/yr per 100 MW (ASSUMED)",
                 f"A 100 MW data center might pay roughly ${pt[1]:.0f} million a year in property tax before any abatement or equipment depreciation.",
                 "AMBER", "AMBER while abatements and equipment depreciation are unknown; GREEN needs a signed agreement showing net payments above $5M/yr per 100 MW",
                 pt[0], "assumed", TODAY, note="order of magnitude only; real bills are lower after server depreciation and any negotiated abatement"))
    scored = [i for i in I if i["scored"]]
    reds = sum(i["rag"] == "RED" for i in scored)
    ambers = sum(i["rag"] == "AMBER" for i in scored)
    ej = next(i for i in I if "EnviroScreen" in i["name"])
    overall = "RED" if reds >= 2 or ej["rag"] == "RED" else ("GREEN" if reds == 0 and ambers <= 1 else "AMBER")
    return dict(site=s["name"], lat=s["lat"], lon=s["lon"], city=s["city"], county=s["county_name"], county_fips=s["st"] + s["county"],
                tract_geoid=tract, generated=TODAY, acs_vintage=f"{ACS_YEAR-4}-{ACS_YEAR} 5-year", overall_rag=overall,
                overall_rule="RED if the EJ indicator is RED or >=2 scored indicators are RED; GREEN if no RED and <=1 AMBER; else AMBER",
                counts=dict(red=reds, amber=ambers, green=len(scored) - reds - ambers), headline="", indicators=I)


# Six words each; edit after reviewing the numbers.
HEADLINES = {"alviso": "Pricey power, mixed burden, modest jobs",
             "novva": "Cheaper power, low-burden tract, modest jobs"}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--lead-dir")
    a = ap.parse_args()
    for slug, s in SITES.items():
        f = OUT / f"{slug}.json"
        prev = json.loads(f.read_text())["indicators"] if f.is_file() else None
        d = build(slug, s, a.lead_dir, prev)
        d["headline"] = HEADLINES[slug]
        assert len(d["headline"].replace(",", "").split()) == 6, d["headline"]
        f.write_text(json.dumps(d, indent=2) + "\n")
        print(slug, d["overall_rag"], d["counts"])
