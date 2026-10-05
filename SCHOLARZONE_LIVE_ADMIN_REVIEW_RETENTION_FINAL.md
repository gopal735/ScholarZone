# SCHOLARZONE — LIVE + ADMIN-REVIEW RETENTION ENGINE
## FINAL SAFETY REPORT

**Contract version:** `live-admin-review-retention/1`
**Branch:** `feat/live-admin-review-retention-engine` (from `8ac1c9a`)
**Worktree:** `C:\Users\GopaL\AppData\Local\Temp\kilo\sz-retention-wt`

| | Baseline (`8ac1c9a`, before this work) | After this work | Delta |
|---|---|---|---|
| Passed | 4 456 | **4 658** | **+202** |
| Failed | 8 | 8 | 0 |
| Errors | 1 | 1 | 0 |
| Skipped | 11 | 11 | 0 |

The 8 failures and 1 error are the **identical pre-existing set** in every run —
`tests/test_neon_migration.py` (8, caused by a gitignored migration SQL file that
is absent from the worktree) and `scripts/artifact_smoke_test.py::test_endpoint`.
Both are unrelated to retention and unchanged by it. **Zero new failures.**

---

## FINAL CLASSIFICATION

> ## `DRY_RUN_PROVEN_HARD_DELETE_HELD`
> ## `RECOVERY_PATH_REQUIRED`

Two classifications, because two independent findings each force one.

**`DRY_RUN_PROVEN_HARD_DELETE_HELD`** — the engine is built, tested, and proven.
Its classifier, guards, bounded delete, race safety and reconciliation all pass
against a real database. Hard deletion is *held* — not by a missing feature, but
because the two switches that authorise it (`cleanup_enabled`, `dry_run`) are
both off by default and cannot be flipped without a deliberate code change.

**`RECOVERY_PATH_REQUIRED`** — Phase 12 asked whether a deleted row could be
brought back. It could not. There is no verified point-in-time recovery path and
no automated backup for the production PostgreSQL database. An irreversible
operation with no way to reverse it is not one environment variable away from
being enabled, so it has not been enabled.

**Production deletion: 0 records deleted. Nothing in production was touched.**

---

## 1. AUTHORITATIVE `LIVE` DEFINITION

Not invented. Reused verbatim from the function the public catalogue itself calls:

**`app.repositories.scholarships.public_visibility_conditions()`**
(`backend/app/repositories/scholarships.py:24`)

```
verification_status != 'quarantined'
AND is_archived IS false
AND is_verified IS true                      # settings.public_require_verified
AND image_url IS NOT NULL                    # settings.public_require_verified_image
AND image_verified_at IS NOT NULL
AND (image_source_type != 'wikimedia' OR image_source_type IS NULL)
                                           # unless public_allow_third_party_image
```

This is the repository's own definition. `app/services/counting/catalogue.py:86`,
the directory query, the homepage statistics, `app/services/auto_delete_collector.py:78`
and the retention engine all resolve LIVE through this one function, so the
retention engine cannot disagree with the public catalogue about what is live.

**The retention engine does not re-derive LIVE.** `RetentionFacts.is_live` arrives
as a resolved boolean; the classifier has no visibility logic of its own to get
wrong.

### Why this matters, concretely

`is_archived` is the clause that carries the retention rule, and the model says why
in its own comment (`backend/app/models.py:31-39`):

> *"`is_archived` answers 'should this record be offered to a visitor at all', and
> it is one-way. A scholarship whose deadline passed is still a true record — it
> just is not an opportunity… Archiving keeps the row, its history and its inbound
> links while removing it from every public read path."*

So **not-live is not a synonym for disposable.** A record hidden by the image
quality gate is a real programme whose awarding body publishes no findable logo.
It is a live scholarship an applicant can still apply to. Section 4 shows what
happens to that population.

---

## 2. AUTHORITATIVE `ADMIN_REVIEW` DEFINITION

No `admin_review` boolean exists in this schema. The state is a **union** of every
surface the repository already uses to mean "a human must look at this next":

```
ADMIN_REVIEW =
      verification_status ∈ {needs_review, conflict, disputed, uncertain,
                             pending, partially_verified, unsupported}
   OR ∃ ScholarshipReview WHERE decision ∉ TERMINAL_REVIEW_DECISIONS
                                   OR reviewed_at IS NULL
   OR ∃ ImageReview       WHERE decision ∉ TERMINAL_REVIEW_DECISIONS
                                   OR reviewed_at IS NULL
```

**Sources, each reused rather than restated:**

| Clause | Authoritative source |
|---|---|
| `needs_review` | `app/services/scholarships.py:58` (`get_verification_queue`) |
| admin queue count | `app/routers/admin_image_review.py:78-86` (`review_queue_counts`) |
| unsettled test | `app/services/auto_delete_policy.py:48-53` (`TERMINAL_REVIEW_DECISIONS`) |
| status vocabulary | `app/services/auto_delete_policy.py:59-71` (`BLOCKING_VERIFICATION_STATUSES`) |
| resolved in SQL | `app/services/retention_engine.py` `admin_review_conditions()` |

The status set is **derived by import**, not restated:
`BLOCKING_VERIFICATION_STATUSES − {active, quarantined}`. `active` is excluded
because it is the *verified* state, not a review state; `quarantined` is excluded
because it is a decision already taken and recorded, and it is protected
separately (Section 3).

**"Unsettled" is deliberately not `decision = 'pending'`.** It means *not terminal,
or terminal with no reviewer recorded* — the same two-part test the existing
closed-record policy applies. A review that is half-finished is precisely the
review that must not be treated as finished.

---

## 3. THE CANONICAL RULE, AND WHERE IT IS CORRECTED

```
PRESERVE = LIVE ∪ ADMIN_REVIEW
DELETE   = NOT PRESERVE
```

**The literal form of that rule is not safe, and the engine does not implement it
literally.** The correction is the substance of this report, so it is stated
plainly.

Applying `DELETE = NOT PRESERVE` directly would delete:

1. **Every archived record.** The repository archives on deadline passage and
   deliberately keeps the row, its history and its inbound links. Archived ≠ junk.
2. **Every record without a verified image.** The image gate is a documented
   product trade-off with "a large, measurable cost" (`core/config.py:36-42`).
   Records hidden for a missing logo are real programmes.
3. **Every record with any history, review, snapshot, restore record or image
   review** — i.e. the best-documented records in the catalogue.
4. **Every record whose status any module has not yet named.**

The mission's own Phase 4 resolves this, and the engine implements Phase 4 as
binding over Phase 3:

> `UNKNOWN != DELETE` · `AMBIGUOUS != DELETE` · `CONFLICTING != DELETE`
> *"If the system cannot PROVE that a record is neither LIVE nor ADMIN_REVIEW, it
> MUST KEEP the record."*

### The classification a record actually receives

`decision` is `KEEP` or `DELETE`. `bucket` is *why*:

| Bucket | Decision | Reason |
|---|---|---|
| `LIVE` | KEEP | `LIVE` |
| `ADMIN_REVIEW` | KEEP | `ADMIN_REVIEW` |
| `PROTECTED` | KEEP | `OPERATOR_PROTECTED` / `PROTECTED_STATUS` / `DEPENDENCY_MUST_SURVIVE` / `NO_RETENTION_CLOCK` / `NOT_ARCHIVED` / `RETENTION_NOT_ELAPSED` / `GRACE_NOT_ELAPSED` / `NOT_ARMED` |
| `AMBIGUOUS` | KEEP | `UNRESOLVED_STATE` |
| `CONFLICTING` | KEEP | `CONFLICTING_STATE` |
| `NOT_LIVE_NOT_REVIEW` | **DELETE** | `NOT_LIVE_NOT_REVIEW` |

**A documented extension to the spec.** The brief allows two KEEP reasons, `LIVE`
and `ADMIN_REVIEW`. A third through fifth are unavoidable, because the brief also
requires `ambiguous/protected` buckets that are *retained*. Those records are
neither LIVE nor ADMIN_REVIEW and are not deleted, which cannot be expressed with
only two reason values. The two named reasons are unchanged and take precedence;
the rest name the specific state, which is what makes an audit possible.

`PROTECTED` is not a loophole. It is where a record lands when it is **proved**
not live and **proved** not under review, and is nevertheless retained for a
stated reason — chiefly evidence (Section 5), an operator override, or having been
hidden by a quality gate rather than closed.

---

## 4. PRESERVED POPULATION

Retained, with the reason that is actually authoritative:

| Population | Count basis | Bucket |
|---|---|---|
| In the public catalogue | `public_visibility_conditions()` | `LIVE` |
| Verification status says a human is next | `BLOCKING_VERIFICATION_STATUSES` | `ADMIN_REVIEW` |
| Unsettled scholarship review | `ScholarshipReview` | `ADMIN_REVIEW` |
| Unsettled image review | `ImageReview` | `ADMIN_REVIEW` |
| **Verified but hidden for a missing logo** | image gate | `PROTECTED` |
| **Quarantined non-scholarship** (e.g. id 490) | `protected_statuses` | `PROTECTED` |
| Carries any PRESERVE evidence row | Section 5 | `PROTECTED` |
| Operator override set | `deletion_protected` | `PROTECTED` |
| Archived under 180 days | `archived_at` | `PROTECTED` |
| Grace period not served | `auto_delete_candidate_since` | `PROTECTED` |
| Archived with no clock / no reason | conflict | `CONFLICTING` |
| `active` status with `is_verified = false` | conflict | `CONFLICTING` |
| `open` + archived + future deadline | conflict | `CONFLICTING` |
| Status nobody has classified | vocabulary | `AMBIGUOUS` |
| Required state column is NULL | schema drift | `AMBIGUOUS` |
| Incomplete evidence | query failure | `AMBIGUOUS` |

**Conflict and unknown are checked before the deletion test, not after.** A
contradictory record is never deletable even when it is 2,834 days past retention.

The retention clock is `archived_at`, never `updated_at` — `updated_at` moves on
every unrelated edit and would silently satisfy any age requirement. This reuses
the reasoning already documented at `auto_delete_policy.py:21-25`.

---

## 5. DELETION POPULATION

A record is a deletion candidate only when **every** one of these holds:

1. not live (canonical predicate),
2. not under admin review (canonical union),
3. every state value is a vocabulary the repository recognises,
4. no internal contradiction,
5. `deletion_protected` is false,
6. status not in `protected_statuses`,
7. **no row in any of the five PRESERVE tables**,
8. `archived_at` present and ≥ `minimum_age_before_delete` (180 days),
9. `is_archived` true,
10. `auto_delete_candidate_since` present and ≥ 14 days,
11. no unsettled fetch attempt, no discovery candidate awaiting a match decision.

Conditions 1-7 are what separate this from a naive `NOT PRESERVE` sweep.
**Condition 7 is the decisive one, and it is the finding that holds deletion.**

---

## 6. REFERENCE-INTEGRITY ANALYSIS

Introspected from live model metadata — `reference_integrity_report()` — not
hand-written, so a table added later appears as `UNCLASSIFIED` instead of being
silently ignored. **7 relationships, all classified, 0 unclassified.**

| Table | Column | Enforced | Disposition |
|---|---|---|---|
| `scholarship_reviews` | `scholarship_id` | NO ACTION / RESTRICT | **PRESERVE** |
| `scholarship_verification_history` | `scholarship_id` | NO ACTION / RESTRICT | **PRESERVE** |
| `scholarship_snapshots` | `scholarship_id` | NO ACTION / RESTRICT | **PRESERVE** |
| `scholarship_restore_records` | `scholarship_id` | NO ACTION / RESTRICT | **PRESERVE** |
| `image_reviews` | `scholarship_id` | NO ACTION / RESTRICT | **PRESERVE** |
| `scholarship_fetch_attempts` | `scholarship_id` | NO ACTION / RESTRICT | DISPOSABLE_WHEN_SETTLED |
| `discovery_candidates` | `matched_scholarship_id` (nullable) | NO ACTION / RESTRICT | SET_NULL |

### The finding

**No relationship declares `ON DELETE CASCADE`.** PostgreSQL therefore *refuses*
to delete a referenced scholarship. Cascade is not the hazard here.

**The hazard is the manual child-row removal required to get around that refusal.**
The existing closed-record collector deletes all six child tables before the
parent (`auto_delete_collector.py:481-497`). That is the only way "through", and it
destroys the record's own evidence: the reviews that explain why a decision was
reached, the verification history that backs every public trust claim, the
point-in-time snapshots that make historical counts answerable, the restore log
that makes a rollback explicable, and the image provenance that stops a logo being
served without a recorded origin.

**Resolution:** a record carrying any PRESERVE row is never a deletion candidate.
The deleting path only ever detaches the one nullable link
(`matched_scholarship_id := NULL`, `match_status := 'unmatched'`) and removes
settled fetch telemetry. **No PRESERVE table is read for deletion at all**, so the
evidence cannot be destroyed by a side effect — verified by
`test_evidence_rows_survive_a_deletion_run`.

Unlinked artefacts are recorded too, because absence from the FK graph is not
evidence of independence: `purged_records_archive.json`, `retired_records.json`,
`record_corrections.json`, `verification_confirmations.json`, and the
`official_details` / `applicant_utility` / `programme_verification` JSON blocks.

**Consequence:** because 5 of 7 tables are PRESERVE, and essentially every real
record has a verification history, **the deletable population in a real catalogue
is expected to be near zero.** That is the correct answer, not a defect.

---

## 7. DRY-RUN RESULT

`dry_run()` performs classification and the full safety gate, and writes exactly
one row: its own audit record. It performs **no** `DELETE`.

Reported: `total_scanned`, `live_kept`, `admin_review_kept`, `protected`,
`ambiguous`, `conflicting`, `delete_candidates`, `errors`, plus a bounded sample of
candidate and retained ids with their exact authoritative reasons.

**The dry run and the deletion call the same `scan()` and the same `classify()`.**
Not the same policy — the same code path over the same rows through the same SQL.
A dry run that approximated the real query would prove nothing about it. Asserted
by `test_dry_run_uses_the_same_scan_as_deletion`.

Reconciliation is required, not reported optimistically: `summary.reconciles()`
is `False` unless `scanned == live_kept + admin_review_kept + protected +
ambiguous + conflicting + delete_candidates`. A run reporting 500 scanned, 480
kept and 30 candidates has not described a dataset — the missing 490 are the
records it was too unsure to mention, and the sum failing is a guard failure.

### Verified end-to-end on a seeded catalogue

```
CLASSIFICATION
  total scanned        : 5
  live     (KEEP)      : 1     <- listed programme
  admin review (KEEP)  : 1     <- verification_status = needs_review
  protected            : 1     <- verified, no verified image (image gate)
  ambiguous            : 1     <- verification_status = brand_new_state
  conflicting          : 0
  delete candidates    : 1     <- stale, archived, armed, no evidence
  arithmetic reconciles: True

DELETE CANDIDATES
         3  NOT_LIVE_NOT_REVIEW
            not live, not under review, not protected, archived 2834 day(s)
            (>= 180), armed 2834 day(s) (>= 14 grace), no dependency that must survive

GUARDS
  [FAIL] ambiguous_within_tolerance
  ! 1 of 5 record(s) could not be classified (20.0%), above the 0.0% tolerance

status: partial
```

The run **blocked itself.** One record in five carried a verification status no
module classifies, so 20% of the catalogue was unclassifiable against a 0%
tolerance, and the guard refused the run — even though the engine was in dry-run
mode and could not have deleted anything regardless. This is the single most
important behaviour in the engine: an unrecognised value does not become
permission to delete, and its presence stops the run.

---

## 8. DELETION CAPS

Named, configurable fields on `RetentionPolicy` — never hidden constants. The
required set is present, plus the two the existing retention clock already had.

| Field | Default | Meaning |
|---|---|---|
| `cleanup_enabled` | **`False`** | Master switch. Deleting path unreachable when false. |
| `dry_run` | **`True`** | Second, independent switch. Both must change. |
| `minimum_age_before_delete` | 180 | Days archived before eligibility. |
| `grace_days` | 14 | Days the persisted candidate clock must have run. |
| `max_delete_per_run` | 50 | Hard ceiling on rows per run. |
| `max_delete_percentage` | 0.05 | Ceiling on share of storage per run. |
| `protected_statuses` | 9 states | Preserved whatever else is true. |
| `batch_size` | 25 | Rows per transaction. |
| `max_ambiguous_ratio` | 0.0 | Share of unclassifiable records that aborts a run. |
| `count_reconciliation_tolerance` | 0 | Slack permitted in the count comparison. |

Defaults are taken from the existing closed-record policy (`AUTO_DELETE_AFTER_DAYS`,
`DELETE_GRACE_DAYS`) so the two retention engines cannot disagree about how long a
record has been gone, and so the persisted grace clock is shared rather than
duplicated.

**Every cap is checked against a number the database produced during this run.** A
guard satisfiable by a constant is not a guard.

Enforcement is at the point of use: `assert_deletion_permitted()` is called before
anything is written, so "enabled" and "really enabled" are two separate, explicit
acts.

---

## 9. CONCURRENCY PROOF

A record is never deleted on a decision made earlier. Between classification and
deletion a record can be reopened, re-verified, put into review, given a
dependency, or have its clocks rewritten. Three defences:

1. **Re-classification.** Each candidate is re-read and re-run through
   `classify()` immediately before deletion. A record that became live, entered
   review, was protected, or acquired a dependency is aborted individually and
   kept.
2. **Conditional `DELETE`.** The removal is a statement whose predicate is the
   *negation* of the same LIVE and ADMIN_REVIEW conditions, plus equality on the
   exact `archived_at` and `auto_delete_candidate_since` the verdict was based on.
   Zero rows matched means the record is kept.
3. **Identity check.** The database identity is captured at the start and
   re-checked before every batch, so a run cannot apply one catalogue's verdicts to
   another's rows.

`conditional_delete()` is exposed as its own named function so the predicate can be
tested **directly against a database**, clause by clause — a guard whose clauses
are only exercised incidentally is an unguarded guard. Each mutation below is
driven separately, after proving the baseline statement does match:

| Mutation between classification and `DELETE` | Result |
|---|---|
| Became live (verified + image + unarchived, **clocks untouched**) | 0 rows → kept |
| Entered review | 0 rows → kept |
| Operator protected | 0 rows → kept |
| Retention clock moved | 0 rows → kept |
| Grace clock cleared | 0 rows → kept |
| Reopened | 0 rows → kept |

The `became_live` case is built to leave both clocks untouched. "Became live"
normally means reopened, and reopening clears `archived_at` — which would let the
clock equality do the refusing and leave the `not live` clause unexercised. The
test asserts the record really is in the public catalogue at that moment
(`public_visibility_conditions()` matches it) so the premise is proven, not assumed.

**Worker-vs-worker coverage:** cleanup vs verification (`became_live`), cleanup vs
admin-review update (`entered_review`, and a pending `ScholarshipReview`/`ImageReview`
inserted between the two reads), cleanup vs scholarship refresh (`reopened`,
`retention_clock_moved`), cleanup vs duplicate correction (a discovery candidate
awaiting a match decision blocks the record). Plus a failed-statement test proving
a rollback leaves **every** record in place.

`with_for_update` is honoured on PostgreSQL and ignored on SQLite, which is why the
re-decision and the conditional statement are the guarantee and the lock only
narrows the window.

---

## 10. ADMIN-REVIEW PROTECTION

`test_retention_admin_review_protection.py`, 99 tests, all passing.

| Claim | Result |
|---|---|
| `LIVE` → retained, reason `LIVE` | proven |
| `ADMIN_REVIEW` → retained, reason `ADMIN_REVIEW` | proven |
| `LIVE` + `ADMIN_REVIEW` → retained (one decision, review named) | proven |
| `NOT_LIVE` + `NOT_ADMIN_REVIEW` → delete candidate | proven |
| `UNKNOWN` → retained | proven |
| `CONFLICTING` → retained | proven |

**Precedence is proven under failure, not just in isolation.** Every one of the
7 admin-review statuses × 8 separate failing gates (deadline expired, not
verified, archived with no clock, not archived, not armed, closed yesterday,
lifecycle closed, has a dependency) is asserted to still yield `KEEP`. 56
combinations. A record under review is kept even when its deadline has passed, its
source is gone, its image is missing and every public visibility gate fails.

Review precedence also wins over *operator protection* — asserted
(`test_admin_review_decision_never_names_protection`) because otherwise the reason
misreports why the record is still here.

The visible consequence is proven in `test_retention_invariants.py`:
`TestAdminVisibility` shows review records remain in the admin queue counts, and
`TestPublicCatalogueEffect` shows they are **not** made public in order to keep
them. Retaining a record must never widen its audience.

---

## 11. AUDIT MECHANISM

Reuses **`maintenance_runs`** — the project's existing operational ledger
(`app/services/maintenance_run_log.py`). No new table: two tables both claiming to
record what a cleanup did would be a second source of truth for the same question,
which is worse than no record at all.

Written **up front** (`status = running`) so a hard crash still leaves a trace, and
finalised **once** in a `finally`, so every exit path — success, guard abort,
exception — produces exactly one row. Statuses are reused from the existing
vocabulary (`ok` / `partial` / `failed`); no new state was invented.

Recorded: `run_id`, `started_at`, `finished_at`, `dry_run` (the mode),
`retention_scanned`, `retention_kept_live`, `retention_kept_admin_review`,
`retention_delete_candidates`, `retention_protected`, `retention_ambiguous`,
`retention_conflicting`, `retention_unclassifiable`, `retention_deleted`,
`retention_aborted`, `retention_guard_failures`, `retention_trigger`,
`retention_contract_version`, the guard results, the error summary and the
duration.

**No personal data.** Counts, state names and the run's own identifiers only.
Asserted by serialising the whole row and asserting it contains no
`email` / `password` / `token` / `secret` / `@`.

### Deletion ledger

`backend/config/purged_records_archive.json` — the **existing** ledger, extended
rather than duplicated, so there is one place that answers "what was deleted and
why". Written **before** the batch commits and confirmed after, matching the
existing collector's discipline: a crash between the two leaves an
over-reported deletion, repairable by reading the id back; the reverse order
leaves a deletion nobody can account for. A full row payload is captured, so a
deleted record can be described exactly.

One defect found and fixed during this work: the engine's default ledger is a
**tracked repository file**, so the test suite was appending real entries to the
project's permanent deletion record. `delete_bounded(..., ledger=)` is now
explicit, every deleting test routes to a temp path, and
`test_a_suite_run_never_writes_the_repository_ledger` asserts the repo ledger is
byte-identical after a deleting run.

---

## 12. RECOVERY MECHANISM

> **`RECOVERY_PATH_REQUIRED`**

`recovery_status()` reports what the repository actually contains, not what the
code would like to claim:

| Mechanism | Present? |
|---|---|
| Verified point-in-time recovery | **No** |
| Automated backups of production | **No** |
| Local SQLite snapshots | Yes, but the only one on record is `scholarzone_final_backup_20260902_122751.db` — a **pre-migration** file that predates the production PostgreSQL database |
| Deletion manifest | Yes — full row payloads, so a record can be described and manually re-inserted |

**The manifest is not a backup.** It can say a row existed and what it said. It
cannot reinstate the row inside a foreign-key graph the application depends on,
and it cannot roll back a transaction. Presenting it as a recovery path is exactly
how an irreversible operation comes to be treated as reversible, so it is described
as what it is and the run status reflects it.

**Therefore hard deletion is not enabled.** In its place the engine implements
**DELETE_CANDIDATE + retention period**: records are classified, candidates are
reported with their exact authoritative reasons, and the grace clock
(`auto_delete_candidate_since`) is the reversible period during which a reopen, a
review, or a corrected deadline cancels a candidate before anything happens. That
clock is persisted rather than derived, because nothing already on a row can tell a
reopen-and-reclose apart from never having reopened.

---

## 13. COUNT RECONCILIATION

Uses **`catalogue_counts()`** (`app/services/counting/catalogue.py:77`) — the
authoritative count definition, the same one the homepage publishes. No second
count definition was created.

After every deleting run:

| Check | Meaning |
|---|---|
| `row_total_decreased_by_deleted` | storage fell by exactly what the report says it deleted |
| `public_total_unchanged` | the public catalogue did not move |
| `admin_review_unchanged` | no reviewable record was removed |
| `no_row_created` | the run created nothing |

**A failed reconciliation raises `CleanupAborted` and ends the run.** It is a gate,
not a report — proven by `test_a_failed_reconciliation_aborts_the_run`, which
simulates a concurrent writer removing a live row and asserts the run aborts.

`public_total_unchanged` is the load-bearing check: a cleanup that deleted what it
said and left the public total untouched removed only records the catalogue was
already hiding, which is the only outcome consistent with "this must not alter the
public catalogue".

---

## 14. MASS-DELETION GUARDS

| Guard | Behaviour on failure |
|---|---|
| Database connection changed mid-run | abort |
| Candidate count exceeds `max_delete_per_run` | abort |
| Candidate share exceeds `max_delete_percentage` | abort |
| Unclassifiable share exceeds `max_ambiguous_ratio` | block |
| Summary does not reconcile | block |
| Reference integrity unclassified | abort |
| Another cleanup run active | block |
| Stale `running` row older than 30 min | **not** treated as competing (a crash must not block every future run) |
| Count reconciliation fails after deletion | abort |
| Any statement or commit fails | batch rolls back, nothing partial |
| `dry_run=True` on a deleting run | `PermissionError` |
| `cleanup_enabled=False` | `PermissionError` |

`CleanupAborted` is never caught and downgraded inside the engine. A partial
"best effort" destructive cleanup is precisely what these guards exist to prevent,
so an abort propagates with the failing check named.

`required status fields cannot be resolved` is handled at classification:
`REQUIRED_STATE_COLUMNS` are scanned for NULL, the affected rows are marked
`evidence_complete=False`, and they classify as `AMBIGUOUS` — never coerced into a
state.

---

## 15. PUBLIC CATALOGUE EFFECT

Proven, not asserted:

- `test_the_directory_lists_exactly_the_live_record` — the public directory
  returns the live record and nothing else.
- `test_a_record_missing_its_logo_is_hidden_but_not_deletable` — the image gate
  hides; it does not make a record junk.
- `test_a_verified_record_hidden_by_the_image_gate_is_never_deletable` — two
  independent protections hold it, so a future edit to the status list cannot
  silently remove the guarantee.
- `test_a_cleanup_dry_run_leaves_the_public_count_untouched`
- `test_a_deletion_run_leaves_the_public_count_untouched` — the public total does
  not move.
- `test_live_matches_the_catalogue_exactly` — the set of records the engine calls
  LIVE is **exactly** `public_visibility_conditions()`. If these ever diverge, that
  test fails.

A live record is never deleted because its public count looks unusual. There is no
such rule, and the `not live` clause of the conditional `DELETE` is the reason.

---

## 16. API / ADMIN VISIBILITY

- **Public users** see `LIVE` only — unchanged; the engine adds no public read path
  and modifies no router.
- **Admins** can still inspect `ADMIN_REVIEW` — `TestAdminVisibility` asserts
  `review_queue_counts()` still reports `scholarships_needing_review`,
  `pending_scholarship_reviews` and `pending_image_reviews` for records the engine
  has classified.
- **`ADMIN_REVIEW` records are never made public to preserve them** — asserted
  explicitly, and the two populations are asserted to be genuinely different sets.
- **Deleted records** cannot appear as live catalogue entries: the delete removes
  the row, and the `not live` clause of the guard means nothing in the public
  predicate is ever targeted.

No router, schema, or serializer was modified.

---

## 17. SCHEDULER STATUS

> **NOT SCHEDULED. NOT WIRED IN.**

`jobs/scholarzone_maintenance.py` is **unmodified**. `STAGE_ORDER`,
`PURGE_CLOSED_EXCLUDED_FROM_ALL`, `DELETING_STAGE` and `ARMING_STAGE` are all
unchanged. The existing closed-record lifecycle (activated in `8ac1c9a`) is
untouched.

Retention is reachable only by running `backend/scripts/retention_dry_run.py` by
hand. It is not importable from the worker, not in any stage list, and not in
`--stage all`.

If it is scheduled later, the required properties are: bounded frequency, a
single-run lock (already implemented via `competing_run_ids`, with a stale-run
expiry), no overlap, a maximum deletion budget, an audit log, dry-run capability,
and a kill switch (`cleanup_enabled`). **The existing maintenance schedule is not
changed by this work and must not be changed without explicit authorisation.**

---

## 18. TEST MATRIX

**202 tests, all passing.** 202 new collected cases; 0 existing tests modified;
**0 tracked files modified** — `git diff 8ac1c9a` is empty; every file below is new.

| Area | Coverage |
|---|---|
| Classification | determinism, `as_of` injection, per-check audit record, no delete with a failing check |
| Live retention | canonical-predicate equality, image-gate population, `archived_at`-based ages |
| Admin-review retention | 7 statuses × 8 failing gates = 56 combinations; both review surfaces; precedence over operator protection |
| Unknown protection | 6 unrecognised verification values, 5 unrecognised lifecycle values, NULL columns, incomplete evidence |
| Conflict protection | archived-without-clock, archived-without-reason, legacy-flag contradiction, open-but-archived-with-future-deadline |
| Deadline changes | future deadline + archived → CONFLICTING; `deadline_date` reset on reopen |
| Verification changes | `active`/`is_verified` contradiction; review-status transitions |
| Admin-review changes | pending review inserted between classification and deletion |
| Race conditions | became-live, entered-review, clocks moved, protected, reopened, refreshed |
| Conditional delete | 6 clauses, each driven separately against a database, baseline proven to match first |
| Reference integrity | 7 relationships introspected; 4 evidence tables block; settled vs unsettled fetch; candidate detach vs block |
| Batching | `batch_size=5` over 7 candidates → `[5, 2]` |
| Max-delete guard | per-run cap aborts, zero records removed |
| Percentage guard | share cap aborts, zero records removed |
| Dry run | same-scan equality, all buckets, samples, bounded samples, writes nothing, empty DB |
| Audit logging | one row, every required field, no personal data, deleting vs dry-run, manifest shape |
| Count reconciliation | 4 checks, forced failure aborts the run |
| Idempotency | **second run finds 0 additional deletions on a mixed dataset** |
| Empty database | reconciles, status ok |
| All-live database | 0 candidates |
| All-review database | 0 candidates |
| All-conflicting database | 0 candidates, all CONFLICTING |
| All-candidate database | still capped |

### Two defects found and fixed by these tests

1. **A statement-level failure escaped `_delete_batch` without rolling back.** The
   `try` wrapped only `session.commit()`. A real failure — foreign key, lock
   timeout, dropped connection — leaves the statements *before* it already applied,
   so the detached discovery links and removed fetch telemetry would have been
   committed against records that were never deleted. The guard now wraps the whole
   mutation, and the test injects the failure at the database rather than at
   `commit`, because a commit that raises before doing anything is not how a real
   transaction fails. (`retention_engine.py:_delete_batch`)
2. **The test suite was writing to the tracked deletion ledger.** See Section 11.

---

## 19. PROPERTY / INVARIANT TESTS

`test_retention_invariants.py`. Populations are generated from a **fixed seed**
(`20261005`) — deliberately, because a failure in a destructive-safety suite must
be reproducible exactly, and a re-rolling generator turns "this invariant is
violated" into "violated sometimes". The generator spans every recognised status,
statuses nobody has classified, both clock states, present/absent dependencies and
both visibility gates; sizes 1, 5, 25 and 200.

| Claim | Result |
|---|---|
| `LIVE ∩ DELETE = ∅` | proven at every size |
| `ADMIN_REVIEW ∩ DELETE = ∅` | proven at every size |
| `DELETE ∩ KEEP = ∅` | proven at every size |
| No AMBIGUOUS or CONFLICTING record is ever deleted | proven at every size |
| `KEEP ⊇ LIVE ∪ ADMIN_REVIEW` | proven at every size |
| `DELETE` equals exactly the unclassified-and-unprotected residual | proven |
| `scanned == sum(buckets)` | proven at every size |
| No `DELETE` carries a failing check | proven at every size |
| Classification is deterministic | proven |
| `assert_invariants()` holds over each population | proven |

`assert_invariants()` runs on **every** scan, including the dry run, so the
guarantee is checked rather than assumed from the branch structure. It is itself
tested against a forged decision to confirm it actually fires.

### Transition proofs, against a database

| Transition before the actual delete | Outcome |
|---|---|
| `DELETE_CANDIDATE` → `LIVE` | **KEEP**, bucket `LIVE`, 0 deleted |
| `DELETE_CANDIDATE` → `ADMIN_REVIEW` | **KEEP**, bucket `ADMIN_REVIEW`, 0 deleted |
| `DELETE_CANDIDATE` → `AMBIGUOUS` | KEEP, 0 deleted |
| `DELETE_CANDIDATE` → `CONFLICTING` | KEEP, 0 deleted |
| no transition (control) | **deleted** |

The control case is essential: without it, the four tests above would also pass
against an engine that never deletes anything.

---

## 20. PRODUCTION DRY RUN

> ## NOT EXECUTED — no authorised production connection

| Requirement | Status |
|---|---|
| All code/tests green | **Yes** — 202/202; full suite shows no new failures |
| Production classifier run in `DRY_RUN` | **Not executed** |
| Production `total` / `live` / `admin_review` / `delete_candidates` / `protected` / `ambiguous` | **Unknown** |
| Anything deleted | **No. Nothing was deleted. Nothing in production was touched.** |

**Why.** This environment has no `SCHOLARZONE_DATABASE_URL`, no `.env`, and no
catalogue database — the only `.db` present is a zero-byte `dev.db`. Production is
Neon/PostgreSQL, reachable only with credentials this environment does not hold
and that this task did not authorise me to use. Reporting numbers here would mean
inventing them, so none are reported.

**What was proven instead:** the same code path, end-to-end, against a seeded
catalogue covering all five classification outcomes — output reproduced in
Section 7, including the engine blocking its own run on an unclassifiable record.

### The command, ready to run

```
cd backend
python scripts/retention_dry_run.py --trigger "phase-20-production-dry-run"
```

It needs only `SCHOLARZONE_DATABASE_URL`. It writes **exactly one row** — its own
`maintenance_runs` audit entry — and deletes nothing. It exits non-zero when a
guard blocks, which is a finding, not a crash.

**Hard deletion is not activated on the basis of this task, and this report does
not authorise it.**

---

## 21. PRODUCTION DELETION

> ## 0 DELETED. NOT AUTHORISED, NOT ATTEMPTED.

Phase 21's eleven preconditions:

| Precondition | Met? |
|---|---|
| Authoritative `LIVE` predicate | **Yes** — canonical function, reused |
| Authoritative `ADMIN_REVIEW` predicate | **Yes** — canonical union, derived by import |
| Reference integrity | **Yes** — 7/7 classified |
| Dry run | **Yes** — code path proven; production run not executed |
| Deletion caps | **Yes** — named fields, checked against real counts |
| Concurrency safety | **Yes** — 6-clause guard tested clause by clause |
| Audit logging | **Yes** — existing ledger reused, no personal data |
| **Recovery / backup path** | **NO — `RECOVERY_PATH_REQUIRED`** |
| Count reconciliation | **Yes** — 4 checks, aborts on failure |
| No ambiguous records | **Unproven in production** — no dataset |
| No active competing cleanup | **Yes** — lock implemented, stale-run expiry |
| **Owner authorisation** | **NO — not given** |

Two preconditions are unmet. Deletion did not proceed.

| Metric | Value |
|---|---|
| Deleted | **0** |
| Kept `LIVE` | 0 changed |
| Kept `ADMIN_REVIEW` | 0 changed |
| Unexpected / ambiguous | 0 changed |
| Public catalogue | **unchanged** |

---

## 22. FINAL SAFETY REPORT SUMMARY

1. **Authoritative `LIVE`** — `public_visibility_conditions()`. Reused, never restated.
2. **Authoritative `ADMIN_REVIEW`** — status union ∪ unsettled scholarship review ∪ unsettled image review. Derived by import from the modules that declare each part.
3. **Preserved population** — live, under review, protected, ambiguous, conflicting: 5 named buckets, each with a stated authoritative reason.
4. **Deletion population** — 11 conditions, all required. Effectively empty on real data, because evidence blocks.
5. **Reference integrity** — 7 relationships, 5 PRESERVE, 1 DISPOSABLE_WHEN_SETTLED, 1 SET_NULL. No CASCADE anywhere; the hazard is manual child removal, and the engine never does it.
6. **Dry run** — proven, self-blocking on an unclassifiable record, `reconciles=True`.
7. **Deletion caps** — 10 named fields, defaults off, every cap checked against a real count.
8. **Concurrency** — re-classify + conditional `DELETE` + identity check. 6 clauses tested individually against a database.
9. **Audit** — existing `maintenance_runs`, one row per run, up-front, no personal data. Existing deletion ledger extended, never duplicated.
10. **Recovery** — `RECOVERY_PATH_REQUIRED`. Manifest recorded as a manifest, not a backup. `DELETE_CANDIDATE` + reversible grace period implemented instead.
11. **Count reconciliation** — authoritative `catalogue_counts()`, 4 checks, aborts on failure.
12. **Production dry run** — not executed; no authorised connection. Command provided; same code path proven on a seeded catalogue.
13. **Production deletion** — 0. Two of eleven preconditions unmet.
14. **Exact deleted count** — **0**
15. **Exact kept `LIVE` count** — **0 changed**
16. **Exact kept `ADMIN_REVIEW` count** — **0 changed**
17. **Unexpected / ambiguous count** — **0 changed**
18. **Scheduler** — not scheduled, not wired, worker unmodified.
19. **Rollback limitations** — a deleted row cannot be restored by anything in this repository. Recovery requires a platform capability that does not exist yet.
20. **Classification** — `DRY_RUN_PROVEN_HARD_DELETE_HELD` + `RECOVERY_PATH_REQUIRED`.

---

## WHAT IS REQUIRED BEFORE HARD DELETE CAN BE CONSIDERED

1. **Establish a verified recovery path** on the production PostgreSQL database —
   Neon point-in-time restore, exercised and timed, with the result recorded. This
   is the blocking item.
2. **Run the production dry run** and resolve whatever it reports. The
   `max_ambiguous_ratio` guard is expected to fire: real catalogues accumulate
   verification statuses no module has classified. Each one must be classified
   before deletion can be considered, and each will be retained meanwhile.
3. **Resolve the `PROTECTED` population by decision, not by sweep.** Every record
   hidden by the image gate, quarantined, or carrying evidence needs a human
   decision. A record that is neither live nor reviewable is still usually a real
   programme.
4. **Obtain explicit owner authorisation**, naming the recovery path.
5. Only then set both `cleanup_enabled=True` and `dry_run=False`, and invoke
   `retention_dry_run.py --execute-delete --recovery-path "…" --confirm-ids "…"`
   with an explicit id list. The authorisation belongs in the command's history,
   not in a configuration value that could have been set months ago by somebody who
   meant something narrower.

---

## FILES

**New — no existing file modified:**

| File | Lines | Purpose |
|---|---|---|
| `backend/app/services/retention_contract.py` | 679 | Pure classifier, policy, invariants. No database, no clock unless `as_of` is injected. |
| `backend/app/services/retention_engine.py` | 1298 | Reference-integrity audit, canonical predicates, scan, dry run, bounded conditional delete, guards, reconciliation, audit ledger, recovery verdict. |
| `backend/scripts/retention_dry_run.py` | 194 | The operator command. Dry run by default; deletion requires an explicit recovery path and an explicit id list. |
| `backend/tests/test_retention_admin_review_protection.py` | 307 | Phases 2, 4, 10 — 31 test functions, 99 collected cases. |
| `backend/tests/test_retention_engine.py` | 906 | Phases 5, 7, 8, 9, 12, 13, 14, 18 (engine half) — 62 test functions, 65 collected cases. |
| `backend/tests/test_retention_invariants.py` | 509 | Phases 15, 16, 18 (shapes), 19 — 25 test functions, 38 collected cases. |

99 + 65 + 38 = **202 collected cases**, all passing. The gap between functions and
cases is the parametrisation: 7 review statuses × 8 failing gates, 6 conditional-delete
mutations, 4 population sizes, 6 unrecognised verification values and 5
unrecognised lifecycle values are each separate cases.

**Deliberately untouched:** `jobs/scholarzone_maintenance.py`, `models.py`,
`schemas.py`, every `routers/*.py`, `services/auto_delete_policy.py`,
`services/auto_delete_collector.py`, `services/counting/*`, `repositories/*`,
`config/purged_records_archive.json`, and the dirty worktree at `8ac1c9a`.

**Baseline, measured rather than assumed:** the full suite was run on the clean
worktree *before* any code was written, giving `8 failed, 4456 passed, 11 skipped,
13 warnings, 1 error`. The run after gives `8 failed, 4658 passed, 11 skipped,
13 warnings, 1 error`. The delta is **+202 passing, with the failing set unchanged
name for name** — the 8 in `tests/test_neon_migration.py` (a gitignored migration
SQL file absent from the worktree) and the 1 error in
`scripts/artifact_smoke_test.py`. Both are unrelated to retention.
