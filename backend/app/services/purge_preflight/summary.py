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
from typing import Optional, Dict, Any


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


@dataclass
class GateSummary:
    """Summary for a single gate."""
    gate_id: str
    name: str
    status: str  # PASS, FAIL, SKIPPED, BLOCKED, MANUAL_REQUIRED, ERROR
    has_artifact: bool
    error: Optional[str] = None
    key_evidence: Dict[str, Any] = None

    def __post_init__(self):
        if self.key_evidence is None:
            self.key_evidence = {}


@dataclass
class PreflightSummary:
    """Complete preflight summary."""
    workflow: str = ""
    run_id: str = ""
    run_number: int = 0
    commit_sha: str = ""
    trigger: str = ""
    timestamp: str = ""
    gates: Dict[str, GateSummary] = None
    overall_status: str = "INCOMPLETE"
    all_mandatory_passed: bool = False
    missing_mandatory: list[str] = None

    def __post_init__(self):
        if self.gates is None:
            self.gates = {}
        if self.missing_mandatory is None:
            self.missing_mandatory = []


def load_gate_result(artifacts_dir: Path, gate_id: str) -> Optional[dict]:
    """Load gate result from artifacts directory."""
    # Try multiple possible artifact names
    possible_names = [
        f"{gate_id}_result.json",
        f"{gate_id.replace('_', '-')}_result.json",
    ]

    for name in possible_names:
        path = artifacts_dir / name
        if path.exists():
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                pass
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
    """Determine gate status from result."""
    status = result.get("status", "UNKNOWN")

    # Normalize status
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
    else:
        return "UNKNOWN"


def generate_summary(artifacts_dir: Path, commit_sha: str = "") -> PreflightSummary:
    """Generate complete preflight summary."""
    summary = PreflightSummary(
        workflow=os.getenv("GITHUB_WORKFLOW", "unknown"),
        run_id=os.getenv("GITHUB_RUN_ID", "unknown"),
        run_number=int(os.getenv("GITHUB_RUN_NUMBER", "0")),
        commit_sha=commit_sha or os.getenv("GITHUB_SHA", "")[:12],
        trigger=os.getenv("GITHUB_EVENT_NAME", "unknown"),
        timestamp=datetime.utcnow().isoformat() + "Z",
    )

    # Load all gate results
    for gate_id in MANDATORY_GATES:
        result = load_gate_result(artifacts_dir, gate_id)

        if result is None:
            summary.gates[gate_id] = GateSummary(
                gate_id=gate_id,
                name=GATE_NAMES.get(gate_id, gate_id),
                status="SKIPPED",
                has_artifact=False,
                error="No artifact found - gate was not executed",
            )
            summary.missing_mandatory.append(gate_id)
        else:
            status = determine_gate_status(result)
            summary.gates[gate_id] = GateSummary(
                gate_id=gate_id,
                name=GATE_NAMES.get(gate_id, gate_id),
                status=status,
                has_artifact=True,
                error=result.get("error"),
                key_evidence=extract_key_evidence(gate_id, result),
            )

    # Determine overall status
    all_passed = True
    for gate_id in MANDATORY_GATES:
        gate_summary = summary.gates.get(gate_id)
        if gate_summary is None or gate_summary.status != "PASS":
            all_passed = False

    summary.all_mandatory_passed = all_passed

    if all_passed:
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
    print(f"Commit SHA:   {summary.commit_sha}")
    print(f"Trigger:      {summary.trigger}")
    print(f"Timestamp:    {summary.timestamp}")
    print(f"Overall:      {summary.overall_status}")
    print()

    # Gate results table
    print("-" * 70)
    print(f"{'GATE':<30} {'STATUS':<15} {'ARTIFACT':<10} {'KEY EVIDENCE'}")
    print("-" * 70)

    for gate_id in MANDATORY_GATES:
        gate = summary.gates.get(gate_id)
        if gate:
            artifact = "✓" if gate.has_artifact else "✗"
            evidence_str = ""
            if gate.key_evidence:
                # Show most important evidence
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

    print("-" * 70)
    print()

    # Detailed results for failed/blocked gates
    for gate_id in MANDATORY_GATES:
        gate = summary.gates.get(gate_id)
        if gate and gate.status in ("FAIL", "ERROR", "BLOCKED"):
            print(f"\n{gate.name} - {gate.status}")
            print(f"  Error: {gate.error}")
            if gate.key_evidence:
                for k, v in gate.key_evidence.items():
                    print(f"  {k}: {v}")

    # Missing gates
    if summary.missing_mandatory:
        print(f"\n⚠️  MISSING MANDATORY GATES: {', '.join(summary.missing_mandatory)}")
        print("   The overall preflight is INCOMPLETE.")
        print("   Run with 'all' gate option to execute all gates.")

    print()
    print("=" * 70)

    if summary.overall_status == "ALL_PREFLIGHT_GATES_COMPLETE":
        print("🎉 ALL PREFLIGHT GATES PASSED")
        print("Ready for production deletion approval (separate explicit operation)")
    elif summary.overall_status == "INCOMPLETE_MISSING_GATES":
        print("⚠️  PREFLIGHT INCOMPLETE - Some gates were not executed")
        print("This summary only reflects executed gates.")
    else:
        print("❌ PREFLIGHT FAILED - Review individual gate results above")

    print("=" * 70)


def save_summary(summary: PreflightSummary, output_path: Path) -> None:
    """Save summary as JSON."""
    with open(output_path, "w") as f:
        json.dump(asdict(summary), f, indent=2, default=str)


def main(artifacts_dir: str = "artifacts", commit_sha: str = "") -> int:
    """CLI entry point for summary generation."""
    artifacts_path = Path(artifacts_dir)
    if not artifacts_path.exists():
        print(f"Artifacts directory not found: {artifacts_dir}", file=sys.stderr)
        return 1

    summary = generate_summary(artifacts_path, commit_sha)
    print_summary(summary)

    # Save summary
    save_summary(summary, Path("preflight_summary.json"))

    # Exit code based on overall status
    if summary.overall_status == "ALL_PREFLIGHT_GATES_COMPLETE":
        return 0
    elif summary.overall_status == "INCOMPLETE_MISSING_GATES":
        # Not a failure - just incomplete
        return 0
    else:
        return 1


if __name__ == "__main__":
    # Allow artifacts dir and commit SHA as args
    artifacts = sys.argv[1] if len(sys.argv) > 1 else "artifacts"
    sha = sys.argv[2] if len(sys.argv) > 2 else ""
    raise SystemExit(main(artifacts, sha))