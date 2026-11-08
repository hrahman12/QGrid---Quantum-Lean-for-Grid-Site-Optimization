"""Distribution-level view from the cached PG&E GRIP file (data/shared/grip/grip_capacity.json).

Question: how much of the requested MW could connect at distribution as N edge sites (0.5-10 MW each)?
Method (directional, not a PG&E determination): each feeder with max_load_hosting_mw >= MIN_SITE_MW is one edge site,
sized min(hosting, MAX_SITE_MW, its bank's remaining headroom_mw), filled largest-first per bank. Headroom is never
pooled across banks of one substation (a spare bank cannot carry a feeder fed by a full one). Feeder -> bank comes
from the feeder's own bank_id, else data/l2/l3_inputs.json (GRIP layer 31), else the substation's only bank;
feeders with no known bank, and banks with no forecast (headroom_mw None), get nothing.
The rest of the request would need transmission-level service.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRIP = Path(os.environ.get("QSITE_GRIP_JSON") or ROOT / "data/shared/grip/grip_capacity.json")
L3 = ROOT / "data/l2/l3_inputs.json"
MIN_SITE_MW, MAX_SITE_MW = 0.5, 10.0


def load_grip():
    try:
        return json.loads(GRIP.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None  # fixture fallback: caller omits the distribution view


def load_bank_map():
    """feeder_id -> bank_id from data/l2/l3_inputs.json ({} if absent)."""
    try:
        return {f["feeder_id"]: f["bank_id"] for f in json.loads(L3.read_text(encoding="utf-8"))["feeders"] if f.get("bank_id")}
    except (OSError, ValueError, KeyError):
        return {}


def edge_sites(grip, requested_mw, bank_of=None):
    bank_of = bank_of or {}
    sites, per_sub = [], []
    for sub in grip["substations"]:
        banks = sub.get("banks", [])
        left = {b["id"]: b.get("headroom_mw") or 0.0 for b in banks}
        only = banks[0]["id"] if len(banks) == 1 else None
        got = 0.0
        feeders = sorted((f for f in sub.get("feeders", []) if (f.get("max_load_hosting_mw") or 0) >= MIN_SITE_MW),
                         key=lambda f: -f["max_load_hosting_mw"])
        for f in feeders:
            bid = f.get("bank_id") or bank_of.get(f["feeder_id"]) or only
            if bid not in left:
                continue  # unknown bank: cannot prove capacity
            mw = round(min(f["max_load_hosting_mw"], MAX_SITE_MW, left[bid]), 2)
            if mw < MIN_SITE_MW:
                continue
            sites.append({"substation_id": sub["id"], "substation": sub["name"], "bank_id": bid, "feeder_id": f["feeder_id"],
                          "feeder": f["name"], "mw": mw, "lat": sub["lat"], "lon": sub["lon"]})
            left[bid] -= mw
            got += mw
        per_sub.append({"id": sub["id"], "name": sub["name"], "lat": sub["lat"], "lon": sub["lon"],
                        "bank_headroom_mw": sub.get("headroom_mw") or 0.0, "connectable_mw": round(got, 2),
                        "feeders_with_hosting": len(feeders)})
    total = round(sum(s["mw"] for s in sites), 2)
    return {"requested_mw": requested_mw, "connectable_at_distribution_mw": min(total, requested_mw),
            "needs_transmission_mw": round(max(0.0, requested_mw - total), 2), "n_edge_sites": len(sites),
            "edge_sites": sites, "substations": per_sub, "note": grip.get("_note", "")}
