"""DC (B-theta) power flow, PTDF/LODF, and N-1 contingency sweep.

DC power flow assumptions (standard; e.g. Stott, Jardim & Alsac, "DC Power Flow Revisited",
IEEE Trans. Power Systems 24(3), 2009, doi:10.1109/TPWRS.2009.2021235):
  |V| = 1 pu everywhere, r << x, small angle differences, no reactive power, lossless.
      P = B' theta,   B'_ij = -1/x_ij,  B'_ii = sum_j 1/x_ij
      f_ij = (theta_i - theta_j) / x_ij
  The slack bus absorbs the injection mismatch.

Line reactance per km. The task brief suggested "~0.8 ohm/km at 115 kV, ~0.5 at 230 kV".
0.8 ohm/km is about twice the physical value for an overhead line (0.8 ohm/MILE, ~0.5
ohm/km, is a common US single-circuit figure, which may be where it came from). We compute
X from line geometry instead:
      X = 2 pi f (mu0 / 2 pi) ln(GMD / GMR_eq)  ohm/m,  mu0/2pi = 2e-7 H/m
(e.g. Glover, Sarma & Overbye, "Power System Analysis and Design", ch. 4), with ASSUMED
phase spacings per voltage class and Drake GMR. Cross-check: pandapower's standard types
(https://pandapower.readthedocs.io/en/latest/std_types/basic.html) give 0.37 ohm/km
(490-AL1/64-ST1A, 110 kV) and 0.285 ohm/km (220 kV) at 50 Hz, i.e. 0.444 and 0.342 ohm/km
at 60 Hz. Our 60 Hz single-conductor values below are 0.42-0.50 ohm/km.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Sequence

import numpy as np

F_HZ = 60.0  # WECC / PG&E system frequency

# Drake GMR 0.0375 ft = 11.43 mm: value from standard ACSR tables (e.g. Glover/Sarma/Overbye
# Appendix Table A.4). RECALLED, not re-fetched this session -> treat as ASSUMED until checked.
DRAKE_GMR_M = 0.0375 * 0.3048

# ASSUMED typical flat-configuration phase spacing (m) and bundling per voltage class.
# Reasoning: spacing must clear switching-surge and swing clearances; ~2.4 m at 60 kV,
# ~4 m at 115 kV, ~7 m at 230 kV are typical of US wood-pole / lattice designs. No PG&E
# design data were available. GMD (flat) = spacing * 2^(1/3).
VOLTAGE_CLASS_GEOMETRY = {
    60.0: dict(phase_spacing_m=2.4, bundle=1, bundle_spacing_m=0.0, gmr_m=DRAKE_GMR_M, status="ASSUMED"),
    115.0: dict(phase_spacing_m=4.0, bundle=1, bundle_spacing_m=0.0, gmr_m=DRAKE_GMR_M, status="ASSUMED"),
    230.0: dict(phase_spacing_m=7.0, bundle=1, bundle_spacing_m=0.0, gmr_m=DRAKE_GMR_M, status="ASSUMED"),
}


def reactance_ohm_per_km(phase_spacing_m: float, gmr_m: float, bundle: int = 1,
                         bundle_spacing_m: float = 0.0, f_hz: float = F_HZ,
                         flat: bool = True) -> float:
    """Positive-sequence series reactance (ohm/km) of a transposed three-phase line."""
    gmd = phase_spacing_m * (2 ** (1 / 3) if flat else 1.0)
    if bundle == 1:
        gmr_eq = gmr_m
    elif bundle == 2:
        gmr_eq = math.sqrt(gmr_m * bundle_spacing_m)
    elif bundle == 3:
        gmr_eq = (gmr_m * bundle_spacing_m ** 2) ** (1 / 3)
    elif bundle == 4:
        gmr_eq = 1.0905 * (gmr_m * bundle_spacing_m ** 3) ** 0.25
    else:
        raise ValueError("bundle must be 1..4")
    return 2 * math.pi * f_hz * 2e-7 * math.log(gmd / gmr_eq) * 1000.0


def typical_reactance_ohm_per_km(kv: float) -> float:
    g = VOLTAGE_CLASS_GEOMETRY.get(float(kv))
    if g is None:
        raise KeyError(f"no geometry for {kv} kV; add an ASSUMED entry with reasoning")
    return reactance_ohm_per_km(g["phase_spacing_m"], g["gmr_m"], g["bundle"], g["bundle_spacing_m"])


def x_pu(length_km: float, kv: float, s_base_mva: float = 100.0,
         x_ohm_per_km: Optional[float] = None) -> float:
    x = (x_ohm_per_km if x_ohm_per_km is not None else typical_reactance_ohm_per_km(kv)) * length_km
    return x / (kv ** 2 / s_base_mva)


# --------------------------------------------------------------------------------------


@dataclass
class Branch:
    name: str
    f: int                 # from-bus index
    t: int                 # to-bus index
    x_pu: float
    rating_mw: float = float("inf")
    meta: dict = field(default_factory=dict)


@dataclass
class Network:
    bus_names: Sequence[str]
    branches: Sequence[Branch]
    slack: int = 0
    s_base_mva: float = 100.0

    @property
    def n(self) -> int:
        return len(self.bus_names)

    def incidence(self, active: Optional[Sequence[bool]] = None) -> np.ndarray:
        br = [b for k, b in enumerate(self.branches) if active is None or active[k]]
        a = np.zeros((len(br), self.n))
        for i, b in enumerate(br):
            a[i, b.f] = 1.0
            a[i, b.t] = -1.0
        return a


def _islands(n: int, edges) -> list[set]:
    adj = {i: set() for i in range(n)}
    for f, t in edges:
        adj[f].add(t)
        adj[t].add(f)
    seen, comps = set(), []
    for s in range(n):
        if s in seen:
            continue
        stack, comp = [s], set()
        while stack:
            u = stack.pop()
            if u in comp:
                continue
            comp.add(u)
            stack.extend(adj[u] - comp)
        seen |= comp
        comps.append(comp)
    return comps


def dc_power_flow(net: Network, injections_mw: Sequence[float],
                  active: Optional[Sequence[bool]] = None) -> dict:
    """Solve the DC power flow. injections_mw: generation minus load per bus (MW).

    The slack bus injection is recomputed to balance the system.
    Returns per-branch flow (MW, positive f->t), loading (|flow| / rating) and angles (deg).
    Inactive branches report flow 0. Raises if the active network is islanded.
    """
    active = [True] * len(net.branches) if active is None else list(active)
    edges = [(b.f, b.t) for b, a in zip(net.branches, active) if a]
    if len(_islands(net.n, edges)) > 1:
        raise np.linalg.LinAlgError("network islanded")
    p = np.asarray(injections_mw, dtype=float) / net.s_base_mva
    p = p.copy()
    p[net.slack] = 0.0
    p[net.slack] = -p.sum()
    bmat = np.zeros((net.n, net.n))
    for b, a in zip(net.branches, active):
        if not a:
            continue
        y = 1.0 / b.x_pu
        bmat[b.f, b.f] += y
        bmat[b.t, b.t] += y
        bmat[b.f, b.t] -= y
        bmat[b.t, b.f] -= y
    keep = [i for i in range(net.n) if i != net.slack]
    theta = np.zeros(net.n)
    theta[keep] = np.linalg.solve(bmat[np.ix_(keep, keep)], p[keep])
    flows = np.array([(theta[b.f] - theta[b.t]) / b.x_pu * net.s_base_mva if a else 0.0
                      for b, a in zip(net.branches, active)])
    ratings = np.array([b.rating_mw for b in net.branches])
    loading = np.abs(flows) / ratings
    return dict(theta_deg=np.degrees(theta), flow_mw=flows, loading=loading,
                slack_mw=p[net.slack] * net.s_base_mva, active=active)


def ptdf(net: Network) -> np.ndarray:
    """Power transfer distribution factors (branches x buses), slack-referenced."""
    a = net.incidence()
    bd = np.diag([1.0 / b.x_pu for b in net.branches])
    bbus = a.T @ bd @ a
    keep = [i for i in range(net.n) if i != net.slack]
    out = np.zeros((len(net.branches), net.n))
    out[:, keep] = bd @ a[:, keep] @ np.linalg.inv(bbus[np.ix_(keep, keep)])
    return out


def lodf(net: Network) -> np.ndarray:
    """Line outage distribution factors: LODF[l, k] = change of flow on l per unit of
    pre-outage flow on k when k trips. Columns of radial (bridge) branches are NaN."""
    h = ptdf(net)
    a = net.incidence()
    ptdf_br = h @ a.T  # branch-to-branch transfer: column k = PTDF of injection at f_k, withdrawal at t_k
    m = len(net.branches)
    out = np.full((m, m), np.nan)
    for k in range(m):
        denom = 1.0 - ptdf_br[k, k]
        if abs(denom) < 1e-9:
            continue
        out[:, k] = ptdf_br[:, k] / denom
        out[k, k] = -1.0
    return out


def n_minus_1(net: Network, injections_mw: Sequence[float]) -> dict:
    """Trip each branch in turn; report post-contingency flows and the worst loading."""
    base = dc_power_flow(net, injections_mw)
    cases = []
    for k, br in enumerate(net.branches):
        active = [i != k for i in range(len(net.branches))]
        edges = [(b.f, b.t) for b, a in zip(net.branches, active) if a]
        comps = _islands(net.n, edges)
        if len(comps) > 1:
            stranded = sorted(set().union(*[c for c in comps if net.slack not in c]))
            stranded_mw = float(sum(injections_mw[i] for i in stranded))
            cases.append(dict(outage=br.name, islanded=True,
                              stranded_buses=[net.bus_names[i] for i in stranded],
                              stranded_injection_mw=stranded_mw, max_loading=float("inf"),
                              worst_branch=None, flow_mw=None, loading=None))
            continue
        r = dc_power_flow(net, injections_mw, active)
        j = int(np.argmax(r["loading"]))
        cases.append(dict(outage=br.name, islanded=False, max_loading=float(r["loading"][j]),
                          worst_branch=net.branches[j].name, flow_mw=r["flow_mw"], loading=r["loading"]))
    worst = max(cases, key=lambda c: c["max_loading"]) if cases else None
    return dict(base=base, cases=cases,
                max_loading=worst["max_loading"] if worst else 0.0,
                worst_outage=worst["outage"] if worst else None,
                worst_branch=worst["worst_branch"] if worst else None,
                secure=bool(worst is None or worst["max_loading"] <= 1.0))
