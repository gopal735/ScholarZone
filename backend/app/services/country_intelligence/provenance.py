"""Provenance typing for every researched figure.

The failure this module exists to prevent is a number with no provenance reaching
a student who will make a life decision on it. A country cost figure that nobody
checked, from nobody in particular, for an unknown year, is worse than no figure
at all, because it looks exactly as trustworthy as one that was read off an
official page last month.

So every researched value carries a ``value_status`` and, where one can honestly
be given, at least one source id. There is no "bare number" representation in this
package: a value that has not been typed is not published.

## Why ``value_status`` is part of the data and not a badge added at render time

A single scalar cannot carry this. "€11,904 blocked account" is a hard legal
threshold, and "€1,600 Munich rent" is one person's crowdsourced report. They may
be the same number. Only the status distinguishes them, so it travels with the
value, is validated with it, and is rendered next to it.

``UNKNOWN`` is a real published state. A cost figure that could not be sourced is
rendered as "not established" with the reason attached, never as ``0`` and never
omitted silently - an absent field and a zero are different claims, and only one
of them is true.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping

#: The complete set of statuses a researched figure may carry.
#:
#: Ordered from strongest to weakest evidence. The order is meaningful: it is the
#: order a reader should trust the figures in.
#:
#: This tuple is the **canonical vocabulary**. Nothing outside it may appear in a
#: stored corpus file: ingestion normalises research vocabulary into these names,
#: and the validator rejects anything that is not one of them. One vocabulary in
#: the stored data is what lets a query or a test ask "is this official?" and get
#: a real answer instead of matching against spelling variants.
#:
#: ``OFFICIAL_REGIONAL_BODY`` is the one category added for this corpus rather
#: than being an alias of something existing. It exists because a genuine and
#: very common source has no honest home among the others: a directive or
#: decision of a supra-national legislature - the European Union, the EEA, the
#: EFTA, the UK devolved administrations. Those bodies are not a national
#: government, not a national statistics office, and emphatically not a
#: university. Folding them into ``OFFICIAL_GOVERNMENT`` would assert a national
#: authority that does not exist, and a reader checking the source would find a
#: Brussels regulation where the label promised a ministry. It was added as its
#: own type because it is a real class of source, not because validation needed
#: another name to pass.
#:
#: Four states were added when the audit contract was completed. They are not
#: interchangeable with the ones above, and the distinction matters:
#:
#: ``ESTIMATE``
#:     A value exists and is published, but the evidence itself qualifies it as an
#:     approximation - a survey, a modelled figure, a representative figure
#:     standing in for a city that publishes no official one. The value is real;
#:     its precision is not. It stays a separate status from ``UNVERIFIED``,
#:     which means no source was read at all.
#:
#: ``CONFLICTING``
#:     Two or more credible sources materially disagree and no authoritative source
#:     resolves it. This status **carries no single value**: the number goes in
#:     ``conflicting`` with every alternative preserved. An average of two
#:     disagreeing official figures is a figure no source published, and
#:     publishing one would invent the very authority the conflict lacks.
#:
#: ``REFUSED``
#:     The system deliberately declines to calculate or publish, because a
#:     contract condition failed - gross income offered for a break-even
#:     calculation, a missing FX rate, a unit mismatch, a forbidden inference. It
#:     carries a reason and names what was required. It is emphatically **not**
#:     ``UNKNOWN``: ``UNKNOWN`` says nobody established the value, ``REFUSED``
#:     says the system saw the inputs and declined. Refusing is a correctness
#:     result, not a failure to look.
#:
#: ``STALE``
#:     Deliberately **not** in this tuple. Staleness is orthogonal to
#:     evidence quality: a figure read off a ministry page can be official *and*
#:     out of date, and forcing it to choose one would make "the 2019 fee, from
#:     the ministry, still officially published" inexpressible. It lives in
#:     :data:`FRESHNESS` instead, so ``OFFICIAL_GOVERNMENT`` + ``STALE`` is a
#:     representable and honest state.
VALUE_STATUS = (
    "OFFICIAL_GOVERNMENT",
    "OFFICIAL_REGIONAL_BODY",
    "OFFICIAL_STATISTICS",
    "UNIVERSITY_OFFICIAL",
    "INSTITUTIONAL_REPORT",
    "CROWDSOURCED",
    "AGGREGATOR",
    "ESTIMATE",
    "DERIVED",
    "CONFLICTING",
    "UNVERIFIED",
    "REFUSED",
    "UNKNOWN",
)

#: How current a claim's evidence is. Orthogonal to :data:`VALUE_STATUS`.
#:
#: ``CURRENT``
#:     Within the configured freshness threshold of the reference date.
#: ``STALE``
#:     Older than the threshold. Still published, still attributed, but the
#:     figure can no longer be presented as current without saying so.
#: ``UNDATED``
#:     The evidence carries no usable date, so its currency cannot be
#:     established. This is deliberately **not** ``CURRENT``. A figure whose
#:     evidence cannot be dated must not pass as fresh just because nobody
#:     checked; the honest answer to "is this current?" when the source has no
#:     date is "unknowable", and reporting that as fresh is the silent lie this
#:     whole module exists to prevent.
FRESHNESS = ("CURRENT", "STALE", "UNDATED")

#: Research spellings for :data:`FRESHNESS`.
FRESHNESS_ALIASES: dict[str, str] = {
    "FRESH": "CURRENT",
    "UP_TO_DATE": "CURRENT",
    "UPTODATE": "CURRENT",
    "RECENT": "CURRENT",
    "OUT_OF_DATE": "STALE",
    "EXPIRED": "STALE",
    "SUPERSEDED": "STALE",
    "NO_DATE": "UNDATED",
    "UNDATED_EVIDENCE": "UNDATED",
}

#: Evidence older than this is reported stale. Applied against an explicitly
#: supplied reference date, never an implicit system clock, so that "is this
#: stale?" is a pure function of the data and the answer cannot change between
#: two runs of the same corpus.
#:
#: Two years, not one. An annual fee schedule or a visa threshold does not go
#: stale the moment a new year starts - it becomes misleading when nobody has
#: checked in two cycles and the number may no longer be the one being charged.
#: The single source of truth for this constant: the auditor and the contract
#: tests both read it from here rather than restating it.
DEFAULT_STALE_AFTER_DAYS = 730


def normalise_freshness(value: Any) -> str | None:
    """Canonical freshness for a research spelling, or ``None`` if unusable."""
    if not isinstance(value, str):
        return None
    collapsed = re.sub(r"[\s\-]+", "_", value.strip()).upper()
    resolved = FRESHNESS_ALIASES.get(collapsed, collapsed)
    return resolved if resolved in FRESHNESS else None

#: Spellings seen in research output that mean an existing status but are not that
#: spelling. Resolved on load, and every resolution is reported as a warning
#: rather than applied silently.
#:
#: This exists because a mangled spelling of a real status is otherwise
#: indistinguishable from an invented one, and the two need opposite handling. A
#: researcher who writes "OFFICIAL_GOVENMENT" has made a typo and their figure is
#: probably fine; a researcher who writes "TRUSTED_SOURCE" has made a claim the
#: schema does not recognise and their figure should not ship. Keeping typos here
#: and unknown statuses rejected separates those two cases without guessing.
#:
#: Keys are normalised with :func:`normalise_status_vocabulary` before lookup, so
#: an alias written "official_university" resolves as readily as one written in
#: capitals. These are **ingest aliases**: an accepted input spelling that is
#: rewritten to one canonical name. They are not themselves publishable.
VALUE_STATUS_ALIASES: dict[str, str] = {
    # Typos observed in real research output.
    "OFFICIAL_GOVERNEMENT": "OFFICIAL_GOVERNMENT",
    "OFFICIAL_GOVERNUMENT": "OFFICIAL_GOVERNMENT",
    "OFFICIAL_GOVERNENT": "OFFICIAL_GOVERNMENT",
    "OFFICIAL_GOVERNMENT": "OFFICIAL_GOVERNMENT",
    "OFFICIAL_GOVERMENT": "OFFICIAL_GOVERNMENT",
    "OFFICIAL_GOVERNMENT_PLACEHOLDER": "OFFICIAL_GOVERNMENT",
    "OFFICIAL_STATISTIC": "OFFICIAL_STATISTICS",
    # The research vocabulary this corpus was actually written in. "OFFICIAL_*
    # family first" is the natural phrasing for a researcher and the opposite of
    # the canonical "noun first" ordering, so these two appear in real output.
    "OFFICIAL_UNIVERSITY": "UNIVERSITY_OFFICIAL",
    "OFFICIAL_REGIONAL": "OFFICIAL_REGIONAL_BODY",
    "REGIONAL_BODY": "OFFICIAL_REGIONAL_BODY",
    # Plain-language reductions.
    "GOVERNMENT": "OFFICIAL_GOVERNMENT",
    "UNIVERSITY": "UNIVERSITY_OFFICIAL",
}


def normalise_status_vocabulary(status: Any) -> str:
    """Canonical name for a research spelling of a status, or the spelling itself.

    Used at both ingest and validation so a figure cannot pass load-time
    validation and then fail to be read back - the reason
    :func:`parse_claim` calls this rather than a bare dict lookup.

    Matching is case- and separator-insensitive (``"official university"``,
    ``"Official-University"`` and ``"OFFICIAL_UNIVERSITY"`` are one spelling).
    That tolerance is safe precisely because it only ever maps a known alias onto
    a canonical name: an unrecognised string is returned unchanged and still
    rejected by the enum check, so widening the normalisation cannot admit a new
    claim type.
    """
    if not isinstance(status, str):
        return status
    collapsed = re.sub(r"[\s\-]+", "_", status.strip()).upper()
    return VALUE_STATUS_ALIASES.get(collapsed, status)


#: The canonical vocabulary for **where a source was published**.
#:
#: Deliberately a separate list from :data:`VALUE_STATUS`. They answer different
#: questions and must not be merged. ``value_status`` is a claim about how well
#: the evidence supports a figure; ``source_type`` is a fact about a publisher.
#: A commercial aggregator can host a figure that a careful researcher still
#: judges unsupported (``UNVERIFIED``), and an official statistics office
#: publishes both numbers the analyst trusts and methods they would not use.
#: Collapsing the two would force one of those truths to be denied.
#:
#: ``DERIVED``, ``UNVERIFIED`` and ``UNKNOWN`` are absent because they describe
#: epistemic states of a *claim*, not places a document can be published from.
#: There is no such thing as a "derived source".
SOURCE_TYPES: tuple[str, ...] = (
    "OFFICIAL_GOVERNMENT",
    "OFFICIAL_REGIONAL_BODY",
    "OFFICIAL_STATISTICS",
    "UNIVERSITY_OFFICIAL",
    "INSTITUTIONAL_REPORT",
    "CROWDSOURCED",
    "AGGREGATOR",
    "MEDIA",
)

#: Research spellings for :data:`SOURCE_TYPES`, resolved on ingest to a canonical
#: name. Same case/separator tolerance as :func:`normalise_status_vocabulary`, and
#: the same safety argument: an unrecognised string is returned unchanged and
#: still rejected, so this map can widen without admitting a new claim type.
SOURCE_TYPE_ALIASES: dict[str, str] = {
    "OFFICIAL_GOVERNEMENT": "OFFICIAL_GOVERNMENT",
    "OFFICIAL_GOVERNUMENT": "OFFICIAL_GOVERNMENT",
    "OFFICIAL_GOVERNENT": "OFFICIAL_GOVERNMENT",
    "OFFICIAL_GOVERMENT": "OFFICIAL_GOVERNMENT",
    "OFFICIAL_GOVERNMENT_PLACEHOLDER": "OFFICIAL_GOVERNMENT",
    "OFFICIAL_UNIVERSITY": "UNIVERSITY_OFFICIAL",
    "OFFICIAL_REGIONAL_BODY": "OFFICIAL_REGIONAL_BODY",
    "OFFICIAL_REGIONAL": "OFFICIAL_REGIONAL_BODY",
    "REGIONAL_BODY": "OFFICIAL_REGIONAL_BODY",
    "OFFICIAL_STATISTIC": "OFFICIAL_STATISTICS",
    "GOVERNMENT": "OFFICIAL_GOVERNMENT",
    "UNIVERSITY": "UNIVERSITY_OFFICIAL",
    "INSTITUTIONAL": "INSTITUTIONAL_REPORT",
    "OFFICIAL_NEWS": "MEDIA",
    "PRESS": "MEDIA",
    "NEWS": "MEDIA",
    "COMMERCIAL": "AGGREGATOR",
}

#: Source types that are **not** an official or authoritative publisher.
#:
#: This set exists to enforce one rule that no amount of careful reading of a
#: claim can enforce for us: a secondary source must never be labelled official.
#: The realistic failure is a researcher finding a reputable newspaper that
#: quoted a ministry, tagging the figure ``OFFICIAL_GOVERNMENT``, and the tag
#: outliving the scrutiny - the student then sees a hard legal threshold
#: presented as primary law and cannot tell it is a journalist's reading of it.
#: Cross-checking the claim's status against its sources' types catches that at
#: validation time, where it can still be corrected.
NON_OFFICIAL_SOURCE_TYPES = frozenset({"CROWDSOURCED", "AGGREGATOR", "MEDIA"})

#: Source types that may back a figure asserted as official.
OFFICIAL_SOURCE_TYPES = frozenset(
    set(SOURCE_TYPES) - NON_OFFICIAL_SOURCE_TYPES
)

_bad_source_aliases = sorted(
    {t for t in SOURCE_TYPE_ALIASES.values() if t not in SOURCE_TYPES}
)
assert not _bad_source_aliases, (
    f"SOURCE_TYPE_ALIASES points at unknown source types: {_bad_source_aliases}"
)


def normalise_source_type(value: Any) -> str | None:
    """Canonical source type for a research spelling, or ``None`` if unusable.

    Returns ``None`` for anything that is not a recognised source type, including
    ``None`` itself, so a caller can treat "no source type declared" and "source
    type declared but unrecognised" the same way: the source cannot be used to
    support an official claim.
    """
    if not isinstance(value, str):
        return None
    collapsed = re.sub(r"[\s\-]+", "_", value.strip()).upper()
    resolved = SOURCE_TYPE_ALIASES.get(collapsed, collapsed)
    return resolved if resolved in SOURCE_TYPES else None

#: Statuses that assert a figure was actually observed somewhere. Each one needs
#: at least one source id, or the figure is an assertion with no evidence.
_EVIDENCE_REQUIRED = frozenset(
    {
        "OFFICIAL_GOVERNMENT",
        "OFFICIAL_REGIONAL_BODY",
        "OFFICIAL_STATISTICS",
        "UNIVERSITY_OFFICIAL",
        "INSTITUTIONAL_REPORT",
        "CROWDSOURCED",
        "AGGREGATOR",
        "ESTIMATE",
        "CONFLICTING",
        "UNVERIFIED",
    }
)

#: Human phrasing for each status. Used verbatim in the API so that the wording a
#: student reads is defined once, next to the rule it is describing, and cannot
#: drift between the API and the interface.
VALUE_STATUS_LABELS: dict[str, str] = {
    "OFFICIAL_GOVERNMENT": "Government source",
    "OFFICIAL_REGIONAL_BODY": "Regional or supranational body",
    "OFFICIAL_STATISTICS": "National statistics",
    "UNIVERSITY_OFFICIAL": "Published by the university",
    "INSTITUTIONAL_REPORT": "Institutional report",
    "CROWDSOURCED": "Crowlsourced data",
    "AGGREGATOR": "Commercial aggregator",
    "ESTIMATE": "Estimate - approximate figure",
    "DERIVED": "Calculated from other published figures",
    "CONFLICTING": "Credible sources disagree",
    "UNVERIFIED": "Unverified - secondary source only",
    "REFUSED": "Not calculated - a required condition failed",
    "UNKNOWN": "Not established",
}

#: Freshness wording, defined once beside the rule that produces it.
FRESHNESS_LABELS: dict[str, str] = {
    "CURRENT": "Within the freshness threshold",
    "STALE": "Older than the freshness threshold",
    "UNDATED": "Evidence carries no usable date",
}

#: Asserted rather than trusted. A label map that is missing a status would leave
#: that status rendering with no disclosure, which is the one failure this whole
#: module exists to prevent - and it would fail silently, in the interface, for
#: exactly one kind of figure.
_missing_labels = sorted(set(VALUE_STATUS) - set(VALUE_STATUS_LABELS))
_extra_labels = sorted(set(VALUE_STATUS_LABELS) - set(VALUE_STATUS))
assert not _missing_labels, f"value_status_labels is missing labels for: {_missing_labels}"
assert not _extra_labels, f"value_status_labels has labels for unknown statuses: {_extra_labels}"

#: Alias targets are asserted against the enum for the same reason: an alias that
#: resolves to a status the validator does not know would fail at serve time,
#: long after it appeared to work at load time.
_bad_aliases = sorted({t for t in VALUE_STATUS_ALIASES.values() if t not in VALUE_STATUS})
assert not _bad_aliases, f"VALUE_STATUS_ALIASES points at unknown statuses: {_bad_aliases}"

#: Statuses that may be shown as a figure without a caveat attached to them. Every
#: other status must be disclosed wherever the number appears. ``UNVERIFIED`` is
#: not in this set, which is the whole difference between it and an official
#: figure.
DISCLOSURE_REQUIRED = frozenset(
    {
        "CROWDSOURCED",
        "AGGREGATOR",
        "ESTIMATE",
        "DERIVED",
        "CONFLICTING",
        "UNVERIFIED",
        "REFUSED",
        "UNKNOWN",
    }
)

#: Statuses that publish no single number, whatever else they carry.
#:
#: ``UNKNOWN`` and ``REFUSED`` carry a reason; ``CONFLICTING`` carries several
#: values. All three are excluded from any "this is the figure" reading, which is
#: what keeps an unhandled conflict from being formatted as an average.
_VALUELESS_STATUSES = frozenset({"UNKNOWN", "REFUSED", "CONFLICTING"})

#: How an income figure relates to tax. ``gross`` is before tax and social
#: insurance; ``net`` is take-home. Only ``net`` may be used to repay a cost.
INCOME_BASIS = frozenset({"gross", "net"})


class ClaimError(ValueError):
    """A researched figure failed validation. Never raised for absent data."""


def resolve_freshness(
    as_of: str | None,
    *,
    reference_date: str | date | None = None,
    stale_after_days: int = DEFAULT_STALE_AFTER_DAYS,
    retrieved_at: str | None = None,
) -> str:
    """Determine a claim's freshness from its own date metadata.

    This is a **pure function of its arguments**. It reads no clock: the
    reference date must be supplied, either by the caller or explicitly defaulted
    to ``today()`` at the boundary that wants wall-clock behaviour. Two runs over
    an unchanged corpus therefore cannot disagree about which figures are stale,
    which is the property the whole audit rests on - a staleness answer that
    changes between runs is not a finding, it is noise.

    ``as_of`` is preferred over ``retrieved_at`` because it is the date the
    evidence describes. A page fetched today may describe a 2019 tariff, and a
    fresh retrieval date must not disguise a decade-old number.

    Returns ``UNDATED`` when no usable date exists. This is the deliberate
    conservative default: a figure whose evidence cannot be dated is reported as
    undated rather than current, because "we could not tell" and "it is fresh" are
    different claims and only one is supported.
    """
    anchor = _parse_iso_date(as_of) or _parse_iso_date(retrieved_at)
    if anchor is None:
        return "UNDATED"
    reference = _parse_iso_date(reference_date) if reference_date is not None else date.today()
    if reference is None:
        return "UNDATED"
    return "STALE" if (reference - anchor).days > stale_after_days else "CURRENT"


def _parse_iso_date(value: Any) -> date | None:
    """Parse ``YYYY-MM-DD`` (optionally with a time part), or return ``None``.

    Deliberately not ``date.fromisoformat`` on the raw string: research output
    carries timestamps like ``2026-10-02T00:00:00Z`` and a few malformed values,
    and an unparseable date must yield ``UNDATED`` rather than raise in the
    middle of a corpus load.
    """
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", value.strip())
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


@dataclass(frozen=True)
class Claim:
    """One researched figure with its evidence attached.

    ``value`` is the headline figure and is ``None`` only when ``value_status`` is
    ``UNKNOWN``. The reverse also holds: a ``None`` value may not carry an evidence
    status, because "not established" is not the same claim as "established at
    €0".

    ``minimum``/``maximum`` carry the span of a range claim. Cost of living is a
    range, not a point: publishing only the mean of a rent distribution would tell
    a student budgeting for a year that they will pay exactly the average, which
    is the specific error that makes a "cost of living" figure useless. A range
    claim with an ``average`` but no ``minimum``/``maximum`` is therefore rejected.
    """

    value: Any
    currency: str | None = None
    per: str | None = None
    value_status: str = "UNKNOWN"
    source_ids: tuple[str, ...] = ()
    as_of: str | None = None
    note: str | None = None
    sample_size: int | None = None
    formula: str | None = None
    minimum: Any = None
    maximum: Any = None
    #: For income figures only, whether the number is gross or net. Carried in the
    #: data rather than assumed at the call site, because the difference is large
    #: enough to change an answer and small enough to be missed: in most European
    #: countries take-home pay is roughly 55-65% of gross, so a break-even
    #: calculation that treats gross as net understates the time to repay by
    #: roughly half. A claim with no ``basis`` is not usable as income.
    basis: str | None = None
    previous: Mapping[str, Any] | None = None
    #: Orthogonal freshness, see :data:`FRESHNESS`. ``None`` means the claim did
    #: not declare one; :func:`resolve_freshness` derives it from the date
    #: metadata rather than letting an undeclared claim pass as current.
    freshness: str | None = None
    #: Populated only for ``CONFLICTING`` claims. See :class:`ConflictingValue`.
    conflicting: tuple[ConflictingValue, ...] = ()
    #: Populated only for ``REFUSED`` claims. See :class:`Refusal`.
    refusal: Refusal | None = None
    #: Why a value is an estimate, required for ``ESTIMATE``.
    estimate_basis: str | None = None
    #: The date staleness is measured from, when the claim records one
    #: independently of ``as_of`` (``retrieved_at``, typically).
    freshness_reference: str | None = None
    #: For net-income claims: the circumstances the figure holds under. See
    #: :mod:`app.services.country_intelligence.net_income`. Opaque here and
    #: validated there, because a net figure is meaningless without it and a
    #: profile is a structured object rather than a field.
    net_income_profile: Mapping[str, Any] | None = None
    #: ``False`` when the claim was carried forward from hand-curated data whose
    #: verbatim extract is not archived, so it cannot be audited from the
    #: repository. See the ingester's carry-forward audit.
    evidence_archived: bool | None = None

    @property
    def is_known(self) -> bool:
        return self.value is not None

    @property
    def is_range(self) -> bool:
        return self.minimum is not None or self.maximum is not None

    @property
    def needs_disclosure(self) -> bool:
        return self.value_status in DISCLOSURE_REQUIRED

    @property
    def publishes_a_number(self) -> bool:
        """Whether this claim may be read as "this is the figure".

        ``CONFLICTING`` and ``REFUSED`` deliberately return ``False``. Both may
        carry structured detail, but neither states a single value, so a consumer
        that checks this cannot accidentally format a conflict as a number.
        """
        return self.value is not None and self.value_status not in _VALUELESS_STATUSES

    def to_dict(self) -> dict[str, Any]:
        """Publish shape.

        Unset fields are omitted rather than published as ``null``, so a client
        cannot mistake "this corpus did not record a currency" for "the currency
        is null". The one field always present is the status, because that is the
        disclosure.
        """
        payload: dict[str, Any] = {"value": self.value, "value_status": self.value_status}
        if self.is_range:
            payload["range"] = {"min": self.minimum, "max": self.maximum, "average": self.value}
        for key, attr in (
            ("currency", "currency"),
            ("per", "per"),
            ("as_of", "as_of"),
            ("note", "note"),
            ("sample_size", "sample_size"),
            ("formula", "formula"),
            ("basis", "basis"),
        ):
            value = getattr(self, attr)
            if value is not None:
                payload[key] = value
        if self.source_ids:
            payload["source_ids"] = list(self.source_ids)
        if self.previous:
            payload["previous"] = dict(self.previous)
        if self.freshness:
            payload["freshness"] = self.freshness
        if self.conflicting:
            payload["conflicting"] = [item.to_dict() for item in self.conflicting]
        if self.refusal is not None:
            payload["refusal"] = self.refusal.to_dict()
        if self.estimate_basis:
            payload["estimate_basis"] = self.estimate_basis
        if self.net_income_profile:
            payload["net_income_profile"] = dict(self.net_income_profile)
        if self.evidence_archived is not None:
            payload["evidence_archived"] = self.evidence_archived
        return payload


def check_official_source_claim(
    claim_status: str, source_types: Mapping[str, str | None], *, path: str
) -> None:
    """Reject a figure asserted as official that rests only on secondary sources.

    A claim marked ``OFFICIAL_GOVERNMENT``, ``OFFICIAL_STATISTICS``,
    ``OFFICIAL_REGIONAL_BODY`` or ``UNIVERSITY_OFFICIAL`` asserts that a primary
    source was read directly. If every source behind it is a newspaper, a
    commercial aggregator or a crowdsourced pool, that assertion is false - the
    figure may well be *correct*, and quite possibly was copied verbatim out of
    the article, but a reader shown the label cannot tell it apart from a figure
    read off the ministry page itself.

    Raising here rather than downgrading is deliberate. Silently downgrading to
    ``UNVERIFIED`` would publish a number whose provenance the researcher did not
    agree to, which is the same failure wearing a smaller hat. The country is
    excluded with the reason attached, and a human decides.

    **At least one** cited source must be primary, not all of them. The target
    failure is a claim resting only on secondary sources; a figure corroborated by
    both a newspaper and a ministry page is properly official, and rejecting it
    would be a false positive that quietly teaches a researcher to drop the
    cross-check.

    A source with no declared type, or one whose type is unrecognised, counts as
    non-official. An unlabelled source cannot be asserted to be primary.
    """
    if claim_status not in _OFFICIAL_ASSERTING_STATUSES:
        return

    declared = {source_id: source_type for source_id, source_type in source_types.items()}
    if any(
        source_type is not None and source_type in OFFICIAL_SOURCE_TYPES
        for source_type in declared.values()
    ):
        # At least one cited source is primary, so a primary source was read. A
        # figure cross-checked against a newspaper *and* a ministry page is
        # properly official, and rejecting it would be a false positive that
        # pressures a researcher to drop a useful corroboration.
        return

    offending = ", ".join(sorted(declared)) or "(none)"
    kinds = ", ".join(sorted({str(kind) for kind in declared.values()}))
    raise ClaimError(
        f"{path}: value_status {claim_status} asserts an official source, but no "
        f"source it cites is one. Cited: {offending} ({kinds}). An unlabelled or "
        f"secondary source cannot support an official claim. Either cite a primary "
        f"source directly and declare its source_type as one of "
        f"{', '.join(sorted(OFFICIAL_SOURCE_TYPES))}, or restate the figure with a "
        f"status that matches what was actually read."
    )


#: Statuses that assert a primary source was read directly, rather than merely
#: that the figure is well evidenced. Only these are subject to the
#: secondary-source gate above; ``INSTITUTIONAL_REPORT`` and ``CROWDSOURCED``
#: already say out loud where they came from.
_OFFICIAL_ASSERTING_STATUSES = frozenset(
    {
        "OFFICIAL_GOVERNMENT",
        "OFFICIAL_REGIONAL_BODY",
        "OFFICIAL_STATISTICS",
        "UNIVERSITY_OFFICIAL",
    }
)


def claim_unknown(reason: str) -> Claim:
    """A figure that could not be established, carrying why.

    The reason is mandatory. "Not established" without a reason tells a reader
    nothing and invites the reader to assume the figure was overlooked.
    """
    if not reason or not reason.strip():
        raise ClaimError("An UNKNOWN claim requires a reason.")
    return Claim(value=None, value_status="UNKNOWN", note=reason.strip())


def _coerce_sources(raw: Any) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        return (raw,)
    if isinstance(raw, (list, tuple)):
        return tuple(str(item) for item in raw if str(item))
    raise ClaimError(f"source_ids must be a list or string, got {type(raw).__name__}.")


@dataclass(frozen=True)
class ConflictingValue:
    """One credible source's figure inside a ``CONFLICTING`` claim.

    A conflict is only worth publishing if each side keeps its own source, value,
    unit and period. Reducing a conflict to its midpoint destroys the one thing
    that made it worth recording - that two bodies in authority genuinely
    disagree, which is itself the answer a student needs. "Bavaria is EUR 650" is
    false; "two Bavarian institutions publish EUR 500 and EUR 800 and no state
    rate exists" is true and actionable.
    """

    value: Any
    currency: str | None = None
    per: str | None = None
    source_ids: tuple[str, ...] = ()
    as_of: str | None = None
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"value": self.value}
        for key, attr in (
            ("currency", "currency"),
            ("per", "per"),
            ("as_of", "as_of"),
            ("note", "note"),
        ):
            value = getattr(self, attr)
            if value is not None:
                payload[key] = value
        if self.source_ids:
            payload["source_ids"] = list(self.source_ids)
        return payload


@dataclass(frozen=True)
class Refusal:
    """Why a value was not produced, and what would have been required.

    A refusal without a reason is indistinguishable from a bug, so ``reason`` is
    mandatory and ``required_input`` is carried wherever the failure names a
    specific missing input. These are returned to the student rather than logged:
    "I will not compute your repayment time from gross salary, because repayable
    income is take-home pay" is an answer, and hiding it behind an empty result
    teaches the student the tool is broken rather than careful.
    """

    reason: str
    required_input: str | None = None
    operation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"reason": self.reason}
        if self.required_input:
            payload["required_input"] = self.required_input
        if self.operation:
            payload["operation"] = self.operation
        return payload


def claim_refused(
    reason: str,
    *,
    required_input: str | None = None,
    operation: str | None = None,
) -> Claim:
    """A value the system declines to produce, carrying why.

    Deliberately distinct from :func:`claim_unknown`. ``UNKNOWN`` is "nobody
    established this"; ``REFUSED`` is "the system had what it needed and the
    contract forbade the answer". Collapsing them would hide a correctness
    decision behind an apparent gap in the research.
    """
    if not reason or not reason.strip():
        raise ClaimError("A REFUSED claim requires a reason.")
    return Claim(
        value=None,
        value_status="REFUSED",
        note=reason.strip(),
        refusal=Refusal(
            reason=reason.strip(),
            required_input=required_input,
            operation=operation,
        ),
    )


def parse_claim(raw: Any, *, path: str) -> Claim:
    """Validate and convert one researched figure.

    Alias resolution happens **here**, not in the corpus loader, and that placement
    is load-bearing. Validation and serving must agree: if the loader accepted a
    mangled status by rewriting it but the stored body kept the original spelling,
    then the figure would validate on load and fail when read back, and would be
    silently downgraded to "not established" at serve time. Resolving in one place
    means both paths see the same status.

    Raises ``ClaimError`` for anything that would publish an unprovenanced or
    self-contradictory figure. Callers are expected to catch it per country and
    exclude that country rather than fail the whole request: one malformed file in
    a corpus of thirty must not take the other twenty-nine offline.
    """
    raw = None if raw is None else dict(raw)
    if isinstance(raw, Mapping):
        status = normalise_status_vocabulary(raw.get("value_status", "UNKNOWN"))
        if isinstance(status, str) and status != raw.get("value_status"):
            raw["value_status"] = status

    if raw is None:
        raise ClaimError(f"{path}: expected a claim object, found null.")
    if not isinstance(raw, Mapping):
        raise ClaimError(f"{path}: expected an object, found {type(raw).__name__}.")

    status = normalise_status_vocabulary(raw.get("value_status", "UNKNOWN"))
    raw["value_status"] = status
    if status not in VALUE_STATUS:
        raise ClaimError(
            f"{path}: value_status {status!r} is not one of {', '.join(VALUE_STATUS)}."
        )

    value = raw.get("value")
    sources = _coerce_sources(raw.get("source_ids"))

    if status == "UNKNOWN":
        if value is not None:
            raise ClaimError(
                f"{path}: value_status UNKNOWN cannot carry a value; "
                f"found {value!r}. Either publish the value with a real status, "
                f"or drop the value and keep the reason."
            )
        return claim_unknown(str(raw.get("note") or raw.get("reason") or ""))

    if status == "REFUSED":
        # A refusal must say what it needed, not merely decline. A REFUSED claim
        # carrying a value would be a contradiction: refusing is a decision about
        # a value that was not produced.
        if value is not None:
            raise ClaimError(
                f"{path}: value_status REFUSED cannot carry a value; found "
                f"{value!r}. A refusal states that no value was produced."
            )
        refusal = raw.get("refusal")
        if not isinstance(refusal, Mapping):
            refusal = {"reason": raw.get("note") or raw.get("reason") or ""}
        return claim_refused(
            str(refusal.get("reason") or raw.get("note") or raw.get("reason") or ""),
            required_input=(
                refusal.get("required_input") if isinstance(refusal, Mapping) else None
            ),
            operation=refusal.get("operation") if isinstance(refusal, Mapping) else None,
        )

    if status == "CONFLICTING":
        # The whole point of this status is that no single value exists. Accepting
        # one here would let a caller publish the midpoint of a disagreement while
        # the label still reads "credible sources disagree", which is the exact
        # false precision the status was added to prevent.
        if value is not None:
            raise ClaimError(
                f"{path}: value_status CONFLICTING cannot carry a single value; "
                f"found {value!r}. Record each source's figure under 'conflicting' "
                f"so the disagreement survives. Averaging or choosing one would "
                f"invent a figure that no source published."
            )
        raw_alternatives = raw.get("conflicting")
        if not isinstance(raw_alternatives, (list, tuple)) or len(raw_alternatives) < 2:
            raise ClaimError(
                f"{path}: a CONFLICTING claim needs at least two credible figures "
                f"under 'conflicting'. A disagreement with one side is an "
                f"ordinary figure, not a conflict."
            )
        alternatives: list[ConflictingValue] = []
        for index, item in enumerate(raw_alternatives):
            if not isinstance(item, Mapping):
                raise ClaimError(
                    f"{path}: conflicting[{index}] must be an object, found "
                    f"{type(item).__name__}."
                )
            item_value = item.get("value")
            if item_value is None:
                raise ClaimError(
                    f"{path}: conflicting[{index}] has no value. Every side of a "
                    f"conflict must state the figure it is disputing."
                )
            item_sources = _coerce_sources(item.get("source_ids"))
            if not item_sources:
                raise ClaimError(
                    f"{path}: conflicting[{index}] has no source id. A conflict "
                    f"between unnamed sources cannot be audited and must not be "
                    f"published."
                )
            alternatives.append(
                ConflictingValue(
                    value=item_value,
                    currency=item.get("currency"),
                    per=item.get("per"),
                    source_ids=item_sources,
                    as_of=item.get("as_of"),
                    note=item.get("note"),
                )
            )
        claim = Claim(
            value=None,
            value_status="CONFLICTING",
            source_ids=tuple(
                dict.fromkeys(sid for item in alternatives for sid in item.source_ids)
            ),
            note=raw.get("note"),
            conflicting=tuple(alternatives),
        )
        return claim

    if value is None:
        raise ClaimError(
            f"{path}: value_status {status} requires a value. Absent data is "
            f"UNKNOWN, not a zero and not a null under an evidence status."
        )

    if status in _EVIDENCE_REQUIRED and not sources:
        raise ClaimError(
            f"{path}: value_status {status} requires at least one source id. "
            f"An observed figure with no source is an assertion, not a measurement."
        )

    if status == "DERIVED" and not raw.get("formula"):
        raise ClaimError(
            f"{path}: a DERIVED figure must name its formula. A derived number "
            f"whose arithmetic is unstated cannot be checked by anyone, including "
            f"its author."
        )

    # An estimate that does not say what makes it an estimate is indistinguishable
    # from a figure the researcher simply rounds. The basis is what lets a reader
    # judge the number, so it is required rather than optional.
    estimate_basis = raw.get("estimate_basis")
    if status == "ESTIMATE" and not estimate_basis:
        raise ClaimError(
            f"{path}: value_status ESTIMATE requires an estimate_basis stating "
            f"what makes the figure approximate. Without it the estimate reads "
            f"exactly like a fact, which is the outcome ESTIMATE exists to avoid."
        )

    previous = raw.get("previous")
    if previous is not None and not isinstance(previous, Mapping):
        raise ClaimError(f"{path}: previous must be an object when present.")

    minimum = raw.get("min")
    maximum = raw.get("max")
    if minimum is not None and not isinstance(minimum, (int, float)):
        raise ClaimError(f"{path}: range min must be numeric.")
    if maximum is not None and not isinstance(maximum, (int, float)):
        raise ClaimError(f"{path}: range max must be numeric.")
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ClaimError(
            f"{path}: range min {minimum} is greater than max {maximum}. "
            f"A reversed range is a transcription error, not a finding."
        )
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        low = minimum if minimum is not None else value
        high = maximum if maximum is not None else value
        if not (low <= value <= high):
            raise ClaimError(
                f"{path}: average {value} lies outside its own range "
                f"{low}-{high}."
            )

    sample_size = raw.get("sample_size")
    if sample_size is not None and not isinstance(sample_size, (int, float)):
        raise ClaimError(f"{path}: sample_size must be numeric when present.")

    basis = raw.get("basis")
    if basis is not None and basis not in INCOME_BASIS:
        raise ClaimError(
            f"{path}: basis {basis!r} is not one of {', '.join(sorted(INCOME_BASIS))}."
        )

    freshness = normalise_freshness(raw.get("freshness"))
    if raw.get("freshness") is not None and freshness is None:
        raise ClaimError(
            f"{path}: freshness {raw.get('freshness')!r} is not one of "
            f"{', '.join(FRESHNESS)}."
        )

    return Claim(
        value=value,
        currency=raw.get("currency"),
        per=raw.get("per"),
        value_status=status,
        source_ids=sources,
        as_of=raw.get("as_of"),
        note=raw.get("note"),
        sample_size=int(sample_size) if isinstance(sample_size, (int, float)) else None,
        formula=raw.get("formula"),
        minimum=minimum,
        maximum=maximum,
        basis=basis,
        previous=previous,
        freshness=freshness,
        estimate_basis=estimate_basis,
        freshness_reference=raw.get("retrieved_at"),
        net_income_profile=(
            dict(raw["net_income_profile"])
            if isinstance(raw.get("net_income_profile"), Mapping)
            else None
        ),
        evidence_archived=(
            raw["evidence_archived"]
            if isinstance(raw.get("evidence_archived"), bool)
            else None
        ),
    )


__all__ = [
    "DEFAULT_STALE_AFTER_DAYS",
    "FRESHNESS",
    "FRESHNESS_ALIASES",
    "FRESHNESS_LABELS",
    "NON_OFFICIAL_SOURCE_TYPES",
    "OFFICIAL_SOURCE_TYPES",
    "SOURCE_TYPES",
    "SOURCE_TYPE_ALIASES",
    "Claim",
    "ClaimError",
    "ConflictingValue",
    "DISCLOSURE_REQUIRED",
    "Refusal",
    "VALUE_STATUS",
    "VALUE_STATUS_ALIASES",
    "VALUE_STATUS_LABELS",
    "check_official_source_claim",
    "claim_refused",
    "claim_unknown",
    "normalise_freshness",
    "normalise_source_type",
    "normalise_status_vocabulary",
    "parse_claim",
    "resolve_freshness",
]