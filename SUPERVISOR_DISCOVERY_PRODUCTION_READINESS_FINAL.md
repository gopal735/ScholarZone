# Supervisor Discovery 1.0 — Production Readiness Final

**Final classification: `NEEDS_HARDENING`**

Not `READY_FOR_STAGING`, because the feature has never successfully extracted a
single professor from a live university site, and the one real pilot that ran to
completion exposed a real defect in the faculty-listing detector. Not `BLOCKED`,
because nothing found is architecturally unsound, the canonical identity was
reused rather than duplicated, and every invariant that can be checked without a
live crawl passes.

Nothing was deployed. No production database was written. No catalogue-wide crawl
was run.

> **This document supersedes `SUPERVISOR_DISCOVERY_1_FINAL.md` and
> `SUPERVISOR_DISCOVERY_DATA_QUALITY_FINAL.md`.** Those were written against
> local `8ac1c9a4`, 79 commits behind master, and contain three claims this gate
> disproved: that no student authentication exists, that Student Dashboard and
> Application Workspace do not exist, and that there is no frontend test runner.
> All three are false on current master. Those two files are left uncommitted as
> historical artifacts; where they disagree with this document, this document is
> correct.

---

## 1. Current Master

| Fact | Value |
|---|---|
| Local `HEAD` | `8ac1c9a40063221904c8994693ffa18746d5fa9d` |
| `origin/master` | `573a983b004ab08578497272659123323ab489b7` |
| Relationship | `HEAD` is a **strict ancestor** of `origin/master` |
| Divergence | `origin/master` is **79 commits ahead**; local-only commits: **0** |

The earlier implementation in the shared working tree was built on `8ac1c9a4` —
79 commits stale. This is the single most consequential finding of the gate, and
it is why everything below was rebuilt on a clean worktree at `origin/master`.

### What 79 commits changed, and why it mattered

`origin/master` now contains the systems the specification assumed existed and
which the earlier audit reported as absent:

- `backend/app/routers/auth.py` — a committed student auth router
- `backend/app/routers/applications.py` — Application Workspace
- `backend/app/routers/dashboard.py` — Student Dashboard
- `backend/app/routers/mentor.py` — GROUNDed AI Mentor 1.0
- models `User`, `UserSession`, `StudentProfile`, `SavedScholarship`,
  `ApplicationRecord`, `ApplicationChecklistItem`
- `backend/app/dependencies.py` — `current_user` / `require_user`
- Vitest configured as the frontend runner (`vitest run`, jsdom,
  `@testing-library/react`)

**Two prior audit conclusions were stale-base artifacts and are hereby retracted:**

| Earlier claim | Status |
|---|---|
| "There is no student authentication" | **False on master.** `User`/`UserSession` + `/auth/*` exist. |
| "Student Dashboard and Application Workspace do not exist" | **False on master.** Both exist. |
| "There is no frontend test runner" | **False on master.** Vitest is configured and has existing suites. |

The earlier build's `students` / `student_sessions` tables, its
`core/student_auth.py`, its `/auth/register|login|me|logout` routes and its
frontend `authService` rewrite were therefore **a second competing identity
system**, which Phase 5 forbids. All of it was deleted. Outreach now keys to
`users.id` and resolves identity through master's own
`app.dependencies.require_user`.

A board note asserting the stale claims was posted and explicitly retracted.

## 2. Clean Baseline

Two worktrees, both from `origin/master`:

| Worktree | Path | State |
|---|---|---|
| Baseline | `%TEMP%/kilo/sz-baseline` | detached at `573a983`, 0 dirty files |
| Feature | `%TEMP%/kilo/sz-supervisor` | branch `feat/supervisor-discovery-1` from `573a983` |

### The two reported failures, classified properly

The earlier report labelled both failures "pre-existing". That label was wrong for
one of them, and Phase 1 requires evidence rather than position on the file list.

| Failure | Clean `origin/master` | Classification |
|---|---|---|
| `test_efficiency_safety::TestRetryPolicy::test_the_retry_shares_the_concurrency_group` | **FAILS** | **Environment/tooling-only.** `ModuleNotFoundError: No module named 'yaml'` — the dev dependency is absent from the virtualenv. Nothing to do with any code change. |
| `test_image_discovery::TestHumanReviewRouting::test_non_content_image_with_license_still_rejected` | **PASSES** | **Contaminated by another actor's uncommitted work.** It failed only in the dirty shared tree, which carries 193 lines of uncommitted changes to `image_validator.py` that predate this work. It is *not* pre-existing on master, and *not* introduced here. |

Re-running both files produced the **identical 9-failure set** on the clean
baseline and on the feature worktree, which is the actual evidence that this
feature introduces no regression. The remaining 8 failures are all
`FileNotFoundError: migration_export.sql` — a generated, gitignored artifact that
does not exist in a fresh worktree, on either tree.

### Suite results

| Run | Result |
|---|---|
| Supervisor feature suites | **119 passed**, 0 failed |
| Full backend, feature worktree | **5 079 passed, 9 failed, 11 skipped** |
| Same 9 failures on clean baseline | **identical** → 0 introduced |
| Frontend `vitest run` | **172 passed** (10 files) |
| Frontend `npm run lint` | **0 errors**, 1 pre-existing warning (`HomePage.jsx`) |
| Frontend `npm run build` | **success** |
| Migration/worker safety verification | **67/67 checks passed** |

An earlier full-suite run was discarded rather than reported: source was edited
while it was still executing, which makes its result untrustworthy. The numbers
above come from a clean re-run with no concurrent edits.

## 3. Supervisor Scope

Seven new tables, no new identity, no change to `app/models.py`.

| Table | Purpose |
|---|---|
| `scholarship_supervisor_coverage` | exactly one discovery state per scholarship |
| `professor_profiles` | one academic, deduplicated on `official_profile_url` |
| `scholarship_professor_links` | relationship + provenance |
| `supervisor_source_evidence` | per-page retrieval record with content hash |
| `professor_availability` | per-scope answer, source and date required |
| `contact_templates` | editable templates mirrored from code |
| `professor_outreach_records` | private, keyed to `users.id` |

The models live in a new `app/models_supervisor.py` rather than being appended to
`app/models.py`. This was a deliberate rebase decision: `models.py` is the file
every schema change contends over, and `Base.metadata` is what `create_all`
reads, so a name collision there breaks startup at the point of creation. Keeping
the feature's tables in their own module means **master's `models.py` is
untouched**, and this feature's schema cannot collide with concurrent model work.

## 4. Database/Migration Safety

One DDL source of truth, `app/supervisor_ddl.py`, imported by **both** the
startup/dev upgrade path (`app/database.py`) and the production migration script
(`backend/migrate_schema.py`). Written twice would be how a column ends up
present in one path and absent in the other, invisibly, until production fails.

`scripts/supervisor_verify_safety.py` checks this statically and exits non-zero on
any violation. **67/67 passed:**

- **Additive only.** No `DROP`, `ALTER`, `DELETE`, `TRUNCATE` or `UPDATE` in any
  statement, on either dialect.
- **No existing table is altered.** No new table name collides with `scholarships`,
  `users`, `user_sessions`, `student_profiles` or `application_records`.
- **No nullable→non-nullable change to an existing column.** All 7 tables are new,
  so no existing column's nullability changes.
- **Foreign keys point at canonical parents**, verified per table. Outreach keys to
  `users(id)` — asserted explicitly, because a second identity table is the exact
  regression Phase 5 forbids.
- **Unique constraints are intentional** and one per table: coverage on
  `scholarship_id`; professor on `official_profile_url`; relationship on
  `(scholarship_id, professor_id, relationship_type)`; evidence on
  `(professor_id, source_url, source_type)`; availability on `(professor_id, scope)`;
  outreach on `(user_id, scholarship_id, professor_id)`.
- **Provenance is structurally required.** `evidence_source_url` is `NOT NULL` on
  relationships; `source_url` and `verified_at` are both `NOT NULL` on
  availability. A claim without a source and a date cannot be represented.
- **Coverage uniqueness is enforced at DB level** by
  `uq_supervisor_coverage_scholarship`, not only by application logic.
- **Indexes support the real lookup paths**, checked per table. A `UNIQUE`
  constraint already indexes its columns on both engines, so no redundant index is
  added over a unique column.
- **No startup migration assumption.** `app/main.py` returns before any DDL in
  production. Verified by reading it, not assumed.

**Downgrade behaviour**: there is no `DROP`. `scripts/supervisor_backfill.py
--rollback-coverage` deletes coverage rows only, and deliberately leaves
professors, links, evidence and outreach intact — those are verified public facts
or a student's private history.

**Explicit production migration procedure** (production does not migrate at
startup, so this is out-of-band and separate):

```
SCHOLARZONE_DATABASE_URL=<neon dsn> python migrate_schema.py --dry-run
SCHOLARZONE_DATABASE_URL=<neon dsn> python migrate_schema.py --validate-only   # exit 1 if missing
SCHOLARZONE_DATABASE_URL=<neon dsn> python migrate_schema.py                   # apply
SCHOLARZONE_DATABASE_URL=<neon dsn> python migrate_schema.py --validate-only   # re-verify
python scripts/db_state.py                                                     # before/after diff
```

`_validate_postgresql_schema` now also asserts the 7 supervisor tables by name,
so a missing table is a named startup failure rather than a 500 on the first
public supervisor request. **Not executed against Neon.**

## 5. Production Universe Contract

The universe is **not** "every row in the table". It is
`CountUniverse.CATALOGUE` — every record `public_visibility_conditions()` permits
to be shown — which is the same population Count Intelligence's catalogue total
already describes. Restating it would create a second answer to "what population
is this count about".

`supervisor_universe_report(db)` returns:

- `universe`: `CATALOGUE`
- `universe_predicate_source`: `app.repositories.scholarships.public_visibility_conditions`
- `universe_size`, `covered_in_universe`, `uncovered_in_universe`
- `coverage_rows_outside_universe` — counted, not deleted

Backfill covers a **superset** (every row, archived included) because coverage
records *what was searched*, not what is currently offered. Holding a coverage row
is not a publication decision: the public API applies the visibility predicate
independently, so a coverage row can never make a hidden scholarship readable.
That independence is asserted by test, not assumed.

### Measured on the local catalogue (scratch copy, master code)

| Measure | Value |
|---|---|
| Total scholarship rows | 722 |
| Coverage rows | 722 |
| Coverage invariant holds | **true** |
| **CATALOGUE universe size** | **484** |
| CATALOGUE universe covered | **484** |
| Universe invariant holds | **true** |
| Coverage rows outside universe | 238 (archived / gated, retained deliberately) |
| Verified supervisors / professors / links / emails | 0 / 0 / 0 / 0 |
| Relationships without evidence | 0 |
| Verified relationships on a non-authoritative source | 0 |
| Availability claims without a source | 0 |
| Duplicate professor profiles / orphan links | 0 / 0 |

**484 is the local development catalogue universe, not production.** Production
public catalogue measured live: **358**. The two databases hold different
content. No production number is guessed.

### Explicitly tested boundary cases

| Case | Expected | Test |
|---|---|---|
| archived | outside universe, no public data | `test_archived_scholarship_exposes_no_supervisor_data` |
| quarantined | outside universe, 404 | `test_quarantined_scholarship_exposes_no_supervisor_data` |
| needs_review | **inside** universe (a trust label, not a gate) | `test_needs_review_scholarship_is_visible_and_may_carry_supervisors` |
| source_blocked | a coverage state, not a visibility gate | `test_source_blocked_scholarship_is_not_exposed` |
| non-public (gated) | 404 | `test_absent_scholarship_is_indistinguishable_from_hidden` |
| retired/merged professor | excluded from the public list, row retained | `build_supervisor_list` filters `profile_status == "merged"` |

`needs_review` is deliberately **inside** the universe. Master's canonical
predicate does not gate on it; inventing a stricter rule inside the supervisor
feature would make supervisor data and catalogue data disagree about what exists.

## 6. Public Visibility Security

Every public supervisor route derives eligibility through
`get_public_scholarship_or_404`, which applies `public_visibility_conditions()`.
The predicate is **reused, never restated**.

The known pre-existing leak in the scholarship **detail** route
(`repositories/scholarships.py:157-158` is a bare `session.get`, and
`routers/scholarships.py` returns 200 for archived/quarantined rows by direct id)
is **not copied**. Confirming it exists was the single most useful output of the
early audit.

Tested:

| Condition | Result |
|---|---|
| archived scholarship | 404 on `/supervisors` and `/supervisor-summary` |
| quarantined scholarship | 404 |
| absent scholarship | 404, **byte-identical body** to the hidden case |
| verified + public | supervisor data appears, gated on its own evidence contract |
| professor public via one scholarship, hidden via another | readable only through the visible one |

The last one matters: a professor who is legitimately public for scholarship A
does not become readable through hidden scholarship B that happens to link them.

The verification and counting contracts are **not weakened**. `CATALOGUE_PREDICATE_SOURCE`,
`verification_contract.py`, Match 2.0 weights and the Count Intelligence universe
are untouched. `CATALOGUE_PREDICATE_SOURCE` is now *read* by the supervisor
coverage report rather than duplicated.

## 7. Auth Security Review

The earlier build introduced its own session system. That was a prerequisite when
it was written and is a **duplicate** on master. It was deleted. What remains:

| Property | Position |
|---|---|
| Identity source | `app/dependencies.require_user`, shared with Dashboard and Application Workspace |
| Session storage | master's `UserSession`, hashed token, `revoked_at` |
| Cookie | master's `scholarzone_session`; `HttpOnly`, `SameSite=Lax`, `Secure` in production |
| Password hashing | master's PBKDF2-HMAC-SHA256 (`app/services/auth.py`) — **not** reimplemented |
| Second auth surface | **none.** Asserted by test: `/auth/*` is exactly `login`, `logout`, `register`, `session` |
| Secret committed | none. No new secret, key or DSN added |
| `user_id` from client | never accepted; ownership is a `WHERE` clause, not a post-check |
| Cross-user access | **404, not 403** — a 403 would confirm the record exists |
| Unauthenticated | 401 on every private route |
| Stale write | 409 via `version`; the newer note survives |
| Illegal transition | 422; `sent → positive` is refused and must pass through `replied` |
| Private data in public responses | asserted by grepping the response body for `notes`, `draft_body`, `user_id`, the account email, and the private note text |
| Rate limiting | 120 reads/min, 20 drafts/min, 60 writes/min per user (in-process, documented as such) |

**Production secret configuration**: not applicable to this change. It adds no
secret and reads none; the session secret remains whatever master already manages.
Nothing is printed, logged or exposed.

One residual, honestly stated: the rate limiter is **in-process**, so it bounds
one application instance only. A multi-instance deployment needs shared state.
That limitation is labelled in the module docstring rather than papered over.

## 8. Real University Pilot

One pilot, read-only, no persistence. `scripts/supervisor_pilot_readonly.py`
imports the worker's fetch and extraction functions and calls **none** of its
persistence functions — no `upsert_professor`, no `upsert_link`, no
`record_evidence`, no `record_availability`, no session, no commit. The only
database access is a read-only SQLite open to choose the target.

Three real institutional hosts, chosen because their own scholarship record names
the institution and its URL is on that institution's domain.

| Target | Host | robots | Page | Faculty links | Candidates |
|---|---|---|---|---|---|
| 175 Erasmus University Rotterdam | `www.eur.nl` | allowed | **unreachable** | — | — |
| 193 University of Adelaide | `adelaide.edu.au` | allowed | 200, 158 947 B | 3 | **0** |
| 63 Michigan State University | `admissions.msu.edu` | allowed | 200, 730 696 B | 11 | **0** |

Erasmus was reported honestly as `SOURCE_BLOCKED` — a retryable access failure,
**not** a negative result. No candidate was evaluated, which is the correct
outcome and not a failure of the harness.

Adelaide: `staff.adelaide.edu.au` was unreachable and correctly skipped as
*"blocked, not an empty page"*. `adelaide.edu.au/people/` returned 200 with **0
candidates**.

### Why zero candidates — and the defect it found

`scripts/supervisor_pilot_diagnose.py` separated "our extractor is broken" from
"these pages are JavaScript-rendered":

| Measurement | Value | Reading |
|---|---|---|
| bytes | 131 532 | substantial markup |
| anchors | 151 | links exist |
| visible text chars | 5 087 | almost no prose |
| **text/markup ratio** | **0.039** | **JavaScript shell** |
| `/people/` links | 2 | both the directory link itself |
| script tags | 33 | client-rendered |

**The extractor is not broken. The page publishes no person links in HTML.**
Producing zero professors here is the correct result.

But the diagnosis also exposed a **real defect in this codebase's code**. The
faculty-listing detector accepted any link containing the word "academic", so on
the MSU pilot it selected `/academics` and `/academics/research` as faculty
directories — subject-area navigation that lists nobody. Each consumed a request
from a budget meant for pages that might publish names.

Fixed: the detector now requires a *people* signal — a path segment
(`/people`, `/person`, `/staff`, `/faculty`, `/directory`, `/profiles`) or an
anchor phrase (`our faculty`, `staff directory`, …). Two regression tests added
naming the observed URLs.

**Honest verdict: the pilot produced zero verified professors from real
institutional sources.** Every field it would have returned was traceable to a
page, and no field was invented — but the pipeline has not yet demonstrated a
successful real extraction. That is the reason this is `NEEDS_HARDENING` rather
than `READY_FOR_STAGING`.

## 9. Negative/Blocked Cases

| # | Case | Honest state | Proof |
|---|---|---|---|
| 1 | robots-disallowed source | request refused | `test_robots_disallow_prevents_the_request`; live: robots gate ran before every fetch on 3 hosts |
| 2 | unreachable source | `source_blocked`, never a negative | `test_an_unreachable_source_produces_no_professor`; live: Erasmus (175) |
| 3 | faculty page exists, nobody listed | `no_verified_supervisor_found`, explicitly *not* "no professors exist" | `test_a_page_read_successfully_with_no_faculty_link_is_a_true_negative`; live: Adelaide |
| 4 | page says "not accepting students" | `verified_no` | `_derive_availability` checks refusal phrases **first** — "not accepting students" contains the affirmative substring "accepting students", so ordering is load-bearing |
| 5 | generic-word false alignment | never `moderate` | `test_generic_word_does_not_manufacture_moderate_alignment` — requires ≥2 significant words |
| 6 | malformed research label | label punctuation stripped, prose ignored | `test_prose_mentioning_research_yields_no_areas`; live: no research areas invented |
| 7 | duplicate professor identity | one row via unique `official_profile_url` | `test_duplicate_professor_is_refused_by_the_database` |
| 8 | missing official email | `not_published` + "use the official page" | `test_availability_defaults_to_not_published_rather_than_a_guess`, `test_unverified_email_is_withheld_even_when_stored` |
| 9 | unknown availability | `unknown` / `not_published`, per scope | `test_a_presence_never_decays_into_stale`, absences never become `stale` |

Case 4 was itself a bug this suite caught earlier: the affirmative phrases were
tested first, so a refusal was read as an offer.

A tenth defect was caught by the frontend test suite: the professor card rendered
`official_email` whenever it was truthy, relying solely on the API to withhold
unverified addresses. The component now gates on `official_email_verified` itself,
so a guess cannot be displayed by any caller.

## 10. Frontend Verification

Master has Vitest configured. **No dependency was added** — jsdom,
`@testing-library/react` and vitest are already declared; the only change is a
`test.environment = 'jsdom'` block in `vite.config.js`, which alters nothing about
the build.

| Gate | Result |
|---|---|
| `npm test` | **172 passed**, 10 files |
| `npm run lint` | **0 errors** (1 pre-existing warning in `HomePage.jsx`) |
| `npm run build` | **success** (603 kB / 168 kB gzip) |

New `SupervisorPanel.test.jsx` — 9 tests driving the component through its real
fetch path with `fetch` mocked:

- completed search with nothing found — and the copy must still say *not that no
  professors exist*
- unsearched record is visually distinct from a negative result
- blocked source reported as a temporary access problem
- verified professor shows evidence, availability state and the no-email
  instruction
- **no probability, response rate or success rate anywhere in the rendered text**
- error state, loading state
- signed-out visitor sees the public list unchanged
- an unverified stored email is never rendered

States verified: loading, error, none-verified, not-searched, blocked,
verified-with-evidence, unauthenticated. Card/detail consistency: the card renders
`Potential Supervisors · N` **only** when a verified count exists — a zero is never
rendered as `0`, because that reads as "this scholarship has no supervisors".

Responsive/a11y: 44 px minimum targets, visible `:focus-visible`,
`prefers-reduced-motion` honoured, availability state spelled out in text **and**
colour so colour is not the only channel.

**Browser E2E: NOT RUN.** No browser driver is available in this environment.
Per the absolute rules, this is **not** claimed as verified. The 25-step journey
remains unexecuted.

## 11. Production Backfill Plan

Prepared, **not executed**.

**A. Migration**
```
python migrate_schema.py --dry-run
python migrate_schema.py --validate-only      # exits 1 if any object missing
python migrate_schema.py
python migrate_schema.py --validate-only
```
Backup/snapshot first. Never on the application startup path.

**B. Coverage backfill** (idempotent, bounded, resumable)
```
python scripts/supervisor_backfill.py --coverage-only
```
Creates one row per missing scholarship, `search_pending`, asserting nothing.
Re-running is a no-op — verified on a fresh database and on a copy of the real
catalogue. Includes `--rollback-coverage`.

**C. Index/constraint validation**
```
python scripts/supervisor_verify_safety.py     # 67 static checks
python scripts/db_state.py                     # before/after object diff
```

**D. Worker enablement** — opt-in and staged:
```
python scripts/supervisor_backfill.py --discover --limit 10     # small first
python scripts/supervisor_pilot_readonly.py <id>                # verify by hand
```
Widen only after the first batches are hand-checked.

**E. Rollback**
```
python scripts/supervisor_backfill.py --rollback-coverage
```
Removes coverage rows only. Professors, links, evidence and outreach survive,
because they are verified public facts or a student's private history. Code
rollback is `git revert` of the single feature commit. No `DROP` was ever issued,
so no data restore is required.

**F. Post-migration invariants** — the script exits non-zero on any failure:

```
coverage_rows == CATALOGUE universe size                    (uncovered_in_universe == [])
duplicate coverage rows                                == 0  (uq constraint)
public professor links without authoritative evidence  == 0
professor links referencing non-public scholarships    == 0
fabricated emails                                      == 0  (verified_official_emails <= stored, unverified_emails_stored == 0)
fabricated availability claims                         == 0  (availability_without_source == 0)
```

## 12. Worker Safety

Worst case for the live catalogue of 358, at the enforced bounds:

| Bound | Value | Worst case for 358 |
|---|---|---|
| Workers | 8 (ceiling 16) | 8 concurrent, capped |
| Per-host delay | 1.0 s | serialised per host, so a single university is never hit concurrently |
| Pages / scholarship | 6 | ≤ 2 148 page fetches |
| Candidates / scholarship | 40 | ≤ 14 320 profile fetches |
| HTML per page | 400 KB | ~860 MB transferred worst case, ~57 KB/s per host at 1 s intervals |
| Faculty pages linked | 3 | bounded discovery fan-out |

The last row is the honest worst case and it is large. It is also why D is a
staged `--limit` rather than a single run, and why the worker is **not** enabled
as part of this release. At a 1 s per-host delay, a full catalogue is roughly
4–8 hours of wall clock and a few thousand requests. That is a deliberate,
scheduled activity, not a deploy-time step.

Verified statically (67/67) and by test: bounded workers, per-host delay enforced
before every request, robots checked before every fetch, page and candidate
budgets enforced, finite `polite_fetch` call sites, **no self-recursive crawl
function**, records scheduled via `next_check_at` rather than retried in a tight
loop. Partial-failure recovery: each scholarship runs on its own session and its
own commit, so one failing university cannot roll back a batch; failures are
recorded as `source_blocked` and retried on the next scheduled run. Blocked-source
persistence is explicit — `last_error_summary` is stored, never published.

## 13. Exact Changed Files

Branch `feat/supervisor-discovery-1` from `573a983b`. 7 modified, 22 added.

**Modified (7)**
```
backend/app/database.py                  supervisor DDL (both dialects) + validator
backend/app/main.py                      three routers registered
backend/app/schemas.py                   supervisor + outreach response models
backend/migrate_schema.py                REQUIRED_TABLES / REQUIRED_INDEXES
frontend/src/components/ScholarshipCard.jsx        CTA
frontend/src/pages/ScholarshipDetailsPage.jsx     panel
frontend/vite.config.js                  jsdom test environment
```

**Added (22)**
```
backend/app/models_supervisor.py         7 tables
backend/app/supervisor_ddl.py            single DDL source of truth
backend/app/core/rate_limit.py           bounded in-process limiter
backend/app/routers/supervisors.py       public read
backend/app/routers/outreach.py          private CRUD (require_user)
backend/app/routers/supervisor_email.py  draft + templates (require_user)
backend/app/services/supervisor_status.py       vocabulary + transitions
backend/app/services/supervisor_alignment.py    deterministic bands
backend/app/services/supervisor_freshness.py    staleness policy
backend/app/services/supervisor_public.py       public read model
backend/app/services/supervisor_coverage.py     coverage + invariants
backend/app/services/supervisor_discovery.py    the worker
backend/app/services/supervisor_email.py        deterministic drafting
backend/scripts/supervisor_backfill.py          backfill / report / rollback
backend/scripts/supervisor_verify_safety.py     67 migration + worker checks
backend/scripts/supervisor_pilot_readonly.py    no-persist real pilot
backend/scripts/supervisor_pilot_diagnose.py    JS-vs-extractor diagnosis
backend/tests/test_supervisor_discovery.py      42 tests
backend/tests/test_supervisor_outreach.py        34 tests
backend/tests/test_supervisor_worker.py          43 tests
frontend/src/services/supervisorService.js
frontend/src/components/SupervisorPanel.jsx / .css / .test.jsx
frontend/src/components/SupervisorCta.jsx / .css
```

**Deliberately absent**: `app/models.py`, `app/dependencies.py`,
`app/services/auth.py`, `app/routers/auth.py`, `frontend/src/services/authService.js`,
`frontend/src/components/AuthForm.jsx`, Match 2.0, counting, applications,
dashboard, mentor, image pipeline, admin verification, any CI workflow, any
`.env`, any database file, any production data dump. No patch scaffolding was
committed.

## 14. Tests

**119 supervisor tests**, all passing:

- `test_supervisor_discovery.py` (42) — coverage for every scholarship,
  idempotency, batch advancement, invariant and universe reports, blocked vs
  pending vs negative, duplicate professor and duplicate relationship refused by
  the database, one professor across two scholarships, public/private schema
  separation by body inspection, unverified relationship never published,
  unverified email withheld, internal error summary never public, the five
  visibility boundary cases, availability staleness, alignment bands, catalogue
  and Match isolation, validation, rate limiting.
- `test_supervisor_outreach.py` (34) — every private route 401, cross-user 404 for
  read/update/delete, a client-supplied `user_id` never honoured, idempotent
  create, illegal transition, unknown enum, 409 stale concurrency, markup and
  length limits, delete leaves the public fact intact, draft fabrication guards,
  draft bounded length, no second `/auth` surface.
- `test_supervisor_worker.py` (43) — host classification, faculty-link detection
  **including the pilot regression**, extraction excluding cross-institution links
  and link labels, no areas without a labelled section, email domain rules,
  availability phrasing including the refusal-ordering case, provenance, no
  duplicates across runs, non-institutional source refused, unreachable / 403 /
  404 / 429 / 5xx / timeout all distinguished from a negative, malformed HTML,
  robots disallow, robots fails closed, bounded concurrency measured.

**9 defects were found by these tests and fixed**, each of which would have
published a false statement: an unreachable source recorded as a completed
negative; "not accepting students" matching the affirmative substring; `blocked`
losing to `not_searched`; a card listing professors against a "none found"
counter; a single generic word producing `MODERATE` alignment; a label colon
stored as a research area; a successful fetch with empty content read as a page;
a coverage backfill that could not advance past its first batch; and the
frontend rendering an unverified email.

## 15. Remaining Risks

1. **No successful real extraction yet.** Three real institutions produced zero
   professors. The extractor is not broken — the directories are JavaScript-rendered
   (text/markup 0.039). Until one real page yields a verified professor end to end,
   the extraction heuristics are unproven.
2. **Recall will be low against real directories.** Server-rendered faculty pages
   are the exception, not the rule, on the hosts sampled. Expect a high
   `no_verified_supervisor_found` and `source_blocked` rate from any first run.
   Both are honest states, but a high blocked rate must be reported as such rather
   than quietly converted.
3. **The pilot detector fix is not yet re-validated against a real site.** It was
   verified against the recorded URLs in a unit test; a re-run against MSU is
   warranted to confirm the budget is spent better.
4. **No browser E2E.** No driver available. The 25-step journey is unexecuted.
5. **In-process rate limiting only.** One instance is bounded; a scaled deployment
   is not.
6. **Inherited, pre-existing and untouched: robots.txt is respected nowhere else in
   this repository**, including the image pipeline, which has a dead
   `respect_robots_txt` flag. The supervisor worker does respect it. This is a
   live compliance gap outside this feature's scope.
7. **The pre-existing scholarship detail leak remains.** Archived and quarantined
   records are still readable by direct id through `/scholarships/{id}`. This
   feature does not copy it; fixing it is separate work.
8. **Research alignment is `INSUFFICIENT_EVIDENCE` for everyone** until a student
   states interests. Master's account has no name field, so the draft sign-off is
   left as `[Your name]` and reported as unresolved rather than derived from the
   email address.
9. **9 pre-existing suite failures** remain (8 missing gitignored artifact, 1
   missing `yaml`). Unrelated, and unchanged by this work.
10. **No frontend E2E or visual regression check.**

## 16. Final Release Classification

# `NEEDS_HARDENING`

**Why not `READY_FOR_STAGING`**

The feature cannot yet demonstrate a single verified professor extracted from a
live institutional source. Everything that can be proven without that — schema
safety, coverage invariants, visibility isolation, identity reuse, ownership,
concurrency, provenance, frontend states, regression-freedom against master — is
proven. But "works correctly and has never successfully run against real data" is
not the same as ready, and the pilot that did run found a real defect in the
faculty detector. Deploying discovery in this state risks publishing professors
extracted by heuristics that have never been shown to work on a real directory.

**Why not `BLOCKED`**

Nothing is architecturally unsound. The canonical identity is reused rather than
duplicated, master is untouched in the files that matter, the visibility contract
is reused rather than restated, all schema changes are additive and idempotent,
every invariant checkable without a live crawl passes, and the work is committed
on an isolated branch with an explicit file list and a working rollback.

**Required to reach `READY_FOR_STAGING`**

1. Demonstrate one successful end-to-end extraction against a real,
   server-rendered faculty page, with every returned field traceable to its
   source. Use `supervisor_pilot_readonly.py`, then a hand-checked `--limit` run.
2. Re-run the pilot against the recorded MSU host to confirm the detector fix
   spends the request budget better.
3. Measure how many of the 358 production records have a derivable institutional
   signal, so `not_applicable` can be classified from evidence rather than left
   `search_pending`.
4. Run the browser E2E journey, or record formally that no driver is available.
5. Keep discovery opt-in. Do **not** add it to the maintenance worker; that
   pipeline is fragile shared machinery and §26 forbids it without proof.