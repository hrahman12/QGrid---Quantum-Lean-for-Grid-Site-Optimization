"""Honest labels shared by pipeline.py and report/summary.py (Astra review #2, #8, #9)."""

DATA_LABEL = ("conditional screening estimate from PG&E GRIP 2028 forecast (directional), "
              "not verified connectable capacity")
RULES_LABEL = ("encoded seven-rule transmission surrogate; no feeder/bank aggregation, curtailment "
               "calendar, flood or transmission-service lead-time rules")


def verdict_label(result):
    return "GREEN on the encoded rules over the supplied evidence" if result == "GREEN" else result


def cert_engine(cert):
    """Engine that actually produced the certificate, from its `engine` field or scope_note text."""
    eng, note = str(cert.get("engine") or ""), str(cert.get("scope_note") or "")
    if eng == "lean4" or (not eng and "Lean 4 decision procedure" in note and "did NOT run" not in note):
        return "Lean 4"
    if eng == "python-mirror" or "python-mirror" in note or "did NOT run" in note:
        return "Python mirror of the Lean rules (Lean did not run)"
    return "unknown (fixture or unlabelled certificate)"


def search_engine(plan):
    method = ((plan or {}).get("search") or {}).get("method")
    return {"psiqdk": "PsiQDK simulated Grover (classical simulation, not quantum hardware)",
            "heuristic": "NumPy/classical fallback (not PsiQDK)",
            "random": "random baseline"}.get(method, f"unknown ({method})")
