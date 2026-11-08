"""pytest for the L3 search stage. PsiQDK-dependent tests skip when psiqdk is not importable (e.g. Windows)."""
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from quantum.baselines import heuristic_search, random_search  # noqa: E402
from quantum.grover_psiqdk import psiqdk_available  # noqa: E402
from quantum.oracle import Oracle, parse_constraints  # noqa: E402
from quantum.search import propose  # noqa: E402
from quantum.space import PlanSpace, build_space, compositions  # noqa: E402
from quantum.statevector import grover_states, marked_probability_theory, optimal_iterations  # noqa: E402

SCHEMA = json.loads((ROOT / "contracts" / "candidate_plan.schema.json").read_text(encoding="utf-8"))
SITE = json.loads((ROOT / "data" / "l1" / "site.json").read_text(encoding="utf-8"))


def _sub(i, headroom, dist, **kw):
    return {"id": f"S{i}", "name": f"Synthetic {i}", "lat": 37.0, "lon": -122.0, "kv": 115, "assumed_mva": 300,
            "distance_km": dist, "headroom_mw": headroom, **kw}


# 150 MW does not fit the real substations' N-1 firm headroom (~19.9 MW each), so search-mechanics tests on the
# real snapshot use a request that does
SITE_FIRM = {**SITE, "requested_mw": 30}
SYN = {"substations": [_sub(1, 200, 1.0), _sub(2, 10, 2.0), _sub(3, 100, 3.0), _sub(4, 40, 4.0), _sub(5, 500, 9.0),
                       _sub(6, 0, 0.5)],
       "lines": [], "iso": {"lmp": None, "load": None, "timestamp": "2026-11-08T00:00:00Z", "source": "test"},
       "dlr_uplift_pct": 10}
SYN_SITE = {"id": "t", "name": "t", "lat": 37, "lon": -122, "requested_mw": 100, "deadline": "2028-06-30", "iso": "CAISO"}


@pytest.fixture(scope="module")
def real_snapshot():
    os.environ["QSITE_OFFLINE"] = "1"  # cached OSM/L2/ISO data only: no network in tests
    try:
        import gridstatus  # noqa: F401
    except ImportError:  # WSL venv has no gridstatus; offline mode only needs the import to succeed
        import types
        sys.modules["gridstatus"] = types.ModuleType("gridstatus")
    from grid.snapshot import get_snapshot
    return get_snapshot(SITE)


# --- space ---------------------------------------------------------------------------------------------
def test_space_size_and_encoding():
    assert len(compositions(4, 4)) == math.comb(7, 3) == 35
    assert all(sum(c) == 4 for c in compositions(4, 4))
    sp = build_space(SYN_SITE, SYN)
    assert [s["id"] for s in sp.substations] == ["S1", "S2", "S3", "S4"]  # nearest 4 with headroom > 0 (S6 has 0)
    assert sp.size == 35 * 2 * 3 * 3 == 630 and sp.n_qubits == 10 and sp.padded_size == 1024
    for i in (0, 1, 17, 314, 629):
        p = sp.decode(i)
        assert sp.encode(p.quarters, p.dlr, p.storage_mw, p.curtail_pct) == i
    with pytest.raises(IndexError):
        sp.decode(630)
    assert build_space(SYN_SITE, SYN, k=3).size == math.comb(6, 2) * 18


def test_splits_sum_exactly():
    sp = PlanSpace("t", 150.0, SYN["substations"][:4])
    for p in sp.plans():
        assert abs(sum(sp.split_mw(p)) - 150.0) < 1e-9


# --- oracle --------------------------------------------------------------------------------------------
def test_oracle_marking_rule():
    sp = build_space(SYN_SITE, SYN)  # requested 100 MW -> 25 MW per quarter
    o = Oracle(sp, SYN)
    assert o.dlr_uplift_pct == [10.0] * 4
    assert o(sp.encode((4, 0, 0, 0), False, 0, 0))          # 100 <= 200
    assert not o(sp.encode((0, 4, 0, 0), False, 0, 0))      # 100 > 10
    assert not o(sp.encode((0, 0, 0, 4), False, 0, 0))      # 100 > 40
    # 50 MW on S4 (headroom 40): load cut by storage 25 + curtail 10% -> 50*0.65 = 32.5 <= 40
    assert not o(sp.encode((2, 0, 0, 2), False, 0, 0))
    assert o(sp.encode((2, 0, 0, 2), False, 25, 10))
    # 25 MW on S2 (headroom 10): DLR alone gives 11 < 25; storage 50 + curtail 10% cut the load to 25*0.4 = 10
    assert not o(sp.encode((3, 1, 0, 0), True, 0, 0))
    assert o(sp.encode((3, 1, 0, 0), False, 50, 10))
    # DLR does not raise substation headroom (lines only): curtail 10% leaves 45 > 40; storage 25 leaves 37.5
    assert not o(sp.encode((2, 0, 0, 2), True, 0, 10))
    assert o(sp.encode((2, 0, 0, 2), True, 25, 0))           # 50*0.75 = 37.5 <= 40
    marked = o.marked_indices()
    assert marked and all(o(i) for i in marked) and max(marked) < sp.size


def test_oracle_missing_dlr_uplift_is_zero_and_said():
    snap = {**SYN, "dlr_uplift_pct": None}
    o = Oracle(build_space(SYN_SITE, snap), snap)
    assert o.dlr_uplift_pct == [0.0] * 4 and any("0%" in n for n in o.notes)


def test_constraint_interpretation():
    subs = SYN["substations"][:4]
    cs = parse_constraints(["capacity: S2 split 25.0 MW > headroom 10.0 MW",
                            "flex_commitment: storage 25.0 MW > committed 0.0 MW (ASSUMED)",
                            "n1: N-1 contingency check failed (1 violations; first: N-1 line L-AB out: line L-BC loading 115% > 110%)",
                            "something the parser does not know"], subs)
    # a named "> headroom X MW" caps that substation instead of excluding it (firm N-1 feedback)
    assert cs.capped_substations == {"S2": 10.0} and not cs.excluded_substations
    assert cs.forbid_storage and cs.require_dlr
    assert cs.unparsed == ["something the parser does not know"]
    # S2 must not match a longer id such as S21
    assert parse_constraints(["capacity: S21 split"], subs).excluded_substations == set()
    assert parse_constraints(["capacity: S2 has no headroom evidence"], subs).excluded_substations == {"S2"}


def test_constraint_exclusion_in_oracle():
    sp = build_space(SYN_SITE, SYN)
    o = Oracle(sp, SYN, ["capacity: S1 split 100 MW > headroom 50 MW", "penalty trigger TRUE: curtailment 10 MW"])
    marked = [sp.decode(i) for i in o.marked_indices()]
    assert marked and all(p.curtail_pct == 0 and sp.split_mw(p)[0] * (1 - p.storage_mw / 100) <= 50 for p in marked)
    assert any(p.quarters[0] for p in marked)  # S1 restricted to 50 MW, not excluded


def test_oracle_respects_n1_firm_headroom():
    snap = {**SYN, "substations": [dict(s, headroom_mw_n1_firm=30.0) if s["id"] == "S1" else s
                                   for s in SYN["substations"]]}
    sp = build_space(SYN_SITE, snap)
    o = Oracle(sp, snap)
    assert not o(sp.encode((4, 0, 0, 0), False, 0, 0))     # 100 MW > firm 30 though headroom 200
    assert all(sp.split_mw(sp.decode(i))[0] <= 30 + 1e-9 or sp.decode(i).storage_mw for i in o.marked_indices())


# --- Grover maths ---------------------------------------------------------------------------------------
def test_numpy_grover_matches_theory():
    n, marked = 8, [3, 77, 200, 201, 255]
    k = optimal_iterations(2 ** n, len(marked))
    assert k == math.floor(math.pi / 4 * math.sqrt(256 / 5))
    states = grover_states(n, marked, k)
    for i, st in enumerate(states):
        assert abs(np.linalg.norm(st) - 1) < 1e-12
        p = float((np.abs(st[marked]) ** 2).sum())
        assert abs(p - marked_probability_theory(256, 5, i)) < 1e-9


@pytest.mark.skipif(not psiqdk_available(), reason="psiqdk not importable here (Windows: run in WSL)")
@pytest.mark.parametrize("n,marked", [(5, [0, 7, 19]), (10, None)])
def test_psiqdk_amplitudes_match_numpy(n, marked, real_snapshot):
    from quantum.grover_psiqdk import run_grover
    if marked is None:  # the real plan space for the real site
        sp = build_space(SITE, real_snapshot)
        marked = Oracle(sp, real_snapshot).marked_indices()
        n = sp.n_qubits
    res = run_grover(n, marked, shots=8, seed=1, return_states=True)
    ref = grover_states(n, marked, res["iterations"])
    assert res["iterations"] == optimal_iterations(2 ** n, len(marked))
    assert len(res["states"]) == len(ref)
    for got, want in zip(res["states"], ref):
        got = np.array([complex(a, b) for a, b in got])
        assert np.max(np.abs(got - want)) <= 1e-6
    assert res["numpy_crosscheck_ok"]
    assert res["resources"]["qpu_metrics"]["toffoli_count"] > 0


# --- propose (contract) --------------------------------------------------------------------------------
def _valid(plan):
    errs = [e.message for e in Draft202012Validator(SCHEMA).iter_errors(plan)]
    assert not errs, errs


def test_propose_numpy_fallback_validates(real_snapshot, tmp_path):
    out = tmp_path / "last_search.json"
    plan = propose(SITE_FIRM, real_snapshot, [], backend="numpy", out_path=out)
    _valid(plan)
    assert plan["search"]["method"] == "heuristic"           # numpy fallback is never labelled psiqdk
    assert abs(sum(s["mw"] for s in plan["splits"]) - SITE_FIRM["requested_mw"]) <= 0.01
    ids = {s["id"] for s in real_snapshot["substations"]}
    assert all(s["substation_id"] in ids for s in plan["splits"])
    rec = json.loads(out.read_text(encoding="utf-8"))
    assert rec["backend"] == "numpy-statevector-fallback" and rec["iterations"] == rec["iterations_expected"]
    assert plan["search"]["evals"] == rec["iterations"] * 32 + 32
    # Astra #9: the actual engine and the full cost (incl. oracle compilation) are recorded
    assert plan["search"]["engine"] == "numpy-fallback"
    assert plan["search"]["evals_total"] == plan["search"]["evals"] + plan["search"]["classical_enumeration_calls"]


def test_propose_auto_backend_labels_honestly(real_snapshot, tmp_path):
    out = tmp_path / "last_search.json"
    plan = propose(SITE, real_snapshot, [], out_path=out)
    _valid(plan)
    rec = json.loads(out.read_text(encoding="utf-8"))
    assert (plan["search"]["method"] == "psiqdk") == (rec["backend"] == "psiqdk")
    if psiqdk_available():
        assert plan["search"]["method"] == "psiqdk"


def test_propose_respects_constraints(real_snapshot, tmp_path):
    first = propose(SITE, real_snapshot, [], backend="numpy", out_path=tmp_path / "a.json")
    used = first["splits"][0]["substation_id"]
    second = propose(SITE, real_snapshot, [f"capacity: {used} split 75.0 MW > headroom 1.0 MW"],
                     backend="numpy", out_path=tmp_path / "b.json")
    _valid(second)
    assert used not in {s["substation_id"] for s in second["splits"]}
    assert abs(sum(s["mw"] for s in second["splits"]) - SITE["requested_mw"]) <= 0.01


def test_propose_widens_k_when_nothing_marked(tmp_path):
    snap = {**SYN, "substations": [_sub(1, 5, 1.0), _sub(2, 5, 2.0), _sub(3, 5, 3.0), _sub(4, 5, 4.0), _sub(5, 500, 9.0)]}
    plan = propose(SYN_SITE, snap, [], backend="numpy", out_path=tmp_path / "w.json")
    _valid(plan)
    assert [s["substation_id"] for s in plan["splits"]] == ["S5"]
    assert json.loads((tmp_path / "w.json").read_text())["oracle"]["widened"]


# --- baselines -----------------------------------------------------------------------------------------
def test_baselines_return_marked_plans(real_snapshot):
    sp = build_space(SITE_FIRM, real_snapshot)
    o = Oracle(sp, real_snapshot)
    for plan, evals in (random_search(sp, o, seed=3), heuristic_search(sp, o)):
        assert plan is not None and evals >= 1 and o(plan)
        _valid(sp.to_candidate_plan(plan, "random", evals))
    p1, _ = heuristic_search(sp, o)
    p2, _ = heuristic_search(sp, o, exclude={p1.index})
    assert p2.index != p1.index
