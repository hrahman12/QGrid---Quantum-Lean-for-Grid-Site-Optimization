"""IEEE Std 738-2012 Annex B worked example (Drake 795 kcmil 26/7 ACSR, SI units).

INPUTS (IEEE 738-2012 Annex B; the conductor block is corroborated by Table I of
Singh et al., arXiv:2607.23536, "Sensitivity Analysis of Dynamic Line Rating for ACSR
Conductors using IEEE-738", which takes them from IEEE 738):
    D0 = 28.14 mm, R(25 C) = 7.283e-5 ohm/m, R(75 C) = 8.688e-5 ohm/m,
    emissivity = 0.8, absorptivity = 0.8, Tmax = 100 C,
    Ta = 40 C, Vw = 0.61 m/s perpendicular to the conductor, elevation 0 m,
    latitude 30 N, line azimuth 90 deg (east-west), June 10 (day 161),
    11:00 local solar time, clear atmosphere.

PUBLISHED REFERENCE RESULTS we test against (IEEE 738-2012 Annex B). The standard is
paywalled (https://standards.ieee.org/ieee/738/4997/) and could not be fetched in this
session, so these are RECALLED values from the standard's worked example, not copied
from a downloaded page. They are mutually consistent: sqrt((81.93 + 39.1 - 22.44)/9.390e-5)
= 1024.7 A, which is the published 1025 A.
    Tfilm = 70 C, mu_f = 2.043e-5, rho_f = 1.029, k_f = 0.02945, N_Re ~ 865
    qc1 = 81.93 W/m, qc2 = 77.06 W/m, qcn = 42.4 W/m  -> qc = 81.93 W/m
    qr  = 39.1 W/m
    Hc ~ 74.9 deg, Zc ~ 114 deg, Qs ~ 1027 W/m^2, qs = 22.44 W/m
    R(100 C) = 9.390e-5 ohm/m
    I = 1025 A
Tolerances: 1% on each heat term (published D0 rounding 28.1 vs 28.14 mm moves qc by ~0.2%),
1% on ampacity.
"""
import math
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(__file__))
import ieee738 as m  # noqa: E402

WHEN = datetime(2011, 6, 10, 11, 0)  # naive -> local solar time, as in the standard
ARGS = dict(T_max_c=100.0, ambient_c=40.0, wind_ms=0.61, wind_angle_deg=90.0, lat=30.0,
            elevation_m=0.0, datetime=WHEN, line_azimuth_deg=90.0)


@pytest.fixture(scope="module")
def hb():
    return m.steady_state_ampacity(m.DRAKE_IEEE738, detail=True, **ARGS)


def test_air_properties(hb):
    c = hb["convection"]
    assert c["t_film"] == pytest.approx(70.0)
    assert c["mu_f"] == pytest.approx(2.043e-5, rel=1e-3)
    assert c["rho_f"] == pytest.approx(1.029, rel=1e-3)
    assert c["k_f"] == pytest.approx(0.02945, rel=1e-3)
    assert c["n_re"] == pytest.approx(865, rel=0.01)


def test_convection(hb):
    c = hb["convection"]
    assert c["qc1"] == pytest.approx(81.93, rel=0.01)
    assert c["qc2"] == pytest.approx(77.06, rel=0.01)
    assert c["qcn"] == pytest.approx(42.4, rel=0.01)
    assert hb["qc"] == c["qc1"]  # low-wind formula governs, as in the standard


def test_radiation(hb):
    assert hb["qr"] == pytest.approx(39.1, rel=0.01)


def test_solar(hb):
    s = hb["solar"]
    assert s["hc_deg"] == pytest.approx(74.9, abs=0.3)
    assert s["zc_deg"] == pytest.approx(114.0, abs=0.5)
    assert s["qs_flux"] == pytest.approx(1027, rel=0.01)
    assert hb["qs"] == pytest.approx(22.44, rel=0.01)


def test_resistance_and_ampacity(hb):
    assert hb["r_ohm_per_m"] == pytest.approx(9.390e-5, rel=1e-3)
    assert hb["ampacity_a"] == pytest.approx(1025, rel=0.01)


def test_temperature_inverts_ampacity():
    amps = m.steady_state_ampacity(m.DRAKE_IEEE738, **ARGS)
    a = dict(ARGS)
    a.pop("T_max_c")
    tc = m.conductor_temperature(amps, m.DRAKE_IEEE738, **a)
    assert tc == pytest.approx(100.0, abs=0.01)


def test_physical_monotonicity():
    base = m.steady_state_ampacity(m.DRAKE_IEEE738, **ARGS)
    more_wind = m.steady_state_ampacity(m.DRAKE_IEEE738, **{**ARGS, "wind_ms": 2.0})
    parallel = m.steady_state_ampacity(m.DRAKE_IEEE738, **{**ARGS, "wind_angle_deg": 0.0})
    hotter = m.steady_state_ampacity(m.DRAKE_IEEE738, **{**ARGS, "ambient_c": 45.0})
    night = m.steady_state_ampacity(m.DRAKE_IEEE738, **{**ARGS, "datetime": datetime(2011, 6, 10, 23, 0)})
    assert more_wind > base > parallel
    assert hotter < base < night


def test_k_angle_and_wind_fold():
    assert m.k_angle(90) == pytest.approx(1.0, abs=1e-3)
    assert m.k_angle(0) == pytest.approx(0.388, abs=1e-3)
    assert m.wind_angle_to_axis(0, 90) == pytest.approx(90)
    assert m.wind_angle_to_axis(270, 90) == pytest.approx(0)
    assert m.wind_angle_to_axis(315, 0) == pytest.approx(45)


def test_aware_datetime_matches_solar_time():
    # Longitude 0, equation of time removed -> UTC clock time = solar time + EoT.
    n = 161
    eot_h = m._equation_of_time_min(n) / 60.0
    utc = datetime(2011, 6, 10, 11, 0, tzinfo=timezone.utc) - timedelta(hours=eot_h)
    day, hour = m.solar_time_hours(utc, longitude_deg=0.0)
    assert day == n and hour == pytest.approx(11.0, abs=1e-6)
