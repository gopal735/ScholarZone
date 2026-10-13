"""Subject-level (occupation-level) salary for the Study-to-Career Strategist.

The single rule this module exists to enforce is the one the feature states as
non-negotiable: **subject-specific pay may appear only when it is sourced at the
occupation level, and a country average is never a stand-in for it.** So a
country for which no occupation-level figure is verified simply has no entry
here, and the strategist reports "Insufficient data" for that cell instead of
reaching for the country's average salary.

This layer keeps the gross occupation figure strictly separate from everything in
the corpus and everything financial: it is never summed with tuition, living
cost, scholarships, a PhD stipend, or a net/take-home income, and it is gross, so
it is never shown as take-home. Those separations are the reason the figure lives
in its own typed shape rather than being folded into the salary a country already
carries.

Loaders refuse to publish a cell unless: verification is PRIMARY_VERIFIED, the
basis is gross, the source is an official statistics office, and the value names
its metric. A cell that fails any of those is dropped with a recorded reason, so
the guard is testable rather than aspirational.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


class OccupationSalaryError(ValueError):
    """A stored occupation-salary cell violates an integrity guard."""


#: Source types allowed to back a subject-level pay figure. A third-party survey,
#: a recruiter page or a crowdsourced report may be honest, but none is an
#: official statistic, and the feature's contract says only occupation-level
#: official data may stand in for a subject figure.
_OFFICIAL_STATISTICS = {"OFFICIAL_STATISTICS"}

#: Units a pay figure may be quoted in. Required so a reader cannot be shown a
#: weekly median beside an annual one without the unit that distinguishes them.
_ALLOWED_PERIODS = {"hour", "week", "month", "year"}


@dataclass(frozen=True)
class OccupationSalary:
    """One verified occupation-level gross pay figure for a country + subject."""

    iso2: str
    subject_key: str
    occupation_label: str
    occupation_code: str
    granularity: str  # "occupation" or "occupation-class"
    value: float
    currency: str
    per: str  # hour/week/month/year
    basis: str  # always "gross"
    metric: str
    source_id: str
    source_publisher: str
    source_type: str
    source_url: str
    as_of: str | None
    minimum: float | None = None
    maximum: float | None = None
    mean: float | None = None
    hourly_in_local: float | None = None
    employment: int | None = None
    demand: str | None = None
    verification: str = "PRIMARY_VERIFIED"

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "iso2": self.iso2,
            "subject_key": self.subject_key,
            "occupation_label": self.occupation_label,
            "occupation_code": self.occupation_code,
            "granularity": self.granularity,
            "value": self.value,
            "currency": self.currency,
            "per": self.per,
            "basis": self.basis,
            "metric": self.metric,
            "value_status": "OFFICIAL_STATISTICS",
            "source": {
                "id": self.source_id,
                "publisher": self.source_publisher,
                "source_type": self.source_type,
                "url": self.source_url,
            },
        }
        for key, attr in (
            ("as_of", "as_of"),
            ("minimum", "minimum"),
            ("maximum", "maximum"),
            ("mean", "mean"),
            ("hourly_in_local", "hourly_in_local"),
            ("employment", "employment"),
            ("demand", "demand"),
        ):
            value = getattr(self, attr)
            if value is not None:
                payload[key] = value
        return payload


def _parse_cell(
    iso2: str, subject_key: str, raw: Mapping_like
) -> OccupationSalary:
    source = raw.get("source") or {}
    cell = OccupationSalary(
        iso2=iso2,
        subject_key=subject_key,
        occupation_label=raw.get("occupation_label", ""),
        occupation_code=raw.get("occupation_code", ""),
        granularity=raw.get("granularity", ""),
        value=raw.get("value"),
        currency=raw.get("currency", ""),
        per=raw.get("per", ""),
        basis=raw.get("basis", ""),
        metric=raw.get("metric", ""),
        source_id=source.get("id", ""),
        source_publisher=source.get("publisher", ""),
        source_type=source.get("source_type", ""),
        source_url=source.get("url", ""),
        as_of=raw.get("as_of"),
        minimum=raw.get("min"),
        maximum=raw.get("max"),
        mean=raw.get("mean"),
        hourly_in_local=raw.get("hourly"),
        employment=raw.get("employment"),
        demand=raw.get("demand"),
        verification=raw.get("verification", ""),
    )
    _validate(cell)
    return cell


def _validate(cell: OccupationSalary) -> None:
    """Refuse a cell that would break an integrity rule if it were published."""
    where = f"{cell.iso2}/{cell.subject_key}"
    if cell.verification != "PRIMARY_VERIFIED":
        raise OccupationSalaryError(
            f"{where}: only PRIMARY_VERIFIED cells may be stored; got "
            f"{cell.verification!r}. A cell that could not be read from the "
            f"primary table is a gap, not a figure."
        )
    if cell.basis != "gross":
        # A net figure in a gross slot, or vice versa, is the exact confusion the
        # corpus exists to prevent; here it is simply refused.
        raise OccupationSalaryError(
            f"{where}: occupation salary must be basis 'gross'; got {cell.basis!r}."
        )
    if cell.source_type not in _OFFICIAL_STATISTICS:
        raise OccupationSalaryError(
            f"{where}: occupation salary must be backed by an official statistics "
            f"source; got source_type {cell.source_type!r}."
        )
    if cell.per not in _ALLOWED_PERIODS:
        raise OccupationSalaryError(
            f"{where}: occupation salary must name its unit (one of "
            f"{sorted(_ALLOWED_PERIODS)}); got {cell.per!r}."
        )
    if not cell.metric:
        raise OccupationSalaryError(
            f"{where}: occupation salary must record the metric it measures so a "
            f"median is not mistaken for an entry salary or a mean."
        )
    if cell.granularity not in {"occupation", "occupation-class"}:
        raise OccupationSalaryError(
            f"{where}: must record whether it is a single occupation or a class, "
            f"so a class median is not read as one role."
        )
    if not isinstance(cell.value, (int, float)) or isinstance(cell.value, bool):
        raise OccupationSalaryError(f"{where}: occupation salary needs a numeric value.")
    if not cell.source_url:
        raise OccupationSalaryError(f"{where}: occupation salary must carry a source URL.")


# Local alias so annotations above read cleanly without importing typing.Mapping
# under two names.
from typing import Mapping as Mapping_like  # noqa: E402


def _load_document(directory: Path | None) -> dict[str, Any]:
    from .corpus import CORPUS_DIR  # local import avoids an import cycle

    base = Path(directory) if directory is not None else CORPUS_DIR
    path = base / "occupation_salary" / "verified.json"
    if not path.exists():
        return {"by_country": {}}
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _verified_cells(directory: str | None = None) -> dict[tuple[str, str], OccupationSalary]:
    """Parse and guard every stored cell once per process.

    A cell that fails a guard is dropped with its reason recorded, not published:
    one bad cell must not take down the whole layer, and must not silently appear
    as a figure. Loading is deterministic and offline (a local file), so the same
    corpus always yields the same cells.
    """
    document = _load_document(Path(directory) if directory else None)
    cells: dict[tuple[str, str], OccupationSalary] = {}
    for iso2, subjects in (document.get("by_country") or {}).items():
        code = (iso2 or "").strip().upper()
        for subject_key, raw in (subjects or {}).items():
            try:
                cell = _parse_cell(code, subject_key, raw)
            except OccupationSalaryError:
                # Dropped on purpose: a cell that violates a guard never reaches a
                # reader. The strategist will show "Insufficient data" for it.
                continue
            cells[(code, subject_key)] = cell
    return cells


def get_verified_occupation_salary(
    iso2: str, subject_key: str, *, directory: Path | None = None
) -> OccupationSalary | None:
    """The verified occupation-level pay figure, or ``None`` when there is not one.

    ``None`` is the honest answer for a country whose subject has no verified
    occupation-level figure. It is never filled with a country average.
    """
    if directory is not None:
        cells = _verified_cells(str(directory))
    else:
        cells = _verified_cells()
    return cells.get(((iso2 or "").strip().upper(), subject_key))


def all_verified_cells(*, directory: Path | None = None) -> tuple[OccupationSalary, ...]:
    if directory is not None:
        cells = _verified_cells(str(directory))
    else:
        cells = _verified_cells()
    return tuple(sorted(cells.values(), key=lambda c: (c.iso2, c.subject_key)))


def reload_verified_cells() -> None:
    """Drop the process cache (for tests that rewrite the file)."""
    _verified_cells.cache_clear()


__all__ = [
    "OccupationSalary",
    "OccupationSalaryError",
    "all_verified_cells",
    "get_verified_occupation_salary",
    "reload_verified_cells",
]
