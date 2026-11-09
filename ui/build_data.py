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
    # only complete runs: pipeline.py writes certificate.json before sources.json and rounds.json
    complete = lambda p: all((p.parent / f).exists() for f in ("site.json", "grid_snapshot.json", "candidate_plan.json",
                                                               "physics_result.json", "sources.json", "rounds.json"))
    cert_p = first_root(roots, "runs/*/certificate.json", complete)
    qroots = ([cert_p.parent.parent.parent] if cert_p else []) + roots
    rich = lambda p: (load(p).get("oracle") or {}).get("M") and (load(p).get("grover") or {}).get("per_iteration") \
        and load(p).get("site_id") == l3["site"]["id"]
    qs_p = first_root(qroots[:1] or roots, "quantum/out/last_search.json")  # same checkout only, never a stale one
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
                                                  "sources", "grid_snapshot", "loop", "rounds")}
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
            "rounds": got.get("rounds"),
            "distribution": (got.get("grid_snapshot") or {}).get("distribution"),
        }
        lab_p = ROOT / "report" / "labels.py"
        if lab_p.exists():
            lab = import_file("qsp_labels", lab_p); src.append(lab_p)
            pipeline["labels"] = {"cert_engine": lab.cert_engine(got.get("certificate") or {}),
                                  "search_engine": lab.search_engine(plan),
                                  "round_search_engine": {str(r["round"]): lab.search_engine({"search": {"method": r.get("search")}})
                                                          for r in (got.get("rounds") or [])},
                                  "data": lab.DATA_LABEL, "rules": lab.RULES_LABEL}
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


# ---------------------------------------------------------------- climate / social / simulation layers
# Each layer is optional: null when its files are absent. Field names are read leniently (first key that
# exists) because the producing PRs were still open when this was written; nothing is filled in or guessed.
STUBS = UI / "dev_stubs"


def pick(d, *keys, default=None):
    for k in keys:
        if isinstance(d, dict) and d.get(k) is not None:
            return d[k]
    return default


def as_list(d, *keys):
    if isinstance(d, list):
        return d
    v = pick(d, *keys)
    return v if isinstance(v, list) else []


def find_layer(rel_paths, stubs, roots):
    """-> (root, is_stub) for the first root holding any of rel_paths; stubs only with --stubs."""
    for r in roots[:1]:
        if any((r / p).exists() for p in rel_paths):
            return r, False
    if stubs and any((STUBS / p).exists() for p in rel_paths):
        return STUBS, True
    return None, False


def tagged(v):
    """A value cell: {value, unit, tag, source, note} from a dict or a bare number."""
    if isinstance(v, dict):
        return {"value": pick(v, "value", "val", "mean", "median"), "unit": pick(v, "unit", "units"),
                "tag": pick(v, "tag", "provenance", "source_type", "kind"), "source": pick(v, "source", "citation", "url"),
                "note": pick(v, "note", "basis", "detail")}
    return {"value": v, "unit": None, "tag": None, "source": None, "note": None}


def build_nature(roots, src):
    """data/shared/nature/<site>.json (AlphaGeo + open-access layer): nature_rag, headline, top3,
    indicators[{name, modality, value, unit, rag, rule, source, method, date, note, line}]. RAG and line used as given."""
    files = sorted((ROOT / "data/shared/nature").glob("*.json"))
    files = [f for f in files if f.stem != "measurements"]
    sites = []
    for f in files:
        d = load(f)
        if not isinstance(d, dict) or "indicators" not in d:
            continue
        src.append(f)
        sites.append({"site": f.stem, "name": (d.get("site") or {}).get("name") or f.stem,
                      "rag": d.get("nature_rag"), "headline": d.get("headline"), "rule": d.get("rule"),
                      "top3": d.get("top3") or [], "generated": d.get("generated"), "source": rel(f, [ROOT]),
                      "indicators": [{k: x.get(k) for k in ("name", "modality", "value", "unit", "rag", "rule", "source",
                                                            "method", "date", "note", "line")} for x in d["indicators"]]})
    if not sites:
        return None
    sites.sort(key=lambda x: x["site"] != "alviso")  # the demo site first
    return {"sites": sites}


def build_socioecon(src):
    """data/shared/socioeconomic/<site>.json: overall_rag, headline, counts, indicators[{name, value, unit,
    plain_english, rag, rag_rule, source, method, date, scored}]. RAG and sentence used as given."""
    sites = []
    for f in sorted((ROOT / "data/shared/socioeconomic").glob("*.json")):
        d = load(f)
        if not isinstance(d, dict) or "indicators" not in d:
            continue
        src.append(f)
        sites.append({"site": f.stem, "name": d.get("site") or f.stem, "rag": d.get("overall_rag"),
                      "headline": d.get("headline"), "rule": d.get("overall_rule"), "counts": d.get("counts"),
                      "generated": d.get("generated"), "tract": d.get("tract_geoid"), "acs": d.get("acs_vintage"),
                      "source": rel(f, [ROOT]),
                      "indicators": [{"name": x.get("name"), "value": x.get("value"), "unit": x.get("unit"),
                                      "line": x.get("plain_english"), "rag": x.get("rag"), "rule": x.get("rag_rule"),
                                      "source": x.get("source"), "method": x.get("method"), "date": x.get("date"),
                                      "scored": x.get("scored")} for x in d["indicators"]]})
    if not sites:
        return None
    sites.sort(key=lambda x: x["site"] != "alviso")
    return {"sites": sites}

def month_of(ts):
    ts = str(ts or "")
    if re.match(r"^\d{9,}(\.\d+)?$", ts):
        return datetime.fromtimestamp(float(ts), timezone.utc).strftime("%Y-%m")
    return ts[:7] if re.match(r"^\d{4}-\d{2}", ts) else None


def build_social(stubs, roots, src):
    base = "data/shared/social/"
    root, is_stub = find_layer([base + n for n in ("social_posts.json", "opposition_events.json", "stakeholders.json",
                                                   "engagement_levers.json")], stubs, roots)
    out = {"stub": is_stub, "posts": None, "events": None, "network": None, "levers": None}
    if root:
        p = root / base / "social_posts.json"
        if p.exists():
            d = load(p); src.append(p)
            posts = as_list(d, "posts", "items", "records")
            by = {}
            stances = []
            for x in posts:
                m = month_of(pick(x, "created_utc", "created", "date", "timestamp", "time"))
                st = str(pick(x, "stance", "label", default="unknown")).lower()
                if st not in stances:
                    stances.append(st)
                if m:
                    by.setdefault(m, {}).setdefault(st, 0)
                    by[m][st] += 1
            recent = sorted(posts, key=lambda x: str(pick(x, "created_utc", "created", "date", default="")), reverse=True)[:6]
            out["posts"] = {"source": rel(p, [root]), "n": len(posts), "stances": stances,
                            "months": [{"month": k, "counts": by[k]} for k in sorted(by)],
                            "platforms": sorted({str(pick(x, "platform", "source", "site", default="?")) for x in posts}),
                            "by_platform": {k: sum(1 for x in posts if pick(x, "platform") == k) for k in {pick(x, "platform") for x in posts}},
                            "by_scope": {k: sum(1 for x in posts if pick(x, "scope") == k) for k in {pick(x, "scope") for x in posts}},
                            "recent": [{"author": pick(x, "id_hash", "author_hash", "user_hash"),
                                        "platform": pick(x, "platform", "source"),
                                        "date": str(pick(x, "created_utc", "created", "date", default=""))[:10],
                                        "stance": pick(x, "stance"), "topics": pick(x, "topics", default=[]),
                                        "title": pick(x, "title", "text", "body", default="")[:160],
                                        "url": pick(x, "url", "permalink", "link")} for x in recent],
                            "note": pick(d, "note", "method", "honesty") if isinstance(d, dict) else None}
        p = root / base / "opposition_events.json"
        if p.exists():
            d = load(p); src.append(p)
            ev = sorted(as_list(d, "events", "items"), key=lambda x: str(pick(x, "date", "start", default="")), reverse=True)
            out["events"] = {"source": rel(p, [root]), "n": len(ev),
                             "note": pick(d, "note") if isinstance(d, dict) else None,
                             "items": [{"date": pick(x, "date", "start"),
                                        "title": pick(x, "title", "name", "summary") or " · ".join(
                                            str(v) for v in (pick(x, "event"), pick(x, "actor"), pick(x, "size")) if v),
                                        "evidence": pick(x, "evidence"),
                                        "url": pick(x, "url", "source_url", "link"),
                                        "outlet": pick(x, "source", "outlet", "publisher"),
                                        "site": pick(x, "site", "site_id"), "type": pick(x, "type", "kind")} for x in ev[:12]]}
        p = root / base / "stakeholders.json"
        if p.exists():
            d = load(p); src.append(p)
            nodes = [{"id": pick(n, "id", "name"), "label": pick(n, "label", "name", "id"), "type": pick(n, "type", "kind", "group"),
                      "stance": pick(n, "stance"), "influence": pick(n, "influence", "weight", "power")}
                     for n in as_list(d, "nodes", "stakeholders")]
            edges = [{"source": pick(e, "source", "from"), "target": pick(e, "target", "to"),
                      "relation": pick(e, "relation", "kind", "type", "label"), "weight": pick(e, "weight")}
                     for e in as_list(d, "edges", "links")]
            out["network"] = {"source": rel(p, [root]), "nodes": nodes, "edges": edges,
                              "note": pick(d, "note", "method") if isinstance(d, dict) else None}
        p = root / base / "engagement_levers.json"
        if p.exists():
            d = load(p); src.append(p)
            out["levers"] = {"source": rel(p, [root]),
                             "items": [{"id": pick(x, "id", "lever"), "name": pick(x, "name", "title", "label", "lever"),
                                        "description": pick(x, "description", "summary", "detail")}
                                       for x in as_list(d, "levers", "items")]}
    socio = []
    for f in sorted((ROOT / "data/shared/socio").glob("*.json")):
        d = load(f); src.append(f)
        socio.append({"site": d.get("site"), "name": d.get("name"), "score": d.get("consent_score"),
                      "verdict": d.get("verdict"), "note": d.get("verdict_note"),
                      "conditions": d.get("amber_conditions") or [], "source": rel(f, [ROOT])})
    out["consent"] = socio or None
    if not any(out[k] for k in ("posts", "events", "network", "levers", "consent")):
        return None
    return out


def build_sim(stubs, roots, src, sim_root=None):
    """sim/mirofish/results/: summary.json + one <scenario>.json per scenario (MiroFish or labelled fallback)."""
    rp = "sim/mirofish/results/summary.json"
    root, is_stub = None, False
    for r in roots[:1] + ([Path(sim_root)] if sim_root else []):
        if (r / rp).exists():
            root = r
            break
    if not root and stubs and (STUBS / rp).exists():
        root, is_stub = STUBS, True
    if not root:
        return None
    sp = root / rp
    summ = load(sp); src.append(sp)
    scen = []
    for x in summ.get("scenarios", []):
        sid = x.get("scenario")
        fp = root / "sim/mirofish/results" / f"{sid}.json"
        det = load(fp) if fp.exists() else {}
        if det:
            src.append(fp)
        ini, fin = det.get("key_actors_initial_stance") or {}, det.get("key_actors_final_stance") or {}
        flips = [{"actor": a, "from": ini[a], "to": fin[a]} for a in fin
                 if a in ini and ini[a] is not None and fin[a] is not None and (ini[a] > 0) != (fin[a] > 0)
                 and ini[a] != 0 and fin[a] != 0]
        scen.append({"id": sid, "name": x.get("label"), "approval": x.get("approval_proxy"), "band": x.get("band"),
                     "support": x.get("support"), "neutral": x.get("neutral"), "oppose": x.get("oppose"),
                     "mean_stance": x.get("mean_stance"), "levers": det.get("levers") or [],
                     "agents": det.get("agents"), "steps": det.get("steps"),
                     "timeline": [{"step": t.get("step"), "mean": t.get("mean")} for t in det.get("stance_timeline") or []],
                     "flips": flips, "top_argument": x.get("top_argument"),
                     "source": rel(fp, [root]) if det else None})
    readme = root / "sim/mirofish/README.md"
    blocked = None
    if readme.exists():
        txt = readme.read_text(encoding="utf-8"); src.append(readme)
        if "ZEP_API_KEY" in txt and "could not run" in txt:
            blocked = "MiroFish itself could not run: it requires a Zep Cloud key (ZEP_API_KEY), which the team did not have (sim/mirofish/README.md)."
    return {"stub": is_stub, "source": rel(sp, [root]), "engine": summ.get("engine"), "blocked_note": blocked,
            "baseline_consent": summ.get("repo_baseline_consent"), "compare_against": summ.get("compare_against"),
            "scenarios": scen}

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--extra-root", action="append", default=[], help="another checkout to search for runs/")
    ap.add_argument("--sim-root", help="checkout holding sim/mirofish/results/ if not yet in this one")
    ap.add_argument("--stubs", action="store_true",
                    help="DEV ONLY: fill absent climate/social/sim layers from ui/dev_stubs (fake STUB values)")
    a = ap.parse_args(argv)
    roots = [ROOT] + [Path(r) for r in a.extra_root if Path(r).exists()]
    data = build(roots)
    extra = []
    data["nature"] = build_nature(roots, extra)
    data["socioecon"] = build_socioecon(extra)
    data["social"] = build_social(a.stubs, roots, extra)
    data["sim"] = build_sim(a.stubs, roots, extra, a.sim_root)
    data["stubs_used"] = [k for k in ("social", "sim") if (data[k] or {}).get("stub")]
    data["files_read"] = sorted(set(data["files_read"]) | {rel(p, roots + [STUBS]) for p in extra if not str(p).startswith(str(STUBS))})
    data = clean(data)
    txt = json.dumps(data, separators=(",", ":"), allow_nan=False)
    (UI / "data.json").write_text(txt + "\n", encoding="utf-8")
    # decision lanes: ORCH's ui/build_decision.py build() owns the RAG rules; it reads the data.json written above
    bd = UI / "build_decision.py"
    data["decision"] = None
    if bd.exists():
        try:
            data["decision"] = clean(import_file("qsp_build_decision", bd).build())
        except Exception as e:  # keep the page buildable if ORCH's builder and this data disagree
            print(f"  WARNING: build_decision.build() failed: {e!r}; decision band hidden")
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
    if data["stubs_used"]:
        print(f"  WARNING: STUB data used for {data['stubs_used']} (--stubs); do not commit this build")
    print(f"  decision: {(data.get('decision') or {}).get('overall', 'MISSING')} - {(data.get('decision') or {}).get('reason', '')}")
    for k in ("nature", "socioecon", "social", "sim"):
        print(f"  {k}: {'present' if data[k] else 'absent'}{' (STUB)' if (data[k] or {}).get('stub') else ''}")
    for k in ("quantum", "pipeline", "edge"):
        print(f"  {k}: {(data[k] or {}).get('source') or (data[k] or {}).get('dir') or 'MISSING'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
