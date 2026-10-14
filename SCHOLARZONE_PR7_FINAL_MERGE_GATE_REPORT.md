# SCHOLARZONE — PR #7 FINAL MERGE GATE REPORT

**Final classification: MERGE_READY**

PR #7 was merged normally (merge commit, no force-push, no history rewrite) after
every gate passed. Post-merge verification is recorded below.

| Item | Value |
|---|---|
| PR | #7 — `feat: Phase A durable slot core + Phase B external dispatch backstop` |
| Branch | `feat/maintenance-phase-b-rebased` |
| Exact head tested | `ef2a1375bb1a14959c2575ced3f73b9437e5604d` (`ef2a137`) |
| Merge base at verification | `cfd0acaf00dc6bd2ec9ce30c6dbc2a128eae032b` |
| `origin/master` at merge time | `22cf31d38014d43ab70dca98eeb0285db6513aaf` (moved during verification) |
| **New master after merge** | **`804133c45cfbf1d52b7b907b91191c6c789d068c`** |
| Merge parents | `22cf31d` + `ef2a137` |
| Merged at | 2026-10-05T08:16:42Z |
| Production activation | **NOT PERFORMED** |
| Production writes | **NONE** |

---

## 1. Refs refreshed and head pinned

`git fetch origin --prune` was run before and after all verification.

- `origin/master` was `cfd0aca` at the start of verification, as briefed.
- PR #7 head was `ef2a137`, exactly as briefed. Earlier in this engagement the
  remote tip had been observed at `93b65e1`, then `b55df30`, then `ef2a137`; the
  brief's value matched the value at verification time.
- All testing ran in a worktree **detached at the exact SHA**
  `ef2a1375bb1a14959c2575ced3f73b9437e5604d`, so a later remote move could not
  change the tree under test. `git rev-parse HEAD` in that worktree equalled the
  exact SHA, and its working tree was clean.

### Head stability

`origin/feat/maintenance-phase-b-rebased` was re-checked after all gates and
again immediately before the merge:

| Check | Result |
|---|---|
| Head at verification start | `ef2a137` |
| Head after all gates | `ef2a137` (unchanged) |
| Head immediately pre-merge | `ef2a137` (unchanged) |
| `gh pr view 7 → headRefOid` | `ef2a137` |
| `origin/master` after merge testing | `22cf31d` (did not move again) |

**The PR head never moved during verification.** No restart was required.

---

## 2. Canonical Phase A architecture proven at the exact head

| Requirement | Result |
|---|---|
| `backend/app/maintenance_slots.py` present | **yes** |
| `backend/app/services/maintenance_slot_store.py` present | **yes** |
| `backend/tests/test_maintenance_slots.py` present | **yes** |
| `backend/tests/test_maintenance_slot_concurrency.py` present | **yes** |
| `backend/tests/test_maintenance_slot_persistence.py` present | **yes** |
| Superseded `backend/app/services/maintenance_slot.py` absent | **yes** |
| Superseded `backend/tests/test_maintenance_slot_core.py` absent | **yes** |
| No duplicate competing Phase A core | **confirmed** |

`git grep -l -E "def claim_slot|def slot_id_for" -- backend/app` returns exactly
one file: `backend/app/services/maintenance_slot_store.py`. There is one
persistence core and one pure identity module, not two competing ones.

`MaintenanceRun.slot_id` is **nullable and non-unique**:

```
slot_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
Index("ix_maintenance_runs_slot_id", "slot_id")          # non-unique index
```

No `unique=True` on `slot_id` in the `MaintenanceRun` table. The startup
migration adds the column as `VARCHAR(64)` and creates
`ix_maintenance_runs_slot_id ON maintenance_runs (slot_id)` — non-unique.
Uniqueness lives on `maintenance_slots.slot_id`, which is the intended design.

---

## 3. Complete PR diff inspected and every file classified

`git diff --name-status cfd0aca ef2a137` — 16 files, 3809 insertions, 3 deletions,
**zero deletions**.

| # | File | Status | Classification |
|---|---|---|---|
| 1 | `.github/workflows/verification-cron.yml` | M | Phase A/B — `workflow_dispatch` inputs for external dispatch; cron retained |
| 2 | `SCHOLARZONE_PHASE_B_INTEGRATION_FINAL.md` | A | Phase A/B — integration proof document (`ef2a137`) |
| 3 | `backend/app/database.py` | M | Phase A — `slot_id` column migration + non-unique index |
| 4 | `backend/app/jobs/scholarzone_maintenance.py` | M | Phase B — source attribution |
| 5 | `backend/app/main.py` | M | Phase B — router registration |
| 6 | `backend/app/maintenance_slots.py` | A | Phase A — pure identity/state-machine core |
| 7 | `backend/app/models.py` | M | Phase A — nullable non-unique `slot_id`, `MaintenanceSlot` |
| 8 | `backend/app/routers/internal_maintenance.py` | A | Phase B — dispatch endpoint |
| 9 | `backend/app/services/maintenance_dispatch.py` | A | Phase B — backstop dispatcher |
| 10 | `backend/app/services/maintenance_run_log.py` | M | Phase B — source attribution |
| 11 | `backend/app/services/maintenance_slot_store.py` | A | Phase A — durable slot persistence |
| 12 | `backend/tests/test_maintenance_dispatch_phase_b.py` | A | Phase B tests |
| 13 | `backend/tests/test_maintenance_slot_concurrency.py` | A | Phase A concurrency tests |
| 14 | `backend/tests/test_maintenance_slot_persistence.py` | A | Phase A persistence tests |
| 15 | `backend/tests/test_maintenance_slots.py` | A | Phase A pure-core tests |
| 16 | `vercel.json` | M | Phase B — backstop cron |

**Every file is in Phase A/B scope. No unrelated changes. No deletions.**

### Preserved surfaces — verified unchanged

| Surface | Files changed by the PR |
|---|---|
| `frontend/` (all) | **0** |
| `backend/app/data/generate_sitemap.py` (SEO) | **0** |
| `backend/app/build_provenance.py` | **0** |
| `backend/app/services/mentor/` | **0** |
| `backend/app/routers/counts.py` | **0** |
| `backend/app/routers/match.py` | **0** |
| `backend/app/services/image_/` | **0** |
| `package.json` / `package-lock.json` | **0** |
| provenance / SEO / vercel / release test files | **0** |

---

## 4. Concurrency implementation verified

Read from `backend/app/services/maintenance_slot_store.py` at the exact head.

| Requirement | Verified | Evidence |
|---|---|---|
| Conditional UPDATE | **yes** | `_guarded_claim()` (line 95) builds `UPDATE ... WHERE slot_id = :slot AND state IN (:states)` against the **Core table**, so the database evaluates the predicate |
| Rowcount determines winner | **yes** | `claim_slot()` line 330: `if result.rowcount == 1: → claimed=True`; otherwise `_classify_lost_claim(...)`. `attempt = attempt + 1` is computed by the database |
| 8 real contenders / distinct connections | **yes** | `CONTENDERS = 8`; each thread opens its own session/connection; `threading.Barrier(CONTENDERS, timeout=60)`; the harness asserts `len(per_thread) == CONTENDERS` |
| Exactly one winner | **yes** | `test_exactly_one_winner_and_seven_losers`, `test_exactly_one_active_owner_is_recorded`, `test_repeated_races_keep_producing_one_winner`; `CLAIMED` is never in the claimable set, so an active lease is structurally unreachable |
| Lease recovery race safe | **yes** | `recover_slot()` is `claim_slot()` with the claimable set narrowed to `EXPIRED` — same conditional UPDATE, same single-winner guarantee. `test_exactly_one_recovery_wins`, `test_a_recovery_race_does_not_reopen_the_slot` |
| Sweep cannot overtake an active claim | **yes** | `expire_stale_claims()` is one conditional UPDATE with `state == CLAIMED AND lease_until IS NOT NULL AND lease_until <= :as_of`; a future lease does not match. `test_sweep_does_not_overtake_an_active_claim` |

Supporting correctness details present: `transition_slot()` derives permitted
predecessors from the pure core's `LEGAL_TRANSITIONS` and puts them in the
`WHERE` clause, so the database decides legality. `_insert_if_absent()` uses
native `ON CONFLICT DO NOTHING` for both `postgresql` and `sqlite` and **raises**
for any other dialect rather than falling back to select-then-insert. Naive
datetimes are rejected. `read_slot()` uses `populate_existing` so a cached
identity-map value cannot disagree with what the guarded UPDATE wrote.

---

## 5. Isolated release gates on the exact head

All run in the worktree detached at `ef2a137`.

| Gate | Composition | Required | Result |
|---|---|---|---|
| Phase A | slots(43) + persistence(57) + concurrency(16) | 116 | **116 passed** |
| Phase B | dispatch_phase_b | 43 | **43 passed** |
| Combined maintenance | the above + autonomous(50) + worker(11) + image-constants(16) | 236 | **236 passed** |
| Provenance / release / vercel / hardening | build_provenance(44) + vercel_migration(41) + release_identity_gate(46) + final_hardening(53) | 184 | **184 passed** |
| `py_compile` on all 13 changed Python files | — | PASS | **exit 0** |

### Frontend

| Gate | Result |
|---|---|
| `npm run lint` | **exit 0** — 0 errors, 1 warning |
| `npm run build` | **exit 0** — 546 modules, built in 531 ms |

The single lint warning is `react-hooks/exhaustive-deps` in
`frontend/src/pages/HomePage.jsx:259`. `frontend/` has **0 changed files** in this
PR, so that warning is pre-existing on master. The build emits only a
chunk-size advisory (>500 kB). Neither is a gate failure.

### Cross-suite isolation probes

The two sequences that failed the earlier independent audit:

| Sequence | Result |
|---|---|
| `test_maintenance_slot_persistence.py` → `test_stats_universe_scope.py` | **74 passed** |
| `test_maintenance_dispatch_phase_b.py` → `test_stats_universe_scope.py` | **60 passed** |

No contamination, and no `PermissionError [WinError 32]` teardown errors.

---

## 6. Full backend regression and failure fingerprint

Identical invocation in both cases: `python -m pytest` from a clean `backend/`,
project venv, per-run `--basetemp`, no untracked artifacts present.

| Tree | passed | failed | skipped | errors |
|---|---|---|---|---|
| PR head `ef2a137` | 5238 | 9 | 10 | 1 |
| master `cfd0aca` (baseline) | 5079 | 9 | 10 | 1 |

`Compare-Object` on the two failure sets: **0 only-on-PR, 0 only-on-master — the
sets are identical.**

Skipped sets also identical (7 unique reasons on both). **0 existing test files
modified** by the PR; 4 test files added; **zero `skip`/`xfail` markers** in the
four new test files. No failure was hidden.

### The 9 baseline failures + 1 error — all pre-existing/environmental

- **`test_neon_migration.py` ×8** — ENVIRONMENT. `backend/migration_export.sql`
  is gitignored (`.gitignore`) and untracked, and nothing under `.github/`
  generates it, so a clean checkout cannot pass these. Previously proven: copying
  the artifact makes the file report 138 passed.
- **`test_efficiency_safety.py::TestRetryPolicy::test_the_retry_shares_the_concurrency_group`**
  — ENVIRONMENT. `PyYAML` is absent from `backend/requirements.txt` and from
  `backend/.venv`. Previously proven: the same test passes under an interpreter
  that has PyYAML and fails under the project venv.
- **`scripts/artifact_smoke_test.py::test_endpoint`** — 1 collection ERROR on both
  trees. `backend/pytest.ini` (which sets `testpaths = tests`) is untracked, so a
  clean checkout finds no ini and collects `*_test.py` under `backend/scripts/`.

---

## 7. `origin/master` moved during verification — handled before merging

`origin/master` advanced from `cfd0aca` to **`22cf31d`** (PR #10, supervisor
discovery) partway through verification. `22cf31d` is a descendant of `cfd0aca`,
so it is a fast-forward of the same lineage, not a divergent rewrite.

Two files that PR #7 touches were also changed by the new master:
`backend/app/database.py` and `backend/app/main.py`.

Because the merge result had never been tested, I did **not** merge on the
strength of the PR-head results alone. Instead:

1. Dry-run conflict detection: `git merge-tree --write-tree` → clean, exit 0.
2. A real merge was performed in a throwaway worktree and committed:
   `0d6b420a` with parents `22cf31d` + `ef2a137`, **0 conflicts**.
3. That merged tree was regression-tested against a fresh baseline of the new
   master:

| Tree | passed | failed | skipped | errors |
|---|---|---|---|---|
| new master `22cf31d` (baseline) | 5306 | 9 | 10 | 1 |
| **merged tree `0d6b420a`** | **5465** | **9** | **10** | **1** |

Failure sets **identical** → **zero new regressions**, and +159 passing tests
(116 + 43) from PR #7.

`origin/master` was then confirmed not to have moved again, PR #7 was confirmed
`MERGEABLE` / `mergeStateStatus: CLEAN`, and the merge proceeded.

---

## 8. Merge executed and proved

```
gh pr merge 7 --merge --delete-branch=false     → exit 0
```

No force-push, no rebase, no history rewrite, no branch deletion.

```
new origin/master = 804133c45cfbf1d52b7b907b91191c6c789d068c
804133c Merge pull request #7 from gopal735/feat/maintenance-phase-b-rebased
parents: 22cf31d38014d43ab70dca98eeb0285db6513aaf ef2a1375bb1a14959c2575ced3f73b9437e5604d
```

- `ef2a137` **is a parent** of `804133c` — proven by
  `git merge-base --is-ancestor ef2a137 804133c` (exit 0).
- All 7 Phase A/B files present in the new master tree.
- `maintenance_slot_store.py` present, `maintenance_slots.py` present,
  superseded `maintenance_slot.py` absent.
- A fresh worktree at `origin/master` was created at `804133c` and confirmed equal
  to `origin/master`.

---

## 9. Post-merge regression on the new master

Run in a clean worktree at `804133c`.

| Gate | Result |
|---|---|
| Phase A | **116 passed** |
| Phase B | **43 passed** |
| Combined maintenance | **236 passed** |
| Provenance / release / vercel / hardening | **184 passed** |
| `test_stats_universe_scope.py` (contamination probe) | **17 passed** |

Full backend regression on the new master, in the clean worktree at `804133c`:

| Tree | passed | failed | skipped | errors |
|---|---|---|---|---|
| `22cf31d` (pre-merge master) | 5306 | 9 | 10 | 1 |
| **`804133c` (post-merge master)** | **5465** | **9** | **10** | **1** |

Failure sets **identical** → **0 new regressions, 0 disappeared**. +159 passing
tests. The post-merge count also matches the pre-merge simulated-merge result
(`0d6b420a`: 5465 / 9 / 10 / 1), so the tree that landed is byte-for-byte the tree
that was tested.

---

## 10. Final gate checklist

| Gate condition | Status | Evidence |
|---|---|---|
| PR head remained stable through complete verification | **PASS** | `ef2a137` at start, after gates, and pre-merge |
| Exact head is the tested head | **PASS** | worktree detached at exact SHA; tested there and as a merge |
| Required CI checks green on that exact head | **PASS** | `backend-tests`, `build-and-smoke`, `env-config`, `frontend-lint`, `frontend-tests`, `git-integrity`, `import-smoke`, `preflight`, `schema-compat`, 4× Vercel — all `pass` |
| Complete diff understood | **PASS** | 16 files classified; 0 unrelated; 0 deletions |
| No unrelated regression exists | **PASS** | failure fingerprint identical to master on head and on merged tree |
| `origin/master` remains compatible | **PASS** | `22cf31d` is a descendant of `cfd0aca`; clean merge; merged tree tested green |
| No force-push / history rewrite required | **PASS** | ordinary `--merge` |
| No test weakened | **PASS** | 0 existing tests modified; 0 skip/xfail; skip sets identical |
| No superseded architecture restored | **PASS** | no `99fab60` artefacts: grep for `TestAtomicClaim`, `_take_ownership`, `non_atomic_take`, `active_claim_winner` → 0 hits |

---

## 11. Recorded caveats — stated, not absorbed

### Docker: UNVALIDATED

Docker is not installed on this machine (`docker: command not found`). The
container/smoke gate could not be executed. This is an environment limitation, not
a code result, and **is not counted as a pass**. Note that the repository's own CI
`build-and-smoke` and `import-smoke` checks **did** pass on the exact head.

### PostgreSQL equivalence: UNKNOWN

No PostgreSQL server is reachable (nothing listening on 5432, no Docker).
`psycopg` 3.3.4 is installed, and the implementation is written to be
dialect-agnostic — `_insert_if_absent()` uses native `ON CONFLICT DO NOTHING` for
both backends and raises for unknown dialects, and the claim/expiry/transition
statements are plain conditional `UPDATE`s with no `SELECT FOR UPDATE` and no
SQLite-specific behaviour. But this has **not been proven at runtime against
PostgreSQL**, so equivalence remains **UNKNOWN**.

### Known test-quality gap — TEST HARDENING FOLLOW-UP (not a merge blocker)

`backend/tests/test_maintenance_slot_concurrency.py` contains **no
forced-interleave / non-vacuity control**. It verifies that eight concurrent
callers produce one winner, which is strong, but it does not prove the harness
*would* fail against a non-atomic implementation.

Why that matters, concretely: on SQLite a read-then-write claim can pass this
suite, because SQLite grants one writer at a time and the write lock usually
closes the read→write window. That is precisely why an earlier audit observed the
same defect surviving isolated runs and only failing under load. A guard that is
only proven green can silently regress.

Suggested follow-up, additive and test-only (it must not replace the persistence
architecture):

1. **Forced-interleave control** — hold every contender's first `UPDATE` at a
   barrier so all eight finish reading before any writes, then assert exactly one
   winner. This must stay green with the conditional `UPDATE` and go red without it.
2. **Injected read-then-write control** — monkeypatch the claim primitive with the
   historical read-then-write and require it to produce eight winners, proving the
   harness can detect the defect it guards.
3. Record the mutation evidence: removing the guard must turn both red (repeatable
   5/5), with the guard present they must stay green (repeatable 5/5).

### Pre-existing ambient-database behaviour (master, not this PR)

`backend/tests/test_autonomous_maintenance.py` creates `backend/scholarzone.db`
in the checkout when run in a short process. Proven by running each gate in
isolation:

| Gate | Ambient file created |
|---|---|
| Phase A (116) | no |
| Phase B (43) | no |
| autonomous_maintenance (50) | **yes** (532,480 bytes) |
| maintenance_worker (11) | no |
| maintenance_image_constants (16) | no |
| provenance/release/vercel (184) | no |

`test_autonomous_maintenance.py` has **0 changes in this PR**, so this is
pre-existing master behaviour and is reported separately, not attributed to PR #7.

Two further pre-existing repository-hygiene items, unchanged by this PR:

- `backend/pytest.ini` is **untracked**, so `testpaths = tests` is not enforced in
  a clean checkout and `scripts/artifact_smoke_test.py` errors at collection.
  Committing it would remove that ERROR.
- `backend/migration_export.sql` is **gitignored and untracked** and nothing in CI
  generates it, which is why 8 `test_neon_migration` tests cannot pass in CI.
- `PyYAML` is not declared in `backend/requirements.txt` although one test imports
  it, which is why that test cannot pass in a clean venv.

---

## 12. Post-merge CI on master, and a pre-existing deployment-pipeline failure

`ScholarZone CI` on `master` at `804133c`: **success** (2m16s).

A separate workflow, **"ScholarZone Native GitHub Deployment Verification"**,
reports **failure**. This is **pre-existing and not caused by PR #7**, proven by
running it on both sides of the merge:

| Run | head SHA | Expected revision | Health endpoint reported | Result |
|---|---|---|---|---|
| 37279870729 (07:49Z, **before** merge) | `22cf31d` | `22cf31d` | HTTP 200, `{"status":"ok","revision":"cfb2b54"}` | `::error::Timed out waiting for the expected build to go live.` |
| 37282873362 (08:19Z, **after** merge) | `804133c` | `804133c` | HTTP 200, `{"status":"ok","revision":"cfb2b54"}` | `::error::Timed out waiting for the expected build to go live.` |

The failure is identical before and after the merge: production is **healthy**
(HTTP 200, `status: ok`) but continues to serve revision **`cfb2b54`**, a commit
that predates `cfd0aca`, while new master revisions never go live. The workflow
retried 40×15 s and timed out both times.

Two consequences worth stating plainly:

1. **PR #7 did not cause this.** It failed identically on `22cf31d`, which
   contains none of PR #7's changes.
2. **Production is NOT running PR #7.** The live revision is still `cfb2b54`, so
   no production activation happened as a result of this merge. That satisfies the
   instruction to stop before production activation — but for an operational
   reason, not by design. The deployment pipeline appears unable to publish any
   revision newer than `cfb2b54`, and that is a separate pre-existing issue for the
   owner to triage. Nothing in this report should be read as a claim that PR #7 is
   live.

---

## 13. Stop point

Work stopped after the post-merge regression. **Production activation was NOT
performed and no production data was written.** No deployment was triggered, no
Vercel promotion, no workflow dispatch, no activation flag enabled.

**MERGE_READY** — PR #7 is merged into `origin/master` at
`804133c45cfbf1d52b7b907b91191c6c789d068c` with the exact tested tree
`ef2a137` as a parent. Post-merge full backend regression on the new master:
**5465 passed / 9 failed / 10 skipped / 1 error**, failure set identical to the
pre-merge master baseline.
