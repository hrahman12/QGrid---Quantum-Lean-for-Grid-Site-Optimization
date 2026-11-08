# QGrid - Quantum-Lean for Grid Site Optimization

## QSiteProof

**Quantum-assisted + Lean-verified site-to-grid integrability in one wrapper.**

> Can this site connect the requested load sooner using existing grid flexibility - and can we formally certify the resulting obligations?

QSiteProof is a proposed one-day hack prototype that combines PsiQDK search, pandapower physical checks, and Lean 4 formal certification. The goal is to find a connect-sooner path using flexibility and existing infrastructure before defaulting to a new transmission corridor.

**Status:** Concept and prototype plan. The architecture, certificate, and evaluation below describe the intended workflow, not completed implementation or measured results.

[Read the original one-page concept plan (PDF)](docs/QSiteProof_Final_Plan_Updated.pdf).

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
