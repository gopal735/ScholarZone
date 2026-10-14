# IMAGE_PURGE_FORENSICS_FINAL.md

**Investigation type:** READ-ONLY forensic analysis
**Date:** 2026-10-04 (evidence window 09:11Z – 09:25Z)
**Production:** `scholarzone-fwzj` (Vercel Services, GitHub auto-deploy from `master`)
**Trigger:** post-fix forensic review of the production maintenance purge

## Safety compliance

| Rule | Status |
|---|---|
| No DB UPDATE/DELETE/INSERT | Held — only `SELECT`-only scripts were executed |
| No image repair / restoration | Held |
| No `images`/`logos`/`repair` stage run | Held |
| No deployment / schema change / migration | Held — `install_image_audit.py` was deliberately **not** run |
| No commits / force push / destructive git | Held — `git worktree add`/`remove` only |
| Auto-delete, Match 2.0, Count Intelligence, Admin Verification, dashboard untouched | Held |

**Read-only tooling used.** `image-audit-check.yml` was **rejected** as a vehicle because it runs
`install_image_audit.py` (a schema write). All queries were instead dispatched through
`db-state-check.yml`, which performs no install step, running only scripts verified SELECT-only by
source inspection: `dump_image_audit.py`, `maintenance_timeline.py`, `image_audit_trail.py`,
`image_state_audit.py`.

---

## 1. Executive Summary

The 18 images cleared by the production purge are **fully identified by direct evidence**. The
`scholarship_image_audit` PostgreSQL trigger was live during the purge and recorded every one of them
with `writer_context = 'maintenance.purge'`.

The central finding is that **the purge cleared 18 images but only 16 records left the public
catalogue**, and the 16 that dropped were records whose images carried verification timestamps yet an
`image_kind` outside the accepted set. The purge predicate requires
`image_kind ∈ ACCEPTED_IMAGE_KINDS` before it will spare a verified image, so a verified image with an
empty or unrecognised `image_kind` is treated as disposable. That is the mechanism behind the
366 → 350 public drop, and it is **pre-existing policy, not a regression**.

Three material limitations qualify everything below:

1. **The audit's first event is `2026-10-04 08:34:18`.** Any image mutation before that instant is
   permanently invisible. The original 14/130/554 reversion predates the instrumentation and
   **cannot** be reconstructed from it.
2. **`before_values` are stored but unreachable** for arbitrary IDs. Only `dump_image_audit.py`
   prints them and it hardcodes `TARGET_IDS = (14, 130, 554)`. No script accepts an ad-hoc query, and
   adding one would require a commit (forbidden). Per-ID pre-purge image values for the other 15
   targets therefore **cannot** be established.
3. **A concurrent actor was actively writing to production throughout.** Public count moved
   350 → 353 and audit rows 71 → 74 *during this investigation*. Several figures below are
   point-in-time, not stable.

---

## 2. Exact 18 Purged IDs

**PROVEN** from `scholarship_image_audit` where `writer_context = 'maintenance.purge'` and
`changed_fields` = `image_url, image_source_url, image_source_type, image_alt_text, image_verified_at`:

| # | ID | # | ID | # | ID |
|---|---|---|---|---|---|
| 1 | **539** | 7 | **569** | 13 | **609** |
| 2 | **548** | 8 | **575** | 14 | **610** |
| 3 | **550** | 9 | **600** | 15 | **612** |
| 4 | **557** | 10 | **601** | 16 | **621** |
| 5 | **558** | 11 | **602** | 17 | **623** |
| 6 | **564** | 12 | **603** | 18 | *(count = 18)* |

Corroboration, independent of the audit:
- `maintenance_runs` id **246**, `09:01:41 → 09:01:48`, status `ok`,
  `counts = {'image_non_logo_cleared': 18, ...}`
- Stage output: `image_rows: 422`, `cleared: 18`, `preserved_accepted: 404`,
  `kept_identity_kinds: ['official_government','official_logo','official_university']`
- Arithmetic: `422 = 18 cleared + 404 preserved`

**Not all `maintenance.purge` rows are mine.** The writer-context tally shows
`maintenance.purge n=32` spanning `08:39:22 → 09:01:47`. The 18 above are precisely those at
`09:01:47.531540+00:00` (run 246). The other 14 belong to the concurrent actor's run 240
(`08:30:17 → 08:39:45`).

---

## 3. Evidence Table

| ID | writer_context | changed_at (UTC) | changed_fields | image_kind in set? |
|---|---|---|---|---|
| 539 | `maintenance.purge` | 09:01:47.531540 | url, source_url, source_type, alt_text, verified_at | not changed |
| 548 | `maintenance.purge` | 09:01:47.531540 | same | not changed |
| 550 | `maintenance.purge` | 09:01:47.531540 | same | not changed |
| 557 | `maintenance.purge` | 09:01:47.531540 | same | not changed |
| 558 | `maintenance.purge` | 09:01:47.531540 | same | not changed |
| 564 | `maintenance.purge` | 09:01:47.531540 | same | not changed |
| 569 | `maintenance.purge` | 09:01:47.531540 | same | not changed |
| 575 | `maintenance.purge` | 09:01:47.531540 | same | not changed |
| 600 | `maintenance.purge` | 09:01:47.531540 | same | not changed |
| 601 | `maintenance.pecret`→`maintenance.purge` | 09:01:47.531540 | same | not changed |
| 602 | `maintenance.purge` | 09:01:47.531540 | same | not changed |
| 603 | `maintenance.purge` | 09:01:47.531540 | same | not changed |
| 607 | `maintenance.purge` | 09:01:47.531540 | same | not changed |
| 609 | `maintenance.purge` | 09:01:47.531540 | same | not changed |
| 610 | `maintenance.purge` | 09:01:47.531540 | same | not changed |
| 612 | `maintenance.purge` | 09:01:47.531540 | same | not changed |
| 621 | `maintenance.purge` | 09:01:47.531540 | same | not changed |
| 623 | `maintenance.purge` | 09:01:47.531540 | same | not changed |

Additional events on 3 of the 18, from the **concurrent** actor's `images` stage after the purge:

| ID | writer_context | changed_fields |
|---|---|---|
| 539, 548, 550 | `maintenance.images` | `image_evaluation_status`, `image_evaluated_at` |

### Two distinct clearing fingerprints (observed, significant)

| Fingerprint | changed_fields | Seen on |
|---|---|---|
| **A** — spares `image_kind` | url, source_url, source_type, alt_text, verified_at | all 18 purge events, and audit row [27] on ID 130 |
| **B** — also nulls `image_kind` | url, source_url, source_type, **kind**, verified_at | audit row [5] on ID 14 (`maintenance.logos`), row [66] on ID 130 (`unknown`) |

Fingerprint A leaves a **stale `image_kind` on a row with no image**. This is a real contract
violation generator and is visible in the current state (§4).

### Per-ID reconstruction — what is NOT recoverable

`title`, `image_source_url`, `image_source_type`, `image_verified_at` (pre-clear), `image_kind`
(pre-clear), `image_evaluation_status` (pre-clear) and public-visibility state (pre-purge) are
**NOT RECOVERABLE** for these 18. The audit stores them in `before_values`, but no runnable
read-only script exposes `before_values` for arbitrary IDs, and no ad-hoc SQL path exists. This is
recorded as a tooling gap, not guessed at.

---

## 4. Public Visibility Impact

Measured directly either side of run 246 (worker `stats` stage, read-only):

| Metric | Pre-purge (run 37190757477) | Post-purge (run 37191067046) | Δ |
|---|---|---|---|
| `total_records` (storage) | 451 | 451 | **0** |
| `with_image` | 422 | 404 | **−18** |
| `without_image` | 29 | 47 | **+18** |
| `identity_marks` | 405 | 405 | 0 |
| `archived_hidden` | 35 | 35 | 0 |
| `public_visible` | **366** | **350** | **−16** |

Public API after purge: `total 350`, `with_image 350`, `verified_active 350`, `countries 43`,
`fully_funded 114`, `with_official_source 345`.

**Which 2 were already non-public — derived, not directly observed.** 18 images were cleared but
public fell by 16, therefore **16 of the 18 were public before the purge and 2 were already
non-public**. Naming which 2 is not possible: the audit does not record visibility, and no
visibility snapshot exists for the pre-purge instant.

### Why 16 dropped — mechanism (evidence-backed)

The purge predicate spares a verified image only when
`image_kind ∈ ACCEPTED_IMAGE_KINDS` (the five canonical values). A record can satisfy the
**public image gate** (which requires a verified official image) while failing the **purge
predicate** (which additionally requires a recognised `image_kind`). Such a record is public, and
purge deletes its image, so it immediately fails the public gate and leaves the catalogue.

The purge cleared `image_verified_at` on all 18, so each carried a verification timestamp — i.e. all
18 possessed verification evidence that was destroyed. Combined with `image_kind` being *absent from
`changed_fields`*, the cleared rows had an `image_kind` that was either empty or outside the accepted
set. This is the exact shape ID 554 still shows (`image_verified_at` set, `image_kind` empty).

**This is pre-existing policy.** The 87ad84c protection only covers the five enumerated kinds; it does
not cover "verified but unrecognised kind".

### Live contract violations observed after the purge

`image_state_audit.py` (read-only), at ~09:22Z:

| Check | Count | Detail |
|---|---|---|
| storage rows / public rows | 451 / **353** | public has since moved 350 → 353 (concurrent actor) |
| `I1_verified_at_without_image` | 1 | id **563** `source_blocked`, kind=None, verified_at=2026-10-01 |
| `I2_status_verified_without_image` | 1 | id **613** `status=verified kind=official_logo verified_at=None` |
| `I3_status_verified_but_not_in_public` | 0 | — |
| `I5_image_without_provenance` | 0 | — |
| `I6_image_without_kind` | **3** | ids **557, 564, 569** — 3 of the purged 18, re-evaluated after the purge with new `verified_at` (09:19:54 / 09:20:53 / 09:21:22) and no kind |

`contract clean: False`. IDs 557, 564 and 569 are a **direct downstream consequence** of the purge:
their images were removed, the concurrent actor's `images` stage then re-stamped `image_verified_at`
without re-establishing an image or a kind, producing an inconsistent row.

---

## 5. 14/130/554 Timeline

All rows below are **PROVEN** audit records. `app='pgbouncer'` on every event.

### ID 14 — "Alberta / ETH excellence scholarship"

| Audit row | Time (UTC) | writer_context | Fields | Before → After |
|---|---|---|---|---|
| [3] | 08:35:23.391597 | **`unknown`** | url, source_url, source_type, kind, verified_at | all `None` → `https://ethz.ch/.../imageCarousel...` (**image SET**) |
| [5] | 08:38:28.768558 | `maintenance.logos` | url, source_url, source_type, **kind**, verified_at | ethz.ch URL → all `None` (**image CLEARED — fingerprint B**) |
| [68] | 09:09:52.755900 | **`unknown`** | url, source_url, source_type, kind, verified_at | all `None` → ethz.ch URL (**image SET again**) |

Current state: `verification_status='needs_review'`, `verified=False`, `image_url=<null>`,
`image_kind=''`, `image_verified_at=''`.

The 08:38:28 clearing is **PROVEN** to be the `logos` stage. The 08:35:23 and 09:09:52 writes are
**UNATTRIBUTED** — no writer set the transaction-local context.

### ID 130 — "Aga Khan Foundation International"

| Audit row | Time (UTC) | writer_context | Fields | Before → After |
|---|---|---|---|---|
| [1] | 08:34:18.727518 | `maintenance.images` | evaluation_status, evaluated_at | `verified` → `source_blocked` |
| [6] | 08:38:28.768558 | `maintenance.logos` | url, source_url, source_type, alt_text, verified_at | `None` → `https://akf.org/.../favicon.svg`, alt `Aga Khan Foundation` (**image SET**) |
| [27] | 08:39:23.519402 | **`maintenance.add`** | url, source_url, source_type, alt_text, verified_at | akf.org favicon → all `None` (**image CLEARED — fingerprint A**) |
| [66] | 09:07:28.287998 | **`unknown`** | **kind**, evaluation_status, evaluated_at | `official_logo` → `None` (**kind CLEARED**) |
| [69] | 09:09:53.763583 | **`unknown`** | evaluation_status, evaluated_at | `None` → `source_blocked` |

Current state: `needs_review`, `verified=False`, `image_url=<null>`, **`image_kind='official_logo'`**
(stale — kind survives while the image is gone), `image_verified_at=''`.

**Anomaly worth flagging:** the `add` stage cleared this image (row [27]), but the only image code in
that stage is `scholarzone_maintenance.py:1319` — `if record.image_url and not row.image_url:` — which
**fills an empty slot and cannot clear**. No `on_conflict_do_update` / `bulk_update_mappings` /
`bulk_save_objects` exists anywhere in the job. The specific statement that nulled ID 130's image is
therefore **UNIDENTIFIED**. Note the writer context is set once per stage, so any code the `add` stage
*invokes* would inherit `maintenance.add`.

### ID 554

| Audit row | Time (UTC) | writer_context | Fields | Before → After |
|---|---|---|---|---|
| [67] | 09:07:28.586270 | **`unknown`** | source_url, source_type, alt_text, verified_at, evaluation_status, evaluated_at | alt `Wellcome`, source `https://wellcome.org/grant-funding/schemes/early-career-awards`, type `official_ng…` → all `None` |
| [70] | 09:10:07.854878 | **`unknown`** | evaluation_status, evaluated_at | `None` → `no_official_image` |
| [71] | 09:10:08.761768 | **`unknown`** | evaluated_at | touch only |

Current state: `needs_review`, `verified=False`, `image_url=<null>`, `image_kind=''`,
**`image_verified_at='2026-10-01T00:00:00Z'`**.

ID 554's audit history begins at 09:07 — its image was set **before** the instrumentation existed, so
the original acquisition is invisible. Its present shape (`verified_at` set, kind empty, no image)
is precisely fingerprint A: a verified image whose kind was never recognised, later cleared.

### 14/130/554 — what is NOT explained

The task asks why these three "previously lost/reverted their images". The audit attributes the
**08:34–09:10** activity completely or partially, but the instrumentation **starts at 08:34:18**.
Any earlier loss — the original reversion under investigation — left no audit row, and no snapshot
or restore record was captured for it. `scholarship_restore_records` and `scholarship_snapshots`
exist as tables but the timeline script aborted before querying them
(`ObjectNotExecutableError` — its own bug: a raw SQL string passed without `text()`).

**I therefore cannot claim a root cause for the original 14/130/554 reversion.**

---

## 6. Hypothesis Matrix

| # | Hypothesis | Verdict | Basis |
|---|---|---|---|
| 1 | `purge` / `do_purge` | **PROVEN** for the 18 (rows [48]–[65], ctx `maintenance.purge`). **DISPROVEN** as the cause of ID 130's 08:39 clear and ID 14's 08:38 clear — those carry different contexts | audit |
| 2 | `images` stage | **PROVEN** contributor: ID 130 row [1] `verified → source_blocked`; post-purge re-evaluation of 539/548/550 and of 557/564/569 | audit |
| 3 | `logos` stage | **PROVEN**: ID 14 row [5] image cleared; ID 130 row [6] image set — both `maintenance.logos` at 08:38:28 (same txid 281764) | audit |
| 4 | discovery writer | **NO EVIDENCE** — no audit row carries a discovery context; `discovery`/`enrich` endpoints are POST-only and were not called | audit, code |
| 5 | enrichment writer | **NO EVIDENCE** — enrichment writes image *fields* only via `enrichment` runs; no matching audit rows in window | audit |
| 6 | admin image review | **NO EVIDENCE** — `admin_image_review` is the only non-maintenance writer that sets context, and appears **0 times** in the audit. No admin decision endpoint was called in this investigation | audit |
| 7 | raw SQL / uninstrumented writer | **PLAUSIBLE BUT UNPROVEN** — 8 events carry `writer_context='unknown'`, which is exactly the signature of a writer that never set the transaction-local GUC. Candidates that do not set it: `data/audit_images.py`, `data/logo_fallback.py`, `data/resolve_generic_images.py`, `data/backfill_alt_text.py`, `services/image_coverage_runner.py`, `routers/verification.py` image endpoints, and every `scripts/*.py` repair script | audit + code |
| 8 | transaction rollback | **NO EVIDENCE** for these events (they are committed rows). But it is a **proven structural blind spot**: the audit INSERT is in the same transaction, so any rolled-back image mutation leaves no trace | trigger design |
| 9 | restore / PITR | **NO EVIDENCE** — no restore record was retrieved; the query aborted | tooling |
| 10 | another maintenance stage | **PROVEN for `maintenance.add`** on ID 130 (row [27]), with the caveat that the clearing statement inside that stage is **UNIDENTIFIED** | audit + code |
| 11 | concurrent actor / worktree / deployment | **PROVEN as an active factor** — a second actor ran maintenance throughout (runs 240, 247–250); writer contexts `maintenance.add`/`maintenance.logos`/`maintenance.images` at 08:34–08:39 belong to that run, not to the fix work. Run 250 was `running` during this investigation | `maintenance_runs`, audit |

---

## 7. Audit Coverage

**Mechanism.** `backend/app/image_audit.py` installs
`trg_scholarships_image_audit AFTER UPDATE ON scholarships FOR EACH ROW WHEN (<tracked cols changed>)`.
Writer identity comes from the transaction-local GUC `scholarzone.writer_context`, read as
`COALESCE(NULLIF(current_setting('scholarzone.writer_context', true), ''), 'unknown')`.

**Covered — PROVEN working:**
- All 8 tracked columns: `image_url`, `image_source_url`, `image_source_type`, `image_kind`,
  `image_alt_text`, `image_verified_at`, `image_evaluation_status`, `image_evaluated_at`
- Per-field granularity (`changed_fields` lists only what moved)
- Full before/after values — **stored**, with `application_name`, `client_addr`, `transaction_id`
- Any writer path, including bulk and ORM writes, **provided the statement is an UPDATE and commits**
- Append-only enforcement: `BEFORE UPDATE OR DELETE` and `BEFORE TRUNCATE` guard triggers reject
  audit-row rewriting

**Not covered — invisible:**

| Gap | Consequence |
|---|---|
| **`AFTER UPDATE` only** | `INSERT` of a row carrying an image produces **no** audit row |
| **No `DELETE` trigger** | Row deletion (e.g. `purge_closed`, auto-delete) leaves no per-row image audit |
| **Same-transaction rollback** | The audit INSERT rolls back with the mutation — a reverted image write is invisible |
| **`writer_context` defaults to `unknown`** | Only 2 call-sites set it: `_run_stage` (`scholarzone_maintenance.py:299`, covering every maintenance stage) and `admin_image_review.py:145`. Every other writer — data scripts, coverage runner, verification HTTP endpoints, one-off repair scripts — is unattributed |
| **`application_name` is always `pgbouncer`** | Connection pooling erases per-client attribution; `client_addr` is the pooler |
| **Retention starts at install** | First event `2026-10-04 08:34:18`. All earlier history is permanently lost |
| **`before_values` not retrievable** | `dump_image_audit.py` hardcodes `(14,130,554)`; `image_audit_trail.py` omits before/after; no ad-hoc SQL. Stored evidence is practically inaccessible |

**Is it sufficient to identify the next real image mutation?**
**Conditionally yes, and no.**

- *Yes* for committed UPDATE mutations performed by a maintenance stage or by admin image review —
  those are attributed precisely, as demonstrated here.
- *No* for: INSERTs, DELETEs, rolled-back writes, and any writer outside those two context-setters —
  roughly the majority of the ~15 mutation paths in §8, including every `data/*.py` script and both
  `routers/verification.py` image endpoints.

The 8 `unknown` events in this very window are the practical demonstration: they are recorded but
**not attributable**, so they cannot be closed.

---

## 8. All Image Mutation Paths

`git grep -E "\.(image_url|image_source_url|image_source_type|image_kind|image_alt_text|image_verified_at|image_evaluation_status|image_evaluated_at)\s*="` over `backend/app`.
"Accepted protected?" = does the code spare verified/accepted images. "Context?" = does it set the
audit writer context.

| # | File : lines | Function / stage | Mutation | Accepted protected? | Verified overwriteable? | Context recorded? | Real stage/func executed by tests? |
|---|---|---|---|---|---|---|---|
| 1 | `jobs/scholarzone_maintenance.py:994-1004` | `do_logos` — clear branch | clears url/source/type/kind/alt/verified + evaluation | **No** — unconditional clear of the stored image | Yes | Yes (`maintenance.logos`) | Yes — cleared ID 14 in production |
| 2 | `…:1010-1024` | `do_logos` — set branch | sets all image fields + `VERIFIED` | n/a (set) | n/a | Yes | Yes |
| 3 | `…:1319-1324` | `do_add` | fills **empty** image slot only, stamps `verified_at=today` | Yes (guarded by `not row.image_url`) | No | Yes (`maintenance.add`) | **No** — cannot clear, yet ID 130 was cleared under this context (§5). **Statement UNIDENTIFIED** |
| 4 | `…:2753-2764` | `do_purge` | **clears url/source/type/kind/alt/verified + evaluation** | **Partially** — only when kind ∉ accepted set **or** no `verified_at` | **Yes, if kind unrecognised** — this is the 18 | Yes (`maintenance.purge`) | Yes — 16 new tests execute it |
| 5 | `services/image_discovery_orchestrator.py:255-267` | discovery clear helper | clears url/source/type/kind/alt/verified + evaluation | **No** | Yes | **No** → `unknown` | Partial |
| 6 | `services/scholarship_image_verifier.py:287-294` | verifier persist | sets url/source/type/kind/verified/alt | n/a | n/a | **No** → `unknown` | Yes |
| 7 | `…:330-335` | verifier clear | clears url/source/type/kind/verified/alt | **No** | Yes | **No** → `unknown` | Yes |
| 8 | `…:211-249` | verifier alt/kind/source paths | sets alt/kind/source_type/verified | n/a | n/a | **No** → `unknown` | Yes |
| 9 | `…:510` | verifier re-stamp | sets `verified_at` | n/a | n/a | **No** → `unknown` | Yes |
| 10 | `services/image_coverage_runner.py:266-267` | coverage evaluator | sets `evaluation_status` + `evaluated_at` | n/a | n/a | **No** → `unknown` | Yes |
| 11 | `services/admin_image_review.py:212-213` | admin review approve | sets `evaluation_status=VERIFIED` + `evaluated_at` | n/a | n/a | **Yes** (`admin_image_review`) — only non-maintenance setter | Yes |
| 12 | `services/image_validator.py:862, 885, 1297, 1313, 1331` | validator classification | sets/clears `image_kind` on a **result object**, not the row | n/a | n/a | n/a (not a row write) | Yes |
| 13 | `routers/verification.py:332` | `POST /internal/images/verify` | sets `image_kind` via orchestrator/verifier | depends on callee | depends on callee | **No** → `unknown` | Yes |
| 14 | `routers/verification.py:364` | `POST /internal/images/revalidate` | conditional update path | depends | depends | **No** → `unknown` | Yes |
| 15 | `data/audit_images.py:322-346` | one-off audit script | clears then re-sets all image fields | **No** (unconditional clear) | Yes | **No** → `unknown` | **No** |
| 16 | `data/logo_fallback.py:138-144` | one-off fallback script | sets all image fields + `VERIFIED` | n/a | n/a | **No** → `unknown` | **No** |
| 17 | `data/resolve_generic_images.py:79-84` | one-off script | clears all image fields | **No** | Yes | **No** → `unknown` | **No** |
| 18 | `data/backfill_alt_text.py:40` | one-off script | overwrites `image_alt_text` | n/a | n/a | **No** → `unknown` | **No** |

**Additional writers invisible to this grep:** `scripts/triple_image_repair.py`,
`scripts/two_record_image_repair.py`, `scripts/phase_8_image_dry_run.py`, and any raw SQL. None set
writer context.

**Highest-risk findings (read-only observations, no change made):**
1. **Path 4 (`do_purge`)** destroys verification evidence on verified images whose `image_kind` is not
   one of the five canonical values. This is what removed 16 records from the public catalogue.
2. **Paths 15 and 17** clear image fields unconditionally with no accepted-image guard and no writer
   context.
3. **Path 3 anomaly** — a stage that provably cannot clear images cleared one in production; the
   mechanism is unidentified and is a genuine blind spot.
4. **14 of 18 paths set no writer context**, so any of them firing again would again yield
   `unknown`.

---

## 9. Proven vs Unproven Findings

### PROVEN (direct evidence)
- The 18 purged IDs, their `writer_context`, their `changed_fields`, and the run
  (`maintenance_runs` 246, `image_non_logo_cleared: 18`).
- `image_rows 422 = cleared 18 + preserved_accepted 404`; `kept_identity_kinds` = the three canonical
  identity kinds.
- Storage total unchanged at 451; zero rows deleted.
- `with_image 422 → 404`; `public_visible 366 → 350`.
- 16 of the 18 were public pre-purge; 2 were already non-public (arithmetic from two measurements).
- ID 14's 08:38:28 image clear was the **`logos`** stage; its image was later re-set by an
  **unattributed** writer at 09:09:52.
- ID 130's image was set by **`logos`** (08:38:28) and cleared under **`maintenance.add`**
  (08:39:23); its `official_logo` kind was nulled by an **unattributed** writer at 09:07:28.
- ID 554's provenance/alt/verified fields were cleared by an **unattributed** writer at 09:07:28.
- The `images` stage moved ID 130 from `verified` to `source_blocked` at 08:34:18.
- The audit is `AFTER UPDATE` only; INSERT and DELETE are uncovered; rollback erases evidence.
- IDs 557, 564, 569 currently violate contract check `I6_image_without_kind`.

### NOT PROVEN — explicitly unclaimed
- **The root cause of the original 14/130/554 image reversion.** The audit begins at 08:34:18; the
  original loss predates it. No causal claim is made.
- **Pre-clear field values for the 18** (`image_url`, `image_source_url`, `image_source_type`,
  `image_kind`, `image_verified_at`, `image_evaluation_status`) and their pre-purge visibility.
  `before_values` exist in the database but are unreachable with current tooling.
- **Which specific 2 of the 18 were already non-public.**
- **The identity of the `unknown` writer** behind 8 audit events, including ID 14's 09:09 re-set,
  ID 130's 09:07 kind clear, and all three ID 554 events.
- **The statement inside `maintenance.add` that cleared ID 130's image.**
- **Whether the 18 purge clears were individually correct.** They followed the predicate as written;
  whether each *should* have been spared is a policy judgement requiring the pre-clear state.

---

## 10. Restoration Readiness

**NOT READY. Restoration is not proposed.**

| Requirement | Status |
|---|---|
| Authoritative pre-clear `image_url` for the 18 | **Unavailable** — `before_values` unreachable without a new script (needs a commit) |
| Pre-clear `image_kind` / `verified_at` / `evaluation_status` | **Unavailable** — same reason |
| Which 16 were public vs the 2 that were not | **Unavailable** — no visibility snapshot |
| Whether each image was trustworthy | **Undecidable** — the evidence needed to judge was cleared |
| Snapshot/restore source | **Absent** — `purged-records-snapshot` is the **closed-records** archive dated 2026-10-01 and contains no image clears |

Two further cautions:
- Three of the 18 (557, 564, 569) have **already been re-evaluated** by the concurrent `images` stage,
  so any restore would race a moving target.
- A further image mutation happened on **ID 14 at 09:09:52**, after the purge. Its state is not the
  pre-purge state.

Restoring from `before_values` would in principle be possible **if** a read-only accessor were added
or an operator with direct database access queried it. That is a decision for the owner, and it is a
write. **Nothing was restored.**

---

## 11. Recommended Next-Safe Action

Strictly ordered, read-only-first, smallest-privilege. **None of this was performed.**

1. **Freeze the concurrent writer before any further forensics.** Production is being mutated
   continuously (public 350 → 353, audit 71 → 74, run 250 `running`). Any snapshot taken now is
   immediately stale. This is the single highest-value next step and requires no code change.

2. **Make the stored audit evidence readable, read-only.** Add a script that prints
   `before_values`/`after_values` for arbitrary IDs (or extend `image_audit_trail.py` with a
   `--full` flag). This is an additive, read-only change that converts today's hardest limitation into
   answerable questions. It is a commit, so it is out of scope here.

3. **Instrument the two structural blind spots.** Extend the trigger to `AFTER INSERT OR DELETE`, or
   document them as accepted gaps. Note `AFTER DELETE` cannot carry `changed_fields` meaningfully, so
   a row-delete audit likely needs its own shape.

4. **Set `writer_context` on the remaining writers**, starting with the highest-risk: `do_purge`,
   `image_discovery_orchestrator` clear helper, `scholarship_image_verifier`, `image_coverage_runner`,
   `data/audit_images.py`, `data/resolve_generic_images.py`, and the `routers/verification.py` image
   endpoints. This would convert all 14 currently-unattributed paths into attributable ones.

5. **Review the purge predicate — the actual cause of the 366 → 350 drop.** The rule
   `kind ∈ ACCEPTED_IMAGE_KINDS` should probably become "spare any image with `image_verified_at`
   set", independent of kind, so an unrecognised kind cannot destroy verification evidence. This is
   a policy change and should be decided by the owner, ideally with the pre-clear data from step 2 in
   hand.

6. **Reconcile the three live contract violations** (ids 563, 613, and 557/564/569) once the writer
   freeze in step 1 holds. ID 613 claims `status=verified` with `kind=official_logo` and
   `verified_at=None` and no image — that inconsistency currently has no writer of record.

7. **Do not restore the 18** until step 2 exists and the original state can actually be read.

---

### Appendix — evidence sources (all read-only)

| Source | Run / ref | What it established |
|---|---|---|
| `dump_image_audit.py` via `db-state-check` | `37191336885` | audit totals (71 rows, 08:34:18 → 09:10:08), writer-context distribution, unattributed count, full 14/130/554 histories, 15 most-recent events |
| `maintenance_timeline.py` via `db-state-check` | `37191579961` | `maintenance_runs` (246 = the purge, 239 = the NameError failure, 240 = concurrent run, 250 running); table presence incl. `scholarship_snapshots`, `scholarship_restore_records`. **Aborted** on its own `ObjectNotExecutableError` before target-state and restore queries |
| `image_audit_trail.py --ids 1..700 --since-id 47` via `db-state-check` | `37191704677` | complete audit detail for all 21 IDs with rows past #47 → **the exact 18 purge IDs** |
| `image_state_audit.py` via `db-state-check` | `37191917932` | 451 storage / 353 public / 98 storage-only; contract violations I1, I2, I6 |
| Production maintenance runs | `37190757477`, `37190793058`, `37190839296`, `37190901230`, `37191067046` | stage results, `cleared: 18`, `preserved_accepted: 404`, pre/post stats |
| `image_audit.py`, `image_discovery_orchestrator.py`, `scholarszone_maintenance.py` (static) | `origin/master` @ investigation time | trigger shape, tracked fields, writer-context mechanism, all mutation paths |

*Report generated read-only. No production data was modified, no secret was read or exposed, no
commit was made.*
