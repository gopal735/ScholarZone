# CURRENT_PRODUCTION_MENTOR_HARDENING_FINAL.md

**NOTHING WAS DEPLOYED. NOTHING WAS PUSHED.** No `vercel --prod`, no production deployment, no Neon
writes, no maintenance stage, no image repair or restoration, no Wave 1–3 apply. `master` was not
modified, amended, rebased, or force-pushed. No shared worktree or branch was touched. All work
happened in one throwaway worktree at
`C:\Users\GopaL\AppData\Local\Temp\kilo\rc-mentor-hardening`.

**This is a release candidate only.**

---

## 1. Base SHA

| Item | Value |
|---|---|
| **Base (current production)** | **`3ee434c01f534e2cfd72300030316cdd27c33789`** |
| Base subject | `docs: add the GROUNDed AI Mentor final and security reports` |
| Production parent | `a1f214b` (merge), which follows `c3aefad fix: correct six defects the browser run found in the grounded mentor` |
| Candidate parent | `3ee434c` — **verified equal to the base, not assumed** |

`3ee434c` was confirmed to be a descendant of `c405b49`, `5416914`, `9ff021b` and `3bf92b6`. Current
production therefore already contains Mentor and both image fixes. The earlier `c405b49`-based R1/R2/R3
candidates were **historical and were not used as a base**.

## 2. Release Candidate SHA

| Item | Value |
|---|---|
| **Candidate SHA** | **`00bc39dab3dbb4977b4b36419f301022c4199323`** (`00bc39d`) |
| Branch | `rc/mentor-hardening` (local only) |
| Commits ahead of production | **1** |
| Subject | `fix: scope mentor chip dedup to one record` |
| Worktree state after construction | **PRISTINE** |

## 3. Exact Changed Files

```
 backend/app/services/mentor/evidence.py |  15 ++-
 backend/tests/test_mentor.py            | 167 +++++++++++++++++++++++++++++++-
 2 files changed, 178 insertions(+), 4 deletions(-)
```

| Status | Path |
|---|---|
| `M` | `backend/app/services/mentor/evidence.py` |
| `M` | `backend/tests/test_mentor.py` |

**Nothing else.** Blob comparison against production confirms these are the only two files that
differ.

### The production fix is three functional lines

```diff
-    seen_values: set[tuple[str, str]] = set()
+    seen_values: set[tuple[int | None, str, str]] = set()
...
-                fingerprint = (chip.label, chip.value)
+                fingerprint = (entry.scholarship_id, chip.label, chip.value)
...
-        fingerprint = (entry.label, entry.value)
+        fingerprint = (None, entry.label, entry.value)
```

The fingerprint is now keyed on the **record id**. `ApplicationFacts` already carries
`scholarship_id`, so one scope expression covers both applications and scholarships. `None` scopes
the student's own profile, which no catalogue or workspace row can collide with. The remaining
lines are the comment recording why the scope exists.

## 4. The Regression — Before and After

### Root cause

`collect()` deduplicated evidence chips on a `(label, value)` pair held in a **single set shared by
every record**. Its own comment stated the intent was "the same fact about the **same record**", but
the implementation was global.

Two different scholarships that legitimately share a country, degree, funding line or deadline is
ordinary, not unusual. The second record's chips were dropped as duplicates, so the mentor reported
that record as having almost nothing to say — and because truncation is silent, it read as a
complete answer.

Introduced by `c3aefad`, which shipped in production `3ee434c`.

### Reproduction at the function level

Two records (`101` Alpha, `202` Beta) with identical country, degree, funding and deadline:

| | chips | Funding chips | Deadline chips |
|---|---|---|---|
| **Before** | 5 | **1** | **1** |
| **After** | 8 | **2** | **2** |

Before, record 202 was reduced to a single identity chip:

```
'Scholarship'  = 'Alpha Programme (record 101)'  key=scholarship-101-identity
'Verification' = 'Confirm with provider'         key=scholarship-101-trust
'Deadline'     = '45 days left.'                 key=scholarship-101-deadline
'Funding'      = 'Full tuition and living cost'  key=scholarship-101-funding
'Scholarship'  = 'Beta Programme (record 202)'   key=scholarship-202-identity
```

After, both records keep every chip:

```
'Scholarship'  = 'Alpha Programme (record 101)'  key=scholarship-101-identity
'Verification' = 'Confirm with provider'         key=scholarship-101-trust
'Deadline'     = '45 days left.'                 key=scholarship-101-deadline
'Funding'      = 'Full tuition and living cost'  key=scholarship-101-funding
'Scholarship'  = 'Beta Programme (record 202)'   key=scholarship-202-identity
'Verification' = 'Confirm with provider'         key=scholarship-202-trust
'Deadline'     = '45 days left.'                 key=scholarship-202-deadline
'Funding'      = 'Full tuition and living cost'  key=scholarship-202-funding
```

### Reproduction over real HTTP — the decisive proof

An isolated local SQLite database was seeded with two records (id `64` Alpha, id `65` Beta) sharing
country `Netherlands`, degree `Master`, funding `Full tuition and living cost` and deadline
`2026-11-18`. Both were tracked through the real `POST /applications` endpoint, and the mentor was
asked through the real authenticated `POST /mentor/message`.

**Same database, same request, same HTTP path — only the fix differs:**

| | Chips returned | Deadline chips |
|---|---|---|
| **Before** (production `3ee434c` code) | `Application state`, `Deadline`, `Profile fields` | **1** |
| **After** (candidate `00bc39d`) | `Application state`, `Deadline`, `Application state`, `Deadline`, `Profile fields` | **2** |

Before, `Beta Programme` silently vanished from the evidence. After, both records are represented.

## 5. Proof No Unrelated Changes Are Included

### Forbidden scope — all untouched

| Scope | Result |
|---|---|
| images | **untouched** |
| `do_logos` | **untouched** |
| `scholarzone_maintenance.py` | **untouched** |
| `scholarship_ingestion.py` | **untouched** |
| Match | **untouched** |
| Count | **untouched** |
| Admin Verification | **untouched** |
| Applications | **untouched** |
| scheduler | **untouched** |
| audit | **untouched** |
| Neon | **untouched** |
| Wave 1–3 | **untouched** |

### No later or unreviewed master commits

Exactly **1 commit** ahead of `3ee434c`, and it is this fix. No merges, no cherry-picks of other
work, no stray commits.

### Blast radius

One module, one function, three functional lines. `collect()` is a pure function used only by the
Mentor evidence path. Nothing else imports the changed symbols.

## 6. Test-Vacuity — Root Cause and Closure

### The vacuity that let this ship

The fingerprint dedup was introduced by `c3aefad` and shipped to production with **no test at all**.
Nothing in `test_mentor.py` referenced `collect`, `seen_values`, `fingerprint`, or any notion of a
duplicate — verified by search across the whole file. The feature's only exercise was an incidental
browser run, which is why a global set scoping a per-record intent survived review.

The new `TestChipDedupScope` closes that gap by calling `collect()` directly.

### A second, latent vacuity — reported, not fixed here

`TestEvidenceBudget::test_application_evidence_reports_measured_progress` wraps its entire body in
`if detail.get("progress_percent") is not None:`. I tested whether that branch is currently dead by
poisoning the guarded assertion: the test **failed**, so the branch executes today and the test is
not vacuous *right now*. It is nonetheless **conditionally vacuous** — if `progress_percent` ever
becomes `None`, the test silently asserts nothing and still passes.

That is outside the scope of this regression and is left untouched rather than bundled into a release
candidate. **Flagged for a separate change.**

## 7. Tests

### New regression tests

Five tests in `TestChipDedupScope`, each covering one requirement:

| Test | Requirement | Result |
|---|---|---|
| `test_the_same_label_and_value_on_different_records_both_survive` | **Req 3** — cross-record must not suppress | pass |
| `test_a_repeat_inside_one_record_is_still_collapsed` | **Req 4** — within-record suppression preserved | pass |
| `test_a_record_repeating_itself_is_not_double_counted` | **Req 4** — same record folded onto the first | pass |
| `test_the_focused_record_still_leads_and_keeps_its_chips` | **Req 5** — named/focused priority intact | pass |
| `test_the_chip_budget_and_order_are_unchanged` | **Req 6** — budget and order intact at limits 1/3/5/10 | pass |

### Proof the tests are not vacuous

The fix was reverted and the new tests re-run:

| | Result |
|---|---|
| Against unfixed code | **2 failed** — `..._on_different_records_both_survive`, `test_the_chip_budget_and_order_are_unchanged` |
| Against fixed code | **5 passed** |

This is the correct signature. The two cross-record tests fail without the fix; the three
within-record tests pass either way, because that behaviour is deliberately unchanged by it.

### Full suites

| Suite | Result |
|---|---|
| **Mentor backend** (`tests/test_mentor.py`) | **82 passed** |
| **Full backend** (`pytest tests`) | **4978 passed, 1 failed, 11 skipped** |
| **Frontend** (`vitest run`) | **163 passed** (9 files) |
| **Frontend build** (`vite build`) | **succeeded** (445ms) |
| **Frontend lint** (`eslint .`) | **0 errors**, 1 pre-existing warning |

The single backend failure is `tests/test_efficiency_safety.py::TestRetryPolicy::test_the_retry_shares_the_concurrency_group`,
which is **pre-existing on production** and is unrelated to this change.

`test_neon_migration.py` requires the untracked `backend/migration_export.sql`, which does not travel
with a worktree; it was supplied for the run and passed. Not a code defect and not present in CI.

**No test was weakened, deleted, skipped, or excluded to reach a green result.**

## 8. Browser E2E

Real Chromium via Playwright against a locally served production build backed by the candidate's own
backend on `127.0.0.1:8000` with an isolated local SQLite database.

| Check | Result |
|---|---|
| `/ScholarZone/mentor` | Renders — `h1` "Mentor", Mentor link in nav |
| **Console errors** | **0** |
| `/ScholarZone/` , `/scholarships`, `/match`, `/dashboard`, `/applications` | HTTP 200, all render |
| `/api/health` | HTTP 200 |
| `/api/mentor/overview` | HTTP 200, 784 bytes |
| `/api/scholarships?limit=5` | HTTP 200 |
| `/api/scholarships/stats` | HTTP 200 |
| `/api/dashboard/`, `/api/applications/` | HTTP 401 — auth gate working, expected when signed out |

### Regression surfaces healthy

| Surface | Result |
|---|---|
| **dashboard** | Renders `h1` "Your dashboard" + sign-in gate; one expected 401 |
| **applications** | Renders `h1` "Your applications" + sign-in gate; one expected 401 |
| **scholarships** | Renders `h1` "All Scholarships", card grid intact |
| **match** | Renders, `title: Match · ScholarZone` |
| **mentor** | Renders, 0 console errors |

### Layout and accessibility

| Check | Result |
|---|---|
| Viewport | 320 × 800 (narrowest tested) |
| Horizontal overflow | **0 px** — no horizontal scrollbar |
| Landmarks | `banner`, `main`, `contentinfo` all present |
| Navigation | 10 links, labelled `Primary navigation` |
| Heading structure | one `h1` per page |

The inherited `"Applications: undefined"` accessible-name nit noted in the earlier release work is
still present and is still **not introduced by this change**.

## 9. Summary Table

| Field | Value |
|---|---|
| Base SHA | `3ee434c01f534e2cfd72300030316cdd27c33789` |
| **Candidate SHA** | **`00bc39dab3dbb4977b4b36419f301022c4199323`** |
| Commits ahead | 1 |
| Changed files | 2 — `evidence.py` (+15/−4), `test_mentor.py` (+167) |
| Regression before | 1 Deadline chip for 2 records; 5 chips total |
| Regression after | 2 Deadline chips for 2 records; 8 chips total |
| Mentor tests | 82 passed |
| Full backend | 4978 passed, 1 pre-existing failure |
| Frontend | 163 passed, build clean, lint 0 errors |
| Browser E2E | 0 console errors, 0 px overflow at 320px |
| Unrelated changes | **none** |
| Worktree | **PRISTINE** |
| Pushed / deployed | **NO / NO** |

## 10. Production Deployment Recommendation

**Recommended: deploy, after normal review.** This candidate is a genuine fast-forward — its parent
is exactly the current production SHA, so it needs no combine commit and no rebase.

**Strengths**

- Fixes a **proven** user-visible regression with before/after evidence at both function level and
  over real HTTP.
- **Three functional lines** in one pure function; blast radius is the Mentor evidence path only.
- Behaviour it must preserve is **verified, not assumed**: within-record suppression, focused-record
  priority, and chip budget/order each have a dedicated test.
- Closes a **test-vacuity** that is the reason the defect shipped.
- Touches none of images, `do_logos`, ingestion, Match, Count, Admin, Applications, scheduler, audit
  or Wave 1–3.

**Residual risks — all acceptable, none blocking**

| Risk | Note |
|---|---|
| Chip counts rise for multi-record answers | Intended. Answers become more complete; the budget still truncates and the response still declares `known`/`unknown`. If the UI had tuned itself to the shorter lists it may look fuller — a visual change, not a wrong one |
| `test_efficiency_safety` failure persists | Pre-existing on production; unrelated; not fixed here |
| `"Applications: undefined"` a11y nit persists | Pre-existing; out of scope; not introduced here |
| `test_application_evidence_reports_measured_progress` is conditionally vacuous | Pre-existing latent fragility; **flagged for a separate change**, deliberately not bundled here |
| Local-only verification | Nothing has been deployed or observed in production |

**Suggested sequence if deploying:** deploy `00bc39d` alone. Read `/health` for the revision, confirm
the Mentor answers a multi-record question citing **each** record, and re-measure public and storage
counts. **Read-only checks only — run no maintenance stage.**

**Not claimed:** that this has been deployed; that production is verified; that the October 3 root
cause is solved (Phase 6 remains **CASE E / NOT OBSERVED**).