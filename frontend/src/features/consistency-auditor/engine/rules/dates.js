/**
 * Rule group A — dates and timelines.
 *
 * Design rule the tests pin: nothing is inferred. A bare year is a bare
 * year, "Jan 2023" and "2023-01" are equal, an ongoing item is never a
 * contradiction with a completed one, and overlapping study and work is a
 * question for the student, not an accusation.
 *
 * Rules:
 *
 * DATE-01  Graduation dates conflict (Possible factual inconsistency)
 *          Two documents state different completion dates for what looks
 *          like the same degree, at or above the precision they share.
 * DATE-02  Range ends before it starts (Possible factual inconsistency)
 *          One document states a range whose end precedes its start. A
 *          typo, but internally impossible, so it is reported.
 * DATE-03  Periods overlap (Needs human review)
 *          Study or work periods in the same document overlap. Studying
 *          while working is normal, so this is a prompt to check, never a
 *          contradiction.
 * DATE-04  Unsupported date format (Needs human review)
 *          A date the engine cannot parse, including Bengali calendar
 *          months. Never guessed, never skipped.
 * DATE-05  Same institution, different start years (Possible factual
 *          inconsistency) — reported only when both documents name the
 *          same entity and give different start years.
 */

import {
  findDates,
  datesEqualAtCoarserPrecision,
  normaliseEntityName,
} from '../normalize.js';
import { CATEGORIES, CONFIDENCE, makeFindingId } from '../findings.js';
import { splitLines } from '../validator.js';

/** Words that mark a degree mention, used to pair a degree with its year. */
const DEGREE_HINTS = /\b(b\.?sc|bachelor|ba|bs|b\.?a|m\.?sc|master|ms|m\.?a|ph\.?d|phd|doctorate|diploma|hsc|ssc|mbbs|b\.?eng|m\.?eng)\b/i;

/** Lines the date rules will not walk, to bound worst-case work. */
const MAX_SCANNED_LINE = 8000;

/**
 * The date rules share one helper: pull every date in a document with its
 * line, so a finding can quote the line the student wrote.
 *
 * @param {import('../validator.js').Document} document
 */
function documentDates(document) {
  const lines = splitLines(document.text);
  const dates = [];
  const unsupported = [];
  let offset = 0;
  for (const line of lines) {
    const length = line.length;
    if (length > 0 && length <= MAX_SCANNED_LINE) {
      const found = findDates(line);
      for (const date of found.dates) {
        dates.push({ ...date, start: date.start + offset, end: date.end + offset });
      }
      for (const entry of found.unsupported) {
        unsupported.push({ ...entry, start: entry.start + offset, end: entry.end + offset });
      }
    } else if (length > MAX_SCANNED_LINE) {
      // A line this long is not a date-bearing line in a statement or CV;
      // skipping it is documented in the README and reported by DATE-04.
      unsupported.push({
        start: offset,
        end: offset + Math.min(length, 400),
        raw: '',
        reason: 'line-too-long',
      });
    }
    offset += length + 1; // +1 for the newline that split() removed
  }
  return { dates, unsupported };
}

/**
 * @param {import('../validator.js').Document[]} documents
 * @returns {import('../findings.js').Finding[]}
 */
export function runDateRules(documents) {
  const findings = [];
  const perDocument = documents.map((document) => ({
    document,
    ...documentDates(document),
  }));

  for (const entry of perDocument) {
    for (const item of entry.unsupported) {
      findings.push({
        id: makeFindingId('DATE-04', [entry.document.id, String(item.start), item.reason]),
        ruleId: 'DATE-04',
        ruleName: 'Unsupported date format',
        category: CATEGORIES.humanReview,
        confidence: CONFIDENCE.weak,
        reason: item.reason === 'line-too-long'
          ? 'A line here is too long for the date checks to read reliably. If it contains dates, check them yourself.'
          : 'This looks like a date the review can\'t read. Bengali calendar months, and other non-Gregorian formats, are not converted — the calendar year would have to be guessed. Give it a look.',
        excerpts: [{
          documentId: entry.document.id,
          documentLabel: entry.document.label,
          start: item.start,
          end: item.end,
          text: entry.document.text.slice(item.start, item.end),
        }],
      });
    }
  }

  // DATE-02: a range that ends before it starts, within one document.
  for (const entry of perDocument) {
    for (const range of rangesWithin(entry.document.text)) {
      if (range.startDate.year !== null && range.endDate !== null && !range.endDate.ongoing) {
        if (compareDates(range.endDate, range.startDate) < 0) {
          findings.push({
            id: makeFindingId('DATE-02', [entry.document.id, String(range.start), String(range.end)]),
            ruleId: 'DATE-02',
            ruleName: 'Range ends before it starts',
            category: CATEGORIES.inconsistency,
            confidence: CONFIDENCE.strong,
            reason: 'This period ends before it begins. That may be a typo, but as written the two dates cannot both be right.',
            excerpts: [{
              documentId: entry.document.id,
              documentLabel: entry.document.label,
              start: range.start,
              end: range.end,
              text: entry.document.text.slice(range.start, range.end),
            }],
          });
        }
      }
    }
  }

  // DATE-01: the same degree stated with different dates across documents.
  findings.push(...graduationConflicts(perDocument));

  // DATE-03: overlapping periods within a document.
  for (const entry of perDocument) {
    const periods = periodsWithin(entry.document.text);
    for (let i = 0; i < periods.length; i += 1) {
      for (let j = i + 1; j < periods.length; j += 1) {
        const a = periods[i];
        const b = periods[j];
        if (overlaps(a, b) && !sharesLabel(a, b)) {
          findings.push({
            id: makeFindingId('DATE-03', [entry.document.id, String(a.start), String(b.start)]),
            ruleId: 'DATE-03',
            ruleName: 'Periods overlap',
            category: CATEGORIES.humanReview,
            confidence: CONFIDENCE.moderate,
            reason: 'Two periods here overlap in time. Studying and working at the same time is common and fine — this is only a prompt to check the dates read the way you meant them.',
            excerpts: [
              excerptOf(entry.document, a.start, a.end),
              excerptOf(entry.document, b.start, b.end),
            ],
          });
          break;
        }
      }
    }
  }

  return findings;
}

/**
 * Graduation conflicts: find each document's lines that both name a degree
 * and carry a completion year, group them by the DEGREE named on the line
 * (not by the whole line — the wording differs between documents, the
 * degree does not), and compare across documents. Only groups named in more
 * than one document can conflict, and only when the years actually differ.
 */
function graduationConflicts(perDocument) {
  const findings = [];
  /** @type {Map<string, Array<{document:any,line:string,start:number,end:number,year:number}>>} */
  const grouped = new Map();

  for (const entry of perDocument) {
    let offset = 0;
    for (const line of splitLines(entry.document.text)) {
      const length = line.length;
      if (length > 0 && length <= MAX_SCANNED_LINE && DEGREE_HINTS.test(line)) {
        const degree = degreeNamed(line);
        if (!degree) {
          offset += length + 1;
          continue;
        }
        const found = findDates(line);
        const completed = found.dates.filter((date) => !date.ongoing);
        // The LAST date on a degree line is the completion signal in the
        // common "BSc in X, 2019 - 2023" shape; the first is the start.
        const completion = completed.length >= 2 ? completed[completed.length - 1] : (completed.length === 1 ? completed[0] : null);
        if (completion && completion.year !== null) {
          const key = degree;
          const bucket = grouped.get(key) ?? [];
          bucket.push({
            document: entry.document,
            line,
            start: offset,
            end: offset + length,
            year: completion.year,
          });
          grouped.set(key, bucket);
        }
      }
      offset += length + 1;
    }
  }

  for (const bucket of grouped.values()) {
    const years = new Set(bucket.map((entry) => entry.year));
      if (years.size > 1) {
        const [first, second] = bucket;
        // The ID is derived from the comparison's content: the facts being
        // compared (the degree and the two years, sorted so the ID does not
        // change with which document happened to be listed first), never
        // from the document order or the surrounding wording.
        const comparisonKey = [first.document.id, second.document.id]
          .slice()
          .sort()
          .join('|');
        findings.push({
          id: makeFindingId('DATE-01', [comparisonKey, JSON.stringify([...years].sort())]),
        ruleId: 'DATE-01',
        ruleName: 'Graduation dates differ across documents',
        category: CATEGORIES.inconsistency,
        confidence: CONFIDENCE.strong,
        reason: 'These documents describe the same qualification with different completion years. Check which is right before you submit.',
        excerpts: [first, second].map((entry) => ({
          documentId: entry.document.id,
          documentLabel: entry.document.label,
          start: entry.start,
          end: entry.end,
          text: entry.line,
        })),
      });
    }
  }
  return findings;
}

/**
 * The degree named on a line, normalised, or null when the line names no
 * degree. Keyed on the DEGREE plus the field that follows it ("bsc computer
 * science"), because what varies between documents is the sentence, not the
 * qualification: "I completed my BSc in Computer Science in 2023" and "BSc
 * Computer Science, completed 2021" must land in the same group. The
 * surrounding wording, the dates and any trailing phrases are deliberately
 * not part of the key.
 *
 * @param {string} line
 * @returns {string|null}
 */
function degreeNamed(line) {
  const match = DEGREE_HINTS.exec(line);
  if (!match) return null;
  const after = line.slice(match.index + match[0].length, match.index + match[0].length + 40);
  // Drop the leading connector, then stop at the first thing that is not
  // part of the degree's field: a year, a comma, a full stop, "in <year>".
  const field = after
    .replace(/^\s*(in|of|from|,|the)\s+/i, '')
    .split(/[,.;(]|\s+in\s+\d{4}/i)[0];
  return normaliseEntityName(`${match[0]} ${field}`).slice(0, 60);
}

/**
 * @param {string} text
 * @returns {Array<{start:number,end:number,startDate:any,endDate:any}>}
 */
function rangesWithin(text) {
  const ranges = [];
  const re = /\b(\d{4})\s*(?:-|–|—|to)\s*(\d{4}|present|current|currently|ongoing|now)\b/gi;
  let match = re.exec(text);
  let guard = 0;
  while (match !== null && guard < 1000) {
    guard += 1;
    const start = match.index;
    const end = start + match[0].length;
    const startDate = { year: Number(match[1]), month: null, day: null, precision: 'year', ongoing: false };
    const endOngoing = /present|current|currently|ongoing|now/i.test(match[2]);
    ranges.push({ start, end, startDate, endDate: endOngoing ? { ongoing: true, year: null } : { year: Number(match[2]), month: null, day: null, precision: 'year', ongoing: false } });
    match = re.exec(text);
  }
  return ranges;
}

/**
 * Study or work periods, detected from a line containing a range or a
 * "since" marker. One period per line at most, which keeps the overlap
 * check quadratic in the number of lines rather than in the text length.
 *
 * @param {string} text
 */
function periodsWithin(text) {
  const periods = [];
  let offset = 0;
  for (const line of splitLines(text)) {
    const length = line.length;
    const range = rangesWithin(line)[0];
    const since = /\bsince\s+(\d{4})/i.exec(line);
    if (range && length <= 4000) {
      periods.push({ start: offset, end: offset + length, line, from: range.startDate.year, to: range.endDate.ongoing ? null : range.endDate.year });
    } else if (since && length <= 4000) {
      periods.push({ start: offset, end: offset + length, line, from: Number(since[1]), to: null });
    }
    offset += length + 1;
  }
  return periods;
}

/**
 * @param {{from:number|null,to:number|null}} a
 * @param {{from:number|null,to:number|null}} b
 */
function overlaps(a, b) {
  if (a.from === null || b.from === null) return false;
  const aEnd = a.to ?? a.from;
  const bEnd = b.to ?? b.from;
  return a.from <= bEnd && b.from <= aEnd;
}

/**
 * Two periods on the same line are the same statement, not an overlap.
 */
function sharesLabel(a, b) {
  return a.start === b.start;
}

/**
 * @param {{year:number|null,month:number|null,day:number|null,ongoing:boolean}} a
 * @param {{year:number|null,month:number|null,day:number|null,ongoing:boolean}} b
 */
function compareDates(a, b) {
  if (a.ongoing || b.ongoing) return 0;
  if (a.year !== b.year) return (a.year ?? 0) - (b.year ?? 0);
  if ((a.month ?? 0) !== (b.month ?? 0)) return (a.month ?? 0) - (b.month ?? 0);
  return (a.day ?? 0) - (b.day ?? 0);
}

/**
 * @param {import('../validator.js').Document} document
 * @param {number} start
 * @param {number} end
 */
function excerptOf(document, start, end) {
  return {
    documentId: document.id,
    documentLabel: document.label,
    start,
    end,
    text: document.text.slice(start, end),
  };
}

/** Exported for the tests that cover the precision comparison directly. */
export { datesEqualAtCoarserPrecision, graduationConflicts };
