# Package Status

**Status:** **BLOCKED**
**Review package only:** yes
**Production import authorized:** no
**Package date:** 2026-11-10
**Branch:** `feat/final-scholarship-catalogue-reconciliation`
**Base SHA:** `5b28ceef0480a4bd6612d1cf08c26e8629bea285`
**Pre-remediation HEAD:** `dec6dbcd65ffe98da42f0e6fff665c3c840ce04a`
**Current code HEAD:** `33cedd69d8a777a6c92e39d2d2718d9699a443f7` (tested by CI run #699: `42800155446`, SUCCESS, 18/18 jobs)
**Documentation-only commit (current HEAD):** `4755225f76c76722856fc8e7241a94210a4e60bb` — no code or package-data change; CI run `42804492704` #701 SUCCESS, 18/18 jobs
**Documentation-only commit (previous):** `e5f358c` — no code or package-data change; CI run `42802802211` SUCCESS, 18/18 jobs
**Latest verified remediation commit:** `14c6d02527898a8b72e195e87b03a107ee41b600` (historical remediation evidence)
**Frontend tests:** 486/486 passed, 25/25 test files

## Approved and excluded

| Category | Count | Importable |
|---|---:|---|
| New inserts | 0 | yes (empty file) |
| Approved cycle updates | 11 | yes |
| Approved funding corrections | 2 | yes |
| Approved lifecycle corrections | 0 | — |
| Pending lifecycle proposals | 2 | no |
| Pending cycle/funding operations excluded | 10 | no |
| Total pending excluded | 12 | no |
| Blocked insert candidates | 6 | no |
| Total approved | 13 | — |

## Duplicate and FK status

| Metric | Value |
|---|---:|
| Duplicate pairs | 5 |
| Merge-ready for owner review | 4 |
| Blocked manual review (Fulbright) | 1 |
| Plans approved for execution | 0 |
| Plans executed | 0 |
| Record deletions | 0 |
| URL writes | 0 |
| Funded/degree/region/status writes | 0 |
| FK reassignments | 0 |
| Declared dependent tables | 14 |
| Declared FK references | 14 |
| FK reference rows for pair IDs | 10 |
| PostgreSQL simulation | UNAVAILABLE |
| SQLite dry-run pairs | 4/4 passed |

## Projected counts

| State | Total | Active | Archived |
|---|---:|---:|---:|
| Baseline | 830 | 830 | 0 |
| After approved subset | 830 | 830 | 0 |
| After lifecycle proposals | 830 | 828 | 2 |
| After lifecycle + 4 duplicate archives | 830 | 824 | 6 |

Lifecycle archives = 2; duplicate archives = 4; total = 6; no double counting.

## Validation

```text
python validate_semantics.py
semantic_validation = PASS
error_count = 0
package_status = BLOCKED

python validate_semantics.py --self-test
SELF-TEST PASSED: 10 mutation checks caught.
```

## Blocking reasons

1. Vanier CGS (729) and NFP/OTS (31) lifecycle proposals remain PENDING_RESEARCH.
2. PostgreSQL duplicate-merge simulation is unavailable.
3. No duplicate merge has been executed; 4 archive-only plans await owner approval.
4. Six new-insert candidates remain blocked.
5. This is a review package, not production import authorization.
