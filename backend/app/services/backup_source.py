"""Hostname allow-list validation for a backup source.

The previous guard looked for the substrings "prod"/"production" in the URL. The
audit showed why that does not work: a real Neon production connection string is

    postgresql://user:***@ep-broad-block-ayrx86zn-pooler.c-5.us-east-2.aws.neon.tech/neondb

It contains neither substring, so the guard admitted the database it was written
to keep out, while refusing a host that merely happened to be called
`prod-1.example.com`. A naming convention is not an identity check.

This module replaces it with the only thing that can be: **an exact allow-list,
default-deny.** A host is permitted only if it is named in the configuration.
Everything else is refused, including hosts nobody thought to name.

Design consequences, each of them deliberate:

* **Default-deny.** An empty, missing, or unparseable allow-list refuses. The
  alternative - refusing only what is known-bad - is the previous version.
* **The known production host is hard-coded as a denial**, not as a note. It is
  named here rather than expected to appear in the allow-list, because a
  production endpoint should never be addable to one by accident.
* **Credentials are never returned, only a redacted identity.** A manifest is
  pasted into tickets; the identity is the dialect and the host, nothing else.
  `parse_source_url` is the only place a full URL exists, and its callers pass
  it straight to `pg_dump` and never to a log or an artefact.
* **Parsing is strict.** A URL without a host, with an unparseable one, or with
  a scheme that is not PostgreSQL is a refusal. A backup of SQLite is refused
  for the same reason `verify_recovery_path.py` refuses one: it would not be
  evidence about a PostgreSQL restore.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from urllib.parse import urlsplit

#: Hostnames that are refused *as a silent non-production source*: they name
#: production, so a backup that reaches one must be explicitly authorised as a
#: production backup. This is not a fallback for a missing allow-list - a belt
#: over the braces: even if this host were added to an allow-list by mistake,
#: the backup still refuses until the authorization variable below is set.
KNOWN_PRODUCTION_HOSTS = frozenset({
    "ep-broad-block-ayrx86zn-pooler.c-5.us-east-2.aws.neon.tech",
})

#: The variable an operator sets to record that a *production* backup is
#: authorised, with a reference they can audit (who approved it, when). Its
#: absence is the refusal: a production backup that nobody claimed
#: responsibility for is exactly the unattended production access this module
#: exists to prevent. Its value is written to the manifest as the
#: authorization record - deliberately not the operator's secret itself.
PRODUCTION_AUTHORIZATION_ENV = "SZ_BACKUP_PRODUCTION_AUTHORIZATION"

#: Only PostgreSQL is a valid backup source. `postgres` is accepted as well as
#: `postgresql` because libpq accepts both.
POSTGRESQL_SCHEMES = frozenset({"postgres", "postgresql"})

#: The environment variable naming the hosts a backup may read and a restore may
#: write. Defined here so the script, the restore script, the workflow and the
#: tests all name the same variable rather than each holding their own spelling.
#: A repository *variable*, not a secret: it is a list of hostnames, which is
#: configuration an operator sets in the repository settings.
ALLOW_LIST_ENV = "SZ_BACKUP_ALLOWED_HOSTS"

#: The variable a repository owner sets to name the non-production hosts a backup
#: may read. Documented in `docs/DATABASE_BACKUP.md`. Unset means nothing is
#: permitted, which is the intended default: a backup that has not been told
#: which host it may read must not read any of them.
ALLOW_LIST_ENV = "SZ_BACKUP_ALLOWED_HOSTS"


class SourceRejected(RuntimeError):
    """The source is not on the allow-list, and a backup must not run.

    Distinct from a missing-variable error: this is an affirmative decision
    that the source is not permitted, with a reason the operator can act on.
    """


@dataclass(frozen=True)
class SourceParts:
    """The connection parameters of a source URL, credentials included.

    Only ``_credential_env`` in the backup script ever sees this object, and
    it exists so that pg_dump can be told the same connection without the
    credential appearing in argv. Nothing here is logged, returned by
    ``parse_source_url``, or written to a manifest.
    """

    username: str | None
    password: str | None
    host: str
    port: int
    database: str


@dataclass(frozen=True)
class SourceIdentity:
    """What a source is, with everything secret removed."""

    scheme: str
    hostname: str
    #: Set only when the caller explicitly asks for the full parts. Never
    #: populated by ``parse_source_url``, so a manifest or a log line built
    #: from an identity cannot leak through it.
    _parts: SourceParts | None = field(default=None, repr=False, compare=False)

    def describe(self) -> str:
        """A single line safe for a manifest or a log."""
        return f"{self.scheme}://{self.hostname}"

    def parts(self) -> SourceParts:
        """The connection parameters, for callers that must connect with them.

        Raises when the identity was built without them: a caller that
        forgot it must not silently connect with an empty credential.
        """
        if self._parts is None:
            raise SourceRejected(
                "this identity carries no connection parts; ask for them explicitly"
            )
        return self._parts


def parse_source_url(url: str, with_parts: bool = False) -> SourceIdentity:
    """Parse a PostgreSQL URL into its identity, refusing anything unusable.

    The returned object carries the scheme and the host only, when
    ``with_parts`` is false. The username, password, port, database name and
    query string are deliberately dropped here rather than stripped at the
    call site, so a caller cannot forget.

    ``with_parts=True`` additionally attaches the connection parts for the
    one caller that must connect with them (the backup's credential
    environment); the returned object still never prints them, but a caller
    holding it can. Nothing else in the codebase asks for them.
    """
    if not url or not isinstance(url, str):
        raise SourceRejected("the source URL is empty")

    if "://" not in url:
        raise SourceRejected(
            "the source URL has no scheme; a backup needs postgresql:// or postgres://"
        )

    try:
        parts = urlsplit(url)
    except ValueError as exc:
        # urlsplit raises ValueError on a malformed URL, e.g. an unparseable
        # port or an invalid IPv6 literal.
        raise SourceRejected(f"the source URL could not be parsed: {exc}") from exc

    scheme = (parts.scheme or "").lower()
    if scheme not in POSTGRESQL_SCHEMES:
        raise SourceRejected(
            f"the source scheme is {scheme!r}, not PostgreSQL; a backup of any "
            "other database is refused"
        )

    try:
        hostname = parts.hostname
    except ValueError as exc:
        # An unparseable IPv6 literal makes .hostname raise.
        raise SourceRejected(f"the source hostname could not be parsed: {exc}") from exc

    if not hostname:
        raise SourceRejected("the source URL has no hostname")

    try:
        # A malformed or out-of-range port is only detected by accessing
        # `.port`: `urlsplit` parses the netloc lazily, so `.hostname` alone
        # accepts `host:notaport`. Left unset, that fails later in pg_dump -
        # which is still fail-closed, but with a message about libpq rather than
        # about a source that was never valid. Reading `.port` here surfaces it
        # where the rest of the source is being validated.
        parts.port  # noqa: B018 - the access is the check
    except ValueError as exc:
        raise SourceRejected(f"the source URL has an unparseable port: {exc}") from exc

    try:
        hostname = hostname.lower()
        hostname.encode("idna")
    except UnicodeError as exc:
        raise SourceRejected(f"the source hostname is not a valid name: {exc}") from exc

    connection = None
    if with_parts:
        connection = SourceParts(
            username=parts.username,
            password=parts.password,
            host=hostname,
            port=parts.port or 5432,
            # A leading "/" is libpq's default database; the name it maps
            # to is not needed for connecting to the configured source.
            database=(parts.path or "/").lstrip("/") or "postgres",
        )
    return SourceIdentity(scheme=scheme, hostname=hostname, _parts=connection)


def _read_allow_list(raw: str | None) -> frozenset[str]:
    """Parse a comma-separated allow-list into hostnames.

    Whitespace and empty entries are tolerated - an operator hand-editing a
    secret will leave a trailing comma - but a resulting empty set is an error,
    because an empty allow-list would mean "nothing is permitted", which is not
    a configuration anybody intends. An entry that is not a bare hostname (one
    carrying a scheme, a path, a port, or a credential) is a malformed
    configuration rather than an over-broad one, and is refused as such: a
    half-pasted connection string would silently match nothing and look like a
    broken backup rather than a misconfigured one.
    """
    if raw is None:
        return frozenset()

    entries = {entry.strip() for entry in raw.split(",")}
    hostnames = frozenset(entry.lower() for entry in entries if entry)

    malformed = sorted(
        entry for entry in hostnames if not _is_bare_hostname(entry)
    )
    if malformed:
        raise SourceRejected(
            f"the allow-list entry {malformed[0]!r} is not a bare hostname; a "
            "host allow-list names hosts, not URLs, ports, or credentials"
        )

    return hostnames


def _is_bare_hostname(entry: str) -> bool:
    """True when the entry could be nothing but a hostname."""
    if "://" in entry or "/" in entry or "@" in entry or ":" in entry:
        return False
    if entry.startswith(".") or entry.endswith("."):
        return False
    return bool(entry)


def resolve_source(
    env_name: str = "SZ_BACKUP_SOURCE_URL", mode: str = "scheduled"
) -> tuple[str, SourceIdentity]:
    """Read the source URL from the environment and validate it.

    Returns `(url, identity)`: the URL for `pg_dump`, and the identity for
    reporting. The URL is never returned to anything that logs.

    Refuses, in order: a missing variable, a missing allow-list, an
    unparseable URL, a non-PostgreSQL URL, a listed production host under
    the scheduled policy or without an authorization record, and a host
    absent from the allow-list.
    """
    url = os.environ.get(env_name)
    if not url:
        raise SourceRejected(f"{env_name} is not set; a backup needs an explicit source")

    return url, validate_source(url, mode=mode)


def source_kind(identity: SourceIdentity) -> str:
    """Classify a source as ``production`` or ``non-production``.

    The classification is explicit and host-based, never a substring guess:
    a host named in the known-production set is production even when its
    name contains no "prod" - which is the exact failure this module was
    written after (the audited Neon host carries no such substring).
    """
    return "production" if identity.hostname in KNOWN_PRODUCTION_HOSTS else "non-production"


def authorization_for(kind: str, mode: str = "scheduled") -> str | None:
    """The recorded authorization for a *production* backup, if any.

    Two rules that encode the policy rather than describe it:

    * A production source is permitted only under the **manual** mode - a
      human pressed the button and the repository owner recorded the
      authorization reference. A *scheduled* run refuses a production
      source whatever the configuration says, so a cron entry cannot
      silently perform the production backup the policy reserves for a
      person. The default is the fail-closed direction: a caller that does
      not declare itself manual gets the unattended policy.
    * A non-production source needs no authorization and must never inherit
      one: the variable is read only when the kind is production, so setting
      it cannot smuggle a second source in behind the non-production path.
    """
    if kind != "production":
        return None
    if mode != "manual":
        raise SourceRejected(
            "the source is a known production endpoint and this run is "
            f"{mode!r}: a production backup is authorised by a person, never by "
            "a schedule. Re-run this workflow manually (workflow_dispatch) once "
            f"{PRODUCTION_AUTHORIZATION_ENV} names the operator's audit "
            "reference; until then the scheduled run backs up only the "
            "non-production sources it is allowed to reach."
        )
    value = os.environ.get(PRODUCTION_AUTHORIZATION_ENV, "").strip()
    if not value:
        raise SourceRejected(
            "the source is a known production endpoint, so a backup of it needs an "
            "explicit authorization: set "
            f"{PRODUCTION_AUTHORIZATION_ENV} to the operator's audit reference "
            "(who approved this backup and when). Refusing to back up "
            "production unattended."
        )
    return value


def validate_source(
    url: str, allow_list_env: str = ALLOW_LIST_ENV, mode: str = "scheduled"
) -> SourceIdentity:
    """Validate one source URL against the configured allow-list."""
    identity = parse_source_url(url)

    allow_list = _read_allow_list(os.environ.get(allow_list_env))
    if not allow_list:
        raise SourceRejected(
            f"{allow_list_env} is not set or is empty; a backup requires an "
            "explicit hostname allow-list, and default-deny applies. Add the "
            "backup host there."
        )

    if identity.hostname not in allow_list:
        raise SourceRejected(
            f"the source host {identity.hostname!r} is not in "
            f"{allow_list_env} (default-deny: only explicitly named hosts are "
            f"permitted). Permitted hosts configured: {sorted(allow_list)}"
        )

    # The kind is decided after the allow-list, so an unlisted host fails as
    # "not permitted" and a listed production host fails as "not authorized":
    # the two refusals mean different things to the operator.
    authorization_for(source_kind(identity), mode=mode)

    return identity


def known_production_hosts() -> list[str]:
    """The deny-list, as a sorted list, for tests and documentation."""
    return sorted(KNOWN_PRODUCTION_HOSTS)


def describe_allow_list(env_name: str = ALLOW_LIST_ENV) -> list[str] | None:
    """The configured allow-list, or None when nothing is configured.

    Used by the manifest so the artifact records *which* hosts were permitted
    rather than which host was used - a manifest that revealed the source
    would leak the infrastructure, and one that revealed nothing would be
    unauditable.
    """
    allow_list = _read_allow_list(os.environ.get(env_name))
    return sorted(allow_list) if allow_list else None
