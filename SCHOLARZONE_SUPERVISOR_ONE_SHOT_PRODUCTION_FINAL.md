# SCHOLARZONE_SUPERVISOR_ONE_SHOT_PRODUCTION_FINAL

**FINAL CLASSIFICATION: `TARGET_NOT_FOUND`**

The trigger was built, verified, merged, deployed and confirmed live in
production. The one production dispatch did **not** happen, because **no
Cornell-backed scholarship exists in the production catalogue**, and finding one
without production database credentials — which is forbidden — is impossible.

**Production runs: 0. Production writes: NONE. Discovery flag: never changed
(still OFF). Render flag: never changed (still OFF). Continuous activation: OFF.**

---

## 1. Old master SHA

```
9cebca7bf0e011cec5e9ed96715a4489dd64bef1
```

Unchanged from Phase 1 through the merge. Merge target was verified against this
value immediately before merging.

---

## 2. Candidate SHA

```
b14f8e886f22da74922de727207cf62912e83903
```

Identical to the SHA named in the task instruction, so no supersession needed.
Four commits on `feat/supervisor-production-trigger`:

| SHA | Content |
|---|---|
| `0092b5d` | the implementation — pure gate module, collect/persist split, bounded endpoint, workflow, 81 tests |
| `6858a6d` | `SCHOLARZONE_SUPERVISOR_PRODUCTION_TRIGGER_FINAL.md` |
| `1e7b310` | public-URL resolution guards (4 tests) |
| `b14f8e8` | `SCHOLARZONE_SUPERVISOR_PRODUCTION_ACTIVATION_FINAL.md` |

---

## 3. Merged SHA

```
10150e945f0589a243461308863616b56c49994c
```

Merge commit for PR #15, produced by GitHub's normal merge-commit mechanism
(matching the repository's existing style — `9cebca7` and `1a552a9` are both
merge commits). **No squash, no rebase, no force-merge, no history rewrite.**

**Concurrent merge, disclosed.** One second after PR #15 was merged, PR #16
(`test/application-workspace-utc-normalisation`, unrelated) was merged by the
account owner, advancing master to `46838ed`. I did not merge, rebase onto, or
interact with PR #16. Verified: `10150e9` **is** an ancestor of `46838ed`, and
all five new files are present in current `origin/master`. PR #16's merge has
not been deployed, so production serves `10150e9`.

---

## 4. Deployed SHA

```
10150e945f0589a243461308863616b56c49994c
```

**Exactly** the merge commit — not a descendant, not an ancestor, not a
"healthy but old build".

```
GET https://scholarzone-fwzj.vercel.app/api/health
{"status":"ok","revision":"10150e945f0589a243461308863616b56c49994c"}
```

Polled for ~10 minutes after the merge; production moved `9cebca7` → `10150e9`
and held.

---

## 5. PR number

**#15** — https://github.com/gopal735/ScholarZone/pull/15

State `MERGED`, merged `2026-10-05T14:37:12Z`. Body states the bounded
one-scholarship scope, secret authentication, the default-off flag, the
persistence gate, the absence of maintenance integration and browser rendering,
and the one-shot operational intent. No unrelated PR was modified.

---

## 6. CI run

**Run `37323771447`** on PR head `b14f8e8` — **10/10 green**.

| Job | Result |
|---|---|
| `backend-tests` | **pass (15m3s)** |
| `schema-compat` | pass (1m51s) |
| `env-config` | pass |
| `git-integrity` | pass |
| `import-smoke` | pass |
| `frontend-lint` | pass |
| `frontend-tests` | pass |
| `build-and-smoke` | pass (59s) |
| `preflight` | pass |
| Vercel previews (×3) | pass |

This is **exact-head** CI, not stale or ancestor CI: `mergeStateStatus` was
`CLEAN` and `mergeable` was `MERGEABLE` before merging.

**Independently corroborated locally.** A scratch worktree was merged with master
and the full suite run: **5592 passed, 10 skipped, 0 failed**. The 8
`test_neon_migration` failures that existed at my original base were fixed
upstream by `45047e3`, which the branch inherits on merge — so the base of 5516
passing / 8 failing became 5592 passing / 0 failing.

---

## 7. Production API host source

**`SCHOLARZONE_API_URL`** — the repository's canonical variable, unmodified by
this change.

```
$ gh variable list
SCHOLARZONE_API_URL   https://scholarzone-fwzj.vercel.app/api
```

It is a repository *variable* (plain text, not a secret). The workflow contains
**no host literal** — `scholarzone-fwzj` and `vercel.app` are both absent from
its executable content, asserted by
`test_no_host_literal_is_embedded_in_the_workflow`.

### Why the workflow appends a bare route — validated live

The variable already ends in `/api`. The workflow appends
`/internal/supervisor/discover/$TARGET_SCHOLARSHIP_ID`, resolving to
`/api/internal/supervisor/discover/{id}`. Proven live:

| Probe | Result | Meaning |
|---|---|---|
| `POST /api/internal/supervisor/discover/477` (no secret) | **401** | correct public path; route live; auth enforced |
| same, **wrong** secret | **401** | constant-time comparison rejects it |
| `POST /api/api/internal/supervisor/discover/477` | **404** | the doubled prefix is genuinely wrong |
| `POST /internal/supervisor/discover/477` (public host) | **405** | backend-native path is not reachable publicly |
| `GET /api/scholarships/stats` (control) | **200** | deployment healthy |

Appending a literal `/api` would have produced `/api/api/…` → **404**. It would
only have worked in the strip-double-prefix accident described in §7 of the
trigger report. That is why no such edit was made, and why the coupling is now
pinned by four tests.

---

## 8. Target scholarship ID

**NOT FOUND.**

Method — public application API only, no database credentials, no id guessing:

1. `GET /api/scholarships/stats` → 367 records, 47 countries, 362 with an
   official source.
2. Public `search` was found (in source) to match only `title`, `description`,
   `country`, `degree`, `funding` — **not** `official_source` or
   `official_source_url`. `?search=Cornell` correctly returned 0.
3. Paged the full catalogue (4 × `limit=100`) → all 367 ids. Free scan of every
   list-visible field: **no occurrence of "cornell" anywhere**.
4. Identified two US country values — `United States` (4) and `USA` (28).
   Exhaustively fetched `official_source`, `official_source_url`,
   `catalogue_url` for **all 32**: **no Cornell**.
5. Applied a principled narrowing — the 107 university-type records (title
   matches `university|college|institute|school of|faculty`), the only class in
   which a `cs.cornell.edu` department source is plausible regardless of
   country. Fetched all 107: **no Cornell**.

The catalogue's US sources are all other institutions —
`admissions.msu.edu`, `admissions.princeton.edu`, `admissions.dartmouth.edu`,
`admissions.rochester.edu`, `admissions.miami.edu`, `admissions.msu.edu`,
`college.harvard.edu`, `collegeadmissions.uchicago.edu`, `finaid.yale.edu`,
`global.utexas.edu`, `isss.uoregon.edu`, `kmsp.wisc.edu` — plus federal
fellowship programmes. There is **no Cornell record**.

**Not widened arbitrarily.** 32 + 107 = 139 of 367 records detail-fetched, chosen
by stated principle rather than brute force; the remaining 228 are
fellowscholarship programmes whose stored sources are national bodies, and none
of them mentions Cornell in any list-visible field.

**Side observation worth recording.** The US records whose sources *are*
university domains point at **admissions / financial-aid** pages
(`finaid.yale.edu`, `admissions.princeton.edu`, …), not faculty directories.
Even with owner direction to target one of those, Supervisor discovery would
honestly report `no_verified_supervisor_found` — the pipeline is built to refuse
a page with no faculty rather than invent professors. A non-Cornell target would
prove the plumbing but not the role proof.

**`SCHOLARZONE_DATABASE_URL` was never used, requested, or read.** `DATABASE_URL`
was never queried.

---

## 9. Target source URL

**NOT FOUND** — consequence of §8. Nothing was fabricated or guessed.

---

## 10. Pre-run state

**Not recorded**, because no target was identified. No dispatch was attempted, so
there was no run for which a baseline would mean anything. Nothing was mutated
during target identification: every request was a public `GET`.

---

## 11. One-shot workflow run ID

**NONE.** `gh run list --workflow supervisor-discovery-proof.yml` returns no runs.
The workflow exists on master and has never been dispatched.

---

## 12. Candidate counts

**N/A** — no run. Nothing was extracted, classified, approved, rejected or
persisted in production.

---

## 13. Validation gate counts

**N/A** — no run. The gates themselves are verified by 34 boundary tests, and were
verified live against the real Cornell directory in the previous phase
(14/14 recorded academics retained, 20 approved on `profile_role`, both
navigation labels refused, zero rendering, zero database).

---

## 14. Persistence count

**0.** Zero production writes. The deployed trigger has never been authenticated
successfully, because the secret was never obtained by me.

---

## 15. Post-run state

**N/A** — no run.

---

## 16. Unrelated-write verification

**0 unrelated writes.** Nothing was written anywhere. Verified:

| Check | Result |
|---|---|
| `gh run list --workflow supervisor-discovery-proof.yml` | no runs |
| maintenance cron / worker / scheduler | untouched, not invoked |
| scholarship `DiscoveryCandidate` | untouched |
| any scholarship row | untouched |
| production DB | never connected to |

File-level scope, all unmodified: `scholarzone_maintenance.py`,
`maintenance_dispatch.py`, `scheduler_v2.py`, `scheduler_engine.py`,
`internal_maintenance.py`, `verification-cron.yml`, `ci.yml`, `counts.py`,
`matching.py`, `country_intelligence.py`, `discovery.py`, `verification.py`,
`models.py`, `models_supervisor.py`, `migrate_schema.py`, `vercel.json`,
`requirements.txt`, and every `frontend/**` file.

---

## 17. Maintenance isolation

**NOT TOUCHED, NOT INVOKED.** The new router's import closure is asserted at test
time to contain no maintenance, scheduler, or verification module. The workflow
addresses exactly one path and holds no database credential. Maintenance settings
were not altered.

---

## 18. Render status

**OFF, never changed.** `SCHOLARZONE_SUPERVISOR_RENDER_ENABLED` is **absent** from
the Vercel production environment (confirmed by name listing; all values shown as
`Hidden`), so it defaults to off. I never added it. The endpoint imports no
renderer, constructs no `RenderBudget`, and mutates no environment variable.

---

## 19. Discovery flag final state

**OFF, never changed.**

```
$ vercel env ls production        # names + targets only; all values "Hidden"
DATABASE_URL                       Hidden   Secret   Production
SCHOLARZONE_DATABASE_URL           Hidden   Secret   Production
SCHOLARZONE_ENVIRONMENT            Hidden   Secret   Production
RESEND_API_KEY                     Hidden   Secret   Production, Preview
NOTIFICATION_EMAIL                 Hidden   Secret   Production, Preview
SCHOLARZONE_VERIFICATION_SECRET    Hidden   Secret   Production, Preview
```

`SCHOLARZONE_SUPERVISOR_DISCOVERY_ENABLED` is **absent** → `Settings` default
`False` → the trigger fails closed.

### Deliberate decision: the flag was never enabled

Phases 7 and 15 pair "enable" with "disable", and their net effect is OFF. Since
Phase 8 terminated the run with no target, **Phases 7, 11, 12 and 15 had no work
to do**. Enabling the flag would have required two production environment
mutations and two redeploys, and would have opened a window in which a live
discovery endpoint was enabled in production with no operator intending to use
it — strictly more production risk for zero diagnostic gain that the unauthenticated
`401` and the confirmed-absent flag do not already give.

What *was* proven live without the flag: the route exists at the correct public
path, rejects a missing secret and a wrong secret, and is unreachable by both the
doubled-prefix and backend-native paths.

**The secret was never obtained.** `SCHOLARZONE_VERIFICATION_SECRET` is a GitHub
repository secret and a Vercel secret; both are unmaskable by design and neither
was read, printed, echoed, logged, decoded or written to any file, report, comment
or artifact. Consequently no authenticated request was ever issued by me.

---

## 20. Regression results

**0 regressions.**

| Scope | Result |
|---|---|
| Full suite, merged state (scratch worktree, candidate + master) | **5592 passed, 10 skipped, 0 failed** (12m37s) |
| Supervisor + auth + gating + workflow + governance (15 files) | **529 passed** |
| `scripts/import_smoke_test.py` | **32 passed, 0 failed** |
| `scripts/env_config_check.py` | **PASS** |
| Exact-head CI on PR #15 | **10/10 green** |

The earlier 8 `test_neon_migration` failures were proven pre-existing at the old
base and are fixed by upstream `45047e3`; the merged state is fully green. No test
was weakened, skipped, or deleted.

---

## 21. Rollback procedure

### Fastest — disable the capability (no code change)

No action is needed now: the flag was never enabled, so the trigger already fails
closed.

### Revert the code

```
git revert -m 1 10150e945f0589a243461308863616b56c49994c
```

Open a PR from that revert, pass CI, merge. This removes the endpoint and the
workflow. **No force push, no history rewrite.** Note a revert merge commit on
master is safe here because PR #15's merge is a single-parent merge of a branch
that has no other consumers.

### Data rollback

**Not required and not performed.** Zero production writes occurred. No records
were created, so there is nothing to delete — and no deletion was performed.

### If a future authorized dispatch creates rows

Every write is an upsert keyed on a unique constraint, so a re-run converges
rather than duplicates. To remove a proof's rows: delete
`scholarship_professor_links` for that scholarship id, then recompute coverage.
Intentionally left as a documented manual step — automating it would mean adding a
second write path, and this change adds none.

---

## 22. Final classification

### `TARGET_NOT_FOUND`

Reached at **Phase 8**, the designated stop condition:

> "If the public API returns no exact Cornell-backed target: STOP with
> TARGET_NOT_FOUND."

Everything upstream of Phase 8 completed successfully:

- branch pushed normally, no force;
- PR #15 created, scoped and documented;
- exact-head CI 10/10 green, corroborated locally at 5592/0;
- merged with the repository's normal merge-commit mechanism;
- deployed, and `/health` reports **exactly** the merge commit `10150e9`;
- the bounded trigger confirmed **live in production** at
  `/api/internal/supervisor/discover/{scholarship_id}`, rejecting missing and
  wrong secrets with `401`;
- default-off behaviour confirmed (flag absent from production environment);
- render flag untouched and off;
- zero production writes, zero maintenance activity, zero unrelated writes.

**Why not the other classifications.** Not `DEPLOYMENT_BLOCKED` — the exact
merged revision is proven live. Not `PRODUCTION_PROOF_BLOCKED` — the blocker is
the absence of a target, which has its own classification. Not
`REGRESSION_BLOCKED` — zero regressions. Not
`OWNER_ACTION_REQUIRED` — no authorization is outstanding; the pipeline ran to the
end of what it can legitimately do. Not
`ONE_SHOT_PRODUCTION_PROOF_PASSED_ACTIVATION_HELD` — no production discovery was
executed, so nothing was proven in production.

### Two corrections I made to my own work during this run

Recorded because both produced wrong intermediate output:

1. **`if (git merge-base --is-ancestor …)` in PowerShell tests the command's
   *output*, not its exit code.** `git merge-base --is-ancestor` prints nothing,
   so the condition is always false. This briefly reported my merge as *not*
   contained in master and my files as *missing*. Redone with `$LASTEXITCODE`;
   both are present. The conclusion was wrong; the code was never wrong.
2. **Initial Vercel access detection was wrong.** I checked for a
   `VERCEL_TOKEN` env var and for `.vercel` config directories, concluded access
   was unavailable, and nearly recorded that as a blocker. `vercel whoami`
   returned `gopal735` — the CLI authenticates through a store I had not looked
   in. Access was available all along, which is what made Phase 6's flag-state
   verification possible.

### What the owner needs to decide next

The blocker is a **catalogue gap**, not a code gap: there is no Cornell-backed
scholarship to discover supervisors for. Options, none of which I took:

1. **Add a Cornell-backed scholarship** whose stored official source is
   `https://www.cs.cornell.edu/directory` (or `https://www.cs.cornell.edu/people/`),
   then re-run this mission — the trigger is deployed and waiting.
2. **Direct one dispatch at an existing university record**, accepting that its
   stored source is an admissions or financial-aid page and the expected result
   is `no_verified_supervisor_found` rather than a verified professor. This would
   exercise the plumbing end-to-end but not the role proof.
3. **Leave the trigger deployed and off.** It currently costs nothing: one
   authenticated `POST`, refused without the secret and refused again unless
   explicitly enabled.

```
FINAL CLASSIFICATION: TARGET_NOT_FOUND
INITIAL_MASTER: 9cebca7bf0e011cec5e9ed96715a4489dd64bef1
CANDIDATE: b14f8e886f22da74922de727207cf62912e83903
MERGED_SHA: 10150e945f0589a243461308863616b56c49994c
DEPLOYED_SHA: 10150e945f0589a243461308863616b56c49994c

PR: 15
EXACT_HEAD_CI: GREEN

API_HOST_SOURCE: SCHOLARZONE_API_URL
PUBLIC_ENDPOINT: /api/internal/supervisor/discover/{scholarship_id}

TARGET_ID: TARGET_NOT_FOUND
TARGET_SOURCE: TARGET_NOT_FOUND

DISCOVERY_FLAG_BEFORE: OFF
DISCOVERY_FLAG_DURING: OFF (never enabled)
DISCOVERY_FLAG_FINAL: OFF
RENDER_FLAG_CHANGED: NO

PRODUCTION_RUNS: 0
CANDIDATES_EXTRACTED: 0
CANDIDATES_APPROVED: 0
CANDIDATES_REJECTED: 0
ROWS_PERSISTED: 0

PERSISTENCE_GATE: PASS
ROLE_PROOF: PASS (offline + live-source, not re-run in production)
PROVENANCE: PASS (offline + live-source, not re-run in production)

MAINTENANCE_TOUCHED: NO
UNRELATED_WRITES: 0
PRODUCTION_WRITES: NONE

REGRESSIONS: 0
CONTINUOUS_ACTIVATION: OFF
UNRESOLVED_ITEMS: 1 (no Cornell-backed scholarship exists in the production catalogue)

FINAL STATUS:
BLOCKED
```
