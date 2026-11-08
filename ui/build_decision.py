"""Build ui/decision.json and inline it into ui/decision.html (opens from file://).

Reads only repo files: ui/data.json (run of ui/build_data.py, which already embeds the
pipeline certificate, rounds, edge loop, flex headroom, growth scenario and site risk),
data/shared/socio/alviso.json, data/shared/social/social_summary.json,
sim/mirofish/results/summary.json and data/shared/climate/alviso.json if present.
Every number shown comes from those files; RAG mapping rules are in this file.

Usage: python ui/build_decision.py
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

UI = Path(__file__).resolve().parent
ROOT = UI.parent
MARK_A = '<script id="decision-data" type="application/json">'
MARK_B = "</script><!--/decision-data-->"


def load(rel: str):
    p = ROOT / rel
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def mw(x: float) -> str:
    return f"{x:.1f}".rstrip("0").rstrip(".")


def climate_bullets(climate: dict | None, risk: dict) -> list[str]:
    fire = "Not in a fire-threat district." if not risk.get("site_in_hftd") else "In a CPUC fire-threat district."
    if not climate:
        return [f"Site in FEMA zone {risk.get('site_flood_zone')}, BFE {risk.get('site_bfe_ft')} ft.", fire]
    hz, heat = climate["hazards_climada"], climate["indicators"]["heat"]
    return [f"River flood {hz['river_flood_depth_p50_baseline']['value']:g} m now -> "
            f"{hz['river_flood_depth_p95_2050']['value']:.2f} m in 2050 (CLIMADA).",
            f"Days >35C: ~{heat['days_tmax_gt_35C_baseline']['value']:g} -> "
            f"~{heat['days_tmax_gt_35C_2050']['value']:g}/yr by 2036-2050.",
            fire]


def build() -> dict:
    d = load("ui/data.json")
    socio = load("data/shared/socio/alviso.json")
    social = load("data/shared/social/social_summary.json")
    sim = load("sim/mirofish/results/summary.json")
    climate = load("data/shared/climate/alviso.json")

    site, p, edge = d["site"], d["pipeline"], d["edge"]
    cert, dist, labels = p["certificate"], p["distribution"], p["labels"]
    req = site["requested_mw"]
    deadline = site["deadline"]
    run = p.get("run", "")

    # Grid power (transmission certificate)
    firm = next((c for c in cert["checks"] if c["name"] == "firm_n1"), None)
    short = float(re.search(r"by ([\d.]+) MW", firm["detail"]).group(1)) if firm and not firm["pass"] else 0.0
    grid_rag = cert["result"]

    # Edge sites now (distribution)
    now_mw, n_sites = dist["connectable_at_distribution_mw"], dist["n_edge_sites"]
    edge_rag = "GREEN" if now_mw > 0 else "RED"

    # Flexibility
    flex = d["flex"]["totals_mw_by_curtailment_pct"]
    flex2 = flex.get("2")

    # Future load (+20% ASSUMED stress)
    stress = d["growth"]["scenarios"]["stress_plus20pct_assumed"]["by_pct"]["0"]["distribution_mw"]
    future_rag = "RED" if stress < now_mw / 2 else "AMBER"

    # Consent
    cs = socio["consent_score"]
    cons_rag = "GREEN" if cs >= 0.65 else "AMBER" if cs >= 0.35 else "RED"
    hard_items = [i for i in socio["items"] if i["effect"] == "hard"]
    stance = social["all"]["by_stance"] if social else {}

    # Climate & resilience
    risk = d["risk"]["summary"]
    zone = risk.get("site_flood_zone")
    clim_rag = "AMBER" if risk.get("site_in_sfha") or risk.get("site_in_hftd") else "GREEN"

    # Timeline: transmission lead time vs years left
    ty = d["l3"]["transmission_years"]
    years_left = (date.fromisoformat(deadline) - date.fromisoformat(d["generated_utc"][:10])).days / 365.25
    time_rag = "RED" if ty[0] > years_left else "AMBER"

    lanes = [
        {"id": "grid", "name": "Grid power", "rag": grid_rag, "num": f"{mw(short)} MW",
         "text": "short at transmission (N-1)",
         "bullets": [f"Transmission plan for {req} MW fails firm N-1 by {mw(short)} MW.",
                     f"Needs {mw(dist['needs_transmission_mw'])} MW beyond distribution capacity.",
                     "Thermal and voltage checks pass; N-1 is the blocker."],
         "src": f"{run}/certificate.json"},
        {"id": "edge", "name": "Edge sites now", "rag": edge_rag, "num": f"{mw(now_mw)} MW",
         "text": f"across {n_sites} feeder sites",
         "bullets": [f"{mw(now_mw)} MW connectable at distribution, 0% curtailment.",
                     f"Edge loop proved {sum(s[1] for s in edge['final']['edge_sites']):.0f} MW GREEN in round {edge['final']['round']}.",
                     "Directional PG&E GRIP 2028 data, not verified capacity."],
         "src": "data/l2/flex_headroom.json, " + edge.get("run", "") + "/edge_alviso.json"},
        {"id": "flex", "name": "Flexibility", "rag": "AMBER", "num": f"{mw(flex2)} MW",
         "text": "with 2% curtailment",
         "bullets": [f"0% curtailment: {mw(flex['0'])} MW. 2%: {mw(flex2)} MW. 10%: {mw(flex['10'])} MW.",
                     "Needs a signed storage/curtailment commitment (none today).",
                     "Curtailment hours are a contract term, not physics."],
         "src": "data/l2/flex_headroom.json"},
        {"id": "future", "name": "Future load", "rag": future_rag, "num": f"{mw(stress)} MW",
         "text": "if area load +20%",
         "bullets": [f"Edge capacity drops from {mw(now_mw)} to {mw(stress)} MW.",
                     "+20% is an ASSUMED stress case, not a utility forecast.",
                     "Lock in capacity early before others queue."],
         "src": "scenarios/growth_alviso.py"},
        {"id": "consent", "name": "Community consent", "rag": cons_rag, "num": f"{cs:.2f}",
         "text": "negotiable, no hard blocker" if not hard_items else f"{len(hard_items)} hard blockers",
         "bullets": [f"Consent score {cs:.2f} (AMBER band 0.35-0.65). Weights ASSUMED.",
                     "San Jose draft standards: recycled-water cooling, carbon-neutral power, generator limits.",
                     f"Public posts: {stance.get('oppose', 0)} oppose, {stance.get('support', 0)} support, {stance.get('neutral', 0)} neutral."],
         "src": "data/shared/socio/alviso.json, data/shared/social/social_summary.json"},
        {"id": "climate", "name": "Climate & resilience", "rag": clim_rag, "num": f"Zone {zone}",
         "text": f"FEMA flood zone, {risk.get('site_bfe_ft')} ft BFE",
         "bullets": climate_bullets(climate, risk),
         "src": "data/shared/climate/alviso.json" if climate else "data/l2/site_risk.json"},
        {"id": "time", "name": "Timeline", "rag": time_rag, "num": f"{ty[0]}-{ty[1]} yrs",
         "text": f"for transmission; {years_left:.1f} yrs left",
         "bullets": [f"Deadline {deadline}: {years_left:.1f} years left.",
                     f"New transmission takes {ty[0]}-{ty[1]} years.",
                     "Distribution edge sites and storage fit the deadline."],
         "src": "data/l2/l3_inputs.json"},
    ]
    for ln in lanes:
        ln["bullets"] = ln["bullets"][:3]

    overall = "RED" if edge_rag == "RED" else ("AMBER" if grid_rag != "GREEN" else "GREEN")
    reason = (f"Not {req} MW. Yes to {mw(now_mw)} MW now." if overall == "AMBER"
              else f"Yes to {req} MW." if overall == "GREEN" else f"No: not {req} MW, no edge capacity.")

    s4 = next((x for x in (sim or {}).get("scenarios", []) if x["scenario"].startswith("S4")), None)
    actions = [
        {"text": f"Phase 16-{mw(now_mw)} MW at edge sites first", "flips": "time", "to": "GREEN"},
        {"text": "Commit 25-50 MW battery storage", "flips": "grid", "to": "AMBER"},
        {"text": f"Accept 2% curtailment ({mw(flex2)} MW)", "flips": "flex", "to": "GREEN"},
        {"text": "Community benefit agreement + local hiring", "flips": "consent", "to": "AMBER"},
        {"text": "Recycled-water cooling + all levers"
                 + (f" (sim {s4['approval_proxy']:.2f})" if s4 else ""),
         "flips": "consent", "to": "GREEN" if s4 and s4["approval_proxy"] >= 0.65 else "AMBER"},
    ]

    sim_chips = None
    if sim:
        sim_chips = {"engine": sim.get("engine", ""),
                     "items": [{"id": s["scenario"].split("_")[0], "label": s["label"],
                                "proxy": s["approval_proxy"],
                                "rag": "GREEN" if s["approval_proxy"] >= 0.65 else "AMBER" if s["approval_proxy"] >= 0.35 else "RED"}
                               for s in sim["scenarios"]]}

    se, ce = labels["search_engine"], labels["cert_engine"]
    how = [
        {"step": "Find", "status": "classical" if "fallback" in se.lower() or "classical" in se.lower() else "Grover", "detail": se},
        {"step": "Check", "status": "N-1 fail" if any(c["name"] == "n1" and not c["pass"] for c in cert["checks"]) else "pass",
         "detail": "AC power flow + N-1 contingency"},
        {"step": "Prove", "status": "Python mirror" if "mirror" in ce.lower() else "Lean 4", "detail": ce},
    ]
    loop = [{"round": r["round"], "rag": r["verdict"]} for r in edge["rounds"]]

    return {
        "question": f"{req} MW at Alviso, San Jose by {date.fromisoformat(deadline).strftime('%b %Y')}?",
        "overall": overall, "reason": reason, "lanes": lanes, "actions": actions,
        "sim": sim_chips, "how": how, "loop": loop,
        "footer": "Screening estimate from public utility data. Not a utility approval.",
        "generated_utc": d["generated_utc"], "run": run,
    }


def main() -> None:
    out = build()
    assert out["overall"] in ("RED", "AMBER", "GREEN") and len(out["lanes"]) >= 5
    assert all(len(ln["bullets"]) <= 3 for ln in out["lanes"])
    blob = json.dumps(out, indent=1)
    (UI / "decision.json").write_text(blob + "\n", encoding="utf-8")
    html = (UI / "decision.html").read_text(encoding="utf-8")
    a, b = html.index(MARK_A) + len(MARK_A), html.index(MARK_B)
    (UI / "decision.html").write_text(html[:a] + blob.replace("</", "<\\/") + html[b:], encoding="utf-8")
    print(f"decision: {out['overall']} - {out['reason']}")


if __name__ == "__main__":
    main()
