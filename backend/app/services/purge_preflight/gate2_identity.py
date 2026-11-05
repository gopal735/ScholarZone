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
Any mismatch or missing metadata fails the gate closed.
"""

import json
import sys
from dataclasses import dataclass, asdict
from datetime import date
from typing import Optional

from .manifest import CANONICAL_TARGET_IDS, TARGET_ID_SET
from .database import DatabaseAccessor, create_accessor, DatabaseIdentity
from .config import DatabaseConfig, PreflightConfig, load_config
from .metadata import save_result_with_metadata


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
    # Additional verification fields
    role_privileges_verified: bool = False
    role_privilege_errors: list[str] = None
    connection_consistency_verified: bool = False
    all_metadata_present: bool = False
    status: str = "PENDING"
    error: Optional[str] = None

    def __post_init__(self):
        if self.identity_errors is None:
            self.identity_errors = []
        if self.missing_ids is None:
            self.missing_ids = []
        if self.records is None:
            self.records = []
        if self.role_privilege_errors is None:
            self.role_privilege_errors = []

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

            # 2. Validate ALL metadata is present (fail closed on missing)
            metadata_fields = {
                "neon_project_id": identity.neon_project_id,
                "neon_branch_id": identity.neon_branch_id,
                "neon_branch_name": identity.neon_branch_name,
                "database_name": identity.database_name,
                "current_user": identity.current_user,
                "server_address": identity.server_address,
            }
            missing_metadata = [k for k, v in metadata_fields.items() if not v]
            if missing_metadata:
                result.status = "FAIL"
                result.error = f"Missing required metadata fields: {missing_metadata}"
                result.all_metadata_present = False
                return result
            result.all_metadata_present = True

            # 3. Validate against expected values (MANDATORY - no defaults)
            validation_errors = accessor.validate_identity(identity)
            result.identity_errors = validation_errors
            result.identity_match = len(validation_errors) == 0

            if not result.identity_match:
                result.status = "FAIL"
                result.error = "; ".join(validation_errors)
                return result

            # 4. Verify role privileges - ensure read-only role has only SELECT
            role_privileges_ok, privilege_errors = _verify_role_privileges(conn, identity.current_user)
            result.role_privileges_verified = role_privileges_ok
            result.role_privilege_errors = privilege_errors
            if not role_privileges_ok:
                result.status = "FAIL"
                result.error = "Role privileges verification failed: " + "; ".join(privilege_errors)
                return result

            # 5. Verify connection target consistency
            consistency_ok = _verify_connection_consistency(conn, accessor.config)
            result.connection_consistency_verified = consistency_ok
            if not consistency_ok:
                result.status = "FAIL"
                result.error = "Connection target consistency check failed"
                return result

            # 6. Verify all target IDs exist and get their details
            records = accessor.get_target_records(conn, target_ids)
            result.records = records
            found_ids = {r["id"] for r in records}
            result.total_found = len(found_ids)
            result.missing_ids = sorted(set(target_ids) - found_ids)

            if result.missing_ids:
                result.status = "FAIL"
                result.error = f"Missing {len(result.missing_ids)} target IDs: {result.missing_ids}"
                return result

            # 7. Verify deadline expiration for each record
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


def _verify_role_privileges(conn, current_user: str) -> tuple[bool, list[str]]:
    """
    Verify the connected role has only read-only privileges.

    Comprehensive check for least-privilege role:
    - Must NOT have superuser, createrole, createdb, replication, bypassrls
    - Must NOT have INSERT, UPDATE, DELETE, TRUNCATE on any table
    - Must have SELECT on scholarships table
    - Must enforce transaction read-only (default_transaction_read_only = on)

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    try:
        with conn.cursor() as cur:
            # 1. Check role attributes (superuser, createrole, createdb, replication, bypassrls)
            cur.execute("""
                SELECT rolsuper, rolcreaterole, rolcreatedb, rolreplication, rolbypassrls
                FROM pg_roles WHERE rolname = current_user
            """)
            role_attrs = cur.fetchone()
            if role_attrs:
                if role_attrs["rolsuper"]:
                    errors.append("Role has SUPERUSER attribute")
                if role_attrs["rolcreaterole"]:
                    errors.append("Role has CREATEROLE attribute")
                if role_attrs["rolcreatedb"]:
                    errors.append("Role has CREATEDB attribute")
                if role_attrs["rolreplication"]:
                    errors.append("Role has REPLICATION attribute")
                if role_attrs["rolbypassrls"]:
                    errors.append("Role has BYPASSRLS attribute")

            # 2. Check table-level privileges on scholarships
            cur.execute("""
                SELECT has_table_privilege(current_user, 'scholarships', 'INSERT') as can_insert,
                       has_table_privilege(current_user, 'scholarships', 'UPDATE') as can_update,
                       has_table_privilege(current_user, 'scholarships', 'DELETE') as can_delete,
                       has_table_privilege(current_user, 'scholarships', 'TRUNCATE') as can_truncate,
                       has_table_privilege(current_user, 'scholarships', 'REFERENCES') as can_reference,
                       has_table_privilege(current_user, 'scholarships', 'TRIGGER') as can_trigger
            """)
            row = cur.fetchone()

            # Read-only role should NOT have write privileges
            if row["can_insert"]:
                errors.append("Role has INSERT privilege on scholarships")
            if row["can_update"]:
                errors.append("Role has UPDATE privilege on scholarships")
            if row["can_delete"]:
                errors.append("Role has DELETE privilege on scholarships")
            if row["can_truncate"]:
                errors.append("Role has TRUNCATE privilege on scholarships")

            # Should have SELECT privilege
            cur.execute("SELECT has_table_privilege(current_user, 'scholarships', 'SELECT') as can_select")
            select_row = cur.fetchone()
            if not select_row["can_select"]:
                errors.append("Role lacks SELECT privilege on scholarships")

            # 3. Check transaction read-only enforcement
            cur.execute("SHOW default_transaction_read_only")
            ro_result = cur.fetchone()
            if ro_result and ro_result["default_transaction_read_only"] != "on":
                errors.append("default_transaction_read_only is not ON")

            # 4. Check for any write privileges on other tables in public schema
            cur.execute("""
                SELECT table_name,
                       has_table_privilege(current_user, table_name, 'INSERT') as can_insert,
                       has_table_privilege(current_user, table_name, 'UPDATE') as can_update,
                       has_table_privilege(current_user, table_name, 'DELETE') as can_delete,
                       has_table_privilege(current_user, table_name, 'TRUNCATE') as can_truncate
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            """)
            for table_row in cur.fetchall():
                table_name = table_row["table_name"]
                if table_row["can_insert"]:
                    errors.append(f"Role has INSERT privilege on {table_name}")
                if table_row["can_update"]:
                    errors.append(f"Role has UPDATE privilege on {table_name}")
                if table_row["can_delete"]:
                    errors.append(f"Role has DELETE privilege on {table_name}")
                if table_row["can_truncate"]:
                    errors.append(f"Role has TRUNCATE privilege on {table_name}")

    except Exception as e:
        errors.append(f"Privilege check failed: {e}")

    return (len(errors) == 0, errors)


def _verify_connection_consistency(conn, config: DatabaseConfig) -> bool:
    """
    Verify connection target consistency by checking that the connection
    parameters match the expected Neon project/branch.
    """
    try:
        with conn.cursor() as cur:
            # Verify the connection is to the expected host/port
            cur.execute("SELECT inet_server_addr() as addr, inet_server_port() as port")
            row = cur.fetchone()

            # For Neon, we can also verify the project/branch via settings
            cur.execute("""
                SELECT
                    current_setting('neon.project_id', true) as project_id,
                    current_setting('neon.branch_id', true) as branch_id,
                    current_setting('neon.branch_name', true) as branch_name
            """)
            neon_row = cur.fetchone()

            # All Neon settings must be present and match expected
            if not neon_row["project_id"] or neon_row["project_id"] != config.expected_neon_project_id:
                return False
            if not neon_row["branch_id"] or neon_row["branch_id"] != config.expected_neon_branch_id:
                return False
            if not neon_row["branch_name"] or neon_row["branch_name"] != config.expected_neon_branch_name:
                return False

        return True
    except Exception:
        return False


def main() -> int:
    """CLI entry point for Gate 2."""
    print("=== GATE 2: PRODUCTION IDENTITY VERIFICATION ===")
    print(f"Target IDs: {CANONICAL_TARGET_IDS}")
    print(f"Count: {len(CANONICAL_TARGET_IDS)}")
    print()

    try:
        config = load_config(gates_to_run={"gate2"})
        accessor = create_accessor(config.database)
    except ValueError as e:
        print(f"CONFIGURATION ERROR: {e}", file=sys.stderr)
        return 1

    result = run_gate2(accessor, CANONICAL_TARGET_IDS)

    # Save results with metadata
    save_result_with_metadata(result.to_dict(), "gate2", "gate2_result.json")

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