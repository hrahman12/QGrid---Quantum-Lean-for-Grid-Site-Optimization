# Stakeholder engagement simulation: Alviso / North San Jose

> **Engine: MiroFish-style fallback, not MiroFish.** This is a transparent agent-based
> opinion-dynamics model in plain Python. It uses no LLM.

## Why MiroFish did not run

[MiroFish](https://github.com/666ghj/MiroFish) was cloned on the AWS box. Its backend
(`backend/app/config.py`) refuses to start without `ZEP_API_KEY`, and it rejects
`ZEP_API_URL`, so it only works with Zep Cloud and cannot use a self-hosted Zep.
It needs Zep to build the knowledge graph, read entities and generate agent profiles.
We had no Zep Cloud key, so MiroFish could not run in the time we had.
An LLM key alone is not enough.

**To run the real thing later:**
1. Get a Zep Cloud key.
2. Set `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL_NAME` and `ZEP_API_KEY` in MiroFish's local `.env`.
3. Run `docker compose up -d`.
4. Upload `seed.md` as the seed document and ask: "How do stakeholders react to the 150 MW proposal, and which engagement turns opposition into acceptance?"
5. Keep the run small: under 40 rounds.

## How to run

```
python sim/mirofish/build_seed.py   # repo data -> seed.json (+ seed.md for MiroFish)
python sim/mirofish/run_sim.py      # seed.json -> results/<scenario>.json + results/summary.json
```

Standard library only. The RNG seed is fixed, so runs are deterministic.

## What is simulated

**Inputs**
- `data/shared/socio/alviso.json`: 11 consent items covering news, policy and public sentiment.
- `data/l2/site_risk.json`: flood zone AE.
- The `STATUS.md` grid headline: 150 MW at transmission is RED; 16 to 38.7 MW fits at distribution.
- `data/shared/social/*.json` was not on `main`, `origin/orch-social` or `origin/orch-socio` at build time, so this run uses `alviso.json` only. If those files exist, `build_seed.py` copies them into `seed.json` for provenance (`social_files_found_not_used`), but `run_sim.py` does not use them yet because their schema was unknown at build time. Next step: load `ACTORS` and `LISTENS` from `stakeholders.json`.

**Agents**
- 38 agents in 10 stakeholder groups: residents, environmental/water advocates, r/sanjose commenters, City Council, Mayor, Planning, PG&E, CPUC/ratepayer advocates, labor and the developer.
- Each group's starting stance, stubbornness and source items are in `build_seed.py`, in `ACTORS`.
- Labor has no source item; it is ASSUMED.

**Dynamics, 50 steps**
- Each step, every agent's new stance is a mix of three things: its anchor, 60% of its own group's mean and 40% of the mean of the groups it listens to (`LISTENS`, ASSUMED).
- Small noise is added each step.

**Levers**
- Each lever moves specific groups' stance and anchor by stated amounts and changes specific item weights (`LEVERS`, ASSUMED, each with a one-line rationale):
  - CBA + local hiring
  - recycled-water/closed-loop cooling + heat reuse
  - edge phase of 16 to 38 MW at distribution + generator limits of 25 h/yr

**Approval proxy**
- The proxy is the repo's own consent formula from `alviso.json`. Each item's weight is adjusted by the levers, then scaled by how far the item's mapped groups moved.
- `run_sim.py` asserts that the unmodified formula reproduces the repo baseline of 0.469.

**Scenarios**

| id | scenario |
|---|---|
| S0 | 150 MW, gas backup, no engagement |
| S1 | + community benefit agreement + local hiring |
| S2 | + recycled-water/closed-loop cooling + heat reuse |
| S3 | 16 to 38 MW edge phase + generator limits |
| S4 | all levers |

**Output per scenario** (`results/<scenario>.json`)
- Stance distribution over time: the support/neutral/oppose count at each step.
- Each key actor's final stance.
- The top 3 remaining opposition arguments, quoted from sourced items.
- The approval proxy and its band.

## Results

All 38 agents. The group columns show each group's mean final stance on a scale from -1 (oppose) to +1 (support).

| scenario | support/neutral/oppose | mean | residents | council | env | PG&E | approval proxy | top remaining argument |
|---|---|---|---|---|---|---|---|---|
| S0 baseline | 13/1/24 | -0.167 | -0.376 | 0.186 | -0.526 | 0.239 | 0.475 AMBER | a-sj-draft-standards |
| S1 CBA + hiring | 14/9/15 | -0.027 | -0.139 | 0.323 | -0.464 | 0.251 | 0.511 AMBER | a-pge-rule30 |
| S2 water + heat | 14/1/23 | -0.028 | -0.219 | 0.327 | -0.226 | 0.253 | 0.521 AMBER | a-pge-rule30 |
| S3 edge phase | 14/2/22 | -0.063 | -0.235 | 0.209 | -0.382 | 0.480 | 0.552 AMBER | a-alviso-opposition |
| S4 all levers | 22/16/0 | 0.215 | 0.159 | 0.486 | -0.020 | 0.505 | 0.668 GREEN-leaning | dcw-q1-2026 |

**Readout**
- No single lever leaves AMBER in this model.
- S3 (edge phase) has the highest single-lever proxy. It brings PG&E and ratepayer advocates on board, but Alviso residents' opposition remains.
- S2 does the most for environmental groups.
- S1 does the most for residents and labor.
- Only S4 (all levers) removes every opposing agent. The remaining top argument in S4 is the national opposition backdrop, which is context the local levers cannot change.

Compare scenarios against S0, not against the repo's 0.469. With no engagement, S0 still drifts to 0.475 because the averaging pulls opposed groups toward the middle.

## LLM used

None. No API key is used, read or stored by this code.

## Limits

- These agents are rule-following numbers, not people, and not LLM personas either. This is a scenario-exploration tool, **not a forecast** of any vote or of public opinion.
- Every stance, influence weight and lever shift is an ASSUMED analyst judgment. Change them in `build_seed.py` and re-run.
- Lever effects are counted twice: a lever changes item weights directly, and it also moves the stances that scale those same items. S4 clearing 0.65 (0.668) depends on this, so do not read "GREEN-leaning" as a solid result.
- The approval proxy inherits the heuristic consent formula. It is not a validated model.
- 38 agents, 50 steps and one site. The results are sensitive to the `LISTENS` weights and stubbornness values; no sensitivity sweep was run.
