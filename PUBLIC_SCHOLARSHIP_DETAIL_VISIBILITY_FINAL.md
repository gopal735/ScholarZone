# PUBLIC SCHOLARSHIP DETAIL VISIBILITY HARDENING 1.0 — FINAL REPORT

| | |
| --- | --- |
| Branch | `visibility-hardening` |
| Commit | `73e6027` |
| Base | `573a983` (`origin/master`) |
| Files changed | **2** — `backend/app/services/scholarships.py`, `backend/tests/test_public_detail_visibility.py` (new) |
| Production revision | `4edd154` — **unchanged. This task did not deploy.** |
| `origin/master` | `573a983` — **unchanged**; the branch was pushed, master was not |
| Database migration | **none** |
| New dependency | **none** |
| Mentor code | **not touched** |

Labels used throughout: **OBSERVED FACT**, **PROVEN**, **DISPROVEN**, **PLAUSIBLE BUT UNPROVEN**, **UNKNOWN**.

---

## 1. Executive summary

`GET /api/scholarships/{id}` resolved its row through a bare primary-key lookup
while every other public surface applied the canonical visibility predicate. The
catalogue therefore had **two universes, and the detail page was the larger one**.
Anything the list excluded — archived, quarantined, awaiting review, or failing
the image gate — remained fully readable by walking ids.

**PROVEN.** For a trust surface, the permissive surface being the one addressed by
id is the wrong way round: the list is the thing a student is steered away from,
and the detail URL is the thing they arrive at from a search result, a shared
link, or a stale bookmark.

The fix is one query on the public read path, applying the **canonical predicate
rather than a restatement of it**.

**PROVEN — the permissive loader was deliberately left alone.**
`get_scholarship_by_id` is shared with the verification pipeline and with the
administrator's verify endpoint, both of which must reach records that are *meant*
to be invisible to applicants. Tightening the shared helper would have broken
those without closing this hole. The boundary belongs on the public read, and
that is where it was placed.

**PROVEN.** A hidden id now answers **exactly** as a missing id does — same status,
same empty body — so the endpoint cannot be used to discover that a record exists.

| Result | Figure |
| --- | --- |
| New tests | **20 passed** |
| Full backend suite | **4987 passed / 8 failed / 11 skipped / 1 error** |
| Baseline (same tree, before the fix) | **4967 passed / 8 failed / 11 skipped / 1 error** |
| Delta | **+20 passed**, failures / skips / warnings / errors **identical** |
| Frontend | **163 passed**, lint **0 errors** — no frontend file changed |
| Browser E2E | **11 / 11 steps**, zero unexpected console errors |

---

## 2. Proven Visibility Bypass

**OBSERVED FACT — the exact path.**

```
GET /api/scholarships/{id}
  → routers/scholarships.py::get_scholarship_endpoint
  → services/scholarships.py:28   get_scholarship_details
  → repositories/scholarships.py:174  get_scholarship_by_id
  → session.get(Scholarship, scholarship_id)        ← no predicate
```

**OBSERVED FACT — every caller of that loader.** There are exactly three, and the
distinction between them is the whole design problem:

| Caller | Contract | May see non-public records? |
| --- | --- | --- |
| `services/scholarships.py:28` `get_scholarship_details` | **public detail** | **No — this was the bug** |
| `services/scholarships.py:79` `verify_scholarship` | admin verify, `X-Admin-Secret` | Yes, by design |
| `services/scholarship_verifier.py:228` | verification pipeline | Yes, by design |

**PROVEN.** Before the fix, `services/scholarships.py::get_scholarship_details`
reached every row regardless of state. Verified over real HTTP against an
isolated database where each record differs from a public one in exactly one
clause: ids 2 (archived), 3 (needs_review), 4 (quarantined) and 5 (no verified
image) all returned **200 with their full payloads**.

**PROVEN.** The public list and the public detail disagreed. In the same fixture
the list contained only the two public ids while detail served four more.

**PROVEN.** Existence was disclosed. A hidden id returned a full record where a
missing id returned a 404, so the endpoint answered "does this id exist?" for any
id in the table — including records deliberately withdrawn from the catalogue.

---

## 3. Architecture Audit

Inspected, per STEP 1.

| Surface | Visibility mechanism | Verdict |
| --- | --- | --- |
| `GET /api/scholarships` (list) | `_filter_conditions` → `public_visibility_conditions()` | correct |
| `GET /api/scholarships/stats` | `catalogue_counts` → same predicate | correct |
| `GET /api/scholarships/{id}` | **bare `session.get`** | **the bypass** |
| `POST /api/scholarships/match` | `match_scholarships` → `load_candidates` → same predicate | correct |
| Count Intelligence | `counting/catalogue.py` → same predicate | correct |
| Dashboard / Application Workspace | `load_facts_for_ids` / `load_contexts` → same predicate | correct |
| Saved scholarships | `dashboard._require_public_scholarship` → same predicate | correct |
| `PATCH /{id}/verify` | `X-Admin-Secret` gated, permissive loader | correct, intentional |
| `GET /scholarships/debug/raw/{id}` | `X-Admin-Secret` gated, dumps all columns | already hardened |
| `GET /admin/verification/queue` | predicate used to label public vs storage-only | correct |

**OBSERVED FACT — the detail endpoint was the only public scholarship surface not
using the predicate.** That is the precise boundary that was bypassed.

**OBSERVED FACT — two structural constraints already exist and were honoured:**

- `tests/test_router_name_resolution.py` asserts `app.routers.scholarships`
  contains **zero** calls to `public_visibility_conditions()` — *"the stats router
  delegates to the counting layer; if it starts calling the predicate again it has
  reintroduced a second counting implementation."* The fix therefore cannot live
  in the router.
- The same test asserts `source.count("def public_visibility_conditions") == 1` in
  the repository — there must be exactly one definition.

**PROVEN.** The fix was placed in the service, which satisfies both.

---

## 4. Canonical Visibility Contract

**OBSERVED FACT — the single definition** is `public_visibility_conditions()` at
`backend/app/repositories/scholarships.py:25`. Its clauses:

1. `verification_status != "quarantined"` — **unconditional**
2. `is_archived.is_(False)` — **unconditional**
3. if `public_require_verified`: `verification_status == "active"`
   (`AUTHORITATIVE_VERIFIED_STATUS`)
4. if `public_require_verified_image`: `image_url IS NOT NULL`,
   `image_verified_at IS NOT NULL`, and `image_source_type != 'wikimedia'` (or NULL)
   unless `public_allow_third_party_image`

**OBSERVED FACT — the verification contract is authoritative and separate.**
`verification_contract.py` defines `AUTHORITATIVE_VERIFIED_STATUS = "active"`,
`UNCERTAIN_VERIFICATION_STATUS = "needs_review"`, and `public_verified_from_status`
as strict equality against `"active"`. The in-repo comment on the predicate is
explicit that the legacy `is_verified` boolean *"is internal bookkeeping and Match
evidence scoring; it is never the authority for a public claim"*, because gating
on it once let a `needs_review` record be published on the strength of a stale
`True`.

**No new visibility enum was created, and `is_verified` was not used as an
independent authority.** PROVEN by a structural test that asserts the public read
calls `public_visibility_conditions()` and that the shared loader does not.

### "Retired" is not a visibility state in this codebase

**DISPROVEN.** The brief lists `retired` among the reasons a record may be outside
the public universe, and it is tempting to add a status filter for it. That would
be inventing visibility logic, which the absolute rule forbids.

**OBSERVED FACT.** The catalogue's own status vocabulary is
`ScholarshipStatus = open | upcoming | closing-soon | closed`. There is no
`retired`. The word appears only inside the maintenance job's vocabulary
(`{"closed", "expired", "discontinued", "retired", "withdrawn"}` and
`retired_records.json`), where retirement is *expressed* by setting
`is_archived = True`.

**Therefore the archived case is the retired case**, and it is tested as such. A
record whose round has closed but which has not yet been archived **remains
public** — which is correct: the catalogue is meant to show closed opportunities,
and the auto-delete/retire job is what eventually archives them.

---

## 5. Minimal Fix

One function, in `backend/app/services/scholarships.py`:

```python
scholarship = session.scalar(
    select(Scholarship)
    .where(Scholarship.id == scholarship_id)
    .where(*public_visibility_conditions())
)
if scholarship is None:
    return None
```

Three properties worth stating, because each was a decision rather than a
default:

1. **It calls the canonical predicate; it does not restate it.** A faithful copy
   would satisfy every behavioural test and still be a second source of truth —
   which is precisely how this bug's sibling problems have arisen in this codebase
   before.
2. **The permissive loader is untouched.** Verified by a structural test asserting
   `public_visibility_conditions` does *not* appear in
   `get_scholarship_by_id`, so the internal verifier's contract is protected by a
   test rather than by a comment.
3. **No `403`.** The service returns `None` and the existing router raises the
   same `404 "Scholarship not found"` it already raised for a missing id, so no
   code change was needed to avoid revealing existence.

No router change, no schema change, no migration, no dependency, no configuration
change.

---

## 6. Public / Internal Separation

**PROVEN — admin and internal access are intact.** Verified over real HTTP with
`X-Admin-Secret` against an isolated database:

| Check | Result |
| --- | --- |
| `PATCH /scholarships/4/verify` on a **quarantined** record | **200** |
| `PATCH` without the admin secret | **405** — refused |
| Admin queue contents | listed **every** hidden id: `1, 2, 3, 5, 6, 4` |
| Verification pipeline loader | unchanged, still permissive |

**PROVEN — private references still resolve.** Over real HTTP, with a signed-in
student: saving a public scholarship and starting an application on it both
succeeded, and `GET /api/applications/{id}` returned the correct name. The private
path uses the Application Workspace, which was not touched.

**PROVEN — no internal field reaches a public response.** Checked on both a public
and a hidden record for `verification_notes`, `verified_by`,
`next_verification_due`, `open_conflicts`, `legacy_is_verified`,
`legacy_agrees_with_status`, `scope`, `review_flags`, `conflicts`, `history`,
`decisions`. None present. The public detail still publishes the trust pair
applicants rely on: `verification_status: "active"`, `verified: true`.

**OBSERVED FACT.** `verification_notes` and `verified_by` are declared in
`schemas.py:274-275` on **`ScholarshipVerificationUpdate`** — the admin *write*
payload — not on any response model. The public detail schema was already clean.

---

## 7. Regression Tests

`backend/tests/test_public_detail_visibility.py` — **20 tests, all passing.**
Written against the **real route**, not the repository helper, because the helper
is shared with the verifier.

**The failure was demonstrated before the fix.** First run: **11 failed,
9 passed**. After the fix: **20 passed**. No test was written to match the fix
without first being shown to fail.

| Group | Tests | Covers |
| --- | --- | --- |
| `TestTheBypass` | 7 | archived, needs_review, quarantined, uncertain, no verified image, third-party-image-only, and list/detail membership |
| `TestPublicDetailStaysOpen` | 3 | public still 200; trust pair still published; list and detail agree on every seeded id |
| `TestExistenceIsNotRevealed` | 1 | hidden and missing answer identically — status *and* body |
| `TestInternalSurfacesKeepTheirAccess` | 4 | admin verifies hidden and quarantined; unauthenticated refused; queue still lists hidden |
| `TestNoInternalFieldLeakage` | 3 | no internal field on a public record; nothing serialised for a hidden one; non-numeric id still 422 |
| `TestCanonicalPredicateIsTheOneUsed` | 2 | the public read calls the predicate; the shared loader does not |

Each non-public case differs from the public fixture in **exactly one clause**, so
a 404 is attributable to that clause rather than to an incidental difference.

### The suite runs with the gates ON

**OBSERVED FACT.** `tests/conftest.py:30-31` sets
`SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED=false` and
`..._IMAGE=false` process-wide, because the long-standing seed rows carry no
images and predate the gate.

That is correct for listing and pagination tests and **wrong for this suite**:
production has both gates on, and the question here is whether the detail endpoint
honours the same rules as the list. The suite therefore switches them back on via
`monkeypatch` — the same mechanism `test_public_quality_gate.py` already uses —
so it tests the universe that actually ships. Without this, four of the seven
bypass cases would have passed vacuously.

### A suspicion I raised and then disproved

I initially believed three existing tests
(`test_public_admin_separation.py::test_public_still_publishes_the_authoritative_trust_pair`,
`test_admin_verification_hardening.py::test_trust_semantics_unchanged`,
`test_public_verification_contract.py::test_api_detail_never_contradicts_its_status`)
*enshrined the vulnerability*, because each seeds a `needs_review` record and reads
it through the public detail URL.

**DISPROVEN.** They pass — **25 passed** — and the reason is the conftest gate
setting above. Under the suite's own configuration `needs_review` *is* publishable,
so hiding it would contradict them. Because the fix honours whichever
configuration is active, **no existing test needed changing**. Their invariant —
`verified` tracks `verification_status` exactly — is untouched.

### A pre-existing test-isolation defect, found and reported not fixed

**PROVEN.** `tests/test_visibility_count_consistency.py:53-55` sets the three gate
variables with bare `os.environ[...]` at import time and **never restores them**,
so they leak into every later test in the same process. Running that file together
with `test_stats_universe_scope.py` fails the latter at line 358
(`assert 5 == 6`).

**PROVEN pre-existing, not a regression:** identical failure **with and without**
this change, verified by stashing the fix and re-running the pair.

Reported rather than fixed: it is outside this task's scope, and changing how an
unrelated test manages its environment could alter what that test proves.

---

## 8. Browser E2E

Real Chromium, real local backend (uvicorn), isolated SQLite database, real HTTP
through the Vite proxy. Seeded with six records, each differing from a fully
public one in exactly one clause, with distinctive sentinel titles so leakage
would be visible.

| # | Step | Result |
| --- | --- | --- |
| 1 | public detail opens | h1 **"VISIBLE Public Scholarship Alpha"**, *Provided by Provider 1*, *Verified listing / Verified active* |
| 2 | archived (`/scholarships/2`) | **Scholarship not found** |
| 3 | needs_review (`/scholarships/3`) | **Scholarship not found** |
| 4 | quarantined (`/scholarships/4`) | **Scholarship not found** |
| 5 | no verified image (`/scholarships/5`) | **Scholarship not found** |
| 6 | a genuinely missing id (`/scholarships/999`) | **byte-identical page to 2–5** |
| 7 | no hidden sentinel anywhere | `leaksArchived`, `leaksNeedsReview`, `leaksQuarantined`, `leaksNoImage` all **false** |
| 8 | public list healthy | h1 *All Scholarships*, shows Alpha, **no hidden title present** |
| 9 | Match healthy | h1 *Match*, 0px overflow |
| 10 | Dashboard healthy | h1 *Your scholarship command center* |
| 11 | Applications healthy | h1 *Your applications* |
| 12 | Mentor healthy | h1 *Mentor*, signed-in state |
| 13 | private references intact | saved + application created; detail resolved |
| 14 | console | **zero unexpected errors** |

**On console errors, stated honestly.** Three classes appeared and all three are
accounted for: `ERR_NAME_NOT_RESOLVED` from the fixture's placeholder
`provider.example` image hosts; nine `404`s from my own deliberate hidden/missing
probes, which are the correct behaviour being observed; and `favicon`. **No
application error and no unhandled rejection.**

The identity of the hidden page matters: it is the *same* not-found page a
non-existent id produces, so a student cannot tell a withdrawn record from a
mistyped link.

---

## 9. Security Verification

**PROVEN — non-disclosure.** Over real HTTP:

| Probe | Status | Body |
| --- | --- | --- |
| hidden id 2 | 404 | *(empty)* |
| missing id 999 | 404 | *(empty)* |
| identical | **yes** | **yes** |

**PROVEN — no field leakage.** Public detail response checked for all eleven
internal fields: none present. Hidden records return no body at all, so there is
no payload in which a field could have leaked.

**PROVEN — no status-code oracle.** No `403` is used anywhere; a hidden record and
a missing record take the same code path.

**PROVEN — configuration is not silently widened.** The predicate's unconditional
clauses (archive, quarantine) apply regardless of settings, so the two
highest-severity states cannot be disabled by a configuration flag. Only the
verification and image gates are settings-dependent, and they default to on.

**PROVEN — the fix cannot be bypassed by configuration of the shared loader.** A
structural test asserts the predicate is applied on the public read path, so the
guarantee is enforced by the shape of the code rather than by a value.

---

## 10. Cross-System Regression

| Suite | Files | Result |
| --- | --- | --- |
| Scholarship routes, visibility, verification, quarantine, router-name-resolution, stats | 13 | **260 passed**, 7 skipped, 1 pre-existing pollution failure |
| Match (`test_matching_api`, `_engine`, `_v2`) | 3 | **538 passed** |
| Count (`test_counting_api`, `_facets`, `test_stats_universe_scope`) | 3 | **95 passed** |
| Dashboard + Application Workspace + **Mentor** | 3 | **211 passed** |
| Admin verification centre, hardening, review centre | 3 | **66 passed** |
| **Full backend suite** | — | **4987 passed / 8 failed / 11 skipped / 1 error** |
| Baseline (same tree, fix stashed) | — | **4967 passed / 8 failed / 11 skipped / 1 error** |
| Frontend (unchanged files) | — | **163 passed**, lint **0 errors**, 1 pre-existing warning |

**PROVEN: zero regressions.** The delta is **+20 passed**, which is exactly the new
suite. Failures (8), skips (11), warnings (13) and errors (1) are all unchanged.

**The 8 failures are the known pre-existing set**, verified by name — all in
`test_neon_migration.py`, which requires the untracked `migration_export.sql`
fixture:

1. `TestMigrationHeaderParsing::test_actual_migration_file_header_not_in_executable_statements`
2. `TestUtf8Encoding::test_migration_file_is_utf8`
3. `TestUtf8Encoding::test_em_dash_present_in_sql`
4. `TestUtf8Encoding::test_en_dash_present_in_sql`
5. `TestBooleanConversion::test_migration_sql_has_true_not_integers`
6. `TestBindParameterDetection::test_detect_bind_params_real_migration_file_has_none`
7. `TestValidateMigrationFile::test_validate_real_migration_file`
8. `TestValidateMigrationFile::test_validate_real_file_in_report`

The 1 error is `scripts/artifact_smoke_test.py::test_endpoint`, also pre-existing.
**No test was altered, skipped, xfailed or weakened.** `migrate_schema.py` and the
`test_neon_migration.py` expectations were deliberately not touched to make the
suite green — this task adds no migration and so has no reason to.

---

## 11. Production Readiness

**PROVEN — this task did not deploy.** `origin/master` remains `573a983`;
production remains `4edd154`. The branch `visibility-hardening` was pushed and
master was deliberately not advanced, because pushing to master triggers the
deploy workflow and the brief forbids deploying here.

**Production therefore still carries the bypass.** That is expected and is the
single most important thing for whoever merges this:

> Until this commit reaches production, `GET /api/scholarships/{id}` on
> `scholarzone-fwzj.vercel.app` still serves archived, quarantined and
> needs-review records by direct id.

**Merge and verification checklist for the release:**

1. Fast-forward `master` to `73e6027` (merge; never rebase — `master` is shared).
2. Confirm `/api/health` reports the new revision.
3. Re-run the 20-test suite against the deployed tree.
4. Spot-check one known non-public id from the catalogue: expect **404**, and
   confirm the body is empty.

**Risk of the change itself: low, and bounded.** It adds a predicate to one
query on one route. The rows it newly hides were already hidden from the list, so
no count, list, Match or dashboard figure changes — verified by the unchanged
Count (95), Match (538) and stats suites. Student-facing surface change is limited
to bookmarked or shared links to withdrawn records, which will now show the same
not-found page as a bad link.

---

## 12. Remaining Risks

**1. The bypass is live in production.** It is fixed and verified locally, but
`origin/master` does not contain it. See §11.

**2. Pre-existing test-isolation defect.**
`tests/test_visibility_count_consistency.py:53-55` leaks three environment
variables process-wide with no restore. Any run that includes it can silently
change the visibility universe for every test collected after it — including, as
observed, a `test_stats_universe_scope` failure that has nothing to do with
either file. **PLAUSIBLE BUT UNPROVEN:** this may also be why the full-suite
baseline is 8 rather than 9 failures — the pollution may be suppressing or
exposing a case depending on collection order. Worth a separate hygiene fix.

**3. The public universe is configuration-dependent.** With
`SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED=false` a `needs_review` record *is* publicly
readable, by design. **UNKNOWN:** whether any deployment sets these flags
differently from production. The two unconditional clauses (archive, quarantine)
cannot be configured away; the other two can.

**4. A public GET still writes.** `get_scholarship_details` repairs `NULL` list
columns and calls `session.commit()`. Pre-existing, observed during the audit, and
**deliberately not changed** — it is not a visibility defect, and altering it would
change behaviour beyond this task's remit. It does mean an anonymous request can
cause a database write.

**5. Other id-addressed read paths were not re-audited.** I enumerated every
caller of `get_scholarship_by_id` and proved the public one is fixed, but other
modules that query `Scholarship` by id for other purposes were not all reviewed in
this task. **PLAUSIBLE BUT UNPROVEN:** none of them is publicly reachable without
a secret — `admin_image_review.py` and `admin_verification.py` both add their own
narrow conditions, and both are admin-gated. A full enumeration of public
`SELECT … WHERE id =` paths would be worth a separate pass.

**6. Closed-but-not-yet-archived records stay public.** Correct today, since the
retire job is what archives them. **UNKNOWN:** how long that window can be if the
maintenance schedule is missed — a link to a long-closed round would keep working
until the record is archived.

**7. Deployment cadence.** With no automated Vercel deploy, the window between
merge and release is however long a human takes to deploy. Given the severity, this
one is worth releasing deliberately rather than waiting for a batch.