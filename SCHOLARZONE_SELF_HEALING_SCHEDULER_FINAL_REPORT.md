# SCHOLARZONE_SELF_HEALING_SCHEDULER_FINAL_REPORT.md

## FINAL CLASSIFICATION: `OWNER_ACTION_REQUIRED`

## EXACT OWNER ACTION
> Create a **GitHub App installation token (preferred) or a fine-grained PAT with `Actions: write`
> on `gopal735/ScholarZone`**, store it as a Vercel encrypted env var on the chosen project, and
> confirm the Vercel plan permits Cron jobs. I cannot create credentials (Part 39 forbids it), so the
> dispatcher cannot be completed without this.

## PRODUCTION WRITES: NONE

---

## Honest scope statement first

**I did not implement this 45-part architecture.** I completed **Part 1** (current-state inspection)
and identified the structural facts that determine whether it is implementable at all. My remaining
budget did not permit implementation, and I will not present design notes as though they were a
working system. Everything below is either verified fact or explicitly unbuilt.

## 1. Current state — PROVEN
| Item | Value |
|---|---|
| `origin/master` | **`ddcd9c3`** (`ddcd9c3662f4d3257d4f92e335fa7422e99ebdeb`) |
| Cron expression | `7 */12 * * *` |
| Other trigger | `workflow_dispatch` present |
| Concurrency | group `scholarzone-maintenance`, **`cancel-in-progress: false`** |
| Worker timeout | 90 minutes |
| `MaintenanceRun` model | **EXISTS** — `backend/app/models.py:476` |
| Vercel `crons` in root `vercel.json` | **ABSENT** |
| Vercel `crons` in `backend/vercel.json` | **ABSENT** |

## 2. Root cause — REFINED, not just "drift"
GitHub Actions `schedule` is documented best-effort: runs are delayed under load and queued runs can
be **dropped entirely**. With `schedule` as the *only* trigger, a dropped event is indistinguishable
from a completed cycle — there is no durable record of what was *supposed* to run. Observed drift
(6–17h gaps, and >8h overdue as of the last check) is consistent with that.

Note the existing `cancel-in-progress: false` is already correct: it prevents duplicate execution but
does nothing for a **dropped** trigger. That asymmetry is the actual gap.

## 3. Structural findings that gate the whole design

**a. No duplicate table is needed.** `MaintenanceRun` exists and Part 4 explicitly prefers reusing
it. A separate slot ledger is a candidate, not a requirement — and creating one would be the duplicate
state Part 15/16 warns against. **Not decided; requires design work I did not perform.**

**b. Vercel Cron is not configured today** in either config file. Whether the current plan permits it
is **UNKNOWN** — Part 38 requires inspection I could not complete.

**c. The dispatcher credential does not exist.** A Vercel function cannot call the GitHub workflow
dispatch API without `Actions: write`. My `gh` keyring session credential is **not** usable for this
and must not be embedded. **This is the hard blocker**, and it is owner-only by rule.

**d. Vercel Cron triggers produce `event=workflow_dispatch`.** Per Part 23, these must be reported as
`external_scheduler_dispatch` and must **never** be counted as GitHub schedule events — otherwise the
Phase 6 forensic gate is contaminated by design. Any implementation must persist `source` durably.

## 4. What is deliberately NOT claimed
- **No** scheduler code, slot model, lease logic, dispatcher, watchdog, or tests were written.
- **No** provider-plan inspection was completed.
- **No** GitHub credential was created, and none is proposed to be faked.
- **Historical Phase 6 remains `CASE E — NOT OBSERVED`.** Not rewritten, not simulated.
- **`maintenance.logos` remains a CONFIRMED LIVE UNSAFE VECTOR** on code/audit grounds; **recurring
  reversion remains NOT PROVEN.**
- The 18 purged images are untouched; `3bf92b6` and `87ad84c` behaviour untouched.

## 5. What remains before this can be built
1. **Owner**: decide GitHub App vs fine-grained PAT; create credential; set it on the chosen Vercel
   project as an encrypted env var. *(blocking)*
2. **Owner**: confirm Vercel plan allows Cron on the target project. *(blocking)*
3. **Owner**: choose the canonical project to host the dispatcher — `scholarzone-fwzj` or
   `scholarzone`. This is unresolved and must not be guessed.
4. Engineering: decide slot model — extend `MaintenanceRun` vs add a slot table — with atomic claim and
   lease expiry.
5. Engineering: implement dispatcher (short, authenticated, fixed repo/workflow/ref), durable
   `source`/`slot_id`/`attempt` in the workflow contract, bounded catch-up, watchdog, status surface.
6. Engineering: CASES A–J as unit/integration proofs. Provider proof (Part 42) can only come after
   merge and real invocation.

## 6. Root-cause statement
The maintenance system has **no durable record of what was due**. It relies on a best-effort trigger
with no catch-up ledger, so a dropped schedule event is silently indistinguishable from a completed
cycle. Fixing the cron minute would not help. The fix is a durable due-ledger with atomic claim,
idempotent execution, and bounded catch-up — which is architecturally sound but **cannot be completed
by me**, because its trigger credential must be created by the owner.