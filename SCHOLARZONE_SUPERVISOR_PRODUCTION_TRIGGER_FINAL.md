# SCHOLARZONE_SUPERVISOR_PRODUCTION_TRIGGER_FINAL

One deliberately bounded production execution path for Supervisor discovery:
`workflow_dispatch` → one integer scholarship id → one authenticated internal
HTTP call → classify with no database in scope → persist only what survived →
commit once.

Nothing is deployed. No production write has occurred. The first production run
requires explicit owner authorisation.

---

## 1. Exact base / master SHA

| Role | SHA | Note |
|---|---|---|
| **Base this candidate was built on** | `1a552a929881953038400e7ef45487384a6df320` | `origin/master` at the time the isolated worktree was created. Merge of PR #13, `fix/supervisor-inline-role-evidence`. |
| **Candidate** | `0092b5d20b87458b65e148ed0575cfe55071ce6b` | branch `feat/supervisor-production-trigger`, committed, **not pushed**. |
| **`origin/master` at report time** | `9cebca7bf0e011cec5e9ed96715a4489dd64bef1` | moved forward *during* this task, by work unrelated to it. |

`git merge-base HEAD origin/master` = `1a552a9`, so the candidate sits directly
on the base with nothing of its own underneath it.

**Merge-safety note.** `git diff --name-only 1a552a9 9cebca7` over every file this
change touches returns **nothing**. None of the four modified or five added files
moved upstream, so rebasing onto current master is expected to be conflict-free.
This was verified, not assumed.

The primary working tree was **not touched**. Local `master` there is at
`8ac1c9a` and is 116 commits behind `origin/master`; that dirty tree was left
exactly as found. All work happened in a fresh isolated worktree at
`C:\Users\GopaL\AppData\Local\Temp\kilo\sz-supervisor-trigger`.

---

## 2. Changed files

**Modified (4)**

| File | Change |
|---|---|
| `backend/app/services/supervisor_discovery.py` | The refactor. `discover_for_scholarship` split into `collect_supervisor_plan` (no session, no writes) + `persist_supervisor_plan` (the only writer, one commit). Render path converted to `_collect_render_for_shells`. Host vocabulary re-exported from the new gate module. |
| `backend/app/core/config.py` | One `Settings` field and one read: `supervisor_discovery_enabled`. Default `False`. |
| `backend/app/main.py` | One import, one `include_router`, with the ordering rationale. |
| `backend/app/services/supervisor_person.py` | One added public predicate, `name_is_person_shaped`, plus its `__all__` entry. Purely additive; no existing behaviour changed. |

**Added (5)**

| File | Purpose |
|---|---|
| `backend/app/services/supervisor_gating.py` | The six gates. **Pure** — no ORM, no session, no module-level mutable state. |
| `backend/app/routers/supervisor_internal.py` | `POST /internal/supervisor/discover/{scholarship_id}`. |
| `.github/workflows/supervisor-discovery-proof.yml` | The dispatch-only proof. |
| `backend/tests/test_supervisor_persistence_boundary.py` | 34 tests: the no-write boundary (A–J) + regression guards. |
| `backend/tests/test_supervisor_production_trigger.py` | 47 tests: endpoint bounds, auth, flag, workflow. |

Diffstat against the base: **4 files changed, 520 insertions(+), 192 deletions(-)**
plus the five new files.

No dependency was added. `requirements.txt` is untouched. No Playwright was
added to any runtime.

---

## 3. Old Supervisor call graph (at `1a552a9`)

```
scripts/supervisor_backfill.py            manual, needs database credentials
  └─ run_discovery_batch(db, limit, max_workers, force)          [:1364]
       └─ ThreadPoolExecutor(max_workers=...)
            └─ _discover_one(scholarship)                        [:1402]
                 ├─ get_session_factory()()          own session, own commit
                 └─ discover_for_scholarship(session, row)       [:1174]
                      │
                      ├─ ensure_coverage_row(db, id)             [:1185]
                      │     └─ db.add(...) ; db.flush()          <-- WRITE #1, before any gate
                      │
                      ├─ [no seed URLs]
                      │     ├─ db.commit()                        [:1188]
                      │     └─ recompute_coverage(searched=True) [:1189]
                      │
                      ├─ [seed host not institutional]
                      │     ├─ mutate coverage row               [:1198-1201]
                      │     └─ db.commit()                       [:1202]
                      │
                      ├─ seed loop: polite_fetch + anchor scan -> faculty_pages (<=3)
                      │
                      ├─ per faculty page:
                      │     ├─ polite_fetch(faculty_url)
                      │     ├─ extract_faculty_candidates()      [:581]  (network only)
                      │     ├─ _persist_candidates()             [:1247]
                      │     │     ├─ upsert_professor()  -> db.add + db.flush()
                      │     │     ├─ upsert_link()
                      │     │     ├─ record_evidence()
                      │     │     └─ record_availability()
                      │     └─ db.commit()                       [:1258]  <-- commit per page
                      │
                      ├─ [directory behind sign-in]
                      │     ├─ ensure_coverage_row + mutate      [:1274-1282]
                      │     └─ db.commit()                       [:1283]
                      │
                      ├─ [client-side shell]
                      │     └─ _attempt_render_for_shells(db, ...)[:1306]
                      │           ├─ render_blocking()            <-- browser
                      │           ├─ _persist_candidates()        [:1093] <-- WRITES mid-collection
                      │           └─ db.commit()                  [:1104]
                      │
                      └─ recompute_coverage(searched, blocked)   [:1334]
                            ├─ mutate coverage row
                            ├─ db.commit()                        [:192 in supervisor_coverage]
                            └─ db.refresh(row)
```

The defect this task set out to fix is visible on line 1 and again in the
per-page loop: a coverage row is **flushed** before any candidate has been
classified, and each page of a multi-page directory is **committed** before the
run's outcome is known. The gating decision was buried inside the fetch loop, so
no external caller could enforce a final candidate-validation gate.

---

## 4. New bounded call graph

```
GitHub Actions: "Supervisor Discovery Proof"  (workflow_dispatch ONLY)
  input: scholarship_id  (required, digits-validated)
  │
  └─ POST $SCHOLARZONE_API_URL/internal/supervisor/discover/$TARGET_SCHOLARSHIP_ID
       header: X-Verification-Secret: $SCHOLARZONE_VERIFICATION_SECRET
       │
       ├─ require_verification_secret()                    supervisor_internal.py
       │     secrets.compare_digest, fails closed, 401
       ├─ _require_discovery_enabled()                     503 unless
       │     SCHOLARZONE_SUPERVISOR_DISCOVERY_ENABLED is true
       ├─ db.get(Scholarship, id)                         exactly one; 404 if absent
       │
       ├─ collect_supervisor_plan(scholarship)             <-- NO SESSION ARGUMENT
       │     │                                                 ZERO write verbs
       │     ├─ scholarship_seed_urls()
       │     ├─ polite_fetch(seed)  -> faculty_pages (<=3)
       │     ├─ polite_fetch(faculty_url)
       │     ├─ extract_faculty_candidates()
       │     │     └─ polite_fetch(each profile)
       │     │           └─ academic_role_in(profile_text)
       │     │              -> role_evidence = "profile_role"
       │     ├─ approve_candidate_set(...)                 supervisor_gating  PURE
       │     │     ├─ verify_supervisor_candidate() x N
       │     │     │     personhood -> role -> institutional domain
       │     │     │     -> provenance -> normalization
       │     │     └─ duplicate check (normalised profile URL,
       │     │            shared across pages of the run)
       │     ├─ [sign-in wall]  -> CoverageOverride, return
       │     └─ _collect_render_for_shells()   no render budget passed
       │           -> approved group, OR an inconclusive status
       │
       └─ persist_supervisor_plan(db, scholarship, plan)   <-- THE ONLY WRITE PATH
             ├─ per group: persist_approved_candidates()
             │     requires ApprovedSupervisorCandidate, else TypeError
             │     ├─ upsert_professor()
             │     ├─ upsert_link()
             │     ├─ record_evidence()
             │     └─ record_availability()
             ├─ coverage_override set? -> ensure_coverage_row + apply + db.commit()
             │                            (no professor rows are written)
             └─ otherwise              -> recompute_coverage() -> db.commit()
```

`discover_for_scholarship` (the pre-existing entry point, used by the backfill
script and by the existing tests) is now exactly:

```python
plan = collect_supervisor_plan(scholarship, render_budget)
return persist_supervisor_plan(db, scholarship, plan)
```

Collect strictly before persist — asserted on the AST in
`test_discover_for_scholarship_collects_before_it_persists`, not merely in a
comment.

---

## 5. Proof that the old production trigger was absent

`git grep` over `backend/app`, `backend/scripts` and `.github` at `1a552a9`, for
every Supervisor entry point:

| Symbol | Non-test callers at `1a552a9` |
|---|---|
| `discover_for_scholarship` | **none** — only tests, and its own definition |
| `run_discovery_batch` | `backend/scripts/supervisor_backfill.py:233` |

`scripts/supervisor_backfill.py` is a manual script: it needs a database
credential, it is not invoked by CI, and it is not reachable over HTTP. No router
imported `supervisor_discovery` at all. `backend/app/routers/supervisors.py` is
the only Supervisor router and it is **read-only and unauthenticated by design**
— `list_supervisors` and `supervisor_summary` return public data and write
nothing.

**Conclusion: there was no production Supervisor trigger.** Not a disabled one,
not a guarded one — none.

### The country route belongs to a different subsystem and was not reused

`POST /internal/discover/country/{country}` → `discover_country_scholarships`
(`backend/app/routers/discovery.py:149`) queries `ApprovedSource.country` and
creates **`DiscoveryCandidate`** rows for *new scholarships*. Its own module
docstring reads "Country-scoped new scholarship discovery". It is the
new-scholarship discovery subsystem, a different pipeline with a different
purpose. This change does not import, call, extend or reuse it, and
`test_it_does_not_reach_the_scholarship_discovery_subsystem` fails if the names
`DiscoveryCandidate`, `run_discovery_round` or `run_discovery_batch` appear in
the new router.

### verification-cron's discover stage is not Supervisor

`.github/workflows/verification-cron.yml` runs
`python -m app.jobs.scholarzone_maintenance` (lines 158, 278) directly against
`SCHOLARZONE_DATABASE_URL`. It imports no router and makes no HTTP call; its own
comment (lines 134–142) states the verification and admin secrets are
deliberately withheld from it. `POST /internal/discover/trigger`
(`routers/verification.py:191`) calls `run_discovery_round` — again the
new-scholarship discovery round, not Supervisor.

**No Supervisor execution path existed inside maintenance.** Rule 13 and 14 are
satisfied: Supervisor remains fully separate, and neither the maintenance worker
nor the scheduler nor the cron file was modified (verified in §16).

---

## 6. Authentication design

The repository already had a convention, so no second philosophy was invented.

| Property | Choice | Why |
|---|---|---|
| Credential | `SCHOLARZONE_VERIFICATION_SECRET` | The existing repository secret. **No new credential, no rotation, no value ever read.** |
| Transport | `X-Verification-Secret` request header | The convention already used by `/internal/verify/trigger` and `/internal/discover/*`. |
| Comparison | `secrets.compare_digest` | Matches `routers/verification.py:56` and `core/admin_auth.py:40`. A plain `==` leaks length and prefix through rejection timing. |
| Header, not query | asserted | A query parameter would land in access logs and browser history. `test_the_secret_is_compared_in_constant_time` fails if `Query(` appears in the router. |
| Failure mode | `401`, fails closed | An unconfigured deployment admits **nobody**, including the owner. `test_an_unconfigured_deployment_admits_nobody`. |
| Never a body field | asserted | `test_it_takes_one_path_parameter_and_no_body` asserts the OpenAPI operation has **no `requestBody` at all**. |

### Two independent conditions, deliberately not merged

Both must hold:

1. the caller presents the verification secret → *is this caller authorised?*
2. `SCHOLARZONE_SUPERVISOR_DISCOVERY_ENABLED` is on → *is this capability switched
   on here?*

Merging them is how a capability silently becomes live in production because
somebody rotated a credential. With them separate, a valid secret held against a
deployment that never enabled the feature is still refused —
`test_a_valid_secret_is_still_refused_while_it_is_off` asserts `503`.

**Check order:** authenticate → feature flag → resolve target. A caller without
the secret learns nothing about whether the feature exists, and a disabled
deployment spends no work resolving a scholarship, so an unauthenticated probe
cannot be used to enumerate valid ids.

---

## 7. `workflow_dispatch` design

`.github/workflows/supervisor-discovery-proof.yml`, name **Supervisor Discovery
Proof**.

| Requirement | Implementation | Asserted by |
|---|---|---|
| `workflow_dispatch` only | sole trigger | `test_workflow_dispatch_is_the_only_trigger` |
| No schedule / push / PR / repository_dispatch | absent | `test_there_is_no_schedule_and_no_matrix` |
| No matrix | no `strategy:` | same |
| One scholarship per run | one input, `scholarship_id` | `test_it_takes_exactly_one_input_and_validates_it` |
| Explicit input validation | `grep -Eq '^[0-9]+$'`, plus a `>= 1` bound | same |
| No country input, no URL input | the input is digits-only; the endpoint takes no body | same + `test_it_calls_only_the_bounded_endpoint` |
| Secret at runtime only | job-level `env:`; **no `${{ }}` inside any `run:` block** | `test_the_secret_is_not_interpolated_into_a_command_line` |
| Secret never printed | no `set -x`, no `curl -v`, no `--value`, no echo of the expansion, header never echoed | 5 separate tests |
| No production DB credential | `SCHOLARZONE_DATABASE_URL` absent from the file | `test_it_is_never_given_the_database_url` |
| Minimal permissions | `permissions: contents: read` | `test_permissions_are_minimised_and_a_timeout_is_set` |
| Explicit timeout | `timeout-minutes: 20` | same |
| Concurrency protection | `group: supervisor-discovery-proof`, `cancel-in-progress: false` | `test_it_has_concurrency_protection` |
| Loud failure | `set -euo pipefail`; non-200 → `::error::` + `exit 1`; ≥3 explicit exits | `test_failure_is_loud_and_non_zero` |
| Host from configuration | `vars.SCHOLARZONE_API_URL`, fails closed when unset; no literal hostname anywhere | `test_the_host_comes_from_a_repository_variable_not_a_literal` |

Concurrency **queues rather than cancels**: two concurrent runs would interleave
their coverage writes for the same scholarship and make the before/after row
counts unreadable, and cancelling a proof in flight would destroy the evidence it
was run to collect.

The workflow receives exactly three environment values and nothing else: the API
host (a repository *variable* — a public hostname), the secret, and the target
id. It does not receive or know the production database URL, needs no schema
access, and makes exactly one HTTPS request.

---

## 8. Exact scope boundary

What the endpoint **cannot** do. Each row is an absence of code, and each has a
test that fails if the capability appears:

| Capability | How it is prevented | Test |
|---|---|---|
| Country-wide discovery | No country parameter; no body; the path takes one integer | `test_a_country_cannot_be_a_target` |
| Batch / multi-target | One integer, `minimum: 1`, in the schema | `test_a_list_of_targets_cannot_be_passed` |
| Arbitrary URL submission | No body; source read from the scholarship's own record | `test_it_takes_one_path_parameter_and_no_body` |
| Maintenance dispatch | Import-closure assertion | `test_the_router_does_not_import_maintenance_or_scheduler_code` |
| Scheduler execution | same | same |
| Verification cron | same | same |
| Browser / Playwright activation | No `supervisor_render` import, no `RenderBudget`, no environment mutation | `test_it_does_not_enable_rendering` |
| Scholarship `DiscoveryCandidate` seeding | Name-absence assertion | `test_it_does_not_reach_the_scholarship_discovery_subsystem` |
| Widening scope on the other side | Only the target scholarship's coverage row is written | `test_it_does_not_touch_any_other_scholarship` |
| Login / CAPTCHA / anti-bot bypass | None attempted; the renderer's access-barrier path is untouched and still returns `SOURCE_BLOCKED` without retrying | pre-existing, unchanged |
| Second external host | Exactly one `/internal/...` path and one `curl` in the file | `test_it_calls_only_the_bounded_endpoint` |

The whole internal Supervisor surface is **one operation**. Asserted against the
generated OpenAPI document:
`test_no_supervisor_route_can_broaden_the_scope`.

---

## 9. Persistence architecture, before and after

### Before

```
discover_for_scholarship()
    -> ensure_coverage_row()        db.add + db.flush     <-- write, pre-gating
    -> [branch] db.commit()
    -> for each faculty page:
           extract_faculty_candidates()
           _persist_candidates()    professors, links,
                                     evidence, availability
           db.commit()                                  <-- write, per page
    -> recompute_coverage()         db.commit() + refresh
```

### After

```
collect_supervisor_plan(scholarship)            NO SESSION, NO WRITES
    -> polite_fetch / extract / classify
    -> approve_candidate_set()                   all six gates
    -> SupervisorDiscoveryPlan(...)              the complete final answer

persist_supervisor_plan(db, scholarship, plan)   THE ONLY WRITER
    -> persist_approved_candidates()  per group  (ApprovedSupervisorCandidate only)
    -> coverage, at the same single boundary
    -> db.commit()  once
```

The architectural change is that **the decision is separated from the ability**.
`collect_supervisor_plan` does not take a `db` argument, so there is no session
for it to write through. `persist_approved_candidates` raises `TypeError` on
anything that is not an `ApprovedSupervisorCandidate`, so the gate is enforced by
the type system rather than by discipline.

### Two functions carry their own writes

`persist_approved_candidates` deliberately delegates to the pre-existing
`upsert_professor` / `upsert_link` / `record_evidence` / `record_availability`
helpers, which each `flush()`. Those flushes are *inside* the single transaction
that `persist_supervisor_plan` commits once — they are how IDs become addressable
for the rows that follow, not separate transactions. `collect_supervisor_plan`
and `_collect_render_for_shells` contain **zero** `commit`/`flush`/`add`/
`execute`/`merge`/`delete` calls, verified by AST walk over the real source.

### Behaviour preserved

`discover_for_scholarship` keeps its signature, its return type and its branch
semantics — including the long-standing asymmetry where a scholarship with no
recorded source URL *reports* `search_pending` while *storing*
`no_verified_supervisor_found`. Every existing Supervisor test passes unchanged,
which is the evidence that this is a refactor rather than a rewrite.

`_persist_candidates` is **retained**, with a corrected docstring, as the
low-level writer that still re-applies both `91bcdb5` storage gates before it
writes. It is no longer on the production path, but it is the second line of
defence that survives the gate module being replaced by something simpler, and it
is what the existing storage-gate test exercises.

---

## 10. No-write gating proof

34 tests in `test_supervisor_persistence_boundary.py`.

| # | Requirement | Test | Result |
|---|---|---|---|
| **A** | Collection with zero DB writes | `test_collecting_a_real_directory_writes_nothing` — asserts 2 candidates approved **and** 0 professors / 0 links / 0 coverage rows | PASS |
| **A** | Collection *cannot* write | `test_collection_needs_no_session_argument_at_all` — signature is exactly `{scholarship, render_budget, official_host_check}` | PASS |
| **A** | The gate module is pure | `test_the_gate_module_cannot_import_the_database_at_all` — subprocess with the SQLAlchemy importer poisoned; import fails if the DB layer is reachable. Verified at runtime too: importing `supervisor_gating` loads **zero** `sqlalchemy` modules | PASS |
| **B** | Personhood failure → zero persistence | `test_b_personhood_failure_produces_zero_persistence`; attribution pinned independently by `test_b_role_restated_as_a_name_is_refused_by_the_personhood_gate` | PASS |
| **C** | Role failure → zero persistence | `test_c_personhood_proven_but_role_not_proven_is_not_stored` — the real Cornell shape | PASS |
| **D** | Institutional-domain failure → zero persistence | `test_d_off_institution_domain_produces_zero_persistence`; attribution pinned by `test_d_off_domain_is_refused_by_the_gate_in_isolation` | PASS |
| **E** | Mixed batch persists only the valid | `test_e_a_mixed_batch_persists_only_the_valid_candidates` (1 approved / 5 examined / 4 rejected, per-gate histogram sums exactly) **and** `test_e_a_mixed_run_persists_only_the_valid_candidates` end-to-end | PASS |
| **F** | All-invalid batch → zero new rows | `test_f_a_wholly_invalid_run_creates_no_supervisor_rows` — 0 professors, 0 links | PASS |
| **F** | The honest negative is still recorded | `test_f_a_wholly_invalid_run_still_records_what_it_learned` — coverage = `no_verified_supervisor_found`, count 0 | PASS |
| **G** | Re-running is idempotent | `test_g_rerunning_the_same_discovery_is_idempotent` — professor, link and coverage counts identical; stored count recomputed from links, never incremented | PASS |
| **H** | Existing valid rows survive a failed run | `test_h_existing_valid_rows_survive_a_later_failed_candidate` | PASS |
| **H** | No partial rows for a refusal | `test_h_a_refused_candidate_leaves_no_partial_row` — 0 rows in `professor_profiles`, `scholarship_professor_links`, `supervisor_source_evidence`, `professor_availability` | PASS |
| **I** | Coverage at the correct boundary only | `test_i_nothing_is_committed_until_the_persistence_boundary` — a `db.commit` spy installed across both stages: **0 commits** during collection, ≥1 at the boundary | PASS |
| **I** | No coverage row mid-collection | `test_i_coverage_is_updated_at_the_boundary_and_not_before` | PASS |
| **J** | No hidden `commit()` pre-gating | `test_j_the_persistence_function_refuses_an_unapproved_candidate` — a raw candidate raises `TypeError`, 0 rows written | PASS |
| **J** | The two types are distinct | `test_j_an_approved_candidate_is_a_distinct_type_from_a_raw_one` | PASS |

### Regression guards on code *shape*

Behaviour is what must be true; these stop it being silently un-true by a later
individually-reasonable edit.

| Guard | Assertion |
|---|---|
| `test_collection_functions_call_no_write` (×5) | None of `collect_supervisor_plan`, `approve_candidate_set`, `verify_supervisor_candidate`, `extract_faculty_candidates`, `_collect_render_for_shells` calls `commit`/`flush`/`execute`/`merge`/`delete`, **and none references a name `db` or `session`** |
| `test_discover_for_scholarship_collects_before_it_persists` | AST call order: `collect_supervisor_plan` index < `persist_supervisor_plan` index |
| `test_discover_for_scholarship_does_not_write_directly` | The public entry point contains no write verb at all |
| `test_the_write_path_is_identified_and_bounded` | The set of functions in the module that call `commit` is a **subset of exactly** `{persist_supervisor_plan, _discover_one}` — any new commit anywhere fails |
| `test_no_coverage_row_is_written_by_the_collect_stage` | `ensure_coverage_row` is unreachable from `collect_supervisor_plan` |

The "only these two functions may commit" guard is the direct answer to "do not
assume `discover_for_scholarship` is the only persistence path": it is a
whole-module allowlist, so a write added anywhere else fails the suite.

---

## 11. Complete gate list

`SupervisorGate`, in reporting order. `primary_failure` is the **earliest**
failure, so a rejection is attributed to its most fundamental cause.

| # | Gate | Asks | Fails when |
|---|---|---|---|
| 1 | `PERSONHOOD` | Does this name claim an **individual**? | No name; not person-shaped; **or the name is only the role written out** (`"Academic Staff"` with role `"academic"`) |
| 2 | `ROLE_EVIDENCE` | Did the institution state an academic role, by a route this product recognises? | `role is None`; `role_evidence` is not one of `{honorific, inline_role, source_context, profile_role}`; **or a role was claimed with no recorded mechanism at all** |
| 3 | `INSTITUTIONAL_DOMAIN` | Is the profile on the **awarding institution's own academic domain**? | No host; not the same registrable domain as the seed; or the host is not academic |
| 4 | `PROVENANCE` | Is there something to **re-verify against**? | No readable source URL; source not published by that institution; or the profile URL is not an absolute `http(s)` URL |
| 5 | `NORMALIZATION` | Does the identity survive to a stable key? | Name or profile URL normalises to an empty key |
| 6 | `DUPLICATE` | Already approved earlier in this run? | Normalised profile URL already in the run's `seen_urls` |

Gate 7 (product-specific verification status) is not a pass/fail gate but a
**derived output**: `verification_status_for(candidate)` returns `VERIFIED` only
when a role was stated *and* the name is not merely that role restated. A caller
cannot supply a status; it is computed from the evidence.

Keyed on the **normalised profile URL** for duplicates, which is the same key as
the `uq_professor_official_profile_url` unique constraint — so the in-run check
and the durable check cannot disagree. Name normalisation is deliberately *not*
the duplicate key: two distinct people can share a name, and collapsing them
would delete a real professor the schema is happy to hold.

---

## 12. Role-versus-personhood proof

This is the distinction the whole task turns on, so it is pinned at three levels.

**Unit level.** `test_c_personhood_alone_never_yields_verified`:

```python
person_only = FacultyCandidate(name="Grace Hopper", profile_url=..., role=None, role_evidence=None)
assert name_is_person_shaped(person_only.name) is True      # the name is fine
assert verification_status_for(person_only) == "unverified" # the role is not
```

A perfectly person-shaped name with no stated role is `unverified`. Personhood
alone can never yield `VERIFIED`.

**Pipeline level.** `test_c_personhood_proven_but_role_not_proven_is_not_stored`
reproduces the exact Cornell shape: two bare names in a directory, one profile
that states a role and one that does not. Result — `examined=2`, `approved=1`,
`rejection_reasons={"role_evidence": 1}`, and the stored set is exactly
`["Grace Hopper"]`.

**The `91bcdb5` invariant is preserved, not replaced.** All 32 tests in
`test_supervisor_inline_role_evidence.py` pass unmodified, including the storage
gate test. The invariant now has *two* independent enforcement points — the pure
gate in `supervisor_gating`, and the retained `_persist_candidates` storage
gate — instead of one. Neither was weakened:

- role word alone never establishes personhood → gates 1 and 2;
- a person name derived solely from role-bearing navigation text is insufficient
  → gate 1, second clause;
- verification needs positive role evidence **plus** person-shaped text beyond
  the role evidence → `verification_status_for`, both conditions.

The known pre-existing limitation is unchanged and is not a regression: a
**plural** role label such as "Postdoctoral Researchers" with role
`"postdoctoral researcher"` slips past the role-removal check, because the
`(?![\w])` boundary cannot match the trailing `s`. This behaves identically on
`1a552a9` and on the candidate. It is not masked by a stronger shortcut; it is a
real edge in a rule this change deliberately preserved verbatim.

---

## 13. Real-source proof — Cornell University

### 13a. Live, static-first, database-free

Executed against the live source using the product's own source-access guards —
`polite_fetch`, which is robots-aware (`_robots_allows`) and per-host rate
limited. **No browser rendering. No database of any kind was opened or created**,
so this cannot constitute a production write. No authentication, CAPTCHA or
anti-bot bypass was used or attempted.

Source: `https://www.cs.cornell.edu/directory`

| Result | Value |
|---|---|
| Seed fetch readable | yes |
| Faculty pages followed | 3 (all on `www.cs.cornell.edu`) |
| Page 1 `/directory` | **14 examined, 14 approved, 0 rejected** |
| Page 2 (filtered directory query) | 19 examined, 6 approved, **13 rejected as duplicates** |
| Page 3 `/directory/staff` | 0 examined, 0 approved |
| **Total approved** | **20 unique professors** |
| Normalised URL keys unique | yes |
| Role evidence on every approval | `profile_role` |
| Verification status on every approval | `verified` |
| Render used | **false** |
| Database used | **false** |

The 14 names on page 1 are exactly the 14 recorded on `91bcdb5`:
Rachit Agarwal, Lorenzo Alvisi, Andrew Appel, William Arms, Yoav Artzi,
Hadar Averbuch-Elor, Shiri Azenkot, Kavita Bala, Tapomayukh Bhattacharjee,
David Bindel, Ken Birman, Florentina Bunea, Diana Cai, Claire Cardie.

**No real academic was dropped by the new gate.** That is the single most
important line in this section: the six gates are strictly more demanding than
the old storage gate, and they cost zero genuine professors.

### 13b. The navigation labels, live

`https://www.cs.cornell.edu/directory/staff` was fetched and is readable, and it
yields **zero candidates**. Forced past the classifier to test the gate in
isolation:

| Label | Classifier | New gate | Status |
|---|---|---|---|
| `Academic Staff` | `None` | `approved=False`, failed `[personhood]` | `unverified` |
| `Academic Planning` | `None` | `approved=False`, failed `[personhood]` | `unverified` |

The `91bcdb5` false positives are refused **twice over** on the live source: once
by the classifier, and once independently by the new pure gate.

### 13c. Offline regression pin

`TestTheRecordedRealSourceEvidence` (5 tests) replays the recorded Cornell
evidence through the new gate with no network, so a future change that broke the
real case fails in CI rather than during a production run:

- all 14 people **pass** once a profile states a role;
- all 14 are **refused** while the role is unproven (`role=None`,
  `role_evidence="source_context"`);
- neither navigation label passes;
- `www.cs.cornell.edu` clears the institutional-domain gate on its own merits.

### 13d. The honest reading of `verified`

`verified` is reported here **only because every one of the 20 approvals carries
`profile_role` evidence** — a role read off that individual's own profile page by
the product's existing profile stage inside `extract_faculty_candidates`.

Personhood on this source was already proven; **role proof was not**. It is now,
because the actual profile stage ran and was read. Had it not, the gate would have
returned `unverified` and no row would have been created (§12). This is the
distinction the production proof must preserve: the production proof may report
`VERIFIED` because the full gate passed, not because a name looked like a person.

---

## 14. Supervisor test results

**Baseline on `1a552a9`, before any change** (12 files):
`390 passed` — the suite was fully green, so every subsequent failure would be
attributable to this candidate.

**After the change:**

| File | Result |
|---|---|
| `test_supervisor_worker.py` | PASS |
| `test_supervisor_discovery_states.py` | PASS |
| `test_supervisor_person_policy.py` | PASS |
| `test_supervisor_inline_role_evidence.py` (32) | PASS |
| `test_supervisor_discovery.py` | PASS |
| `test_supervisor_outreach.py` | PASS |
| `test_supervisor_render_e2e.py` | PASS — including the real-browser end-to-end proof |
| `test_supervisor_render_policy.py` | PASS |
| **`test_supervisor_persistence_boundary.py` (34, new)** | **PASS** |
| **`test_supervisor_production_trigger.py` (47, new)** | **PASS** |

**81 new tests, 0 failures.** Zero pre-existing Supervisor test was modified,
weakened or deleted.

The render end-to-end suite passing unchanged is significant: it exercises the
real Playwright path, so `_collect_render_for_shells` returning approved groups
instead of writing inline is verified against a real rendered page, not only
against fixtures.

---

## 15. Full regression classification

The full backend suite was run **twice at each commit** — once on the candidate and
once on a pristine detached worktree checked out at the exact base `1a552a9` — so
every failure is classified by **reproduction at the base**, not by inspection.

| | passed | failed | skipped | total | wall clock |
|---|---|---|---|---|---|
| **Base `1a552a9`** | 5498 | 8 | 10 | 5516 | 19:08 |
| **Candidate `0092b5d`** | **5579** | **8** | 10 | 5597 | 13:47 |
| Delta | **+81** | **0** | 0 | +81 | |

The +81 is exactly the 81 new tests, and every one passes. The two failure lists
are **byte-for-byte identical**.

### Classification of every failure

**8 failures — `tests/test_neon_migration.py` — `PRE_EXISTING`**

```
TestMigrationHeaderParsing::test_actual_migration_file_header_not_in_executable_statements
TestUtf8Encoding::test_migration_file_is_utf8
TestUtf8Encoding::test_em_dash_present_in_sql
TestUtf8Encoding::test_en_dash_present_in_sql
TestBooleanConversion::test_migration_sql_has_true_not_integers
TestBindParameterDetection::test_detect_bind_params_real_migration_file_has_none
TestValidateMigrationFile::test_validate_real_migration_file
TestValidateMigrationFile::test_validate_real_file_in_report
```

Evidence, not inference:

1. All 8 reproduce identically on a **pristine worktree at the base commit**.
2. The cause is visible in the base run's own traceback:
   `FileNotFoundError: ...\backend\migration_export.sql`. The file these tests
   assert against **is not in the repository** at `1a552a9`. Nothing in this
   change creates, deletes or references it — `backend/migration_export.sql` and
   `test_neon_migration.py` are both outside the diff (§16).
3. Upstream `1a552a9..9cebca7` subsequently rewrote `test_neon_migration.py`
   (153 lines) and deleted `tests/migration_export_fixture.py` (135 lines),
   consistent with this breakage already being addressed in a direction this
   branch does not include.

**Owner-visible note (not a candidate issue):** because the missing file is
absent from the repository rather than merely from this worktree, these 8 will
also fail in CI on a fresh checkout. That is a pre-existing condition of
`master`, and per instruction 20 this change does **not** touch CI pipefail
behaviour to address it.

**3 failures — ambient-database assertions — `ENVIRONMENT_ONLY`**

An earlier candidate run reported 3 additional failures:

```
test_maintenance_dispatch_phase_b.py::TestIsolation::test_no_ambient_database_is_created
test_maintenance_slots.py::test_no_ambient_database_is_created_or_touched
test_maintenance_slots.py::test_ambient_database_still_absent_after_suite
```

Classified `ENVIRONMENT_ONLY`, by experiment rather than by argument:

- These assert that `backend/scholarzone.db` **does not exist** in the working
  directory.
- A stale, gitignored `backend/scholarzone.db` (868 KB) was present in the
  worktree directory, left by an earlier run in that same directory.
- After removing it, a **full clean re-run of the candidate suite produced
  exactly the 8 `neon_migration` failures and nothing else** — the 3 are gone.
- A full clean run of the suite does **not** recreate the file, which confirms
  the suite does not produce it.
- The file is listed in `.gitignore:10`, is untracked, and is absent from a
  pristine checkout — so it cannot occur in CI.

### Totals

| Category | Count |
|---|---|
| `CANDIDATE_REGRESSION` | **0** |
| `PRE_EXISTING` | **8** |
| `ENVIRONMENT_ONLY` | **3** (in one run; **0** from a clean tree) |
| `UNRESOLVED` | **0** |

---

## 16. Scope audit (Phase 13)

Verified mechanically against the diff, not by reading it:

| Must not change | Status |
|---|---|
| `app/jobs/scholarzone_maintenance.py` | untouched |
| `app/services/maintenance_dispatch.py` | untouched |
| `app/scheduler_v2.py`, `app/services/scheduler_engine.py` | untouched |
| `app/routers/internal_maintenance.py` | untouched |
| `.github/workflows/verification-cron.yml` | untouched |
| `.github/workflows/ci.yml` | untouched |
| `app/services/counts.py` (Count Intelligence) | untouched |
| `app/services/matching.py` (Match 2.0) | untouched |
| `app/services/country_intelligence.py` | untouched |
| `app/routers/discovery.py` (scholarship discovery) | untouched |
| `app/routers/verification.py` | untouched |
| `app/models.py`, `app/models_supervisor.py` | untouched |
| `migrate_schema.py`, any migration or schema file | untouched |
| Any `frontend/**` file | **none changed** |
| `README.md`, `vercel.json`, `requirements.txt` | untouched |
| Production data | no production connection was ever opened |
| Reduced-motion / accessibility bug | not touched (out of scope by instruction) |
| CI pipefail behaviour | not touched (out of scope by instruction) |

**No unrelated change appeared. No OWNER_ACTION_REQUIRED condition from a scope
violation.**

---

## 17. CI limitations

- **`tests/test_neon_migration.py` fails 8 tests on a fresh checkout of `master`.**
  The file it asserts against, `backend/migration_export.sql`, is not in the
  repository. This is pre-existing on the base commit and reproduces there
  identically (§15). Per instruction 20 this change does not alter CI pipefail
  behaviour to mask or fix it. **Owner decision required if a green pipeline is
  wanted before merge** — merging this branch will not turn those red, and will
  not make them redder either.
- `pytest-timeout` is not installed in the backend requirements, so `--timeout`
  is unavailable locally. CI's own invocation is unaffected; this only limits
  local run bounds, and the suite completes in 13–19 minutes either way.
- The full-suite timings above are single runs on one Windows host and are not
  a performance baseline.
- The live Cornell fetch (§13a) is **not** part of CI. It depends on an external
  university page and would make CI fail on their outage, which is exactly the
  dependency the existing Supervisor test suite refuses to take. Its offline
  equivalent (`TestTheRecordedRealSourceEvidence`) is in CI.

---

## 17. Feature flag semantics

```
SCHOLARZONE_SUPERVISOR_DISCOVERY_ENABLED
```

| Property | Value |
|---|---|
| Read by | `backend/app/core/config.py` → `Settings.supervisor_discovery_enabled` |
| Values | `1` / `true` / `yes` / `on` (existing `_as_bool` convention) |
| **Default** | **`False` — OFF, in every environment** |
| Gates | the Supervisor discovery **trigger endpoint** only |
| Does **not** gate | browser rendering, and nothing else |

### Explicitly NOT the render flag

```
SCHOLARZONE_SUPERVISOR_RENDER_ENABLED     (read by app/services/supervisor_render.py)
SCHOLARZONE_SUPERVISOR_DISCOVERY_ENABLED  (read by app/core/config.py)  <- new
```

These are deliberately separate, and the separation is enforced by a test:

- `application configuration does not read the render flag at all` — routing it
  through `Settings` would be the first step towards the two collapsing;
- the trigger never imports `supervisor_render`, never constructs a
  `RenderBudget`, and never mutates an environment variable.

**Turning discovery on does not make Playwright available in production.** The
trigger passes no render budget, so the renderer reports itself unavailable and a
client-side directory lands on the honest inconclusive state
`source_requires_rendering` rather than being rendered. Conversely, enabling the
renderer does not make this endpoint reachable — it still needs the secret *and*
this flag.

### Activation semantics

1. Merge `feat/supervisor-production-trigger` into `master`.
2. Deploy. The endpoint now exists and is **refusing everything** (`503`).
3. On the deployment, set `SCHOLARZONE_SUPERVISOR_DISCOVERY_ENABLED=true` and
   redeploy / restart.
4. The endpoint is now reachable for a holder of
   `SCHOLARZONE_VERIFICATION_SECRET`.
5. `POST /internal/supervisor/discover/<id>` performs one bounded run.

Steps 2 and 3 are separate on purpose: the code can be deployed dark, and the
capability switched on afterwards. Reverting the flag at step 3 disables the
trigger immediately without a code change.

---

## 18. Deployment status

**NONE.** Nothing was deployed, pushed, merged or force-pushed.

- Candidate committed locally on `feat/supervisor-production-trigger`.
- Not pushed to any remote.
- No PR opened.
- The primary dirty working tree was never touched.
- No production write occurred.
- `SCHOLARZONE_DATABASE_URL` was never read, requested, printed, logged or used.
- `SCHOLARZONE_VERIFICATION_SECRET` was never requested, read, printed, logged,
  decoded or inspected. No test, script or workflow contains its value; the
  workflow references it only as `${{ secrets.SCHOLARZONE_VERIFICATION_SECRET }}`.

---

## 19. Expected production row changes

For **one** scholarship, from **one** dispatch:

| Table | Rows | Condition |
|---|---|---|
| `scholarship_supervisor_coverage` | **0 or 1** | created only if absent |
| `professor_profiles` | **0..N** | one per candidate passing all six gates |
| `scholarship_professor_links` | **0..N** | one per approved professor |
| `supervisor_source_evidence` | **0..N** | one per approved professor per source |
| `professor_availability` | **0..N** | one per approved professor |
| **any other table** | **0** | — |

If no candidate passes, **zero rows** are added to any professor, link, evidence
or availability table. The coverage row is still written, because "we looked and
found nothing" is itself an answer the product is required to record.

No other scholarship's coverage row is touched
(`test_it_does_not_touch_any_other_scholarship`).

---

## 20. Rollback plan

| Situation | Action |
|---|---|
| **Before merge** | Nothing to undo. `git branch -D feat/supervisor-production-trigger`. No production effect. |
| **After merge, before dispatch** | Set `SCHOLARZONE_SUPERVISOR_DISCOVERY_ENABLED=false` on the deployment → endpoint returns `503` immediately. Fastest kill switch; no code change, no redeploy logic. |
| **After a dispatched run** | Set the flag to `false` first (stops further runs), then `git revert 0092b5d20b87458b65e148ed0575cfe55071ce6b` on a new branch and redeploy. |
| **Data rollback** | Any row the proof created is an upsert keyed on a unique constraint, so re-running converges rather than duplicating. Rows written by a proof are removed by `DELETE`ing the `scholarship_professor_links` for that scholarship id and recomputing coverage — deliberately *not* automated here, because an automated data rollback is a second write path, and this change adds no write paths. |

No history rewrite and no force-push is required or permitted at any stage.
Reverting the flag is preferred over reverting the commit, because it is
immediate and needs no deploy.

---

## 21. Owner action required

**YES.** Nothing below has been done, and each item is deliberate.

1. **Review and merge** `feat/supervisor-production-trigger` (`0092b5d`) into
   `master`. Note `origin/master` has advanced to `9cebca7`; no file overlap, so
   a rebase is expected to be clean.
2. **Confirm `vars.SCHOLARZONE_API_URL`** is set and correct. It is used by the
   proof workflow and is currently only consumed by `deploy.yml` and
   `frontend.yml`. **One open item for you:** `admin-auth-check.yml` hardcodes
   `https://scholarzone-fwzj.vercel.app/api` while `deploy.yml` uses
   `vars.SCHOLARZONE_API_URL` bare. This change follows `deploy.yml` (the
   workflow that actually verifies a deployment). Please confirm which host is
   authoritative for GitHub Actions before dispatching.
3. **Deploy** to production. The trigger will be live but refusing (`503`).
4. **Set `SCHOLARZONE_SUPERVISOR_DISCOVERY_ENABLED=true`** on the deployment.
   Leave `SCHOLARZONE_SUPERVISOR_RENDER_ENABLED` untouched — discovery and
   rendering are separate, and rendering must stay off for this proof.
5. **Choose the single target scholarship id** and record the pre-run state
   (below).
6. **Explicitly authorise the dispatch.** This has not been run, and will not be
   run without that authorisation.

### Pre-run record (Phase 12) — to be captured by the owner

- [ ] current `SELECT count(*) FROM professor_profiles;`
- [ ] current coverage row for the target id (status, count, last checked)
- [ ] target scholarship id
- [ ] that scholarship's `official_source_url` / `catalogue_url`
- [ ] current `scholarship_professor_links` count for that id

### Post-run checklist (Phase 12)

- [ ] HTTP 200 from the authenticated call; the run log shows the target id
- [ ] response reports `scholarship_id` equal to the requested id, and nothing else
- [ ] no maintenance dispatch occurred
- [ ] no scholarship `DiscoveryCandidate` activity
- [ ] no browser rendering (`render_requested: false` in the response)
- [ ] `approved` / `rejected` counts and the `rejected_by_gate` histogram are consistent (`sum == rejected`)
- [ ] `professors_written` matches the change in `professor_profiles`
- [ ] only the five Supervisor tables changed
- [ ] idempotency: re-dispatch, confirm counts unchanged

**Do not run country-wide discovery.** There is no such capability to run.

---

## 22. Final classification

### `READY_FOR_OWNER_ACTIVATION`

Every condition in the rubric is met:

- [x] **Bounded trigger exists** — one integer, no body, one route, one request.
- [x] **Auth is proven** — existing secret, header, `compare_digest`, fails
      closed; plus the independent default-off capability flag. 12 auth/bound tests.
- [x] **Persistence is separated from classification** — collect takes no session
      and has zero write verbs; persist is the only writer and commits once.
- [x] **No-write gate tests pass** — A–J, 34 tests, all green.
- [x] **Real source reaches the full role/person/provenance validation path** —
      live Cornell, static-first, database-free: 14/14 real academics retained,
      20 approved with `profile_role`, both navigation labels refused, zero
      rendering, zero database.
- [x] **No regression** — full suite run at the candidate **and** at the base:
      5579 vs 5498 passed, identical 8-test failure list, delta exactly the 81 new
      tests. Zero `CANDIDATE_REGRESSION`.
- [x] **Production execution NOT authorised and NOT executed.**
- [x] **91bcdb5 invariant preserved**, and now enforced in two independent places.
- [x] **Scope audit clean** — no unrelated subsystem, schema, migration or
      frontend file touched.

`OWNER_ACTION_REQUIRED` is *not* the classification, because nothing here is
blocked: the remaining steps are the ordinary activation this rubric reserves
"ready for owner activation" for — merge, deploy, enable the flag, authorise the
dispatch.

The production proof has **not** been performed. It requires the owner's
authorisation at step 6 above.

---

FINAL CLASSIFICATION: READY_FOR_OWNER_ACTIVATION
CANDIDATE: 0092b5d20b87458b65e148ed0575cfe55071ce6b
MASTER: 9cebca7bf0e011cec5e9ed96715a4489dd64bef1 (base of candidate: 1a552a929881953038400e7ef45487384a6df320)
TRIGGER: PRESENT — workflow_dispatch-only, POST /internal/supervisor/discover/{scholarship_id}, secret + default-off flag, not deployed
PERSISTENCE_GATING: PROVEN — collect has no session and zero write verbs; persist is the only writer and commits once; 34 boundary tests green
REAL_SOURCE_ROLE_PROOF: ESTABLISHED — live Cornell, static-first, database-free, zero rendering; 20 approved on profile_role, 14/14 recorded academics retained, both navigation labels refused
PRODUCTION WRITES: NONE
DEPLOYMENT: NONE
OWNER ACTION REQUIRED: YES
UNRESOLVED ITEMS: 0
