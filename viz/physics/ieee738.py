"""IEEE Std 738-2012 steady-state thermal rating of bare overhead conductors (SI units).

Implements the heat balance  qc + qr = qs + I^2 R(Tc)  of IEEE Std 738-2012,
"IEEE Standard for Calculating the Current-Temperature Relationship of Bare
Overhead Conductors" (https://standards.ieee.org/ieee/738/4997/, now superseded
by 738-2023; this module follows the 2012 equations on purpose because the
Annex B worked example used in test_ieee738.py comes from that edition).

Equation map (2012 clause numbers, SI forms):
    qc1  forced convection, low wind      eq (3a)  K_angle [1.01 + 1.35 N_Re^0.52] k_f (Ts - Ta)
    qc2  forced convection, high wind     eq (3b)  K_angle 0.754 N_Re^0.6 k_f (Ts - Ta)
    K_angle wind direction factor         eq (4a)  1.194 - cos(phi) + 0.194 cos(2 phi) + 0.368 sin(2 phi)
    N_Re Reynolds number                  eq (2c)  D0 rho_f V_w / mu_f
    qcn  natural convection               eq (5a)  3.645 rho_f^0.5 D0^0.75 (Ts - Ta)^1.25
    qr   radiated cooling                 eq (7a)  17.8 D0 eps [((Ts+273)/100)^4 - ((Ta+273)/100)^4]
    qs   solar heating                    eq (8)   alpha Q_se sin(theta) A'
    theta                                 eq (9)   arccos[cos(Hc) cos(Zc - Zl)]
    mu_f, rho_f, k_f air properties       eqs (13a), (14a), (15a)
    Hc solar altitude                     eq (16)  arcsin[cos(Lat) cos(delta) cos(omega) + sin(Lat) sin(delta)]
    delta declination                     eq (16b) 23.46 sin[(284 + N)/365 * 360]
    Zc solar azimuth                      eq (17)  C + arctan(chi), chi = sin(omega)/(sin(Lat)cos(omega) - cos(Lat)tan(delta))
    Q_s clear / industrial atmosphere     eq (18)  polynomial in Hc, Table 2 coefficients (SI)
    K_solar elevation correction          eq (20)  1 + 1.148e-4 He - 1.108e-8 He^2
    R(Tc) linear interpolation            eq (10)

Rules taken from the standard:
  * Forced convection uses the larger of qc1 and qc2; the convective loss used
    is the larger of forced and natural convection (2012 clause 4.4.3).
  * Air properties are evaluated at the film temperature Tfilm = (Ts + Ta)/2.
  * Time is LOCAL SOLAR TIME in the standard. A naive datetime is taken as local
    solar time (that is how the Annex example is specified). A timezone-aware
    datetime is converted to apparent solar time with the station longitude
    and the NOAA / Spencer (1971) equation of time (see _equation_of_time_min).

Measured irradiance: IEEE 738 has no input for measured irradiance. When a live
global-horizontal irradiance is supplied we scale the IEEE clear-sky flux by a
clearness ratio  k = GHI_measured / (Q_s(Hc) sin(Hc)),  clipped to [0, 1.2].
This scaling is OUR modelling choice (ASSUMED), not part of IEEE 738.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

# --------------------------------------------------------------------------------------
# Conductor data
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Conductor:
    name: str
    diameter_m: float            # outside diameter D0
    r_low_ohm_per_m: float       # AC resistance at t_low_c
    t_low_c: float
    r_high_ohm_per_m: float      # AC resistance at t_high_c
    t_high_c: float
    emissivity: float = 0.5
    absorptivity: float = 0.5
    sources: dict = field(default_factory=dict, compare=False)

    def resistance(self, tc_c: float) -> float:
        """IEEE 738-2012 eq (10): linear interpolation (and extrapolation) of R(Tc)."""
        slope = (self.r_high_ohm_per_m - self.r_low_ohm_per_m) / (self.t_high_c - self.t_low_c)
        return slope * (tc_c - self.t_low_c) + self.r_low_ohm_per_m


# Drake 795 kcmil 26/7 ACSR exactly as parameterised in the IEEE 738-2012 Annex B example.
# Corroborated (same D, R25, R75, eps, alpha) by Table I of Singh et al., "Sensitivity
# Analysis of Dynamic Line Rating for ACSR Conductors using IEEE-738", arXiv:2607.23536,
# which takes them from IEEE 738. Southwire lists the same conductor at OD 28.13 mm:
# https://www.southwire.com/wire-cable/bare-aluminum-overhead-transmission-distribution/acsr/p/10154308
DRAKE_IEEE738 = Conductor(
    name="Drake 795 kcmil 26/7 ACSR (IEEE 738-2012 Annex B parameters)",
    diameter_m=0.02814,
    r_low_ohm_per_m=7.283e-5,
    t_low_c=25.0,
    r_high_ohm_per_m=8.688e-5,
    t_high_c=75.0,
    emissivity=0.8,
    absorptivity=0.8,
    sources={
        "diameter_m": "IEEE 738-2012 Annex B; arXiv:2607.23536 Table I (0.02814 m); Southwire 10154308 (28.13 mm)",
        "r_low/high": "IEEE 738-2012 Annex B; arXiv:2607.23536 Table I (7.283e-5 @25C, 8.688e-5 @75C ohm/m)",
        "emissivity/absorptivity": "IEEE 738-2012 Annex B example values (0.8/0.8). Real weathered "
                                   "conductors vary 0.2-0.9; for a live rating these are ASSUMED.",
    },
)

# --------------------------------------------------------------------------------------
# Air properties (IEEE 738-2012 eqs 13a, 14a, 15a; SI)
# --------------------------------------------------------------------------------------


def air_viscosity(t_film_c: float) -> float:
    """Dynamic viscosity of air, kg/(m s). Eq (13a)."""
    return 1.458e-6 * (t_film_c + 273.0) ** 1.5 / (t_film_c + 383.4)


def air_density(t_film_c: float, elevation_m: float) -> float:
    """Air density, kg/m^3. Eq (14a)."""
    he = elevation_m
    return (1.293 - 1.525e-4 * he + 6.379e-9 * he ** 2) / (1.0 + 0.00367 * t_film_c)


def air_conductivity(t_film_c: float) -> float:
    """Thermal conductivity of air, W/(m C). Eq (15a)."""
    return 2.424e-2 + 7.477e-5 * t_film_c - 4.407e-9 * t_film_c ** 2


# --------------------------------------------------------------------------------------
# Convective cooling
# --------------------------------------------------------------------------------------


def k_angle(phi_deg: float) -> float:
    """Wind direction factor, eq (4a). phi = angle between wind and conductor AXIS (90 = perpendicular)."""
    phi = math.radians(phi_deg)
    return 1.194 - math.cos(phi) + 0.194 * math.cos(2 * phi) + 0.368 * math.sin(2 * phi)


def wind_angle_to_axis(wind_from_deg: float, line_azimuth_deg: float) -> float:
    """Acute angle (0..90 deg) between a meteorological wind direction and a line's axis.

    Meteorological direction (where wind blows FROM) and line azimuth are both measured
    clockwise from true north; the conductor axis is bidirectional, so fold to 0..90.
    """
    d = abs((wind_from_deg - line_azimuth_deg) % 180.0)
    return 180.0 - d if d > 90.0 else d


def convective_terms(conductor: Conductor, ts_c: float, ta_c: float, wind_ms: float,
                     wind_angle_deg: float, elevation_m: float) -> dict:
    """Return all convective intermediate quantities (W/m) for inspection and tests."""
    d0 = conductor.diameter_m
    t_film = 0.5 * (ts_c + ta_c)
    mu = air_viscosity(t_film)
    rho = air_density(t_film, elevation_m)
    kf = air_conductivity(t_film)
    dt = ts_c - ta_c
    n_re = d0 * rho * max(wind_ms, 0.0) / mu
    ka = k_angle(wind_angle_deg)
    qc1 = ka * (1.01 + 1.35 * n_re ** 0.52) * kf * dt
    qc2 = ka * 0.754 * n_re ** 0.6 * kf * dt
    qcn = 3.645 * rho ** 0.5 * d0 ** 0.75 * (abs(dt) ** 1.25) * (1 if dt >= 0 else -1)
    qc = max(qc1, qc2, qcn) if dt >= 0 else min(qc1, qc2, qcn)
    return dict(t_film=t_film, mu_f=mu, rho_f=rho, k_f=kf, n_re=n_re, k_angle=ka,
                qc1=qc1, qc2=qc2, qcn=qcn, qc=qc)


def convective_cooling(conductor: Conductor, ts_c: float, ta_c: float, wind_ms: float,
                       wind_angle_deg: float = 90.0, elevation_m: float = 0.0) -> float:
    return convective_terms(conductor, ts_c, ta_c, wind_ms, wind_angle_deg, elevation_m)["qc"]


# --------------------------------------------------------------------------------------
# Radiated cooling
# --------------------------------------------------------------------------------------


def radiated_cooling(conductor: Conductor, ts_c: float, ta_c: float) -> float:
    """Eq (7a), W/m."""
    return 17.8 * conductor.diameter_m * conductor.emissivity * (
        ((ts_c + 273.0) / 100.0) ** 4 - ((ta_c + 273.0) / 100.0) ** 4)


# --------------------------------------------------------------------------------------
# Solar geometry and heating
# --------------------------------------------------------------------------------------

# IEEE 738-2012 Table 2 (SI): total heat flux Qs (W/m^2) vs solar altitude Hc (deg)
_QS_CLEAR = (-42.2391, 63.8044, -1.9220, 3.46921e-2, -3.61118e-4, 1.94318e-6, -4.07608e-9)
_QS_INDUSTRIAL = (53.1821, 14.2110, 6.6138e-1, -3.1658e-2, 5.4654e-4, -4.3446e-6, 1.3236e-8)


def _equation_of_time_min(day_of_year: int) -> float:
    """Equation of time (minutes), Spencer (1971) as used by NOAA
    (https://gml.noaa.gov/grad/solcalc/solareqns.PDF). Not part of IEEE 738."""
    g = 2 * math.pi / 365.0 * (day_of_year - 1)
    return 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g)
                     - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))


def solar_time_hours(dt: datetime, longitude_deg: Optional[float]) -> tuple[int, float]:
    """(day_of_year, local apparent solar time in hours).

    Naive datetime -> already local solar time (IEEE convention).
    Aware datetime -> converted from UTC using longitude (east positive) + equation of time.
    """
    if dt.tzinfo is None:
        return dt.timetuple().tm_yday, dt.hour + dt.minute / 60.0 + dt.second / 3600.0
    if longitude_deg is None:
        raise ValueError("longitude_deg is required for a timezone-aware datetime")
    u = dt.astimezone(timezone.utc)
    n = u.timetuple().tm_yday
    utc_h = u.hour + u.minute / 60.0 + (u.second + u.microsecond * 1e-6) / 3600.0
    t = utc_h + longitude_deg / 15.0 + _equation_of_time_min(n) / 60.0
    if t < 0:  # crossed midnight backwards: use previous day's declination (negligible change)
        t += 24.0
        n = max(1, n - 1)
    elif t >= 24:
        t -= 24.0
        n = min(366, n + 1)
    return n, t


def solar_position(lat_deg: float, day_of_year: int, solar_hour: float) -> dict:
    """Solar altitude Hc and azimuth Zc (deg, clockwise from north), eqs (16)-(17)."""
    lat = math.radians(lat_deg)
    delta_deg = 23.46 * math.sin(math.radians((284 + day_of_year) / 365.0 * 360.0))
    delta = math.radians(delta_deg)
    omega_deg = (solar_hour - 12.0) * 15.0
    omega = math.radians(omega_deg)
    sin_hc = math.cos(lat) * math.cos(delta) * math.cos(omega) + math.sin(lat) * math.sin(delta)
    hc_deg = math.degrees(math.asin(max(-1.0, min(1.0, sin_hc))))
    denom = math.sin(lat) * math.cos(omega) - math.cos(lat) * math.tan(delta)
    chi = math.sin(omega) / denom if denom != 0 else math.copysign(float("inf"), math.sin(omega) or 1.0)
    # Table 3 of 738-2012: solar azimuth constant C
    if -180.0 <= omega_deg < 0.0:
        c = 0.0 if chi >= 0 else 180.0
    else:
        c = 180.0 if chi >= 0 else 360.0
    zc_deg = c + math.degrees(math.atan(chi))
    return dict(delta_deg=delta_deg, omega_deg=omega_deg, chi=chi, hc_deg=hc_deg, zc_deg=zc_deg % 360.0)


def solar_flux_qs(hc_deg: float, atmosphere: str = "clear") -> float:
    """Eq (18): total solar + sky radiated heat flux Qs (W/m^2) at sea level."""
    if hc_deg <= 0:
        return 0.0
    coeffs = _QS_CLEAR if atmosphere == "clear" else _QS_INDUSTRIAL
    return max(0.0, sum(c * hc_deg ** i for i, c in enumerate(coeffs)))


def k_solar(elevation_m: float) -> float:
    """Eq (20): elevation correction for solar flux."""
    return 1.0 + 1.148e-4 * elevation_m - 1.108e-8 * elevation_m ** 2


def solar_terms(conductor: Conductor, lat_deg: float, elevation_m: float, when: datetime,
                line_azimuth_deg: float, longitude_deg: Optional[float] = None,
                atmosphere: str = "clear", measured_ghi_wm2: Optional[float] = None) -> dict:
    n, hour = solar_time_hours(when, longitude_deg)
    pos = solar_position(lat_deg, n, hour)
    hc, zc = pos["hc_deg"], pos["zc_deg"]
    qs_flux = solar_flux_qs(hc, atmosphere)
    qse = k_solar(elevation_m) * qs_flux
    clearness = None
    if measured_ghi_wm2 is not None and hc > 0 and qse > 0:
        clear_horizontal = qse * math.sin(math.radians(hc))
        clearness = max(0.0, min(1.2, measured_ghi_wm2 / clear_horizontal))  # ASSUMED scaling
        qse *= clearness
    elif measured_ghi_wm2 is not None and hc <= 0:
        clearness = 0.0
    theta = math.degrees(math.acos(max(-1.0, min(1.0,
                         math.cos(math.radians(hc)) * math.cos(math.radians(zc - line_azimuth_deg))))))
    qs = conductor.absorptivity * qse * math.sin(math.radians(theta)) * conductor.diameter_m if hc > 0 else 0.0
    return dict(day_of_year=n, solar_hour=hour, **pos, qs_flux=qs_flux, qse=qse, theta_deg=theta,
                clearness=clearness, qs=qs)


def solar_heating(conductor: Conductor, lat_deg: float, elevation_m: float, when: datetime,
                  line_azimuth_deg: float, **kw) -> float:
    return solar_terms(conductor, lat_deg, elevation_m, when, line_azimuth_deg, **kw)["qs"]


# --------------------------------------------------------------------------------------
# Heat balance: ampacity and conductor temperature
# --------------------------------------------------------------------------------------


def heat_balance(conductor: Conductor, ts_c: float, ambient_c: float, wind_ms: float,
                 wind_angle_deg: float, lat: float, elevation_m: float, when: datetime,
                 line_azimuth_deg: float, **solar_kw) -> dict:
    conv = convective_terms(conductor, ts_c, ambient_c, wind_ms, wind_angle_deg, elevation_m)
    qr = radiated_cooling(conductor, ts_c, ambient_c)
    sol = solar_terms(conductor, lat, elevation_m, when, line_azimuth_deg, **solar_kw)
    return dict(convection=conv, qc=conv["qc"], qr=qr, solar=sol, qs=sol["qs"],
                r_ohm_per_m=conductor.resistance(ts_c))


def steady_state_ampacity(conductor: Conductor, T_max_c: float, ambient_c: float, wind_ms: float,
                          wind_angle_deg: float, lat: float, elevation_m: float, datetime: datetime,
                          line_azimuth_deg: float, detail: bool = False, **solar_kw):
    """Steady-state thermal rating (A) at maximum allowable conductor temperature T_max_c.

    I = sqrt((qc + qr - qs) / R(Tmax)), IEEE 738-2012 eq (1b).
    solar_kw: longitude_deg (needed for aware datetimes), atmosphere ('clear'|'industrial'),
              measured_ghi_wm2 (live irradiance; see module note, ASSUMED scaling).
    """
    hb = heat_balance(conductor, T_max_c, ambient_c, wind_ms, wind_angle_deg, lat, elevation_m,
                      datetime, line_azimuth_deg, **solar_kw)
    net = hb["qc"] + hb["qr"] - hb["qs"]
    amps = math.sqrt(net / hb["r_ohm_per_m"]) if net > 0 else 0.0
    if detail:
        hb["ampacity_a"] = amps
        return hb
    return amps


def conductor_temperature(current_a: float, conductor: Conductor, ambient_c: float, wind_ms: float,
                          wind_angle_deg: float, lat: float, elevation_m: float, datetime: datetime,
                          line_azimuth_deg: float, t_hi_c: float = 400.0, tol_c: float = 1e-4,
                          **solar_kw) -> float:
    """Steady-state conductor temperature (C) carrying current_a, by bisection on the heat balance.

    f(Ts) = qc(Ts) + qr(Ts) - qs - I^2 R(Ts) is increasing in Ts over the physical range
    (cooling grows like (Ts-Ta)^1.25..^4, Joule heating only linearly through R(Ts)), so
    bisection on [Ta - 20, t_hi_c] is robust. With qs >= 0 and I >= 0 the root is >= Ta;
    the lower bracket only guards rounding.
    """
    qs = solar_heating(conductor, lat, elevation_m, datetime, line_azimuth_deg, **solar_kw)

    def f(ts):
        qc = convective_cooling(conductor, ts, ambient_c, wind_ms, wind_angle_deg, elevation_m)
        return qc + radiated_cooling(conductor, ts, ambient_c) - qs - current_a ** 2 * conductor.resistance(ts)

    lo, hi = ambient_c - 20.0, t_hi_c
    if f(hi) < 0:
        raise ValueError(f"no steady state below {t_hi_c} C for {current_a} A (thermal runaway / out of range)")
    if f(lo) > 0:
        return lo
    while hi - lo > tol_c:
        mid = 0.5 * (lo + hi)
        if f(mid) > 0:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)
