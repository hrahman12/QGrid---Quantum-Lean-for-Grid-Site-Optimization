"""Grover search over the plan space, built and simulated with PsiQDK (psiqdk.workbench + psiqdk.algorithms).

What this is: a classical statevector SIMULATION (PsiQDK workbench simulator) of a fault-tolerant quantum
search circuit, plus PsiQDK's resource estimates for that circuit. It is not a hardware run and it is not a
quantum advantage: the phase oracle is compiled from a marked list that was found by evaluating the cheap
classical predicate on every plan (quantum/oracle.py), so the classical side already did N evaluations.

Circuit (n = ceil(log2 N) qubits, register "plan"):
    reg.had()                                         uniform superposition over 2^n indices
    repeat k = floor(pi/4 * sqrt(2^n / M)) times:
        MarkedPhaseOracle.compute(reg)                (reg == m).reflect(180) for every marked m  -> -1 phase
        GroverDiffuser.compute(reg)                   psiqdk.algorithms: H^n, (reg == 0).reflect(180), H^n
    read(reg) per shot

PsiQDK API used: psiqdk.workbench.QPU (reset, pull_state, push_state, metrics, set_param('random_seed')),
psiqdk.workbench.Qubits (had, read, `== value` condition, .reflect(theta)), psiqdk.workbench.Qubrick (base class
of MarkedPhaseOracle / UniformPrep), psiqdk.algorithms.GroverDiffuser, psiqdk.algorithms.AmplitudeAmplifiedQubrick
(exact-amplitude variant, recorded alongside), psiqdk.workbench.qre.resource_estimator.

CLI (used by quantum/search.py through WSL):  python -m quantum.grover_psiqdk --in job.json --out result.json
    job.json = {"n_qubits": 10, "marked": [..], "shots": 32, "seed": 7, "top_k": 8}
"""
from __future__ import annotations

import argparse
import json
import sys
import time

import numpy as np

from quantum.statevector import grover_states, optimal_iterations, top_k


def psiqdk_available() -> bool:
    try:
        import psiqdk.workbench  # noqa: F401
        import psiqdk.algorithms  # noqa: F401
        return True
    except Exception:  # ImportError, or the native simulator wheel failing to load
        return False


def _qubricks():
    from psiqdk.workbench import Qubrick

    class MarkedPhaseOracle(Qubrick):
        """Phase oracle: flips the sign of every marked basis state (one multi-controlled Z per marked index).

        Generalised to an arbitrary reflection angle so AmpAmp's final fractional step can call it.
        Same pattern as psiqdk.algorithms.GoodReflectionGrover, extended from one good state to a set.
        """

        def __init__(self, marked, **kwargs):
            super().__init__(**kwargs)
            self.marked = [int(m) for m in marked]

        def _compute(self, sys_reg, angle: float = 180, ctrl=0, **kwargs):
            qc = self.get_qc()
            qc.label("oracle")
            for m in self.marked:
                (ctrl | (sys_reg == m)).reflect(theta=angle)
            qc.label()

    class UniformPrep(Qubrick):
        """A: |0^n> -> uniform superposition (the base Qubrick that amplitude amplification boosts)."""

        def _compute(self, sys_reg, ctrl=0, **kwargs):
            sys_reg.had()

    return MarkedPhaseOracle, UniformPrep


def _metrics(qc) -> dict:
    out = {}
    try:
        out["qpu_metrics"] = {k: (float(v) if isinstance(v, float) else int(v)) for k, v in qc.metrics().items()}
    except Exception as e:  # report, don't hide
        out["qpu_metrics_error"] = f"{type(e).__name__}: {e}"
    try:
        from psiqdk.workbench.qre import resource_estimator
        res = resource_estimator(qc).resources()
        out["resource_estimator"] = {str(k): (v if isinstance(v, (int, float)) else str(v)) for k, v in res.items()}
    except Exception as e:
        out["resource_estimator_error"] = f"{type(e).__name__}: {e}"
    return out


def run_grover(n_qubits: int, marked, shots: int = 32, seed: int = 7, k_top: int = 8, iterations=None,
               return_states: bool = False) -> dict:
    """Build + simulate the Grover circuit with PsiQDK. Returns a JSON-able dict (see module docstring).

    return_states=True adds 'states': the PsiQDK statevector after each iteration as [[re, im], ...] lists.
    """
    from psiqdk.algorithms import AmplitudeAmplifiedQubrick, GroverDiffuser
    from psiqdk.workbench import QPU, Qubits

    MarkedPhaseOracle, UniformPrep = _qubricks()
    marked = sorted({int(m) for m in marked})
    dim = 2 ** n_qubits
    M = len(marked)
    k = optimal_iterations(dim, M) if iterations is None else int(iterations)
    t0 = time.time()

    # --- textbook Grover, k iterations, statevector after each one --------------------------------------
    qc = QPU()
    qc.reset(n_qubits)
    qc.set_param("random_seed", int(seed))
    reg = Qubits(n_qubits, "plan", qc)
    oracle, diffuser = MarkedPhaseOracle(marked), GroverDiffuser()
    reg.had()
    states = [np.array(qc.pull_state(), dtype=np.complex128)]
    for _ in range(k):
        oracle.compute(reg)
        diffuser.compute(reg)
        states.append(np.array(qc.pull_state(), dtype=np.complex128))
    resources = _metrics(qc)          # circuit only (prep + k iterations), before any measurement
    final = states[-1]

    # --- shots: restore the final state and measure the register with the PsiQDK simulator ------------
    samples = []
    for _ in range(shots):
        qc.push_state(final)
        samples.append(int(reg.read()))

    # --- independent numpy cross-check (same convention incl. global phase) ----------------------------
    ref = grover_states(n_qubits, marked, k)
    diffs = [float(np.max(np.abs(a - b))) for a, b in zip(states, ref)]

    mset = set(marked)
    per_iter = []
    for i, st in enumerate(states):
        p = np.abs(st) ** 2
        per_iter.append({"iteration": i, "p_marked": float(p[marked].sum()) if marked else 0.0, **top_k(p, k_top)})

    # --- PsiQDK AmplitudeAmplifiedQubrick (exact AA with a fractional last step), recorded for comparison
    aa = {}
    if 0 < M < dim:
        try:
            qa = QPU()
            qa.reset(n_qubits)
            ra = Qubits(n_qubits, "plan", qa)
            AmplitudeAmplifiedQubrick(UniformPrep(), GroverDiffuser(), MarkedPhaseOracle(marked)).compute(
                ra, p_succ=M / dim)
            pa = np.abs(np.array(qa.pull_state())) ** 2
            aa = {"p_marked": float(pa[marked].sum()), "note": "vanilla exact AA (arXiv:quant-ph/0005055) via "
                  "AmplitudeAmplifiedQubrick(UniformPrep, GroverDiffuser, MarkedPhaseOracle); last step uses "
                  "fractional reflection angles", **_metrics(qa)}
        except Exception as e:
            aa = {"error": f"{type(e).__name__}: {e}"}

    import importlib.metadata as md
    versions = {}
    for pkg in ("psiqdk", "psiqdk-workbench", "psiqdk-algorithms", "workbench-sim-native"):
        try:
            versions[pkg] = md.version(pkg)
        except md.PackageNotFoundError:
            pass

    out = {
        "backend": "psiqdk",
        "simulation_note": "PsiQDK workbench statevector SIMULATION of a fault-tolerant Grover circuit; "
                           "not a hardware run; no quantum advantage claimed (oracle compiled from a classically "
                           "enumerated marked list).",
        "versions": versions,
        "n_qubits": n_qubits, "padded_N": dim, "M": M, "iterations": k,
        "iteration_rule": "floor(pi/4*sqrt(padded_N/M))",
        "per_iteration": per_iter,
        "shots": shots, "seed": seed, "samples": samples,
        "samples_marked": sum(1 for s in samples if s in mset),
        "numpy_crosscheck_max_abs_diff_per_iteration": diffs,
        "numpy_crosscheck_ok": bool(max(diffs) <= 1e-6),
        "resources": resources,
        "resources_note": "qc.metrics() of the simulated circuit (state prep + k Grover iterations, no reads). "
                          "The oracle is a lookup: one (n-1)-controlled Z per marked index, so its cost grows with M; "
                          "an arithmetic comparator oracle would be the cheaper fault-tolerant design.",
        "amplitude_amplified_qubrick": aa,
        "api_used": ["psiqdk.workbench.QPU", "psiqdk.workbench.Qubits", "psiqdk.workbench.Qubrick",
                     "Qubits.had", "(Qubits == m).reflect(theta)", "Qubits.read", "QPU.pull_state",
                     "QPU.push_state", "QPU.metrics", "psiqdk.algorithms.GroverDiffuser",
                     "psiqdk.algorithms.AmplitudeAmplifiedQubrick", "psiqdk.workbench.qre.resource_estimator"],
        "wall_s": round(time.time() - t0, 3),
    }
    if return_states:
        out["states"] = [[[float(a.real), float(a.imag)] for a in st] for st in states]
    return out


def run_numpy(n_qubits: int, marked, shots: int = 32, seed: int = 7, k_top: int = 8, iterations=None) -> dict:
    """Fallback when PsiQDK is unavailable: same circuit, numpy statevector, numpy shot sampling."""
    from quantum.statevector import sample
    marked = sorted({int(m) for m in marked})
    dim = 2 ** n_qubits
    k = optimal_iterations(dim, len(marked)) if iterations is None else int(iterations)
    states = grover_states(n_qubits, marked, k)
    per_iter = []
    for i, st in enumerate(states):
        p = np.abs(st) ** 2
        per_iter.append({"iteration": i, "p_marked": float(p[marked].sum()) if marked else 0.0, **top_k(p, k_top)})
    samples = sample(np.abs(states[-1]) ** 2, shots, seed)
    mset = set(marked)
    return {
        "backend": "numpy-statevector-fallback",
        "simulation_note": "numpy statevector simulation fallback (PsiQDK not available); not PsiQDK, not hardware.",
        "n_qubits": n_qubits, "padded_N": dim, "M": len(marked), "iterations": k,
        "iteration_rule": "floor(pi/4*sqrt(padded_N/M))", "per_iteration": per_iter,
        "shots": shots, "seed": seed, "samples": samples,
        "samples_marked": sum(1 for s in samples if s in mset), "resources": None,
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    job = json.loads(open(a.inp, encoding="utf-8").read())
    res = run_grover(job["n_qubits"], job["marked"], job.get("shots", 32), job.get("seed", 7),
                     job.get("top_k", 8), job.get("iterations"))
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(res, f)
    print(f"psiqdk grover: N={res['padded_N']} M={res['M']} k={res['iterations']} "
          f"p_marked={res['per_iteration'][-1]['p_marked']:.4f} crosscheck_ok={res['numpy_crosscheck_ok']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
