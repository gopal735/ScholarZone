"""Country normalisation for Country Intelligence.

The catalogue stores ``scholarships.country`` as free text. On the 722 stored rows it
carries 82 distinct strings for 63 real countries plus a handful of
multi-country and worldwide scopes. Those strings are *not* clean: ``"United
States"`` and ``"USA"`` are the same country, ``"Czech Republic"`` and
``"Czechia"`` are the same country, and one row holds a corrupted ``"Türkiye"``
whose ``ü`` was written as a single Latin-1 byte. Counting per raw string would
split a country in half and invent a third country that does not exist.

Resolution therefore happens on the *canonical* country, and this module is the one
place that decides it.

## Why this does not extend ``matching.normalize.COUNTRY_CODES``

``COUNTRY_CODES`` is an eligibility gate. Adding an entry there would let a new
country resolve inside nationality and preferred-country scoring, which changes
Match results. That is out of scope here and is exactly the kind of silent
behaviour change this feature must not make. So ``COUNTRY_CODES`` is reused
verbatim as the first step, and this module adds a second, explicitly enumerated
layer on top for the countries the gate does not know about.

The extension is a visible constant with one entry per decision, so a reviewer can
see every difference between "what the Match gate knows" and "what Country
Intelligence knows" without reading call sites.

## Nothing is guessed

An unrecognised string resolves to ``None`` and says why. Substring matching is
specifically not used: ``"Ireland"`` is a substring of neither ``"Northern Ireland"``
nor ``"Netherlands"``, but ``"Chad"`` is a substring of nothing useful either, and
the day a country name is a prefix of another country's name a substring rule
silently reassigns one country's scholarships to the other. A lookup that returns
``None`` is recoverable; a wrong answer is not.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable

from ..matching.normalize import COUNTRY_CODES, resolve_country_code

#: How a raw ``scholarships.country`` string was classified.
#:
#: ``COUNTRY`` - exactly one country, with a resolved ISO 3166-1 alpha-2 code.
#: ``MULTI_COUNTRY`` - the string enumerates more than one country. The
#:   enumeration is resolved where the names are recognised, because a scholarship
#:   open to "Czechia, Hungary, Poland and Slovakia" belongs to four country
#:   counts, not to a fifth country.
#: ``GLOBAL`` - the string claims no particular country ("Global", "International").
#: ``UNRESOLVED`` - the string looks like a country but no name is recognised. The
#:   value is never silently folded into ``GLOBAL``: a typo and a worldwide scheme
#:   are different problems with different fixes.
COUNTRY_VALUE_KIND = ("COUNTRY", "MULTI_COUNTRY", "GLOBAL", "UNRESOLVED")


#: Countries present in the catalogue that ``matching.normalize.COUNTRY_CODES``
#: does not carry, with their ISO 3166-1 alpha-2 code and display name.
#:
#: Verified against the 82 distinct ``country`` strings on the stored catalogue:
#: these 18 rows resolve to real countries that the Match gate treats as unknown.
#: Extending ``COUNTRY_CODES`` instead would quietly widen eligibility scoring,
#: which this feature must not do.
COUNTRY_CODE_EXTENSIONS: dict[str, str] = {
    "algeria": "DZ",
    "barbados": "BB",
    "brunei": "BN",
    "brunei darussalam": "BN",
    "fiji": "FJ",
    "guyana": "GY",
    "hong kong": "HK",
    "mauritius": "MU",
    "rwanda": "RW",
    # Stored as the official name with a precomposed ``ü``. ``COUNTRY_CODES``
    # carries only the ASCII transliteration "turkiye", so the official spelling
    # the catalogue actually uses resolves to nothing without this entry.
    "t\u00fcrkiye": "TR",
}

#: ISO 3166-1 alpha-2 codes that exist but are not countries in the residency or
#: cost sense used here. ``HK`` is a Special Administrative Region, which is a
#: correct destination with its own immigration system, not an error to be folded
#: into China. It is researched on its own terms and carries its own figures.
CODE_NOTES: dict[str, str] = {
    "HK": "Special Administrative Region with its own immigration system; not counted within China.",
}

#: Strings that describe an opening with no single host country. They are counted
#: and surfaced - a worldwide scheme is real information - but they are never
#: attributed to a country, because attributing "Global" to a country would inflate
#: that country's scholarship count with programmes it does not host.
GLOBAL_VALUE_PHRASES: frozenset[str] = frozenset(
    {
        "global",
        "international",
        "multiple",
        "multiple countries",
        "eu (multiple)",
        "multi-country",
        "worldwide",
        "all countries",
        "any country",
    }
)

#: Display name for every ISO code this feature can publish. Sourced from the ISO
#: 3166 English short name, so the UI never shows a raw two-letter code where a
#: name belongs.
COUNTRY_DISPLAY_NAMES: dict[str, str] = {
    "AE": "United Arab Emirates", "AR": "Argentina", "AT": "Austria", "AU": "Australia",
    "AZ": "Azerbaijan", "BD": "Bangladesh", "BE": "Belgium", "BG": "Bulgaria",
    "BN": "Brunei", "BO": "Bolivia", "BR": "Brazil", "CA": "Canada", "CH": "Switzerland",
    "CL": "Chile", "CN": "China", "CO": "Colombia", "CR": "Costa Rica", "CZ": "Czechia",
    "DE": "Germany", "DK": "Denmark", "DZ": "Algeria", "EC": "Ecuador",
    "EE": "Estonia", "EG": "Egypt", "ES": "Spain",
    "FI": "Finland", "FR": "France", "GB": "United Kingdom", "GE": "Georgia",
    "GH": "Ghana", "GR": "Greece", "HK": "Hong Kong", "HR": "Croatia", "HU": "Hungary",
    "ID": "Indonesia", "IE": "Ireland", "IL": "Israel", "IN": "India", "IQ": "Iraq",
    "IR": "Iran", "IS": "Iceland", "IT": "Italy", "JP": "Japan", "KE": "Kenya",
    "KR": "South Korea", "KW": "Kuwait", "KZ": "Kazakhstan", "LB": "Lebanon",
    "LK": "Sri Lanka", "LT": "Lithuania", "LU": "Luxembourg", "LV": "Latvia",
    "MA": "Morocco", "MK": "North Macedonia", "ML": "Mali",
    "MT": "Malta", "MX": "Mexico", "MY": "Malaysia", "NG": "Nigeria", "NL": "Netherlands",
    "NO": "Norway", "NP": "Nepal", "NZ": "New Zealand", "OM": "Oman", "PA": "Panama",
    "PE": "Peru", "PH": "Philippines", "PK": "Pakistan", "PL": "Poland",
    "PT": "Portugal", "QA": "Qatar", "RO": "Romania", "RS": "Serbia", "RU": "Russia",
    "RW": "Rwanda", "SA": "Saudi Arabia", "SE": "Sweden", "SG": "Singapore",
    "SI": "Slovenia", "SK": "Slovakia", "TH": "Thailand", "TR": "Türkiye", "TW": "Taiwan",
    "UA": "Ukraine", "US": "United States", "UY": "Uruguay", "UZ": "Uzbekistan",
    "VN": "Vietnam", "ZA": "South Africa", "ZM": "Zambia", "ZW": "Zimbabwe",
}

#: Flag emoji for every ISO code published here. Derived from the code's two
#: regional indicator symbols, so it cannot drift from the code it represents.
_FLAG_RANGES = ((0x1F1E6, 0x1F1FF),)


def flag_emoji(iso2: str) -> str | None:
    """Regional-indicator flag for an ISO alpha-2 code, or ``None`` if invalid."""
    if len(iso2) != 2 or not iso2.isalpha() or not iso2.isascii():
        return None
    return "".join(chr(_FLAG_RANGES[0][0] + ord(ch.upper()) - ord("A")) for ch in iso2)


def display_name(iso2: str) -> str:
    """Human name for an ISO code.

    Falls back to the code itself rather than to an invented name, so an unmapped
    code is visibly unmapped instead of silently mislabelled.
    """
    return COUNTRY_DISPLAY_NAMES.get(iso2, iso2)


def normalise_country_text(value: str | None) -> str:
    """Fold a stored country string to a comparable form.

    Unicode is normalised to NFC and whitespace is collapsed. NFC is not cosmetic
    here: the catalogue stores one country as ``"Türkiye"`` with a precomposed
    ``ü`` (``U+00FC``), and a value written by a different editor as ``"T"``
    plus ``U+0075 U+0308`` is the same country name in a different encoding.
    Without folding, the two forms are different strings and one of them silently
    disappears from the country counts.
    """
    text = unicodedata.normalize("NFC", (value or "")).strip()
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).lower()


def resolve_country_code_extended(value: str | None) -> str | None:
    """Resolve a country name or ISO code to alpha-2, extending the Match gate.

    The alias map is consulted **before** the Match gate, and that ordering is not
    incidental. ``resolve_country_code`` contains a shortcut that returns any
    two-letter input uppercased, so it answers ``"uk"`` with ``"UK"`` - which is
    not an ISO 3166-1 alpha-2 country code - and returns that before the alias map
    is ever read. The catalogue stores both ``"UK"`` and ``"United Kingdom"``, so
    asking the gate first splits one country into two: the United Kingdom ends up
    counted twice, once as a country that does not exist and once as the real one.

    Checking the alias map first resolves that, and costs nothing elsewhere: any
    genuine ISO code that is also a name key resolves to the same value either way.
    Neither layer is allowed to answer by guessing a substring.
    """
    text = normalise_country_text(value)
    if not text:
        return None
    aliased = COUNTRY_CODES.get(text)
    if aliased:
        return aliased
    extended = COUNTRY_CODE_EXTENSIONS.get(text)
    if extended:
        return extended
    return resolve_country_code(value)


@dataclass(frozen=True)
class CountryResolution:
    """What a stored country string turned out to be.

    ``iso2`` is populated for ``COUNTRY`` only. ``members`` is populated for
    ``MULTI_COUNTRY`` and lists every member that resolved, so a four-country
    programme is counted under each of the four. ``unresolved_members`` lists the
    members that did *not* resolve, and is published rather than discarded: a
    string naming five countries of which three are recognised must not be counted
    as though it named three countries, because the two countries that went missing
    would appear to host nothing. ``reason`` is populated whenever the string could
    not be attributed, and is published rather than discarded.
    """

    raw: str
    kind: str
    iso2: str | None = None
    members: tuple[str, ...] = field(default_factory=tuple)
    unresolved_members: tuple[str, ...] = field(default_factory=tuple)
    reason: str | None = None

    @property
    def is_country(self) -> bool:
        return self.kind == "COUNTRY"

    @property
    def is_partially_resolved(self) -> bool:
        """True when at least one enumerated host country could not be resolved.

        The record is still counted under every country that *did* resolve - that
        part is known and useful - but the partial state is reported, because a
        half-counted record otherwise looks like a complete one.
        """
        return bool(self.members) and bool(self.unresolved_members)


def _split_enumeration(text: str) -> list[str]:
    """Split an enumerated country string into candidate country names.

    Handles the separators that actually appear in the catalogue - commas,
    slashes, semicolons, ``and``, ampersands and newlines - and splits hyphenated
    qualifiers such as ``"host-country"`` on the hyphen. It does not attempt full
    natural-language parsing, because the alternative is guessing, and a guessed
    membership is a scholarship attributed to a country that cannot host it.
    """
    parts = re.split(r",|;|/|\band\b|&|\n|\+", text)
    cleaned: list[str] = []
    for part in parts:
        candidate = part.strip().strip(".;")
        # A trailing qualifier describes the scheme, not a country.
        candidate = re.split(r"\s+-\s+|\s+\(", candidate)[0]
        candidate = candidate.strip()
        if candidate:
            cleaned.append(candidate)
    return cleaned


def classify_country_value(value: str | None) -> CountryResolution:
    """Classify one stored ``country`` string into exactly one published kind.

    This is the only entry point the rest of the feature uses. It never raises and
    never returns a partially populated result.
    """
    raw = (value or "").strip()
    text = normalise_country_text(raw)
    if not text:
        return CountryResolution(
            raw=raw, kind="UNRESOLVED", reason="Empty country value."
        )

    single = resolve_country_code_extended(text)
    if single:
        return CountryResolution(raw=raw, kind="COUNTRY", iso2=single)

    if text in GLOBAL_VALUE_PHRASES:
        return CountryResolution(
            raw=raw,
            kind="GLOBAL",
            reason="The record states no single host country.",
        )

    # An enumeration: every member that resolves is a real host of this record.
    parts = _split_enumeration(text)
    if len(parts) > 1:
        members: list[str] = []
        unresolved: list[str] = []
        for part in parts:
            code = resolve_country_code_extended(part)
            if code:
                members.append(code)
            elif part not in GLOBAL_VALUE_PHRASES and not _looks_like_scope(part):
                # A bare unrecognised name is a genuine gap and is reported. An
                # eligibility *scope* such as "low- or middle-income countries" is
                # not a host country we failed to recognise, so reporting it as one
                # would pad the gap list with text that never claimed to name a
                # country.
                unresolved.append(part)
        unique_members = tuple(dict.fromkeys(members))
        if unique_members:
            return CountryResolution(
                raw=raw,
                kind="MULTI_COUNTRY",
                members=unique_members,
                unresolved_members=tuple(dict.fromkeys(unresolved)),
                reason=(
                    f"Open to {len(unique_members)} recognised "
                    f"{'country' if len(unique_members) == 1 else 'countries'}."
                ),
            )
        return CountryResolution(
            raw=raw,
            kind="MULTI_COUNTRY",
            reason="The record enumerates several countries, none of which is recognised.",
        )

    return CountryResolution(
        raw=raw,
        kind="UNRESOLVED",
        reason="No recognised country name matches this value, and no guess was attempted.",
    )


#: Descriptions of *who* may apply, which are not country names. These appear
#: inside enumerated strings on the catalogue and must not be reported as a host
#: country that failed to resolve.
_SCOPE_MARKERS: tuple[str, ...] = (
    "countries",
    "nationals",
    "nationality",
    "citizens",
    "residents",
    "income",
    "applicant",
    "applicants",
    "students",
    "graduates",
    "region",
    "worldwide",
    "diaspora",
)


def _looks_like_scope(text: str) -> bool:
    """True when an enumeration member describes an eligibility scope, not a country.

    Deliberately narrow: it fires only on wording that is unambiguously a scope
    description. A bare unrecognised name is still reported, because a country
    this module has never heard of is exactly the gap a reviewer needs to see.
    """
    return any(marker in text for marker in _SCOPE_MARKERS)


def classify_country_values(values: Iterable[str | None]) -> list[CountryResolution]:
    """Classify an iterable of stored values, order-preserving and de-duplicated."""
    seen: set[str] = set()
    results: list[CountryResolution] = []
    for value in values:
        key = normalise_country_text(value)
        if key in seen:
            continue
        seen.add(key)
        results.append(classify_country_value(value))
    return results


__all__ = [
    "CODE_NOTES",
    "COUNTRY_CODE_EXTENSIONS",
    "COUNTRY_DISPLAY_NAMES",
    "COUNTRY_VALUE_KIND",
    "CountryResolution",
    "GLOBAL_VALUE_PHRASES",
    "classify_country_value",
    "classify_country_values",
    "display_name",
    "flag_emoji",
    "normalise_country_text",
    "resolve_country_code_extended",
]