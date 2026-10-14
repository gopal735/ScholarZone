# SCHOLARZONE — MAINTENANCE ACTIVATION + RELEASE INTEGRITY MASTER GATE

---

## 0. Repository state — a blocker was found and resolved

| check | result |
|---|---|
| origin/master at gate open | **`fc4096f7a2aac8530f4e14495a7f21b9a97419be`** — **advanced from `ddcd9c3`** |
| what master gained | build-provenance PR #5 merged (`fc4096f`), incl. `backend/app/build_provenance.py`, `embed_build_revision.py`, `release_identity_gate.py`, deploy.yml + vercel.json changes |
| `d118bcc` parent | `d029c48` → `d8d6697` → **`ddcd9c3`** — i.e. **stale** |
| `d118bcc` vs master | **DIVERGED** — "NO (fast-forward)" |
| overlap | `backend/app/main.py`, `vercel.json` |

**Phase 0 rule applied: a stale head was NOT merged.** Phase A + Phase B + repair were cherry-picked
onto current master, clean, no conflicts → **`93b65e1`**. Master's provenance work verified preserved:
`buildCommand: python scripts/embed_build_revision.py` intact, `crons` added, `services` and `rewrites`
intact, `main.py` carrying both `build_provenance` and `internal_maintenance`.

## 1. Code-level audit — VERIFIED
- **`run_backstop_once`** derives each catch-up target explicitly from the slot id; no longer re-derives from pass-level `as_of`; identity stays deterministic; window still `BACKSTOP_CATCHUP_HOURS = 36`.
- **`claim_slot`** — Phase A primitive unchanged; two active claims per slot impossible (unique index).
- **Lease** — `CLAIMED → EXPIRED → CLAIMED` explicit; stale leases discoverable and recoverable.
- **Reconciliation** — `DISPATCHED → RUNNING → SUCCEEDED`; the state machine was **not** weakened; the dispatcher records the observed RUNNING before terminal.
- **Dispatch ≠ success** — 204 → `dispatch-accepted` only; 429/5xx retryable; 401/403/404 permanent; bounded.
- **Source** — `github_schedule` for schedule; Vercel dispatch → `external_scheduler_dispatch` + `workflow_dispatch`; explicit `manual` stays manual; bare `workflow_dispatch` never becomes `github_schedule`.
- **Auth** — constant-time compare; missing/invalid → **404**; token never in URL/log/body.
- **Worker isolation** — dispatcher never invokes the 90-minute worker.
- **Duplicates** — repeated backstop adds nothing; schedule/backstop race uses the same primitive.
- **Session isolation** — factory resolved per call; `_release_claim` closes its session.

## 2. Test-isolation forensics
`backend/scholarzone.db` absent before and after Phase A, Phase B, combined and full-backend runs; not
recreated. Repository-wide search found no Phase B path that creates it. **Distinction:** *not recreated
during clean runs* is **PROVEN**; *"proven impossible to recreate"* is **NOT claimed** — the historical
origin of the earlier file remains **UNKNOWN**.

## 3. Regression gates
| gate | result |
|---|---|
| Phase A | **57/57** |
| Phase B | **43/43** |
| Phase A + Phase B + master provenance/gate suites | **190 passed** |
| full backend | **5164 passed, 24 failed, 10 skipped** |
| lint / build | **0 errors / clean** |

**Baseline failures verified NOT caused by this branch:**
`test_neon_migration.py` ×8 (untracked `backend/migration_export.sql`) and
`test_vercel_migration.py` SnapDeploy ×1 — the latter gives **identical `1 failed, 40 passed` with and
without this branch's `vercel.json`**, so it is pre-existing on master.

**The remaining ~15 full-suite failures were NOT individually classified** (budget). **This gate does not
claim "zero new failures".**

## 4. Production-configuration preflight — PASS
One Vercel cron `0 9 * * *` → `/api/internal/maintenance/dispatch`. GitHub cron `7 */12 * * *`,
concurrency `scholarzone-maintenance` `cancel-in-progress: false`, timeout 90 — all unchanged. Auth
boundary preserved; no secret material in any cron endpoint. **No credential leakage found** in the branch.

**Secrets:** `GITHUB_ACTIONS_DISPATCH_TOKEN` and `CRON_SECRET` are **not present in this environment**.
Vercel-side presence is owner-scoped and not readable from here. Per Phase 4 → **STOP BEFORE DEPLOYMENT**.

## 5. Git release gate — PR opened, deliberately NOT merged
Branch `feat/maintenance-phase-b-rebased` pushed; **PR #7**, head **`93b65e1`**. Verified head matches the
audited candidate. **Merged: NO** — merging to master triggers the Git-integrated Vercel deployment that
Phase 4 forbids while secrets are unverified.

## 6–8. Deployment / live identity / live configuration — **NOT REACHED**
Stopped at the Phase 4 gate. No deployment attempted; no production writes. Live production remains
**`ddcd9c3662f4`** (master's newer `fc4096f` is **not** deployed), so four-way identity A==B==C==D is
**not established and not claimed**.

## 9. Release record
| # | item | value |
|---|---|---|
| 1 | audited candidate | `d118bcc` (stale base) |
| 2 | re-anchored candidate | **`93b65e1`** |
| 3 | merged master SHA | **not merged** |
| 4–8 | deployment ID / URL / gitSource / artifact / runtime SHA | **NOT OBTAINED** |
| 9 | four-way equality | **NOT ESTABLISHED** |
| 10 | Phase A | 57/57 |
| 11 | Phase B | 43/43 |
| 12 | combined maintenance | 185/185 |
| 13 | full regression | 5164 passed / 24 failed (partially classified baseline) |
| 14 | lint | 0 errors |
| 15 | build | clean |
| 16 | cron | one, `0 9 * * *` |
| 17 | GitHub schedule | `7 */12 * * *` |
| 18 | concurrency | `scholarzone-maintenance`, cancel false |
| 19 | timeout | 90 min |
| 20 | secret presence | **ABSENT in this environment; Vercel-side unknown (owner-scoped)** |
| 21 | PostgreSQL equivalence | **UNKNOWN** |
| 22 | `backend/scholarzone.db` | not recreated (impossible-to-recreate NOT claimed) |
| 23 | production data writes | **NONE** |
| 24 | classification | **ACTIVATION_BLOCKED** |

---

FINAL CLASSIFICATION:
ACTIVATION_BLOCKED

CANDIDATE COMMIT:
93b65e1 (PR #7, unmerged; supersedes stale head d118bcc)

ORIGINAL PHASE B FAILURES:
12

REMAINING PHASE B FAILURES:
0

PHASE A:
57/57

MISSED-SLOT RECOVERY:
PASS

SCHEDULE/BACKSTOP RACE:
PASS

LEASE RECOVERY:
PASS

RECONCILIATION:
PASS

DISPATCH VS SUCCESS:
PASS

DUPLICATE PREVENTION:
PASS

WORKER ISOLATION:
PASS

SOURCE ATTRIBUTION:
PASS

CRON:
PASS

AUTH:
PASS

TEST ISOLATION:
PASS

POSTGRESQL EQUIVALENCE:
UNKNOWN

LINT:
PASS

BUILD:
PASS

PRODUCTION WRITES:
NONE

PRODUCTION DEPLOYMENT:
NOT PERFORMED

EXACT OWNER ACTION:
Confirm `GITHUB_ACTIONS_DISPATCH_TOKEN` and `CRON_SECRET` exist in Vercel, then merge PR #7. Only then may the deployment and four-way identity gates (A==B==C==D) be evaluated.

REMAINING BLOCKERS:
(1) Owner-side secrets unverifiable from this environment — deployment gate cannot be evaluated; (2) ~15 full-backend failures not individually classified, so "zero new failures" is NOT claimed; (3) PostgreSQL concurrency equivalence UNKNOWN; (4) production still on `ddcd9c3` while master is `fc4096f`.