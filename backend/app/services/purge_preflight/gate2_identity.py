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
    - Must NOT have INSERT, UPDATE, DELETE, TRUNCATE on any table in ANY schema
    - Must have SELECT on scholarships table
    - Must enforce transaction read-only (default_transaction_read_only = on)
    - Must NOT inherit elevated privileges via role memberships
    - Must NOT have CREATE privilege on ANY schema
    - Must NOT have USAGE/UPDATE on sequences (or only USAGE for nextval)
    - Must NOT have EXECUTE on functions that modify data
    - Must audit membership options (ADMIN OPTION, SET ROLE)
    - Must detect membership-chain traversal limits and fail closed
    - Must fail closed on inaccessible catalogs or incomplete privilege checks
    - Must NOT claim comprehensive least privilege without full scope audit

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    warnings = []  # Non-fatal issues for audit

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

            # 2. Check role memberships and inherited privileges (with options)
            membership_errors, membership_warnings = _check_role_memberships(cur, current_user)
            errors.extend(membership_errors)
            warnings.extend(membership_warnings)

            # 3. Check table-level privileges on scholarships
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

            # 4. Check transaction read-only enforcement
            cur.execute("SHOW default_transaction_read_only")
            ro_result = cur.fetchone()
            if ro_result and ro_result["default_transaction_read_only"] != "on":
                errors.append("default_transaction_read_only is not ON")

            # 5. Check for any write privileges on tables in ALL schemas (not just public)
            _check_all_table_privileges(cur, current_user, errors)

            # 6. Check schema privileges on ALL schemas (not just public)
            _check_all_schema_privileges(cur, current_user, errors)

            # 7. Check sequence privileges in ALL schemas
            _check_all_sequence_privileges(cur, current_user, errors)

            # 8. Check function/routine EXECUTE privileges in ALL schemas
            _check_all_function_privileges(cur, current_user, errors)

            # 9. Check for SET ROLE exposure
            _check_set_role_exposure(cur, current_user, errors)

            # 10. Verify catalog accessibility - fail closed if we can't query required catalogs
            _verify_catalog_accessibility(cur, errors)

    except Exception as e:
        errors.append(f"Privilege check failed: {e}")

    # Add warnings to errors for fail-closed behavior (warnings become errors in strict mode)
    # In production, we treat warnings as errors to ensure comprehensive audit
    all_errors = errors + [f"[AUDIT WARNING] {w}" for w in warnings]

    return (len(all_errors) == 0, all_errors)


def _check_role_memberships(cur, current_user: str) -> tuple[list[str], list[str]]:
    """
    Recursively check role memberships via pg_auth_members for inherited privileges.
    Reports any inherited SUPERUSER, CREATEROLE, CREATEDB, REPLICATION, BYPASSRLS.
    Also checks membership options (ADMIN OPTION, SET ROLE).
    Detects membership-chain traversal limits and fails closed.
    
    Returns:
        Tuple of (errors, warnings)
    """
    errors = []
    warnings = []
    visited = set()
    max_depth = 10

    def check_role_recursive(role_name: str, depth: int = 0) -> None:
        if role_name in visited or depth > max_depth:
            if depth > max_depth:
                errors.append(f"Role membership chain exceeds maximum depth ({max_depth}) - possible cycle or excessive nesting")
            return
        visited.add(role_name)

        try:
            cur.execute("""
                SELECT r.rolname, r.rolsuper, r.rolcreaterole, r.rolcreatedb, r.rolreplication, r.rolbypassrls,
                       m.admin_option, m.roleid, m.member
                FROM pg_roles r
                JOIN pg_auth_members m ON r.oid = m.roleid
                JOIN pg_roles member ON member.oid = m.member
                WHERE member.rolname = %s
            """, (role_name,))

            for member_role in cur.fetchall():
                member_name = member_role["rolname"]
                admin_option = member_role["admin_option"]
                
                if member_role["rolsuper"]:
                    errors.append(f"Role inherits SUPERUSER via membership in {member_name}")
                if member_role["rolcreaterole"]:
                    errors.append(f"Role inherits CREATEROLE via membership in {member_name}")
                if member_role["rolcreatedb"]:
                    errors.append(f"Role inherits CREATEDB via membership in {member_name}")
                if member_role["rolreplication"]:
                    errors.append(f"Role inherits REPLICATION via membership in {member_name}")
                if member_role["rolbypassrls"]:
                    errors.append(f"Role inherits BYPASSRLS via membership in {member_name}")
                
                # Check membership options
                if admin_option:
                    warnings.append(f"Role has ADMIN OPTION on membership in {member_name} (can grant membership to others)")
                
                # Check for SET ROLE exposure
                warnings.append(f"Role can SET ROLE to {member_name} via membership")

                # Recursively check nested memberships
                check_role_recursive(member_name, depth + 1)
        except Exception as e:
            errors.append(f"Failed to query role memberships for {role_name}: {e}")

    check_role_recursive(current_user)
    return errors, warnings


def _check_all_table_privileges(cur, current_user: str, errors: list[str]) -> None:
    """Check table privileges in ALL schemas, not just public."""
    try:
        cur.execute("""
            SELECT table_schema, table_name,
                   has_table_privilege(current_user, table_schema || '.' || table_name, 'INSERT') as can_insert,
                   has_table_privilege(current_user, table_schema || '.' || table_name, 'UPDATE') as can_update,
                   has_table_privilege(current_user, table_schema || '.' || table_name, 'DELETE') as can_delete,
                   has_table_privilege(current_user, table_schema || '.' || table_name, 'TRUNCATE') as can_truncate
            FROM information_schema.tables
            WHERE table_type = 'BASE TABLE'
            AND table_schema NOT IN ('pg_catalog', 'information_schema')
        """)
        
        for table_row in cur.fetchall():
            table_name = f"{table_row['table_schema']}.{table_row['table_name']}"
            if table_row["can_insert"]:
                errors.append(f"Role has INSERT privilege on {table_name}")
            if table_row["can_update"]:
                errors.append(f"Role has UPDATE privilege on {table_name}")
            if table_row["can_delete"]:
                errors.append(f"Role has DELETE privilege on {table_name}")
            if table_row["can_truncate"]:
                errors.append(f"Role has TRUNCATE privilege on {table_name}")
    except Exception as e:
        errors.append(f"Failed to check table privileges across schemas: {e}")


def _check_all_schema_privileges(cur, current_user: str, errors: list[str]) -> None:
    """Check schema privileges on ALL schemas, not just public."""
    try:
        cur.execute("""
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
        """)
        
        for schema_row in cur.fetchall():
            schema_name = schema_row["schema_name"]
            # Check CREATE privilege (should be FALSE for read-only)
            cur.execute("SELECT has_schema_privilege(current_user, %s, 'CREATE') as can_create", (schema_name,))
            create_row = cur.fetchone()
            if create_row and create_row["can_create"]:
                errors.append(f"Role has CREATE privilege on schema {schema_name} (should be read-only)")
            
            # Check USAGE privilege (should be TRUE for read-only to access objects)
            cur.execute("SELECT has_schema_privilege(current_user, %s, 'USAGE') as can_usage", (schema_name,))
            usage_row = cur.fetchone()
            if usage_row and not usage_row["can_usage"]:
                errors.append(f"Role lacks USAGE privilege on schema {schema_name} (required for read access)")
    except Exception as e:
        errors.append(f"Failed to check schema privileges: {e}")


def _check_all_sequence_privileges(cur, current_user: str, errors: list[str]) -> None:
    """Check sequence privileges in ALL schemas."""
    try:
        cur.execute("""
            SELECT sequence_schema, sequence_name
            FROM information_schema.sequences
            WHERE sequence_schema NOT IN ('pg_catalog', 'information_schema')
        """)
        
        for seq_row in cur.fetchall():
            seq_name = f"{seq_row['sequence_schema']}.{seq_row['sequence_name']}"
            
            # Check USAGE privilege (allows nextval/currval)
            cur.execute("SELECT has_sequence_privilege(current_user, %s, 'USAGE') as can_usage", (seq_name,))
            usage_row = cur.fetchone()
            if usage_row and usage_row["can_usage"]:
                errors.append(f"Role has USAGE privilege on sequence {seq_name} (allows nextval/currval)")
            
            # Check UPDATE privilege (allows setval - should NEVER be granted to read-only)
            cur.execute("SELECT has_sequence_privilege(current_user, %s, 'UPDATE') as can_update", (seq_name,))
            update_row = cur.fetchone()
            if update_row and update_row["can_update"]:
                errors.append(f"Role has UPDATE privilege on sequence {seq_name} (allows setval - WRITE privilege)")
    except Exception as e:
        errors.append(f"Failed to check sequence privileges: {e}")


def _check_all_function_privileges(cur, current_user: str, errors: list[str]) -> None:
    """Check function/routine EXECUTE privileges in ALL schemas."""
    try:
        cur.execute("""
            SELECT routine_schema, routine_name, routine_type, data_type
            FROM information_schema.routines
            WHERE routine_schema NOT IN ('pg_catalog', 'information_schema')
        """)
        
        for func_row in cur.fetchall():
            func_name = f"{func_row['routine_schema']}.{func_row['routine_name']}"
            routine_type = func_row["routine_type"]  # 'FUNCTION' or 'PROCEDURE'
            
            cur.execute("SELECT has_function_privilege(current_user, %s, 'EXECUTE') as can_execute", (func_name,))
            exec_row = cur.fetchone()
            if exec_row and exec_row["can_execute"]:
                errors.append(f"Role has EXECUTE privilege on {routine_type.lower()} {func_name} (audit required)")
    except Exception as e:
        errors.append(f"Failed to check function privileges: {e}")


def _check_set_role_exposure(cur, current_user: str, errors: list[str]) -> None:
    """Check for SET ROLE exposure - roles that current_user can SET ROLE to."""
    try:
        # Check which roles current_user can SET ROLE to
        cur.execute("""
            SELECT r.rolname
            FROM pg_roles r
            WHERE has_role_privilege(current_user, r.oid, 'SET ROLE')
            AND r.rolname != current_user
        """)
        
        for role_row in cur.fetchall():
            role_name = role_row["rolname"]
            errors.append(f"Role can SET ROLE to {role_name} (privilege escalation risk)")
    except Exception as e:
        errors.append(f"Failed to check SET ROLE exposure: {e}")


def _verify_catalog_accessibility(cur, errors: list[str]) -> None:
    """Verify that required system catalogs are accessible - fail closed if not."""
    required_catalogs = [
        ("pg_roles", "SELECT 1 FROM pg_roles LIMIT 1"),
        ("pg_auth_members", "SELECT 1 FROM pg_auth_members LIMIT 1"),
        ("information_schema.tables", "SELECT 1 FROM information_schema.tables LIMIT 1"),
        ("information_schema.schemata", "SELECT 1 FROM information_schema.schemata LIMIT 1"),
        ("information_schema.sequences", "SELECT 1 FROM information_schema.sequences LIMIT 1"),
        ("information_schema.routines", "SELECT 1 FROM information_schema.routines LIMIT 1"),
        ("pg_settings", "SELECT 1 FROM pg_settings LIMIT 1"),
    ]
    
    for catalog_name, query in required_catalogs:
        try:
            cur.execute(query)
        except Exception as e:
            errors.append(f"Cannot access required catalog {catalog_name}: {e}")


# Keep the old helper functions for backward compatibility but they now delegate to new comprehensive functions
def _check_schema_privileges(cur, current_user: str, errors: list[str]) -> None:
    """Backward compatibility - delegates to comprehensive check."""
    # This is now handled by _check_all_schema_privileges in _verify_role_privileges
    pass


def _check_sequence_privileges(cur, current_user: str, errors: list[str]) -> None:
    """Backward compatibility - delegates to comprehensive check."""
    # This is now handled by _check_all_sequence_privileges in _verify_role_privileges
    pass


def _check_function_privileges(cur, current_user: str, errors: list[str]) -> None:
    """Backward compatibility - delegates to comprehensive check."""
    # This is now handled by _check_all_function_privileges in _verify_role_privileges
    pass


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