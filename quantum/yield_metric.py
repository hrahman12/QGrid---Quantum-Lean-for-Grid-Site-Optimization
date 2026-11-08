"""Lean Green Yield: GREEN certificates per 10 verification cycles, for psiqdk-Grover vs random vs heuristic.

One verification cycle = grid.physics.check(plan, snapshot) (pandapower AC power flow + N-1) followed by
lean.certify.certify(plan, physics, site). Each method proposes one plan per cycle from the same space and
oracle; plans already verified are excluded, and every RED blocking condition is appended to the constraints
the next proposal must respect (the same feedback loop pipeline.py describes). Counts come from actual runs
only; nothing is estimated or extrapolated.

Usage: python -m quantum.yield_metric [site.json] [--cycles 10]
Writes quantum/out/yield_metric.json. Uses the offline snapshot caches (QSITE_OFFLINE=1) unless already set.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .baselines import heuristic_search, random_search
from .oracle import Oracle
from .search import grover_pick
from .space import build_space

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "out" / "yield_metric.json"


def run_method(method, site, snapshot, cycles=10, seed=0, certify=None, check=None):
    if check is None:
        from grid.physics import check
    if certify is None:
        from lean.certify import certify
    constraints, tried, log = [], set(), []
    greens = 0
    total_evals = 0
    backend = None
    for c in range(cycles):
        space = build_space(site, snapshot)
        oracle = Oracle(space, snapshot, constraints)
        if method == "psiqdk":
            plan, evals, info = grover_pick(space, oracle, exclude=tried, seed=seed + c)
            res = info.get("result") or {}
            backend = res.get("backend", backend)
            label = "psiqdk" if res.get("backend") == "psiqdk" else "heuristic"
        elif method == "random":
            plan, evals = random_search(space, oracle, seed=seed * 1000 + c, exclude=tried)
            label = "random"
        elif method == "heuristic":
            plan, evals = heuristic_search(space, oracle, exclude=tried)
            label = "heuristic"
        else:
            raise ValueError(method)
        total_evals += evals
        if plan is None:
            log.append({"cycle": c + 1, "plan": None, "note": "no marked, untried plan left; cycle not spent"})
            break
        cand = space.to_candidate_plan(plan, label, evals)
        phys = check(cand, snapshot)
        cert = certify(cand, phys, site, snapshot=snapshot)
        green = cert["result"] == "GREEN"
        greens += green
        tried.add(plan.index)
        if not green and cert["blocking_condition"]:
            constraints.append(cert["blocking_condition"])
        log.append({"cycle": c + 1, "plan_index": plan.index, "splits": cand["splits"], "flex": cand["flex"],
                    "evals": evals, "physics_clean": bool(phys["converged"] and phys["n1_pass"] and not phys["violations"]),
                    "result": cert["result"], "blocking_condition": cert["blocking_condition"],
                    "certify_engine": cert.get("engine")})
    spent = sum(1 for e in log if e.get("plan_index") is not None)
    return {"method": method, "seed": seed, "backend": backend, "cycles_spent": spent, "green": greens,
            "green_per_10_cycles": round(10 * greens / spent, 2) if spent else None,
            "oracle_evals_total": total_evals, "cycles": log}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("site", nargs="?", default=str(ROOT / "data" / "l1" / "site.json"))
    ap.add_argument("--cycles", type=int, default=10)
    ap.add_argument("--random-seeds", type=int, default=5)
    ap.add_argument("--grover-seeds", type=int, default=3)
    a = ap.parse_args(argv)
    os.environ.setdefault("QSITE_OFFLINE", "1")
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from grid.snapshot import get_snapshot
    site = json.loads(Path(a.site).read_text(encoding="utf-8"))
    snap = get_snapshot(site)
    t0 = time.time()
    runs = [run_method("psiqdk", site, snap, a.cycles, seed=7 + i) for i in range(a.grover_seeds)]
    runs += [run_method("random", site, snap, a.cycles, seed=i) for i in range(a.random_seeds)]
    runs += [run_method("heuristic", site, snap, a.cycles)]
    summary = {}
    for r in runs:
        s = summary.setdefault(r["method"], {"runs": 0, "green": 0, "cycles": 0, "oracle_evals": 0})
        s["runs"] += 1
        s["green"] += r["green"]
        s["cycles"] += r["cycles_spent"]
        s["oracle_evals"] += r["oracle_evals_total"]
    for s in summary.values():
        s["green_per_10_cycles_mean"] = round(10 * s["green"] / s["cycles"], 2) if s["cycles"] else None
    out = {"generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "definition": "GREEN certificates per 10 verification cycles (cycle = grid.physics.check + lean.certify)",
           "note": "Actual runs only. 'psiqdk' = PsiQDK simulation of Grover (numpy fallback if backend says so); "
                   "no quantum advantage claimed. GREEN covers only the encoded rules over the supplied evidence, "
                   "not a utility approval.",
           "site_id": site["id"], "snapshot_iso_source": snap["iso"]["source"],
           "summary": summary, "runs": runs, "wall_s": round(time.time() - t0, 1)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    for m, s in summary.items():
        print(f"{m:10} GREEN/10 cycles = {s['green_per_10_cycles_mean']}  ({s['green']} GREEN over {s['cycles']} "
              f"cycles, {s['runs']} run(s), oracle evals {s['oracle_evals']})")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
