# ScholarZone Supervisor Discovery — Final Review Gate

Review of the integrated candidate. Not pushed, not merged, not deployed,
production rendering not enabled.

```
PRODUCTION_ACTIVATION = OFF
PRODUCTION_STATE = UNKNOWN
PRODUCTION_WRITES = NONE
```

---

## 0. Master moved again during this review

The task named `cfb2b54`. Verified independently three ways at the start of this
review — `git ls-remote`, the GitHub API, and a `--prune` fetch — and found that
master is now:

```
cfd0aca  chore(seo): add Google Search Console verification (#9)
```

`cfb2b54` is its direct parent, and the new commit touches **`frontend/index.html`
only**. Overlap with any supervisor file: **none**. Master also still contains no
supervisor implementation, so nothing was duplicated.

The candidate is therefore based on the task's stated master `cfb2b54` and is one
cosmetic SEO merge behind the current tip. That is stated plainly rather than
papered over, and it does not block a merge decision.

## 1. Exact diff

`cfb2b54 → 61d0c81` (before this review's commit): **45 files, +13 625 / −2**.

After this review's fix commit, four further files changed; all supervisor-scoped
or review tooling.

**The two deleted lines in the entire diff were audited individually**, because a
deletion is where a regression hides:

| File | Deleted | Verdict |
|---|---|---|
| `backend/requirements.txt` | one blank line | cosmetic |
| `backend/app/database.py` | `if not (image_kind_ok and image_reviews_ok and indexes_ok):` | **extended, not weakened** |

The validator's raise condition is now
`image_kind_ok and image_reviews_ok and indexes_ok and supervisor_tables_ok` — a
strict superset. All three original checks still gate the raise, and the missing-object
report still names all four. Verified by reading the integrated file.

## 2. Scope

34 of 45 files are supervisor-named. The 11 others are each a minimal integration
point, and no unrelated product file is among them:

`app/core/rate_limit.py` (limiter used only by supervisor routes) ·
`app/database.py` (guarded DDL + validator) · `app/main.py` (three router
registrations) · `app/routers/outreach.py` · `app/schemas.py` (response models) ·
`migrate_schema.py` (registration) · `requirements.txt` (documented optional
dependency) · `tests/support_local_js_directory.py` (test fixture) ·
`ScholarshipCard.jsx` (2-line CTA mount) · `ScholarshipDetailsPage.jsx` (9-line
panel mount) · `vite.config.js` (jsdom for component tests).

## 3. Preserved subsystems

Every named subsystem file — build provenance, SEO, Count, Match, Mentor,
visibility, image, maintenance, auth, repositories, routers — is **byte-identical
to master**. Verified file by file, not inferred from the absence of a diff hunk.

`3bf92b6` (ingestion) and `87ad84c` (purge) remain ancestors. Their 37 tests pass.

## 4–11. Policy checks

| # | Check | Result |
|---|---|---|
| 4 | Browser fallback bounded | all 10 budget dimensions finite; no unbounded constructible |
| 5 | Static-first | `_attempt_render_for_shells` returns early when no shell is found; a test patches the renderer to **raise** and a server-rendered directory still passes |
| 6 | JS fallback opt-in | flag checked inside the driver; never assigned anywhere in the repo |
| 7 | Login-gated → `SOURCE_BLOCKED` | `SourceOutcome.SOURCE_BLOCKED` branch at line 1053; returns and stops for that source |
| 8 | No CAPTCHA bypass / stealth / proxy | grep across supervisor modules finds only comments stating there is **no** solving, plus the word "unresolved" |
| 9 | Domain validation | `render_href_allowed` before navigation; rejects social, search engines, `javascript:`, `file:`, lookalikes |
| 10 | Academic-role evidence | `if not candidate.has_role_evidence` gates storage at line 953 |
| 11 | No name blacklist | `_NOT_A_NAME_WORDS`, `_NOT_A_PERSON_PHRASES`, blacklist symbols: **none** |
| 12 | Determinism | 15/15 identical |
| 13 | Activation OFF | flag unset everywhere; maintenance worker never invokes supervisor discovery or rendering; `run_discovery_batch` calls `discover_for_scholarship(session, row)` with **no** budget, so the batch path cannot render |
| 14 | No accidental real rendering | no real institution is rendered anywhere in any test or script |

## Browser review — real Chromium, integrated frontend + backend

Driven against the running integrated app: Vite dev serving the integrated
frontend, uvicorn serving the integrated API, headless Chromium over real HTTP.
Seeded a four-record fixture catalogue, one per coverage state.

| Surface | Result |
|---|---|
| Catalogue | loads; 4 cards on the filtered view |
| Card CTA | **exactly 1 of 4 cards** shows `POTENTIAL SUPERVISORS · 1` |
| Scholarship detail | renders |
| Supervisor panel | renders on all four records |
| Verified state | professor, verified email, and "Not published" availability all shown |
| Empty state | "No verified supervisors found yet" |
| Not-searched state | "…has not been completed…" |
| Blocked/inconclusive state | "…only after the page loads in a browser…" |
| States distinct | **all four render different copy** |
| Console errors | **0** |
| Page errors | **0** |
| Layout at 1280 | no horizontal overflow on any record |
| Layout at 360 | no horizontal overflow |
| Phantom/verified claim | **none** — no "verified professor", "guaranteed", "chance", "response rate" or "%" anywhere |

### The review found a real defect, which is now fixed

Eight console errors on every public detail page. The outreach tracker fetched
`/outreach` unconditionally, so a signed-out visitor generated a 401 that the
browser logged. Fixed by deriving the signed-out view during render and never
issuing the request without a session — deliberately not with a `setState` inside
the effect, which is the synchronous-write pattern the repo's lint rule forbids.

The panel tests were rendering the component outside the provider the application
always mounts. Corrected to the real provider tree, which exposed an import that
resolved to the context module instead of the provider on a case-insensitive
filesystem. The app spells it `'../context/AuthContext.jsx'`; the tests now do
the same.

### Two harness errors I made, corrected rather than reported as findings

- I first asserted the CTA count against an unfiltered catalogue. The application
  seeds its own catalogue into whatever database it is pointed at, so my fixtures
  were never on page 1. The "failure" was my harness, not the product.
- I then set a past deadline to force the fixtures to the front, which made the
  lifecycle manager **close** them. Replaced with a unique country and a filter,
  which is the correct way to isolate them.

## Test results — measured on the integrated tree

| Gate | Result |
|---|---|
| Supervisor tests | **227 passed**, 0 failed |
| Real JS E2E | PASS (5 tests, real headless browser over real HTTP) |
| Static negative proof | PASS |
| Browser fallback proof | PASS |
| Domain validation | PASS |
| Login / anti-bot safety | PASS (8 tests) |
| Determinism | PASS — 10 in-process + 5 isolated, all `56 passed`, 1 distinct outcome |
| Migration + worker safety | 67/67 |
| Deployment-file checks | 27 passed |
| Frontend | **195 passed**, 11 files |
| Lint | **0 errors**, 1 pre-existing warning |
| Build | success |
| Full backend | **5 306 passed, 9 failed, 10 skipped** vs baseline on untouched `cfb2b54` **5 079 passed, 9 failed, 10 skipped**; failure sets diffed **by name**, identical |

No test was skipped, xfailed or loosened: the skip count is **unchanged at 10**.

## What this still does not prove

The local browser chain is genuinely proven. That a **real production
institutional directory** can be processed successfully is **not**. Bounded
read-only validation found real sources that are inconclusive (JavaScript-rendered),
login-gated, or inaccessible. No real institution has yet yielded a verified
professor. That gap is why production rendering stays off.

---

```
FINAL DECISION:
READY_FOR_MERGE

REVIEWED CANDIDATE:
259e456  (61d0c81 + this review's fix)
branch feat/supervisor-discovery-integrated
base cfb2b54, the master named in the task
current origin/master is cfd0aca — one SEO-only commit ahead, zero file overlap

PUSHED: NO
MERGED: NO
DEPLOYED: NO

PRODUCTION_ACTIVATION:
OFF

PRODUCTION_STATE:
UNKNOWN

PRODUCTION_WRITES:
NONE

SUPERVISOR TESTS:
227 passed, 0 failed

REAL JS E2E:
PASS

STATIC NEGATIVE PROOF:
PASS

BROWSER FALLBACK PROOF:
PASS

DOMAIN VALIDATION:
PASS

DETERMINISM:
PASS — 15/15 identical

BROWSER CONSOLE ERRORS:
0 (one real defect found by this review and fixed)

FRONTEND:
195 passed, 11 files; lint 0 errors; build success

FULL BACKEND:
5 306 passed, 9 failed, 10 skipped
baseline on untouched cfb2b54: 5 079 passed, 9 failed, 10 skipped
failure sets identical by name; skip count unchanged at 10

MERGE CONDITIONS SATISFIED:
- browser fallback bounded
- static-first intact
- JS fallback opt-in and never enabled
- login-gated -> SOURCE_BLOCKED
- no CAPTCHA/anti-bot circumvention
- domain validation enforced
- academic-role positive evidence enforced
- no name blacklist
- determinism intact
- build provenance, SEO, Count, Match, Mentor, visibility, image, maintenance intact
- both production image fixes preserved and tested
- no unrelated dirty work touched

REMAINING BLOCKERS:
1. Production supervisor state is UNKNOWN. No real institutional directory has
   yielded a verified professor, so enabling production rendering would activate
   a capability whose real-world hit rate is unmeasured. This is an owner
   decision, not a merge blocker.
2. Master is one SEO-only merge ahead of the candidate base. Trivially resolvable
   at merge time; noted so it is not a surprise.
3. No browser E2E against a real institutional site, by choice: that would run a
   browser against a third party's server. Read-only static validation establishes
   the classification instead.
```