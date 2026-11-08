"""Hand-computed checks for sag.py.

Case: level 300 m span, Drake (w = 1.627 kg/m x 9.80665 = 15.9554 N/m), H = 28 000 N.
  a   = H / w             = 1754.89 m
  S/2a = 150 / 1754.89    = 0.085476
  cosh(0.085476) = 1 + u^2/2 + u^4/24 = 1.0036553     (series, u^4 term 2.2e-6)
  sag = a (cosh - 1)      = 6.4147 m
  parabolic w S^2 / 8H    = 15.9554 * 90000 / 224000 = 6.4106 m
  arc length 2a sinh(S/2a) = S (1 + u^2/6 + ...) = 300 * 1.0012178 = 300.3653 m
"""
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(__file__))
import sag as m  # noqa: E402

W = 1.627 * 9.80665
H = 28000.0
S = 300.0


def test_hand_case_level_span():
    assert W == pytest.approx(15.9554, rel=1e-5)
    assert m.sag(S, H, W) == pytest.approx(6.4147, abs=2e-3)
    assert m.sag_parabolic(S, H, W) == pytest.approx(6.4106, abs=2e-3)
    assert m.arc_length(S, H, W) == pytest.approx(300.3653, abs=2e-3)


def test_drake_composite_properties():
    c = m.DRAKE_MECH
    assert c.area_m2 * 1e6 == pytest.approx(468.5, abs=1.0)
    assert c.modulus_pa / 1e9 == pytest.approx(73.9, abs=0.5)
    assert c.alpha_per_c == pytest.approx(18.9e-6, abs=0.1e-6)
    assert c.rts_n / 1e3 == pytest.approx(140.1, abs=0.1)


def test_state_change_identity_and_monotonic():
    c = m.DRAKE_MECH
    assert m.tension_at_temperature(S, c, H, 15.0, 15.0) == pytest.approx(H, rel=1e-8)
    sags = [m.sag_at_temperature(S, c, H, 15.0, t)["sag_m"] for t in (0, 15, 50, 75, 100)]
    assert all(b > a for a, b in zip(sags, sags[1:]))


def test_catenary_state_change_matches_parabolic_cubic():
    c = m.DRAKE_MECH
    for t in (-10.0, 50.0, 100.0):
        h_cat = m.tension_at_temperature(S, c, H, 15.0, t)
        h_par = m.tension_cubic_parabolic(S, c, H, 15.0, t)
        assert h_cat == pytest.approx(h_par, rel=5e-3)


def test_hand_thermal_sag_increment():
    # Inextensible-limit check (EA -> inf): dL = L alpha dT, and for a parabola
    # L = S + 8 D^2 / (3 S)  =>  D2 = sqrt(D1^2 + 3 S dL / 8).
    c = m.DRAKE_MECH
    stiff = m.ConductorMech("stiff", c.weight_n_per_m, c.area_m2, 1e16, c.alpha_per_c, c.rts_n, c.diameter_m)
    d1 = m.sag_parabolic(S, H, W)
    dl = (S + 8 * d1 ** 2 / (3 * S)) * c.alpha_per_c * 60.0
    d2_hand = math.sqrt(d1 ** 2 + 3 * S * dl / 8)
    d2 = m.sag_at_temperature(S, stiff, H, 15.0, 75.0)["sag_m"]
    assert d2 == pytest.approx(d2_hand, rel=5e-3)


def test_ruling_span():
    assert m.ruling_span([300, 300, 300]) == pytest.approx(300)
    assert m.ruling_span([200, 400]) == pytest.approx(math.sqrt((200 ** 3 + 400 ** 3) / 600))


def test_3d_points_level_and_inclined():
    r = m.catenary_points_3d((0, 0, 30), (300, 0, 30), H, W, n=101)
    p = r["points"]
    assert p[0] == pytest.approx([0, 0, 30])
    assert p[-1] == pytest.approx([300, 0, 30])
    assert r["sag_m"] == pytest.approx(m.sag(S, H, W), rel=1e-9)
    assert 30 - p[:, 2].min() == pytest.approx(m.sag(S, H, W), rel=1e-6)

    # Inclined, diagonal in plan: 300 m horizontal at 45 deg, B 12 m higher
    d = 300 / math.sqrt(2)
    r2 = m.catenary_points_3d((0, 0, 30), (d, d, 42), H, W, n=201)
    q = r2["points"]
    assert q[0] == pytest.approx([0, 0, 30])
    assert q[-1] == pytest.approx([d, d, 42], abs=1e-9)
    # For a parabola, sag of an inclined span measured vertically from the chord equals the
    # level-span sag w S^2 / 8H; the catenary differs by O(h^2/S^2).
    assert r2["sag_m"] == pytest.approx(m.sag_parabolic(S, H, W), rel=5e-3)
    # arc length identity
    seg = np.linalg.norm(np.diff(q, axis=0), axis=1).sum()
    assert seg == pytest.approx(r2["arc_length_m"], rel=1e-4)
