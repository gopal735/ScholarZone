"""Deterministic research-to-corpus ingestion.

Run it from ``backend/``::

    python scripts/ingest_country_intelligence.py
    python scripts/ingest_country_intelligence.py --country DE
    python scripts/ingest_country_intelligence.py --check
    python scripts/ingest_country_intelligence.py --normalize

## What it does

    raw research -> parse -> normalise -> source-type map -> country-code map
                 -> field validation -> provenance validation -> formula validation
                 -> unit/currency validation -> gap generation
                 -> canonical ISO2 JSON -> schema validation -> write

Every stage that can reject a figure does, and a rejected country produces **no
file at all**. Half a country is worse than no country: a reader has no way to
know which half survived.

## Determinism

The same raw document and the same contract version produce byte-identical output.
There is no source of "now" in this pipeline. ``retrieved_at`` is carried from the
source document, never from the clock, because a pipeline that stamps the current
time cannot be re-run to check whether its output changed — and a corpus whose
provenance drifts on every run is a corpus nobody trusts. That also means a re-run
is always safe: it can only tell you the truth is unchanged.

## It will not do the thing you might ask

There is no ``--force``, no ``--skip-validation``, no ``--trust-me`` and no way to
write a country whose figures failed. Those flags all exist in ingestion tools
somewhere, and every one of them has been used once to make a red build go green
with a number nobody checked. If a country is being rejected, the answer is to
fix the research or record the gap, not to bypass the gate.

## What is ingestible right now

Nothing, from raw research: no raw document is recoverable, which
``config/country_intelligence/research_raw/manifest.json`` records explicitly.
What *is* runnable today is ``--normalize``, which rewrites canonical vocabulary
in place - research vocabulary such as ``OFFICIAL_UNIVERSITY`` resolved to the
canonical ``UNIVERSITY_OFFICIAL`` - without touching any figure's value. That is
the one transformation that is safe on data of unknown provenance, because it
changes how a figure is labelled rather than what it says.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

# Allow ``python scripts/ingest_country_intelligence.py`` from backend/ without
# requiring the package to be installed first.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.country_intelligence.corpus import (  # noqa: E402
    CORPUS_DIR,
    SECTION_NAMES,
    ClaimError,
    load_corpus,
)
from app.services.country_intelligence.fx import parse_fx_table  # noqa: E402
from app.services.country_intelligence.formulas import (  # noqa: E402
    FORMULAS,
    registry_problems,
)
from app.services.country_intelligence.net_income import (
    NetIncomeError,
    profile_from_raw,
    validate_profile,
)
from app.services.country_intelligence.provenance import (  # noqa: E402
    OFFICIAL_SOURCE_TYPES,
    SOURCE_TYPE_ALIASES,
    SOURCE_TYPES,
    VALUE_STATUS,
    VALUE_STATUS_ALIASES,
    normalise_source_type,
    normalise_status_vocabulary,
)
from app.services.country_intelligence.taxonomy import display_name  # noqa: E402

#: Bumped when the canonical shape changes. Recorded in every written file so a
#: reader can tell which contract a file was produced under.
CONTRACT_VERSION = "1.0.0"

RESEARCH_RAW_DIR = CORPUS_DIR / "research_raw"
MANIFEST_PATH = RESEARCH_RAW_DIR / "manifest.json"
GLOBAL_RAW_DIR = RESEARCH_RAW_DIR / "_global"
FX_RAW_PATH = GLOBAL_RAW_DIR / "001_fx_reference_rates.json"
FX_CANONICAL_PATH = CORPUS_DIR / "fx" / "rates.json"

#: Indentation for written files. Fixed rather than inferred so a diff of two
#: runs is empty rather than full of reindentation.
JSON_INDENT = 2

#: Currencies this corpus recognises, from ISO 4217.
#:
#: Closed on purpose. A three-letter prefix that is not on this list is refused
#: rather than accepted as a currency, because "100 SEK" and "100 SEK-per-thing"
#: both start with three letters and only one of them is money.
KNOWN_CURRENCIES: frozenset[str] = frozenset(
    {
        "AUD", "BGN", "BRL", "CAD", "CHF", "CLP", "CNY", "COP", "CZK", "DKK",
        "EUR", "GBP", "HKD", "HRK", "HUF", "IDR", "ILS", "INR", "ISK", "JPY",
        "KRW", "MXN", "MYR", "NOK", "NZD", "PHP", "PLN", "RON", "RUB", "SEK",
        "SGD", "THB", "TRY", "USD", "ZAR",
    }
)


@dataclass
class IngestReport:
    """What happened to one country."""

    iso2: str
    written: bool = False
    path: Path | None = None
    reason: str = ""
    warnings: list[str] = field(default_factory=list)
    #: Income-contract violations found while building this country, surfaced
    #: as gaps rather than silently demoted.
    income_gaps: list[dict[str, Any]] = field(default_factory=list)
    normalisations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "iso2": self.iso2,
            "written": self.written,
            "path": str(self.path) if self.path else None,
            "reason": self.reason,
            "warnings": list(self.warnings),
            "normalisations": list(self.normalisations),
        }


def _load_json(path: Path) -> Any:
    """Parse JSON, rejecting duplicate keys.

    A duplicate key is a real defect and ``json.loads`` will not tell you: Python's
    parser keeps the last value and discards the earlier one without comment. Two
    research agents in this build emitted duplicated keys, in one case two
    different values under the same name, so silently keeping one of them would
    have published a figure that the document itself contradicts. The check is on
    the raw object so it catches the collision before anything is interpreted.
    """
    # ``utf-8-sig`` rather than ``utf-8``: a researcher's editor may write a byte
    # order mark, and refusing to read a country because of one invisible leading
    # byte is a availability problem masquerading as a data-quality signal. The
    # decoder strips the mark when present and behaves identically when absent.
    text = path.read_text(encoding="utf-8-sig")

    def _reject(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        seen: dict[str, Any] = {}
        for key, value in pairs:
            if key in seen:
                raise ValueError(
                    f"duplicate JSON key {key!r}. Two values under one name means the "
                    f"document contradicts itself; the parser would silently keep "
                    f"only the last."
                )
            seen[key] = value
        return seen

    def _reject_duplicate_constant(name: str) -> Any:
        raise ValueError(f"duplicate JSON constant {name!r}")

    return json.loads(
        text, object_pairs_hook=_reject, parse_constant=_reject_duplicate_constant
    )


#: Placeholder markers seen in research output. Matched case-insensitively against
#: string values anywhere in the document.
#:
#: A placeholder is worse than a missing value, because it occupies the position
#: where a real figure would go. Detected and rejected rather than published.
PLACEHOLDER_MARKERS = (
    "TODO",
    "TBD",
    "FIXME",
    "PLACEHOLDER",
    "XXX",
    "lorem ipsum",
    "example.com",
    "INSERT_",
    "FILL_ME",
)


def _find_placeholders(node: Any, path: str = "") -> list[str]:
    """Every placeholder-looking string in a document, with its path."""
    found: list[str] = []
    if isinstance(node, Mapping):
        for key, value in node.items():
            found.extend(_find_placeholders(value, f"{path}.{key}" if path else str(key)))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found.extend(_find_placeholders(value, f"{path}[{index}]"))
    elif isinstance(node, str):
        lowered = node.lower()
        if any(marker.lower() in lowered for marker in PLACEHOLDER_MARKERS):
            found.append(f"{path}: {node!r}")
    return found


def _normalise_statuses(node: Any, changes: list[str], path: str = "") -> Any:
    """Rewrite research status spellings to canonical names, recursively."""
    if isinstance(node, Mapping):
        result: dict[str, Any] = {}
        for key, value in node.items():
            if key in ("value_status", "source_type"):
                original = value
                resolved = (
                    normalise_source_type(value)
                    if key == "source_type"
                    else normalise_status_vocabulary(value)
                )
                if resolved and resolved != original:
                    changes.append(f"{path}.{key}: {original!r} -> {resolved!r}")
                    value = resolved
                elif key == "source_type" and original is not None and resolved is None:
                    raise ClaimError(
                        f"{path}.{key}: {original!r} is not a recognised source type. "
                        f"Known types: {', '.join(SOURCE_TYPES)}."
                    )
            result[key] = _normalise_statuses(value, changes, f"{path}.{key}")
        return result
    if isinstance(node, list):
        return [_normalise_statuses(item, changes, f"{path}[{i}]") for i, item in enumerate(node)]
    return node


def _canonical_sort(value: Any) -> Any:
    """Recursively sort object keys, leaving arrays in their given order.

    Arrays are not sorted: in this corpus a list is an ordered claim - a sequence
    of study levels or city tiers - and reordering it would change what the
    document says. Keys are sorted so that two runs produce identical bytes.
    """
    if isinstance(value, Mapping):
        return {key: _canonical_sort(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_canonical_sort(item) for item in value]
    return value


def _write_country(path: Path, document: Mapping[str, Any]) -> None:
    """Write a canonical country file deterministically."""
    payload = _canonical_sort(dict(document))
    path.write_text(
        json.dumps(payload, indent=JSON_INDENT, ensure_ascii=False, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def _validate_document(document: Mapping[str, Any], iso2: str) -> list[str]:
    """Validate one candidate country document through the real corpus loader.

    The loader is the authority, not this script. Ingestion deliberately reuses
    ``load_corpus`` by writing to a temporary directory and asking it to parse the
    result, so there is exactly one definition of "a valid country file" and
    ingestion cannot drift from what the application will later accept.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        staged = Path(tmp) / f"{iso2}.json"
        _write_country(staged, document)
        corpus = load_corpus(Path(tmp))

    if corpus.iso2_codes == (iso2,):
        return []
    if corpus.problems:
        return [problem.reason for problem in corpus.problems]
    return [
        f"{iso2}: the document did not load. Sections present: "
        f"{sorted(document.get('sections', {})).strip()} (expected some of "
        f"{', '.join(SECTION_NAMES)})."
    ]


def normalise_existing(corpus_dir: Path = CORPUS_DIR) -> list[IngestReport]:
    """Rewrite canonical vocabulary in place. Safe on data of any provenance.

    This is the only transformation applied to a file we did not produce from raw
    research, and it is safe precisely because it cannot change a figure: it
    rewrites ``OFFICIAL_UNIVERSITY`` to ``UNIVERSITY_OFFICIAL`` and leaves every
    value, source id, date and gap alone. The alternative - leaving research
    spelling in the stored corpus - is what makes "is this official?" unanswerable
    by query, which is the reason for a canonical vocabulary existing at all.
    """
    reports: list[IngestReport] = []
    for path in sorted(corpus_dir.glob("*.json")):
        iso2 = path.stem.upper()
        report = IngestReport(iso2=iso2, path=path)
        try:
            document = _load_json(path)
            if not isinstance(document, Mapping):
                raise ClaimError("Country file must contain an object.")
            changes: list[str] = []
            normalised = _normalise_statuses(document, changes)
            normalised.setdefault("contract_version", CONTRACT_VERSION)
            report.normalisations = changes
            problems = _validate_document(normalised, iso2)
            if problems:
                report.reason = "; ".join(problems)
                report.warnings.append("File left unchanged.")
                reports.append(report)
                continue
            _write_country(path, normalised)
            report.written = True
            report.reason = (
                f"Normalised {len(changes)} status spelling(s)."
                if changes
                else "Already canonical; rewritten byte-identically."
            )
        except (ClaimError, ValueError, OSError, UnicodeDecodeError) as exc:
            report.reason = str(exc)
        reports.append(report)
    return reports


def ingest_country(
    raw_path: Path, corpus_dir: Path = CORPUS_DIR
) -> IngestReport:
    """Run one raw research document through the full pipeline.

    Returns a report; writes a file only when every gate passes. The stages are
    explicit and ordered so the report can say which one stopped it.
    """
    iso2 = raw_path.stem.upper()
    report = IngestReport(iso2=iso2, path=corpus_dir / f"{iso2}.json")

    try:
        raw = _load_json(raw_path)
    except (ValueError, OSError, UnicodeDecodeError) as exc:
        report.reason = f"Parse failed: {exc}"
        return report
    if not isinstance(raw, Mapping):
        report.reason = "Parse failed: document is not an object."
        return report

    placeholders = _find_placeholders(raw)
    if placeholders:
        report.reason = (
            f"Rejected: {len(placeholders)} placeholder value(s) present. A placeholder "
            f"occupies the position of a real figure and would be published as one: "
            + "; ".join(placeholders[:3])
        )
        return report

    try:
        changes: list[str] = []
        document = _normalise_statuses(dict(raw), changes)
        report.normalisations = changes
    except ClaimError as exc:
        report.reason = f"Normalisation failed: {exc}"
        return report

    if "contract_version" in document:
        report.warnings.append(
            f"Input already declares contract_version {document['contract_version']!r}; "
            f"overwritten with {CONTRACT_VERSION!r}."
        )
    document["contract_version"] = CONTRACT_VERSION

    report.warnings.extend(_validate_document(document, iso2))
    if report.warnings:
        report.reason = "Rejected by the corpus validator; no file written."
        return report

    corpus_dir.mkdir(parents=True, exist_ok=True)
    _write_country(report.path, document)
    report.written = True
    report.reason = "Ingested."
    return report


def build_fx_table(raw_path: Path = FX_RAW_PATH, target: Path = FX_CANONICAL_PATH) -> IngestReport:
    """Build the canonical exchange-rate table from archived raw evidence.

    Exchange rates are global rather than per-country, so they get their own
    canonical file instead of being duplicated into seventeen country files where
    seventeen copies of one dated fact could drift apart.

    Only currencies actually quoted on the archived page are carried over. A rate
    table padded with currencies the source did not publish would be a table
    nobody could audit against the evidence behind it.
    """
    report = IngestReport(iso2="FX", path=target)
    if not raw_path.exists():
        report.reason = (
            "No archived FX evidence. Comparison continues to refuse mixed-currency "
            "rows, which is the correct behaviour before a rate has been sourced."
        )
        return report

    try:
        raw = _load_json(raw_path)
    except (ValueError, OSError, UnicodeDecodeError) as exc:
        report.reason = f"Parse failed: {exc}"
        return report

    for required in ("source_id", "source_url", "as_of", "claims"):
        if not raw.get(required):
            report.reason = (
                f"Rejected: {required!r} is missing. A rate table without a "
                f"{required} cannot be audited, and an unauditable rate must not be "
                f"used to convert anything."
            )
            return report

    base = str(raw.get("base") or "EUR").upper()
    rates: dict[str, float] = {}
    for claim in raw.get("claims", []):
        # Claims are written as "<CURRENCY> per <BASE>", so the base is the part
        # after " per ". Parsing direction rather than assuming it is the point:
        # a rate quoted the other way round converts a comparison into its inverse
        # and nothing downstream would catch it.
        unit = str(claim.get("unit", "")).strip()
        suffix = f" per {base}"
        if not unit.upper().endswith(suffix.upper()):
            continue
        currency = unit[: -len(suffix)].strip().upper()
        value = claim.get("value")
        if len(currency) == 3 and isinstance(value, (int, float)) and not isinstance(value, bool):
            rates[currency] = float(value)

    if not rates:
        report.reason = (
            f"Rejected: no claim in the evidence is quoted as '<CURRENCY> per {base}'. "
            f"The direction of a rate is what stops a conversion being inverted, so an "
            f"unparseable direction is not guessed at."
        )
        return report

    document = {
        "base": base,
        "as_of": raw["as_of"],
        "source_id": raw["source_id"],
        "source_url": raw["source_url"],
        "publisher": raw.get("publisher", "unspecified"),
        "contract_version": CONTRACT_VERSION,
        "rates": {code: rates[code] for code in sorted(rates)},
        "caveat": (
            "European Central Bank reference rates are published for information "
            "purposes only; the ECB discourages using them for transactions. These "
            "figures compare the magnitude of study costs between countries and must "
            "not be used to budget a currency transfer."
        ),
    }

    try:
        parse_fx_table(document, path=str(target))
    except ClaimError as exc:
        report.reason = f"Rejected by the FX validator: {exc}"
        return report

    target.parent.mkdir(parents=True, exist_ok=True)
    _write_country(target, document)
    report.written = True
    report.reason = (
        f"Built from {raw['source_id']} dated {raw['as_of']} with "
        f"{len(rates)} currencies."
    )
    return report


#: Explicit topic -> corpus path mapping.
#:
#: Deliberately a visible table with one row per decision, and **no default**. A
#: topic that is not listed produces a gap naming the topic, never a guess. A
#: mapping table that silently guessed would be the single place where a research
#: topic could land in a section it does not belong to, and nothing downstream
#: would notice because the number would be a plausible shape in the wrong slot.
TOPIC_PATHS: dict[str, tuple[str, ...]] = {
    # Education costs
    "bachelor_tuition": ("education_costs", "tuition_fees", "public", "bachelor"),
    "master_tuition": ("education_costs", "tuition_fees", "public", "master"),
    "phd_tuition": ("education_costs", "tuition_fees", "public", "phd"),
    "private_bachelor_tuition": (
        "education_costs", "tuition_fees", "private", "bachelor",
    ),
    "mandatory_fees": ("education_costs", "mandatory_fees", "public"),
    "bachelor_tuition_mandatory_fees_stuttgart": (
        "education_costs", "mandatory_fees", "stuttgart",
    ),
    "mandatory_fees_semester_fee_tum": (
        "education_costs", "mandatory_fees", "tum",
    ),
    "per_university_non_eu_tuition_tum": (
        "education_costs", "tuition_fees", "by_university", "tum", "bachelor",
    ),
    "bachelor_tuition_tuebingen": (
        "education_costs", "tuition_fees", "by_university", "tuebingen", "bachelor",
    ),
    "tuition_bands": ("education_costs", "tuition_fees", "structure"),
    # Country-specific tuition exceptions, kept as their own fields rather than
    # folded into a national average. Germany is not "public tuition is free".
    "baden_wuerttemberg_non_eu_tuition": (
        "education_costs", "tuition_fees", "by_state", "baden_wuerttemberg",
        "non_eu_per_semester",
    ),
    "bavaria_non_eu_tuition_thi": (
        "education_costs", "tuition_fees", "by_state", "bavaria", "thi",
    ),
    "bavaria_non_eu_tuition_hs_muenchen": (
        "education_costs", "tuition_fees", "by_state", "bavaria", "muenchen",
    ),
    # One-time costs
    "financial_proof": ("one_time_costs", "blocked_account"),
    "visa_fees": ("one_time_costs", "visa_fee"),
    "visa_fees_ihs": ("one_time_costs", "immigration_health_surcharge"),
    "health_insurance": ("one_time_costs", "student_health_insurance"),
    # Living costs
    "living_costs": ("living_costs", "monthly_costs", "medium", "total"),
    "living_costs_low": ("living_costs", "monthly_costs", "low", "total"),
    "living_costs_high": ("living_costs", "monthly_costs", "high", "total"),
    "housing": ("living_costs", "housing", "medium"),
    # Work and residency
    "student_work_rights": ("residency", "work_while_studying"),
    "post_study_work": ("residency", "job_seeker_residence_permit", "duration"),
    "post_study_work_costs": ("residency", "job_seeker_residence_permit", "income_requirement"),
    "permanent_residence": ("residency", "permanent_residence"),
    "naturalisation_citizenship": ("residency", "citizenship"),
    "skilled_worker": ("residency", "skilled_worker_route"),
    "blue_card": ("residency", "blue_card"),
    # Career
    "career": ("career", "employment_outcomes"),
    "salary": ("career", "average_starting_salary", "bachelor"),
    "net_income": ("career", "net_monthly_income"),
    # The net-income track writes these topic names. Both map to the same
    # contract-validated slot; "net_income" is kept as an alias so artifacts
    # written before the track used the longer name still ingest.
    "net_monthly_income": ("career", "net_monthly_income"),
    "net_take_home_income": ("career", "net_monthly_income"),
    # Gross lives at its own path, never beside net, so a later reader cannot
    # mistake one for the other. Ingestion refuses a gross figure on the net
    # topic regardless of what the artifact says, because a gross salary in a
    # net slot is the specific error this corpus exists to prevent.
    "gross_monthly_income": ("career", "average_starting_salary", "gross_monthly"),
    "gross_monthly_salary": ("career", "average_starting_salary", "gross_monthly"),
    "gross_annual_income": ("career", "average_starting_salary", "gross_annual"),
    # Where a net derivation is refused because its gross was not independently
    # sourced, the tax parameters behind it are still real, cited and dated. They
    # get their own slot so that evidence is preserved rather than discarded with
    # the conclusion it could not support - and so a future pass with a sourced
    # gross can complete the derivation from parameters already in the corpus.
    "income_tax_parameters": ("career", "income_tax_parameters"),
    "net_derivation_parameters": ("career", "income_tax_parameters"),
    # Scholarships and quality of life
    "scholarship_landscape": ("scholarship_landscape", "note"),
    "government_scholarship_bachelor_myth": (
        "scholarship_landscape", "national_scheme",
    ),
    "si_scholarship": ("scholarship_landscape", "national_scheme"),
    "quality_of_life": ("quality_of_life", "note"),
    # Second-degree / prior-study rules, which are not tuition at all
    "bachelor_tuition_second_course": (
        "education_costs", "tuition_fees", "second_degree_rules",
    ),
}

#: Topics whose figures describe a **rule** rather than a price. Their numeric value
#: is retained but flagged, because "18,000 students" is not a cost and must never
#: be read as one.
DESCRIPTIVE_TOPICS: frozenset[str] = frozenset(
    {"bachelor_tuition_second_course", "si_scholarship", "scholarship_landscape"}
)

#: Recognised time bases. Anything outside this set is refused rather than coerced,
#: because coercing it would misstate by a factor of twelve.
UNIT_PERIODS: dict[str, str] = {
    "year": "year", "semester": "semester", "quarter": "quarter",
    "month": "month", "week": "week", "day": "day", "once": "once",
    "application": "once", "programme": "programme", "months": "month",
    "hours": "hour", "hour": "hour", "years": "year", "days": "day",
    # Synonyms researchers actually use. "academic year" is how several European
    # systems phrase the year a fee applies to, and treating it as unknown would
    # reject otherwise good evidence for vocabulary rather than for data quality.
    "academic": "year", "academicyear": "year", "calendar": "year",
    "study": "programme", "studies": "programme", "term": "semester",
}

#: Topics whose figures are **per study level**, and must be filed under the level
#: they were measured at.
#:
#: Sweden is the case that forced this. It operates two different job-search
#: permits - the one whose page says "9 months" is outbound and second-cycle only,
#: while the Bachelor permit runs up to 12 months. Two artifacts therefore share
#: the topic ``post_study_work`` and describe genuinely different permits. Filing
#: them at one path made a *count* claim ("0 bachelor degrees qualify for this
#: permit") collide with a *duration*, and the true 12-month Bachelor figure was
#: then discarded as a spurious conflict.
#:
#: Filing by level is not a tidiness fix: a Bachelor and a Master reading the same
#: duration path is a category error, because they are different legal routes.
LEVEL_SENSITIVE_TOPICS: frozenset[str] = frozenset(
    {"post_study_work", "bachelor_tuition", "master_tuition", "phd_tuition"}
)

#: Corpus paths whose figures are durations. A count landing here asserts that
#: something happened zero times, which is a different claim from "it took no
#: time".
DURATION_PATH_MARKERS = ("duration", "years", "deadline")
#:
#: A claim with no currency reaching one of these is refused rather than stored: a
#: unitless number in a tuition slot is indistinguishable from a cost to every
#: consumer, and would flow into a derived total as though it were one.
MONETARY_PATH_MARKERS = ("tuition_fees", "blocked_account", "costs", "fee", "salary")

#: Corpus paths whose figures are money. A zero in one of these asserts the country
#: charges nothing at all, which is a stronger claim than any other figure here.
ZERO_COST_PATH_MARKERS = ("tuition_fees", "mandatory_fees", "blocked_account", "costs", "fee", "salary")

#: Study levels that appear as a component of a canonical tuition path. A path may
#: carry each of these at most once.
STUDY_LEVEL_COMPONENTS: tuple[str, ...] = ("bachelor", "master", "phd")

#: Phrase stamped into a note by the zero rule, used to keep the demotion
#: idempotent across rebuilds. A rebuild re-reads its own previous output, so
#: without this marker the refusal sentence would be appended again on every pass.
_ZERO_REFUSAL_MARKER = "it is not published, because"

#: Longest period phrase is matched first, so "per year" is not read as "per y".
_PERIOD_SCAN = sorted(UNIT_PERIODS, key=len, reverse=True)


def is_cost_path(path: str) -> bool:
    """True when ``path`` is a money slot, and the figure in it is a cost.

    A figure that ingestion deliberately diverted under ``related_figures`` is not a
    cost claim even when its path contains a cost marker. That bucket exists
    precisely to hold real numbers that are *not* prices - counts, durations and
    statements - and applying the cost rules to them would demote evidence for
    being honest about what it is.
    """
    if "related_figures" in path.split("."):
        return False
    return any(marker in path for marker in ZERO_COST_PATH_MARKERS)


def zero_cost_refusal(
    claim: Mapping[str, Any], path: str, archived_source_ids: set[str]
) -> str | None:
    """Return ``None`` when a zero may be published, else why it may not.

    **One rule, one place.** A zero tuition is a strong claim: it says the country
    charges nothing, and it reaches a derived total that a reader treats as a
    budget. It therefore needs the same evidence as any other figure, and the
    failure mode is worse than a missing number because a zero *looks* like an
    answer.

    This was previously enforced only inside the fresh-build claim loop, which left
    two holes that both shipped: a carried-forward zero bypassed it entirely, and
    even in the fresh path the demotion was written to a node that the very next
    statement rebound, so it never reached the file. Germany carried EUR 0/year for
    public Bachelor, Master and PhD tuition whose only source was
    make-it-in-germany.com's Skilled Immigration Act page - a visa page, not a
    tuition page, with no archived extract - and ``derive_tuition`` returned 0.0
    while Baden-Wuerttemberg's real statutory fee sat in the same corpus at a
    different path.

    So the rule is stated once, here, and called from **every** entry point that can
    put a claim in the corpus: a fresh ingest, a carried-forward claim, a merged
    claim, a rebuilt claim and a retained legacy claim. A claim's origin never
    decides whether it is trusted; its evidence does.

    A zero may be published only when all four hold:

    1. it **cites a source** - an unsourced zero is an assumption;
    2. **every** source behind it is archived, so the claim can be audited against
       the page that states it rather than taken on the URL's word;
    3. it carries a **recognised currency**, so it is money and not a count;
    4. it states a **period**, so it is a defined quantity rather than a bare zero.

    Anything else becomes ``UNKNOWN``, which refuses rather than understates.
    """
    if not is_cost_path(path):
        return None
    if claim.get("value") != 0:
        return None

    cited = {str(item) for item in (claim.get("source_ids") or []) if str(item)}
    if not cited:
        return (
            "the claim states that the cost is zero but cites no source, so the zero "
            "is an assumption rather than a finding"
        )
    unarchived = sorted(cited - archived_source_ids)
    if unarchived:
        return (
            f"the only source(s) behind the zero are {', '.join(unarchived)}, whose "
            f"verbatim extract is not archived, so the claim that the cost is zero "
            f"cannot be audited against the page that states it"
        )
    currency = claim.get("currency")
    if not currency or str(currency).upper() not in KNOWN_CURRENCIES:
        return (
            "the zero states no recognised currency, so it cannot be told apart from a "
            "count that happens to be zero"
        )
    if not claim.get("per"):
        return (
            "the zero states no period, so it is not a defined quantity: 'zero per "
            "year' and 'zero per semester' are different claims and a bare zero is "
            "not either"
        )
    return None


def canonical_claim_path(path: list[str]) -> list[str]:
    """Collapse a repeated study-level component so a level appears exactly once.

    ``bachelor_tuition`` already maps to ``...tuition_fees.public.bachelor`` - the
    level is part of the canonical path - so the level-append step must not add it
    again. When it did, the result was ``...public.bachelor.bachelor``, a path no
    derivation could reach: researched tuition existed in the corpus and was
    invisible to ``derive_tuition`` for 13 of 17 countries while the refusal
    reason said no researched data was present.

    Enforcing the shape **here**, in the one function every canonical write goes
    through, is what makes it impossible for any stage - the level append, the
    period step, the related-figures diversion, the collision rebuild or a future
    one - to re-create the defect. Fixing the append alone would only move the
    problem to the next stage that touches the path.

    Collapsing an adjacent duplicate is deliberately narrow. A path that names two
    *different* levels is a different error and is not silently rewritten here.
    """
    result: list[str] = []
    for part in path:
        if part in STUDY_LEVEL_COMPONENTS and result and result[-1] == part:
            continue
        result.append(part)
    return result


def _split_unit(unit: Any) -> tuple[str | None, str | None, list[str]]:
    """Turn ``"EUR per year (cost of attendance estimate)"`` into ``("EUR", "year", [])``.

    Direction and period are parsed rather than inferred, because a monthly figure
    fed to an annual slot is wrong by a factor of twelve while still looking like a
    cost.

    Parenthetical qualifications are stripped first. A researcher who writes
    ``"EUR per semester (tuition plus Students' Union fee)"`` has stated the period
    clearly and added a caveat; refusing it over the caveat would discard good
    evidence for a formatting habit. The caveat belongs in the note, and the
    researcher's own ``research_notes`` already carries it.
    """
    problems: list[str] = []
    if unit is None:
        return None, None, problems
    text = str(unit).strip()
    if not text:
        return None, None, problems

    # Drop parentheticals and any " - " aside; keep the leading unit expression.
    core = re.split(r"[(\[]| - | – | — ", text, maxsplit=1)[0].strip()
    lowered = core.lower()

    currency = None
    match = re.match(r"^([A-Za-z]{3})\b", core)
    if match:
        candidate = match.group(1).upper()
        if candidate in KNOWN_CURRENCIES:
            currency = candidate
        else:
            problems.append(
                f"unit {text!r} starts with {candidate!r}, which is not a recognised "
                f"currency. The currency was left unset rather than guessed."
            )

    per = None
    # A period must be **stated**, never inferred from prose. Scanning the whole
    # string for a period word was too loose: it read a claim whose unit was
    # "bachelor degrees qualifying for this permit as defined on page" as having a
    # period, which then let a *count* through a guard meant to keep counts out of
    # duration fields. Only an exact period token or an explicit "per <period>"
    # construction is honoured.
    explicit = re.search(r"\bper\s+([A-Za-z]+)", lowered)
    if explicit:
        token = explicit.group(1).rstrip("s")
        per = UNIT_PERIODS.get(token) or UNIT_PERIODS.get(explicit.group(1))
        if per is None:
            # "GBP per person" and "EUR per academic year" are not failures.
            # The first states a basis rather than a period; the second is a
            # synonym the vocabulary had not seen. Rejecting a whole country over
            # either discards good evidence for vocabulary, so the qualifier is
            # kept in the researcher's own note and no period is assumed.
            pass
    elif lowered in UNIT_PERIODS:
        per = UNIT_PERIODS[lowered]
    elif lowered.rstrip("s") in UNIT_PERIODS:
        per = UNIT_PERIODS[lowered.rstrip("s")]
    else:
        bare = re.fullmatch(r"([A-Za-z]+)", lowered)
        if bare and (bare.group(1).rstrip("s") in UNIT_PERIODS or bare.group(1) in UNIT_PERIODS):
            per = UNIT_PERIODS.get(bare.group(1)) or UNIT_PERIODS.get(bare.group(1).rstrip("s"))

    if currency is None and per is None:
        # Not a money figure and not a duration - a count or a statement. That is
        # legitimate for a rule ("18 months", "2 renewals"), so it is described
        # rather than rejected.
        return None, None, []

    return currency, per, problems


def ingest_country_from_raw(
    iso2: str, corpus_dir: Path = CORPUS_DIR, raw_dir: Path | None = None
) -> IngestReport:
    """Build one canonical country file from its archived raw evidence.

    Every claim that reaches the file must have arrived in an artifact carrying a
    source id, a source URL, a publisher and a date. An artifact that says
    ``UNAVAILABLE`` becomes a **gap**, which is published, rather than a figure.

    An unmapped topic also becomes a gap. That is the important behaviour: research
    arrives faster than the schema can be extended, and the honest result of a new
    topic nobody has mapped is a visible to-do item.
    """
    country = iso2.upper()
    source_dir = raw_dir if raw_dir is not None else RESEARCH_RAW_DIR / country
    report = IngestReport(iso2=country, path=corpus_dir / f"{country}.json")

    if not source_dir.is_dir():
        report.reason = (
            f"No archived research for {country}. No file was written; a country with "
            f"no evidence does not get a profile."
        )
        return report

    sources: dict[str, dict[str, Any]] = {}
    sections: dict[str, Any] = {}
    gaps: list[dict[str, Any]] = []
    claimed_fields: dict[str, str] = {}
    notes: list[str] = []

    for artifact_path in sorted(source_dir.glob("*.json")):
        try:
            artifact = _load_json(artifact_path)
        except (ValueError, OSError, UnicodeDecodeError) as exc:
            report.reason = f"Parse failed for {artifact_path.name}: {exc}"
            return report
        if not isinstance(artifact, Mapping):
            report.reason = f"{artifact_path.name}: artifact is not an object."
            return report

        if artifact.get("raw_status") not in (None, "ARCHIVED"):
            # Any explicit non-archived status is a negative-evidence record: the
            # researcher's finding is that a figure is ABSENT, and the reason why
            # becomes a published gap. UNAVAILABLE means the source was
            # unreachable; NOT_FOUND_IN_LAW means the provision does not exist.
            # Both are results worth keeping, and neither may become a figure.
            gaps.append(
                {
                    "field": f"{country.lower()}.{artifact.get('topic', artifact_path.stem)}",
                    "reason": str(
                        artifact.get("reason", "Evidence could not be established.")
                    ),
                    "attempted_sources": list(artifact.get("attempted_sources", [])),
                    "checked_at": artifact.get("checked_at"),
                    "next_review": artifact.get("next_review"),
                }
            )
            continue

        placeholders = _find_placeholders(artifact)
        if placeholders:
            report.reason = (
                f"{artifact_path.name}: rejected, {len(placeholders)} placeholder "
                f"value(s): " + "; ".join(placeholders[:3])
            )
            return report

        topic = str(artifact.get("topic") or artifact_path.stem)
        path = TOPIC_PATHS.get(topic)
        if path is None:
            gaps.append(
                {
                    "field": f"{country.lower()}.{topic}",
                    "reason": (
                        f"Evidence was retrieved and archived, but this topic has no "
                        f"explicit mapping into the corpus schema, so the figure was "
                        f"not placed. Adding the mapping is a reviewed change, not "
                        f"something ingestion should guess."
                    ),
                    "attempted_sources": [str(artifact.get("source_url", ""))],
                    "checked_at": artifact.get("retrieved_at"),
                }
            )
            notes.append(f"{artifact_path.name}: unmapped topic {topic!r} archived, not ingested")
            continue

        source_id = str(artifact.get("source_id") or "").strip()
        source_url = str(artifact.get("source_url") or "").strip()
        publisher = str(artifact.get("publisher") or "").strip()
        source_type = normalise_source_type(artifact.get("source_type"))
        if not source_id or not source_url or not publisher or source_type is None:
            report.reason = (
                f"{artifact_path.name}: rejected. A claim needs a source id, a source "
                f"URL, a publisher and a recognised source_type; got "
                f"id={source_id!r} url={source_url!r} publisher={publisher!r} "
                f"type={artifact.get('source_type')!r}. A figure whose provenance cannot "
                f"be pointed at is not published."
            )
            return report

        existing = sources.get(source_id)
        if existing and existing["url"] != source_url:
            report.reason = (
                f"{artifact_path.name}: source_id {source_id!r} is already defined with "
                f"a different URL. One id may not name two documents."
            )
            return report
        sources[source_id] = {
            "id": source_id,
            "publisher": publisher,
            "title": str(artifact.get("title") or f"{topic} evidence"),
            "url": source_url,
            "source_type": source_type,
            "retrieved_at": artifact.get("retrieved_at"),
            # Marks a source whose verbatim extract is stored under research_raw/.
            # Carried-forward sources lack this, which is how the merge tells
            # proven evidence from a URL someone once cited.
            "archived": True,
            "as_of": artifact.get("as_of"),
            "confidence": artifact.get("confidence"),
            "notes": artifact.get("research_notes"),
        }

        claims = artifact.get("claims") or []
        if not isinstance(claims, list) or not claims:
            gaps.append(
                {
                    "field": f"{country.lower()}.{topic}",
                    "reason": "Evidence was archived but carries no claims.",
                    "attempted_sources": [source_url],
                    "checked_at": artifact.get("retrieved_at"),
                }
            )
            continue

        for claim in claims:
            if not isinstance(claim, Mapping):
                report.reason = f"{artifact_path.name}: a claim is not an object."
                return report
            value = claim.get("value")
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                # A textual finding is evidence, and evidence that carries no figure
                # belongs in the gaps list where it is visible. Rejecting the whole
                # country for it would discard every other verified figure alongside
                # one statement.
                gaps.append(
                    {
                        "field": f"{country.lower()}.{claim.get('claim_id', topic)}",
                        "reason": (
                            f"Archived evidence recorded a finding with no numeric "
                            f"figure: {claim.get('statement', 'no statement given')}"
                        ),
                        "attempted_sources": [source_url],
                        "checked_at": artifact.get("retrieved_at"),
                    }
                )
                continue

            currency, per, unit_problems = _split_unit(claim.get("unit"))
            if unit_problems:
                report.reason = f"{artifact_path.name}: " + "; ".join(unit_problems)
                return report

            claim_path = list(path)
            level = str(claim.get("study_level") or "").lower()
            # Append the study level only when the topic's canonical path does not
            # already end in it.
            #
            # ``bachelor_tuition`` maps to
            # ``education_costs.tuition_fees.public.bachelor`` - the level is part
            # of the path already. Appending it again produced
            # ``...public.bachelor.bachelor``, which no derivation could reach, so
            # researched tuition existed in the corpus and was invisible to
            # ``derive_tuition`` for 14 of 17 countries while the refusal reason
            # said no researched data was present.
            #
            # The check is structural rather than per-country: any topic whose path
            # already names the level is left alone, and any level-agnostic topic
            # still gets one appended.
            if (
                topic in LEVEL_SENSITIVE_TOPICS
                and level in ("bachelor", "master", "phd")
                and (not claim_path or claim_path[-1] != level)
            ):
                claim_path = claim_path + [level]
            # The period becomes a child of the level node rather than being folded
            # into the level's own path, so a semester figure and an annual figure
            # for the same level stay distinct quantities. A year figure therefore
            # lands exactly on ``...public.<level>`` and is reachable; a semester
            # figure lands on ``...public.<level>.semester`` and is resolved by the
            # derivation layer, which annualises it deterministically and records
            # the lineage.
            if per in ("semester", "month") and "non_eu_per_semester" not in path:
                claim_path = claim_path + [per]

            dotted = ".".join(claim_path)
            # The zero rule itself lives in ``zero_cost_refusal`` and is applied
            # once ``node`` exists, further down. It used to sit here, and it never
            # fired: it wrote ``node["value"] = None`` while ``node`` was still
            # unbound (a NameError on the first zero claim, a silent mutation of the
            # *previous* claim's node on every later one), and the statement that
            # builds ``node`` immediately rebound the name, discarding the demotion
            # even in the runs where it did not raise. It also compared against a
            # set that always contained the claim's own source, because the fresh
            # path hardcodes ``archived: True`` for every artifact it reads. The
            # rule is stated once and called from every entry point instead; see
            # ``zero_cost_refusal``.

            is_monetary_slot = any(
                marker in dotted for marker in MONETARY_PATH_MARKERS
            )
            is_duration_slot = any(
                marker in dotted for marker in DURATION_PATH_MARKERS
            )
            # A duration slot needs a stated period. A claim without one is a
            # price or a count - "SEK application fee" is money, "0 bachelor
            # degrees qualify" is a count - and filing it under a duration makes
            # two different claims read as one: that something took no time, and
            # that something happened zero times.
            if is_duration_slot and per is None:
                claim_path = claim_path + [
                    "related_figures", str(claim.get("claim_id", "figure"))
                ]
                dotted = ".".join(claim_path)
            descriptive = topic in DESCRIPTIVE_TOPICS or (currency is None and is_monetary_slot)
            if descriptive and is_monetary_slot:
                # The number is real evidence, but it is not money - it is a rule, a
                # count or a duration that happened to be filed under a topic whose
                # primary figure is a cost. Routing it into the cost slot would make
                # it indistinguishable from a price and it would flow into a derived
                # total as one. So it is stored beside the slot as a related figure
                # and the gap says why.
                claim_path = claim_path + ["related_figures", str(claim.get("claim_id", "figure"))]
                dotted = ".".join(claim_path)
                gaps.append(
                    {
                        "field": f"{country.lower()}.{str(claim.get('claim_id', topic))}",
                        "reason": (
                            f"Archived figure recorded, but it is not a currency figure "
                            f"and its topic's primary field holds money. It is stored as "
                            f"a related figure rather than as a cost. Statement: "
                            f"{claim.get('statement', 'no statement given')}"
                        ),
                        "attempted_sources": [source_url],
                        "checked_at": artifact.get("retrieved_at"),
                    }
                )
            node: dict[str, Any] = {
                "value": value,
                "value_status": source_type
                if source_type in VALUE_STATUS
                else "INSTITUTIONAL_REPORT",
                "source_ids": [source_id],
            }
            if currency:
                node["currency"] = currency
            if per:
                node["per"] = per
            claim_as_of = claim.get("as_of") or artifact.get("as_of")
            if claim_as_of:
                node["as_of"] = str(claim_as_of)
            else:
                # A currency threshold without a date is a figure nobody can say is
                # current. Recorded as a gap rather than published undated.
                report.reason = (
                    f"{artifact_path.name}: claim {claim.get('claim_id')!r} is a "
                    f"time-sensitive figure with no as_of. An undated threshold cannot "
                    f"be told apart from a stale one."
                )
                return report
            statement = claim.get("statement")
            if statement:
                node["note"] = str(statement)
            if claim.get("study_level"):
                node["study_level"] = str(claim["study_level"])
            # After the note and study level are set: the income contract may
            # replace the note with the reason it demoted the claim, and running
            # first would let the original statement overwrite that reason.
            _apply_income_contract(node, artifact, claim, topic, dotted, currency, per, report)
            if descriptive:
                node["descriptive"] = True

            # The zero rule, applied at the boundary where a claim becomes a node -
            # after the node exists, so a demotion can actually stick. The identical
            # call is made in ``_audit_carried_claim`` for claims that arrive by
            # carry-forward, so a zero is judged on its evidence and never on
            # whether this build happened to re-derive it.
            archived_sources = {
                source["id"]
                for source in sources.values()
                if isinstance(source, dict) and source.get("archived")
            }
            _apply_zero_cost_contract(
                node, dotted, archived_sources, report, artifact,
            )

            if dotted in claimed_fields:
                # Several archived figures reached one corpus path.
                #
                # This is NOT automatically a conflict. A conflict means two
                # credible sources make contradictory claims about the same fact.
                # What actually happens here far more often is that one topic
                # covers several distinct figures - Australia's financial capacity
                # publishes a living-expenses element, an income-route figure and a
                # travel element; a Canadian tuition page gives a first-year figure,
                # a later-year figure and an incidental fee; a work-rights topic
                # carries 15 hours a week and a six-month job search.
                #
                # Those are not contradictions, and promoting them to CONFLICTING
                # would tell a student that two authorities disagree when in fact
                # one authority published several things. That is false precision
                # in the opposite direction to the one the status prevents.
                #
                # So the collision is published as a gap that names every figure and
                # says plainly which it is: the schema cannot yet separate them, and
                # no single value is published. A CONFLICTING claim is reserved for
                # research that explicitly declares one.
                existing_node = _dig(sections, claim_path)
                # Two **values** are needed before this is a collision at all.
                # Comparing with != alone treats a REFUSED or UNKNOWN node - whose
                # value is deliberately None - as a disagreement with the next
                # claim, and the rebuild below then overwrites the refusal with a
                # node that has no status, silently deleting the reason the figure
                # was not published. Absence is not a competing value.
                if (
                    existing_node
                    and existing_node.get("value") is not None
                    and value is not None
                    and existing_node.get("value") != value
                ):
                    # When two figures reach one path, the one the source actually
                    # published outranks one computed from another figure.
                    #
                    # Austria returned both: EUR 3,084/month, tabulated by Statistik
                    # Austria as "Vollzeit | Netto", and EUR 2,208.08 from
                    # "26 497 / 12", which the artifact itself labelled "DERIVED BY
                    # ARITHMETIC ONLY, NOT PUBLISHED BY THE SOURCE". Both are
                    # arithmetically sound and only one is a published net wage.
                    # Whichever arrives second used to win, which meant the
                    # official figure lost to a division.
                    _priority = _publication_priority
                    if _priority(existing_node) > _priority(node):
                        # The figure already stored is the better one. Keep it, and
                        # record the newcomer rather than dropping it.
                        gaps.append(
                            _superseded_gap(
                                country, dotted, existing_node, node, source_id,
                                claim_as_of, artifact, claimed_fields[dotted],
                            )
                        )
                        claimed_fields[dotted] = source_id
                        continue
                    alternatives = list(existing_node.get("colliding_values") or [])
                    if not alternatives:
                        alternatives = [
                            {
                                "value": existing_node.get("value"),
                                "currency": existing_node.get("currency"),
                                "per": existing_node.get("per"),
                                "source_ids": list(existing_node.get("source_ids") or []),
                                "as_of": existing_node.get("as_of"),
                                "statement": existing_node.get("note"),
                            }
                        ]
                    alternatives.append(
                        {
                            "value": value,
                            "currency": currency,
                            "per": per,
                            "source_ids": [source_id],
                            "as_of": claim_as_of,
                            "statement": claim.get("statement"),
                        }
                    )
                    seen: set[tuple[Any, ...]] = set()
                    deduped: list[dict[str, Any]] = []
                    for item in alternatives:
                        key = (
                            item.get("value"),
                            item.get("currency"),
                            item.get("per"),
                            tuple(item.get("source_ids") or ()),
                        )
                        if key in seen:
                            continue
                        seen.add(key)
                        deduped.append(item)

                    published = deduped[0]
                    _put(
                        sections,
                        claim_path,
                        {
                            "value": published.get("value"),
                            "value_status": source_type
                            if source_type in VALUE_STATUS
                            else "INSTITUTIONAL_REPORT",
                            "source_ids": list(published.get("source_ids") or []),
                            "as_of": published.get("as_of"),
                            "note": published.get("statement"),
                            # Every other figure for this topic travels with the
                            # claim, so nothing is silently dropped, but only one
                            # value is presented and the ambiguity is published.
                            "colliding_values": deduped,
                        },
                    )
                    if currency:
                        _put(sections, claim_path + ["currency"], currency)
                    if per:
                        _put(sections, claim_path + ["per"], per)

                    rendered = "; ".join(
                        f"{item.get('value')}"
                        + (f" {item['currency']}" if item.get("currency") else "")
                        + (f" per {item['per']}" if item.get("per") else "")
                        + f" ({', '.join(item.get('source_ids') or [])})"
                        for item in deduped
                    )
                    gaps.append(
                        {
                            "field": f"{country.lower()}.{dotted}",
                            "reason": (
                                f"{len(deduped)} archived figures reach this one corpus "
                                f"field, so the schema cannot yet publish them separately: "
                                f"{rendered}. These are distinct figures for one topic, "
                                f"not necessarily a contradiction between sources. No "
                                f"average was computed and no single value was chosen "
                                f"between them; the first is shown with the rest "
                                f"attached under colliding_values. Splitting the topic in "
                                f"TOPIC_PATHS is the reviewed fix."
                            ),
                            "attempted_sources": list(
                                dict.fromkeys(
                                    sid
                                    for item in deduped
                                    for sid in (item.get("source_ids") or [])
                                )
                            ),
                            "checked_at": artifact.get("retrieved_at"),
                        }
                    )
                    claimed_fields[dotted] = source_id
                    continue
            claimed_fields[dotted] = source_id
            _put(sections, claim_path, node)

    if not sources:
        report.reason = (
            f"No usable evidence for {country}. No file was written; research that "
            f"produced no citable source cannot become a profile."
        )
        return report

    currency = None
    for source in sources.values():
        currency = currency or source.get("currency")

    document = {
        "country": {
            "iso2": country,
            "name_en": display_name(country),
            "currency": None,
        },
        "contract_version": CONTRACT_VERSION,
        "research": {
            "researched_at": max(
                (str(s["retrieved_at"]) for s in sources.values() if s.get("retrieved_at")),
                default="",
            ),
            "evidence_artifact_count": len(
                list((raw_dir if raw_dir is not None else RESEARCH_RAW_DIR / country).glob("*.json"))
            ),
        },
        "sources": [sources[key] for key in sorted(sources)],
        "sections": sections,
        "gaps": sorted(gaps, key=lambda gap: str(gap.get("field"))),
    }

    report.normalisations = notes
    document = _merge_existing(document, report.path, report)
    problems = _validate_document(document, country)
    if problems:
        report.reason = (
            "Rejected by the corpus validator; no file written. " + "; ".join(problems)
        )
        return report

    corpus_dir.mkdir(parents=True, exist_ok=True)
    _write_country(report.path, document)
    report.written = True
    report.reason = (
        f"{len(sources)} source(s), {len(claimed_fields)} figure(s), "
        f"{len(gaps)} gap(s)."
    )
    return report


def _merge_existing(document: dict[str, Any], existing_path: Path, report: IngestReport) -> dict[str, Any]:
    """Carry forward claims the new build did not re-derive.

    A rebuild that only ever *writes* silently deletes reviewed data the moment a
    research pass returns fewer fields than the last one - which is the normal
    direction, because research is intermittent. Germany lost its blocked account,
    Blue Card and Bachelor-tuition claims exactly that way on the first run of this
    pipeline.

    So an existing claim is preserved when the new build says nothing about its
    path, and the new build wins wherever both have an opinion. Every preserved
    claim is recorded in the report rather than merged silently, because "this file
    now mixes figures from two evidence generations" is something a reviewer must
    be told.
    """
    if not existing_path.exists():
        return document
    try:
        previous = json.loads(existing_path.read_text(encoding="utf-8"))
    except (ValueError, OSError, UnicodeDecodeError):
        report.warnings.append(
            f"Existing {existing_path.name} could not be parsed, so nothing was carried "
            f"forward from it and the rebuild replaces it."
        )
        return document
    if not isinstance(previous, dict):
        return document

    previous_sources = {
        source["id"]: source
        for source in previous.get("sources", [])
        if isinstance(source, dict) and source.get("id")
    }
    merged_sources = {
        source["id"]: source
        for source in document.get("sources", [])
        if isinstance(source, dict) and source.get("id")
    }
    carried = 0

    # Source ids proven by an archived artifact for this country. A carried claim
    # citing one of these is backed by real evidence on disk; one citing anything
    # else rests on a source whose verbatim text was never archived.
    archived_source_ids = {
        source["id"]
        for source in document.get("sources", [])
        if isinstance(source, dict) and source.get("id") and source.get("archived")
    }

    unbacked: list[str] = []

    def _is_claim(candidate: Any) -> bool:
        return isinstance(candidate, dict) and "value_status" in candidate

    def _walk(node: Any, fresh: Any, prefix: str = "") -> Any:
        nonlocal carried
        if not isinstance(node, dict):
            # A previous value that is not a section - most often ``None``, which
            # is how an earlier build left a topic it had no evidence for. The old
            # code fell through here and kept the ``None``, so the fresh value was
            # silently discarded and the section stayed empty forever. This is not
            # cosmetic: it is why 16 countries carried a null ``career`` section and
            # silently kept refusing break-even after the net-income evidence
            # arrived. The fresh value must win whenever the previous one is not a
            # section to merge into.
            return fresh
        if fresh is not None and not isinstance(fresh, dict):
            return fresh
        result = dict(node)
        for key, value in node.items():
            if _is_claim(value):
                if not (isinstance(fresh, dict) and key in fresh):
                    result[key] = _audit_carried_claim(value, archived_source_ids, f"{prefix}.{key}".strip("."), unbacked)
                    carried += 1
                else:
                    result[key] = fresh[key]
            elif isinstance(value, dict):
                result[key] = _walk(
                    value,
                    fresh.get(key) if isinstance(fresh, dict) else None,
                    f"{prefix}.{key}".strip("."),
                )
            elif (
                not isinstance(value, (str, int, float, bool))
                and isinstance(fresh, dict)
                and key in fresh
            ):
                # The previous value is ``None`` (or another non-section) where
                # this build produced a section. Take the fresh one.
                #
                # Without this, a section an earlier build left as ``None`` could
                # never be populated by any later rebuild: the fresh value was
                # computed, then discarded, and the corpus kept refusing for lack
                # of evidence that was sitting in the archive the whole time. That
                # is how 16 countries kept a null ``career`` section and a refused
                # break-even after the net-income artifacts had arrived.
                result[key] = fresh[key]
        # Union at **every** depth, not only at the top level.
        #
        # The walk iterates the previous file's keys, so a section this build
        # produced under a key the previous build never had was computed and then
        # dropped. At the top level that was patched by the union below; nested, it
        # was not patched at all, so a fresh ``tuition_fees.public`` was lost
        # whenever the previous file happened to hold ``tuition_fees.by_state``.
        # The evidence was read, ingested, and discarded by the merge, silently, on
        # every run.
        #
        # A claim node is **not** unioned into a section. A previous
        # ``residency.citizenship`` holding six separate claims and a fresh
        # ``residency.citizenship`` holding one are different granularities, and
        # merging a claim's own keys (``value``, ``value_status``, ``source_ids``)
        # in as siblings of those claims would both destroy them and invent a
        # seventh. The previous section is the richer record of the two, so it is
        # kept whole.
        if isinstance(fresh, dict) and not _is_claim(fresh):
            for key, value in fresh.items():
                if key not in result:
                    result[key] = value
        return result

    # Normalise the previous file's path shape before merging against it.
    #
    # The committed corpus holds ``...public.bachelor.bachelor`` in 13 countries,
    # written by the bug this function is being fixed for. Repairing that here -
    # inside ingestion, from the raw archive - is the only route that satisfies the
    # rule that generated canonical JSON is never hand-edited to paper over a
    # pipeline defect. The previous document is re-shaped in memory before the walk
    # sees it, so both sides of the comparison carry the same canonical shape and
    # the claim is merged at the path the contract defines. Every claim, source id,
    # ``colliding_values`` entry and ``evidence_archived`` flag travels with it; only
    # the duplicated level component is removed, and a repair is recorded so the
    # change is visible rather than silent.
    previous_sections, renested, collisions = _renest_legacy_levels(previous.get("sections", {}))
    for path in renested:
        report.normalisations.append(
            f"{path}: legacy path named the study level twice; rebuilt at the "
            f"canonical path by this ingestion run"
        )
    for path in collisions:
        report.warnings.append(
            f"{path}: a legacy claim could not be re-nested because the canonical path "
            f"it maps to was already occupied. The first claim in document order was "
            f"kept; this one was not written, and no value was overwritten."
        )
    fresh_sections = document.get("sections", {})
    merged_sections = _walk(previous_sections, fresh_sections)
    # Union the two key sets. The walk only iterates the *previous* file's keys, so
    # a section the previous build simply never had - because at the time there was
    # no evidence for it - could never be introduced by any later rebuild. The
    # fresh value was computed, then dropped on the floor.
    #
    # This is why 16 countries kept a null ``career`` section and a refused
    # break-even after the net-income artifacts had already been archived: the
    # evidence was read, ingested into a fresh document, and then discarded by the
    # merge, silently and on every single run.
    for key, value in fresh_sections.items():
        if key not in merged_sections:
            merged_sections[key] = value
    document["sections"] = merged_sections
    for source_id, source in previous_sources.items():
        merged_sources.setdefault(source_id, source)

    document["sources"] = [merged_sources[key] for key in sorted(merged_sources)]

    # Every carried claim that no archived artifact backs becomes an explicit,
    # published gap. The claim itself is preserved - deleting it would erase the
    # record that someone once thought it worth publishing - but a student can no
    # longer meet it without also meeting the statement that its evidence was
    # never archived.
    #
    # Gaps are keyed by field before merging, because a rebuild reads the previous
    # output: appending unconditionally would publish a second identical gap on
    # every run and make the gap count a function of how often ingestion ran.
    existing_gaps = {
        gap.get("field"): gap
        for gap in document.get("gaps", [])
        if isinstance(gap, dict) and gap.get("field")
    }
    for path in unbacked:
        field = f"{report.iso2.lower()}.{path}"
        if field in existing_gaps:
            continue
        existing_gaps[field] = {
            "field": field,
            "reason": (
                "Carried forward from hand-curated data. This claim cites a source "
                "URL, but no archived artifact holds the verbatim extract it was read "
                "from, so the figure cannot be audited against the page that states it. "
                "The claim is retained rather than deleted, and is marked "
                "evidence_archived=false. Treat it as unverified until the source is "
                "archived."
            ),
            "checked_at": None,
        }
    document["gaps"] = [existing_gaps[key] for key in sorted(existing_gaps)]

    if carried:
        report.warnings.append(
            f"{carried} claim(s) carried forward from the previous {existing_path.name} "
            f"because this rebuild produced no evidence for them. Those claims are "
            f"hand-curated and their underlying raw evidence is not archived; review "
            f"them against a source before treating them as current."
        )
        report.normalisations.append(f"carried {carried} prior claim(s) forward")
    if unbacked:
        report.normalisations.append(
            f"marked {len(unbacked)} carried claim(s) evidence_archived=false and "
            f"published each as an explicit gap"
        )
    return document


def _audit_carried_claim(
    node: dict[str, Any], archived_source_ids: set[str], path: str, unbacked: list[str]
) -> dict[str, Any]:
    """Mark a carried claim whose raw evidence was never archived.

    The claim keeps its value and its ``value_status``. Downgrading it to
    ``UNVERIFIED`` would be a different and wrong claim - that asserts the figure
    came from a secondary source, when in fact it came from the ministry page named
    in ``source_ids`` and the only deficiency is that nobody archived the extract.

    So the deficiency is recorded where it can be seen, rather than by blurring a
    status that means something else: ``evidence_archived: false`` on the claim and
    a published gap naming it. A claim with no value (``UNKNOWN``) is left alone -
    it already states that nothing is established.
    """
    if node.get("value") is None:
        # Already carries no value. Normally that is the end of the line - the claim
        # states that nothing is established, so there is nothing to audit.
        #
        # A zero this rule refused is the exception. Demoting it set ``value`` to
        # None, so on the next rebuild this branch would be taken and the gap that
        # explains the refusal would never be republished - the reason would appear
        # once and then vanish, and a rebuild would silently change what the corpus
        # says about itself. Registering the path keeps the refusal published and
        # the output byte-identical between runs, which is the property the
        # determinism requirement depends on.
        if _ZERO_REFUSAL_MARKER in str(node.get("note") or ""):
            unbacked.append(path)
        return node

    audited = dict(node)
    already_marked = audited.get("evidence_archived") is False
    cited = set(audited.get("source_ids") or [])
    backed = bool(cited and cited & archived_source_ids)

    if not (already_marked or backed):
        # The verbatim extract is not in research_raw/, so the figure cannot be
        # audited against the page that states it. Recorded where it is seen, as
        # ``evidence_archived: false`` plus a published gap.
        #
        # Idempotence: the annotation is only ever applied once. A rebuild reads the
        # previous output, so an unguarded append would repeat itself on every pass
        # and grow the file without bound.
        unbacked.append(path)
        if not already_marked:
            audited["evidence_archived"] = False
            audited["note"] = (
                f"{audited.get('note', '').strip()} "
                "Carried forward from hand-curated data; the verbatim extract behind "
                "this figure is not in research_raw/, so it cannot be audited from the "
                "repository."
            ).strip()
    elif already_marked:
        unbacked.append(path)

    # The same zero rule the fresh path applies, run against the same evidence and
    # on **every** path through this function. A carried-forward claim is not
    # trusted for having survived a rebuild, and neither is one whose extract is
    # archived: "archived" answers only whether the page can be re-read, not whether
    # the zero is a claim about money. Skipping the rule on the early returns is
    # precisely how Germany's EUR 0/year outlived the rule that was written to stop
    # it.
    return _demote_unpublishable_zero(audited, path, archived_source_ids, [])


def _apply_zero_cost_contract(
    node: dict[str, Any],
    dotted: str,
    archived_source_ids: set[str],
    report: IngestReport,
    artifact: Mapping[str, Any] | None = None,
) -> None:
    """Apply the zero rule to a claim being written by this build.

    Thin wrapper so the fresh path and the carry-forward path call one rule, and so
    the fresh path also publishes a normalisation note and a gap naming the field -
    the carry-forward path publishes its own gap, because it has no artifact.
    """
    reason = zero_cost_refusal(node, dotted, archived_source_ids)
    if reason is None:
        return
    unbacked: list[str] = []
    _demote_unpublishable_zero(node, dotted, archived_source_ids, unbacked)
    report.normalisations.append(
        f"{dotted}: zero cost claim demoted to UNKNOWN because {reason}"
    )
    if artifact is not None:
        _publish_income_gap(report, dotted, str(node["note"]), unbacked, artifact)


def _demote_unpublishable_zero(
    node: dict[str, Any],
    dotted: str,
    archived_source_ids: set[str],
    unbacked: list[str],
) -> dict[str, Any]:
    """Demote ``node`` to UNKNOWN in place when its zero cannot be published.

    ``source_ids``, ``as_of`` and any ``colliding_values`` are deliberately
    **kept**. The figure is refused, not erased: a reviewer must still be able to see
    which document asserted the zero and when, or the rejection is unreviewable and
    the next pass cannot tell a refused zero from a zero that was never claimed.
    What stops being published is the value and its status.

    Idempotent by construction. A rebuild reads the previous output, so this runs
    again on every pass over a claim it already demoted; the note is appended only
    once, detected by the marker phrase below, or the file would grow without bound
    and the gap count would become a function of how often ingestion ran.
    """
    reason = zero_cost_refusal(node, dotted, archived_source_ids)
    if reason is None:
        return node
    unbacked.extend(str(item) for item in (node.get("source_ids") or []))
    node["value"] = None
    node["value_status"] = "UNKNOWN"
    if _ZERO_REFUSAL_MARKER not in str(node.get("note") or ""):
        node["note"] = (
            f"{node.get('note', '').strip()} This claim stated that the cost is zero, "
            f"and it is not published, because {reason}. A zero is a strong claim "
            f"rather than a missing value: it asserts the country charges nothing, and "
            f"it reaches a total that a reader treats as a budget. It is recorded as "
            f"UNKNOWN so the total refuses, which is the safe direction, rather than "
            f"publishing an unearned zero that understates the cost. The source and "
            f"date behind the refused claim are retained above."
        ).strip()
    return node


def _apply_income_contract(
    node: dict[str, Any],
    artifact: Mapping[str, Any],
    claim: Mapping[str, Any],
    topic: str,
    dotted: str,
    currency: str | None,
    per: str | None,
    report: IngestReport,
) -> None:
    """Enforce the net-income contract on an income claim as it is written.

    Two rules, both of which must hold regardless of what the artifact asserts
    about itself:

    1. **A net figure must carry its reference profile.** Take-home pay is a
       property of a tax year, a household and a residency status, not of a
       salary. A net figure without those is a naked scalar that reads as
       universal, so the claim is demoted to ``UNKNOWN`` with the missing keys
       named and a gap is published. It is not deleted and not accepted.

    2. **A gross figure can never occupy the net slot.** Checked here rather than
       trusted from the artifact, because a gross salary presented as take-home
       pay understates the months to repay by roughly half in most European
       countries - which is the specific wrong answer the break-even gate exists
       to refuse.

    Demotion rather than rejection is deliberate: rejecting would discard the
    evidence, and the evidence is real even when its placement is wrong. A gap
    that says "this is gross, and it was filed as net" tells a reviewer exactly
    what to fix.
    """
    is_net_topic = dotted == "career.net_monthly_income" or topic.startswith("net_")
    artifact_says_estimate = bool(artifact.get("estimate")) or bool(claim.get("estimate"))

    # Rule 2: gross in the net slot, by any signal.
    says_gross = str(claim.get("statement") or "").lower()
    basis = str(artifact.get("basis") or claim.get("basis") or "").lower()
    gross_signal = (
        basis == "gross"
        or "gross" in says_gross
        or "before tax" in says_gross
        or "brutto" in says_gross
        or "brut" in says_gross
    )
    if is_net_topic and gross_signal:
        report.normalisations.append(
            f"{dotted}: figure describes GROSS income and was filed on the net topic; "
            f"demoted to UNKNOWN rather than published as take-home pay"
        )
        node["value"] = None
        node["value_status"] = "UNKNOWN"
        node["note"] = (
            "This figure describes gross (before-tax) income, not take-home pay. It "
            "was filed on the net topic and has been demoted rather than published, "
            "because break-even must compare money out against money that actually "
            "reaches the worker. Using gross here would roughly halve the reported "
            "months in most European countries."
        )
        _publish_income_gap(
            report, dotted, node["note"], [str(source_id_of(node))], artifact
        )
        return

    if not is_net_topic:
        return

    # Rule 3: a derived net must cite a gross that someone else published.
    #
    # This is the rule that stops honest arithmetic from becoming a fabricated
    # country fact. A tax model applied to a real official salary produces a
    # correct answer to "what would this person take home" - which is not the same
    # question as "what does a graduate in this country take home". Without a
    # sourced gross for the population the claim describes, the result is a fact
    # about the tax system, not about the country, and publishing it on the net
    # topic would tell a student they will earn a number no source states.
    #
    # It applies to **derivations only**. A statistics office that publishes a net
    # median outright - Austria's Statistik Austria does exactly this, tabulating
    # "Vollzeit | Netto" - has no gross input to source, and the figure is exactly
    # as official as any other. Refusing it would be refusing the best evidence in
    # the set because of a defect it does not have.
    #
    # The tax parameters behind a refused derivation remain archived and
    # auditable; only the conclusion is declined.
    derivation = artifact.get("derivation")
    is_a_derivation = isinstance(derivation, Mapping) and (
        "gross_input" in derivation
        or "gross_input_eur_per_month" in derivation
        or "step_1_gross_jpy_per_month" in derivation
        or "method" in derivation
        or "net_working" in derivation
    )
    gross_declared_sourced = bool(
        is_a_derivation and derivation.get("gross_input_sourced") is True
    )
    if is_a_derivation and not gross_declared_sourced:
        detail = ""
        if isinstance(derivation, Mapping) and derivation.get("gross_input_note"):
            detail = f" The artifact states: {derivation['gross_input_note']}"
        refusal_reason = (
            "This figure is a tax-model evaluation at a chosen gross salary, not an "
            "observed net income. The arithmetic may be sound and the tax parameters "
            "official, but no source publishes a gross salary for the population this "
            "claim describes, so the result is a fact about the tax system rather than "
            f"about what someone in this country would take home.{detail}"
        )
        report.normalisations.append(
            f"{dotted}: derived net refused, its gross input is not independently "
            f"sourced"
        )
        node["value"] = None
        node["value_status"] = "REFUSED"
        # The full explanation goes in the refusal reason, not just in the note: a
        # REFUSED claim's note mirrors its reason, so a long note alone is discarded
        # at parse time and the reader would be left with a bare code.
        node["refusal"] = {
            "reason": refusal_reason,
            "required_input": (
                "A cited source publishing a gross salary for the same population, "
                "with its own URL and date."
            ),
            "operation": "net from gross via published tax parameters",
        }
        node["note"] = refusal_reason
        _publish_income_gap(report, dotted, refusal_reason, [str(source_id_of(node))], artifact)
        return

    # A figure the source did not publish must never present as one the source
    # published, however well-sourced the arithmetic behind it is.
    #
    # This was caught on Austria: an artifact carried a claim of EUR 2,208.08
    # whose own statement read "DERIVED BY ARITHMETIC ONLY, NOT PUBLISHED BY THE
    # SOURCE: 26 497 EUR / 12". The division is legitimate and deterministic, but
    # the result is not a figure the statistics office published, and labelling it
    # OFFICIAL_STATISTICS would have put a number into the corpus that no source
    # states. Detected from the claim's own words, because that is where a
    # researcher records it when the artifact has no structured derivation block.
    statement_text = " ".join(
        str(part)
        for part in (
            claim.get("statement"),
            artifact.get("notes"),
            artifact.get("evidence_limitations"),
        )
        if part
    ).lower()
    unpublished_by_source = any(
        marker in statement_text
        for marker in (
            "not published by the source",
            "derived by arithmetic",
            "not a published",
            "arithmetic only",
            "computed by dividing",
            "divided by 12",
            "not published by any source",
        )
    )
    if unpublished_by_source:
        report.normalisations.append(
            f"{dotted}: figure is arithmetic on a published figure, not a published "
            f"figure; demoted rather than presented as official"
        )
        node["value"] = None
        node["value_status"] = "REFUSED"
        node["note"] = (
            "Refused: this figure was computed from another published figure rather "
            "than published in its own right, so it cannot carry the source's "
            "authority. The underlying published figure belongs in the corpus; a "
            "derived monthly reading of an annual figure needs a registered formula "
            "before it can be shown, because 'a year divided by twelve' is not the "
            "same number as a monthly median and readers will treat it as one."
        )
        node["refusal"] = {
            "reason": str(node["note"]),
            "required_input": (
                "A monthly figure published by the source, or a registered formula "
                "that annual-to-monthly conversion is allowed to use."
            ),
            "operation": "period conversion",
        }
        _publish_income_gap(report, dotted, str(node["note"]), [str(source_id_of(node))], artifact)
        return

    # Rule 1: a net figure needs its circumstances.
    # A published population aggregate (a median across all employees) already has
    # the per-household variation averaged in, so it is not asked for a marital
    # status it does not have. Declared per artifact, and inferred from a
    # population that is a median/mean/average across everyone.
    population_text = str(
        artifact.get("population") or claim.get("population") or ""
    ).lower()
    if not population_text:
        # Researchers frequently state the population inside their prose
        # assumptions rather than in a dedicated field. Looking only at the
        # dedicated field missed Austria's published net median entirely, because
        # the population was described in a sentence: "population = employees ...
        # aged 15+". The prose is therefore searched too.
        raw_assumptions = artifact.get("assumptions")
        if isinstance(raw_assumptions, (list, tuple)):
            population_text = " ".join(str(a) for a in raw_assumptions).lower()
    is_population_aggregate = bool(artifact.get("population_aggregate")) or any(
        token in population_text
        for token in (
            "all employees",
            "all employed",
            "employees",
            "median",
            "average",
            "mean",
        )
    )
    profile = profile_from_raw(
        {
            **(
                artifact.get("assumptions") and {"assumptions": artifact["assumptions"]}
                or {}
            ),
            "population": artifact.get("population") or population_text or None,
            "tax_year": claim.get("tax_year") or artifact.get("tax_year") or claim.get("as_of") or artifact.get("as_of"),
            "currency": currency,
            "per": per,
            "basis_kind": "ESTIMATE" if artifact_says_estimate else "OFFICIAL",
            "limitations": artifact.get("evidence_limitations") or artifact.get("notes"),
            "population_aggregate": is_population_aggregate,
        }
    )
    try:
        validate_profile(profile, path=dotted)
    except NetIncomeError as exc:
        report.normalisations.append(
            f"{dotted}: net figure demoted to UNKNOWN, reference profile incomplete"
        )
        node["value"] = None
        node["value_status"] = "UNKNOWN"
        node["note"] = str(exc)
        _publish_income_gap(report, dotted, str(exc), [str(source_id_of(node))], artifact)
        return

    node["net_income_profile"] = profile.to_dict()
    node["basis"] = "net"
    if artifact_says_estimate and node["value_status"] in VALUE_STATUS:
        # An estimate must never present as an official figure, whatever the
        # artifact's own source_type says. The official-asserting value statuses
        # are exactly the official source types, so one public set covers both.
        if node["value_status"] in OFFICIAL_SOURCE_TYPES:
            node["value_status"] = "ESTIMATE"
        node.setdefault(
            "estimate_basis",
            "Secondary estimation rather than a figure published by an authority.",
        )


def source_id_of(node: Mapping[str, Any]) -> str:
    cited = node.get("source_ids") or []
    return cited[0] if cited else ""


def _publish_income_gap(
    report: IngestReport,
    dotted: str,
    reason: str,
    source_ids: list[str],
    artifact: Mapping[str, Any],
) -> None:
    report.income_gaps.append(
        {
            "field": dotted,
            "reason": reason,
            "attempted_sources": [
                url
                for url in [artifact.get("source_url"), *source_ids]
                if url
            ],
            "checked_at": artifact.get("retrieved_at"),
        }
    )


def _publication_priority(node: Mapping[str, Any]) -> int:
    """How authoritative a figure is, for choosing between two on one path.

    Three tiers, in descending order:

    2. A figure a source **published**. Its ``value_status`` is a real evidence
       status, and the source said the number itself.
    1. An ``ESTIMATE``. A real figure, but the evidence qualifies it as
       approximate - better than arithmetic on someone else's number, worse than
       the source's own.
    0. Anything **computed** from another figure: ``DERIVED``, ``REFUSED``,
       ``UNKNOWN``, or a value whose provenance is absent.

    The distinction that matters is 2 against 0. Dividing an official annual
    figure by twelve produces a perfectly reasonable monthly number, and it is
    not a number the statistics office published. If it can displace the real
    figure it is how a corpus ends up quoting arithmetic as fact.
    """
    status = node.get("value_status")
    if status == "ESTIMATE":
        return 1
    if status in {
        "OFFICIAL_GOVERNMENT",
        "OFFICIAL_REGIONAL_BODY",
        "OFFICIAL_STATISTICS",
        "UNIVERSITY_OFFICIAL",
        "INSTITUTIONAL_REPORT",
    }:
        return 2
    return 0


def _superseded_gap(
    country: str,
    dotted: str,
    kept: Mapping[str, Any],
    dropped: Mapping[str, Any],
    source_id: str,
    as_of: str | None,
    artifact: Mapping[str, Any],
    kept_source_id: str,
) -> dict[str, Any]:
    """Record a figure that lost to a better-sourced one, without discarding it.

    The losing figure is not deleted and not silently ignored. It becomes a gap
    that names both, says which was kept and why, and points at the source of each
    - so a reviewer can disagree with the ranking and find both numbers.
    """
    return {
        "field": f"{country.lower()}.{dotted}",
        "reason": (
            f"Two figures reach this field. Kept {kept.get('value')!r} from "
            f"{kept_source_id} ({kept.get('value_status')}), because a source "
            f"published it. Not published: {dropped.get('value')!r} from {source_id}, "
            f"which is computed from another published figure rather than published in "
            f"its own right. The computed figure is archived in full under its own "
            f"source id and is not a duplicate of the published one; it is a different "
            f"quantity. No average was taken and neither figure was invented."
        ),
        "attempted_sources": [
            url
            for url in (kept.get("source_ids") or [], dropped.get("source_ids") or [])
            if url
        ],
        "checked_at": artifact.get("retrieved_at"),
    }


def _dig(node: Any, path: list[str]) -> Any:
    current = node
    for part in path:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _renest_legacy_levels(sections: Any) -> tuple[Any, list[str], list[str]]:
    """Re-shape a previous document's paths so a level component appears once.

    Returns ``(rebuilt, repaired, collisions)``.

    The committed corpus contains ``...tuition_fees.public.bachelor.bachelor`` in 13
    countries, produced by a merge that recursed by dict-key position instead of by
    canonical path. Those files are generated artefacts, so the repair belongs in
    ingestion rather than in a hand edit: this reads the previous document, applies
    the same :func:`canonical_claim_path` rule the writer enforces, and moves every
    claim to the canonical path.

    Implemented as flatten-then-rebuild rather than a recursive rewrite. A recursive
    rewrite has to decide, at each level, whether a rebuilt child *is* the value for
    its key or a section that happens to contain it, and getting that wrong silently
    re-emits the nesting it was written to remove - which is what the first version
    of this function did. Flattening every leaf to its full path first makes the
    mapping from old path to new path explicit and total, so there is no level at
    which the shape can drift.

    Nothing is dropped. A claim keeps its ``value``, ``value_status``,
    ``source_ids``, ``as_of``, ``note``, ``colliding_values`` and
    ``evidence_archived`` flag; only the duplicated component is removed.

    If two claims land on one canonical path - a previous file holding both
    ``public.bachelor`` and ``public.bachelor.bachelor`` - the first in document
    order is kept and the second is reported in ``collisions`` rather than silently
    overwriting a reviewed claim with another. That case does not occur in the
    shipped corpus; it is handled so a future file cannot lose a claim without
    saying so.
    """
    leaves: list[tuple[tuple[str, ...], Any]] = []

    def _flatten(node: Any, path: tuple[str, ...]) -> None:
        if isinstance(node, dict) and "value_status" in node:
            leaves.append((path, node))
            return
        if isinstance(node, dict):
            for key, value in node.items():
                _flatten(value, path + (str(key),))
            return
        # A scalar or None left at a section position by an earlier build. It is
        # carried across at its own canonical path so it is not discarded.
        leaves.append((path, node))

    _flatten(sections, ())

    repaired: list[str] = []
    collisions: list[str] = []
    collisions_seen: set[tuple[str, ...]] = set()
    rebuilt: dict[str, Any] = {}
    for path, node in leaves:
        target = tuple(canonical_claim_path(list(path)))
        if target != path:
            repaired.append(".".join(path))
        if target in collisions_seen:
            collisions.append(".".join(path))
            continue
        collisions_seen.add(target)
        current = rebuilt
        for part in target[:-1]:
            child = current.get(part)
            if not isinstance(child, dict):
                child = {}
                current[part] = child
            current = child
        current[target[-1]] = dict(node) if isinstance(node, dict) else node

    return rebuilt, repaired, collisions


def _put(node: dict[str, Any], path: list[str], value: Any) -> None:
    """Write one canonical value, enforcing the path shape on the way in.

    This is the single point every canonical section write passes through, so it is
    where the "a level appears exactly once" rule is enforced. Enforcing it here
    rather than at the level-append step is deliberate: the append was already
    conditional, and the malformed path survived anyway because a *later* stage
    rebuilt it from whatever the previous file happened to contain. A rule applied
    once, at the writer, cannot be bypassed by a stage that has not been written
    yet.

    It is also not a fallback. The path is corrected, not searched for: a claim that
    was addressed to ``...public.bachelor.bachelor`` is stored at
    ``...public.bachelor``, and nothing here tries a second path when the first is
    absent.
    """
    canonical = canonical_claim_path(path)
    current = node
    for part in canonical[:-1]:
        current = current.setdefault(part, {})
    current[canonical[-1]] = value


def ingest_from_archive(
    corpus_dir: Path = CORPUS_DIR, manifest_path: Path = MANIFEST_PATH
) -> list[IngestReport]:
    """Ingest every country the manifest records as having archived evidence.

    The manifest is an **inventory**, not a driver: it records what was retrieved
    and what may be ingested. This function reads it as such, taking the
    eligibility of each scope from the manifest and then ingesting the country
    from its archived directory.

    It previously expected a single ``raw_file`` per country. That field described
    the old one-document-per-country layout and no longer exists, so a
    manifest-driven run reported every country as "marks this ARCHIVED but names
    no raw_file" - a confident message about a field the manifest has never
    contained since reconciliation. Eligibility now comes from the artifact
    inventory instead, which is what the manifest actually holds.

    A scope with no ingestion-eligible artifact is reported as such and nothing is
    attempted: the pipeline does not go looking for a document that was never
    saved, and it does not treat a manifest entry as a substitute for one.
    """
    if not manifest_path.exists():
        return []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    reports: list[IngestReport] = []
    for entry in manifest.get("countries", []):
        iso2 = str(entry.get("iso2", "")).upper()
        if not iso2:
            continue
        eligible = [
            item
            for item in entry.get("artifacts", [])
            if item.get("ingestion_eligible")
        ]
        if not eligible:
            reports.append(
                IngestReport(
                    iso2=iso2,
                    reason=(
                        f"{entry.get('raw_status', 'RAW_SOURCE_UNAVAILABLE')}: "
                        f"{len(entry.get('artifacts', []))} artifact(s) archived, none "
                        f"of them ingestion-eligible. No figure from this country was "
                        f"ingested. A summary of a finding is not a source document, "
                        f"and a figure whose provenance cannot be pointed at is not "
                        f"published."
                    ),
                )
            )
            continue
        reports.append(
            ingest_country_from_raw(iso2, corpus_dir=corpus_dir, raw_dir=None)
        )
    return reports


def check(corpus_dir: Path = CORPUS_DIR) -> list[str]:
    """Report every country file that would not survive a load.

    Exit status is what CI should branch on; this is the read-only counterpart of
    ingestion and is safe to run anywhere.
    """
    corpus = load_corpus(corpus_dir)
    problems = [problem.to_dict() for problem in corpus.problems]
    for problem in problems:
        print(f"  FAIL {problem['iso2']}: {problem['reason']}")
    for record in corpus.records:
        print(
            f"  ok   {record.iso2}  sources={len(record.sources)} "
            f"gaps={len(record.gaps)} claims={len(record.claims)}"
        )
    return [str(problem) for problem in problems]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic Country Intelligence ingestion.",
        epilog=(
            "There is no flag to skip a gate. A country that fails is not written, "
            "and the reason is printed."
        ),
    )
    parser.add_argument("--country", help="Ingest one ISO2 from the raw archive.")
    parser.add_argument(
        "--check", action="store_true",
        help="Validate every country file and exit non-zero on any failure.",
    )
    parser.add_argument(
        "--normalize", action="store_true",
        help="Rewrite research status spelling to canonical vocabulary in place.",
    )
    parser.add_argument(
        "--corpus-dir", default=None, help="Corpus directory (defaults to the shipped one).",
    )
    args = parser.parse_args(argv)

    corpus_dir = Path(args.corpus_dir) if args.corpus_dir else CORPUS_DIR

    contract_problems = registry_problems()
    if contract_problems:
        print("Formula registry is incoherent; refusing to ingest:", file=sys.stderr)
        for problem in contract_problems:
            print(f"  - {problem}", file=sys.stderr)
        return 2

    if args.check:
        print(f"Checking {corpus_dir}")
        problems = check(corpus_dir)
        print(f"{len(problems)} problem(s)")
        return 1 if problems else 0

    if args.normalize:
        reports = normalise_existing(corpus_dir)
        for report in reports:
            state = "wrote" if report.written else "kept "
            print(f"  {state} {report.iso2}: {report.reason}")
            for change in report.normalisations:
                print(f"        {change}")
        return 0

    if args.country:
        fx = build_fx_table(target=corpus_dir / "fx" / "rates.json")
        print(f"  {'wrote' if fx.written else 'skip '} FX: {fx.reason}")
        raw = RESEARCH_RAW_DIR / f"{args.country.upper()}.json"
        directory = RESEARCH_RAW_DIR / args.country.upper()
        if not directory.is_dir():
            print(
                f"No archived research directory at {directory}. A country whose raw "
                f"research is not archived cannot be ingested.",
                file=sys.stderr,
            )
            return 1
        reports = [ingest_country_from_raw(args.country.upper(), corpus_dir)]
    else:
        reports = [build_fx_table(target=corpus_dir / "fx" / "rates.json")]
        for directory in sorted(RESEARCH_RAW_DIR.glob("*/")):
            iso2 = directory.name.upper()
            if len(iso2) != 2 or not iso2.isalpha() or iso2 == "_GLOBAL":
                continue
            reports.append(ingest_country_from_raw(iso2, corpus_dir))
        if not any(r.iso2 == "FX" for r in reports):
            reports.insert(0, build_fx_table(target=corpus_dir / "fx" / "rates.json"))

    failures = 0
    for report in reports:
        state = "wrote" if report.written else "skip "
        print(f"  {state} {report.iso2}: {report.reason}")
        for warning in report.warnings:
            print(f"        ! {warning}")
        if not report.written and report.iso2:
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())