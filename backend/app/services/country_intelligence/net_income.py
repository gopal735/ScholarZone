"""The reference profile a net-income figure has to declare before it can ship.

## Why "net" is not a number

Take-home pay is not a property of a salary. It is a property of a salary *and a
set of circumstances*, and the circumstances are not a rounding detail - in most
European countries they move take-home pay by several thousand euros a year:

- **Tax year.** Every figure expires when the budget changes. A net figure whose
  year is unstated cannot be checked against the table it came from.
- **Marital status and dependents.** This is usually the single largest
  adjustment, and it is a *family* fact, not an employment fact. A "median net
  wage" computed over all households silently averages together households that
  pay very different tax.
- **Residency.** Several countries (notably Singapore, and parts of the Nordic
  system) tax residents and non-residents differently. A resident's net is not a
  student's net.
- **Employee social contributions.** Pension, health and unemployment insurance
  are deducted from gross in most European systems and from nothing in others. In
  Singapore CPF is the mirror image: a large, mandatory, *saving* deduction that
  never reaches the worker but still changes what "take-home" means.
- **The population the figure describes.** A median across all graduates is not a
  median for a new graduate in a specific field.

So this module makes those circumstances part of the data. A net figure that does
not declare them is rejected rather than published, because a number without its
assumptions reads as more precise than it is and a student budgeting four years
cannot see what is missing.

## What this deliberately does not do

It does not ship a tax model. It is tempting to implement seventeen national
tax systems from published brackets, and that temptation is exactly where a
fabricated number would come from: a bracket boundary transcribed wrongly, a
social contribution rate from the wrong year, an allowance applied twice. A
silently wrong tax model produces a confidently wrong break-even, which is worse
than the refusal this corpus ships today.

Instead the contract distinguishes two honest routes to a net figure:

1. **Published.** An authority states the net directly, or publishes a net-gross
   table whose output we read. The figure is official and the table is the
   evidence.
2. **Derived.** Only where the full progressive computation can be reproduced
   from cited parameters by a registered closed formula. Until that exists for a
   country, that country has no net figure.

Between those sits a third state that is not a failure: an estimate. A reputable
secondary model can inform a student, provided it is labelled ``ESTIMATE`` and
carries the assumptions that make it computable at all.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

#: The circumstances a net figure must declare, and why each one is required.
#:
#: Ordered by how much damage the omission does. ``tax_year`` is first because it
#: is the one that silently invalidates a figure: a net amount from a superseded
#: tax year still looks entirely plausible.
REQUIRED_ASSUMPTIONS: dict[str, str] = {
    "tax_year": (
        "The tax year the figure belongs to. A net amount from a superseded year "
        "still looks plausible, so an unstated year cannot be inferred."
    ),
    "marital_status": (
        "Single or married. Usually the largest single adjustment to take-home "
        "pay, and a family fact rather than an employment fact."
    ),
    "dependents": (
        "Number of dependents claimed, or an explicit statement that none are "
        "claimed. A household-level median silently averages different household "
        "tax positions together."
    ),
    "residency": (
        "Resident or non-resident status, where the jurisdiction distinguishes "
        "them. Several systems tax residents and non-residents differently."
    ),
    "employee_social_contributions": (
        "Whether pension, health and unemployment contributions are deducted from "
        "this figure, and which. Some systems have no such deduction; Singapore's "
        "CPF is a large deduction that never reaches the worker."
    ),
    "population": (
        "Who the figure describes - all employees, all graduates, or new "
        "graduates in a field. A median across all graduates is not a median for "
        "someone in their first job."
    ),
}

#: Assumptions that are worth recording but do not block publication, because a
#: reasonable figure can omit them and say so.
OPTIONAL_ASSUMPTIONS: dict[str, str] = {
    "jurisdiction": (
        "The specific region, municipality or state. Italian IRPEF add-ons and "
        "Swedish tax tables both vary by municipality, so a national figure must "
        "say whether it is a national average or a single-jurisdiction figure."
    ),
    "occupation": "The occupation or field the figure covers, where known.",
    "employment_type": "Full-time, part-time, permanent or contract.",
    "method": "How the figure was produced, for secondary estimates.",
}

#: Assumptions whose value is a meaningful assertion rather than free text, so a
#: value of ``None`` or an empty string cannot pass.
_ENUMS: dict[str, frozenset[str]] = {
    "marital_status": frozenset({"single", "married", "single_person", "couple"}),
    "residency": frozenset({"resident", "non_resident", "both_reported"}),
    "dependents": frozenset({"none", "some", "varies"}),
}

#: The employee-contribution disclosure, which is a question rather than a number
#: and so has a closed answer set.
_SOCIAL_ANSWERS = frozenset(
    {
        "included",
        "excluded",
        "partial",
        "not_applicable",
        "cpf_included_as_saving",
    }
)

_ALL = tuple(REQUIRED_ASSUMPTIONS) + tuple(OPTIONAL_ASSUMPTIONS)


class NetIncomeError(ValueError):
    """A net-income reference profile failed validation."""


@dataclass(frozen=True)
class NetIncomeProfile:
    """The circumstances under which a net-income figure is true.

    Stored beside the value rather than in a comment, because the value is
    meaningless without it and a comment is the first thing a transformation
    strips.
    """

    #: The assumptions themselves. Free text, with the keys in
    #: :data:`REQUIRED_ASSUMPTIONS` and :data:`OPTIONAL_ASSUMPTIONS`.
    assumptions: Mapping[str, str] = field(default_factory=dict)
    #: The population the figure describes, e.g. "median take-home pay, all
    #: employees". Duplicated out of ``assumptions`` so a reader can be told what
    #: a number is about without parsing a dict.
    population: str | None = None
    #: The tax year, e.g. "2026". Required.
    tax_year: str | None = None
    #: The currency the figure is in.
    currency: str | None = None
    #: ``month`` or ``year``. Required: a net figure with no period cannot be
    #: compared with a cost figure.
    per: str | None = None
    #: ``OFFICIAL`` for an authority's own published figure, ``DERIVED`` for a
    #: reproduced computation, ``ESTIMATE`` for a secondary model.
    basis_kind: str | None = None
    #: Anything a reader would be misled by if they saw only the number.
    limitations: str | None = None
    #: ``True`` when the figure is a **population aggregate** - a median or mean
    #: published across everyone in a population, rather than computed for one
    #: hypothetical person.
    #:
    #: This exists because demanding a marital status of a published median is
    #: wrong, and requiring it would have discarded the best net figure in the
    #: corpus. Austria's Statistik Austria tabulates ``Vollzeit | Netto`` across all
    #: employees: the households with and without children, and the single and the
    #: married, are already inside that median. Asking which marital status the
    #: figure assumes has no answer, because it spans all of them. Demanding one
    #: would have refused an official, published, directly-quoted net wage on a
    #: technicality - and would have pushed the research toward inventing a
    #: "typical person" to satisfy a field that does not apply.
    #:
    #: A population aggregate still requires ``population`` and ``tax_year``,
    #: because those genuinely determine what the number is about.
    population_aggregate: bool = False

    #: How a net figure was arrived at.
    BASIS_KINDS = ("OFFICIAL", "DERIVED", "ESTIMATE")

    def missing_required(self) -> list[str]:
        """Required assumption keys with nothing usable in them.

        ``tax_year`` and ``population`` are also promoted dataclass fields so a
        reader can be told what a number is about without parsing a dict, so they
        are looked up in **both** places. Checking only the dict would report them
        missing on a fully specified profile, which is how a required-field check
        gets quietly disabled.
        """
        missing: list[str] = []
        for key, _reason in REQUIRED_ASSUMPTIONS.items():
            value = self.assumptions.get(key)
            if value is None or not str(value).strip():
                # Fall back to the promoted field of the same name.
                promoted = getattr(self, key, None)
                if promoted is None or not str(promoted).strip():
                    missing.append(key)
        if not (self.tax_year and str(self.tax_year).strip()):
            missing.append("tax_year")
        if not (self.per and str(self.per).strip()):
            missing.append("per")

        if self.population_aggregate:
            # A population aggregate has no single household behind it. The
            # per-person circumstances are already averaged into the number, so
            # requiring them would force a researcher to invent a "typical person"
            # for a figure that does not describe one.
            ignored = {
                "marital_status",
                "dependents",
                "residency",
                "employee_social_contributions",
            }
            return sorted(set(missing) - ignored)
        return sorted(set(missing))

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "assumptions": dict(sorted(self.assumptions.items())),
            "required_assumptions": list(REQUIRED_ASSUMPTIONS),
        }
        for attr in (
            "population", "tax_year", "currency", "per", "basis_kind",
            "limitations", "population_aggregate",
        ):
            value = getattr(self, attr)
            if value is not None and value != ("" if attr == "population_aggregate" else None):
                payload[attr] = value
        return payload

    def describe(self) -> str:
        """One sentence a student can read next to the number.

        Without this the figure is a naked scalar, and a naked scalar is exactly
        what a reader assumes is universal.
        """
        parts = []
        if self.tax_year:
            parts.append(f"{self.tax_year} tax year")
        if self.population:
            parts.append(self.population)
        for key in ("marital_status", "dependents", "residency", "jurisdiction"):
            value = self.assumptions.get(key)
            if value:
                parts.append(f"{key.replace('_', ' ')}: {value}")
        social = self.assumptions.get("employee_social_contributions")
        if social:
            parts.append(f"social contributions {social}")
        return "; ".join(parts) if parts else "assumptions not stated"


def validate_profile(profile: NetIncomeProfile, *, path: str) -> None:
    """Reject a net figure that has not declared where it applies.

    Raising rather than defaulting is deliberate. Defaulting a missing
    marital status to "single" would produce a confident number for a household
    that is not single, and the reader would have no way to know the assumption
    was ours rather than the source's.
    """
    missing = profile.missing_required()
    if missing:
        reasons = "; ".join(
            f"{key} ({REQUIRED_ASSUMPTIONS.get(key, 'needed for a period to exist')})"
            for key in missing
        )
        raise NetIncomeError(
            f"{path}: a net-income figure must declare the circumstances it holds "
            f"under. Missing: {reasons}. Defaulting any of these would publish a "
            f"confident number for a household, tax year or residency status nobody "
            f"stated."
        )

    if profile.basis_kind is not None and profile.basis_kind not in profile.BASIS_KINDS:
        raise NetIncomeError(
            f"{path}: basis_kind {profile.basis_kind!r} is not one of "
            f"{', '.join(profile.BASIS_KINDS)}."
        )

    # Where the source gave a closed set of values, an invented one is a sign the
    # reader was not looking at the source.
    for key, allowed in _ENUMS.items():
        value = profile.assumptions.get(key)
        if value is not None and str(value).strip().lower() not in allowed:
            raise NetIncomeError(
                f"{path}: assumption {key}={value!r} is not one of "
                f"{', '.join(sorted(allowed))}. If the situation is genuinely "
                f"something else, say so in notes rather than inventing a new "
                f"value that no reader can interpret."
            )

    social = profile.assumptions.get("employee_social_contributions")
    if social is not None and str(social).strip().lower() not in _SOCIAL_ANSWERS:
        raise NetIncomeError(
            f"{path}: employee_social_contributions={social!r} is not one of "
            f"{', '.join(sorted(_SOCIAL_ANSWERS))}. This field is the difference "
            f"between a salary and what reaches the worker, and 'some' is not an "
            f"answer."
        )


def profile_from_raw(raw: Mapping[str, Any] | None) -> NetIncomeProfile:
    """Build a profile from a stored/ingested mapping.

    Tolerant on purpose: a profile missing fields is *validated* by
    :func:`validate_profile` and reported with a reason, rather than crashing
    here. A missing assumption is a finding, not an exception to be swallowed
    somewhere deeper.
    """
    raw = dict(raw or {})
    # Research output may state assumptions as a list of prose sentences rather
    # than a structured mapping. That is not machine-checkable, so it is preserved
    # verbatim as prose and the per-person keys stay absent - which means a derived
    # figure is still demoted, while a population aggregate (which does not need
    # them) can still be published with its full context attached.
    raw_assumptions = raw.get("assumptions")
    if isinstance(raw_assumptions, Mapping):
        assumptions = dict(raw_assumptions)
    else:
        assumptions = {}
        if isinstance(raw_assumptions, (list, tuple)):
            raw = {**raw, "assumptions_prose": [str(a) for a in raw_assumptions]}
    return NetIncomeProfile(
        assumptions=assumptions,
        population=raw.get("population") or assumptions.get("population"),
        tax_year=raw.get("tax_year") or raw.get("as_of"),
        currency=raw.get("currency"),
        per=raw.get("per"),
        basis_kind=raw.get("basis_kind"),
        limitations=raw.get("limitations") or raw.get("note"),
        population_aggregate=bool(raw.get("population_aggregate")),
    )


__all__ = [
    "OPTIONAL_ASSUMPTIONS",
    "REQUIRED_ASSUMPTIONS",
    "NetIncomeError",
    "NetIncomeProfile",
    "profile_from_raw",
    "validate_profile",
]