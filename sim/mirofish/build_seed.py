"""Repo data -> simulation seed.

Writes sim/mirofish/seed.json (input to run_sim.py) and sim/mirofish/seed.md
(a plain-text brief that can be uploaded to MiroFish as its seed document).

Sources: data/shared/socio/alviso.json (consent items), data/l2/site_risk.json,
STATUS.md headline, and data/shared/social/*.json when present.
Actor groups, stances, influence and lever shifts are ASSUMED analyst judgments,
each tied to the consent item(s) it comes from.
"""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent

# group: (label, n_agents, initial stance [-1 oppose .. +1 support], stubbornness, source items, note)
ACTORS = {
    "residents": ("Alviso residents & neighborhood groups", 10, -0.6, 0.3, ["a-alviso-opposition", "a-sj-moratorium-calls"], "asked for a pause at the Oct 15 2026 meeting"),
    "env": ("Environmental / water advocates", 6, -0.7, 0.4, ["a-sj-draft-standards", "a-sj-moratorium-calls"], "water, carbon, gas-backup concerns"),
    "online": ("r/sanjose petition commenters", 6, -0.5, 0.2, ["a-reddit-sanjose"], "mostly negative: grid, rates, water"),
    "council": ("San Jose City Council", 5, 0.2, 0.3, ["a-sj-council-pro-growth", "a-sj-draft-standards"], "pro-growth, drafting standards; vote Dec 2026"),
    "mayor": ("Mayor of San Jose", 1, 0.5, 0.5, ["a-sj-moratorium-calls"], "opposes a ban"),
    "planning": ("Planning department", 2, 0.0, 0.5, ["a-sj-permit-pathway"], "special use permit pathway"),
    "pge": ("PG&E", 2, 0.3, 0.6, ["a-pge-rule30", "a-sj-pge-partnership"], "Rule 30 interim; 150 MW at transmission RED per grid result"),
    "ratepayer": ("CPUC / ratepayer advocates", 2, -0.2, 0.5, ["a-ca-sb57"], "SB 57 cost-shift study"),
    "labor": ("Building trades / local labor", 3, 0.2, 0.4, [], "ASSUMED, no item in alviso.json"),
    "developer": ("Developer (150 MW proposal)", 1, 0.9, 0.9, ["a-alviso-opposition"], "proposer"),
}
# who listens to whom (cross-group influence, normalised in run_sim.py). ASSUMED.
LISTENS = {
    "residents": {"env": 3, "online": 3, "mayor": 1, "council": 1, "labor": 1, "developer": 0.5},
    "env": {"residents": 3, "online": 1, "ratepayer": 1, "council": 1},
    "online": {"residents": 3, "env": 2, "ratepayer": 1},
    "council": {"residents": 2, "mayor": 3, "planning": 1, "labor": 1, "env": 1, "pge": 1, "developer": 1},
    "mayor": {"council": 2, "labor": 1, "developer": 1, "residents": 1},
    "planning": {"council": 3, "pge": 1, "mayor": 1},
    "pge": {"ratepayer": 1, "developer": 1, "council": 1},
    "ratepayer": {"online": 1, "env": 1, "pge": 1},
    "labor": {"developer": 2, "council": 1, "residents": 1},
    "developer": {"council": 1, "mayor": 1},
}
# item id -> actor groups whose final stance scales that item's weight in the consent formula
ITEM_ACTORS = {
    "a-sj-draft-standards": ["env", "council"],
    "a-sj-moratorium-calls": ["residents", "env"],
    "a-alviso-opposition": ["residents"],
    "a-sj-permit-pathway": ["planning"],
    "a-pge-rule30": ["pge"],
    "a-ca-sb57": ["ratepayer"],
    "a-reddit-sanjose": ["online"],
    "a-sj-council-pro-growth": ["council", "mayor"],
    "a-sj-pge-partnership": ["pge"],
}
# levers: stance shift per group (applied at announcement and to the group's anchor)
# and item weight deltas. All shifts ASSUMED; rationale in "why".
LEVERS = {
    "cba_local_hiring": {
        "label": "Community benefit agreement + local hiring",
        "stance": {"residents": 0.35, "labor": 0.4, "council": 0.15, "online": 0.1, "mayor": 0.1},
        "items": {"a-alviso-opposition": -0.15, "a-sj-moratorium-calls": -0.1},
        "why": "addresses 'what does Alviso get'; draft standards already ask for housing fees",
    },
    "recycled_water_heat_reuse": {
        "label": "Recycled-water / closed-loop cooling + heat reuse",
        "stance": {"env": 0.4, "residents": 0.15, "council": 0.2, "online": 0.1},
        "items": {"a-sj-draft-standards": -0.35, "a-reddit-sanjose": -0.05},
        "why": "meets the draft San Jose cooling condition; water was a top petition complaint",
    },
    "edge_phase_gen_limits": {
        "label": "Edge phase 16-38 MW at distribution + generator limits (25 h/yr)",
        "stance": {"pge": 0.3, "ratepayer": 0.25, "residents": 0.2, "env": 0.15, "online": 0.1, "developer": -0.2},
        "items": {"a-pge-rule30": -0.3, "a-ca-sb57": -0.1, "a-sj-draft-standards": -0.15, "a-reddit-sanjose": -0.05},
        "why": "grid result: 150 MW transmission RED, 16 MW GREEN / 38.7 MW fits at distribution; meets 25 h/yr generator-testing draft limit",
    },
}
SCENARIOS = {
    "S0_baseline": {"label": "150 MW, gas backup, no engagement", "levers": []},
    "S1_cba_hiring": {"label": "S0 + community benefit agreement + local hiring", "levers": ["cba_local_hiring"]},
    "S2_water_heat": {"label": "S0 + recycled-water/closed-loop cooling + heat reuse", "levers": ["recycled_water_heat_reuse"]},
    "S3_edge_phase": {"label": "16-38 MW edge phase at distribution + generator limits", "levers": ["edge_phase_gen_limits"]},
    "S4_all_levers": {"label": "All levers", "levers": list(LEVERS)},
}


def load(rel):
    p = ROOT / rel
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def main():
    alviso = load("data/shared/socio/alviso.json")
    risk = load("data/l2/site_risk.json")
    status = (ROOT / "STATUS.md").read_text(encoding="utf-8")
    m = re.search(r"\*\*Headline so far\*\*(.*)", status)
    headline = m.group(1).strip(" :") if m else ""
    social = {n: load(f"data/shared/social/{n}.json") for n in ("stakeholders", "engagement_levers", "social_posts", "opposition_events")}
    social = {k: v for k, v in social.items() if v is not None}

    known = {i["id"] for i in alviso["items"]}
    for g, a in ACTORS.items():
        assert set(a[4]) <= known, (g, a[4])
    assert set(ITEM_ACTORS) <= known

    seed = {
        "site": alviso["name"],
        "consent_formula": alviso["consent_formula"],
        "consent_score_repo": alviso["consent_score"],
        "items": [{k: i[k] for k in ("id", "type", "effect", "weight", "applies_to", "summary", "url")} for i in alviso["items"]],
        "site_risk": risk["summary"] if risk else None,
        "grid_headline": headline,
        "actors": {g: dict(zip(("label", "n", "stance", "stubborn", "items", "note"), a)) for g, a in ACTORS.items()},
        "listens": LISTENS,
        "item_actors": ITEM_ACTORS,
        "levers": LEVERS,
        "scenarios": SCENARIOS,
        "social_files_found_not_used": sorted(social),  # copied for provenance; run_sim.py does not consume them yet
        "social": social,
    }
    (HERE / "seed.json").write_text(json.dumps(seed, indent=1, ensure_ascii=False), encoding="utf-8")

    md = [f"# Data-center proposal: {alviso['name']}", "",
          "A developer proposes a 150 MW data center in Alviso / North San Jose with gas backup generators.", "",
          f"Grid screening: {headline}", ""]
    if risk:
        md += [f"Site risk: FEMA flood zone {risk['summary']['site_flood_zone']} (in SFHA: {risk['summary']['site_in_sfha']}).", ""]
    md += ["## Stakeholders"] + [f"- {a[0]}: {a[5]}" for a in ACTORS.values()] + ["", "## Evidence (news, policy, public sentiment)"]
    md += [f"- [{i['type']}, {i['effect']}] {i['summary']} ({i['url']})" for i in alviso["items"]]
    md += ["", "## Engagement options under discussion"] + [f"- {lv['label']}: {lv['why']}" for lv in LEVERS.values()]
    (HERE / "seed.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"seed: {sum(a[1] for a in ACTORS.values())} agents, {len(alviso['items'])} items, social files: {sorted(social) or 'none'}")


if __name__ == "__main__":
    main()
