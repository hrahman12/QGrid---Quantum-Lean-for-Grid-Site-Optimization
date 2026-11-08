"""Region adapters: one interface for "what grid is near this site", per country.

get_adapter(site) -> adapter with substations(site), ratings(subs), distribution(site), iso_signal(site), snapshot(site).
  us_caiso    US sites: the existing grid/snapshot.py path (OSM + L2 ratings + PG&E GRIP + CAISO/gridstatus), unchanged.
  global_osm  any country: OSM Overpass substations (cached in data/shared/global/<site_id>/), ASSUMED voltage-class
              ratings, no distribution layer, static per-country signal from data/shared/global/grid_signals.json.
  eu_entsoe   documented stub only (see EU_ENTSOE_TODO); not wired, needs an ENTSO-E API token.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .. import snapshot as snap

GLOBAL = Path(__file__).resolve().parents[2] / "data" / "shared" / "global"
# ASSUMED firm transformer MVA per voltage class (IEC classes used outside North America). Not measured.
GLOBAL_MVA_BY_KV = {66: 60, 110: 120, 132: 150, 150: 200, 220: 300, 275: 400, 330: 500, 380: 750, 400: 750, 500: 900, 765: 1500}

EU_ENTSOE_TODO = ("eu_entsoe (not wired): ENTSO-E Transparency Platform would add hourly day-ahead prices per bidding zone "
                  "(doc A44), actual total load (A65) and cross-border flows; needs a free API token (ENTSOE_API_KEY) "
                  "and e.g. entsoe-py. Until then EU sites use global_osm with the static grid_signals.json figures.")


class UsCaiso:
    name = "us_caiso"

    def snapshot(self, site):
        return snap.get_snapshot(site)  # US path, byte-for-byte as before

    def substations(self, site):
        return self.snapshot(site)["substations"]

    def ratings(self, subs):
        return subs  # already rated by L2 / snapshot.MVA_BY_KV

    def distribution(self, site):
        return self.snapshot(site).get("distribution")

    def iso_signal(self, site):
        return snap.iso_signal(site["iso"])


class GlobalOsm:
    name = "global_osm"

    def _cache(self, site):
        return GLOBAL / site["id"] / "osm_substations.geojson"

    def substations(self, site):
        cache = self._cache(site)
        if os.environ.get("QSITE_OFFLINE") == "1" or cache.exists():  # cached pool wins: demo runs offline
            fc, src = json.loads(cache.read_text(encoding="utf-8")), f"cache:{cache.relative_to(GLOBAL.parents[2]).as_posix()}"
        else:
            # only >= 60 kV-tagged yards: dense EU metros otherwise hit Overpass's 400-element cap with 20 kV kiosks
            fc, src = snap._fetch_osm_substations(site, cache, '["voltage"~"[0-9]{6}|[6-9][0-9]{4}"]')
        return snap.pick_substations(fc, site), src

    def ratings(self, subs):
        for s in subs:
            mva = snap._near(GLOBAL_MVA_BY_KV, s["kv"])
            s.update(assumed_mva=mva, headroom_mw=round(mva * snap.PF * (1 - snap.UTIL), 1),
                     rating_source="ASSUMED: grid/adapters GLOBAL_MVA_BY_KV voltage-class table")
        return subs

    def distribution(self, site):
        return None  # no public feeder hosting-capacity map outside PG&E GRIP

    def iso_signal(self, site):
        table = json.loads((GLOBAL / "grid_signals.json").read_text(encoding="utf-8"))["countries"]
        c = table.get(site["country"])
        if not c:
            return {"lmp": None, "load": None, "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "source": f"unavailable:{site['country']} (no entry in data/shared/global/grid_signals.json)"}
        return {"lmp": c["lmp_usd_mwh"], "load": c["load_mw"], "timestamp": c["timestamp"],
                "source": f"static:grid_signals.json[{site['country']}] ({c['source']})",
                "carbon_g_per_kwh": c.get("carbon_g_per_kwh"), "status": c["status"]}

    def snapshot(self, site):
        subs, src = self.substations(site)
        if not subs:
            raise RuntimeError(f"no OSM substations >= {snap.MIN_KV} kV within {snap.RADIUS_KM} km of {site['id']}")
        subs = self.ratings(subs)
        iso = self.iso_signal(site)
        return {
            "site_id": site["id"], "substations": subs, "lines": snap.infer_lines(subs) if len(subs) > 1 else [],
            "iso": iso, "dlr_uplift_pct": snap.DLR_UPLIFT_PCT_DEFAULT, "adapter": self.name,
            "assumptions": [
                f"substations: {src}; (c) OpenStreetMap contributors (ODbL)",
                f"ASSUMED ratings: voltage-class table {GLOBAL_MVA_BY_KV}; headroom_mw = assumed_mva*{snap.PF}*(1-{snap.UTIL})",
                f"lines inferred (MST + 2nd-nearest), rating from kV table {snap.LINE_MVA_BY_KV}, length = straight line x {snap.ROUTE_FACTOR}",
                f"ASSUMED dlr_uplift_pct {snap.DLR_UPLIFT_PCT_DEFAULT} (no regional DLR study)",
                f"iso: {iso['source']}; static annual figure, not a live market signal",
                "distribution: none (no public hosting-capacity map for this country)",
                EU_ENTSOE_TODO,
            ],
        }


def get_adapter(site):
    return UsCaiso() if site.get("country", "US") == "US" else GlobalOsm()
