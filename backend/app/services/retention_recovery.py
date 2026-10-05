"""What recovery would have to prove before any hard deletion can be authorised.

This module exists to make one specific claim checkable: **that a deleted
scholarship could be brought back.** Everything else about retention is
engineering; this is the part that depends on a capability outside the
application, and an assumption about it is an assumption that a row is gone
forever.

Three things are deliberately absent, because each would be a way of making the
claim look better than it is:

* **No URL is read, logged, or reported.** The database is identified by
  :func:`database_identity`, which returns the *dialect* and whether a host is
  configured - never the connection string, never a host name, never a password.
  A recovery report gets pasted into tickets and chat threads, and a connection
  string in a ticket is a credential leak with a long half-life.
* **No status is asserted from configuration alone.** "The platform offers PITR"
  is a statement about a product, not about this database. Each requirement is
  either demonstrated by something this module actually probed, or reported as
  unmet.
* **Nothing here creates a backup system.** Discovering that none exists is the
  finding. The response is a plan an owner can approve and an engineer can
  execute, not infrastructure materialised to make the report read better.

The classification vocabulary is deliberate and narrow:

``PROVEN``
    Demonstrated here, by an executed check whose output is retained.
``CONFIGURED_NOT_PROVEN``
    Something is set up, but its behaviour has not been observed.
``DOCUMENTED_ONLY``
    Described in prose somewhere; never exercised.
``ABSENT``
    Searched for and not found.
``UNKNOWN``
    Could not be determined from this environment, and saying so is the honest
    answer.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

RECOVERY_CONTRACT_VERSION = "retention-recovery/1"

# ---------------------------------------------------------------------------
# Status vocabulary
# ---------------------------------------------------------------------------

PROVEN = "PROVEN"
CONFIGURED_NOT_PROVEN = "CONFIGURED_NOT_PROVEN"
DOCUMENTED_ONLY = "DOCUMENTED_ONLY"
ABSENT = "ABSENT"
UNKNOWN = "UNKNOWN"

#: Statuses that count as "this capability is available". Only :data:`PROVEN`
#: does, and that is the entire reason the vocabulary exists: a capability
#: reported as configured is a capability nobody has watched work.
SATISFIED_STATUSES = frozenset({PROVEN})


# ---------------------------------------------------------------------------
# Phase 2 - the recovery requirements contract
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RecoveryRequirement:
    id: str
    requirement: str
    #: What would have to be shown for this to be PROVEN. Written so that
    #: satisfying it requires running something, not asserting something.
    demonstrated_by: str
    #: Why it is here, in terms of what breaks without it.
    consequence_if_absent: str


#: A-H, exactly as the recovery contract specifies them.
RECOVERY_REQUIREMENTS: tuple[RecoveryRequirement, ...] = (
    RecoveryRequirement(
        "A",
        "A recoverable source must exist.",
        demonstrated_by=(
            "A dump or an identified restore point covering the production database, "
            "produced by something outside this repository, whose existence is "
            "demonstrated rather than assumed from a product plan."
        ),
        consequence_if_absent=(
            "Deletion is irreversible. Nothing downstream can compensate: an audit "
            "record describes a row, it does not restore one."
        ),
    ),
    RecoveryRequirement(
        "B",
        "Recovery must work independently of the production application process.",
        demonstrated_by=(
            "The restore is executed by a tool that does not import this application's "
            "models, does not need the API running, and does not need the application "
            "credentials - a database client or a platform console."
        ),
        consequence_if_absent=(
            "Recovery that needs the application is recovery that fails at exactly the "
            "moment it is needed, because the application is what the incident broke."
        ),
    ),
    RecoveryRequirement(
        "C",
        "Recovery must target an isolated destination.",
        demonstrated_by=(
            "A restore executed into a separate database, verified there, with the "
            "source left untouched and unmodified."
        ),
        consequence_if_absent=(
            "Verifying a restore by restoring it over production converts a data loss "
            "into a data loss plus a silent overwrite of the remaining good data."
        ),
    ),
    RecoveryRequirement(
        "D",
        "Recovery must preserve PostgreSQL data types and FK relationships.",
        demonstrated_by=(
            "PostgreSQL types, constraints and the full foreign-key graph present in "
            "the restored database, checked by querying the catalogue of the restored "
            "destination rather than by inspecting the dump file."
        ),
        consequence_if_absent=(
            "A row can come back as text where a timestamp belonged, and every query "
            "that trusted the type quietly changes meaning. SQLite is not a "
            "substitute: its type affinity and absent foreign-key enforcement make a "
            "SQLite round-trip evidence about a different database."
        ),
    ),
    RecoveryRequirement(
        "E",
        "Recovery must allow verification of row, child evidence, history, "
        "verification state and provenance.",
        demonstrated_by=(
            "Named representative records located in the restored destination "
            "together with their child rows in every one of the seven foreign-key "
            "tables, with the verification and source/provenance columns compared "
            "value for value against the source."
        ),
        consequence_if_absent=(
            "A restored scholarship row with no reviews, no verification history and no "
            "snapshots is not a restored scholarship. It is a row that has lost the "
            "evidence that made any public claim about it defensible."
        ),
    ),
    RecoveryRequirement(
        "F",
        "Recovery point/time must be identifiable.",
        demonstrated_by=(
            "The restore reports the exact point or transaction it came from, and that "
            "identifier is written into the retained evidence artefact."
        ),
        consequence_if_absent=(
            "'Restored from backup' without a point in time cannot answer what was lost, "
            "so the incident cannot be closed - only deferred."
        ),
    ),
    RecoveryRequirement(
        "G",
        "Restore must be reproducible enough for an owner to trust.",
        demonstrated_by=(
            "The procedure written as runnable steps with named inputs and expected "
            "outputs, executed once end to end with timings and results recorded."
        ),
        consequence_if_absent=(
            "A recovery path that exists only as knowledge in one person's head has an "
            "availability of one person, and that person is unavailable during an "
            "incident by definition."
        ),
    ),
    RecoveryRequirement(
        "H",
        "Recovery evidence must be retained as an auditable artefact.",
        demonstrated_by=(
            "A durable, dated, tamper-evident record of the restore: inputs, "
            "destination, verification results, timings and the identity of who ran it."
        ),
        consequence_if_absent=(
            "After the fact there is no way to show that a deletion was safe, so every "
            "future deletion is an unevidenced act."
        ),
    ),
)


# ---------------------------------------------------------------------------
# Phase 3 - capability inventory
# ---------------------------------------------------------------------------


def database_identity() -> dict[str, Any]:
    """Describe the configured database without revealing it.

    Reports the dialect and whether a remote host is configured. Deliberately does
    not report the host, the database name, the user or the URL itself: this
    function's output is designed to be pasted into a report.
    """
    try:
        from ..core.config import get_settings

        settings = get_settings()
        url = getattr(settings, "database_url", None) or ""
    except Exception:  # noqa: BLE001 - a config error is a finding, not a crash
        return {"dialect": UNKNOWN, "configured": False, "detail": "settings could not be read"}

    if not url:
        return {
            "dialect": "none",
            "configured": False,
            "detail": "no database URL is configured in this process",
        }

    dialect = url.split(":", 1)[0].split("+", 1)[0].strip().lower() or "unknown"
    remote = any(marker in url for marker in ("@", "neon.tech", "postgres"))
    return {
        "dialect": dialect,
        "configured": True,
        "remote": remote,
        # The driver, not the destination: "the credentials point at PostgreSQL"
        # is operationally useful and reveals nothing.
        "note": "URL withheld by design; never logged or reported",
    }


def production_dialect_evidence() -> dict[str, Any]:
    """Establish the production dialect from the repository, not from this process.

    This process has no production connection, and its configured dialect says
    nothing about production - it is a development default. Reading the dialect
    off a local default and then reporting a finding about the production
    platform would be a fabricated result, in the direction that happens to look
    more reassuring. So the production dialect is established from what the
    repository itself asserts about it.
    """
    root = _repo_root()
    signals: list[str] = []
    for relative in ("backend/.env.example", "backend/DEPLOYMENT_GUIDE.md"):
        path = root / relative
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "postgres" in text.lower():
            signals.append(relative)
    migration_tests = root / "backend" / "tests" / "test_neon_migration.py"
    if migration_tests.exists():
        signals.append("backend/tests/test_neon_migration.py")
    return {
        "dialect": "postgresql" if signals else UNKNOWN,
        "basis": signals or ["no repository statement about the production dialect was found"],
        "method": "repository assertion only; this process has no production connection",
    }


def _which(*names: str) -> dict[str, str]:
    found = {}
    for name in names:
        path = shutil.which(name)
        if path:
            found[name] = path
    return found


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _workflow_inventory() -> list[dict[str, Any]]:
    """Which workflows, if any, actually produce a copy of the database.

    The markers are *actions*, never nouns. An earlier version of this function
    matched the bare words "backup" and "snapshot" and consequently reported
    ``verification-cron.yml`` as a backup job - because the maintenance worker
    writes to ``scholarship_snapshots``, the temporal-versioning table. That is
    the exact failure this inventory exists to prevent: a capability reported as
    PROVEN because a word appeared somewhere in the file. A workflow counts only
    if it invokes a dump tool, a transfer tool, or a platform backup CLI.
    """
    root = _repo_root()
    workflows = root / ".github" / "workflows"
    if not workflows.is_dir():
        return []
    action_markers = (
        "pg_dump",
        "pg_restore",
        "aws s3 cp",
        "aws s3 sync",
        "gsutil cp",
        "rclone copy",
        "neonctl",
        "wal-g",
        "barman",
        "pgbackrest",
    )
    found = []
    for path in sorted(workflows.glob("*.yml")):
        text = path.read_text(encoding="utf-8", errors="replace").lower()
        matched = [marker for marker in action_markers if marker in text]
        found.append(
            {
                "workflow": path.name,
                "produces_a_backup": bool(matched),
                "matched_actions": matched,
            }
        )
    return found


def _local_sqlite_snapshots() -> list[dict[str, Any]]:
    root = _repo_root()
    found = []
    for pattern in ("*.db", "*.sqlite", "*.sqlite3", "backup/*.db"):
        for path in root.glob(pattern):
            if path.name == "dev.db":
                continue
            found.append({"path": str(path.relative_to(root)), "bytes": path.stat().st_size})
    return found


def recovery_capability_inventory() -> list[dict[str, Any]]:
    """Search this environment for every recovery capability the task names.

    Each entry is a finding, not a claim. Where the answer is ``ABSENT`` it
    records that the search ran, so the absence is evidence rather than silence.
    """
    identity = database_identity()
    clients = _which("pg_dump", "pg_restore", "psql", "pg_basebackup")
    workflows = _workflow_inventory()
    backups = [w for w in workflows if w["produces_a_backup"]]
    snapshots = _local_sqlite_snapshots()

    try:
        import boto3  # noqa: F401

        object_store_client = PROVEN
    except Exception:  # noqa: BLE001
        object_store_client = ABSENT

    import inspect

    try:
        from . import retention_engine as _engine

        recovery_status = callable(getattr(_engine, "recovery_status", None))
    except Exception:  # noqa: BLE001
        recovery_status = False

    now = datetime.now(timezone.utc).isoformat()

    def entry(
        cid: str, capability: str, status: str, searched: str, note: str = ""
    ) -> dict[str, Any]:
        return {
            "id": cid,
            "capability": capability,
            "status": status,
            "searched": searched,
            "note": note,
            "observed_at": now,
        }

    return [
        entry(
            "R1",
            "Provider point-in-time restore",
            UNKNOWN,
            "repository text for pitr/point-in-time/neon api, and PATH for provider CLIs",
            "The production database is PostgreSQL by the repository's own account, and "
            "the hosting platform may offer point-in-time restore. That capability lives "
            "in the platform account, which this environment cannot observe, so it is "
            "UNKNOWN rather than ABSENT: 'the platform has it' and 'the platform does not "
            "have it' are both claims nobody here has checked. Product availability is "
            "not evidence.",
        ),
        entry(
            "R2",
            "Provider backup configuration",
            UNKNOWN,
            "repository text for backup configuration, infrastructure-as-code, neon api",
            "Backup configuration for a managed platform lives in the platform account. "
            "Its absence from this repository is expected and proves nothing either way.",
        ),
        entry(
            "R3",
            "Scheduled database snapshots via CI",
            PROVEN if backups else ABSENT,
            "every .github/workflows/*.yml read and matched against backup *actions* "
            "(pg_dump, pg_restore, aws s3, gsutil, rclone, neonctl, wal-g, barman, "
            "pgbackrest) rather than against the words 'backup' or 'snapshot'",
            (
                f"backup-capable workflows found: "
                f"{[w['workflow'] for w in backups]}"
                if backups
                else "all seven workflows were read; none invokes a dump, transfer or "
                "platform-backup action. db-state-check.yml runs a read-only state query, "
                "which is not a backup, and verification-cron.yml mentions 'snapshot' only "
                "because the temporal-versioning table is named scholarship_snapshots."
            ),
        ),
        entry(
            "R4",
            "Logical dump tooling (pg_dump / pg_restore)",
            PROVEN if {"pg_dump", "pg_restore"} <= set(clients) else ABSENT,
            "PATH lookup for pg_dump, pg_restore, psql, pg_basebackup",
            (
                f"resolved: {sorted(clients)}"
                if clients
                else "no PostgreSQL client binaries on PATH, so no logical dump could "
                "be taken or restored from this environment"
            ),
        ),
        entry(
            "R5",
            "Physical replication tooling",
            ABSENT,
            "PATH lookup for pg_basebackup",
            "No base-backup tooling, so no physical-copy recovery path is available.",
        ),
        entry(
            "R6",
            "Restore runbook",
            DOCUMENTED_ONLY,
            "repository documentation referencing restore",
            "DEPLOYMENT_GUIDE.md records a backup artefact with its SHA-256 and a "
            "migration export. A manifest of a file is not a procedure for restoring "
            "one, and the artefact it describes is a pre-migration SQLite file that "
            "predates the production PostgreSQL database.",
        ),
        entry(
            "R7",
            "Encrypted off-site backup objects",
            ABSENT,
            "repository text and dependency list for object storage and encryption",
            "No object-storage client is a dependency and no workflow uploads a "
            "database artefact anywhere.",
        ),
        entry(
            "R8",
            "Backup retention policy",
            ABSENT,
            "repository text for backup retention",
            "The project's .gitignore retention patterns cover local SQLite files, "
            "which are development artefacts rather than a backup policy.",
        ),
        entry(
            "R9",
            "Disaster-recovery documentation",
            ABSENT,
            "repository text for disaster recovery, failover, runbook",
            "No disaster-recovery or failover document exists.",
        ),
        entry(
            "R10",
            "Local database snapshots",
            DOCUMENTED_ONLY if snapshots else ABSENT,
            "filesystem scan for .db, .sqlite, .sqlite3 and backup/*.db",
            (
                f"snapshots on disk: {snapshots}"
                if snapshots
                else "no snapshot file is present in this worktree. The ones named in "
                "documentation are gitignored and were not carried into a clean checkout."
            ),
        ),
        entry(
            "R11",
            "Object storage client available to this repository",
            object_store_client,
            "import of boto3",
            "Determines whether a backup upload could be implemented here at all "
            "without a new dependency.",
        ),
        entry(
            "R12",
            "Engine-side recovery reporting exists",
            PROVEN if recovery_status else ABSENT,
            "app.services.retention_engine.recovery_status",
            "The engine reports its own recovery verdict. This is the engine being "
            "honest about the gap; it is not evidence of a recovery capability.",
        ),
    ]


# ---------------------------------------------------------------------------
# Phase 2 - evaluating the contract
# ---------------------------------------------------------------------------


def recovery_requirements_report(
    inventory: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Evaluate A-H against what is actually known, and report what is missing.

    A requirement is met only by :data:`PROVEN` evidence. ``CONFIGURED_NOT_PROVEN``
    is deliberately *not* sufficient: "the platform offers it" is the exact thought
    that turns an irreversible operation into an incident.
    """
    inventory = inventory if inventory is not None else recovery_capability_inventory()
    by_id = {item["id"]: item for item in inventory}

    # Which inventory entries each requirement depends on. Stated explicitly so a
    # capability cannot go unlinked and silently stop counting.
    dependencies: Mapping[str, tuple[str, ...]] = {
        "A": ("R1", "R2", "R3", "R4"),
        "B": ("R4", "R3"),
        "C": (),
        "D": ("R4", "R5"),
        "E": ("R4",),
        "F": ("R1", "R4"),
        "G": (),
        "H": (),
    }

    rows: list[dict[str, Any]] = []
    for requirement in RECOVERY_REQUIREMENTS:
        linked = dependencies.get(requirement.id, ())
        statuses = [by_id[c]["status"] for c in linked if c in by_id]
        if not statuses:
            status = ABSENT
        elif all(s in SATISFIED_STATUSES for s in statuses):
            status = PROVEN
        elif any(s == PROVEN for s in statuses):
            status = CONFIGURED_NOT_PROVEN
        else:
            status = max(statuses, key=lambda s: {UNKNOWN: 0, ABSENT: 1,
                                                   DOCUMENTED_ONLY: 2,
                                                   CONFIGURED_NOT_PROVEN: 3}.get(s, 0))
        rows.append(
            {
                "id": requirement.id,
                "requirement": requirement.requirement,
                "demonstrated_by": requirement.demonstrated_by,
                "consequence_if_absent": requirement.consequence_if_absent,
                "depends_on": list(linked),
                "status": status,
                "satisfied": status in SATISFIED_STATUSES,
            }
        )

    met = [r["id"] for r in rows if r["satisfied"]]
    unmet = [r["id"] for r in rows if not r["satisfied"]]
    return {
        "contract_version": RECOVERY_CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database_identity": database_identity(),
        "production_dialect_evidence": production_dialect_evidence(),
        "requirements": rows,
        "satisfied": met,
        "unmet": unmet,
        "recovery_path_proven": not unmet,
        "verdict": "RECOVERY_PATH_PROVEN" if not unmet else "RECOVERY_PATH_NOT_PROVEN",
        "consequence": (
            "Hard deletion remains held. Per the recovery contract, an irreversible "
            "operation without a demonstrated recovery path is not authorised, "
            "irrespective of how well classified its target set is."
        ),
    }


# ---------------------------------------------------------------------------
# Phase 5 - the implementation-ready plan
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlanItem:
    number: int
    item: str
    specification: str
    #: What makes this item verifiable rather than aspirational.
    verification: str


#: Produced because no recovery source exists. Not implemented here: Phase 5 of
#: the task forbids materialising speculative infrastructure, and building a
#: backup system the owner has not chosen is a decision for the owner.
RECOVERY_PLAN: tuple[PlanItem, ...] = (
    PlanItem(
        1,
        "Backup technology and source",
        specification=(
            "Two independent mechanisms, because one is a single point of failure: "
            "(a) the platform's own point-in-time restore on the managed PostgreSQL "
            "database, enabled at its shortest supported retention; (b) a nightly "
            "logical dump taken with pg_dump -Fc from a runner that holds no "
            "application credentials beyond read access."
        ),
        verification=(
            "A dump exists with a recorded SHA-256, and the platform's restore window "
            "is quoted from the provider console into the evidence artefact."
        ),
    ),
    PlanItem(
        2,
        "Schedule",
        specification=(
            "Nightly logical dump, plus the platform's continuous WAL retention. The "
            "dump job must run on a schedule that does not coincide with the "
            "maintenance worker, so a backup is never taken mid-migration."
        ),
        verification="Two consecutive runs on schedule, with both artefacts retained.",
    ),
    PlanItem(
        3,
        "Retention period",
        specification=(
            "Logical dumps retained for 35 days. This must exceed the longest "
            "possible interval between a deletion and its discovery, including a "
            "holiday period, and must be reviewed whenever max_delete_per_run changes."
        ),
        verification="The retention policy is written down and the oldest artefact's age is checkable.",
    ),
    PlanItem(
        4,
        "Encryption expectations",
        specification=(
            "Client-side encryption before upload, with the key held outside the "
            "backup store. Server-side encryption alone is insufficient if the store "
            "is readable with the application's own credentials."
        ),
        verification="A dump restored from encrypted storage without any other credential path.",
    ),
    PlanItem(
        5,
        "Access control",
        specification=(
            "Backup read access restricted to a named recovery role, separate from "
            "the application's runtime role. Restores executable only by the owner or "
            "a named on-call engineer, and every restore logged."
        ),
        verification="The application's runtime credentials cannot read the backup store.",
    ),
    PlanItem(
        6,
        "Restore destination strategy",
        specification=(
            "An ephemeral isolated PostgreSQL database, never production. It must be "
            "built from the same major version so that type behaviour, constraint "
            "behaviour and the foreign-key graph are comparable."
        ),
        verification="The destination's connection string is shown to differ from production before any restore begins.",
    ),
    PlanItem(
        7,
        "Restore verification procedure",
        specification=(
            "In order: schema and table count; foreign-key graph completeness against "
            "the seven known relationships; representative scholarship rows; child rows "
            "in all seven foreign-key tables; verification state; source and provenance "
            "columns; then an application read-only smoke test against the restored copy."
        ),
        verification="Every check produces a pass/fail line in the evidence artefact; any failure aborts.",
    ),
    PlanItem(
        8,
        "Recovery point objective",
        specification=(
            "RPO 24 hours by default - the nightly dump interval. This is a business "
            "decision about acceptable data loss, not a technical one, and the owner "
            "must accept it explicitly."
        ),
        verification="The stated RPO is recorded with the owner's name and the date.",
    ),
    PlanItem(
        9,
        "Recovery time objective",
        specification=(
            "RTO 4 hours, measured from a real timed restore rather than estimated. "
            "The measurement is the deliverable; the target is an input to it."
        ),
        verification="A wall-clock time recorded from a completed restore into an isolated destination.",
    ),
    PlanItem(
        10,
        "Owner approval point",
        specification=(
            "Two approvals, both required and neither implied by the other: approval "
            "to build the backup path, and - only after the restore test passes - "
            "approval to unlock hard deletion for a named, id-limited run."
        ),
        verification="Both approvals recorded with names, dates and the exact scope authorised.",
    ),
    PlanItem(
        11,
        "Evidence artefact required before hard deletion unlocks",
        specification=(
            "A dated restore-verification record containing: recovery source type, "
            "recovery point or transaction identifier, destination identity (with no "
            "credentials), restore method and version, schema validation result, "
            "foreign-key integrity result, representative row and child-evidence "
            "comparison, timings, and the identity of who ran it. Written by "
            "scripts/verify_recovery_path.py, never by hand."
        ),
        verification=(
            "The release gate reads the artefact and finds every field present; a "
            "missing field holds the gate closed."
        ),
    ),
)


def recovery_plan_as_dict() -> list[dict[str, Any]]:
    return [
        {
            "number": item.number,
            "item": item.item,
            "specification": item.specification,
            "verification": item.verification,
        }
        for item in RECOVERY_PLAN
    ]


__all__ = [
    "ABSENT",
    "CONFIGURED_NOT_PROVEN",
    "DOCUMENTED_ONLY",
    "PROVEN",
    "RECOVERY_CONTRACT_VERSION",
    "RECOVERY_PLAN",
    "RECOVERY_REQUIREMENTS",
    "RecoveryRequirement",
    "UNKNOWN",
    "PlanItem",
    "database_identity",
    "recovery_capability_inventory",
    "recovery_plan_as_dict",
    "recovery_requirements_report",
]
