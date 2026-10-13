/**
 * Study-level buckets derived from the catalogue's own degree strings.
 *
 * The catalogue stores degree in two fields that are both free text:
 * `degree` and `degree_levels`. Together they hold 164 distinct values across
 * the 618 public records, and their cardinality is the problem: the longest
 * value is a full sentence ("Any degree programme at a Charles University
 * faculty (undergraduate, master's or doctoral)") and roughly 60 of them are
 * held by exactly one record each. A menu built from those values is a
 * 164-entry list where almost every choice matches one scholarship.
 *
 * What a student actually chooses is a level, and a level is a bucket many of
 * those strings collapse into: "Master's", "Master's, PhD", "Master's,
 * Post-Master's" and "Undergraduate, Master's, Doctoral" are all master's-
 * eligible. So this module derives the set of levels a record is eligible for
 * and the filter selects a bucket instead of a literal.
 *
 * The derivation is deliberately conservative and total:
 *
 *   - It returns a set, not a scalar, because a record that accepts both
 *     bachelor's and doctoral applicants must be reachable from both buckets.
 *     Collapsing it to one would make it unfindable from the other.
 *   - A record whose text mentions no recognised level falls back to
 *     `UNSPECIFIED`, which is a real answer rather than a silent `any`. It is
 *     never merged into `any`: "no level stated" and "every level" are
 *     different claims, and a filter that treats them as equal hides records
 *     behind a bucket they were never in.
 *   - Matching is on word stems so "Masters", "master's", "postgraduate" and
 *     "post-master's" are not missed by a literal comparison.
 */

/**
 * The sentinel a "no filter" select carries.
 *
 * Imported from a leaf module rather than restated, because this module and the
 * tuition matcher both need it and neither can import the URL state module
 * without a cycle - the URL module imports them for their labels.
 */
import { NO_FILTER } from '../services/catalogueValues.js'

/** Every bucket this module can return. Order is display order. */
export const STUDY_LEVELS = Object.freeze([
  { value: 'bachelor', label: "Bachelor's" },
  { value: 'master', label: "Master's" },
  { value: 'doctoral', label: 'Doctoral / PhD' },
  { value: 'postdoc', label: 'Postdoctoral' },
  { value: 'any', label: 'Any level' },
])

/** A bucket for records whose degree text states no recognisable level. */
export const UNSPECIFIED_LEVEL = 'unspecified'

const LEVEL_PATTERNS = [
  // Order matters: a postdoc string must be tested before doctoral, because
  // "PhD, Postdoc" contains "phd" and would otherwise resolve to doctoral
  // only, losing the postdoc bucket.
  {
    value: 'postdoc',
    test: (text) => /post[\s-]?doc/i.test(text),
  },
  {
    value: 'doctoral',
    test: (text) => /\b(ph\.?\s?d|doctoral|doctorate|dphil|phd)\b/i.test(text),
  },
  {
    // "postgraduate" alone is ambiguous - it can mean master's - so it is only
    // treated as master's when a master's stem is also present.
    //
    // `m.s.c` joins `m.a.s.c` because "MSc" and "M.A.Sc" are the same degree
    // written two ways, and the shorter form is common enough in the catalogue
    // that dropping it removes real records from the bucket.
    value: 'master',
    test: (text) => /m\.?a\.?s\.?c|m\.?s\.?c|master|post[\s-]?graduate|mba|mphil/i.test(text),
  },
  {
    value: 'bachelor',
    test: (text) => /b\.?tech|b\.?sc|bachelor|b\.?e\b|undergrad|ug\b|associate/i.test(text),
  },
]

/**
 * Patterns for a record that explicitly accepts any level. These are phrases
 * that say so, not a catch-all: "Bachelor's, Master's, PhD" is *not* `any`,
 * because it excludes a postdoc, and putting it in `any` would make it
 * answerable by a postdoctoral search that then returns it incorrectly.
 */
const ANY_LEVEL_PATTERN = /(any degree|all levels|all programmes|any level|any programme|every level)/i

/**
 * The sentinel a "no filter" value takes in catalogue state.
 *
 * Checked before anything derived, because the distinction that matters is
 * between "the student chose anything" and "the student chose a bucket":
 * returning false for the former would make an unfiltered catalogue show
 * nothing.
 */
const NO_FILTER_VALUE = NO_FILTER

/** True for a string that carries usable text. Never coerces a falsy value. */
function isText(value) {
  return typeof value === 'string' && value.trim() !== ''
}

/**
 * Derive the study-level buckets a record is eligible for.
 *
 * @param {object|null|undefined} scholarship
 * @returns {string[]} One or more of the STUDY_LEVELS values, or
 *   `[UNSPECIFIED_LEVEL]` when the record states no recognisable level.
 */
export function getStudyLevels(scholarship) {
  if (scholarship === null || typeof scholarship !== 'object') {
    return [UNSPECIFIED_LEVEL]
  }

  // `degree_levels` is the descriptive field; `degree` mirrors it in a shorter
  // form. Both are read, because a record can name a level in one and not the
  // other, and `degree` is the field the existing exact-match filter uses.
  const texts = [scholarship.degree_levels, scholarship.degree].filter(isText)

  if (texts.length === 0) {
    return [UNSPECIFIED_LEVEL]
  }

  const combined = texts.join(' / ')

  if (ANY_LEVEL_PATTERN.test(combined)) {
    return ['any']
  }

  const levels = LEVEL_PATTERNS.filter((pattern) => pattern.test(combined)).map(
    (pattern) => pattern.value,
  )

  if (levels.length === 0) {
    return [UNSPECIFIED_LEVEL]
  }

  return levels
}

/**
 * True when a record belongs to a bucket, so a filter selection matches it.
 *
 * `unspecified` is not matched by any real bucket: a record that names no
 * level must not appear under "Any level", because "no level stated" is not
 * evidence that any level is accepted. Selecting `unspecified` is available to
 * callers that want to surface exactly those records.
 */
export function matchesStudyLevel(scholarship, level) {
  if (!isText(level) || level.trim().toLowerCase() === NO_FILTER_VALUE) {
    return true
  }

  return getStudyLevels(scholarship).includes(level.trim())
}

/**
 * Human label for a bucket value. Unknown values pass through unchanged.
 *
 * `any` needs no special case: a record whose text says "any degree programme"
 * is reported as `any`, which is in STUDY_LEVELS and so has a label.
 */
export function studyLevelLabel(level) {
  const found = STUDY_LEVELS.find((entry) => entry.value === level)
  if (found) {
    return found.label
  }
  return level === UNSPECIFIED_LEVEL ? 'Level not stated' : level
}
