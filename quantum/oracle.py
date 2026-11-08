"""Cheap feasibility predicate over the plan space: the 'marking' rule that Grover's phase oracle flips.

    marked(plan)  <=>  storage + curtailment <= requested, and for every candidate substation i:
                           net_split(split_i)  <=  headroom_mw_i      (quantum/load_model.py, shared with certify)
                       and the plan does not violate any constraint fed back from Lean.

    net_factor  = max(0, 1 - (storage_mw + curtailment_mw) / requested_mw)
                  (storage and curtailment cut the site load pro rata across splits, same convention as
                  grid/physics.py)
    DLR: dlr_uplift_pct is still recorded (substation entry, else snapshot['dlr_uplift_pct'], else 0) but,
                  since Astra #6, it is NOT applied to substation headroom: data/l2 defines DLR on LINE
                  ratings only, and lean/certify.py uses the same rule. The pandapower check decides lines.

This predicate is the cheap screen only. The expensive 'verification cycle' runs afterwards on the one
chosen plan: grid.physics.check (pandapower AC power flow incl. N-1) and then lean.certify. A marked plan
is a candidate, never a result.

Constraints (past Lean blocking conditions, free text) are interpreted by `parse_constraints`:
  1. names a substation (id like osm-way-123, or its name) -> plans that put any MW on it are unmarked
     (e.g. lean 'capacity: osm-way-X split 37.5 MW > headroom 29.9 MW', or an n1 detail naming XF-osm-way-X)
  2. else names a flex resource (lean flex_commitment / deadline / penalty_trigger details):
       'storage' -> storage_mw must be 0;  'curtail' -> curtailment must be 0;  'DLR' -> DLR must be off
  3. else mentions a line loading / overload -> only plans with DLR on are marked
     (DLR is the only line-side flex grid/physics.py models)
  4. anything else is recorded as `unparsed` and does not change the marking
Every interpretation is written to quantum/out/last_search.json.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .load_model import net_split
from .space import Plan, PlanSpace


@dataclass
class ConstraintSet:
    excluded_substations: set[str] = field(default_factory=set)
    require_dlr: bool = False
    forbid_dlr: bool = False
    forbid_storage: bool = False
    forbid_curtailment: bool = False
    interpretations: list[dict] = field(default_factory=list)

    @property
    def unparsed(self) -> list[str]:
        return [i["constraint"] for i in self.interpretations if i["effect"] == "unparsed"]


def _mentions(text: str, sub: dict) -> bool:
    if re.search(re.escape(sub["id"]) + r"(?![\w])", text):
        return True
    name = (sub.get("name") or "").strip()
    return len(name) >= 4 and name.lower() in text.lower()


def parse_constraints(constraints, substations) -> ConstraintSet:
    cs = ConstraintSet()
    for c in constraints or []:
        text = str(c)
        hit = [s["id"] for s in substations if _mentions(text, s)]
        if hit:
            cs.excluded_substations.update(hit)
            cs.interpretations.append({"constraint": text, "effect": f"exclude plans loading {hit}"})
            continue
        flex = []
        if re.search(r"\bstorage\b", text, re.I):
            cs.forbid_storage = True
            flex.append("storage_mw must be 0")
        if re.search(r"curtail", text, re.I):
            cs.forbid_curtailment = True
            flex.append("curtailment must be 0")
        if re.search(r"\bDLR\b", text, re.I):
            cs.forbid_dlr = True
            flex.append("DLR must be off")
        if flex:
            cs.interpretations.append({"constraint": text, "effect": "; ".join(flex)})
        elif re.search(r"\bline\b.*\b(loading|overload)", text, re.I) or re.search(r"\boverload", text, re.I):
            cs.require_dlr = True
            cs.interpretations.append({"constraint": text, "effect": "line overload: mark only plans with DLR on"})
        else:
            cs.interpretations.append({"constraint": text, "effect": "unparsed"})
    return cs


class Oracle:
    """Marking predicate bound to one PlanSpace + snapshot + constraint set. Counts its own calls."""

    def __init__(self, space: PlanSpace, snapshot: dict, constraints=None):
        self.space = space
        self.constraints = parse_constraints(constraints, space.substations)
        self.notes = []
        snap_uplift = snapshot.get("dlr_uplift_pct")
        self.dlr_uplift_pct = []
        for s in space.substations:
            if s.get("dlr_uplift_pct") is not None:
                self.dlr_uplift_pct.append(float(s["dlr_uplift_pct"]))
            elif snap_uplift is not None:
                self.dlr_uplift_pct.append(float(snap_uplift))
            else:
                self.dlr_uplift_pct.append(0.0)
        src = ("substation entries" if any(s.get("dlr_uplift_pct") is not None for s in space.substations)
               else "snapshot['dlr_uplift_pct']" if snap_uplift is not None else None)
        if src is None:
            self.notes.append("snapshot has no dlr_uplift_pct: DLR uplift taken as 0% (DLR plans gain nothing)")
        else:
            self.notes.append(f"DLR uplift {sorted(set(self.dlr_uplift_pct))}% from {src}; NOT applied to substation "
                              "headroom (L2 defines it on line ratings; shared quantum/load_model.py semantics)")
        self.calls = 0

    def margins(self, plan: Plan) -> list[float]:
        """Per candidate substation: (effective capacity - effective load) / effective capacity."""
        sp = self.space
        out = []
        for s, mw in zip(sp.substations, sp.split_mw(plan)):
            # Astra #6: shared net-load model with lean/certify.py; DLR uplifts line ratings only, so
            # substation headroom is NOT raised by DLR here (was an optimistic screening shortcut).
            cap = float(s["headroom_mw"])
            load = net_split(mw, sp.requested_mw, plan.storage_mw, sp.curtail_mw(plan))
            out.append((cap - load) / cap if cap > 0 else float("-inf"))
        return out

    def __call__(self, plan_or_index) -> bool:
        self.calls += 1
        plan = plan_or_index if isinstance(plan_or_index, Plan) else self.space.decode(plan_or_index)
        cs = self.constraints
        if (cs.require_dlr and not plan.dlr) or (cs.forbid_dlr and plan.dlr):
            return False
        if (cs.forbid_storage and plan.storage_mw > 0) or (cs.forbid_curtailment and plan.curtail_pct > 0):
            return False
        # Astra #5: storage + curtailment relief above the requested load is not credible (certify fails it)
        if plan.storage_mw + self.space.curtail_mw(plan) > self.space.requested_mw + 1e-9:
            return False
        for s, q in zip(self.space.substations, plan.quarters):
            if q and s["id"] in cs.excluded_substations:
                return False
        return all(m >= -1e-9 for m, q in zip(self.margins(plan), plan.quarters) if q)

    def marked_indices(self, exclude=()) -> list[int]:
        """Enumerate the whole space classically with the predicate (N calls). This list is what the
        phase oracle is compiled from, so the Grover run below gives no query speedup: it demonstrates
        the search mechanics and its resource cost, nothing more."""
        ex = set(exclude)
        return [i for i in range(self.space.size) if i not in ex and self(i)]


def objective(space: PlanSpace, oracle: Oracle, plan: Plan) -> tuple:
    """Lower is better. (number of flex resources used, flex MW used, -min margin over loaded substations, index).

    'Fewest flex resources, then most balanced headroom margin': the most balanced plan is the one whose
    worst-loaded substation keeps the largest fraction of its (effective) headroom free.
    """
    n_flex = int(plan.dlr) + int(plan.storage_mw > 0) + int(plan.curtail_pct > 0)
    flex_mw = plan.storage_mw + space.curtail_mw(plan)
    used = [m for m, q in zip(oracle.margins(plan), plan.quarters) if q]
    return (n_flex, flex_mw, -min(used) if used else 0.0, plan.index)
