"""pandapower check of one candidate plan against a grid_snapshot (L1).

Model (all assumptions, none measured):
  ext_grid (1.02 pu) -> HV bus (highest kV in the snapshot)
  HV bus -> source transformer XF-<sub> (sn = assumed_mva) -> substation bus
  snapshot lines tie substations together (tap transformer T-<sub>-<kv> if the line kV differs from the bus kV)
  each substation carries an existing load = assumed_mva*PF - headroom_mw, plus the plan's split.
Flexibility: storage_mw and curtailment_mw cut the site load pro-rata across splits,
  dlr raises line ratings by snapshot['dlr_uplift_pct'] (default 15), reconductor by RECONDUCTOR_UPLIFT.
Limits: normal <=100% loading, 0.95-1.05 pu; N-1 <=110% emergency, 0.90-1.10 pu over two contingency sets:
  every snapshot line out (power flow), and each substation's largest source bank out (firm check: the plan's MW at a
  substation, after flex, must be <= its headroom_mw_n1_firm when the snapshot has it; substations without it are unchecked).
shortcut: the bank outage is a capacity check, not a re-solved flow (XF-<sub> is one lumped transformer); upgrade by
  modelling banks as parallel transformers if per-bank data reaches the snapshot.
shortcut: site load sits on the substation bus (no LV site feeder), PQ only at constant PF; upgrade if Lean needs it.
"""
from __future__ import annotations

import math
import warnings

import numpy as np
import pandapower as pp

PF = 0.95
Q_PER_P = math.tan(math.acos(PF))
SLACK_VM_PU = 1.02
RECONDUCTOR_UPLIFT = 1.40
LOAD_LIMIT_PCT = 100.0
N1_LIMIT_PCT = 110.0
V_NORMAL = (0.95, 1.05)
V_N1 = (0.90, 1.10)
# Standard overhead-line per-km values by kV (r ohm/km, x ohm/km, c nF/km); typical ACSR, assumed.
LINE_RX = {69: (0.19, 0.42, 9), 115: (0.09, 0.40, 10), 138: (0.07, 0.40, 10), 230: (0.05, 0.39, 11),
           345: (0.03, 0.37, 12), 500: (0.02, 0.33, 13)}
TRAFO_VK_PERCENT, TRAFO_VKR_PERCENT = 10.0, 0.3


def _std(kv):
    return LINE_RX[min(LINE_RX, key=lambda k: abs(k - kv))]


def build_net(plan, snap):
    """Return (net, unknown_substations). Nothing is solved here."""
    subs = {s["id"]: s for s in snap["substations"]}
    unknown = [s["substation_id"] for s in plan["splits"] if s["substation_id"] not in subs]
    flex = plan["flex"]
    mw = {}
    for s in plan["splits"]:
        if s["substation_id"] in subs:
            mw[s["substation_id"]] = mw.get(s["substation_id"], 0.0) + s["mw"]
    total = sum(mw.values())
    net_total = max(0.0, total - flex["storage_mw"] - flex["curtailment_mw"])
    scale = net_total / total if total > 0 else 0.0

    net = pp.create_empty_network(f_hz=60.0)
    hv_kv = max(s["kv"] for s in subs.values())
    hv = pp.create_bus(net, hv_kv, name="HV")
    pp.create_ext_grid(net, hv, vm_pu=SLACK_VM_PU, name="ext")
    bus = {}  # (sub_id, kv) -> bus index

    def trafo(sub, hv_bus, lv_bus, hv_v, lv_v, name):
        pp.create_transformer_from_parameters(
            net, hv_bus, lv_bus, sn_mva=sub["assumed_mva"], vn_hv_kv=max(hv_v, lv_v), vn_lv_kv=min(hv_v, lv_v),
            vkr_percent=TRAFO_VKR_PERCENT, vk_percent=TRAFO_VK_PERCENT, pfe_kw=0, i0_percent=0, name=name)

    for sid, s in subs.items():
        b = pp.create_bus(net, s["kv"], name=sid)
        bus[(sid, s["kv"])] = b
        trafo(s, hv, b, hv_kv, s["kv"], f"XF-{sid}")
        base = max(0.0, s["assumed_mva"] * PF - s["headroom_mw"])
        p = base + mw.get(sid, 0.0) * scale
        pp.create_load(net, b, p_mw=p, q_mvar=p * Q_PER_P, name=sid)

    def bus_at(sid, kv):
        if (sid, kv) not in bus:
            s = subs[sid]
            bus[(sid, kv)] = pp.create_bus(net, kv, name=f"{sid}@{kv}")
            trafo(s, bus[(sid, s["kv"])], bus[(sid, kv)], s["kv"], kv, f"T-{sid}-{kv}")
        return bus[(sid, kv)]

    uplift = (1 + snap.get("dlr_uplift_pct", 15.0) / 100 if flex["dlr"] else 1.0) * (RECONDUCTOR_UPLIFT if flex["reconductor"] else 1.0)
    for ln in snap["lines"]:
        if ln["from"] not in subs or ln["to"] not in subs:
            continue
        r, x, c = _std(ln["kv"])
        pp.create_line_from_parameters(
            net, bus_at(ln["from"], ln["kv"]), bus_at(ln["to"], ln["kv"]), length_km=ln["length_km"],
            r_ohm_per_km=r, x_ohm_per_km=x, c_nf_per_km=c,
            max_i_ka=ln["rating_mva"] * uplift / (math.sqrt(3) * ln["kv"]), name=ln["id"])
    net.substation_mw = {sid: v * scale for sid, v in mw.items()}  # plan MW after flex, per substation
    return net, unknown


def _firm_violations(net, subs):
    out = []
    for sid, p in net.substation_mw.items():
        firm = subs[sid].get("headroom_mw_n1_firm")
        if firm is not None and p > firm + 1e-6:
            out.append(f"N-1 transformer XF-{sid} largest bank out: plan {p:.1f} MW > firm headroom {firm:.1f} MW (headroom_mw_n1_firm)")
    return out


def _solve(net):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            pp.runpp(net, numba=False)
        return True
    except Exception:  # pandapower raises LoadflowNotConverged and numeric errors
        return False


def _violations(net, limit_pct, vlim, tag=""):
    out = []
    load_buses = set(net.load.bus)
    for b in load_buses:
        if np.isnan(net.res_bus.vm_pu[b]):
            out.append(f"{tag}bus {net.bus.name[b]} unsupplied")
    for tbl, res, kind in ((net.line, net.res_line, "line"), (net.trafo, net.res_trafo, "transformer")):
        for i, name in tbl.name.items():
            v = res.loading_percent[i]
            if not np.isnan(v) and v > limit_pct:
                out.append(f"{tag}{kind} {name} loading {v:.0f}% > {limit_pct:.0f}%")
    vm = net.res_bus.vm_pu[list(load_buses)].dropna()
    for b, v in vm.items():
        if not vlim[0] <= v <= vlim[1]:
            out.append(f"{tag}bus {net.bus.name[b]} voltage {v:.3f} pu outside {vlim[0]}-{vlim[1]}")
    return out


def check(plan, snapshot):
    """plan: candidate_plan, snapshot: grid_snapshot -> physics_result (see contracts/physics_result.schema.json)."""
    net, unknown = build_net(plan, snapshot)
    if unknown:
        return {"converged": False, "max_line_loading_pct": None, "v_min_pu": None, "v_max_pu": None,
                "n1_pass": False, "violations": [f"unknown substation {u} in plan" for u in unknown]}
    if not _solve(net):
        return {"converged": False, "max_line_loading_pct": None, "v_min_pu": None, "v_max_pu": None,
                "n1_pass": False, "violations": ["base-case power flow did not converge"]}
    loads = np.concatenate([net.res_line.loading_percent.values, net.res_trafo.loading_percent.values])
    vm = net.res_bus.vm_pu.dropna()
    violations = _violations(net, LOAD_LIMIT_PCT, V_NORMAL)

    n1_viol = _firm_violations(net, {s["id"]: s for s in snapshot["substations"]})
    for i, name in net.line.name.items():
        net.line.at[i, "in_service"] = False
        if not _solve(net):
            n1_viol.append(f"N-1 line {name} out: power flow did not converge")
        else:
            n1_viol += _violations(net, N1_LIMIT_PCT, V_N1, tag=f"N-1 line {name} out: ")
        net.line.at[i, "in_service"] = True
    return {"converged": True,
            "max_line_loading_pct": round(float(np.nanmax(loads)), 1),
            "v_min_pu": round(float(vm.min()), 4), "v_max_pu": round(float(vm.max()), 4),
            "n1_pass": not n1_viol, "violations": violations + n1_viol}
