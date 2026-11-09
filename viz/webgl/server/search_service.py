"""Bounded browser jobs using the repository's actual PsiQDK circuit and feasibility oracle."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BOUNDS = {"load": (25, 500), "growth": (0, 50), "utilization": (40, 95), "split": (0, 100),
          "storage": (0, 100), "curtailment": (0, 20), "dlr": (0, 30), "temperature": (10, 50),
          "lineLimit": (60, 100), "months": (0, 60)}
DEFAULTS = dict(load=150, growth=0, utilization=65, split=75, storage=0, curtailment=0, dlr=0,
                temperature=25, lineLimit=100, months=20, reconductor=False, rowPermit=False,
                floodProtected=True, storageCommitted=True, requireN1=True, outage="none")
BROWSER_QUBITS = 7


def validate_settings(value):
    if not isinstance(value, dict):
        raise ValueError("settings must be an object")
    result = dict(DEFAULTS)
    for key, (lo, hi) in BOUNDS.items():
        if key not in value:
            continue
        number = value[key]
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number):
            raise ValueError(f"{key} must be a finite number")
        if not lo <= number <= hi:
            raise ValueError(f"{key} must be between {lo} and {hi}")
        result[key] = number
    for key in ("reconductor", "rowPermit", "floodProtected", "storageCommitted", "requireN1"):
        if key in value:
            if not isinstance(value[key], bool):
                raise ValueError(f"{key} must be boolean")
            result[key] = value[key]
    if value.get("outage", "none") not in ("none", "northern", "esteros"):
        raise ValueError("unsupported outage")
    result["outage"] = value.get("outage", "none")
    return result


def build_job(settings):
    from quantum.space import Plan, PlanSpace
    from quantum.oracle import Oracle
    run = json.loads((ROOT / "viz/webgl/public/data/run.json").read_text(encoding="utf-8"))
    s = validate_settings(settings)
    requested = s["load"] * (1 + s["growth"] / 100)
    ids = [p["substation_id"] for p in run["candidate_plan"]["splits"]]
    snapshot = json.loads(json.dumps(run["grid_snapshot"]))
    selected = []
    for i, sid in enumerate(ids):
        sub = next(x for x in snapshot["substations"] if x["id"] == sid)
        if (s["outage"] == "northern" and i == 0) or (s["outage"] == "esteros" and i == 1):
            continue
        # Changes to utilization / temperature are explicitly scenario assumptions. Firm caps are fixed.
        sub["headroom_mw"] *= (100 - s["utilization"]) / 35 / (1 + max(0, s["temperature"] - 25) * .008)
        if not s["requireN1"]:
            sub.pop("headroom_mw_n1_firm", None)
        selected.append(sub)

    class BudgetSpace(PlanSpace):
        def __init__(self):
            self.storage_options = tuple(sorted({0.0, min(25.0, s["storage"]), min(50.0, s["storage"]), float(s["storage"])}))
            # Three curtailment levels keep every supported job within 128 slots.
            self.curtail_options = tuple(sorted({0.0, min(5.0, s["curtailment"]), float(s["curtailment"])}))
            self.dlr_options = (False, True) if s["dlr"] > 0 else (False,)
            super().__init__(site_id=run["site"]["id"], requested_mw=requested, substations=selected)

        @property
        def size(self):
            return len(self.splits) * len(self.dlr_options) * len(self.storage_options) * len(self.curtail_options)

        @property
        def n_qubits(self):
            return BROWSER_QUBITS

        def decode(self, index):
            if not 0 <= index < self.size:
                raise IndexError("plan index outside bounded space")
            rest, ci = divmod(index, len(self.curtail_options))
            rest, si = divmod(rest, len(self.storage_options))
            spi, di = divmod(rest, len(self.dlr_options))
            return Plan(index, self.splits[spi], self.dlr_options[di], self.storage_options[si], self.curtail_options[ci])

    space = BudgetSpace()
    if space.size > space.padded_size:
        raise ValueError("job exceeds the fixed seven-qubit browser register")
    oracle = Oracle(space, snapshot)
    marked = oracle.marked_indices()
    return s, run, space, oracle, marked


def run_native(settings):
    """Linux / macOS worker. There is deliberately no NumPy execution fallback."""
    from quantum.grover_psiqdk import run_grover, psiqdk_available, _qubricks
    from quantum.oracle import objective
    if not psiqdk_available():
        raise RuntimeError("PsiQDK native simulator is unavailable. Install the supported Linux PsiQDK runtime.")
    s, run, space, oracle, marked = build_job(settings)
    start = time.monotonic()
    result = run_grover(space.n_qubits, marked, shots=32, seed=7, return_states=True)
    if result.get("backend") != "psiqdk":
        raise RuntimeError("The job did not execute on PsiQDK.")
    from psiqdk.workbench import QPU, Qubits
    qc = QPU()
    qc.reset(space.n_qubits)
    register = Qubits(space.n_qubits, "plan", qc)
    register.had()
    _qubricks()[0](marked).compute(register)
    phase_state = [[float(a.real), float(a.imag)] for a in qc.pull_state()]
    hits = sorted(set(result["samples"]) & set(marked))
    chosen = min((space.decode(i) for i in hits), key=lambda p: objective(space, oracle, p)) if hits else None
    plan = space.to_candidate_plan(chosen, "psiqdk", result["iterations"] * 32 + 32) if chosen else None
    if plan:
        plan["flex"]["reconductor"] = s["reconductor"]
    chosen_settings = None
    if chosen:
        chosen_settings = dict(s, storage=chosen.storage_mw, curtailment=chosen.curtail_pct,
                               dlr=s["dlr"] if chosen.dlr else 0)
        northern_id = run["candidate_plan"]["splits"][0]["substation_id"]
        chosen_settings["split"] = next((q * 25 for sub, q in zip(space.substations, chosen.quarters)
                                         if sub["id"] == northern_id), 0)
    digest = hashlib.sha256(json.dumps(s, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {
        "job_id": uuid.uuid4().hex, "engine": "psiqdk-workbench", "backend": "psiqdk",
        "completed_utc": datetime.now(timezone.utc).isoformat(), "wall_s": round(time.monotonic() - start, 3),
        "input_settings": s, "input_sha256": digest, "status": "candidate_measured" if chosen else "no_candidate_measured",
        "plan": plan, "selected_settings": chosen_settings, "marked_indices": marked, "phase_state": phase_state,
        "space": {"N": space.size, "padded_N": space.padded_size, "n_qubits": space.n_qubits,
                  "split_steps_pct": 25, "storage_options": space.storage_options, "curtailment_options": space.curtail_options,
                  "candidate_substations": [{"id": sub["id"], "name": sub["name"]} for sub in space.substations]},
        "result": result, "measurements": dict(Counter(str(x) for x in result["samples"])),
        "scope": "Actual PsiQDK Workbench statevector simulation, not quantum hardware. The marking list is compiled classically. A measured candidate still needs grid physics and Lean verification.",
    }


def execute(settings):
    settings = validate_settings(settings)
    if os.name != "nt":
        return run_native(settings)
    if not shutil.which("wsl"):
        raise RuntimeError("PsiQDK requires Linux / WSL on Windows; no native backend was found.")
    script = ROOT / "viz/webgl/server/runner.py"
    wsl_path = "/mnt/" + script.drive[0].lower() + script.as_posix()[2:]
    wrapper = ROOT / "viz/webgl/server/wsl_runner.sh"
    wrapper_path = "/mnt/" + wrapper.drive[0].lower() + wrapper.as_posix()[2:]
    command = ["wsl", "-d", "Ubuntu", "--", "bash", wrapper_path, wsl_path]
    process = subprocess.run(command, input=json.dumps(settings), text=True, capture_output=True, timeout=100)
    if process.returncode:
        raise RuntimeError("PsiQDK worker failed. Check the Linux PsiQDK environment; no fallback result was returned.")
    lines = [line.removeprefix("QGRID_RESULT=") for line in process.stdout.splitlines() if line.startswith("QGRID_RESULT=")]
    if not lines:
        raise RuntimeError("PsiQDK worker returned no result.")
    result = json.loads(lines[-1])
    if result.get("backend") != "psiqdk":
        raise RuntimeError("A non-PsiQDK result was rejected.")
    return result
