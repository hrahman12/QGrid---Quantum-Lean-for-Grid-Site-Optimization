"""QSiteProof - live grid scraper + visual dashboard.

Pulls CAISO's public live feeds (today's 5-min demand, net demand, fuel mix,
batteries, CO2, system stats) and real-time LMPs from CAISO OASIS for the
NP15 hub (PG&E / North San Jose pricing zone), then writes
data/live_grid.json and dashboard/live_grid.html.

Run:  python scrape_live_grid.py
"""
import csv, io, json, zipfile, datetime as dt, urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
RAW = ROOT / "data" / "raw"; RAW.mkdir(parents=True, exist_ok=True)
DASH = ROOT / "dashboard"; DASH.mkdir(exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (QSiteProof hack prototype)"}
OUTLOOK = "https://www.caiso.com/outlook/current/{}"
FEEDS = ["demand", "netdemand", "fuelsource", "storage", "co2"]
NODES = ["TH_NP15_GEN-APND"]


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def read_csv(text):
    rows = list(csv.DictReader(io.StringIO(text)))
    cols = {k: [num(r[k]) if k != "Time" else r[k] for r in rows] for k in rows[0]} if rows else {}
    return cols


def scrape():
    out = {"scraped_at": dt.datetime.now().isoformat(timespec="seconds"), "feeds": {}}
    for f in FEEDS:
        txt = get(OUTLOOK.format(f + ".csv")).decode("utf-8", "replace")
        (RAW / f"live_{f}.csv").write_text(txt)
        out["feeds"][f] = read_csv(txt)
    stats = get(OUTLOOK.format("stats.txt")).decode()
    (RAW / "live_stats.json").write_text(stats)
    out["stats"] = json.loads(stats)

    # Real-time 5-min LMP (OASIS), today in Pacific time (UTC-8 in Nov).
    day = dt.datetime.utcnow().strftime("%Y%m%d")
    url = ("https://oasis.caiso.com/oasisapi/SingleZip?queryname=PRC_INTVL_LMP"
           f"&startdatetime={day}T08:00-0000&enddatetime={day}T23:59-0000&version=1"
           f"&market_run_id=RTM&node={','.join(NODES)}&resultformat=6")
    lmp = {}
    try:
        z = zipfile.ZipFile(io.BytesIO(get(url)))
        txt = z.read(z.namelist()[0]).decode()
        (RAW / "live_lmp.csv").write_text(txt)
        for r in csv.DictReader(io.StringIO(txt)):
            node, item = r["NODE"], r["XML_DATA_ITEM"]
            t = dt.datetime.fromisoformat(r["INTERVALSTARTTIME_GMT"]) - dt.timedelta(hours=8)
            lmp.setdefault(node, {}).setdefault(item, {})[t.strftime("%H:%M")] = float(r["MW"])
    except Exception as e:  # OASIS throttles; keep dashboard alive
        out["lmp_error"] = str(e)
    out["lmp"] = {n: {k: dict(sorted(v.items())) for k, v in d.items()} for n, d in lmp.items()}
    (ROOT / "data" / "live_grid.json").write_text(json.dumps(out))
    return out


def dashboard(d):
    html = (ROOT / "dashboard" / "template_live.html").read_text(encoding="utf-8")
    html = html.replace("/*__DATA__*/null", json.dumps(d))
    (DASH / "live_grid.html").write_text(html, encoding="utf-8")


if __name__ == "__main__":
    data = scrape()
    dashboard(data)
    s = data["stats"]
    print(f"Scraped {data['scraped_at']}: demand now {s.get('CurrentSystemDemandWithoutPump')} MW, "
          f"peak fcst {s.get('todayForecastPeakDemand')} MW, solar {s.get('currentSolar')} MW")
    print("LMP nodes:", list(data["lmp"]), data.get("lmp_error", ""))
    print("Dashboard ->", DASH / "live_grid.html")
