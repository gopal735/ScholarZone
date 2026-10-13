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


#: Where the canonical Bangladeshi Taka reference rate lives. Kept as its own
#: file, not folded into the ECB table, for a reason that is verified and not a
#: preference: the ECB reference set genuinely does not publish a EUR/BDT rate,
#: so adding BDT to ``rates.json`` would put a figure there that no source on that
#: page backs. A second, separately-sourced and separately-dated rate is the only
#: honest representation, and keeping it in its own artifact is what lets a
#: reviewer see at a glance which publisher stands behind which number.
BDT_FILENAME = "bdt.json"


@dataclass(frozen=True)
class BdtConversion:
    """A conversion into Bangladeshi Taka, composed from its source legs.

    Every leg names the rate it used, the rate's date, the publisher and the URL,
    because a BDT figure is always the product of at least a bridge to US dollars
    (ECB) and the Bangladesh Bank rate itself. A reader who is shown only the final
    number cannot see that two different central banks and two different dates
    stand behind it, which is exactly the seam this payload exists to expose.
    """

    value: float
    amount: float
    from_currency: str
    legs: tuple[dict[str, Any], ...]
    caveat: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": round(self.value, 2),
            "amount": round(self.amount, 2),
            "from_currency": self.from_currency,
            "to_currency": "BDT",
            "legs": [dict(leg) for leg in self.legs],
            "caveat": self.caveat,
        }


@lru_cache(maxsize=1)
def get_bdt_table(directory: Path | None = None) -> FxTable | None:
    """The Bangladesh Bank USD/BDT reference rate, or ``None`` when absent.

    Absent is a legitimate state and the only honest one before a rate has been
    sourced. A caller that needs BDT calls :func:`convert_to_bdt` and gets a
    refusal naming the missing rate, never a figure derived from parity.
    """
    from .corpus import CORPUS_DIR

    base = Path(directory) if directory is not None else CORPUS_DIR
    path = base / FX_DIRNAME / BDT_FILENAME
    if not path.exists():
        return None
    document = json.loads(path.read_text(encoding="utf-8"))
    return parse_fx_table(document, path=str(path))


def reload_bdt_table() -> None:
    """Drop the process cache. For tests that change the table on disk."""
    get_bdt_table.cache_clear()


def convert_to_bdt(amount: Any, from_currency: str) -> dict[str, Any]:
    """Convert a sourced amount into Bangladeshi Taka, or refuse.

    BDT is shown beside the original figures with the exchange-rate date, which is
    the one conversion a Bangladeshi student needs and the one the ECB table cannot
    supply directly. The conversion is composed from two separately-sourced legs:

    1. the original currency is brought to US dollars through the **ECB** reference
       table (the corridor the corpus already trusts), then
    2. US dollars are brought to Taka through the **Bangladesh Bank** reference
       rate.

    Both legs, both rates, both dates and both publishers are published in the
    result. If either rate is missing the whole conversion is refused with the
    reason; no rate is assumed, interpolated or treated as parity, so a BDT figure
    is never produced from a number nobody sourced.
    """
    bdt = get_bdt_table()
    if bdt is None:
        raise FxUnavailable(
            "No sourced Bangladesh Bank reference rate is available, so a BDT "
            "figure cannot be shown. The original currency is preserved and no "
            "rate was assumed."
        )
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise FxUnavailable(
            "A BDT conversion needs a numeric amount; none was supplied and no "
            "rate was assumed."
        )
    src = (from_currency or "").strip().upper()

    if not src:
        raise FxUnavailable(
            "A conversion needs a source currency; none was supplied, and no rate "
            "was assumed."
        )

    legs: list[dict[str, Any]] = []

    if src == "BDT":
        return BdtConversion(
            value=float(amount),
            amount=float(amount),
            from_currency="BDT",
            legs=[{
                "step": "identity",
                "from_currency": "BDT",
                "to_currency": "BDT",
                "rate": 1.0,
                "rate_date": bdt.as_of,
                "amount": round(float(amount), 2),
                "note": "The figure is already in Bangladeshi Taka; no conversion was performed.",
            }],
            caveat=bdt.caveat,
        ).to_dict()

    current = float(amount)

    if src == "USD":
        legs.append({
            "step": "noop",
            "from_currency": "USD",
            "to_currency": "USD",
            "amount": round(current, 2),
            "note": "The figure is already in US dollars, so only the Bangladesh Bank leg applies.",
        })
    else:
        ecb = get_fx_table()
        if ecb is None:
            raise FxUnavailable(
                f"{src} is not US dollars and the corpus holds no sourced EUR "
                f"reference table to bridge it to a rate the Bangladesh Bank "
                f"table (US dollars) can convert. No rate was assumed, so BDT "
                f"cannot be shown for this figure."
            )
        bridge = ecb.convert(current, src, "USD")
        current = bridge.amount
        legs.append({
            "step": "bridge",
            "from_currency": src,
            "to_currency": "USD",
            "rate": bridge.rate,
            "rate_date": bridge.rate_date,
            "amount": round(bridge.amount, 2),
            "source_id": bridge.source_id,
            "source_url": bridge.source_url,
            "via": list(bridge.via),
        })

    final = bdt.convert(current, "USD", "BDT")
    legs.append({
        "step": "bdt",
        "from_currency": "USD",
        "to_currency": "BDT",
        "rate": final.rate,
        "rate_date": final.rate_date,
        "amount": round(final.amount, 2),
        "source_id": final.source_id,
        "source_url": final.source_url,
        "publisher": bdt.publisher,
        "via": list(final.via),
    })

    combined = (
        f"{bridge_caveat(legs)} The BDT figure also reflects the Bangladesh Bank "
        f"reference rate dated {bdt.as_of}; the two legs were published on "
        f"different dates and both are shown."
    ) if legs and legs[0].get("step") == "bridge" else bdt.caveat

    return BdtConversion(
        value=final.amount,
        amount=float(amount),
        from_currency=src,
        legs=tuple(legs),
        caveat=combined,
    ).to_dict()


def bridge_caveat(legs: list[dict[str, Any]]) -> str:
    """The ECB caveat, recovered from a bridge leg so it is never dropped.

    The ECB publishes for information only and discourages transactional use; a
    converted BDT figure carries that forward. Returning it from the leg rather
    than hardcoding it keeps the caveat travelling with the data rather than in a
    string a future edit can forget.
    """
    from .corpus import CORPUS_DIR  # noqa: F401 - locality: table loaded the same way

    ecb = get_fx_table()
    return ecb.caveat if ecb else ""


def reload_fx_table() -> None:
    """Drop the process cache. For tests that change the table on disk."""
    get_fx_table.cache_clear()


__all__ = [
    "BDT_FILENAME",
    "ECB_INFORMATION_ONLY_CAVEAT",
    "BdtConversion",
    "Conversion",
    "FxTable",
    "FxUnavailable",
    "convert_to_bdt",
    "get_bdt_table",
    "get_fx_table",
    "parse_fx_table",
    "reload_bdt_table",
    "reload_fx_table",
]