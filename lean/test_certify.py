"""Tests for lean/certify.py and the Lean checker (synthetic test inputs, not measured data)."""
import copy
import hashlib
import json
import random
import re
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from lean import certify as C  # noqa: E402

SCHEMA = json.loads((ROOT / "contracts" / "certificate.schema.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
STANDARD_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}

SITE = {"id": "test-site", "name": "Test site", "lat": 37.0, "lon": -122.0, "requested_mw": 150,
        "deadline": "2028-06-30", "iso": "CAISO"}
SNAP = {"site_id": "test-site",
        "substations": [{"id": "A", "name": "A", "lat": 37, "lon": -122, "kv": 230, "assumed_mva": 1260,
                         "distance_km": 1, "headroom_mw": 100.0},
                        {"id": "B", "name": "B", "lat": 37, "lon": -122, "kv": 115, "assumed_mva": 90,
                         "distance_km": 2, "headroom_mw": 60.0}],
        "lines": [], "iso": {"lmp": None, "load": None, "timestamp": "2026-11-08T00:00:00Z", "source": "test"}}
PLAN = {"site_id": "test-site", "splits": [{"substation_id": "A", "mw": 95.0}, {"substation_id": "B", "mw": 55.0}],
        "flex": {"dlr": False, "storage_mw": 0, "curtailment_mw": 0, "reconductor": False},
        "search": {"method": "heuristic", "evals": 1}}
PHYS = {"converged": True, "max_line_loading_pct": 71.1, "v_min_pu": 0.9937, "v_max_pu": 1.02,
        "n1_pass": True, "violations": []}
AS_OF = "2026-11-08"


def lean_ok():
    try:
        C.ensure_built()
        return True
    except Exception:
        return False


LEAN = lean_ok()
needs_lean = pytest.mark.skipif(not LEAN, reason="Lean/lake not available to build lean/")


def run(plan=PLAN, phys=PHYS, site=SITE, engine="auto", **kw):
    kw.setdefault("as_of", AS_OF)
    return C.certify(plan, phys, site, snapshot=SNAP, engine=engine, write_evidence=False, **kw)


def mod(base, **changes):
    out = copy.deepcopy(base)
    for path, v in changes.items():
        cur = out
        keys = path.split("__")
        for k in keys[:-1]:
            cur = cur[int(k)] if isinstance(cur, list) else cur[k]
        cur[keys[-1]] = v
    return out


# (label, kwargs for run(), expected blocking obligation, expected detail fragment)
RED_CASES = [
    ("capacity_over_headroom", dict(plan=mod(PLAN, splits__0__mw=105.0, splits__1__mw=45.0)),
     "capacity", "A split 105.000 MW > headroom 100.000 MW"),
    ("capacity_sum", dict(plan=mod(PLAN, splits__1__mw=50.0)), "capacity", "!= requested 150.000 MW"),
    ("capacity_unknown_sub", dict(plan=mod(PLAN, splits__1__substation_id="Z")), "capacity", "no headroom evidence"),
    ("capacity_duplicate", dict(plan=mod(PLAN, splits=[{"substation_id": "B", "mw": 50.0}] * 3)),
     "capacity", "appears in more than one split"),
    ("thermal_loading", dict(phys=mod(PHYS, max_line_loading_pct=104.2)), "thermal_voltage", "max loading 104.2%"),
    ("thermal_voltage_low", dict(phys=mod(PHYS, v_min_pu=0.9312)), "thermal_voltage", "v_min 0.9312 pu"),
    ("thermal_not_converged", dict(phys={"converged": False, "max_line_loading_pct": None, "v_min_pu": None,
                                         "v_max_pu": None, "n1_pass": False, "violations": ["did not converge"]}),
     "thermal_voltage", "did not converge"),
    ("n1_fail", dict(phys=mod(PHYS, n1_pass=False, violations=["N-1 line L1 out: line L2 loading 121% > 110%"])),
     "n1", "N-1 contingency check failed"),
    ("flex_storage_uncommitted", dict(plan=mod(PLAN, flex__storage_mw=10)), "flex_commitment",
     "storage 10.000 MW > committed 0.000 MW"),
    ("deadline_storage", dict(plan=mod(PLAN, flex__storage_mw=10), as_of="2027-06-01",
                              commitment={"storage_mw": 20, "curtailment_mw": 0, "source": "test"}),
     "deadline", "storage lead time 547 d"),
    ("deadline_reconductor", dict(plan=mod(PLAN, flex__reconductor=True), permits={"row_granted": True}),
     "deadline", "reconductor lead time 1095 d"),
    ("deadline_past", dict(as_of="2028-07-01"), "deadline", "is after deadline"),
    ("permit_row", dict(plan=mod(PLAN, flex__reconductor=True), as_of="2024-01-01"), "permit_row",
     "no permit-granted evidence"),
    ("penalty_curtailment", dict(plan=mod(PLAN, flex__curtailment_mw=20),
                                 commitment={"storage_mw": 0, "curtailment_mw": 30, "source": "test"}),
     "penalty_trigger", "curtailment 20.000 MW > cap 10.0%"),
]


@pytest.mark.parametrize("engine", ["auto", "python"])
def test_green_case(engine):
    if engine == "auto" and not LEAN:
        pytest.skip("Lean unavailable")
    cert = run(engine=engine)
    assert cert["result"] == "GREEN" and cert["blocking_condition"] is None
    assert [c["name"] for c in cert["checks"]] == C.ALL_ORDER and all(c["pass"] for c in cert["checks"])
    assert cert["engine"] == ("lean4" if engine == "auto" else "python-mirror")
    assert not list(VALIDATOR.iter_errors(cert))


@pytest.mark.parametrize("engine", ["auto", "python"])
@pytest.mark.parametrize("label,kw,blocker,fragment", RED_CASES, ids=[c[0] for c in RED_CASES])
def test_red_blocking(label, kw, blocker, fragment, engine):
    if engine == "auto" and not LEAN:
        pytest.skip("Lean unavailable")
    cert = run(engine=engine, **kw)
    # Astra #2: a lone negotiable failure (storage/permit/curtailment terms) is AMBER, not RED
    assert cert["result"] == ("AMBER" if C.TAGS[blocker] == "negotiable" else "RED")
    assert cert["result"] != "AMBER" or cert["conditions"]
    assert cert["blocking_condition"].startswith(blocker + ": "), cert["blocking_condition"]
    assert fragment in cert["blocking_condition"], cert["blocking_condition"]
    first_fail = next(c for c in cert["checks"] if not c["pass"])
    assert first_fail["name"] == blocker
    assert cert["blocking_condition"] == f"{first_fail['name']}: {first_fail['detail']}"
    assert not list(VALIDATOR.iter_errors(cert))


def test_green_coherent_with_contract_validator():
    from validate import coherence_errors  # scripts/ on path via pipeline import
    cert = run()
    assert coherence_errors(SITE, SNAP, PLAN, PHYS, cert) == []


def test_scope_note_and_hash_binding():
    cert = run()
    ev = cert["evidence"]
    digest = hashlib.sha256(json.dumps(ev, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert cert["evidence_sha256"] == digest and digest in cert["scope_note"]
    assert "GREEN covers only the encoded rules over the supplied evidence; it is not a utility interconnection approval." in cert["scope_note"]
    assert run()["evidence_sha256"] == digest  # deterministic
    assert run(plan=mod(PLAN, splits__0__mw=95.001, splits__1__mw=54.999))["evidence_sha256"] != digest
    if LEAN:
        assert "Lean 4 decision procedure" in cert["scope_note"]
        for t in ("verdict_green_iff_all", "verdict_red_blocking_sound", "certify_deterministic"):
            assert t in cert["scope_note"]


def test_fallback_never_claims_lean(monkeypatch):
    def boom(_):
        raise RuntimeError("simulated: lake not found")
    monkeypatch.setattr(C, "run_lean", boom)
    cert = run(engine="auto")
    assert cert["engine"] == "python-mirror"
    assert "python-mirror (Lean unavailable)" in cert["scope_note"]
    assert "Lean did NOT run" in cert["scope_note"] and "Lean 4 decision procedure" not in cert["scope_note"]
    assert not list(VALIDATOR.iter_errors(cert))


def test_headroom_from_plan_splits():
    plan = mod(PLAN, splits=[{"substation_id": "A", "mw": 95.0, "headroom_mw": 100.0},
                             {"substation_id": "B", "mw": 55.0, "headroom_mw": 50.0}])
    cert = C.certify(plan, PHYS, SITE, as_of=AS_OF, engine="python", write_evidence=False)
    assert cert["evidence"]["headroom_source"] == "candidate_plan splits.headroom_mw"
    assert cert["blocking_condition"] == "capacity: B split 55.000 MW > headroom 50.000 MW"


def _random_evidence(rng):
    n = rng.randint(1, 4)
    req = rng.choice([50000, 150000, 90000])
    kws = [rng.randint(0, req) for _ in range(n - 1)]
    kws.append(max(0, req - sum(kws)) if rng.random() < 0.7 else rng.randint(0, req))
    ids = [rng.choice(["A", "B", "C", "D", "É-sub"]) for _ in range(n)]
    splits = [{"substation_id": i, "kw": k, "headroom_known": rng.random() < 0.9,
               "headroom_kw": max(0, k + rng.randint(-5000, 20000))} for i, k in zip(ids, kws)]
    a = rng.randint(20000, 21000)
    return {
        "format": C.EVIDENCE_FORMAT, "site_id": "rand", "requested_kw": req, "splits": splits,
        "headroom_source": "random", "dlr": rng.random() < 0.4,
        "dlr_headroom_uplift_permille": rng.choice([0, 0, 150]),
        "storage_kw": rng.choice([0, 0, 5000, 20000]), "curtailment_kw": rng.choice([0, 0, 10000, 20000]),
        "reconductor": rng.random() < 0.3, "new_row": rng.random() < 0.1,
        "converged": rng.random() < 0.9, "has_loading": rng.random() < 0.95,
        "max_loading_permille": rng.randint(500, 1100), "loading_limit_permille": 1000,
        "has_voltage": rng.random() < 0.95, "v_min_pu4": rng.randint(9300, 10000),
        "v_max_pu4": rng.randint(10000, 10700), "v_lo_pu4": 9500, "v_hi_pu4": 10500,
        "n1_pass": rng.random() < 0.8, "violation_count": rng.choice([0, 0, 0, 2]),
        "first_violation": rng.choice(["", "line L2 loading 112% > 100%"]),
        "committed_storage_kw": rng.choice([0, 10000, 30000]), "committed_curtailment_kw": rng.choice([0, 15000, 30000]),
        "commitment_source": "random", "as_of": "x", "as_of_day": a, "deadline": "y",
        "deadline_day": a + rng.randint(-10, 1300), "lead_dlr_days": 365, "lead_storage_days": 547,
        "lead_reconductor_days": 1095, "row_permit_granted": rng.random() < 0.5, "curtail_cap_permille": 100,
    }


@needs_lean
def test_mirror_agrees_with_lean():
    rng = random.Random(20261108)
    cases = [run()["evidence"]] + [run(**kw)["evidence"] for _, kw, _, _ in RED_CASES]
    cases += [_random_evidence(rng) for _ in range(60)]
    results = set()
    for ev in cases:
        lean = C.run_lean(ev)
        assert lean["engine"] == "lean4"
        lean = {k: lean[k] for k in ("checks", "result", "blocking_condition")}
        assert lean == C.mirror_report(ev), json.dumps(ev)
        results.add(lean["blocking_condition"].split(":")[0] if lean["blocking_condition"] else "GREEN")
    assert {"GREEN", *C.ORDER} <= results  # the sample exercises every outcome


@needs_lean
def test_theorems_use_only_standard_axioms():
    lake = C._find_lake()
    r = subprocess.run([lake, "env", "lean", "Axioms.lean"], cwd=C.LEAN_DIR, capture_output=True, text=True,
                       encoding="utf-8", timeout=600)
    assert r.returncode == 0, r.stdout + r.stderr
    lines = [ln for ln in r.stdout.splitlines() if "depends on axioms" in ln or "does not depend" in ln]
    assert len(lines) >= 10, r.stdout
    for ln in lines:
        m = re.search(r"\[(.*)\]", ln)
        axioms = {a.strip() for a in m.group(1).split(",")} if m else set()
        assert axioms <= STANDARD_AXIOMS, ln
    assert "sorry" not in r.stdout
    src = " ".join(p.read_text(encoding="utf-8") for p in (C.LEAN_DIR / "QSiteProof").glob("*.lean"))
    assert "sorry" not in src and "native_decide" not in src and not re.search(r"^\s*axiom ", src, re.M)


# ---------- Astra #2 #4 #5 #6 (python layer; not yet in lean/QSiteProof) ----------

L3 = json.loads((ROOT / "data" / "l2" / "l3_inputs.json").read_text(encoding="utf-8"))


def _bank_with_cap():
    for b in L3["banks"]:
        cap = b["cap_mw_by_curtailment_pct"].get("0")
        feeds = [f for f in L3["feeders"] if f.get("bank_id") == b["bank_id"]]
        if cap and cap > 1 and len(feeds) >= 2:
            return b, cap, feeds
    pytest.skip("no bank with >=2 feeders and positive cap in l3_inputs.json")


def test_bank_rule_shared_bank_cap_is_hard():
    b, cap, feeds = _bank_with_cap()
    site = {**SITE, "requested_mw": round(cap + 2, 3)}
    snap = {**SNAP, "substations": SNAP["substations"] + [
        {"id": f["substation_id"], "name": "x", "lat": 0, "lon": 0, "kv": 12, "assumed_mva": 50, "distance_km": 1,
         "headroom_mw": 1000.0} for f in feeds[:2]]}
    half = round((cap + 2) / 2, 3)
    splits = [{"substation_id": feeds[0]["substation_id"], "feeder_id": feeds[0]["feeder_id"], "mw": half},
              {"substation_id": feeds[1]["substation_id"],
               "feeder_id": feeds[1]["feeder_id"], "mw": round(cap + 2 - half, 3)}]
    if splits[0]["substation_id"] == splits[1]["substation_id"]:
        splits[1]["substation_id"] = "A"  # capacity rule forbids duplicate substations; bank is via feeder_id
    plan = {**PLAN, "splits": splits}
    cert = C.certify(plan, PHYS, site, snapshot=snap, as_of=AS_OF, engine="python", write_evidence=False)
    bank = next(c for c in cert["checks"] if c["name"] == "bank")
    assert not bank["pass"] and bank["tag"] == "hard" and b["bank_id"] in bank["detail"], bank
    assert cert["result"] == "RED"
    # each feeder alone under its bank cap -> bank check passes
    small = {**plan, "splits": [dict(splits[0], mw=1.0)]}
    cert2 = C.certify(small, PHYS, {**site, "requested_mw": 1.0}, snapshot=snap, as_of=AS_OF, engine="python",
                      write_evidence=False)
    assert next(c for c in cert2["checks"] if c["name"] == "bank")["pass"]


def test_amber_lists_conditions_and_red_only_on_hard():
    cert = run(engine="python", plan=mod(PLAN, flex__storage_mw=10))
    assert cert["result"] == "AMBER" and cert["conditions"] and "flex_commitment" in cert["conditions"][0]
    assert not list(VALIDATOR.iter_errors(cert))
    # negotiable + hard failure together -> RED, blocking = the hard one
    cert = run(engine="python", plan=mod(PLAN, flex__storage_mw=10), phys=mod(PHYS, n1_pass=False))
    assert cert["result"] == "RED" and cert["blocking_condition"].startswith("n1: ")


def test_storage_relief_bounded_by_load():
    site = {**SITE, "requested_mw": 1.0}
    plan = {**PLAN, "splits": [{"substation_id": "A", "mw": 1.0}],
            "flex": {"dlr": False, "storage_mw": 50, "curtailment_mw": 0, "reconductor": False}}
    cert = C.certify(plan, PHYS, site, snapshot=SNAP, as_of="2024-01-01", engine="python", write_evidence=False,
                     commitment={"storage_mw": 50, "curtailment_mw": 0, "source": "test"})
    assert cert["result"] == "RED" and cert["blocking_condition"].startswith("storage_relief: ")
    ok = run(engine="python", plan=mod(PLAN, flex__storage_mw=10), as_of="2024-01-01",
             commitment={"storage_mw": 10, "curtailment_mw": 0, "source": "test"})
    relief = next(c for c in ok["checks"] if c["name"] == "storage_relief")
    assert relief["pass"] and "40.000 MWh" in relief["detail"] and "4 h" in relief["detail"]


def test_net_load_shared_with_oracle():
    # Astra #6 repro: 100 MW load, 25 MW storage, 80 MW headroom -> both oracle and certify say fits
    from quantum.load_model import net_split
    assert net_split(100, 100, 25, 0) == 75.0
    site = {**SITE, "requested_mw": 100.0}
    snap = {**SNAP, "substations": [dict(SNAP["substations"][0], headroom_mw=80.0)]}
    plan = {**PLAN, "splits": [{"substation_id": "A", "mw": 100.0}],
            "flex": {"dlr": False, "storage_mw": 25, "curtailment_mw": 0, "reconductor": False}}
    cert = C.certify(plan, PHYS, site, snapshot=snap, as_of="2024-01-01", engine="python", write_evidence=False,
                     commitment={"storage_mw": 25, "curtailment_mw": 0, "source": "test"})
    assert next(c for c in cert["checks"] if c["name"] == "capacity")["pass"], cert["checks"]
    # DLR does not raise substation headroom (lines only)
    over = {**plan, "flex": {"dlr": True, "storage_mw": 0, "curtailment_mw": 0, "reconductor": False}}
    cert = C.certify(over, PHYS, site, snapshot=snap, as_of="2024-01-01", engine="python", write_evidence=False,
                     params={"dlr_headroom_uplift_permille": 300})
    assert cert["blocking_condition"].startswith("capacity: ")


def test_evidence_hash_binds_plan_ids():
    base = run()["evidence_sha256"]
    assert run(plan=mod(PLAN, site_id="other-site"))["evidence_sha256"] != base
    assert run(plan=mod(PLAN, site_id="other-site"))["blocking_condition"].startswith("evidence_binding: ")
    fe = mod(PLAN, splits__0__feeder_id="F1")
    h1 = run(plan=fe)["evidence_sha256"]
    assert h1 != base and run(plan=mod(fe, splits__0__feeder_id="F2"))["evidence_sha256"] != h1
    assert run(plan=mod(PLAN, splits__1__bank_id="BANK-9"))["evidence_sha256"] != base
    assert run(phys=mod(PHYS, max_line_loading_pct=71.2))["evidence_sha256"] != base


def test_firm_n1_red_names_gap_and_amber_when_flex_closes_it():
    snap = {**SNAP, "substations": [dict(s, headroom_mw_n1_firm=30.0) for s in SNAP["substations"]]}
    viol = ["N-1 transformer XF-A largest bank out: plan 95.0 MW > firm headroom 60.0 MW (headroom_mw_n1_firm)"]
    phys = mod(PHYS, n1_pass=False, violations=viol)
    cert = C.certify(PLAN, phys, SITE, snapshot=snap, as_of=AS_OF, engine="python", write_evidence=False)
    assert cert["result"] == "RED"
    assert cert["blocking_condition"].startswith("firm_n1: exceeds firm N-1 capacity of the candidate substations by")
    # firm 30: needs 150*(1-30/95)=102.6 MW relief > 65 MW levers -> RED. firm 63 + 45 MW storage: 5.5 MW more -> AMBER
    plan = mod(PLAN, flex__storage_mw=45, flex__curtailment_mw=0)
    snap2 = {**snap, "substations": [dict(s, headroom_mw_n1_firm=63.0) for s in SNAP["substations"]]}
    cert = C.certify(plan, phys, SITE, snapshot=snap2, as_of="2024-01-01", engine="python", write_evidence=False,
                     commitment={"storage_mw": 45, "curtailment_mw": 0, "source": "test"})
    firm = next(c for c in cert["checks"] if c["name"] == "firm_n1")
    assert not firm["pass"] and firm["tag"] == "negotiable", firm
    assert cert["result"] == "AMBER" and any(c.startswith("firm_n1") for c in cert["conditions"]), cert["blocking_condition"]
