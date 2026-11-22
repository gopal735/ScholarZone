"""Canonical supported country registry for Mentor discovery."""

from __future__ import annotations

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
