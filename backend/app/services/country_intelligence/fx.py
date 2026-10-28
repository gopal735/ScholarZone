"""Sourced, dated exchange rates for cross-currency comparison.

## Why this exists

Comparison previously refused every mixed-currency row, because the corpus held no
exchange rate and converting at a remembered or assumed rate is how a comparison
silently inverts. That refusal was correct and it was also the only thing available.

Now a rate exists with a source, a publisher and a date, which is what the refusal
was waiting for. This module is the only place a conversion may happen.

## What it will not do

It will not guess, interpolate, or fall back. If a currency is absent from the
table, the result is a refusal with a reason. If no path exists between two
currencies, likewise. There is no "assume parity" branch, because parity is a
conversion rate that nobody sourced.

## Direction is explicit

Rates are stored as *units of foreign currency per one unit of base*, and
:meth:`FxTable.convert` states which direction it converted in both the return
value and the published metadata. Getting this backwards is the single most likely
error with an FX table: ``1 EUR = 1.1225 USD`` and ``1 USD = 0.8908 EUR`` are the
same fact, and mixing them turns a cost comparison into its inverse. Rather than
rely on a caller reading the base correctly, every published conversion carries the
rate it used, its date, and the pair it was applied to.

## The ECB caveat travels with the numbers

The European Central Bank publishes its reference rates "for information purposes
only" and discourages using them for transactions. That is fine for comparing the
magnitude of study costs across countries and wrong for budgeting a transfer. The
caveat is part of the published payload, not a comment, so a client cannot render a
converted figure without also being able to render why it is indicative.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from .provenance import ClaimError

#: Where the canonical rate table lives, relative to the corpus directory.
FX_DIRNAME = "fx"
RATES_FILENAME = "rates.json"


class FxUnavailable(Exception):
    """No sourced rate exists for the requested conversion.

    Raised rather than returned so a caller cannot accidentally treat a missing
    rate as a conversion that produced ``None``, which is indistinguishable from a
    genuine absence in a result payload.
    """


@dataclass(frozen=True)
class Conversion:
    """One conversion, with everything needed to audit and reproduce it."""

    amount: float
    from_currency: str
    to_currency: str
    rate: float
    rate_date: str
    source_id: str
    source_url: str
    via: tuple[str, ...]
    caveat: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": round(self.amount, 2),
            "from_currency": self.from_currency,
            "to_currency": self.to_currency,
            "rate": self.rate,
            "rate_definition": f"units of {self.to_currency} per 1 {self.from_currency}",
            "rate_date": self.rate_date,
            "source_id": self.source_id,
            "source_url": self.source_url,
            "via": list(self.via),
            "caveat": self.caveat,
        }


@dataclass(frozen=True)
class FxTable:
    """One dated set of reference rates, quoted against a single base."""

    base: str
    as_of: str
    rates: dict[str, float]
    source_id: str
    source_url: str
    publisher: str
    caveat: str

    def has(self, currency: str) -> bool:
        code = (currency or "").upper()
        return code == self.base or code in self.rates

    def convert(self, amount: float, from_currency: str, to_currency: str) -> Conversion:
        """Convert between two currencies through the base, or refuse.

        Every conversion is a pair of legs against the base, and both legs are
        published. That is slower than a shortcut and it is the point: a reader can
        see exactly how a GBP figure became a EUR figure without trusting the
        arithmetic.
        """
        source = (from_currency or "").upper()
        target = (to_currency or "").upper()

        if not source or not target:
            raise FxUnavailable(
                "A conversion needs both a source and a target currency; one was "
                "missing, and no rate was assumed."
            )
        if source == target:
            return Conversion(
                amount=float(amount),
                from_currency=source,
                to_currency=target,
                rate=1.0,
                rate_date=self.as_of,
                source_id=self.source_id,
                source_url=self.source_url,
                via=(source,),
                caveat="No conversion was needed; both figures are already in "
                f"{source}.",
            )
        for currency in (source, target):
            if not self.has(currency):
                raise FxUnavailable(
                    f"{currency} is not in the rate table dated {self.as_of}. The "
                    f"table covers {self.base} and {', '.join(sorted(self.rates))}. "
                    f"No rate was assumed for it."
                )

        # Units of X per 1 EUR.
        source_per_base = 1.0 if source == self.base else self.rates[source]
        target_per_base = 1.0 if target == self.base else self.rates[target]
        rate = target_per_base / source_per_base

        return Conversion(
            amount=float(amount) * rate,
            from_currency=source,
            to_currency=target,
            rate=rate,
            rate_date=self.as_of,
            source_id=self.source_id,
            source_url=self.source_url,
            via=(source, self.base, target),
            caveat=self.caveat,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "base": self.base,
            "as_of": self.as_of,
            "source_id": self.source_id,
            "source_url": self.source_url,
            "publisher": self.publisher,
            "currencies": sorted({self.base, *self.rates}),
            "rate_count": len(self.rates),
            "caveat": self.caveat,
        }


#: The ECB's own restriction, carried so it cannot be dropped downstream.
ECB_INFORMATION_ONLY_CAVEAT = (
    "European Central Bank reference rates are published for information purposes "
    "only; the ECB discourages using them for transactions. These figures compare "
    "the magnitude of study costs between countries and must not be used to budget "
    "a currency transfer."
)


def parse_fx_table(document: Any, *, path: str = "fx/rates.json") -> FxTable:
    """Validate a canonical rate table.

    Rejects a table with no date, no base, or no rates. All three would produce
    conversions that could not be audited, which is the one thing this module
    exists to prevent.
    """
    if not isinstance(document, dict):
        raise ClaimError(f"{path}: rate table must be an object.")
    base = document.get("base")
    as_of = document.get("as_of")
    rates = document.get("rates")
    source_id = document.get("source_id")
    source_url = document.get("source_url")

    for field, value in (
        ("base", base), ("as_of", as_of),
        ("source_id", source_id), ("source_url", source_url),
    ):
        if not value or not isinstance(value, str):
            raise ClaimError(
                f"{path}: {field!r} is required. A rate without a {field} cannot be "
                f"audited, and an unauditable rate must not be used to convert."
            )
    if not isinstance(rates, dict) or not rates:
        raise ClaimError(f"{path}: 'rates' must be a non-empty object.")

    parsed: dict[str, float] = {}
    for currency, rate in rates.items():
        code = str(currency).upper()
        if len(code) != 3 or not code.isalpha():
            raise ClaimError(f"{path}: {currency!r} is not a three-letter currency code.")
        if code == base.upper():
            raise ClaimError(
                f"{path}: the base currency must not appear in 'rates'; it is 1 by "
                f"definition and listing it invites a double conversion."
            )
        if isinstance(rate, bool) or not isinstance(rate, (int, float)) or rate <= 0:
            raise ClaimError(f"{path}: rate for {code} must be a positive number.")
        parsed[code] = float(rate)

    return FxTable(
        base=base.upper(),
        as_of=as_of,
        rates=parsed,
        source_id=source_id,
        source_url=source_url,
        publisher=document.get("publisher") or "unspecified",
        caveat=document.get("caveat") or ECB_INFORMATION_ONLY_CAVEAT,
    )


@lru_cache(maxsize=1)
def get_fx_table(directory: Path | None = None) -> FxTable | None:
    """The canonical rate table, or ``None`` when there is none.

    Cached per directory so corpus loading stays a single read in production and a
    test can point at a temporary one. Absent is a legitimate state: comparison
    falls back to refusing mixed-currency rows, which is the correct behaviour
    before a rate has been sourced.
    """
    from .corpus import CORPUS_DIR

    base = Path(directory) if directory is not None else CORPUS_DIR
    path = base / FX_DIRNAME / RATES_FILENAME
    if not path.exists():
        return None
    document = json.loads(path.read_text(encoding="utf-8"))
    return parse_fx_table(document, path=str(path))


def reload_fx_table() -> None:
    """Drop the process cache. For tests that change the table on disk."""
    get_fx_table.cache_clear()


__all__ = [
    "ECB_INFORMATION_ONLY_CAVEAT",
    "Conversion",
    "FxTable",
    "FxUnavailable",
    "get_fx_table",
    "parse_fx_table",
    "reload_fx_table",
]