import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["QSITE_OFFLINE"] = "1"


def test_edge_case_red_on_bank_rule_then_green(tmp_path):
    from scenarios.edge_alviso import run
    out = run(mw=16.0, rounds=20, out_root=tmp_path)
    rounds = out["rounds"]
    # round 1: feeder-level view passes Hannah's certificate but the transformer-bank rule makes it RED
    assert rounds[0]["verdict"] == "RED" and not rounds[0]["bank_rule"]["pass"]
    # the loop converges to a plan that passes every bank cap
    assert out["final"] is not None and out["final"]["verdict"] in {"GREEN", "AMBER"}
    assert out["final"]["bank_rule"]["pass"]
    assert abs(sum(mw for _, mw in out["final"]["edge_sites"]) - 16.0) < 0.01
    assert (tmp_path / next(p.name for p in tmp_path.iterdir()) / "edge_alviso.json").exists()
