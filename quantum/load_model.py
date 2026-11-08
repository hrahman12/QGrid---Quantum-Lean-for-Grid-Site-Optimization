"""One net-load semantics shared by the search oracle (quantum/oracle.py) and the certificate
(lean/certify.py). Astra #6: before this the oracle checked net load with DLR-uplifted transformer
headroom while certify checked gross load, so the two disagreed on the same plan.

    relief      = storage_mw + curtailment_mw, capped at requested_mw (relief cannot exceed the load
                  it relieves -- Astra #5; certify separately fails a plan whose relief > requested)
    net_split   = split_mw * (1 - relief / requested_mw)   (pro rata across splits, as grid/physics.py)

DLR is NOT applied here: data/l2 defines DLR as an uplift on LINE ratings only, so substation /
transformer / bank headroom is compared with net_split unchanged by DLR (both oracle and certify).
"""
from __future__ import annotations

STORAGE_DURATION_H = 4.0  # ASSUMED storage duration; certify states the MWh obligation it implies


def net_factor(requested_mw: float, storage_mw: float, curtailment_mw: float) -> float:
    req = float(requested_mw)
    if req <= 0:
        return 0.0
    relief = min(float(storage_mw) + float(curtailment_mw), req)
    return max(0.0, 1.0 - relief / req)


def net_split(split_mw: float, requested_mw: float, storage_mw: float, curtailment_mw: float) -> float:
    """Net MW a split puts on its substation/bank after pro-rata storage + curtailment relief."""
    return float(split_mw) * net_factor(requested_mw, storage_mw, curtailment_mw)


if __name__ == "__main__":  # self-check
    assert net_split(50, 100, 25, 10) == 50 * 0.65
    assert net_split(1, 1, 50, 0) == 0.0  # relief capped at load; certify fails it separately
    assert net_split(10, 0, 0, 0) == 0.0
