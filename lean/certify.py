"""Prove stage (L3): certify(plan, physics, site) -> certificate.

Pipeline:  plan + physics_result + site (+ grid snapshot headroom)
           -> fixed-point evidence JSON (kW, per-mille, 1e-4 pu, day numbers; no floats)
           -> Lean 4 checker `lake exe qsiteproof` (lean/QSiteProof/*.lean)
           -> certificate (contracts/certificate.schema.json)

The Lean theorems (kernel-checked when the library is built) are:
  verdict_green_iff_all, verdict_red_blocking_sound, verdict_red_iff_exists, blocking_is_first,
  verdict_extensional, certify_deterministic, report_pass_sound, report_blocking_none_iff_green.
The verdict itself is computed by the compiled Lean executable from the same definitions.

Headroom: certify()'s pipeline signature has no snapshot. Headroom is taken from, in order:
  1. the `snapshot=` kwarg;
  2. `headroom_mw` on each plan split (extra key; candidate_plan.schema allows it);
  3. the file named by env QSITEPROOF_SNAPSHOT;
  4. grid.snapshot.get_snapshot(site) with QSITE_OFFLINE=1 (cache only; same L2 ratings as the pipeline);
  5. the newest runs/*/grid_snapshot.json for this site_id that covers every split;
  otherwise the split is marked "no headroom evidence" and capacity fails (never guessed).

If Lean cannot run, an identical Python mirror (mirror_report) decides, and scope_note says
"python-mirror (Lean unavailable)". Env QSITEPROOF_ENGINE=auto|lean|python (default auto).

ASSUMED parameters (stated in every scope_note): flex lead times (DLR 365 d, storage 547 d,
reconductor 1095 d), curtailment penalty cap 10% of requested, voltage band 0.95-1.05 pu and
100% loading limit (same as grid/physics.py), DLR headroom uplift 0% (L2 method: DLR uplifts
line ratings, not transformer headroom; validate.py also ignores flex for headroom), no
storage/curtailment committed and no ROW permit unless the site supplies evidence.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

LEAN_DIR = Path(__file__).resolve().parent
ROOT = LEAN_DIR.parent
OUT_DIR = LEAN_DIR / "out"
EVIDENCE_FORMAT = "qsiteproof-evidence/1"
ORDER = ["capacity", "thermal_voltage", "n1", "flex_commitment", "deadline", "permit_row", "penalty_trigger"]
THEOREMS = ["verdict_green_iff_all", "verdict_red_blocking_sound", "blocking_is_first",
            "verdict_extensional", "certify_deterministic", "report_pass_sound"]

DEFAULTS = {
    "lead_dlr_days": 365,          # ~12 months, ASSUMED
    "lead_storage_days": 547,      # ~18 months, ASSUMED
    "lead_reconductor_days": 1095,  # ~36 months, ASSUMED
    "curtail_cap_permille": 100,   # 10% of requested, ASSUMED
    "loading_limit_permille": 1000,  # 100% (grid/physics.py LOAD_LIMIT_PCT)
    "v_lo_pu4": 9500, "v_hi_pu4": 10500,  # 0.95-1.05 pu (grid/physics.py V_NORMAL)
    "dlr_headroom_uplift_permille": 0,
}
SCOPE_TAIL = ("GREEN covers only the encoded rules over the supplied evidence; "
              "it is not a utility interconnection approval.")

_EPS = 1e-6


# ---------- fixed-point conversion (conservative rounding) ----------

def _kw_round(mw):
    return int(round(float(mw) * 1000))


def _kw_floor(mw):
    return max(0, int(math.floor(float(mw) * 1000 + _EPS)))


def _kw_ceil(mw):
    return max(0, int(math.ceil(float(mw) * 1000 - _EPS)))


def _day(d):
    if isinstance(d, str):
        d = date.fromisoformat(d[:10])
    return (d - date(1970, 1, 1)).days


def _headroom_source(plan, site, snapshot):
    """-> ({substation_id: headroom_mw}, source label). See module docstring for the order."""
    ids = [s["substation_id"] for s in plan["splits"]]
    if snapshot is not None:
        return {s["id"]: s["headroom_mw"] for s in snapshot["substations"]}, "snapshot kwarg"
    if all("headroom_mw" in s for s in plan["splits"]):
        return {s["substation_id"]: s["headroom_mw"] for s in plan["splits"]}, "candidate_plan splits.headroom_mw"
    env = os.environ.get("QSITEPROOF_SNAPSHOT")
    if env and Path(env).exists():
        snap = json.loads(Path(env).read_text(encoding="utf-8"))
        return {s["id"]: s["headroom_mw"] for s in snap["substations"]}, f"QSITEPROOF_SNAPSHOT={env}"
    try:
        import sys
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from grid.snapshot import get_snapshot
        old = os.environ.get("QSITE_OFFLINE")
        os.environ["QSITE_OFFLINE"] = "1"
        try:
            snap = get_snapshot(site)
        finally:
            if old is None:
                os.environ.pop("QSITE_OFFLINE", None)
            else:
                os.environ["QSITE_OFFLINE"] = old
        heads = {s["id"]: s["headroom_mw"] for s in snap["substations"]}
        if all(i in heads for i in ids):
            return heads, "grid.snapshot.get_snapshot(site) offline cache"
    except Exception:  # grid lane unavailable or no cache: fall through to earlier runs
        pass
    runs = sorted((ROOT / "runs").glob("*/grid_snapshot.json"), reverse=True) if (ROOT / "runs").exists() else []
    for p in runs:
        try:
            snap = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        heads = {s["id"]: s["headroom_mw"] for s in snap.get("substations", [])}
        if snap.get("site_id") in (None, site.get("id")) and all(i in heads for i in ids):
            return heads, f"{p.relative_to(ROOT).as_posix()} (earlier pipeline run)"
    return {}, "none (no snapshot found)"


def build_evidence(plan, physics, site, snapshot=None, *, as_of=None, commitment=None,
                   permits=None, params=None):
    """Plan/physics/site/snapshot -> (evidence dict for the Lean checker, notes list)."""
    p = {**DEFAULTS, **(params or {})}
    heads, head_src = _headroom_source(plan, site, snapshot)
    splits = []
    for s in plan["splits"]:
        h = heads.get(s["substation_id"])
        splits.append({"substation_id": s["substation_id"], "kw": _kw_round(s["mw"]),
                       "headroom_known": h is not None, "headroom_kw": _kw_floor(h) if h is not None else 0})

    flex = plan["flex"]
    commit = commitment if commitment is not None else site.get("flex_commitment")
    if commit is not None:
        c_store, c_curt = _kw_floor(commit.get("storage_mw", 0)), _kw_floor(commit.get("curtailment_mw", 0))
        c_src = commit.get("source", "site evidence")
    else:
        c_store, c_curt, c_src = 0, 0, "ASSUMED: no site commitment evidence, none committed"
    perm = permits if permits is not None else site.get("permits", {})

    as_of = as_of or os.environ.get("QSITEPROOF_AS_OF") or datetime.now(timezone.utc).date().isoformat()
    lm, vmin, vmax = physics.get("max_line_loading_pct"), physics.get("v_min_pu"), physics.get("v_max_pu")
    viol = list(physics.get("violations") or [])
    ev = {
        "format": EVIDENCE_FORMAT,
        "site_id": site.get("id", ""),
        "requested_kw": _kw_round(site["requested_mw"]),
        "splits": splits,
        "headroom_source": head_src,
        "dlr": bool(flex["dlr"]),
        "dlr_headroom_uplift_permille": int(p["dlr_headroom_uplift_permille"]),
        "storage_kw": _kw_ceil(flex["storage_mw"]),
        "curtailment_kw": _kw_ceil(flex["curtailment_mw"]),
        "reconductor": bool(flex["reconductor"]),
        "new_row": bool(flex.get("new_row", False)),
        "converged": bool(physics["converged"]),
        "has_loading": lm is not None,
        "max_loading_permille": max(0, int(math.ceil(float(lm) * 10 - _EPS))) if lm is not None else 0,
        "loading_limit_permille": int(p["loading_limit_permille"]),
        "has_voltage": vmin is not None and vmax is not None,
        "v_min_pu4": max(0, int(math.floor(float(vmin) * 10000 + _EPS))) if vmin is not None else 0,
        "v_max_pu4": max(0, int(math.ceil(float(vmax) * 10000 - _EPS))) if vmax is not None else 0,
        "v_lo_pu4": int(p["v_lo_pu4"]), "v_hi_pu4": int(p["v_hi_pu4"]),
        "n1_pass": bool(physics["n1_pass"]),
        "violation_count": len(viol),
        "first_violation": viol[0] if viol else "",
        "committed_storage_kw": c_store,
        "committed_curtailment_kw": c_curt,
        "commitment_source": c_src,
        "as_of": as_of[:10], "as_of_day": _day(as_of),
        "deadline": site["deadline"][:10], "deadline_day": _day(site["deadline"]),
        "lead_dlr_days": int(p["lead_dlr_days"]),
        "lead_storage_days": int(p["lead_storage_days"]),
        "lead_reconductor_days": int(p["lead_reconductor_days"]),
        "row_permit_granted": bool(perm.get("row_granted", False)),
        "curtail_cap_permille": int(p["curtail_cap_permille"]),
    }
    return ev


def canonical(evidence):
    return json.dumps(evidence, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def evidence_hash(evidence):
    return hashlib.sha256(canonical(evidence).encode("ascii")).hexdigest()


# ---------- Python mirror of lean/QSiteProof/{Basic,Report}.lean ----------

def _mw(kw):
    return f"{kw // 1000}.{kw % 1000:03d} MW"


def _pct(pm):
    return f"{pm // 10}.{pm % 10}%"


def _pu(v):
    return f"{v // 10000}.{v % 10000:04d}"


def _uplift(e):
    return e["dlr_headroom_uplift_permille"] if e["dlr"] else 0


def _split_fits(e, s):
    return s["headroom_known"] and s["kw"] * 1000 <= s["headroom_kw"] * (1000 + _uplift(e))


def _distinct(ids):
    return len(set(ids)) == len(ids)


def _first_dup(ids):
    for i, x in enumerate(ids):
        if x in ids[i + 1:]:
            return x
    return None


def _deadline_met(e):
    a, d = e["as_of_day"], e["deadline_day"]
    return (a <= d and (not e["dlr"] or a + e["lead_dlr_days"] <= d)
            and (not e["storage_kw"] > 0 or a + e["lead_storage_days"] <= d)
            and (not e["reconductor"] or a + e["lead_reconductor_days"] <= d))


def _penalty_triggered(e):
    return e["requested_kw"] * e["curtail_cap_permille"] < e["curtailment_kw"] * 1000 or not _deadline_met(e)


def _holds(name, e):
    if name == "capacity":
        return (sum(s["kw"] for s in e["splits"]) == e["requested_kw"]
                and _distinct([s["substation_id"] for s in e["splits"]])
                and all(_split_fits(e, s) for s in e["splits"]))
    if name == "thermal_voltage":
        return (e["converged"] and e["has_loading"] and e["max_loading_permille"] <= e["loading_limit_permille"]
                and e["has_voltage"] and e["v_lo_pu4"] <= e["v_min_pu4"] and e["v_max_pu4"] <= e["v_hi_pu4"])
    if name == "n1":
        return e["n1_pass"] and e["violation_count"] == 0
    if name == "flex_commitment":
        return e["storage_kw"] <= e["committed_storage_kw"] and e["curtailment_kw"] <= e["committed_curtailment_kw"]
    if name == "deadline":
        return _deadline_met(e)
    if name == "permit_row":
        return not (e["reconductor"] or e["new_row"]) or e["row_permit_granted"]
    if name == "penalty_trigger":
        return not _penalty_triggered(e)
    raise KeyError(name)


def _uplift_note(e):
    u = _uplift(e)
    return f" (+{_pct(u)} DLR headroom uplift)" if u > 0 else ""


def _detail(name, e):
    if name == "capacity":
        total = sum(s["kw"] for s in e["splits"])
        if total != e["requested_kw"]:
            return f"splits sum {_mw(total)} != requested {_mw(e['requested_kw'])}"
        d = _first_dup([s["substation_id"] for s in e["splits"]])
        if d is not None:
            return f"substation {d} appears in more than one split"
        for s in e["splits"]:
            if not _split_fits(e, s):
                if s["headroom_known"]:
                    return f"{s['substation_id']} split {_mw(s['kw'])} > headroom {_mw(s['headroom_kw'])}{_uplift_note(e)}"
                return f"{s['substation_id']} has no headroom evidence in the grid snapshot"
        return (f"{len(e['splits'])} splits sum to requested {_mw(e['requested_kw'])}; "
                f"every split <= substation headroom{_uplift_note(e)}")
    if name == "thermal_voltage":
        if not e["converged"]:
            return "base-case power flow did not converge"
        if not e["has_loading"]:
            return "max line loading missing from physics result"
        if e["max_loading_permille"] > e["loading_limit_permille"]:
            return f"max loading {_pct(e['max_loading_permille'])} > limit {_pct(e['loading_limit_permille'])}"
        if not e["has_voltage"]:
            return "voltage missing from physics result"
        if e["v_min_pu4"] < e["v_lo_pu4"]:
            return f"v_min {_pu(e['v_min_pu4'])} pu < {_pu(e['v_lo_pu4'])} pu"
        if e["v_max_pu4"] > e["v_hi_pu4"]:
            return f"v_max {_pu(e['v_max_pu4'])} pu > {_pu(e['v_hi_pu4'])} pu"
        return (f"converged; max loading {_pct(e['max_loading_permille'])} <= {_pct(e['loading_limit_permille'])}; "
                f"voltage {_pu(e['v_min_pu4'])}-{_pu(e['v_max_pu4'])} pu within "
                f"{_pu(e['v_lo_pu4'])}-{_pu(e['v_hi_pu4'])} pu")
    if name == "n1":
        first = f"; first: {e['first_violation']}" if e["first_violation"] else ""
        if not e["n1_pass"]:
            return f"N-1 contingency check failed ({e['violation_count']} violations{first})"
        if e["violation_count"] > 0:
            return f"{e['violation_count']} violations reported{first}"
        return "N-1 pass; no violations"
    if name == "flex_commitment":
        src = e["commitment_source"]
        if e["storage_kw"] > e["committed_storage_kw"]:
            return f"storage {_mw(e['storage_kw'])} > committed {_mw(e['committed_storage_kw'])} ({src})"
        if e["curtailment_kw"] > e["committed_curtailment_kw"]:
            return f"curtailment {_mw(e['curtailment_kw'])} > committed {_mw(e['committed_curtailment_kw'])} ({src})"
        return (f"storage {_mw(e['storage_kw'])} <= {_mw(e['committed_storage_kw'])}; curtailment "
                f"{_mw(e['curtailment_kw'])} <= {_mw(e['committed_curtailment_kw'])} ({src})")
    if name == "deadline":
        if e["as_of_day"] > e["deadline_day"]:
            return f"as-of {e['as_of']} is after deadline {e['deadline']}"
        left = e["deadline_day"] - e["as_of_day"]
        opts = [("DLR", e["dlr"], e["lead_dlr_days"]), ("storage", e["storage_kw"] > 0, e["lead_storage_days"]),
                ("reconductor", e["reconductor"], e["lead_reconductor_days"])]
        used = [o for o in opts if o[1]]
        for n, _, lead in used:
            if lead > left:
                return (f"{n} lead time {lead} d (ASSUMED) > {left} d left before deadline {e['deadline']} "
                        f"(as of {e['as_of']})")
        if not used:
            return (f"no flex option with a lead time used; {left} d left before deadline {e['deadline']} "
                    f"(as of {e['as_of']})")
        names = ", ".join(f"{n} {lead} d" for n, _, lead in used)
        return (f"used options finish in time ({names}; lead times ASSUMED) <= {left} d left before deadline "
                f"{e['deadline']} (as of {e['as_of']})")
    if name == "permit_row":
        what = "reconductor" if e["reconductor"] else "new ROW"
        if e["reconductor"] or e["new_row"]:
            if e["row_permit_granted"]:
                return f"{what} used; ROW/permit granted per supplied evidence"
            return f"{what} needs ROW/permit; no permit-granted evidence supplied"
        return "no reconductor or new ROW used; no ROW permit needed"
    if name == "penalty_trigger":
        if e["requested_kw"] * e["curtail_cap_permille"] < e["curtailment_kw"] * 1000:
            return (f"penalty trigger TRUE: curtailment {_mw(e['curtailment_kw'])} > cap "
                    f"{_pct(e['curtail_cap_permille'])} of requested")
        if not _deadline_met(e):
            return "penalty trigger TRUE: deadline miss"
        return (f"penalty trigger FALSE: curtailment {_mw(e['curtailment_kw'])} <= cap "
                f"{_pct(e['curtail_cap_permille'])} of requested; deadline met")
    raise KeyError(name)


def mirror_report(e):
    """Python mirror of `QSiteProof.report` + `reportJson` (without engine/lean_version)."""
    checks = [{"name": n, "pass": bool(_holds(n, e)), "detail": _detail(n, e)} for n in ORDER]
    first = next((c for c in checks if not c["pass"]), None)
    return {"checks": checks, "result": "RED" if first else "GREEN",
            "blocking_condition": f"{first['name']}: {first['detail']}" if first else None}


# ---------- Lean runner ----------

def _exe_path():
    return LEAN_DIR / ".lake" / "build" / "bin" / ("qsiteproof.exe" if os.name == "nt" else "qsiteproof")


def _find_lake():
    found = shutil.which("lake")
    if found:
        return found
    for cand in (Path.home() / ".elan" / "bin" / "lake.exe", Path.home() / ".elan" / "bin" / "lake"):
        if cand.exists():
            return str(cand)
    return None


def _sources_newer_than(exe):
    t = exe.stat().st_mtime
    srcs = list(LEAN_DIR.glob("*.lean")) + list((LEAN_DIR / "QSiteProof").glob("*.lean"))
    return any(p.stat().st_mtime > t for p in srcs)


def ensure_built(timeout=900):
    """Return the Lean checker path, running `lake build` when missing or stale. Raises on failure."""
    exe = _exe_path()
    if exe.exists() and not _sources_newer_than(exe):
        return exe
    lake = _find_lake()
    if not lake:
        raise RuntimeError("lake not found on PATH or ~/.elan/bin")
    r = subprocess.run([lake, "build"], cwd=LEAN_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    if r.returncode != 0 or not exe.exists():
        raise RuntimeError(f"lake build failed: {(r.stdout + r.stderr)[-800:]}")
    return exe


def run_lean(evidence, timeout=120):
    """Run the Lean checker on the canonical evidence; return its parsed JSON report."""
    exe = ensure_built()
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "evidence.json"
        path.write_text(canonical(evidence), encoding="ascii")
        r = subprocess.run([str(exe), str(path)], capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"qsiteproof exited {r.returncode}: {r.stderr.strip()[-400:]}")
    out = json.loads(r.stdout)
    if out.get("engine") != "lean4":
        raise RuntimeError("unexpected checker output")
    return out


# ---------- stage entry point ----------

def _assumption_note(ev):
    return (f"ASSUMED: lead times DLR {ev['lead_dlr_days']} d, storage {ev['lead_storage_days']} d, "
            f"reconductor {ev['lead_reconductor_days']} d; curtailment penalty cap {_pct(ev['curtail_cap_permille'])} "
            f"of requested; loading limit {_pct(ev['loading_limit_permille'])}, voltage band "
            f"{_pu(ev['v_lo_pu4'])}-{_pu(ev['v_hi_pu4'])} pu; DLR headroom uplift {_pct(ev['dlr_headroom_uplift_permille'])}; "
            f"flex commitment: {ev['commitment_source']}; ROW permit granted: {str(ev['row_permit_granted']).lower()}; "
            f"as-of {ev['as_of']}; headroom from {ev['headroom_source']}.")


def certify(plan, physics, site, snapshot=None, *, as_of=None, commitment=None, permits=None,
            params=None, engine=None, write_evidence=True):
    """plan: candidate_plan, physics: physics_result, site: site -> certificate.

    Optional kwargs (the pipeline passes none): snapshot (grid_snapshot for headroom), as_of
    (YYYY-MM-DD), commitment ({storage_mw, curtailment_mw, source}), permits ({row_granted}),
    params (override DEFAULTS), engine ("auto"|"lean"|"python").
    """
    ev = build_evidence(plan, physics, site, snapshot, as_of=as_of, commitment=commitment,
                        permits=permits, params=params)
    digest = evidence_hash(ev)
    engine = engine or os.environ.get("QSITEPROOF_ENGINE", "auto")
    lean_err = None
    rep = None
    if engine in ("auto", "lean"):
        try:
            rep = run_lean(ev)
        except Exception as exc:  # any failure to run Lean -> mirror, and say so
            if engine == "lean":
                raise
            lean_err = str(exc).splitlines()[0][:200] if str(exc) else type(exc).__name__
    if rep is not None:
        how = (f"Rules checked by the Lean 4 decision procedure QSiteProof (Lean {rep.get('lean_version', '?')}, "
               f"compiled `lake exe qsiteproof`); its correctness theorems are kernel-checked: "
               + ", ".join(f"QSiteProof.{t}" for t in THEOREMS) + ".")
        engine_used = "lean4"
    else:
        rep = mirror_report(ev)
        why = f" ({lean_err})" if lean_err else ""
        how = ("Rules checked by python-mirror (Lean unavailable)" + why + "; Lean did NOT run for this certificate. "
               "The mirror re-implements lean/QSiteProof (theorems there: "
               + ", ".join(THEOREMS) + ") but carries no proof.")
        engine_used = "python-mirror"
    if write_evidence:
        try:
            OUT_DIR.mkdir(exist_ok=True)
            (OUT_DIR / f"evidence-{digest[:16]}.json").write_text(canonical(ev), encoding="ascii")
        except OSError:
            pass
    scope = (f"{how} Obligations in order: {', '.join(ORDER)}. Evidence sha256: {digest} "
             f"(canonical JSON, sorted keys). {_assumption_note(ev)} {SCOPE_TAIL}")
    return {"checks": rep["checks"], "result": rep["result"], "blocking_condition": rep["blocking_condition"],
            "scope_note": scope, "engine": engine_used, "evidence_sha256": digest, "evidence": ev}


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 4:
        raise SystemExit("usage: python lean/certify.py plan.json physics.json site.json")
    a = [json.loads(Path(x).read_text(encoding="utf-8")) for x in sys.argv[1:]]
    print(json.dumps(certify(*a), indent=2))
