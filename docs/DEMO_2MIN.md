# QSiteProof: 2-minute demo script

Setup (before you go on stage, 1 minute):
1. `git pull` then `.\run.ps1 demo` (Windows) or `./run.sh demo` (Mac/Linux). All steps run offline.
2. `cd ui; python -m http.server 8765` and open http://localhost:8765 full screen (3D view).
3. Keep a terminal with `python scenarios/edge_alviso.py` output ready (or report/summary.html in a second tab).
4. Reset the 3D page: curtailment 0%, +20% toggle off.

## 0:00-0:20 The problem (3D view, top)
"About $3 trillion is going into data centers by 2030, and $130 billion of US projects stalled in a single quarter this year. The bottleneck isn't money, it's power and consent. A developer asks: can I get **150 MW** here in North San Jose, **how much, and how soon**?"
Point at the site beacon (150 MW, FEMA flood zone AE) and the substation pillars.

## 0:20-0:45 The honest no (3D view, left panel)
"Our pipeline finds a plan, checks it with a real power-flow simulation, and certifies it against written rules. For 150 MW at transmission the answer today is **RED**: firm N-1 capacity is **45 MW short**, even with 50 MW of batteries and 15 MW of curtailment. Most tools would have told you yes."
Point at "150 MW at transmission today: RED · firm_n1". Red pillars = transformers already at 0 MW.

## 0:45-1:15 The agent learns (terminal: edge loop)
"So it looks for the yes-if at distribution, using PG&E's own grid data. Round 1: it picks Nortech feeders; the bank they share is already full, **RED**. That becomes a constraint. Round 2: Lawrence bank 1 is full, **RED**. Round 3: **GREEN, 16 MW** on three Lawrence feeders. Feeders look like 376 MW of capacity; the transformers above them only have 38.8. The agent learns that limit round by round."

## 1:15-1:40 The moving landscape (3D view, controls)
Click curtailment **2%**: "Accept curtailment in about 2% of hours, 98% availability, and it's **47.6 MW**." Click **0%** again, toggle **+20% growth**: "But utility forecasts were made before AI data centers. If load grows 20% more, it drops to **7.4 MW**. Same site, same day."
Mention consent: "Consent layer: AMBER. San Jose's draft standards and local opposition are negotiable: a community benefit agreement, recycled-water cooling, clean supply, heat reuse."

## 1:40-2:00 Any country, and what's real
"It works for any country: Frankfurt comes back **AMBER, yes if 25 MW of storage is committed**; Johor, Malaysia **AMBER, yes if 5 MW of curtailment is committed**.
Find with a Grover search, check with power flow, prove with Lean rules. Every verdict says which engine ran and which numbers are assumptions. We never claim utility approval, only a defensible yes, yes-if, or no."

## If asked
- Quantum: Grover search runs on a simulator (PsiQDK); no quantum advantage claimed at this size.
- Lean: the laptop shows which engine ran (Lean 4 or the Python mirror of the same rules).
- Data: PG&E GRIP 2028 forecast (directional), OSM substations, CAISO NP15, FEMA, Data Center Watch; ratings not from GRIP are labelled ASSUMED.
