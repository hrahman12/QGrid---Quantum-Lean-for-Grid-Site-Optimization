"""Run SeaBridgeAI climada_workers for the two QSiteProof sites; write raw JSON.

Usage (climada env python):  python run_climada.py <climada-stack dir> <out raw.json>
Env/paths come from the caller's environment (CLIMADA_* names); nothing secret is read here.
"""
import json, subprocess, sys, os
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
STACK, OUT = sys.argv[1], sys.argv[2]
SITES = {"alviso": ("Alviso / North San Jose, CA", 37.4265, -121.975),
         "novva": ("NOVVA Colorado Springs, CO", 39.0130, -104.8164)}
HAZ = ["river_flood", "wildfire", "coastal_surge", "seasonal_heat"]
CASES = [("historical", "2025"), ("SSP245", "2050")]

def run(job):
    site, hz, scen, per = job
    name, lat, lon = SITES[site]
    p = {"location": {"property_id": site, "address": name, "lat": lat, "lon": lon},
         "scenario": scen, "period": per, "n_years": 300}
    env = dict(os.environ, PYTHONPATH=STACK, PYTHONIOENCODING="utf-8")
    try:
        r = subprocess.run([sys.executable, "-m", f"climada_workers.{hz}"], input=json.dumps(p).encode(),
                           capture_output=True, cwd=STACK, env=env, timeout=420)
        return job, json.loads(r.stdout.decode())
    except Exception as e:  # keep going; record failure
        return job, {"metadata": {"status": "error", "error": repr(e)[:300]}}

jobs = [(s, h, sc, pe) for s in SITES for h in HAZ for sc, pe in CASES]
with ThreadPoolExecutor(4) as ex:
    res = list(ex.map(run, jobs))
json.dump([{"site": j[0], "hazard": j[1], "case": f"{j[2]}/{j[3]}", "out": o} for j, o in res], open(OUT, "w"), indent=1)
for j, o in res:
    print(j, o.get("metadata", {}).get("status"), o.get("intensity_p50"), o.get("intensity_p95"), o.get("frequency_per_year"), (o.get("metadata", {}).get("reason") or o.get("metadata", {}).get("error") or "")[:110])
