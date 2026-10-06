"""Derived cost, break-even and return figures.

Everything here is arithmetic over figures that arrived from somewhere else. That
is the whole reason this module exists as its own layer: a derived number is the
one most likely to be believed, because it looks like a fact rather than a
research artifact. It is also the one most likely to be wrong, because a single
missing or misused input produces a confident number with no visible seam.

So three rules govern everything below.

**1. Refuse rather than approximate.** Every function returns a ``Derivation``,
never a bare number. When an input is missing the result is ``REFUSED`` with the
reason, and the caller renders "not established". A cost calculator that silently
returns 0 for a country with no living-cost data is worse than one that says so:
the student budgets from it.

**2. Name the arithmetic.** Every derived figure carries the formula string and
the corpus paths of its inputs, so a reader can recompute it by hand and disagree
if they wish. ``DERIVED`` is the only status a figure here may carry, and the
corpus validator would reject it if the formula were missing.

**3. Never mix currencies silently.** Converting a EUR salary against a USD
tuition requires an exchange rate, which is itself a researched figure with a
date. Without a sourced rate the derivation is refused. Silently using a stale
rate is how a "break-even in 14 months" claim gets made.

## The two places this module refuses to do what was asked of it

**Break-even needs net income, not gross.** Break-even compares money in against
money out, so it must use take-home pay after tax and social insurance. Gross
salary is what official statistics usually publish, because tax is not their
concern. Dividing a gross figure by an after-tax cost understates break-even
comfortably - in Germany the gross-to-net gap is around 40%. So if the corpus
carries only a gross figure, break-even is refused and says exactly which claim
was missing.

**Return on investment is not promised.** ROI here means "cumulative income over
N years minus the money invested, divided by the money invested". It is a
ratio of two researched figures with no discounting, no risk adjustment and no
modelling of whether a graduate finds work. It is labelled a ratio, never a
return, and the response states that it ignores the possibility of no income at
all - which is the outcome the whole calculation is silent about.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .provenance import Claim, normalise_status_vocabulary

#: Version of the derivation arithmetic itself. Published on every response so a
#: changed number can be traced to a changed formula rather than guessed at.
DERIVATION_VERSION = "1.0.0"

#: The study levels this feature reasons about. Bachelor's is first because it is
#: the level where tuition is genuinely paid out of pocket: the platform's users
#: apply predominantly to funded postgraduate programmes, so for them tuition is
#: covered and living cost dominates.
STUDY_LEVELS: tuple[str, ...] = ("bachelor", "master", "phd")

#: Levels where a scholarship commonly carries tuition as well as a stipend.
#: Used only to word a note. It never changes an amount on its own - the coverage
#: figure is the catalogue's own measured proportion, not this flag.
POSTGRADUATE_LEVELS: frozenset[str] = frozenset({"master", "phd"})

CITY_TIERS: tuple[str, ...] = ("low", "medium", "high")

#: Refusal codes. Declared so the API can distinguish "we could not compute this"
#: from "we computed this and it is zero", and so a test can assert on a specific
#: reason rather than on prose.
REFUSAL_MISSING_INPUT = "MISSING_INPUT"
REFUSAL_MISSING_NET_INCOME = "MISSING_NET_INCOME"
REFUSAL_MISSING_FX_RATE = "MISSING_FX_RATE"
REFUSAL_CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
REFUSAL_NO_RESEARCH = "NO_RESEARCHED_DATA"
REFUSAL_GROSS_INCOME = "GROSS_INCOME_NOT_REPAYABLE"
REFUSAL_UNIT_MISMATCH = "UNIT_MISMATCH"
REFUSAL_MISSING_PERIOD = "MISSING_PERIOD"
REFUSAL_UNSUPPORTED_INPUT = "UNSUPPORTED_INPUT"

#: Human phrasing for each refusal code. Defined beside the codes so the API
#: wording for "why not" is written once and cannot drift from the code that
#: triggered it. Every code is a *correctness* outcome: the system declined
#: because a contract condition failed, not because it failed to look.
REFUSAL_LABELS: dict[str, str] = {
    REFUSAL_MISSING_INPUT: "A required input was not supplied.",
    REFUSAL_MISSING_NET_INCOME: "Net (take-home) income was not supplied.",
    REFUSAL_MISSING_FX_RATE: "No sourced exchange rate covers these currencies.",
    REFUSAL_CURRENCY_MISMATCH: "Currencies or units do not match.",
    REFUSAL_NO_RESEARCH: "This country has no researched data to derive from.",
    REFUSAL_GROSS_INCOME: "Gross income cannot repay a cost; take-home pay is required.",
    REFUSAL_UNIT_MISMATCH: "The units of the inputs do not agree.",
    REFUSAL_MISSING_PERIOD: "The figure states no period, so it cannot be annualised.",
    REFUSAL_UNSUPPORTED_INPUT: "The input is not of a type this formula accepts.",
}


@dataclass(frozen=True)
class Derivation:
    """One derived figure, or an explicit refusal to produce it."""

    key: str
    formula: str
    inputs: tuple[str, ...] = field(default_factory=tuple)
    value: float | None = None
    currency: str | None = None
    per: str | None = None
    #: ``None`` when the figure was computed, otherwise the refusal code.
    refusal: str | None = None
    reason: str | None = None
    #: What the refusal would need in order to proceed, when the failure names a
    #: specific missing input. Carried so the caller can tell the student what to
    #: supply rather than only that something is missing.
    required_input: str | None = None
    #: The formula or operation that refused, so a refusal read in isolation still
    #: says what would have been computed.
    operation: str | None = None

    @property
    def computed(self) -> bool:
        return self.value is not None and self.refusal is None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "key": self.key,
            "status": "DERIVED" if self.computed else "NOT_DERIVED",
            # A refusal publishes REFUSED, never UNKNOWN. "Nobody established this"
            # and "the system declined to compute this" are different facts, and
            # collapsing them hides a correctness decision behind an apparent gap in
            # the research.
            "value_status": "DERIVED" if self.computed else "REFUSED",
            "formula": self.formula,
            "inputs": list(self.inputs),
        }
        if self.computed:
            payload["value"] = self.value
            if self.currency:
                payload["currency"] = self.currency
            if self.per:
                payload["per"] = self.per
        else:
            payload["refusal"] = self.refusal
            payload["reason"] = self.reason
            refusal_detail: dict[str, Any] = {
                "reason": self.reason or REFUSAL_LABELS.get(self.refusal or "", "Refused."),
                "operation": self.operation or self.formula,
            }
            if self.required_input:
                refusal_detail["required_input"] = self.required_input
            payload["refusal_detail"] = refusal_detail
        return payload


def _refused(
    key: str,
    formula: str,
    inputs: Sequence[str],
    code: str,
    reason: str,
    *,
    required_input: str | None = None,
) -> Derivation:
    return Derivation(
        key=key,
        formula=formula,
        inputs=tuple(inputs),
        refusal=code,
        reason=reason,
        required_input=required_input,
        operation=formula,
    )


def find_claim(
    record_sections: Mapping[str, Any], path: Sequence[str]
) -> Mapping[str, Any] | Claim | None:
    """Resolve a slash-free path to a figure, validated if the corpus was.

    Accepts either a nested section body (the research as written) or a flat
    mapping of validated :class:`Claim` objects keyed by dotted path, so callers
    that have a :class:`~app.services.country_intelligence.corpus.CountryRecord`
    can pass ``record.claims`` and get figures whose block-level metadata has
    already been inherited and whose status aliases have already been resolved.

    The flat lookup is tried first. A nested body and a validated claims map differ
    in a way that matters: a figure inheriting ``value_status`` from its parent
    has no status of its own in the raw body, so a caller that requires one sees
    no figure and drops a sourced number. Validated claims do not have that
    property, which is why they are preferred.
    """
    if record_sections:
        direct = record_sections.get(".".join(path))
        if isinstance(direct, Claim):
            return direct
        if isinstance(direct, Mapping) and direct.get("value") is not None:
            return direct

    node: Any = record_sections
    for key in path:
        if not isinstance(node, Mapping) or key not in node:
            return None
        node = node[key]
    return node if isinstance(node, (Mapping, Claim)) else None


def _numeric(claim: Any) -> float | None:
    """The usable number inside a figure, or ``None``.

    A validated :class:`Claim` is taken at its word: it has already been checked,
    and a ``None`` value there means the status was ``UNKNOWN``. A raw mapping is
    treated as usable only when it declares its own status, because the corpus is
    not supposed to contain bare numbers and a raw body cannot express an
    inherited one.
    """
    if claim is None:
        return None
    if isinstance(claim, Claim):
        if claim.value_status == "UNKNOWN":
            return None
        value = claim.value
    else:
        if not isinstance(claim, Mapping) or not claim.get("value_status"):
            return None
        if normalise_status_vocabulary(claim["value_status"]) == "UNKNOWN":
            return None
        value = claim.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _claim_currency(claim: Any) -> str | None:
    if claim is None:
        return None
    if isinstance(claim, Claim):
        return claim.currency
    if not isinstance(claim, Mapping):
        return None
    currency = claim.get("currency")
    return str(currency) if currency else None


def _claim_basis(claim: Any) -> str | None:
    if isinstance(claim, Claim):
        return claim.basis
    if isinstance(claim, Mapping):
        basis = claim.get("basis")
        return str(basis) if basis else None
    return None


def scholarship_coverage(
    measured_fully_funded: int | None, measured_total: int | None
) -> tuple[float | None, str | None]:
    """Proportion of this country's scholarships that are fully funded.

    This is a **measured** catalogue figure, not a researched assumption, and that
    distinction is the point. "Master's and PhD are usually fully funded" is not a
    safe default: on the current catalogue it is true for China, Norway and Belgium
    and false for Finland, Denmark, Spain and Chile, where no listed scholarship is
    fully funded. Applying the catalogue's own proportion keeps the cost model
    honest for exactly the countries where the assumption would hurt.

    Returns ``(None, reason)`` when there is not enough scholarship volume for the
    proportion to mean anything. A rate computed from one or two records is noise,
    and dividing a tuition bill by it would be a very precise answer to a very
    shaky question.
    """
    if not measured_total or measured_total < 3:
        return None, (
            f"Too few listed scholarships ({measured_total or 0}) for the fully-funded "
            f"proportion to be meaningful."
        )
    if measured_fully_funded is None:
        return None, "The fully-funded count was not measured."
    return measured_fully_funded / measured_total, None


def _find_tuition_claim(
    sections: Mapping[str, Any], level: str
) -> tuple[Mapping[str, Any] | None, str]:
    """Locate the tuition figure for one level, and say where it was found.

    Two canonical shapes are accepted, and only these two:

    - ``education_costs.tuition_fees.public.<level>`` - a figure stated per year,
      which is what a derivation can use directly.
    - ``education_costs.tuition_fees.public.<level>.<period>`` - a figure stated
      per semester or per month. Resolving these is why the lookup exists at all:
      before it, a semester fee sat at a path nothing could reach, and the refusal
      reason claimed no researched data existed while the evidence was in the file.

    There is deliberately **no third shape and no fallback**. A path that is not
    one of these two returns nothing, because a derivation that guesses where to
    look will eventually find a number in the wrong place and use it.

    The returned note records which shape matched, so a refusal or a refusal-to-refuse
    can be traced to a specific path rather than to "nothing was found".
    """
    direct = find_claim(
        sections, ("education_costs", "tuition_fees", "public", level)
    )
    if direct is not None and _numeric(direct) is not None:
        return direct, f"Read from education_costs.tuition_fees.public.{level}."

    node = _dig_node(sections, ["education_costs", "tuition_fees", "public", level])
    if isinstance(node, Mapping):
        for period in ("year", "semester", "month"):
            candidate = _dig_node(node, [period])
            if candidate is not None and _numeric(candidate) is not None:
                return (
                    candidate,
                    f"Read from education_costs.tuition_fees.public.{level}.{period}; "
                    f"the source states a {period} figure, which is a different "
                    f"quantity from an annual one and must not be substituted for it "
                    f"without a registered conversion.",
                )
    return None, (
        f"Neither education_costs.tuition_fees.public.{level} nor a stated period "
        f"under it holds a value. No fallback path is searched by design."
    )


def _dig_node(node: Any, path: list[str]) -> Any:
    current = node
    for part in path:
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def derive_tuition(
    sections: Mapping[str, Any],
    level: str,
    coverage: float | None,
) -> Derivation:
    """Annual tuition the student expects to pay themselves, after any coverage.

    Gross tuition is looked up for the level, then reduced by the coverage
    proportion. Both halves are published: a student offered a full scholarship
    needs the gross figure, and a student offered nothing needs the zero, and one
    number cannot be both.
    """
    normalised = (level or "").strip().lower()
    formula = (
        f"expected_tuition = gross_tuition * (1 - coverage); "
        f"coverage = catalogue fully_funded / catalogue total"
    )
    if normalised not in STUDY_LEVELS:
        return _refused(
            "tuition_expected", formula, [], REFUSAL_MISSING_INPUT,
            f"Unknown study level {level!r}. Known levels: {', '.join(STUDY_LEVELS)}.",
        )

    gross_claim, gross_note = _find_tuition_claim(sections, normalised)
    inputs = [f"education_costs.tuition_fees.public.{normalised}"]
    gross = _numeric(gross_claim)
    if gross is None:
        return _refused(
            "tuition_expected", formula, inputs, REFUSAL_NO_RESEARCH,
            f"No sourced public-university tuition for {normalised} in this "
            f"country. {gross_note}",
        )

    currency = _claim_currency(gross_claim)
    if coverage is None:
        return _refused(
            "tuition_expected", formula, inputs, REFUSAL_MISSING_INPUT,
            "No coverage proportion is available, so gross tuition cannot be reduced. "
            "Gross tuition is published separately and is unchanged by this.",
        )

    expected = gross * (1.0 - coverage)
    if normalised in POSTGRADUATE_LEVELS:
        formula += (
            f"; {normalised} is a postgraduate level, where a funded award commonly "
            f"carries tuition as well as a stipend"
        )
    return Derivation(
        key="tuition_expected",
        formula=formula,
        inputs=tuple(inputs),
        value=round(expected, 2),
        currency=currency,
        per="year",
    )


def derive_living(sections: Mapping[str, Any], tier: str) -> Derivation:
    """Annual living cost for a city tier.

    Prefers the corpus's own published monthly total for the tier, because a total
    researched as a whole is more trustworthy than one we add up from parts we may
    have partially sourced. Only if the total is absent does it sum the components,
    and then it says so in the formula.
    """
    normalised = (tier or "").strip().lower()
    formula = "living_annual = monthly_total * 12"
    if normalised not in CITY_TIERS:
        return _refused(
            "living_annual", formula, [], REFUSAL_MISSING_INPUT,
            f"Unknown city tier {tier!r}. Known tiers: {', '.join(CITY_TIERS)}.",
        )

    total_claim = find_claim(sections, ("living_costs", "monthly_costs", normalised, "total"))
    inputs = [f"living_costs.monthly_costs.{normalised}.total"]
    monthly = _numeric(total_claim)
    if monthly is not None:
        return Derivation(
            key="living_annual",
            formula=formula,
            inputs=tuple(inputs),
            value=round(monthly * 12, 2),
            currency=_claim_currency(total_claim),
            per="year",
        )

    component_keys = (
        "rent_1br_city_center", "rent_1br_outside_center", "food", "transport",
        "utilities", "internet", "study_materials", "personal",
    )
    monthly_parts: list[float] = []
    used: list[str] = []
    for component in component_keys:
        claim = find_claim(
            sections, ("living_costs", "monthly_costs", normalised, component)
        )
        value = _numeric(claim)
        if value is not None:
            monthly_parts.append(value)
            used.append(f"living_costs.monthly_costs.{normalised}.{component}")

    if not monthly_parts:
        return _refused(
            "living_annual", formula, inputs, REFUSAL_NO_RESEARCH,
            f"No sourced living-cost components or total for the {normalised} city tier.",
        )

    formula = "living_annual = (" + " + ".join(
        part.rsplit(".", 1)[-1] for part in used
    ) + ") * 12"
    return Derivation(
        key="living_annual",
        formula=formula,
        inputs=tuple(used),
        value=round(sum(monthly_parts) * 12, 2),
        currency=_claim_currency(find_claim(
            sections, ("living_costs", "monthly_costs", normalised, component_keys[0])
        )),
        per="year",
    )


def derive_total_investment(
    tuition: Derivation, living: Derivation, one_time: Derivation, years: float
) -> Derivation:
    """Total money committed over the whole programme.

    One-time costs are paid once, not per year. A formula that multiplied the
    visa fee by the programme length would inflate every total by a small amount,
    and it is exactly the kind of error nobody checks because the number is still
    the right order of magnitude.
    """
    formula = (
        "total_investment = tuition_annual * years + living_annual * years + one_time_total"
    )
    inputs = [item.key for item in (tuition, living, one_time) if item.computed]

    missing = [item.key for item in (tuition, living, one_time) if not item.computed]
    if missing:
        return _refused(
            "total_investment", formula, inputs, REFUSAL_MISSING_INPUT,
            "Cannot total a programme while these are not established: "
            + ", ".join(missing)
            + ". A partial total would understate the cost, which is the direction "
            "that gets a student caught out.",
        )

    currencies = {item.currency for item in (tuition, living, one_time) if item.currency}
    if len(currencies) > 1:
        return _refused(
            "total_investment", formula, inputs, REFUSAL_CURRENCY_MISMATCH,
            f"These figures are quoted in different currencies ({', '.join(sorted(currencies))}) "
            f"and no sourced exchange rate was supplied, so they cannot be added.",
        )

    value = (
        tuition.value * years + living.value * years + one_time.value
    )
    return Derivation(
        key="total_investment",
        formula=formula,
        inputs=tuple(inputs),
        value=round(value, 2),
        currency=next(iter(currencies), None),
        per="programme",
    )


def _claim_note(claim: Any) -> str | None:
    if isinstance(claim, Claim):
        return claim.note
    if isinstance(claim, Mapping):
        note = claim.get("note") or claim.get("reason")
        return str(note) if note else None
    return None


def _claim_status(claim: Any) -> str | None:
    if isinstance(claim, Claim):
        return claim.value_status
    if isinstance(claim, Mapping):
        status = claim.get("value_status")
        return normalise_status_vocabulary(status) if status else None
    return None


def derive_break_even(
    investment: Derivation, net_income: Any
) -> Derivation:
    """Months of take-home work needed to recover the programme cost.

    Gross income is refused on purpose; see the module docstring. A gross salary
    divided into an after-tax cost produces a confidently wrong number, and it is
    the most tempting shortcut available here precisely because gross salary is
    what official statistics publish.
    """
    formula = "break_even_months = total_investment / net_monthly_income"
    inputs = ["total_investment"]
    if not investment.computed:
        return _refused(
            "break_even_months", formula, inputs, REFUSAL_MISSING_INPUT,
            "Cannot compute break-even without an established programme cost.",
        )

    status = _claim_status(net_income)
    if net_income is None or status is None:
        return _refused(
            "break_even_months", formula, inputs, REFUSAL_MISSING_NET_INCOME,
            "No income figure was found. Break-even needs take-home pay after tax and "
            "social insurance; a gross salary is not used, because it would "
            "understate the months needed.",
        )
    if status == "UNKNOWN":
        return _refused(
            "break_even_months", formula, inputs, REFUSAL_MISSING_NET_INCOME,
            "Take-home income is not established for this country: "
            + str(_claim_note(net_income) or "no reason recorded"),
        )

    monthly_net = _numeric(net_income)
    if monthly_net is None or monthly_net <= 0:
        return _refused(
            "break_even_months", formula, inputs, REFUSAL_MISSING_NET_INCOME,
            "Take-home income is present but is not a positive monthly number, so it "
            "cannot be used to divide a cost.",
        )

    basis = _claim_basis(net_income)
    if basis != "net":
        label = "gross" if basis == "gross" else "undeclared"
        return _refused(
            "break_even_months", formula, inputs, REFUSAL_GROSS_INCOME,
            f"The income figure is {label}, not take-home pay. Break-even compares "
            f"money out against money in, so only a net figure may be used; take-home "
            f"pay in this country is typically a fraction of gross, so using gross "
            f"would roughly halve the months reported. Declare the figure with "
            f'"basis": "net" once a sourced take-home amount is available.',
            required_input=(
                'A monthly take-home (net) income figure with "basis": "net", '
                "sourced from an authoritative source for this country."
            ),
        )

    income_currency = _claim_currency(net_income)
    if investment.currency and income_currency and investment.currency != income_currency:
        return _refused(
            "break_even_months", formula, inputs, REFUSAL_MISSING_FX_RATE,
            f"Investment is in {investment.currency} and income is in {income_currency}. "
            f"An exchange rate is required and none was sourced. No rate is assumed and "
            f"no parity is invented, so these currencies are not treated as equal.",
            required_input=(
                f"A sourced {investment.currency} to {income_currency} exchange rate "
                f"with a published date."
            ),
        )

    return Derivation(
        key="break_even_months",
        formula=formula,
        inputs=tuple([*inputs, "net_monthly_income"]),
        value=round(investment.value / monthly_net, 1),
        per="months",
    )


def derive_roi(investment: Derivation, annual_income: Mapping[str, Any] | None, years: float) -> Derivation:
    """Income multiple over the programme cost.

    Deliberately a ratio and not a percentage: a percentage invites the reading
    "you will earn 640% of your investment", which is not what the arithmetic says.
    The arithmetic is ``(income * years - investment) / investment``, and it is
    only as good as the two researched figures under it.
    """
    formula = "roi_multiple = (annual_income * years - total_investment) / total_investment"
    inputs = ["total_investment"]
    if not investment.computed:
        return _refused(
            "roi_multiple", formula, inputs, REFUSAL_MISSING_INPUT,
            "Cannot compute a return multiple without an established programme cost.",
        )
    income = _numeric(annual_income)
    if income is None:
        return _refused(
            "roi_multiple", formula, inputs, REFUSAL_MISSING_INPUT,
            "No sourced annual income figure was found, so no return can be computed.",
        )
    if investment.value <= 0:
        return _refused(
            "roi_multiple", formula, inputs, REFUSAL_MISSING_INPUT,
            "Programme cost is not positive, so a return multiple is undefined.",
        )
    return Derivation(
        key="roi_multiple",
        formula=formula,
        inputs=tuple([*inputs, "annual_income"]),
        value=round((income * years - investment.value) / investment.value, 3),
        per=f"multiple_over_{int(years)}_years",
    )


def derive_one_time_total(sections: Mapping[str, Any]) -> Derivation:
    """Sum the country's one-time costs.

    Only components that are individually sourced are summed, and the formula
    names exactly which ones. A total that quietly omitted an unsourced visa fee
    would read as complete.
    """
    formula = "one_time_total = sum(sourced one_time components)"
    node = sections.get("one_time_costs")
    # Flat is detected by prefix, not by exact membership: a validated claims map
    # is keyed by full path ("one_time_costs.blocked_account"), so testing for the
    # bare prefix as a key would miss every one of them and refuse a country that
    # has a perfectly good sourced blocked account.
    flat = any(str(path).startswith("one_time_costs.") for path in sections)
    if not flat and not isinstance(node, Mapping):
        return _refused(
            "one_time_total", formula, [], REFUSAL_NO_RESEARCH,
            "This country has no researched one-time cost section.",
        )

    parts: list[float] = []
    used: list[str] = []
    currency: str | None = None

    # Accept either the raw section body or a flat validated-claims map. The two
    # are iterated differently because their nesting differs: raw bodies hold the
    # claims as direct children, while validated claims are keyed by full path and
    # may include descendants that are not one-time costs at all.
    if flat:
        candidates = [
            (path, claim)
            for path, claim in sections.items()
            if isinstance(claim, Claim) and str(path).startswith("one_time_costs.")
        ]
    else:
        node = sections.get("one_time_costs")
        candidates = [
            (f"one_time_costs.{key}", value)
            for key, value in (node.items() if isinstance(node, Mapping) else [])
            if isinstance(value, (Mapping, Claim))
        ]

    for path, value in candidates:
        if _claim_status(value) is None:
            continue
        amount = _numeric(value)
        if amount is None:
            continue
        parts.append(amount)
        used.append(path)
        currency = currency or _claim_currency(value)

    if not parts:
        return _refused(
            "one_time_total", formula, [], REFUSAL_NO_RESEARCH,
            "No one-time cost components are sourced for this country.",
        )
    return Derivation(
        key="one_time_total",
        formula="one_time_total = " + " + ".join(part.rsplit(".", 1)[-1] for part in used),
        inputs=tuple(used),
        value=round(sum(parts), 2),
        currency=currency,
        per="once",
    )


__all__ = [
    "CITY_TIERS",
    "DERIVATION_VERSION",
    "Derivation",
    "POSTGRADUATE_LEVELS",
    "REFUSAL_CURRENCY_MISMATCH",
    "REFUSAL_GROSS_INCOME",
    "REFUSAL_LABELS",
    "REFUSAL_MISSING_FX_RATE",
    "REFUSAL_MISSING_INPUT",
    "REFUSAL_MISSING_NET_INCOME",
    "REFUSAL_MISSING_PERIOD",
    "REFUSAL_NO_RESEARCH",
    "REFUSAL_UNIT_MISMATCH",
    "REFUSAL_UNSUPPORTED_INPUT",
    "STUDY_LEVELS",
    "derive_break_even",
    "derive_living",
    "derive_one_time_total",
    "derive_roi",
    "derive_total_investment",
    "derive_tuition",
    "find_claim",
    "scholarship_coverage",
]