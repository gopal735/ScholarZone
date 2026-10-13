"""The Study-to-Career Strategist.

One decision experience across subject, degree, funding model, budget, country,
career, work rights, post-study work, permanent residence and citizenship, built
entirely on top of the existing Country Intelligence plane. It adds no new facts:
it reads validated corpus claims, the measured scholarship plane, the verified
occupation-salary layer and the sourced FX table, and it composes them into a
comparison that refuses to lie.

The rules this module is written to make unbreakable, and which the tests assert:

* A missing figure is "Insufficient data" with a reason. It is never 0, never
  averaged into a total, never sorted as cheapest or highest.
* A country gets no overall recommendation while an *essential* criterion is
  unsourced, and no country is ever called the universal best. The essential set is
  `subject_salary` + `post_study_work` (the study-to-career spine): cost is shown
  and weighted but its frequent absence lowers evidence completeness and raises a
  risk note rather than silently suppressing career/work facts.
* Tuition (gross, public, per year), living cost (per month), scholarship count,
  stipend, PhD salary, gross and net are kept in separate cells. They are never
  summed here. Subject salary is gross and comes only from an occupation-level
  source; a country salary average is shown, if at all, labelled as a country-level
  context figure and never as subject pay.
* There is no single composite score. Comparison is criterion-by-criterion, and the
  user's weights + selection rule are echoed back so the ranking rule is fully
  visible.
* No admission probability, visa-approval odds or immigration outcome is invented;
  pathway steps are sourced, dated, informational facts with official links.

Budget and funding model change the *interpretation* only, from researched evidence:
budget is scored against each sourced cost figure **separately** (years of tuition,
never summed with months of living), and the funding note is driven by **measured**
degree-level scholarship counts (never fabricated, never subject-matched). When a
figure is missing the budget verdict is "Insufficient", never a zero.

The module is a pure composition of the corpus: no database writes, and it is
gated behind a default-off feature flag at the router.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable, Mapping

from ..country_intelligence import fx
from ..country_intelligence.corpus import get_corpus
from ..country_intelligence.derive import derive_living, find_claim
from ..country_intelligence.provenance import resolve_freshness
from ..country_intelligence.occupation_salary import OccupationSalary
from ..country_intelligence.occupation_salary import (
    get_verified_occupation_salary,
)
from .subjects import SUBJECTS, get_subject

#: Ceiling on countries compared in one result, matching the existing compare
#: router's max ``compare_countries``. The frontend also caps selection at six.
MAX_COMPARE_COUNTRIES = 6
DEFAULT_STALE_AFTER_DAYS = 730

_DEGREES = {"bachelor", "master", "phd"}
_FUNDING_MODELS = {"fully_funded", "tuition_only", "partial", "self_funded"}

# The seven criteria. Exactly the financial and pathway dimensions the feature
# names, kept as separate cells so nothing is merged. ``essential`` marks the
# criteria without which a country cannot be given an overall recommendation.
CRITERIA: tuple[dict[str, Any], ...] = (
    {"key": "tuition", "label_en": "Tuition (public, gross, per year)",
     "category": "cost", "essential": False, "higher_is_better": False, "money": True},
    {"key": "living_cost", "label_en": "Living cost (monthly, medium)",
     "category": "cost", "essential": False, "higher_is_better": False, "money": True},
    {"key": "funding_opportunities", "label_en": "Fully-funded scholarships (count)",
     "category": "funding", "essential": False, "higher_is_better": True, "money": False},
    {"key": "subject_salary", "label_en": "Subject-level salary (gross, occupation-level)",
     "category": "career", "essential": True, "higher_is_better": True, "money": True},
    {"key": "post_study_work", "label_en": "Post-study work (job-seeker) route",
     "category": "pathway", "essential": True, "higher_is_better": True, "money": False},
    {"key": "permanent_residence", "label_en": "Permanent residence route",
     "category": "pathway", "essential": False, "higher_is_better": True, "money": False},
    {"key": "citizenship", "label_en": "Citizenship / naturalisation",
     "category": "pathway", "essential": False, "higher_is_better": True, "money": False},
)

CRITERIA_INDEX = {criterion["key"]: criterion for criterion in CRITERIA}
TOTAL_CRITERIA = len(CRITERIA)
DEFAULT_WEIGHTS = {
    "cost": 25, "funding": 15, "career": 30, "pathway": 30,
}


def essential_criteria() -> tuple[str, ...]:
    """The criteria that must be sourced for a country to be ranked at all.

    Derived from ``CRITERIA`` so the flags, the ranking gate, the API's published
    ``essential_criteria`` list and the tests can never drift apart.
    """
    return tuple(k for k, meta in CRITERIA_INDEX.items() if meta["essential"])


@dataclass(frozen=True)
class ValidationError(ValueError):
    message: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message


def _bdt(value: Any, currency: str | None) -> dict[str, Any]:
    """Convert a sourced money figure to BDT with both source legs published.

    Uses the sourced composition (original -> USD via ECB -> USD -> BDT via
    Bangladesh Bank). When either leg is missing the conversion is refused and the
    reason is returned; the figure is never invented and the original currency is
    always preserved.
    """
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return {"value": None, "unavailable_reason": "No numeric amount to convert."}
    code = (currency or "").strip().upper()
    if not code:
        return {"value": None, "unavailable_reason": "No currency recorded on the figure."}
    try:
        result = fx.convert_to_bdt(float(value), code)
    except fx.FxUnavailable as exc:
        return {"value": None, "unavailable_reason": str(exc)}
    return {
        "value": result["value"],
        "from_currency": code,
        "legs": result["legs"],
        "rate_dates": [leg.get("rate_date") for leg in result["legs"] if leg.get("rate_date")],
        "caveat": result["caveat"],
        "unavailable_reason": None,
    }


def budget_interpretation(
    cell: Mapping[str, Any], budget_bdt: float | None
) -> dict[str, Any]:
    """How a person's BDT budget relates to one cost cell.

    Scored **per cell**, so tuition and living are never added together. A cost cell
    with no sourced figure yields "Insufficient" with the reason and no number; a
    figure whose currency cannot be converted yields "unavailable" with the FX
    reason. Neither is ever turned into zero. Only the reference date and the two
    sourced legs behind the BDT figure are quoted, so the coverage number is
    traceable to the same evidence as the cost itself.
    """
    unit_word = (
        "months of living cost" if cell.get("criterion") == "living_cost"
        else "years of public tuition"
    )
    if budget_bdt is None:
        return {"status": "no_budget", "note": "No budget provided, so coverage against your budget is not assessed."}
    if cell.get("status") != "sourced" or cell.get("value") is None:
        return {
            "status": "insufficient",
            "bdt_budget": budget_bdt,
            "note": f"Cannot assess budget coverage: {(cell.get('reason') or 'the figure is not sourced')}. No zero is assumed.",
        }
    per_bdt = (cell.get("bdt") or {}).get("value")
    if not isinstance(per_bdt, (int, float)) or per_bdt <= 0:
        reason = (cell.get("bdt") or {}).get("unavailable_reason") or "No sourced BDT conversion is available for this figure."
        return {
            "status": "unavailable",
            "bdt_budget": budget_bdt,
            "note": f"Cannot convert this cost to BDT, so budget coverage is not assessed: {reason}.",
        }
    covered = budget_bdt / per_bdt
    covered_rounded = round(covered, 1)
    if budget_bdt == 0:
        return {"status": "computed", "bdt_budget": 0, "unit": unit_word, "value": 0.0, "per_bdt": per_bdt,
                "note": "Your budget is zero, so it covers no period of this cost."}
    return {
        "status": "computed",
        "bdt_budget": budget_bdt,
        "unit": unit_word,
        "value": covered_rounded,
        "per_bdt": per_bdt,
        "per": cell.get("per"),
        "note": f"Your BDT budget covers about {covered_rounded} {unit_word}. Tuition and living are shown separately and never summed.",
    }


def _sources_payload(record: Any, source_ids: Iterable[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for source_id in source_ids:
        source = record.source(source_id)
        if source is not None:
            out.append({
                "id": source.id,
                "publisher": source.publisher,
                "title": source.title,
                "url": source.url,
                "source_type": source.source_type,
                "as_of": source.as_of,
            })
        else:
            out.append({"id": source_id})
    return out


def _base_cell(criterion: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "criterion": criterion["key"],
        "label_en": criterion["label_en"],
        "category": criterion["category"],
        "essential": criterion["essential"],
        "higher_is_better": criterion["higher_is_better"],
        "status": "unknown",
        "reason": None,
        "value": None,
        "currency": None,
        "per": None,
        "basis": None,
        "granularity": None,
        "value_status": None,
        "as_of": None,
        "freshness": None,
        "stale_warning": False,
        "sources": [],
        "bdt": None,
    }


def _apply_freshness(
    cell: dict[str, Any], as_of: str | None,
    *, reference_date: str | date | None, stale_after_days: int,
) -> None:
    # Normalise a month-only as_of ("2025-05") to a full date so a dated month is
    # not silently reported as UNDATED (cannot be dated) when it can be dated.
    anchor = as_of
    if isinstance(anchor, str) and len(anchor) == 7 and anchor[4] == "-":
        anchor = f"{anchor}-01"
    cell["freshness"] = resolve_freshness(
        anchor, reference_date=reference_date, stale_after_days=stale_after_days,
    )
    cell["stale_warning"] = cell["freshness"] in {"STALE", "UNDATED"}


def _money_cell(
    record: Any, criterion: Mapping[str, Any], *,
    value: Any, currency: str | None, per: str | None, value_status: str | None,
    source_ids: Iterable[str], as_of: str | None, reference_date, stale_after_days,
    basis: str | None = None,
) -> dict[str, Any]:
    cell = _base_cell(criterion)
    cell.update({
        "status": "sourced",
        "value": value, "currency": currency, "per": per, "basis": basis,
        "value_status": value_status, "as_of": as_of,
        "sources": _sources_payload(record, source_ids),
        "bdt": _bdt(value, currency),
    })
    _apply_freshness(
        cell, as_of, reference_date=reference_date, stale_after_days=stale_after_days,
    )
    return cell


def _insufficient(criterion: Mapping[str, Any], reason: str) -> dict[str, Any]:
    cell = _base_cell(criterion)
    cell["status"] = "insufficient"
    cell["value_status"] = "UNKNOWN"
    cell["reason"] = reason
    return cell


def _gross_tuition_claim(record: Any, degree: str) -> Any | None:
    """The **gross** public tuition figure for a degree, unmerged with any scholarship.

    Tuition is its own cell: it is never reduced by a scholarship proportion here,
    because a funded award and an unfunded student need different numbers and one
    figure cannot be both. Both canonical corpus shapes are read (a per-year figure,
    and a figure stated per semester/month which keeps its stated unit rather than
    being silently annualised). Returns ``None`` when no figure is sourced.
    """
    for path in (
        ("education_costs", "tuition_fees", "public", degree),
        ("education_costs", "tuition_fees", "public", degree, "year"),
        ("education_costs", "tuition_fees", "public", degree, "semester"),
        ("education_costs", "tuition_fees", "public", degree, "month"),
    ):
        claim = record.claim(*path)
        if claim is not None and claim.publishes_a_number:
            return claim
    return None


def _tuition_cell(
    record: Any, degree: str, *, reference_date, stale_after_days,
) -> dict[str, Any]:
    criterion = CRITERIA_INDEX["tuition"]
    claim = _gross_tuition_claim(record, degree)
    if claim is None:
        return _insufficient(
            criterion,
            f"Public tuition for {degree} is not sourced for this country. No zero is "
            f"assumed and no country average is substituted; check university or "
            f"state fee schedules directly.",
        )
    return _money_cell(
        record, criterion, value=claim.value, currency=claim.currency, per=claim.per,
        value_status=claim.value_status, source_ids=claim.source_ids, as_of=claim.as_of,
        reference_date=reference_date, stale_after_days=stale_after_days,
    )


def _living_cell(record: Any, *, reference_date, stale_after_days) -> dict[str, Any]:
    criterion = CRITERIA_INDEX["living_cost"]
    claim = find_claim(record.claims, ("living_costs", "monthly_costs", "medium", "total"))
    if claim is None or not getattr(claim, "publishes_a_number", False):
        return _insufficient(
            criterion,
            "A medium monthly living-cost total is not sourced for this country. No "
            "national average is substituted, so budget entirely from other sources.",
        )
    return _money_cell(
        record, criterion, value=claim.value, currency=claim.currency, per=claim.per,
        value_status=claim.value_status, source_ids=claim.source_ids, as_of=claim.as_of,
        reference_date=reference_date, stale_after_days=stale_after_days,
    )


def funding_scenario(
    facts: Any, degree: str, funding_model: str | None
) -> dict[str, Any]:
    """How the chosen funding model reads against **measured** scholarship counts.

    The counts come from the catalogue's measured plane; they are degree-level, so
    they are never matched to the chosen subject, and they are never presented as a
    promise. Only the interpretation changes with the funding model - no figure is
    invented, none is turned into zero, and no country is dropped for having few.
    """
    fully = int(getattr(facts, "fully_funded", 0) or 0) if facts is not None else 0
    total = int(getattr(facts, "scholarships", 0) or 0) if facts is not None else 0
    if total == 0:
        base = (
            f"No {degree} scholarships are currently measured for this country in the "
            f"catalogue. That is a measurement of listings, not a statement that none "
            f"exist; search each programme directly."
        )
    else:
        base = (
            f"Measured for {degree}: {fully} fully-funded of {total} listed "
            f"scholarships. These are degree-level counts, are not matched to your "
            f"subject, and are not a promise of an award."
        )
    model_notes = {
        "fully_funded": "You want a fully-funded place: prioritise countries with the most fully-funded listings, but read each award on its own terms.",
        "tuition_only": "You want tuition covered: the catalogue does not split tuition-only awards, so treat tuition as unfunded unless an award states otherwise.",
        "partial": "Partial help is not measured at country level: any partial coverage must be read from each award's terms.",
        "self_funded": "You plan to self-fund, so budget coverage against tuition and living (shown separately) matters most; fully-funded listings appear only as an alternative.",
    }
    return {
        "funding_model": funding_model,
        "degree": degree,
        "fully_funded_count": fully,
        "total_count": total,
        "subject_matched": False,
        "note": base,
        "model_note": model_notes.get(funding_model or "", ""),
    }


def _funding_cell(
    iso2: str, degree: str, funding_model: str | None, measured: Mapping[str, Any],
) -> dict[str, Any]:
    criterion = CRITERIA_INDEX["funding_opportunities"]
    facts = measured.get(iso2) if measured else None
    scenario = funding_scenario(facts, degree, funding_model)
    if facts is None or not getattr(facts, "scholarships", 0):
        return _insufficient(
            criterion,
            "No scholarship listings are currently measured for this degree level. "
            "This is a measurement of listings, kept separate from cost and pay.",
        ) | {"scenario": scenario}
    cell = _base_cell(criterion)
    cell.update({
        "status": "sourced",
        "value_status": "MEASURED",
        "value": scenario["fully_funded_count"],
        "per": "fully-funded listings",
        "sources": [{"id": "catalogue", "publisher": "ScholarZone catalogue (measured)"}],
        "detail": {"fully_funded": scenario["fully_funded_count"],
                   "total_listings": scenario["total_count"], "degree": degree},
        "basis": "count",
        "scenario": scenario,
    })
    return cell


def _subject_salary_cell(
    iso2: str, subject_key: str, record: Any, *,
    reference_date, stale_after_days,
) -> dict[str, Any]:
    criterion = CRITERIA_INDEX["subject_salary"]
    salary: OccupationSalary | None = get_verified_occupation_salary(iso2, subject_key)
    if salary is None:
        return _insufficient(
            criterion,
            "No occupation-level pay figure is officially sourced for this country and "
            "subject. A country salary average is not used here because it is not a "
            "subject-level figure.",
        )
    cell = _base_cell(criterion)
    payload = salary.to_dict()
    cell.update({
        "status": "sourced",
        "value": salary.value,
        "currency": salary.currency,
        "per": salary.per,
        "basis": salary.basis,
        "granularity": salary.granularity,
        "value_status": payload["value_status"],
        "as_of": salary.as_of,
        "occupation_label": salary.occupation_label,
        "occupation_code": salary.occupation_code,
        "sources": [{
            "id": salary.source_id, "publisher": salary.source_publisher,
            "source_type": salary.source_type, "url": salary.source_url,
        }],
        "bdt": _bdt(salary.value, salary.currency),
        "demand": salary.demand,
        "note": (
            "This is a gross, whole-occupation median, not entry-level, not "
            "degree-specific and not take-home pay."
            + ("" if salary.granularity == "occupation"
               else " It is an occupation-CLASS median, so it spans several related roles.")
        ),
    })
    if salary.minimum is not None or salary.maximum is not None:
        cell["range"] = {"min": salary.minimum, "max": salary.maximum, "average": salary.value}
    _apply_freshness(
        cell, salary.as_of, reference_date=reference_date, stale_after_days=stale_after_days,
    )
    return cell


def _node(record: Any, claim_path: tuple[str, ...]) -> Mapping[str, Any] | None:
    section: Any = record.sections
    for part in claim_path:
        if not isinstance(section, Mapping) or part not in section:
            return None
        section = section[part]
    return section if isinstance(section, Mapping) else None


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _deep_leaf(record: Any, claim_path: tuple[str, ...]) -> dict[str, Any] | None:
    """Descend a residency block to the deepest scalar leaf.

    A route such as the job-seeker permit is stored as ``duration`` with the real
    figure under ``duration.month`` (occasionally further nested per degree), so
    reading the branch head yields a parent with no number. This descends through
    single-child mappings until it finds a numeric field, and returns the supporting
    metadata for that figure rather than for the branch it hides under. A branch or
    a prose-only node returns ``None`` for the figure while still being detectable
    as present.
    """
    node = _node(record, claim_path)
    if node is None:
        return None
    if _is_number(node.get("value")):
        return {"value": node.get("value"), "per": node.get("per"),
                "as_of": node.get("as_of"), "note": node.get("note"),
                "source_ids": list(node.get("source_ids") or ())}
    for child_key, child in node.items():
        if isinstance(child, Mapping):
            deeper = _deep_leaf(record, claim_path + (child_key,))
            if deeper is not None:
                return deeper
    return None


def _step_source_ids(record: Any, claim_path: tuple[str, ...]) -> list[str]:
    """Walk from the deepest leaf up to find attached source ids.

    The corpus inherits source metadata at block level, so a figure may sit under a
    path that carries the ids, or one level up may. The first non-empty set going up
    the branch wins. When none can be found, the caller records a missing-source
    reason rather than claiming a source that is not there.
    """
    for depth in range(len(claim_path), 0, -1):
        sub = claim_path[:depth]
        claim = record.claim(*sub)
        if claim is not None and getattr(claim, "source_ids", None):
            return list(claim.source_ids)
        node = _node(record, sub)
        if isinstance(node, Mapping) and node.get("source_ids"):
            return list(node.get("source_ids") or ())
    return []


PATHWAY_STEPS: tuple[tuple[str, tuple[str, ...]]] = (
    ("student_residence_permit", ("residency", "student_residence_permit", "duration")),
    ("post_study_work", ("residency", "job_seeker_residence_permit", "duration")),
    ("work_permit", ("residency", "blue_card")),
    ("permanent_residence", ("residency", "permanent_residence")),
    ("citizenship", ("residency", "citizenship")),
)

_PATHWAY_CRITERIA = {
    "post_study_work": (
        CRITERIA_INDEX["post_study_work"],
        ("residency", "job_seeker_residence_permit", "duration"),
    ),
    "permanent_residence": (
        CRITERIA_INDEX["permanent_residence"], ("residency", "permanent_residence"),
    ),
    "citizenship": (
        CRITERIA_INDEX["citizenship"], ("residency", "citizenship"),
    ),
}


def _pathway_cell(
    record: Any, criterion: Mapping[str, Any], *,
    claim_path: tuple[str, ...], reference_date, stale_after_days,
) -> dict[str, Any]:
    leaf = _deep_leaf(record, claim_path)
    node = _node(record, claim_path)
    if leaf is None and node is None:
        return _insufficient(
            criterion,
            f"No sourced {criterion['label_en'].lower()} route is recorded for this "
            f"country. This is informational and is not a statement that the route does "
            f"or does not exist; verify with the official immigration authority.",
        )
    cell = _base_cell(criterion)
    source_ids = _step_source_ids(record, claim_path)
    if leaf is not None:
        cell.update({
            "status": "sourced", "value": leaf["value"], "per": leaf["per"],
            "value_status": "DERIVED", "as_of": leaf["as_of"],
            "sources": _sources_payload(record, source_ids),
            "note": leaf["note"],
        })
    else:
        cell.update({
            "status": "sourced", "value_status": "DERIVED", "value": None,
            "sources": _sources_payload(record, source_ids),
            "as_of": node.get("as_of"),
            "note": node.get("note") or "Route described in the corpus.",
        })
    if not cell["sources"]:
        cell["source_missing_reason"] = (
            "This route is present in the corpus but no official source link is "
            "attached at this step; verify directly with the immigration authority."
        )
    _apply_freshness(
        cell, cell.get("as_of"), reference_date=reference_date, stale_after_days=stale_after_days,
    )
    return cell


def _pathway_cell_for(
    record: Any, key: str, *, reference_date, stale_after_days,
) -> dict[str, Any]:
    criterion, path = _PATHWAY_CRITERIA[key]
    return _pathway_cell(
        record, criterion, claim_path=path,
        reference_date=reference_date, stale_after_days=stale_after_days,
    )


def pathway_timeline(
    iso2: str, *, reference_date=None, stale_after_days=DEFAULT_STALE_AFTER_DAYS,
) -> dict[str, Any]:
    """The student-visa -> ... -> citizenship timeline for one country.

    Each step is a separate sourced fact with its condition, source, source link
    and checked date. A step the corpus does not cover is returned as
    "Insufficient data" with its reason, so gaps are visible rather than skipped.
    Nothing here is a guarantee; every step links to the official source.
    """
    corpus = get_corpus()
    record = corpus.get((iso2 or "").strip().upper())
    steps: list[dict[str, Any]] = []
    if record is None:
        return {"iso2": (iso2 or "").upper(), "steps": [], "reason": "Country not in the researched corpus."}
    for name, path in PATHWAY_STEPS:
        leaf = _deep_leaf(record, path)
        node = _node(record, path)
        if leaf is None and node is None:
            steps.append({
                "step": name, "status": "insufficient",
                "reason": "No sourced pathway data for this step.",
                "condition": None, "source": None, "as_of": None, "official_link": None,
            })
            continue
        source_ids = _step_source_ids(record, path)
        sources = _sources_payload(record, source_ids)
        link = next((s.get("url") for s in sources if s.get("url")), None)
        condition = (leaf or {}).get("note") or (node or {}).get("note")
        as_of = (leaf or {}).get("as_of") or (node or {}).get("as_of")
        step: dict[str, Any] = {
            "step": name,
            "status": "sourced" if leaf is not None else "informational",
            "value": (leaf or {}).get("value"),
            "per": (leaf or {}).get("per"),
            "condition": condition,
            "as_of": as_of,
            "sources": sources,
            "official_link": link,
        }
        if not sources:
            step["source_missing_reason"] = (
                "This route is present in the corpus but no official source link is "
                "attached at this step; verify directly with the immigration authority."
            )
        _apply_freshness(
            step, as_of, reference_date=reference_date, stale_after_days=stale_after_days,
        )
        steps.append(step)
    return {"iso2": record.iso2, "name": record.name, "steps": steps,
            "disclaimer": "Informational only; not legal or immigration advice. Verify every step with the official authority."}


def _country_cells(
    iso2: str, *, degree: str, subject_key: str, funding_model: str | None,
    measured: Mapping[str, Any], reference_date, stale_after_days, budget_bdt: float | None,
) -> dict[str, dict[str, Any]]:
    record = get_corpus().get(iso2)
    if record is None:
        return {}
    cells: dict[str, Any] = {}
    cells["tuition"] = _tuition_cell(record, degree, reference_date=reference_date, stale_after_days=stale_after_days)
    cells["living_cost"] = _living_cell(record, reference_date=reference_date, stale_after_days=stale_after_days)
    cells["funding_opportunities"] = _funding_cell(iso2, degree, funding_model, measured)
    cells["subject_salary"] = _subject_salary_cell(iso2, subject_key, record, reference_date=reference_date, stale_after_days=stale_after_days)
    cells["post_study_work"] = _pathway_cell_for(record, "post_study_work", reference_date=reference_date, stale_after_days=stale_after_days)
    cells["permanent_residence"] = _pathway_cell_for(record, "permanent_residence", reference_date=reference_date, stale_after_days=stale_after_days)
    cells["citizenship"] = _pathway_cell_for(record, "citizenship", reference_date=reference_date, stale_after_days=stale_after_days)
    # Budget interpretation is applied per cost cell only, and never sums the two.
    for key in ("tuition", "living_cost"):
        cells[key]["budget_interpretation"] = budget_interpretation(cells[key], budget_bdt)
    return cells


def _evidence_completeness(cells: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    sourced = sorted(k for k, c in cells.items() if c["status"] == "sourced")
    missing = sorted(k for k, c in cells.items() if c["status"] != "sourced")
    return {
        "sourced": len(sourced), "total": TOTAL_CRITERIA,
        "fraction": f"{len(sourced)}/{TOTAL_CRITERIA}",
        "criteria_sourced": sourced, "criteria_missing": missing,
    }


def _essential_complete(cells: Mapping[str, Mapping[str, Any]]) -> bool:
    return all(cells[key]["status"] == "sourced" for key in essential_criteria())


def _why(cells: Mapping[str, Mapping[str, Any]], weights: Mapping[str, int]) -> dict[str, list[str]]:
    recommended: list[str] = []
    risks: list[str] = []
    for key, meta in CRITERIA_INDEX.items():
        cell = cells[key]
        weight = weights.get(meta["category"], 0)
        if cell["status"] == "sourced":
            if meta["essential"] and weight >= 20:
                recommended.append(
                    f"Prioritised {meta['label_en'].lower()} is sourced"
                    + (" and currently dated." if not cell["stale_warning"] else " (but stale - re-verify)."),
                )
        else:
            if meta["essential"]:
                risks.append(f"{meta['label_en']}: {cell['reason']}")
            else:
                risks.append(f"{meta['label_en']}: not sourced in the corpus.")
        if cell["status"] == "sourced" and cell["stale_warning"]:
            risks.append(
                f"{meta['label_en']} is stale/undated ({cell['freshness']}); re-verify before relying on it.",
            )
    return {"recommended": recommended, "risks": risks}


def plan(
    session: Any,
    *,
    subject_key: str,
    degree: str,
    funding_model: str | None = None,
    budget_bdt: float | None = None,
    weights: Mapping[str, int] | None = None,
    iso2s: Iterable[str] | None = None,
    reference_date: str | date | None = None,
    stale_after_days: int = DEFAULT_STALE_AFTER_DAYS,
) -> dict[str, Any]:
    """Compare countries on the seven criteria, with no composite score.

    A country is only ``comparison`` (ranked) when every essential criterion is
    sourced; otherwise it is placed in ``insufficient_data`` with the reasons it
    cannot be ranked. When no explicit country list is given, the default set is the
    best-evidenced countries by a deterministic rule (most sourced criteria, then
    ISO code) - so the code, not a hardcoded slice, decides what "best-covered"
    means. Weights and the selection rule are echoed back so nothing is hidden.
    """
    subject = get_subject(subject_key)
    if subject is None:
        raise ValidationError(f"Unknown subject {subject_key!r}.")
    degree = (degree or "").strip().lower()
    if degree not in _DEGREES:
        raise ValidationError(f"degree must be one of {sorted(_DEGREES)}; got {degree!r}.")
    if funding_model is not None and funding_model not in _FUNDING_MODELS:
        raise ValidationError(f"funding_model must be one of {sorted(_FUNDING_MODELS)}.")
    budget_bdt = float(budget_bdt) if isinstance(budget_bdt, (int, float)) and not isinstance(budget_bdt, bool) and budget_bdt >= 0 else None
    active_weights = dict(DEFAULT_WEIGHTS)
    if weights:
        for key, value in weights.items():
            if key in active_weights and isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
                active_weights[key] = int(value)

    corpus = get_corpus()
    measured: Mapping[str, Any] = {}
    if session is not None:
        from ..country_intelligence.catalogue import measure_country_catalogue
        measured = measure_country_catalogue(session).by_country

    entries: list[dict[str, Any]] = []
    for record in corpus:
        iso2 = record.iso2
        cells = _country_cells(
            iso2, degree=degree, subject_key=subject_key, funding_model=funding_model,
            measured=measured, reference_date=reference_date,
            stale_after_days=stale_after_days, budget_bdt=budget_bdt,
        )
        completeness = _evidence_completeness(cells)
        ranked = _essential_complete(cells)
        entries.append({
            "iso2": iso2, "name": record.name,
            "currency": record.currency,
            "evidence_completeness": completeness,
            "cells": cells,
            "ranked": ranked,
            "why": _why(cells, active_weights),
        })

    skipped: list[str] = []
    if iso2s:
        requested = []
        for code in iso2s:
            up = (code or "").strip().upper()
            if up in corpus.iso2_codes and up not in requested:
                requested.append(up)
            elif up and up not in skipped:
                skipped.append(up)
        # Explicit selection: preserve the caller's order, capped at six.
        selected = [e for e in entries if e["iso2"] in requested]
        selected.sort(key=lambda e: requested.index(e["iso2"]))
        selected = selected[:MAX_COMPARE_COUNTRIES]
        selection_rule = (
            "Explicit country list supplied by you; capped at six."
        )
    else:
        # Deterministic evidence-coverage selection: most sourced criteria first,
        # ISO code ascending as a stable tie-break. This is what 'best-covered'
        # means and it is computed, not hardcoded.
        ordered = sorted(
            entries, key=lambda e: (-e["evidence_completeness"]["sourced"], e["iso2"]),
        )
        selected = ordered[:MAX_COMPARE_COUNTRIES]
        selection_rule = (
            f"Default selection shows the top {MAX_COMPARE_COUNTRIES} countries by "
            f"evidence completeness (most of {TOTAL_CRITERIA} criteria sourced), "
            f"ties broken by ISO code ascending, so 'best-covered' is computed rather "
            f"than asserted. Pass an explicit iso2s list to compare a set you choose."
        )

    comparison = [e for e in selected if e["ranked"]]
    insufficient = []
    for e in selected:
        if e["ranked"]:
            continue
        e = dict(e)
        e["not_ranked_reason"] = (
            "An essential criterion ("
            + " or ".join(essential_criteria())
            + ") is missing, so this country is not given an overall rank and is "
            "never claimed as 'best'."
        )
        insufficient.append(e)

    return {
        "request": {
            "subject_key": subject_key, "subject_name_en": subject.name_en,
            "degree": degree, "funding_model": funding_model, "budget_bdt": budget_bdt,
            "weights": active_weights, "max_countries": MAX_COMPARE_COUNTRIES,
            "essential_criteria": list(essential_criteria()),
        },
        "ranking_rule": (
            f"No single composite score is shown. Comparison is criterion-by-criterion. "
            f"A country appears in 'comparison' only when every essential criterion is "
            f"sourced; the essential criteria are {list(essential_criteria())}. Cost cells "
            f"are shown and weighted, but a missing cost lowers the evidence meter and "
            f"raises a risk note rather than removing a country. Weights above are the "
            f"ones you set, echoed back unchanged."
        ),
        "selection_rule": selection_rule,
        "subject_coverage_note_en": subject.coverage_note_en,
        "criteria": [dict(c) for c in CRITERIA],
        "comparison": comparison,
        "insufficient_data": insufficient,
        "skipped_iso2": skipped,
        "disclaimer": (
            "Informational only. This is not legal, immigration, financial or admission "
            "advice, and no admission, visa or citizenship outcome is predicted."
        ),
    }


def coverage_matrix(
    *, subjects: Iterable[str] | None = None, reference_date=None,
) -> dict[str, Any]:
    """Country x subject evidence matrix for the admin data-gap report."""
    corpus = get_corpus()
    keys = list(subjects) if subjects else [s.key for s in SUBJECTS]
    rows: list[dict[str, Any]] = []
    for iso2 in corpus.iso2_codes:
        for subject_key in keys:
            salary = get_verified_occupation_salary(iso2, subject_key)
            rows.append({
                "country_iso2": iso2, "subject_key": subject_key,
                "subject_salary": "sourced" if salary else "insufficient",
                "occupation": salary.occupation_label if salary else None,
                "source_url": salary.source_url if salary else None,
                "as_of": salary.as_of if salary else None,
            })
    return {
        "subjects": keys,
        "countries": list(corpus.iso2_codes),
        "matrix": rows,
        "gaps": [
            {"country_iso2": r["country_iso2"], "subject_key": r["subject_key"]}
            for r in rows if r["subject_salary"] == "insufficient"
        ],
        "note": (
            "subject_salary here means occupation-level pay verified against a primary "
            "official source. 'insufficient' means no such source is held; it is a "
            "research gap to prioritise, never to backfill from a country average."
        ),
    }


def subject_catalog() -> list[dict[str, Any]]:
    return [
        {
            "key": s.key, "name_en": s.name_en, "name_bn": s.name_bn,
            "occupation_slug": s.occupation_slug,
            "taxonomy_fields": list(s.taxonomy_fields),
            "coverage_note_en": s.coverage_note_en,
        }
        for s in SUBJECTS
    ]


__all__ = [
    "CRITERIA", "MAX_COMPARE_COUNTRIES", "ValidationError",
    "budget_interpretation", "coverage_matrix", "essential_criteria",
    "funding_scenario", "plan", "pathway_timeline", "subject_catalog",
]
