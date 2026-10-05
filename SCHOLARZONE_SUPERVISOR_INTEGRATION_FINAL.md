# ScholarZone Supervisor Discovery — Re-anchor Integration Final

The supervisor candidate was based on stale master and has been re-anchored onto
the actual current canonical master. Everything below was re-run **on the
integrated tree**, not on the old candidate.

No push. No merge. No deploy. Production rendering remains OFF.
**Production writes: NONE.**

---

## 1. The stated master was also stale

The task named `fc4096f7a2aac8530f4e14495a7f21b9a97419be` as canonical. It is not
current — master advanced again, roughly two minutes before the task began.

Verified three independent ways, none of which trusts a local ref:

| Source | Result |
|---|---|
| `git ls-remote origin HEAD refs/heads/master` (contacts the server, ignores local refs) | `cfb2b54d03341316985e66c7963a4c73976d33ef` |
| GitHub API `repos/gopal735/ScholarZone/commits/master` | `cfb2b54d…`, "Merge pull request #8 from gopal735/seo/google-indexing-release", 2026-10-04T20:18:18Z |
| `git fetch --prune` then local `origin/master` | `cfb2b54d…` (fast-forward from `fc4096f`) |

`fc4096f7` is present locally and **is an ancestor of `cfb2b54`** — verified. The
fetch reported `fc4096f..cfb2b54 master -> origin/master`, so the true canonical
master used here is:

```
cfb2b54d03341316985e66c7963a4c73976d33ef
```

The earlier report's `master = ddcd9c3` was accurate when written and is now two
merges behind. Corrected here rather than carried forward.

## 2. Ancestry of the candidate

| Fact | Value |
|---|---|
| Candidate | `a0f3681` (parent `d87f657`) |
| Merge-base with current master | `ddcd9c3` |
| **Candidate contains current master?** | **No** |
| Commits on master missing from the candidate | 12 (SEO release + build-provenance release) |

So the candidate genuinely was based on older master, and re-anchoring was
required rather than optional.

## 3. No duplication risk

Current master contains **no** supervisor implementation — `git ls-tree` for
`supervisor` on `cfb2b54` returns nothing. There was nothing to duplicate, so the
integration is purely additive.

## 4. Integration method

**Cherry-pick onto a new branch from current master.** The original branch
`feat/supervisor-discovery-2` (`a0f3681`) is **untouched**; nothing was rebased,
reset, cleaned or force-pushed, and master was not rewritten.

```
git worktree add -b feat/supervisor-discovery-integrated <path> cfb2b54
git cherry-pick d87f657     # zero conflicts
git cherry-pick a0f3681     # zero conflicts
```

New history: `cfb2b54 → ef2e512 (1.0) → 4501e2c (2.0)`.

### The two overlaps, and why both sides survived

| File | Master's side | Supervisor side | Result |
|---|---|---|---|
| `backend/app/main.py` | `build_provenance`, `read_embedded_revision`, `/health` revision reporting | three supervisor router registrations | **both present** — provenance imports at lines 15–16, routers at 310/337/338 |
| `frontend/src/pages/ScholarshipDetailsPage.jsx` | SEO canonical URL, JSON-LD, `CANONICAL_ORIGIN` | `<SupervisorPanel>` mount | **both present** — panel imported at line 4, SEO block intact |

Verified by reading the integrated files, not by assuming the merge was clean.

### Preserved, checked by ancestry and by file

`3bf92b6` ingestion image preservation · `87ad84c` purge image safety ·
`fc4096f7` build provenance · `ddcd9c3` public visibility · Match 2.0 ·
Count Intelligence · Mentor · Dashboard · image pipeline · ingestion · purge ·
admin verification · `repositories/scholarships.py` · `routers/scholarships.py` ·
`app/models.py` · `app/dependencies.py` · `app/services/auth.py` ·
`routers/auth.py`.

**Supervisor scope preserved intact:** browser fallback, academic-evidence rules,
login/anti-bot safety, domain validation, bounds, determinism, provenance. The
seven supervisor tables are defined exactly once; no second auth module exists
(`student_auth*.py` count: 0).

**Auth ownership unchanged:** the integrated app exposes exactly
`/auth/login`, `/auth/logout`, `/auth/register`, `/auth/session` — master's four,
none of the supervisor's.

## 5. Verification on the integrated tree

Nothing below is inherited from the old candidate. All of it ran against the
re-anchored branch.

### Supervisor suite

**227 passed, 0 failed** — the exact count previously reported, now measured here.

### The specific proofs the gate named

| Proof | Result |
|---|---|
| Static negative proof — a static fetch genuinely cannot see the professor | **PASS** |
| Browser fallback proof — real headless Chromium, real JS, real professor stored | **PASS** |
| Domain validation | **PASS** |
| Login / anti-bot safety | **PASS** (8 tests) |

### Determinism

**15/15 identical** — 10 in-process plus 5 isolated-process, all `56 passed`, one
distinct outcome.

### Full backend regression — measured, not inferred

| | Baseline (untouched `cfb2b54`) | Integrated | Delta |
|---|---|---|---|
| Passed | 5 079 | **5 306** | **+227** |
| Failed | 9 | **9** | 0 |
| Skipped | 10 | **10** | 0 |

The baseline was run on a **separate detached worktree at `cfb2b54`**, not
computed. The two failure sets were then diffed **by name** and are
**identical**: zero new deterministic failures.

All nine are environmental and reproduce on untouched master: one missing `yaml`
dev dependency, eight missing gitignored `migration_export.sql`.

### Frontend

| Gate | Result |
|---|---|
| `npm test` | **195 passed, 11 files** |
| `npm run lint` | **0 errors**, 1 pre-existing warning |
| `npm run build` | **success** |

195 rather than the earlier 174 because current master contributes its own SEO
contract suite. Both sides run.

### No test weakened

No test was skipped, xfailed, deleted or loosened by the integration. The skip
count is **unchanged at 10** between baseline and integrated, which is the
measurable form of that claim.

## 6. Re-checks

| Item | Status |
|---|---|
| Supervisor tests | 227 passed, 0 failed — measured on the integrated tree |
| Unexplained new failures | **zero** — failure sets diffed by name, identical |
| Skipped / xfailed / weakened tests | none; skip count unchanged at 10 |
| Production activation | **OFF** — `SCHOLARZONE_SUPERVISOR_RENDER_ENABLED` unset by default; maintenance worker untouched; batch path passes no render budget |
| PostgreSQL / production supervisor state | **UNKNOWN** — not read, not inferred |
| Production writes | **NONE** |

## 7. What this does and does not prove

**Proven:** the local browser chain works — real HTTP, real JavaScript execution,
real rendered DOM, real academic-role extraction, real storage, deterministically,
on the integrated tree. That is a genuine result.

**Not proven:** that a real production institutional directory can be processed
successfully. Bounded read-only validation against three real public
institutions found two inconclusive (one JavaScript-rendered, one login-gated) and
one inaccessible (HTTP 500). No real institution has yet yielded a professor, and
this integration did not change that.

That gap is why production rendering stays off, and why it is an owner decision
rather than a step this work took.

---

```
FINAL CLASSIFICATION:
READY_FOR_REVIEW

CURRENT MASTER:
cfb2b54d03341316985e66c7963a4c73976d33ef
(the task's stated fc4096f7 is an ancestor of this, one merge behind)

INTEGRATION METHOD:
cherry-pick onto a new branch from current master; zero conflicts;
original branch a0f3681 untouched; nothing rebased, reset, cleaned or pushed

SUPERVISOR SUITE:
227 passed, 0 failed (measured on the integrated tree)

REAL JS E2E:
PASS

STATIC NEGATIVE PROOF:
PASS

BROWSER FALLBACK PROOF:
PASS

DOMAIN VALIDATION:
PASS

DETERMINISM:
PASS - 15/15 identical

FULL BACKEND REGRESSION:
5 306 passed, 9 failed, 10 skipped
baseline on untouched cfb2b54: 5 079 passed, 9 failed, 10 skipped
failure sets identical by name; zero new deterministic failures

FRONTEND:
195 passed, 11 files; lint 0 errors; build success

SKIPPED / XFAILED / WEAKENED TESTS:
none - skip count unchanged at 10

PRODUCTION ACTIVATION:
OFF

PRODUCTION WRITES:
NONE

PRODUCTION SUPERVISOR STATE:
UNKNOWN

EXACT REMAINING BLOCKERS:
1. No real institutional directory has yet yielded a verified professor. The local
   end-to-end proof is genuine, but real sources validate as inconclusive or
   inaccessible. Production rendering therefore stays off until an owner enables
   it and it is run against real records.
2. Owner merge decision. This branch is ready for review; it has not been pushed,
   merged or deployed.
```