#!/usr/bin/env python3
"""
Generate a public-safe JSON snapshot from the local SQLite database.

Uses the canonical public visibility predicate:
- Exclude closed, archived, and quarantined records
- Do not gate catalogue inclusion on verification/image quality
- Serialize using the existing public response schema (ScholarshipDetailResponse fields)
- Never export admin notes, secrets, private session/user data, or internal review fields

The predicate is deliberately the same one the public API uses
(``app.repositories.scholarships.public_visibility_conditions``), so a record
that the live list would hide is not published here either. It is restated as
SQL rather than imported because this script must run without the backend
package or a live database.

Run from repository root: python generate_snapshot.py
"""

import sqlite3
import json
import sys
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Any

# The single authoritative value for "this record may be presented publicly as
# verified". Mirrored from app.verification_contract so the two cannot drift in
# silence; the snapshot's own `verified` field and its `verified_active`
# statistic are both derived from this and must agree with each other and with
# the API.
AUTHORITATIVE_VERIFIED_STATUS = "active"

# The value the public contract reports when a record carries no usable
# verification status. Mirrored from app.verification_contract.
UNCERTAIN_VERIFICATION_STATUS = "needs_review"

# Lifecycle states the public catalogue defines. Anything else is serialised as
# null, exactly as ScholarshipResponse._unknown_status_becomes_null does, so an
# unrecognised stored value is reported as "status not published" rather than
# being invented or failing the whole export.
PUBLIC_LIFECYCLE_STATUSES = ("open", "upcoming", "closing-soon", "closed")

# Fields the public response schema declares, as an explicit allowlist.
#
# An allowlist rather than a blacklist: the table carries internal workflow
# state (verification_notes, verified_by, next_verification_due, is_archived,
# archived_at, archived_reason, image_evaluation_status, is_verified, ...) and
# a blacklist would have to enumerate every one of them and stay correct as new
# internal columns are added. Anything not listed here is not exported, so a
# new internal column is private by default rather than public by omission.
#
# The set is the union of ScholarshipResponse and ScholarshipDetailResponse,
# plus the researched enrichment fields the 2026-10-11 publication added:
# the structured funding triple, the tuition-coverage flag, the applicant
# guidance the research authors, and the official provenance the research
# records (extra official URLs and the citation list). Those researched fields
# are published deliberately, as a reviewed extension of the public contract,
# because they are the fields applicants cannot verify from the awarding
# body's own single landing page. `funding_amount` is null whenever no amount
# was confirmed, and is never derived from a percentage.
PUBLIC_FIELDS: tuple[str, ...] = (
    "id",
    "title",
    "name",
    "country",
    "degree",
    "degree_levels",
    "funding",
    "funding_type",
    "funding_amount",
    "funding_currency",
    "funding_period",
    "tuition_coverage",
    "deadline",
    "deadline_date",
    "deadline_precision",
    "status",
    "verified",
    "last_verified_at",
    "verification_status",
    "official_source_url",
    "official_source_urls",
    "source_citations",
    "applicant_utility",
    "updated_at",
    "image_url",
    "image_source_type",
    "image_kind",
    "description",
    "region",
    "duration",
    "application_period",
    "official_source",
    "catalogue_url",
    "official_updates_url",
    "application_link",
    "image_source_url",
    "image_verified_at",
    "image_alt_text",
    "eligibility",
    "eligibility_summary",
    "benefits",
    "coverage",
    "requirements",
    "documents",
    "required_documents",
    "english_requirement",
    "application_method",
    "selection_notes",
    "program_type",
    "best_fit",
    "last_verified_date",
    "notes",
)

# Columns the export actually reads. Checked before anything is read so a
# missing column or a missing file fails with the real reason instead of a
# bare KeyError on row 1.
#
# This list covers the sort expressions as well as the record fields. Two of
# the repository's ordering keys are not public fields - `created_at` for
# `recently-added`, and `is_verified` for `recommended` - so a database missing
# either would otherwise reach the sort query and raise a bare
# `OperationalError` naming a column the operator has never heard of, after the
# whole export had already succeeded.
REQUIRED_COLUMNS: tuple[str, ...] = (
    "id",
    "title",
    "country",
    "degree",
    "funding",
    "deadline_display",
    "deadline_date",
    "deadline_precision",
    "status",
    "verification_status",
    "updated_at",
    "created_at",
    "is_verified",
    "last_verified_at",
    "official_source_url",
    "official_source",
    "image_url",
    "image_source_type",
    "image_kind",
    "image_source_url",
    "image_verified_at",
    "image_alt_text",
    "description",
    "region",
    "duration",
    "application_period",
    "catalogue_url",
    "official_updates_url",
    "application_link",
    "eligibility",
    "eligibility_summary",
    "benefits",
    "coverage",
    "requirements",
    "documents",
    "english_requirement",
    "application_method",
    "selection_notes",
    "program_type",
    "best_fit",
    "last_verified_date",
    "notes",
    # The researched enrichment columns. A snapshot that publishes the funding
    # triple, coverage, citations or applicant guidance needs them present;
    # `_assert_inputs` fails with the real reason before any row is read.
    "funding_amount",
    "funding_currency",
    "funding_period",
    "tuition_coverage",
    "applicant_utility",
    "official_details",
    "programme_verification",
)

# The three columns the visibility predicate reads. A NULL in any of them makes
# the SQL predicate evaluate to NULL, which a WHERE clause treats as "exclude"
# - so such a record silently disappears from the public set without being
# counted in any excluded bucket, and the reconciliation below stops holding.
# They are checked explicitly so that is a loud failure rather than a silent
# shrinking of the catalogue.
VISIBILITY_COLUMNS: tuple[str, ...] = ("status", "is_archived", "verification_status")

# Fields serialised as a date, and as a datetime, matching the public schema.
# `last_verified_at`/`last_verified_date`/`deadline_date` are declared `date`,
# and `updated_at`/`image_verified_at` are declared `datetime`; the API
# therefore emits them as `YYYY-MM-DD` and as ISO 8601 respectively. SQLite
# stores all of them as text in a database-specific shape
# ("2026-10-09 13:35:21", "2025-06-26 00:00:00.000000"), which is not what the
# API returns, so they are normalised here rather than passed through.
DATE_FIELDS = ("last_verified_at", "last_verified_date", "deadline_date")
DATETIME_FIELDS = ("updated_at", "image_verified_at")

# Keys an applicant-guidance blob must never carry.
#
# `applicant_utility` is authored for applicants and published here
# deliberately, so its provenance is checked rather than assumed. The research
# pipeline has kept it clean (0 violations measured across the corpus), but a
# blob is a free-form object and free-form objects drift. An internal key
# reaching a public file is an export bug of exactly the kind the PUBLIC_FIELDS
# allowlist exists to stop, so it fails the export loudly here instead of
# shipping a reviewer's workflow notes to the catalogue.
FORBIDDEN_UTILITY_KEYS = frozenset(
    {
        "verification_notes",
        "verified_by",
        "next_verification_due",
        "is_archived",
        "archived_at",
        "archived_reason",
        "image_evaluation_status",
        "image_evaluated_at",
        "auto_delete_candidate_since",
        "deletion_protected",
        "is_verified",
        "quarantine_reason",
        "quarantined",
    }
)


LIST_FIELDS = (
    "eligibility",
    "benefits",
    "coverage",
    "requirements",
    "documents",
    "application_method",
    "required_documents",
)

# Precomputed orderings, one per sort mode the catalogue offers.
#
# Two of the repository's sort keys are not public fields. `recently-added`
# orders by `created_at`, and `recommended` (which is also `default`) orders by
# the legacy `is_verified` boolean. Neither is part of the public response
# schema, so the fallback had no way to reproduce the live ordering and instead
# approximated it with a timestamp it did have - which put `recently-added` in a
# materially different order (632 of 634 positions) and `recommended` in a
# different one for 502 of 634 records. The badge a reader sees is derived from
# `verification_status`, not from `is_verified`, so the mismatch was not even
# visible as an inconsistency; it was simply a different list.
#
# Rather than widen the public schema to carry those two columns, or restate the
# ordering in JavaScript and hope it stays equivalent to the SQL, the orders are
# computed here by running the repository's own expressions over the same rows
# and are stored as ordered ID lists under `meta.sort_orders`. An ordering is a
# property of the dataset, not of each record, so it belongs in the snapshot's
# metadata rather than on every scholarship object.
#
# Each entry is the `ORDER BY` tail only: the base filter is always the public
# visibility predicate, applied by the caller below. NULL semantics are
# whatever SQLite decides for the expression, which is the point - the fallback
# inherits the backend's behaviour instead of reimplementing it.
SORT_MODES: dict[str, tuple[str, ...]] = {
    # Mirrors _sort_expressions: is_verified DESC, status priority ASC,
    # updated_at DESC, id ASC. `is_verified` is the legacy column, exactly as
    # the repository uses it, not the derived public flag.
    "recommended": (
        "CASE WHEN is_verified = 1 THEN 0 ELSE 1 END ASC",
        "CASE status WHEN 'open' THEN 0 WHEN 'closing-soon' THEN 1 ELSE 2 END ASC",
        "updated_at DESC",
        "id ASC",
    ),
    "recently-added": ("created_at DESC", "id ASC"),
    "recently-updated": ("updated_at DESC", "id ASC"),
    # deadline-soon and deadline-earliest share the repository's own predicates.
    "deadline-soon": ("(deadline_date IS NULL) ASC", "deadline_date ASC", "id ASC"),
    "deadline-earliest": ("(deadline_date IS NULL) ASC", "deadline_date ASC", "id ASC"),
    "deadline-latest": ("(deadline_date IS NULL) ASC", "deadline_date DESC", "id ASC"),
    # Exact equality on the lower-cased value, matching the repository's
    # `case(func.lower(funding) == "fully funded", 0, else_=1)`.
    "fully-funded": (
        "CASE WHEN lower(COALESCE(funding, '')) = 'fully funded' THEN 0 ELSE 1 END ASC",
        "updated_at DESC",
        "id ASC",
    ),
    "name-asc": ("lower(COALESCE(title, '')) ASC", "id ASC"),
    "name-desc": ("lower(COALESCE(title, '')) DESC", "id ASC"),
}

# The public predicate the catalogue uses, restated for the sort queries below.
PUBLIC_VISIBILITY_WHERE = (
    "status != 'closed' AND is_archived = 0 AND verification_status != 'quarantined'"
)

# The derived predicate: the visibility rule plus the deadline rule.
#
# The two are one notion of "public" - a record the catalogue would report as
# closed is not public, whether the stored status says so or the deadline does.
# Using only the stored predicate here would order a set that includes the
# twelve records the export now excludes, and the mismatch would surface as the
# coverage assertion in `_build_sort_orders`.
DERIVED_PUBLIC_VISIBILITY_WHERE = (
    f"{PUBLIC_VISIBILITY_WHERE} "
    "AND (deadline_date IS NULL OR date(deadline_date) >= date('now'))"
)


def dict_from_row(cursor: sqlite3.Cursor, row: sqlite3.Row) -> dict[str, Any]:
    """Convert a sqlite3 row to a dict with proper type handling."""
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def normalize_list_field(value: Any) -> list[str]:
    """Normalize a JSON list field to a list of strings.

    The database column is declared ``JSON`` (``eligibility``, ``benefits``,
    ``coverage``, ``requirements``, ``documents``, ``application_method``), and
    SQLite hands it back as the *text* of that JSON, so a value that arrives
    here is usually a string like ``'["Open to all", "Age 18+"]'`` rather than a
    Python list.

    Treating that text as one whole item is what the export used to do, and it
    meant every one of the 634 public records carried a single-element list
    holding the literal JSON source - one unreadable blob per field where a
    catalogue should show separate bullets. A caller has no way to tell that
    from a genuinely one-item list, so the data is silently wrong rather than
    visibly broken.

    Anything that is not valid JSON, and is not already a list, is still
    accepted as a single item: a plain free-text value is a legitimate shape
    for a repair-er's hand-written row, and refusing it would drop the content
    the record does have.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text)
            except (TypeError, ValueError):
                return [value]
            if isinstance(parsed, list):
                return [str(item) for item in parsed if item is not None]
        return [value]
    return [str(value)]


def _coerce_date(value: Any) -> date | None:
    """Coerce a stored value to a date, or None if that is not possible."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None
    # ISO-8601 with a time component, which is what SQLite hands back for a
    # date-typed column that was written from a datetime.
    head = text.split("T", 1)[0].split(" ", 1)[0]
    try:
        return date.fromisoformat(head)
    except ValueError:
        return None


# The catalogue's own rule for what a deadline means, restated so the snapshot
# and the live API cannot disagree about the same record.
#
# `app/services/lifecycle_manager.py:evaluate_lifecycle` proposes CLOSED when a
# deadline is in the past and CLOSING_SOON within 14 days, and
# `refresh_scholarship_statuses` applies it. `generate_snapshot.py` used to copy
# the stored status verbatim, so a record whose deadline had passed was
# published as `open` or `closing-soon` while the API would have served it as
# closed - in the direction that matters, because it tells a student a deadline
# is still upcoming when it is not.
#
# Twelve of the 634 committed records were in exactly that state, including id 2
# with a deadline of 2026-04-22. The same asymmetry is what broke the backend
# suite's exact-ID assertions, which were written when those deadlines were
# still in the future.
CLOSING_SOON_WINDOW_DAYS = 14


def _derive_status(stored_status: Any, deadline: date | None, today: date) -> str | None:
    """Derive the lifecycle status the catalogue would serve for this record.

    Only the catalogue's own lifecycle values are published. A stored value
    outside them is reported as "no lifecycle status", which is what
    ScholarshipResponse._unknown_status_becomes_null does, rather than passed
    through - passing it through would publish an internal or mistyped status as
    though the catalogue defined it.

    Closed is not a value this can return from a stored open/closing-soon by
    deadline alone... it is: a deadline in the past is closed, and a closed
    record is then excluded by the visibility predicate, which is the honest
    outcome - the deadline has gone.
    """
    if stored_status not in PUBLIC_LIFECYCLE_STATUSES:
        return None

    if deadline is None:
        return stored_status

    days_remaining = (deadline - today).days

    # A deadline in the past. The record is closed as far as the catalogue is
    # concerned, and the visibility predicate will therefore exclude it, which
    # is the honest outcome: the deadline has gone.
    if days_remaining < 0:
        return "closed"

    # Within the closing-soon window. Only ever narrows an open record, so a
    # stored `closing-soon` is left alone and a stored `open` is promoted.
    if days_remaining <= CLOSING_SOON_WINDOW_DAYS:
        if stored_status == "open":
            return "closing-soon"

    return stored_status

def _coerce_datetime(value: Any) -> datetime | None:
    """Coerce a stored value to a naive datetime, or None."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if not isinstance(value, str):
        return None

    text = value.strip().replace(" ", "T")
    if not text:
        return None

    # Fractional seconds of more than six digits are rejected by
    # fromisoformat on older interpreters, and SQLite writes them
    # ("2025-06-26T00:00:00.000000" has six, but a database written elsewhere
    # may carry more). Truncate rather than losing the whole timestamp.
    head, sep, tail = text.partition(".")
    if sep:
        digits = []
        for char in tail:
            if char.isdigit():
                digits.append(char)
            else:
                break
        text = f"{head}.{''.join(digits)[:6]}"

    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass

    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue

    return None


def normalize_date(value: Any) -> str | None:
    """Normalize a date-typed value to `YYYY-MM-DD`, or None."""
    return _coerce_date(value).isoformat() if _coerce_date(value) else None


def normalize_datetime(value: Any) -> str | None:
    """Normalize a datetime-typed value to ISO 8601, or None.

    The wall-clock value is preserved exactly as stored. A timezone designator
    is deliberately NOT added: the database stores these without one, and
    appending a "Z" the source never asserted would move the instant the
    moment it is parsed. This matches the API, which serialises the same
    column to `2026-10-09T13:35:21` with no offset.
    """
    parsed = _coerce_datetime(value)
    return parsed.isoformat() if parsed else None


def _assert_inputs(db_path: str, cursor: sqlite3.Cursor) -> set[str]:
    """Fail loudly, with the real reason, before any row is read."""
    if not Path(db_path).is_file():
        raise SystemExit(
            f"Snapshot source not found: {db_path}\n"
            "Pass the SQLite database as the first argument, or create "
            "backend/scholarzone.db."
        )

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='scholarships'")
    if cursor.fetchone() is None:
        raise SystemExit(f"No 'scholarships' table in {db_path}; nothing to export.")

    columns = {row[1] for row in cursor.execute("PRAGMA table_info(scholarships)").fetchall()}
    missing = [column for column in REQUIRED_COLUMNS if column not in columns]
    if missing:
        raise SystemExit(
            f"{db_path} is missing columns the public export needs: {sorted(missing)}\n"
            "Apply the schema migrations in backend/app/database.py before generating a snapshot."
        )
    return columns


def _require_no_null_visibility(cursor: sqlite3.Cursor) -> None:
    """A NULL in a predicate column silently removes a record from the export."""
    for column in VISIBILITY_COLUMNS:
        cursor.execute(f"SELECT COUNT(*) FROM scholarships WHERE {column} IS NULL")
        count = cursor.fetchone()[0]
        if count:
            raise SystemExit(
                f"{count} scholarships have a NULL {column}. The public predicate "
                f"`{column} != ...` excludes them without counting them anywhere, "
                "so the record counts would silently stop reconciling. Repair the "
                "column rather than letting the catalogue shrink."
            )


def _reconcile(counts: dict[str, int]) -> None:
    """source == public + excluded_union, or the metadata is a lie.

    This is the invariant that makes the published counts meaningful. It is
    asserted rather than printed, because a snapshot whose own header cannot
    account for every source row is a snapshot nobody can trust the totals on.
    """
    expected = counts["public"] + counts["excluded_union"]
    if expected != counts["source"]:
        raise SystemExit(
            "Public export does not reconcile: "
            f"public ({counts['public']}) + excluded_union ({counts['excluded_union']}) "
            f"= {expected}, but the source table holds {counts['source']} rows.\n"
            "Every excluded row must fall into exactly one excluded bucket."
        )


def _parse_json_blob(value: Any) -> Any:
    """Parse a JSON blob, or return None when it is absent or unparseable.

    The research columns hold JSON text. A row whose blob is missing or
    unreadable publishes as no data rather than failing the whole export: the
    catalogue's rule everywhere else is that a single bad record must not take
    the export offline. The difference from a null field is invisible to the
    reader by design - no research, no claim.
    """
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except (TypeError, ValueError):
            return None
    return None


def _coerce_amount(value: Any) -> int | float | None:
    """Coerce a stored funding amount to a number, or preserve its null.

    Absence is the honest value here: a programme with no confirmed amount
    publishes `null`, which is the difference between "we did not find a
    figure" and inventing one. A percentage-style award is not a currency
    amount and is never smuggled through this gate - the amount column holds
    confirmed currency figures only, which the research pipeline enforces at
    write time and this export does not second-guess beyond refusing to
    invent a value the column does not hold.
    """
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def _normalise_currency(value: Any) -> str | None:
    """ISO 4217 code or null. A non-ISO value publishes as null, not as text.

    The catalogue cannot verify a currency it cannot name; a free-text
    currency is not a currency, and publishing one would put a claim on the
    page that the API's contract does not make.
    """
    if not isinstance(value, str):
        return None
    text = value.strip().upper()
    if len(text) == 3 and text.isalpha():
        return text
    return None


def _normalise_url_list(value: Any) -> list[str]:
    """Deduplicated http(s) URLs from a JSON list, order preserved.

    Only absolute http(s) entries survive, matching what the frontend will
    link: a relative or ftp reference is not something a reader can follow,
    so it is dropped rather than published as a broken link.
    """
    if not isinstance(value, list):
        return []
    seen: set[str] = set()
    out: list[str] = []
    for entry in value:
        if not isinstance(entry, str):
            continue
        text = entry.strip()
        if not text.startswith(("http://", "https://")):
            continue
        if text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _build_source_citations(verification: Any) -> list[str]:
    """Official citations from a programme-verification blob.

    The blob's `source_citations` key holds the URLs the research read, in
    several historical shapes (a list of URLs, an object mapping a label to a
    URL, a list of objects). All of them are flattened to URLs here; anything
    that is not a URL is not a citation a reader can check, so it is not
    exported as one.
    """
    if not isinstance(verification, dict):
        return []

    urls: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, str):
            candidate = node.strip()
            if candidate.startswith(("http://", "https://")):
                urls.append(candidate)
            return
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if isinstance(node, dict):
            for value in node.values():
                walk(value)

    walk(verification.get("source_citations"))
    return _normalise_url_list(urls)


def _build_official_source_urls(official: Any) -> list[str]:
    """Official URLs from an official-details blob beyond the primary one.

    `official_source_urls` is the research's own list of the awarding body's
    pages for the programme (the fact sheet, the application instructions,
    the catalogue entry). The primary `official_source_url` column is the
    landing page; this list is the evidence trail beside it.
    """
    if not isinstance(official, dict):
        return []
    return _normalise_url_list(official.get("official_source_urls"))


def _build_applicant_utility(blob: Any) -> dict[str, Any] | None:
    """Publish the authored applicant guidance, or null when there is none.

    The research writes guidance keyed by role (summary, best fit, document
    audit, alerts, submission workflow, ...). It is published verbatim when
    it is an object with at least one usable value: an empty object is the
    honest "no guidance was authored" and publishes as null rather than as
    an empty section the frontend would have to special-case.

    Internal workflow keys are refused: see FORBIDDEN_UTILITY_KEYS. This is a
    public file and a reviewer's bookkeeping has no business being in it.
    """
    if not isinstance(blob, dict) or not blob:
        return None
    forbidden = sorted(FORBIDDEN_UTILITY_KEYS & set(blob))
    if forbidden:
        raise AssertionError(
            "applicant_utility carries internal workflow key(s): "
            f"{forbidden}. Export refused rather than publishing internal notes."
        )
    cleaned = {key: value for key, value in blob.items() if value not in (None, "", [], {})}
    return cleaned or None


def _build_public_record(d: dict[str, Any], today: date) -> dict[str, Any]:
    """Serialize one row against the public allowlist."""
    stored_status = d["status"]
    verification_status = d["verification_status"]
    if not (isinstance(verification_status, str) and verification_status.strip()):
        verification_status = UNCERTAIN_VERIFICATION_STATUS

    # The status is derived, not copied. `_derive_status` applies the deadline
    # rule the catalogue applies, so a deadline that has passed is not published
    # as upcoming - see its own comment for what was wrong when this was a
    # straight copy of the stored value.
    status = _derive_status(stored_status, _coerce_date(d["deadline_date"]), today)

    record: dict[str, Any] = {
        "id": d["id"],
        "title": d["title"],
        "name": d["title"],  # alias for title
        "country": d["country"],
        "degree": d["degree"],
        "degree_levels": d["degree"],  # alias for degree
        "funding": d["funding"],
        "funding_type": d["funding"],  # alias for funding
        # The researched enrichment fields. Each is null-preserving: no amount
        # means null amount, not a derived one, and no guidance means no
        # guidance section. The research pipeline that wrote them enforces the
        # evidence rules (official citations, no invented figures); this export
        # only refuses to invent values of its own.
        "funding_amount": _coerce_amount(d.get("funding_amount")),
        "funding_currency": _normalise_currency(d.get("funding_currency")),
        "funding_period": d.get("funding_period") or None,
        "tuition_coverage": (
            None if d.get("tuition_coverage") is None else bool(d.get("tuition_coverage"))
        ),
        "official_source_urls": _build_official_source_urls(
            _parse_json_blob(d.get("official_details"))
        ),
        "source_citations": _build_source_citations(
            _parse_json_blob(d.get("programme_verification"))
        ),
        "applicant_utility": _build_applicant_utility(
            _parse_json_blob(d.get("applicant_utility"))
        ),
        "deadline": d["deadline_display"] or d["deadline_date"],
        "deadline_date": normalize_date(d["deadline_date"]),
        "deadline_precision": d["deadline_precision"],
        "status": status,
        # Derived from the authoritative verification status, never from the
        # legacy `is_verified` column. The public API derives it the same way
        # (verification_contract.public_verified_from_status) and would report
        # a different answer for any row where the two disagree, so exporting
        # the stored boolean here published a claim the API does not make.
        "verified": verification_status == AUTHORITATIVE_VERIFIED_STATUS,
        "last_verified_at": normalize_date(d["last_verified_at"]),
        "verification_status": verification_status,
        "official_source_url": d["official_source_url"],
        "updated_at": normalize_datetime(d["updated_at"]),
        "image_url": d["image_url"],
        "image_source_type": d["image_source_type"],
        "image_kind": d["image_kind"],
        # Detail-only fields
        "description": d["description"],
        "region": d["region"],
        "duration": d["duration"],
        "application_period": d["application_period"],
        "official_source": d["official_source"],
        "catalogue_url": d["catalogue_url"],
        "official_updates_url": d["official_updates_url"],
        "application_link": d["application_link"],
        "image_source_url": d["image_source_url"],
        "image_verified_at": normalize_datetime(d["image_verified_at"]),
        "image_alt_text": d["image_alt_text"],
        "eligibility": normalize_list_field(d["eligibility"]),
        "eligibility_summary": d["eligibility_summary"],
        "benefits": normalize_list_field(d["benefits"]),
        "coverage": normalize_list_field(d["coverage"]),
        "requirements": normalize_list_field(d["requirements"]),
        "documents": normalize_list_field(d["documents"]),
        "required_documents": normalize_list_field(d["documents"]),  # alias
        "english_requirement": d["english_requirement"],
        "application_method": normalize_list_field(d["application_method"]),
        "selection_notes": d["selection_notes"],
        "program_type": d["program_type"],
        "best_fit": d["best_fit"],
        "last_verified_date": normalize_date(d["last_verified_date"]),
        "notes": d["notes"],
    }

    # Defence in depth: the allowlist above is the mechanism, this is the
    # assertion that it held. An internal column appearing here means the
    # export grew a field without anyone deciding to publish it.
    unexpected = set(record) - set(PUBLIC_FIELDS)
    if unexpected:
        raise AssertionError(f"Public record carries non-public fields: {sorted(unexpected)}")

    # The public schema types these as arrays. A snapshot that shipped a bare
    # string, or a null, would break the consumers that map over them.
    for field in LIST_FIELDS:
        if not isinstance(record[field], list):
            raise AssertionError(
                f"List field {field!r} serialised as {type(record[field]).__name__}, expected list."
            )

    # The public schema types these as date and datetime. The API therefore
    # answers with `YYYY-MM-DD` and ISO 8601; a snapshot answering in the
    # database's own text shape is a different type from the same field.
    for field in DATE_FIELDS:
        if record[field] is not None:
            date.fromisoformat(record[field])
    for field in DATETIME_FIELDS:
        if record[field] is not None:
            datetime.fromisoformat(record[field])

    return record


def _build_sort_orders(cursor: sqlite3.Cursor, public_ids: list[int]) -> dict[str, list[int]]:
    """Order the exported records the way the repository orders the live list.

    Every mode is computed by running the repository's own ORDER BY expressions
    over exactly the rows that were exported, so the result is derived from the
    same rule rather than restated beside it. The consequence is that a kind of
    drift that comparators are prone to - text case-folding, date parsing, NULL
    placement - cannot arise here, because there is only one implementation.

    The returned lists are total orders over the public set. A filtered subset
    inherits the backend's relative order, which is what makes the frontend able
    to filter first and then apply this index without re-sorting.

    The row set is selected by the exported ID list rather than by the
    visibility predicate, because with baseline preservation (see
    `generate_snapshot`) the exported set is the predicate's set union the
    published-baseline set: the published rows the deadline rule would hide are
    part of the exported set by design, and an ordering computed from the
    predicate alone would not cover them.
    """
    if not public_ids:
        return {mode: [] for mode in SORT_MODES}

    id_placeholders = ", ".join(str(int(rid)) for rid in public_ids)
    orders: dict[str, list[int]] = {}
    for mode, expressions in SORT_MODES.items():
        order_by = ", ".join(expressions)
        cursor.execute(
            f"SELECT id FROM scholarships WHERE id IN ({id_placeholders}) "
            f"ORDER BY {order_by}"
        )
        ids = [int(row[0]) for row in cursor.fetchall()]

        # An ordering that missed or invented a record would silently reorder
        # the catalogue, and nothing downstream would notice.
        if sorted(ids) != sorted(public_ids):
            raise AssertionError(
                f"Sort order {mode!r} does not cover exactly the public records "
                f"({len(ids)} ordered vs {len(public_ids)} exported)."
            )
        orders[mode] = ids

    return orders


def _load_baseline_ids(baseline_path: str | None) -> list[int]:
    """Published baseline IDs from the deployed snapshot, or [] when absent.

    The baseline is the artifact the catalogue is already serving: the
    committed `frontend/public/scholarships-snapshot.json`. Reading it here is
    what makes a publication non-destructive - a record the catalogue has
    been serving does not silently disappear from the next snapshot because
    a research pass wrote a past deadline date into the database. The record
    is still labelled honestly (closed, by the derived status) and stays
    visible for review; it just is not *removed* as a side effect of
    regenerating a file.

    A baseline that is absent (the first publication of a catalogue, and
    every test export) simply has nothing to protect. A baseline that is
    PRESENT but cannot be read is not that case: it is the deployed artifact
    refusing to be honoured, and proceeding without it would shrink the
    catalogue silently - the exact failure this mode exists to stop - so it
    is a hard error. The read is BOM-tolerant because the committed artifact
    has been written by more than one tool on more than one platform.
    """
    if not baseline_path:
        return []
    path = Path(baseline_path)
    if not path.is_file():
        return []
    try:
        with open(path, encoding="utf-8-sig") as handle:
            baseline = json.load(handle)
    except (OSError, ValueError) as error:
        raise SystemExit(
            f"Cannot read the published baseline {baseline_path}: {error}.\n"
            "Refusing to publish without it: the records it serves would "
            "leave the catalogue silently. Fix the artifact, or pass "
            "--strict to publish by the visibility predicate alone."
        ) from error
    records = baseline.get("scholarships")
    if not isinstance(records, list):
        raise SystemExit(
            f"The published baseline {baseline_path} has no scholarships array.\n"
            "Refusing to publish without it: the records it serves would "
            "leave the catalogue silently. Fix the artifact, or pass "
            "--strict to publish by the visibility predicate alone."
        )
    return sorted(
        {
            int(record["id"])
            for record in records
            if isinstance(record, dict) and record.get("id") is not None
        }
    )


def generate_snapshot(
    db_path: str,
    output_path: str,
    baseline_mode: str = "preserve",
    baseline_path: str | None = None,
) -> dict[str, Any]:
    """Generate the public JSON snapshot from the local database.

    `baseline_mode` chooses the public set:

    * ``strict`` - the original rule only. The public set is the canonical
      visibility predicate minus the deadline rule: a record whose deadline
      has passed is excluded from the snapshot entirely. This is the
      invariant the backend suite and the parity verifier are written
      against, and it stays available unchanged.
    * ``preserve`` (default) - strict, plus published-baseline protection.
      Every record the deployed snapshot already serves stays published
      unless the database now excludes it explicitly (status closed,
      archived, or quarantined). Records the deadline rule would hide stay
      published and are labelled ``closed`` by the derived status, so the
      catalogue shows the honest state instead of removing a record nobody
      reviewed for removal. Use this mode when publishing research into an
      existing catalogue: without it, a research pass that writes past
      deadline dates silently shrinks the public set - measured at 622 to
      470 records on the 2026-10-11 publication - which is a catalogue
      deletion nobody asked for, and which loses the enrichment along with
      the records.

    `baseline_path` defaults to `output_path`: the artifact this run
    replaces is the baseline this run protects.
    """
    if baseline_mode not in ("preserve", "strict"):
        raise SystemExit(f"Unknown baseline mode: {baseline_mode!r} (use preserve|strict)")
    # Checked before connecting. `sqlite3.connect` happily creates an empty
    # database at the path, so a typo in the argument would otherwise succeed
    # and then fail several steps later with "no such table: scholarships",
    # pointing at the schema rather than at the wrong path.
    if not Path(db_path).is_file():
        raise SystemExit(
            f"Snapshot source not found: {db_path}\n"
            "Pass the SQLite database as the first argument, or create "
            "backend/scholarzone.db."
        )

    if baseline_mode == "preserve" and baseline_path is None:
        baseline_path = output_path
    baseline_ids = set(_load_baseline_ids(baseline_path)) if baseline_mode == "preserve" else set()

    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        _assert_inputs(db_path, cursor)
        _require_no_null_visibility(cursor)

        # All counts are read from the database. None of them are literals.
        def scalar(sql: str) -> int:
            cursor.execute(sql)
            return int(cursor.fetchone()[0])

        counts = {
            "source": scalar("SELECT COUNT(*) FROM scholarships"),
            "closed": scalar("SELECT COUNT(*) FROM scholarships WHERE status = 'closed'"),
            "archived": scalar("SELECT COUNT(*) FROM scholarships WHERE is_archived = 1"),
            "quarantined": scalar(
                "SELECT COUNT(*) FROM scholarships WHERE verification_status = 'quarantined'"
            ),
            # The excluded union accounts for overlaps: a record that is both
            # closed and archived is one excluded row, not two, which is why
            # the sum of the three buckets above is larger than this figure.
            # Recomputed below as the exact complement of the public set, so
            # the header cannot disagree with the records it describes.
            "excluded_union": scalar(
                "SELECT COUNT(*) FROM scholarships "
                "WHERE status = 'closed' OR is_archived = 1 "
                "OR verification_status = 'quarantined'"
            ),
        }
        today = date.today()

        # The rows the stored predicate publishes, and which of them the
        # catalogue's own deadline rule would call closed. The predicate set is
        # what the catalogue would serve today; the deadline set is the derived
        # closure the API reports.
        cursor.execute(
            """
            SELECT id, deadline_date FROM scholarships
            WHERE status != 'closed'
              AND is_archived = 0
              AND verification_status != 'quarantined'
            """
        )
        predicate_ids: set[int] = set()
        deadline_passed: set[int] = set()
        for row in cursor.fetchall():
            rid = int(row["id"])
            predicate_ids.add(rid)
            deadline = _coerce_date(row["deadline_date"])
            if deadline is not None and deadline < today:
                deadline_passed.add(rid)

        # Records excluded by the evidence rather than by the deadline rule:
        # a baseline record that has since been closed, archived or quarantined
        # is removed with its reason recorded, not protected from it.
        explicit_ids = {
            int(row[0])
            for row in cursor.execute(
                "SELECT id FROM scholarships "
                "WHERE status = 'closed' OR is_archived = 1 "
                "OR verification_status = 'quarantined'"
            )
        }
        baseline_conflict = baseline_ids & explicit_ids

        # The deadline rule hides what the predicate publishes and whose
        # deadline has gone, EXCEPT for records the deployed snapshot already
        # serves: those stay published and labelled closed, so publishing
        # research cannot quietly remove a listing no one reviewed.
        deadline_excluded = deadline_passed - baseline_ids
        public_ids_set = (predicate_ids | baseline_ids) - deadline_excluded - explicit_ids

        counts["baseline_records"] = len(baseline_ids)
        counts["baseline_preserved"] = len(deadline_passed & baseline_ids)
        counts["baseline_removed"] = len(baseline_conflict)
        counts["newly_public"] = len(baseline_ids and (public_ids_set - baseline_ids))
        counts["deadline_passed"] = len(deadline_excluded)
        counts["public"] = len(public_ids_set)
        counts["excluded_union"] = counts["source"] - counts["public"]
        _reconcile(counts)

        # The exported rows, ordered by id so the export is byte-for-byte
        # reproducible for a given database. With baseline preservation the
        # set also carries the baseline records the deadline rule would hide;
        # those are labelled closed by the derived status, so membership and
        # the honest state stay consistent with each other.
        ordered_ids = sorted(public_ids_set)
        if ordered_ids:
            id_list = ", ".join(str(rid) for rid in ordered_ids)
            cursor.execute(
                f"SELECT * FROM scholarships WHERE id IN ({id_list}) ORDER BY id"
            )
            rows = cursor.fetchall()
        else:
            rows = []

        if {int(row["id"]) for row in rows} != public_ids_set:
            raise AssertionError("Public record query does not match the computed public set.")

        scholarships = [
            _build_public_record(dict_from_row(cursor, row), today) for row in rows
        ]
        public_ids = [record["id"] for record in scholarships]

        # Orderings, computed from the same rows by the same rule the live
        # list uses. Two of the repository's sort keys (`created_at` for
        # recently-added, the legacy `is_verified` for recommended/default) are
        # not public fields, so this is what keeps the fallback's order equal
        # to the API's order without widening the public schema.
        sort_orders = _build_sort_orders(cursor, public_ids)

        # Statistics are derived from the records actually exported, using the
        # same predicates the count intelligence layer publishes, so the two
        # cannot disagree about the same dataset.
        total = len(scholarships)
        countries = len({s["country"] for s in scholarships if s["country"]})
        open_count = sum(1 for s in scholarships if s["status"] == "open")
        closing_soon = sum(1 for s in scholarships if s["status"] == "closing-soon")
        upcoming = sum(1 for s in scholarships if s["status"] == "upcoming")
        verified_active = sum(1 for s in scholarships if s["verified"])
        with_image = sum(1 for s in scholarships if s["image_url"])
        with_official_source = sum(1 for s in scholarships if s["official_source"])
        # The published `fully_funded` statistic uses the broad substring
        # definition, which is what the count intelligence layer uses
        # (catalogue.py). The ordering uses exact equality. That disagreement
        # exists inside the API itself; it is preserved deliberately here so
        # the statistic keeps matching the API's statistic.
        fully_funded = sum(
            1
            for s in scholarships
            if (s["funding"] or "").lower().find("fully funded") != -1
            and "partial" not in (s["funding"] or "").lower()
        )

        # The statistic is computed from the exported `verified` field, so these
        # two must agree by construction. Asserted, because if they ever stop
        # agreeing the header would describe a dataset the file does not hold.
        assert verified_active == sum(1 for s in scholarships if s["verified"])

        stats = {
            "total": total,
            "countries": countries,
            "open": open_count,
            "closing_soon": closing_soon,
            "upcoming": upcoming,
            "verified_active": verified_active,
            "fully_funded": fully_funded,
            "with_image": with_image,
            "with_official_source": with_official_source,
        }

        # The values the filter controls can actually select, taken from the
        # records that were exported.
        #
        # The directory's country, degree, funding, status and deadline-month
        # controls were hardcoded lists. Against this catalogue that meant: a
        # "Country" menu of four entries out of 74 real ones; a "Degree" menu
        # whose three entries matched 1, 3 and 1 records while the values most of
        # the catalogue actually holds were absent; and a "Funding" menu of one
        # entry out of 88.
        #
        # A control that cannot match is worse than a missing one: it presents
        # itself as working and returns nothing. A URL such as
        # ?country=Japan made the contradiction plain - the results were Japan,
        # and the menu read "All countries", because Japan was not an option and
        # the browser fell back to the first one.
        #
        # Under strict visibility the status menu deliberately omits `closed`,
        # because no published record can ever be closed. Under baseline
        # preservation, records the deadline rule closed are published - and
        # labelled - so `closed` becomes a selectable status that really does
        # match records. The menu therefore describes this catalogue rather
        # than an abstract one.
        filter_options = {
            "countries": sorted({s["country"] for s in scholarships if s["country"]}),
            "degrees": sorted({s["degree"] for s in scholarships if s["degree"]}),
            "funding_types": sorted({s["funding"] for s in scholarships if s["funding"]}),
            "statuses": sorted({s["status"] for s in scholarships if s["status"]}),
            "deadline_months": sorted(
                {int(s["deadline_date"][5:7]) for s in scholarships if s["deadline_date"]}
            ),
        }

        snapshot = {
            "meta": {
                "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "source_database": Path(db_path).name,
                "source_record_count": counts["source"],
                "public_record_count": total,
                # What was excluded, by bucket. `deadline_passed` is the derived
                # bucket: records the stored status left open but whose deadline
                # has gone, which the catalogue would report as closed. It is
                # named in the header so its size is visible rather than
                # becoming a quiet difference between the header and the
                # records.
                "excluded": {
                    "closed": counts["closed"],
                    "archived": counts["archived"],
                    "quarantined": counts["quarantined"],
                    "deadline_passed": counts["deadline_passed"],
                },
                "excluded_union": counts["excluded_union"],
                "deadline_passed": counts["deadline_passed"],
                # The published-baseline protection this run applied. Recorded
                # so the published count's provenance is auditable rather than
                # implied: which artifact the baseline was, its exact ID set,
                # how many records stayed published that strict visibility
                # would have hidden, and whether any baseline record was
                # removed by an explicit exclusion (the only allowed way for a
                # published record to disappear). The ID set is embedded
                # because the parity verifier has to be able to recompute the
                # expected public set from the database plus the declared
                # baseline, never from the snapshot's own records.
                "baseline": {
                    "mode": baseline_mode,
                    "source": Path(baseline_path).name if baseline_path else None,
                    "baseline_records": counts["baseline_records"],
                    "baseline_ids": sorted(baseline_ids),
                    "baseline_preserved": counts["baseline_preserved"],
                    "baseline_removed": counts["baseline_removed"],
                    "newly_public": counts["newly_public"],
                },
                "status_derived_at": today.isoformat(),
                "schema_version": "2.0",
                "visibility_predicate": (
                    "status != closed AND is_archived = false "
                    "AND verification_status != quarantined"
                ),
                # Selectable values, so the filter menus describe this catalogue
                # rather than a smaller one.
                "filter_options": filter_options,
                # Ordered ID lists, one per sort mode, so the fallback returns
                # the live ordering without exposing the internal columns the
                # ordering is derived from.
                "sort_orders": sort_orders,
                "sort_order_modes": sorted(sort_orders),
            },
            "stats": stats,
            "scholarships": scholarships,
        }

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        with open(output, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)

        return snapshot
    finally:
        # Closed on every path, including the SystemExit and AssertionError
        # paths above, so a failed run cannot leak a database handle.
        conn.close()


if __name__ == "__main__":
    # Default paths
    args = sys.argv[1:]
    baseline_mode = "preserve"
    baseline_path = None
    if args and args[0] in ("--strict",):
        # The original rule alone: no published-baseline protection. Use it
        # deliberately, when the intent is to publish exactly what the
        # visibility predicate serves.
        baseline_mode = "strict"
        args = args[1:]
    elif args and args[0] == "--baseline":
        # Name the artifact the publication must protect, when it is not the
        # one this run replaces - e.g. re-deriving a publication whose earlier
        # snapshot has already been committed on this branch.
        if len(args) < 2:
            raise SystemExit("--baseline needs a path to the snapshot to protect.")
        baseline_path = args[1]
        args = args[2:]
    db_path = args[0] if args else "backend/scholarzone.db"
    output_path = args[1] if len(args) > 1 else "frontend/public/scholarships-snapshot.json"

    print(f"Generating snapshot from {db_path} (baseline mode: {baseline_mode})...")
    snapshot = generate_snapshot(
        db_path, output_path, baseline_mode=baseline_mode, baseline_path=baseline_path
    )
    meta = snapshot["meta"]
    baseline = meta["baseline"]
    print(f"Generated {output_path}")
    print(f"  Public scholarships: {meta['public_record_count']}")
    print(
        "  Baseline: "
        f"{baseline['baseline_records']} records, "
        f"{baseline['baseline_preserved']} preserved past their deadline "
        f"(labelled closed), {baseline['baseline_removed']} removed by an "
        f"explicit exclusion, {baseline['newly_public']} newly public"
    )
    print(f"  Stats: {snapshot['stats']}")
