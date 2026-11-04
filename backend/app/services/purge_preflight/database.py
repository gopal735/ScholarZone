"""
Database access layer for Purge Preflight Gates.

Provides connection management and query helpers with:
- Dependency injection for connections
- Read-only enforcement
- No import-time connections
- Proper resource cleanup
"""

import contextlib
from typing import Generator, Optional, Any
from dataclasses import dataclass

import psycopg2
from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import RealDictCursor

from .config import DatabaseConfig


@dataclass(frozen=True)
class DatabaseIdentity:
    """Verified database identity information."""
    database_name: str
    server_version: str
    current_user: str
    server_address: str
    server_port: int
    neon_project_id: Optional[str]
    neon_branch_id: Optional[str]
    neon_branch_name: Optional[str]
    is_read_only: bool
    in_transaction: bool


@dataclass(frozen=True)
class ForeignKeyInfo:
    """Foreign key metadata from information_schema."""
    constraint_name: str
    table_schema: str
    table_name: str
    column_names: list[str]  # Supports composite FKs
    referenced_table_schema: str
    referenced_table_name: str
    referenced_column_names: list[str]  # Supports composite FKs
    on_delete_action: str
    on_update_action: str
    is_cascade: bool
    is_composite: bool


@dataclass(frozen=True)
class ReferenceCount:
    """Reference count for a target ID in a referencing table."""
    table_name: str
    column_name: str
    target_id: int
    count: int


class DatabaseAccessor:
    """
    Database accessor with dependency-injected connections.

    All methods accept an existing connection - no internal connection
    creation. This ensures testability and explicit lifecycle management.
    """

    def __init__(self, config: DatabaseConfig):
        self.config = config

    @contextlib.contextmanager
    def connect_readonly(self) -> Generator[PgConnection, None, None]:
        """Create a read-only connection to production."""
        conn = psycopg2.connect(self.config.readonly_url)
        try:
            conn.autocommit = True
            conn.set_session(readonly=True)
            yield conn
        finally:
            conn.close()

    @contextlib.contextmanager
    def connect_backup(self) -> Generator[PgConnection, None, None]:
        """Create a backup-role connection to production."""
        conn = psycopg2.connect(self.config.backup_url)
        try:
            conn.autocommit = True
            # Backup role may need write access for pg_dump but we only read
            conn.set_session(readonly=True)
            yield conn
        finally:
            conn.close()

    @contextlib.contextmanager
    def connect_test(self) -> Generator[PgConnection, None, None]:
        """Create a connection to disposable test database (Gate 1 only)."""
        if not self.config.test_url:
            raise RuntimeError("TEST_DATABASE_URL not configured - required for Gate 1")
        conn = psycopg2.connect(self.config.test_url)
        try:
            conn.autocommit = False  # Explicit transaction control for Gate 1
            yield conn
        finally:
            conn.close()

    def verify_identity(self, conn: PgConnection) -> DatabaseIdentity:
        """Verify and return database identity information."""
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get basic identity
            cur.execute("""
                SELECT
                    current_database() as db_name,
                    version() as server_version,
                    current_user as current_user,
                    inet_server_addr() as server_addr,
                    inet_server_port() as server_port,
                    current_setting('neon.project_id', true) as neon_project_id,
                    current_setting('neon.branch_id', true) as neon_branch_id,
                    current_setting('neon.branch_name', true) as neon_branch_name,
                    pg_is_in_recovery() as is_replica
            """)
            row = cur.fetchone()

            # Check read-only status
            cur.execute("SHOW default_transaction_read_only")
            ro_result = cur.fetchone()
            is_read_only = ro_result["default_transaction_read_only"] == "on" if ro_result else False

            # Check transaction state
            cur.execute("SELECT pg_backend_pid()")
            cur.execute("SELECT txid_current_if_assigned()")
            txid_result = cur.fetchone()
            in_transaction = txid_result["txid_current_if_assigned"] is not None

            return DatabaseIdentity(
                database_name=row["db_name"],
                server_version=row["server_version"],
                current_user=row["current_user"],
                server_address=row["server_addr"] or "unknown",
                server_port=row["server_port"] or 5432,
                neon_project_id=row["neon_project_id"] or None,
                neon_branch_id=row["neon_branch_id"] or None,
                neon_branch_name=row["neon_branch_name"] or None,
                is_read_only=is_read_only,
                in_transaction=in_transaction,
            )

    def validate_identity(self, identity: DatabaseIdentity) -> list[str]:
        """
        Validate database identity against expected values.

        Returns:
            List of validation errors (empty if valid).
        """
        errors = []

        if identity.database_name != self.config.expected_database_name:
            errors.append(
                f"Database name mismatch: expected '{self.config.expected_database_name}', "
                f"got '{identity.database_name}'"
            )

        if identity.neon_project_id != self.config.expected_neon_project_id:
            errors.append(
                f"Neon project ID mismatch: expected '{self.config.expected_neon_project_id}', "
                f"got '{identity.neon_project_id}'"
            )

        if identity.neon_branch_id != self.config.expected_neon_branch_id:
            errors.append(
                f"Neon branch ID mismatch: expected '{self.config.expected_neon_branch_id}', "
                f"got '{identity.neon_branch_id}'"
            )

        if identity.neon_branch_name != self.config.expected_neon_branch_name:
            errors.append(
                f"Neon branch name mismatch: expected '{self.config.expected_neon_branch_name}', "
                f"got '{identity.neon_branch_name}'"
            )

        if not identity.is_read_only:
            errors.append("Connection is not read-only")

        if identity.in_transaction:
            errors.append("Connection is in a transaction (should be autocommit for read-only)")

        return errors

    def get_target_records(self, conn: PgConnection, target_ids: list[int]) -> list[dict[str, Any]]:
        """Fetch full records for target IDs."""
        if not target_ids:
            return []

        placeholders = ','.join(['%s'] * len(target_ids))
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"""
                SELECT
                    id, title, country, degree, funding, funding_type,
                    deadline_date, deadline_display, deadline_precision,
                    status, fully_funded, funding_amount, funding_currency,
                    funding_period, tuition_coverage, living_cost_coverage,
                    travel_coverage, accommodation, insurance, insurance_coverage,
                    duration, conditions, funding_details, official_source,
                    official_source_url, official_details, applicant_utility,
                    programme_verification, auto_delete_candidate_since,
                    deletion_protected, verification_status, last_verified_at,
                    verified_by, verification_notes, next_verification_due,
                    is_archived, archived_at, archived_reason,
                    created_at, updated_at
                FROM scholarships
                WHERE id IN ({placeholders})
                ORDER BY deadline_date
            """, tuple(target_ids))
            return [dict(row) for row in cur.fetchall()]

    def get_all_foreign_keys(self, conn: PgConnection) -> list[ForeignKeyInfo]:
        """Discover ALL foreign keys referencing scholarships.id.

        Handles composite foreign keys by grouping columns by constraint.
        """
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    tc.constraint_name,
                    tc.table_schema,
                    tc.table_name,
                    kcu.column_name,
                    kcu.ordinal_position,
                    ccu.table_schema as referenced_table_schema,
                    ccu.table_name as referenced_table_name,
                    ccu.column_name as referenced_column_name,
                    rc.delete_rule as on_delete_action,
                    rc.update_rule as on_update_action
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage ccu
                  ON ccu.constraint_name = tc.constraint_name
                 AND ccu.table_schema = tc.table_schema
                JOIN information_schema.referential_constraints rc
                  ON rc.constraint_name = tc.constraint_name
                 AND rc.constraint_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND ccu.table_name = 'scholarships'
                  AND ccu.column_name = 'id'
                  AND ccu.table_schema = 'public'
                ORDER BY tc.table_schema, tc.table_name, tc.constraint_name, kcu.ordinal_position
            """)

            # Group by constraint to handle composite FKs
            from collections import defaultdict
            fk_groups = defaultdict(list)
            for row in cur.fetchall():
                fk_groups[row["constraint_name"]].append(row)

            results = []
            for constraint_name, rows in fk_groups.items():
                first_row = rows[0]
                column_names = [r["column_name"] for r in rows]
                referenced_column_names = [r["referenced_column_name"] for r in rows]
                is_composite = len(column_names) > 1

                results.append(
                    ForeignKeyInfo(
                        constraint_name=constraint_name,
                        table_schema=first_row["table_schema"],
                        table_name=first_row["table_name"],
                        column_names=column_names,
                        referenced_table_schema=first_row["referenced_table_schema"],
                        referenced_table_name=first_row["referenced_table_name"],
                        referenced_column_names=referenced_column_names,
                        on_delete_action=first_row["on_delete_action"],
                        on_update_action=first_row["on_update_action"],
                        is_cascade=first_row["on_delete_action"] == "CASCADE",
                        is_composite=is_composite,
                    )
                )

            return results

    def count_references(
        self,
        conn: PgConnection,
        fk: ForeignKeyInfo,
        target_ids: list[int]
    ) -> int:
        """
        Count references to target IDs in a specific table/column(s).

        Handles both single-column and composite foreign keys.
        Uses parameterized query with safe identifier quoting.
        """
        if not target_ids:
            return 0

        # Safely quote identifiers
        quoted_table = self._quote_identifier(fk.table_name)
        quoted_columns = [self._quote_identifier(col) for col in fk.column_names]

        placeholders = ','.join(['%s'] * len(target_ids))

        if fk.is_composite:
            # For composite FK: (col1, col2, ...) IN ((id1, id2, ...), ...)
            # We need to check if ANY target_id tuple matches
            # Since we're checking references to scholarships.id (single column),
            # and the FK is composite, we need to check if any of the target_ids
            # appear in the referencing column that maps to scholarships.id
            # For simplicity, we check the first referenced column (which maps to id)
            # But actually, for a composite FK referencing scholarships(id),
            # only one column maps to id, the others map to other columns
            # We'll check the column that corresponds to the 'id' reference
            idx = fk.referenced_column_names.index('id') if 'id' in fk.referenced_column_names else 0
            quoted_column = quoted_columns[idx]
            query = f"SELECT COUNT(*) FROM {quoted_table} WHERE {quoted_column} = ANY(%s)"
        else:
            quoted_column = quoted_columns[0]
            query = f"SELECT COUNT(*) FROM {quoted_table} WHERE {quoted_column} = ANY(%s)"

        with conn.cursor() as cur:
            cur.execute(query, (tuple(target_ids),))
            return cur.fetchone()[0]

    def count_references_per_target(
        self,
        conn: PgConnection,
        fk: ForeignKeyInfo,
        target_ids: list[int]
    ) -> dict[int, int]:
        """
        Count references for EACH target ID individually.

        Returns dict mapping target_id -> count for this FK.
        """
        if not target_ids:
            return {}

        quoted_table = self._quote_identifier(fk.table_name)

        if fk.is_composite:
            idx = fk.referenced_column_names.index('id') if 'id' in fk.referenced_column_names else 0
            quoted_column = self._quote_identifier(fk.column_names[idx])
        else:
            quoted_column = self._quote_identifier(fk.column_names[0])

        results = {}
        with conn.cursor() as cur:
            for tid in target_ids:
                cur.execute(
                    f"SELECT COUNT(*) FROM {quoted_table} WHERE {quoted_column} = %s",
                    (tid,)
                )
                results[tid] = cur.fetchone()[0]
        return results

    def count_all_references(
        self,
        conn: PgConnection,
        target_ids: list[int]
    ) -> dict[str, int]:
        """Count references across all referencing tables."""
        fks = self.get_all_foreign_keys(conn)
        results = {}

        for fk in fks:
            count = self.count_references(conn, fk, target_ids)
            if fk.is_composite:
                key = f"{fk.table_name}.({','.join(fk.column_names)})"
            else:
                key = f"{fk.table_name}.{fk.column_names[0]}"
            results[key] = count

        return results

    def count_all_references_per_target(
        self,
        conn: PgConnection,
        target_ids: list[int]
    ) -> dict[int, dict[str, int]]:
        """
        Count references for EACH target ID across ALL referencing tables.

        Returns:
            dict mapping target_id -> {fk_key -> count}
        """
        fks = self.get_all_foreign_keys(conn)
        results = {tid: {} for tid in target_ids}

        for fk in fks:
            if fk.is_composite:
                key = f"{fk.table_name}.({','.join(fk.column_names)})"
            else:
                key = f"{fk.table_name}.{fk.column_names[0]}"

            per_target = self.count_references_per_target(conn, fk, target_ids)
            for tid, count in per_target.items():
                results[tid][key] = count

        return results

    def verify_target_existence(
        self,
        conn: PgConnection,
        target_ids: list[int]
    ) -> tuple[set[int], set[int]]:
        """
        Verify which target IDs exist in the database.

        Returns:
            Tuple of (found_ids, missing_ids)
        """
        if not target_ids:
            return set(), set()

        placeholders = ','.join(['%s'] * len(target_ids))
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT id FROM scholarships WHERE id IN ({placeholders})",
                (tuple(target_ids),)
            )
            found = {row[0] for row in cur.fetchall()}

        expected = set(target_ids)
        missing = expected - found
        return found, missing

    def get_scholarship_count(self, conn: PgConnection) -> int:
        """Get total scholarship count."""
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM scholarships")
            return cur.fetchone()[0]

    def execute_in_transaction(
        self,
        conn: PgConnection,
        operations: list[tuple[str, tuple]]
    ) -> list[Any]:
        """
        Execute multiple operations in a single transaction.

        Args:
            conn: Connection with autocommit=False
            operations: List of (sql, params) tuples

        Returns:
            List of results from each operation
        """
        results = []
        with conn.cursor() as cur:
            for sql, params in operations:
                cur.execute(sql, params)
                try:
                    results.append(cur.fetchall())
                except psycopg2.ProgrammingError:
                    results.append(None)
        return results

    @staticmethod
    def _quote_identifier(identifier: str) -> str:
        """Safely quote a PostgreSQL identifier."""
        # Validate identifier contains only safe characters
        if not identifier:
            raise ValueError(f"Invalid identifier: empty string")
        if not all(c.isalnum() or c in '_' for c in identifier):
            raise ValueError(f"Invalid identifier: {identifier}")
        return f'"{identifier}"'


def create_accessor(config: DatabaseConfig) -> DatabaseAccessor:
    """Factory function to create a DatabaseAccessor."""
    return DatabaseAccessor(config)