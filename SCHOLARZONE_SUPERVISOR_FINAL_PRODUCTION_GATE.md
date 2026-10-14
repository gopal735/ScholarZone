# SCHOLARZONE — SUPERVISOR FINAL PRODUCTION GATE

**FINAL CLASSIFICATION: SUPERVISOR_SCHEMA_READY_DISCOVERY_NOT_PROVEN**

The Supervisor schema blocker is resolved and the Supervisor runtime is healthy.
Real-source discovery could **not** be executed from this environment, so it is
**not** claimed.

| Item | Value |
|---|---|
| Production SHA | `1a552a929881953038400e7ef45487384a6df320` |
| `origin/master` | `1a552a929881953038400e7ef45487384a6df320` — **match** |
| SCHEMA_READY | **YES** |
| ROUTES_HEALTHY | **YES** |
| REAL_SOURCE_PROVEN | **NO** |
| VERIFIED_PROFESSORS | **0** |
| Persisted candidates | **0** |
| Production writes by me | **NONE** |
| Supervisor activation | **OFF** (not enabled) |
| Maintenance | **OFF** (not touched, no dispatch POSTed) |
| Playwright | optional, **not installed** in the production runtime |
| Migrations run by me | **NONE** |

---

## PHASE 1 — Pre-flight

| Check | Result |
|---|---|
| `GET https://scholarzone-fwzj.vercel.app/api/health` | `200` `{"status":"ok","revision":"1a552a929881953038400e7ef45487384a6df320"}` |
| Production SHA == `origin/master` | **YES** |
| Stale SHA? | **NO** — did not stop |

### Database identity — could not be established

The production connection string is **not obtainable from this environment**:

| Source | Result |
|---|---|
| `SCHOLARZONE_DATABASE_URL` in process env | not set |
| `backend/.env` | only `RESEND_API_KEY`, `NOTIFICATION_EMAIL`, `SCHOLARZONE_VERIFICATION_SECRET` |
| `.env.local` / `.env.production.local` | only `VERCEL_OIDC_TOKEN` |
| `vercel env pull --environment=production` (canonical project) | `SCHOLARZONE_DATABASE_URL` and `DATABASE_URL` written as **`[SENSITIVE]`** placeholders (13 chars) |

So I could not connect to Neon, and therefore could **not** perform the read-only
schema inspection this phase calls for (existing tables, indexes, column types,
nullability, constraints, foreign keys, unique indexes, row counts) directly
against the database. The verification in Phase 4 is therefore **functional and
behavioural**, not introspective. That limitation is stated rather than glossed.

---

## PHASE 2 — Exact DDL proven (authoritative source)

Read from `backend/app/supervisor_ddl.py` at `origin/master`, assembled through the
repository's own helpers — `create_table_statements("postgresql")` and
`index_statements()` — which are the same functions `app/database.py` and
`backend/migrate_schema.py` both import, so the statement text cannot drift.

| Measure | Value |
|---|---|
| `CREATE TABLE IF NOT EXISTS` statements | **7** |
| `CREATE INDEX IF NOT EXISTS` statements | **21** |
| **Total** | **28** |
| Non-conforming statements | **0** |
| Forbidden tokens found (`DROP`, `DELETE`, `UPDATE`, `TRUNCATE`, `ALTER`, `INSERT`, `REPLACE`, `GRANT`, `REVOKE`) | **0** |

`REQUIRED_NEW_TABLES` matches `NEW_TABLE_DDL` keys exactly. Every statement begins
`CREATE TABLE IF NOT EXISTS` or `CREATE INDEX IF NOT EXISTS`.

### The 28 statements

```
 1. CREATE TABLE IF NOT EXISTS contact_templates (...)
 2. CREATE TABLE IF NOT EXISTS scholarship_supervisor_coverage (...)
 3. CREATE TABLE IF NOT EXISTS professor_profiles (...)
 4. CREATE TABLE IF NOT EXISTS scholarship_professor_links (...)
 5. CREATE TABLE IF NOT EXISTS supervisor_source_evidence (...)
 6. CREATE TABLE IF NOT EXISTS professor_availability (...)
 7. CREATE TABLE IF NOT EXISTS professor_outreach_records (...)
 8. CREATE INDEX IF NOT EXISTS ix_contact_templates_active ON contact_templates (is_active)
 9. CREATE INDEX IF NOT EXISTS ix_supervisor_coverage_status ON scholarship_supervisor_coverage (status)
10. CREATE INDEX IF NOT EXISTS ix_supervisor_coverage_next_check_at ON scholarship_supervisor_coverage (next_check_at)
11. CREATE INDEX IF NOT EXISTS ix_supervisor_coverage_scholarship_id ON scholarship_supervisor_coverage (scholarship_id)
12. CREATE INDEX IF NOT EXISTS ix_professor_institution_name ON professor_profiles (institution_name)
13. CREATE INDEX IF NOT EXISTS ix_professor_institution_department ON professor_profiles (institution_name, department_name)
14. CREATE INDEX IF NOT EXISTS ix_professor_canonical_name ON professor_profiles (canonical_name)
15. CREATE INDEX IF NOT EXISTS ix_professor_profile_status ON professor_profiles (profile_status)
16. CREATE INDEX IF NOT EXISTS ix_professor_next_verification_at ON professor_profiles (next_verification_at)
17. CREATE INDEX IF NOT EXISTS ix_professor_links_scholarship_status ON scholarship_professor_links (scholarship_id, verification_status)
18. CREATE INDEX IF NOT EXISTS ix_professor_links_scholarship_id ON scholarship_professor_links (scholarship_id)
19. CREATE INDEX IF NOT EXISTS ix_professor_links_professor_id ON scholarship_professor_links (professor_id)
20. CREATE INDEX IF NOT EXISTS ix_professor_links_verification_status ON scholarship_professor_links (verification_status)
21. CREATE INDEX IF NOT EXISTS ix_supervisor_evidence_professor_id ON supervisor_source_evidence (professor_id)
22. CREATE INDEX IF NOT EXISTS ix_supervisor_evidence_scholarship_id ON supervisor_source_evidence (scholarship_id)
23. CREATE INDEX IF NOT EXISTS ix_supervisor_evidence_source_host ON supervisor_source_evidence (source_host)
24. CREATE INDEX IF NOT EXISTS ix_professor_availability_professor_id ON professor_availability (professor_id)
25. CREATE INDEX IF NOT EXISTS ix_outreach_user_status ON professor_outreach_records (user_id, status)
26. CREATE INDEX IF NOT EXISTS ix_outreach_user_follow_up ON professor_outreach_records (user_id, follow_up_due_at)
27. CREATE INDEX IF NOT EXISTS ix_outreach_professor_id ON professor_outreach_records (professor_id)
28. CREATE INDEX IF NOT EXISTS ix_outreach_scholarship_id ON professor_outreach_records (scholarship_id)
```

No unexpected statement was found, so no stop was required.

---

## PHASE 3 — Apply: **already applied, not by me**

**I did not run the migration.** No credentials were available to run it, and I did
not attempt to work around that.

By the time I reached the apply step, the schema had **already been applied to
production by another actor** out-of-band, exactly as `backend/app/supervisor_ddl.py`
prescribes. Master is unchanged at `1a552a9`, so this was a database-side action,
not a code deployment.

The repository states this requirement itself:

> `backend/app/supervisor_ddl.py` — "Two callers need this DDL and they must not
> disagree: the startup/dev upgrade path in `app.database`, and **the out-of-band
> production migration in `backend/migrate_schema.py`** […] which is invisible
> until a production query fails on a field that validates fine locally."

And `app/main.py::_run_init` confirms production must never self-migrate:

> "Production verifies connectivity and nothing else. **It does not run the schema
> migration.** `create_all` plus the `ALTER TABLE` and `CREATE INDEX` statements
> take `ACCESS EXCLUSIVE` locks on `scholarships` and carry no statement timeout,
> so on a serverless cold start they wait on any concurrent maintenance job and
> never return."

That is the correct design, and it is why the tables could not appear on their own.
No migration run ID, start/end time, or transaction outcome is recorded here
because **no migration was executed by this task**. Inventing one would be
dishonest.

---

## PHASE 4 — Verification (functional, not introspective)

Direct database introspection was impossible (Phase 1). What is proven is that the
tables exist and serve correctly, because three endpoints read from three different
Supervisor tables and return well-formed data.

| Endpoint | Status | Evidence of the underlying table |
|---|---|---|
| `GET /api/scholarships/533/supervisors` | **200** | reads `scholarship_supervisor_coverage` |
| `GET /api/scholarships/533/supervisor-summary` | **200** | reads `scholarship_supervisor_coverage` |
| `GET /api/supervisor-email/templates` | **200** | reads `contact_templates`, returns **3 real rows** |

Actual payloads:

```json
GET /api/scholarships/533/supervisors
{"scholarship_id":533,
 "coverage":{"coverage_status":"search_pending","verified_supervisor_count":0,
             "evidence_state":"not_collected","last_checked_at":null,
             "discovery_pending":true},
 "supervisors":[]}

GET /api/supervisor-email/templates
[{"template_key":"masters_initial", ...},
 {"template_key":"phd_initial", ...},
 {"template_key":"follow_up_no_response", ...}]
```

`contact_templates` returning three populated rows is decisive: the table exists and
holds data, and it can only be read if `CREATE TABLE` succeeded.

**The missing-table 500 is gone.** For comparison, earlier in this same engagement on
master `adb4dee` these exact routes returned **HTTP 500** while `/api/scholarships/533`
returned 200 — the classic missing-table signature.

### Data integrity

| Check | Result |
|---|---|
| Professor rows | **0** — `verified_supervisor_count: 0`, `supervisors: []` |
| Scholarship rows | **12**, unchanged (12 before) |
| Unrelated data changed | **none observed** |
| Production writes by me | **NONE** — every request I issued was a `GET` |

Not verifiable without database access: per-column types, nullability, constraint
definitions, foreign keys, and unique indexes. Stated as unverified rather than
assumed.

---

## PHASE 5 — Idempotency

Not executed by me, and I make **no claim** about a second run.

The DDL is structurally idempotent — all 28 statements are `IF NOT EXISTS`
(Phase 2) — and `_upgrade_postgresql_schema` wraps them in a single
`engine.begin()` transaction. But that is a static property of the SQL, not an
observed second run. Claiming "NO CHANGES NEEDED" without having run it would be a
false report.

---

## PHASE 6 — Live Supervisor routes

| Route | Status |
|---|---|
| `/scholarships/{id}/supervisors` | **HTTP 200** |
| `/scholarships/{id}/supervisor-summary` | **HTTP 200** |
| `/supervisor-email/templates` | **HTTP 200** |

The missing-table 500 is confirmed gone. All three return correct, non-error
responses consistent with an empty-but-healthy discovery state.

Note: `/api/supervisor/discover` does not exist in this codebase. The real read
routes are the three above; the write/discovery surface is
`/api/internal/discover/*`.

---

## PHASE 7 — Real production discovery: **NOT EXECUTED**

Discovery could not be run, for two independent reasons, both because the required
secrets are Vercel-SENSITIVE and correctly not guessable:

| Path | Requirement | Availability |
|---|---|---|
| Internal HTTP route `/api/internal/discover/*` | header `X-Verification-Secret` equal to `settings.verification_secret` | **production secret unpullable** (`[SENSITIVE]`) |
| Local bounded run against production | `SCHOLARZONE_DATABASE_URL` | **unpullable** (`[SENSITIVE]`) |

`backend/app/routers/discovery.py:34` guards the router with
`_verify_secret(x_verification_secret)` and returns
`"Invalid or missing verification secret."` on mismatch. The only
`SCHOLARZONE_VERIFICATION_SECRET` on this machine is a local development value in
`backend/.env`; using it against production would fail, and attempting to guess or
brute the production secret is out of the question.

Consequently:

- **No real source was fetched.**
- **The merged inline-role fix (`91bcdb5`, "a role word alone must not establish a
  person") was therefore NOT exercised against a real source.** Its unit tests cover
  it; real-source proof does not exist.
- No login, CAPTCHA or anti-bot bypass was used, because no request was made at all.

---

## PHASE 8 — Persistence

| Measure | Value |
|---|---|
| Candidates evaluated | **0** |
| Candidates passing identity/provenance | **0** |
| Rows persisted | **0** |
| Professor rows after | **0** |

Nothing was persisted, and **no identity was fabricated**. Production coverage
remains `coverage_status: search_pending`, `evidence_state: not_collected`,
`discovery_pending: true` — an honest "not yet looked" state, which is the correct
outcome when discovery has not run.

---

## PHASE 9 — Activation decision

Per Phase 9 and the absolute rules, **broad Supervisor activation was NOT enabled**.
It was not enabled even conditionally: real-source proof did not succeed, so the
precondition for activation was not met.

| Item | State |
|---|---|
| SCHEMA_READY | **YES** |
| ROUTES_HEALTHY | **YES** |
| REAL_SOURCE_PROVEN | **NO** |
| VERIFIED_PROFESSORS | **0** |
| Supervisor activation | **OFF — unchanged** |
| Maintenance | **OFF — unchanged** |
| Browser rendering | **unavailable** in the default production runtime (Playwright not installed); `SCHOLARZONE_SUPERVISOR_RENDER_ENABLED` off |

Maintenance isolation held: I did not touch maintenance, did not POST
`/api/internal/maintenance/dispatch`, and did not alter any Phase A/B file.

---

## PHASE 10 — CI caveat (recorded, not acted on)

Per instruction, **CI was not modified**.

**`backend-tests` remains structurally false-green.** `.github/workflows/ci.yml:77-80`:

```yaml
      - name: Run backend tests
        run: |
          cd backend
          python -m pytest tests/ -x --tb=short 2>&1 | tee pytest.log
```

No `set -o pipefail`, so the step reports `tee`'s always-zero exit status and cannot
fail. A failing backend suite is reported as a passing job, and the
`Upload test results` step is gated on `if: failure()` so the log is never uploaded
either. The repository already documents this hazard for the frontend step it did
fix (`ci.yml:148-150`: "*which is exactly what the backend step above does*").

**Green `backend-tests` was not treated as proof anywhere in this report.** Every
backend figure quoted here comes from locally executed runs or from live production
requests, never from that job.

---

## What remains, and the single unblock

Everything except one step is done. The Supervisor schema is live, the routes are
healthy, and the only outstanding item is exercising real discovery.

**To run Phase 7/8, one of these is needed — deliberately not worked around here:**

1. Supply the production `SCHOLARZONE_VERIFICATION_SECRET` so a single bounded
   `POST /api/internal/discover/trigger` (or `/api/internal/discover/country/{country}`)
   can be issued against one official university domain; or
2. Supply the production `SCHOLARZONE_DATABASE_URL` so
   `python backend/migrate_schema.py --validate-only` can confirm the schema
   introspectively and a bounded local discovery run can be performed.

With either, the remaining sequence is: one bounded official-domain discovery →
verify personhood + institutional domain + academic role + source provenance →
persist only fully-verified candidates → report `VERIFIED_PROFESSORS = N` → then
decide on bounded activation. Until a real source has been proven, activation should
stay off.

---

## Constraint compliance

| Rule | Status |
|---|---|
| Never enable Supervisor before schema is healthy | **honoured** — activation left OFF |
| Never fabricate identities | **honoured** — 0 candidates, 0 persisted |
| Never run unrelated migrations | **honoured** — no migration run at all |
| Never modify maintenance | **honoured** — zero maintenance changes |
| Never install Playwright back into the Vercel function | **honoured** — untouched; `requirements.txt` still free of it |
| Never touch dirty worktree `8ac1c9a4` | **honoured** — all work in isolated worktrees |
| Never force-push | **honoured** — no push issued |

---

## Classification

**SUPERVISOR_SCHEMA_READY_DISCOVERY_NOT_PROVEN**

The production Supervisor schema blocker is resolved: all three Supervisor routes
return `200` with correct data, including three real `contact_templates` rows, and the
missing-table 500 signature is gone. Professor rows remain `0`, the catalogue is
unchanged at 12 scholarships, and I made no production writes.

Real-source discovery is **not** claimed. It could not be executed because both the
production verification secret and the production database URL are Vercel-SENSITIVE
and unpullable, and guessing them is not acceptable. Consequently the merged
inline-role personhood fix remains unproven against a real source, verified
professors stand at `0`, Supervisor activation remains **OFF**, and maintenance
remains **OFF**.
