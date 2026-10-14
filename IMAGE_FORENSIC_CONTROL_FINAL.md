# IMAGE FORENSIC CONTROL — PHASE 6.2 FINAL

**Mode:** READ-ONLY. **No repair, no restore, no image stage, no maintenance dispatch, no production
data change, no deploy.** One exception, declared: a **read-only** introspection script was pushed to a
**non-master branch** (`forensics/pg-audit-catalog-readonly`) because no existing script performs
PostgreSQL catalog introspection, and pushing to master would have triggered CI → deployment →
`create_image_audit_schema()` on startup, which executes DDL against the very boundary under
examination. `origin/master` was verified unmoved (`c405b49`) throughout. No application file was
modified. No stage, scheduler, `do_logos`, `do_purge`, or audit schema was touched.

**Evidence base:** live production PostgreSQL via run `37193180489` (SELECT-only), plus
`forensic_preflight.py`, `db_state.py`, `scholarship_image_audit`, and
`scholarship_verification_history`. `validate_audit_ddl.py` was **not** run: it executes DDL inside a
rolled-back transaction and therefore validates "would this install work", not "what is installed".

---

## 1. Executive Summary

The audit boundary is **materially stronger than I previously reported, and my previous report was
wrong.** Live catalog shows **three** triggers, not one: DELETE and TRUNCATE **are** guarded. My claim
that "the immutable guard is BEFORE UPDATE only, so DELETE/TRUNCATE are unguarded" is **DISPROVEN**.

Three findings dominate:

1. **`do_logos` is a proven image-destroying writer, by design.** `logo_only` mode calls
   `_clear_stored_image()` for any record whose stored image is not an identity mark, with the
   in-source comment *"A stored programme photo must not survive a logo-only sweep."* It cleared **6
   records including id 14** at 08:38:28 (txn `281764`). Id 14's repaired image is `program_image` —
   therefore a standing deletion target for the next logos sweep.
2. **The "18 purged images" are identified**: `purge` stage, run `326171d202ec4a44`, 09:01:41,
   `cleared: 18` (audit txn `282670`).
3. **An unattributed writer is actively creating invalid state.** Five records (557, 564, 569, 603,
   618) now violate `I6_image_without_kind`, written by `writer_context='unknown'` at 09:19–09:29 —
   setting `image_url` and `image_verified_at` while leaving `image_kind` NULL.

**The audit cannot prove absence of mutation** (§4). Absence of an audit row is consistent with a
rolled-back write, an INSERT or DELETE on `scholarships`, or owner tampering. That inference is
withdrawn.

---

## 2. Current Production Snapshot (09:53 UTC, read-only)

| measure | value |
|---|---|
| storage `B` | **451** |
| public `A` | **358** (`A−B`=0, `B−A`=93, `A&B`=358) |
| audit rows | 91 at 09:33; writer tally below |
| `orphan_audit_rows` (audit row with no scholarship) | **0** |
| `I6_image_without_kind` (whole catalogue) | **5 → {557, 564, 569, 603, 618}** |
| …of which publicly visible | **{557, 564, 603}** |
| malformed rows / orphan reviews / duplicates | 0 / 0 / 0 |
| `candidate_since_null` / `_set` | 451 / 0 |

Writer distribution (PROVEN, live):

| writer_context | mutations | window |
|---|---|---|
| `maintenance.purge` | 32 | 08:39:22 → 09:01:47 |
| `maintenance.add` | 21 | all at 08:39:23.519402 |
| `unknown` | 19 | 08:35:23 → 09:29:44 |
| `maintenance.images` | 11 | 08:34:18 → 09:25:06 |
| `maintenance.logos` | 8 | all at 08:38:28.768558 |

**Residue worth flagging:** ids **611** (`image_kind='program_image'`, no image) and **613**
(`image_kind='official_logo'`, no image) carry the same kind-without-image corruption as the original
id 130.

---

## 3. Audit Trigger Inventory (live `pg_trigger`, run 37193180489)

### On `scholarship_image_audit`

| trigger | enabled | events | timing | granularity | function | SECURITY DEFINER | function settings |
|---|---|---|---|---|---|---|---|
| `trg_scholarship_image_audit_immutable` | **O** (origin, active) | **UPDATE + DELETE** | **BEFORE** | **ROW** | `scholarzone_image_mutation_guard()` | **False** | `None` |
| `trg_scholarship_image_audit_no_truncate` | **O** | **TRUNCATE** | **BEFORE** | **STATEMENT** | `scholarzone_image_mutation_guard()` | **False** | `None` |

### On `scholarships`

| trigger | enabled | events | timing | granularity | function | SECURITY DEFINER | function settings |
|---|---|---|---|---|---|---|---|
| `trg_scholarships_image_audit` | **O** | **UPDATE only** | **AFTER** | **ROW** | `scholarzone_record_image_mutation()` | **True** | `['search_path=public']` |

`scholarships` has **exactly one** non-internal trigger. There is **no AFTER INSERT and no AFTER
DELETE** trigger.

Guard body (verbatim): `RAISE EXCEPTION 'scholarship_image_audit is append-only; % is not permitted',
TG_OP USING ERRCODE = 'restrict_violation';` — a blanket refusal for any `TG_OP`, so it cannot be
bypassed by an unlisted event. The guard is not `SECURITY DEFINER` and pins no `search_path`, but it
resolves no object names, so `search_path` hijacking gives an attacker nothing here. The **record**
function *is* `SECURITY DEFINER` with `search_path=public` pinned — the correct hardening for a
privileged function, since it performs the audit `INSERT`.

### Ownership, grants, roles

| property | value |
|---|---|
| table owner | `neondb_owner` (audit, context and `scholarships` tables) |
| connected role | `neondb_owner`; `rolsuper=False`, `bypass_rls=True`, `createrole=True`, `createdb=True` |
| explicit grants on audit table | **only `neondb_owner`**: SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER |
| `PUBLIC` grants | **0** → `REVOKE … FROM PUBLIC` **is effective** |
| `has_table_privilege(current_user)` | SELECT/INSERT/UPDATE/DELETE/TRUNCATE all **true** (owner implicit rights) |
| other login roles | `cloud_admin` (**rolsuper=True**), `neon_service` (createdb, createrole, bypassrls) |
| RLS on any of the three tables | **not enabled** |

### Reconciling the contradiction — explicit

Both earlier reports were partly wrong, in opposite directions.

- The claim *"the immutable guard is BEFORE UPDATE only, so DELETE/TRUNCATE are unguarded"* is
  **DISPROVEN**. `trg_scholarship_image_audit_immutable` is `BEFORE … UPDATE + DELETE`, and
  `trg_scholarship_image_audit_no_truncate` is `BEFORE TRUNCATE`. My earlier reading came from the
  **SQLite** DDL, where only a `BEFORE UPDATE` guard exists — a divergence between dialects that I
  failed to check before generalising.
- The claim *"audit boundary safe: NO"* (owner retains UPDATE/DELETE/TRUNCATE) is a **false negative**.
  A PostgreSQL owner cannot have its own privileges revoked, so those bits read `true` for every owner
  regardless of `REVOKE`. `forensic_preflight.py` has since been corrected to say exactly this and to
  test the guards instead. **The `REVOKE … FROM PUBLIC` did work** (`public_grants=0`).

**Residual escape, PROVEN:** `neondb_owner` owns the table and holds the `TRIGGER` privilege, so it
can `DROP TRIGGER` or `ALTER TABLE … DISABLE TRIGGER` and then delete or rewrite audit rows. A
superuser (`cloud_admin`) or a `CREATEROLE` role can do the same and more. Closing this requires a
non-owner role and is out of this phase.

---

## 4. Audit Tamper / Integrity Model — evidence matrix

`UPDATE` on `scholarships` is captured by an `AFTER UPDATE … ROW` trigger with a null-safe
`IS DISTINCT FROM` `WHEN` clause over the 8 tracked columns. Everything else follows from what that one
trigger does *not* cover.

| Mutation type | Captured? | Durable after commit? | Tamper-resistant? | Writer context? |
|---|---|---|---|---|
| `UPDATE` (any of 8 image cols) | **Yes** | Yes | Owner can drop guard, then rewrite | Yes if `image_writer` used, else `unknown` |
| `UPDATE` (non-image cols only) | No (`WHEN` false) | n/a | n/a | n/a |
| `INSERT` into `scholarships` | **NO** — no AFTER INSERT trigger | n/a | n/a | n/a |
| `DELETE` from `scholarships` | **NO** — no AFTER DELETE trigger | n/a | n/a | n/a |
| `TRUNCATE scholarships` | **NO** | n/a | n/a | n/a |
| **Rolled-back `UPDATE`** | **NO** — audit `INSERT` is in the same transaction, so the rollback erases it | No | n/a | n/a |
| Bulk `UPDATE` | Yes (row trigger fires per row) | Yes | as above | as above |
| Raw SQL `UPDATE` | Yes | Yes | as above | as above |
| ORM `UPDATE` | Yes | Yes | as above | as above |
| Admin review write | Yes, **if** it writes an image column | Yes | as above | only if it uses `image_writer` |
| Maintenance stages | Yes | Yes | as above | Yes — `maintenance.<stage>` observed |
| Audit `UPDATE`/`DELETE` | Rejected by guard trigger | n/a | **Yes** against `UPDATE`/`DELETE` | n/a |
| Audit `TRUNCATE` | Rejected by statement guard | n/a | **Yes** | n/a |
| Audit row deletion after `DROP TRIGGER` | **Possible** | n/a | **NO** — owner escape | n/a |

### What the audit can and cannot support

**Can support:** that a *committed* `UPDATE` touching a tracked column occurred, its before/after
values, its transaction id, and a self-asserted writer label.

**Cannot support — and this inference is formally withdrawn:**

- ~~"No audit row means no mutation."~~ Invalid. A rolled-back write, an `INSERT`, a `DELETE`, or an
  owner-disabled trigger all produce no row.
- ~~"Writer context identifies the writer."~~ `writer_context` is
  `current_setting('scholarzone.writer_context')`, a **transaction-local setting the writer itself
  sets**. Any session can `SET` it. It records *which code path set the label*, not who wrote, and is
  **forgeable**. `maintenance.add` on id 130 (§10) is a live demonstration that the label and the
  writing code can disagree.
- Audit self-verification is also incomplete: `create_image_audit_schema()` **swallows installation
  exceptions** and logs CRITICAL, so a failed upgrade can leave a stale, weaker structure in place
  while the app appears instrumented. The live catalog read in §3 is the only reliable check, and it
  is why this document reports catalog facts rather than installer output.

---

## 5. Concurrent Writer Inventory

| workflow | image-capable | concurrency group | cancel-in-progress |
|---|---|---|---|
| `verification-cron.yml` | **yes** — all 22 stages incl. images/logos/purge | `scholarzone-maintenance` | `false` |
| `controlled-image-repair.yml` | **yes** — runs `triple_image_repair.py --evaluate` | **NONE** | n/a |
| `db-state-check.yml` | **YES — arbitrary script with production credentials** | **NONE** | n/a |
| `image-audit-check.yml` | runs `install_image_audit.py` (**DDL**) | **NONE** | n/a |
| `promote-validated-scholarships.yml` | promotion writes | `production-promotion` | `true` |
| `closed-record-audit.yml` | archival | `closed-record-audit` | `false` |
| `deploy.yml` / `frontend.yml` / `ci.yml` | no | various | — |

`verification-cron.yml` declares `concurrency:` **twice** (duplicate YAML mapping key); the second
wins. Both specify the same group and `cancel-in-progress: false`, so behaviour is unaffected, but it
is a latent config defect.

**Answers to the six questions:**

1. **Who can launch image maintenance?** Anyone with write access to the repo who can dispatch
   `verification-cron.yml`, `controlled-image-repair.yml`, `db-state-check.yml`, or
   `image-audit-check.yml`.
2. **Which can run images/logos/purge?** `verification-cron.yml` (any stage, or `all`),
   `controlled-image-repair.yml` (evaluate), and `db-state-check.yml` (any script at all).
3. **Do manual and scheduled runs share a group?** Only for `verification-cron.yml`. The three
   image-capable entry points above have **no group**, so a manual repair and a scheduled sweep can
   run simultaneously — and did.
4. **Can two evaluations target the same scholarship?** **Yes.** No advisory lock, no `SELECT … FOR
   UPDATE`, no `skip_locked`, no `nowait` exists anywhere in `scholarzone_maintenance.py` or
   `image_coverage_runner.py` (verified by search — zero matches). There is **no application-level
   lock or idempotency guard** preventing duplicate evaluation.
5. **Why did two sessions evaluate `[14,130,554]`?** Two dispatches ran ~8 s apart:
   my `--evaluate` (run 37191169731, persisted id 14 at 09:09:52, audit txn 282716) and a
   `Controlled Image Repair (forensic)` run (37191246675, sha `91f0d2a`, which also re-ran
   `install_image_audit.py`, i.e. DDL). Audit ids 70/71 (id 554, 09:10:07–08) are the second actor's.
   Nothing prevented the overlap.
6. **Can a third evaluation happen?** **Yes**, at any time, by either entry point. There is no
   mechanism that prevents it and no mechanism that would stop me from observing one cleanly.
7. **Safest genuinely quiescent observation window:** none can be *enforced* from inside this task.
   The only existing safe mechanism is the `scholarzone-maintenance` concurrency group, which is
   `cancel-in-progress: false` and therefore **queues rather than cancels** — it cannot produce a
   single uncontaminated window while another actor holds the other three unlocked entry points.
   **Containment cannot be enforced.** A valid window requires operator action: pause the other actor
   and gate `db-state-check.yml`, `controlled-image-repair.yml` and `image-audit-check.yml` behind the
   same concurrency group.

---

## 6. Quiescence Readiness

**NOT READY.** Preconditions missing:

- No post-repair complete scheduled cycle has been observed (the 09:13:57 run is still
  `status='running'`, `finished_at=None` in `maintenance_runs` id 250 — a **stuck run record** left by
  a cancelled GitHub run, so its stages may still have executed).
- Three image-capable workflows are unlocked against each other.
- No application-level lock prevents duplicate evaluation.
- An `unknown` writer was still mutating images at 09:29:44, four minutes before the last snapshot.

---

## 7. Public Count 366 → 350 → 358 Reconstruction

Verified read-only from `maintenance_runs` stage details and censuses:

| time (UTC) | source | public_visible |
|---|---|---|
| 08:41 | census | 366 |
| 09:00:57 | run `8568b80845d04be2` `stats` | **366** |
| 09:01:41 | run `326171d202ec4a44` `purge` | — (`with_image` 422→404, `without_image` 29→47, `cleared: 18`) |
| 09:06:32 | run `bac7158253c0484f` `stats` | **350** |
| 09:35–09:53 | census | **358** |

So 366→350 occurred **between 09:00:57 and 09:06:32**, and 350→358 **between 09:06:32 and 09:35**.

**Attribution: UNKNOWN, and specifically not attributable per-ID.** `scholarship_verification_history`
contains **0 rows** changing `verification_status`, `is_verified`, `is_archived`, `official_source_url`
or `status` since 08:30 — so the writers that moved public visibility did not record history, and no
archived snapshots of membership exist. Naming the 16 IDs that left is therefore **not possible from
retained evidence**, and I will not guess.

Explicitly **not** assumed: that the verification stage caused it, that the image stage caused it, that
the count system caused it. The `purge` run in the window is temporally adjacent but its counts
(`cleared: 18`, image-only) do not match the public delta (16) and `purge` does not write visibility
columns — so the correlation is **plausible, unproven, and I decline to assert it**.

The 3-record controlled repair is **excluded** as a cause: all three targets are outside the public
universe and only those 3 rows were written.

---

## 8. ID 14 Attribution Status

**`do_logos` as an image-clearing writer: PROVEN** (code + audit).

- Audit id **5**, 08:38:28.768558, txn `281764`, `writer_context='maintenance.logos'`,
  changed fields `image_url, image_source_url, image_source_type, image_kind, image_verified_at`,
  before = the ETH Zurich URL, after = all NULL.
- Mechanism (`image_discovery_orchestrator.py`, method `run`, lines 485–689):
  ```python
  if self.logo_only and self._is_non_logo_stored(session, scholarship_id):
      _clear_stored_image(session, scholarship_id)
  ```
  with the source comment *"A stored programme photo must not survive a logo-only sweep."*
  `_is_non_logo_stored` treats an unset `image_kind` as non-logo, so **any** non-identity image is a
  deletion target. The same transaction cleared ids 557, 558, 564, 569, 575.

**Recurrence: UNPROVEN.** Exactly one `maintenance.logos` execution appears in the audit
(8 mutations, all in txn 281764 at one instant). That is a single observed execution, not a
demonstrated schedule. Per the Phase 6.2 rule I did **not** dispatch a `logos` run to force the event,
and I will not present a `workflow_dispatch` logos execution as a natural scheduled recurrence.

**Current status:** id 14 holds `image_url` = ETH Zurich URL, `image_kind='program_image'`,
`image_verified_at` = 09:09:52. Because it is a `program_image`, it remains a **standing deletion
target** for the next `logo_only` sweep. Holding now is not evidence of safety.

---

## 9. ID 557 / 564 / 569 Investigation (root cause only, no repair)

**The reported scope was incomplete.** `I6_image_without_kind` currently affects **five** records:
**557, 564, 569, 603, 618** (557/564/603 are public).

**What happened to 557, 564, 569 (identical shape):**

1. `maintenance.logos`, 08:38:28, txn 281764 — **cleared** a legitimate identity logo.
2. `maintenance.add`, 08:39:23, txn 281792 — **re-set** that same logo.
3. `maintenance.purge`, 09:01:47, txn 282670 — **cleared it again**.
4. `unknown`, 09:19:54–09:20:53 — **set a different image** (`down-arrow.svg` for 557,
   a `Themen` banner for 564, a `wbi.be` news image for 569) with `image_verified_at` populated but
   **`image_kind` left NULL** → the I6 violation.

Committed? **Yes** — all four events are committed audit rows, and the values are live now.

**Which writer created the invalid state?** `writer_context='unknown'`. Per the Phase 6.2 rule the
root cause therefore **remains UNKNOWN**; independent evidence identifying the writer does not exist.
I am **not** claiming `87ad84c`, which touched the *purge* selection and is not implicated in this
path.

**Invalid state still exists:** yes, in all five records. Also note the replacement images are of poor
quality — 557's `down-arrow.svg` is a navigational arrow, 569's is a news image with alt text
*"Etudiant qui effectue une recherche - canva copyright"* — so these are not merely unlabelled, they
are wrong images.

**Not repaired**, as instructed.

---

## 10. ID 130 Contradiction

**Known facts:** audit id 27, 08:39:23.519402, txn 281792, `writer_context='maintenance.add'`,
before = `akf.org/…/favicon.svg`, after = NULL. Changed fields were exactly
`image_url, image_source_url, image_source_type, image_alt_text, image_verified_at` —
**`image_kind` was NOT changed**, leaving `image_kind='official_logo'` on an image-less row (the
class-A corruption).

**Code trace result — the obvious explanation is DISPROVEN.** `do_add`'s only image write is guarded:

```python
if record.image_url and not row.image_url:      # scholarzone_maintenance.py:1319
    row.image_url = record.image_url
    ...
```

`not row.image_url` makes it incapable of clearing a populated image. It can only fill an empty slot.

**Nor is `_clear_stored_image` the culprit**: it clears **all six** image fields *including*
`image_kind` (§3), which does not match the 5-field signature.

A repository-wide search found exactly **one** site that nulls `image_url` without nulling
`image_kind` — `image_discovery_orchestrator.py:660` — but that line is the `logo_only` branch calling
`_clear_stored_image`, whose body clears `image_kind` too. So no matching writer exists in the code
reachable from `do_add`.

**Conclusion: UNKNOWN.** The `maintenance.add` label was set on txn 281792, but the write that emptied
id 130 was not performed by `do_add`'s image code and matches no known clearing helper. Because
`writer_context` is a transaction-local, self-asserted setting (§4), the label records which code path
*stamped the transaction*, not which code wrote the row. I am not inventing a mechanism.

**Sequence worth noting:** id 130's image was set by `maintenance.logos` at 08:38:28 and cleared 55
seconds later at 08:39:23 — i.e. one stage's output was destroyed within the same cycle.

---

## 11. Triple Repair Script Assessment (`backend/scripts/triple_image_repair.py`)

Read-only; **not modified**. Defects documented:

1. **`--reset` can never report `RESET_OK` — PROVEN.** `PRESERVE_FIELDS` includes `updated_at`, and
   `results[sid] = "RESET_OK" if not drift else "RESET_DRIFT"` compares every preserve field before and
   after. Any successful reset bumps `updated_at`, so the check always reports drift. Empirically both
   records reported `RESET_DRIFT` / `RESET FAILED` while in fact **only `updated_at` changed** and no
   content field did. **The script's own success/failure verdict is unreliable and must not be trusted
   as a safety signal.**
2. **Target enforcement is sound.** `TARGETS = [14, 130, 554]` is a module constant, not an argument,
   and `main()` requires exactly one of `--inspect/--reset/--evaluate`. It cannot be widened by
   argument or environment.
3. **No idempotency protection and no locking.** `--evaluate` delegates to `ImageCoverageRunner` with
   no advisory lock or row lock. Two concurrent invocations both evaluate the same three records —
   which is exactly what happened (my run and the peer's run 8 s apart).
4. **Concurrent execution can produce misleading self-verification.** The script prints per-record
   `changed image fields` by diffing before/after around its own run. Under concurrency those diffs
   attribute another actor's writes to itself.
5. **The repair path emits no writer label.** It never calls `image_writer`, so its mutations are
   recorded `unknown` — indistinguishable by context from a genuinely unattributed writer. This is a
   **safe-failure design** (labelling never enables attribution) but it defeats per-run attribution.
6. `--reset` refuses per record when `image_url IS NOT NULL` (`ABORT_HAS_IMAGE`) — correct.

**Safe future requirements:** a maintenance-level advisory lock keyed on scholarship id; an
`image_writer` label carrying the run id; a drift check that excludes server-maintained timestamps;
and a concurrency group on any workflow that can invoke it.

---

## 12. 18-ID Restoration Readiness

**No restore performed. No restore script written.**

**Identification: PROVEN.** The 18 are the `purge` stage output of run `326171d202ec4a44`
(09:01:41–09:01:48), `image_rows: 422, cleared: 18, preserved_accepted: 404`, audit txn `282670`
(`maintenance.purge`). `counts: {'image_non_logo_cleared': 18}`.

**Current state.** The audit holds **41 clear events across 23 distinct records** — a superset of the
18, because `maintenance.logos` (txn 281764) and `maintenance.add` (txn 281792) also cleared images.
Of those 23: **12 hold an image now** (14, 557, 558, 564, 569, 575, 600, 601, 603, 612, 618, 623) and
**11 hold none** (130, 539, 548, 550, 602, 607, 609, 610, 611, 613, 621).

**Recoverability: PROVEN for the bytes, and irrelevant for trust.** Every cleared URL survives in
`before_values` of its audit row, so the image references are recoverable. What is **not** recoverable
is any claim that restoring them is *correct*: the pipeline has since re-evaluated most of these
records, and for 557/564/569/603/618 it wrote *new, worse* images (arrow icon, banner, news photo) with
no `image_kind`. Restoring from `before_values` would overwrite later deliberate evaluations.

**Contamination: PROVEN.** Restoration evidence is already contaminated:
- 12 of the 23 were re-imaged between 09:17 and 09:29, mostly by an `unknown` writer.
- `maintenance.purge` ran **twice** (txn 281790 at 08:39:22 and txn 282670 at 09:01:47), the second
  clearing images that `maintenance.add` had re-set at 08:39:23 — so the same record was cleared, set
  and cleared again within 23 minutes.
- The 18/23 figures do not reconcile, because the second purge and the logos sweep overlap the first.

---

## 13. Proven Findings

1. Three audit triggers are live, enabled `O`: `BEFORE UPDATE OR DELETE` row-level and `BEFORE
   TRUNCATE` statement-level on the audit table; `AFTER UPDATE` row-level on `scholarships`.
2. `DELETE` and `TRUNCATE` on `scholarship_image_audit` **are blocked** by triggers.
3. `REVOKE … FROM PUBLIC` is effective: `public_grants = 0`; only `neondb_owner` holds grants.
4. The owner escape is real: `neondb_owner` owns the table and holds `TRIGGER`, and `cloud_admin` is a
   superuser, so guards can be dropped and rows rewritten.
5. The `scholarships` trigger covers **UPDATE only** — `INSERT`, `DELETE` and `TRUNCATE` are unaudited.
6. Rolled-back mutations leave **no** audit row (same transaction).
7. `writer_context` is a self-asserted, forgeable, transaction-local setting.
8. `do_logos` cleared id 14's `program_image` at 08:38:28 (txn 281764), plus 557/558/564/569/575.
9. The mechanism is `_is_non_logo_stored` + `_clear_stored_image` under `logo_only`.
10. The "18 purged images" are `purge` run `326171d202ec4a44`, txn 282670.
11. `I6_image_without_kind` affects **5** records (557, 564, 569, 603, 618), not 3.
12. Those violations were created by an `unknown` writer at 09:19–09:29 setting `image_url` without
    `image_kind`.
13. No advisory lock, no row lock, no `skip_locked` exists in the worker or the coverage runner.
14. `controlled-image-repair.yml`, `db-state-check.yml` and `image-audit-check.yml` have **no**
    concurrency group; `verification-cron.yml` declares `concurrency:` twice.
15. `do_add`'s image write is guarded by `not row.image_url` and cannot clear.
16. `--reset` in `triple_image_repair.py` can never report `RESET_OK`.
17. `maintenance_runs` id 250 is stuck at `status='running'`, `finished_at=None`.
18. Audit has 0 orphan rows; storage steady at 451; `candidate_since_set` 0.

## 14. Disproven Findings

1. **"The immutable guard is BEFORE UPDATE only; DELETE/TRUNCATE are unguarded."** DISPROVEN — that
   described the SQLite DDL, not PostgreSQL.
2. **"audit boundary safe: NO"** — DISPROVEN as a verdict. Owner privilege bits are not a safety
   test; the guards are the enforcement and they are present. The residual owner-drop escape is real
   but is a different, narrower claim.
3. **"`maintenance.add` cleared id 130 through its own image write."** DISPROVEN — the write is
   guarded by `not row.image_url`.
4. **"`_clear_stored_image` emptied id 130."** DISPROVEN — it also nulls `image_kind`; the audit shows
   `image_kind` untouched.
5. **"Id 14 holding its image proves logos is safe."** DISPROVEN — `program_image` is by construction a
   deletion target in `logo_only` mode.
6. **"No audit row means no mutation."** DISPROVEN (§4); inference withdrawn.

## 15. Plausible But Unproven

1. That the 366→350 drop is related to the adjacent `purge` run — the arithmetic does not match
   (18 cleared vs 16 public) and `purge` writes no visibility columns.
2. That the `unknown` writer at 09:19–09:29 was an ad-hoc script dispatched through
   `db-state-check.yml` — timing is consistent, nothing proves it.
3. That `maintenance.add`'s label leaked onto another writer's transaction — the mechanism would
   explain id 130, but no code path was found.
4. That the logos sweep that cleared 6 records recurs on a schedule — only one execution is on record.

## 16. Unknowns

1. October 3 root cause. Untouched by this phase; **UNKNOWN**.
2. Which specific scholarship IDs entered/left the public universe across 366→350→358. No archived
   membership snapshots exist and `scholarship_verification_history` has 0 rows for visibility fields
   since 08:30, so per-ID reconstruction is **not possible from retained evidence**.
3. The exact code path that emptied id 130 under the `maintenance.add` label.
4. The identity of every `unknown` writer (19 mutations, 08:35–09:29).
5. Whether `maintenance_runs` id 250 executed any stage after its GitHub run was cancelled.
6. Whether a logos recurrence is scheduled, since only one logos execution is on record.
7. Whether the 18 (purge) and the 23 (all clearers) sets were ever reconciled by whoever reported "18".

## 17. Exact Preconditions for a Valid Phase 6

1. **Enforce quiescence** — pause the other actor and put `controlled-image-repair.yml`,
   `db-state-check.yml` and `image-audit-check.yml` into the `scholarzone-maintenance` concurrency
   group (or an equivalent lock). Not enforceable from inside this task.
2. **Add an application-level lock** — advisory lock keyed on scholarship id in
   `ImageCoverageRunner`, so duplicate evaluation is impossible regardless of workflow topology.
3. **Close the `INSERT`/`DELETE` gap** — add `AFTER INSERT` and `AFTER DELETE` triggers, or state
   explicitly and permanently that those paths are out of scope.
4. **Reduce the owner escape** — run the application as a non-owner role so `REVOKE` is meaningful.
5. **Fix `do_logos` scope** — decide whether a logos sweep may delete a non-logo programme image. At
   present it is designed to, and id 14 is its standing target. This is a **policy decision** and I am
   not making it.
6. **Make `writer_context` trustworthy** — or accept it as a hint and stop treating it as attribution.
7. **Archive public-universe membership snapshots** so count movement is reconstructible per ID.
8. **Clear the stuck run** id 250 and confirm no orphaned runner is still writing.
9. **Repair the two script defects** in `triple_image_repair.py` (drift check, labelling, locking)
   before any further controlled use.

## 18. Safest Next Action

**Do nothing that writes.** The next action is an **operator** action, not a code change:

1. Establish quiescence per §17.1 and confirm `maintenance_runs` id 250 is resolved.
2. Then run **one** `verification-cron.yml --stage logos` under that quiescence, and treat it as the
   controlled experiment §8 requires: capture `before`, the logos execution, `after`, and the audit
   attribution. That is a *dispatched* logos execution and must be labelled as such — it is **not** a
   natural scheduled recurrence and cannot prove one.
3. In parallel, fix the drift check in `triple_image_repair.py` so its verdict can be trusted, and give
   the repair path an `image_writer` label.

**Nothing in this document authorises a repair, a restore, or a stage run.** Sections 13–16 are the
evidence; §17 is what must be true before Phase 6 can be classified on anything but UNKNOWN.