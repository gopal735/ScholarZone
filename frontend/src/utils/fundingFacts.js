/**
 * Funding facts, and the guard against comparing incomparable funding.
 *
 * `funding_amount` looks like a number and is one on 485 of the 618 public
 * records. It is not a comparable number, and the reason is in the same
 * records: the amounts are stated in 42 different currencies and against 228
 * distinct period descriptions, from "per month" to "monthly allowance plus
 * airfare, tuition and language training". 1 400 EUR per month and
 * 14 400 000 KRW per month are the same money; 1 400 EUR per month and
 * 14 400 000 KRW once are not.
 *
 * The mission brief is explicit that missing values must not be read as zero
 * and that only comparable values may be sorted. So this module refuses to
 * rank funding amount at all, and instead exposes the single comparison that
 * is always safe - whether the award says it covers tuition, which is a
 * three-state fact the data actually carries (`tuition_coverage` is true on
 * 375 records, false on 215 and absent on 28).
 *
 * Nothing here converts currency or period, and nothing here synthesises a
 * value for a record that has none. Both would be fabrication.
 */

// The shared filter sentinel. Imported rather than restated because the
// tuition matcher below and the URL state module have to agree on what a
// select means by "Any tuition coverage".
import { NO_FILTER } from '../services/catalogueValues.js'

/** True for a string that carries usable text. Never coerces a falsy value. */
function isText(value) {
  return typeof value === 'string' && value.trim() !== ''
}

/**
 * True when two records' funding amounts could be compared as numbers.
 *
 * Always false in practice, and that is the finding rather than a gap: the
 * catalogue has no normalisation of currency or period, so two amounts are
 * comparable only when they share a currency and a period description. The
 * function is exposed so a future caller can ask rather than assume, and so a
 * test can pin the answer.
 */
export function fundingAmountsComparable(first, second) {
  if (!first || !second) {
    return false
  }

  if (typeof first.funding_amount !== 'number' || typeof second.funding_amount !== 'number') {
    return false
  }

  // A differing currency is decisive on its own.
  if (first.funding_currency !== second.funding_currency) {
    return false
  }

  // So is a differing period. Period is a free-text field, so this is an
  // exact comparison of the published wording: "per month" and
  // "monthly allowance plus airfare" are different claims, and treating them
  // as equal would compare a rate against a total.
  if (first.funding_period !== second.funding_period) {
    return false
  }

  return true
}

/**
 * The one funding comparison the data supports: tuition coverage.
 *
 * Returns one of three answers, because the data carries three states. `null`
 * means the record does not say, which is not the same as "no tuition
 * coverage" - 28 public records are in that state, and reporting them as
 * uncovered would be a fabricated negative.
 */
export function getTuitionCoverage(scholarship) {
  if (scholarship === null || typeof scholarship !== 'object') {
    return null
  }

  if (scholarship.tuition_coverage === true) {
    return true
  }

  if (scholarship.tuition_coverage === false) {
    return false
  }

  return null
}

/** The selectable values for the tuition-coverage filter. */
export const TUITION_COVERAGE_OPTIONS = Object.freeze([
  { value: 'yes', label: 'Tuition covered' },
  { value: 'no', label: 'Tuition not covered' },
  { value: 'not-stated', label: 'Coverage not stated' },
])

const TUITION_COVERAGE_LABELS = Object.freeze({
  yes: 'Tuition covered',
  no: 'Tuition not covered',
  'not-stated': 'Coverage not stated',
})

export function tuitionCoverageLabel(value) {
  return TUITION_COVERAGE_LABELS[value] ?? value
}

/** True when a record matches a tuition-coverage filter selection. */
export function matchesTuitionCoverage(scholarship, selection) {
  // The sentinel is checked first, for the same reason the study-level matcher
  // checks it: a select on "Any tuition coverage" is not filtering, and
  // returning false for it would empty an unfiltered catalogue.
  if (selection === NO_FILTER || selection === null || selection === undefined) {
    return true
  }
  if (!isText(selection)) {
    return true
  }

  const coverage = getTuitionCoverage(scholarship)

  if (selection === 'not-stated') {
    return coverage === null
  }

  if (selection === 'yes') {
    return coverage === true
  }

  if (selection === 'no') {
    return coverage === false
  }

  return false
}

/** At or below this length a funding string is shown whole. */
const FUNDING_BADGE_LIMIT = 34

/**
 * Categories the published funding text maps onto, in precedence order.
 *
 * These are classifications of the record's own wording, not new facts: a
 * record whose `funding` reads "Annual stipend of HK$344,400 …" is classified
 * `Stipend` because the provider's own text says it is a stipend. The full
 * text is returned alongside and is what the card exposes as a tooltip and a
 * screen-reader string, so the summary never stands in for the source.
 *
 * The pattern property is `pattern`, not `test`: a property named `test` on a
 * RegExp shadows nothing, but calling `entry.test(text)` calls the RegExp
 * itself rather than its `test` method, and throws
 * "entry.test is not a function" at runtime - which is exactly what the first
 * browser run of this module produced.
 */
const FUNDING_CATEGORIES = [
  { value: 'Fully funded', pattern: /fully\s*fund/i },
  { value: 'Tuition support', pattern: /tuition|fee\s*(waiver|reduction|cover)/i },
  { value: 'Stipend', pattern: /stipend|allowance|living\s*(allowance|cost)|maintenance/i },
  { value: 'Research funding', pattern: /research\s*fund|research\s*grant/i },
  { value: 'Travel support', pattern: /travel|airfare|flight|relocation/i },
  { value: 'Partial funding', pattern: /partial|partially/i },
  { value: 'Need-based', pattern: /need[\s-]?based|financial\s*need|means[\s-]?tested/i },
  { value: 'Housing support', pattern: /housing|accommodation|residence/i },
  { value: 'Health cover', pattern: /health|medical|insurance/i },
]

/**
 * A funding label that fits a badge, with the full wording retained.
 *
 * @param {object|null|undefined} scholarship
 * @returns {{label: string, full: string|null, isCategory: boolean, truncated: boolean}}
 *   `full` is null only when the record publishes no funding text at all, in
 *   which case `label` is the honest "Funding not stated" and `isCategory` is
 *   true so the badge renders in its quieter style.
 */
export function fundingBadgeLabel(scholarship) {
  const raw = scholarship?.funding
  const text = typeof raw === 'string' && raw.trim() !== '' ? raw.trim() : null

  if (text === null) {
    return { label: 'Funding not stated', full: null, isCategory: true, truncated: false }
  }

  if (text.length <= FUNDING_BADGE_LIMIT) {
    return { label: text, full: text, isCategory: false, truncated: false }
  }

  // A category exists, so use it. The badge becomes scannable and the record's
  // own long wording stays one tooltip and one screen-reader string away.
  const category = FUNDING_CATEGORIES.find((entry) => entry.pattern.test(text))
  if (category) {
    return { label: category.value, full: text, isCategory: true, truncated: true }
  }

  // No category. The first clause is the only part of a long funding string
  // that reads as a label, and it is cut at a boundary rather than mid-word so
  // the visible text is still a real phrase.
  const firstClause = text.split(/[;,.]/)[0].trim()
  if (firstClause !== '' && firstClause.length <= FUNDING_BADGE_LIMIT) {
    return { label: `${firstClause}…`, full: text, isCategory: true, truncated: true }
  }

  const words = text.split(/\s+/)
  let label = ''
  for (const word of words) {
    if (label.length + word.length + 1 > FUNDING_BADGE_LIMIT) {
      break
    }
    label = label === '' ? word : `${label} ${word}`
  }
  return { label: `${label}…`, full: text, isCategory: true, truncated: true }
}

/**
 * A single line stating what the funding is, for a card or a comparison cell.
 *
 * `funding` is the short published label and is used first because it is what
 * a student reads. `funding_type` is only used when the short label is absent,
 * never concatenated onto it, because that would produce a sentence claiming
 * two different funding descriptions for one award.
 *
 * The amount is appended only when both a currency and a period are present,
 * because an amount without either is a unitless number that reads as money.
 */
export function describeFunding(scholarship) {
  if (scholarship === null || typeof scholarship !== 'object') {
    return 'Funding not stated'
  }

  const shortLabel = isText(scholarship.funding) ? scholarship.funding.trim() : null
  const longLabel = isText(scholarship.funding_type) ? scholarship.funding_type.trim() : null

  const parts = []
  if (shortLabel) {
    parts.push(shortLabel)
  } else if (longLabel) {
    parts.push(longLabel)
  }

  const amount = scholarship.funding_amount
  const currency = isText(scholarship.funding_currency) ? scholarship.funding_currency.trim() : null
  const period = isText(scholarship.funding_period) ? scholarship.funding_period.trim() : null

  if (typeof amount === 'number' && Number.isFinite(amount) && currency && period) {
    parts.push(`${currency} ${amount.toLocaleString()} ${period}`)
  }

  if (parts.length === 0) {
    return 'Funding not stated'
  }

  return parts.join(' — ')
}
