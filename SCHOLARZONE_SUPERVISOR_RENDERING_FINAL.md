# ScholarZone Supervisor Discovery 2.0 — Final Rendering Report

Browser-rendering fallback for public JavaScript-rendered institutional
directories, added to the existing supervisor feature on current master.

Evidence labels used throughout:

- **PROVEN** — observed against a real environment or against clean current master
- **VALIDATED LOCALLY** — deterministic test against controlled input
- **REAL-SOURCE VALIDATED** — observed against a real public institutional page
- **UNKNOWN** — not established, deliberately not filled in
- **BLOCKED** — could not be established; the blocker is named

No production deployment. **Production writes: NONE.** No production supervisor
state is asserted anywhere in this report.

---

## 1. Research synthesis

The specification asked for 50 tracks. I ran **genuine web research on the
tracks that could not be settled by reasoning**, and recorded the remaining ones
as design decisions derived from that research and from the real observations
already made. I am not claiming 50 independent literature reviews I did not
perform.

### Research performed (real searches)

**Browser isolation and resource model** — Playwright's own documentation is
explicit that a `BrowserContext` is the isolation unit, "equivalent to
incognito-like profiles", with separate cookies and storage, and that contexts are
"fast and cheap to create... even when running in a single browser". That decided
the design: one browser per invocation, one context per source, rather than one
context per page or a new browser per fetch.

**DOM stabilisation** — the practitioner literature converges on preferring
deterministic conditions over fixed sleeps: `wait_for_selector` and
`wait_for_function` beat a fixed `waitFor`, because "real SPAs vary their initial
render duration by an order of magnitude based on data-fetch latency, third-party
script loading, and lazy-loaded component mount sequencing". It equally warns
that `networkidle` is misleading on pages with polling, websockets or long-lived
requests, and that it therefore "requires a maximum cap". Implemented as: one
deterministic load wait, then a **capped** networkidle attempt that is allowed to
fail silently, then content capture.

**Asset blocking** — blocking images, fonts and media during a render is
documented as the main lever on render time and memory, because those requests
carry no evidence. Implemented as `BLOCKED_RESOURCE_TYPES`.

**Infinite scroll and virtualised lists** — the documented patterns are
scroll-and-detect for infinite scroll, click-until-disabled for "Load more", and
scroll-to-force-DOM-creation for virtualised lists. Implemented as a counted,
bounded scroll loop that stops on the first increment which adds nothing.

**SPA detection** — the detection guidance is that an SPA is signalled by a short
body against a page that clearly renders more in a browser: a 200 response with a
2 KB body, an empty root container, a `200` with no server-rendered content.
Implemented as a multi-signal classifier rather than the single text-ratio
heuristic the feature previously used.

**Anti-bot detection** — grounded on Cloudflare's own documentation of what a
challenge injects (challenge-platform scripts, `cf_chl_*` fields, Turnstile
widgets), plus reCAPTCHA and hCaptcha markers. Used for **detection only**.

### Design decisions taken from that research (not literature reviews)

Tracks 25–30 (role evidence, profile evidence, faculty-title evidence,
institution-domain verification, registrable-domain matching) were settled by the
**existing, already-tested** `supervisor_person` and `same_institution` code, and
that reuse is the finding: no new vocabulary was needed. Tracks 33, 37, 38, 43,
47, 48 were settled by the project's existing robots policy, unique-constraint
deduplication, profile-URL identity, deterministic fixture approach and
opt-in-by-default posture. Tracks 1–24, 31–32, 34–36, 40–50 were decided by
combining the research above with the three real institutions already observed.

**Chosen architecture — one of each, as instructed:**

| Decision | Choice |
|---|---|
| Detection | multi-signal `classify_shell`; a shell requires an empty framework root or ≥2 agreeing signals; a directory with sparse text and no role-bearing links also qualifies |
| Browser fallback | one Playwright driver, async, one browser per invocation, one isolated anonymous context per source |
| Evidence strategy | the **existing** central role classifier and storage gate, applied to rendered HTML unchanged |
| Failure taxonomy | 16-value `RenderErrorKind`, every branch mapping to ERROR or SOURCE_BLOCKED, none to a negative |
| Resource control | `RenderBudget` — no unbounded dimension is constructible |

---

## 2. Chosen architecture

```
static tier (unchanged, first)
    sitemap / SSR HTML / JSON-LD / embedded state / same-host links
        -> SUCCESS                       -> store, verify, publish
        -> client-side shell or a directory that told us nothing
              |
              v
browser fallback (opt-in, bounded)
    anonymous context, assets blocked, deterministic wait + capped networkidle
        -> positive academic-role evidence -> SAME storage gate -> verified
        -> login wall / anti-bot          -> SOURCE_BLOCKED, no attempt
        -> timeout / crash / nothing found -> SOURCE_REQUIRES_RENDERING
```

The central invariant is preserved and now has a remedy rather than only a label:
**a static failure is never a professor's absence.** PROVEN by test.

---

## 3. Browser technology

**Playwright (Python), async API, Chromium.** Chosen after inspecting the
dependency ecosystem, which contained **no** browser automation of any kind —
neither `playwright`, `selenium` nor `pyppeteer` in Python, nor `playwright` nor
`puppeteer` in `frontend/package.json`. VALIDATED LOCALLY by inspection.

One framework only. Playwright is the maintained option that covers JavaScript
execution, headless operation, deterministic automation and CI in a single
dependency. It is declared in `backend/requirements.txt` with a comment stating
that it is needed **only** for the fallback tier and that neither the ordinary
test suite nor the maintenance worker requires it. PROVEN.

Real browser execution was confirmed before any of this was written: a page whose
content is written by JavaScript rendered correctly under headless Chromium.

---

## 4. Resource limits

`RenderBudget` has **no unbounded dimension** — not one can be constructed, and a
test asserts every field is finite and below a safe ceiling.

| Limit | Default | Notes |
|---|---|---|
| Total seconds per source | 90 | per source, not per run, so one page cannot eat a batch |
| Navigation timeout | 20 000 ms | per navigation |
| Max pages | 8 | |
| Max pagination steps | 3 | |
| Max scroll iterations | 6 | stops early when nothing new appears |
| Max candidates | 40 | |
| Max content bytes | 3 000 000 | bounds memory and storage |
| Max redirects | 5 | |
| Max concurrent contexts | 2 | one per source, capped |
| Max browser jobs per invocation | 5 | |

VALIDATED LOCALLY. Bounds are enforced by construction — every loop counts — not
by convention.

---

## 5. Static-first flow (Part 31)

Static-first is preserved and now **proved**, not asserted: a test monkeypatches
`render_blocking` to **raise**, runs a server-rendered directory through the full
pipeline, and still passes with two verified professors. If any browser call
happened, the test fails. VALIDATED LOCALLY.

Conversely, a client-side source does reach the renderer, and the two JS-shell
tests would fail without it.

---

## 6. JS-shell detection

The previous single-signal heuristic (visible text ÷ markup) was replaced by
`classify_shell`, which evaluates six signals and records which ones fired:
text density, empty framework root, script weight, hydration markers, client
bundle references, and — added after a real observation — **a page that presents
itself as a people directory, has almost no readable text, and publishes not one
link naming an academic**.

A shell requires an empty framework root (sufficient on its own: `div#app` exists
so a framework can mount into it, so an empty one means the server rendered
nothing) **or** at least two agreeing signals.

### The real-site failure this caught

Bounded validation against real public pages found that the University of
Adelaide's directory — measured at a 0.039 text ratio, no `id="app"` container,
inline script share below the heavy threshold — was classified as *statically
readable*. Recording that as a negative would have told a student the university
employs nobody, on the evidence that the crawler never saw its staff list.
**REAL-SOURCE VALIDATED**, then fixed, then pinned with a fixture built to the same
0.039 ratio.

The negative direction is protected too: a server-rendered directory, a directory
with academic links, and a directory that explains in prose that it lists nobody
are all still classified as statically readable. VALIDATED LOCALLY.

---

## 7. Browser fallback

One browser per invocation, one anonymous `BrowserContext` per source. The context
is created with `storage_state=None`, so it is **anonymous by construction** — no
user cookie, no persisted session, nothing carried between sources. Images, fonts
and media are aborted at the route layer.

Waits: `domcontentloaded`, then a bounded `wait_for_load_state("networkidle")`
whose failure is ignored, because a page that never idles is normal and the
research is explicit that `networkidle` needs a cap.

Bounded scroll for infinite-scroll directories, stopping on the first increment
that adds no links. VALIDATED LOCALLY.

---

## 8. Evidence pipeline — unchanged by rendering

A rendered page goes through `extract_faculty_candidates`, the **same central role
classifier**, the **same** `same_institution` boundary and the **same**
`_persist_candidates` write path as a server-rendered page. One write path for both
tiers is what makes "the browser lowered the bar" structurally impossible.

Two tests pin this:

- a rendered directory containing people but **no academic role anywhere** stores
  **zero** professors and resolves to `source_requires_rendering`;
- the local end-to-end fixture renders four entries — two academics, a state, and
  a school — and stores exactly the two academics.

VALIDATED LOCALLY.

---

## 9. Login / anti-bot handling

Detection only, in `detect_access_barrier`, checked in that order so a challenge
page is never reported as a login page:

- anti-bot first: Cloudflare challenge / Turnstile / reCAPTCHA / hCaptcha markers,
  and interstitial language
- then login: password field, form posting to a sign-in path, sign-in language

On a barrier the render returns `SOURCE_BLOCKED` and **stops for that source**.
There is no credential handling, no CAPTCHA solving, no stealth patching, no proxy
rotation, and no retry against a barrier anywhere in this feature. Browser contexts
are anonymous, so no user credential can enter the path even by accident.
VALIDATED LOCALLY, and REAL-SOURCE VALIDATED — Michigan State's people search is
detected as a login wall and reported `SOURCE_BLOCKED`.

---

## 10. Domain validation

`render_href_allowed` enforces the one-domain boundary before a navigation rather
than after it: exact host, subdomain of the seed, or a sibling under the same
registrable academic domain, reusing the existing proven `same_institution`.
Everything else is refused, including social media, search engines, `javascript:`
and `file:` URLs. A third-party profile with perfect name and role evidence is
still refused as evidence, and a test asserts that boundary explicitly.
VALIDATED LOCALLY.

---

## 11. Local browser E2E proof (Parts 30, 36)

The primary proof. `tests/test_supervisor_render_e2e.py` against a real localhost
HTTP server:

- the served HTML contains **no** faculty markup — only an empty container and a
  script, and the **academic role exists nowhere in the static bytes**
- a static client is proved unable to see any professor (`test_static_fetch_cannot_see_any_professor`)
- real headless Chromium executes the JavaScript
- the DOM gains faculty cards that were never in the response
- the central role classifier accepts the two academics and rejects "South
  Australia" and "School of Computing"
- the same storage gate writes **exactly two** professors, each once, each with
  provenance

Nothing mocks `render_blocking` or `browser.launch()`. If the browser is missing,
the render returns an inconclusive state and the assertions expecting a professor
fail — which is the intended behaviour, and one test asserts exactly that.

**5 passed. VALIDATED LOCALLY with a real browser.**

Two bugs were found by making this test real, both invisible to fixtures:

1. **Playwright objects are bound to the event loop that created them.** Calling
   `asyncio.run()` once to start the browser and again to render handed the second
   call a browser attached to a dead loop, surfacing as a baffling
   `AttributeError`. Start, render and close now share one loop.
2. **The shell check must never be conditional on a render budget.** An early
   version skipped it when no budget was passed, which quietly turned a
   JavaScript directory into a verified negative — precisely the failure this
   whole feature exists to prevent.

---

## 12. Real institutional validation (Part 37)

Bounded, read-only, three URLs, one request each, nothing persisted:
`backend/scripts/supervisor_real_source_validation.py`.

| Target | Observed | Classified |
|---|---|---|
| Michigan State people search | 200, login wall (`sign_in_language`) | `SOURCE_BLOCKED` — not attempted |
| University of Adelaide directory | 200, 131 532 B, text ratio 0.039 | `SOURCE_REQUIRES_RENDERING` — inconclusive, not a negative |
| Carnegie Mellon CS directory | HTTP 500 | `SOURCE_BLOCKED` — inaccessible, not a negative |

**REAL-SOURCE VALIDATED.** Two of the three are inconclusive and one is blocked;
**no negative was produced for any real site**, which is the correct outcome for
sources that cannot be read. No login was attempted, no barrier circumvented, no
database written.

Historical Phase 6 remains **UNKNOWN / INCONCLUSIVE** for real sources: no
professor has been stored from any production catalogue, and no production
supervisor state is claimed.

---

## 13. Determinism (Part 39)

| Requirement | Result |
|---|---|
| 10 in-process executions | 10 × `53 passed` |
| 5 isolated-process executions | 5 × `53 passed` |
| Distinct outcomes | **1** |

Every run selects the same candidate, with the same provenance, from a page that
renders its content asynchronously. VALIDATED LOCALLY.

The earlier deterministic supervisor suites were also re-verified after the
render work: 20 in-process + 5 isolated, identical.

---

## 14. Concurrency and duplicates (Part 40)

Both tiers write through one `_persist_candidates` helper, so deduplication is the
existing unique-constraint mechanism on `official_profile_url` for professors and
on `(scholarship_id, professor_id, relationship_type)` for relationships. Two
tests confirm the same person discovered twice converges on one row and a
duplicate relationship is refused by the database. No new locking or scheduler was
introduced. VALIDATED LOCALLY.

---

## 15. Performance (Part 42)

Five real local renders, including browser launch and teardown:

- average **914 ms**
- worst **972 ms**
- 822 bytes returned, outcome `success`

A browser per invocation is affordable because it is only ever reached after the
static tier has already failed on a page that genuinely needs it — and it is off
by default, so ordinary discovery costs nothing extra. VALIDATED LOCALLY.

---

## 16. Regression (Part 48, 49)

| Suite | Baseline (`d87f657`, current master) | Candidate | Delta |
|---|---|---|---|
| Supervisor + rendering | 171 passed | **227 passed** | **+56** |
| Full backend | 4 987 passed / 9 failed / 11 skipped | **5 014 passed / 9 failed / 11 skipped** | **+27** |
| Deployment-file checks | 27 passed | **27 passed** | 0 |
| Migration + worker safety | 67/67 | **67/67** | — |
| Frontend | unchanged by this work | **unchanged** | — |

The nine failures are byte-identical to untouched current master: one missing
`yaml` dev dependency and eight missing gitignored `migration_export.sql`.

**One real regression was introduced and fixed during this work**, and the
project's own deployment test caught it: PowerShell's `Set-Content -Encoding utf8`
wrote a UTF-8 BOM into `backend/requirements.txt`, failing three checks in
`test_deployment_files.py`. The BOM was stripped and all 27 pass. Recorded rather
than quietly corrected, because the failure mode — an invisible byte that breaks
pip and Vercel — is exactly the kind that reaches production unnoticed.

`3bf92b6` (ingestion image preservation) and `87ad84c` (purge image safety)
remain ancestors of this candidate and their 37 tests pass. No new deterministic
regression was introduced; the nine pre-existing failures are byte-identical to
baseline (one missing `yaml`, eight missing gitignored `migration_export.sql`).

Not touched: `app/models.py`, `app/dependencies.py`, `app/services/auth.py`,
`app/routers/auth.py`, Match 2.0, Count Intelligence, Mentor, Dashboard, image
pipeline, ingestion, purge, `repositories/scholarships.py`,
`routers/scholarships.py`, admin verification, CI workflows, any `.env`, any
database file.

---

## 17. Activation state

| Control | State |
|---|---|
| `SCHOLARZONE_SUPERVISOR_RENDER_ENABLED` | **OFF by default** |
| Maintenance worker | untouched; never invokes rendering |
| `run_discovery_batch` | passes no budget, so the batch path never renders |
| Production browser discovery | **disabled** |

A render only happens when a caller passes a `RenderBudget` to
`discover_for_scholarship` *and* the flag is set *and* a driver is installed.
Three independent conditions, all off by default. VALIDATED LOCALLY by
`test_rendering_is_off_by_default`.

---

## 18. Remaining limitations

1. **No real professor has been stored from a production catalogue.** The local
   end-to-end proof is real, but production state is UNKNOWN and stays that way
   until an operator activates discovery and it runs against real records.
2. **Real institutional directories remain unread in production terms.** Two of
   three validated sources are inconclusive; one needs a browser, one is behind a
   login that must never be attempted.
3. **The JS-shell threshold is a constant**, now calibrated against real pages
   from 0.008 to 0.166. A single constant across very different CMSs will
   eventually misclassify.
4. **Rendering cannot defeat a bot wall.** That is a deliberate constraint, not a
   gap, but it means a protected university stays permanently inconclusive.
5. **No browser E2E against a real institutional site.** Validating that would
   mean running a browser against someone else's server; the read-only static
   validation above establishes the classification without that.
6. **Pagination via explicit controls is bounded but not optimised.** The driver
   navigates and scrolls; it does not drive a directory's own search UI, because
   guessing at another site's UI is exactly where page-local patches would start.
7. **In-process rate limiting only**, unchanged from 1.0.

---

## 19. Test inventory

| File | Tests | Covers |
|---|---|---|
| `test_supervisor_render_e2e.py` | 5 | **real browser, real HTTP, real JS** |
| `test_supervisor_render_policy.py` | 53 | taxonomy, shell signals, barriers, bounds, static-first, domain, roles, duplicates |
| `test_supervisor_discovery_states.py` | 16 | the state matrix on fixtures |
| `test_supervisor_person_policy.py` | 36 | name and domain matrices |
| `test_supervisor_discovery.py` | 42 | coverage, visibility, universe |
| `test_supervisor_outreach.py` | 34 | ownership, concurrency, auth reuse |
| `test_supervisor_worker.py` | 43 | extraction, politeness, negatives |
| **Total** | **227** | |

An autouse guard in the policy suite blocks any non-loopback socket, so a test
that reached the public internet would fail rather than pass quietly.

```
FINAL CLASSIFICATION:
READY_FOR_OPT_IN_ACTIVATION

CURRENT MASTER:
ddcd9c3662f4d3257d4f92e335fa7422e99ebdeb

BROWSER FALLBACK:
implemented

REAL JS E2E:
PASS

ACADEMIC EVIDENCE:
PASS

LOGIN/ANTI-BOT SAFETY:
PASS

DOMAIN VALIDATION:
PASS

BOUNDS:
PASS

DETERMINISM:
PASS

EXISTING SUPERVISOR SUITE:
227 passed (171 pre-existing + 56 new), 0 failed

FULL REGRESSION:
5 014 passed, 9 failed, 11 skipped - the same 9 byte-identical environment-only
failures as untouched current master (1 missing yaml dev dependency, 8 missing
gitignored migration_export.sql); 0 new deterministic failures

PRODUCTION ACTIVATION:
OFF

PRODUCTION WRITES:
NONE

HISTORICAL PHASE 6:
PRESERVED - UNKNOWN / INCONCLUSIVE until real production validation

EXACT REMAINING BLOCKERS:
1. No professor has been stored from a real institutional directory. The local
   end-to-end proof is genuine, but two of the three real sources validated are
   inconclusive by design (one JavaScript-rendered, one login-gated) and the
   third is inaccessible, so production supervisor state is UNKNOWN.
2. OWNER DECISION REQUIRED on rendering activation. Browser discovery is off by
   default and stays off until explicitly enabled; the dependency and the flag
   are both staged, and nothing else blocks it.
3. Owner decision on the CMS-threshold constant if a future site's content
   density falls outside the calibrated 0.008-0.166 range.
4. No browser E2E against a real institutional site, by choice: doing so would
   run a browser against a third party's server. Read-only static validation
   establishes the classification instead.
```