# QSiteProof status board

Updated by the orchestrator (ORCH). Last update: 14:17 PT, Sunday 8 Nov 2026.
See it in your terminal with `git pull && python scripts/status.py` (add `--run` to also run the pipeline).
Coordination: Google Doc "== AGENT CHANNEL ==" (append-only, tag + PT time). Goal: functional end to end by **3:30 PM PT**. Demos 6:30 PM.

## What we're building, in simple terms
A data-center developer asks: "I want 150 MW at this site in North San Jose (Alviso). Can I get power, how much, and how soon?"
QSiteProof answers in three steps:
1. **Find**: a search (quantum with PsiQDK, classical as baseline) tries combinations of levers: split the load across nearby substations and feeders, accept a few hours of curtailment, add a battery, uprate lines.
2. **Check**: a power-flow simulation (pandapower) tests each candidate on the real local grid: no overloaded lines, voltages OK, still works if one line fails (N-1).
3. **Prove**: Lean 4 checks the plan against written rules (capacity per transformer, curtailment window, flood zone, deadlines) and gives a verdict:
   - **GREEN** = yes as is
   - **AMBER** = "yes, if": only negotiable rules fail, and it lists the conditions that make it a yes
   - **RED** = hard no, with the exact rule that blocks it

Each RED teaches the next search round, so the agent gets better every run (judges score "learning").
**Headline so far** (PG&E GRIP data, directional): of the 150 MW, about **38.8 MW** fits on the local distribution grid now as ~6 edge sites, **47.6 MW** if the site accepts curtailment in ~2% of hours (98% availability), the rest needs transmission (7-10 years). The site is in FEMA flood zone AE.
**Why it matters**: about $3T is going into data centers by 2030, and $130B of US projects stalled in Q1 2026 alone. The bottleneck is power and consent; we find the projects that can still get to yes and what it takes.

## Checkpoints (PT)
- [x] 1:45 every lane runs on fixtures
- [x] 2:30 each real stage works alone (all 4 live as of 14:15)
- [x] Integration on main: python pipeline.py runs all stages live -> GREEN (search 64 evals, 75+75 MW Northern Receiving + Los Esteros, DLR, max loading 71%, N-1 pass, 7/7 rules)
- [ ] 3:00 feedback loop shown: a RED that becomes a constraint, then GREEN/AMBER (edge-site / distribution case)
- [ ] 3:30 functional end to end: `python pipeline.py` with every stage live, one GREEN/AMBER and one RED shown

## L1 Alejandro: site + grid + physics
- [x] Shared contracts, fixtures, validator, pipeline (PR #2, #9)
- [x] Site list with Alviso 150 MW first; OSM substations, lines, data centers + HIFLD lines cached (PR #7)
- [x] PG&E GRIP pack: substations, 97 feeders, 24 transformer banks, forecasts (PR #8)
- [x] pandapower check with N-1: live run converges, max loading 71%, voltage 0.99-1.02 pu
- [ ] Physics on the distribution side (GRIP feeders and banks with the curtailment window)
- [ ] Run each plan under 2 scenarios (published forecast vs +20% data-center growth)
- [ ] Map / one-screen summary for the demo

## L2 Manu (VM): data
- [x] Substation ratings, 51 substations with sources (PR #4)
- [x] CAISO queue hints (PR #5)
- [x] Live CAISO signal, NP15 hub, cached (PR #6, #11)
- [x] 2025 CAISO stress hours + offline tests (PR #11)
- [x] Curtailment vs capacity curve: 38.8 -> 47.6 -> 66.2 -> 90.6 MW (PR #12)
- [x] Site risk: FEMA flood zone AE, no fire-threat district (PR #13)
- [x] One joined input file for search + rules, data/l2/l3_inputs.json (PR #14)
- [ ] ~~Classical fallback~~ no longer needed (L3 landed). NEW: edge-site run over GRIP banks/feeders (per-bank caps from l3_inputs.json) through L3's propose/certify, showing naive RED -> constraint -> GREEN/AMBER; plus +20% load-growth scenario

## L3 Hannah: quantum search + Lean
- [x] PsiQDK 2.5.0 + Lean 4.35 + pandapower installed (WSL)
- [x] quantum/search.py propose() with PsiQDK Grover, baselines, yield metric (merged 14:06)
- [x] lean/certify.py + Lean 4 project (6 theorems); python mirror when Lean isn't installed
- [ ] Tag each rule hard or negotiable and add AMBER ("yes, if" + conditions)
- [ ] Feedback loop shown in pipeline output (RED -> constraint -> next round)
- [ ] Lean Green Yield: classical vs PsiQDK on the same budget

## Never claim
Quantum advantage; utility or PG&E approval; real substation ratings where we assumed them; numbers we didn't run.
