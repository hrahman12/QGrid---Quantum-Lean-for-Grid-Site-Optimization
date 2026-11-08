"""Search stage (L3): propose(site, snapshot, constraints) -> candidate_plan.

Steps
  1. enumerate the discrete plan space (quantum/space.py; default N = 630 plans, n = 10 qubits, padded to 1024)
  2. mark it with the cheap oracle (quantum/oracle.py), honouring the Lean blocking conditions in `constraints`
  3. Grover search over the marked set, simulated:
        psiqdk importable in this process      -> quantum.grover_psiqdk.run_grover          method "psiqdk"
        else Windows + WSL ~/qsite-venv         -> same module via `wsl -d Ubuntu` subprocess method "psiqdk"
        else                                    -> numpy statevector of the same circuit     method "heuristic"
     ('psiqdk' is reported only when PsiQDK actually ran; the numpy fallback is recorded as such in
     quantum/out/last_search.json because the contract enum has no 'numpy' value.)
     Force a backend with env QSITE_GROVER_BACKEND=auto|psiqdk|wsl|numpy (default auto).
  4. among the measured shots that are marked, pick the best plan by the objective in quantum/oracle.py:
     fewest flex resources, then least flex MW, then the largest worst-case headroom margin.

evals (candidate_plan.search.evals) = oracle queries spent by the search
    = grover_iterations * shots   (each shot re-runs the circuit, which queries the oracle once per iteration)
    + shots                       (one classical predicate check per measured sample to confirm it is marked)
  Not included, and recorded separately as classical_enumeration_calls: the N predicate calls used to compile
  the lookup phase oracle. Because of that compilation step this Grover run has no query advantage; it is a
  simulation of the fault-tolerant algorithm, reported with PsiQDK's resource estimates.

If nothing in the K-nearest space is marked, K is widened one substation at a time; if still nothing is
marked, the plan with the smallest worst-case overload is returned with method "heuristic" and the
failure is written to last_search.json (the verification cycle will then report it RED).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .oracle import Oracle, objective
from .space import DEFAULT_K, build_space
from .statevector import optimal_iterations

QDIR = Path(__file__).resolve().parent
ROOT = QDIR.parent
OUT = QDIR / "out"
LAST = OUT / "last_search.json"
WSL_SCRIPT = QDIR / "_wsl_grover.sh"
WSL_TIMEOUT_S = int(os.environ.get("QSITE_WSL_TIMEOUT", "300"))
SHOTS, SEED = 32, 7

def engine_label(backend):
    """Astra #9: the engine that actually produced the pick (method enum stays psiqdk|heuristic|random)."""
    if backend == "psiqdk":
        return "psiqdk-simulated-grover"
    if backend and "numpy" in str(backend):
        return "numpy-fallback"
    return "classical"


HONESTY = ("Grover here is a classical simulation (PsiQDK workbench simulator, or numpy fallback) of a "
           "fault-tolerant quantum search circuit. No quantum hardware ran and no quantum advantage is claimed: "
           "the phase oracle is compiled from a marked list found by evaluating the classical predicate on all N "
           "plans. A marked plan is only a candidate; grid.physics.check (pandapower, N-1) and lean.certify decide.")


def _to_wsl(p: Path) -> str:
    p = Path(p).resolve()
    drive = p.drive.rstrip(":").lower()
    return f"/mnt/{drive}" + p.as_posix()[len(p.drive):]


def _run_wsl(job: dict) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    tag = uuid.uuid4().hex[:8]
    jp, rp = OUT / f"_job_{tag}.json", OUT / f"_result_{tag}.json"
    jp.write_text(json.dumps(job), encoding="utf-8")
    try:
        r = subprocess.run(["wsl", "-d", "Ubuntu", "--", "bash", _to_wsl(WSL_SCRIPT), _to_wsl(ROOT), _to_wsl(jp),
                            _to_wsl(rp)], capture_output=True, text=True, timeout=WSL_TIMEOUT_S)
        if r.returncode != 0 or not rp.exists():
            raise RuntimeError(f"WSL runner exit {r.returncode}: {(r.stderr or r.stdout).strip()[-400:]}")
        return json.loads(rp.read_text(encoding="utf-8"))
    finally:
        for p in (jp, rp):
            try:
                p.unlink()
            except OSError:
                pass


def run_backend(n_qubits: int, marked, shots: int = SHOTS, seed: int = SEED, backend: str | None = None):
    """-> (result dict from quantum.grover_psiqdk, list of fallback reasons)."""
    from . import grover_psiqdk as g
    backend = (backend or os.environ.get("QSITE_GROVER_BACKEND", "auto")).lower()
    job = {"n_qubits": n_qubits, "marked": list(marked), "shots": shots, "seed": seed, "top_k": 8}
    why = []
    if backend in ("auto", "psiqdk"):
        if g.psiqdk_available():
            return g.run_grover(n_qubits, marked, shots, seed), why
        why.append("psiqdk not importable in this Python")
        if backend == "psiqdk":
            raise RuntimeError(why[-1])
    if backend in ("auto", "wsl"):
        if os.name == "nt" and shutil.which("wsl") and WSL_SCRIPT.exists():
            try:
                res = _run_wsl(job)
                res["runner"] = "wsl -d Ubuntu (~/qsite-venv)"
                return res, why
            except (RuntimeError, subprocess.TimeoutExpired, OSError, ValueError) as e:
                why.append(f"WSL PsiQDK runner failed: {type(e).__name__}: {str(e)[:300]}")
                if backend == "wsl":
                    raise
        else:
            why.append("not Windows+WSL")
            if backend == "wsl":
                raise RuntimeError(why[-1])
    return g.run_numpy(n_qubits, marked, shots, seed), why


def _overload_fallback(space, oracle):
    best = min(space.plans(), key=lambda p: (-min(m for m, q in zip(oracle.margins(p), p.quarters) if q),
                                             objective(space, oracle, p)))
    return best


def grover_pick(space, oracle, exclude=(), shots=SHOTS, seed=SEED, backend=None):
    """Mark, run Grover, pick the best measured marked plan. -> (Plan | None, evals, info dict)."""
    marked = oracle.marked_indices(exclude)
    info = {"M": len(marked), "classical_enumeration_calls": space.size}
    if not marked:
        return None, 0, info
    res, why = run_backend(space.n_qubits, marked, shots, seed, backend)
    mset = set(marked)
    hits = sorted({s for s in res["samples"] if s in mset})
    k = res["iterations"]
    evals = k * shots + shots
    info.update(result=res, fallback_reasons=why, measured_marked_distinct=len(hits))
    if hits:
        plan = min((space.decode(i) for i in hits), key=lambda p: objective(space, oracle, p))
        info["picked_from"] = "measured shots"
    else:  # every shot missed (P ~ (1-p_marked)^shots): say so, take the objective-best marked plan
        plan = min((space.decode(i) for i in marked), key=lambda p: objective(space, oracle, p))
        info["picked_from"] = "no measured shot was marked; objective-best of the classical marked list"
    return plan, evals, info


def propose(site, snapshot, constraints=None, *, exclude=(), k=DEFAULT_K, shots=SHOTS, seed=SEED,
            backend=None, out_path=LAST):
    """site, grid_snapshot, list of past Lean blocking conditions -> candidate_plan (contract dict)."""
    t0 = time.time()
    constraints = list(constraints or [])
    n_with_headroom = sum(1 for s in snapshot["substations"] if (s.get("headroom_mw") or 0) > 0)
    widened = []
    while True:
        space = build_space(site, snapshot, k)
        oracle = Oracle(space, snapshot, constraints)
        plan, evals, info = grover_pick(space, oracle, exclude, shots, seed, backend)
        if plan is not None or k >= n_with_headroom:
            break
        widened.append(f"no marked plan with K={k}; widening to K={k + 1}")
        k += 1

    res = info.get("result") or {}
    if plan is None:
        plan = _overload_fallback(space, oracle)
        method, evals = "heuristic", space.size
        backend_used = "none (no marked plan): smallest worst-case overload"
    else:
        backend_used = res.get("backend")
        method = "psiqdk" if backend_used == "psiqdk" else "heuristic"
    cand = space.to_candidate_plan(plan, method, evals)
    # Astra #9: extra keys (candidate_plan.search allows them): the real engine and the full evaluation cost,
    # including the N classical predicate calls that compiled the lookup oracle
    cand["search"].update(engine=engine_label(backend_used), classical_enumeration_calls=space.size,
                          evals_total=evals + space.size)

    record = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "honesty": HONESTY,
        "site_id": site["id"],
        "space": space.describe(),
        "oracle": {"rule": "storage+curtail <= requested and split_i*(1-(storage+curtail)/requested) <= headroom_i (DLR: lines only)",
                   "notes": oracle.notes, "constraints": oracle.constraints.interpretations,
                   "excluded_plan_indices": sorted(set(exclude)), "M": info.get("M", 0),
                   "classical_enumeration_calls": space.size, "widened": widened},
        "backend": backend_used, "method": method,
        "fallback_reasons": info.get("fallback_reasons", []),
        "iterations": res.get("iterations"),
        "iterations_expected": optimal_iterations(space.padded_size, info.get("M", 0)),
        "evals": evals,
        "evals_definition": "grover_iterations*shots (in-circuit oracle queries) + shots (classical check of each "
                            "measured sample); excludes the N classical calls that compiled the lookup oracle",
        "picked_from": info.get("picked_from"),
        "objective": "min (flex resources used, flex MW, -worst-case headroom margin, index)",
        "chosen_plan_index": plan.index,
        "chosen_plan": cand,
        "grover": res,
        "wall_s": round(time.time() - t0, 3),
    }
    if out_path:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(record, indent=1), encoding="utf-8")
    return cand
