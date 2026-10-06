"""Declarative, reproducible formulas for every derived figure.

## Why this module exists

Research output computes totals. A researcher sums a tuition figure, twelve months
of living cost and a visa fee, and publishes the result. Two agents did this in the
same build and **both** produced a ``value`` that contradicted their own stated
formula: one claimed EUR 14,529.78 where the inputs gave EUR 13,931.91, another
was wrong in three of four rows by thousands. A corpus that trusted those numbers
would have shipped four confidently incorrect figures with a formula printed
beside them, and the formula would have been the receipt that looked like proof.

The old check could not catch this. It asked only whether a DERIVED figure *had* a
``formula`` string. Presence, not agreement. So this module makes agreement the
thing that is checked.

## Three rules

**1. No arbitrary Python.** A corpus file never carries code. It names a
``formula_id`` and a version; the arithmetic lives in this registry as an ordinary
Python function. There is no ``eval``, no ``exec``, no import hook, no pickle.
A corpus file is data that a reviewer reads, and adding a figure to it cannot
execute anything. ``eval`` was rejected not because a malicious researcher is the
threat model - it is that a *formula* is supposed to be checkable, and an
expression string nobody can analyse is not.

**2. The expression string is documentation, and it is asserted against the code.**
Each entry publishes a human-readable ``expression``. A test asserts every
published expression matches its registry entry, so the two cannot drift and the
text beside a published number always describes the arithmetic that produced it.
The code is authoritative; the string is the receipt.

**3. A derived value must be reproducible from its declared inputs.**
:func:`verify_formula_claim` recomputes the figure and raises when the declared
value disagrees. That is the check that would have caught both agents above. It
is a hard corpus rejection, not a warning: a total nobody can reproduce is not a
total.

## Currency is never converted here

If a formula's currency-bearing inputs are not all in one currency, the result is
a refusal. Not a conversion at a remembered rate, not an approximation, not an
``assume the euro`` default. Converting needs a sourced rate for an applicable
period, which is itself a researched figure with a date, and this module has no
rate to consult. Refusing is the only honest answer available, and the refusal
code says so.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

from .provenance import ClaimError

#: Refusal codes. Shared vocabulary with :mod:`derive` where the concepts overlap,
#: so an API client can recognise a reason regardless of which layer produced it.
REFUSAL_MISSING_INPUT = "MISSING_INPUT"
REFUSAL_UNIT_MISMATCH = "UNIT_MISMATCH"
REFUSAL_CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
REFUSAL_MISSING_FX_RATE = "MISSING_FX_RATE"
REFUSAL_MISSING_INPUT_VALUE = "MISSING_INPUT_VALUE"
REFUSAL_NOT_DERIVED = "NOT_A_DERIVED_CLAIM"

#: Time bases a currency figure may be quoted on. Kept closed on purpose: an
#: unrecognised ``per`` cannot be silently treated as annual, because that error
#: multiplies a monthly rent by twelve and publishes it as a yearly figure.
ALLOWED_PERIODS: frozenset[str] = frozenset(
    {"year", "semester", "quarter", "month", "week", "once", "programme"}
)

#: Units a formula may *produce*. Wider than :data:`ALLOWED_PERIODS` because an
#: output may be a duration or a ratio rather than a money-per-period figure. A
#: break-even of "14 months" is a legitimate answer in months; "14 years" would be
#: a refusal's job to explain.
ALLOWED_OUTPUT_UNITS: frozenset[str] = ALLOWED_PERIODS | {"months", "rate", "ratio"}

#: How many months are in each period. Declared rather than written into the
#: arithmetic of each formula, so "monthly * 12" appears once and cannot drift.
PERIOD_MONTHS: dict[str, float] = {
    "year": 12.0,
    "semester": 6.0,
    "quarter": 3.0,
    "month": 1.0,
    "week": 1.0 / 4.345,
    "once": 1.0,
    "programme": 1.0,
}

#: Tolerance when comparing a recomputed figure to a declared one, as a relative
#: epsilon. Loose enough to absorb floating-point representation of an otherwise
#: exact identity, tight enough that the EUR 14,529.78 / 13,931.91 class of error
#: (4.1% apart) fails by two orders of magnitude.
RELATIVE_TOLERANCE = 1e-6
ABSOLUTE_TOLERANCE = 1e-9


@dataclass(frozen=True)
class FormulaInput:
    """One resolved input value handed to a formula."""

    name: str
    value: float
    currency: str | None = None
    per: str | None = None
    basis: str | None = None
    path: str | None = None

    @property
    def is_monetary(self) -> bool:
        return self.currency is not None


@dataclass(frozen=True)
class FormulaInputSpec:
    """What a formula requires of one input.

    ``expected_per`` is the integrity check that matters. Without it, a monthly
    living-cost figure could be fed to an annual formula and the output would be
    wrong by a factor of twelve while still looking like a cost.
    """

    name: str
    expected_per: str | None = None
    required: bool = True
    monetary: bool = True
    #: Requires ``basis == "net"`` when the input is income. Enforced in code
    #: rather than convention, because this is the one rule that is always
    #: tempting to break: gross pay is what statistics offices publish.
    requires_net_basis: bool = False
    description: str = ""

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "expected_per": self.expected_per,
            "required": self.required,
            "monetary": self.monetary,
            "requires_net_basis": self.requires_net_basis,
            "description": self.description,
        }


@dataclass(frozen=True)
class FormulaSpec:
    """One registered formula: an id, a version, and closed arithmetic."""

    formula_id: str
    version: int
    expression: str
    inputs: tuple[FormulaInputSpec, ...]
    output_per: str
    decimals: int = 2
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    #: Refusal conditions this formula can raise. Published so a client can tell
    #: what the formula is capable of refusing, rather than discovering it by
    #: hitting it.
    refusals: tuple[str, ...] = field(default_factory=tuple)
    evaluator: Callable[[dict[str, FormulaInput]], float] = lambda _v: 0.0

    def to_contract(self) -> dict[str, Any]:
        """The formula as published: everything except the callable."""
        return {
            "formula_id": self.formula_id,
            "formula_version": self.version,
            "expression": self.expression,
            "inputs": [spec.describe() for spec in self.inputs],
            "output_per": self.output_per,
            "assumptions": list(self.assumptions),
            "refusals": list(self.refusals),
        }


@dataclass(frozen=True)
class FormulaOutcome:
    """A computed figure, or a typed refusal."""

    formula_id: str
    version: int
    inputs: Mapping[str, FormulaInput]
    value: float | None = None
    currency: str | None = None
    per: str | None = None
    refusal: str | None = None
    reason: str | None = None
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    expression: str = ""

    @property
    def computed(self) -> bool:
        return self.value is not None and self.refusal is None

    def to_contract(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "formula_id": self.formula_id,
            "formula_version": self.version,
            "expression": self.expression,
            "inputs": {
                name: {
                    "value": item.value,
                    "currency": item.currency,
                    "per": item.per,
                    "basis": item.basis,
                    "path": item.path,
                }
                for name, item in self.inputs.items()
            },
            "assumptions": list(self.assumptions),
        }
        if self.computed:
            payload["status"] = "COMPUTED"
            payload["value"] = self.value
            if self.currency:
                payload["currency"] = self.currency
            if self.per:
                payload["output_per"] = self.per
        else:
            payload["status"] = "REFUSED"
            payload["refusal"] = self.refusal
            payload["reason"] = self.reason
        return payload


def _refuse(
    spec: FormulaSpec,
    inputs: Mapping[str, FormulaInput],
    code: str,
    reason: str,
) -> FormulaOutcome:
    return FormulaOutcome(
        formula_id=spec.formula_id,
        version=spec.version,
        inputs=dict(inputs),
        refusal=code,
        reason=reason,
        assumptions=spec.assumptions,
        expression=spec.expression,
    )


# --------------------------------------------------------------------------------------
# The registry
# --------------------------------------------------------------------------------------

#: Annual cost a student funds themselves.
#:
#: One-time costs are added **once**, not multiplied by years. That asymmetry is
#: the whole reason this is a named formula rather than a total of three figures a
#: reader multiplies themselves: multiplying a visa fee by a programme length
#: inflates the answer by a small amount that nobody checks because the order of
#: magnitude is right.
ANNUAL_COST_V1 = FormulaSpec(
    formula_id="annual_cost_v1",
    version=1,
    expression="annual_cost = annual_tuition + (monthly_living_cost * 12) + one_time_fees",
    inputs=(
        FormulaInputSpec(
            name="annual_tuition",
            expected_per="year",
            description="Tuition payable for one year of the programme.",
        ),
        FormulaInputSpec(
            name="monthly_living_cost",
            expected_per="month",
            description="Living cost for one month.",
        ),
        FormulaInputSpec(
            name="one_time_fees",
            expected_per="once",
            required=False,
            description="Visa, residence permit and setup fees, paid once.",
        ),
    ),
    output_per="year",
    assumptions=(
        "One-time fees are paid once, not per year.",
        "Living cost is held constant across the year.",
    ),
    refusals=(REFUSAL_MISSING_INPUT, REFUSAL_UNIT_MISMATCH, REFUSAL_MISSING_FX_RATE),
    evaluator=lambda v: (
        v["annual_tuition"].value
        + v["monthly_living_cost"].value * 12.0
        + (v.get("one_time_fees").value if v.get("one_time_fees") else 0.0)
    ),
)

#: Gross tuition reduced by the catalogue's measured fully-funded proportion.
EXPECTED_TUITION_V1 = FormulaSpec(
    formula_id="expected_tuition_v1",
    version=1,
    expression="expected_tuition = gross_tuition * (1 - coverage)",
    inputs=(
        FormulaInputSpec(
            name="gross_tuition",
            expected_per="year",
            description="Published tuition for the study level.",
        ),
        FormulaInputSpec(
            name="coverage",
            monetary=False,
            description=(
                "Measured proportion of this country's listed scholarships that are "
                "fully funded. A measured catalogue figure, not a researched "
                "assumption - postgraduate study is not fully funded everywhere."
            ),
        ),
    ),
    output_per="year",
    assumptions=(
        "Coverage is the catalogue's measured fully-funded proportion, applied to "
        "every applicant. A student actually holding an award funds more than one.",
    ),
    refusals=(
        REFUSAL_MISSING_INPUT,
        REFUSAL_UNIT_MISMATCH,
        REFUSAL_MISSING_FX_RATE,
        REFUSAL_MISSING_INPUT_VALUE,
    ),
    evaluator=lambda v: v["gross_tuition"].value * (1.0 - v["coverage"].value),
)

#: Total across a whole programme.
MULTI_YEAR_COST_V1 = FormulaSpec(
    formula_id="multi_year_cost_v1",
    version=1,
    expression=(
        "programme_cost = (annual_tuition + annual_living_cost) * years "
        "+ one_time_fees"
    ),
    inputs=(
        FormulaInputSpec(name="annual_tuition", expected_per="year"),
        FormulaInputSpec(name="annual_living_cost", expected_per="year"),
        FormulaInputSpec(name="years", monetary=False, description="Programme length."),
        FormulaInputSpec(name="one_time_fees", expected_per="once", required=False),
    ),
    output_per="programme",
    refusals=(REFUSAL_MISSING_INPUT, REFUSAL_UNIT_MISMATCH, REFUSAL_MISSING_FX_RATE),
    evaluator=lambda v: (
        v["annual_tuition"].value + v["annual_living_cost"].value
    ) * v["years"].value + (v.get("one_time_fees").value if v.get("one_time_fees") else 0.0),
)

#: Months of take-home work to recover a cost.
#:
#: ``requires_net_basis`` on the income input is the structural form of the rule
#: that break-even compares money out against money *in*. Gross pay divided into
#: an after-tax cost understates break-even by roughly half in most European
#: countries, and gross is what official statistics publish, which is exactly why
#: the check cannot live in a comment.
BREAK_EVEN_MONTHS_V1 = FormulaSpec(
    formula_id="break_even_months_v1",
    version=1,
    expression="break_even_months = programme_cost / net_monthly_income",
    inputs=(
        FormulaInputSpec(name="programme_cost", expected_per="programme"),
        FormulaInputSpec(
            name="net_monthly_income",
            expected_per="month",
            requires_net_basis=True,
            description=(
                "Take-home pay after tax and social insurance. A gross figure is "
                "refused: it overstates what reaches the student."
            ),
        ),
    ),
    output_per="months",
    decimals=1,
    assumptions=(
        "Income is assumed constant and a full-time job is assumed available. "
        "Neither is established by this corpus.",
    ),
    refusals=(
        REFUSAL_MISSING_INPUT,
        REFUSAL_UNIT_MISMATCH,
        REFUSAL_MISSING_FX_RATE,
        REFUSAL_MISSING_INPUT_VALUE,
    ),
    evaluator=lambda v: v["programme_cost"].value / v["net_monthly_income"].value,
)

#: Cash a student must have on arrival, which is **not** the total economic cost.
#:
#: Separated from ``multi_year_cost_v1`` because conflating the two is the most
#: expensive kind of confusion available here: the up-front figure is smaller, so
#: a reader who budgets from it understates what the degree costs, and a reader
#: who needs the total but is shown the deposit cannot show that they qualify.
INITIAL_CASH_V1 = FormulaSpec(
    formula_id="initial_cash_v1",
    version=1,
    expression=(
        "initial_cash = first_year_tuition + (monthly_living_cost * 12) "
        "+ one_time_fees + blocked_account"
    ),
    inputs=(
        FormulaInputSpec(name="first_year_tuition", expected_per="year"),
        FormulaInputSpec(name="monthly_living_cost", expected_per="month"),
        FormulaInputSpec(name="one_time_fees", expected_per="once", required=False),
        FormulaInputSpec(
            name="blocked_account",
            expected_per="once",
            required=False,
            description=(
                "Money frozen on a residence permit. Not spent, so it is excluded "
                "from total economic cost and included here."
            ),
        ),
    ),
    output_per="once",
    assumptions=(
        "A blocked account is money the student cannot spend, not a cost. It is "
        "reported here and excluded from programme cost.",
    ),
    refusals=(REFUSAL_MISSING_INPUT, REFUSAL_UNIT_MISMATCH, REFUSAL_MISSING_FX_RATE),
    evaluator=lambda v: (
        v["first_year_tuition"].value
        + v["monthly_living_cost"].value * 12.0
        + (v.get("one_time_fees").value if v.get("one_time_fees") else 0.0)
        + (v.get("blocked_account").value if v.get("blocked_account") else 0.0)
    ),
)

#: Sum of independently sourced one-time costs.
ONE_TIME_TOTAL_V1 = FormulaSpec(
    formula_id="one_time_total_v1",
    version=1,
    expression="one_time_total = sum(each sourced one-time component)",
    inputs=(),
    output_per="once",
    assumptions=(
        "Only components that are individually sourced are summed, and the formula "
        "names each one. A total that quietly omitted an unsourced visa fee would "
        "read as complete.",
    ),
    refusals=(REFUSAL_MISSING_INPUT, REFUSAL_MISSING_FX_RATE),
    evaluator=lambda v: v["__total__"].value,
)

FORMULAS: dict[str, FormulaSpec] = {
    spec.formula_id: spec
    for spec in (
        ANNUAL_COST_V1,
        BREAK_EVEN_MONTHS_V1,
        EXPECTED_TUITION_V1,
        INITIAL_CASH_V1,
        MULTI_YEAR_COST_V1,
        ONE_TIME_TOTAL_V1,
    )
}

#: ``formula_id`` -> every published version. A reader that has cached
#: ``expected_tuition_v1`` version 1 can tell whether the arithmetic changed.
FORMULA_VERSIONS: dict[str, tuple[int, ...]] = {
    formula_id: (spec.version,) for formula_id, spec in FORMULAS.items()
}


def get_formula(formula_id: str, version: int | None = None) -> FormulaSpec | None:
    """A registered formula, or ``None``.

    A version is checked when supplied so a corpus file pinned to version 1 of a
    formula that has since been revised cannot be evaluated with the new
    arithmetic and still claim to be version 1.
    """
    spec = FORMULAS.get(formula_id)
    if spec is None:
        return None
    if version is not None and spec.version != version:
        return None
    return spec


def formula_contracts() -> list[dict[str, Any]]:
    """Every registered formula, for publication on the meta endpoint."""
    return [spec.to_contract() for spec in FORMULAS.values()]


def _check_currency(
    spec: FormulaSpec, inputs: Mapping[str, FormulaInput]
) -> str | None:
    """Refuse when monetary inputs are not in one currency. Never convert."""
    currencies = {
        item.currency
        for name, item in inputs.items()
        if any(s.name == name and s.monetary for s in spec.inputs) and item.currency
    }
    if len(currencies) > 1:
        return ", ".join(sorted(currencies))
    return None


def evaluate(
    spec: FormulaSpec, inputs: Mapping[str, FormulaInput]
) -> FormulaOutcome:
    """Run a formula, or say precisely why it will not run.

    Every failure path returns a refusal with a code. There is no branch that
    substitutes a default, drops an input, or returns a number it is unsure of -
    the entire point of this module is that a derived figure is either
    reproducible from what it declares or it is not published.
    """
    resolved = {name: item for name, item in inputs.items() if item is not None}

    for spec_input in spec.inputs:
        if not spec_input.required:
            continue
        item = resolved.get(spec_input.name)
        if item is None:
            return _refuse(
                spec, resolved, REFUSAL_MISSING_INPUT,
                f"Required input {spec_input.name!r} was not supplied. "
                f"{spec_input.description}".strip(),
            )

    for spec_input in spec.inputs:
        item = resolved.get(spec_input.name)
        if item is None:
            continue
        if spec_input.expected_per is not None and item.per not in (
            None, spec_input.expected_per
        ):
            return _refuse(
                spec, resolved, REFUSAL_UNIT_MISMATCH,
                f"Input {spec_input.name!r} is quoted per {item.per!r} but this "
                f"formula requires per {spec_input.expected_per!r}. Feeding one "
                f"into the other would be wrong by a factor of the period.",
            )
        if spec_input.requires_net_basis and item.basis != "net":
            label = item.basis or "undeclared"
            return _refuse(
                spec, resolved, REFUSAL_UNIT_MISMATCH,
                f"Input {spec_input.name!r} is {label}, not take-home pay. "
                f"Break-even compares money out against money in, so only a net "
                f"figure may be used; take-home pay is typically a fraction of "
                f"gross, so using gross would roughly halve the months reported.",
            )
        if spec_input.monetary and item.currency is None and item.value != 0:
            return _refuse(
                spec, resolved, REFUSAL_MISSING_INPUT,
                f"Input {spec_input.name!r} has no currency, so it cannot be added "
                f"to another monetary figure.",
            )

    mixed = _check_currency(spec, resolved)
    if mixed is not None:
        return _refuse(
            spec, resolved, REFUSAL_MISSING_FX_RATE,
            f"Monetary inputs are quoted in more than one currency ({mixed}) and "
            f"this corpus holds no sourced exchange rate, so they cannot be added. "
            f"No rate was assumed.",
        )

    try:
        raw = spec.evaluator(dict(resolved))
    except (KeyError, ZeroDivisionError, TypeError) as exc:
        return _refuse(
            spec, resolved, REFUSAL_MISSING_INPUT,
            f"The formula could not be evaluated from the supplied inputs: {exc}.",
        )

    currency = next(
        (item.currency for item in resolved.values() if item.currency), None
    )
    return FormulaOutcome(
        formula_id=spec.formula_id,
        version=spec.version,
        inputs=dict(resolved),
        value=round(float(raw), spec.decimals),
        currency=currency,
        per=spec.output_per,
        assumptions=spec.assumptions,
        expression=spec.expression,
    )


def values_agree(declared: float, recomputed: float) -> bool:
    """Whether a declared figure matches a recomputation of it."""
    return abs(declared - recomputed) <= max(
        ABSOLUTE_TOLERANCE, RELATIVE_TOLERANCE * abs(recomputed)
    )


def _coerce_declared_input(spec_input: FormulaInputSpec, raw: Any, *, path: str) -> FormulaInput:
    """Read one declared formula input from a corpus claim body.

    Accepts a bare number or an object carrying ``value``/``currency``/``per``.
    A bare number is only allowed for a non-monetary input, where there is no
    unit to state and nothing to get wrong.
    """
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        if spec_input.monetary:
            raise ClaimError(
                f"{path}: formula input {spec_input.name!r} is a bare number, but a "
                f"monetary input must declare its currency. Use "
                f'{{"value": ..., "currency": "...", "per": "..."}}.'
            )
        return FormulaInput(name=spec_input.name, value=float(raw))
    if not isinstance(raw, Mapping):
        raise ClaimError(
            f"{path}: formula input {spec_input.name!r} must be a number or an object, "
            f"found {type(raw).__name__}."
        )

    value = raw.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ClaimError(
            f"{path}: formula input {spec_input.name!r} needs a numeric 'value'."
        )
    per = raw.get("per")
    if per is not None and per not in ALLOWED_PERIODS:
        raise ClaimError(
            f"{path}: formula input {spec_input.name!r} has per={per!r}, which is not "
            f"one of {', '.join(sorted(ALLOWED_PERIODS))}."
        )
    return FormulaInput(
        name=spec_input.name,
        value=float(value),
        currency=raw.get("currency"),
        per=per,
        basis=raw.get("basis"),
    )


def verify_formula_claim(raw: Mapping[str, Any], *, path: str) -> FormulaOutcome:
    """Validate one DERIVED figure's formula and prove it reproduces the value.

    Raises ``ClaimError`` when the formula is missing, unrecognised, references an
    input it does not declare, is refused, or disagrees with the value beside it.
    A corpus file must therefore pass this to be published at all.

    The declared ``formula`` may be a registry id (the usual form) or a full
    contract object. Both are held to the same standard; the object form is
    accepted so a reviewed file states the version it was written against.
    """
    declared = raw.get("formula")
    if not declared:
        raise ClaimError(
            f"{path}: a DERIVED figure must declare a formula. A derived number "
            f"whose arithmetic is unstated cannot be checked by anyone, including "
            f"its author."
        )

    if isinstance(declared, str):
        declared_id, declared_version, inputs_raw = declared, None, raw.get("inputs")
    elif isinstance(declared, Mapping):
        declared_id = declared.get("formula_id")
        declared_version = declared.get("formula_version")
        inputs_raw = declared.get("inputs")
        declared_expression = declared.get("expression")
        if declared_expression is not None:
            known_spec = get_formula(declared_id or "")
            if known_spec is None:
                raise ClaimError(
                    f"{path}: formula {declared_id!r} is not registered, so its "
                    f"expression cannot be checked."
                )
            if declared_expression != known_spec.expression:
                raise ClaimError(
                    f"{path}: formula expression {declared_expression!r} does not "
                    f"match the registered expression for {declared_id!r}. The "
                    f"arithmetic is defined in code; a file cannot restate it "
                    f"differently."
                )
    else:
        raise ClaimError(
            f"{path}: 'formula' must be a registry id or an object, found "
            f"{type(declared).__name__}."
        )

    spec = get_formula(declared_id or "", declared_version)
    if spec is None:
        known = ", ".join(sorted(FORMULAS))
        raise ClaimError(
            f"{path}: formula {declared_id!r}"
            + (f" version {declared_version}" if declared_version is not None else "")
            + f" is not registered. Known formulas: {known}."
        )

    if not isinstance(inputs_raw, Mapping):
        raise ClaimError(
            f"{path}: formula {spec.formula_id!r} requires an 'inputs' object naming "
            f"each value it used."
        )

    declared_names = {spec_input.name for spec_input in spec.inputs}
    for spec_input in spec.inputs:
        if spec_input.required and spec_input.name not in inputs_raw:
            raise ClaimError(
                f"{path}: formula {spec.formula_id!r} requires input "
                f"{spec_input.name!r}, which this figure does not declare. The "
                f"formula cannot be reproduced without every input it uses."
            )

    unexpected = sorted(set(inputs_raw) - declared_names)
    if unexpected:
        raise ClaimError(
            f"{path}: formula {spec.formula_id!r} does not accept input(s) "
            f"{', '.join(unexpected)}. Declared inputs are "
            f"{', '.join(sorted(declared_names))}. An unrecognised input means the "
            f"arithmetic that produced this value is not the arithmetic on record."
        )

    resolved: dict[str, FormulaInput] = {}
    for spec_input in spec.inputs:
        if spec_input.name not in inputs_raw:
            continue
        resolved[spec_input.name] = _coerce_declared_input(
            spec_input, inputs_raw[spec_input.name], path=path
        )

    outcome = evaluate(spec, resolved)
    if not outcome.computed:
        raise ClaimError(
            f"{path}: formula {spec.formula_id!r} does not produce a value for the "
            f"inputs given - {outcome.refusal}: {outcome.reason}"
        )

    value = raw.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ClaimError(f"{path}: a DERIVED figure needs a numeric 'value'.")

    if not values_agree(float(value), outcome.value):
        raise ClaimError(
            f"{path}: declared value {value!r} does not match {spec.formula_id!r} "
            f"applied to its own declared inputs, which give {outcome.value!r} "
            f"({spec.expression}). A derived figure that its own formula does not "
            f"reproduce is a transcription error and is rejected."
        )

    declared_currency = raw.get("currency")
    if declared_currency is not None and outcome.currency is not None:
        if declared_currency != outcome.currency:
            raise ClaimError(
                f"{path}: declared currency {declared_currency!r} does not match the "
                f"currency of its inputs ({outcome.currency!r})."
            )

    return outcome


def registry_problems() -> list[str]:
    """Incoherences in the formula registry itself. Empty is correct.

    This is a self-check on the module rather than on any corpus file. It exists
    because the registry is hand-maintained data as much as code, and these are
    the mistakes that are easy to make while editing it and invisible until a
    figure somewhere else goes wrong: a duplicated id shadowing a formula, a
    duplicate expression suggesting a copy-paste, an output period outside the
    closed vocabulary, or a formula whose ``refusals`` omit a code it can
    actually raise.

    Exposed as a function so a failure names the offending formula instead of
    appearing as an assertion on import.
    """
    problems: list[str] = []
    seen_expressions: dict[str, str] = {}
    for formula_id, spec in FORMULAS.items():
        if spec.formula_id != formula_id:
            problems.append(
                f"{formula_id}: registered under a key that is not its own formula_id "
                f"({spec.formula_id!r})"
            )
        if spec.version < 1:
            problems.append(f"{formula_id}: version must be >= 1, found {spec.version}")
        if not spec.expression.strip():
            problems.append(f"{formula_id}: expression is empty; it is the published receipt")
        if spec.output_per not in ALLOWED_OUTPUT_UNITS:
            problems.append(
                f"{formula_id}: output_per {spec.output_per!r} is not one of "
                f"{', '.join(sorted(ALLOWED_OUTPUT_UNITS))}"
            )
        for spec_input in spec.inputs:
            if spec_input.expected_per is not None and spec_input.expected_per not in ALLOWED_PERIODS:
                problems.append(
                    f"{formula_id}: input {spec_input.name!r} expects per "
                    f"{spec_input.expected_per!r}, which is outside the vocabulary"
                )
            if spec_input.expected_per is None and spec_input.monetary:
                problems.append(
                    f"{formula_id}: monetary input {spec_input.name!r} declares no "
                    f"expected_per, so a monthly figure could be fed to an annual "
                    f"formula unnoticed"
                )
        # Only demand a refusal code the formula can actually raise. A formula
        # with no monetary input cannot hit a currency refusal, and one with no
        # declared periods cannot hit a unit refusal; demanding them anyway would
        # push authors to list refusals they cannot produce, which is the same
        # "declare a badge that does nothing" problem this corpus exists to avoid.
        raiseable = {REFUSAL_MISSING_INPUT}
        if any(spec_input.expected_per or spec_input.requires_net_basis for spec_input in spec.inputs):
            raiseable.add(REFUSAL_UNIT_MISMATCH)
        if any(spec_input.monetary for spec_input in spec.inputs):
            raiseable.add(REFUSAL_MISSING_FX_RATE)
        if not raiseable <= set(spec.refusals):
            missing = sorted(raiseable - set(spec.refusals))
            problems.append(
                f"{formula_id}: refusals omit codes this formula can raise: "
                f"{', '.join(missing)}"
            )
        if spec.expression in seen_expressions:
            problems.append(
                f"{formula_id}: expression is identical to {seen_expressions[spec.expression]!r}; "
                f"one of them is a copy-paste"
            )
        else:
            seen_expressions[spec.expression] = formula_id
    return problems


__all__ = [
    "ALLOWED_PERIODS",
    "FORMULAS",
    "FORMULA_VERSIONS",
    "PERIOD_MONTHS",
    "FormulaInput",
    "FormulaInputSpec",
    "FormulaOutcome",
    "FormulaSpec",
    "evaluate",
    "formula_contracts",
    "get_formula",
    "values_agree",
    "verify_formula_claim",
]
