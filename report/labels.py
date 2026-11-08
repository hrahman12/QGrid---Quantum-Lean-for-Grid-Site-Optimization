"""Honest labels shared by pipeline.py and report/summary.py (Astra review #2, #8, #9)."""

DATA_LABEL = ("conditional screening estimate from PG&E GRIP 2028 forecast (directional), "
              "not verified connectable capacity")
RULES_LABEL = ("encoded rules: capacity, thermal/voltage, N-1 incl. firm transformer capacity, transformer-bank cap, "
               "storage bound, flexibility, deadline, permit/ROW, penalty trigger, evidence binding; each tagged "
               "hard or negotiable (AMBER = only negotiable fail). Not covered: hourly curtailment calendar, flood, "
               "transmission-service lead time")


def data_label(site):
    """Headroom provenance depends on the region adapter that built the snapshot."""
    if (site or {}).get("country", "US") == "US":
        return DATA_LABEL
    return ("ASSUMED voltage-class ratings on OpenStreetMap substations (global adapter), "
            "screening estimate only, not verified connectable capacity")


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
    search = (plan or {}).get("search") or {}
    engine = search.get("engine")
    if engine:
        return {"psiqdk-simulated-grover": "PsiQDK simulated Grover (classical simulation, not quantum hardware)",
                "numpy-fallback": "NumPy fallback of the Grover search (not PsiQDK)",
                "classical": "classical search"}.get(engine, engine)
    method = search.get("method")
    return {"psiqdk": "PsiQDK simulated Grover (classical simulation, not quantum hardware)",
            "heuristic": "NumPy/classical fallback (not PsiQDK)",
            "random": "random baseline"}.get(method, f"unknown ({method})")
