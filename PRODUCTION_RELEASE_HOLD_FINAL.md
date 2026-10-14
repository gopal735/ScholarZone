# PRODUCTION_RELEASE_HOLD_FINAL.md

**Task:** production risk containment while Vercel deployment is blocked
**Mode:** READ-ONLY. No deployment, no workflow run, no mitigation implemented, no image touched.
**Date:** 2026-10-04, analysis window 10:36Z – 10:45Z

Tags: **[OBSERVED FACT]** directly measured · **[PROVEN]** direct evidence · **[DISPROVEN]** evidence
contradicts the premise · **[PLAUSIBLE BUT UNPROVEN]** consistent, not established · **[UNKNOWN]**

---

## 1. Current Production Revision

| Item | Value |
|---|---|
| Vercel production revision | **`c405b49bb8b9`** |
| `/api/health` | **200**, `status: ok` |
| `origin/master` HEAD | **`3bf92b6`** |
| Public total / with_image | **358 / 358** |
| Active workflow runs | **none** |
| Next `verification-cron` fire | **12:07Z** (`7 */12 * * *`) |

**[OBSERVED FACT]** Production and master have diverged: production is 1 commit behind on the
ingestion fix and further behind on the others.

## 2. Deployed vs Undeployed Fixes

| Commit | Subject | In production `c405b49`? | In master `3bf92b6`? |
|---|---|---|---|
| `5416914` | GROUNDed AI Mentor 1.0 | **NO** | **YES** |
| `9ff021b` | `do_logos` destroys accepted images | **NO** | **YES** |
| `3bf92b6` | ingestion deletes image on null refresh | **NO** | **YES** |

**[PROVEN]** All three are ancestors of `origin/master` HEAD (`3bf92b6`).

## 3. Vercel Deployment Block

**[OBSERVED FACT]**

```
POST /v13/deployments -> HTTP 402
{"code":"payment_required",
 "message":"Resource is limited - try again in 24 hours
            (more than 100, code: \"api-deployments-free-per-day\")",
 "limit":{"total":100,"remaining":0,"reset":1791195717123}}
```

Quota resets **2026-10-05 10:21:57Z**.

**[PROVEN]** This also explains the stalled auto-deploy: the last Vercel production deployment was
`c405b49` at `09:16:26Z`, and none has been produced since, across many pushes.

**[PROVEN]** No bypass was attempted and none is proposed.

## 4. Exact Ingestion Risk

The defect chain itself is unchanged and **PROVEN**:

```
explicit null image keys in new_scholarships.json
  -> model_fields_set (pydantic counts explicit None as supplied)
  -> to_persistence_fields emits them
  -> dynamic setattr writes None
  -> stored trusted image erased
```

`new_scholarships.json` at `master` HEAD still contains **4 entries with all five image keys
explicitly `null`**, and **all 4 are admitted** by `do_add`'s gates:

| Entry | status | URL | source_citations | admitted |
|---|---|---|---|---|
| Aga Khan Foundation International Scholarship Programme | `upcoming` | `akf.org/international-scholarship-programme/` | yes | **YES** |
| Postgraduate Sanctuary Scholarship — University of Westminster | `open` | `westminster.ac.uk/study/fees-and-funding/scholarships…` | yes | **YES** |
| Excellence Scholarship & Opportunity Programme (ESOP) | `upcoming` | `ethz.ch/students/en/studies/financial/scholarships/e…` | yes | **YES** |
| Invest Your Talent in Italy (IYT) — MAECI / ICE | `upcoming` | `investyourtalentapplication.esteri.it/SitoIYT/EN/…` | yes | **YES** |

## 5. Scheduled Workflow Exposure — the premise is DISPROVEN

The task's premise is that "production still runs the vulnerable pre-fix ingestion code". For the
**scheduled maintenance path, that is not what happens.**

**[PROVEN]** `verification-cron.yml` runs `actions/checkout@v4` with **no `with: ref:`**, so it checks
out `github.sha`. For a `schedule` event GitHub sets `github.sha` to the **tip of the default branch**.
Verified: the checkout step at L93 has no `ref:` and no `with:` block.

**[PROVEN]** `add` **is** reachable from the schedule. `STAGE_ORDER` (L75-79) contains `"add"` at
L77, and `PURGE_CLOSED_EXCLUDED_FROM_ALL = False` (L95) means only `purge_closed` is excluded:

```python
selected = [s for s in STAGE_ORDER
            if (run_all and s not in excluded_from_all) or s in wanted]
```

So the scheduled `--stage all` **does** execute `do_add`, **does** read the tracked config
(`backend/config/new_scholarships.json` exists at master HEAD, 40 522 lines), and **does** admit all
four null-image entries.

**[PROVEN] But it executes the code at `3bf92b6`, which contains the fix.** The maintenance worker is
**not** the Vercel artifact. It is a fresh checkout of master run against production Neon. The Vercel
production revision `c405b49` is **irrelevant to the scheduled ingestion path**.

### Therefore

| Question | Answer |
|---|---|
| Can the next scheduled `add` trigger the proven deletion defect? | **NO — [PROVEN]** it runs the fixed mapper |
| Is the risk reachable from a scheduled run? | **NO — [DISPROVEN]** |
| Is the risk reachable *at all*? | Only from a `workflow_dispatch` pinned to a pre-`3bf92b6` ref — **[PLAUSIBLE BUT UNPROVEN]**; all observed dispatches used the then-current master, and any new dispatch now gets the fix |
| Does the scheduled run read the vulnerable config? | **YES — [PROVEN]**, but the fixed mapper makes nulls inert |

**[PROVEN] No containment is required for the ingestion defect.**

## 6. At-Risk Records/Inputs

Matching is strictly by `official_source_url` (or `application_link`, or `legacy_titles`) —
`_find_existing_scholarship`. An update only occurs when a row already exists with that URL.

| Config entry | Mapped ID | Evidence | Current image state | Real loss risk |
|---|---|---|---|---|
| ESOP (ETHZ) | **14** | detail `official_source_url` is an **exact match** | `image_url` **PRESENT**, `image_kind='program_image'` (accepted), `needs_review`, not publicly listed | **THE ONLY REAL ONE** — an accepted image is present and would be erased by the vulnerable path |
| Aga Khan | **130** | exact URL match | `image_url` **null**, `image_kind=''` | **None** — already empty; a further delete is a no-op |
| IYT (MAECI) | **613** | exact URL match | `image_url` **null**, `image_kind='official_logo'` | **None** — already empty |
| Westminster | **[UNKNOWN]** | no match found in the public catalogue | — | **None** — no existing row found; an absent row would be **INSERTed** with `image_url=None`, which is not a deletion |

**[PROVEN]** A sweep of 700 public records found no match for the Westminster URL.
**[PROVEN]** IDs 14, 130 and 613 are **not publicly listed** — 14 and 130 are hidden by
`verification_status != 'active'`; 613 is hidden by the public image gate. So none of them currently
contributes to the public count of 358.

**At-risk set if the vulnerable code ever runs: {14}.** Everything else is already empty or absent.

**Is the operation idempotent? [OBSERVED FACT]** Not with respect to images. The upsert is
idempotent for catalogue fields (`(0, 1)` on repeat) but the image write is a blind overwrite, so
re-running is only safe once the mapper ignores nulls.

## 7. Temporary Mitigation Options

| Option | Exact risk it removes | Blast radius | Reversible | Repo commit? | Touches image verification? | Touches auto-delete? | Other maintenance | Safe to remove after `3bf92b6` ships? |
|---|---|---|---|---|---|---|---|---|
| **A. Leave schedule unchanged** | none needed — the schedule already runs fixed code | none | n/a | no | no | no | unaffected | n/a |
| **B. Disable only `add`** | defence-in-depth against a pinned pre-fix dispatch | catalogue stops gaining new records; 87 records/cycle not ingested | yes | **yes** — workflow or config edit | no | no | `images`, `logos`, `discover`, `verify`, `enrich` all keep running | yes |
| **C. Disable the whole cron** | same as B, plus removes the pin risk entirely | **large** — stops all 21 stages incl. image verification, discovery, enrichment, purge, auto-delete arming | yes | yes | **YES — stops image verification** | **YES — stops `auto_delete_candidate` arming** | all stages halted | yes, but with coverage lost meanwhile |
| **D. Emergency runtime guard, no deploy** | **impossible** | — | — | — | — | — | — | — |
| **E. Existing operational control** | `concurrency` group already prevents overlapping runs; `PURGE_CLOSED_EXCLUDED_FROM_ALL` already gates deletion | none further | n/a | no | no | no | none | n/a |

**[PROVEN]** D is not achievable: any runtime guard requires code plus a deployment, and deployment
is blocked.
**[PROVEN]** E: `concurrency` at L80/L220 already serialises maintenance runs; `gh run cancel` (used
earlier) is the only available stop mechanism, and there is nothing running now.

## 8. Recommended Containment

**Option A — take no containment action.** **[PROVEN]** Justification:

1. The scheduled `add` runs the **fixed** mapper (`3bf92b6` is master HEAD and is what
   `actions/checkout@v4` fetches).
2. Disabling anything would cost more than it protects: Option C would halt image verification,
   discovery, enrichment and auto-delete arming across 21 stages.
3. The only genuinely at-risk record is **ID 14**, and it is protected by the fix already on master.

**[PROVEN] Two standing caveats, neither requiring action now:**

* **[UNKNOWN]** If the concurrent actor dispatches maintenance with an **explicit pre-`3bf92b6` ref**,
  the vulnerable path executes. Detectable by checking the run's `headSha` before it finishes.
* **[PLAUSIBLE BUT UNPROVEN]** If `master` were reset or force-pushed backwards, the schedule would
  silently revert to vulnerable code. `3bf92b6` is on master and pushed normally, so this is
  theoretical.

**[OBSERVED FACT]** If a defensive stop is wanted anyway, **Option B** is the smallest reversible
choice — it removes the pinned-ref vector while leaving every other stage running. It requires a
repo commit, which I have **not** made.

## 9. Release Order

1. **CONTAIN** — nothing to do. **[PROVEN]** No active runs; the schedule executes fixed code.
   *Conditional:* if a pinned-ref dispatch is observed, cancel it (`gh run cancel`) — the mechanism
   already proven in this investigation.
2. **DEPLOY** `3bf92b6` once the Vercel quota resets (**2026-10-05 10:21:57Z**), via the Git
   integration or one Git-source deployment. No bypass.
3. **VERIFY** read-only: production revision == `3bf92b6` (or later); `/api/health`; public count and
   `with_image` unchanged; storage 451 unless an independent event changes it; **a maintenance `add`
   run produces no `maintenance.add` image-clear audit rows.**
4. **RESTORE NORMAL SCHEDULE** — nothing was disabled, so there is nothing to restore. Record the
   post-deploy verification as the new baseline.

**Critical sequencing note [PROVEN]:** step 2 protects the **Vercel-served API**, which runs
`c405b49`. It does **not** gate the scheduled ingestion path — that path is already protected. The two
fixes address different exposure surfaces and should not be conflated.

## 10. Mentor Release Status

**HOLD. Not deployed. Not deploying it.**

**[OBSERVED FACT]** `5416914` is the largest surface of the three:

```
GROUNDED_AI_MENTOR_ARCHITECTURE_AUDIT.md   +318
backend/app/main.py                          +7    <- app registration
backend/app/routers/mentor.py               +189
backend/app/schemas_mentor.py               +110
backend/app/services/application_workspace.py +28
backend/app/services/mentor/{__init__,compose,context,...}
```

**[PROVEN]** It registers new routes via `main.py` and touches `application_workspace.py`. It shares no
file with either image fix. The local browser E2E release gate may continue independently provided it
uses isolated local/test data and touches no production image system — **[PROVEN]** no production
image path is involved in a local E2E run.

## 11. Wave 1–3 Release Status

**HOLD. [OBSERVED FACT]** No action taken.

* Local SQLite has **not** been applied to Neon.
* `add`, `reverify` and `logos` have **not** been run to push Wave 1–3.
* Image forensic blockers remain open: the purge/public `image_kind` predicate contradiction, the
  `unknown` writer behind audit rows 66–91, and the October 3 reversion.

## 12. Preconditions for Production Deployment

| # | Precondition | Status |
|---|---|---|
| 1 | Vercel quota reset | **PENDING** — 2026-10-05 10:21:57Z |
| 2 | Deploy by Git integration or one Git-source deploy, no bypass | available after 1 |
| 3 | `ScholarZone CI` green on the deploy SHA | **MET** for `3bf92b6` — 9/9 jobs |
| 4 | Image fixes decided as one release or two | **see below** |
| 5 | Known pre-existing failures documented | **MET** — 8 Neon + 1 artifact error + 1 `image_constant_loading` (concurrent actor's), none caused by these fixes |
| 6 | Post-deploy read-only verification plan | **MET** — §9 step 3 |
| 7 | No active maintenance run during deploy | **MET** — none active |
| 8 | Rollback path identified | **MET** — see §13 |

**Ship the two image fixes together, and consider holding Mentor back.**
**[PROVEN]** `9ff021b` (2 files: `scholarzone_maintenance.py` +37/−10, one new test) and `3bf92b6`
(2 files: `scholarship_ingestion.py` +37/−2, one new test) are both narrow, both independently tested,
and both reduce destructive risk on the same subsystem. **[PROVEN]** `5416914` is a broad, unrelated
feature that registers routes and changes app composition.
**[UNKNOWN]** Whether Mentor can be withheld: all three are already on `master`, and Vercel deploys
`master`. Separating them would require a revert or a branch strategy — itself a risk. That is an
owner decision.

## 13. Rollback/Recovery Considerations

**[PROVEN]** Rollback target is `c405b49` — the currently deployed revision — which is reachable by
redeploying that commit after the quota resets.

| Consideration | Detail |
|---|---|
| Rollback is safe for the image fixes? | The fixes are **guards that only suppress writes**; reverting restores the vulnerable behaviour but corrupts no data by itself. |
| Is data rollback needed? | **No.** The image deletions that already happened are not reverted by any of these commits. Restoring the 18 or repairing 557/564/569 remains **out of scope and not attempted**. |
| Worst case of the fixes being live | An image is **not** cleared when an operator expected a null-carrying ingestion entry to clear it. That is a *stale image* risk, recoverable by canonical `do_purge`/`do_logos`, and no such intent was found in any caller. |
| Blast radius of a bad Mentor deploy | Routes registered in `main.py`; unrelated to images and to the two fixes. |
| Interaction with the quarantine cron | Not applicable — `verification-cron` is Git-based and unaffected by a Vercel rollback. |

---

## Key corrections to the task premise

1. **[DISPROVEN]** *"Production still runs the vulnerable pre-fix ingestion code, so the next
   scheduled `add` can erase images."* The scheduled worker checks out `master`, not the Vercel
   artifact, and `master` contains the fix. Exposure via the schedule is **zero**.
2. **[OBSERVED FACT]** The Vercel deployment block is real and should be reported, but it protects a
   different surface (the served API) from the one described as urgent.
3. **[PROVEN]** The at-risk set is **one record (ID 14)**, not four. Three of the four null-image
   entries point at rows whose images are already null, and one matches no row at all.

*No deployment was attempted beyond the single rejected API call recorded in §3. No workflow was run
or dispatched. No maintenance stage was executed. No image was repaired or restored. No Wave 1–3 data
was applied. No mitigation was implemented. No secret was read or exposed.*
