#!/usr/bin/env python3
"""Check overall preflight status from summary JSON with comprehensive validation."""

import json
import sys
import os
from datetime import datetime, timezone
from typing import Dict, Any, List

REQUIRED_SUMMARY_FIELDS = {
    "workflow", "run_id", "run_number", "run_attempt", "commit_sha",
    "trigger", "timestamp", "gates", "overall_status",
    "all_mandatory_passed", "missing_mandatory", "validation_errors"
}

REQUIRED_GATE_FIELDS = {"gate_id", "name", "status", "has_artifact", "error", "key_evidence", "validation_errors"}

VALID_OVERALL_STATUSES = {
    "ALL_PREFLIGHT_GATES_COMPLETE",
    "INCOMPLETE_MISSING_GATES",
    "FAILED_GATES_PRESENT"
}

VALID_GATE_STATUSES = {"PASS", "FAIL", "SKIPPED", "BLOCKED", "MANUAL_REQUIRED", "ERROR", "UNKNOWN"}

MANDATORY_GATES = ["gate1", "gate2", "gate3", "gate4", "gate5", "gate6", "gate7"]


def validate_summary_structure(summary: Dict[str, Any]) -> List[str]:
    """Validate summary JSON structure and required fields."""
    errors = []

    for field in REQUIRED_SUMMARY_FIELDS:
        if field not in summary:
            errors.append(f"Missing required summary field: '{field}'")

    if "gates" in summary:
        if not isinstance(summary["gates"], dict):
            errors.append("'gates' must be an object")
        else:
            for gate_id in MANDATORY_GATES:
                if gate_id not in summary["gates"]:
                    errors.append(f"Missing gate in summary: '{gate_id}'")
                else:
                    gate = summary["gates"][gate_id]
                    if not isinstance(gate, dict):
                        errors.append(f"Gate '{gate_id}' is not an object")
                    else:
                        for field in REQUIRED_GATE_FIELDS:
                            if field not in gate:
                                errors.append(f"Gate '{gate_id}' missing required field: '{field}'")
                        if "status" in gate and gate["status"] not in VALID_GATE_STATUSES:
                            errors.append(f"Gate '{gate_id}' has invalid status: '{gate['status']}'")

    if "overall_status" in summary and summary["overall_status"] not in VALID_OVERALL_STATUSES:
        errors.append(f"Invalid overall_status: '{summary['overall_status']}'")

    return errors


def validate_summary_freshness(summary: Dict[str, Any], max_age_hours: int = 24) -> List[str]:
    """Validate summary is not stale."""
    errors = []
    if "timestamp" not in summary:
        errors.append("Summary missing timestamp")
        return errors

    try:
        summary_time = datetime.fromisoformat(summary["timestamp"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        age_hours = (now - summary_time).total_seconds() / 3600
        if age_hours > max_age_hours:
            errors.append(f"Summary is stale: {age_hours:.1f} hours old (max {max_age_hours}h)")
    except Exception as e:
        errors.append(f"Invalid timestamp format: {e}")

    return errors


def validate_all_gates_complete(summary: Dict[str, Any]) -> List[str]:
    """Validate that all mandatory gates are present and passed."""
    errors = []

    if not summary.get("all_mandatory_passed", False):
        errors.append("Not all mandatory gates passed")

    missing = summary.get("missing_mandatory", [])
    if missing:
        errors.append(f"Missing mandatory gates: {', '.join(missing)}")

    validation_errors = summary.get("validation_errors", [])
    if validation_errors:
        errors.extend(validation_errors)

    for gate_id in MANDATORY_GATES:
        gate = summary.get("gates", {}).get(gate_id, {})
        gate_errors = gate.get("validation_errors", [])
        if gate_errors:
            errors.extend([f"Gate {gate_id}: {e}" for e in gate_errors])

        status = gate.get("status")
        if status != "PASS":
            errors.append(f"Gate {gate_id} status is '{status}', not PASS")

    return errors


def validate_single_gate_not_represented_as_full(summary: Dict[str, Any]) -> List[str]:
    """Ensure a single-gate run is not represented as a completed seven-gate run."""
    errors = []

    executed_gates = sum(1 for g in summary.get("gates", {}).values() if g.get("has_artifact", False))
    skipped_gates = sum(1 for g in summary.get("gates", {}).values() if g.get("status") == "SKIPPED")

    if summary.get("overall_status") == "ALL_PREFLIGHT_GATES_COMPLETE" and executed_gates < 7:
        errors.append(f"Overall status claims ALL_PREFLIGHT_GATES_COMPLETE but only {executed_gates}/7 gates executed")

    if executed_gates == 1 and skipped_gates == 6:
        errors.append("Single-gate diagnostic run detected - cannot represent as full preflight completion")

    return errors


def main() -> int:
    summary_path = "preflight_summary.json"

    if not os.path.exists(summary_path):
        print(f"FAILURE: Summary file not found: {summary_path}", file=sys.stderr)
        return 1

    try:
        with open(summary_path, "r") as f:
            summary = json.load(f)
    except json.JSONDecodeError as e:
        print(f"FAILURE: Invalid JSON in summary: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"FAILURE: Error reading summary: {e}", file=sys.stderr)
        return 1

    all_errors = []

    all_errors.extend(validate_summary_structure(summary))
    all_errors.extend(validate_summary_freshness(summary))
    all_errors.extend(validate_all_gates_complete(summary))
    all_errors.extend(validate_single_gate_not_represented_as_full(summary))

    print("Overall status:", summary.get("overall_status", "UNKNOWN"))
    print("All mandatory passed:", summary.get("all_mandatory_passed", False))
    print("Missing mandatory:", summary.get("missing_mandatory", []))
    print("Validation errors:", len(all_errors))

    if all_errors:
        print("\nVALIDATION FAILURES:")
        for error in all_errors:
            print(f"  - {error}")
        print("\nFAILURE: Preflight incomplete or failed")
        return 1

    if summary.get("overall_status") != "ALL_PREFLIGHT_GATES_COMPLETE":
        print("\nFAILURE: Preflight incomplete or failed")
        return 1

    print("\nSUCCESS: All gates passed validation")
    return 0


if __name__ == "__main__":
    sys.exit(main())