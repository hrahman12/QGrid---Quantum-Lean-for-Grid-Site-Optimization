"""QSiteProof pipeline: site -> grid snapshot -> search -> physics -> certificate.

Each stage lives in its lane's folder. A stage whose module or function doesn't exist yet
falls back to fixtures/, so the pipeline runs end to end today. Real errors inside a lane's
module are NOT swallowed.

Usage: python pipeline.py [path/to/site.json] [--rounds N]
"""
import argparse
import importlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
from report import labels  # noqa: E402
from validate import STAGES, coherence_errors, load_schemas, schema_errors  # noqa: E402

ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "fixtures"


def fixture(name):
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def stage(module, func, name, *args):
    """Call module.func(*args); fall back to fixtures/<name>.json only if the lane code is absent."""
    try:
        mod = importlib.import_module(module)
    except ModuleNotFoundError as e:
        parts = module.split(".")
        if e.name not in {".".join(parts[:i]) for i in range(1, len(parts) + 1)}:
            raise  # a dependency inside the lane module is missing: surface it
        return fixture(name), "FIXTURE"
    fn = getattr(mod, func, None)
    if fn is None:
        return fixture(name), "FIXTURE"
    return fn(*args), "live"


def pro_rata_plan(site, snapshot):
    """Stand-in for L3 until quantum.search exists: split the request by each substation's headroom."""
    subs = snapshot["substations"]
    total = sum(max(s.get("headroom_mw") or 0, 0) for s in subs) or len(subs)
    want = site["requested_mw"]
    splits = [{"substation_id": s["id"],
               "mw": round(want * (max(s.get("headroom_mw") or 0, 0) or (total / len(subs))) / total, 2)}
              for s in subs]
    splits[-1]["mw"] = round(want - sum(x["mw"] for x in splits[:-1]), 2)  # exact total after rounding
    return {"site_id": site["id"], "splits": splits,
            "flex": {"dlr": False, "storage_mw": 0, "curtailment_mw": 0, "reconductor": False},
            "search": {"method": "heuristic", "evals": 1}}


def blocking_constraint(cert, snapshot):
    """RED certificate -> structured constraint {rule, substation_id?, detail}. The search lane reads it as text."""
    rule, _, detail = str(cert.get("blocking_condition") or "").partition(": ")
    c = {"rule": rule, "detail": detail}
    sub = next((s["id"] for s in snapshot["substations"] if s["id"] in detail), None)
    if sub:
        c["substation_id"] = sub
    return c


def plan_summary(plan):
    flex = ",".join(k for k, v in plan["flex"].items() if v) or "no flex"
    return " ".join(f"{s['substation_id']}={s['mw']:g}" for s in plan["splits"]) + f" [{flex}]"


def run(site_path=None, out_root=None, rounds=5):
    site_path = site_path or ("data/l1/site.json" if (ROOT / "data/l1/site.json").exists() else None)
    site = json.loads((ROOT / site_path).read_text(encoding="utf-8")) if site_path else fixture("site")
    sources = {"site": site_path or "FIXTURE"}
    out = {"site": site}

    out["grid_snapshot"], sources["grid_snapshot"] = stage("grid.snapshot", "get_snapshot", "grid_snapshot", site)
    constraints, log = [], []  # blocking conditions from RED certificates, fed to the next proposal
    for rnd in range(1, max(rounds, 1) + 1):
        out["candidate_plan"], sources["candidate_plan"] = stage(
            "quantum.search", "propose", "candidate_plan", site, out["grid_snapshot"], list(constraints))
        if sources["candidate_plan"] == "FIXTURE" and sources["grid_snapshot"] != "FIXTURE":
            # fixture plan names synthetic SUB-A..D; re-split it over the live snapshot's substations
            out["candidate_plan"], sources["candidate_plan"] = pro_rata_plan(site, out["grid_snapshot"]), "FIXTURE"
        out["physics_result"], sources["physics_result"] = stage(
            "grid.physics", "check", "physics_result", out["candidate_plan"], out["grid_snapshot"])
        out["certificate"], sources["certificate"] = stage(
            "lean.certify", "certify", "certificate", out["candidate_plan"], out["physics_result"], site)
        cert, plan = out["certificate"], out["candidate_plan"]
        c = blocking_constraint(cert, out["grid_snapshot"]) if cert.get("blocking_condition") else None
        log.append({"round": rnd, "plan": plan_summary(plan), "verdict": cert["result"],
                    "blocking_rule": c and c["rule"], "blocking_condition": cert.get("blocking_condition"),
                    "evals": plan["search"]["evals"], "search": plan["search"]["method"],
                    "constraints_in": list(constraints)})
        if cert["result"] != "RED":
            break  # GREEN (or AMBER)
        if c in constraints:  # same block again: the search lane cannot act on it, more rounds are pointless
            log[-1]["stopped"] = "stalled: constraint already applied"
            break
        constraints.append(c)

    schemas = load_schemas()
    problems = [e for n in STAGES for e in schema_errors(n, out[n], schemas)]
    if not problems:
        problems = coherence_errors(*(out[n] for n in STAGES))

    run_dir = Path(out_root or ROOT / "runs") / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True, exist_ok=True)
    for n in STAGES:
        (run_dir / f"{n}.json").write_text(json.dumps(out[n], indent=2), encoding="utf-8")
    (run_dir / "sources.json").write_text(json.dumps(sources, indent=2), encoding="utf-8")
    (run_dir / "rounds.json").write_text(json.dumps(log, indent=2), encoding="utf-8")

    print_rounds(log)
    print_summary(out, sources, problems, run_dir)
    return out, sources, problems, run_dir


def print_rounds(log):
    print(f"{'round':>5}  {'verdict':7} {'blocking rule':16} {'evals':>5}  plan")
    for r in log:
        print(f"{r['round']:>5}  {r['verdict']:7} {r['blocking_rule'] or '-':16} {r['evals']:>5}  {r['plan']}"
              + (f"  ({r['stopped']})" if r.get("stopped") else ""))
    print()


def print_summary(out, sources, problems, run_dir):
    site, snap, plan, phys, cert = (out[n] for n in STAGES)
    print(f"QSiteProof  {site['name']}  ({site['requested_mw']} MW, {site['iso']}, by {site['deadline']})")
    print("-" * 72)
    for n in STAGES:
        print(f"  {n:16} {sources[n]}")
    print("-" * 72)
    heads = {s["id"]: s for s in snap["substations"]}
    for s in plan["splits"]:
        sub = heads.get(s["substation_id"], {})
        print(f"  {s['substation_id']:8} {s['mw']:7.1f} MW  / headroom {sub.get('headroom_mw', '?')} MW (screening est.)  {sub.get('name', '')}")
    print(f"  flex: {plan['flex']}   search: {labels.search_engine(plan)} ({plan['search']['evals']} evals)")
    print(f"  physics: converged={phys['converged']} max_loading={phys['max_line_loading_pct']}% "
          f"V=[{phys['v_min_pu']}, {phys['v_max_pu']}] N-1={'pass' if phys['n1_pass'] else 'FAIL'}")
    for c in cert["checks"]:
        print(f"  {'PASS' if c['pass'] else 'FAIL'}  {c['name']}: {c['detail']}")
    print("-" * 72)
    print(f"  certificate engine: {labels.cert_engine(cert)}")
    print(f"  rules covered: {labels.RULES_LABEL}")
    print(f"  headroom data: {labels.DATA_LABEL}")
    print(f"  RESULT: {labels.verdict_label(cert['result'])}" + (f"  blocked by: {cert['blocking_condition']}" if cert["blocking_condition"] else ""))
    print(f"  {cert['scope_note']}")
    if any(v == "FIXTURE" for v in sources.values()):
        print("  NOTE: stages marked FIXTURE used synthetic fixture data, not live results.")
    for p in problems:
        print(f"  CONTRACT PROBLEM: {p}")
    print(f"  wrote {run_dir}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("site", nargs="?")
    ap.add_argument("--rounds", type=int, default=5, help="max propose->physics->certify rounds")
    args = ap.parse_args()
    _, _, problems, _ = run(args.site, rounds=args.rounds)
    sys.exit(1 if problems else 0)
