"""Build data/l2/queue_hints.json: CAISO interconnection-queue activity at substations near Alviso.

Input (cached, offline): data/l2/cache/caiso_queue_bay_counties_2026-11-08.csv, the CAISO public queue
(gridstatus CAISO().get_interconnection_queue(), PublicQueueReport.xlsx) filtered to Santa Clara,
Alameda and San Mateo counties. Refresh with: python data/l2/build_queue_hints.py --refresh

The CAISO queue lists generation and storage requests only. Large loads such as data centers are
handled by PG&E outside this queue, so this is a congestion/competition hint, not hosting capacity.
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache" / "caiso_queue_bay_counties_2026-11-08.csv"
SUBS = HERE / "substation_ratings.json"
OUT = HERE / "queue_hints.json"

SUFFIXES = re.compile(r"\s+(Substation|Receiving Station|Switching Station|Distribution Substation)\b.*$", re.I)


def refresh():
    import gridstatus
    q = gridstatus.CAISO().get_interconnection_queue()
    q = q[q["County"].str.contains("Santa Clara|Alameda|San Mateo", case=False, na=False)]
    q.to_csv(CACHE, index=False)


def key(name):
    return SUFFIXES.sub("", name).strip().lower()


def main():
    if "--refresh" in sys.argv:
        refresh()
    q = pd.read_csv(CACHE)
    subs = json.loads(SUBS.read_text(encoding="utf-8"))["substations"]
    by_key = {}
    for s in subs:
        k = key(s["name"])
        if len(k) >= 4 and not k.startswith("n-"):
            by_key.setdefault(k, []).append(s)

    loc = q["Interconnection Location"].fillna("").str.lower()
    hints = []
    for k, group in sorted(by_key.items(), key=lambda kv: kv[1][0]["distance_km"]):
        rows = q[loc.str.contains(rf"\b{re.escape(k)}\b", regex=True)]
        if rows.empty:
            continue
        items = []
        for _, r in rows.iterrows():
            items.append({
                "queue_id": str(r["Queue ID"]),
                "location": r["Interconnection Location"],
                "type": r["Generation Type"],
                "mw": None if pd.isna(r["Capacity (MW)"]) else float(r["Capacity (MW)"]),
                "status": r["Status"],
                "proposed_cod": None if pd.isna(r["Proposed Completion Date"]) else str(r["Proposed Completion Date"])[:10],
                "at": "line" if re.search(r"\bline\b|\btap\b|-", str(r["Interconnection Location"]), re.I) else "substation",
            })
        active = [i for i in items if i["status"] == "ACTIVE"]
        active_bus = [i for i in active if i["at"] == "substation"]
        hints.append({
            "substation_ids": [s["id"] for s in group],
            "substation": group[0]["name"],
            "distance_km": group[0]["distance_km"],
            "active_count": len(active),
            "active_mw": round(sum(i["mw"] or 0 for i in active), 1),
            "active_mw_at_substation": round(sum(i["mw"] or 0 for i in active_bus), 1),
            "active_storage_mw_at_substation": round(sum(i["mw"] or 0 for i in active_bus if "storage" in str(i["type"]).lower()), 1),
            "withdrawn_count": sum(i["status"] == "WITHDRAWN" for i in items),
            "completed_count": sum(i["status"] == "COMPLETED" for i in items),
            "projects": items,
        })

    doc = {
        "site_id": "nsj-alviso-150",
        "source": "CAISO public interconnection queue (PublicQueueReport.xlsx) via gridstatus 0.37.0 CAISO().get_interconnection_queue(), pulled 2026-11-08, cached in cache/caiso_queue_bay_counties_2026-11-08.csv",
        "match_method": "substation name (suffix stripped) as a whole word in 'Interconnection Location'; substations from substation_ratings.json",
        "caveats": [
            "The CAISO queue covers generation and storage only; data-center load requests are not in it.",
            "Active storage near a substation is a possible flexibility partner (battery) and a sign of interest in that node, not available capacity.",
            "Many withdrawals at a substation hint at costly upgrades there; this is a hint, not a study result.",
            "Hosting capacity: PG&E's ICA/hosting-capacity map needs a PG&E login, so it is not cached here (ASSUMED unknown).",
        ],
        "utility_territory": {
            "value": "PG&E (transmission and distribution)",
            "status": "ASSUMED",
            "basis": "The site is in the City of San Jose (Alviso). Silicon Valley Power serves the City of Santa Clara, not San Jose. Not confirmed against a PG&E territory map.",
        },
        "hints": hints,
    }
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.name}: {len(hints)} substations with queue activity")
    for h in hints:
        print(f"  {h['distance_km']:5.1f} km {h['substation']}: active {h['active_count']} ({h['active_mw']} MW, {h['active_mw_at_substation']} MW at the substation), withdrawn {h['withdrawn_count']}, completed {h['completed_count']}")


if __name__ == "__main__":
    main()
