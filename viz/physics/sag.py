"""Catenary sag, ruling-span change of state, and 3D conductor geometry.

Physics (textbook; e.g. CIGRE TB 324 "Sag-tension calculation methods for overhead
lines" (2007) and the Southwire Overhead Conductor Manual):

  Catenary, horizontal tension H (N), weight per length w (N/m), parameter a = H/w:
      y(x) = a [cosh((x - x0)/a) - cosh(x0/a)]           (y(0) = 0)
  Level span S:  sag D = a (cosh(S/2a) - 1),  arc length L = 2a sinh(S/2a)
  Inclined span (height difference h between attachments):
      x0 = S/2 - a asinh( h / (2a sinh(S/2a)) )          (position of the lowest point)
      L  = sqrt( (2a sinh(S/2a))^2 + h^2 )
      sag (max vertical chord-to-curve gap) at sinh((x*-x0)/a) = h/S

  Ruling span (equivalent span of a tension section with suspension insulators):
      RS = sqrt( sum S_i^3 / sum S_i )

  Linear change of state (elastic + thermal, no creep, no aluminium "knee point"):
      L(H, T) = L_ref * (1 + alpha (T - T_ref)) * (1 + (H - H_ref)/(E A))
  solved against the catenary length L_geo(H) = 2(H/w) sinh(wS/2H) for H at the new T.
  Using horizontal tension in the elastic term (instead of the average tension) is the
  usual small-sag approximation; it is < 0.1 % for sag/span < 3 %.

Conductor mechanical data are tagged SOURCED or ASSUMED in DRAKE_MECH below.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Sequence

import numpy as np

G = 9.80665  # m/s^2, standard gravity (CGPM 1901)


@dataclass(frozen=True)
class ConductorMech:
    name: str
    weight_n_per_m: float
    area_m2: float
    modulus_pa: float        # final composite modulus E
    alpha_per_c: float       # composite linear thermal expansion
    rts_n: float             # rated tensile strength
    diameter_m: float
    sources: dict = field(default_factory=dict, compare=False)

    @property
    def ea(self) -> float:
        return self.modulus_pa * self.area_m2


def composite_acsr(a_al_m2: float, a_st_m2: float, e_al: float, e_st: float,
                   alpha_al: float, alpha_st: float) -> tuple[float, float]:
    """Rule of mixtures for a bimetallic stranded conductor -> (E, alpha) of the composite."""
    ea = e_al * a_al_m2 + e_st * a_st_m2
    e = ea / (a_al_m2 + a_st_m2)
    alpha = (alpha_al * e_al * a_al_m2 + alpha_st * e_st * a_st_m2) / ea
    return e, alpha


# --- Drake 795 kcmil 26/7 ACSR ------------------------------------------------------------
_D_AL = 4.442e-3   # 0.1749 in aluminium strand; ASTM B232 Drake construction (recalled; see sources)
_D_ST = 3.454e-3   # 0.1360 in steel strand
_A_AL = 26 * math.pi / 4 * _D_AL ** 2   # = 402.9 mm^2 (795 kcmil = 402.8 mm^2 by definition)
_A_ST = 7 * math.pi / 4 * _D_ST ** 2    # = 65.6 mm^2
_E_AL, _E_ST = 55e9, 190e9              # ASSUMED stranded final moduli
_ALPHA_AL, _ALPHA_ST = 23.0e-6, 11.5e-6  # ASSUMED (handbook values for 1350 Al and galvanised steel)
_E_DRAKE, _ALPHA_DRAKE = composite_acsr(_A_AL, _A_ST, _E_AL, _E_ST, _ALPHA_AL, _ALPHA_ST)

DRAKE_MECH = ConductorMech(
    name="Drake 795 kcmil 26/7 ACSR",
    weight_n_per_m=1.627 * G,           # 1627 kg/km
    area_m2=_A_AL + _A_ST,
    modulus_pa=_E_DRAKE,                # ~73.9 GPa
    alpha_per_c=_ALPHA_DRAKE,           # ~18.9e-6 /C
    rts_n=31500 * 4.4482216,            # 31,500 lbf = 140.1 kN
    diameter_m=0.02813,
    sources={
        "weight_n_per_m": "SOURCED: Southwire 795-26/7 ACSR Drake, 1627 kg/km, "
                          "https://www.southwire.com/wire-cable/bare-aluminum-overhead-transmission-distribution/acsr/p/10154308",
        "diameter_m": "SOURCED: same Southwire page, nominal OD 28.13 mm",
        "area_m2": "DERIVED from 26 x 4.442 mm Al + 7 x 3.454 mm steel strands (ASTM B232 Drake construction, "
                   "recalled; corroborated by statnett/linerate IEEE738 test fixture: outer strand 4.4 mm, core 10.4 mm, "
                   "https://github.com/statnett/linerate/blob/main/tests/acceptance_tests/test_ieee_ampacity_cases.py)",
        "rts_n": "SOURCED (secondary): 31,500 lbf rated breaking strength in multiple manufacturer listings "
                 "(e.g. https://nassaunationalcable.com/products/795-d-acsr); verify against a mill test report",
        "modulus_pa": "ASSUMED: rule of mixtures with E_al=55 GPa, E_st=190 GPa (typical stranded final moduli); "
                      "gives ~74 GPa, in line with published ACSR 26/7 final moduli",
        "alpha_per_c": "ASSUMED: rule of mixtures with 23.0e-6 (Al) and 11.5e-6 (steel) /C; gives ~18.9e-6 /C",
        "limitations": "Linear elastic model: no creep, no high-temperature knee point (Al goes slack above "
                       "~knee temperature and the steel core carries the load); sags above ~100 C are underestimated.",
    },
)


# --------------------------------------------------------------------------------------
# Catenary primitives
# --------------------------------------------------------------------------------------


def sag(span_m: float, horizontal_tension_n: float, weight_n_per_m: float) -> float:
    """Mid-span sag (m) of a level catenary span."""
    a = horizontal_tension_n / weight_n_per_m
    return a * (math.cosh(span_m / (2 * a)) - 1.0)


def sag_parabolic(span_m: float, horizontal_tension_n: float, weight_n_per_m: float) -> float:
    return weight_n_per_m * span_m ** 2 / (8 * horizontal_tension_n)


def arc_length(span_m: float, horizontal_tension_n: float, weight_n_per_m: float,
               height_diff_m: float = 0.0) -> float:
    a = horizontal_tension_n / weight_n_per_m
    lv = 2 * a * math.sinh(span_m / (2 * a))
    return math.hypot(lv, height_diff_m)


def ruling_span(spans_m: Iterable[float]) -> float:
    s = np.asarray(list(spans_m), dtype=float)
    return float(math.sqrt((s ** 3).sum() / s.sum()))


def _bisect(f, lo, hi, tol=1e-6, maxit=200):
    flo, fhi = f(lo), f(hi)
    if flo * fhi > 0:
        raise ValueError("root not bracketed")
    for _ in range(maxit):
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        if abs(hi - lo) < tol * max(1.0, abs(mid)):
            return mid
        if (fm > 0) == (fhi > 0):
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
    return 0.5 * (lo + hi)


def tension_at_temperature(span_m: float, cond: ConductorMech, h_ref_n: float, t_ref_c: float,
                           t_c: float) -> float:
    """Horizontal tension (N) at conductor temperature t_c from a reference state, by the
    linear change-of-state equation on the (ruling) span."""
    w = cond.weight_n_per_m
    l_ref = arc_length(span_m, h_ref_n, w)

    def resid(h):
        l_geo = arc_length(span_m, h, w)
        l_phys = l_ref * (1 + cond.alpha_per_c * (t_c - t_ref_c)) * (1 + (h - h_ref_n) / cond.ea)
        return l_geo - l_phys  # decreasing in h

    lo = 1e-3 * h_ref_n
    hi = max(cond.rts_n * 2.0, 5 * h_ref_n)
    return _bisect(resid, lo, hi, tol=1e-10)


def tension_cubic_parabolic(span_m: float, cond: ConductorMech, h_ref_n: float, t_ref_c: float,
                            t_c: float) -> float:
    """Closed-form parabolic state-change equation (classic cubic) for cross-checking:
        H2^2 [H2 - H1 + (w S)^2 EA / (24 H1^2) + alpha EA (T2 - T1)] = (w S)^2 EA / 24
    """
    w, ea = cond.weight_n_per_m, cond.ea
    k = (w * span_m) ** 2 * ea / 24.0
    b = -h_ref_n + k / h_ref_n ** 2 + cond.alpha_per_c * ea * (t_c - t_ref_c)
    roots = np.roots([1.0, b, 0.0, -k])
    real = [r.real for r in roots if abs(r.imag) < 1e-6 * abs(r) and r.real > 0]
    return float(max(real))


def sag_at_temperature(span_m: float, cond: ConductorMech, h_ref_n: float, t_ref_c: float,
                       t_c: float, ruling_span_m: float | None = None) -> dict:
    """Sag of an actual span at temperature t_c; tension solved on the ruling span (if given)."""
    rs = ruling_span_m or span_m
    h = tension_at_temperature(rs, cond, h_ref_n, t_ref_c, t_c)
    return dict(t_c=t_c, horizontal_tension_n=h, sag_m=sag(span_m, h, cond.weight_n_per_m),
                tension_pct_rts=100 * h / cond.rts_n, ruling_span_m=rs)


# --------------------------------------------------------------------------------------
# 3D geometry
# --------------------------------------------------------------------------------------


def catenary_points_3d(p_a: Sequence[float], p_b: Sequence[float], horizontal_tension_n: float,
                       weight_n_per_m: float, n: int = 41) -> dict:
    """3D catenary between attachment points A=(x,y,z) and B=(x,y,z) (metres, z up).

    Returns points (n x 3), the inclined-span sag (max vertical gap to the chord),
    the lowest point, and arc length. The curve passes exactly through A and B.
    """
    a_pt = np.asarray(p_a, dtype=float)
    b_pt = np.asarray(p_b, dtype=float)
    dxy = b_pt[:2] - a_pt[:2]
    s = float(np.hypot(*dxy))
    if s <= 0:
        raise ValueError("attachment points must be horizontally separated")
    h = float(b_pt[2] - a_pt[2])
    a = horizontal_tension_n / weight_n_per_m
    x0 = s / 2 - a * math.asinh(h / (2 * a * math.sinh(s / (2 * a))))
    c0 = math.cosh(x0 / a)

    def y(x):
        return a * (np.cosh((x - x0) / a) - c0)

    xs = np.linspace(0.0, s, n)
    zs = a_pt[2] + y(xs)
    u = dxy / s
    pts = np.column_stack([a_pt[0] + xs * u[0], a_pt[1] + xs * u[1], zs])
    pts[-1, 2] = b_pt[2]  # remove round-off at the far end
    x_star = x0 + a * math.asinh(h / s)
    x_star = min(max(x_star, 0.0), s)
    sag_incl = float(h * x_star / s - y(x_star))
    xl = min(max(x0, 0.0), s)
    low = np.array([a_pt[0] + xl * u[0], a_pt[1] + xl * u[1], a_pt[2] + y(xl)])
    return dict(points=pts, sag_m=sag_incl, lowest_point=low, x0_m=x0, span_m=s, height_diff_m=h,
                arc_length_m=arc_length(s, horizontal_tension_n, weight_n_per_m, h))
