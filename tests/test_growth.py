import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scenarios.growth_alviso import run  # noqa: E402


def test_baseline_reproduces_grip_and_flex_curve():
    base = run()["scenarios"]["baseline_grip_2028"]["by_curtailment_pct"]
    assert abs(base["0"]["distribution_mw"] - 38.8) < 0.5
    for pct, mw in {"2": 47.6, "5": 66.2, "10": 90.6}.items():
        assert abs(base[pct]["distribution_mw"] - mw) < 0.5


def test_stress_is_strictly_lower_and_adds_zero_banks():
    sc = run()["scenarios"]
    for pct, b in sc["baseline_grip_2028"]["by_curtailment_pct"].items():
        s = sc["stress_plus20pct_assumed"]["by_curtailment_pct"][pct]
        assert s["distribution_mw"] < b["distribution_mw"]
        assert set(b["banks_at_zero"]) <= set(s["banks_at_zero"])
