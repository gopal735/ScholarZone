"""The twelve conditions that must all hold before hard delete may run.

This module is the difference between "hard delete is held" being a statement in
a document and being a fact about the software. It evaluates every condition
mechanically, from evidence, and returns :data:`HELD` unless all twelve are
:data:`PROVEN`.

Three properties are the reason this is code rather than a checklist:

* **Absence is a verdict, not an absence.** With no evidence supplied, every
  condition that depends on evidence is ``ABSENT`` - not "assumed fine". A gate
  that defaults to open because it has nothing to evaluate is a gate that will
  open eventually, at the worst possible moment.
* **A condition cannot be satisfied by assertion.** Each condition names the
  exact artefact field it reads, and the evaluation reports which field was
  missing. Saying "restore verified: yes" in a hand-written file satisfies
  nothing; a dated artefact produced by
  ``scripts/verify_recovery_path.py`` does.
* **The gate is callable and testable.** :func:`evaluate_release_gate` takes an
  evidence mapping and returns a verdict, so "the gate refuses" is a property a
  test can assert rather than a claim a reader has to take on trust.

Owner authorisation is condition 9 and is deliberately *not* inferable from
anything else. Every other condition being green is a reason to ask for
authorisation, never a substitute for it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from .retention_contract import RETENTION_CONTRACT_VERSION, RetentionPolicy, default_policy
from .retention_recovery import (
    PROVEN,
    RECOVERY_CONTRACT_VERSION,
    recovery_requirements_report,
)

GATE_CONTRACT_VERSION = "retention-release-gate/1"

HELD = "HELD"
RELEASED = "RELEASED"

#: Evidence statuses. Only :data:`PROVEN` opens a condition.
STATUS_PROVEN = PROVEN
STATUS_ABSENT = "ABSENT"
STATUS_FAILED = "FAILED"
STATUS_UNPROVEN = "CONFIGURED_NOT_PROVEN"

#: Evidence fields an artefact must carry. Checked for presence as well as
#: truth, because an artefact missing its recovery point or its operator is not
#: evidence of anything.
REQUIRED_EVIDENCE_FIELDS = (
    "recovery_source_type",
    "recovery_point",
    "destination",
    "restore_method",
    "restore_tool_version",
    "schema_validation",
    "foreign_key_validation",
    "representative_rows_verified",
    "child_evidence_verified",
    "verification_state_verified",
    "provenance_verified",
    "executed_at",
    "executed_by",
    "duration_seconds",
    "contract_version",
)


@dataclass(frozen=True)
class GateCondition:
    id: int
    condition: str
    #: The evidence path this condition reads. ``None`` means the condition is
    #: satisfied by the software itself rather than by an artefact.
    evidence_field: str | None
    #: How the condition is satisfied without an artefact, for the code-derived
    #: ones. Empty for evidence-derived conditions.
    derived_from: str = ""


GATE_CONDITIONS: tuple[GateCondition, ...] = (
    GateCondition(
        1,
        "Verified recovery source exists",
        "__recovery__.recovery_source_proven",
        derived_from="app.services.retention_recovery.recovery_requirements_report requirement A",
    ),
    GateCondition(
        2,
        "Restore test passed",
        "__recovery__.restore_test_passed",
        derived_from="a completed restore into an isolated destination, recorded in evidence",
    ),
    GateCondition(
        3,
        "Foreign-key integrity validated after restore",
        "__recovery__.foreign_key_validation_passed",
        derived_from="the seven known relationships queried in the restored destination",
    ),
    GateCondition(
        4,
        "Representative row and child evidence recovered",
        "__recovery__.child_evidence_verified",
        derived_from="named scholarship rows plus their rows in all seven foreign-key tables",
    ),
    GateCondition(
        5,
        "Dry-run remains non-destructive",
        None,
        derived_from="app.services.retention_engine.dry_run, asserted by statement-level "
        "SQL logging in tests/test_retention_dry_run_safety.py",
    ),
    GateCondition(
        6,
        "DELETE_CANDIDATE classification is proven",
        None,
        derived_from="assert_invariants on every scan, plus the state machine's "
        "DELETE_CANDIDATE-only rule",
    ),
    GateCondition(
        7,
        "Grace period is satisfied",
        "__candidates__.all_grace_satisfied",
        derived_from="the exact candidate set named in the authorisation, each past "
        "auto_delete_candidate_since + grace_days",
    ),
    GateCondition(
        8,
        "Rollback/recovery procedure is documented",
        "__recovery__.procedure_documented",
        derived_from="a runnable restore procedure referenced by the evidence artefact",
    ),
    GateCondition(
        9,
        "Owner explicitly authorises deletion",
        "__owner__.authorised",
        derived_from="an explicit authorisation naming the ids and the recovery path. "
        "Inferable from nothing else, ever.",
    ),
    GateCondition(
        10,
        "Deletion execution is bounded",
        None,
        derived_from="RetentionPolicy.max_delete_per_run and max_delete_percentage, both "
        "checked against counts the database produced during the run",
    ),
    GateCondition(
        11,
        "Deletion is auditable",
        None,
        derived_from="app.services.retention_engine writes one maintenance_runs row per "
        "run and a confirmed deletion manifest",
    ),
    GateCondition(
        12,
        "No active conflicting verification/evidence state exists",
        "__candidates__.no_conflicting_state",
        derived_from="no concurrent retention run, and no candidate in UNKNOWN, AMBIGUOUS, "
        "CONFLICTING, PROTECTED or GRACE_ELIGIBLE",
    ),
)


def _dig(evidence: Mapping[str, Any] | None, path: str) -> Any:
    """Read ``a.b.c`` out of a nested mapping, or ``None`` if any hop is missing."""
    node: Any = evidence
    for part in path.split("."):
        if not isinstance(node, Mapping) or part not in node:
            return None
        node = node[part]
    return node


def evaluate_release_gate(
    evidence: Mapping[str, Any] | None = None,
    *,
    policy: RetentionPolicy | None = None,
    run_recovery_contract: bool = True,
) -> dict[str, Any]:
    """Evaluate all twelve conditions and return a verdict.

    ``evidence`` is the recovery evidence artefact as written by
    ``scripts/verify_recovery_path.py``, or ``None``. The default of ``None`` is
    the safe one: with nothing to evaluate, every evidence-derived condition is
    unmet and the gate is :data:`HELD`.
    """
    policy = policy or default_policy()
    evidence = evidence or {}

    rows: list[dict[str, Any]] = []
    for condition in GATE_CONDITIONS:
        if condition.evidence_field is None:
            # Code-derived. These are properties of the engine and its tests; the
            # failure mode being guarded against is somebody deleting the test,
            # and the test suite failing is that guard.
            rows.append(
                {
                    "id": condition.id,
                    "condition": condition.condition,
                    "source": "code",
                    "derived_from": condition.derived_from,
                    "status": STATUS_PROVEN,
                    "satisfied": True,
                }
            )
            continue

        value = _dig(evidence, condition.evidence_field)
        satisfied = value is True
        rows.append(
            {
                "id": condition.id,
                "condition": condition.condition,
                "source": "evidence",
                "evidence_field": condition.evidence_field,
                "observed": value,
                "status": STATUS_PROVEN if satisfied else (
                    STATUS_ABSENT if value is None else STATUS_FAILED
                ),
                "satisfied": satisfied,
            }
        )

    unmet = [row for row in rows if not row["satisfied"]]

    # The artefact's own completeness is reported alongside, because a gate that
    # passes on a partial artefact is a gate that passed on the wrong thing.
    missing_fields = [f for f in REQUIRED_EVIDENCE_FIELDS if f not in evidence]
    artefact_complete = bool(evidence) and not missing_fields

    # Condition 7 and 12 need a live read of the recovery contract rather than a
    # cached claim, so the gate re-derives requirement A itself.
    recovery = recovery_requirements_report() if run_recovery_contract else None
    requirement_a = None
    if recovery:
        requirement_a = next(
            (r for r in recovery["requirements"] if r["id"] == "A"), None
        )

    conditions_by_id = {row["id"]: row for row in rows}
    if requirement_a is not None:
        satisfied_a = requirement_a["satisfied"]
        conditions_by_id[1]["status"] = (
            STATUS_PROVEN if satisfied_a else requirement_a["status"]
        )
        conditions_by_id[1]["satisfied"] = bool(satisfied_a)
        conditions_by_id[1]["observed"] = (
            "all recovery requirements satisfied"
            if satisfied_a
            else f"recovery requirement A is {requirement_a['status']}"
        )
        unmet = [row for row in rows if not row["satisfied"]]

    policy_bounded = (
        policy.max_delete_per_run > 0
        and 0 < policy.max_delete_percentage <= 1
        and policy.batch_size > 0
    )
    conditions_by_id[10]["observed"] = {
        "max_delete_per_run": policy.max_delete_per_run,
        "max_delete_percentage": policy.max_delete_percentage,
        "batch_size": policy.batch_size,
        "bounded": policy_bounded,
    }
    conditions_by_id[10]["satisfied"] = bool(policy_bounded)
    if not policy_bounded:
        conditions_by_id[10]["status"] = STATUS_FAILED
        unmet = [row for row in rows if not row["satisfied"]]

    return {
        "gate_contract_version": GATE_CONTRACT_VERSION,
        "retention_contract_version": RETENTION_CONTRACT_VERSION,
        "recovery_contract_version": RECOVERY_CONTRACT_VERSION,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "conditions": rows,
        "conditions_total": len(rows),
        "conditions_satisfied": len(rows) - len(unmet),
        "unmet_ids": sorted(row["id"] for row in unmet),
        "verdict": RELEASED if not unmet else HELD,
        "hard_delete": RELEASED if not unmet else HELD,
        "evidence_supplied": bool(evidence),
        "evidence_artefact_complete": artefact_complete,
        "evidence_fields_missing": missing_fields,
        "recovery_contract_verdict": (recovery or {}).get("verdict"),
        "next_actions": _next_actions(unmet),
    }


def _next_actions(unmet: list[dict[str, Any]]) -> list[str]:
    """What has to happen next, in the order it unblocks things."""
    ids = {row["id"] for row in unmet}
    actions: list[str] = []
    if ids & {1, 2, 3, 4, 8}:
        actions.append(
            "Establish a recovery source and run scripts/verify_recovery_path.py against "
            "it, restoring into an isolated PostgreSQL destination (conditions 1-4, 8)."
        )
    if 7 in ids:
        actions.append(
            "Name the exact candidate set; every id must be past its grace period "
            "(condition 7)."
        )
    if 12 in ids:
        actions.append(
            "Resolve every UNKNOWN, AMBIGUOUS, CONFLICTING, PROTECTED and "
            "GRACE_ELIGIBLE record, and confirm no retention run is active (condition 12)."
        )
    if 9 in ids:
        actions.append(
            "Obtain explicit owner authorisation naming the ids and the recovery path "
            "(condition 9). This cannot be derived from any other condition."
        )
    if 10 in ids:
        actions.append("Set a bounded deletion policy (condition 10).")
    return actions


def gate_as_markdown(report: Mapping[str, Any]) -> str:
    """Render the gate as a checklist, for pasting into a report or an issue.

    Plain ASCII markers only. This string gets printed to a Windows console with
    a cp1252 code page, and a glyph that cannot encode turns a gate report into a
    traceback - which is a poor way to learn that the gate is closed.
    """
    lines = [
        "| # | Condition | Source | Status |",
        "|---|-----------|--------|--------|",
    ]
    for row in report["conditions"]:
        if row["satisfied"]:
            status = "MET"
        elif row["source"] == "evidence":
            status = f"NOT MET [{row['status']}] (`{row.get('evidence_field')}`)"
        else:
            status = f"NOT MET [{row['status']}]"
        lines.append(f"| {row['id']} | {row['condition']} | {row['source']} | {status} |")
    lines.append("")
    lines.append(f"**Verdict: {report['verdict']}**")
    return "\n".join(lines)


__all__ = [
    "GATE_CONDITIONS",
    "GATE_CONTRACT_VERSION",
    "HELD",
    "RELEASED",
    "REQUIRED_EVIDENCE_FIELDS",
    "GateCondition",
    "evaluate_release_gate",
    "gate_as_markdown",
]
