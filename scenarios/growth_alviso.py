"""Moving-landscape scenario: distribution headroom near Alviso if forecast load grows.

Utility forecasts predate AI data centers. Recompute per-bank headroom
  max(0, rating - forecast_2028 * growth * q)
for q = effective peak factor at each curtailment budget (from data/l2/flex_headroom.json).
  baseline : growth 1.0  = published PG&E GRIP 2028 forecast (directional GRIP data)
  stress   : growth 1.2  = ASSUMED +20% forecast load (data-center growth), NOT a forecast.
Not a PG&E approval or study. Usage: python scenarios/growth_alviso.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FLEX = ROOT / "data" / "l2" / "flex_headroom.json"
OUT = ROOT / "runs" / "scenarios" / "growth_alviso.json"
SCENARIOS = {"baseline_grip_2028": 1.0, "stress_plus20pct_assumed": 1.2}
LABEL = ("Directional GRIP data (2028 forecast, pending load withheld). The +20% case is an ASSUMED stress "
         "scenario, not a utility forecast. Not a PG&E approval.")


def run(flex=None):
    flex = flex or json.loads(FLEX.read_text(encoding="utf-8"))
    pcts = list(flex["substations"][0]["by_curtailment_pct"])
    out = {"label": LABEL, "year": flex["year"], "scenarios": {}}
    for name, g in SCENARIOS.items():
        rows = {}
        for p in pcts:
            banks = []
            for s in flex["substations"]:
                lv = s["by_curtailment_pct"][p]
                for b in lv["banks"]:
                    banks.append({"id": b["id"], "name": b["name"], "substation": s["name"],
                                  "headroom_mw": round(max(0.0, b["rating_mw"] - b["forecast_mw"] * g * lv["effective_peak_factor"]), 2)})
            rows[p] = {"distribution_mw": round(sum(b["headroom_mw"] for b in banks), 2),
                       "banks_at_zero": sorted(b["name"] for b in banks if b["headroom_mw"] == 0),
                       "banks": banks}
        out["scenarios"][name] = {"load_growth_factor": g, "by_curtailment_pct": rows}
    base = out["scenarios"]["baseline_grip_2028"]["by_curtailment_pct"]
    for p in pcts:
        out["scenarios"]["stress_plus20pct_assumed"]["by_curtailment_pct"][p]["newly_zero_vs_baseline"] = sorted(
            set(out["scenarios"]["stress_plus20pct_assumed"]["by_curtailment_pct"][p]["banks_at_zero"]) - set(base[p]["banks_at_zero"]))
    out["curtailment_pcts"] = pcts
    return out


def table(out, pcts=("0", "2", "5", "10")):
    lines = [out["label"], f"{'scenario':26}" + "".join(f"{p + '% curt':>12}" for p in pcts)]
    for name, sc in out["scenarios"].items():
        lines.append(f"{name:26}" + "".join(f"{sc['by_curtailment_pct'][p]['distribution_mw']:>9.1f} MW" for p in pcts))
    for name, sc in out["scenarios"].items():
        for p in pcts:
            r = sc["by_curtailment_pct"][p]
            lines.append(f"  {name} @ {p}%: {len(r['banks_at_zero'])} banks at 0 MW"
                         + (f"; newly zero vs baseline: {', '.join(r['newly_zero_vs_baseline'])}" if r.get("newly_zero_vs_baseline") else ""))
    return "\n".join(lines)


def main():
    out = run()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(table(out))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
