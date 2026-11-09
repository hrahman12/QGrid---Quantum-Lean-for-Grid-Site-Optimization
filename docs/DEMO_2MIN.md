# QSiteProof: 2-minute demo script

Audience: non-technical decision-makers (investors, developers, policymakers).
Screen: the 3D page (ui/index.html, or the team's trycloudflare link). Backup: ui/decision.html (opens offline, double-click).
Before you start: page at the top, curtailment 0%, "+20% growth" off.

## 0:00-0:15 The question
"$3 trillion is going into data centers by 2030, and $130 billion of US projects stalled in a single quarter this year. The bottleneck isn't money: it's power, permits and consent.
A developer asks us: **can I get 150 megawatts here, in North San Jose, by mid-2028?**"

## 0:15-0:35 The answer, in one light
Point at the traffic light: **AMBER: yes, if.**
"Not 150 megawatts today. **38.7 megawatts now**, across 9 smaller edge sites. Here's why, in colors."
- **Grid power RED**: "the big substations are 45 megawatts short if one transformer fails."
- **Edge sites GREEN**: "38.7 megawatts fit today on the local grid."
- **Flexibility AMBER**: "accept a few hours of curtailment a year and it's 47.6."
- **Future load RED**: "if demand grows 20% more than the utility planned, it drops to 7.4."
- **Nature & climate RED**: "a wildlife refuge 300 meters away, wetlands, very high flood risk."
- **Community AMBER** and **Socioeconomic AMBER**: "negotiable, with conditions."
- **Timeline RED**: "new transmission takes 7 to 10 years."

## 0:35-1:00 How it decided (the agent learns)
Scroll to the edge-site loop, press Play.
"Our agent proposes a plan, a power-grid simulation checks it, and a proof engine certifies it against written rules. Round 1: RED, that transformer is already full. Round 2: RED again. Round 3: **GREEN, 16 megawatts.** Every 'no' becomes a rule for the next try. On paper the feeders look like 430 megawatts; the transformers above them only have 39. The agent learns that by itself."

## 1:00-1:20 The moving landscape
Click curtailment **2%**: "Accept 2% curtailment: 47.6 megawatts."
Back to **0%**, turn on **+20% growth**: "But utility plans were written before AI data centers. If load grows 20% more: 7.4 megawatts. Same site, same day. Decisions need to be re-checked, not assumed."

## 1:20-1:45 What makes it a YES
Scroll to the scenarios / "What makes it a YES".
"We simulated how the community, the city and the utility react to different plans. Baseline: AMBER, most groups opposed. A community benefit agreement helps residents; recycled-water cooling and heat reuse help environmental groups; starting smaller at the edge brings the utility on board. **All of it together reaches GREEN-leaning, with no group opposed.** No single lever does it alone."

## 1:45-2:00 Close
"It works anywhere: Frankfurt and Johor come back 'yes, if' too. QSiteProof turns grid, climate, nature, economic and community data into one honest answer: **yes, yes-if, or no**, and exactly what it takes to get to yes. It's a screening tool, not a utility approval, and it never claims what it didn't check."

## If asked (one line each)
- Data: PG&E's public grid capacity data, OpenStreetMap substations, CAISO prices, FEMA, US Fish & Wildlife, protected-area data, satellite land-change data (AlphaEarth), Census, EIA, CalEnviroScreen, public social posts and local news.
- Quantum: the search runs on a quantum simulator (PsiQDK); no quantum advantage claimed. At 150 MW no plan is feasible, so it runs classical, and says so.
- Proof: Lean 4 checks all 11 rules on our Linux machine; laptops run the same rules in Python and the screen says which ran.
- Simulation: stakeholder agents are a scenario tool, not a forecast (MiroFish-style; full MiroFish needs a Zep key).
- Weak spots we label: water stress is unverified; ratings outside PG&E data are assumptions; consent weights are judgments.

## Setup (1 minute before)
1. `git pull`, then `.\run.ps1 demo` (Windows) or `./run.sh demo` (Mac/Linux). Everything runs offline.
2. Open the 3D page (the team link, or `cd ui; python -m http.server 8765` then http://localhost:8765), full screen.
3. Backup: double-click ui/decision.html.
