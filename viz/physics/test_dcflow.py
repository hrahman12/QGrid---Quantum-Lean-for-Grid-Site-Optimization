"""3-bus DC power flow, hand-solved.

Buses 1 (slack), 2, 3; lines 1-2, 1-3, 2-3 each x = 0.1 pu on 100 MVA; loads 100 MW at
bus 2 and 50 MW at bus 3.
  Reduced B' (buses 2,3) = [[20, -10], [-10, 20]],  P = [-1.0, -0.5] pu
  inverse = (1/300) [[20, 10], [10, 20]]
  theta2 = -25/300 = -0.08333 rad, theta3 = -20/300 = -0.06667 rad
  f12 = 83.33 MW, f13 = 66.67 MW, f23 = -16.67 MW (16.67 MW flows 3 -> 2)
N-1 (ratings 120 MW):
  trip 1-2: f13 = 150, f23 = -100 -> max loading 1.25
  trip 1-3: f12 = 150, f23 = +50  -> 1.25
  trip 2-3: f12 = 100, f13 = 50   -> 0.833
"""
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(__file__))
import dcflow as m  # noqa: E402


def net3(rating=120.0):
    br = [m.Branch("1-2", 0, 1, 0.1, rating), m.Branch("1-3", 0, 2, 0.1, rating),
          m.Branch("2-3", 1, 2, 0.1, rating)]
    return m.Network(["1", "2", "3"], br, slack=0)


INJ = [0.0, -100.0, -50.0]


def test_base_case():
    r = m.dc_power_flow(net3(), INJ)
    assert np.radians(r["theta_deg"]) == pytest.approx([0, -25 / 300, -20 / 300])
    assert r["flow_mw"] == pytest.approx([250 / 3, 200 / 3, -50 / 3])
    assert r["slack_mw"] == pytest.approx(150.0)


def test_n_minus_1():
    res = m.n_minus_1(net3(), INJ)
    by = {c["outage"]: c for c in res["cases"]}
    assert by["1-2"]["flow_mw"] == pytest.approx([0, 150, -100])
    assert by["1-3"]["flow_mw"] == pytest.approx([150, 0, 50])
    assert by["2-3"]["flow_mw"] == pytest.approx([100, 50, 0])
    assert res["max_loading"] == pytest.approx(1.25)
    assert res["secure"] is False
    assert m.n_minus_1(net3(rating=160.0), INJ)["secure"] is True


def test_lodf_reproduces_outages():
    n = net3()
    base = m.dc_power_flow(n, INJ)["flow_mw"]
    L = m.lodf(n)
    for k, c in enumerate(m.n_minus_1(n, INJ)["cases"]):
        predicted = base + L[:, k] * base[k]
        assert predicted == pytest.approx(c["flow_mw"], abs=1e-9)


def test_radial_outage_islands():
    br = [m.Branch("1-2", 0, 1, 0.1, 200), m.Branch("2-3", 1, 2, 0.1, 200)]
    res = m.n_minus_1(m.Network(["1", "2", "3"], br), [0, -50, -30])
    assert all(c["islanded"] for c in res["cases"])
    assert res["cases"][1]["stranded_buses"] == ["3"]
    assert math.isinf(res["max_loading"])


def test_reactance_geometry():
    # hand: 115 kV, 4 m flat -> GMD 5.0397 m; GMR 11.43 mm; ln(440.92) = 6.0889
    # X = 2*pi*60*2e-7 * 6.0889 * 1000 = 0.4591 ohm/km
    assert m.typical_reactance_ohm_per_km(115) == pytest.approx(0.4591, abs=2e-4)
    for kv in (60, 115, 230):
        assert 0.35 < m.typical_reactance_ohm_per_km(kv) < 0.55
    # 2-bundle lowers reactance
    assert m.reactance_ohm_per_km(7.0, m.DRAKE_GMR_M, 2, 0.457) < m.typical_reactance_ohm_per_km(230)
    # per-unit: 10 km at 115 kV, Zbase = 132.25 ohm
    assert m.x_pu(10, 115) == pytest.approx(4.591 / 132.25, rel=1e-3)
