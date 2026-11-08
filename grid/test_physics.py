import json
from pathlib import Path

from grid.physics import check

FIX = Path(__file__).resolve().parents[1] / "fixtures"
SNAP = json.loads((FIX / "grid_snapshot.json").read_text(encoding="utf-8"))
NO_FLEX = {"dlr": False, "storage_mw": 0, "curtailment_mw": 0, "reconductor": False}


def plan(splits, flex=NO_FLEX):
    return {"splits": [{"substation_id": k, "mw": v} for k, v in splits.items()], "flex": flex,
            "search": {"method": "heuristic", "evals": 1}}


def test_balanced_split_passes():
    r = check(plan({"SUB-A": 60, "SUB-B": 50, "SUB-C": 40}), SNAP)
    assert r["converged"] and r["n1_pass"] and r["violations"] == []
    assert 0 < r["max_line_loading_pct"] <= 100 and 0.95 <= r["v_min_pu"] <= r["v_max_pu"] <= 1.05


def test_overloaded_single_substation_fails_with_reason():
    r = check(plan({"SUB-A": 150}), SNAP)
    assert r["converged"] and not r["n1_pass"]
    assert r["max_line_loading_pct"] > 100
    assert any("XF-SUB-A" in v and "> 100%" in v for v in r["violations"])


def test_flex_relieves_the_same_plan():
    heavy = {"SUB-A": 150}
    base = check(plan(heavy), SNAP)["max_line_loading_pct"]
    flex = {"dlr": True, "storage_mw": 30, "curtailment_mw": 20, "reconductor": False}
    assert check(plan(heavy, flex), SNAP)["max_line_loading_pct"] < base


def test_unknown_substation_is_reported_not_raised():
    r = check(plan({"NOPE": 10}), SNAP)
    assert not r["converged"] and "unknown substation NOPE" in r["violations"][0]


def test_75mw_on_19_9mw_firm_substation_fails_n1():
    snap = {**SNAP, "substations": [{**s, "headroom_mw_n1_firm": 19.9} if s["id"] == "SUB-A" else s for s in SNAP["substations"]]}
    r = check(plan({"SUB-A": 75}), snap)
    assert r["converged"] and not r["n1_pass"]
    assert any("XF-SUB-A largest bank out" in v and "75.0 MW > firm headroom 19.9 MW" in v for v in r["violations"])
    assert check(plan({"SUB-A": 75}), SNAP)["n1_pass"]  # same plan without firm data: only lines are outaged


def test_distribution_edge_sites_respect_bank_headroom():
    from grid.distribution import edge_sites
    grip = {"substations": [{"id": "S1", "name": "S ONE", "lat": 0, "lon": 0, "headroom_mw": 12.0, "banks": [{"id": "B1", "headroom_mw": 12.0}],
                             "feeders": [
        {"feeder_id": "f1", "name": "F1", "max_load_hosting_mw": 14.3}, {"feeder_id": "f2", "name": "F2", "max_load_hosting_mw": 5.0},
        {"feeder_id": "f3", "name": "F3", "max_load_hosting_mw": 0.2}, {"feeder_id": "f4", "name": "F4", "max_load_hosting_mw": None}]}]}
    r = edge_sites(grip, 150)  # single bank: feeders default to it
    assert [s["mw"] for s in r["edge_sites"]] == [10.0, 2.0]  # 10 MW cap, then what is left of the 12 MW bank headroom
    assert r["connectable_at_distribution_mw"] == 12.0 and r["needs_transmission_mw"] == 138.0


def test_edge_sites_never_pool_headroom_across_banks():
    from grid.distribution import edge_sites
    grip = {"substations": [{"id": "S", "name": "S", "lat": 0, "lon": 0, "headroom_mw": 9.0,
                             "banks": [{"id": "FULL", "headroom_mw": 0}, {"id": "SPARE", "headroom_mw": 9.0}, {"id": "NOFC", "headroom_mw": None}],
                             "feeders": [{"feeder_id": "a", "name": "A", "max_load_hosting_mw": 8.5},
                                         {"feeder_id": "b", "name": "B", "max_load_hosting_mw": 6.0},
                                         {"feeder_id": "c", "name": "C", "max_load_hosting_mw": 7.0},
                                         {"feeder_id": "d", "name": "D", "max_load_hosting_mw": 9.0}]}]}
    r = edge_sites(grip, 150, {"a": "FULL", "b": "SPARE", "c": "NOFC"})  # d: unknown bank
    assert [(s["feeder_id"], s["mw"]) for s in r["edge_sites"]] == [("b", 6.0)]


def test_real_grip_edge_sites_within_every_bank_cap():
    from collections import Counter

    import pytest

    from grid.distribution import edge_sites, load_bank_map, load_grip
    grip = load_grip()
    if grip is None:
        pytest.skip("no GRIP cache")
    r = edge_sites(grip, 150, load_bank_map())
    cap = {b["id"]: b.get("headroom_mw") or 0.0 for s in grip["substations"] for b in s.get("banks", [])}
    used = Counter()
    for s in r["edge_sites"]:
        assert 0.5 <= s["mw"] <= 10.0
        used[s["bank_id"]] += s["mw"]
    assert all(mw <= cap[b] + 1e-6 for b, mw in used.items()), {b: (mw, cap[b]) for b, mw in used.items() if mw > cap[b]}
