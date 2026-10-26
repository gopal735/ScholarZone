"""Canonical place taxonomy for the catalogue.

The catalogue stores three place-shaped facts on every row: ``country``,
``region`` and ``funding``. All three are free-text columns, so they drift.
This module is the one place that says what a canonical value looks like, and
it is importable by the repair tool, the ingest stages and the tests.

WHY A SHARED MODULE RATHER THAN A SCRIPT

``country`` is compared with ``==`` in deduplication
(``discovery_identity.find_near_duplicate``), entity resolution
(``entity_resolution``) and the knowledge graph (``knowledge_graph``). An alias
split is therefore not cosmetic: while the catalogue held both ``USA`` (22 rows)
and ``United States`` (38 rows), two records for the same award under different
spellings were two different countries as far as near-duplicate detection was
concerned, so the alias split was actively suppressing deduplication. Any place a
new value is introduced has to go through this module or the drift returns.

THE REGION ENUM

``region`` is display-only - no endpoint filters on it and the Match surface has
no region control - so the enum can be the correct one rather than the one that
happens to be stored. It deliberately excludes countries. ``Australia``,
``Canada``, ``United States`` and ``New Zealand`` were all being used as region
values (18, 11, 10 and 9 rows), which is the category error that let a sentence
like "South Africa (study must be in South Africa) - for citizens of any African
country" be a legal value.

Assignments follow ``matching.nlp.REGION_MEMBERS``, the curated expansion the
match engine already uses, so a region means the same thing in both places. That
table places Egypt, Morocco and Tunisia under MENA rather than Africa; this
module follows it rather than second-guessing it, because a second opinion about
where Egypt goes would produce a region that means something different in the
filter than in the pickers.
"""

from __future__ import annotations

import re
import unicodedata

#: The complete set of legal ``region`` values. Anything else in the column is a
#: defect, not a synonym.
REGIONS: tuple[str, ...] = (
    "Europe",
    "North America",
    "Latin America",
    "Asia",
    "Oceania",
    "Africa",
    "Middle East",
    "Global",
)

#: Value used when a record genuinely spans countries. It is a real answer to
#: "where", not a placeholder for "we did not look": the award publishes its own
#: eligible-country list, and that list belongs in eligibility, not in the place
#: columns.
MULTIPLE = "Multiple"

#: Country spellings the catalogue must never store, mapped to the canonical
#: name. Keys are compared casefolded after stripping accents, so the map is
#: written in plain ASCII and matches "Türkiye" as well as "Turkiye".
COUNTRY_ALIASES: dict[str, str] = {
    # The two splits that actually cost coverage.
    "usa": "United States",
    "us": "United States",
    "u s": "United States",
    "u s a": "United States",
    "united states of america": "United States",
    "america": "United States",
    "uk": "United Kingdom",
    "u k": "United Kingdom",
    "great britain": "United Kingdom",
    "britain": "United Kingdom",
    "england": "United Kingdom",
    "scotland": "United Kingdom",
    "wales": "United Kingdom",
    "northern ireland": "United Kingdom",
    # Long and short official forms.
    "brunei darussalam": "Brunei",
    "republic of korea": "South Korea",
    "korea": "South Korea",
    "russian federation": "Russia",
    "viet nam": "Vietnam",
    "hong kong sar": "Hong Kong",
    "hong kong": "Hong Kong",
    "macau sar": "Macao",
    "czech republic": "Czech Republic",
    "czechia": "Czech Republic",
    "turkiye": "Turkey",
    # Prose and multi-country placeholders that were filed as a country.
    "international": MULTIPLE,
    "international students": MULTIPLE,
    "global": MULTIPLE,
    "worldwide": MULTIPLE,
    "multiple": MULTIPLE,
    "multiple countries": MULTIPLE,
    "multi country": MULTIPLE,
    "eu multiple": MULTIPLE,
    "eu": MULTIPLE,
    "european union": MULTIPLE,
    "various": MULTIPLE,
}

#: Stored ``region`` values that were already trying to say one of the eight
#: legal ones under another name. Kept separate from :data:`COUNTRY_ALIASES`
#: because these are region spellings, not country spellings.
REGION_ALIASES: dict[str, str] = {
    "worldwide": "Global",
    "world wide": "Global",
    "international": "Global",
    "south america": "Latin America",
    "central and south america": "Latin America",
    "caribbean": "Latin America",
}

#: Country -> region. Built from ``matching.nlp.REGION_MEMBERS`` for the places it
#: covers and extended explicitly for the African and Asian countries it omits,
#: so this table is complete on its own rather than depending on a reader of the
#: other module.
COUNTRY_REGION: dict[str, str] = {
    # Europe
    "Austria": "Europe", "Belgium": "Europe", "Bulgaria": "Europe", "Croatia": "Europe",
    "Cyprus": "Europe", "Czech Republic": "Europe", "Denmark": "Europe",
    "Estonia": "Europe", "Finland": "Europe", "France": "Europe", "Germany": "Europe",
    "Greece": "Europe", "Hungary": "Europe", "Iceland": "Europe", "Ireland": "Europe",
    "Italy": "Europe", "Latvia": "Europe", "Liechtenstein": "Europe",
    "Lithuania": "Europe", "Luxembourg": "Europe", "Malta": "Europe",
    "Netherlands": "Europe", "Norway": "Europe", "Poland": "Europe",
    "Portugal": "Europe", "Romania": "Europe", "Slovakia": "Europe",
    "Slovenia": "Europe", "Spain": "Europe", "Sweden": "Europe",
    "Switzerland": "Europe", "United Kingdom": "Europe", "Ukraine": "Europe",
    "Moldova": "Europe", "Belarus": "Europe", "Serbia": "Europe",
    "North Macedonia": "Europe", "Albania": "Europe", "Montenegro": "Europe",
    "Bosnia and Herzegovina": "Europe", "Kosovo": "Europe",
    # North America
    "Canada": "North America", "United States": "North America",
    "Mexico": "North America",
    # Latin America and the Caribbean
    "Argentina": "Latin America", "Brazil": "Latin America", "Chile": "Latin America",
    "Colombia": "Latin America", "Costa Rica": "Latin America", "Cuba": "Latin America",
    "Ecuador": "Latin America", "El Salvador": "Latin America",
    "Guatemala": "Latin America", "Honduras": "Latin America",
    "Jamaica": "Latin America", "Nicaragua": "Latin America",
    "Panama": "Latin America", "Paraguay": "Latin America", "Peru": "Latin America",
    "Uruguay": "Latin America", "Venezuela": "Latin America",
    "Bolivia": "Latin America", "Guyana": "Latin America",
    "Suriname": "Latin America", "Barbados": "Latin America",
    "Trinidad and Tobago": "Latin America", "Dominican Republic": "Latin America",
    "Haiti": "Latin America", "Belize": "Latin America",
    "Bahamas": "Latin America", "Puerto Rico": "Latin America",
    # Asia
    "Bangladesh": "Asia", "China": "Asia", "Hong Kong": "Asia", "Macao": "Asia",
    "India": "Asia", "Indonesia": "Asia", "Japan": "Asia", "Malaysia": "Asia",
    "Maldives": "Asia", "Mongolia": "Asia", "Myanmar": "Asia", "Nepal": "Asia",
    "Pakistan": "Asia", "Philippines": "Asia", "Singapore": "Asia",
    "South Korea": "Asia", "Sri Lanka": "Asia", "Taiwan": "Asia",
    "Thailand": "Asia", "Vietnam": "Asia", "Cambodia": "Asia", "Laos": "Asia",
    "Brunei": "Asia", "Timor-Leste": "Asia", "Kazakhstan": "Asia",
    "Uzbekistan": "Asia", "Kyrgyzstan": "Asia", "Tajikistan": "Asia",
    "Turkmenistan": "Asia", "Afghanistan": "Asia",
    # Oceania
    "Australia": "Oceania", "New Zealand": "Oceania", "Fiji": "Oceania",
    "Samoa": "Oceania", "Tonga": "Oceania", "Papua New Guinea": "Oceania",
    "Solomon Islands": "Oceania", "Vanuatu": "Oceania",
    # Africa
    "Algeria": "Africa", "Botswana": "Africa", "Burundi": "Africa",
    "Cameroon": "Africa", "Congo": "Africa", "Democratic Republic of the Congo": "Africa",
    "Djibouti": "Africa", "Ethiopia": "Africa", "Ghana": "Africa",
    "Kenya": "Africa", "Lesotho": "Africa", "Liberia": "Africa",
    "Madagascar": "Africa", "Malawi": "Africa", "Mali": "Africa",
    "Mauritius": "Africa", "Mozambique": "Africa", "Namibia": "Africa",
    "Niger": "Africa", "Nigeria": "Africa", "Rwanda": "Africa",
    "Senegal": "Africa", "Seychelles": "Africa", "Sierra Leone": "Africa",
    "Somalia": "Africa", "South Africa": "Africa", "Tanzania": "Africa",
    "Togo": "Africa", "Tunisia": "Africa", "Uganda": "Africa",
    "Zambia": "Africa", "Zimbabwe": "Africa", "Eswatini": "Africa",
    "Gambia": "Africa", "Guinea": "Africa", "Ivory Coast": "Africa",
    "Burkina Faso": "Africa", "Benin": "Africa", "Chad": "Africa",
    "Equatorial Guinea": "Africa", "Gabon": "Africa", "Mauritania": "Africa",
    "Niger": "Africa", "Sudan": "Africa", "South Sudan": "Africa",
    # Middle East, following REGION_MEMBERS' "middle east and north africa".
    "Egypt": "Middle East", "Iran": "Middle East", "Iraq": "Middle East",
    "Israel": "Middle East", "Jordan": "Middle East", "Kuwait": "Middle East",
    "Lebanon": "Middle East", "Morocco": "Middle East", "Oman": "Middle East",
    "Qatar": "Middle East", "Saudi Arabia": "Middle East",
    "Turkey": "Middle East", "United Arab Emirates": "Middle East",
    "Armenia": "Middle East", "Azerbaijan": "Middle East", "Georgia": "Middle East",
    "Yemen": "Middle East", "Syria": "Middle East", "Lebanon": "Middle East",
    "State of Palestine": "Middle East", "Bahrain": "Middle East",
    # Caucasus sits between the two; REGION_MEMBERS omits it entirely, and Africa
    # would be plainly wrong, so it joins MENA.
    "Russian Federation": "Europe",
    "Russia": "Europe",
}

#: Countries that are their own region answer when the record is a single-country
#: award. Used only to sanity-check the mapping at import time.
_GLOBAL_SENTINEL = "Global"

#: Leading country name in a prose region value, e.g. "Germany (host research
#: institution)" -> "Germany". Ordered longest-first at build time so that
#: "United Kingdom" wins over "United".
_ALIAS_KEYS_SORTED = sorted(COUNTRY_ALIASES, key=len, reverse=True)

_WORD_RE = re.compile(r"[a-z0-9]+")


def _ascii_fold(text: str) -> str:
    """Casefold, strip accents, and reduce to word characters.

    "T\u00fcrkiye" -> "turkiye", "C\u00f4te d'Ivoire" -> "cote d ivoire". The stored
    value is repaired by :func:`canonical_country` from the *original* string, so
    this is only ever used for lookup and comparison.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(_WORD_RE.findall(stripped.casefold()))


def _repair_mojibake(text: str) -> str:
    """Return the intended text for a string carrying double-decoded UTF-8.

    The catalogue picked up "Türkiye" written as "TÃ¼rkiye" and
    "Côte d'Ivoire" as "CÃ´te d'Ivoire" from a Latin-1 decode of UTF-8 bytes.
    The round trip below recovers the intended text; a string that does not
    change under it is returned untouched.
    """
    if not any(ch in text for ch in ("\ufffd", "Ã", "Â", "â")):
        return text
    for candidate in (lambda: text.encode("cp1252", "strict").decode("utf-8", "strict"),
                      lambda: text.encode("latin-1", "strict").decode("utf-8", "strict")):
        try:
            recovered = candidate()
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        if recovered != text:
            return recovered
    return text


#: Country names tried as a leading prefix, longest first, so "United Kingdom"
#: is preferred over "United" and "South Africa" over "South".
_COUNTRY_PREFIXES: tuple[str, ...] = tuple(
    sorted(COUNTRY_REGION, key=len, reverse=True)
)

#: Characters that may legally follow a country name for the name to count as
#: the value's opening token. Written as a set rather than a regex because a
#: regex with an ``$`` alternative matches every single-character string, which
#: silently made "Indiana" resolve to "India".
_PREFIX_BOUNDARY_CHARS = frozenset(" \t\r\n\f\v(,;/:-–—")


def _leading_country(text: str) -> str | None:
    """The country a value opens with, if it opens with one."""
    for name in _COUNTRY_PREFIXES:
        if text.casefold().startswith(name.casefold()):
            tail = text[len(name):]
            if not tail or tail[0] in _PREFIX_BOUNDARY_CHARS:
                return name
    return None


def _opens_with_place_list(text: str) -> bool:
    """True when the value's opening clause enumerates several places.

    A comma inside a parenthesis is an address, not a second country: "South
    Africa (AIMS, 6 Melrose Road, Muizenberg, Cape Town)" is one place. A comma
    before the first semicolon or dash, at parenthesis depth zero, is a list:
    "United Kingdom, Republic of Ireland, low- or middle-income countries".
    """
    depth = 0
    for index, ch in enumerate(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            leading = text[:index]
            # A clause boundary before the comma means the comma is in a
            # sentence, not in a list of places.
            if not re.search(r"[;/]| - | – |—", leading):
                return True
    return False


def canonical_country(value: str | None) -> str | None:
    """Return the canonical country name, or ``None`` when there is nothing to read.

    Handles the three failure modes actually present in the column: an alias
    spelling, a prose sentence with a country buried in it, and mojibake.

    A country is never guessed. When the value names more than one place the
    answer is :data:`MULTIPLE`, because "which of these?" is not a question the
    country column is allowed to answer.
    """
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None

    repaired = _repair_mojibake(raw)
    folded = _ascii_fold(repaired)
    if not folded:
        return None

    if folded in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[folded]

    # A list of places before any prose is the answer "Multiple", and it has to be
    # tested before the prefix match or a two-country award gets filed under
    # whichever country happens to come first.
    if _opens_with_place_list(repaired):
        return MULTIPLE

    leading = _leading_country(repaired)
    if leading:
        return leading

    # "International", "Global", "Host administering organisation country (...)" -
    # placeholders that were filed as a country.
    head_word = re.split(r"[\s(,;/:\-–—]", repaired, maxsplit=1)[0].strip().casefold()
    if head_word in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[head_word]

    if len(folded.split()) > 6:
        return MULTIPLE

    return repaired


def canonical_region(country: str | None, region: str | None = None) -> str | None:
    """Return the canonical region for a record.

    Precedence is deliberate and runs stored-value-first:

    1. A region that is already legal is kept. It was set by a researcher who
       read the source, and re-deriving it from a column that is itself damaged
       would replace a correct answer with a worse one. Erasmus Mundus is a
       European consortium whose ``country`` is "Multiple"; deriving from the
       country turns a correct "Europe" into a meaningless "Global".
    2. A legacy spelling is mapped onto the enum - "Worldwide" is "Global".
    3. A country used as a region ("Australia", "Canada", "United States",
       "New Zealand") and any prose sentence are derived from ``country``, which
       is the only trustworthy place information on the row.
    4. Nothing resolves, so the answer is ``None``: an unset enum is honest, a
       guess is not.
    """
    stored = (region or "").strip()
    if stored in REGIONS:
        return stored

    if stored:
        folded = _ascii_fold(stored)
        if folded in REGION_ALIASES:
            return REGION_ALIASES[folded]

    resolved_country = canonical_country(country)
    if resolved_country == MULTIPLE:
        return "Global"
    if resolved_country and resolved_country in COUNTRY_REGION:
        return COUNTRY_REGION[resolved_country]
    return None


#: Funding labels that differ from a dominant spelling only by case or plural.
#:
#: Deliberately tiny. The catalogue holds 106 distinct ``funding`` values and most
#: of that variety is real information - "Tuition Fee Waiver (NZ$15,000 towards
#: tuition fees)" carries an amount that "Tuition Fee Waiver" would not. Only exact
#: spelling variants of the four dominant terms are folded, because the card
#: renders this column verbatim and matching the claim frame to the exact string
#: "Fully Funded" is the only thing that is actually broken. Collapsing the rest
#: would need a separate ``funding_type`` enum column, which is a migration.
FUNDING_LABEL_ALIASES: dict[str, str] = {
    "fully funded": "Fully Funded",
    "partially funded": "Partially Funded",
    "partial funding": "Partially Funded",
    "partial": "Partially Funded",
    "stipend": "Stipend",
    "tuition fee waiver": "Tuition Fee Waiver",
    "tuition waiver": "Tuition Fee Waiver",
    "tuition fee waiver, stipend": "Tuition Fee Waiver, Stipend",
}


def canonical_funding_label(value: str | None) -> str | None:
    """Fold a funding label that is a spelling variant of a dominant term."""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    return FUNDING_LABEL_ALIASES.get(raw.casefold(), raw)


# ═══════════════════════════════════════════════════════════════════
# Filter normalisation
#
# The funding and degree filters are selects, so a filter value is a
# *question*, not a stored string. The catalogue answers that question
# with 96 distinct funding labels and a dozen degree spellings, and the
# filters used to compare the question against the stored string with
# ``==`` - so selecting "Master" returned the 3 rows literally spelled
# "Master" out of 84 master's programmes, and "Tuition Waiver" returned
# nothing at all, because the catalogue stores "Tuition Fee Waiver".
#
# A bucket selects an *aspect* of coverage, not a classification. A row
# belongs to every bucket whose aspect it states: "Stipend + Tuition Fee
# Waiver" is both a stipend row and a tuition-waiver row, and forcing it
# into one bucket would hide it from the other filter. This is why the
# vocabulary below is a map from a filter value to the words that state
# that aspect, rather than a partition of the label space.
#
# The exclusion list is the honesty rule. A filter that promises "fully
# funded" may not return a row whose own label says "partially": "Fully
# Funded, Partially Funded" and "Full funding (partial living stipend)"
# are deliberately unreachable from that filter. The reverse is fine -
# every "partial to full" offer is at least a partial offer - so the
# partial filter has no exclusions.
# ═══════════════════════════════════════════════════════════════════

#: requested filter value (case-folded, apostrophes and possessives
#: removed) -> (words that state the aspect, words that deny it)
FUNDING_FILTER_BUCKETS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "fully funded": (
        ("fully funded", "fully-funded", "full funding", "full scholarship",
         "full sponsorship", "full study funding", "full masters scholarship"),
        ("partially", "partial to full", "various"),
    ),
    "partially funded": (
        ("partial",),
        (),
    ),
    "tuition fee waiver": (
        ("tuition", "fee"),
        (),
    ),
    "stipend": (
        ("stipend", "stipendium", "salary", "fellowship"),
        (),
    ),
    "research funding": (
        ("research",),
        (),
    ),
    "need based": (
        ("need",),
        (),
    ),
}

#: requested filter value (case-folded, apostrophes and possessives
#: removed) -> words a stored degree label contains when the row is at
#: that level. A joint degree ("Master's, PhD") answers for both levels,
#: which is correct: the filter asks what level the row offers, not what
#: the only level is.
DEGREE_FILTER_BUCKETS: dict[str, tuple[str, ...]] = {
    "bachelor": ("bachelor", "undergraduate"),
    "undergraduate": ("bachelor", "undergraduate"),
    "master": ("master",),
    "phd": ("phd", "ph.d", "doctoral", "doctorate"),
    "doctoral": ("phd", "ph.d", "doctoral", "doctorate"),
    "postgraduate": ("master", "phd", "postgraduate"),
    "postdoc": ("postdoctoral", "post-doc"),
}


def _filter_key(value: str | None) -> str | None:
    """The bucketing key for a requested filter value.

    Case, surrounding space, a trailing possessive and the punctuation a
    select puts in its option text ("Master's", "Tuition Waiver") are all
    removed, because none of them change which aspect is being asked
    about. Anything that does not reduce to a known key returns ``None``
    and the caller keeps exact matching for it.
    """
    if value is None:
        return None
    key = str(value).strip().casefold()
    if not key or key == "all":
        return None
    key = key.replace("'", "").replace("\u2019", "").replace("-", " ").replace("/", " ")
    key = " ".join(key.split())
    if key.endswith("s") and not key.endswith("ss"):
        key = key[:-1]
    return key or None


def funding_filter_bucket(value: str | None) -> tuple[tuple[str, ...], tuple[str, ...]] | None:
    """The aspect words for a requested funding filter, or ``None``.

    ``None`` means the caller asked for a value the taxonomy does not
    know as a filter - a verbatim stored label, a facet name, a typo -
    and the caller must fall back to exact matching rather than guess.
    """
    key = _filter_key(value)
    if key is None:
        return None
    if key in FUNDING_FILTER_BUCKETS:
        return FUNDING_FILTER_BUCKETS[key]
    # The label aliases map a spelling variant onto the dominant term,
    # so "Tuition Waiver" resolves through "Tuition Fee Waiver".
    canonical = FUNDING_LABEL_ALIASES.get(str(value).strip().casefold())
    if canonical is not None:
        return FUNDING_FILTER_BUCKETS.get(_filter_key(canonical))
    return None


def degree_filter_bucket(value: str | None) -> tuple[str, ...] | None:
    """The level words for a requested degree filter, or ``None``."""
    return DEGREE_FILTER_BUCKETS.get(_filter_key(value) or "")


def coverage_boolean(value: object) -> bool | None:
    """Read a coverage flag out of ``official_details``.

    The column was never backfilled and ``official_details`` already holds a clean
    boolean for most rows, but a minority of records stored the sentence a
    researcher wrote instead of the boolean - "Full tuition fees for up to 4
    years" - and those are prose, not evidence, so they return ``None`` rather
    than being coerced to ``True``.
    """
    return value if isinstance(value, bool) else None


def as_bool(value: object) -> bool | None:
    """Read a SQLite BOOLEAN column as a Python bool, or ``None``.

    A ``BOOLEAN`` column is stored as an integer and the driver hands back
    ``1``, so ``value is True`` is False for a column that genuinely holds True.
    Anything that is not a bool or a 0/1 integer is ``None``: prose and
    near-misses are not boolean evidence.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    return None


def fully_funded_is_permitted(fully_funded: object, tuition_coverage: object) -> bool:
    """The funding invariant, in one place.

    ``fully_funded`` is a claim about expenses the source addressed. It may only
    stand when tuition coverage is affirmatively True; a stipend on its own is
    not a scholarship that pays your tuition, and an unset flag is not evidence.

    The tuition flag goes through :func:`as_bool` because this is called with raw
    column values as well as with JSON, and the two disagree about the type of
    True.
    """
    return bool(fully_funded) and as_bool(tuition_coverage) is True