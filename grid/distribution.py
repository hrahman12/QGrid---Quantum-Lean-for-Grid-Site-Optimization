"""Distribution-level view from the cached PG&E GRIP file (data/shared/grip/grip_capacity.json).

Question: how much of the requested MW could connect at distribution as N edge sites (0.5-10 MW each)?
Method (directional, not a PG&E determination): per substation, edge sites = feeders with max_load_hosting_mw >= MIN_SITE_MW,
each sized min(hosting, MAX_SITE_MW), filled largest-first until the substation's bank headroom_mw is used up.
The rest of the request would need transmission-level service.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

GRIP = Path(os.environ.get("QSITE_GRIP_JSON") or Path(__file__).resolve().parents[1] / "data/shared/grip/grip_capacity.json")
MIN_SITE_MW, MAX_SITE_MW = 0.5, 10.0


def load_grip():
    try:
        return json.loads(GRIP.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None  # fixture fallback: caller omits the distribution view


def edge_sites(grip, requested_mw):
    sites, per_sub = [], []
    for sub in grip["substations"]:
        left = sub.get("headroom_mw") or 0.0
        got = 0.0
        feeders = sorted((f for f in sub.get("feeders", []) if (f.get("max_load_hosting_mw") or 0) >= MIN_SITE_MW),
                         key=lambda f: -f["max_load_hosting_mw"])
        for f in feeders:
            mw = round(min(f["max_load_hosting_mw"], MAX_SITE_MW, left), 2)
            if mw < MIN_SITE_MW:
                continue
            sites.append({"substation_id": sub["id"], "substation": sub["name"], "feeder_id": f["feeder_id"],
                          "feeder": f["name"], "mw": mw, "lat": sub["lat"], "lon": sub["lon"]})
            left -= mw
            got += mw
        per_sub.append({"id": sub["id"], "name": sub["name"], "lat": sub["lat"], "lon": sub["lon"],
                        "bank_headroom_mw": sub.get("headroom_mw") or 0.0, "connectable_mw": round(got, 2),
                        "feeders_with_hosting": len(feeders)})
    total = round(sum(s["mw"] for s in sites), 2)
    return {"requested_mw": requested_mw, "connectable_at_distribution_mw": min(total, requested_mw),
            "needs_transmission_mw": round(max(0.0, requested_mw - total), 2), "n_edge_sites": len(sites),
            "edge_sites": sites, "substations": per_sub, "note": grip.get("_note", "")}
