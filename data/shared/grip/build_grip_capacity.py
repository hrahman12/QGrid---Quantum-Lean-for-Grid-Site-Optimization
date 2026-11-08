"""Offline: raw/ (PG&E GRIP cache from fetch_grip.py) -> grip_capacity.json. Run: python build_grip_capacity.py

Directional data only. Not a PG&E interconnection or service approval.
Join: feeder_id[:5] == substation id (e.g. feeder 083611104 -> substation 08361 BRITTON).
Feeder max_load_hosting_mw = MAX of LoadCapacity_kW over the feeder's line sections (layer 3), in MW. GRIP gives no
feeder-head section id, so this is the best case on the feeder, not what a new load at an arbitrary point gets.
"""
import json, statistics
from pathlib import Path

HERE = Path(__file__).parent
MISSING = -99.99


def feats(n, ext="geojson"):
    return json.load(open(HERE / "raw" / f"layer_{n}.{ext}"))["features"]


def num(v):
    return None if v is None or v == MISSING else v


def mw(kw):
    return None if num(kw) is None or kw < 0 else round(kw / 1000, 3)


def month_hour(s):
    toks = [t.strip() for t in (s or "").split(",") if t.strip()]
    if len(toks) == 1:
        m, h = toks[0].split("_")
        return int(m), int(h), 1
    return None, None, len(toks)  # many tied hours (e.g. capacity 0 all year): no single limiting hour


def build():
    subs = {}
    for f in feats(0):
        p, (lon, lat) = f["properties"], f["geometry"]["coordinates"]
        subs[p["SubstationID"]] = dict(id=p["SubstationID"], name=p["SubstationName"].strip(), lat=round(lat, 6),
                                       lon=round(lon, 6), voltage_kv=p["Voltage_kV"], banks=[], feeders=[])
    feeder_rows = {}  # layer 31 FEEDER rows: feeder-level rating/loading, idnumber == feeder id
    for f in feats(31):
        p, (lon, lat) = f["properties"], f["geometry"]["coordinates"]
        if p["facilitytype"] == "FEEDER":
            feeder_rows[p["idnumber"]] = p
            continue
        s = subs.get(p["substationid"])
        if s is None:
            continue
        rating, f26, f28 = (num(p[k]) for k in ("facilityratingmw", "facilityloadingmw2026", "facilityloadingmw2028"))
        series = [num(p[f"facilityloadingmw{y}"]) for y in range(2026, 2041)]
        series = [x for x in series if x is not None]
        s["banks"].append(dict(
            id=p["idnumber"], name=p["bankname"].strip(), lat=round(lat, 6), lon=round(lon, 6), rating_mw=rating,
            forecast_load_mw={"2026": f26, "2028": f28}, peak_loading_pct=num(p["peakfacilityloadingpercent"]),
            max_forecast_loading_pct_2026_2040=round(100 * max(series) / rating, 1) if series and rating else None,
            pending_load_mw=None,  # GRIP pending load is per feeder, not per bank
            headroom_mw=None if rating is None or f28 is None else round(max(0, rating - f28), 2)))

    pending = {}
    for f in feats(33):
        p = f["properties"]
        pending.setdefault(p["feeder_id"], []).append(num(p["Expected_Load__Amount_MW"]))

    sections = {}
    for f in feats(3):
        sections.setdefault(f["properties"]["FeederId"], []).append(f["properties"])
    unjoined = []
    for fid, secs in sorted(sections.items()):
        vals = [(mw(p["LoadCapacity_kW"]), p) for p in secs]
        known = [(v, p) for v, p in vals if v is not None]
        best = max(known, key=lambda t: (t[0], month_hour(t[1]["limiting_month_hour"])[2] == 1))[1] if known else None
        top = max(v for v, _ in known) if known else None
        mon, hr, n = month_hour(best["limiting_month_hour"]) if best else (None, None, 0)
        pl = pending.get(fid, [])
        fr = feeder_rows.get(fid, {})
        entry = dict(feeder_id=fid, name=secs[0]["FeederName"], max_load_hosting_mw=top, limiting_month=mon,
                     limiting_hour=hr, limiting_n_hours=n, limiting_criteria=best["limiting_criteria"] if best else None,
                     n_line_sections=len(secs), n_sections_missing=len(secs) - len(known),
                     feeder_rating_mw=num(fr.get("facilityratingmw")), feeder_forecast_2026_mw=num(fr.get("facilityloadingmw2026")),
                     feeder_forecast_2028_mw=num(fr.get("facilityloadingmw2028")),
                     pending_load_mw=round(sum(x for x in pl if x is not None), 3) if any(x is not None for x in pl) else None,
                     n_pending_records=len(pl))
        s = subs.get(fid[:5])
        if s:
            s["feeders"].append(entry)
        else:
            unjoined.append(entry)

    for s in subs.values():
        b = s["banks"]
        pend = [x["pending_load_mw"] for x in s["feeders"] if x["pending_load_mw"] is not None]
        s["pending_load_mw"] = round(sum(pend), 3) if pend else None
        kb = [x for x in b if x["headroom_mw"] is not None]  # banks with a usable forecast
        s["rating_mw"] = round(sum(x["rating_mw"] for x in kb), 2) if kb else None  # same banks as the forecast sums
        s["rating_mw_all_banks"] = round(sum(x["rating_mw"] for x in b), 2) if b else None
        s["forecast_load_mw"] = {y: round(sum(x["forecast_load_mw"][y] for x in kb), 2) for y in ("2026", "2028")} if kb else None
        s["n_banks_without_forecast"] = len(b) - len(kb)  # GRIP gives -99.99 (redacted/missing); excluded from headroom
        # sum of per-bank floored headroom (a deficit bank cannot be offset by a spare one), minus known pending load
        s["headroom_mw"] = round(max(0, sum(x["headroom_mw"] for x in kb) - (s["pending_load_mw"] or 0)), 2) if kb else None

    sl = list(subs.values())
    allf = [x for s in sl for x in s["feeders"]]
    hosts = [x["max_load_hosting_mw"] for x in allf if x["max_load_hosting_mw"] is not None]
    banks = [b for s in sl for b in s["banks"]]
    over = [b for b in banks if (b["max_forecast_loading_pct_2026_2040"] or 0) > 100]
    summary = dict(
        substations=len(sl), banks=len(banks), feeders_joined=len(allf), feeders_unjoined=len(unjoined),
        feeders_total_in_bbox=len(sections),
        total_distribution_headroom_mw=round(sum(s["headroom_mw"] or 0 for s in sl), 2),
        banks_without_forecast=sum(b["headroom_mw"] is None for b in banks),
        total_bank_rating_mw_with_forecast=round(sum(b["rating_mw"] for b in banks if b["headroom_mw"] is not None), 2),
        total_bank_forecast_2028_mw=round(sum(b["forecast_load_mw"]["2028"] for b in banks if b["headroom_mw"] is not None), 2),
        feeders_with_hosting_value=len(hosts), median_feeder_hosting_mw=round(statistics.median(hosts), 3),
        max_feeder_hosting_mw=max(hosts), feeders_zero_hosting=sum(h == 0 for h in hosts),
        banks_over_100pct_peak=sum((b["peak_loading_pct"] or 0) > 100 for b in banks),
        banks_over_100pct_any_year_2026_2040=len(over),
        pending_load_records=sum(len(v) for v in pending.values()),
        pending_load_records_missing_amount=sum(x is None for v in pending.values() for x in v),
        high_fire_threat_districts=[{k: f["properties"][k] for k in ("hftd", "cpuc_tier")} for f in feats(18)])
    return dict(
        _note="PG&E GRIP values are directional, not guaranteed; not a PG&E approval. -99.99 -> null. See SOURCES.md.",
        summary=summary, substations=sl, unjoined_feeders=unjoined)


if __name__ == "__main__":
    out = build()
    s = out["summary"]
    assert s["feeders_joined"] + s["feeders_unjoined"] == s["feeders_total_in_bbox"]
    assert all(b["headroom_mw"] is None or b["headroom_mw"] >= 0 for x in out["substations"] for b in x["banks"])
    (HERE / "grip_capacity.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(s, indent=1))
