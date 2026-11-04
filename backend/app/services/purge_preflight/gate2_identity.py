"""
Gate 2: Production Identity Verification

Connects using READ-ONLY role. Verifies:
- Exact Neon project ID
- Exact Neon branch ID
- Exact Neon branch name
- Exact database name
- Current database identity
- Current database user
- Server identity
- Read-only transaction state
- Role privileges
- Connection target consistency

All expected values are MANDATORY - no silent defaults.
Any mismatch fails the gate.
"""

import json
import sys
from dataclasses import dataclass, asdict
from typing import Optional

from .manifest import CANONICAL_TARGET_IDS, TARGET_ID_SET
from .database import DatabaseAccessor, create_accessor, DatabaseIdentity
from .config import DatabaseConfig, PreflightConfig, load_config


@dataclass
class Gate2Result:
    """Gate 2 execution result."""
    test_name: str = "gate2_identity"
    neon_project_id: Optional[str] = None
    neon_branch_id: Optional[str] = None
    neon_branch_name: Optional[str] = None
    database_name: Optional[str] = None
    current_user: Optional[str] = None
    server_address: Optional[str] = None
    server_port: int = 0
    server_version: Optional[str] = None
    is_read_only: bool = False
    in_transaction: bool = False
    identity_match: bool = False
    identity_errors: list[str] = None
    total_found: int = 0
    missing_ids: list[int] = None
    records: list[dict] = None
    status: str = "PENDING"
    error: Optional[str] = None

    def __post_init__(self):
        if self.identity_errors is None:
            self.identity_errors = []
        if self.missing_ids is None:
            self.missing_ids = []
        if self.records is None:
            self.records = []

    def to_dict(self) -> dict:
        return asdict(self)


def run_gate2(accessor: DatabaseAccessor, target_ids: list[int]) -> Gate2Result:
    """
    Execute Gate 2: Production Identity Verification.

    Args:
        accessor: DatabaseAccessor with readonly production connection
        target_ids: List of target IDs to verify

    Returns:
        Gate2Result with identity verification and record details
    """
    from datetime import date
    result = Gate2Result()

    try:
        with accessor.connect_readonly() as conn:
            # 1. Verify database identity
            identity = accessor.verify_identity(conn)
            result.neon_project_id = identity.neon_project_id
            result.neon_branch_id = identity.neon_branch_id
            result.neon_branch_name = identity.neon_branch_name
            result.database_name = identity.database_name
            result.current_user = identity.current_user
            result.server_address = identity.server_address
            result.server_port = identity.server_port
            result.server_version = identity.server_version[:80] + "..." if len(identity.server_version) > 80 else identity.server_version
            result.is_read_only = identity.is_read_only
            result.in_transaction = identity.in_transaction

            # 2. Validate against expected values (MANDATORY - no defaults)
            validation_errors = accessor.validate_identity(identity)
            result.identity_errors = validation_errors
            result.identity_match = len(validation_errors) == 0

            if not result.identity_match:
                result.status = "FAIL"
                result.error = "; ".join(validation_errors)
                return result

            # 3. Verify all target IDs exist and get their details
            records = accessor.get_target_records(conn, target_ids)
            result.records = records
            found_ids = {r["id"] for r in records}
            result.total_found = len(found_ids)
            result.missing_ids = sorted(set(target_ids) - found_ids)

            if result.missing_ids:
                result.status = "FAIL"
                result.error = f"Missing {len(result.missing_ids)} target IDs: {result.missing_ids}"
                return result

            # 4. Verify deadline expiration for each record
            expired_count = 0
            future_deadline_ids = []
            for record in records:
                deadline = record.get("deadline_date")
                if deadline:
                    if isinstance(deadline, str):
                        deadline = date.fromisoformat(deadline)
                    if deadline < date.today():
                        expired_count += 1
                    else:
                        future_deadline_ids.append(record["id"])

            if future_deadline_ids:
                result.status = "FAIL"
                result.error = f"Records with future deadlines (not expired): {future_deadline_ids}"
                return result

            result.status = "PASS"
            return result

    except Exception as e:
        result.status = "ERROR"
        result.error = str(e)
        return result


def main() -> int:
    """CLI entry point for Gate 2."""
    print("=== GATE 2: PRODUCTION IDENTITY VERIFICATION ===")
    print(f"Target IDs: {CANONICAL_TARGET_IDS}")
    print(f"Count: {len(CANONICAL_TARGET_IDS)}")
    print()

    try:
        config = load_config()
        accessor = create_accessor(config.database)
    except ValueError as e:
        print(f"CONFIGURATION ERROR: {e}", file=sys.stderr)
        return 1

    result = run_gate2(accessor, CANONICAL_TARGET_IDS)

    # Save results
    with open("gate2_result.json", "w") as f:
        json.dump(result.to_dict(), f, indent=2, default=str)

    print("\n=== GATE 2 RESULT ===")
    print(json.dumps(result.to_dict(), indent=2, default=str))

    if result.status == "PASS":
        print("\n✅ GATE 2 PASSED: All identity checks passed, all 34 target IDs verified")
        return 0
    else:
        print(f"\n❌ GATE 2 {result.status}: {result.error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())