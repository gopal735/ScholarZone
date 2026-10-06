"""Merging the two planes into what a reader actually sees.

Three inputs, kept apart until the last moment:

* the **measured** catalogue counts, recomputed per request (:mod:`catalogue`)
* the **researched** corpus figures, curated and sourced (:mod:`corpus`)
* the **derived** arithmetic over both, with refusals (:mod:`derive`)

Nothing in this module invents a figure. Every number it returns either came out
of a query, came out of a file with a source attached, or came out of a named
formula over those two. Anything it could not obtain is absent with a reason, and
:func:`country_summary` reports the country's **data completeness** so the
interface can say which of the sections it is actually showing.

## Countries are not all in the same state, and the response says so

A country on the catalogue with no corpus file is a real situation: we hold
scholarships for it and have not researched its cost of living. Those two facts
belong together on one card - the scholarships are real and useful - but they
must not be presented as though both halves were researched. So a summary carries
``researched_sections`` and ``missing_sections``, and the interface renders the
researched parts with their provenance and leaves the rest explicitly absent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from . import COUNTRY_INTELLIGENCE_VERSION
from .catalogue import CountryCatalogue, measure_country_catalogue
from .corpus import SECTION_NAMES, CountryRecord, get_corpus
from .derive import (
    CITY_TIERS,
    DERIVATION_VERSION,
    REFUSAL_LABELS,
    STUDY_LEVELS,
    Derivation,
    derive_break_even,
    derive_living,
    derive_one_time_total,
    derive_roi,
    derive_total_investment,
    derive_tuition,
    find_claim,
    scholarship_coverage,
)
from .fx import FxUnavailable, get_fx_table
from .formulas import formula_contracts
from .provenance import (
    DEFAULT_STALE_AFTER_DAYS,
    FRESHNESS,
    FRESHNESS_LABELS,
    INCOME_BASIS,
    NON_OFFICIAL_SOURCE_TYPES,
    OFFICIAL_SOURCE_TYPES,
    SOURCE_TYPES,
    VALUE_STATUS,
    VALUE_STATUS_LABELS,
    parse_claim,
)
from .taxonomy import CODE_NOTES, display_name, flag_emoji


@dataclass(frozen=True)
class CountrySummary:
    """One country as a reader meets it on a card."""

    iso2: str
    name: str
    measured: Mapping[str, Any]
    researched_sections: tuple[str, ...]
    missing_sections: tuple[str, ...]
    headline: Mapping[str, Any]
    currency: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "iso2": self.iso2,
            "name": self.name,
            "flag": flag_emoji(self.iso2),
            "currency": self.currency,
            "code_note": CODE_NOTES.get(self.iso2),
            "measured": dict(self.measured),
            "researched_sections": list(self.researched_sections),
            "missing_sections": list(self.missing_sections),
            "headline": dict(self.headline),
        }


def _claim_payload(record: CountryRecord | None, path: tuple[str, ...]) -> dict[str, Any]:
    """Resolve one researched figure and publish it, or publish its absence.

    An unsourced path returns an explicit ``UNKNOWN`` payload with a reason rather
    than being omitted, so the interface can render "not established" in place.
    That keeps a gap visible instead of leaving a silent hole in the layout.
    """
    if record is None:
        return {
            "value": None,
            "value_status": "UNKNOWN",
            "note": "No country intelligence has been researched for this country yet.",
        }
    raw = find_claim(record.sections, path)
    if raw is None:
        return {
            "value": None,
            "value_status": "UNKNOWN",
            "note": f"Not researched: {'.'.join(path)}.",
        }
    try:
        return parse_claim(raw, path=".".join(path)).to_dict()
    except Exception as exc:  # a validated corpus cannot reach here, but never trust that
        return {"value": None, "value_status": "UNKNOWN", "note": f"Unusable corpus entry: {exc}"}


def _headline(record: CountryRecord | None, coverage: float | None) -> dict[str, Any]:
    """The four figures a country card leads with.

    Ordered the way a student actually decides: what will it cost, what might it
    pay, can I stay, and how confident is any of this.
    """
    return {
        # Bachelor's first: it is the level where tuition is genuinely paid.
        "tuition_bachelor": _claim_payload(
            record, ("education_costs", "tuition_fees", "public", "bachelor")
        ),
        "living_monthly_medium": _claim_payload(
            record, ("living_costs", "monthly_costs", "medium", "total")
        ),
        "starting_salary": _claim_payload(
            record, ("career", "average_starting_salary", "master")
        ),
        "post_study_work_months": _claim_payload(
            record, ("residency", "job_seeker_residence_permit", "duration")
        ),
        "scholarship_coverage_applied": coverage,
    }


def _sections_state(record: CountryRecord | None) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if record is None:
        return (), SECTION_NAMES
    researched = tuple(name for name in SECTION_NAMES if record.section(name))
    missing = tuple(name for name in SECTION_NAMES if not record.section(name))
    return researched, missing


def country_summary(
    iso2: str, measured: CountryCatalogue, record: CountryRecord | None
) -> CountrySummary:
    """Build one country card from both planes."""
    facts = measured.get(iso2)
    coverage, _ = scholarship_coverage(
        facts.fully_funded if facts else None, facts.scholarships if facts else None
    )
    researched, missing = _sections_state(record)
    return CountrySummary(
        iso2=iso2,
        name=(record.name if record else display_name(iso2)),
        measured=facts.to_dict() if facts else {},
        researched_sections=researched,
        missing_sections=missing,
        headline=_headline(record, coverage),
        currency=record.currency if record else None,
    )


def country_summaries(session) -> list[CountrySummary]:
    """Every country with at least one of: catalogue records, or research.

    A country that has no records and no research is omitted rather than rendered
    as an empty card: there is nothing to show and nothing to promise.
    """
    measured = measure_country_catalogue(session)
    corpus = get_corpus()

    codes = set(measured.by_country) | set(corpus.iso2_codes)
    summaries: list[CountrySummary] = []
    for iso2 in sorted(codes):
        record = corpus.get(iso2)
        facts = measured.get(iso2)
        if facts is None and record is None:
            continue
        summaries.append(country_summary(iso2, measured, record))
    return summaries


def country_detail(session, iso2: str) -> dict[str, Any] | None:
    """Everything known about one country, or ``None`` when it is unknown."""
    normalised = (iso2 or "").strip().upper()
    measured = measure_country_catalogue(session)
    corpus = get_corpus()
    record = corpus.get(normalised)
    facts = measured.get(normalised)

    if record is None and facts is None:
        return None

    researched, missing = _sections_state(record)
    coverage, coverage_reason = scholarship_coverage(
        facts.fully_funded if facts else None, facts.scholarships if facts else None
    )

    return {
        "country": {
            "iso2": normalised,
            "name": record.name if record else display_name(normalised),
            "flag": flag_emoji(normalised),
            "currency": record.currency if record else None,
            "code_note": CODE_NOTES.get(normalised),
            "european_union": bool(record and record.european_union),
            "schengen": bool(record and record.schengen),
            "researched_at": record.researched_at if record else None,
        },
        "measured": facts.to_dict() if facts else None,
        "researched_sections": list(researched),
        "missing_sections": list(missing),
        "headline": _headline(record, coverage),
        "sections": {
            name: record.section(name) for name in researched
        } if record else {},
        "sources": [source.to_dict() for source in record.sources] if record else [],
        "gaps": [gap.to_dict() for gap in record.gaps] if record else [],
        "measured_unattributed": [group.to_dict() for group in measured.unattributed],
        "reconciliation": measured.reconciliation(),
        "coverage": {"rate": coverage, "reason": coverage_reason},
    }


#: The comparison rows the tool offers, in display order.
#:
#: Each row names the corpus path it reads, so adding a row is adding data, not
#: adding code. Rows whose figure is absent for every selected country are
#: reported as unavailable rather than rendered as a row of "not established".
COMPARISON_ROWS: tuple[dict[str, Any], ...] = (
    {"key": "tuition_bachelor", "label": "Bachelor tuition (public, international)",
     "path": ("education_costs", "tuition_fees", "public", "bachelor"), "higher_is_better": False},
    {"key": "tuition_master", "label": "Master tuition (public, international)",
     "path": ("education_costs", "tuition_fees", "public", "master"), "higher_is_better": False},
    {"key": "living_low", "label": "Living cost, low-cost city",
     "path": ("living_costs", "monthly_costs", "low", "total"), "higher_is_better": False},
    {"key": "living_medium", "label": "Living cost, mid-cost city",
     "path": ("living_costs", "monthly_costs", "medium", "total"), "higher_is_better": False},
    {"key": "living_high", "label": "Living cost, high-cost city",
     "path": ("living_costs", "monthly_costs", "high", "total"), "higher_is_better": False},
    {"key": "blocked_account", "label": "Proof of funds required",
     "path": ("one_time_costs", "blocked_account"), "higher_is_better": False},
    {"key": "post_study_work", "label": "Post-study work permit",
     "path": ("residency", "job_seeker_residence_permit", "duration"), "higher_is_better": True},
    {"key": "salary_master", "label": "Master's starting salary",
     "path": ("career", "average_starting_salary", "master"), "higher_is_better": True},
)


def _currency_status(values: Mapping[str, Any]) -> dict[str, Any]:
    """Whether a comparison row's figures can legitimately be ranked against each other.

    Two paths out, and both are explicit:

    * **One currency** - comparable as-is.
    * **Several currencies with a sourced rate** - comparable after conversion, and
      the converted figures, the rate, its date and its direction are published
      alongside the originals. Nothing is converted silently.
    * **Several currencies with no sourced rate** - refused, with the currencies
      named. EUR 20,000 against GBP 18,000 is a comparison between two numbers and
      nothing else, and a lower number in a weaker currency is not a cheaper
      country.

    A refused row is still returned. Dropping it would hide real data; marking it
    is what stops a client sorting on it.
    """
    table = get_fx_table()
    currencies = sorted(
        {
            str(payload["currency"])
            for payload in values.values()
            if isinstance(payload, Mapping)
            and payload.get("value") is not None
            and payload.get("currency")
        }
    )

    if len(currencies) <= 1:
        return {"comparable": True, "currencies": currencies, "fx_required": False}

    if table is None:
        return {
            "comparable": False,
            "currencies": currencies,
            "fx_required": True,
            "refusal": (
                f"This row mixes currencies ({', '.join(currencies)}) and the corpus "
                f"holds no sourced exchange rate, so the figures are not numerically "
                f"comparable. No rate was assumed."
            ),
        }

    # Pivot on the base currency: it is the one both legs of every rate are
    # quoted against, so converting through it needs no pair of rates to be
    # combined and no rounding to compound.
    pivot = table.base
    converted: dict[str, Any] = {}
    missing: list[str] = []
    for code, payload in values.items():
        if not isinstance(payload, Mapping) or payload.get("value") is None:
            continue
        currency = str(payload.get("currency") or "")
        try:
            conversion = table.convert(float(payload["value"]), currency, pivot)
        except FxUnavailable as exc:
            missing.append(f"{code} ({currency or 'no currency'}): {exc}")
            continue
        converted[code] = conversion.to_dict()

    if missing:
        return {
            "comparable": False,
            "currencies": currencies,
            "fx_required": True,
            "refusal": (
                f"Some figures in this row cannot be converted to {pivot}: "
                + "; ".join(missing)
            ),
        }

    return {
        "comparable": True,
        "currencies": currencies,
        "fx_required": True,
        "pivot_currency": pivot,
        "converted": converted,
        "fx": {
            "source_id": table.source_id,
            "source_url": table.source_url,
            "publisher": table.publisher,
            "as_of": table.as_of,
            "base": table.base,
        },
    }


def compare_countries(session, iso2s: list[str]) -> dict[str, Any]:
    """A comparison matrix across the countries that can actually answer.

    A country with no researched figure for a row contributes "not established"
    rather than a zero, and a row nobody can answer is dropped from the matrix
    entirely with a note. A comparison table whose empty cells are ambiguous is
    worse than a shorter honest one.
    """
    measured = measure_country_catalogue(session)
    corpus = get_corpus()

    normalised: list[str] = []
    for code in iso2s:
        candidate = (code or "").strip().upper()
        if candidate and candidate not in normalised:
            normalised.append(candidate)

    countries = []
    for code in normalised:
        record = corpus.get(code)
        facts = measured.get(code)
        if record is None and facts is None:
            countries.append({"iso2": code, "name": display_name(code), "known": False})
            continue
        researched, missing = _sections_state(record)
        countries.append(
            {
                "iso2": code,
                "name": record.name if record else display_name(code),
                "flag": flag_emoji(code),
                "currency": record.currency if record else None,
                "known": True,
                "scholarships": facts.scholarships if facts else None,
                "fully_funded": facts.fully_funded if facts else None,
                "researched_sections": list(researched),
                "missing_sections": list(missing),
            }
        )

    rows: list[dict[str, Any]] = []
    dropped: list[str] = []
    for spec in COMPARISON_ROWS:
        values: dict[str, Any] = {}
        any_known = False
        for entry in countries:
            code = entry["iso2"]
            if not entry.get("known"):
                values[code] = None
                continue
            payload = _claim_payload(corpus.get(code), spec["path"])
            values[code] = payload
            if payload["value"] is not None:
                any_known = True
        if not any_known:
            dropped.append(spec["label"])
            continue
        rows.append(
            {
                "key": spec["key"],
                "label": spec["label"],
                "higher_is_better": spec["higher_is_better"],
                "values": values,
                **_currency_status(values),
            }
        )

    refused = [row["label"] for row in rows if not row["comparable"]]
    table = get_fx_table()

    return {
        "countries": countries,
        "rows": rows,
        "dropped_rows": dropped,
        "dropped_rows_reason": (
            "No selected country has a sourced figure for these, so they are not "
            "shown rather than shown as empty."
        ),
        "incomparable_rows": refused,
        "winner_policy": (
            "No winner is declared. Countries are quoted in their own currencies, "
            "so a lower number in a weaker currency is not a cheaper country, and "
            "ranking them would say something the data cannot support."
        ),
        "ranking_rule": (
            "A row is comparable only when every figure in it can be brought to one "
            "currency: either they are already in the same currency, or the corpus "
            "holds a sourced rate for the period. Converted rows publish the rate, "
            "its date and its direction alongside the originals. No rate is assumed, "
            "interpolated, or invented."
        ),
        "fx": table.to_dict() if table else None,
        "fx_available": table is not None,
    }


def calculate_cost(
    session,
    iso2: str,
    level: str,
    tier: str,
    years: float,
) -> dict[str, Any]:
    """The interactive cost calculator, including every refusal.

    Returns the derivations as a list rather than a nested total so the interface
    can show *why* a number is missing beside the number that is present. A total
    with no visible derivation is how a student ends up budgeting from arithmetic
    they cannot check.
    """
    normalised = (iso2 or "").strip().upper()
    measured = measure_country_catalogue(session)
    corpus = get_corpus()
    record = corpus.get(normalised)

    facts = measured.get(normalised)
    coverage, coverage_reason = scholarship_coverage(
        facts.fully_funded if facts else None, facts.scholarships if facts else None
    )

    # Validated claims, not raw section bodies. Block-level metadata has been
    # inherited and aliases resolved by this point, which is what keeps a figure
    # that declares its status once at the top of a block usable below it.
    sections = dict(record.claims) if record else {}

    tuition = derive_tuition(sections, level, coverage)
    living = derive_living(sections, tier)
    one_time = derive_one_time_total(sections)
    total = derive_total_investment(tuition, living, one_time, years)

    net_income = find_claim(sections, ("career", "net_monthly_income"))
    annual_income = find_claim(sections, ("career", "average_starting_salary", "master"))
    break_even = derive_break_even(total, net_income)
    roi = derive_roi(total, annual_income, years)

    return {
        "country": {
            "iso2": normalised,
            "name": record.name if record else display_name(normalised),
            "flag": flag_emoji(normalised),
            "currency": record.currency if record else None,
        },
        "inputs": {
            "study_level": level,
            "city_tier": tier,
            "duration_years": years,
        },
        "available_inputs": {
            "study_levels": list(STUDY_LEVELS),
            "city_tiers": list(CITY_TIERS),
            "coverage": coverage,
            "coverage_reason": coverage_reason,
        },
        "measured": facts.to_dict() if facts else None,
        "derivation_version": DERIVATION_VERSION,
        "results": [
            tuition.to_dict(),
            living.to_dict(),
            one_time.to_dict(),
            total.to_dict(),
            break_even.to_dict(),
            roi.to_dict(),
        ],
        "net_gain_note": (
            "The return multiple is a ratio of two researched figures over "
            f"{years:g} years. It does not discount time, does not model the risk "
            "of finding no work, and is not a forecast."
        ),
    }


def intelligence_meta() -> dict[str, Any]:
    """Versions and the value-status vocabulary, so the UI cannot invent a status."""
    return {
        "country_intelligence_version": COUNTRY_INTELLIGENCE_VERSION,
        "derivation_version": DERIVATION_VERSION,
        "value_status": list(VALUE_STATUS),
        "value_status_labels": dict(VALUE_STATUS_LABELS),
        # Freshness and refusals are published in the same place as the status
        # vocabulary, so a client can label them without hardcoding strings. An
        # endpoint that exposes a stale figure but not the word for staleness
        # leaves the UI to invent the disclosure, which is the one thing this
        # payload exists to prevent.
        "freshness": list(FRESHNESS),
        "freshness_labels": dict(FRESHNESS_LABELS),
        "stale_after_days": DEFAULT_STALE_AFTER_DAYS,
        "refusal_codes": dict(REFUSAL_LABELS),
        "source_types": list(SOURCE_TYPES),
        "official_source_types": sorted(OFFICIAL_SOURCE_TYPES),
        "non_official_source_types": sorted(NON_OFFICIAL_SOURCE_TYPES),
        "income_basis": sorted(INCOME_BASIS),
        "formula_registry": formula_contracts(),
        "study_levels": list(STUDY_LEVELS),
        "city_tiers": list(CITY_TIERS),
        "comparison_rows": [
            {"key": spec["key"], "label": spec["label"]} for spec in COMPARISON_ROWS
        ],
    }


__all__ = [
    "COMPARISON_ROWS",
    "CountrySummary",
    "calculate_cost",
    "compare_countries",
    "country_detail",
    "country_summaries",
    "intelligence_meta",
]
