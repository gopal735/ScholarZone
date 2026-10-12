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
