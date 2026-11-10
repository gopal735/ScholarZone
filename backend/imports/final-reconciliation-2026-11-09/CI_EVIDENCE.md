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

The authoritative exact-HEAD result is the GitHub Actions workflow run attached
to the latest commit on PR #81. A green run on an earlier commit is not accepted
as exact-HEAD evidence.

To verify after pushing:

```bash
git rev-parse HEAD
gh pr checks 81 --watch
gh run list --branch feat/final-scholarship-catalogue-reconciliation --limit 1
```

Record the remediation commit SHA, workflow run URL, and conclusion in the PR
conversation when the run finishes. Local validation above is necessary but is
not a substitute for exact-HEAD CI.
