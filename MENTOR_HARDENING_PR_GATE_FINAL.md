# MENTOR_HARDENING_PR_GATE_FINAL.md

**Task:** prepare the Mentor hardening for a safe PR into current master
**Date:** 2026-10-04
**PR:** **#1** — https://github.com/gopal735/ScholarZone/pull/1 (OPEN, MERGEABLE)
**No deployment. No merge. Master not rewritten.**

Tags: **[OBSERVED FACT]** measured · **[PROVEN]** direct evidence · **[DISPROVEN]** contradicts an
assumption · **[UNKNOWN]**

---

## 1. Current Production

| Item | Value |
|---|---|
| Production revision | **`4edd154a3037`** (`/api/health`, `status: ok`) |
| Unchanged by this task | **[OBSERVED FACT]** identical before and after |

## 2. Current Master

| Item | Value |
|---|---|
| `origin/master` HEAD | **`573a983b004ab08578497272659123323ab489b7`** |
| Commits after production | **2** |
| Those commits | `84d9d7e` docs: correct the commit list in the final report header · `573a983` docs: the wording fix is deployed and verified in production |
| Files they change | `GROUNDed_AI_MENTOR_1_FINAL.md`, `GROUNDed_AI_MENTOR_SECURITY_FINAL.md` (+8 / −8) |
| **Mentor files changed on master since production** | **NONE** |

**[PROVEN]** Master and production diverged from `4edd154`. Master is 2 documentation commits ahead.
**No Mentor code has changed on master since the candidate was authored.**

## 3. Candidate ef074a5

`ef074a5` was built on `4edd154` (production), because the original `0118703` was based on `3bf92b6`
— an older Mentor tree.

**[PROVEN] `ef074a5` is NOT suitable as a PR head.** Master and candidate diverged with **zero file
overlap**, so no conflict is possible, but merging the candidate as-is would have **reverted master's
two documentation commits** — a violation of the "do not remove unrelated commits" rule.

## 4. Master / Candidate Difference

| | |
|---|---|
| merge-base(candidate, master) | `4edd154` |
| Files both changed | **none** — zero overlap |
| Candidate-only (absent from master) | all 6 Mentor files |
| Master-only (must be preserved) | the 2 doc files |
| `git diff master ef074a5` | **8 files** — 6 Mentor + **2 doc reverts** ← unacceptable |

## 5. Exact Required Hardening

Classification of every change, reviewed line-by-line:

| File | Change | Classification |
|---|---|---|
| `routers/mentor.py` | Module docstring: overview is *intentionally* public; no db/user/Depends so it cannot read an account; tests pin both halves | **M1 documentation correction** — zero code change |
| `services/mentor/context.py` | `ApplicationFacts.official_source_url` field | **required M2** |
| `services/mentor/context.py` | populate from the canonical row in `_applications_for` (row already in scope — **no new query**) | **required M2** |
| `services/mentor/context.py` | `_official_source_urls()` + wiring for the dashboard path | **necessary supporting refactor** — `ApplicationItem` has no page and Application Workspace is out of scope |
| `services/mentor/evidence.py` | `_sourced_verification()` helper | **required M2** |
| `services/mentor/evidence.py` | `source_url` + gating on application deadline | **required M2** |
| `services/mentor/evidence.py` | `source_url` + gating on eligibility / fit / readiness | **required M2** (found by audit, not in the original brief) |
| `components/mentor/MentorAnswer.jsx` | official-source link per chip, `_blank` + `noreferrer noopener`, renders nothing when absent | **required M3** — the API field existed but the UI never rendered it |
| `tests/test_mentor_hardening.py` | 25 new tests | **test strengthening** |
| `MentorPage.test.jsx` | +2 tests, **0 lines removed** (`git diff -w` verified) | **test strengthening** |
| — | **unnecessary changes** | **none** — one instance found and removed (see §9) |
| — | **risky changes** | **none** |

## 6. Preserved Production Behavior

**[PROVEN]** verified present in the final candidate:

| Behaviour | Status |
|---|---|
| `27047de` ("stop asserting a claim it never checked") | **safe** — the candidate does not touch `compose.py` |
| funding-word logic (`_FUNDING_WORDS`, `_funding_word`) | present |
| exact/month/unknown deadline semantics (`_EXACT_PRECISION`, `is_exact`) | present |
| record-scoped chip dedup (`seen_values`) | present |
| focused application prioritisation (`focused_application`) | present |

## 7. Test Results

| Gate | Result |
|---|---|
| Backend: mentor, evidence, arbitration, confidence, scholarship evidence, workspace, dashboard | **312 passed**, 0 failed |
| `test_mentor_hardening.py` | **25 passed** |
| Source-less / unsourced / verified subset | **6 passed** |
| Frontend full suite | **165 passed** / 9 files |
| Frontend lint | **exit 0** — 0 errors, 1 pre-existing warning |
| Frontend build | **exit 0** — 259ms |

### Source-evidence contract (STEP 4)

Static audit of every verification-bearing `EvidenceItem`: **all six claim types** — deadline,
eligibility, fit, readiness, application evidence, funding — either carry `source_url` or are gated
on it. The single item without a source (`application-state`) asserts `verification = None`, so it
can never claim "Verified".

Runtime proof on a real backend:

| Property | Result |
|---|---|
| Emitted URL == stored canonical URL | **18 checked, 0 mismatches — no fabrication** |
| `Verified` claims without a source, across 8 intents | **30 Verified, 0 unsourced** |
| Genuinely source-less record labelled `Verified` | **0** (rule proven by unit test) |

## 8. Browser E2E

Real uvicorn + real vite + real Chromium + isolated SQLite. **21/22 passed.**

Passing: overview public / message 401 anonymous · login · exact-day countdown · unknown deadline
stays unknown · source links rendered and canonical https · funding humanised · **record-scoped chip
dedup (0 duplicates)** · **named application leads the evidence** · cross-user isolation ·
Dashboard/Applications/Scholarships/Match · zero unexpected console errors · responsive
360/768/1440 · logout blocks private while overview stays public.

**The one failure was my assertion, not the code.** I seeded a fixture whose *stored*
`official_source_url` was `placeholder.invalid` and then asserted no placeholder URLs appeared.
Mentor echoed the stored value faithfully — correct behaviour. I replaced that check with the real
property (emitted == stored), which passed 18/18.

**[PROVEN] One check was vacuous and is reported as such:** the browser-level "source-less record"
case produced no evidence items, because that record surfaces nothing. The downgrading rule is proven
non-vacuously by `test_a_source_less_deadline_is_not_labelled_verified`, which asserts
`verification is None` directly.

## 9. PR Safety

**[PROVEN]** `ef074a5` was **not** used as the PR head. A fresh candidate was built from **current
master** and the hardening cherry-picked onto it:

```
origin/master 573a983  +  cherry-pick ef074a5  =  13e9765
```

**[PROVEN]** `13e9765` is a **direct child of `573a983`** — a clean single-commit PR. Diff vs master
is **exactly 6 files**, +576 / −11.

**[PROVEN]** Master's two documentation commits are **untouched**: neither appears in the PR diff.

**[PROVEN]** I found and removed one piece of **unnecessary churn** during review — my earlier
cherry-pick had re-indented three existing lines in `MentorAnswer.jsx`. After the fix the diff for
that file is **purely additive, 0 lines removed**.

**[PROVEN]** No unrelated work is included. No image, ingestion, scheduler, audit, Match, Count or
Wave 1–3 file appears in the PR.

## 10. Final Candidate SHA

| | |
|---|---|
| **Base** | `573a983` (current `origin/master`) |
| **Final candidate** | **`13e9765`** |
| Branch | `release/mentor-hardening-pr` (pushed) |
| PR | **#1** → `master`, OPEN, MERGEABLE |
| Changed files | 6 |
| Diffstat | +576 / −11 |
| Hardening scope | source-evidence contract (M2) + docstring correction (M1) + UI link (M3) + tests |

```
CURRENT MASTER
  573a983  (2 unrelated doc commits, preserved)
    +
ONLY REQUIRED MENTOR HARDENING
    13e9765  =  6 files, +576 / -11
```

## 11. Merge Recommendation

# `READY_FOR_PR`

**[PROVEN]** PR #1 is open, mergeable, correctly based, and scoped to exactly the six Mentor files.

**Merge after the Vercel quota resets: 2026-10-05 10:21:57Z.** The quota is still exhausted —
**[OBSERVED FACT]** no deployment has been produced since `4edd154`.

**[PROVEN] Merge, do not deploy the branch directly.** Vercel's Git integration deploys `master`; a
non-default branch yields a **preview**, not production. Merging is what triggers the real deployment.

Suggested post-merge verification (read-only): `/api/health` revision; `/api/mentor/overview` still
200 and account-invariant; `/api/mentor/message` 401 anonymous; no `Verified` evidence without a
source; no public-count or storage change.

Two local branches remain for audit only and can be deleted after merge: `mentor/hardening-3bf92b6`
(`0118703`, superseded) and `release/mentor-hardening-on-4edd154` (`ef074a5`, superseded by `13e9765`).

## 12. Remaining Issues

1. **`ef074a5` and `0118703` are superseded.** Both are stale relative to master. If either is ever
   merged it would revert master's documentation commits. They should be deleted after `13e9765` lands.
2. **Quota** is the only thing standing between this PR and production.
3. **[UNKNOWN]** Whether the owner wants the M1 docstring change and the M2/M3 behaviour change in one
   PR. They are independent and would split cleanly if review prefers.
4. **[UNKNOWN]** The source-less-record browser case could not be exercised end-to-end because such a
   record surfaces no evidence items. The rule is covered by unit test; an end-to-end fixture would
   need a listed record with an empty source, which production data does not currently contain.
5. **Out of scope, still open from earlier phases:** the purge/public `image_kind` predicate
   contradiction, the `unknown`-writer behind audit rows 66–91, and the October 3 reversion. None is
   touched by this PR.

**No deployment occurred. No merge was performed. Master was not rewritten. No unrelated work was
included. Production is unchanged at `4edd154`.**