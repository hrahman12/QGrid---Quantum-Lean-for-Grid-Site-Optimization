"""The discrete plan space the search stage explores (L3).

A plan = (how the requested MW is split over K candidate substations) x (DLR off/on)
         x (storage_mw) x (curtailment as % of the request).

  candidate substations  the K (default 4) nearest substations in the grid_snapshot with headroom_mw > 0,
                         ordered by distance_km (ties by id)
  splits                 all compositions of STEPS quarters (25% steps) into K bins: C(STEPS+K-1, K-1)
                         (K=4 -> 35)
  dlr                    {off, on}
  storage_mw             {0, 25, 50}
  curtailment            {0%, 5%, 10%} of requested_mw (converted to MW in the plan)

Default size N = 35 * 2 * 3 * 3 = 630 plans. Each plan has an integer index in [0, N); the Grover register
uses n = ceil(log2 N) qubits, and the padding indices [N, 2^n) are never marked.

Index layout (mixed radix, last factor fastest):
    index = ((split_idx * len(DLR) + dlr_idx) * len(STORAGE_MW) + storage_idx) * len(CURTAIL_PCT) + curtail_idx
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from itertools import combinations

STEPS = 4                    # 25% steps
DLR = (False, True)
STORAGE_MW = (0, 25, 50)
CURTAIL_PCT = (0, 5, 10)
DEFAULT_K = 4


def compositions(total: int, k: int) -> list[tuple[int, ...]]:
    """All k-tuples of non-negative ints summing to total (stars and bars), in a fixed lexicographic order."""
    out = []
    for bars in combinations(range(total + k - 1), k - 1):
        prev, parts = -1, []
        for b in bars:
            parts.append(b - prev - 1)
            prev = b
        parts.append(total + k - 1 - prev - 1)
        out.append(tuple(parts))
    return sorted(out, reverse=True)  # (4,0,0,0) first: all load on the nearest substation


def candidate_substations(snapshot: dict, k: int = DEFAULT_K) -> list[dict]:
    """The k nearest snapshot substations with headroom_mw > 0 (by distance_km, then id)."""
    subs = [s for s in snapshot["substations"] if (s.get("headroom_mw") or 0) > 0]
    subs.sort(key=lambda s: (s.get("distance_km", float("inf")), s["id"]))
    return subs[:k]


@dataclass(frozen=True)
class Plan:
    index: int
    quarters: tuple[int, ...]   # per candidate substation, in units of 25% of requested_mw
    dlr: bool
    storage_mw: float
    curtail_pct: float


@dataclass
class PlanSpace:
    site_id: str
    requested_mw: float
    substations: list[dict]
    splits: list[tuple[int, ...]] = field(default_factory=list)

    def __post_init__(self):
        if not self.splits:
            self.splits = compositions(STEPS, len(self.substations))

    # --- sizes -------------------------------------------------------------------------------
    @property
    def size(self) -> int:
        return len(self.splits) * len(DLR) * len(STORAGE_MW) * len(CURTAIL_PCT)

    @property
    def n_qubits(self) -> int:
        return max(1, math.ceil(math.log2(self.size)))

    @property
    def padded_size(self) -> int:
        return 2 ** self.n_qubits

    # --- encode / decode ---------------------------------------------------------------------
    def decode(self, index: int) -> Plan:
        if not 0 <= index < self.size:
            raise IndexError(f"plan index {index} outside [0, {self.size})")
        rest, ci = divmod(index, len(CURTAIL_PCT))
        rest, si = divmod(rest, len(STORAGE_MW))
        split_idx, di = divmod(rest, len(DLR))
        return Plan(index, self.splits[split_idx], DLR[di], float(STORAGE_MW[si]), float(CURTAIL_PCT[ci]))

    def encode(self, quarters, dlr, storage_mw, curtail_pct) -> int:
        split_idx = self.splits.index(tuple(quarters))
        return ((split_idx * len(DLR) + DLR.index(bool(dlr))) * len(STORAGE_MW)
                + STORAGE_MW.index(int(storage_mw))) * len(CURTAIL_PCT) + CURTAIL_PCT.index(int(curtail_pct))

    def plans(self):
        return (self.decode(i) for i in range(self.size))

    # --- plan -> numbers / contract ----------------------------------------------------------
    def split_mw(self, plan: Plan) -> list[float]:
        """MW per candidate substation (gross site load, before storage/curtailment); sums exactly to requested."""
        mw = [round(self.requested_mw * q / STEPS, 2) for q in plan.quarters]
        nz = [i for i, q in enumerate(plan.quarters) if q]
        if nz:  # absorb rounding in the last non-zero split so the total is exact
            last = nz[-1]
            mw[last] = round(self.requested_mw - sum(m for i, m in enumerate(mw) if i != last), 2)
        return mw

    def curtail_mw(self, plan: Plan) -> float:
        return round(self.requested_mw * plan.curtail_pct / 100.0, 2)

    def to_candidate_plan(self, plan: Plan, method: str, evals: int) -> dict:
        """Plan -> contracts/candidate_plan.schema.json (only substations with a non-zero split are listed)."""
        mw = self.split_mw(plan)
        # headroom_mw is copied verbatim from the grid_snapshot the search was given (no DLR uplift) so that
        # lean.certify checks capacity against the same snapshot the pipeline used, instead of rebuilding one
        # from the grid lane's offline cache. The split schema allows extra keys; validate.py still re-checks
        # every split against the pipeline's own grid_snapshot.
        splits = [{"substation_id": s["id"], "mw": m,
                   **({"headroom_mw": s["headroom_mw"]} if isinstance(s.get("headroom_mw"), (int, float)) else {})}
                  for s, m in zip(self.substations, mw) if m > 0]
        return {
            "site_id": self.site_id,
            "splits": splits,
            "flex": {"dlr": plan.dlr, "storage_mw": plan.storage_mw,
                     "curtailment_mw": self.curtail_mw(plan), "reconductor": False},
            "search": {"method": method, "evals": int(evals)},
        }

    def describe(self) -> dict:
        return {
            "site_id": self.site_id, "requested_mw": self.requested_mw,
            "candidate_substations": [{k: s.get(k) for k in ("id", "name", "distance_km", "headroom_mw")}
                                      for s in self.substations],
            "k": len(self.substations), "split_steps": f"{100 // STEPS}% of requested_mw",
            "n_splits": len(self.splits), "dlr": list(DLR), "storage_mw": list(STORAGE_MW),
            "curtailment_pct": list(CURTAIL_PCT), "N": self.size, "n_qubits": self.n_qubits,
            "padded_N": self.padded_size,
            "index_layout": "((split_idx*2 + dlr_idx)*3 + storage_idx)*3 + curtail_idx; padding indices never marked",
        }


def build_space(site: dict, snapshot: dict, k: int = DEFAULT_K) -> PlanSpace:
    subs = candidate_substations(snapshot, k)
    if not subs:
        raise ValueError("grid_snapshot has no substation with headroom_mw > 0")
    return PlanSpace(site_id=site["id"], requested_mw=float(site["requested_mw"]), substations=subs)
