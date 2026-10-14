# Supervisor Discovery — Current-Master Rebuild, Real-World Final

Every conclusion below is tagged. The tags are not decoration; two of them are
the reason this document exists.

- **PROVEN** — demonstrated against real institutional pages or against clean
  master, with the evidence named.
- **VALIDATED** — verified by test against the current codebase, but not yet
  observed on real institutional content.
- **UNKNOWN** — not established. Deliberately not filled in.
- **BLOCKED** — could not be established, and the blocker is named.

**Final classification: `NEEDS_HARDENING`**

No production deployment. No production database write. No catalogue crawl. `a70b667`
was not merged or pushed; the work was ported file-by-file onto a fresh worktree
at current `origin/master`.

---

## 1. Current Master

| Fact | Value | Tag |
|---|---|---|
| `origin/master` | `573a983b004ab08578497272659123323ab489b7` | PROVEN |
| Local `HEAD` | `8ac1c9a40063221904c8994693ffa18746d5fa9d` | PROVEN |
| Local master vs origin/master | 79 behind, 0 ahead | PROVEN |
| `origin/master` moved during this task | No — unchanged at `573a983` across two fetches | PROVEN |
| Fresh baseline worktree | `%TEMP%/kilo/szcm-baseline`, detached, 0 dirty | PROVEN |
| Feature worktree | `%TEMP%/kilo/szcm`, `feat/supervisor-discovery-current-master` | PROVEN |
| Shared dirty worktree | Untouched; `HEAD`, the other actor's `image_validator.py` (193 insertions) and every uncommitted file are as found | PROVEN |

25 worktrees exist from other actors. None was modified, removed or cleaned.
Notably `visibility-wt` and `visibility-release-wt` carry a separate live
visibility fix; this branch does not touch it (section 15).

## 2. Stale-Base Reconciliation

`a70b667` was **not** merged. Its file manifest was extracted and every file
re-verified before porting.

`a70b667`'s parent is `573a983` — byte-identical to the new worktree's base. So the
port is deterministic rather than a reconciliation of divergent content.

Manifest guard run against the 34 files of `a70b667`: **no Match, Count, Mentor,
Application, Dashboard, auth, image, `repositories/scholarships.py`,
`routers/scholarships.py`, `.env` or database file touched.** PROVEN.

## 3. Supervisor Scope

Seven tables, no identity, no change to `app/models.py`:

`scholarship_supervisor_coverage`, `professor_profiles`,
`scholarship_professor_links`, `supervisor_source_evidence`,
`professor_availability`, `contact_templates`, `professor_outreach_records`.

Models live in `app/models_supervisor.py`, importing `Base` from `app/models.py`,
so master's `models.py` is untouched and this feature's schema cannot collide with
concurrent model work. PROVEN.

Schema is additive and idempotent, described once in `app/supervisor_ddl.py` and
imported by both `app/database.py` and `backend/migrate_schema.py`. Production
still does not migrate at startup. PROVEN.

## 4. Auth Reuse

Master's identity is reused, never reimplemented. PROVEN by five independent checks,
all of them regression tests:

| Check | Result |
|---|---|
| Supervisor routers import | `from ..dependencies import require_user` — same as applications, dashboard, mentor |
| Local auth module | none exists |
| `user_id` foreign key | `users.id` |
| `/auth/*` paths registered | exactly `login`, `logout`, `register`, `session` |
| Master files untouched | `models.py`, `dependencies.py`, `services/auth.py`, `routers/auth.py`, `authService.js`, `AuthForm.jsx` |

The earlier build's `students`, `student_sessions`, `core/student_auth.py` and
`/auth/me` are absent and protected by `test_supervisor_owns_no_auth_module`,
`test_supervisor_declares_no_user_or_session_table`,
`test_outreach_ownership_keys_to_the_canonical_user_table` and
`test_supervisor_does_not_register_a_second_auth_surface`.

## 5. Migration Safety

`scripts/supervisor_verify_safety.py` — **67/67 PASS**. PROVEN.

Additive only (no `DROP`/`ALTER`/`DELETE`/`TRUNCATE`/`UPDATE`), no existing table
altered, no nullable→non-nullable change, FK parents verified per table,
one intentional unique constraint per table, `evidence_source_url` NOT NULL,
availability `source_url` + `verified_at` both NOT NULL, and indexes covering every
real lookup path. A `UNIQUE` constraint already indexes its columns on both engines,
so no redundant index is added over a unique column.

## 6. Faculty Discovery Architecture

Unchanged from the ported design, with one correction the pilot forced:

`same_institution()` replaces hostname equality as the **authority** test. PROVEN
that hostname equality was wrong: `admissions.msu.edu` and `msu.edu` are one
university, as are `adelaide.edu.au` and `staff.adelaide.edu.au`. Comparing
hostnames rejected the awarding institution's own pages — a false negative, not a
safety property. Exact-host matching is retained for crawl scoping; the looser
registrable-academic-domain comparison decides whether a page is evidence.

The registrable-domain function recognises only the academic suffixes the module
already trusts, longest-suffix-first. An unrecognised host returns itself, so
comparison falls back to exact-host equality rather than guessing.

## 7. JS-Rendered Source Handling

This is where the real work went, and it changed the design.

### What was established before adding anything

| Lower-cost path | Result | Tag |
|---|---|---|
| Declared sitemap (`Sitemap:` in robots.txt) | **Absent** on all 4 hosts probed: `adelaide.edu.au`, `www.eur.nl`, `admissions.msu.edu`, `msu.edu` | PROVEN |
| Embedded application state (`__NEXT_DATA__`, `__NUXT__`, `__INITIAL_STATE__`, `__APOLLO_STATE__`) | **Absent** on the Adelaide directory | PROVEN |
| JSON-LD structured data | Only `CollegeOrUniversity`. **No `Person`** | PROVEN |
| Server-rendered person links | **Zero** on every reachable page | PROVEN |
| The institution's own declared search endpoint | `adelaide.edu.au/search/` is itself a JS shell (0.038); its results come from an unpublished Funnelback backend | PROVEN |
| Chrome headless rendering of the directory | Renders 165 988 B (vs 131 532 served) but still yields **no person links** — the directory is an interactive search | PROVEN |

### Decision

**No browser dependency was added.** Two reasons, and the second is decisive.

First, Phase 5 forbids adding one merely because pages are dynamic, and the
cheaper paths were genuinely exhausted rather than assumed.

Second, and more importantly: rendering did not even solve the problem here. The
Adelaide directory renders into an interactive search whose results arrive from an
internal endpoint. Producing a professor would have required either interactive
session automation with cookies, or reverse-engineering an unpublished internal
search API by guessing parameters — which is precisely what the politeness and
robots rules exist to prevent. I did not do it, and I did not attempt to
authenticate anywhere.

**Browser tooling availability** (recorded because it bounds the option, not
because it was used): Chrome and Edge are installed locally and a Playwright
browser cache exists; no Python `playwright` or `selenium` is installed, and
master's `requirements.txt` declares neither.

### What shipped instead

A new coverage state, `SOURCE_REQUIRES_RENDERING`. This is the single most
consequential change from the real-world work. PROVEN as necessary.

The pilot established that every reachable page of a major university directory is
a JavaScript shell — text/markup ratios of **0.005 to 0.039**. Under the previous
design those scholarships would have been recorded as
`no_verified_supervisor_found`, which asserts that the university published no
faculty. That is not what was observed. A distinct, non-publicating state keeps
"we looked and it was empty" separable from "we looked and could not read it", and
`INCONCLUSIVE_COVERAGE_STATUSES` groups it with `source_blocked`, `search_pending`
and `needs_verification` rather than with the true negatives.

Detection is `page_is_javascript_shell(html, text)` — text to markup below 0.15.
Deliberately conservative: it reports a shell only when the document is
overwhelmingly script, and it does not fire when a search genuinely completes with
nobody listed. Both directions are tested.

**No rendering infrastructure is in this branch.** Whether to ship one is an open
decision, recorded in section 21.

## 8. Real Institution Pilot

Read-only, no persistence. `supervisor_pilot_readonly.py` imports the worker's
fetch and extraction functions and calls none of its persistence functions; the
only database access is a read-only SQLite open to choose a target.

| Target | Host | Seed result | Directory result |
|---|---|---|---|
| Erasmus University Rotterdam | `www.eur.nl` | 200, 167 953 B, **0.026** | 0 people-directory links |
| University of Adelaide | `adelaide.edu.au` | 200, 158 947 B, **0.039** | `adelaide.edu.au/people/` 200 with **0 candidates**; `staff.adelaide.edu.au` unreachable and correctly skipped as *"blocked, not an empty page"* |
| Michigan State University | `admissions.msu.edu` | 200, 730 696 B, **0.005** | people search resolves to `search.msu.edu/people/` — **authentication-gated** ("Sign In") |

Additional real observations, all PROVEN:

- `msu.edu/` serves a **212-byte** redirect stub with no content.
- Walking `admissions.msu.edu/academics` → department pages across the
  registrable domain: every page a JS shell (0.005–0.011), one people link each,
  and every one resolves to the login-gated search.
- Walking `adelaide.edu.au/schools/` and its partner pages: every page a JS shell,
  every one linking only to `/people/`.
- Erasmus' homepage is a JS shell at 0.026–0.027 with 0 people links.

## 9. Verified Professor Evidence

**BLOCKED.**

Zero professors were extracted from real institutional sources. The blocker is
specific and named: the pilot institutions serve JavaScript-rendered directories
whose content is produced by an unpublished internal search backend, one of which
is authentication-gated. Reaching a professor requires interactive session
automation or reverse-engineering that internal API. Neither was done.

Per Phase 17, this is not substituted with fixture success. **VALIDATED** is not
upgraded to **PROVEN** anywhere on the strength of tests alone.

The required fields — name, institution, department when published, authoritative
profile URL, email only when published, research areas only when supported,
availability only when supported — remain implemented and tested, but have not
been observed against a real person.

## 10. Negative/Blocked Semantics

Preserved, and now with one additional state. PROVEN by test.

| Condition | State |
|---|---|
| Unreachable / 403 / 404 / 429 / 5xx / timeout / DNS / SSL | `source_blocked` |
| Reachable but JavaScript-rendered | `source_requires_rendering` |
| Reachable, read successfully, nobody listed | `no_verified_supervisor_found` |
| Secondary-source evidence only | `needs_verification` |
| Never searched | `search_pending` |
| Not applicable by nature | `not_applicable` |

`"not accepting students"` still cannot match `"accepting students"` — refusal
phrases are tested first, and the test asserts both directions. VALIDATED.

## 11. Identity Deduplication

Deduplication remains on the unique authoritative profile URL, so the same person
found via a department page, a lab page and a profile page converges on one row.
The unique constraint is the mechanism, so it holds across runs. VALIDATED.

Merging is never attempted on surname, department or a shared research term — there
is no such code path. Surname and institution are **not** sufficient: they collide,
and a wrong merge would attach one person's availability to another. A merge would
require two distinct authoritative URLs pointing at one identity, and the safest
current behaviour is to keep both rows. VALIDATED.

## 12. Research Alignment

Unchanged and separate from Match 2.0. Match weights, the Match engine and the
Count Intelligence core are untouched. VALIDATED, and asserted by isolation tests
that compare Match output before and after supervisor data exists.

Generic one-word overlap cannot produce `MODERATE`; two significant words are
required. VALIDATED.

Label handling was tightened, because the pilot showed two failure modes:

| Input | Result | Tag |
|---|---|---|
| `"AI:"`, `"Research:"`, `"Interests:"`, `"Area:"` | `[]` — a bare label is never an area | VALIDATED |
| `"Research: AI"` | `["AI"]` — the value, never the label or `": AI"` | VALIDATED |
| `"Area: Computational Biology"` | `["Computational Biology"]` | VALIDATED |
| `"She works in the field of robotics."` | `[]` — prose cannot trigger a label | VALIDATED |
| `"Research interests: machine learning; formal verification"` | both areas | VALIDATED |

Generic labels (`area`, `interests`, `fields`, `topics`) require a colon; specific
ones (`research interests`, `specialisms`, `expertise`) do not. The minimum value
length is 2 characters so `AI` survives.

## 13. Email/Availability Trust

No email is ever constructed from a name. There is no code path of the form
`firstname.lastname@domain`, and none was added. PROVEN by inspection of the
extractor.

An email is published only when read from a page on the institution's own domain,
matching that domain, with obfuscated and placeholder addresses skipped rather than
repaired. The server gates on `official_email_verified`; the frontend gates
independently — a test proved the component would otherwise have rendered a stored
unverified address.

Availability uses the five explicit states, each requiring a source URL and a
verification date (both `NOT NULL`). Absences never decay into `stale`. VALIDATED.

## 14. Robots

The supervisor worker checks robots before every fetch, caches the decision for an
hour per origin, and **fails closed** — an unreadable robots.txt means the request
is refused. Disallowed paths are never requested, asserted by inspecting the
request log. Verified live on every pilot fetch. VALIDATED and PROVEN respectively
(live requests were made only after the gate returned true).

No infinite retry: one fetch per URL per page budget, `MAX_PAGES_PER_SCHOLARSHIP`
caps a scholarship, and records are rescheduled via `next_check_at` rather than
retried in a loop.

**Scope respected**: the pre-existing absence of robots handling in the image
pipeline is a live compliance gap in this repository, and it is **not** addressed
here. Out of scope, deliberately.

## 15. Public Visibility

Every public supervisor route derives eligibility from
`get_public_scholarship_or_404`, which applies the canonical
`public_visibility_conditions()` from `app/repositories/scholarships.py`. The
predicate is reused, never restated or copied. PROVEN.

Archived, quarantined and absent scholarships all return 404 with **byte-identical**
bodies. A professor public through one scholarship is not readable through a hidden
one that links them. Coverage rows may exist for hidden records without making them
readable — coverage is not a publication decision. VALIDATED.

Not weakened: `CATALOGUE_PREDICATE_SOURCE`, `verification_contract.py`, Match 2.0
weights and the Count Intelligence universe are untouched. The coverage report now
*reads* `CATALOGUE_PREDICATE_SOURCE` rather than duplicating the universe.

**The separate security issue is not duplicated.** The public scholarship-detail
route's bare `session.get` leak is untouched, because master does not contain the
fix and other actors are working on it. Supervisor does not depend on that route
for access control.

## 16. Frontend

Master's Vitest runner is used. **No test framework was added** — jsdom,
`@testing-library/react` and vitest are already declared; the only config change is
`test.environment = 'jsdom'`.

| Gate | Baseline | Feature |
|---|---|---|
| `npm test` | 163 passed, 9 files | **174 passed**, 10 files |
| `npm run lint` | 0 errors, 1 warning | **0 errors**, 1 warning (same pre-existing `HomePage.jsx`) |
| `npm run build` | success | **success** |

Covered: unverified stored email never rendered; sourced email shown only with the
flag; zero-professor state; blocked state; **render-required state**; secondary-only
state; verified-professor state; error; loading; signed-out visitor; and an
assertion that no probability, response rate or success rate appears anywhere in
rendered text.

Counter and card stay consistent: the card renders `Potential Supervisors · N` only
when a verified count exists, and never renders a zero as `0`.

**Browser E2E: not run.** No browser driver is available to this session. This is
recorded, not claimed. **BLOCKED.**

## 17. Test Safety

No test writes production data, calls a production API at import, or mutates the
process environment without restoring it. The visibility-gate fixtures in
`test_supervisor_discovery.py` save and restore their environment and clear the
cached settings object, because that cache is what decides a later module's
outcome. Every supervisor test builds its own in-memory SQLite via `StaticPool`; the
backfill script was exercised only against a **copy** of the local catalogue, and
never against `scholarzone.db` or Neon. VALIDATED.

## 18. Clean Baseline

Run on **untouched** current master, in a separate worktree, before any change.

| Suite | Baseline |
|---|---|
| Backend | **4966 passed, 9 failed, 11 skipped** |
| Frontend | 163 passed |
| Lint | 0 errors, 1 warning |
| Build | success |

The 9 backend failures are 1 × missing `yaml` dev dependency and 8 × missing
gitignored `migration_export.sql` — both environmental, both present on untouched
master. PROVEN.

## 19. Test Results

| Suite | Baseline | Feature | Delta |
|---|---|---|---|
| Backend full | 4966 passed / 9 failed / 11 skipped | **5117 passed / 9 failed / 11 skipped** | **+151 passed, 0 new failures** |
| Frontend | 163 passed | **174 passed** | +11 |
| Migration/worker safety | — | **67/67** | — |

The two failure sets were extracted and compared **line by line**: byte-identical,
9 for 9. **Zero new deterministic failures.** PROVEN.

Supervisor suites: **156 passed** across `test_supervisor_discovery.py` (42),
`test_supervisor_outreach.py` (34), `test_supervisor_worker.py` (43),
`test_supervisor_realworld.py` (37).

## 20. Exact Git Diff

Branch `feat/supervisor-discovery-current-master` from `573a983b`. 7 modified,
33 added. No scaffolding, no secrets, no data files, no unrelated work.

**Modified (7)**
```
backend/app/database.py                  guarded DDL both dialects + validator
backend/app/main.py                      three routers
backend/app/schemas.py                   supervisor/outreach models
backend/migrate_schema.py                REQUIRED_TABLES / REQUIRED_INDEXES
frontend/src/components/ScholarshipCard.jsx       CTA
frontend/src/pages/ScholarshipDetailsPage.jsx    panel
frontend/vite.config.js                  jsdom test environment
```

**Added (33)**
```
backend/app/models_supervisor.py            7 tables, FK to users.id
backend/app/supervisor_ddl.py               single DDL source of truth
backend/app/core/rate_limit.py              bounded in-process limiter
backend/app/routers/{supervisors,outreach,supervisor_email}.py
backend/app/services/supervisor_{status,alignment,freshness,public,coverage,discovery,email}.py
backend/scripts/supervisor_backfill.py          backfill / report / rollback
backend/scripts/supervisor_verify_safety.py     67 migration + worker checks
backend/scripts/supervisor_pilot_readonly.py    no-persist pilot
backend/scripts/supervisor_pilot_diagnose.py    JS-vs-extractor diagnosis
backend/scripts/supervisor_probe_structured.py  sitemap / declared-endpoint probe
backend/scripts/supervisor_probe_embedded.py    embedded-state + JSON-LD probe
backend/scripts/supervisor_probe_msu_departments.py  same-institution department walk
backend/tests/test_supervisor_{discovery,outreach,worker,realworld}.py
frontend/src/services/supervisorService.js
frontend/src/components/SupervisorPanel.{jsx,css,test.jsx}
frontend/src/components/SupervisorCta.{jsx,css}
```

**Deliberately untouched:** `app/models.py`, `app/dependencies.py`,
`app/services/auth.py`, `app/routers/auth.py`, `routers/applications.py`,
`routers/dashboard.py`, `routers/mentor.py`, `repositories/scholarships.py`,
`routers/scholarships.py`, Match 2.0, `services/counting`, image pipeline, admin
verification, CI workflows, `.env`, any database file.

## 21. Remaining Risks

1. **BLOCKED — no real professor proven.** The central milestone is not met. Every
   statement about extraction quality is therefore VALIDATED, not PROVEN.
2. **The pilot institutions may be unrepresentative.** They are admissions
   portals and the most JS-heavy parts of any university site. A different sample
   might be static. **UNKNOWN** either way — not measured.
3. **Recall will be poor until rendering exists.** Every reachable page sampled was
   a JS shell, so `source_requires_rendering` is likely to be the common outcome,
   not an edge case. This is honest, and it is also a poor user experience.
4. **Whether to ship rendering is an open decision.** Options: interactive browser
   automation (new dependency, container image, memory, WAF exposure),
   institution-permitted API access, or accepting the current honest state. This
   branch takes none of them.
5. **`same_institution` is a heuristic.** It treats `*.msu.edu` as one institution,
   which is right for a single-tenant academic domain and would be wrong for a
   multi-tenant one. Conservative by construction: unrecognised suffixes fall back
   to exact-host equality.
6. **The JS-shell threshold is a constant.** 0.15 text/markup. VALIDATED against
   six real pages spanning 0.005–0.039, but a single constant across very different
   CMSs will eventually misclassify.
7. **In-process rate limiting only.** One instance is bounded; a scaled deployment
   is not.
8. **Inherited, out of scope:** robots is respected nowhere else in this repository,
   including the image pipeline's dead `respect_robots_txt` flag; and the
   scholarship-detail route still leaks archived/quarantined records by id.
9. **Browser E2E never run.** No driver available.
10. **9 pre-existing suite failures** remain, unchanged by this work.
11. **Discovery has never been run at scale.** Bounded by design; unproven at 358.

## 22. Final Decision

# `NEEDS_HARDENING`

**Why not `READY_FOR_STAGING`** — the required milestone in Phase 17 was not met.
One real institutional faculty source yielding one real professor, with every
emitted field traced to its source, **BLOCKED**. Fixtures are not substituted for
it. Shipping in this state would mean presenting an unproven extractor as a working
one, which is the failure this whole feature exists to avoid.

**Why not `BLOCKED`** — nothing is architecturally unsound. Master is the only
base and is untouched in every file that matters. Identity is reused, with five
regression tests preventing a second system. Migration is additive, idempotent and
verified 67/67. The visibility contract is reused, not copied, and the separate
security fix is deliberately not duplicated. Zero new deterministic failures across
5117 backend and 174 frontend tests. Three real defects found by real-world probing
were fixed, and the probing also produced an honest new coverage state that prevents
the worker from asserting a negative it never established.

**To reach `READY_FOR_STAGING`**

1. Extract one real professor end to end, every field traceable, with a documented
   decision on rendering: ship bounded browser automation, obtain institutional API
   permission, or broaden the institution sample.
2. Measure the fraction of production records with a statically readable faculty
   page, so `source_requires_rendering` is known to be a minority case or accepted
   as the norm.
3. Run the browser E2E journey, or record formally that no driver is available.
4. Keep discovery opt-in and out of the maintenance worker regardless of the above.