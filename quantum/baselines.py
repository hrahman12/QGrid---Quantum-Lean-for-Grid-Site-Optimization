"""Classical baselines over the same plan space and the same oracle (for the Lean Green Yield metric).

random_search     draw plan indices uniformly (with replacement) from [0, N) until the oracle marks one that is
                  not excluded. evals = oracle calls made.
heuristic_search  walk the plans in a fixed greedy order and return the first marked, non-excluded one.
                  Order: fewest flex resources, least flex MW, then splits closest (L1) to a headroom-proportional
                  split of the request. evals = oracle calls made.
Both return (Plan | None, evals). Plan -> contract dict with PlanSpace.to_candidate_plan(plan, method, evals).
"""
from __future__ import annotations

import random

from .oracle import Oracle
from .space import STEPS, Plan, PlanSpace


def random_search(space: PlanSpace, oracle: Oracle, seed: int = 0, exclude=(), max_evals: int = 100_000):
    rng = random.Random(seed)
    ex = set(exclude)
    before = oracle.calls
    for _ in range(max_evals):
        i = rng.randrange(space.size)
        if i in ex:
            continue
        if oracle(i):
            return space.decode(i), oracle.calls - before
    return None, oracle.calls - before


def heuristic_order(space: PlanSpace) -> list[int]:
    heads = [max(float(s["headroom_mw"]), 0.0) for s in space.substations]
    total = sum(heads) or 1.0
    target = [STEPS * h / total for h in heads]

    def key(p: Plan):
        n_flex = int(p.dlr) + int(p.storage_mw > 0) + int(p.curtail_pct > 0)
        dist = sum(abs(q - t) for q, t in zip(p.quarters, target))
        return (n_flex, p.storage_mw + space.curtail_mw(p), dist, p.index)

    return [p.index for p in sorted(space.plans(), key=key)]


def heuristic_search(space: PlanSpace, oracle: Oracle, exclude=()):
    ex = set(exclude)
    before = oracle.calls
    for i in heuristic_order(space):
        if i in ex:
            continue
        if oracle(i):
            return space.decode(i), oracle.calls - before
    return None, oracle.calls - before
