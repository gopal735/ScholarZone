"""Canonical supported country registry for Mentor discovery."""

from __future__ import annotations

import unicodedata

# Canonical country names present in the catalogue (plus common variants).
CANONICAL_COUNTRIES: frozenset[str] = frozenset(
    {
        "Algeria","Argentina","Australia","Austria","Azerbaijan","Bangladesh","Barbados",
        "Belgium","Brazil","Brunei","Canada","Chile","China","Colombia","Czech Republic",
        "Denmark","Egypt","Fiji","Finland","France","Germany","Ghana","Hong Kong",
        "Hungary","India","Ireland","Italy","Japan","Malaysia","Mauritius","Mexico",
        "Morocco","Netherlands","New Zealand","Nigeria","Pakistan","Philippines",
        "Poland","Portugal","Qatar","Serbia","Singapore","South Africa","South Korea",
        "Spain","Sri Lanka","Sweden","Switzerland","Taiwan","Thailand","Turkey",
        "United Kingdom","United States",
    }
)

# Alias -> canonical
COUNTRY_ALIASES: dict[str, str] = {
    "uk": "United Kingdom",
    "u.k.": "United Kingdom",
    "britain": "United Kingdom",
    "great britain": "United Kingdom",
    "england": "United Kingdom",
    "usa": "United States",
    "us": "United States",
    "america": "United States",
    "united states of america": "United States",
    "deutschland": "Germany",
    "jarmani": "Germany",
    "জার্মানি": "Germany",
    "france": "France",
    "ফ্রান্স": "France",
    "italy": "Italy",
    "ইতালি": "Italy",
    "spain": "Spain",
    "স্পেন": "Spain",
    "netherlands": "Netherlands",
    "holland": "Netherlands",
    "switzerland": "Switzerland",
    "সুইজারল্যান্ড": "Switzerland",
    "sweden": "Sweden",
    "norway": "Norway",
    "denmark": "Denmark",
    "finland": "Finland",
    "austria": "Austria",
    "belgium": "Belgium",
    "portugal": "Portugal",
    "poland": "Poland",
    "ireland": "Ireland",
    "canada": "Canada",
    "australia": "Australia",
    "japan": "Japan",
    "south korea": "South Korea",
    "korea": "South Korea",
    "china": "China",
    "india": "India",
    "singapore": "Singapore",
    "taiwan": "Taiwan",
    "new zealand": "New Zealand",
    "turkey": "Turkey",
    "hong kong": "Hong Kong",
    "malaysia": "Malaysia",
    "thailand": "Thailand",
    "qatar": "Qatar",
    "egypt": "Egypt",
    "morocco": "Morocco",
    "mexico": "Mexico",
    "brazil": "Brazil",
    "argentina": "Argentina",
    "chile": "Chile",
    "colombia": "Colombia",
    "south africa": "South Africa",
    "nigeria": "Nigeria",
    "ghana": "Ghana",
    "kenya": "Kenya",
    "pakistan": "Pakistan",
    "bangladesh": "Bangladesh",
    "sri lanka": "Sri Lanka",
    "philippines": "Philippines",
    "indonesia": "Indonesia",
    "vietnam": "Vietnam",
}


def resolve_country(text: str):
    """Return canonical country name or None. None means not resolved."""
    if not isinstance(text, str):
        return None
    low = text.strip().lower()
    if low in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[low]
    # direct canonical match (case-insensitive)
    for c in CANONICAL_COUNTRIES:
        if c.lower() == low:
            return c
    # substring match in a longer phrase
    for alias, canon in COUNTRY_ALIASES.items():
        if alias in low.split() or low == alias:
            # only if whole-word
            pass
    # try token-level
    tokens = low.replace(",", " ").split()
    for t in tokens:
        if t in COUNTRY_ALIASES:
            return COUNTRY_ALIASES[t]
        for c in CANONICAL_COUNTRIES:
            if c.lower() == t:
                return c
    # multi-word aliases
    for alias, canon in sorted(COUNTRY_ALIASES.items(), key=lambda x: -len(x[0])):
        if alias in low:
            # ensure not partial word? allow phrase
            return canon
    return None


def extract_country_from_message(message: str):
    """Scan message for a supported country. Returns canonical name or None."""
    if not isinstance(message, str):
        return None
    low = message.lower()
    # try multi-word aliases first
    for alias, canon in sorted(COUNTRY_ALIASES.items(), key=lambda x: -len(x[0])):
        # word boundary-ish
        if alias in low:
            return canon
    # canonical direct
    for c in CANONICAL_COUNTRIES:
        if c.lower() in low:
            return c
    return None


# Recognised world countries that may not yet have catalogue coverage.
RECOGNIZED_COUNTRIES: frozenset[str] = frozenset(
    {
        "Afghanistan","Albania","Algeria","Andorra","Angola","Antigua and Barbuda","Argentina",
        "Armenia","Australia","Austria","Azerbaijan","Bahamas","Bahrain","Bangladesh","Barbados",
        "Belarus","Belgium","Belize","Benin","Bhutan","Bolivia","Bosnia and Herzegovina",
        "Botswana","Brazil","Brunei","Bulgaria","Burkina Faso","Burundi","Cabo Verde","Cambodia",
        "Cameroon","Canada","Central African Republic","Chad","Chile","China","Colombia",
        "Comoros","Congo","Costa Rica","Cote d'Ivoire","Croatia","Cuba","Cyprus","Czech Republic",
        "Democratic Republic of the Congo","Denmark","Djibouti","Dominica","Dominican Republic",
        "Ecuador","Egypt","El Salvador","Equatorial Guinea","Eritrea","Estonia","Eswatini",
        "Ethiopia","Fiji","Finland","France","Gabon","Gambia","Georgia","Germany","Ghana",
        "Greece","Grenada","Guatemala","Guinea","Guinea-Bissau","Guyana","Haiti","Honduras",
        "Hungary","Iceland","India","Indonesia","Iran","Iraq","Ireland","Israel","Italy",
        "Jamaica","Japan","Jordan","Kazakhstan","Kenya","Kiribati","Kuwait","Kyrgyzstan","Laos",
        "Latvia","Lebanon","Lesotho","Liberia","Libya","Liechtenstein","Lithuania","Luxembourg",
        "Madagascar","Malawi","Malaysia","Maldives","Mali","Malta","Marshall Islands","Mauritania",
        "Mauritius","Mexico","Micronesia","Moldova","Monaco","Mongolia","Montenegro","Morocco",
        "Mozambique","Myanmar","Namibia","Nauru","Nepal","Netherlands","New Zealand","Nicaragua",
        "Niger","Nigeria","North Korea","North Macedonia","Norway","Oman","Pakistan","Palau",
        "Palestine","Panama","Papua New Guinea","Paraguay","Peru","Philippines","Poland",
        "Portugal","Qatar","Romania","Russia","Rwanda","Saint Kitts and Nevis","Saint Lucia",
        "Saint Vincent and the Grenadines","Samoa","San Marino","Sao Tome and Principe",
        "Saudi Arabia","Senegal","Serbia","Seychelles","Sierra Leone","Singapore","Slovakia",
        "Slovenia","Solomon Islands","Somalia","South Africa","South Korea","South Sudan",
        "Spain","Sri Lanka","Sudan","Suriname","Sweden","Switzerland","Syria","Taiwan",
        "Tajikistan","Tanzania","Thailand","Timor-Leste","Togo","Tonga","Trinidad and Tobago",
        "Tunisia","Turkey","Turkmenistan","Tuvalu","Uganda","Ukraine","United Arab Emirates",
        "United Kingdom","United States","Uruguay","Uzbekistan","Vanuatu","Vatican City",
        "Venezuela","Vietnam","Yemen","Zambia","Zimbabwe",
    }
)


def _all_country_entries():
    entries = []
    # canonical supported
    for c in CANONICAL_COUNTRIES:
        entries.append((c.lower(), c, True))
    # aliases
    for alias, canon in COUNTRY_ALIASES.items():
        entries.append((alias.lower(), canon, canon in CANONICAL_COUNTRIES))
    # recognized unsupported
    for c in RECOGNIZED_COUNTRIES:
        if c not in CANONICAL_COUNTRIES:
            entries.append((c.lower(), c, False))
    # sort by length desc
    entries.sort(key=lambda e: -len(e[0]))
    return entries


_COUNTRY_ENTRIES = _all_country_entries()


def _boundary_match(text: str, alias: str, pos: int) -> bool:
    n = len(text)
    end = pos + len(alias)
    if pos > 0:
        prev = text[pos-1]
        if prev.isalnum() or prev == "_":
            return False
    if end < n:
        nxt = text[end]
        if nxt.isalnum() or nxt == "_":
            return False
    return True


def _find_country_matches(text: str):
    if not isinstance(text, str):
        return []
    norm = unicodedata.normalize("NFC", text).lower() if False else None
    import unicodedata
    low = unicodedata.normalize("NFC", text).lower()
    matches = []
    pos = 0
    n = len(low)
    while pos < n:
        found = False
        for alias, canon, supported in _COUNTRY_ENTRIES:
            if low.startswith(alias, pos) and _boundary_match(low, alias, pos):
                matches.append((pos, pos+len(alias), canon, supported))
                pos = pos + len(alias)
                found = True
                break
        if not found:
            pos += 1
    return matches


def resolve_country(text: str):
    """Return canonical country name (supported) or None. None means not resolved."""
    res = resolve_country_resolution(text)
    if res["status"] == "RESOLVED_SUPPORTED":
        return res["country"]
    return None


def resolve_country_resolution(text: str) -> dict:
    """Return a resolution dict with status."""
    if not isinstance(text, str) or not text.strip():
        return {"country": None, "status": "NOT_PROVIDED", "explicit": False, "canonical_id": None, "candidates": []}
    matches = _find_country_matches(text)
    distinct = []
    seen = set()
    for m in matches:
        if m[2] not in seen:
            seen.add(m[2])
            distinct.append(m)
    if not distinct:
        return {"country": None, "status": "NOT_PROVIDED", "explicit": False, "canonical_id": None, "candidates": []}
    if len(distinct) > 1:
        return {"country": distinct[0][2], "status": "AMBIGUOUS_FILTER", "explicit": True, "canonical_id": None, "candidates": [d[2] for d in distinct]}
    canon = distinct[0][2]
    supported = distinct[0][3]
    if supported:
        return {"country": canon, "status": "RESOLVED_SUPPORTED", "explicit": True, "canonical_id": canon, "candidates": [canon]}
    return {"country": canon, "status": "RESOLVED_NO_CATALOGUE_DATA", "explicit": True, "canonical_id": canon, "candidates": [canon]}


def extract_country_from_message(message: str):
    """Scan message for a supported country. Returns canonical name or None."""
    res = resolve_country_resolution(message)
    if res["status"] == "RESOLVED_SUPPORTED":
        return res["country"]
    # If single recognized-but-unsupported, return None (discovery handles status separately)
    return None
