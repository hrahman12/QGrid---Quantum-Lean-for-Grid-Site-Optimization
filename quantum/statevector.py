"""Independent numpy statevector Grover (no PsiQDK). Used as the cross-check and as the fallback simulator.

Convention matches the PsiQDK circuit in quantum/grover_psiqdk.py exactly (including global phase):
    start   H^n |0>                       = uniform |s>
    oracle  O = I - 2 sum_{m in marked} |m><m|
    diffuse D = H^n (I - 2|0><0|) H^n     = I - 2|s><s|
    one Grover iteration = D @ O  (this is minus the textbook 2|s><s| - I, i.e. a global phase (-1)^k)
"""
from __future__ import annotations

import math

import numpy as np


def optimal_iterations(n_total: int, n_marked: int) -> int:
    """floor(pi/4 * sqrt(N/M)); 0 when nothing (or everything) is marked."""
    if n_marked <= 0 or n_marked >= n_total:
        return 0
    return int(math.floor(math.pi / 4 * math.sqrt(n_total / n_marked)))


def grover_states(n_qubits: int, marked, iterations: int) -> list[np.ndarray]:
    """Statevectors after 0..iterations Grover iterations (list of length iterations+1)."""
    dim = 2 ** n_qubits
    psi = np.full(dim, 1 / math.sqrt(dim), dtype=np.complex128)
    sign = np.ones(dim)
    sign[list(marked)] = -1.0
    out = [psi.copy()]
    for _ in range(iterations):
        psi = psi * sign                  # oracle: flip the marked basis states
        psi = psi - 2 * psi.mean()        # I - 2|s><s|, since <s|psi>|s> = mean(psi) * (1,...,1)
        out.append(psi.copy())
    return out


def marked_probability_theory(n_total: int, n_marked: int, k: int) -> float:
    theta = math.asin(math.sqrt(n_marked / n_total))
    return math.sin((2 * k + 1) * theta) ** 2


def sample(probs, shots: int, seed: int) -> list[int]:
    rng = np.random.default_rng(seed)
    p = np.clip(np.real(np.asarray(probs, dtype=float)), 0, None)
    return [int(x) for x in rng.choice(len(p), size=shots, p=p / p.sum())]


def top_k(probs, k: int) -> dict:
    probs = np.asarray(probs, dtype=float)
    order = np.argsort(-probs, kind="stable")[:k]
    top = [{"index": int(i), "p": float(probs[i])} for i in order]
    return {"top": top, "rest": float(max(0.0, 1.0 - sum(t["p"] for t in top)))}
