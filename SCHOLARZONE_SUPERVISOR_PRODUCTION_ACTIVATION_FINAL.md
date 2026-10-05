# SCHOLARZONE_SUPERVISOR_PRODUCTION_ACTIVATION_FINAL

**FINAL CLASSIFICATION: OWNER_ACTION_REQUIRED**

Pre-dispatch gates **1, 2, 3, 4 and 6 FAILED**. Execution stopped before any
`workflow_dispatch`, per the instruction "If any gate fails: STOP."

No production discovery was executed. No production write occurred. No merge,
push or deployment was performed.

---

## 1. Merged SHA

**NONE — the candidate is not merged.**

```
$ git merge-base --is-ancestor 0092b5d origin/master   ->  exit 1  (NOT an ancestor)
$ git ls-remote --heads origin feat/supervisor-production-trigger  ->  (no output)
$ git cat-file -e origin/master:backend/app/routers/supervisor_internal.py       ->  absent
$ git cat-file -e origin/master:.github/workflows/supervisor-discovery-proof.yml ->  absent
```

The feature branch exists **only locally**. It has never been pushed, and neither
the endpoint nor the workflow exists on `master`.

---

## 2. Deployed SHA

**`9cebca7bf0e011cec5e9ed96715a4489dd64bef1`** — this is what production actually
serves, and it is **not** the candidate.

```
GET https://scholarzone-fwzj.vercel.app/api/health   ->  HTTP 200
{"status":"ok","revision":"9cebca7bf0e011cec5e9ed96715a4489dd64bef1"}
```

`9cebca7` equals current `origin/master` and is the merge base of the candidate,
so production is running the parent commit with none of this work in it. Gate 4
fails: `/health` does not report the candidate SHA.

Candidate SHA is now **`1e7b310f19a8731b1a8ce204e5099304d2bc119d`** (three
commits: `0092b5d` implementation, `6858a6d` report, `1e7b310` public-URL
guards).

---

## 3. Production API host source

**`SCHOLARZONE_API_URL` — authoritative, and already configured.**

```
$ gh variable list
SCHOLARZONE_API_URL   https://scholarzone-fwzj.vercel.app/api
```

It is a repository **variable** (plain text, not masked, not sensitive). It is
the same source `deploy.yml` and `frontend.yml` already use, so this follows the
convention the owner designated.

**No host literal is embedded in the Supervisor workflow.** Asserted by
`test_no_host_literal_is_embedded_in_the_workflow` (`scholarzone-fwzj` and
`vercel.app` are both absent from executable content).

### Resolution of the public endpoint — verified, and a trap avoided

The variable **already ends in `/api`**. The workflow therefore appends a **bare**
route, and the concatenation is what produces the required public path:

```
$SCHOLARZONE_API_URL  +  /internal/supervisor/discover/$TARGET_SCHOLARSHIP_ID
https://…vercel.app/api  +  /internal/supervisor/discover/<id>
  =>  https://…vercel.app/api/internal/supervisor/discover/<id>
```

This is correct, and it is confirmed against three pieces of real code:

1. **`vercel.json`** — top-level `rewrites` sends `/api/(.*)` to the `backend`
   service, and that service's `routes` transform rewrites `request.path` from
   `/api/(.*)` to `/$1`.
2. **`backend/app/middleware/api_prefix.py`** — `PREFIX = "/api"`; the middleware
   removes **exactly one** leading `/api` (`api_prefix.py:41-42`), and is not a
   loop.
3. **`backend/app/routers/supervisor_internal.py`** — the route is declared at
   the root, `/internal/supervisor/discover/{scholarship_id}`, with no prefix of
   its own.

**The literal instruction "the public route MUST be `/api/…`" must not be applied
by editing the workflow's route string.** Appending a second `/api` would produce
`/api/api/internal/supervisor/discover/<id>`. That would happen to still resolve —
because the Vercel transform strips one prefix and the middleware strips another
— but it would be surviving only as an accident of two independent layers, and it
would break the moment either layer was tightened. It would also contradict every
other workflow in the repository.

Therefore **no code change was made**. The requirement "public endpoint =
`/api/internal/supervisor/discover/{scholarship_id}`" is **already satisfied**, and
the coupling that makes it satisfied is now asserted rather than left to memory, by
four new tests in `TestThePublicUrlResolution`:

- `test_the_variable_already_carries_the_public_api_prefix` — checks `vercel.json`
  and the middleware, and asserts the middleware is not a `while` loop;
- `test_the_workflow_requests_the_public_api_path` — resolves the real variable
  value against the real route string and asserts the result is **exactly**
  `/api/internal/supervisor/discover/$TARGET_SCHOLARSHIP_ID`, and explicitly
  **not** `/api/api/…`;
- `test_the_backend_route_itself_is_root_level`;
- `test_no_host_literal_is_embedded_in_the_workflow`.

---

## 4. Public endpoint

```
POST https://scholarzone-fwzj.vercel.app/api/internal/supervisor/discover/{scholarship_id}
  header: X-Verification-Secret: <SCHOLARZONE_VERIFICATION_SECRET>
  body:   none — the OpenAPI operation declares no requestBody at all
```

Backend-native route (after prefix stripping): `/internal/supervisor/discover/{scholarship_id}`.

---

## 5. Pre-dispatch gate results

| # | Gate | Result | Evidence |
|---|---|---|---|
| 1 | Candidate is merged | **FAIL** | Not an ancestor of `origin/master`; branch unpushed |
| 2 | Exact merged SHA identified | **FAIL (n/a)** | No merge exists |
| 3 | Deployment completed | **FAIL** | Endpoint and workflow absent from `origin/master` |
| 4 | `/health` reports exact expected revision | **FAIL** | Reports `9cebca7`, not the candidate |
| 5 | `SCHOLARZONE_API_URL` configured | **PASS** | `https://scholarzone-fwzj.vercel.app/api` |
| 6 | Supervisor discovery explicitly enabled | **FAIL** | Code not deployed; the flag is a Vercel env var, absent by default |
| 7 | Render flag independent and OFF | **PASS** | `test_it_does_not_enable_rendering`, `test_it_is_a_different_switch_from_rendering`; workflow sets no render variable; endpoint passes no `RenderBudget` |
| 8 | `workflow_dispatch`-only | **PASS** | `test_workflow_dispatch_is_the_only_trigger` |
| 9 | Exactly one `scholarship_id` input | **PASS** | `test_it_takes_exactly_one_input_and_validates_it` |
| 10 | No country input | **PASS** | `test_a_country_cannot_be_a_target` |
| 11 | No batch input | **PASS** | `test_a_list_of_targets_cannot_be_passed` |
| 12 | No arbitrary URL input | **PASS** | `test_it_takes_one_path_parameter_and_no_body` — no `requestBody` in the OpenAPI operation |
| 13 | No maintenance invocation | **PASS** | `test_the_router_does_not_import_maintenance_or_scheduler_code`; workflow addresses only `/internal/supervisor/discover/…` |
| 14 | No scholarship `DiscoveryCandidate` invocation | **PASS** | `test_it_does_not_reach_the_scholarship_discovery_subsystem` |
| 15 | Authentication uses `SCHOLARZONE_VERIFICATION_SECRET` | **PASS** | `test_the_secret_comes_from_the_repository_secret_at_runtime`; the repository secret exists (name confirmed via `gh secret list`; **value never read**) |
| 16 | Secret value never printed | **PASS** | 5 tests: no `set -x`, no `curl -v`, no `--value`, no echo of the expansion, header never echoed |
| 17 | Persistence gate remains active | **PASS** | 34/34 boundary tests green |
| 18 | No production DB credential to the runner | **PASS** | `test_it_is_never_given_the_database_url`; job `env` is exactly the three expected keys |

**Score: 13 PASS, 5 FAIL. Instruction followed: STOP.**

Verification runs backing gates 7–18: **22 passed** (gate-mapped subset) and
**34 passed** (persistence boundary). All 85 new tests in the two new files pass.

---

## 6. Owner authorization

**NOT PRESENT.**

The instruction is explicit: *"Do NOT dispatch production discovery merely because
all technical checks pass. Require explicit owner authorization for ONE production
Supervisor discovery execution. If owner authorization is absent: FINAL
CLASSIFICATION = OWNER_ACTION_REQUIRED and stop."*

No such authorization appears in the task context. Production runs: **0**.

---

## 7. Target scholarship

**NOT SELECTED — owner input required.**

The preference is a Cornell-backed scholarship, since
`https://www.cs.cornell.edu/directory` is the one source validated live
(static-first, database-free, zero rendering; 20 professors approved on
`profile_role` evidence, 14/14 recorded academics retained, both navigation labels
refused).

**I cannot determine its scholarship ID.** The ID lives in the production
database, and rule 9 forbids using `SCHOLARZONE_DATABASE_URL` from the agent
environment — including read-only queries. Guessing or scanning ids would be
worse than asking.

The owner must supply the single id whose recorded
`official_source_url` / `catalogue_url` is the Cornell directory. Note that the
target is passed as one integer in the dispatch input and is the **only** thing
the runner is told; the source is read from that scholarship's own record inside
the backend, never supplied by the caller.

---

## 8. Authentication proof

| Property | State |
|---|---|
| Credential | `SCHOLARZONE_VERIFICATION_SECRET` (existing repository secret) |
| Repository secret present | **Yes** — confirmed by name only via `gh secret list` (updated 2026-10-04) |
| Transport | `X-Verification-Secret` header, the repository's existing convention |
| Comparison | `secrets.compare_digest` — constant time |
| Failure mode | `401`, **fails closed** — an unconfigured deployment admits nobody |
| Second condition | `SCHOLARZONE_SUPERVISOR_DISCOVERY_ENABLED`, default **OFF** |
| In workflow | job-level `env:`; **no `${{ }}` interpolation inside any `run:` block**, so the value is never rendered into a script, a trace, a log or an error |
| Printed? | **No.** No `set -x`, no `curl -v`, no `--value`, no echo of the expansion, response body contains counts only |
| Secret value accessed by me | **Never.** No request, no print, no log, no echo, no decode, no inspection |

Two independent conditions must both hold. That separation is deliberate: merging
them is how a capability becomes silently live because somebody rotated a
credential.

---

## 9. One-shot run result

**NOT EXECUTED.** No `workflow_dispatch` was issued. No workflow run ID exists.
No retry was attempted. Scope was not broadened.

The post-run audit fields — run ID, deployed SHA, target id, HTTP status,
extracted / rejected / personhood / role-proof / provenance / approved / persisted
counts, render usage, maintenance activity, scholarship discovery activity — are
all **N/A**, because no run occurred.

`DATABASE_URL` was never obtained and never printed.

---

## 10. Persistence result

**Gate verified PASS; nothing persisted.** The gate that governs the one-shot run
is active and tested:

- `collect_supervisor_plan()` takes **no session** and contains **zero**
  `commit`/`flush`/`add`/`execute`/`merge`/`delete` calls, and references no name
  `db` or `session`;
- `persist_approved_candidates()` accepts only `ApprovedSupervisorCandidate` and
  raises `TypeError` on anything else;
- `persist_supervisor_plan()` is the only writer, and commits once;
- a whole-module allowlist asserts that the only functions in
  `supervisor_discovery.py` that may call `commit` are `persist_supervisor_plan`
  and the pre-existing `_discover_one`.

So a future one-shot run that fails every gate writes **zero** professor,
relationship, evidence and availability rows, and writes only the coverage row —
the honest negative the product is required to record.

---

## 11. Unrelated-write audit

**0 unrelated writes.** Nothing was executed, so nothing was written.

Standing guarantee for the eventual run, asserted by test:

| Must not change | Test |
|---|---|
| Only the target scholarship's coverage row | `test_it_does_not_touch_any_other_scholarship` |
| No maintenance dispatch | `test_the_router_does_not_import_maintenance_or_scheduler_code` |
| No scheduler execution | same |
| No scholarship `DiscoveryCandidate` rows | `test_it_does_not_reach_the_scholarship_discovery_subsystem` |
| No duplicate professor rows | URL unique constraint + `DUPLICATE` gate keyed on the same normalised URL; idempotency pinned by `test_g_rerunning_the_same_discovery_is_idempotent` |
| Provenance retained | every persisted professor carries `supervisor_source_evidence` with source URL, source type, HTTP status and content hash |
| Correct verification status | derived from evidence by `verification_status_for`; personhood alone can never yield `VERIFIED` |
| Correct institutional domain | `INSTITUTIONAL_DOMAIN` gate against the awarding institution's registrable domain |
| Correct person identity | `PERSONHOOD` gate, structural person shape **and** not merely the role restated |

---

## 12. Continuous activation state

**OFF.**

Nothing continuous was added, and nothing continuous may be added. Explicitly
**not** present in the candidate:

- no `schedule:` / `cron:` trigger — `test_there_is_no_schedule_and_no_matrix`;
- no maintenance stage — `vercel.json`'s existing
  `/api/internal/maintenance/dispatch` cron is untouched by this change, and
  `backend/app/jobs/scholarzone_maintenance.py` is unmodified;
- no always-on worker — `run_discovery_batch` remains reachable only from the
  manual backfill script.

The workflow remains an **owner-controlled operational tool**: `workflow_dispatch`
only, one target per run, `concurrency: supervisor-discovery-proof` with
`cancel-in-progress: false`.

---

## 13. Rollback instructions

### Before merge (current state)

Nothing to roll back. The candidate is a local branch only. Delete with:

```
git branch -D feat/supervisor-production-trigger
```

No production effect whatsoever.

### After merge, before dispatch

```
# Vercel dashboard -> Settings -> Environment Variables
SCHOLARZONE_SUPERVISOR_DISCOVERY_ENABLED = false
```

The endpoint then returns `503` immediately. **This is the fast kill switch** —
it needs no code change and no redeploy.

### After a dispatched run

1. Set the flag to `false` first, to stop any further run.
2. Revert the code:
   ```
   git revert 1e7b310 6858a6d 0092b5d
   ```
   (reverse order), on a new branch, then redeploy.
3. **Data rollback is deliberately not automated here.** Any row the proof created
   is an upsert keyed on a unique constraint, so a re-run converges rather than
   duplicates. To remove a proof's rows: delete
   `scholarship_professor_links` for that scholarship id, then recompute coverage.
   This is intentionally left as a documented manual step — adding an automated
   data-rollback path would mean adding a second write path, and this change adds
   none.

No history rewrite and no force-push is required or permitted at any stage.

---

## 14. Owner actions required, in order

1. **Review and merge** `feat/supervisor-production-trigger` (`1e7b310`). Push the
   branch and open a PR. Note `origin/master` has advanced to `9cebca7`; no file
   overlaps with this change, so a rebase is expected to be clean.
2. **Wait for the Vercel deployment** to complete.
3. **Verify the deployed revision**: `GET $SCHOLARZONE_API_URL/health` must report
   the merge SHA. Do not proceed until it does.
4. **Set `SCHOLARZONE_SUPERVISOR_DISCOVERY_ENABLED=true`** on the production Vercel
   deployment. Leave `SCHOLARZONE_SUPERVISOR_RENDER_ENABLED` **untouched** — the two
   are separate switches and rendering must stay off for a static-first proof.
5. **Supply the target scholarship id** — the Cornell-backed scholarship whose
   recorded official source is `https://www.cs.cornell.edu/directory`. I cannot
   determine this without production database access, which is forbidden.
6. **Record the pre-run state** (§15).
7. **Give explicit authorization** for ONE production `workflow_dispatch`.

Only after step 7 will a single dispatch be issued. Not before. And not retried
automatically.

### Host authority — resolved, no action needed

The owner's concern was a hardcoded Vercel host. Verified: the Supervisor workflow
contains no host literal and resolves its URL entirely from
`vars.SCHOLARZONE_API_URL`. The separate `admin-auth-check.yml` does hardcode
`https://scholarzone-fwzj.vercel.app/api` — that value is identical to the
variable's, so the two agree, and that file is **outside this change's scope** and
was deliberately not modified. Flagged for the owner's awareness only.

---

## 15. Pre-run state to record (owner, at step 6)

- [ ] `SELECT count(*) FROM professor_profiles;`
- [ ] `SELECT status, verified_supervisor_count, last_checked_at, evidence_state FROM scholarship_supervisor_coverage WHERE scholarship_id = <TARGET>;`
- [ ] target scholarship id
- [ ] that scholarship's `official_source_url` and `catalogue_url`
- [ ] `SELECT count(*) FROM scholarship_professor_links WHERE scholarship_id = <TARGET>;`
- [ ] `SELECT count(*) FROM supervisor_source_evidence WHERE scholarship_id = <TARGET>;`

### Post-run assertions (owner, after dispatch)

- [ ] HTTP 200; run log shows the requested target id and nothing else
- [ ] response `scholarship_id` equals the requested id
- [ ] `sum(rejected_by_gate) == rejected`
- [ ] `professors_written` equals the change in `professor_profiles`
- [ ] no maintenance dispatch; no scholarship `DiscoveryCandidate` change
- [ ] `render_requested: false`; no rendering occurred
- [ ] only the five Supervisor tables changed
- [ ] **do not run country-wide discovery — no such capability exists**

---

## 16. Final classification

### `OWNER_ACTION_REQUIRED`

Five of the eighteen pre-dispatch gates failed (1, 2, 3, 4, 6), and explicit
owner authorization for the one production execution is absent. Per the
instruction, execution stopped at the gate and no dispatch was issued.

The code is technically ready and fully verified — 85 new tests green, 13 of 18
gates PASS, zero `CANDIDATE_REGRESSION`. What is missing is not engineering work;
it is owner action: **merge, deploy, set one Vercel environment variable, supply
one target id, and authorize one dispatch.**

This is not `MERGE_BLOCKED`: nothing is defective, and no regression was found.
This is not `READY_FOR_OWNER_ACTIVATION` either, because the trigger cannot be
activated yet — it is not on `master` and not deployed, so gates 1 through 4 are
unconditionally false today.

```
FINAL CLASSIFICATION: OWNER_ACTION_REQUIRED
MERGED_SHA: NONE (candidate not merged; branch unpushed)
DEPLOYED_SHA: 9cebca7bf0e011cec5e9ed96715a4489dd64bef1 (current origin/master; NOT the candidate)
API_HOST_SOURCE: SCHOLARZONE_API_URL
PUBLIC_ENDPOINT: /api/internal/supervisor/discover/{scholarship_id}
TRIGGER: BLOCKED
OWNER_AUTHORIZATION: NO
PRODUCTION_RUNS: 0
PERSISTENCE_GATE: PASS
UNRELATED_WRITES: 0
MAINTENANCE_TOUCHED: NO
RENDER_USED: NO
CONTINUOUS_ACTIVATION: OFF
PRODUCTION_WRITES: NONE
FINAL_STATUS: BLOCKED
```

### Note on `TRIGGER: BLOCKED` vs `FINAL_CLASSIFICATION: OWNER_ACTION_REQUIRED`

These are not in conflict, and both are reported deliberately.

`TRIGGER: BLOCKED` states the mechanical outcome: the pre-dispatch gate failed, so
the trigger cannot be invoked and no run occurred. `FINAL_CLASSIFICATION:
OWNER_ACTION_REQUIRED` states the cause and the remedy: the block is owner action,
not a defect. `FINAL_STATUS: BLOCKED` is used rather than
`READY_FOR_OWNER_ACTIVATION` because gates 1–4 are unconditionally false until the
owner merges and deploys — activation is not yet the only remaining step, the
trigger does not exist in production at all.

Candidate SHA for the next step: **`1e7b310f19a8731b1a8ce204e5099304d2bc119d`**.
