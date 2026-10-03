"""The arithmetic that turns component scores into a fit score, and nothing else.

Every formula in ScholarZone Match that combines components lives here, so the
mathematics can be read in one place and tested in isolation from the catalogue,
the database and the interface.

Four quantities are produced, in this order:

**Coverage-aware fit**

        Fit = SUM(W_i x C_i x E_i) / SUM(W_i x E_i)

``W_i`` is a component's configured weight, ``C_i`` its score in [0, 100], and
``E_i`` is 1 when the component was evaluated and 0 when it was not. An
unevaluated component is excluded from *both* halves of the fraction. It is never
substituted with a zero, because that would convert "we could not measure this"
into "you scored zero here", and it is never dropped from only one half, which
would inflate the result.

When the denominator is zero - no dimension could be evaluated at all - the fit
score is ``None``. Reporting ``0`` there would assert the fit is terrible when
the truth is that there is nothing to say.

**Coverage**

    Coverage = SUM(W_i x E_i) / 1.0 x 100

Because the configured weights total exactly 1.0, coverage is simply the
percentage of total weight that was evaluated. It answers a different question
from fit: a high fit on 30% coverage means four dimensions agreed and three were
unmeasurable, which is a materially different statement from a high fit on 100%
coverage.

**Effective weight and contribution**

        W_effective_i = W_i / SUM(W_i x E_i)
        Contribution_i = W_effective_i x C_i

Configured weights are not the weights that were actually applied. Once the
unevaluated components are excluded, the remaining components are renormalised
over what is left, and their effective weights sum to 1. Reporting the
configured weight next to the score would misstate what happened: an academic
score of 96 at a configured 25% does not add "24 points" when other components
were excluded, because academic actually carried a larger share of the average.

The contributions sum to the fit score by construction, which is asserted by the
test suite within a display-rounding tolerance.

**Sensitivity range**

    N = SUM(W_i x C_i)   over evaluated components
    E = SUM(W_i)         over evaluated components
    U = SUM(W_i)         over unevaluated components  (= 1.0 - E)

    current    = N / E
    lower      = N / 100
    upper      = (N + 100 x U) / 100

The range brackets what the same record would score if every unevaluated
dimension turned out to be the worst possible value, or the best possible value.
It is arithmetic, not a prediction: it says nothing about which outcome is more
likely, it is never used for ranking, and it is never presented without that
caveat.

Nothing in this module reads a clock, a database or a random number. Given the
same components it returns the same numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .config import (
    FIT_BANDS,
    FIT_WEIGHTS,
    TOTAL_CONFIGURED_WEIGHT,
    clamp,
)
from .types import EligibilityStatus


@dataclass(frozen=True)
class ComponentContribution:
    """One component's actual share of the final score.

    ``configured_weight`` is what the model says. ``effective_weight`` is what
    was applied after the unevaluated components were excluded. Reporting the
    configured weight alone would misstate the arithmetic.
    """

    name: str
    score: float
    configured_weight: float
    effective_weight: float
    contribution: float


@dataclass(frozen=True)
class SensitivityRange:
    """The bracket implied by the unevaluated components. Not a prediction."""

    lower_bound: float
    upper_bound: float
    unevaluated_weight: float
    unevaluated_components: tuple[str, ...]
    caveat: str = "Mathematical sensitivity range, not a prediction."


@dataclass(frozen=True)
class FitMetrics:
    """Everything derived arithmetically from a set of component scores."""

    #: ``None`` when nothing could be evaluated. Never 0 as a stand-in.
    fit_score: float | None
    fit_band: str | None
    fit_label: str | None
    data_coverage: float
    evaluated_component_count: int
    total_component_count: int
    contributions: tuple[ComponentContribution, ...] = ()
    sensitivity: SensitivityRange | None = None
    numerator: float = 0.0
    denominator: float = 0.0


SENSITIVITY_CAVEAT = "Mathematical sensitivity range, not a prediction."


def fit_band(score: float | None) -> tuple[str | None, str | None]:
    """Classify a fit score into its locked band.

    ``None`` in, ``(None, None)`` out: an unscoreable result has no band, and
    reporting "Low Fit" for a result nothing could be measured on would be a
    fabricated classification.
    """
    if score is None:
        return None, None
    for threshold, key, label in FIT_BANDS:
        if score >= threshold:
            return key, label
    last_key, last_label = FIT_BANDS[-1][1], FIT_BANDS[-1][2]
    return last_key, last_label


# ---------------------------------------------------------------------------
# The public fit disclosure
# ---------------------------------------------------------------------------
#
# The fit arithmetic and the fit *disclosure* are separate decisions, and keeping
# them in one explicit state model is what prevents the second one from quietly
# corrupting the first. There are exactly three states, and only one of them
# suppresses the score:

#: The gate ruled the record INELIGIBLE. No public fit score, no public band.
FIT_LABEL_INELIGIBLE = "INELIGIBLE"
FIT_LABEL_INELIGIBLE_DISPLAY = "Not eligible"

#: Nothing could be evaluated. An absence, reported as an absence.
FIT_LABEL_NOT_EVALUATED = "NOT_EVALUATED"
FIT_LABEL_NOT_EVALUATED_DISPLAY = "Not evaluated"


class FitDisclosure(StrEnum):
    """How a fit result is disclosed to the reader."""

    #: A deterministic score and band are published.
    SCORED = "SCORED"
    #: No dimension could be evaluated, so no score exists.
    NOT_EVALUATED = "NOT_EVALUATED"
    #: The hard gate refused the record, so the score is withheld.
    SUPPRESSED_INELIGIBLE = "SUPPRESSED_INELIGIBLE"


@dataclass(frozen=True)
class PublicFit:
    """What the interface is allowed to say about fit for one record.

    ``internal_fit_score`` is the raw arithmetic result. It lives on this internal
    object only and is never serialised onto ``MatchResult``, because a raw number
    beside a suppressed result invites a client to treat it as a ranking signal
    the gate already refused. It exists so the engine's own diagnostics can see
    whether an ineligibility came from a hard rule or from an absence of data.
    """

    fit_score: float | None
    fit_band: str | None
    fit_label: str
    fit_label_display: str
    disclosure: FitDisclosure
    internal_fit_score: float | None

    @property
    def is_publicly_scored(self) -> bool:
        return self.disclosure is FitDisclosure.SCORED


def resolve_public_fit(status: EligibilityStatus, metrics: FitMetrics) -> PublicFit:
    """Resolve one record's fit disclosure from the gate verdict and the arithmetic.

    The complete decision table, with no string manipulation anywhere in it:

    ==========================  ===================  ==========================
    Eligibility                fit_score            fit_label
    ==========================  ===================  ==========================
    ``INELIGIBLE``             ``None``             ``INELIGIBLE``
    ``NEEDS_VERIFICATION``     the score, if any    the band, if any
    ``ELIGIBLE``               the score, if any    the band, if any
    ==========================  ===================  ==========================

    NEEDS_VERIFICATION deliberately behaves exactly like ELIGIBLE here. The
    published rule exists but could not be checked, and that is a statement about
    our evidence, not about the student's fit: withholding a deterministic score
    would hide a real measurement, and rewriting the band into a second key broke
    fit-tier and facet lookups. Eligibility is reported separately and stays
    visible on every result, which is where the reader is told about it.
    """
    if status is EligibilityStatus.INELIGIBLE:
        return PublicFit(
            fit_score=None,
            fit_band=None,
            fit_label=FIT_LABEL_INELIGIBLE,
            fit_label_display=FIT_LABEL_INELIGIBLE_DISPLAY,
            disclosure=FitDisclosure.SUPPRESSED_INELIGIBLE,
            internal_fit_score=metrics.fit_score,
        )

    if metrics.fit_score is None:
        return PublicFit(
            fit_score=None,
            fit_band=None,
            fit_label=FIT_LABEL_NOT_EVALUATED,
            fit_label_display=FIT_LABEL_NOT_EVALUATED_DISPLAY,
            disclosure=FitDisclosure.NOT_EVALUATED,
            internal_fit_score=None,
        )

    return PublicFit(
        fit_score=metrics.fit_score,
        fit_band=metrics.fit_band,
        fit_label=metrics.fit_band or FIT_LABEL_NOT_EVALUATED,
        fit_label_display=metrics.fit_label or FIT_LABEL_NOT_EVALUATED_DISPLAY,
        disclosure=FitDisclosure.SCORED,
        internal_fit_score=metrics.fit_score,
    )


def compute_fit(components: tuple[dict, ...]) -> FitMetrics:
    """Apply the locked formula to one record's component scores.

    ``components`` is a sequence of mappings carrying ``name``, ``weight``,
    ``status`` and ``score``, in presentation order. Keeping this function
    independent of the ``ComponentScore`` model means the arithmetic can be
    tested without constructing a whole scholarship, and means a future caller
    cannot smuggle a score in under a different shape.

    Nothing is rounded here. Rounding happens once, at the end, and only on the
    value that is actually displayed, so the contributions still sum to the
    published fit score.
    """
    numerator = 0.0
    denominator = 0.0
    unevaluated_weight = 0.0
    unevaluated_names: list[str] = []
    contributions: list[ComponentContribution] = []
    evaluated_count = 0

    for component in components:
        name = component["name"]
        weight = float(component["weight"])
        score = component.get("score")

        if score is None:
            # Unknown. Its weight is excluded from the denominator and its score
            # never reaches the numerator.
            unevaluated_weight += weight
            unevaluated_names.append(name)
            continue

        score = clamp(float(score))
        evaluated_count += 1
        numerator += weight * score
        denominator += weight
        contributions.append(
            ComponentContribution(
                name=name,
                score=score,
                configured_weight=weight,
                effective_weight=0.0,  # filled in below, once the total is known
                contribution=0.0,
            )
        )

    total_components = len(components)

    if denominator > 0:
        raw_fit = clamp(numerator / denominator)
        fit_score = round(raw_fit, 1)
        # The denominator is already a sum of weights, so it is the fraction of
        # the model that was evaluated. Multiplying by 100 gives the percentage.
        data_coverage = round(clamp(denominator) * 100.0, 1)
    else:
        # Nothing was measurable. The fit is undefined, not zero.
        fit_score = None
        data_coverage = 0.0
        contributions = []

    resolved = [
        ComponentContribution(
            name=item.name,
            score=item.score,
            configured_weight=item.configured_weight,
            effective_weight=item.configured_weight / denominator,
            contribution=(item.configured_weight / denominator) * item.score,
        )
        for item in contributions
    ]

    sensitivity = None
    if denominator > 0 and unevaluated_weight > 0:
        # ``TOTAL_CONFIGURED_WEIGHT`` (100) is the top of the 0-100 component
        # scale, so it is what an unevaluated dimension would contribute if it
        # turned out to be the best possible value. The divisor is the sum of the
        # configured weights, which is exactly 1.0 - not 100, which is what made
        # this range report 0-1 fractions beside a 0-100 score:
        #
        #     lower = (N + 0   x U) / 1.0
        #     upper = (N + 100 x U) / 1.0
        total_weight = sum(FIT_WEIGHTS.values()) or 1.0
        lower = clamp(numerator / total_weight)
        upper = clamp((numerator + TOTAL_CONFIGURED_WEIGHT * unevaluated_weight) / total_weight)
        sensitivity = SensitivityRange(
            lower_bound=round(lower, 1),
            upper_bound=round(upper, 1),
            unevaluated_weight=round(unevaluated_weight, 4),
            unevaluated_components=tuple(unevaluated_names),
            caveat=SENSITIVITY_CAVEAT,
        )

    band_key, band_label = fit_band(fit_score)

    return FitMetrics(
        fit_score=fit_score,
        fit_band=band_key,
        fit_label=band_label,
        data_coverage=data_coverage,
        evaluated_component_count=evaluated_count,
        total_component_count=total_components,
        contributions=tuple(resolved),
        sensitivity=sensitivity,
        numerator=numerator,
        denominator=denominator,
    )


def contributions_sum_to_fit(metrics: FitMetrics) -> bool:
    """Whether the published contributions reconcile with the published score.

    A single place for the invariant so the test, the API and any future caller
    all ask the same question the same way. Tolerance is ``SUM_TOLERANCE``,
    which covers only the rounding applied for display.
    """
    if metrics.fit_score is None:
        return not metrics.contributions
    total = sum(item.contribution for item in metrics.contributions)
    return abs(total - metrics.fit_score) <= 0.05


def total_configured_weight() -> float:
    """Sum of the configured fit weights. Used by the coverage invariant test."""
    return sum(FIT_WEIGHTS.values())


__all__ = [
    "ComponentContribution",
    "FIT_LABEL_INELIGIBLE",
    "FIT_LABEL_INELIGIBLE_DISPLAY",
    "FIT_LABEL_NOT_EVALUATED",
    "FIT_LABEL_NOT_EVALUATED_DISPLAY",
    "FitDisclosure",
    "FitMetrics",
    "PublicFit",
    "SENSITIVITY_CAVEAT",
    "SensitivityRange",
    "compute_fit",
    "contributions_sum_to_fit",
    "fit_band",
    "resolve_public_fit",
    "total_configured_weight",
]