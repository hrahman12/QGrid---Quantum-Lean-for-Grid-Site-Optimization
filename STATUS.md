# QSiteProof status board

Updated by the orchestrator (ORCH). Last update: 15:02 PT, Sunday 8 Nov 2026.
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
**Headline so far** (PG&E GRIP 2028 forecast; conditional screening estimates, directional): 150 MW at transmission is **RED** today (N-1 firm capacity: 19.9 MW firm at each candidate substation). At distribution, **38.7 MW** fits across 9 edge sites with every transformer bank within its cap; **47.6 MW** with ~2% curtailment (98% availability); only **7.4 MW** if load grows 20% beyond the utility forecast. Edge loop demo: RED (Nortech bank full) -> RED (Lawrence bank 1 full) -> GREEN 16 MW. Consent layer: Alviso 0.47 and NOVVA 0.43, both AMBER (heuristic score). Site is in FEMA flood zone AE.
**Why it matters**: about $3T is going into data centers by 2030, and $130B of US projects stalled in Q1 2026 alone. The bottleneck is power and consent; we find the projects that can still get to yes and what it takes.

## Checkpoints (PT)
- [x] 1:45 every lane runs on fixtures
- [x] 2:30 each real stage works alone (all 4 live as of 14:15)
- [x] Integration on main: python pipeline.py runs all stages live -> GREEN (search 64 evals, 75+75 MW Northern Receiving + Los Esteros, DLR, max loading 71%, N-1 pass, 7/7 rules)
- [x] 3:00 feedback loop shown: scenarios/edge_alviso.py RED -> RED -> GREEN 16 MW (PR #20); pipeline loop with rounds.json (PR #22)
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
- [x] Edge-site loop scenarios/edge_alviso.py (PR #20); live-pull cache fix (PR #19); feeder->bank link fix (PR #15)

## L3 Hannah: quantum search + Lean
- [x] PsiQDK 2.5.0 + Lean 4.35 + pandapower installed (WSL)
- [x] quantum/search.py propose() with PsiQDK Grover, baselines, yield metric (merged 14:06)
- [x] lean/certify.py + Lean 4 project (6 theorems); python mirror when Lean isn't installed
- [ ] Tag each rule hard or negotiable and add AMBER ("yes, if" + conditions)
- [ ] Feedback loop shown in pipeline output (RED -> constraint -> next round)
- [ ] Lean Green Yield: classical vs PsiQDK on the same budget

## Adversarial review (Astra, 14:50) and fixes
- [x] #1 edge sites now allocated per transformer bank (PR #21)
- [x] #3 N-1 checks firm transformer capacity (PR #21) -> 150 MW now honestly RED
- [x] #10 pipeline feedback loop + #8 honest labels: Lean vs Python mirror, PsiQDK vs fallback, screening estimates (PR #22)
- [ ] #2 bank rule inside certify + hard/negotiable tags + AMBER, #6 shared net-load model, #5 storage bound, #4 hash binds plan/site/snapshot, #9 honest yield (branch orch-fix-l3, in progress)
- [ ] Search respects firm N-1 caps so the 150 MW loop reaches AMBER/RED with the exact gap (orch-fix-l3)
- [ ] One-command demo + summary with both loops, growth, consent (orch-demo-flow)
- [x] Consent layer: data/shared/socio/ (Alviso, NOVVA) + NOVVA facts and footprints (PR #23). Social media/radio: public web only (Reddit mirror, station websites); no X/Facebook/radio audio.

## Never claim
Quantum advantage; utility or PG&E approval; real substation ratings where we assumed them; numbers we didn't run.
