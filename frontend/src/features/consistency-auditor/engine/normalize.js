/**
 * Application Consistency Auditor V1 — text normalisation.
 *
 * Every function here returns a NEW value. Nothing in this module mutates
 * its input, and nothing in this module reads the DOM, the network, or
 * storage. The engine is the only place these are called, so the guarantee
 * "the user's document is never rewritten" is enforced at the point where
 * the text is first touched, not at the point where it is displayed.
 *
 * Three things are normalised, and only these three:
 *   numerals (Bengali digits and digit forms to Western digits),
 *   dates (to {year, month|null, day|null, precision, ongoing}),
 *   names (case, spacing, punctuation, common abbreviations).
 *
 * A normalised value is only ever used for COMPARISON. Findings carry
 * character offsets into the ORIGINAL string so excerpts are displayed
 * exactly as the user wrote them.
 */

/**
 * @typedef {Object} ParsedDate
 * @property {number|null} year
 * @property {number|null} month 1-12, or null when not stated
 * @property {number|null} day 1-31, or null when not stated
 * @property {'year'|'month'|'day'} precision
 * @property {boolean} ongoing true for present/current/ongoing/since
 * @property {number} start index in the original text
 * @property {number} end index in the original text
 * @property {string} raw the text exactly as written
 */

/** Bengali digits ০-৯ mapped to ০-9. */
const BENGALI_DIGITS = '০১২৩৪৫৬৭৮৯';

/**
 * @param {string} value
 * @returns {string}
 */
export function toWesternDigits(value) {
  if (typeof value !== 'string' || value === '') return '';
  let out = '';
  for (const character of value) {
    const index = BENGALI_DIGITS.indexOf(character);
    out += index === -1 ? character : String(index);
  }
  return out;
}

/** English month names and their common three-letter forms. */
const MONTHS = {
  jan: 1, january: 1,
  feb: 2, february: 2,
  mar: 3, march: 3,
  apr: 4, april: 4,
  may: 5,
  jun: 6, june: 6,
  jul: 7, july: 7,
  aug: 8, august: 8,
  sep: 9, sept: 9, september: 9,
  oct: 10, october: 10,
  nov: 11, november: 11,
  dec: 12, december: 12,
};

/** Bengali Gregorian month names. Bengali calendar months are absent on purpose. */
const BENGALI_MONTHS = {
  জানুয়ারি: 1, ফেব্রুয়ারি: 2, মার্চ: 3, এপ্রিল: 4, মে: 5, জুন: 6,
  জুলাই: 7, আগস্ট: 8, সেপ্টেম্বর: 9, অক্টোবর: 10, নভেম্বর: 11, ডিসেম্বর: 12,
};

/**
 * Bengali calendar months. Correctly NOT converted to Gregorian: the
 * mapping differs by year (the Bengali year starts in mid-April), so
 * converting one would require knowing which Gregorian year the document
 * means. The engine therefore treats a Bengali month name followed by a
 * year as an unsupported format and reports "needs human review".
 */
export const BENGALI_CALENDAR_MONTHS = [
  'বৈশাখ', 'জ্যৈষ্ঠ', 'আষাঢ়', 'শ্রাবণ', 'ভাদ্র', 'আশ্বিন',
  'কার্তিক', 'অগ্রহায়ণ', 'পৌষ', 'মাঘ', 'ফাল্গুন', 'চৈত্র',
];

/**
 * Normalise a string for COMPARISON only: fold case, collapse whitespace,
 * drop punctuation. The input is never modified.
 *
 * @param {string} value
 * @returns {string}
 */
export function normaliseForComparison(value) {
  if (typeof value !== 'string') return '';
  return toWesternDigits(value)
    .toLowerCase()
    .replace(/[\s\u00a0]+/g, ' ')
    .replace(/[.,;:!?"'`()[\]{}]/g, '')
    .replace(/\s*[-–—/]\s*/g, '-')
    .trim();
}

/**
 * The conservative entity-name normalisation: the comparison normalisation
 * plus a small, explicit table of abbreviations that mean the same thing
 * ("univ." -> "university", "b.sc." -> "bsc"). Deliberately small: a large
 * table would merge names that are genuinely different, and a false merge
 * is worse than a missed one in this feature.
 *
 * @param {string} value
 * @returns {string}
 */
export function normaliseEntityName(value) {
  let text = normaliseForComparison(value);
  const abbreviations = [
    [/\buniv\b/g, 'university'],
    [/\buni\b/g, 'university'],
    [/\binst\b/g, 'institute'],
    [/\bdept\b/g, 'department'],
    [/\bengg\b/g, 'engineering'],
    [/\bb sc\b/g, 'bsc'],
    [/\bb s c\b/g, 'bsc'],
    [/\bb a\b/g, 'ba'],
    [/\bm s c\b/g, 'msc'],
    [/\bm sc\b/g, 'msc'],
    [/\bph d\b/g, 'phd'],
    [/\bmax\b/g, 'maximum'],
    [/\bmin\b/g, 'minimum'],
  ];
  for (const [pattern, replacement] of abbreviations) {
    text = text.replace(pattern, replacement);
  }
  return text.replace(/\s+/g, ' ').trim();
}

/**
 * Conservative string similarity (normalised Levenshtein). Used with the
 * thresholds documented in engine/rules/entities.js.
 *
 * @param {string} left
 * @param {string} right
 * @returns {number} 0..1
 */
export function similarity(left, right) {
  const a = normaliseEntityName(left);
  const b = normaliseEntityName(right);
  if (a === '' && b === '') return 1;
  if (a === '' || b === '') return 0;
  if (a === b) return 1;
  const distance = levenshtein(a, b);
  const longest = Math.max(a.length, b.length);
  return 1 - distance / longest;
}

/**
 * Iterative Levenshtein with two rows: O(n) memory and no recursion, so a
 * long line cannot exhaust the stack. The strings are compared after
 * normalisation, which caps their meaningful length.
 *
 * @param {string} a
 * @param {string} b
 * @returns {number}
 */
function levenshtein(a, b) {
  if (a === b) return 0;
  if (a.length === 0) return b.length;
  if (b.length === 0) return a.length;
  let previous = new Array(b.length + 1);
  let current = new Array(b.length + 1);
  for (let j = 0; j <= b.length; j += 1) previous[j] = j;
  for (let i = 1; i <= a.length; i += 1) {
    current[0] = i;
    for (let j = 1; j <= b.length; j += 1) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      current[j] = Math.min(
        previous[j] + 1,
        current[j - 1] + 1,
        previous[j - 1] + cost,
      );
    }
    [previous, current] = [current, previous];
  }
  return previous[b.length];
}

/**
 * Date tokens, in the order they are tried. All are anchored, linear
 * patterns (no nested quantifiers, no backtracking traps): each token runs
 * at most once over the text with a single global regex, and no pattern
 * contains a quantifier inside a quantified group.
 */
const DATE_TOKEN_PATTERNS = [
  // "2023-01-15" / "2023/01/15"
  {
    kind: 'day',
    re: /\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b/g,
    build: (m, offset) => ({
      year: Number(m[1]), month: Number(m[2]), day: Number(m[3]),
      precision: 'day', ongoing: false, start: offset, end: offset + m[0].length, raw: m[0],
    }),
  },
  // "15 January 2023" / "January 15, 2023"
  {
    kind: 'day',
    re: /\b(\d{1,2})\s+([A-Za-z]{3,9})\.?\s+(\d{4})\b/g,
    build: (m, offset) => makeDayFromMonthName(m[2], Number(m[1]), Number(m[3]), m[0], offset),
  },
  {
    kind: 'day',
    re: /\b([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})\b/g,
    build: (m, offset) => makeDayFromMonthName(m[1], Number(m[2]), Number(m[3]), m[0], offset),
  },
  // Bengali: "১৫ জানুয়ারি ২০২৩"
  {
    kind: 'day',
    re: /([০-৯]{1,2})\s+(জানুয়ারি|ফেব্রুয়ারি|মার্চ|এপ্রিল|মে|জুন|জুলাই|আগস্ট|সেপ্টেম্বর|অক্টোবর|নভেম্বর|ডিসেম্বর)\s+([০-৯]{4})/g,
    build: (m, offset) => makeDayFromBengali(m[2], Number(toWesternDigits(m[1])), Number(toWesternDigits(m[3])), m[0], offset),
  },
  // "Jan 2023", "January 2023", "Sept 2022". The word must be an actual
  // month name: "completed 2021" is a year, not a month, and the lookup
  // returning null must reject the token rather than emit a month-precision
  // date whose month nobody stated.
  {
    kind: 'month',
    re: /\b([A-Za-z]{3,9})\.?\s+(\d{4})(?!\d)/g,
    build: (m, offset) => makeMonthFromName(m[1], Number(m[2]), m[0], offset, true),
  },
  // Bengali: "জানুয়ারি ২০২৩"
  {
    kind: 'month',
    re: /(জানুয়ারি|ফেব্রুয়ারি|মার্চ|এপ্রিল|মে|জুন|জুলাই|আগস্ট|সেপ্টেম্বর|অক্টোবর|নভেম্বর|ডিসেম্বর)\s+([০-৯]{4})/g,
    build: (m, offset) => ({
      year: Number(toWesternDigits(m[2])), month: BENGALI_MONTHS[m[1]], day: null,
      precision: 'month', ongoing: false, start: offset, end: offset + m[0].length, raw: m[0],
    }),
  },
  // "01/2023", "2023-01", "2023/01". Both parts are digits, and neither
  // month nor day carries a trailing period: "completed 2021." must read as
  // a year, not as 20/21.
  {
    kind: 'month',
    re: /\b(\d{1,2})[/](\d{4})(?!\d)/g,
    build: (m, offset) => ({
      year: Number(m[2]), month: Number(m[1]), day: null,
      precision: 'month', ongoing: false, start: offset, end: offset + m[0].length, raw: m[0],
    }),
  },
  {
    kind: 'month',
    re: /\b(\d{4})[-/](\d{1,2})(?!\d)(?!\.\d)/g,
    build: (m, offset) => ({
      year: Number(m[1]), month: Number(m[2]), day: null,
      precision: 'month', ongoing: false, start: offset, end: offset + m[0].length, raw: m[0],
    }),
  },
  // A bare year, not consumed by a longer token above.
  {
    kind: 'year',
    re: /\b(\d{4})\b/g,
    build: (m, offset) => ({
      year: Number(m[1]), month: null, day: null,
      precision: 'year', ongoing: false, start: offset, end: offset + m[0].length, raw: m[0],
    }),
  },
  // Bengali digits as a bare year: "২০২৩" — but NOT where those digits are
  // the year of a Bengali calendar month, which the unsupported pass must
  // own. The calendar check runs first in findDates() and claims those
  // characters, so this pattern never sees them.
  {
    kind: 'year',
    re: /([০-৯]{4})/g,
    build: (m, offset) => ({
      year: Number(toWesternDigits(m[1])), month: null, day: null,
      precision: 'year', ongoing: false, start: offset, end: offset + m[0].length, raw: m[0],
    }),
  },
  // Ongoing markers. No leading \b: the marker usually follows a hyphen or
  // an en dash ("2021 - Present"), and a word boundary does not match
  // between '-' and 'P'.
  {
    kind: 'ongoing',
    re: /(?<![A-Za-z])(present|current|currently|ongoing|now)(?![A-Za-z])|বর্তমান/gi,
    build: (m, offset) => ({
      year: null, month: null, day: null,
      precision: 'year', ongoing: true, start: offset, end: offset + m[0].length, raw: m[0],
    }),
  },
  // "since 2022" / "since January 2023".
  {
    kind: 'since',
    re: /\bsince\s+(?:(present|current|currently|ongoing|now)\b|(\d{4})\b|([A-Za-z]{3,9})\.?\s+(\d{4})\b)/gi,
    build: (m, offset) => {
      if (m[1]) {
        return { year: null, month: null, day: null, precision: 'year', ongoing: true, start: offset, end: offset + m[0].length, raw: m[0] };
      }
      if (m[2]) {
        return { year: Number(m[2]), month: null, day: null, precision: 'year', ongoing: true, start: offset, end: offset + m[0].length, raw: m[0] };
      }
      return { year: Number(m[4]), month: MONTHS[m[3].toLowerCase()] ?? null, day: null, precision: 'month', ongoing: true, start: offset, end: offset + m[0].length, raw: m[0] };
    },
  },
];

/** Bengali calendar months followed by a year: flagged, never converted. */
const BENGALI_CALENDAR_RE = new RegExp(
  `(?:${BENGALI_CALENDAR_MONTHS.join('|')})\\s*([০-৯]{4}|\\d{4})`,
  'g',
);

/**
 * Extract every recognised date token from a text, in document order.
 *
 * Overlaps are resolved by the earlier (longer/more specific) pattern: a
 * token already consumed by a more specific pattern is not re-matched by a
 * general one, so "January 2023" is one month token and not a name token
 * plus a year token.
 *
 * @param {string} text
 * @returns {{dates: ParsedDate[], unsupported: Array<{start:number,end:number,raw:string,reason:string}>}}
 */
export function findDates(text) {
  const dates = [];
  const unsupported = [];
  if (typeof text !== 'string' || text === '') return { dates, unsupported };

  const claimed = new Array(text.length).fill(false);

  // The Bengali calendar pass runs FIRST, before any date token, so its
  // digits are claimed before the bare-year patterns can read them as a
  // Gregorian year. A Bengali year differs from the Gregorian one by 593
  // years, so getting this order wrong turns "বৈশাখ ১৪৩২" into a 1432
  // graduation date.
  bengaliCalendarPass(text, claimed, unsupported);

  const claim = (start, end) => {
    for (let i = start; i < end && i < claimed.length; i += 1) {
      if (claimed[i]) return false;
    }
    for (let i = start; i < end && i < claimed.length; i += 1) claimed[i] = true;
    return true;
  };

  for (const pattern of DATE_TOKEN_PATTERNS) {
    pattern.re.lastIndex = 0;
    let match = pattern.re.exec(text);
    let guard = 0;
    while (match !== null) {
      guard += 1;
      if (guard > 20000) break; // a hard bound: no pattern may spin
      const start = match.index;
      const end = start + match[0].length;
      // A pattern may decline a match (a "month name" that is not a month).
      // Declining must leave the characters unclaimed so the next pattern
      // can read them, rather than silently swallowing the year.
      const built = pattern.build(match, start);
      if (built && claim(start, end)) {
        dates.push(built);
      }
      if (pattern.re.lastIndex === match.index) pattern.re.lastIndex += 1;
      match = pattern.re.exec(text);
    }
  }

  // Ranges: "2021–2023", "2021 - 2023", "Jan 2023 - present".
  const ranges = findRanges(text, claimed);
  for (const range of ranges) dates.push(range);

  dates.sort((a, b) => (a.start - b.start) || (a.end - b.end));
  unsupported.sort((a, b) => a.start - b.start);
  return { dates, unsupported };
}

/**
 * Claim every Bengali calendar month mention before any date token can read
 * its digits, and record it as an unsupported format. Never converted: the
 * Bengali year starts in mid-April, so a Bengali month plus a Bengali year
 * cannot be mapped to a Gregorian date without knowing which Gregorian year
 * the document means.
 *
 * @param {string} text
 * @param {boolean[]} claimed
 * @param {Array<{start:number,end:number,raw:string,reason:string}>} unsupported
 */
function bengaliCalendarPass(text, claimed, unsupported) {
  BENGALI_CALENDAR_RE.lastIndex = 0;
  let match = BENGALI_CALENDAR_RE.exec(text);
  let guard = 0;
  while (match !== null) {
    guard += 1;
    if (guard > 5000) break;
    const start = match.index;
    const end = start + match[0].length;
    let free = true;
    for (let i = start; i < end && i < claimed.length; i += 1) {
      if (claimed[i]) {
        free = false;
        break;
      }
    }
    if (free) {
      for (let i = start; i < end && i < claimed.length; i += 1) claimed[i] = true;
      unsupported.push({ start, end, raw: match[0], reason: 'bengali-calendar-month' });
    }
    match = BENGALI_CALENDAR_RE.exec(text);
  }
}

/**
 * Ranges between two recognised endpoints. Only ranges whose both ends
 * parse are ranges; anything else is left for the token rules to report
 * individually.
 *
 * @param {string} text
 * @param {boolean[]} claimed
 * @returns {ParsedDate[]}
 */
function findRanges(text, claimed) {
  const ranges = [];
  // A conservative, bounded pattern: two years or a year and an ongoing word,
  // joined by a dash, en dash or the word "to", with limited spacing.
  const rangeRe = /\b(\d{4})\s*(?:-|–|—|to)\s*(\d{4}|present|current|currently|ongoing|now)\b/gi;
  let match = rangeRe.exec(text);
  let guard = 0;
  while (match !== null) {
    guard += 1;
    if (guard > 5000) break;
    const start = match.index;
    const end = start + match[0].length;
    let free = true;
    for (let i = start; i < end && i < claimed.length; i += 1) if (claimed[i]) free = false;
    if (free) {
      const right = /present|current|currently|ongoing|now/i.test(match[2]);
      ranges.push({
        year: Number(match[1]), month: null, day: null,
        precision: 'year', ongoing: right, start, end, raw: match[0],
      });
      for (let i = start; i < end && i < claimed.length; i += 1) claimed[i] = true;
    }
    match = rangeRe.exec(text);
  }
  return ranges;
}

/**
 * @param {string} monthName
 * @param {number} day
 * @param {number} year
 * @param {string} raw
 * @param {number} offset
 * @returns {ParsedDate}
 */
function makeDayFromMonthName(monthName, day, year, raw, offset) {
  const month = MONTHS[String(monthName).toLowerCase().replace(/\./g, '')] ?? null;
  return {
    year, month, day, precision: 'day', ongoing: false,
    start: offset, end: offset + raw.length, raw,
  };
}

/**
 * @param {string} monthNameBn
 * @param {number} day
 * @param {number} year
 * @param {string} raw
 * @param {number} offset
 * @returns {ParsedDate}
 */
function makeDayFromBengali(monthNameBn, day, year, raw, offset) {
  return {
    year, month: BENGALI_MONTHS[monthNameBn] ?? null, day, precision: 'day', ongoing: false,
    start: offset, end: offset + raw.length, raw,
  };
}

/**
 * Build a month token from "Month YYYY".
 *
 * When `strict` is set (the token patterns), an unrecognised word makes the
 * whole match a non-date: the caller's `claim()` will not have been called
 * yet, and returning null tells `findDates` to drop the token and leave the
 * characters for the year pattern to read. Without strict, a null month
 * would otherwise produce a "month precision" date for the word "completed".
 *
 * @param {string} monthName
 * @param {number} year
 * @param {string} raw
 * @param {number} offset
 * @param {boolean} [strict]
 * @returns {ParsedDate|null}
 */
function makeMonthFromName(monthName, year, raw, offset, strict = false) {
  const month = MONTHS[String(monthName).toLowerCase().replace(/\./g, '')] ?? null;
  if (strict && month === null) return null;
  return {
    year, month, day: null, precision: 'month', ongoing: false,
    start: offset, end: offset + raw.length, raw,
  };
}

/**
 * Are two dates equal at the coarser of their precisions? "Jan 2023" and
 * "2023-01" are equal; a bare year is never treated as equal to a month or
 * a day the document does not state, and no day or month is invented.
 *
 * @param {ParsedDate} a
 * @param {ParsedDate} b
 * @returns {boolean}
 */
export function datesEqualAtCoarserPrecision(a, b) {
  if (!a || !b) return false;
  if (a.ongoing !== b.ongoing) return false;
  if (a.year !== b.year) return false;
  const precision = a.precision === 'year' || b.precision === 'year' ? 'year' : (a.precision === 'month' || b.precision === 'month' ? 'month' : 'day');
  if (precision === 'year') return true;
  if (a.month === null || b.month === null) return a.month === b.month;
  if (precision === 'month') return a.month === b.month;
  return a.day === b.day;
}

/**
 * Convert a four-digit Bengali year to a number. Exported for the tests so
 * the mapping is proven rather than asserted in prose.
 *
 * @param {string} value
 * @returns {number}
 */
export function bengaliYearToNumber(value) {
  return Number(toWesternDigits(value));
}
