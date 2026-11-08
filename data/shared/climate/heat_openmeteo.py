"""Days/yr with Tmax >35C, 1995-2014 vs 2036-2050 (SSP5-8.5), Open-Meteo Climate API (CMIP6 HighResMIP, raw/no bias correction).
Usage: python heat_openmeteo.py out.json"""
import json, sys, time, urllib.request, urllib.error, statistics
SITES = {"alviso": (37.4265, -121.975), "novva": (39.0130, -104.8164)}
MODELS = ["EC_Earth3P_HR", "MRI_AGCM3_2_S", "CMCC_CM2_VHR4", "MPI_ESM1_2_XR"]
WIN = {"base_1995_2014": (1995, 2014), "fut_2036_2050": (2036, 2050)}
def get(lat, lon, a, b):
    u = (f"https://climate-api.open-meteo.com/v1/climate?latitude={lat}&longitude={lon}&start_date={a}-01-01&end_date={b}-12-31"
         f"&models={','.join(MODELS)}&daily=temperature_2m_max")
    for i in range(8):
        try:
            return json.load(urllib.request.urlopen(u, timeout=90))["daily"]
        except urllib.error.HTTPError as e:
            if e.code != 429: raise
            time.sleep(30 * (i + 1))
    raise RuntimeError("rate limited")
out = {}
for s, (lat, lon) in SITES.items():
    out[s] = {}
    for k, (a, b) in WIN.items():
        d = get(lat, lon, a, b); time.sleep(5)
        for m in MODELS:
            v = [x for x in d.get(f"temperature_2m_max_{m}", []) if x is not None]
            out[s].setdefault(m, {})[k] = {"d35_per_yr": round(sum(x > 35 for x in v) / (b - a + 1), 2), "mean_tmax_C": round(statistics.mean(v), 2), "n": len(v)} if v else {"error": "no data"}
json.dump(out, open(sys.argv[1], "w"), indent=1)
print(json.dumps(out))
