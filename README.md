# QGrid - Quantum-Lean for Grid Site Optimization

## QSiteProof

**Quantum-assisted + Lean-verified site-to-grid integrability in one wrapper.**

> Can this site connect the requested load sooner using existing grid flexibility - and can we formally certify the resulting obligations?

QSiteProof is a proposed one-day hack prototype that combines PsiQDK search, pandapower physical checks, and Lean 4 formal certification. The goal is to find a connect-sooner path using flexibility and existing infrastructure before defaulting to a new transmission corridor.

**Status:** Concept and prototype plan. The architecture, certificate, and evaluation below describe the intended workflow, not completed implementation or measured results.

[Read the original one-page concept plan (PDF)](docs/QSiteProof_Final_Plan_Updated.pdf).

## Case study: North San Jose, Santa Clara County, California

**Selected study area: North San Jose / Alviso.**

> Can a new high-density compute site connect sooner by splitting its requested load across multiple substations and combining existing-grid flexibility, while satisfying formally encoded interconnection and permitting constraints?

### Why this location

- **PG&E capacity screening:** PG&E lists San Jose and Alviso in its service area. Use PG&E GRIP / ICA data to screen candidate connections within PG&E electric territory. Sources: [PG&E service area](https://www.pge.com/en/featured/pge-service-area.html), [PG&E GRIP](https://grip.pge.com/).
- **CAISO signals:** Use live / near-live demand, prices, and congestion context from [GridStatus.io's CAISO dashboard](https://www.gridstatus.io/live/CAISO).
- **Real compute geography:** San Jose's published data-center applications include projects in the Alviso area, providing a concrete setting for a large compute-load study. Source: [City of San Jose data-center and large energy-use projects](https://www.sanjoseca.gov/your-government/departments-offices/planning-building-code-enforcement/planning-division/data-center-and-other-large-energy-use-projects).
- **Substation-splitting question:** Evaluate multiple candidate substations and load allocations against a single-connection baseline, directly addressing **RFQ 2.2: split one large load across several substations**. Candidate connection points and their feasibility will be established during the study.
- **Permitting layer:** Encode the site's applicable zoning, hazard, right-of-way (ROW), deadline, and interconnection conditions as Lean obligations, using San Jose-specific evidence and rules.
- **Nearby comparison case:** The [Energy Hack Track 1 resources](https://github.com/arhamshah08/energy-hack/blob/main/tracks/1-sites/README.md) include City of Santa Clara data-center zoning and permitting material. Use that as a comparison with its own jurisdiction and utility context.

### Utility and jurisdiction boundary

**Santa Clara County** identifies the county containing this North San Jose case study. The **City of Santa Clara** is a separate municipality whose municipal utility, **Silicon Valley Power**, supplies electricity within its city boundaries. A City of Santa Clara comparison requires its own utility data and permitting rules. Source: [California Energy Commission review of Silicon Valley Power's Integrated Resource Plan](https://efiling.energy.ca.gov/GetDocument.aspx?DocumentContentId=102957&tn=265948).

The primary electrical-capacity layer for the North San Jose / Alviso study is PG&E GRIP / ICA. Treat its hosting-capacity values as screening estimates; establish site-specific connection feasibility through the grid model and utility study process. See the [Energy Hack Track 2 capacity-data guidance](https://github.com/arhamshah08/energy-hack/blob/main/tracks/2-grid-capacity/README.md).

### Proposed 150 MW demo

**150 MW North San Jose compute site** → **PsiQDK searches substation splits / flexibility** → **pandapower verifies grid feasibility** → **Lean 4 certifies the encoded obligations** → **SITE INTEGRABLE 🟢**, if all required checks pass.

The 150 MW request is an illustrative scenario input. A rejected candidate returns its blocking condition for the next search iteration.

## One wrapper - three engines

| Stage | Engine / inputs | Role |
| --- | --- | --- |
| **Input** | Site + live grid | Requested MW, candidate substations, GridStatus.io signals, flexibility options, and connection deadline. |
| **Find** | PsiQDK | Grover search / amplitude amplification over load splits, DLR, storage, curtailment, and topology choices. |
| **Check physics** | pandapower | Validate power flow, thermal limits, voltage limits, and N-1 contingency performance. |
| **Prove** | Lean 4 | Check encoded capacity, flexibility, deadline, right-of-way (ROW) / permitting conditions, and penalty-trigger rules; produce a GREEN / RED result. |

### What PsiQDK contributes

- Searches the discrete planning space instead of quantumizing AC power flow.
- Encodes substation splits, DLR, reconductoring, storage, curtailment, and topology choices.
- Returns a candidate plus fault-tolerant quantum computing (FTQC) resource estimates, such as logical resources and Active Volume.
- Can use Lean failure conditions as new constraints for the next search.

### What Lean 4 contributes

- Acts as the final trust boundary: AI / quantum search cannot self-certify.
- Proves encoded obligations only after the candidate passes physical grid checks.
- Returns the exact blocking condition when a plan is rejected.
- Produces a proof-backed GREEN / RED site-integrability result for the encoded rules.

Formal certification is scoped to the encoded obligations and supplied evidence. Physical grid feasibility is checked separately with pandapower.

## Example final certificate

*Illustrative output from the concept plan; not the result of an executed grid study.*

| Check | Example result |
| --- | --- |
| Requested capacity | PASS |
| Thermal / voltage | PASS |
| N-1 reliability | PASS |
| Flexibility commitment | PASS |
| Permit / ROW condition | PASS |
| Penalty trigger | FALSE |
| **Final result** | **GREEN - SITE INTEGRABLE** |

## Hack metric: Lean Green Yield

Compare how many candidates become formally certifiable plans per expensive verification cycle across:

1. Random search.
2. A classical heuristic.
3. PsiQDK-assisted search.

## Hack fit

- **Primary track:** Track 2 - Assess grid capacity at the edge.
- **Search core:** RFQ 2.2 - Does splitting one large load across several substations connect more of it?
- **Overall framing:** X.1 - From site to plan: choose sites, check their capacity, and add the flexibility needed to connect sooner, spanning Tracks 1 + 2 + 3.

QSiteProof uses PsiQDK for the RFQ 2.2 search core, pandapower to check physical feasibility, and Lean 4 to certify the encoded interconnection, penalty, and permitting obligations.

**Find quantumly. Check physically. Prove formally.**
