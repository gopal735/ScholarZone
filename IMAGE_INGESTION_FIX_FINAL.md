# IMAGE_INGESTION_FIX_FINAL.md

**Task:** fix the proven image-ingestion deletion defect only
**Date:** 2026-10-04
**Commit:** `3bf92b6` — `fix: stop ingestion from deleting a stored image on a null refresh`
**Status:** fix merged to `master`, CI green, **production deployment BLOCKED by Vercel quota**

Tags used throughout: **[OBSERVED FACT]** directly measured · **[PROVEN]** direct evidence ·
**[DISPROVEN]** evidence contradicts · **[PLAUSIBLE BUT UNPROVEN]** consistent, not established ·
**[UNKNOWN]**

---

## 1. Executive Summary

The proven defect is real, was reproduced locally before fixing, and is now fixed by a 4-line guard
in one function.

`scholarship_image_audit` recorded a single transaction — **txn 281792, 2026-10-04 08:39:23.519402,
`writer_context='maintenance.add'`** — blanking the image fields of four scholarships (130, 557, 564,
569). The `changed_fields` were exactly the five image fields that
`ScholarshipIngestionRecord.to_persistence_fields()` maps, with `image_kind` absent because the mapper
does not map it. That is a five-of-five fingerprint match, not a resemblance.

The mechanism is fully traced and was verified against a real data file:
`do_add` copies **every** key of a worklist entry into the ingestion model
(`flat = {k: v for k, v in entry.items() if k != "detail"}` → `ScholarshipIngestionRecord(**flat)`).
`backend/config/new_scholarships.json` contains entries whose five image keys are present and
explicitly `null`. Pydantic records explicitly-supplied keys in `model_fields_set` even when the value
is `None`, so the mapper emitted them and the upsert's dynamic `setattr` loop wrote `None` over stored
images.

**This does NOT resolve the historical October 3 image reversion.** That remains unproven and
separately investigated. `do_logos` and `do_purge` were not touched.

## 2. Proven Production Evidence

| Evidence | Value |
|---|---|
| Transaction | `txn 281792`, `08:39:23.519402` |
| Writer context | `maintenance.add` |
| Records affected | **130, 557, 564, 569** (audit_ids 27, 31, 33, 35) |
| `changed_fields` | `image_url, image_source_url, image_source_type, image_alt_text, image_verified_at` |
| Mapping fingerprint | **exact 5-of-5** match with `to_persistence_fields` |
| `image_kind` | absent from the UPDATE → stale kind survived |
| ID 130 outcome | `image_kind='official_logo'` with `image_url = NULL` |
| Downstream | 4 `I6`-shaped inconsistencies; 3 confirmed by `image_state_audit` |

**[PROVEN]** Also present in the config today: entries for *Aga Khan Foundation International
Scholarship* (→ ID 130) and *Excellence Scholarship & Opportunity Programme*, ETHZ (→ ID 14), each
carrying all five image keys as `null`.

## 3. Root Cause

**[PROVEN]** Two facts combine:

1. **Absence was encoded as retraction.** The mapper's contract was "apply the field if the caller
   supplied the key". Pydantic's `model_fields_set` cannot distinguish *omitted* from *explicitly
   null*, so both produced a write of `None`.
2. **A legitimate producer of explicit nulls exists.** `do_add` forwards raw worklist JSON verbatim,
   and that JSON legitimately contains `"image_url": null` to mean "we have no image for this one".

So a routine catalogue refresh, carrying no opinion about images, destroyed verified images —
including accepted `program_image` and `official_banner`, which the 87ad84c policy exists to protect.

**[PROVEN]** The bug was invisible to a `row.image_url =` grep because the write is a dynamic
`setattr` in a different module, reached through a function call.

## 4. Architecture Audit

### Callers of `upsert_verified_scholarships` — all audited

| Caller | Passes image fields? |
|---|---|
| `app/jobs/scholarzone_maintenance.py:1246` (`do_add`) | **Yes — forwards raw worklist keys verbatim, including explicit nulls** |
| `app/seed.py:100` | via `VERIFIED_SCHOLARSHIPS` — omits keys or supplies real URLs |
| `scripts/add_us_scholarships.py:580` | static; omits keys |
| `scripts/import_additional_scholarships.py:25` | static; omits keys |
| `scripts/seed_real_scholarships.py:35` | static; omits keys |
| `app/data/verified_scholarships.py`, `additional_scholarships.py` | 64 records with real `image_url`, 67 with provenance; the rest omit the keys |

**[PROVEN]** **No caller uses ingestion to retract an image.** Every clearing path in the system goes
somewhere else: `do_purge`, `do_logos`, `image_discovery_orchestrator`, `scholarship_image_verifier`,
`data/audit_images.py`, `data/resolve_generic_images.py`. None goes through
`upsert_verified_scholarships`.

**[PROVEN]** Canonical clearing therefore remains intact and untouched: `do_purge` and `do_logos` are
byte-identical, and both are covered by tests that execute the real functions.

### `image_kind` producer semantics

**[PROVEN]** Kinds are produced by the image pipeline only: `image_validator._classify_image_kind`,
`do_logos` (`_kind_for`), `image_coverage_runner`. The ingestion model has **no** `image_kind` field
and no producer semantics for one.

**Consequence, honoured by the fix:** `image_kind` was deliberately **not** added to the mapper.
Writing one would fabricate trust evidence.

### Related predicates (read, not changed)

* `public_visibility_conditions()` — gates on `image_url IS NOT NULL`, `image_verified_at IS NOT NULL`,
  `image_source_type IS DISTINCT FROM 'wikimedia'`. It never references `image_kind`.
* `do_purge` — spares on **kind**. Unchanged by this task.
* `I6_image_without_kind` — contract check. Unchanged.

## 5. Exact Code Path

```
do_add                                    scholarzone_maintenance.py:1152-1202
  flat = {k: v for k, v in entry.items() if k != "detail"}        :1156
  record = ScholarshipIngestionRecord(**flat)                       :1198   <-- explicit nulls enter here
  upsert_verified_scholarships(session, fresh)                      :1246
    persistence_fields = record.to_persistence_fields(verified_on)  scholarship_ingestion.py:229
      if source_field in self.model_fields_set:                     :124   <-- None is "supplied"
        fields[database_field] = getattr(self, source_field)
    for field, value in persistence_fields.items():
        setattr(scholarship, field, value)                          :253-254 <-- writes None
    session.commit()                                                 :257
```

## 6. Intended Semantics

Derived from the audit, not invented. **[PROVEN]** for each row:

| Case | Intended behaviour | Evidence |
|---|---|---|
| **A. Absent image field** | leave stored image untouched | current behaviour already correct; all static callers rely on it |
| **B. Explicit `None`** | **treat as absence, not retraction** | no caller retracts via ingestion; clearing is owned by `do_purge`/`do_logos` |
| **C. Trusted replacement** | apply, with its provenance | 64 config records carry real URLs; `do_add` docstring: "a logo is only attached when it came with provenance" |
| **D. Existing verified image** | preserve unless C | 87ad84c |
| **E. Existing accepted image** (`program_image`, `official_banner`) | preserve | 87ad84c; purge reported `preserved_accepted: 404` |
| **F. Non-accepted image** | canonical clearing only, via `do_purge` | purge predicate |
| **G. Image source refresh** | replacement applies; clearing does not | C + B |

## 7. Minimal Fix

One guard, scoped to image fields, in `services/scholarship_ingestion.py`:

```python
IMAGE_PERSISTENCE_FIELDS = frozenset({
    "image_url", "image_source_url", "image_source_type",
    "image_verified_at", "image_alt_text",
})

for source_field, database_field in mappings.items():
    if source_field not in self.model_fields_set:
        continue
    value = getattr(self, source_field)
    if database_field in IMAGE_PERSISTENCE_FIELDS and value is None:
        continue          # absence is not a retraction
    fields[database_field] = value
```

**[OBSERVED FACT]** Diff: **1 production file, +26 / −2**, all inside
`to_persistence_fields` plus one module constant. No other function touched.

Properties, each mapped to a requirement:

| Requirement | How it is met |
|---|---|
| 1. preserve trusted image when no authoritative replacement | nulls are dropped; absent keys already were |
| 2. explicit `None` cannot erase | the guard |
| 3. legitimate replacement preserved | non-null values still applied (tests prove it) |
| 4. legitimate clearing preserved | clearing lives in `do_purge`/`do_logos`, untouched; tests execute both real stages |
| 5. verification semantics not weakened | no verification field touched |
| 6. public visibility unchanged | `repositories/scholarships.py` untouched |
| 7. purge semantics unchanged | `do_purge` untouched |
| 8. no other subsystem changed | single-file diff |

**Not a special case.** No scholarship ID appears in the fix or in the production diff.
**`image_kind` not added to the mapper** — no producer semantics, so adding it would fabricate trust.

## 8. Regression Tests

`backend/tests/test_ingestion_image_preservation.py` — **20 tests**, all driving the real
`upsert_verified_scholarships` against a real SQLite database. Nothing re-derives the rule.

| # | Required scenario | Test |
|---|---|---|
| 1 | trusted image + image fields absent | `test_ingestion_without_image_keys_leaves_the_image_alone` |
| 2 | trusted image + `image_url=None` | `test_only_image_url_null_preserves_the_rest_of_the_pairing` |
| 3 | accepted `program_image` | `test_accepted_non_identity_kind_is_not_erased[program_image]` |
| 4 | accepted `official_banner` | `test_accepted_non_identity_kind_is_not_erased[official_banner]` |
| 5 | verified `official_logo` | covered by the all-kinds parametrization |
| 6 | authoritative replacement works | `test_authoritative_replacement_is_applied`, `test_replacement_on_a_row_with_no_image_still_works` |
| 7 | canonical clear still works **iff policy permits** | `test_the_real_purge_stage_still_clears_a_non_accepted_image`, `…_preserves_an_accepted_image` — both execute the **real `do_purge`** |
| 8 | url/kind consistency | `test_preserved_image_never_ends_up_url_without_kind`, `test_ingestion_does_not_write_image_kind` |
| 9 | **exact txn-281792 failure shape** | `test_all_five_image_fields_explicit_null_preserves_the_image[5 kinds]` — asserts the record really carries explicit nulls, or the test would prove nothing |
| 10 | real function executed | every test calls the real upsert / real purge stage |

### Failure reproduction **[PROVEN]**

Run against the **unfixed** mapper, before any change:

```
9 failed, 11 passed
  FAILED test_all_five_image_fields_explicit_null_preserves_the_image[official_banner]
  FAILED test_all_five_image_fields_explicit_null_preserves_the_image[official_government]
  FAILED test_all_five_image_fields_explicit_null_preserves_the_image[official_logo]
  FAILED test_all_five_image_fields_explicit_null_preserves_the_image[official_university]
  FAILED test_all_five_image_fields_explicit_null_preserves_the_image[program_image]
  FAILED test_only_image_url_null_preserves_the_rest_of_the_pairing
  FAILED test_accepted_non_identity_kind_is_not_erased[program_image]
  FAILED test_accepted_non_identity_kind_is_not_erased[official_banner]
  FAILED test_mapper_drops_explicit_null_image_fields
```

After the fix: **20 passed**. The 11 that passed before are the canonical-purge and
legitimate-replacement tests, which confirms the blast radius was exactly the explicit-null path.

**[OBSERVED FACT]** IDs 130/557/564/569 were used only as forensic scenarios. No production row was
read for the test, modified, or restored.

## 9. Baseline Comparison

Honest, measured on the **same commit** (`c405b49`) with and without the change.

| Suite | Baseline (clean master) | With fix |
|---|---|---|
| New regression file | — | **20 passed** |
| Image/ingestion/maintenance suites (17 files) | — | **455 passed** |
| `test_scholarships.py` isolated | 12 passed | 12 passed |
| `test_image_constant_loading.py` isolated | **1 failed**, 33 passed | **1 failed**, 33 passed |
| Full backend | 11 failed, 4850 passed, 11 skipped, 1 error | 9 failed, **4872** passed, 11 skipped, 1 error |

### Pre-existing failures — documented, not hidden, not mine to fix

| Failure | Count | Status |
|---|---|---|
| `test_neon_migration.py` (8 tests) | 8 | **Environmental** — asserts on a Neon migration SQL file absent from the repo. Identical on baseline. |
| `scripts/artifact_smoke_test.py::test_endpoint` | 1 error | **Pre-existing.** Identical on baseline. |
| `test_image_constant_loading.py::…no_stats_unrelated_vocabulary_binding…` | 1 | **Pre-existing, concurrent actor's in-flight work.** Byte-identical failure with and without my change. It asserts `do_stats` must not import `ACCEPTED_IMAGE_KINDS`, which contradicts master's own current code. Not mine; not touched. |
| `test_scholarships.py` (2 tests) | 2 | **Cross-test pollution in the full run only.** Pass 12/12 in isolation on **both** baseline and fixed. Neither test references images. |

**Net:** my change adds 20 passing tests and removes no test. No test was weakened, skipped, or
deleted. The apparent "2 fewer failures" is ordering sensitivity in two tests that are green in
isolation either way — I am **not** claiming to have fixed them.

## 10. Production Deployment

**[PROVEN]** Gates met before attempting: defect reproduced (9 failures), fix minimal (1 file), 20 +
455 tests pass, full suite compared to baseline, no `do_logos`/`do_purge`/scheduler/audit change,
diff and staged diff reviewed, CI green.

| Item | Result |
|---|---|
| Commit | `3bf92b6`, fast-forward push `9ff021b..3bf92b6` |
| `ScholarZone CI` | **success — 9/9 jobs** (preflight, backend-tests, frontend-tests, frontend-lint, build-and-smoke, import-smoke, schema-compat, env-config, git-integrity) |
| Production deploy | **BLOCKED** |

**Deployment blocker — [OBSERVED FACT]:**

```
POST /v13/deployments  ->  HTTP 402
{"code":"payment_required",
 "message":"Resource is limited - try again in 24 hours
            (more than 100, code: \"api-deployments-free-per-day\")",
 "limit":{"total":100,"remaining":0,"reset":1791195717123}}
```

Quota resets **2026-10-05 10:21:57Z**.

**[PROVEN]** This also explains the stalled auto-deploy: the last Vercel production deployment was
`c405b49` at `09:16:26Z`, and no deployment has been produced since, across many pushes — consistent
with the daily deployment allowance being exhausted. **[UNKNOWN]** whether the Git integration will
auto-deploy `3bf92b6` after the reset, or whether it needs a manual trigger.

I did **not** deploy from a local worktree, and did not attempt any quota workaround.

## 11. Production Verification

Read-only, at the time of writing:

| Check | Result |
|---|---|
| Production revision | `c405b49bb8b9` — **the fix is NOT deployed** |
| `/api/health` | **200**, `status: ok` |
| `/api/scholarships/stats` | **200** |
| `/api/scholarships?limit=2` | **200** |
| `/api/admin/verification/summary` anonymous | **401** — guard intact, Admin Verification untouched |
| Match / Count / Dashboard / Applications | not exercised; **no production path was modified**, and the change is ingestion-only and not on any request path |

**Ingestion/upsert smoke test in production:** **[UNKNOWN] / not performed.** The only way to
exercise it against production is to run the `add` stage, which is a mutation and was correctly
refused. No synthetic mutation, no image repair, no shortcut.

## 12. Invariants

| Invariant | Status |
|---|---|
| Public count | 358 at time of writing — **drifting independently of this change** (350 → 353 → 358 during this work, caused by the concurrent actor's continued image work). This fix is **not deployed**, so it cannot have caused any of it. |
| `with_image == total` | 358 == 358 — every public record still carries an image |
| Storage rows | **[UNKNOWN]** this run — the public API cannot see storage rows, and I did not trigger a maintenance run to read it. Last measured value was 451. |
| Match / Count | **[UNKNOWN]** — not exercised; no count logic touched |
| Admin Verification | untouched; anonymous 401 confirmed |
| Audit instrumentation | untouched; no synthetic events added; no evidence altered |

## 13. What This Fix Does NOT Prove

1. **It does not explain or fix the October 3 image reversion.** **[UNKNOWN]** — the audit's first
   event is `2026-10-04 08:34:18`; the original loss predates it. No causal claim is made.
2. **It does not address `do_logos`.** **[PROVEN]** still capable of clearing an accepted
   `program_image`; left deliberately untouched so the forensic observation opportunity survives.
3. **It does not resolve the purge/public predicate contradiction.** **[PROVEN]** the public image
   gate never references `image_kind` while `do_purge` requires it, and ingestion guarantees
   `image_kind IS NULL`. Unchanged, as instructed.
4. **It does not restore any of the 18 purged images, nor IDs 14/130/554/557/564/569.**
5. **It does not attribute the `writer_context='unknown'` writes** that re-set images on 557/564/569
   and produced the I6 violations. **[UNKNOWN]** writer identity.
6. **It does not close the audit gaps** — INSERT, DELETE, rollback, and the ~14 mutation paths that
   set no `writer_context`.
7. **It does not prove production is safe**, because it is not deployed.

## 14. Remaining Image Reversion Investigation

Deliberately untouched, as instructed:

* `do_logos` clear branch (`scholarzone_maintenance.py:994-1004`) — **[PROVEN]** cleared ID 14's image
  at 08:38:28 and set ID 130's at the same instant.
* The recurring-reversion pattern and whether it relates to October 3. **[UNKNOWN]**
* The `maintenance.add` → `unknown` transition on IDs 14, 130, 554 at 09:07–09:10. **[UNKNOWN]**
* The `I6` violations on 557/564/569, now known to be caused by a later unattributed write, **not**
  by the ingestion defect. **[PROVEN]** — those records were re-set at 09:21 by
  `writer_context='unknown'`, after the 09:01 purge.

**[OBSERVED FACT]** Note the distinction that matters: the I6 violations were **not** caused by this
ingestion bug. The ingestion clears happened at 08:39; the I6 shapes were created at 09:21 by a
different, still-unidentified writer.

## 15. Remaining Unknowns

1. **[UNKNOWN]** Whether the Git integration will auto-deploy `3bf92b6` after the quota reset.
2. **[UNKNOWN]** Identity of the `unknown` writer behind audit rows 66–91.
3. **[UNKNOWN]** Root cause of the October 3 reversion.
4. **[UNKNOWN]** Whether the purge/public predicate contradiction is intended policy.
5. **[UNKNOWN]** Current storage row count (public API cannot see it; not measured this run).
6. **[UNKNOWN]** Whether any legitimate workflow *wants* ingestion to retract an image. None was
   found; if one is ever required it must be an explicit named policy, not an implicit null.
7. **[UNKNOWN]** Pre-clear image state for the 18 purged IDs — `before_values` exist in the audit
   table but no script exposes them for arbitrary IDs.

## 16. Recommended Next Action

1. **Wait for the Vercel quota reset (2026-10-05 10:21:57Z), then confirm `3bf92b6` deploys** — either
   automatically or via one Git-source deployment. Do not work around the quota.
2. **Before the next `add` stage runs, verify the fix is live.** This matters: `new_scholarships.json`
   still contains 4 entries with five explicit null image keys, and `do_add` still runs on the
   `verification-cron.yml` schedule (`7 */12 * * *`, next fire 12:07Z). **Until the fix is deployed,
   the next scheduled `add` stage can delete images again.** Either pause the workflow or accept that
   risk knowingly.
3. **Re-run the audit and `image_state_audit` after deployment** and confirm no new
   `maintenance.add` image clears appear.
4. **Separately, decide the purge/public predicate contradiction.** It is the mechanism behind the
   366 → 350 drop and it is structural, not incidental. Out of scope here; it needs an owner
   decision and the `before_values` extractor first.
5. **Leave `do_logos` alone** until the reversion investigation is complete, as instructed.

---

### Changed files

| File | Change |
|---|---|
| `backend/app/services/scholarship_ingestion.py` | +26 / −2 — the guard and `IMAGE_PERSISTENCE_FIELDS` |
| `backend/tests/test_ingestion_image_preservation.py` | new — 20 tests |

No other file. No `do_logos`, no `do_purge`, no scheduler, no audit instrumentation, no frontend, no
Match, Count, Dashboard, Applications, or Admin Verification.

*No production data was modified. No image was repaired or restored. No secret was read or exposed.
No `git add .`, no `git add -A`, no reset, no force push, no destructive rebase, no amend of another
actor's commit. The only production-touching action attempted was one deployment API call, which the
provider rejected with HTTP 402.*
