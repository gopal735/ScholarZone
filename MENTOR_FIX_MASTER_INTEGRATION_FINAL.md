# MENTOR FIX — MASTER INTEGRATION FINAL

**No deployment. No push. No merge to master. No force push, no history rewrite, no amend.** One new
commit exists on a **local branch only**, verified absent from the remote.

---

## 1. Current Production SHA

`4edd154a303715442a2f0517b052259e5f113cab` — `docs: record the final suite numbers and the production run`

Confirmed live via `/api/health` at the start and again at the close of this task. Production **did not
move** during this work.

## 2. Current Master SHA

`573a983b004ab08578497272659123323ab489b7` — `docs: the wording fix is deployed and verified in production`

Divergence from production — master is a **fast-forward** of production (`merge-base --is-ancestor`
exit 0) by exactly **two docs-only commits**:

```
573a983  docs: the wording fix is deployed and verified in production
84d9d7e  docs: correct the commit list in the final report header
4edd154  (production)
```

No code difference between production and master, which is why the fix applied without conflict.

**Pre-check — master does NOT already contain the fix:**

| probe | result |
|---|---|
| `fingerprint = (entry.scholarship_id, chip.label, chip.value)` | **absent** |
| `_STUDENT_SCOPE` defined | **absent** |
| `fingerprint = (chip.label, chip.value)` (the bug) | **present** |
| `backend/tests/test_evidence_record_identity.py` | **not on master** |

## 3. Candidate SHA

`00d835dff9da1d63d6d8106660370b6673493291` — the production-based candidate, used as the fix source.

**Not deployed directly**, per the absolute rule.

## 4. Integration Method

**Cherry-pick, `git cherry-pick -n`, then one explicit commit.**

| gate | outcome |
|---|---|
| cherry-pick applicability | **clean, exit 0**, no conflict |
| unrelated history pulled in | **none** — 2 files, both intended |
| current-master behaviour lost | **none** — every other path byte-identical |
| rebase of shared master | **not performed** |
| history rewrite / amend | **none** |

Because the cherry-pick applied cleanly, no equivalent hand-built patch was needed. `-n` was used so the
commit message could describe the master integration accurately rather than repeating the
production-based candidate's message, and so the staged content could be inspected before committing.

**Strongest available correctness evidence:** master's pre-patch `evidence.py` was **byte-identical** to
production's, and the post-patch blobs are **byte-identical to the proven candidate's**:

| file | staged blob | equals candidate `00d835d` |
|---|---|---|
| `evidence.py` | `8e957c0efc2cb41c091ea21745a4d72b008bc9eb` | **True** |
| `test_evidence_record_identity.py` | `bfcefaf9ead11fc20a3c3f809401b745ae526e27` | **True** |

Same input, same output — so the master integration is provably the same artefact that was tested.

## 5. Exact Diff

```
$ git diff --name-status 573a983 a4d5833
M       backend/app/services/mentor/evidence.py
A       backend/tests/test_evidence_record_identity.py

$ git diff --stat 573a983 a4d5833
 backend/app/services/mentor/evidence.py        |  20 ++-
 backend/tests/test_evidence_record_identity.py | 236 +++++++++++++++++++++++++
 2 files changed, 253 insertions(+), 3 deletions(-)
```

Logic change, in full:

```python
+_STUDENT_SCOPE = "__student__"
-    seen_values: set[tuple[str, str]] = set()
+    seen_values: set[tuple[object, str, str]] = set()
-                fingerprint = (chip.label, chip.value)
+                fingerprint = (entry.scholarship_id, chip.label, chip.value)
-        fingerprint = (entry.label, entry.value)
+        fingerprint = (_STUDENT_SCOPE, entry.label, entry.value)
```

(the remainder of the `evidence.py` diff is explanatory comment text)

## 6. Existing Master Changes Preserved

`applications.py` and `main.py` verified **byte-identical** between master and production, confirming the
applications/scholarship routing is untouched. All seven Mentor defect fixes verified present:

| fix | evidence in the integration tree |
|---|---|
| 1 — focused application leads | `groups = [ordered_applications] if focused_application is not None else []` |
| 2 — precision gating | `_EXACT_PRECISION = "exact"`, `def is_exact` |
| 3 — funding vocabulary | `def funding_word`, `def funding_is_unmeasured` |
| 4 — repeated gap once | `unestablished_funding` in `compose.py` |
| 5 — chip basis not duplicated | `return entry.verification \|\| ''` |
| 6 — nav overflow | `flex-wrap: wrap` in `Navigation.css` |
| 7 (`27047de`) — unchecked claims | `compose.py` byte-identical to master/production |

**Scope discipline:** no image, ingestion, scheduler, audit, Match, Count, Applications, Neon or Wave 1–3
file appears in the diff.

## 7. Regression Tests

| gate | result |
|---|---|
| regression suite on the integration tree | **10 passed** |
| **non-vacuity** — file reverted to master's bare version | **5 failed / 5 passed** |
| restored from the proven blob | **10 passed** |
| `test_mentor.py` — master's own file, unmodified | **78 passed** |
| relevant suite (15 files) | **1046 passed, 1 skipped** |
| import smoke | `_STUDENT_SCOPE = __student__` |

A first attempt at the non-vacuity check was **void** — `git stash --keep-index` left the fix in place, so
it reported 10 passed. It was redone properly by checking the file out at `HEAD` and restoring the exact
proven blob afterwards; the 5/5 split above is the real result.

Required assertions:

1. same chip within the **same** record deduplicates — two collapse tests, plus browser `max per record=1`
2. same chip across **different** records independently visible — `twinA=[Application state, Deadline]` **and** `twinB=[Application state, Deadline]`
3. named/focused priority — browser: first chip `id=65` when scholarship 65 was named
4. chip budget works — browser: `items=10` at `limit=10`
5. budget truncation ≠ deduplication — dedicated test: a truncated record keeps a prefix, a suppressed one keeps only its name
6. deadline precision truthful — "About 45 days left. The published date is not recorded to the day…"
7. application evidence correct — 5 applications created and answered from
8. no Mentor context regression — student evidence still appended; master's `test_mentor.py` unmodified and green

## 8. Browser E2E

Real local backend (uvicorn on the integration tree), isolated local SQLite (`int.db`), real HTTP, real
Chromium. Seeded a collision pair `INT Twin Alpha` (64) / `INT Twin Beta` (65), identical in verification,
funding and day count.

| # | check | result |
|---|---|---|
| 1–3 | twin records, identical chips, **both retain their own** | **PASS** — both `[Application state, Deadline]` |
| 4 | focused scholarship prioritised | **PASS** — first chip `id=65` |
| 5 | application context correct | **PASS** — 5 applications |
| 6 | dashboard | **PASS** 200 |
| 7 | applications | **PASS** 200 |
| 8 | scholarships | **PASS** 200 |
| 9 | match | **PASS** 200 |
| 10 | logout/auth | **PASS** — logout 204, then mentor 401 and applications 401 |
| 11 | zero changed-code console errors | **PASS** — see below |
| 12 | responsive | **PASS** — 320px: `wrap=wrap`, `right=277`, no horizontal scroll, 0 interactive overflow, 10 nav links |

Unchanged behaviours re-verified live: deadline precision truthful, unknown deadline stays unknown,
funding `UNKNOWN` unmeasured, same-record duplicates collapse, budget respected.

**Console errors — 14, all attributed, none from the changed code:** 12 ×
`ERR_NAME_NOT_RESOLVED @ https://int{1..4}.example/logo.png` (my own fixtures on the reserved `.example`
TLD) and 2 × `401` on `/api/mentor/message` and `/api/applications` (my own post-logout probes).

### A methodology failure worth recording

The **first** E2E attempt in this task produced false failures — applications returned 404 and every
evidence check failed. Cause: I had stopped the earlier worktree's **vite** but left its **uvicorn** holding
port 8000, so my new backend never bound and the browser silently talked to the *previous* database.
The run was discarded, not reported as a result.

I then added an **identity gate** before trusting any E2E run — asserting
`GET /api/scholarships/64 → 200 "INT Twin Alpha"` — and only re-ran after it passed. Every E2E number in
this report comes from a run where that gate was checked first.

## 9. Build / Lint

| gate | result |
|---|---|
| `npm test` | **163 passed** (9 files) |
| `npm run lint` | **0 errors**, 1 pre-existing `HomePage.jsx` warning |
| `npm run build` | **success** |
| `py_compile` + import smoke | clean |

## 10. Commit SHA

```
a4d5833b4c3e16f41f11fc7b777751c9aff4ee38   integrate/mentor-dedup-onto-master
parent                                       573a983b004ab08578497272659123323ab489b7  (== current master)
```

Verification after committing:

| check | result |
|---|---|
| parent == current master | **True** |
| `573a983` is an ancestor of the integration | **True** (exit 0) — no history rewrite |
| commits master → integration | **exactly 1** — no unrelated commit added or removed |
| diff vs master | 2 files, 253 insertions / 3 deletions |
| integration SHA present on remote | **False** — **not pushed** |
| master on origin | **unchanged** at `573a983` |
| production | **unchanged** at `4edd154` |

Staging was explicit throughout (`git add <two paths>`); `git add .` / `-A` were never used. The local E2E
harness `backend/int_seed.py` was left **untracked** and is not in the commit.

## 11. Deployment Readiness

**GREEN — READY FOR PRODUCTION AUTO-DEPLOY**, subject to one owner action.

The commit is a clean fast-forward of master: pushing `integrate/mentor-dedup-onto-master` to master would
not rewrite anything, because its parent *is* current master.

Evidence: identical artefact to the tested candidate (blob-verified) · 2-file diff · **10 passed** with a
provably non-vacuous test (**5 failed** without the fix) · **1046 backend / 163 frontend** green · lint and
build clean · **17/17 browser E2E** on a real stack with an identity gate.

Owner actions still required, unchanged from earlier phases:
1. **Push** this branch to master (not done here — no authorization in this task).
2. **Confirm the Vercel build limit has reset** before promoting: on 2026-10-04 the account was returning
   *"Deployment rate limited — retry in 24 hours"* on both projects, and every promotion since has had to
   race that limit.
3. **Re-verify master immediately before pushing** — it advanced twice during the previous two phases.

## 12. Remaining Mentor Issues

| issue | classification |
|---|---|
| **M2** — application-scoped evidence cannot expose an official source URL; a `Verified` deadline chip can carry `source_url: None` | **PROVEN**, TRUST/UX HARDENING, **non-blocking**, deferred by instruction |
| **M1** — module docstring still claims "Both require a session. There is no public mentor route" | **PROVEN** documentation defect; excluded from this candidate |
| Vacuity guard for the Mentor fixtures | **PROVEN** absent; production fixtures are currently non-vacuous |
| Chip-basis presentation test (defect 5) | **PROVEN** untested; excluded |
| `evidence.py` still ends without a trailing newline (pre-existing) | **PROVEN**, cosmetic |
| Sibling `self._is_non_logo_stored` `AttributeError` in `--stage images --logo-only` | **PROVEN** dead branch; **arming trap** — never fix the call without also fixing the predicate |
| `maintenance_runs` id 250 stale `status='running'` | **UNKNOWN** whether still active |

**Final classification: GREEN — READY FOR PRODUCTION AUTO-DEPLOY**