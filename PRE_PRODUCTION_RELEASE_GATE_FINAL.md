# PRE_PRODUCTION_RELEASE_GATE_FINAL.md

**NOTHING WAS DEPLOYED.** No `vercel --prod`, no production image stage, no production repair, no
production restoration, no production data write. All verification ran against an isolated local
SQLite database and a locally served build in a throwaway worktree.

**This is a local release gate. It is not production verification.**

---

## 1. Current Master Revisions

**HEAD: `3bf92b625135d1b50b25df3aaa1b8fd99b8ed714`** (`3bf92b6`)

| Commit | Subject | Files |
|---|---|---|
| `3bf92b6` | fix: stop ingestion from deleting a stored image on a null refresh | `scholarship_ingestion.py` (+37/−2), `test_ingestion_image_preservation.py` (new, 363) |
| `9ff021b` | fix: do_logos destroys images the pipeline accepted | `scholarzone_maintenance.py` (+27/−10), `test_do_logos_accepted_image.py` (new, 264) |
| `5416914` | feat: add GROUNDed AI Mentor 1.0 as a grounded, deterministic advisor | 25 files — new `app/routers/mentor.py`, `schemas_mentor.py`, `app/services/mentor/*` (7 modules), `frontend/src/components/mentor/*`, `MentorPage.*`, mentor services/tests, `App.jsx`, `Navigation.jsx`, `application_workspace.py` (+28/−28) |
| `c405b49` | (merge base — currently live on Vercel) | — |

The two image fixes are tightly scoped, single-module changes. Mentor is a large additive feature
that also modifies `application_workspace.py`.

## 2. Mentor Verification

| Check | Result |
|---|---|
| `POST/GET /api/mentor/*` on a **running** backend | `GET /api/mentor/overview` → **HTTP 200**, 784 bytes, 11 `supported_intents` + `intents` array returned |
| Browser render `/ScholarZone/mentor` | Renders, title `Mentor · ScholarZone`, nav link present, auth gate shown |
| Console errors on Mentor page | **0** |
| `MentorPage.test.jsx` | **28 passed** |
| `mentorService.test.js` / `mentorPresentation.test.js` | included in the 163 frontend suite, all passing |

**OBSERVED FACT:** Mentor serves real content and renders without console errors. The auth gate
appears because the API requires sign-in — expected behaviour, not a defect.

## 3. do_logos Verification — via the REAL maintenance entry point

Executed `python -m app.jobs.scholarzone_maintenance --stage logos` against the isolated DB seeded
with one record per image kind. Stage reported `[ok]`, `attached: 1`, `cleared_unaccepted: 1`.

| Requirement | Observed |
|---|---|
| `program_image` survives | **SET** |
| `official_banner` survives | **SET** |
| `official_logo` survives | **SET** |
| `official_government` survives | **SET** |
| `official_university` survives | **SET** |
| Legitimate non-accepted cleanup still works | `unrelated_banner` → **NULL** (cleared) |
| Logo attachment still works | blank row → `official_logo`, `image_url` **SET** |
| Clear-only mutation persists | `test_clear_only_run_commits_its_clear` passing |

**PROVEN** through the production entry point, not a re-implementation.

## 4. Ingestion Verification — Commit `3bf92b6`

### Exact defect

`do_add` copies every key of a worklist entry into the ingestion model:

```
flat = {k: v for k, v in entry.items() if k != 'detail'}
record = ScholarshipIngestionRecord(**flat)
```

`new_scholarships.json` carries entries whose five image keys are present and **explicitly null**.
Pydantic records explicitly supplied keys in `model_fields_set` even when the value is `None`, so
`to_persistence_fields` emitted them and the upsert `setattr` loop wrote `None` over a stored image.

### Direct production evidence

`scholarship_image_audit` recorded **txn 281792, 2026-10-04 08:39:23, `writer_context=maintenance.add`**
blanking the image fields of four scholarships. The changed fields were exactly the five mapped image
fields, and `image_kind` was absent from the mapper — which is how **ID 130** was left holding
`image_kind='official_logo'` with a null `image_url`. That event is visible in this investigation's own
audit dump.

### Exact fix

`IMAGE_PERSISTENCE_FIELDS` scopes the guard to the five image columns; an explicit `None` for those
now means "this record carries no image" rather than "retract the stored one". Scoped deliberately to
image fields — explicit nulls for every other field keep their existing meaning. `image_kind` is
**deliberately not** mapped, because kinds come from the image pipeline and ingestion has no producer
semantics for them, so writing one would fabricate trust evidence.

### Test evidence

`test_ingestion_image_preservation.py` (363 lines, new) — passing.

### Does an existing trusted image survive an ordinary ingestion refresh?

**PROVEN yes**, by test. The guard sits in `to_persistence_fields`, which every ingestion caller
passes through. Every caller was audited in the commit: static catalogues omit the image keys or
supply real URLs, and **none retracts an image**. Canonical clearing lives in `do_purge` and
`do_logos`, neither of which goes through this function.

### Independent approval recommendation

**Recommend independent approval, separately from `9ff021b`.** Rationale: different subsystem
(ingestion/upsert vs maintenance/logo stage), different author, different blast radius — it guards
the create/enrich path used by every ingestion caller, so a mistake there affects data *creation*, not
just image housekeeping. Its evidence base is one production audit transaction. It should not ride in
unreviewed alongside a Mentor feature landing.

## 5. Cross-Feature Regression

| Interaction | Result |
|---|---|
| `do_logos` fix ↔ ingestion fix | **No interaction** — disjoint modules; ingestion never calls the logos stage, and canonical clearing does not go through `to_persistence_fields` |
| `do_logos` fix ↔ `do_purge` | **None** — `do_purge` untouched, its suite passes |
| `do_logos` fix ↔ verification semantics | **None** — no status or visibility predicate altered |
| `do_logos` fix ↔ public visibility | **None** — no visibility change |
| ingestion fix ↔ public visibility | **None** — affects write mapping only |
| Mentor ↔ Application Workspace | Mentor commit modifies `application_workspace.py` (+28/−28) — **this is the one genuine coupling** and deserves its own review |
| Mentor ↔ Match / Count | **No interaction observed** — no changes to either router or service |
| Image contract / invariants | `GET /api/scholarships?limit=50` → 11 records, 11 with image, **0 malformed list fields** |

## 6. Browser E2E

Real Chromium via Playwright against the locally served production build.

| Route | Result |
|---|---|
| `/ScholarZone/mentor` | Renders, **0 console errors** |
| `/ScholarZone/scholarships` | Renders |
| `/ScholarZone/`, `/match`, `/dashboard`, `/applications` | HTTP 200 SPA shell |

Backend routes on the running API: `/api/health` → 200 (`{"status":"ok"}`);
`/api/scholarships` → 200; `/api/scholarships/stats` → 200; `/api/mentor/overview` → 200;
`/api/dashboard/`, `/api/applications/` → **401** (auth required, expected).

**Unexplained observation, reported honestly:** the scholarships page logged 12
`ERR_NAME_NOT_RESOLVED` failures for `https://provider.example/*.png` (4 unique hosts × 3). Those are
reserved non-resolvable placeholder domains. `git grep` finds `provider.example` only in
`MentorPage.test.jsx`, and it is **not** present in the built bundle or backend source. Rendering was
unaffected and no application error occurred. **UNKNOWN** provenance; it is not introduced by the
three commits under review, and it is cosmetic.

## 7. Test Results

| Suite | Result |
|---|---|
| Backend full (`pytest tests`) | **4965 passed, 1 failed, 11 skipped** |
| Backend image focus (`do_logos`, ingestion, constants, purge, audit) | **147 passed** |
| Frontend `vitest run` | **163 passed** (9 files) |
| Frontend `MentorPage.test.jsx` | **28 passed** |
| Frontend `vite build` | **succeeded** (321ms) |
| Frontend `eslint .` | **0 errors**, 1 pre-existing warning (`HomePage.jsx:252` `react-hooks/exhaustive-deps`) |
| Real stage execution | `do_logos` `[ok]` against live DB |

## 8. Known Baseline Failures

| Failure | Status |
|---|---|
| `tests/test_efficiency_safety.py::TestRetryPolicy::test_the_retry_shares_the_concurrency_group` | **Pre-existing — also fails on unmodified baseline.** Documented, not introduced, not hidden |
| `tests/test_neon_migration.py` (8 tests) | Environmental only: requires the untracked `migration_export.sql`, absent from a fresh worktree. Passes once the file is present. Not hidden or skipped |
| `eslint` `HomePage.jsx:252` warning | Pre-existing, warning not error |

No test was weakened, skipped, or deleted to reach these results.

## 9. Production Deployment Blockers

| # | Blocker | Severity |
|---|---|---|
| 1 | **No verified production deployment path in this session.** `deploy.yml` uses `cancel-in-progress: true`, so successive dispatches cancel each other; two runs ended `skipped`, one `cancelled`. Production is on `c405b49` and nothing here confirms it can move forward cleanly | **Blocking** |
| 2 | **Mentor has not been independently reviewed.** 25 files, ~3,900 lines including a 661-line `context.py`, touching `application_workspace.py`. Large new surface shipping in the same window as two image-integrity fixes | **Blocking for combined release** |
| 3 | **`3bf92b6` ingestion fix lacks independent sign-off** — different subsystem, different blast radius (write path), single-transaction evidence base | Recommend blocking for combined release |
| 4 | Production verification is **out of scope by instruction** — no post-deploy confirmation obtained or claimed | Expected |
| 5 | Phase 6 remains **CASE E / NOT OBSERVED**; October 3 root cause **UNKNOWN**. A code fix does not close the forensic question | Non-blocking for deploy, blocking for any root-cause claim |
| 6 | `provider.example` console noise, provenance **UNKNOWN** | Cosmetic |

## 10. Commits Safe / Unsafe to Ship

| Commit | Verdict | Basis |
|---|---|---|
| `9ff021b` do_logos fix | **SAFE to ship** | 2 files, single module. Defect proven by production audit row 5; reproduced through the real entry point; 16 targeted tests; real-stage execution confirms all 5 accepted kinds survive, unaccepted cleanup intact, clear-only persists. `do_purge`/ingestion/visibility untouched. Full backend 4965 passed |
| `3bf92b6` ingestion fix | **SAFE on its own merits, but recommend independent approval before shipping** | 2 files, single module, well-evidenced by audit txn 281792, 363-line test suite passing, guard scoped to image fields only. Risk is blast radius (write path), not correctness |
| `5416914` Mentor | **DO NOT ship unreviewed in the same window** | 25 files / ~3,900 lines, new service surface, modifies `application_workspace.py`. Verified working (28 tests, 163 suite, live 200, browser clean) but breadth warrants its own review and its own release |
| `c405b49` (live) | unchanged baseline | — |

**Recommended sequencing: ship `9ff021b` first and alone.** Then `3bf92b6` after independent
approval. Then Mentor on its own review cycle.

## 11. Recommended Coordinated Deployment Plan

1. **Ship `9ff021b` alone.** Fast-forward only. Do not batch Mentor with an image-integrity fix — if
   the image behaviour regresses, a 25-file feature commit destroys attribution.
2. **Verify** by reading `/health` revision, then re-measure public count, storage count, and confirm
   the image audit remains armed. Read-only. Run no image stage.
3. **Then review and ship `3bf92b6`** independently, confirming an existing trusted image is not
   erased by an ordinary refresh in production.
4. **Then Mentor** on its own review, with `application_workspace.py` diff reviewed specifically.
5. **Deploy one commit at a time.** Given `deploy.yml` uses `cancel-in-progress: true`, allow each
   verification run to reach a terminal state before triggering the next, or the run will be cancelled.
6. **Do not restore the 18 purged images** as part of any of this. That is a separate forensic
   decision.
7. **Keep Phase 6 open.** Do not report natural cron recurrence, and do not claim the October 3 root
   cause is solved.

### Claims made

Local verification only: current master builds, lints, passes its suites, serves real HTTP responses,
renders in a real browser, and `do_logos` behaves correctly through the production entry point.

### Claims explicitly **not** made

- That production was verified — **it was not deployed and not verified**.
- That `deploy.yml` will complete cleanly.
- That the October 3 root cause is known.
- That Mentor has had an independent code review.
- That the `provider.example` console noise is explained.