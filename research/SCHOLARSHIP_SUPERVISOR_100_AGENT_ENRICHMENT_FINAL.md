# ScholarZone Supervisor Enrichment — 100-Agent Live Research Run (FINAL)

Run date: 2026-10-14. Corpus: all 643 non-archived scholarships in `backend/scholarzone.db`
(695 total; 52 archived left untouched as `search_pending`).

## Method

100 live research agents (`general` subagents, each doing live websearch/webfetch against
official institutional pages) each received one batch of 6–7 scholarships. The corpus was
split into exactly 100 batch files (`research/supervisor_agent_batches/input/`), of which
batches 001–092 carried content (643 scholarships) and 093–100 were empty padding batches.
Several agents were killed mid-run by provider TPM/concurrency limits and were relaunched
until every batch produced output; batch 093–100 agents correctly wrote empty arrays.

Each agent returned, per scholarship, either a set of professor records or an outcome, with
strict provenance rules: official institutional domains only for profile URLs, emails only
when published on an institutional page (never constructed), and an evidence URL + quote
for every professor.

## Data quality gates applied before writing

- `validate_outputs.py`: 643/643 result objects, 0 schema problems, 0 duplicate
  scholarship entries.
- Profile-URL collisions (one shared faculty page used for several people) were resolved by
  fetching the official pages directly: DGIST professors were re-pointed at their per-person
  on-page anchors (`#info01`, `#info02`, `#info25`), KINGS professors at their official
  person pages (`/professor/index.do?pId=jiyoon`, `pId=wooyong`). For InLife and FNU no
  person-specific page exists, so only the first professor per shared page was kept
  (3 duplicate entries dropped rather than misattributed).
- All 152 professor emails were re-checked against the profile host: 19 differ only by
  legitimate institutional variants (CAS institute mail domains `igsnrr/rcees/iggcas/gucas`
  vs UCAS people pages, `ntnu.edu` vs `ntnu.no`, `ista.ac.at` vs `ist.ac.at`,
  `impmc.sorbonne-universite.fr` vs `upmc.fr`, `janelia.org` vs `janelia.hhmi.org`,
  `bse.eu` vs `upf.edu`). Zero fabricated addresses.
- Export encoding verified by HEX: names stored as UTF-8 (e.g. `C3BC` = ü in "Günther").

## What was written to the database

| table | rows |
|---|---|
| `professor_profiles` | 197 |
| `scholarship_professor_links` | 199 (all `verified` against official sources) |
| `supervisor_source_evidence` | 322 |
| `scholarship_supervisor_coverage` (active scholarships) | 643 |

Coverage breakdown for active scholarships: 78 `verified_supervisors`, 183
`no_verified_supervisor_found`, 376 `not_applicable` (national/government schemes with no
attached institution), 5 `source_blocked`, 1 `source_requires_rendering`. 152 professors
carry a published institutional email; 45 have none (none published — left null).

Freshness: `last_verified_at` = run date, `next_verification_at` = +180 days on profiles
and coverage.

## Reproduce / audit

- Inputs: `research/supervisor_agent_batches/input/batch_001..100.json`
- Agent outputs: `research/supervisor_agent_batches/output/batch_001..100.json`
- `validate_outputs.py` — schema gate over the raw outputs
- `find_collisions.py` — profile-URL collision report
- `patch_collisions.py` — applies the verified person-specific URL patches
- `merge_to_db.py [--dry-run]` — idempotent, vocabulary-checked writer
- `verify_db.py`, `review_emails.py`, `check_dupes.py` — post-merge checks
- Pre-enrichment DB snapshot: `backups/scholarzone.pre_supervisor_enrichment_20261014_154140.db`
  (git-ignored via the existing `*.db` rule)

The merge is idempotent (upserts keyed on `official_profile_url` and the
`scholarship_id`/`relationship_type` unique constraint); re-running it changes nothing.

## Post-review hardening (local review of the uncommitted change)

- `merge_to_db.py` now filters at professor granularity (`sanitize_items`): a malformed
  professor is logged and dropped, never silently discarding its whole scholarship, and a
  malformed email is nulled with a log rather than stored.
- `evidence_state` is no longer a tautology: `partial` is written for `source_blocked` /
  `source_requires_rendering` outcomes where provenance could not be built.
- The production DB connection uses a 30s busy timeout.
- Dead `emails_found` accumulator and unused `sys` import removed.
- The pre-enrichment backup was moved out of `backend/` to `backups/` (git-ignored).

Verification after hardening: ORM reads of all three supervisor tables succeed, and
`build_supervisor_list()` returns professors, emails and evidence for scholarship 14, 62
and 70. Row counts are unchanged (197 / 199 / 322) and a re-merge is a no-op.
Pre-existing, unrelated tree state: `backend/tests/test_supervisor_personhood_gate.py`
fails with `NameError: _looks_like_a_person_name` because the app exposes
`looks_like_a_person_name` while that test still calls the old private name — a drift from
the in-flight merge that predates this enrichment and touches no database code.
