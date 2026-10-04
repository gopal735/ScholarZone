# PUBLIC SCHOLARSHIP VISIBILITY SECURITY RELEASE — FINAL REPORT

| | |
| --- | --- |
| Base SHA (`origin/master`) | `573a983b004ab08578497272659123323ab489b7` |
| Final candidate SHA | `38700d8973948754fd38cf23123773a20d20f5e2` |
| Candidate tree | `d9f86c4359f7b458caaf1817eeba51c1c8e8e0f9` |
| Master tree (unchanged) | `4f97927dfbe99e83000799eee44da328356e2bd4` |
| Release branch | `security/public-visibility-release` |
| Worktree | `C:\Users\GopaL\AppData\Local\Temp\kilo\visibility-release-wt` |
| PR | **https://github.com/gopal735/ScholarZone/pull/2** — OPEN, not merged, not deployed |
| `origin/master` | **unchanged at `573a983`** |
| Canonical production | `scholarzone-fwzj` · `https://scholarzone-fwzj.vercel.app` · `4edd154a3037` |
| Diff scope | **3 files, +965 / −2** |
| Database migration | none · new dependency: none · config change: none |

Classification labels: **OBSERVED FACT**, **PROVEN**, **DISPROVEN**, **PLAUSIBLE BUT UNPROVEN**, **UNKNOWN**.

---

## 1. Production State

**PROVEN — the vulnerability is live in production.**

| Project | Domain | Revision |
| --- | --- | --- |
| **`scholarzone-fwzj`** (canonical) | `https://scholarzone-fwzj.vercel.app` | **`4edd154a3037`** |
| `scholarzone` (stale secondary) | `https://scholarzone.vercel.app` | `3ee434c01f53` |

Production runs `4edd154`, which predates the fix. The public detail endpoint on
the canonical domain is therefore still the pre-fix, permissive one.

**OBSERVED FACT — this task changed nothing in production.** No merge, no deploy,
no data write, no Vercel configuration change. `origin/master` is still `573a983`.

---

## 2. Security Vulnerability

`GET /api/scholarships/{id}` resolved its row through a **bare primary-key
lookup**, while every other public surface applied the canonical visibility
predicate. The catalogue had **two universes, and the detail page was the larger
one**.

**PROVEN.** For any record outside the public universe, the endpoint leaked:
title, provider, official source URL, deadlines, requirements, documents,
eligibility, funding and image metadata. Reachable by walking ids — no search, no
privilege, no credential.

**PROVEN.** It was also an existence oracle. A hidden id returned a full record
where a missing id returned a 404, so the endpoint answered *"does this id exist?"*
for every row in the table, including records deliberately withdrawn from the
catalogue.

**Severity reasoning.** The exposed fields are scholarship records the project has
chosen not to publish: unresolved verification, quarantine (a trust decision), and
archived rounds. Quarantined rows in particular are withheld *because* they are
suspect, so publishing them inverts the purpose of the quarantine. Impact is
confidentiality and trust-integrity, not integrity of data or availability of
writes.

---

## 3. Root Cause

**OBSERVED FACT — the exact path.**

```
GET /api/scholarships/{id}
  → routers/scholarships.py::get_scholarship_endpoint
  → services/scholarships.py:28   get_scholarship_details
  → repositories/scholarships.py:174  get_scholarship_by_id
  → session.get(Scholarship, scholarship_id)          ← no predicate
```

**OBSERVED FACT — `get_scholarship_by_id` has exactly three callers**, and the
distinction between them is the whole design problem:

| Caller | Contract | May read non-public rows? |
| --- | --- | --- |
| `services/scholarships.py:28` `get_scholarship_details` | **public detail** | **No — this was the bug** |
| `services/scholarships.py:79` `verify_scholarship` | admin, `X-Admin-Secret` | **Yes, by design** |
| `services/scholarship_verifier.py:228` | verification pipeline | **Yes, by design** |

**Root cause in one sentence.** A loader that is *deliberately* permissive for
trusted internal callers was also used by a public route, so the public boundary
was enforced nowhere on the detail path.

**PROVEN.** This was an omission, not a divergence. The list, stats, Match, Count
Intelligence, dashboard, Application Workspace and saved-scholarships surfaces all
already used `public_visibility_conditions()`. The detail endpoint was the **only**
public scholarship surface that did not.

**PROVEN.** Two structural guards already existed and constrained the fix:

- `tests/test_router_name_resolution.py` asserts `app.routers.scholarships` contains
  **zero** calls to `public_visibility_conditions()` — the router must delegate.
- The same test asserts exactly **one** `def public_visibility_conditions` in the repository.

---

## 4. Fix

One function, on the public read path:

```python
scholarship = session.scalar(
    select(Scholarship)
    .where(Scholarship.id == scholarship_id)
    .where(*public_visibility_conditions())
)
if scholarship is None:
    return None
```

Four properties, each a decision rather than a default:

1. **It calls the canonical predicate; it does not restate it.** A faithful copy
   would pass every behavioural test and still be a second source of truth — which
   is precisely how this codebase has been bitten before.
2. **The permissive loader is untouched**, so the admin verify endpoint and the
   verification pipeline keep their contract. Tightening the shared helper would
   have broken both without closing the hole.
3. **No `403`.** A hidden record takes the same code path as a missing one, so the
   pre-existing router 404 applies unchanged. No router change was needed.
4. **No router change, no schema change, no migration, no dependency, no
   configuration change.**

### Why not fix the shared loader

**PROVEN.** Doing so would have broken the verification pipeline, whose entire
purpose is to examine quarantined and archived records, and the admin verify
endpoint. Two structural tests now enforce the split: the public read must call the
predicate, and the shared loader must not.

---

## 5. Branch Provenance

Verified rather than assumed, per STEP 1.

| Question | Answer |
| --- | --- |
| Exact parent of `0ab5469` | `73e60279be572342a595d6fa02c97ced6d280cfd` |
| Exact branch tip (local / remote) | `0ab5469922ab3adda72c7237223c8329619d9df7` — identical |
| Is `0ab5469` directly on `573a983`? | **No** — its parent is the fix commit `73e6027` |
| **Is the fix directly on `573a983`?** | **YES** — `73e6027^` = `573a983b004ab08578497272659123323ab489b7` |
| `merge-base(origin/master, 0ab5469)` | `573a983` — the current master tip |
| Commits on master missing from the branch | **none** |

**Conclusion.** `0ab5469` is two commits *ahead of* current master on a perfectly
linear history, with **zero divergence**. It is based directly on `573a983`.

**Therefore STEP 2's port condition is not met, and no cherry-pick was performed.**
Cherry-picking onto master would have risked a conflict and produced a different
tree for no benefit; the brief also explicitly says not to cherry-pick blindly.

---

## 6. Current-Master Integration

A fresh isolated release branch was created from **current** `origin/master` and
fast-forwarded to the verified tip:

```
origin/master (573a983)  ──ff──▶  security/public-visibility-release (0ab5469) ──▶ 38700d8
```

| Check | Result |
| --- | --- |
| Release branch created from `origin/master` | yes, at `573a983` |
| Fast-forward only (`--ff-only`) | yes, no merge commit created |
| Candidate tree identical to `0ab5469` at that point | **YES** (`b946fada…`) |
| Commits on master absent from the candidate | **0** |
| Working tree after integration | clean |

One further commit, `38700d8`, added a single test (see §7). Product code was not
touched by it.

**PROVEN — the product-code delta versus current master is exactly one function**
(§10). No current-master behaviour is altered anywhere else.

---

## 7. Regression Tests

`backend/tests/test_public_detail_visibility.py` — **21 tests, all passing** on the
release candidate, run against the **real route** rather than the repository
helper.

| Required by the brief | Test | Result |
| --- | --- | --- |
| archived | `test_an_archived_record_is_not_readable_by_direct_id` | PASSED |
| quarantined | `test_a_quarantined_record_is_not_readable_by_direct_id` | PASSED |
| image-gated hidden record | `test_a_record_without_a_verified_image_…` and `test_a_third_party_image_only_record_…` | PASSED |
| verification-state-hidden record | `test_a_needs_review_record_…` and `test_an_uncertain_record_…` | PASSED |
| nonexistent ID | `test_a_hidden_record_and_a_missing_record_answer_identically` | PASSED |
| publicly visible record | `test_a_public_record_is_still_served` | PASSED |
| admin access to hidden record | `test_admin_verification_still_reaches_a_hidden_record`, `…_quarantined_record`, `…_requires_the_admin_secret`, `…_queue_still_lists_hidden_records` | PASSED |
| **verification-pipeline access to hidden record** | `test_the_verification_pipeline_can_still_reach_a_hidden_record` | PASSED |

**PROVEN — hidden and missing are indistinguishable**, asserted on both status and
body:

```python
assert hidden.status_code == missing.status_code == 404
assert hidden.json() == missing.json()
```

Also asserted: no internal field on a public record; **nothing serialised at all**
for a hidden one; list and detail agree on membership for every seeded id; and the
structural invariants of §3.

**PROVEN — the failure was demonstrated before the fix.** First run of the suite on
the unfixed tree: **11 failed, 9 passed**. After the fix: 21 passed.

**Note on one test's provenance.** `38700d8` added
`test_the_verification_pipeline_can_still_reach_a_hidden_record` because the
pipeline's access was previously covered only *structurally* — by asserting the
shared loader carries no predicate, which would still pass if a caller stopped using
the loader entirely. It is now asserted functionally, through the loader the
pipeline actually calls.

### Security contract, verified end to end

| Requirement | Evidence |
| --- | --- |
| HTTP 404 for non-visible | tests + real HTTP + browser |
| Empty / equivalent body | hidden body `''`; identical to missing |
| No distinguishable response | byte-identical page in the browser for hidden and missing |
| No internal fields | 11 internal field names checked; none present |
| No leakage via exception/message | the service returns `None`; the router's pre-existing 404 is unchanged |
| No existence oracle | identical status, body and rendered page |
| Public records still normal | `200` with title, provider and trust pair |
| Admin reaches hidden | `PATCH /scholarships/{id}/verify` on a quarantined id → `200`; unauthenticated → refused |
| Verification pipeline reaches hidden | quarantined and archived both returned by the pipeline's loader |
| Private saved/application refs unaffected | saved + application created; detail resolved correctly |

---

## 8. Full Test Verification

| Gate | Baseline (fix stashed, same tree) | Release candidate | Delta |
| --- | --- | --- | --- |
| Dedicated visibility tests | — | **21 passed** | +21 |
| Full backend suite | 4967 passed / 8 failed / 11 skipped / 13 warnings / 1 error | **4988 passed / 8 failed / 11 skipped / 13 warnings / 1 error** | **+21 passed, nothing else moved** |
| Frontend tests | 163 passed | **163 passed** (9 files) | 0 |
| Frontend lint | 0 errors, 1 pre-existing warning | **0 errors, 1 pre-existing warning** | 0 |
| Frontend build | pass | **pass** | 0 |
| Browser E2E | — | **11 / 11 steps, zero unexpected console errors** | — |

**PROVEN: zero new failures.** The delta is **+21 passed**, which is exactly the
new suite. Failures (8), skips (11), warnings (13) and errors (1) are **identical**.

**The 8 failures are the known pre-existing set**, verified by name — all in
`test_neon_migration.py`, which requires the untracked `migration_export.sql`
fixture: `TestMigrationHeaderParsing::test_actual_migration_file_header_not_in_executable_statements`,
`TestUtf8Encoding::{test_migration_file_is_utf8, test_em_dash_present_in_sql,
test_en_dash_present_in_sql}`, `TestBooleanConversion::test_migration_sql_has_true_not_integers`,
`TestBindParameterDetection::test_detect_bind_params_real_migration_file_has_none`,
`TestValidateMigrationFile::{test_validate_real_migration_file, test_validate_real_file_in_report}`.

The 1 error is `scripts/artifact_smoke_test.py::test_endpoint`, also pre-existing.

**PROVEN.** No test was altered, skipped, xfailed or weakened. No migration
expectation was touched to manufacture a green suite — this release adds no
migration and so has no reason to.

**PROVEN.** Cross-system regression groups all green on the candidate: Match
**538**, Count **95**, Dashboard + Application Workspace + **Mentor 211**, Admin
verification centre/hardening/review **66**.

**Browser E2E provenance.** The E2E ran against the tree at `0ab5469`. The product
code is **byte-identical** between `0ab5469` and the candidate `38700d8` — verified
with `git diff --name-only -- backend/app/ frontend/`, which returned empty. The
only change is the additional test. The E2E evidence therefore carries over exactly.

---

## 9. Production Target

**PROVEN — two ScholarZone Vercel projects exist**, so the canonical one was
established from evidence rather than from the local linkage.

| | Canonical | Secondary |
| --- | --- | --- |
| Project name | **`scholarzone-fwzj`** | `scholarzone` |
| Project id | `prj_NLC71y3rKRIOduTla785AzEOEFL5` | — |
| Org | `team_hTBAjdC3hMGDgW2GOAb1Mbw8` (`gopal735s-projects`) | same |
| Domain | `https://scholarzone-fwzj.vercel.app` | `https://scholarzone.vercel.app` |
| Current revision | **`4edd154a3037`** | `3ee434c01f53` |
| Last update | 1h | 2h |

**Evidence that `scholarzone-fwzj` is canonical**, four independent strands:

1. The release brief states production is `4edd154`; only `scholarzone-fwzj`
   serves `4edd154a3037`.
2. It has the most recent deployment.
3. It is the project Vercel reports as linked to this repository.
4. Strand 3 alone would **not** have been sufficient — which is why it was
   corroborated rather than relied on.

**OBSERVED FACT — `core/config.py:93-94` lists *both* domains in
`allowed_origins`.** That is a CORS allow-list, **not** evidence of canonical
status, and it is recorded here so nobody later mistakes it for one.

**Expected post-merge path.**

- `/api/health` derives `revision` from `VERCEL_GIT_COMMIT_SHA`, which Vercel
  injects for the exact commit it built — so the endpoint describes the artefact
  actually running, not a remembered label.
- After merge and deploy, `https://scholarzone-fwzj.vercel.app/api/health` should
  report the **12-character prefix of whichever commit was deployed**.
- If master is fast-forwarded, that is `38700d8` → `38700d897394`. If GitHub
  creates a merge commit, it is that new SHA.
- **Independently of the SHA, the deployed tree must be `d9f86c4359f7b458caaf1817eeba51c1c8e8e0f9`.**
  That tree hash is the durable check, because a SHA can differ while the artefact
  is identical.

**Deployment risk that needs an operator decision.** Releasing to the `scholarzone`
project instead would leave the user-facing domain on the vulnerable build while
appearing to have shipped the fix. **Recommend confirming the target project
explicitly before deploying.**

No Vercel configuration was changed in this task.

---

## 10. Exact Diff Scope

```
base SHA           : 573a983b004ab08578497272659123323ab489b7
final candidate SHA: 38700d8973948754fd38cf23123773a20d20f5e2
files changed      : 3
diffstat           : 3 files changed, 965 insertions(+), 2 deletions(-)
```

| File | +/- | Role |
| --- | --- | --- |
| `backend/app/services/scholarships.py` | +32 / −2 | **the security fix** |
| `backend/tests/test_public_detail_visibility.py` | +458 / −0 | new — 21 regression tests |
| `PUBLIC_SCHOLARSHIP_DETAIL_VISIBILITY_FINAL.md` | +475 / −0 | new — the fix's own report |

### Exact security behaviour changed

**One function, `get_scholarship_details`.** Its row resolution changes from
`session.get(Scholarship, id)` to a `SELECT` constrained by
`public_visibility_conditions()`. Consequences:

- `GET /api/scholarships/{id}` now returns **404** for archived, quarantined,
  `needs_review`, `uncertain`, and image-gated records, with an empty body
  identical to a nonexistent id.
- Publicly visible records are unaffected.
- The router, response schema, admin routes, verification pipeline, and every other
  service are **unchanged**.

### Excluded as forbidden — verified mechanically

`git diff --name-only 573a983 38700d8 | grep -Ei 'match|count|mentor|supervisor|application_workspace|image|ingest|logo|do_logos|scheduler|maintenance|models\.py|migrate_schema|requirements|auth'`
→ **empty.**

Not touched: Match 2.0 · Count Intelligence · Mentor · Supervisor Discovery ·
Application Workspace · image pipeline · ingestion · scheduler · maintenance ·
`models.py` · `migrate_schema.py` · `requirements.txt` · auth. No database data
change, no schema change, no dependency, no configuration change, no formatting of
unrelated files.

**The two markdown/report files are documentation of this security change**, not
unrelated feature work; they are listed separately above so a reviewer can drop
them without touching the fix.

---

## 11. PR

| | |
| --- | --- |
| URL | **https://github.com/gopal735/ScholarZone/pull/2** |
| Title | Security: public scholarship detail shared a larger universe than the public list |
| Base | `master` |
| Head | `security/public-visibility-release` |
| State | **OPEN** · not a draft · **not merged** · `mergedAt: (none)` |
| Mergeable | `MERGEABLE` |
| Scope | 3 files, +965 / −2 |

**PROVEN.** Exactly one PR was opened by this task. PR #1
(`release/mentor-hardening-pr`, *"fix: make every verified Mentor claim
auditable"*) belongs to another actor and was **not** touched, branched from, or
merged.

**`origin/master` was not moved.** Git was used for `fetch`, `worktree add`,
`merge --ff-only`, and `push` of a single named branch only. No `git add .`, no
`git add -A`, no `reset --hard`, no `git clean`, no force push, no rebase, no
amend of another actor's commit. Nothing was deployed from a non-default branch.

---

## 12. Release Recommendation

## Classification: **READY_TO_MERGE**

Justification, tied to evidence rather than confidence:

- **PROVEN** — the bypass is reproduced, fixed, and the fix is proven to close it
  (11 failures before, 21 passes after).
- **PROVEN** — hidden records are byte-indistinguishable from nonexistent ones.
- **PROVEN** — every trusted internal caller keeps its access, asserted both
  structurally and functionally.
- **PROVEN** — one canonical predicate, called not copied; the router and the
  shared loader invariants are enforced by tests.
- **PROVEN** — zero new failures across the full backend suite, and no test was
  weakened. Product code is byte-identical to the tree that passed browser E2E.
- **PROVEN** — the diff is one function plus its tests and documentation, with
  every forbidden area mechanically excluded.
- **PROVEN** — the candidate is a strict fast-forward of current master, so
  merging cannot conflict or drop concurrent work.

### Conditions on the merge

1. Merge **without** squash-merging the report away if you want the provenance
   record; otherwise note that the tree hash will change.
2. Confirm the deploy target is **`scholarzone-fwzj`**, not the stale `scholarzone`
   project (§9).
3. After deploy, verify `/api/health` reports the new revision **and** spot-check a
   known non-public id returns 404 with an empty body.
4. Confirm the deployed tree is `d9f86c4359f7b458caaf1817eeba51c1c8e8e0f9`.

### Why this should not wait for a batch

The vulnerability is **live**, unauthenticated, and enumerable. It publishes
records the project has deliberately withdrawn — including quarantined rows, which
are withheld *because* they are suspect. Given the fix is one function, 21 tests,
zero regressions and three files, the cost of releasing it alone is lower than the
cost of leaving it open another cycle. This release is deliberately isolated and
must not be bundled with feature work.

---

## 13. Remaining Pre-existing Issues

Reported, not fixed, and **deliberately excluded from this release** per STEP 7.

1. **Environment leak in `tests/test_visibility_count_consistency.py:53-55`.**
   Sets `SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED`,
   `SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED_IMAGE` and
   `SCHOLARZONE_PUBLIC_ALLOW_THIRD_PARTY_IMAGE` via bare `os.environ[...]` at
   import time and **never restores them**, so they leak into every test collected
   later in the same process. **PROVEN** independent of this change: running that
   file together with `test_stats_universe_scope.py` fails the latter
   (`assert 5 == 6`) **with the fix stashed as well as applied**.
   **PLAUSIBLE BUT UNPROVEN:** this may also explain why the full-suite baseline is
   8 failures rather than 9 — collection order may be suppressing or exposing a
   case. **Recommendation:** a separate hygiene fix using `monkeypatch`, as
   `test_public_quality_gate.py` already does.

2. **The public universe is configuration-dependent.** With
   `SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED=false`, a `needs_review` record *is*
   publicly readable — by design, and that is why the suite runs with the gates on.
   **UNKNOWN:** whether any deployment sets these flags differently from production.
   The archive and quarantine clauses cannot be configured away; the verification
   and image gates can.

3. **A public GET still writes.** `get_scholarship_details` repairs `NULL` list
   columns and calls `session.commit()`. Pre-existing, observed during the audit,
   **not changed** — it is not a visibility defect, and altering it would exceed
   this task's scope. It does mean an anonymous request can cause a database write.

4. **Other id-addressed read paths were not re-audited.** I enumerated every caller
   of `get_scholarship_by_id` and proved the public one is fixed.
   **PLAUSIBLE BUT UNPROVEN:** none of the others is publicly reachable without a
   secret — `admin_image_review.py` and `admin_verification.py` each add their own
   narrow conditions and both are admin-gated. A full enumeration of public
   `SELECT … WHERE id =` paths would be worth a separate pass.

5. **Closed-but-not-yet-archived records stay public.** Correct today, since the
   retire job is what archives them. **UNKNOWN:** how long that window can be if
   the maintenance schedule is missed — a link to a long-closed round keeps working
   until the record is archived.

6. **A stale duplicate production project exists.** `scholarzone.vercel.app` runs
   an older revision and is listed in `allowed_origins` alongside the canonical
   domain. **PLAUSIBLE BUT UNPROVEN:** it may be serving users who then miss
   security fixes deployed only to the canonical project. Worth confirming whether
   it should be retired or kept deliberately in step.

7. **Deployment cadence.** With no automated Vercel deploy, the window between
   merge and release is however long a human takes. For a live, unauthenticated
   enumeration vulnerability, that latency is part of the exposure.