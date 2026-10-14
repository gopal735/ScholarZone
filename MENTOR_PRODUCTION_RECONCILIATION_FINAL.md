# MENTOR_PRODUCTION_RECONCILIATION_FINAL.md

**Task:** reconcile Mentor hardening `0118703` against current production `4edd154`
**Mode:** DEBUG — read-only first, no deployment, no master merge
**Date:** 2026-10-04

Tags: **[OBSERVED FACT]** measured · **[PROVEN]** direct evidence · **[DISPROVEN]** contradicts an
assumption · **[PLAUSIBLE BUT UNPROVEN]** · **[UNKNOWN]**

---

## 1. Current Production Revision

| Item | Value |
|---|---|
| Production revision | **`4edd154a3037`** (`/api/health`, `status: ok`) |
| `origin/master` HEAD | `573a983` |
| Ancestry | `4edd154` **is** an ancestor of `origin/master` — production is **2 commits behind** |
| Net diff production → master | **2 files**, both unrelated docs: `GROUNDed_AI_MENTOR_1_FINAL.md`, `GROUNDed_AI_MENTOR_SECURITY_FINAL.md` |
| Mentor code changed between production and master | **NONE** |

**[PROVEN]** I earlier reported master as "79 commits" ahead of production. **That was a bug in my
own script** (a mis-captured variable). Verified twice since — `git rev-list --count` returns **2**, and
the net file diff is **2**. Corrected figure used throughout.

**[PROVEN]** `origin/master` already contains `5416914`, `9ff021b` and `3bf92b6`. It does **not**
contain `0118703`.

## 2. 0118703 Change Inventory

Seven distinct changes. Status against production `4edd154`:

| # | Change | In production? |
|---|---|---|
| M1-a | `routers/mentor.py` module docstring corrected (overview is public) | **ABSENT** |
| M1-b | `/mentor/overview` behaviour | already public and static — **no change needed** |
| M2-a | `ApplicationFacts.official_source_url` field | **ABSENT** |
| M2-b | Application deadline evidence carries `source_url` | **ABSENT** |
| M2-c | Scholarship `eligibility` evidence carries `source_url` | **ABSENT** |
| M2-d | Scholarship `fit` evidence carries `source_url` | **ABSENT** |
| M2-e | Scholarship `readiness` evidence carries `source_url` | **ABSENT** |
| M2-f | "Verified" withheld when no source exists | **ABSENT** |
| M3 | `MentorAnswer.jsx` renders the official-source link | **ABSENT** |

**[PROVEN]** Production's `evidence.py` still reads
`verification=item.verification_label if item.is_listed else None` with no `source_url` on the
application deadline, and `verification=verification` with no `source_url` on eligibility/fit/readiness.

## 3. Already-Live Changes

**M1-b only.** `[PROVEN]` production's `/mentor/overview` is already public and already returns only
static capability metadata — `supported_intents`, `intents`, `redirects`, `max_message_length`,
`assistance_available`, 11 intents, no id-bearing key.

So the *runtime* contract `0118703` documented was already true in production. Only the **documentation**
was wrong. That is why M1 required no behavioural change.

## 4. Missing Changes

All eight code changes above. **[PROVEN]** absent from production and from master.

## 5. Superseded / Conflicting Changes

**[PROVEN] This is the finding that changes the answer.** Production is **ahead** of the hardening's
base (`0118703~1` = `3bf92b6`) on Mentor quality:

| Symbol | Production `4edd154` | Hardening base `3bf92b6` |
|---|---|---|
| `_FUNDING_WORDS` / `_funding_word` | **present** | absent |
| `_EXACT_PRECISION` / `is_exact` | **present** | absent |
| `collect()` de-duplication of identical `(label, value)` | **present** | absent |
| Focused-application prioritisation in `collect()` | **present** | absent |

Net: production carries **+131 / −32** across `compose.py`, `context.py`, `evidence.py` that the
hardening branch does not have.

**[PROVEN] A blind cherry-pick of `0118703` onto production would have been wrong.** Two of its six
files (`context.py`, `evidence.py`) differ between production and its parent, so the patch does not
apply to the code it was written against. The hardening was therefore **re-derived against
production's newer code** rather than transplanted.

**No supersession of the hardening itself.** None of the eight missing changes exists in production in
any form. **No conflict** either — production's newer work is orthogonal (funding wording, precision
model, evidence ordering) and is preserved untouched.

## 6. Production Runtime Verification (read-only)

No account created, nothing mutated. The only write-shaped call was `POST /mentor/message` **without
a session**, which the guard rejects before any handler body runs.

| Check | Result |
|---|---|
| `/api/health` | **200**, `status: ok`, `revision 4edd154a3037` |
| `/api/mentor/overview` | **200** — public, 11 intents, static keys only, no account token |
| `/api/mentor/message` unauthenticated | **401** |
| `/api/mentor/overview` contains any id/email/scholarship token | **none** |

**[PROVEN] Authenticated production verification is impossible without a write** (it needs an
account with saved scholarships and an application). Per instruction, that is documented rather than
forced. It is substituted two ways:

1. **Source-level:** production runs exactly `4edd154`, and that commit's source demonstrably lacks the
   hardening — this is stronger than a probe, because it is the code itself.
2. **Local identical-code:** the candidate runs production's code plus only the hardening, verified
   with real HTTP (§10).

**[OBSERVED FACT]** Production `/openapi.json` returns an effectively empty document (1 path, no
title), so schema introspection is not available there. Behavioural probes were used instead.

## 7. Current Master Comparison

```
4edd154  (production)
   └─ 84d9d7e, 573a983   (2 doc-only commits)
573a983  (master)

0118703 ── parent 3bf92b6   (separate line; 0118703 not in master)
ef074a5 ── parent 4edd154   (candidate: production + hardening)
```

**[PROVEN]** `0118703` is not an ancestor of master or production. Master contains the three approved
fixes but not the hardening. Master and production differ only by 2 unrelated documents.

## 8. Exact Release Candidate

```
BASE:                4edd154          (current production, unmodified)
+
EXACT HARDENING:     re-derived minimal equivalent of 0118703
                     6 files, +579 / -14
=
RELEASE CANDIDATE:   ef074a57757bc419d5ca203b921f7aa374b06276
                     branch: release/mentor-hardening-on-4edd154 (local only)
```

**[PROVEN]** Exactly 6 files differ from production, all Mentor:

| File | Change |
|---|---|
| `backend/app/routers/mentor.py` | M1 docstring corrected |
| `backend/app/services/mentor/context.py` | `official_source_url` field + row-backed population + `_official_source_urls()` for the dashboard path |
| `backend/app/services/mentor/evidence.py` | `_sourced_verification()` + `source_url` on application deadline, eligibility, fit, readiness |
| `backend/tests/test_mentor_hardening.py` | new — 25 tests |
| `frontend/src/components/mentor/MentorAnswer.jsx` | official-source link per evidence item |
| `frontend/src/pages/MentorPage.test.jsx` | +2 tests (appended, purely additive) |

**[PROVEN]** The candidate does **not** include master's 2 unrelated documents, and includes nothing
else from master.

## 9. Tests

| Suite | Result |
|---|---|
| `test_mentor_hardening.py` | **25 passed** |
| mentor + application workspace + student dashboard + 3 evidence suites | **312 passed**, 0 failed |
| Full frontend | **165 passed / 9 files** |
| Frontend lint | **exit 0** — 0 errors, 1 pre-existing warning |
| Frontend build | **exit 0** — 568ms |

**[PROVEN] Production's newer semantics are preserved in the candidate:** `_FUNDING_WORDS` and
`_funding_word` still in `evidence.py`; `_EXACT_PRECISION` and `is_exact` still in `context.py`.

**[PROVEN] One test was corrected rather than the code.** My ported test asserted an application's
deadline always appears in the general answer. Production's `collect()` deliberately collapses an
identical `(label, value)` pair onto the first basis that reported it, so when the application's
deadline repeats the scholarship's own figure it is suppressed. That is intended
record-scoped-chip behaviour. **I changed the test, not the de-duplication**, and added a named-
application test that proves the sourced item does appear when it leads.

## 10. Browser E2E — **19/19 passed**

Real uvicorn + real vite + real Chromium + isolated SQLite, running the candidate. No production data.

| Check | Result |
|---|---|
| M1 private route 401 anonymous | PASS |
| M1 overview public | PASS |
| login + session | PASS |
| Mentor opens | PASS |
| verified fact rendered | PASS |
| unknown deadline truthful | PASS |
| official source link rendered | PASS — 6 links, all `https://`, `_blank`, `noreferrer noopener` |
| **no Verified claim without a source, across 5 intents** | **PASS — 0 offenders** (18 verified claims, 18 sourced) |
| funding wording humanised (`_FUNDING_WORDS` kept) | PASS |
| second-user isolation | PASS — 0 saved, no leakage |
| Dashboard / Applications / Scholarships / Match | PASS |
| zero unexpected console errors | PASS |
| responsive 360/768/1440 | PASS |
| logout blocks private, overview stays public | PASS |

## 11. Production Deployment Plan

**Not executed.** No deployment, no push, no merge.

1. **Push the candidate branch** and open a PR against `master`. Do **not** merge `0118703`.
2. **Wait for the Vercel quota** — resets **2026-10-05 10:21:57Z**. **[PROVEN]** still exhausted: no
   deployment has been produced since `4edd154`; the daily API allowance was consumed.
3. **Merge the PR to `master`** so the Git integration produces the deployment. Do **not** deploy the
   branch directly: a non-default branch yields a **preview**, not production, and the absolute rule
   forbids that.
4. **Post-deploy read-only verification:** `/api/health` revision; `/api/mentor/overview` still 200 and
   account-invariant; `/api/mentor/message` 401 anonymous; no `Verified` evidence without a source;
   no public-count or storage change.

## 12. Final Recommendation

# `NEEDS_HARDENING`

**[PROVEN]** The hardening is **missing** from production — all eight code changes — but production
already behaves correctly on the one contract that mattered at runtime (the public, static overview),
so nothing is presently broken or leaking.

**[PROVEN]** `0118703` must **not** be applied as-is. Production has moved ahead of its base on
Mentor, and two of its six files no longer match. The correct artefact is the re-derived candidate
**`ef074a5`** on base **`4edd154`** — production plus the minimal equivalent hardening, with
production's newer funding, precision and evidence-ordering work fully preserved.

**Recommended path:** push `release/mentor-hardening-on-4edd154`, PR it to `master`, merge after the
quota resets, then verify read-only. The old branch `mentor/hardening-3bf92b6` (`0118703`) can be
discarded once the candidate lands.

**[UNKNOWN]** Whether to ship this together with anything else currently on master. Master's only
other content is 2 documentation files, so that question is nearly moot.

**No deployment occurred.** Nothing was pushed, merged, or dispatched. No production data was read or
written, no account created. No image, ingestion, scheduler, audit or Wave 1–3 system was touched.
Master history is unchanged. Both branches remain local only.