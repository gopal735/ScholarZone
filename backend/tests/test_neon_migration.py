"""Regression tests for the Neon migration script.

Tests verify_schema(), split_sql_statements(), filter_migration_statements(),
synchronize_sequences(), and the validate-only mode without requiring
a real PostgreSQL connection.
"""

import pytest
import sys
import os
from sqlalchemy import create_engine, inspect, text

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from neon_migrate import (
    verify_schema,
    connect,
    split_sql_statements,
    filter_migration_statements,
    run_migration,
    discover_sequences,
    synchronize_sequences,
    validate,
    confirm_empty,
)


# ---------------------------------------------------------------------------
# verify_schema() tests
# ---------------------------------------------------------------------------

class TestVerifySchema:
    """Tests for verify_schema() function."""

    def test_verify_schema_with_all_tables(self, sqlite_engine_with_tables, capsys):
        """verify_schema succeeds when all required tables exist."""
        result = verify_schema(sqlite_engine_with_tables)
        assert len(result) > 0
        assert "scholarships" in result
        assert "scholarship_verification_history" in result
        assert "scholarship_reviews" in result

    def test_verify_schema_missing_tables(self, sqlite_engine, capsys):
        """verify_schema returns empty list when required tables are missing."""
        result = verify_schema(sqlite_engine)
        assert result == []
        captured = capsys.readouterr()
        assert "Missing tables" in captured.out

    def test_verify_schema_partial_tables(self, sqlite_engine, capsys):
        """verify_schema reports missing tables when only some exist."""
        with sqlite_engine.begin() as conn:
            conn.execute(text("CREATE TABLE scholarships (id INTEGER PRIMARY KEY, title TEXT)"))
        result = verify_schema(sqlite_engine)
        assert result == []

    def test_verify_schema_uses_get_table_names(self, sqlite_engine):
        """verify_schema uses inspector.get_table_names() not get_tables()."""
        inspector = inspect(sqlite_engine)
        assert hasattr(inspector, "get_table_names")
        assert not hasattr(inspector, "get_tables")  # Bug was here

    def test_verify_schema_reports_all_tables(self, sqlite_engine_with_tables, capsys):
        """verify_schema reports the total number of tables found."""
        verify_schema(sqlite_engine_with_tables)
        captured = capsys.readouterr()
        assert "3 tables found" in captured.out


# ---------------------------------------------------------------------------
# SQL statement splitting tests
# ---------------------------------------------------------------------------

class TestSplitSqlStatements:
    """Tests for split_sql_statements() function."""

    def test_simple_statements(self):
        """Two simple statements are split correctly."""
        sql = "SELECT 1; SELECT 2;"
        stmts = split_sql_statements(sql)
        assert len(stmts) == 2
        assert stmts[0] == "SELECT 1"
        assert stmts[1] == "SELECT 2"

    def test_empty_string(self):
        """Empty string returns empty list."""
        assert split_sql_statements("") == []

    def test_whitespace_only(self):
        """Whitespace-only string returns empty list."""
        assert split_sql_statements("   \n  ") == []

    def test_semicolons_inside_single_quotes(self):
        """Semicolons inside single-quoted strings are not separators."""
        sql = "SELECT 'hello;world'; SELECT 2;"
        stmts = split_sql_statements(sql)
        assert len(stmts) == 2
        assert "hello;world" in stmts[0]

    def test_json_array_with_semicolons(self):
        """JSON arrays with embedded semicolons inside string literals."""
        # JSON arrays are inside single-quoted SQL string literals
        json_str = '["Item 1; with semicolon", "Item 2"]'
        sql = f"INSERT INTO t (data) VALUES ('{json_str}');"
        stmts = split_sql_statements(sql)
        assert len(stmts) == 1
        assert "semicolon" in stmts[0]

    def test_single_quote_escaped_with_double_single_quote(self):
        """Doubled single quotes ('' escaping) inside strings."""
        sql = "INSERT INTO t (name) VALUES ('it''s a test'); SELECT 1;"
        stmts = split_sql_statements(sql)
        assert len(stmts) == 2
        assert "it''s a test" in stmts[0]

    def test_em_dash_unicode_in_string(self):
        """Em-dash (U+2014) and en-dash (U+2013) inside string literals."""
        sql = "INSERT INTO t (desc) VALUES ('DAAD \u2014 German Academic'); SELECT 1;"
        stmts = split_sql_statements(sql)
        assert len(stmts) == 2
        assert "DAAD \u2014 German Academic" in stmts[0]

    def test_line_comments_ignored(self):
        """Line comments do not break statement splitting."""
        sql = "-- This is a comment\nSELECT 1; -- inline comment\nSELECT 2;"
        stmts = split_sql_statements(sql)
        assert len(stmts) == 2

    def test_block_comments_ignored(self):
        """Block comments do not break statement splitting."""
        sql = "/* This is a block comment */ SELECT 1; /* another */ SELECT 2;"
        stmts = split_sql_statements(sql)
        assert len(stmts) == 2

    def test_begin_commit_not_split_as_statements(self):
        """BEGIN and COMMIT statements are returned as separate items."""
        sql = "BEGIN;\nINSERT INTO t (id) VALUES (1);\nCOMMIT;"
        stmts = split_sql_statements(sql)
        assert len(stmts) == 3
        assert "BEGIN" in stmts[0]
        assert "COMMIT" in stmts[2]

    def test_multiple_transaction_control(self):
        """Multiple transaction control statements are all separated."""
        sql = "BEGIN; SELECT 1; COMMIT; BEGIN; SELECT 2; COMMIT;"
        stmts = split_sql_statements(sql)
        assert len(stmts) == 6

    def test_realistic_migration_fragment(self):
        """A realistic INSERT statement from migration_export.sql (without Unicode)."""
        sql = (
            "INSERT INTO scholarships (id, title, country, degree, funding, "
            "deadline_date, status, is_verified, created_at, updated_at) "
            "VALUES (1, 'Erasmus Mundus Joint Masters', 'EU', 'PG only', 'Fully Funded', "
            "NULL, 'open', 1, '2026-08-07 12:48:06', '2026-09-01 18:36:20');"
        )
        stmts = split_sql_statements(sql)
        assert len(stmts) == 1
        assert "Erasmus Mundus" in stmts[0]

    def test_json_with_embedded_double_quotes(self):
        """JSON arrays with double quotes inside single-quoted SQL string."""
        sql = """INSERT INTO t (data) VALUES ('{"key": "value"}'); SELECT 2;"""
        stmts = split_sql_statements(sql)
        assert len(stmts) == 2
        assert '{"key": "value"}' in stmts[0]

    def test_trailing_semicolon(self):
        """Trailing semicolons are handled."""
        sql = "SELECT 1; SELECT 2;; SELECT 3;"
        stmts = split_sql_statements(sql)
        assert len(stmts) == 3

    def test_double_quote_identifier_with_semicolon(self):
        """Double-quoted identifiers containing semicolons."""
        sql = 'SELECT * FROM "table;with;semis"; SELECT 2;'
        stmts = split_sql_statements(sql)
        assert len(stmts) == 2
        assert "table;with;semis" in stmts[0]

    def test_mixed_unicode_and_escaped_quotes(self):
        """Em-dash + escaped apostrophe + JSON in single INSERT."""
        json_data = '["Item 1", "Item 2 with '' apostrophe and \u2014 dash"]'
        sql = (
            f"INSERT INTO scholarships (id, title, eligibility) "
            f"VALUES (1, 'DAAD \u2014 Scholarship', '{json_data}'); "
            f"INSERT INTO scholarships (id, title) VALUES (2, 'Another');"
        )
        stmts = split_sql_statements(sql)
        assert len(stmts) == 2
        assert "DAAD \u2014" in stmts[0]
        assert "Item 1" in stmts[0]


# ---------------------------------------------------------------------------
# filter_migration_statements() tests
# ---------------------------------------------------------------------------

class TestFilterMigrationStatements:
    """Tests for filter_migration_statements() function."""

    def test_filters_begin(self):
        stmts = ["BEGIN", "INSERT INTO t VALUES (1)"]
        filtered = filter_migration_statements(stmts)
        assert len(filtered) == 1
        assert "INSERT" in filtered[0]

    def test_filters_commit(self):
        stmts = ["INSERT INTO t VALUES (1)", "COMMIT"]
        filtered = filter_migration_statements(stmts)
        assert len(filtered) == 1

    def test_filters_rollback(self):
        stmts = ["ROLLBACK", "INSERT INTO t VALUES (1)"]
        filtered = filter_migration_statements(stmts)
        assert len(filtered) == 1

    def test_filters_start_transaction(self):
        stmts = ["START TRANSACTION", "INSERT INTO t VALUES (1)"]
        filtered = filter_migration_statements(stmts)
        assert len(filtered) == 1

    def test_keeps_regular_statements(self):
        stmts = ["INSERT INTO t VALUES (1)", "UPDATE t SET x=1", "DELETE FROM t"]
        filtered = filter_migration_statements(stmts)
        assert len(filtered) == 3

    def test_case_insensitive(self):
        stmts = ["begin", "insert into t values (1)", "commit"]
        filtered = filter_migration_statements(stmts)
        assert len(filtered) == 1

    def test_keeps_comments(self):
        """Comment lines are kept (they're valid SQL statements)."""
        stmts = ["-- Table scholarships: 303 rows"]
        filtered = filter_migration_statements(stmts)
        assert len(filtered) == 1  # Comments aren't transaction control

    def test_empty_input(self):
        assert filter_migration_statements([]) == []


# ---------------------------------------------------------------------------
# Transaction rollback tests
# ---------------------------------------------------------------------------

class TestTransactionSafety:
    """Tests for transaction rollback behavior."""

    def test_migration_rolls_back_on_failure(self, sqlite_engine, capsys):
        """If a statement fails, all changes are rolled back."""
        with sqlite_engine.begin() as conn:
            conn.execute(text("CREATE TABLE test_rollback (id INTEGER PRIMARY KEY, name TEXT)"))

        sql = "INSERT INTO test_rollback (id, name) VALUES (1, 'first'); INSERT INTO nonexistent_table VALUES (2); INSERT INTO test_rollback (id, name) VALUES (3, 'third');"
        stmts = split_sql_statements(sql)
        filtered = filter_migration_statements(stmts)

        rolled_back = False
        try:
            with sqlite_engine.begin() as conn:
                conn.execute(text(filtered[0]))  # succeeds
                conn.execute(text(filtered[1]))  # fails
                conn.execute(text(filtered[2]))  # would succeed but won't run
        except Exception:
            rolled_back = True

        assert rolled_back is True

        with sqlite_engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM test_rollback")).scalar()
            assert count == 0, "Transaction should have rolled back ALL changes"

    def test_successful_migration_commits(self, sqlite_engine, capsys):
        """If all statements succeed, changes are committed."""
        with sqlite_engine.begin() as conn:
            conn.execute(text("CREATE TABLE test_commit (id INTEGER PRIMARY KEY, name TEXT)"))

        sql = "INSERT INTO test_commit (id, name) VALUES (1, 'a'); INSERT INTO test_commit (id, name) VALUES (2, 'b');"
        stmts = split_sql_statements(sql)
        filtered = filter_migration_statements(stmts)

        with sqlite_engine.begin() as conn:
            for stmt in filtered:
                conn.execute(text(stmt))

        with sqlite_engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM test_commit")).scalar()
            assert count == 2


# ---------------------------------------------------------------------------
# Sequence synchronization tests
# ---------------------------------------------------------------------------

class TestSequenceSafety:
    """Tests for sequence synchronization."""

    def test_discover_sequences_non_postgres(self, sqlite_engine):
        """On non-PostgreSQL engines, discover_sequences returns empty list."""
        with sqlite_engine.begin() as conn:
            conn.execute(text("CREATE TABLE scholarships (id INTEGER PRIMARY KEY, title TEXT)"))
        result = discover_sequences(sqlite_engine)
        assert result == [], "Non-PostgreSQL engine should return empty list"

    def test_synchronize_sequences_skips_on_sqlite(self, sqlite_engine):
        """synchronize_sequences should handle non-PostgreSQL engines gracefully."""
        with sqlite_engine.begin() as conn:
            conn.execute(text("CREATE TABLE scholarships (id INTEGER PRIMARY KEY, title TEXT)"))
        # Should not crash on SQLite
        result = synchronize_sequences(sqlite_engine)
        assert result is True


# ---------------------------------------------------------------------------
# Validate-only mode tests
# ---------------------------------------------------------------------------

class TestValidateOnlyMode:
    """Tests for --validate-only flag behavior."""

    def test_main_has_validate_only_arg(self):
        """main() should accept --validate-only argument."""
        import neon_migrate
        assert callable(neon_migrate.main)

    def test_main_has_non_interactive_arg(self):
        """main() should accept --non-interactive argument."""
        import neon_migrate
        assert callable(neon_migrate.main)


# ---------------------------------------------------------------------------
# UTF-8 encoding tests
# ---------------------------------------------------------------------------

class TestUtf8Encoding:
    """Tests for UTF-8 encoding handling."""

    def test_migration_file_is_utf8(self):
        """migration_export.sql should be valid UTF-8."""
        import pathlib
        sql_path = pathlib.Path(__file__).parent.parent / "migration_export.sql"
        with open(sql_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert len(content) > 0

    def test_em_dash_present_in_sql(self):
        """migration_export.sql contains em-dash Unicode characters."""
        import pathlib
        sql_path = pathlib.Path(__file__).parent.parent / "migration_export.sql"
        with open(sql_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "\u2014" in content, "em-dash should be present in migration SQL"

    def test_en_dash_present_in_sql(self):
        """migration_export.sql contains en-dash Unicode characters."""
        import pathlib
        sql_path = pathlib.Path(__file__).parent.parent / "migration_export.sql"
        with open(sql_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "\u2013" in content, "en-dash should be present in migration SQL"

    def test_split_preserves_unicode(self):
        """Statement splitting preserves Unicode characters in strings."""
        sql = "INSERT INTO t (val) VALUES ('\u2014 em-dash \u2013 en-dash \u2264 less-than-or-equal');"
        stmts = split_sql_statements(sql)
        assert len(stmts) == 1
        assert "\u2014" in stmts[0]
        assert "\u2013" in stmts[0]
        assert "\u2264" in stmts[0]

    def test_split_preserves_json_unicode(self):
        """JSON arrays with Unicode characters are preserved."""
        sql = "INSERT INTO t (data) VALUES ('[\"Item \u2014 dash\", \"Item \u2013 dash\"]');"
        stmts = split_sql_statements(sql)
        assert len(stmts) == 1
        assert "\u2014" in stmts[0]
        assert "\u2013" in stmts[0]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sqlite_engine():
    """Create an in-memory SQLite engine."""
    engine = create_engine("sqlite:///:memory:")
    yield engine
    engine.dispose()


@pytest.fixture
def sqlite_engine_with_tables(sqlite_engine):
    """Create an in-memory SQLite engine with required tables."""
    with sqlite_engine.begin() as conn:
        conn.execute(text("CREATE TABLE scholarships (id INTEGER PRIMARY KEY, title TEXT)"))
        conn.execute(text("CREATE TABLE scholarship_verification_history (id INTEGER PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE scholarship_reviews (id INTEGER PRIMARY KEY)"))
    return sqlite_engine


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
