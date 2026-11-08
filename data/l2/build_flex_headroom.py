"""Build data/l2/flex_headroom.json: distribution MW connectable if the site accepts curtailment in a few hours.

Organizers: "accepting curtailment on a few hot hours (~98% availability) connects much sooner".
This turns that into numbers per PG&E bank near Alviso, offline, from the shared GRIP pack.

Inputs (all cached):
  data/shared/grip/grip_capacity.json   bank rating_mw and forecast_load_mw["2028"] (PG&E GRIP)
  data/shared/grip/raw/layer_25.json    SubstationLoadProfile: per substation, month_hour "high"/"low"
                                        (units undocumented; peaks of 48-99 thousand vs bank ratings
                                        of 89-178 MW suggest kW; only the SHAPE is used, so units cancel)
  data/l2/ciso_2025_stress.json         2025 CAISO system stress cells, to check overlap

Method (directional, ASSUMED where stated):
  shape(m,h) = high(m,h) / max(high) for the bank's substation.
  Each (month, hour) cell is ASSUMED to repeat on every day of that month (conservative: the
  "high" day stands in for all days, which overstates curtailment hours).
  For a curtailment budget of B hours/year, curtail the highest cells until B is used; q_B is
  the highest shape value left. Effective bank peak = forecast_2028 x q_B.
  flex_headroom_mw(bank) = max(0, rating - forecast_2028 x q_B). With B = 0 this equals GRIP's
  firm bank headroom (pending load is withheld in GRIP, so it is an upper bound either way).
Not a PG&E flexible-service offer; a GREEN on these numbers is the encoded rules only.

Usage: python data/l2/build_flex_headroom.py
"""
import calendar
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GRIP = ROOT / "data" / "shared" / "grip"
HERE = Path(__file__).resolve().parent
OUT = HERE / "flex_headroom.json"
YEAR = 2028  # GRIP forecast year used by grip_capacity.json; also the site deadline year
HOURS = 8784 if calendar.isleap(YEAR) else 8760
BUDGETS_PCT = [0, 0.5, 1, 2, 3, 5, 10]


def profiles():
    rows = json.loads((GRIP / "raw" / "layer_25.json").read_text(encoding="utf-8"))["features"]
    by = defaultdict(dict)
    for f in rows:
        a = f.get("attributes") or f.get("properties") or f
        m, h = (int(x) for x in a["monthhour"].split("_"))
        if a.get("high") is not None and a["high"] > 0:
            by[a["subname"].upper()][(m, h)] = float(a["high"])
    return by


def ciso_cells():
    p = HERE / "ciso_2025_stress.json"
    if not p.exists():
        return set()
    w = json.loads(p.read_text(encoding="utf-8"))["curtailment_windows"]["net_load_top2pct"]
    return {(int(m), int(h)) for m, hs in w["hours_by_month"].items() for h in hs}


def curtail(prof, budget_h):
    """Return (q, cells, hours_used): curtail the highest cells while their hours fit in budget_h."""
    peak = max(prof.values())
    cells = sorted(prof.items(), key=lambda kv: kv[1], reverse=True)
    used, chosen = 0, []
    for (m, h), v in cells:
        n = calendar.monthrange(YEAR, m)[1]
        if used + n > budget_h:
            q = v / peak
            break
        used += n
        chosen.append((m, h))
    else:
        q = 0.0
    return q, chosen, used


def main():
    cap = json.loads((GRIP / "grip_capacity.json").read_text(encoding="utf-8"))
    prof = profiles()
    stress = ciso_cells()
    subs_out, totals = [], {str(b): 0.0 for b in BUDGETS_PCT}
    for s in cap["substations"]:
        p = prof.get(s["name"].upper())
        banks = [b for b in s["banks"] if b.get("rating_mw") and (b.get("forecast_load_mw") or {}).get(str(YEAR)) is not None]
        if not p or not banks:
            continue
        by_budget = {}
        for pct in BUDGETS_PCT:
            budget_h = pct / 100 * HOURS
            q, cells, used = curtail(p, budget_h) if pct else (1.0, [], 0)
            bank_rows = []
            for b in banks:
                f = b["forecast_load_mw"][str(YEAR)]
                bank_rows.append({"id": b["id"], "name": b["name"], "rating_mw": b["rating_mw"], "forecast_mw": f,
                                  "flex_headroom_mw": round(max(0.0, b["rating_mw"] - f * q), 2)})
            total = round(sum(r["flex_headroom_mw"] for r in bank_rows), 2)
            totals[str(pct)] += total
            by_budget[str(pct)] = {
                "curtail_hours_per_year": used,
                "availability_pct": round(100 * (1 - used / HOURS), 2),
                "effective_peak_factor": round(q, 4),
                "flex_headroom_mw": total,
                "curtail_cells": [{"month": m, "hour": h} for m, h in sorted(cells)],
                "cells_overlapping_ciso_2025_stress": sum((m, h) in stress for m, h in cells),
                "banks": bank_rows,
            }
        subs_out.append({"id": s["id"], "name": s["name"], "lat": s["lat"], "lon": s["lon"],
                         "firm_headroom_mw": by_budget["0"]["flex_headroom_mw"],
                         "grip_headroom_mw": s.get("headroom_mw"),
                         "by_curtailment_pct": by_budget})
    subs_out.sort(key=lambda x: -x["by_curtailment_pct"]["2"]["flex_headroom_mw"])
    doc = {
        "site_id": "nsj-alviso-150",
        "year": YEAR,
        "disclaimer": "Directional. GRIP data is not guaranteed and pending load is withheld (upper bound). Not a PG&E flexible-service offer or interconnection approval.",
        "method": __doc__.split("Method (directional, ASSUMED where stated):")[1].split("Usage:")[0].strip(),
        "sources": {
            "bank_ratings_forecasts": "data/shared/grip/grip_capacity.json (PG&E GRIP layer 31)",
            "load_shape": "data/shared/grip/raw/layer_25.json (PG&E GRIP SubstationLoadProfile, 'high' by month_hour)",
            "system_stress": "data/l2/ciso_2025_stress.json (EIA-930 CISO 2025, net-load top 2%)",
        },
        "assumptions": [
            "ASSUMED: each month's 'high' profile day repeats every day of that month (conservative).",
            "ASSUMED: the substation load shape applies to each of its banks.",
            "Banks without a 2028 GRIP forecast are excluded (6 of 24), as in grip_capacity.json.",
        ],
        "totals_mw_by_curtailment_pct": {k: round(v, 2) for k, v in totals.items()},
        "curve": [{"curtailment_pct": b, "availability_pct": round(100 - b, 2), "distribution_mw": round(totals[str(b)], 2)} for b in BUDGETS_PCT],
        "substations": subs_out,
    }
    OUT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print("total distribution MW by curtailment % of hours:", doc["totals_mw_by_curtailment_pct"])
    for s in subs_out:
        r = s["by_curtailment_pct"]
        print(f"  {s['name']:14} firm {s['firm_headroom_mw']:6.1f} (GRIP {s['grip_headroom_mw']}) | 1% {r['1']['flex_headroom_mw']:6.1f} | 2% {r['2']['flex_headroom_mw']:6.1f} "
              f"({r['2']['curtail_hours_per_year']} h, cells {[(c['month'], c['hour']) for c in r['2']['curtail_cells']]}, CISO overlap {r['2']['cells_overlapping_ciso_2025_stress']}) | 5% {r['5']['flex_headroom_mw']:6.1f}")


if __name__ == "__main__":
    main()
