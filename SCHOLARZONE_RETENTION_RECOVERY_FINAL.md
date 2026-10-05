# SCHOLARZONE — RETENTION RECOVERY-PATH PROOF + HARD-DELETE RELEASE GATE

## FINAL SAFETY REPORT

---

## 1. EXACT CANDIDATE SHA

| | |
|---|---|
| **Candidate** | `8ac1c9a40063221904c8994693ffa18746d5fa9d` |
| **Branch** | `feat/live-admin-review-retention-engine` |
| **Worktree** | `C:\Users\GopaL\AppData\Local\Temp\kilo\sz-retention-wt` (clean, isolated) |
| **Primary dirty worktree** | untouched — `8ac1c9a` in the main checkout retains its 495 changed paths, unmodified |
| **Retention contract** | `live-admin-review-retention/2` (was `/1`; see §2) |
| **Recovery contract** | `retention-recovery/1` |
| **Release gate contract** | `retention-release-gate/1` |
| **Tracked files modified** | **0** — `git diff 8ac1c9a -- .` is empty; all 14 deliverables are new files |

**Scope audit (Phase 13): clean.** No Supervisor, Match 2.0, Country Intelligence,
frontend, CI, or scheduler change. `jobs/scholarzone_maintenance.py` is not
imported, not modified, and not reachable from the retention engine. No unrelated
change appeared, so nothing to stop and report.

---

## 2. RETENTION STATE MACHINE

The task requires eight named states. The engine had six *buckets* and no
explicit lifecycle, so `GRACE_ELIGIBLE` was invisible — inferable only by
string-matching a reason. That is now a first-class field, and
`UNKNOWN` has been split from `AMBIGUOUS` because they are different failures
with different remedies.

**Why the split matters.** `UNKNOWN` is a question about a *record*: a value no
module has classified, needing a data decision. `AMBIGUOUS` is a question about a
*run*: a query returned NULL or short, needing a fixed query. They were both
`UNRESOLVED_STATE`. Reporting them separately is what makes the dry-run output
actionable rather than merely alarming.

### The eight states

| State | Meaning | Decision | Reachable by |
|---|---|---|---|
| `KEEP` | LIVE ∪ ADMIN_REVIEW | KEEP | gate 1 or 2 |
| `UNKNOWN` | a value nobody has classified | KEEP | gate 5 |
| `AMBIGUOUS` | the run failed to look properly | KEEP | gate 4 |
| `CONFLICTING` | the record contradicts itself | KEEP | gate 3 |
| `PROTECTED` | a stated permanent protection holds | KEEP | gates 6–9 |
| `GRACE_ELIGIBLE` | **every** deletion condition holds except the reversible clock | KEEP | gate 10 |
| `DELETE_CANDIDATE` | every condition holds | **DELETE** | gate 11 |
| `DELETED` | terminal | — | `delete_bounded` only |

### Transitions, as data

`RETENTION_TRANSITIONS` enumerates `from -> {to}` in
`app/services/retention_contract.py`, and `assert_transition()` is the only
reader. Two properties are encoded rather than described:

- **Nothing reaches `DELETED` except from `DELETE_CANDIDATE`** — the incoming set
  is exactly `{DELETE_CANDIDATE}`.
- **`DELETE_CANDIDATE` is not terminal.** It may fall back to `GRACE_ELIGIBLE` or
  `KEEP` when a concurrent writer re-verifies, reviews or reopens the record,
  which is the ordinary outcome of a lost race.

`DELETED` is the only terminal state.

### Gates, in evaluation order

| # | Gate | Bucket / State on failure |
|---|---|---|
| 1 | admin review (status, pending scholarship review, pending image review) | KEEP |
| 2 | live (canonical predicate) | KEEP |
| 3 | contradiction | CONFLICTING |
| 4 | incomplete evidence | AMBIGUOUS |
| 5 | unrecognised vocabulary | UNKNOWN |
| 6 | operator protection | PROTECTED |
| 7 | configured status protection | PROTECTED |
| 8 | reference integrity | PROTECTED |
| 9 | retention clock / archived | PROTECTED |
| 10 | grace clock | **GRACE_ELIGIBLE** |
| 11 | the only `DELETE` return site | DELETE_CANDIDATE |

### Every transition verified

| Property | Test count |
|---|---|
| Exactly 8 states; every state has a transition row | 2 |
| Only `DELETED` is terminal; no state is a dead end | 2 |
| `DELETED` reachable only from `DELETE_CANDIDATE` | 1 |
| `DELETE_CANDIDATE` unreachable from `DELETED` | 1 |
| Each state produced by a real record shape | 9 (parametrised) |
| `UNKNOWN` vs `AMBIGUOUS` distinguished | 1 |
| Illegal transitions refused (`KEEP→DELETED`, all 4 retained states) | 5 |
| Legal transitions permitted (3) | 3 |
| `NON_DELETABLE_STATES` enumerated, not inferred | 1 |
| Forged decisions caught (mislabelled state, forged delete, candidate-wearing-keep, grace+delete) | 4 |
| Histogram reconciles; grace-eligible counted | 2 |

### The four "does not imply DELETE" proofs

| Claim | Result |
|---|---|
| Archival alone does not imply DELETE — archived 10 days ago, unarmed | `PROTECTED` / `RETENTION_NOT_ELAPSED` |
| Missing verified image does not imply DELETE — verified, unarchived, no logo | `PROTECTED` |
| Historical evidence does not imply DELETE — fully aged and armed, holds a review row | `PROTECTED` / `DEPENDENCY_MUST_SURVIVE` |
| Only a fully qualified candidate reaches `DELETE_CANDIDATE` | all 14 checks true |

### Defect found and fixed in this work

**`CONFLICTING` shipped labelled `STATE_KEEP`.** The new bucket↔state
consistency check (`LEGAL_STATES_FOR_BUCKET`) now catches it, and the biconditional
`is_delete ⟺ (state == DELETE_CANDIDATE)` catches deletions in either wrong
state. Both are asserted against forged decisions, because an assertion nobody has
tried to violate is an assertion nobody has checked.

---

## 3. DELETION GATE ANALYSIS

`DELETE_CANDIDATE` requires **all eleven** conditions. Seven are the deletion
preconditions from the previous report; the four added by this task are the state
machine's own integrity.

| # | Condition | Failure → |
|---|---|---|
| 1 | not under admin review (3 surfaces) | KEEP |
| 2 | not live (canonical `public_visibility_conditions()`) | KEEP |
| 3 | no contradiction | CONFLICTING |
| 4 | evidence complete | AMBIGUOUS |
| 5 | every value recognised | UNKNOWN |
| 6 | `deletion_protected` false | PROTECTED |
| 7 | status not in `protected_statuses` | PROTECTED |
| 8 | no PRESERVE dependency row | PROTECTED |
| 9 | `archived_at` present, `is_archived` true, ≥ 180 days | PROTECTED |
| 10 | `auto_delete_candidate_since` present, ≥ 14 days | GRACE_ELIGIBLE |
| 11 | all 14 named checks true at decision time | DELETE_CANDIDATE |

**Gates are not merely counted — they are cross-checked.** Every condition that
can stop a deletion is recorded in `decision.checks`, whether or not its branch was
reached. A `DELETE_CANDIDATE` whose own checks contain a failure raises. That is
the specific bug this repository has already shipped once: a condition computed
and never enforced.

**Nothing in this work weakened a gate.** No gate was removed, no grace period
shortened, no `protected_statuses` reduced, no candidate set broadened. The change
was strictly additive: a `state` field, a `grace_eligible` flag, and two assertion
checks.

### Reference integrity (unchanged, re-verified)

7 relationships, **0 unclassified**, **0 `ON DELETE CASCADE`**, 5 PRESERVE.

| Model | Disposition | Enforced |
|---|---|---|
| `ScholarshipReview` | PRESERVE | NO ACTION / RESTRICT |
| `ScholarshipVerificationHistory` | PRESERVE | NO ACTION / RESTRICT |
| `ScholarshipSnapshot` | PRESERVE | NO ACTION / RESTRICT |
| `ScholarshipRestoreRecord` | PRESERVE | NO ACTION / RESTRICT |
| `ImageReview` | PRESERVE | NO ACTION / RESTRICT |
| `ScholarshipFetchAttempt` | DISPOSABLE_WHEN_SETTLED | NO ACTION / RESTRICT |
| `DiscoveryCandidate` | SET_NULL | NO ACTION / RESTRICT |

---

## 4. RECOVERY CAPABILITY INVENTORY

Twelve capabilities probed by executing a search, not by assertion. Status
vocabulary: `PROVEN` / `CONFIGURED_NOT_PROVEN` / `DOCUMENTED_ONLY` / `ABSENT` /
`UNKNOWN`.

| ID | Capability | Status | Evidence |
|---|---|---|---|
| R1 | Provider point-in-time restore | **UNKNOWN** | Platform-account capability; not observable from here. Neither "has" nor "has not" is checked. |
| R2 | Provider backup configuration | **UNKNOWN** | Lives in the platform account. Absence here proves nothing. |
| R3 | Scheduled DB snapshots via CI | **ABSENT** | All 7 workflows read; none invokes a dump, transfer or platform-backup action. |
| R4 | `pg_dump` / `pg_restore` | **ABSENT** | No PostgreSQL client binaries on PATH. |
| R5 | Physical replication (`pg_basebackup`) | **ABSENT** | Not on PATH. |
| R6 | Restore runbook | **DOCUMENTED_ONLY** | `DEPLOYMENT_GUIDE.md` records a backup artefact + SHA-256. A manifest of a file is not a procedure for restoring one. |
| R7 | Encrypted off-site backup objects | **ABSENT** | No object-storage client dependency; no workflow uploads a DB artefact. |
| R8 | Backup retention policy | **ABSENT** | `.gitignore` patterns cover local SQLite dev files, not backups. |
| R9 | Disaster-recovery documentation | **ABSENT** | No DR or failover document. |
| R10 | Local database snapshots | **ABSENT** | No snapshot in this worktree; the named ones are gitignored. |
| R11 | Object-storage client available | **ABSENT** | `boto3` not importable. |
| R12 | Engine-side recovery reporting | **PROVEN** | The engine reports its own gap. This is honesty, not a capability. |

**Only R12 is `PROVEN`, and it is the engine reporting that it has no recovery
path.** Two entries are `UNKNOWN` rather than `ABSENT` on purpose: claiming the
platform *lacks* PITR would be a fabricated result in the reassuring direction.

### Two defects found in my own inventory

1. **False `PROVEN`.** The first detector matched the bare words "backup" and
   "snapshot", and reported `verification-cron.yml` as a backup job — because the
   worker writes to `scholarship_snapshots`. A capability inventory that reports
   `PROVEN` for something absent is worse than no inventory. Now matches **actions**
   only (`pg_dump`, `aws s3 cp`, `gsutil`, `rclone`, `neonctl`, `wal-g`, `barman`,
   `pgbackrest`), with a regression test that a file merely *saying* "snapshot" is
   not a backup.
2. **A misleading dialect inference.** R1 keyed off this process's configured
   dialect, which defaults to SQLite locally. That would have implied the
   production platform was checked and has no PITR. Production is now established
   from repository assertion only (`.env.example`, `DEPLOYMENT_GUIDE.md`,
   `test_neon_migration.py` → PostgreSQL), and the method is reported alongside
   the answer.

---

## 5. RECOVERY PROOF

> ### NOT PROVEN

| Requirement | Status | Why |
|---|---|---|
| A — a recoverable source exists | ABSENT | No backup source of any kind was found. |
| B — works independently of the application | ABSENT | No dump tooling; nothing to demonstrate. |
| C — targets an isolated destination | ABSENT | No restore was performed. |
| D — preserves PostgreSQL types and FK | ABSENT | No PostgreSQL server available. |
| E — row + child evidence + history + verification + provenance | ABSENT | No restore to verify against. |
| F — recovery point identifiable | ABSENT | No restore point exists. |
| G — reproducible for an owner to trust | ABSENT | No procedure has been executed. |
| H — evidence retained as an auditable artefact | ABSENT | Nothing to retain. |

**`CONFIGURED_NOT_PROVEN` is not accepted as satisfying a requirement.** That is
the exact reasoning — "the platform offers it" — that turns an irreversible
operation into an incident.

### What *was* built: a harness that refuses to fake a pass

`scripts/verify_recovery_path.py` performs the full Phase 4 chain — restore into an
isolated destination, schema check, FK-graph check against the seven known
relationships, representative rows, child rows in all seven tables, verification
state, provenance, timings — and writes the dated evidence artefact the gate
reads.

It **refuses** rather than degrading:

- **non-PostgreSQL source or destination.** Verified: with a SQLite URL it exits 2
  with *"a SQLite round-trip validates SQLite's type affinity and its optional
  foreign-key enforcement — a different database from the one in production, so
  accepting one would produce a recovery proof that was never performed."*
- **a destination that looks like production** (`neon.tech`, `prod`) — restoring over
  production converts a data loss into a data loss plus a silent overwrite.
- **identical source and destination** — a restore must target an isolated database.
- **a missing URL** — no default, no fallback to the application connection.

Verified live: both refusal paths exit 2 and write no files.

---

## 6. RESTORE VERIFICATION

> ### NOT_AVAILABLE

No PostgreSQL server and no client tooling exist in this environment. `pgserver`,
`postgresql-wheel`, `testing.postgresql`, `pglite` were all probed; none yields a
usable PostgreSQL server here.

**No SQLite substitute was used, and none will be.** Requirement D is specifically
about PostgreSQL type behaviour and foreign-key enforcement. A SQLite round-trip
proves something about SQLite. Reporting it as restore evidence would be the
single most tempting shortcut in this task and it is exactly the one that turns a
missing capability into a fake green check.

What was proven instead: the **retention half** of the integration, offline
(§7), and the harness's **refusal logic**, live.

---

## 7. FK VERIFICATION

Introspected live from model metadata, not hand-written: 7 relationships,
0 unclassified, 0 cascades, 5 PRESERVE. The deleting path detaches only the one
nullable link and removes only settled fetch telemetry. **No PRESERVE table is read
for deletion at all.**

`verify_recovery_path.py` queries the *restored destination's own catalogue* for
all seven relationships — not the dump file. A restore that silently lost a table
would otherwise pass a discovery-based check that only sees what survived.

---

## 8. DRY-RUN PROOF

> ### PASS

Proven by reading the SQL the database actually received, via SQLAlchemy's
`before_cursor_execute` hook — not by asserting about the code.

| Check | Result |
|---|---|
| Zero `DELETE` statements | PASS |
| Zero `UPDATE` outside the run ledger | PASS |
| Zero writes to `scholarships` | PASS |
| Zero writes to any of the 7 child evidence tables | PASS |
| Only writes are `INSERT` + `UPDATE` on `maintenance_runs` | PASS |
| Zero DDL statements | PASS |
| The canonical visibility predicate is the only source | PASS |
| Query scope confined to catalogue + evidence + ledger | PASS |
| **Statement count constant as the dataset grows 7 → 147 records** | PASS |
| No scholarship row changes | PASS |
| No child evidence row changes | PASS |
| Public counts identical before/after | PASS |
| The only new row is the audit entry | PASS |
| Repeated runs agree on every decided field | PASS |
| Manifest generation byte-deterministic | PASS |
| An unconfirmed entry is replaced by its confirmation, not double-counted | PASS |
| Unknown record is not a candidate | PASS |
| Grace record is eligible but not a candidate | PASS |
| Evidence record is not a candidate | PASS |
| Only the fully-qualified record is a candidate | PASS |
| Grace clock resolves on a fixed boundary (0/13/14/400 days) | PASS |
| Clearing the clock reverses eligibility | PASS |
| Whole proof runs offline, no production connection | PASS |
| Deleting path still reachable (so the proofs are not vacuous) | PASS |

The constant statement count is a **scope** claim, not a performance one: the scan
is one pass with conditional aggregates, not a query per row.

**Declared write scope:** 0 scholarship rows, 0 child rows, 1 audit row. The report
states this explicitly so an operator reading it knows exactly what was written.

---

## 9. PRODUCTION DRY-RUN READINESS

| Check | Result |
|---|---|
| Required environment variables | `Settings.database_url` (dataclass field, confirmed) |
| Dry run is the default mode | PASS — `--execute-delete` is opt-in |
| Deleting branch unreachable in dry-run mode | PASS (verified by source inspection) |
| `--execute-delete` without `--recovery-path` | **REFUSED**, exit 2, message states a ledger is not a backup |
| `--execute-delete` without `--confirm-ids` | **REFUSED**, exit 2 |
| Importing the module performs no writes | PASS |
| No credential or URL is ever printed | PASS |
| URL reaches the command only via `get_settings()` | PASS — the literal `SCHOLARZONE_DATABASE_URL` appears nowhere in the script |
| Output keys stable | PASS (17 keys asserted) |
| Write scope declared | PASS |
| Bounded execution | Statement count independent of catalogue size; no per-row loop |
| Timeout behaviour | **Measured, not enforced** — `elapsed_seconds` reported; no cancellation. A production deployment wanting a hard cap should set a server-side `statement_timeout`, which this code deliberately does not set on the operator's behalf. |
| Transaction behaviour | Own transaction; the only commit writes the run row |
| Absence of destructive SQL | PASS (§8) |
| Report artefact generation | PASS |

---

## 10. WAS PRODUCTION DRY-RUN EXECUTED?

> ### PRODUCTION_DRY_RUN_EXECUTION = **NOT_PERFORMED**

No `SCHOLARZONE_DATABASE_URL`, no `.env`, no catalogue database in this
environment. **No production count is stated anywhere** — inventing one would be
the easiest way to produce a report that looks finished and is not.

Command, ready to run:

```
cd backend
python scripts/retention_dry_run.py --trigger "phase-20-production-dry-run"
```

Exit code is 0 on clean, 1 when a guard blocks. One audit row written; nothing else.

---

## 11. ALL PRODUCTION WRITE COUNTS

| Operation | Count |
|---|---|
| Production DELETE | **0** |
| Production UPDATE | **0** |
| Production INSERT | **0** |
| Production DDL / migration | **0** |
| Production purge | **0** |
| **Total production writes** | **NONE** |

Every database touched in this work was a SQLite file created inside a test's own
`tmp_path`. No production connection was opened at any point.

---

## 12. ROLLBACK EVIDENCE

Nine tests, all failures injected **at the database**, not by patching
`Session.commit`. Patching `commit` to raise before doing anything would pass a
suite with no rollback at all — which is precisely the bug this file keeps fixed.

| Mode | Injected at | Result |
|---|---|---|
| **A** child rows removed, parent delete raises | `DELETE FROM scholarships` | 0 deleted; **all** rows survive; child-row counts unchanged; discovery link **not** left detached |
| **B** parent delete fails after 2 successes | 3rd `DELETE FROM scholarships` | 0 deleted; all survive — earlier successes rolled back |
| **C** database statement error | child-table `DELETE` | 0 deleted; all survive |
| **D** transaction commit failure | `DELETE FROM scholarships` | 0 deleted; all survive; run **not** reported `ok` |
| **E** timeout | `DELETE FROM scholarships` | 0 deleted; all survive |
| **F** connection loss | `DELETE FROM scholarships` | 0 deleted; all survive |
| **G** duplicate execution | same ids twice; repeated ids in one run | 2nd run deletes 0; ledger not double-counted; repeated id deleted once |
| **H** restart during grace period | new engine + new session, 4× | grace-eligible record survives every restart; clock does not advance with restarts |
| Cross-mode | 6 modes × all assertions | **No partially completed destructive transaction survives** |

### The `_delete_batch` rollback fix is confirmed effective

Test A is the specific regression: the guard wraps the **whole mutation**, not
just `commit`. Previously the discovery-link detaches and fetch-attempt deletions
were outside the `try`, so a statement failure would have committed child-row
changes against records that were never deleted. Both A and B now assert child-row
counts are unchanged, which is the assertion that would have failed before the fix.

A retry after an abort succeeds — the engine is not left poisoned.

---

## 13. FAILURE-INJECTION EVIDENCE

Covered in §12. Additionally, the fixture supports *Nth-match* injection, because
a failure on the first match proves rollback but a failure on the **third** proves
that work already applied earlier in the same batch is undone. Both are required;
only a counter expresses the second.

---

## 14. MANIFEST SEMANTICS

> ### MANIFEST ≠ BACKUP

Stated in the ledger itself, not only in a docstring:

```json
"MANIFEST != BACKUP": "This file records what the retention engine deleted and the
exact reason each record was classified that way. It is NOT a backup, NOT a restore
point, and NOT a recovery path. It contains no schema, no type information, no
transaction boundaries and no child rows, so it cannot reinstate a deleted
scholarship inside the foreign-key graph the application depends on, and it cannot
rewind a committed transaction."
```

Every written entry carries `manifest_is_a_backup: false`, `recoverable: false`,
`manifest_kind: "retention_deletion_manifest"`, and
`purpose: "audit and reconciliation only"`.

### Required metadata, present per record

`record_identity`, `classification_reason`, `classification_detail`, `state`,
`grace_eligible`, `decision_timestamp`, `run_id`, `contract_version`,
`conditions_verified`, `dependencies_present_at_decision`, `dependencies_preserved`,
`dependency_policy`, `recoverable_from_this_entry: false`, `recovery_note`.

### Credential refusal

`append_deletion_manifest` walks the entry and **raises** on any
credential-shaped key — `password`, `secret`, `token`, `api_key`, `credential`,
`authorization`, `database_url`, `dsn`, `email`, and 8 more — at any nesting depth.
Verified for nested structures, and the refused entry is not written at all.

The check is **by key, not by value**, because the dangerous case is a new field
someone adds to a batch entry without thinking about where it lands.

### The manifest stores no row data

Deliberately. A full payload would help manual re-insertion and would also mean an
untracked second copy of the catalogue. Audit and reconciliation is the purpose;
recovery needs a restore, not a JSON file.

### Defect found and fixed: the ledger is now append-only

The Phase 13 scope audit caught **`backend/config/purged_records_archive.json`
losing 29,909 lines**. Root cause: `append_deletion_manifest` rebuilt `records`
from `batches` and recomputed `count`. The closed-record collector's ledger has
**no `batches` key at all** — 151 records live in a top-level `records`. So the
rewrite emptied it.

**Every test passed.** All of them wrote to a fresh temporary ledger and never
exercised the shared one. The file was restored from git immediately.

The function is now append-only, scoped to `retention_*` keys it owns
(`retention_batches`, `retention_summary`, `retention_runs`). The collector's
`records`, `count`, `breakdown`, `child_rows`, `children`, `purged_at` are left
byte-identical. An unreadable ledger is flagged, not replaced. Eight regression
tests pin the collector's real shape, including that it has no `batches` key.

### Second defect: `ledger=None` was not "no ledger"

`ledger=None` means *use the default* — the tracked repository file. A test
intended silence and instead wrote to it. `write_manifest: bool = True` now makes
silence an explicit choice. Verified: a full retention run leaves the repository
ledger byte-identical.

---

## 15. HARD-DELETE GATE CHECKLIST

`app/services/retention_release_gate.py` — `evaluate_release_gate()` is callable
and testable. **Absence is a verdict, not an absence:** with no evidence, every
evidence-derived condition is `ABSENT`, never "assumed fine".

| # | Condition | Source | Status |
|---|---|---|---|
| 1 | Verified recovery source exists | evidence | **NOT MET** — `RECOVERY_PATH_NOT_PROVEN` |
| 2 | Restore test passed | evidence | **NOT MET** — no restore performed |
| 3 | FK integrity validated after restore | evidence | **NOT MET** |
| 4 | Representative row + child evidence recovered | evidence | **NOT MET** |
| 5 | Dry-run remains non-destructive | code | MET |
| 6 | `DELETE_CANDIDATE` classification is proven | code | MET |
| 7 | Grace period is satisfied | evidence | **NOT MET** — no candidate set named |
| 8 | Rollback/recovery procedure is documented | evidence | **NOT MET** — procedure exists as a plan, not executed |
| 9 | Owner explicitly authorises deletion | evidence | **NOT MET** — not given |
| 10 | Deletion execution is bounded | code | MET |
| 11 | Deletion is auditable | code | MET |
| 12 | No active conflicting verification/evidence state | evidence | **NOT MET** |

### **4 of 12 met. Verdict: HELD.**

### Three properties of the gate itself, tested

1. **With no evidence the gate is HELD** — every evidence condition `ABSENT`.
2. **A complete-looking evidence file alone does not release the gate.** Condition 1
   re-derives the live recovery contract rather than reading the artefact, so a
   hand-written file cannot wave it open. This is the gate's most important negative
   test.
3. **Owner authorisation is inferable from nothing.** It lives in an `__owner__`
   namespace that no recovery artefact can populate.

---

## 16. OWNER ACTION REQUIRED

> ### YES

In order, each unblocking the next:

1. **Decide the backup technology and authorise building it** (plan items 1–5).
   Blocking item. Nothing else can proceed without it.
2. **Create the recovery source** — platform PITR plus a nightly logical dump.
3. **Run `scripts/verify_recovery_path.py`** against it, restoring into an isolated
   PostgreSQL destination. Produces the evidence artefact; unlocks gate conditions
   1–4 and 8.
4. **Run the production dry run** and resolve whatever it reports. Expect
   `max_ambiguous_ratio` to fire: real catalogues accumulate verification statuses
   no module has classified. Each must be adjudicated, and each is retained
   meanwhile.
5. **Adjudicate the retained population by decision, not by sweep.** Records hidden
   by the image gate, quarantined, or carrying evidence each need a human call.
5. **Record RPO and RTO**, measured rather than estimated, with owner sign-off.
6. **Name the exact candidate set**, every id past its grace period (condition 7).
7. **Obtain explicit owner authorisation** naming the ids and the recovery path
   (condition 9).

Only then set `cleanup_enabled=True` **and** `dry_run=False`, and invoke
`retention_dry_run.py --execute-delete --recovery-path "…" --confirm-ids "…"`.

---

## 17. UNRESOLVED ITEMS

**4 unresolved.**

| # | Item | Why it cannot be closed here |
|---|---|---|
| U1 | Provider PITR and backup configuration (R1, R2) | Platform-account capability. Not observable from a repository or an unauthenticated process. Needs someone with console access to answer, and the answer recorded. |
| U2 | Restore test / FK-after-restore / child-evidence recovery (conditions 2–4) | No PostgreSQL server and no dump tooling in this environment. Cannot be approximated without a fake pass. |
| U3 | Production dry run | No authorised connection. No production figure is stated anywhere. |
| U4 | Production UNKNOWN / AMBIGUOUS counts | Only knowable from the production dry run. The `max_ambiguous_ratio` guard is expected to fire; what it will find is unknown. |

None of these is a blocker to the engine itself. All four block hard delete, which
is held.

---

## 18. TESTING

**Retention suites: 336 collected, all passing.**

| File | Cases | Covers |
|---|---|---|
| `test_retention_admin_review_protection.py` | 99 | Phases 2, 4, 10 |
| `test_retention_engine.py` | 65 | Phases 5, 7, 8, 9, 12, 13, 14, 18 |
| `test_retention_recovery_gate.py` | 79 | Phases 1, 2, 3, 5, 8, 10, 11 |
| `test_retention_invariants.py` | 38 | Phases 15, 16, 18, 19 |
| `test_retention_dry_run_safety.py` | 29 | Phase 6 |
| `test_retention_production_readiness.py` | 15 | Phase 7 |
| `test_retention_failure_injection.py` | 9 | Phase 9 |

**Full backend suite: run without `-x`.** Result in §19.

**Lint / import smoke:** all six new modules compile; both CLI scripts import with
no module-level side effects; no unused imports.

### Failure classification (Phase 12)

| Class | Count | Detail |
|---|---|---|
| **CANDIDATE_REGRESSION** | **0** | No test that passed at `8ac1c9a` now fails. |
| PRE_EXISTING | 8 | `tests/test_neon_migration.py` — a gitignored migration SQL file absent from the worktree. Present at baseline, identical names. |
| PRE_EXISTING | 1 | `scripts/artifact_smoke_test.py::test_endpoint`. |
| ENVIRONMENT_ONLY | 4 | Phase 8's PostgreSQL half (U2) and Phase 20 (U3) — reported as NOT_AVAILABLE rather than skipped silently. |

**No test was weakened.** No `-x`, no skip added to make a run green, no assertion
loosened to accommodate a defect. Where a test failed, the cause was diagnosed and
either the product or the test was corrected — 6 defects in my own new code this
way, each recorded below.

### Six defects found in this work's own code

| Defect | Impact | Status |
|---|---|---|
| Ledger rebuilt `records` from `batches`, emptying the collector's 151 records | **Data loss**, 29,909 lines | Fixed: append-only, 8 regression tests |
| `ledger=None` meant "use the default" (the tracked file) | Suite wrote to the repo ledger | Fixed: explicit `write_manifest` |
| `CONFLICTING` labelled `STATE_KEEP` | Wrong self-description; verdict still safe | Fixed: bucket↔state map, asserted |
| State assertion logic inverted | Assertion rejected valid decisions | Fixed: correct biconditional |
| Inventory matched bare nouns, false `PROVEN` on a workflow | Inventory worse than none | Fixed: action markers + regression test |
| R1 dialect inferred from a local SQLite default | Would imply platform checked | Fixed: repository assertion only |

All six were caught by tests or the scope audit — none by review.

---

## 19. FULL SUITE RESULT

Run **without `-x`**, in the clean worktree, at candidate
`8ac1c9a40063221904c8994693ffa18746d5fa9d`.

| | Baseline `8ac1c9a` | After retention work | After recovery work | Delta vs baseline |
|---|---|---|---|---|
| Passed | 4 456 | 4 658 | **4 790** | **+334** |
| Failed | 8 | 8 | 8 | **0** |
| Errors | 1 | 1 | 1 | **0** |
| Skipped | 11 | 11 | 11 | 0 |
| Warnings | 13 | 13 | 13 | 0 |
| Duration | 368 s | 381 s | 312 s | — |

**Arithmetic reconciles exactly:** 4 456 baseline + 334 retention tests = 4 790
actual. The +334 is precisely the 334 collected retention cases in §18; nothing
else moved.

**The failing set is byte-identical to baseline, name for name:**

| Test | Class |
|---|---|
| `test_neon_migration.py::TestMigrationHeaderParsing::test_actual_migration_file_header_not_in_executable_statements` | PRE_EXISTING |
| `test_neon_migration.py::TestUtf8Encoding::test_migration_file_is_utf8` | PRE_EXISTING |
| `test_neon_migration.py::TestUtf8Encoding::test_em_dash_present_in_sql` | PRE_EXISTING |
| `test_neon_migration.py::TestUtf8Encoding::test_en_dash_present_in_sql` | PRE_EXISTING |
| `test_neon_migration.py::TestBooleanConversion::test_migration_sql_has_true_not_integers` | PRE_EXISTING |
| `test_neon_migration.py::TestBindParameterDetection::test_detect_bind_params_real_migration_file_has_none` | PRE_EXISTING |
| `test_neon_migration.py::TestValidateMigrationFile::test_validate_real_migration_file` | PRE_EXISTING |
| `test_neon_migration.py::TestValidateMigrationFile::test_validate_real_file_in_report` | PRE_EXISTING |
| `scripts/artifact_smoke_test.py::test_endpoint` (error) | PRE_EXISTING |

All nine are caused by a gitignored migration SQL file that is absent from a clean
worktree, and by a pre-existing artifact-test issue. **None is related to
retention, and none was present or absent differently at any point.**

> **CANDIDATE_REGRESSION: 0**

### Post-run side-effect verification

| Check | Result |
|---|---|
| `backend/config/purged_records_archive.json` | **byte-identical**; 151 records, count 151, no `retention_*` keys added |
| Candidate worktree `git diff 8ac1c9a` | **empty** — 0 tracked files modified |
| Primary dirty worktree | **untouched** — 495 changed paths, same as baseline; HEAD still `8ac1c9a` |

The ledger check is the one that matters most here, given §14: a retention test
that wrote to the shared ledger would have corrupted the collector's permanent
record of past deletions. The fix in §14 and the `write_manifest` flag together
mean a full 4 790-test run now leaves it exactly as it found it.

---

## FINAL CLASSIFICATION

> ## `RECOVERY_PATH_NOT_PROVEN_HARD_DELETE_HELD`

Not `RECOVERY_PATH_PROVEN_HARD_DELETE_HELD`: no recovery source exists, so no
restore test was performed. Not `DRY_RUN_PROVEN_HARD_DELETE_HELD`: that
classification understates the finding, because the dry run was *not* the binding
constraint — recovery is. Not `MERGE_BLOCKED`: **0 regressions**. Not `UNRESOLVED`:
the engine and every offline proof are complete; what is unresolved is four
externally-dependent items, all listed.

**Hard delete remains HELD at 4 of 12 gate conditions.** Nothing about that is
recoverable by writing more code.
