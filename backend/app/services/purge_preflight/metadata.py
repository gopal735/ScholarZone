"""
Metadata utilities for gate results.
"""

import os
import json
from datetime import datetime, timezone
from typing import Dict, Any


SCHEMA_VERSION = "1.0.0"


def get_github_metadata() -> Dict[str, Any]:
    """Extract GitHub Actions metadata from environment."""
    return {
        "commit_sha": os.getenv("GITHUB_SHA", ""),
        "run_id": os.getenv("GITHUB_RUN_ID", ""),
        "run_attempt": int(os.getenv("GITHUB_RUN_ATTEMPT", "1")),
        "run_number": int(os.getenv("GITHUB_RUN_NUMBER", "0")),
        "workflow": os.getenv("GITHUB_WORKFLOW", "unknown"),
        "job": os.getenv("GITHUB_JOB", "unknown"),
    }


def add_metadata_to_result(result_dict: Dict[str, Any], gate_id: str) -> Dict[str, Any]:
    """Add required metadata fields to a gate result dictionary."""
    meta = get_github_metadata()
    result_dict.update({
        "gate_id": gate_id,
        "schema_version": SCHEMA_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "commit_sha": meta["commit_sha"],
        "run_id": meta["run_id"],
        "run_attempt": meta["run_attempt"],
        "run_number": meta["run_number"],
        "workflow": meta["workflow"],
    })
    return result_dict


def save_result_with_metadata(result_dict: Dict[str, Any], gate_id: str, output_path: str) -> None:
    """Save gate result with metadata to JSON file."""
    result_with_meta = add_metadata_to_result(result_dict, gate_id)
    with open(output_path, "w") as f:
        json.dump(result_with_meta, f, indent=2, default=str)