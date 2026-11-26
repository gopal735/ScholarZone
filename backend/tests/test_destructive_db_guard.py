"""Unit tests for the disposable PostgreSQL test-database safety guard."""

import os
from unittest.mock import MagicMock

import pytest

from app.test_db_safety import (
    APPROVED_LOOPBACK_HOSTS,
    APPROVED_TEST_DB_NAMES,
    validate_disposable_postgres_url,
    verify_disposable_db_identity,
    verify_disposable_db_marker,
    verify_expected_pg_version,
)

GOOD_URL = "postgresql://test:test@127.0.0.1:5440/scholarzone_test?sslmode=disable"


def _set_allow(monkeypatch, val):
    if val is None:
        monkeypatch.delenv("SCHOLARZONE_ALLOW_DESTRUCTIVE_TEST_DB", raising=False)
    else:
        monkeypatch.setenv("SCHOLARZONE_ALLOW_DESTRUCTIVE_TEST_DB", val)


def test_missing_opt_in_flag_rejected(monkeypatch):
    _set_allow(monkeypatch, None)
    with pytest.raises(RuntimeError):
        validate_disposable_postgres_url(GOOD_URL, None)


def test_opt_in_zero_rejected(monkeypatch):
    _set_allow(monkeypatch, "0")
    with pytest.raises(RuntimeError):
        validate_disposable_postgres_url(GOOD_URL, "0")


def test_opt_in_unexpected_rejected(monkeypatch):
    with pytest.raises(RuntimeError):
        validate_disposable_postgres_url(GOOD_URL, "yes")


def test_missing_url_rejected(monkeypatch):
    with pytest.raises(RuntimeError):
        validate_disposable_postgres_url("", "1")


def test_empty_url_rejected(monkeypatch):
    with pytest.raises(RuntimeError):
        validate_disposable_postgres_url("", "1")


def test_malformed_url_rejected(monkeypatch):
    with pytest.raises(RuntimeError):
        validate_disposable_postgres_url("not-a-url", "1")


def test_sqlite_url_rejected(monkeypatch):
    with pytest.raises(RuntimeError):
        validate_disposable_postgres_url("sqlite:///foo.db", "1")


def test_remote_host_rejected(monkeypatch):
    with pytest.raises(RuntimeError):
        validate_disposable_postgres_url("postgresql://u:p@db.example.com:5432/scholarzone_test", "1")


def test_production_like_host_rejected(monkeypatch):
    with pytest.raises(RuntimeError):
        validate_disposable_postgres_url("postgresql://u:p@prod.db.internal:5432/scholarzone_test", "1")


def test_localhost_attacker_rejected(monkeypatch):
    with pytest.raises(RuntimeError):
        validate_disposable_postgres_url("postgresql://u:p@localhost.attacker.example:5432/scholarzone_test", "1")


def test_localhost_permitted_parsing(monkeypatch):
    validate_disposable_postgres_url("postgresql://u:p@localhost:5432/scholarzone_test", "1")


def test_127_permitted_parsing(monkeypatch):
    validate_disposable_postgres_url("postgresql://u:p@127.0.0.1:5432/scholarzone_test", "1")


def test_ipv6_permitted_parsing(monkeypatch):
    validate_disposable_postgres_url("postgresql://u:p@[::1]:5432/scholarzone_test", "1")


def test_wrong_db_name_rejected(monkeypatch):
    with pytest.raises(RuntimeError):
        validate_disposable_postgres_url("postgresql://u:p@127.0.0.1:5432/production", "1")


def test_wrong_db_name_postgres_rejected(monkeypatch):
    with pytest.raises(RuntimeError):
        validate_disposable_postgres_url("postgresql://u:p@127.0.0.1:5432/postgres", "1")


def test_unexpected_current_database_rejected(monkeypatch):
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = ("production", "127.0.0.1", "160000")
    with pytest.raises(RuntimeError):
        verify_disposable_db_identity(conn, "scholarzone_test")


def test_unexpected_server_address_rejected(monkeypatch):
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = ("scholarzone_test", "8.8.8.8", "160000")
    with pytest.raises(RuntimeError):
        verify_disposable_db_identity(conn, "scholarzone_test")


def test_valid_identity_permitted(monkeypatch):
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = ("scholarzone_test", "127.0.0.1", "160000")
    verify_disposable_db_identity(conn, "scholarzone_test")


def test_production_url_with_opt_in_rejected(monkeypatch):
    with pytest.raises(RuntimeError):
        validate_disposable_postgres_url("postgresql://u:p@prod.example.com:5432/scholarzone_test", "1")


def test_marker_missing_rejected():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    with pytest.raises(RuntimeError):
        verify_disposable_db_marker(conn, "run-1", "digest-1")


def test_marker_wrong_run_id_rejected():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = ("other-run", "digest-1")
    with pytest.raises(RuntimeError):
        verify_disposable_db_marker(conn, "run-1", "digest-1")


def test_marker_wrong_digest_rejected():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = ("run-1", "wrong-digest")
    with pytest.raises(RuntimeError):
        verify_disposable_db_marker(conn, "run-1", "digest-1")


def test_marker_missing_config_rejected():
    conn = MagicMock()
    with pytest.raises(RuntimeError):
        verify_disposable_db_marker(conn, None, "digest-1")
    with pytest.raises(RuntimeError):
        verify_disposable_db_marker(conn, "run-1", None)


def test_marker_valid_accepted():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = ("run-1", "digest-1")
    verify_disposable_db_marker(conn, "run-1", "digest-1")


def test_pg_version_mismatch_rejected():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = ("170000",)
    with pytest.raises(RuntimeError):
        verify_expected_pg_version(conn, "160000")


def test_pg_version_match_accepted():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = ("160000",)
    verify_expected_pg_version(conn, "160000")


def test_pg_version_none_skips():
    conn = MagicMock()
    verify_expected_pg_version(conn, None)
