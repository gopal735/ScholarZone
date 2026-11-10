# CI Evidence

**Package:** `backend/imports/final-reconciliation-2026-11-09/`
**Branch:** `feat/final-scholarship-catalogue-reconciliation`
**Base SHA:** `5b28ceef0480a4bd6612d1cf08c26e8629bea285`

## Pre-remediation state

| Item | Value |
|---|---|
| Pre-remediation HEAD | `dec6dbcd65ffe98da42f0e6fff665c3c840ce04a` |
| Checks at old HEAD | SUCCESS |
| PR | #81 |
| Mergeable | yes |
| Draft | no |

The old checks passed before this remediation. They do not validate the
rewritten package, which is why exact-HEAD CI is required.

## Local validation evidence (2026-11-10)

```text
python validate_semantics.py
{
  "semantic_validation": "PASS",
  "error_count": 0,
  "package_status": "BLOCKED",
  "postgresql_simulation": "UNAVAILABLE"
}

python validate_semantics.py --self-test
SELF-TEST PASSED: 10 mutation checks caught.
```

Duplicate simulation: isolated SQLite copy, 4/4 pairs passed,
830/830/0 → 830/826/4, coverage 830 → 830, 0 URL arrays,
4/4 UNIQUE collision probes, source database SHA unchanged.

PostgreSQL simulation: **UNAVAILABLE** (no disposable DSN, PostgreSQL
client/server, or Docker). Not a pass.

## Exact-HEAD CI

**Code HEAD tested:** `33cedd69d8a777a6c92e39d2d2718d9699a443f7`
**Documentation-only commit (current HEAD):** `e5f358cb7b90abf3677aa0f705d886acacdb4104` — no code or package-data change
**Latest verified remediation commit:** `14c6d02527898a8b72e195e87b03a107ee41b600` (historical remediation evidence)

**Exact-HEAD ScholarZone CI run #699:** SUCCESS — https://github.com/gopal735/ScholarZone/actions/runs/42800155446
**ScholarZone CI for documentation commit:** SUCCESS — https://github.com/gopal735/ScholarZone/actions/runs/42802802211

**Result:** 18/18 jobs passed (backend-tests, Gate 1/2 PostgreSQL 16 and 18,
migration, preflight, schema compatibility, frontend, snapshot, import-smoke,
zero-paid guard, git-integrity, env-config).

**Frontend tests:** 486/486 passed, 25/25 test files.

**Backend tests:** 6,204 passed, 15 skipped.

**Reconciliation package tests:** `backend/tests/test_final_reconciliation_package.py`
— 3 passed.

**Distinction:** The 18/18 CI jobs include PostgreSQL CI compatibility jobs
(migration, preflight, schema compatibility on PostgreSQL 16 and 18). These are
CI environment compatibility checks, not the package's PostgreSQL
duplicate-merge simulation, which remains **UNAVAILABLE** (no disposable DSN,
PostgreSQL client/server, or Docker in this local environment) and is not
reported as a pass.

The old checks at pre-remediation HEAD passed before this remediation. They do
not validate the rewritten package, which is why exact-HEAD CI is required.
Local validation is necessary but is not a substitute for exact-HEAD CI.
