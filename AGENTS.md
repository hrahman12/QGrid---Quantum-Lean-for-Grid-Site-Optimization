# AGENTS.md (QSiteProof)

Coordination: Google Doc "== AGENT CHANNEL ==" (issue #1 still mirrored). Plan: README.md. Status and checkpoints: STATUS.md (`python scripts/status.py`).

## Lanes
| Lane | Owner | Folders |
|---|---|---|
| L1 site + live grid + pandapower | Alejandro | `site/`, `grid/` |
| L2 missing site + live grid data | Manu | `data/` |
| L3 PsiQDK + Lean 4 | Hannah | `quantum/`, `lean/` |
| Shared | everyone, via `[CONTRACT]` | `contracts/`, `fixtures/`, `pipeline.py`, `scripts/` |

Only touch your lane's folders.

## Stage interfaces (`pipeline.py` calls these; plain dicts matching `contracts/*.schema.json`)
```python
grid/snapshot.py   get_snapshot(site) -> grid_snapshot
quantum/search.py  propose(site, snapshot, constraints) -> candidate_plan   # constraints: list[str] of past blocking conditions
grid/physics.py    check(plan, snapshot) -> physics_result
lean/certify.py    certify(plan, physics, site) -> certificate
```
If a module or function doesn't exist yet, `pipeline.py` uses `fixtures/<name>.json` and labels that stage `FIXTURE` in the summary. Never present a FIXTURE stage as a measured result.

## Contracts
- Change `contracts/` or `fixtures/` only after posting a `[CONTRACT]` comment on issue #1 that says what changes and why. Update schema, example and fixture in the same PR.
- A GREEN certificate covers only the encoded rules. It is not a utility interconnection approval.

## Commands
`./run.sh setup|validate|test|pipeline` (Windows: `.\run.ps1 ...`). Run `validate` and `test` before every PR. `pipeline` writes to `runs/<UTC timestamp>/` (gitignored).

## Git
Use one branch per lane (`l1-...`, `l2-...`, `l3-...`). Open small PRs to `main`; never push straight to `main` (ORCH tests and merges). Never force-push.

## Status to issue #1
```sh
gh issue comment 1 --repo hrahman12/QGrid---Quantum-Lean-for-Grid-Site-Optimization --body "[L1·Alejandro] 14:05 ✅ what changed | PR #n | ⛔ none"
```
Use ✅ for done, 🟡 for in progress and ❌ for blocked. Put the blocker after ⛔.

## No secrets
Keep keys and tokens out of commits, comments and WhatsApp. Use `.env` (gitignored). Cache fetched data to files so the demo runs offline.
