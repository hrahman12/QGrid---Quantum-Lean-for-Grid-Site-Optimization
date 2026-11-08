"""Build ui/data.json (and the inline fallback copy in ui/index.html) from real repo files.

Every number the UI shows comes from one of the files read here; nothing is invented.
Derived values (e.g. transmission share = requested - distribution cap) are labelled as derived.

Usage:
    /root/qsiteproof/.venv/bin/python ui/build_data.py [--extra-root /root/qsiteproof]

--extra-root adds another checkout to search for untracked run outputs
(runs/<UTC>/*.json, quantum/out/last_search.json). The newest file wins.
Stdlib + pandas only.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

UI = Path(__file__).resolve().parent
ROOT = UI.parent
MARK_A = '<script id="qsp-data" type="application/json">'
MARK_B = "</script><!--/qsp-data-->"


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def rel(p: Path, roots) -> str:
    for r in roots:
        try:
            return str(p.resolve().relative_to(r.resolve()))
        except ValueError:
            pass
    return str(p)


def clean(o):
    """NaN/inf -> None so the output is strict JSON."""
    if isinstance(o, float):
        return o if o == o and abs(o) != float("inf") else None
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    return o


def newest(paths):
    paths = [p for p in paths if p.exists()]
    return max(paths, key=lambda p: p.stat().st_mtime) if paths else None


def first_root(roots, pattern, ok=lambda p: True):
    """Newest match for `pattern` in the first root that has one (this checkout wins over --extra-root)."""
    for r in roots:
        hit = newest([p for p in r.glob(pattern) if ok(p)])
        if hit:
            return hit
    return None


def import_file(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build(roots):
    src = []  # files actually read
    d2 = ROOT / "data" / "l2"

    flex_p = d2 / "flex_headroom.json"
    flex = load(flex_p); src.append(flex_p)
    l3_p = d2 / "l3_inputs.json"
    l3 = load(l3_p); src.append(l3_p)
    rat_p = d2 / "substation_ratings.json"
    rat = load(rat_p); src.append(rat_p)
    risk_p = d2 / "site_risk.json"
    risk = load(risk_p); src.append(risk_p)
    stress_p = d2 / "ciso_2025_stress.json"
    stress = load(stress_p); src.append(stress_p)
    grip_p = ROOT / "data" / "shared" / "grip" / "grip_capacity.json"
    grip = load(grip_p); src.append(grip_p)

    # ---- curtailment curve + per-substation flex headroom (flex_headroom.json)
    pcts = [str(c["curtailment_pct"]).rstrip("0").rstrip(".") if isinstance(c["curtailment_pct"], float)
            else str(c["curtailment_pct"]) for c in flex["curve"]]
    flex_out = {
        "disclaimer": flex["disclaimer"],
        "year": flex["year"],
        "assumptions": flex["assumptions"],
        "curve": flex["curve"],
        "totals_mw_by_curtailment_pct": flex["totals_mw_by_curtailment_pct"],
        "substations": [{
            "id": s["id"], "name": s["name"], "lat": s["lat"], "lon": s["lon"],
            "firm_headroom_mw": s["firm_headroom_mw"],
            "by_pct": {p: {"flex_headroom_mw": v["flex_headroom_mw"], "availability_pct": v["availability_pct"],
                           "curtail_hours_per_year": v["curtail_hours_per_year"],
                           "banks": [{"id": b["id"], "name": b["name"], "flex_headroom_mw": b["flex_headroom_mw"]}
                                     for b in v["banks"]]}
                       for p, v in s["by_curtailment_pct"].items()},
        } for s in flex["substations"]],
        "source": rel(flex_p, roots),
    }

    # ---- +20% growth scenario: computed by ORCH's scenarios/growth_alviso.run() on the same flex file
    growth_p = ROOT / "scenarios" / "growth_alviso.py"
    growth = None
    if growth_p.exists():
        g = import_file("growth_alviso", growth_p).run(flex); src.append(growth_p)
        growth = {"label": g["label"], "source": rel(growth_p, roots) + " run(flex_headroom.json)", "scenarios": {}}
        for name, sc in g["scenarios"].items():
            growth["scenarios"][name] = {
                "load_growth_factor": sc["load_growth_factor"],
                "by_pct": {p: {"distribution_mw": r["distribution_mw"], "banks_at_zero": len(r["banks_at_zero"]),
                               "banks_total": len(r["banks"]),
                               "by_substation": {n: round(sum(b["headroom_mw"] for b in r["banks"]
                                                              if b["substation"] == n), 2)
                                                 for n in dict.fromkeys(b["substation"] for b in r["banks"])}}
                           for p, r in sc["by_curtailment_pct"].items()},
            }

    # ---- banks + feeders (l3_inputs.json)
    l3_out = {
        "site": l3["site"],
        "disclaimer": l3["disclaimer"],
        "summary": l3["summary"],
        "rule_inputs": l3["rule_inputs"],
        "banks": [{k: b.get(k) for k in ("bank_id", "bank", "substation", "lat", "lon", "distance_km", "rating_mw",
                                          "forecast_2028_mw", "has_forecast", "cap_mw_by_curtailment_pct",
                                          "flood_sfha")} for b in l3["banks"]],
        "feeders": [{k: f.get(k) for k in ("feeder_id", "feeder", "substation", "bank_id", "lat", "lon",
                                            "distance_km", "hosting_mw", "edge_site_max_mw",
                                            "eligible_edge_site", "flood_sfha")} for f in l3["feeders"]],
        "transmission_candidates": l3["transmission_candidates"],
        "source": rel(l3_p, roots),
    }
    m = re.search(r"(\d+)\s*-\s*(\d+)\s*years", l3["rule_inputs"].get("R_transmission", ""))
    l3_out["transmission_years"] = [int(m.group(1)), int(m.group(2))] if m else None

    # ---- substations within 25 km (ASSUMED ratings)
    rat_out = {
        "disclaimer": rat["disclaimer"], "radius_km": rat["radius_km"],
        "power_factor": rat["power_factor"], "existing_load_pct": rat["existing_load_pct"],
        "voltage_classes": {k: {"mva_per_bank": v["mva_per_bank"], "banks": v["banks"], "status": v["status"],
                                "transformation": v["transformation"]} for k, v in rat["voltage_classes"].items()},
        "substations": [{k: s.get(k) for k in ("id", "name", "lat", "lon", "kv", "assumed_mva", "distance_km",
                                                "headroom_mw", "operator", "voltage_class")} for s in rat["substations"]],
        "source": rel(rat_p, roots),
    }

    # ---- risk
    risk_out = {"summary": risk["summary"], "lean_rule_hint": risk["lean_rule_hint"], "caveats": risk["caveats"],
                "points": [{"kind": p["kind"], "name": p["name"], "lat": p["lat"], "lon": p["lon"],
                            "flood_zone": (p.get("flood") or {}).get("zone"),
                            "sfha": (p.get("flood") or {}).get("sfha"),
                            "bfe_ft": (p.get("flood") or {}).get("bfe_ft")} for p in risk["points"]],
                "source": rel(risk_p, roots)}

    # ---- CAISO price/load (latest csv) + 2025 stress
    csv_p = newest(sorted(d2.glob("caiso_*.csv")))
    caiso = None
    if csv_p:
        df = pd.read_csv(csv_p); src.append(csv_p)
        caiso = {"source": rel(csv_p, roots),
                 "interval_start_utc": df["interval_start_utc"].astype(str).tolist(),
                 "load_mw": df["load_mw"].round(0).tolist(),
                 "lmp_np15_da": df["lmp_np15_da"].round(2).tolist(),
                 "load_max": float(df["load_mw"].max()), "load_min": float(df["load_mw"].min()),
                 "lmp_max": float(df["lmp_np15_da"].max()), "lmp_min": float(df["lmp_np15_da"].min()),
                 "lmp_mean": round(float(df["lmp_np15_da"].mean()), 2)}
    cw = stress["curtailment_windows"]
    stress_out = {"source": rel(stress_p, roots), "year": stress["year"], "note": stress["note"],
                  "demand_peak_mw": stress["demand_peak_mw"],
                  "mean_hours_per_day_by_month": stress["demand_p90_hours_per_day"]["mean_hours_per_day_by_month"],
                  "windows": {k: {kk: v[kk] for kk in ("metric", "top_share", "availability_if_curtailed_pct",
                                                        "hours_per_year", "days_with_stress", "months")}
                              for k, v in cw.items()}}

    # ---- quantum search record (newest quantum/out/last_search.json across roots)
    # the search record must belong to the same checkout as the pipeline run shown below
    cert_p = first_root(roots, "runs/*/certificate.json")
    qroots = ([cert_p.parent.parent.parent] if cert_p else []) + roots
    rich = lambda p: (load(p).get("oracle") or {}).get("M") and (load(p).get("grover") or {}).get("per_iteration") \
        and load(p).get("site_id") == l3["site"]["id"]
    qs_p = first_root(qroots, "quantum/out/last_search.json", rich) or first_root(qroots, "quantum/out/last_search.json")
    quantum = None
    if qs_p:
        q = load(qs_p); src.append(qs_p)
        gr = q.get("grover") or {}
        per = gr.get("per_iteration") or []
        quantum = {
            "source": rel(qs_p, roots), "generated_utc": q.get("generated_utc"), "honesty": q.get("honesty"),
            "site_id": q.get("site_id"), "backend": q.get("backend"), "method": q.get("method"),
            "fallback_reasons": q.get("fallback_reasons"),
            "space": {k: (q.get("space") or {}).get(k) for k in ("requested_mw", "k", "n_splits", "split_steps",
                                                                  "N", "n_qubits", "padded_N", "index_layout",
                                                                  "dlr", "storage_mw", "curtailment_pct")},
            "candidate_substations": [c["name"] for c in (q.get("space") or {}).get("candidate_substations", [])],
            "oracle": {"rule": (q.get("oracle") or {}).get("rule"), "M": (q.get("oracle") or {}).get("M"),
                       "constraints": [c.get("constraint") for c in (q.get("oracle") or {}).get("constraints", [])],
                       "classical_enumeration_calls": (q.get("oracle") or {}).get("classical_enumeration_calls"),
                       "widened": len((q.get("oracle") or {}).get("widened", []))},
            "iterations": q.get("iterations"), "iterations_expected": q.get("iterations_expected"),
            "iteration_rule": gr.get("iteration_rule"),
            "evals": q.get("evals"), "evals_definition": q.get("evals_definition"),
            "shots": gr.get("shots"), "samples_marked": gr.get("samples_marked"), "seed": gr.get("seed"),
            "p_marked": [round(it["p_marked"], 6) for it in per],
            "top_final": (per[-1].get("top") if per else None),
            "samples": gr.get("samples"),
            "numpy_crosscheck_ok": gr.get("numpy_crosscheck_ok"),
            "versions": gr.get("versions"), "simulation_note": gr.get("simulation_note"),
            "qpu_metrics": ((gr.get("resources") or {}).get("qpu_metrics")),
            "chosen_plan_index": q.get("chosen_plan_index"),
            "chosen_plan": q.get("chosen_plan"), "wall_s": q.get("wall_s"),
        }

    # ---- latest pipeline run (a runs/<UTC>/ dir with certificate.json)

    pipeline = None
    if cert_p:
        run = cert_p.parent
        files = {n: (run / f"{n}.json") for n in ("site", "candidate_plan", "physics_result", "certificate",
                                                  "sources", "grid_snapshot", "loop")}
        got = {n: load(p) for n, p in files.items() if p.exists()}
        src.extend(p for p in files.values() if p.exists())
        names = {s["id"]: s for s in (got.get("grid_snapshot") or {}).get("substations", [])}
        plan = got.get("candidate_plan") or {}
        pipeline = {
            "run": run.name, "dir": rel(run, roots),
            "site": got.get("site"), "sources": got.get("sources"),
            "plan": {"splits": [{**s, "name": names.get(s["substation_id"], {}).get("name"),
                                 "kv": names.get(s["substation_id"], {}).get("kv")} for s in plan.get("splits", [])],
                     "flex": plan.get("flex"), "search": plan.get("search")},
            "physics": got.get("physics_result"),
            "certificate": got.get("certificate"),
        }
        # plan space as defined in quantum/space.py on this run's snapshot; marked set from quantum/oracle.py
        if (ROOT / "quantum" / "space.py").exists() and got.get("site") and got.get("grid_snapshot"):
            try:
                sys.path.insert(0, str(ROOT))
                from quantum.oracle import Oracle
                from quantum.space import build_space
                space = build_space(got["site"], got["grid_snapshot"])
                pipeline["space"] = space.describe()
                pipeline["space"]["source"] = "quantum/space.py build_space(site, grid_snapshot).describe()"
                if quantum and quantum["site_id"] == got["site"]["id"] and not quantum["oracle"]["constraints"]:
                    marked = Oracle(space, got["grid_snapshot"], []).marked_indices()
                    if len(marked) == quantum["oracle"]["M"] and space.padded_size == quantum["space"]["padded_N"]:
                        quantum["marked_indices"] = sorted(marked)
                        quantum["marked_source"] = ("quantum/oracle.py Oracle(space, grid_snapshot, []).marked_indices()"
                                                    f" on {run.name}; count matches record M={len(marked)}")
                src.extend([ROOT / "quantum" / "space.py", ROOT / "quantum" / "oracle.py"])
            except Exception as e:  # pragma: no cover - optional context
                pipeline["space_error"] = repr(e)

    # ---- edge-site feedback loop (newest runs/*/edge_alviso.json)
    edge_p = first_root(roots, "runs/*/edge_alviso.json")
    edge = None
    if edge_p:
        e = load(edge_p); src.append(edge_p)
        edge = {**e, "source": rel(edge_p, roots), "run": edge_p.parent.name}

    grip_out = {"note": grip["_note"], "summary": grip["summary"], "source": rel(grip_p, roots)}

    return {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "honesty": [
            "Grover runs on a simulator; no quantum advantage is claimed.",
            "GREEN covers the encoded rules only; not a PG&E/utility approval.",
            "GRIP values are directional.",
            "Substation MVA ratings marked ASSUMED are planning placeholders, not real ratings.",
        ],
        "site": l3["site"], "flex": flex_out, "pcts": pcts, "growth": growth, "l3": l3_out,
        "ratings": rat_out, "risk": risk_out, "caiso": caiso, "stress": stress_out, "grip": grip_out,
        "quantum": quantum, "pipeline": pipeline, "edge": edge,
        "files_read": sorted({rel(p, roots) for p in src}),
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--extra-root", action="append", default=[], help="another checkout to search for runs/")
    a = ap.parse_args(argv)
    roots = [ROOT] + [Path(r) for r in a.extra_root if Path(r).exists()]
    data = clean(build(roots))
    txt = json.dumps(data, separators=(",", ":"), allow_nan=False)
    (UI / "data.json").write_text(txt + "\n", encoding="utf-8")
    html_p = UI / "index.html"
    if html_p.exists():
        html = html_p.read_text(encoding="utf-8")
        i, j = html.find(MARK_A), html.find(MARK_B)
        if i >= 0 and j > i:
            safe = txt.replace("</", "<\\/")
            html = html[: i + len(MARK_A)] + safe + html[j:]
            html_p.write_text(html, encoding="utf-8")
    print(f"wrote {UI / 'data.json'} ({len(txt)//1024} KB) from {len(data['files_read'])} files")
    for k in ("quantum", "pipeline", "edge"):
        print(f"  {k}: {(data[k] or {}).get('source') or (data[k] or {}).get('dir') or 'MISSING'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
