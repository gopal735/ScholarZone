# Supervisor Discovery 1.0 — Data Quality Report

Every figure below was read from a database at a stated moment by
`backend/scripts/supervisor_backfill.py`. None is estimated, extrapolated or
carried over from another environment.

- **Environment**: local development, `backend/scholarzone.db` (SQLite)
- **Moment**: immediately after `python scripts/supervisor_backfill.py`
- **Production**: not measured. See section 3.

---

## 1. Coverage completeness

| Measure | Value | Expected |
|---|---|---|
| Total scholarship rows | 722 | — |
| Coverage rows | 722 | 722 |
| Scholarships missing coverage | 0 | 0 |
| **Coverage invariant holds** | **true** | true |
| Coverage rows whose count disagrees with their links | 0 | 0 |

`COUNT(scholarships) == COUNT(scholarship_supervisor_coverage)`, exactly.

Archived records are included. Coverage records what was searched, not what is
currently offered, so a row that vanished when a scholarship left the catalogue
would make this count ambiguous against the catalogue count. This is the
documented exception rule: **no exclusions apply.**

## 2. Coverage by status

| Status | Count | Meaning |
|---|---|---|
| `search_pending` | 722 | Not yet searched. Asserts nothing. |
| `verified_supervisors` | 0 | ≥1 verified relationship. |
| `no_verified_supervisor_found` | 0 | Completed read, nothing qualifying. |
| `source_blocked` | 0 | Official source refused or unreachable. |
| `needs_verification` | 0 | Secondary evidence only, withheld. |
| `not_applicable` | 0 | Cannot have supervisors by nature. |
| **Total** | **722** | |

- Scholarships with ≥1 verified supervisor: **0**
- Scholarships with 0 verified supervisors: **722**

**A count of zero is not a failure here.** It means discovery has not run against
these records. Presenting it as "no professors exist" would be a claim the system
has no evidence for, and the API and UI both refuse to make it.

## 3. Production

Live public catalogue, measured read-only during this work:

| Measure | Value |
|---|---|
| Public scholarships (`/api/scholarships/stats`) | **358** |
| Countries | 43 |
| Open / closing soon / upcoming | 264 / 42 / 47 |
| Verified and imaged | 358 |

The local database holds 722 rows against 358 public production records. The gap
is archived and gated records plus the two databases holding different content.

**The raw production row count is not available from this machine.** The Neon URL
is in no local environment file, and application startup deliberately does not
migrate or seed in production. Production figures must come from
`supervisor_backfill.py` run against the production database. They are left blank
here rather than guessed:

- Total production scholarships: _not measured_
- Production coverage rows after backfill: _not measured_
- Production status breakdown: _not measured_
- Production professors / links / verified emails: _not measured_

## 4. Provenance integrity

| Check | Value | Must be |
|---|---|---|
| Relationships with evidence | 0 | — |
| **Relationships without a source** | **0** | 0 |
| **Verified relationships on a non-authoritative source** | **0** | 0 |
| Source-evidence rows | 0 | — |

`evidence_source_url` and `evidence_source_type` are `NOT NULL` on
`scholarship_professor_links`. A relationship without provenance cannot be
represented, let alone published.

## 5. Professor identity

| Check | Value | Must be |
|---|---|---|
| Total unique professors | 0 | — |
| **Duplicate professor profiles** | **0** | 0 |
| Verified official emails | 0 | — |
| Unverified emails stored | 0 | 0 |
| Stale or never-verified professors | 0 | — |
| Professors with no relationship | 0 | — |

Deduplication key is `official_profile_url` (unique). Two runs that discover the
same person converge on one row rather than two near-duplicates.

## 6. Availability

| Check | Value | Must be |
|---|---|---|
| Availability claims total | 0 | — |
| **Claims without a source URL** | **0** | 0 |
| Claims without a verification date | 0 | 0 |

`source_url` and `verified_at` are `NOT NULL` on `professor_availability`. An
availability claim without a source and a date is not representable.

## 7. Schema

| Object | Count | Notes |
|---|---|---|
| New tables | 9 | All additive; `scholarships` untouched. |
| Declared indexes on new tables | 25 | Verified: every DDL index name exists in the models, and no model index is missing from the DDL. |
| Unnamed unique constraints | 0 | All named `uq_*`. |

Verified on SQLite: `init_database()` twice creates all 9 tables and every
declared index, and the second run is a no-op. Production reaches these tables
through `backend/migrate_schema.py`, because app startup does not migrate in
production.

## 8. Cross-feature isolation

| Check | Result |
|---|---|
| Catalogue totals before vs after supervisor data | unchanged (asserted) |
| Match summary before vs after supervisor data | unchanged (asserted) |
| Count Intelligence universe | untouched — no code path added |
| Match 2.0 weights | untouched |
| Application Workspace | does not exist; no lifecycle created |
| Image pipeline | untouched |
| Admin Verification | untouched |
| Scholarship verification semantics | untouched |

## 9. Fabricated-data audit

The central question. Everything below was checked structurally, not sampled.

| Forbidden claim | Enforcement | Present? |
|---|---|---|
| Invented professor | A row requires an official profile URL read from the institution's domain. No code path writes a professor from a name alone. | **0** |
| Invented email | Published only when read from the institution's own page with a matching domain. | **0** |
| `accepting_students` defaulting true | Five explicit states; default `unknown`. | **0** |
| Inferred funding | `not_published` when the page is silent. | **0** |
| Response rate / success rate | No such field, endpoint or computation exists. | **0** |
| Admission or acceptance probability | No numeric output in any alignment or availability path. | **0** |
| Citation count, h-index, i10-index | Not modelled at all. | **0** |
| Invented paper title in a draft | No publication store exists; the draft path cannot reference one. | **0** |
| Invented personal connection in a template | Templates state only what the student knows. | **0** |
| Student testimonials | Not modelled. | **0** |
| "No professors exist" | No code path can produce it. Coverage states are enumerated and none means that. | **0** |

**Total professors in the database: 0. Total claims made: 0.**

## 10. Failure-state correctness

Verified by test rather than by inspection, because these are the paths that turn
a gap into a false statement:

| Condition | Recorded as | Must never be |
|---|---|---|
| Official source unreachable | `source_blocked` | a negative result |
| HTTP 403 / 412 | `source_blocked` | a negative result |
| HTTP 404 on a faculty page | `source_blocked` | "no supervisors exist" |
| HTTP 429 / 5xx | `source_blocked` | a negative result |
| Timeout / DNS / SSL | `source_blocked` | a negative result |
| Page read, nobody relevant | `no_verified_supervisor_found` | "no professors exist" |
| robots.txt disallows | no request made | any fetch |
| robots.txt unreadable | request refused | any fetch |
| Non-institutional source host | `source_blocked`, no professor | any professor |
| Malformed HTML | run completes, no professor | a crash |
| Re-run of the same discovery | identical row and count counts | duplicated rows |

## 11. Test results

| Suite | Result |
|---|---|
| `tests/test_supervisor_discovery.py` | 38 passed |
| `tests/test_supervisor_outreach.py` | 43 passed |
| `tests/test_supervisor_worker.py` | 42 passed |
| **Feature total** | **123 passed, 0 failed** |
| Full backend suite | 4827 passed, 2 failed, 2 skipped |

The 2 failures are pre-existing and unrelated:

1. `test_efficiency_safety.py::TestRetryPolicy::test_the_retry_shares_the_concurrency_group`
   — `ModuleNotFoundError: No module named 'yaml'`, a missing dev dependency in
   the virtualenv.
2. `test_image_discovery.py::TestHumanReviewRouting::test_non_content_image_with_license_still_rejected`
   — an image-pipeline assertion in `image_validator.py`, a file carrying 193
   lines of uncommitted work by another actor that predates this feature.

Neither file is touched by this work.

Frontend: `npm run lint` → 0 errors (1 pre-existing warning in `HomePage.jsx`);
`npm run build` → success.

## 12. Outstanding data-quality work

Ordered by how much they affect trust in published results.

1. **Run discovery against real institutional pages and review the statuses
   before widening.** Everything so far is verified against fixtures. Real faculty
   directories are structurally diverse, and the extraction heuristics are
   unproven outside fixtures. Publishing professors from an untuned extractor is
   exactly the failure this feature is meant to avoid, so the first real run
   should be small and hand-checked.
2. **Expect a high `source_blocked` rate.** WAFs, bot protection and non-HTML
   directories are common. A high blocked rate is a correct result, not a bug —
   but it should be reported as such and not quietly converted to "none found".
3. **Measure how many scholarships have no derivable institution signal.**
   `scholarships` has no institution column, so `not_applicable` classification
   depends on parsing `official_source` and hostnames. This has not been measured
   and should be before the backfill is trusted to classify anything beyond
   `search_pending`.
4. **Fix robots.txt in the image pipeline.** It is respected in the supervisor
   worker and nowhere else. Pre-existing, out of scope here, and a genuine
   compliance gap.
5. **Reconcile the card's summary count with the link table.** The public list
   self-heals a drifted counter; the card does not. A nightly reconciliation job
   would close it.
6. **No E2E run.** The real browser journey is unexecuted, and the local database
   has no verified professors to exercise it against.
7. **No frontend test runner.** Vitest is not installed and no dependency was
   added to introduce it.
8. **Password hashing cost.** `scrypt` N=2^14 is a reasonable interactive
   parameter today. The digest is self-describing, so raising it later
   re-verifies old hashes rather than invalidating them.