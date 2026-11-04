"""
Summary Generator for Production Purge Preflight Gates

Generates final preflight report with proper status handling.
Distinguishes PASS, FAIL, SKIPPED, BLOCKED, MANUAL_REQUIRED.
Never counts a skipped gate as passed.
Never counts a missing artifact as passed.
Verifies actual result JSON.
Verifies required evidence fields.
Verifies the correct PR commit SHA.
Fails if any mandatory gate is missing or incomplete.
"""

import json
import os
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

GATE_NAMES = {
    "gate1": "Gate 1 - Atomicity and Rollback",
    "gate2": "Gate 2 - Production Identity",
    "gate3": "Gate 3 - Dependencies",
    "gate4": "Gate 4 - Backup & Restore",
    "gate5": "Gate 5 - Classification",
    "gate6": "Gate 6 - Cycle Validation",
    "gate7": "Gate 7 - Git Safety",
}

MANDATORY_GATES = ["gate1", "gate2", "gate3", "gate4", "gate5", "gate6", "gate7"]

SCHEMA_VERSION = "1.0.0"
VALID_STATUSES = {"PASS", "FAIL", "ERROR", "BLOCKED", "MANUAL_REQUIRED", "SKIPPED", "UNKNOWN"}
REQUIRED_METADATA_FIELDS = {"commit_sha", "run_id", "run_attempt", "gate_id", "schema_version", "workflow", "timestamp"}


@dataclass
class GateSummary:
    """Summary for a single gate."""
    gate_id: str
    name: str
    status: str
    has_artifact: bool
    error: Optional[str] = None
    key_evidence: Dict[str, Any] = None
    validation_errors: List[str] = None

    def __post_init__(self):
        if self.key_evidence is None:
            self.key_evidence = {}
        if self.validation_errors is None:
            self.validation_errors = []


@dataclass
class PreflightSummary:
    """Complete preflight summary."""
    workflow: str = ""
    run_id: str = ""
    run_number: int = 0
    run_attempt: int = 1
    commit_sha: str = ""
    trigger: str = ""
    timestamp: str = ""
    gates: Dict[str, GateSummary] = None
    overall_status: str = "INCOMPLETE"
    all_mandatory_passed: bool = False
    missing_mandatory: list[str] = None
    validation_errors: List[str] = None

    def __post_init__(self):
        if self.gates is None:
            self.gates = {}
        if self.missing_mandatory is None:
            self.missing_mandatory = []
        if self.validation_errors is None:
            self.validation_errors = []


def validate_gate_result_schema(result: dict, gate_id: str) -> List[str]:
    """Validate gate result JSON schema and required metadata fields."""
    errors = []

    if not isinstance(result, dict):
        errors.append(f"Gate {gate_id}: result is not a JSON object")
        return errors

    if "status" not in result:
        errors.append(f"Gate {gate_id}: missing required 'status' field")
    elif result["status"] not in VALID_STATUSES:
        errors.append(f"Gate {gate_id}: invalid status '{result['status']}', must be one of {sorted(VALID_STATUSES)}")

    for field in REQUIRED_METADATA_FIELDS:
        if field not in result:
            errors.append(f"Gate {gate_id}: missing required metadata field '{field}'")
        elif not result[field]:
            errors.append(f"Gate {gate_id}: metadata field '{field}' is empty")

    if "schema_version" in result and result["schema_version"] != SCHEMA_VERSION:
        errors.append(f"Gate {gate_id}: schema version mismatch, expected '{SCHEMA_VERSION}', got '{result['schema_version']}'")

    if "gate_id" in result and result["gate_id"] != gate_id:
        errors.append(f"Gate {gate_id}: gate_id in artifact ('{result['gate_id']}') does not match expected '{gate_id}'")

    return errors


def validate_gate_metadata(result: dict, expected_commit_sha: str, expected_run_id: str, expected_run_attempt: int,
                           expected_workflow: str, gate_id: str) -> List[str]:
    """Validate gate result metadata matches expected values."""
    errors = []

    if "commit_sha" in result:
        actual_sha = result["commit_sha"]
        if actual_sha and actual_sha != expected_commit_sha:
            errors.append(f"Gate {gate_id}: commit SHA mismatch, expected '{expected_commit_sha[:12]}', got '{actual_sha[:12]}'")

    if "run_id" in result:
        actual_run_id = str(result["run_id"])
        if actual_run_id and actual_run_id != expected_run_id:
            errors.append(f"Gate {gate_id}: run ID mismatch, expected '{expected_run_id}', got '{actual_run_id}'")

    if "run_attempt" in result:
        actual_attempt = result["run_attempt"]
        if actual_attempt is not None and int(actual_attempt) != expected_run_attempt:
            errors.append(f"Gate {gate_id}: run attempt mismatch, expected '{expected_run_attempt}', got '{actual_attempt}'")

    if "workflow" in result:
        actual_workflow = result["workflow"]
        if actual_workflow and actual_workflow != expected_workflow:
            errors.append(f"Gate {gate_id}: workflow mismatch, expected '{expected_workflow}', got '{actual_workflow}'")

    return errors


def load_gate_result(artifacts_dir: Path, gate_id: str, expected_commit_sha: str = "", expected_run_id: str = "",
                     expected_run_attempt: int = 1, expected_workflow: str = "") -> Optional[dict]:
    """Load and validate gate result from artifacts directory."""
    possible_names = [
        f"{gate_id}_result.json",
        f"{gate_id.replace('_', '-')}_result.json",
    ]

    for name in possible_names:
        path = artifacts_dir / name
        if path.exists():
            try:
                with open(path, "r") as f:
                    result = json.load(f)
            except json.JSONDecodeError as e:
                return {"_load_error": f"Invalid JSON: {e}", "_artifact_path": str(path)}

            schema_errors = validate_gate_result_schema(result, gate_id)
            if schema_errors:
                result["_schema_errors"] = schema_errors

            if expected_commit_sha or expected_run_id or expected_workflow:
                metadata_errors = validate_gate_metadata(
                    result, expected_commit_sha, expected_run_id, expected_run_attempt, expected_workflow, gate_id
                )
                if metadata_errors:
                    result["_metadata_errors"] = metadata_errors

            return result
    return None


def extract_key_evidence(gate_id: str, result: dict) -> dict:
    """Extract key evidence fields for summary."""
    evidence = {}

    if gate_id == "gate1":
        evidence = {
            "deleted_count": result.get("deleted_count"),
            "exact_match": result.get("exact_match"),
            "rollback_test_passed": result.get("rollback_test_passed"),
            "idempotent_test_passed": result.get("idempotent_test_passed"),
            "final_count": result.get("final_count"),
        }
    elif gate_id == "gate2":
        evidence = {
            "identity_match": result.get("identity_match"),
            "total_found": result.get("total_found"),
            "missing_ids": result.get("missing_ids"),
            "neon_project_id": result.get("neon_project_id"),
            "neon_branch_name": result.get("neon_branch_name"),
        }
    elif gate_id == "gate3":
        evidence = {
            "cascade_fk_count": result.get("cascade_fk_count"),
            "total_references_to_targets": result.get("total_references_to_targets"),
            "safe_to_delete": result.get("safe_to_delete"),
            "inspection_errors": result.get("inspection_errors"),
        }
    elif gate_id == "gate4":
        evidence = {
            "backup_verified": result.get("backup_verified"),
            "checksum_verified": result.get("checksum_verified"),
            "gpg_fingerprint_verified": result.get("gpg_fingerprint_verified"),
            "restore_test_passed": result.get("restore_test_passed"),
            "pitr_status": result.get("pitr_status"),
        }
    elif gate_id == "gate5":
        evidence = {
            "closed_count": result.get("closed_count"),
            "closing_soon_count": result.get("closing_soon_count"),
            "blocked_count": result.get("blocked_count"),
            "classification_errors": result.get("classification_errors"),
        }
    elif gate_id == "gate6":
        evidence = {
            "expired_cycles": result.get("expired_cycles"),
            "evergreen_programmes": result.get("evergreen_programmes"),
            "future_deadlines": result.get("future_deadlines"),
            "blocked_ids": result.get("blocked_ids"),
        }
    elif gate_id == "gate7":
        evidence = {
            "branch_match": result.get("branch_match"),
            "worktree_isolated": result.get("worktree_isolated"),
            "secrets_detected": len(result.get("secrets_detected", [])),
            "unrelated_changes": len(result.get("unrelated_changes", [])),
            "production_mutation_risk": result.get("production_mutation_risk"),
        }

    return evidence


def determine_gate_status(result: dict) -> str:
    """Determine gate status from result, considering validation errors."""
    if "_load_error" in result:
        return "ERROR"
    if "_schema_errors" in result and result["_schema_errors"]:
        return "ERROR"
    if "_metadata_errors" in result and result["_metadata_errors"]:
        return "ERROR"

    status = result.get("status", "UNKNOWN")

    if status == "PASS":
        return "PASS"
    elif status == "FAIL":
        return "FAIL"
    elif status == "ERROR":
        return "ERROR"
    elif status == "BLOCKED":
        return "BLOCKED"
    elif status == "MANUAL_REQUIRED":
        return "MANUAL_REQUIRED"
    elif status == "SKIPPED":
        return "SKIPPED"
    else:
        return "UNKNOWN"


def generate_summary(artifacts_dir: Path, commit_sha: str = "", run_id: str = "", run_number: str = "",
                     run_attempt: str = "1", workflow: str = "") -> PreflightSummary:
    """Generate complete preflight summary with full validation."""
    expected_commit_sha = commit_sha or os.getenv("GITHUB_SHA", "")
    expected_run_id = run_id or os.getenv("GITHUB_RUN_ID", "")
    expected_run_attempt = int(run_attempt or os.getenv("GITHUB_RUN_ATTEMPT", "1"))
    expected_workflow = workflow or os.getenv("GITHUB_WORKFLOW", "unknown")

    summary = PreflightSummary(
        workflow=expected_workflow,
        run_id=expected_run_id,
        run_number=int(run_number or os.getenv("GITHUB_RUN_NUMBER", "0")),
        run_attempt=expected_run_attempt,
        commit_sha=expected_commit_sha[:12] if expected_commit_sha else "",
        trigger=os.getenv("GITHUB_EVENT_NAME", "unknown"),
        timestamp=datetime.utcnow().isoformat() + "Z",
    )

    all_gates_executed = True

    for gate_id in MANDATORY_GATES:
        result = load_gate_result(
            artifacts_dir, gate_id,
            expected_commit_sha, expected_run_id, expected_run_attempt, expected_workflow
        )

        if result is None:
            all_gates_executed = False
            summary.gates[gate_id] = GateSummary(
                gate_id=gate_id,
                name=GATE_NAMES.get(gate_id, gate_id),
                status="SKIPPED",
                has_artifact=False,
                error="No artifact found - gate was not executed",
                validation_errors=["Missing artifact"],
            )
            summary.missing_mandatory.append(gate_id)
        else:
            validation_errors = []
            if "_schema_errors" in result:
                validation_errors.extend(result["_schema_errors"])
            if "_metadata_errors" in result:
                validation_errors.extend(result["_metadata_errors"])
            if "_load_error" in result:
                validation_errors.append(result["_load_error"])

            status = determine_gate_status(result)

            if status == "SKIPPED":
                all_gates_executed = False
                summary.missing_mandatory.append(gate_id)

            summary.gates[gate_id] = GateSummary(
                gate_id=gate_id,
                name=GATE_NAMES.get(gate_id, gate_id),
                status=status,
                has_artifact=True,
                error=result.get("error"),
                key_evidence=extract_key_evidence(gate_id, result),
                validation_errors=validation_errors,
            )

    if not all_gates_executed:
        summary.validation_errors.append("Not all mandatory gates were executed (single-gate or partial run)")

    all_passed = True
    for gate_id in MANDATORY_GATES:
        gate_summary = summary.gates.get(gate_id)
        if gate_summary is None or gate_summary.status != "PASS":
            all_passed = False
            if gate_summary and gate_summary.status in ("SKIPPED", "ERROR", "FAIL", "BLOCKED", "MANUAL_REQUIRED", "UNKNOWN"):
                summary.validation_errors.append(f"Gate {gate_id} status is {gate_summary.status}, not PASS")

    summary.all_mandatory_passed = all_passed

    if all_passed and all_gates_executed:
        summary.overall_status = "ALL_PREFLIGHT_GATES_COMPLETE"
    elif summary.missing_mandatory:
        summary.overall_status = "INCOMPLETE_MISSING_GATES"
    else:
        summary.overall_status = "FAILED_GATES_PRESENT"

    return summary


def print_summary(summary: PreflightSummary) -> None:
    """Print formatted summary to stdout."""
    print("=" * 70)
    print("PRODUCTION PURGE PREFLIGHT - FINAL REPORT")
    print("=" * 70)
    print(f"Workflow:     {summary.workflow}")
    print(f"Run ID:       {summary.run_id}")
    print(f"Run Number:   {summary.run_number}")
    print(f"Run Attempt:  {summary.run_attempt}")
    print(f"Commit SHA:   {summary.commit_sha}")
    print(f"Trigger:      {summary.trigger}")
    print(f"Timestamp:    {summary.timestamp}")
    print(f"Overall:      {summary.overall_status}")
    print()

    print("-" * 70)
    print(f"{'GATE':<30} {'STATUS':<15} {'ARTIFACT':<10} {'KEY EVIDENCE'}")
    print("-" * 70)

    for gate_id in MANDATORY_GATES:
        gate = summary.gates.get(gate_id)
        if gate:
            artifact = "✓" if gate.has_artifact else "✗"
            evidence_str = ""
            if gate.key_evidence:
                key_items = []
                for k, v in gate.key_evidence.items():
                    if v is not None:
                        key_items.append(f"{k}={v}")
                evidence_str = "; ".join(key_items[:3])

            status_icon = {
                "PASS": "✅",
                "FAIL": "❌",
                "SKIPPED": "⏭️",
                "BLOCKED": "🚫",
                "MANUAL_REQUIRED": "📋",
                "ERROR": "💥",
                "UNKNOWN": "❓",
            }.get(gate.status, "❓")

            print(f"{gate.name:<30} {status_icon} {gate.status:<12} {artifact:<10} {evidence_str}")

            if gate.validation_errors:
                for ve in gate.validation_errors:
                    print(f"{'':<30}      ↳ VALIDATION: {ve}")

    print("-" * 70)
    print()

    for gate_id in MANDATORY_GATES:
        gate = summary.gates.get(gate_id)
        if gate and gate.status in ("FAIL", "ERROR", "BLOCKED"):
            print(f"\n{gate.name} - {gate.status}")
            print(f"  Error: {gate.error}")
            if gate.key_evidence:
                for k, v in gate.key_evidence.items():
                    print(f"  {k}: {v}")

    if summary.missing_mandatory:
        print(f"\n⚠️  MISSING MANDATORY GATES: {', '.join(summary.missing_mandatory)}")
        print("   The overall preflight is INCOMPLETE.")
        print("   Run with 'all' gate option to execute all gates.")

    if summary.validation_errors:
        print("\n⚠️  VALIDATION ERRORS:")
        for ve in summary.validation_errors:
            print(f"   - {ve}")

    print()
    print("=" * 70)

    if summary.overall_status == "ALL_PREFLIGHT_GATES_COMPLETE":
        print("🎉 ALL PREFLIGHT GATES PASSED")
        print("Ready for production deletion approval (separate explicit operation)")
    elif summary.overall_status == "INCOMPLETE_MISSING_GATES":
        print("⚠️  PREFLIGHT INCOMPLETE - Some gates were not executed")
        print("This summary only reflects executed gates.")
        print("A full 'all' gate run is required for production deletion approval.")
    else:
        print("❌ PREFLIGHT FAILED - Review individual gate results above")

    print("=" * 70)


def save_summary(summary: PreflightSummary, output_path: Path) -> None:
    """Save summary as JSON."""
    with open(output_path, "w") as f:
        json.dump(asdict(summary), f, indent=2, default=str)


def main(artifacts_dir: str = "artifacts", commit_sha: str = "", run_id: str = "", run_number: str = "",
         run_attempt: str = "1", workflow: str = "") -> int:
    """CLI entry point for summary generation."""
    artifacts_path = Path(artifacts_dir)
    if not artifacts_path.exists():
        print(f"Artifacts directory not found: {artifacts_dir}", file=sys.stderr)
        return 1

    summary = generate_summary(artifacts_path, commit_sha, run_id, run_number, run_attempt, workflow)
    print_summary(summary)

    save_summary(summary, Path("preflight_summary.json"))

    if summary.overall_status == "ALL_PREFLIGHT_GATES_COMPLETE":
        return 0
    else:
        return 1


if __name__ == "__main__":
    artifacts = sys.argv[1] if len(sys.argv) > 1 else "artifacts"
    sha = sys.argv[2] if len(sys.argv) > 2 else ""
    run_id = sys.argv[3] if len(sys.argv) > 3 else ""
    run_number = sys.argv[4] if len(sys.argv) > 4 else ""
    run_attempt = sys.argv[5] if len(sys.argv) > 5 else "1"
    workflow = sys.argv[6] if len(sys.argv) > 6 else ""
    raise SystemExit(main(artifacts, sha, run_id, run_number, run_attempt, workflow))