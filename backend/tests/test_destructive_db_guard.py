"""Unit tests for the disposable PostgreSQL test-database safety guard."""

import os
from unittest.mock import MagicMock

import pytest

from app.test_db_safety import (
    APPROVED_LOOPBACK_HOSTS,
    APPROVED_TEST_DB_NAMES,
    validate_disposable_postgres_url,
    verify_disposable_db_identity,
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
    conn.execute.return_value.fetchone.return_value = ("scholarzone_test", "10.0.0.5", "160000")
    with pytest.raises(RuntimeError):
        verify_disposable_db_identity(conn, "scholarzone_test")


def test_valid_identity_permitted(monkeypatch):
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = ("scholarzone_test", "127.0.0.1", "160000")
    verify_disposable_db_identity(conn, "scholarzone_test")


def test_production_url_with_opt_in_rejected(monkeypatch):
    with pytest.raises(RuntimeError):
        validate_disposable_postgres_url("postgresql://u:p@prod.example.com:5432/scholarzone_test", "1")
