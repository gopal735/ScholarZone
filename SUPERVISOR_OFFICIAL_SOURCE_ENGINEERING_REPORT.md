# Supervisor official-source coverage - engineering report

Supersedes earlier supervisor reports where they disagree with current code. Every
number here comes from a run against a copied local catalogue; the batch is
resumable from the recorded audit trail, and the report at
`SUPERVISOR_OFFICIAL_SOURCE_COVERAGE_REPORT.md` is the generated snapshot.

## Repository state

| Item | Value |
| --- | --- |
| Initial SHA (shared checkout HEAD) | `9a6805cf57438cba9baa05f0d8a2a89d59f1260c` |
| Branch at start | `fix/public-catalogue-non-closed-visibility` |
| Upstream | `git@github.com:gopal735/ScholarZone.git` (org `gopal735`) |
| Worktree | `C:\Users\GopaL\AppData\Local\Temp\kilo\sz-supervisor-coverage` (new, isolated) |
| Feature branch | `feat/supervisor-official-source-coverage` |
| Working tree before work | dirty (untracked artefacts only; no modified tracked files) |

The shared checkout was never reset, cleaned, switched, or checked out
destructively. All work happened in a separate `git worktree` on a new branch.
No production data was accessed: discovery ran against a *copy* of the local
SQLite catalogue at `%TEMP%\kilo\sz-cov-data\catalogue.db`, never
`backend/scholarzone.db` or Neon.

## What was built

1. **`backend/app/services/supervisor_applicability.py` (new)** - pure
   applicability classifier. `NOT_APPLICABLE` is reached only when the record's
   own `degree`/`program_type` states a non-programme category and no
   degree-level token; unknown stays applicable and is searched.
2. **`backend/app/services/supervisor_contacts.py` (new)** - reads an official
   administrative contact for a record with no supervisor, from the awarding
   body's own page (plus one contact-route hop), with provenance and its own
   verified-email flag. Emails are accepted only on the awarding domain.
3. **`backend/app/services/supervisor_batch.py` (new)** + **
   `backend/scripts/supervisor_coverage_batch.py` (new)** - the all-scholarship
   batch: manual, bounded, resumable (`after_id` cursor + state file),
   idempotent (upserts), rate-limited (all traffic via `polite_fetch`),
   auditable (one JSON line per item), and dry-run with zero writes. The
   one-scholarship proof route is untouched, and the batch passes no render
   budget.
4. **`scholarship_official_contacts` table** - additive DDL in
   `app/models_supervisor.py` + `app/supervisor_ddl.py`, registered with the
   retention engine, the safety script, and the public read path
   (`supervisor_public.py` returns contacts as a separate list, never inside
   `supervisors`).
5. **`backend/scripts/supervisor_coverage_report.py` (new)** - read-only
   coverage report with per-category totals and source URLs.
6. **Frontend** - `SupervisorPanel` renders official contacts only where there
   is no professor list, labelled as an office, with the same client-side
   verified-email gate the professor cards use.

## Verification gates tightened (not weakened)

A live pass against the real world exposed four ways non-faculty reached the
public list. All four are closed, each with regression tests:

- Organisational names ("Educational Development Unit", "Honours Program") are
  refused on every evidence route - `supervisor_person.py`.
- Administrative office pages (chancellery, admissions, registry, office-team)
  are refused as supervisory evidence - `supervisor_gating.py`. This changes
  the pinned NTU policy, which previously accepted chancellery staff as
  potential supervisors; two tests were updated to pin the new rule.
- Repeated link furniture ("Read More" x16) is skipped by a document-derived
  count, not a word list - `supervisor_discovery.py`.
- Award/donor names ("Dr Helen Marchant-Pritchard Memorial Scholarship") are
  refused, and the honorific path may no longer be re-entered to truncate a
  name out of one.

No gate was relaxed and no failing test was suppressed; two NTU policy tests
and three retention-count tests were updated to pin the stricter rules, with
the reason recorded in each.

## Commands run

```
python scripts/supervisor_verify_safety.py                    # 75/75 checks passed
python scripts/import_smoke_test.py                           # 32 passed, 0 failed
python -m pytest tests/ -q -k supervisor -p no:randomly       # 433 passed
python -m pytest tests/ --tb=line -q -p no:randomly           # 6354 passed, 10 skipped, 1 xfailed
                                                                 (3 maintenance failures removed: see below)
python -m pytest tests/test_maintenance_*.py -q               # 46 passed after fix
cd frontend && npm run lint && npm test && npm run build      # lint clean; 198 tests; build ok
python scripts/supervisor_coverage_batch.py --dry-run ...     # zero writes asserted by tests
python scripts/supervisor_coverage_report.py ...              # generated the coverage report
```

The three `test_no_ambient_database_is_created` failures were caused by a
zero-byte `backend/scholarzone.db` this session created when running a reporting
script without `SCHOLARZONE_DATABASE_URL` set. The file was deleted and those 46
tests pass standalone; the full suite itself is green.

## Coverage summary (snapshot)

636 public scholarships are in scope. 175 were processed by the final gates
before this report; 439 remain `search_pending` and are disclosed, not hidden.
Totals: 2 scholarships with verified supervisors (2 professors: Prof Leon Terry,
Cranfield University; Prof Bushra Ateeq, IIT Kanpur), 0 verified professor
emails, 2 not applicable, 80 official contacts (27 with verified official
emails), 85 blocked, 21 JavaScript-rendered, 87 completed negatives.

See `SUPERVISOR_OFFICIAL_SOURCE_COVERAGE_REPORT.md` for the generated totals,
per-category listings and source URLs.

## Deliberately not done

- No production flags enabled, no discovery dispatched in production, no
  deploy, no merge.
- The contact table reaches production through the existing out-of-band
  migration path; the public read path degrades to "no contacts" until it
  exists, and that tolerance is tested.
