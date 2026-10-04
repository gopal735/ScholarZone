"""Append-only, database-level audit of every scholarship image mutation.

The image regression on scholarships 14, 130 and 554 reverted with no
verification-history row and no recorded maintenance run. Every writer that
survived forensics writes image columns through the ORM and commits, so the
application layer left no durable trace of who changed what.

The only place a mutation cannot avoid is the database itself. This module
defines a trigger on ``scholarships`` that records a row whenever any tracked
image field actually changes. Because it lives in the database it also captures
bulk updates, raw SQL, one-off scripts, admin/API writes and any concurrent
actor that never ran through application code.

Design constraints:

* **Append only.** Updates and deletes are rejected by a guard trigger, so the
  table cannot be quietly rewritten.
* **Cheap when idle.** The trigger body is guarded by ``WHEN`` on the tracked
  columns, so an unrelated ``Scholarship`` update costs one comparison per
  column and inserts nothing.
* **Never optional.** A mutation without an application context is still
  recorded, labelled ``unknown``. Silence would be the one unacceptable
  outcome for an audit.
* **No secrets.** Only the tracked image columns, the transaction identity and
  coarse connection metadata are stored. Credentials, headers and tokens are
  never captured.

Writer attribution is best-effort. A label proves which code path ran, not who
ran it; the guard exists to make an unattributed mutation visible as
``unknown`` rather than to assert an identity.
"""
from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

#: The image columns whose mutation is audited. These are exactly the fields
#: the image pipeline writes; ``image_source_url`` and ``image_alt_text`` are
#: the column names for the source and alt-text values.
TRACKED_IMAGE_FIELDS: tuple[str, ...] = (
    "image_url",
    "image_source_url",
    "image_source_type",
    "image_kind",
    "image_alt_text",
    "image_verified_at",
    "image_evaluation_status",
    "image_evaluated_at",
)

AUDIT_TABLE = "scholarship_image_audit"
GUARD_TABLE = "scholarship_image_audit_context"
UNATTRIBUTED = "unknown"

#: Bound so a caller cannot stuff an unbounded string into a narrow column, and
#: so a malformed label cannot break the INSERT that records the mutation.
_MAX_CONTEXT = 120


def sanitize_writer_context(label: object) -> str:
    """Return a safe, bounded writer label, or ``unknown``.

    Context arrives from application code and, through the PostgreSQL session
    setting, potentially from a connection string. It is therefore reduced to a
    short single-line string before it can reach the audit table.
    """
    if label is None:
        return UNATTRIBUTED
    text_value = " ".join(str(label).split())
    if not text_value:
        return UNATTRIBUTED
    return text_value[:_MAX_CONTEXT]


def _changed_condition(reference: str = "OLD", other: str = "NEW") -> str:
    """``WHEN`` clause for the tracked columns.

    ``IS DISTINCT FROM`` is null-safe, so NULL -> URL and URL -> NULL both
    count as a change, which is precisely the transition that went missing.
    """
    parts = [
        f"{reference}.{field} IS DISTINCT FROM {other}.{field}"
        for field in TRACKED_IMAGE_FIELDS
    ]
    return "\n            OR ".join(parts)


def _pg_context_lookup() -> str:
    """Read the transaction-local writer label, defaulting to ``unknown``."""
    return (
        "COALESCE(NULLIF(current_setting('scholarzone.writer_context', true), ''), "
        f"'{UNATTRIBUTED}')"
    )


def _pg_record_sql() -> str:
    """One INSERT per mutated row, listing only the fields that changed.

    PL/pgSQL, because an ``AFTER`` row trigger must ``RETURN NULL`` and that
    statement exists only in the procedural dialect.

    Field names are inlined from :data:`TRACKED_IMAGE_FIELDS`, a module-level
    constant. They are deliberately not passed as bind parameters: a function
    body is parsed when the function is created, so a driver placeholder inside
    it would be a syntax error rather than a parameter.

    Each changed field appends its name and merges one key into the before/after
    objects, so an event carries exactly the fields that moved rather than a full
    row copy.
    """
    body = []
    for field in TRACKED_IMAGE_FIELDS:
        test = f"OLD.{field} IS DISTINCT FROM NEW.{field}"
        body.append(f"    IF {test} THEN")
        body.append(f"        fields := fields || '{field}, ';")
        body.append(
            f"        before_values := before_values || "
            f"jsonb_build_object('{field}', OLD.{field});"
        )
        body.append(
            f"        after_values := after_values || "
            f"jsonb_build_object('{field}', NEW.{field});"
        )
        body.append("    END IF;")
    body = "\n".join(body)

    return f"""
CREATE OR REPLACE FUNCTION scholarzone_record_image_mutation()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $audit$
DECLARE
    fields text := '';
    before_values jsonb := '{{}}'::jsonb;
    after_values jsonb := '{{}}'::jsonb;
BEGIN
{body}

    INSERT INTO {AUDIT_TABLE} (
        scholarship_id, changed_fields, before_values, after_values,
        writer_context, application_name, client_addr, transaction_id
    )
    VALUES (
        NEW.id,
        btrim(fields),
        before_values,
        after_values,
        {_pg_context_lookup()},
        current_setting('application_name', true),
        inet_client_addr()::text,
        txid_current()::text
    );
    RETURN NULL;
END;
$audit$"""


def postgresql_audit_ddl() -> list[str]:
    """Idempotent DDL installing the audit table, trigger and guard.

    Every statement is guarded so running this on every startup is safe and
    re-running it changes nothing.
    """
    return [
        f"""
CREATE TABLE IF NOT EXISTS {AUDIT_TABLE} (
    id BIGSERIAL PRIMARY KEY,
    scholarship_id INTEGER NOT NULL,
    changed_at_utc TIMESTAMPTZ NOT NULL DEFAULT now(),
    changed_fields TEXT NOT NULL,
    before_values JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    after_values JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    writer_context VARCHAR(120) NOT NULL DEFAULT '{UNATTRIBUTED}',
    application_name TEXT,
    client_addr TEXT,
    transaction_id TEXT
)
""",
        f"COMMENT ON TABLE {AUDIT_TABLE} IS "
        "'Append-only forensic record of scholarship image mutations. "
        "Read-only for operators; no application endpoint exposes it.'",
        f"CREATE INDEX IF NOT EXISTS ix_{AUDIT_TABLE}_scholarship "
        f"ON {AUDIT_TABLE} (scholarship_id, changed_at_utc DESC)",
        f"CREATE INDEX IF NOT EXISTS ix_{AUDIT_TABLE}_changed_at "
        f"ON {AUDIT_TABLE} (changed_at_utc DESC)",
        f"CREATE INDEX IF NOT EXISTS ix_{AUDIT_TABLE}_writer "
        f"ON {AUDIT_TABLE} (writer_context)",
        # Single-row holder for the transaction-local writer label. The trigger
        # falls back to 'unknown' when the row is absent, so a forgotten
        # context is visible rather than silent. It holds no scholarship data.
        f"""
CREATE TABLE IF NOT EXISTS {GUARD_TABLE} (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    writer_context VARCHAR(120) NOT NULL
)
""",
        _pg_record_sql(),
        f"""
CREATE OR REPLACE FUNCTION scholarzone_image_mutation_guard()
RETURNS trigger
LANGUAGE plpgsql
AS $guard$
BEGIN
    RAISE EXCEPTION
        'scholarship_image_audit is append-only; % is not permitted', TG_OP
        USING ERRCODE = 'restrict_violation';
END;
$guard$
""",
        f"""
DROP TRIGGER IF EXISTS trg_{AUDIT_TABLE}_immutable ON {AUDIT_TABLE}
""",
        f"""
CREATE TRIGGER trg_{AUDIT_TABLE}_immutable
BEFORE UPDATE OR DELETE ON {AUDIT_TABLE}
FOR EACH ROW EXECUTE FUNCTION scholarzone_image_mutation_guard()
""",
        # TRUNCATE does not fire row-level triggers, so the guard above cannot
        # see it and the whole table could be emptied in one statement. This
        # statement-level trigger is the only thing that stops it. The
        # application connects as the table owner on Neon, and a PostgreSQL
        # owner cannot have its own privileges revoked, so enforcement has to
        # live in the database rather than in the grant.
        f"DROP TRIGGER IF EXISTS trg_{AUDIT_TABLE}_no_truncate ON {AUDIT_TABLE}",
        f"""
CREATE TRIGGER trg_{AUDIT_TABLE}_no_truncate
BEFORE TRUNCATE ON {AUDIT_TABLE}
FOR EACH STATEMENT EXECUTE FUNCTION scholarzone_image_mutation_guard()
""",
        # Denied for every role that is not the owner. The owner keeps its
        # implicit rights, which is why the triggers above exist.
        f"REVOKE UPDATE, DELETE, TRUNCATE ON {AUDIT_TABLE} FROM PUBLIC",
        f"DROP TRIGGER IF EXISTS trg_scholarships_image_audit ON scholarships",
        f"""
CREATE TRIGGER trg_scholarships_image_audit
AFTER UPDATE ON scholarships
FOR EACH ROW
WHEN (
            {_changed_condition()}
        )
EXECUTE FUNCTION scholarzone_record_image_mutation()
""",
    ]


def _sqlite_json_object(reference: str) -> str:
    """Build a JSON object holding only the fields that changed.

    ``json_object`` retains keys whose value is NULL, which would report a
    field that never moved as a change of ``null -> null``. Instead each field
    is projected as a key/value pair and filtered to the rows whose key is not
    NULL, so only genuinely changed fields appear.
    """
    rows = []
    for field in TRACKED_IMAGE_FIELDS:
        test = f"OLD.{field} IS NOT NEW.{field}"
        rows.append(
            f"            SELECT '{field}' AS k, {reference}.{field} AS v "
            f"WHERE {test}"
        )
    union = "\n            UNION ALL\n".join(rows)
    return (
        "(SELECT coalesce(json_group_object(k, v), '{{}}')\n"
        "             FROM (\n"
        f"            {union}\n"
        "             ))"
    )


def _sqlite_changed_fields_concat() -> str:
    """Concatenate the names of changed fields into one comma-separated list.

    ``||`` is explicit between every term because adjacent string literals in
    SQL are not concatenated implicitly.
    """
    terms = [
        f"CASE WHEN OLD.{f} IS NOT NEW.{f} THEN '{f}, ' ELSE '' END"
        for f in TRACKED_IMAGE_FIELDS
    ]
    joined = "\n            || ".join(terms)
    # Each term contributes a trailing ', '. The list is trimmed at both ends
    # so the stored value reads 'image_url, image_kind' - the same shape the
    # PostgreSQL path produces with array_to_string(fields, ', ') - and splits
    # cleanly on ', '.
    return f"rtrim(ltrim(\n            {joined}\n        ), ', ')"


def sqlite_audit_ddl() -> list[str]:
    """Idempotent DDL for SQLite, used by local development and the test suite.

    SQLite cannot run the PL/pgSQL function, so the same conditional logic is
    expressed as a trigger body. The audited fields, the null-safe comparison
    and the append-only guard are identical, which is what lets the behaviour
    be tested without a PostgreSQL server.
    """
    return [
        f"""
CREATE TABLE IF NOT EXISTS {AUDIT_TABLE} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scholarship_id INTEGER NOT NULL,
    changed_at_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    changed_fields TEXT NOT NULL,
    before_values TEXT NOT NULL DEFAULT '{{}}',
    after_values TEXT NOT NULL DEFAULT '{{}}',
    writer_context VARCHAR(120) NOT NULL DEFAULT '{UNATTRIBUTED}',
    application_name TEXT,
    client_addr TEXT,
    transaction_id TEXT
)
""",
        f"CREATE INDEX IF NOT EXISTS ix_{AUDIT_TABLE}_scholarship "
        f"ON {AUDIT_TABLE} (scholarship_id, changed_at_utc DESC)",
        f"""
CREATE TABLE IF NOT EXISTS {GUARD_TABLE} (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    writer_context VARCHAR(120) NOT NULL
)
""",
        "DROP TRIGGER IF EXISTS trg_scholarships_image_audit",
        f"""
CREATE TRIGGER trg_scholarships_image_audit
AFTER UPDATE ON scholarships
FOR EACH ROW
WHEN (
            {_changed_condition("OLD", "NEW").replace(" IS DISTINCT FROM ", " IS NOT ")}
        )
BEGIN
    INSERT INTO {AUDIT_TABLE} (
        scholarship_id, changed_fields, before_values, after_values,
        writer_context, application_name, client_addr, transaction_id
    )
    SELECT
        NEW.id,
        trim(
            {_sqlite_changed_fields_concat()}
        ),
        {_sqlite_json_object("OLD")},
        {_sqlite_json_object("NEW")},
        COALESCE(
            (SELECT writer_context FROM {GUARD_TABLE} WHERE singleton = 1),
            '{UNATTRIBUTED}'
        ),
        NULL,
        NULL,
        NULL;
END
""",
        "DROP TRIGGER IF EXISTS trg_scholarship_image_audit_immutable",
        f"""
CREATE TRIGGER trg_scholarship_image_audit_immutable
BEFORE UPDATE ON {AUDIT_TABLE}
FOR EACH ROW
WHEN (1 = 1)
BEGIN
    SELECT RAISE(ABORT, 'scholarship_image_audit is append-only; UPDATE is not permitted');
END
""",
        "DROP TRIGGER IF EXISTS trg_scholarship_image_audit_no_delete",
        f"""
CREATE TRIGGER trg_scholarship_image_audit_no_delete
BEFORE DELETE ON {AUDIT_TABLE}
FOR EACH ROW
WHEN (1 = 1)
BEGIN
    SELECT RAISE(ABORT, 'scholarship_image_audit is append-only; DELETE is not permitted');
END
""",
        # SQLite has no TRUNCATE statement, so the delete guard is the whole
        # boundary there.
    ]


def audit_ddl_for(dialect: str) -> list[str]:
    """Return the DDL appropriate to a SQLAlchemy dialect name."""
    if dialect == "postgresql":
        return postgresql_audit_ddl()
    if dialect == "sqlite":
        return sqlite_audit_ddl()
    return []


def create_image_audit_schema(connection) -> None:
    """Install or upgrade the audit structure for the connection's dialect.

    Safe to call on every startup: all statements are guarded, and re-running
    leaves an existing table, trigger and guard intact.
    """
    statements = audit_ddl_for(connection.dialect.name)
    if not statements:
        logger.info("[IMAGE AUDIT] dialect %s not instrumented", connection.dialect.name)
        return
    try:
        # Installed before the trigger: the SQLite trigger body calls
        # scholarzone_writer_context(), so the function has to exist on every
        # connection before any write can reach it.
        instrument_engine_for_writer_context()
        for statement in statements:
            connection.execute(text(statement))
    except Exception:
        # Deliberately swallowed. This is instrumentation, and taking a live
        # site down because a forensic trigger could not be installed would
        # trade availability for a log line. The CRITICAL record is the signal
        # that attribution is not currently provable, and the trigger's
        # presence is verified explicitly after deployment.
        logger.critical(
            "[IMAGE AUDIT] CRITICAL: audit structure could not be installed. "
            "Image mutations are NOT being recorded until this is resolved.",
            exc_info=True,
        )
        return
    logger.info("[IMAGE AUDIT] audit structure verified for %s", connection.dialect.name)


#: Label for the code path currently running. A ContextVar rather than a
#: module global because maintenance stages run concurrently in threads, and a
#: shared global would let one stage's label be attributed to another.
_writer_label: ContextVar[str | None] = ContextVar("scholarzone_writer_label", default=None)

_engine_instrumented = False


def _stamp_context_on_sqlite(connection, label: str) -> None:
    """Deprecated shim retained for clarity; use :func:`_apply_context`."""
    _apply_context(connection, label)


def instrument_engine_for_writer_context() -> None:
    """Make the current writer label reachable from the audit trigger.

    Registered once per process. On SQLite the label is written to a
    single-row helper table at the start of every session transaction. On
    PostgreSQL it is set as a transaction-local setting, so a pooled connection
    cannot carry one writer's label into an unrelated later request.

    Attribution is deliberately carried by data the trigger can read, not by a
    Python callback: a trigger that calls a function missing from a connection
    would abort the writes it exists to record.
    """
    global _engine_instrumented
    if _engine_instrumented:
        return

    @event.listens_for(Session, "after_begin")
    def _stamp_writer_context(session, transaction, connection):  # noqa: ANN001
        """Stamp, or clear, the label when a transaction opens.

        This is the path a maintenance stage takes: it opens its own session
        inside the writer block, so the label is already set by the time the
        transaction begins. When no label is set the previous one is cleared, so
        a connection reused for an unlabelled write cannot inherit it.

        The write is skipped when the connection already holds an empty context,
        which is the overwhelmingly common case. Avoiding a needless write per
        transaction matters on SQLite, where a file-backed database serialises
        writers and a redundant write would contend with unrelated sessions.
        """
        label = _writer_label.get() or ""
        if not label and _context_is_clear(connection):
            return
        _apply_context(connection, label)

    _engine_instrumented = True


def _context_is_clear(connection) -> bool:
    """Report whether the context row is already empty on this connection.

    Used to skip a redundant write. A failure here is treated as "not clear", so
    the caller performs the write and correctness does not depend on the check
    succeeding.
    """
    try:
        if connection.engine.dialect.name != "sqlite":
            return True
        current = connection.execute(
            text(f"SELECT writer_context FROM {GUARD_TABLE} WHERE singleton = 1")
        ).scalar()
        return not current
    except Exception:
        return False


def _apply_context(connection, label: str) -> None:
    """Write ``label`` to the channel the audit trigger reads.

    Always writes, including an empty label: the row is cleared first so a label
    committed by an earlier transaction cannot be inherited by the next one on
    the same connection. Without that, a pooled connection would carry one
    writer's label into an unrelated later request and the audit would name the
    wrong code path.

    Never raises: attribution is observability, and a failure to label must not
    abort the write being observed.
    """
    try:
        dialect = connection.engine.dialect.name
        if dialect == "postgresql":
            # ``true`` makes the setting transaction-local, so it cannot leak to
            # the next transaction that borrows this pooled connection.
            connection.execute(
                text("SELECT set_config('scholarzone.writer_context', :label, true)"),
                {"label": label or ""},
            )
        elif dialect == "sqlite":
            connection.execute(text(f"DELETE FROM {GUARD_TABLE} WHERE singleton = 1"))
            if label:
                connection.execute(
                    text(f"INSERT INTO {GUARD_TABLE} (singleton, writer_context) "
                         "VALUES (1, :label)"),
                    {"label": label},
                )
    except Exception:
        logger.debug("[IMAGE AUDIT] writer context could not be applied",
                     exc_info=True)


@contextmanager
def image_writer(label: str, session: Session | None = None) -> Iterator[None]:
    """Attribute image mutations performed in this block to ``label``.

    The label applies to any transaction opened inside the block, and to
    ``session`` if one is passed. Passing the session matters when its
    transaction is already open: the transaction-start hook will not fire, so
    without an explicit write the label would be missing.

    A writer that mutates images without using this block is still audited,
    labelled ``unknown``; the context narrows attribution, it never enables it.
    """
    safe = sanitize_writer_context(label)
    token = _writer_label.set(safe)
    try:
        if session is not None:
            _apply_context(session.connection(), safe)
        yield
    finally:
        _writer_label.reset(token)


@contextmanager
def writer_context(session: Session, label: str) -> Iterator[Session]:
    """Attribute image mutations in this block to ``label``.

    Applies the label to an already-open session, for callers that hold one.
    The write is issued here rather than relying on transaction start, because a
    session handed to this function has usually already begun its transaction
    on an earlier read; the UPDATE that follows is emitted by a later commit.

    The context is an attribution hint, not an identity claim: it records which
    code path ran. A mutation with no label is still audited, as ``unknown``.
    """
    safe = sanitize_writer_context(label)
    with image_writer(safe, session):
        yield session


def audit_trigger_is_installed(engine) -> bool:
    """Report whether the image-mutation trigger is actually installed.

    An audit table with no trigger behind it would let mutations pass
    unrecorded while appearing audited, so startup treats a missing trigger as
    an invalid schema rather than logging it and continuing.
    """
    dialect = engine.dialect.name
    with engine.connect() as connection:
        if dialect == "postgresql":
            found = connection.execute(
                text(
                    "SELECT count(*) FROM pg_trigger "
                    "WHERE tgrelid = 'scholarships'::regclass "
                    "AND tgname = 'trg_scholarships_image_audit' "
                    "AND NOT tgisinternal"
                )
            ).scalar()
            return bool(found)
        if dialect == "sqlite":
            found = connection.execute(
                text(
                    "SELECT count(*) FROM sqlite_master "
                    "WHERE type = 'trigger' "
                    "AND name = 'trg_scholarships_image_audit'"
                )
            ).scalar()
            return bool(found)
    return False


READ_ONLY_INSPECTION_SQL = f"""\
-- Read-only inspection of the image mutation audit. Every statement is a
-- SELECT; the append-only guard rejects UPDATE and DELETE at the database.

-- Everything that ever changed these three records, newest first:
SELECT id, scholarship_id, changed_at_utc, changed_fields,
       before_values, after_values, writer_context,
       application_name, client_addr, transaction_id
FROM {AUDIT_TABLE}
WHERE scholarship_id IN (14, 130, 554)
ORDER BY changed_at_utc DESC, id DESC;

-- Mutations nobody attributed - the ones worth investigating first:
SELECT id, scholarship_id, changed_at_utc, changed_fields, writer_context
FROM {AUDIT_TABLE}
WHERE writer_context = '{UNATTRIBUTED}'
ORDER BY changed_at_utc DESC, id DESC;

-- Which writer contexts are actually clearing images:
SELECT writer_context, count(*) AS mutations,
       min(changed_at_utc) AS first_seen, max(changed_at_utc) AS last_seen
FROM {AUDIT_TABLE}
GROUP BY writer_context
ORDER BY mutations DESC;

-- The full image history of one record, across every writer:
SELECT changed_at_utc, changed_fields, before_values, after_values, writer_context
FROM {AUDIT_TABLE}
WHERE scholarship_id = :scholarship_id
ORDER BY changed_at_utc, id;
"""
