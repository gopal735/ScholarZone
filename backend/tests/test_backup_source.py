"""The hostname allow-list that decides whether a backup may read at all.

The guard these tests cover replaced a substring check. That check looked for
"prod" and "production" in the URL, and the audit found why it could not work:
the real production connection string is

    postgresql://user:***@ep-broad-block-ayrx86zn-pooler.c-5.us-east-2.aws.neon.tech/neondb

It contains neither substring, so the guard admitted the exact host it existed
to exclude while refusing an innocent one. These tests therefore assert the
properties that make an allow-list an identity check rather than a naming
convention: default-deny, exact matching, and a deny-list that beats
configuration.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.backup_source import (  # noqa: E402
    ALLOW_LIST_ENV,
    KNOWN_PRODUCTION_HOSTS,
    PRODUCTION_AUTHORIZATION_ENV,
    SourceIdentity,
    SourceRejected,
    authorization_for,
    parse_source_url,
    resolve_source,
    source_kind,
    validate_source,
)

#: The production endpoint named in the audit. Deliberately carrying no "prod"
#: substring, because that is the whole point: the check that looked for one
#: admitted it.
PRODUCTION_URL = (
    "postgresql://user:sup3rsecret@ep-broad-block-ayrx86zn-pooler.c-5."
    "us-east-2.aws.neon.tech/dbname"
)


@pytest.fixture
def no_allow_list(monkeypatch):
    """The default state of a repository that has configured nothing."""
    monkeypatch.delenv(ALLOW_LIST_ENV, raising=False)


class TestParsing:
    def test_a_postgresql_url_yields_scheme_and_host_only(self, monkeypatch):
        monkeypatch.delenv(ALLOW_LIST_ENV, raising=False)
        identity = parse_source_url(PRODUCTION_URL)
        assert identity == SourceIdentity(
            scheme="postgresql",
            hostname="ep-broad-block-ayrx86zn-pooler.c-5.us-east-2.aws.neon.tech",
        )

    def test_the_postgres_scheme_is_accepted(self):
        assert parse_source_url("postgres://u:p@host/db").scheme == "postgres"

    @pytest.mark.parametrize(
        "url",
        [
            "",
            "not-a-url",
            "https://host/db",
            "mysql://u:p@host/db",
            "sqlite:///tmp/db.sqlite",
            "postgresql://user:pass@/dbname",
            "postgresql://user:pass@host:not-a-port/db",
        ],
    )
    def test_anything_that_is_not_a_usable_postgresql_url_is_refused(self, url):
        with pytest.raises(SourceRejected):
            parse_source_url(url)

    def test_the_identity_never_carries_a_credential(self):
        identity = parse_source_url(PRODUCTION_URL)
        assert "sup3rsecret" not in identity.describe()
        assert "dbname" not in identity.describe()


class TestAllowListDefaultDeny:
    def test_a_missing_allow_list_refuses_every_host(
        self, no_allow_list, monkeypatch
    ):
        monkeypatch.setenv(
            "SZ_BACKUP_SOURCE_URL", "postgresql://u:p@approved-host/db"
        )
        with pytest.raises(SourceRejected, match=ALLOW_LIST_ENV):
            resolve_source("SZ_BACKUP_SOURCE_URL")

    @pytest.mark.parametrize(
        "value",
        ["", "   ", ",", " , ,"],
    )
    def test_an_empty_allow_list_refuses_every_host(
        self, monkeypatch, value
    ):
        """An allow-list that names nothing permits nothing, not "everything"."""
        monkeypatch.setenv(ALLOW_LIST_ENV, value)
        with pytest.raises(SourceRejected, match="not set or is empty"):
            validate_source("postgresql://u:p@approved-host/db")

    def test_an_unlisted_host_is_refused(self, monkeypatch):
        monkeypatch.setenv(ALLOW_LIST_ENV, "approved-host")
        with pytest.raises(SourceRejected, match="not in"):
            validate_source("postgresql://u:p@some-other-host/db")

    def test_a_host_is_refused_when_the_list_names_a_different_one(self, monkeypatch):
        """Mismatched rather than absent: the failure that looks like a typo."""
        monkeypatch.setenv(ALLOW_LIST_ENV, "backup-a.example.com")
        with pytest.raises(SourceRejected, match="not in"):
            validate_source("postgresql://u:p@backup-b.example.com/db")


class TestAllowListMatching:
    def test_a_named_host_is_accepted(self, monkeypatch):
        monkeypatch.setenv(ALLOW_LIST_ENV, "backup-staging.example.com")
        identity = validate_source(
            "postgresql://u:p@backup-staging.example.com/scholarzone"
        )
        assert identity.hostname == "backup-staging.example.com"

    def test_matching_is_case_insensitive_on_both_sides(self, monkeypatch):
        monkeypatch.setenv(ALLOW_LIST_ENV, "Backup-Staging.Example.com")
        identity = validate_source(
            "postgresql://u:p@BACKUP-STAGING.EXAMPLE.COM/scholarzone"
        )
        assert identity.hostname == "backup-staging.example.com"

    def test_several_hosts_may_be_listed(self, monkeypatch):
        monkeypatch.setenv(
            ALLOW_LIST_ENV, "backup-a.example.com, backup-b.example.com ,"
        )
        assert validate_source(
            "postgresql://u:p@backup-b.example.com/db"
        ).hostname == "backup-b.example.com"

    def test_a_malformed_entry_is_a_configuration_error_not_a_silent_miss(
        self, monkeypatch
    ):
        """A half-pasted URL must not quietly match nothing."""
        monkeypatch.setenv(ALLOW_LIST_ENV, "postgres://backup-a.example.com/db")
        with pytest.raises(SourceRejected, match="not a bare hostname"):
            validate_source("postgresql://u:p@backup-a.example.com/db")

    def test_a_port_in_the_list_is_malformed(self, monkeypatch):
        monkeypatch.setenv(ALLOW_LIST_ENV, "backup-a.example.com:5432")
        with pytest.raises(SourceRejected, match="not a bare hostname"):
            validate_source("postgresql://u:p@backup-a.example.com:5432/db")


class TestProductionDenyList:
    def test_the_audited_production_hostname_is_refused_without_authorization(self, monkeypatch):
        """Even when the allow-list names it explicitly.

        This is the case the substring guard failed: the host carries no "prod"
        marker, so the only thing that classifies it is an explicit decision.
        The refusal is now "not authorized" rather than "never": production is
        reachable only through the authorization variable, deliberately.
        """
        host = "ep-broad-block-ayrx86zn-pooler.c-5.us-east-2.aws.neon.tech"
        monkeypatch.setenv(ALLOW_LIST_ENV, host)
        monkeypatch.delenv(PRODUCTION_AUTHORIZATION_ENV, raising=False)
        with pytest.raises(SourceRejected, match="authorization"):
            validate_source(PRODUCTION_URL)

    def test_a_listed_production_host_is_classified_production_even_without_a_prod_substring(self):
        assert source_kind(parse_source_url(PRODUCTION_URL)) == "production"

    def test_a_named_host_without_a_prod_substring_is_still_production(self):
        """The failure the old substring guard could not see: the host is
        production by policy, not by name."""
        for host in KNOWN_PRODUCTION_HOSTS:
            assert "prod" not in host

    def test_authorization_permits_the_production_host_and_records_it(self, monkeypatch):
        host = "ep-broad-block-ayrx86zn-pooler.c-5.us-east-2.aws.neon.tech"
        monkeypatch.setenv(ALLOW_LIST_ENV, host)
        monkeypatch.setenv(
            PRODUCTION_AUTHORIZATION_ENV, "owner-approval-2026-10-12"
        )
        identity = validate_source(PRODUCTION_URL)
        assert identity.hostname == host
        assert authorization_for(source_kind(identity)) == "owner-approval-2026-10-12"

    def test_a_non_production_source_ignores_the_production_authorization(self, monkeypatch):
        """Setting the authorization must not smuggle a second source in."""
        monkeypatch.setenv(ALLOW_LIST_ENV, "backup-a.example.com")
        monkeypatch.setenv(PRODUCTION_AUTHORIZATION_ENV, "approval-that-does-not-apply")
        identity = validate_source("postgresql://u:p@backup-a.example.com/db")
        assert authorization_for(source_kind(identity)) is None
        assert source_kind(identity) == "non-production"

    def test_a_missing_variable_is_a_distinct_refusal(self, monkeypatch):
        monkeypatch.delenv("SZ_BACKUP_SOURCE_URL", raising=False)
        monkeypatch.setenv(ALLOW_LIST_ENV, "backup-a.example.com")
        with pytest.raises(SourceRejected, match="not set"):
            resolve_source("SZ_BACKUP_SOURCE_URL")

    def test_the_refusal_names_no_credential(self, monkeypatch):
        monkeypatch.setenv(ALLOW_LIST_ENV, "backup-a.example.com")
        with pytest.raises(SourceRejected) as caught:
            resolve_source("SZ_BACKUP_SOURCE_URL")
        assert "sup3rsecret" not in str(caught.value)
