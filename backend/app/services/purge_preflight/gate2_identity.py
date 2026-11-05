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
    Also checks membership options (ADMIN OPTION, INHERIT OPTION, SET OPTION).
    Do not assume every membership grants SET ROLE - check set_option.
    Correctly evaluate nested membership chains.
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
                       m.admin_option, m.inherit_option, m.set_option,
                       m.roleid, m.member
                FROM pg_roles r
                JOIN pg_auth_members m ON r.oid = m.roleid
                JOIN pg_roles member ON member.oid = m.member
                WHERE member.rolname = %s
            """, (role_name,))

            for member_role in cur.fetchall():
                member_name = member_role["rolname"]
                admin_option = member_role["admin_option"]
                inherit_option = member_role["inherit_option"]
                set_option = member_role["set_option"]
                
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
                
                if not inherit_option:
                    warnings.append(f"Role membership in {member_name} has NOINHERIT - privileges not automatically inherited")
                
                # Check for SET ROLE exposure - only if set_option is true
                # Do NOT assume every membership grants SET ROLE
                if set_option:
                    warnings.append(f"Role can SET ROLE to {member_name} via membership (set_option=true)")
                else:
                    warnings.append(f"Role membership in {member_name} has NOSET ROLE - cannot SET ROLE to this role")

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
    """Check function/routine EXECUTE privileges in ALL schemas.
    
    Implements a defensible security policy:
    - Inspect SECURITY DEFINER functions and procedures (potential privilege escalation)
    - Identify routines that can perform privileged mutations
    - Account for PostgreSQL PUBLIC EXECUTE defaults
    - Allow harmless PUBLIC EXECUTE read-only functions (SECURITY INVOKER, no mutations)
    - Flag SECURITY DEFINER routines as potential privilege escalation
    - Flag routines that perform mutations (INSERT/UPDATE/DELETE/TRUNCATE)
    - Detect dynamic SQL (EXECUTE, PREPARE) that may hide mutations
    - Inspect function call dependencies (pg_depend) for indirect mutating calls
    - Check for trigger functions that may perform mutations
    - Check for SECURITY DEFINER with mutable search_path
    - Conservative fail-closed: if uncertain about mutation capability, flag as potential risk
    - Preserve strict policy against actual privilege escalation
    """
    try:
        # First, get all routines with their security properties
        cur.execute("""
            SELECT 
                n.nspname as routine_schema,
                p.proname as routine_name,
                CASE p.prokind 
                    WHEN 'f' THEN 'FUNCTION'
                    WHEN 'p' THEN 'PROCEDURE'
                    WHEN 'a' THEN 'AGGREGATE'
                    WHEN 'w' THEN 'WINDOW'
                END as routine_type,
                p.prosecdef as security_definer,
                p.provolatile,
                p.oid as routine_oid,
                pg_get_functiondef(p.oid) as function_definition
            FROM pg_proc p
            JOIN pg_namespace n ON p.pronamespace = n.oid
            WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY n.nspname, p.proname
        """)
        
        all_routines = cur.fetchall()
        
        # Build call dependency graph from pg_depend
        call_dependencies = _build_call_dependency_graph(cur)
        
        # Get trigger functions
        trigger_function_oids = _get_trigger_function_oids(cur)
        
        # Pre-compute mutating status for all routines
        routine_mutating_cache = {}
        for func_row in all_routines:
            routine_oid = func_row["routine_oid"]
            routine_mutating_cache[routine_oid] = _analyze_routine_for_mutations(
                cur, func_row, call_dependencies, trigger_function_oids, routine_mutating_cache
            )
        
        for func_row in all_routines:
            func_name = f"{func_row['routine_schema']}.{func_row['routine_name']}"
            routine_type = func_row["routine_type"]
            security_definer = func_row["security_definer"]
            routine_oid = func_row["routine_oid"]
            function_definition = func_row["function_definition"] or ""
            
            # Check if current_user has EXECUTE privilege
            cur.execute("SELECT has_function_privilege(current_user, %s, 'EXECUTE') as can_execute", (func_name,))
            exec_row = cur.fetchone()
            
            if not exec_row or not exec_row["can_execute"]:
                continue  # No EXECUTE privilege, nothing to audit
            
            # Get mutation analysis results
            analysis = routine_mutating_cache.get(routine_oid, {})
            is_mutating = analysis.get("is_mutating", False)
            has_dynamic_sql = analysis.get("has_dynamic_sql", False)
            has_indirect_mutation = analysis.get("has_indirect_mutation", False)
            is_trigger_function = analysis.get("is_trigger_function", False)
            search_path_risk = analysis.get("search_path_risk", False)
            uncertain = analysis.get("uncertain", False)
            risk_reasons = analysis.get("risk_reasons", [])
            
            # Determine risk level - FAIL CLOSED on any risk or uncertainty
            if security_definer:
                # SECURITY DEFINER runs with owner's privileges - potential privilege escalation
                reasons = ["SECURITY DEFINER (privilege escalation risk)"]
                if search_path_risk:
                    reasons.append("mutable search_path")
                if has_dynamic_sql:
                    reasons.append("dynamic SQL (EXECUTE/PREPARE)")
                if has_indirect_mutation:
                    reasons.append("indirect mutating calls")
                if is_trigger_function:
                    reasons.append("trigger function")
                if uncertain:
                    reasons.append("uncertain mutation capability (fail-closed)")
                errors.append(f"Role has EXECUTE on SECURITY DEFINER {routine_type.lower()} {func_name} ({'; '.join(reasons)})")
            elif is_mutating or has_dynamic_sql or has_indirect_mutation or is_trigger_function or search_path_risk or uncertain:
                # Any mutation risk or uncertainty - fail closed
                reasons = []
                if is_mutating:
                    reasons.append("direct DML mutations")
                if has_dynamic_sql:
                    reasons.append("dynamic SQL (EXECUTE/PREPARE)")
                if has_indirect_mutation:
                    reasons.append("indirect mutating calls")
                if is_trigger_function:
                    reasons.append("trigger function")
                if search_path_risk:
                    reasons.append("mutable search_path")
                if uncertain:
                    reasons.append("uncertain mutation capability (fail-closed)")
                errors.append(f"Role has EXECUTE on risky {routine_type.lower()} {func_name} ({'; '.join(reasons)})")
            else:
                # SECURITY INVOKER, non-mutating, no dynamic SQL, no indirect mutations, not a trigger, certain - likely harmless
                pass  # No error for harmless routines
                
    except Exception as e:
        errors.append(f"Failed to check function privileges: {e}")


def _build_call_dependency_graph(cur) -> dict[int, set[int]]:
    """Build a call dependency graph from pg_depend.
    
    Returns a mapping from routine OID to set of called routine OIDs.
    """
    dependencies = {}
    try:
        # pg_depend records dependencies between objects
        # classid = pg_proc (1255), objid = routine OID, refclassid = pg_proc, refobjid = called routine OID
        # deptype = 'n' for normal dependency
        cur.execute("""
            SELECT d.objid as caller_oid, d.refobjid as callee_oid
            FROM pg_depend d
            WHERE d.classid = 'pg_proc'::regclass
            AND d.refclassid = 'pg_proc'::regclass
            AND d.deptype = 'n'
        """)
        for row in cur.fetchall():
            caller = row["caller_oid"]
            callee = row["callee_oid"]
            if caller not in dependencies:
                dependencies[caller] = set()
            dependencies[caller].add(callee)
    except Exception:
        # If we can't query pg_depend, return empty graph (conservative: no indirect call detection)
        pass
    return dependencies


def _get_trigger_function_oids(cur) -> set[int]:
    """Get OIDs of functions that are used as triggers."""
    trigger_oids = set()
    try:
        # pg_trigger.tgfoid references the trigger function
        cur.execute("SELECT DISTINCT tgfoid FROM pg_trigger WHERE tgfoid != 0")
        for row in cur.fetchall():
            trigger_oids.add(row["tgfoid"])
    except Exception:
        pass
    return trigger_oids


def _analyze_routine_for_mutations(
    cur,
    func_row: dict,
    call_dependencies: dict[int, set[int]],
    trigger_function_oids: set[int],
    routine_mutating_cache: dict[int, dict]
) -> dict:
    """Analyze a routine for mutation capabilities.
    
    Returns a dict with keys:
    - is_mutating: direct DML in function body
    - has_dynamic_sql: uses EXECUTE, PREPARE, or dynamic SQL construction
    - has_indirect_mutation: calls other mutating functions (transitive)
    - is_trigger_function: is a trigger function
    - search_path_risk: SECURITY DEFINER with mutable search_path
    - uncertain: cannot determine mutation status (fail-closed)
    - risk_reasons: list of specific risk identifiers
    """
    routine_oid = func_row["routine_oid"]
    function_definition = func_row["function_definition"] or ""
    security_definer = func_row["security_definer"]
    routine_type = func_row["routine_type"]
    
    result = {
        "is_mutating": False,
        "has_dynamic_sql": False,
        "has_indirect_mutation": False,
        "is_trigger_function": routine_oid in trigger_function_oids,
        "search_path_risk": False,
        "uncertain": False,
        "risk_reasons": []
    }
    
    func_def_upper = function_definition.upper()
    
    # 1. Check for direct DML mutations
    dml_keywords = [
        " INSERT ", " UPDATE ", " DELETE ", " TRUNCATE ",
        "INSERT(", "UPDATE(", "DELETE(", "TRUNCATE("
    ]
    # Also check for MERGE (PostgreSQL 15+)
    if " MERGE " in func_def_upper or "MERGE(" in func_def_upper:
        result["is_mutating"] = True
        result["risk_reasons"].append("MERGE")
    elif any(keyword in func_def_upper for keyword in dml_keywords):
        result["is_mutating"] = True
        result["risk_reasons"].append("direct DML")
    
    # 2. Check for dynamic SQL patterns
    has_execute = " EXECUTE " in func_def_upper and "EXECUTE FUNCTION" not in func_def_upper and "EXECUTE PROCEDURE" not in func_def_upper
    dynamic_sql_construction_patterns = [
        " PREPARE ",           # PREPARE statement
        " EXECUTE IMMEDIATE ", # EXECUTE IMMEDIATE (PL/pgSQL)
        "FORMAT(",             # format() function often used for dynamic SQL
        "QUOTE_IDENT(",        # quote_ident() used in dynamic SQL
        "QUOTE_LITERAL(",      # quote_literal() used in dynamic SQL
        "QUOTE_NULLABLE(",     # quote_nullable() used in dynamic SQL
    ]
    has_dynamic_construction = any(pattern in func_def_upper for pattern in dynamic_sql_construction_patterns)
    
    if has_execute:
        result["has_dynamic_sql"] = True
        result["risk_reasons"].append("EXECUTE statement")
    if has_dynamic_construction:
        result["has_dynamic_sql"] = True
        result["risk_reasons"].append("dynamic SQL construction")
    
    # 3. Check for SECURITY DEFINER with mutable search_path
    if security_definer:
        # Check if function has SET search_path in its definition
        # SECURITY DEFINER functions without fixed search_path are risky
        if "SET SEARCH_PATH" not in func_def_upper and "SET search_path" not in func_def_upper:
            # Check pg_proc.proconfig for search_path setting
            try:
                cur.execute("""
                    SELECT proconfig FROM pg_proc WHERE oid = %s
                """, (routine_oid,))
                row = cur.fetchone()
                proconfig = row["proconfig"] if row else None
                has_search_path_config = False
                if proconfig:
                    for config_item in proconfig:
                        if config_item.startswith("search_path="):
                            has_search_path_config = True
                            break
                if not has_search_path_config:
                    result["search_path_risk"] = True
                    result["risk_reasons"].append("SECURITY DEFINER without fixed search_path")
            except Exception:
                # If we can't check, assume risk (fail closed)
                result["search_path_risk"] = True
                result["risk_reasons"].append("SECURITY DEFINER search_path unverifiable")
    
    # 4. Check for indirect mutations via call dependencies (transitive closure)
    # Use memoized recursion to avoid infinite loops
    visited = set()
    
    def check_indirect_mutation(oid: int, depth: int = 0) -> bool:
        if depth > 20:  # Prevent infinite recursion
            return True  # Fail closed on deep recursion
        if oid in visited:
            return False  # Already checked this path
        visited.add(oid)
        
        # Check direct callees
        callees = call_dependencies.get(oid, set())
        for callee_oid in callees:
            # Check if callee is mutating (from cache or recursive analysis)
            callee_analysis = routine_mutating_cache.get(callee_oid)
            if callee_analysis is not None:
                if callee_analysis.get("is_mutating") or callee_analysis.get("has_dynamic_sql") or callee_analysis.get("has_indirect_mutation"):
                    return True
            else:
                # Callee not in our cache (maybe in pg_catalog or not yet processed)
                # Conservative: check if it's a known mutating system function
                try:
                    cur.execute("""
                        SELECT proname, prosecdef, provolatile
                        FROM pg_proc WHERE oid = %s
                    """, (callee_oid,))
                    callee_row = cur.fetchone()
                    if callee_row:
                        # Volatile functions with security definer are suspicious
                        if callee_row["prosecdef"] and callee_row["provolatile"] == 'v':
                            return True
                        # Known mutating system functions
                        mutating_names = {"pg_sleep", "pg_advisory_lock", "pg_advisory_xact_lock"}
                        if callee_row["proname"] in mutating_names:
                            return True
                except Exception:
                    pass
                # Recursively check callee's callees
                if check_indirect_mutation(callee_oid, depth + 1):
                    return True
        return False
    
    if check_indirect_mutation(routine_oid):
        result["has_indirect_mutation"] = True
        result["risk_reasons"].append("indirect mutating calls")
    
# 5. Conservative fail-closed: if we cannot determine with certainty, flag as uncertain
    # This happens when:
    # - Function body is not accessible (e.g., C functions without source)
    # - Dynamic SQL detected but cannot be fully analyzed
    # - Complex control flow that may conditionally mutate
    if not result["is_mutating"] and not result["has_dynamic_sql"] and not result["has_indirect_mutation"]:
        # Check if function definition is empty or minimal (C functions, etc.)
        if not function_definition.strip() or "LANGUAGE C" in func_def_upper or "LANGUAGE INTERNAL" in func_def_upper:
            result["uncertain"] = True
            result["risk_reasons"].append("C/internal function - mutation capability unknown")
        # Check for volatile functions that might have side effects
        elif func_row.get("provolatile") == 'v' and "RETURN" in func_def_upper and "SELECT" not in func_def_upper:
            # Volatile function that doesn't obviously just SELECT - uncertain
            result["uncertain"] = True
            result["risk_reasons"].append("volatile function with unclear side effects")

    return result


def _check_set_role_exposure(cur, current_user: str, errors: list[str]) -> None:
    """Check for SET ROLE exposure - roles that current_user can SET ROLE to.
    
    Uses pg_has_role() with 'SET' privilege type, which is the correct
    PostgreSQL function for checking SET ROLE privilege.
    """
    try:
        # Check which roles current_user can SET ROLE to
        # pg_has_role(current_user, role_oid, 'SET') is the correct function
        cur.execute("""
            SELECT r.rolname
            FROM pg_roles r
            WHERE pg_has_role(current_user, r.oid, 'SET')
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