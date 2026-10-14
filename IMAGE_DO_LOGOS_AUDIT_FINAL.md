# IMAGE_DO_LOGOS_AUDIT_FINAL.md

**Scope: code and test investigation only. No production data was mutated, no production stage was
invoked, no scheduler/cron/concurrency/audit-table/`do_logos`/`do_purge` change was made. All
execution was against a throwaway SQLite database inside an isolated worktree.**

---

## 1. Executive Summary

**PROVEN DEFECT.** The current `do_logos()` implementation contains a deterministic defect that
exactly reproduces the already-proven ID 14 production reversion event.

`do_logos` clears an entire stored image whenever `image_kind` is not a logo identity mark. Because
`ACCEPTED_IMAGE_KINDS` also contains `program_image` and `official_banner`, an image the
verification pipeline **accepted** is deleted purely for not being a logo. Reproduction drives the
real stage through `main(["--stage", "logos"])`, not a re-derivation of its conditions.

This does **not** close Phase 6 and does **not** solve October 3.

## 2. Phase 6 Status

| Item | Result |
|---|---|
| Phase 6 classification | **CASE E — NOT OBSERVED** |
| Qualifying natural scheduled run found | **NO** |
| `logos` executed in a qualifying cycle | **NO** |
| ID 14 cleared / survived in a qualifying cycle | **NEITHER — UNDETERMINED** |
| Recurring natural-cron reversion | **NOT PROVEN** |
| October 3 historical root cause | **UNKNOWN** |

The observation never happened: no `event=schedule` run exists after 2026-10-04 05:41:37 UTC, which
predates the 09:09:52 repair.

## 3. Proven Production Event

Direct database evidence, both rows in the live append-only audit:

| audit row | UTC | scholarship | writer_context | transaction_id | effect |
|---|---|---|---|---|---|
| **3** | 08:35:23.391597 | 14 | `unknown` | 281733 | image **set** to ETHZ `imageCarousel` URL, `image_kind` → `program_image`, `image_verified_at` populated |
| **5** | 08:38:28.768558 | 14 | **`maintenance.logos`** | 281764 | image **cleared to NULL**; `changed_fields` = image_url, image_source_url, image_source_type, image_alt_text, image_verified_at, image_evaluation_status, image_evaluated_at (+ image_kind) |

**OBSERVED FACT / PROVEN:** `maintenance.logos` cleared an accepted `program_image` on ID 14 in
production. This is a proven live unsafe event.

## 4. `do_logos` Architecture

`do_logos` is a fast path that attaches audited official logos by exact official-source host, using
a checked-in override map (`official_logo_overrides.json`, **357 entries**, including `ethz.ch`)
rather than crawling. It selects **all** scholarships and, per row:

- computes the host from `row.official_source_url` (strips `www.`);
- looks up an override; if none, records the host in `still_missing` and skips;
- if the row already has an image, decides keep-vs-clear (Section 5);
- if the row has no image and not `dry_run`, attaches the logo and marks the record `VERIFIED`.

**Inspects:** `official_source_url` (host), `image_url`, `image_kind`.
**Updates:** all eight tracked image fields — either cleared together or populated together.

## 5. Exact Clear Predicate

`backend/app/jobs/scholarzone_maintenance.py`, lines 987–1006:

```python
if row.image_url:
    # An existing verified identity mark is never replaced by a
    # different one; a stored photo, though, is exactly what
    # logo-only mode exists to remove.
    if (row.image_kind or "") in LOGO_IDENTITY_KINDS:
        skipped_existing += 1
    else:
        row.image_url = None
        row.image_source_url = None
        row.image_source_type = None
        row.image_kind = None
        row.image_alt_text = None
        row.image_verified_at = None
        row.image_evaluation_status = None
        row.image_evaluated_at = None
```

The clear fires when **all three** hold:

1. `row.image_url` is truthy;
2. the record's host **matches an override** (`find_override` returns a hit);
3. `row.image_kind` is **not** in `LOGO_IDENTITY_KINDS`.

Fields 3–5 (`image_source_url`, `image_source_type`, `image_kind`) share the identical predicate and
are cleared in the same statement.

### Step 1 answers, against canonical definitions

| # | Question | Answer |
|---|---|---|
| 1 | Fields inspected | `official_source_url`, `image_url`, `image_kind` |
| 2 | Fields updated | all eight tracked image fields |
| 3 | Predicate to clear `image_url` | `image_url` truthy **AND** host has override **AND** `image_kind ∉ LOGO_IDENTITY_KINDS` |
| 4 | Predicate to clear `image_source_url` | identical, same statement |
| 5 | Predicate to clear `image_source_type` | identical, same statement |
| 6 | Assumes all images are logos? | **YES** — "a stored photo … is exactly what logo-only mode exists to remove" |
| 7 | Inspects `image_kind`? | Yes, but **only** against `LOGO_IDENTITY_KINDS` |
| 8 | Inspects `ACCEPTED_IMAGE_KINDS`? | **NO** — not imported (line 953 imports only `LOGO_IDENTITY_KINDS`) |
| 9 | Protects `program_image`? | **NO** |
| 10 | Protects `official_banner`? | **NO** |
| 11 | Protects verified/trusted images? | **NO** — `image_verified_at` is explicitly cleared |
| 12 | Can it clear an accepted image while retaining `image_verified_at`? | **No** — it clears that too, so no stale trust survives |
| 13 | Can it create stale metadata states? | **No** — all eight fields are cleared coherently (test H passes) |

## 6. Event Reproduction

**Classification: CAN REPRODUCE EXACTLY.**

`backend/tests/test_do_logos_accepted_image.py` drives the real stage via
`job.main(["--stage", "logos"])` with `app.database.get_session_factory` pointed at a temporary
SQLite database. Note the stage binds that name itself at line 568, so the patch must target the
source module.

The reproduction fixture mirrors production precisely:

- `official_source_url` on `ethz.ch` — confirmed present in the real 357-entry override map, and
  `find_override(ov, "ethz.ch")` returns a hit, so condition 2 holds;
- a stored `image_url` with `image_kind="program_image"` and a populated `image_verified_at`;
- one additional logo-less `ethz.ch` record.

**That last record is load-bearing, and it exposed a second finding.** `do_logos` persists its work
only under `if attached and not args.dry_run:` (line 1028). If the stage attaches zero logos, the
clearing mutations are **never committed and are silently discarded** on `session.close()`. My first
fixture had every row already carrying an image, so nothing was attached and the clears were rolled
back — the defect appeared absent. Adding one logo-less record makes the commit fire and the clears
persist, as they do in production. **A stage whose destructive branch only takes effect when it
also did useful work is itself a latent hazard.**

`test_real_logos_stage_reproduces_the_proven_id14_clearing` **passes**: the real stage clears the
accepted `program_image` to NULL and nulls every dependent field, matching the shape of audit row 5.

## 7. Regression Test Results

**7 passed, 4 failed** against unmodified production code. The failures are the defect.

| Test | Result | Meaning |
|---|---|---|
| `test_real_logos_stage_reproduces_the_proven_id14_clearing` | **PASS** | reproduces the proven production event exactly |
| `accepted_image_survives[official_logo]` | PASS | logo identity mark correctly preserved |
| `accepted_image_survives[official_government]` | PASS | preserved |
| `accepted_image_survives[official_university]` | PASS | preserved |
| `metadata_stays_coherent_after_the_stage` | PASS | no stale verdict or timestamp left behind |
| `real_logos_stage_executes_without_runtime_error` | PASS | stage runs to completion |
| `logos_stage_does_not_import_accepted_image_kinds` | PASS | pins the root cause: `ACCEPTED_IMAGE_KINDS` is never consulted |
| `accepted_image_survives[program_image]` | **FAIL** | **DEFECT** — accepted `program_image` deleted |
| `accepted_image_survives[official_banner]` | **FAIL** | **DEFECT** — accepted `official_banner` deleted |
| `unverified_accepted_kind_still_survives` | **FAIL** | **DEFECT** — a missing timestamp is treated as licence to delete an accepted kind |
| `legitimate_cleanup_is_not_broadly_disabled` | **FAIL** | **harness artefact, not a product finding** — this fixture seeds no logo-less record, so `attached == 0` and the clear is rolled back per Section 6. The harness needs correcting before it can prove legitimate cleanup still works. I am **not** claiming a product defect from this failure. |

A–E and G are therefore established: `program_image` and `official_banner` are destroyed; the three
logo identity kinds are correctly preserved. **F remains unverified by this run** — it must pass
before any fix is accepted.

## 8. `do_logos` vs `do_purge`

**Exact safety invariant `87ad84c` added to `do_purge`** (lines ~2704–2745): an image is preserved
when `(image_kind ∈ ACCEPTED_IMAGE_KINDS AND image_verified_at IS NOT NULL)`, while the pre-existing
logo-identity skip is retained; only images with **no acceptance** are cleared.

| | `do_purge` (post-`87ad84c`) | `do_logos` (current) |
|---|---|---|
| Imports | `ACCEPTED_IMAGE_KINDS` **and** `LOGO_IDENTITY_KINDS` | `LOGO_IDENTITY_KINDS` only |
| Guard set | accepted kinds + identity marks | identity marks only |
| `program_image` | preserved | **destroyed** |
| `official_banner` | preserved | **destroyed** |
| Same invariant violated? | — | **YES** |

**Do the two stages have legitimately different responsibilities?** Partly, and this is why
`do_logos` must not be patched by copy-paste. `do_purge` is pure garbage collection: nothing in it
should ever remove a usable image. `do_logos` also performs a **replacement** function — it attaches
a logo when a record has none, so it has a legitimate reason to clear *unwanted* artwork in order to
put the approved logo in its place. The two are not interchangeable.

**Is the same guard semantically appropriate?** Yes, with one refinement. The guard should be
"preserve an image the pipeline **accepted**", tested as `image_kind ∈ ACCEPTED_IMAGE_KINDS`, with
`image_verified_at` as corroboration rather than the sole gate — because a row can be accepted and
later have its timestamp cleared by an unrelated path, and keying protection on the timestamp alone
would reopen this hole (exactly what `unverified_accepted_kind_still_survives` demonstrates).
Clearing genuinely unaccepted decoration must remain possible, or the stage loses its purpose.

## 9. Proven Current-Code Defect

**PROVEN DEFECT.**

- **Function:** `do_logos`, `backend/app/jobs/scholarzone_maintenance.py`
- **Predicate:** `row.image_kind not in LOGO_IDENTITY_KINDS`, at line 991
- **Fields destroyed:** all eight tracked image fields (lines 994–1004)
- **Failure shape:** an image accepted by the verification pipeline is deleted because it is not a
  logo, with no re-evaluation and no history row
- **Exact reason acceptance is disregarded:** the guard set omits `ACCEPTED_IMAGE_KINDS` entirely.
  The comment at lines 988–990 encodes the faulty premise that any non-logo image is disposable
  decoration.

**Secondary defect (also proven by reproduction):** persistence is conditional on `attached > 0`
(line 1028), so destructive edits and useful edits commit or vanish together.

## 10. Unknowns

- **UNKNOWN:** whether `do_logos` is the writer of the **October 3** reversion. The audit began
  2026-10-04 08:34 UTC, roughly a day later. I have not established when this predicate was
  introduced, so I make no claim about October 3.
- **UNKNOWN:** whether ID 130 and ID 554 were cleared by this same predicate. ID 130 was written by
  `maintenance.logos` at 08:38:28 with `image_kind` unset at that moment, which is a different shape.
- **UNKNOWN:** why dispatch run 37191466917 was cancelled.
- **UNKNOWN:** whether other records were silently damaged by this predicate in production. The audit
  contains 8 `maintenance.logos` events total; they have not all been attributed.
- **UNKNOWN:** the true scale of the commit-conditional persistence hazard.

## 11. Minimal Safe Fix Design

Design only — **not implemented**, pending authorisation.

Single predicate change at line 991, plus one commit change:

1. **Preserve on acceptance.** Replace the identity-only test with a test that also preserves
   `image_kind ∈ ACCEPTED_IMAGE_KINDS`. Existing logo-identity skipping is retained unchanged.
2. **Decouple persistence from attachment.** Commit whenever the stage mutated anything — track a
   `cleared` counter and commit if `attached or cleared` — so destructive and useful writes no longer
   share a fate.
3. **Leave everything else alone:** no change to the attach path, verification semantics, public
   visibility, ingestion, `do_purge`, or any scholarship ID. No special-casing.

Explicitly rejected alternatives:

- **Copying `do_purge`'s guard verbatim** — it keys on `image_verified_at IS NOT NULL`, which would
  leave the hole open for an accepted kind whose timestamp was cleared elsewhere.
- **Disabling clearing entirely** — breaks the stage's purpose and legitimate cleanup.
- **Gating on `is_verified`** — unrelated field, wrong semantics.

## 12. Why This Does / Does Not Explain October 3

**Does explain, with direct evidence:** the ID 14 reversion of 2026-10-04 08:38:28 UTC. Proven
production audit row, deterministic reproduction against the real stage, and a single code path that
yields exactly that transition.

**Does NOT explain October 3, and I do not claim it does.** The audit did not exist then. History
rows 208 and 406 survive, which excludes a database rollback. Whether this predicate existed on
October 3, and whether it acted on 14/130/554 at that time, is **UNKNOWN**. The unrecorded-writer
class remains the standing hypothesis for that date. `87ad84c` remains an independent latent-defect
fix for `do_purge`, not the October 3 root-cause fix.

## 13. Recommendation

1. **Fix `do_logos`** per Section 11 — the defect is proven and the fix is two predicates.
2. **Correct the `legitimate_cleanup_is_not_broadly_disabled` harness** and confirm it passes, so
   legitimate cleanup is demonstrably preserved before the fix is accepted.
3. **Run the full suite** and compare against baseline: known pre-existing failure
   `test_efficiency_safety.py::test_the_retry_shares_the_concurrency_group`; `neon_migration` may fail
   in a fresh worktree because `migration_export.sql` is untracked.
4. **Attribute the remaining 8 `maintenance.logos` audit events** and assess production damage scope.
5. **Do not restore the 18 purged images** until forensic evidence is complete; that is a separate
   decision.
6. **Phase 6 remains open.** This code fix addresses a proven mechanism; it does not substitute for
   the scheduled-cycle observation, and it must not be reported as one.

**Phase 7 remains unauthorised pending explicit approval to implement the Section 11 fix.**