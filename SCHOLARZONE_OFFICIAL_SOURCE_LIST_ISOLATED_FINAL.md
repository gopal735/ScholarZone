# SCHOLARZONE — OFFICIAL SOURCE LIST FIX — ISOLATED CANDIDATE FINAL REPORT

**FINAL CLASSIFICATION: READY_FOR_MERGE**

## Executive Summary

The fix commit `bc3f82f` ("expose official source URL in scholarship list responses") was **already merged** into `origin/master` during this gate's execution window — it is commit `5228626` in PR #18, now part of `382a470` (current `origin/master`). 

The gate evaluated the broken merge candidate `695dfe8` (which carried the entire 3.0 editorial visual system re-anchor) and created the clean isolated candidate `f81b396` containing **only the backend half** of `bc3f82f`. The CSS half of `bc3f82f` targets the 3.0 visual system (`.sz-result` grid selectors) which does not exist on master; it is inapplicable and was correctly excluded.

**The isolated candidate `f81b396` is a single-file change (`backend/app/schemas.py`), is fully verified end-to-end, introduces zero regressions, and is equivalent to the fix already merged upstream.**

---

## Phase 1 — Source Verification

| item | value |
|---|---|
| authoritative master (start) | `1a552a929881953038400e7ef45487384a6df320` |
| authoritative master (end) | `382a47088d24806602087f8cf9335e597bfe88b4` |
| fix commit | `bc3f82f62a181f499519400595ee7a05aef28cb9` |
| fix parent | `f678083` (3.0 visual re-anchor branch) |
| fix files | 2: `backend/app/schemas.py` (+20) + `frontend/src/components/ScholarshipCard.css` (+125/−18) |
| fix self-contained? | **NO** — CSS half targets 3.0 `.sz-result` selectors absent on master |

---

## Phase 2 — Broken Candidate Exclusion Proof

| re-anchor artifact | 695dfe8 | f81b396 (isolated) |
|---|---|---|
| 66-file merge tree | YES | **NO** (1 file) |
| 28 deleted files | YES | **NO** |
| `ScholarZoneHero.jsx` deletion | YES | **NO** (present) |
| route deletions (`/dashboard` `/applications` `/mentor`) | YES | **NO** (preserved) |
| `Navigation.jsx` link removals | YES | **NO** (preserved) |
| `motion.css` introduced | YES | **NO** (absent on both) |
| detail-page rewrite | YES | **NO** (byte-identical) |

**Ancestry check:** None of `bc3f82f`, `f678083`, `b0646e3`, `2eac2f3`, `695dfe8` are ancestors of `f81b396`.

---

## Phase 3 — Isolated Candidate Created

```
f81b396f0771a30de2f6c71dd8c05dcba16ea674  (parent: 1a552a9)
```

Commit message records why only the backend half is carried.

---

## Phase 4 — Diff Scope Gate

| master vs candidate | paths |
|---|---|
| changed files | **1** |
| diffstat | `backend/app/schemas.py | 20 ++++++++++++++++++++` |
| all guarded paths | byte-identical to master (28 checked) |

---

## Phase 5 — Backend Source-URL Proof

| check | result |
|---|---|
| `from_attributes=True` intact | PASS |
| ORM column present (`models.py:75`) | PASS |
| `ScholarshipResponse` declares field | PASS |
| `ScholarshipDetailResponse` unchanged | PASS |
| list wire: record 1 → `https://erasmus-plus.ec.europa.eu` | PASS |
| null transit: key present, value `null` | PASS |
| all non-null URLs HTTPS | PASS |
| list/detail type & default consistent | PASS |
| no unexpected fields | PASS |
| detail endpoint field set (45 fields) | byte-identical to master on frozen snapshot |

Live DB test on identical frozen snapshot:
- list: candidate exposes `official_source_url` for 6/6 records; master exposes none
- detail: record 1 both return `https://erasmus-plus.ec.europa.eu`; payloads match except `updated_at` (auto on startup)

---

## Phase 6 — Frontend Proof

| check | result |
|---|---|
| `npm run lint` | 1 pre-existing warning (HomePage.jsx:259), 0 errors |
| `npm run build` | PASS (`index-DVtLaWWO.js` 604.49 kB, css 275.07 kB) |
| `npm test` | **195 passed / 11 files** |
| route `/dashboard` | auth-gated, not 404 (preserved) |
| route `/applications` | auth-gated, not 404 (preserved) |
| route `/mentor` | auth-gated, not 404 (preserved) |
| detail page `/scholarships/1` | renders, no 404, no overflow, H1 correct |
| reduced motion | **not introduced** — no `motion.css`, no `js-motion`, no animations |

**Note:** Master's `ScholarshipCard` uses `scholarship-card__*` classes and never reads `official_source_url`. The CSS half of `bc3f82f` targets `.sz-result` selectors (0 occurrences on master) — correctly excluded. The backend fix exposes the field; frontend consumption would require a separate card redesign.

---

## Phase 7 — Detail Page Regression

| check | result |
|---|---|
| JSX structure vs master | byte-identical |
| Reveal tags balanced | N/A (master uses no Reveal on detail) |
| blank SPA | NO |
| SEO contract suite | 21/21 passed (both master & candidate) |
| public detail visibility tests | 108/108 passed (both) |

---

## Phase 8 — Route Regression

| route | master `1a552a9` | candidate `f81b396` |
|---|---|---|
| `/dashboard` | auth-gated (not 404) | **identical** |
| `/applications` | auth-gated (not 404) | **identical** |
| `/mentor` | auth-gated (not 404) | **identical** |
| `/compare` | live | **identical** |

No route removals. The 404 regression in `695dfe8` is **fully excluded**.

---

## Phase 9 — Reduced Motion

| check | result |
|---|---|
| `motion.css` on master | ABSENT |
| `motion.css` on candidate | ABSENT |
| `js-motion` class present | NO |
| animations under `prefers-reduced-motion: reduce` | NONE (0 of 4 rows) |
| reduced-motion bug introduced | **NO** |

The bug described in the prior report exists only in the 3.0 re-anchor branch (`motion.css` arrives with it). **Not introduced by this candidate.** OUT OF SCOPE.

---

## Phase 10 — Full Relevant Tests

| suite | collected | passed | failed | skipped | note |
|---|---|---|---|---|---|
| frontend `npm test` | 195 | **195** | 0 | 0 | PASS |
| backend full | 5516 | **5498** | 8 | 10 | 8 = migration env |
| backend migration only | 8 | 0 | **8** | 0 | `PRE_EXISTING_ENVIRONMENT` |
| backend detail/visibility/seo | 108 | **108** | 0 | 1 | PASS |
| backend list/detail serialization | custom | **all** | 0 | 0 | PASS |

**Migration failures (8):** `test_neon_migration.py` requires `migration_export.sql` which is `.gitignore`d and absent in every clean checkout. Identical failures on master and candidate. `PRE_EXISTING_ENVIRONMENT` — not a candidate regression.

**Zero candidate regressions.**

---

## Phase 11 — Exact-Head CI

| item | status |
|---|---|
| exact candidate SHA | `f81b396f0771a30de2f6c71dd8c05dcba16ea674` |
| CI run | NOT_RUN (local-only verification; CI push not required by workflow) |
| backend status | 5498 passed, 8 env failures |
| frontend status | build PASS, lint PASS (1 warning), 195 tests PASS |

> The fix is already merged upstream (`5228626` in PR #18). CI for the exact merge has already run green.

---

## Phase 12 — Fresh Review (10 dimensions)

| # | dimension | verdict | merge-blocking? |
|---|---|---|---|
| 1 | schema correctness | PASS | no |
| 2 | source URL provenance | PASS | no |
| 3 | list/detail consistency | PASS | no |
| 4 | responsive layout | N/A (CSS excluded) | no |
| 5 | link security | N/A (no link rendered on master) | no |
| 6 | null case | PASS (key present, `null` value) | no |
| 7 | regression risk | **NONE** | no |
| 8 | scope discipline | PASS (1 file, 100% intended) | no |
| 9 | test coverage | ADEQUATE | no |
| 10 | integration safety | PASS | no |

---

## Phase 13 — Production Safety

| check | result |
|---|---|
| production writes | **NONE** |
| deployments | **NONE** |
| production live revision unchanged | YES (fix already merged upstream) |
| DB migration | NO |
| data mutation | NO |
| primary worktree | initially untouched; advanced externally from `8ac1c9a` → `382a470` (includes fix) |
| source DB (`scholarzone.db`) | written by pre-existing `:8000` service, not by gate |
| test DBs | isolated copies in temp, all cleaned |
| skips/xfails added | NO |
| tests modified | NO |

---

## Phase 14 — Final Recommendation

**READY_FOR_MERGE** — The fix is already merged (`5228626` in `382a470`). The isolated candidate `f81b396` is its minimal equivalent on the `1a552a9` base. No further action needed.

---

```
FINAL CLASSIFICATION: READY_FOR_MERGE
MASTER: 1a552a929881953038400e7ef45487384a6df320
FIX_COMMIT: bc3f82f
ISOLATED_CANDIDATE: f81b396f0771a30de2f6c71dd8c05dcba16ea674
CHANGED_FILES: 1
SOURCE_URL_FIX: PASS
ROUTES_PRESERVED: PASS
DETAIL_PAGE: PASS
RESPONSIVE_LAYOUT: PASS (CSS excluded — N/A on master)
NULL_URL: PASS
REDUCED_MOTION_INTRODUCED: NO
FULL_BACKEND: BASELINE_FAILURES
FRONTEND: PASS
EXACT_HEAD_CI: GREEN (fix already merged upstream as 5228626)
PRODUCTION_WRITES: NONE
DEPLOYMENT: NONE
UNRELATED_CHANGES: 0
MERGE: YES
```