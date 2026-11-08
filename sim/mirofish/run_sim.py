"""MiroFish-style fallback, NOT MiroFish: transparent agent-based opinion dynamics.

Each agent belongs to a stakeholder group with a stance in [-1, 1].
Step: s_i <- a*anchor_i + (1-a)*(0.6*own-group mean + 0.4*listened-to groups mean) + noise.
Levers shift a group's stance and anchor by stated amounts and change item weights.
Approval proxy = the repo's consent formula (alviso.json) with each item's weight
scaled by how far its mapped groups moved. No LLM, no network, fixed RNG seed.
"""
import json
import pathlib
import random

HERE = pathlib.Path(__file__).resolve().parent
STEPS, SEED, BAND = 50, 7, 0.15


def consent(items, scale=None):
    """Repo formula: S=1-prod(1-w) supportive; O=1-prod(1-w*m) opposition; clamp(0.5+0.5(S-O))."""
    S = O = 1.0
    for i in items:
        w = min(0.95, max(0.0, i["weight"] * (scale or {}).get(i["id"], 1.0)))
        if i["effect"] == "supportive":
            S *= 1 - w
        else:
            O *= 1 - w * (1.0 if i["effect"] == "hard" else 0.6)
    return round(min(1.0, max(0.0, 0.5 + 0.5 * ((1 - S) - (1 - O)))), 3)


def band(x):
    return "GREEN-leaning" if x >= 0.65 else "AMBER" if x >= 0.35 else "RED-leaning"


def clip(x):
    return max(-1.0, min(1.0, x))


def run(seed, name, sc):
    rng = random.Random(SEED)
    actors, levers = seed["actors"], [seed["levers"][k] for k in sc["levers"]]
    shift = {g: sum(lv["stance"].get(g, 0) for lv in levers) for g in actors}
    agents = []  # (group, stance, anchor)
    for g, a in actors.items():
        for _ in range(a["n"]):
            s0 = clip(a["stance"] + rng.gauss(0, 0.1))
            agents.append([g, clip(s0 + shift[g]), clip(s0 + shift[g])])
    items = [dict(i, weight=max(0.0, i["weight"] + sum(lv["items"].get(i["id"], 0) for lv in levers))) for i in seed["items"]]

    def gmean(g):
        v = [a[1] for a in agents if a[0] == g]
        return sum(v) / len(v)

    timeline = []
    for t in range(STEPS + 1):
        st = [a[1] for a in agents]
        timeline.append({"step": t, "support": sum(s > BAND for s in st), "neutral": sum(abs(s) <= BAND for s in st),
                         "oppose": sum(s < -BAND for s in st), "mean": round(sum(st) / len(st), 3)})
        if t == STEPS:
            break
        means = {g: gmean(g) for g in actors}
        new = []
        for g, s, anchor in agents:
            ls = seed["listens"][g]
            social = 0.6 * means[g] + 0.4 * sum(w * means[h] for h, w in ls.items()) / sum(ls.values())
            a = actors[g]["stubborn"]
            new.append(clip(a * anchor + (1 - a) * social + rng.gauss(0, 0.02)))
        for ag, s in zip(agents, new):
            ag[1] = s

    final = {g: round(gmean(g), 3) for g in actors}
    init = {g: actors[g]["stance"] for g in actors}
    # item weight scale: opposition items shrink as mapped groups move toward support (distance 1-s);
    # supportive items grow with (1+s). shortcut: linear ratio, no calibration; upgrade with stakeholder data.
    scale = {}
    for iid, gs in seed["item_actors"].items():
        eff = next(i["effect"] for i in seed["items"] if i["id"] == iid)
        f, i0 = sum(final[g] for g in gs) / len(gs), sum(init[g] for g in gs) / len(gs)
        scale[iid] = round(max(0.0, min(2.0, (1 + f) / (1 + i0) if eff == "supportive" else (1 - f) / (1 - i0))), 3)
    proxy = consent(items, scale)
    opp = sorted((i for i in items if i["effect"] != "supportive"), key=lambda i: -i["weight"] * scale.get(i["id"], 1))
    return {
        "engine": "MiroFish-style fallback, not MiroFish (agent-based opinion dynamics, no LLM)",
        "scenario": name, "label": sc["label"], "levers": [seed["levers"][k]["label"] for k in sc["levers"]],
        "agents": len(agents), "steps": STEPS, "rng_seed": SEED,
        "stance_timeline": timeline,
        "key_actors_final_stance": {actors[g]["label"]: final[g] for g in actors},
        "key_actors_initial_stance": {actors[g]["label"]: init[g] for g in actors},
        "top_opposition_arguments": [{"item": i["id"], "effective_weight": round(i["weight"] * scale.get(i["id"], 1), 3),
                                      "argument": i["summary"][:240], "source": i["url"]} for i in opp[:3]],
        "approval_proxy": {"consent_score": proxy, "band": band(proxy), "item_weight_scale": scale,
                           "note": "repo consent formula with lever-adjusted, stance-scaled weights; heuristic, not a forecast"},
    }


def main():
    seed = json.loads((HERE / "seed.json").read_text(encoding="utf-8"))
    assert abs(consent(seed["items"]) - seed["consent_score_repo"]) < 0.002, "formula does not reproduce repo score"
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    summary = []
    for name, sc in seed["scenarios"].items():
        r = run(seed, name, sc)
        (out / f"{name}.json").write_text(json.dumps(r, indent=1, ensure_ascii=False), encoding="utf-8")
        last = r["stance_timeline"][-1]
        k = r["key_actors_final_stance"]
        summary.append({"scenario": name, "label": r["label"], "support": last["support"], "neutral": last["neutral"],
                        "oppose": last["oppose"], "mean_stance": last["mean"],
                        "residents": k["Alviso residents & neighborhood groups"], "council": k["San Jose City Council"],
                        "env": k["Environmental / water advocates"], "pge": k["PG&E"],
                        "approval_proxy": r["approval_proxy"]["consent_score"], "band": r["approval_proxy"]["band"],
                        "top_argument": r["top_opposition_arguments"][0]["item"]})
    (out / "summary.json").write_text(json.dumps({"engine": "MiroFish-style fallback, not MiroFish",
                                                  "repo_baseline_consent": seed["consent_score_repo"],
                                                  "social_files_used": seed["social_files_used"],
                                                  "scenarios": summary}, indent=1), encoding="utf-8")
    print("| scenario | support/neutral/oppose | mean | residents | council | env | PG&E | approval proxy | top argument |")
    print("|---|---|---|---|---|---|---|---|---|")
    for s in summary:
        print(f"| {s['scenario']} | {s['support']}/{s['neutral']}/{s['oppose']} | {s['mean_stance']} | {s['residents']} | "
              f"{s['council']} | {s['env']} | {s['pge']} | {s['approval_proxy']} {s['band']} | {s['top_argument']} |")


if __name__ == "__main__":
    main()
