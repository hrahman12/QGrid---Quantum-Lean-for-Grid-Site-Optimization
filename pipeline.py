"""QSiteProof pipeline: site -> grid snapshot -> search -> physics -> certificate.

Each stage lives in its lane's folder. A stage whose module or function doesn't exist yet
falls back to fixtures/, so the pipeline runs end to end today. Real errors inside a lane's
module are NOT swallowed.

Usage: python pipeline.py [path/to/site.json]
"""
import importlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
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


def run(site_path=None, out_root=None):
    site = json.loads(Path(site_path).read_text(encoding="utf-8")) if site_path else fixture("site")
    sources = {"site": site_path or "FIXTURE"}
    out = {"site": site}

    out["grid_snapshot"], sources["grid_snapshot"] = stage("grid.snapshot", "get_snapshot", "grid_snapshot", site)
    constraints = []  # Lean blocking conditions fed back into the next search (one pass for now)
    out["candidate_plan"], sources["candidate_plan"] = stage(
        "quantum.search", "propose", "candidate_plan", site, out["grid_snapshot"], constraints)
    out["physics_result"], sources["physics_result"] = stage(
        "grid.physics", "check", "physics_result", out["candidate_plan"], out["grid_snapshot"])
    out["certificate"], sources["certificate"] = stage(
        "lean.certify", "certify", "certificate", out["candidate_plan"], out["physics_result"], site)

    schemas = load_schemas()
    problems = [e for n in STAGES for e in schema_errors(n, out[n], schemas)]
    if not problems:
        problems = coherence_errors(*(out[n] for n in STAGES))

    run_dir = Path(out_root or ROOT / "runs") / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True, exist_ok=True)
    for n in STAGES:
        (run_dir / f"{n}.json").write_text(json.dumps(out[n], indent=2), encoding="utf-8")
    (run_dir / "sources.json").write_text(json.dumps(sources, indent=2), encoding="utf-8")

    print_summary(out, sources, problems, run_dir)
    return out, sources, problems, run_dir


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
        print(f"  {s['substation_id']:8} {s['mw']:7.1f} MW  / headroom {sub.get('headroom_mw', '?')} MW  {sub.get('name', '')}")
    print(f"  flex: {plan['flex']}   search: {plan['search']['method']} ({plan['search']['evals']} evals)")
    print(f"  physics: converged={phys['converged']} max_loading={phys['max_line_loading_pct']}% "
          f"V=[{phys['v_min_pu']}, {phys['v_max_pu']}] N-1={'pass' if phys['n1_pass'] else 'FAIL'}")
    for c in cert["checks"]:
        print(f"  {'PASS' if c['pass'] else 'FAIL'}  {c['name']}: {c['detail']}")
    print("-" * 72)
    print(f"  RESULT: {cert['result']}" + (f"  blocked by: {cert['blocking_condition']}" if cert["blocking_condition"] else ""))
    print(f"  {cert['scope_note']}")
    if any(v == "FIXTURE" for v in sources.values()):
        print("  NOTE: stages marked FIXTURE used synthetic fixture data, not live results.")
    for p in problems:
        print(f"  CONTRACT PROBLEM: {p}")
    print(f"  wrote {run_dir}")


if __name__ == "__main__":
    _, _, problems, _ = run(sys.argv[1] if len(sys.argv) > 1 else None)
    sys.exit(1 if problems else 0)
