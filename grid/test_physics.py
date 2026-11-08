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


def test_distribution_edge_sites_respect_bank_headroom():
    from grid.distribution import edge_sites
    grip = {"substations": [{"id": "S1", "name": "S ONE", "lat": 0, "lon": 0, "headroom_mw": 12.0, "feeders": [
        {"feeder_id": "f1", "name": "F1", "max_load_hosting_mw": 14.3}, {"feeder_id": "f2", "name": "F2", "max_load_hosting_mw": 5.0},
        {"feeder_id": "f3", "name": "F3", "max_load_hosting_mw": 0.2}, {"feeder_id": "f4", "name": "F4", "max_load_hosting_mw": None}]}]}
    r = edge_sites(grip, 150)
    assert [s["mw"] for s in r["edge_sites"]] == [10.0, 2.0]  # 10 MW cap, then what is left of the 12 MW bank headroom
    assert r["connectable_at_distribution_mw"] == 12.0 and r["needs_transmission_mw"] == 138.0
