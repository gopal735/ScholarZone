# ScholarZone Supervisor Discovery — Final Report

Scope: Supervisor Discovery 1.0 reconstructed on current master, with real-world
discovery hardened and honestly reported.

Evidence labels used throughout:

- **PROVEN** — demonstrated against current master or real institutional pages
- **VALIDATED** — verified by deterministic test, not yet observed on real content
- **UNKNOWN** — not established, deliberately not filled in
- **BLOCKED** — could not be established; the blocker is named

No production write of any kind occurred. No production deployment. No fabricated
supervisor, evidence, verification note, production count or test record.

---

## 1. Current master SHA

| Fact | Value | Label |
|---|---|---|
| Current `origin/master` | `ddcd9c3662f4d3257d4f92e335fa7422e99ebdeb` | PROVEN |
| Previous candidate `1be99d4` | `1be99d4cb5ea9408f0455217adb22e1bde6cc81a` | PROVEN |
| `1be99d4` parent | `573a983b004ab08578497272659123323ab489b7` | PROVEN |
| Merge-base(master, `1be99d4`) | `573a983b…` | PROVEN |
| Local `HEAD` (shared worktree) | `8ac1c9a40063221904c8994693ffa18746d5fa9d`, 79 behind, never rebased | PROVEN |
| **Final candidate** | `4e2d0c1` (see §20) | PROVEN |
| Candidate base | `ddcd9c3`, direct parent — **no stale ancestry** | PROVEN |

**Master advanced during the previous task.** `1be99d4` was built on `573a983`;
master is now `ddcd9c3`, a merge of the public-visibility security release. So
`1be99d4`'s ancestry genuinely was stale, and the candidate was rebuilt from the
new master rather than rebased or re-labelled. `1be99d4` was not merged and not
pushed.

---

## 2. Merge-base and ancestry integrity

`git merge-base origin/master 1be99d4` = `573a983`, which is `1be99d4`'s parent. The
old candidate was therefore a clean single commit on the then-current master, and
the only thing wrong with it was that master moved.

The final candidate is a single commit whose parent is `ddcd9c3`. Verified, not
assumed: `git rev-parse HEAD^` equals `git rev-parse origin/master`. PROVEN.

---

## 3. Changed-file manifest

35 files. Every file carries a recorded reason; the audit script **fails** if any
file lacks one, so an unexplained file cannot enter the candidate.

### New — supervisor product (10)

| File | +/− | Reason |
|---|---|---|
| `backend/app/models_supervisor.py` | +360 | 7 tables; `user_id` → `users.id` |
| `backend/app/supervisor_ddl.py` | +342 | one DDL source for both migration paths |
| `backend/app/core/rate_limit.py` | +91 | bounded limiter for supervisor routes |
| `backend/app/routers/supervisors.py` | +126 | public supervisor read |
| `backend/app/routers/outreach.py` | +382 | private outreach via `require_user` |
| `backend/app/routers/supervisor_email.py` | +123 | draft + templates via `require_user` |
| `backend/app/services/supervisor_status.py` | +328 | state vocabulary incl. `source_requires_rendering` |
| `backend/app/services/supervisor_person.py` | +327 | personhood by positive evidence |
| `backend/app/services/supervisor_public.py` | +336 | public read model, reuses the canonical predicate |
| `backend/app/services/supervisor_coverage.py` | +361 | coverage invariant + universe report |
| `backend/app/services/supervisor_discovery.py` | +1276 | the worker |
| `backend/app/services/supervisor_alignment.py` | +231 | deterministic alignment, separate from Match |
| `backend/app/services/supervisor_freshness.py` | +119 | staleness policy |
| `backend/app/services/supervisor_email.py` | +356 | deterministic drafting |

### New — deterministic tests and tooling (7)

| File | + | Reason |
|---|---|---|
| `backend/tests/test_supervisor_discovery.py` | 809 | coverage, visibility, universe |
| `backend/tests/test_supervisor_discovery_states.py` | 422 | the state matrix on fixtures |
| `backend/tests/test_supervisor_person_policy.py` | 221 | name and domain matrices |
| `backend/tests/test_supervisor_outreach.py` | 628 | ownership, concurrency, auth reuse |
| `backend/tests/test_supervisor_worker.py` | 643 | extraction, politeness, negatives |
| `backend/scripts/supervisor_backfill.py` | 327 | idempotent backfill / report / rollback |
| `backend/scripts/supervisor_verify_safety.py` | 177 | 67 static migration and worker checks |

### New — frontend (8)

`supervisorService.js`, `SupervisorPanel.{jsx,css,test.jsx}`,
`SupervisorCta.{jsx,css}`

### Modified (7) — smallest possible integration

| File | Δ | Reason |
|---|---|---|
| `backend/app/main.py` | +14 | register three routers |
| `backend/app/schemas.py` | +177 | supervisor/outreach response models |
| `backend/app/database.py` | +41/−1 | guarded DDL, both dialects, + validator |
| `backend/migrate_schema.py` | +12 | production migration registration |
| `frontend/src/components/ScholarshipCard.jsx` | +2 | mount the CTA |
| `frontend/src/pages/ScholarshipDetailsPage.jsx` | +9 | mount the panel |
| `frontend/vite.config.js` | +8 | jsdom for component tests |

Each of these 7 was verified **byte-identical between `573a983` and `ddcd9c3`
before the port**, so the candidate's version of each is precisely "current master
plus supervisor edits", with no master change to re-apply and none reversed.

---

## 4. Intended vs omitted classification

Classification of all 38 files in `1be99d4`, enforced by a script that exits
non-zero unless the sets match exactly. Result: **31 retained, 7 omitted, 0
unexplained.** PROVEN.

| Omitted file | Reason |
|---|---|
| `SUPERVISOR_CURRENT_MASTER_REAL_WORLD_FINAL.md` | superseded; this specification renames the report |
| `backend/scripts/supervisor_pilot_readonly.py` | live-network harness, not product |
| `backend/scripts/supervisor_pilot_diagnose.py` | live-network diagnosis, not product |
| `backend/scripts/supervisor_probe_structured.py` | live-network probe, not product |
| `backend/scripts/supervisor_probe_embedded.py` | live-network probe, not product |
| `backend/scripts/supervisor_probe_msu_departments.py` | live-network probe, not product |
| `backend/tests/test_supervisor_realworld.py` | its name assertions encoded the blacklist design this candidate replaces; rewritten instead |

Omitting the five probe scripts removes **every live-network code path from the
candidate**. That is what makes Part 15 true by construction: nothing in the
release gate can be perturbed by the internet.

---

## 5. Current-master production fixes preserved

| Commit | Behaviour | In current master? | Direct regression |
|---|---|---|---|
| `3bf92b6` | ingestion must not delete a stored image on a null refresh | **yes** (ancestor) | `test_ingestion_image_preservation.py` **passes** |
| `87ad84c` | purge must not clear an image the pipeline accepted | **yes** (ancestor) | `test_purge_image_safety.py` **passes** |

Both verified with `git merge-base --is-ancestor`, then executed:
**37 passed**. No repository-integrity issue. Nothing was silently reverted. PROVEN.

---

## 6. Auth reuse proof

| Check | Result | Label |
|---|---|---|
| Supervisor routers import `from ..dependencies import require_user` | yes, same as applications/dashboard/mentor | PROVEN |
| Any local auth module | none | PROVEN |
| `students` table created | **no** | PROVEN |
| `student_sessions` table created | **no** | PROVEN |
| Duplicate `/auth` router | none — exactly `login`, `logout`, `register`, `session` | PROVEN |
| Ownership source | `users.id` via `require_user` | PROVEN |
| Session mechanism | master's `UserSession`, untouched | PROVEN |

Five regression tests enforce this, so a second identity system cannot return
without failing the build.

---

## 7. Discovery-state model

Seven explicit, serialisable states. **The central invariant: inability to
observe ≠ evidence of absence.**

| State | Meaning | Public? |
|---|---|---|
| `verified_supervisors` | ≥1 verified relationship | yes |
| `no_verified_supervisor_found` | read an authoritative directory, no qualifying person | yes |
| `source_requires_rendering` | reached and read, content assembled by JavaScript | no |
| `source_blocked` | unreachable, 403/429/5xx/timeout, **or login-gated** | no |
| `needs_verification` | evidence exists but is not authoritative | no |
| `search_pending` | never searched | no |
| `not_applicable` | cannot apply by nature | no |

`source_requires_rendering` and `source_blocked` are grouped in
`INCONCLUSIVE_COVERAGE_STATUSES`; `no_verified_supervisor_found` is deliberately
**not** in that set. VALIDATED.

### Negative-claim safety contract (Part 11)

`no_verified_supervisor_found` requires an authoritative, server-rendered faculty
directory that was actually fetched and read, containing no person qualifying
under the documented semantics. Each of the following is tested **not** to produce
it: empty HTML shell, JavaScript-only search, HTTP 200 with an empty shell,
missing sitemap, missing JSON-LD `Person`, zero server-rendered person links,
login-gated directory, inaccessible unpublished endpoint, client-side-only search
UI, HTTP 403, 404, 429, 500, 503. VALIDATED.

### Consumer audit (Parts 10, 22)

Every consumer of the state strings was enumerated. They are:

- the supervisor modules themselves (`supervisor_status`, `supervisor_coverage`,
  `supervisor_public`, `supervisor_discovery`)
- `models_supervisor` (column default) and `supervisor_ddl` (comments)
- `scripts/supervisor_backfill.py` (report)
- `frontend SupervisorPanel.jsx` — explicit per-state branches, including
  `source_requires_rendering` and `needs_verification`
- `frontend SupervisorCta.jsx` — reads the count only

A grep for non-supervisor modules importing the supervisor state or tables returned
**two files, both supervisor routers**. No consumer outside the feature reads a
supervisor state. Nothing performs `inconclusive → negative`. PROVEN.

---

## 8. Faculty discovery architecture

Personhood is decided by **positive evidence**, in
`app/services/supervisor_person.py`:

1. an **academic role** stated in the label — honorific (`Dr`, `Prof`) or inline
   (`Jane Smith — Professor of Computer Science`); or
2. **source context** — a personal-profile path, directly under a people/profile
   root, on a page already established as a directory.

Neither the words nor the host alone are sufficient. This replaced a
geographic/institutional blacklist, because a blacklist only contains the cases
somebody already thought of and reads as though it were the safety mechanism. The
remaining lexical sets are small and justified: academic role phrases, honorifics,
name particles, and a *navigational* slug set (`faculty`, `directory`, `search`, …)
that describes page sections rather than people. **VALIDATED** across 36 policy
tests.

### Source-context requirement (Part 7)

Storage requires an academic role stated by the institution, on the listing **or**
on the profile. Directory structure identifies a *candidate to check*; it does not
identify a professor, and it cannot distinguish a person from a call to action —
`/people/apply-now` and `/people/ada-lovelace` are the same shape. So the pipeline
asks for the role rather than trying to recognise a name from its URL. A candidate
without role evidence is **dropped before any row is written**, not written and
then hidden. VALIDATED.

### Confidence / evidence separation (Part 23)

Three things are kept distinct and explicitly separated:

- **source provenance** — which institution owns the page
- **person identity** — `classify_person_candidate`, which never inspects the host
- **academic role** — `FacultyCandidate.role`, required for storage
- **final verification state** — `_verification_status_for`, the single place
  evidence strength becomes a verdict

A test asserts the boundary directly: the same text yields the same person-decision
regardless of the host being first-party, and first-party ownership alone yields
`academic_role_stated = False`. VALIDATED.

---

## 9. JS-rendered source handling

Phase 5 requires exhausting cheaper paths before considering a renderer. Against
real institutional sources, all were exhausted:

| Path | Result | Label |
|---|---|---|
| Declared sitemap | absent on all 4 hosts probed | PROVEN |
| Embedded state (`__NEXT_DATA__`, `__NUXT__`, `__INITIAL_STATE__`, `__APOLLO_STATE__`) | absent | PROVEN |
| JSON-LD | only `CollegeOrUniversity`; no `Person` | PROVEN |
| Server-rendered person links | zero, on every reachable page | PROVEN |
| Institution's own declared search endpoint | itself a JS shell; results from an unpublished backend | PROVEN |
| Headless rendering | rendered 165 988 B (from 131 532 served), still zero person links | PROVEN |

Measured text/markup ratios: **Erasmus 0.026, Adelaide 0.039, MSU 0.005–0.011**.
Every reachable page of all three is a JavaScript shell.

### Rendering policy decision

**No browser dependency was added.** Two reasons. First, Phase 5 forbids adding one
merely because pages are dynamic, and the cheaper paths were genuinely exhausted
rather than assumed. Second, rendering did not solve the problem: the Adelaide
directory renders into an interactive search whose results arrive from an
unpublished internal endpoint, and MSU's official people search is
**authentication-gated** (`search.msu.edu/people/` → "Sign In"). Reaching a
professor would have required interactive session automation, or reverse-engineering
an internal API by guessing parameters, or authenticating — none of which a public
crawler should do, and none of which was done.

A failed extraction is therefore never translated into "no professor". VALIDATED
by test; PROVEN by observation.

---

## 10. Institutions and sources tested

Real institutions inspected read-only in the previous phase; all findings recorded
here, none re-fetched in this task:

| Institution | Host | Result |
|---|---|---|
| Erasmus University Rotterdam | `www.eur.nl` | JS shell 0.026; no people links; one scholarship URL unreachable |
| University of Adelaide | `adelaide.edu.au` | JS shell 0.039; interactive search; every reachable page a shell |
| Michigan State University | `admissions.msu.edu`, `msu.edu` | JS shell 0.005–0.011; people search **login-gated** |

Production sources were **not** contacted in this task. Production supervisor state
remains **UNKNOWN**. PROVEN (no write occurred).

---

## 11. Phase 6 status

**INCONCLUSIVE / BLOCKED.** No professor has been extracted from a real
institutional source. No fabricated positive and no fabricated negative.

The milestone required for `READY_FOR_OWNER_MERGE` is: one real faculty source →
one real professor → every emitted field traced to its source. **Not met.**

Why each earlier path is inconclusive:

- **JS shell** — the institution may well publish its staff; we were served a shell
  and never saw them. Absence of evidence.
- **Login-gated** — the directory exists and is authoritative; we are not authorised
  to read it. Inaccessibility, not emptiness.
- **Missing sitemap / JSON-LD** — a property of what a site publishes, not a fact
  about whether it employs anyone.

All three are recorded as `SOURCE_REQUIRES_RENDERING` or `SOURCE_BLOCKED`, never
as a negative. Fixtures are not substituted for the milestone. BLOCKED.

---

## 12. False-name examples

Rejected because **none states an academic role**, not because of a word list:

`South Australia`, `Adelaide City`, `Adelaide City Campus`, `Magill Campus`,
`English Language Centre`, `University Senior College`, `School of Computing`,
`Faculty of Engineering`, `Admissions Office`, `Library Services`,
`Research Institutes`, `Student Housing`, `Apply Now`, `Archive 2019`

Accepted, with the evidence named:

| Label | Evidence |
|---|---|
| `Dr Ada Lovelace` | `honorific` |
| `Professor Alan Turing` | `honorific` |
| `Jane Smith — Professor of Computer Science` | `inline_role`, name `Jane Smith` |
| `Grace Hopper` at `/people/grace-hopper` in a directory | `source_context` (weaker) |

`Faculty of Engineering` is rejected because the role vocabulary contains
individual academic ranks and deliberately **not** the collective "faculty".
VALIDATED.

---

## 13. `same_institution` logic

`admissions.msu.edu` and `msu.edu` → **same**. `www.msu.edu` → same.
`staff.adelaide.edu.au` and `adelaide.edu.au` → same. Longest-suffix-first
registrable-domain computation, keeping the suffix plus the final label before it.

| Case | Result |
|---|---|
| `msu.edu` + `evil-msu.example` | different |
| `example.edu` + `example.com` | different |
| `notmsu.edu` + `msu.edu` | different |
| `msu.edu.evil.example` + `msu.edu` | different |
| `a.b.c.msu.edu` + `msu.edu` | same |
| `a.ac.uk` + `b.ac.uk` | different |
| `ox.ac.uk` + `chem.ox.ac.uk` | same |
| unknown host | falls back to exact-host equality |

An unrecognised suffix returns the host unchanged, so an ambiguous host degrades
to exact matching rather than being guessed into an institution.

**Domain matching is not a trust verdict.** A first-party domain is evidence of
source ownership and nothing else; identity and role are judged separately, and a
test asserts that boundary explicitly. VALIDATED.

---

## 14. Deterministic fixture model

`test_supervisor_discovery_states.py` runs the real extractor, real classifier and
real state machine against fixed strings. The **network boundary only** is mocked;
no policy or decision function is mocked. No test touches the internet — the five
live-network scripts were omitted from the candidate precisely so this is structural
rather than a convention.

Fixtures: genuine faculty page, JS shell, empty shell, place-name directory,
login-gated directory, roleless directory, server-rendered-but-empty directory,
plus malformed and digit-bearing labels.

Live institutional sources are recorded in §10 as evidence. They are **not** part
of the release gate, so intermittent internet behaviour cannot affect the
deterministic verdict. VALIDATED.

---

## 15. Repeated-test results

| Requirement | Result |
|---|---|
| 20 in-process executions, identical | **20/20 identical** |
| 5 isolated-process executions, identical | **5/5 identical** |
| Outcome across all 25 | `171 passed`, 0 failed |

Timing varied between runs; outcomes did not. Compared on outcome with duration
stripped. No test is skipped, xfailed or retried to obtain the result. VALIDATED.

---

## 16. Backend regression results

Clean baseline run first, on untouched current master in a separate worktree.

| Suite | Baseline (`ddcd9c3`, untouched) | Candidate | Delta |
|---|---|---|---|
| Supervisor suites | — | **171 passed** | +171 |
| Full backend | 4 875 passed / 9 failed / 11 skipped | **5 046 passed / 9 failed / 11 skipped** | **+171, 0 new failures** |
| Migration + worker safety | — | **67/67** | — |

The two failure sets were extracted and compared name by name: **byte-identical,
9 for 9** — one missing `yaml` dev dependency, eight missing gitignored
`migration_export.sql`. Both are present on untouched master. PROVEN.

Named subsystems, executed directly (Part 17):

| Subsystem | Result |
|---|---|
| Public scholarship endpoints (`test_public_detail_visibility.py`, master's new security suite) | **21 passed** |
| Ingestion / purge image safety (the two production fixes) | **37 passed** |
| Student Dashboard | **57 passed** |
| Match 2.0 (`test_matching_v2.py`) | **371 passed** |
| Count Intelligence (`test_counting_api.py`) | **34 passed** |
| Schema migration | **22 passed** |
| API routing | full suite green |

Unchanged files were still verified to have not regressed through imports or shared
utilities: the full suite exercises them.

---

## 17. Frontend results

Master's Vitest runner used. **No framework added** — jsdom,
`@testing-library/react` and vitest are already declared; the only config change is
`test.environment = 'jsdom'`.

| Gate | Baseline | Candidate |
|---|---|---|
| `npm test` | 163 passed / 9 files | **174 passed / 10 files** |
| `npm run lint` | 0 errors, 1 warning | **0 errors, 1 warning** (same pre-existing `HomePage.jsx`) |
| `npm run build` | success | **success** |

Rendered states asserted: render-required, blocked, needs-verification, not-searched,
none-verified, verified-with-evidence, error, loading, signed-out. Plus: unverified
stored email never rendered, and no probability, response rate or success rate
anywhere in rendered text.

---

## 18. Secrets and production state

**Secret scan: 0 credential-shaped findings.** Pattern names only were inspected;
no value was printed. One placeholder-shaped hit was reported rather than
filtered — `PASSWORD = "<value>"` in a test module, a dummy constant. No `.env`,
`.db`, `.pem`, `.key` or production dump is in the candidate. PROVEN.

**Production writes: NONE.**
**Production supervisor state: UNKNOWN** — not read, not inferred, not estimated.
No production figure in this report is derived from local fixtures.

---

## 19. Remaining limitations

1. **Phase 6 BLOCKED** — no real professor extracted. The milestone is not met and
   fixtures were not substituted for it.
2. **Recall will be low until rendering exists.** Every sampled page was a JS shell,
   so `source_requires_rendering` is likely the common outcome. That is honest, and
   it is also a poor user experience.
3. **Whether to ship rendering is an open owner decision**: interactive browser
   automation (new dependency, container image, memory, WAF exposure),
   institution-permitted API access, or accepting the honest inconclusive state.
   This candidate takes none of them.
4. **Whether the pilot sample is representative is UNKNOWN.** They were admissions
   portals, the most JS-heavy part of any university site. Not measured either way.
5. **The JS-shell threshold (0.15 text/markup) is a single constant**, validated
   against real pages spanning 0.005–0.039. A single constant across very different
   CMSs will eventually misclassify.
6. **`same_institution` is a heuristic.** Correct for single-tenant academic domains,
   wrong for multi-tenant ones; unrecognised suffixes fall back to exact-host
   equality.
7. **In-process rate limiting only** — one instance is bounded, a scaled deployment
   is not.
8. **No browser E2E.** No driver available; not claimed.
9. **9 pre-existing suite failures** remain, unchanged by this work.
10. **Inherited, out of scope:** robots is respected nowhere else in this repository,
    including the image pipeline's dead `respect_robots_txt` flag.

---

## 20. Owner action

1. Decide the rendering question in limitation 3. Until then, discovery stays
   opt-in and out of the maintenance worker.
2. Run the browser E2E journey, or record formally that no driver is available.
3. Review and merge this branch. It is scope-clean, current-master-based and
   deterministic.

---

## 21. Final classification

The gate for `READY_FOR_OWNER_MERGE` requires that no known correctness blocker
remains. One does: **Phase 6 is BLOCKED** — the feature has never extracted a
verified professor from a live institutional source, so extraction quality is
`VALIDATED` against fixtures and `UNKNOWN` against reality. Shipping it as a
working discovery capability would present an unproven extractor as a proven one,
which is the exact failure this feature exists to prevent.

Everything else in the gate is met: current master is the base with no stale
ancestry, only intended supervisor changes are present, both production fixes are
preserved and regression-tested, no JS shell or login-gated source can become a
false negative, place and institution names are rejected by mechanism rather than
list, real person detection is preserved, `same_institution` is safe and is not a
trust verdict, auth is reused and cannot be duplicated, the discovery state is
explicit and non-collapsing in every consumer, fixtures are deterministic, no live
network is required for the gate, 25/25 executions are identical, there are no new
regressions, no secrets, no production writes, and no fabricated supervisor or
negative claim.

```
FINAL CLASSIFICATION:
CANDIDATE_READY_FOR_REVIEW

EXACT OWNER ACTION:
Review and merge branch feat/supervisor-discovery-final (single commit on ddcd9c3).
Decide the rendering question for JS-rendered directories: ship bounded browser
automation, obtain institutional API permission, or accept the honest inconclusive
state. Run the browser E2E or record that no driver is available. Until the
rendering decision is made, keep discovery opt-in and out of the maintenance worker.

PRODUCTION WRITES:
NONE
```