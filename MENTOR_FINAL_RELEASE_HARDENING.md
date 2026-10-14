# MENTOR_FINAL_RELEASE_HARDENING.md

**Task:** Mentor final pre-release hardening — no production deployment
**Date:** 2026-10-04
**Branch:** `mentor/hardening-3bf92b6` (isolated) · **commit `0118703`** · **base `3bf92b6`**

Tags: **[OBSERVED FACT]** measured · **[PROVEN]** direct evidence · **[DISPROVEN]** contradicts an
assumption · **[PLAUSIBLE BUT UNPROVEN]** · **[UNKNOWN]**

---

## 1. Approved Release SHA

| Item | Value |
|---|---|
| Approved release boundary | **`3bf92b6`** — unchanged, not rewritten |
| Hardening commit | **`0118703`**, parent `3bf92b6`, 1 commit ahead |
| Branch | `mentor/hardening-3bf92b6` — **isolated, not merged, not pushed** |
| `origin/master` at time of writing | `573a983` — advanced again by the other actor |
| Production Vercel | `c405b49` — **unchanged** |

**[PROVEN]** `a1f214b` and the newer master tips were **not** merged, not deployed, and not used as a
base. The hardening sits directly on the approved boundary.

## 2. M1 Contract Decision — **Option A: intentionally public**

I inspected how the frontend actually uses the endpoint before deciding, as instructed.

| Evidence | Source |
|---|---|
| *"The vocabulary the mentor understands. **Public: it contains no account data.**"* | `mentorService.js:140` |
| *"The overview is only a list of suggestions, so failing to load it must not block the page"* | `MentorPage.jsx:77` |
| *"Safe to call before sign-in: it contains only vocabulary, so it cannot leak anything about an account. That is also why the private surfaces still require a session - this route has nothing private on it to protect."* | `routers/mentor.py` `read_overview` |
| `read_overview()` takes **no** `db`, **no** `user`, **no** `Depends` — it structurally cannot read an account | `routers/mentor.py:128-129` |
| Payload byte-identical for two different users and after logout; only `supported_intents`, `intents`, `redirects`, `max_message_length`, `assistance_available` | measured |

**[PROVEN] The conflict was internal to one file.** The module docstring said *"Both require a
session. There is no public mentor route"*; the handler's own docstring said the opposite. The
implementation and both the frontend and handler docstrings agree the route is public.

**Decision: Option A.** The implementation was correct and the documentation was wrong. I corrected
the module docstring rather than adding `require_user` — locking the route down would buy no privacy
(it reads no account) and would break the signed-out composer the interface depends on. **A security
change was not made to satisfy a docstring.**

Regression tests now *prove* the payload is account-invariant and contain no id-bearing key, and that
the private route still refuses an anonymous caller.

## 3. M2 Evidence Decision

### What was proven

`ApplicationFacts` had **no** `official_source_url`, so `evidence.py` emitted an application deadline
with `verification=item.verification_label` and **no** `source_url` — a "Verified" claim with nothing
behind it. **[PROVEN]**

### Smallest safe change

1. **`ApplicationFacts.official_source_url`** added, default `None`.
2. Populated from the canonical row in `_applications_for`, where `row` was **already in scope** —
   **no new query, no invented URL, no duplicated data.**
3. **Dashboard path:** `ApplicationItem` carries no official page, and Application Workspace is
   forbidden to change. Resolved with `_official_source_urls()` — **one read of
   `Scholarship.official_source_url` keyed by id**, mentor-local. This is what stops the general path
   from silently losing both the link and the label the named path gets.
4. **Withholding rule:** where no source exists, the verification label is dropped. The figure still
   renders; it simply stops claiming a backing it does not have.
5. **Privacy preserved:** the URL is the scholarship's own public official page, already exposed on
   public endpoints. No user data, no cross-user exposure.

### Requirement-by-requirement

| Requirement | Status |
|---|---|
| Source from canonical scholarship data | **MET** — copied from `row.official_source_url` |
| Do not invent URL | **MET** — `None` stays `None`; test asserts it |
| Do not duplicate unrelated data | **MET** — one scalar per facts object |
| Do not weaken privacy | **MET** — public page only; isolation tested |
| Preserve user isolation | **MET** — second user sees nothing; browser-verified |
| UNKNOWN deadline stays UNKNOWN | **MET** — `test_an_unknown_deadline_stays_unknown` |
| Month precision stays month precision | **MET** — `test_month_precision_is_not_promoted_to_a_day` |
| Source-less claims not labelled fully verified | **MET** — `_sourced_verification`, asserted across every returned item |

## 4. Additional Mentor Findings

**M3-a — three more source-less verified claims.** A scan of `evidence.py` for items carrying
`verification` without `source_url` found four, not one: scholarship `eligibility` (L128), `fit`
(L141), `readiness` (L155) and application `deadline`. All four are the same trust defect, all small,
all within Mentor. **All four fixed.**

**M3-b — the Mentor UI never rendered `source_url` at all.** The field existed in the API schema and
was populated by `scholarship_evidence`, but `MentorAnswer.jsx` only linked to the internal
scholarship page. M2 would have been half-delivered without this. Each evidence item now links to its
official page, `target="_blank"` with `rel="noreferrer noopener"`, and renders **nothing** when there
is no source.

**Left alone deliberately:** the duplicate headline (`headline` and `why` carry identical text).
Cosmetic, pre-existing, and fixing it would be redesign rather than hardening.

## 5. Exact Changes

`0118703` — 6 files, +556 / −22

| File | Change |
|---|---|
| `backend/app/routers/mentor.py` | +23/−7 — module docstring corrected to state the real contract and why |
| `backend/app/services/mentor/context.py` | +51 — `official_source_url` on `ApplicationFacts`; populated row-backed; `_official_source_urls()` for the dashboard path |
| `backend/app/services/mentor/evidence.py` | +36 — `_sourced_verification()`; `source_url` on the application deadline; eligibility/fit/readiness sourced and gated |
| `backend/tests/test_mentor_hardening.py` | +379 — new, 24 tests |
| `frontend/src/components/mentor/MentorAnswer.jsx` | +17 — official source link per evidence item |
| `frontend/src/pages/MentorPage.test.jsx` | +48 — 2 new tests (**purely additive; verified with `git diff -w`: no existing test weakened**) |

**Not touched:** `do_logos`, ingestion, scheduler, audit, Match, Count, Application Workspace,
Neon, Wave 1–3, images.

## 6. Backend Tests

| Suite | Result |
|---|---|
| `test_mentor.py` + `test_mentor_hardening.py` | **91 passed** (24 new) |
| mentor + application workspace + student dashboard + 3 evidence suites | **300 passed** |
| **Full backend** | **4982 passed, 8 failed, 11 skipped, 1 error** |

**[PROVEN] No new failures.** The 8 failures are all `test_neon_migration.py` and the 1 error is
`artifact_smoke_test.py::test_endpoint` — the established environmental baseline (they assert on a
Neon migration SQL file absent from the repository). Identical to the previously proven baseline.

## 7. Frontend Tests

| Suite | Result |
|---|---|
| `MentorPage.test.jsx` | **30 passed** (28 existing + 2 new) |
| `mentorService.test.js` + `mentorPresentation.test.js` | **51 passed** |
| **Full frontend** | **165 passed / 9 files** |
| lint | **exit 0** — 0 errors, 1 pre-existing warning (`HomePage.jsx:252`) |
| build | **exit 0** — `built in 419ms` |

## 8. Browser E2E — **22/22 passed**

Real uvicorn (`app.main:app`) + real vite + real Chromium + isolated SQLite. No production contact.

Isolation proven by `GET /api/scholarships/1` returning the seeded `Gates Cambridge Scholarship`.

| # | Check | Result |
|---|---|---|
| 1 | login + session | PASS |
| 2 | Mentor opens | PASS |
| 3 | verified scholarship fact rendered | PASS |
| 4 | **official source link rendered** | PASS — 9 links, all `https://`, `target=_blank`, `rel=noreferrer noopener` |
| 5 | unknown deadline stated | PASS |
| 6 | application context | PASS — `application-2-deadline`, `Verified`, `source_url=https://www.gatescambridge.org/apply/` |
| 6d | **no verified claim without a source** | PASS — 0 offenders |
| 7 | logout blocks private routes | PASS — 401 / 401 |
| 8 | private route 401 anonymous; **overview public** | PASS — 401 / 200 |
| 9 | second-user isolation | PASS — 0 saved, no leakage |
| 10–13 | Dashboard, Applications, Scholarships, Match | PASS |
| 14 | zero unexpected console errors | PASS |
| 15 | responsive 360/768/1440 | PASS — no overflow |

## 9. Privacy/Security

| Property | Status |
|---|---|
| Overview leaks account data | **NO** — proven account-invariant across two users and post-logout |
| New leak introduced | **NO** — only the scholarship's own public official page, already public elsewhere |
| Private route still protected | **YES** — `POST /mentor/message` 401 anonymous and after logout |
| Cross-user leakage | **NO** — browser-verified |
| Verified claims auditable | **YES** — every `Verified` item now carries an openable source |
| Unsourced claims downgraded, not hidden | **YES** — figure still shown, label withheld |
| URL invented anywhere | **NO** — `None` remains `None`, asserted by test |

## 10. Release Boundary

```
c405b49 (production)
  └─ 5416914  Mentor
  └─ 9ff021b  do_logos fix
  └─ 3bf92b6  ingestion fix          <- approved boundary
       └─ 0118703  Mentor hardening  <- this work, isolated branch
```

**[PROVEN]** `0118703` is a single commit on top of `3bf92b6`. `a1f214b`, `573a983` and every other
concurrent master tip are **excluded**. Master history untouched; no force push, no amend, no reset,
no `git add .`/`-A`.

**[UNKNOWN]** Whether `0118703` should be merged into master or deployed directly is an owner
decision — merging would pull in whatever master has become since, which is exactly what this task
said not to do.

## 11. Vercel Deployment Preconditions

| # | Precondition | Status |
|---|---|---|
| 1 | Vercel quota reset | **PENDING** — 2026-10-05 10:21:57Z |
| 2 | Deploy a known SHA, no bypass | available after 1 |
| 3 | CI green on the deploy SHA | **NOT RUN** — `0118703` is unpushed by design |
| 4 | Mentor local gate | **MET** — 22/22 |
| 5 | Backend + frontend suites | **MET** — 4982 + 165 |
| 6 | Lint + build | **MET** |
| 7 | Release boundary explicit | **MET** — `3bf92b6` + `0118703` |
| 8 | Owner decision: merge vs direct deploy of `0118703` | **OUTSTANDING** |

## 12. Final Mentor Status

# GREEN

Both contracts are now correct and each is enforced by a test that would fail if it regressed:

* **M1** — the overview is public **by decision and by documentation**, with the payload proven to
  carry no account data, and the private route proven to refuse anonymous callers.
* **M2** — every claim Mentor labels `Verified` now carries the scholarship's own official page, and
  a claim with no page behind it is downgraded instead of asserted.

Both changes **make the system more truthful rather than more locked down**, which is the correct
direction for a grounded advisor: the previous behaviour was a stronger claim with weaker support.

**No deployment occurred.** Nothing was pushed, merged, or dispatched. No production data was read
or written. No image system, Wave 1–3, scheduler, audit, Match, Count, or Application Workspace was
touched. Master history is unchanged.