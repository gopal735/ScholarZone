/**
 * Frontend Country Taxonomy
 *
 * Mirrors backend/app/services/taxonomy.py canonical_country logic.
 * This ensures the frontend and backend agree on country canonicalization
 * without requiring a shared package or build-time generation.
 */

const COUNTRY_ALIASES = {
  // The two splits that actually cost coverage.
  'usa': 'United States',
  'us': 'United States',
  'u s': 'United States',
  'u s a': 'United States',
  'united states of america': 'United States',
  'america': 'United States',
  'uk': 'United Kingdom',
  'u k': 'United Kingdom',
  'great britain': 'United Kingdom',
  'britain': 'United Kingdom',
  'england': 'United Kingdom',
  'scotland': 'United Kingdom',
  'wales': 'United Kingdom',
  'northern ireland': 'United Kingdom',
  // Long and short official forms.
  'brunei darussalam': 'Brunei',
  'republic of korea': 'South Korea',
  'korea': 'South Korea',
  'russian federation': 'Russia',
  'viet nam': 'Vietnam',
  'hong kong sar': 'Hong Kong',
  'hong kong': 'Hong Kong',
  'macau sar': 'Macao',
  'czech republic': 'Czech Republic',
  'czechia': 'Czech Republic',
  'turkiye': 'Turkey',
  // Prose and multi-country placeholders that were filed as a country.
  'international': 'Multiple',
  'international students': 'Multiple',
  'global': 'Multiple',
  'worldwide': 'Multiple',
  'multiple': 'Multiple',
  'multiple countries': 'Multiple',
  'multi country': 'Multiple',
  'eu multiple': 'Multiple',
  'eu': 'Multiple',
  'european union': 'Multiple',
  'various': 'Multiple',
};

const REGIONS = new Set([
  'Europe',
  'North America',
  'Latin America',
  'Asia',
  'Oceania',
  'Africa',
  'Middle East',
  'Global',
]);

const MULTIPLE = 'Multiple';

const _WORD_RE = /[a-z0-9]+/g;

function _asciiFold(text) {
  // Casefold, strip accents, and reduce to word characters.
  // Simple version without full Unicode normalization for frontend.
  return text
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '') // Remove combining diacritics
    .match(_WORD_RE)
    ?.join(' ') || '';
}

function _repairMojibake(text) {
  // Return the intended text for a string carrying double-decoded UTF-8.
  if (!/[ÃÂâ\uFFFD]/.test(text)) return text;
  for (const candidate of [
    () => {
      try { return new TextDecoder('utf-8').decode(new TextEncoder().encode(text)); } catch { return null; }
    },
    () => {
      try { return decodeURIComponent(escape(text)); } catch { return null; }
    },
  ]) {
    try {
      const recovered = candidate();
      if (recovered && recovered !== text) return recovered;
    } catch {
      // Ignore recovery failures
    }
  }
  return text;
}

const _COUNTRY_PREFIXES = [
  'United States', 'United Kingdom', 'South Korea', 'South Africa',
  'Czech Republic', 'United Arab Emirates', 'Saudi Arabia', 'Sri Lanka',
  'Papua New Guinea', 'Solomon Islands', 'New Zealand', 'Costa Rica',
  'El Salvador', 'Equatorial Guinea', 'Ivory Coast', 'Burkina Faso',
  'Bosnia and Herzegovina', 'North Macedonia', 'Trinidad and Tobago',
  'Dominican Republic', 'Hong Kong', 'Puerto Rico', 'Viet Nam',
  'Turkey', 'Russia', 'Vietnam', 'Brazil', 'Canada', 'Mexico', 'India',
  'China', 'Japan', 'Germany', 'France', 'Italy', 'Spain', 'Australia',
  'Poland', 'Netherlands', 'Turkey', 'Iran', 'Turkey', 'Turkey',
].sort((a, b) => b.length - a.length);

// Deduplicate
const _UNIQUE_PREFIXES = [...new Set(_COUNTRY_PREFIXES)];

const _PREFIX_BOUNDARY_CHARS = new Set(' \t\r\n\f\v(,;/:-\u2013\u2014'.split(''));

function _leadingCountry(text) {
  const lower = text.toLowerCase();
  for (const name of _UNIQUE_PREFIXES) {
    if (lower.startsWith(name.toLowerCase())) {
      const tail = text.slice(name.length);
      if (!tail || _PREFIX_BOUNDARY_CHARS.has(tail[0])) {
        return name;
      }
    }
  }
  return null;
}

function _opensWithPlaceList(text) {
  let depth = 0;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (ch === '(') depth++;
    else if (ch === ')') depth = Math.max(0, depth - 1);
    else if (ch === ',' && depth === 0) {
      const leading = text.slice(0, i);
      if (!/[;/]/.test(leading) && !/ - | \u2013 | \u2014 /.test(leading)) {
        return true;
      }
    }
  }
  return false;
}

/**
 * Return the canonical country name, or null when there is nothing to read.
 * Mirrors backend canonical_country() exactly.
 */
export function canonicalCountry(value) {
  if (value == null) return null;
  const raw = String(value).trim();
  if (!raw) return null;

  const repaired = _repairMojibake(raw);
  const folded = _asciiFold(repaired);
  if (!folded) return null;

  if (COUNTRY_ALIASES[folded]) {
    return COUNTRY_ALIASES[folded];
  }

  // A list of places before any prose is the answer "Multiple"
  if (_opensWithPlaceList(repaired)) {
    return MULTIPLE;
  }

  const leading = _leadingCountry(repaired);
  if (leading) {
    return leading;
  }

  // "International", "Global", "Host administering organisation country (...)" -
  // placeholders that were filed as a country.
  const headWord = repaired.split(/[\s(,;/:\-–—]/)[0].trim().toLowerCase();
  if (COUNTRY_ALIASES[headWord]) {
    return COUNTRY_ALIASES[headWord];
  }

  if (folded.split(/\s+/).length > 6) {
    return MULTIPLE;
  }

  return repaired;
}

/**
 * Check if a canonical country value represents a real single country.
 * Excludes MULTIPLE, GLOBAL, and region values.
 */
export function isRealCountry(canonical) {
  if (!canonical) return false;
  if (canonical === MULTIPLE) return false;
  if (REGIONS.has(canonical)) return false;
  return true;
}

/**
 * Normalise a funding label that is a spelling variant of a dominant term.
 * Mirrors backend canonical_funding_label().
 */
export function canonicalFundingLabel(value) {
  if (value == null) return null;
  const raw = String(value).trim();
  if (!raw) return null;

  const FUNDING_LABEL_ALIASES = {
    'fully funded': 'Fully Funded',
    'partially funded': 'Partially Funded',
    'partial funding': 'Partially Funded',
    'partial': 'Partially Funded',
    'stipend': 'Stipend',
    'tuition fee waiver': 'Tuition Fee Waiver',
    'tuition waiver': 'Tuition Fee Waiver',
    'tuition fee waiver, stipend': 'Tuition Fee Waiver, Stipend',
  };

  return FUNDING_LABEL_ALIASES[raw.toLowerCase()] || raw;
}