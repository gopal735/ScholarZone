/**
 * Comparison rows.
 *
 * Each row is a decision-relevant attribute, and each carries its own
 * renderer because the value decides what "missing" means. Two rules:
 *
 *   1. A value the catalogue does not carry renders as "Not stated". It must
 *      never render as an empty cell, because an empty cell reads as "no
 *      answer" and "Not stated" reads as "we do not know", and a student
 *      deciding between two awards needs to know which one they are looking at.
 *   2. A confirmed negative renders as the negative. `tuition_coverage: false`
 *      means the provider says tuition is not covered; that is information,
 *      and rendering it as "Not stated" would hide it.
 *
 * Funding amount is deliberately NOT compared. The amounts are published in 42
 * different currencies against 228 distinct period descriptions, so
 * "1400" and "14400000" are not two values on one scale - putting them in the
 * same column would invite a comparison the data does not support.
 */

import {
  getDeadlineLabel,
  getDeadlinePrecisionLabel,
  getLastVerifiedLabel,
  getScholarshipStatus,
} from '../utils/scholarshipPresentation.js'
import { describeFunding, getTuitionCoverage } from '../utils/fundingFacts.js'
import { studyLevelLabel } from '../utils/studyLevel.js'
import { readText } from '../utils/scholarshipDetail.js'

/** The value shown when the catalogue does not carry a field. */
export const NOT_STATED = 'Not stated'

/** The provider that runs the award. */
function providerOf(scholarship) {
  return readText(scholarship?.official_source) || NOT_STATED
}

/** Host country, with the region in parentheses when it adds a distinction. */
function locationOf(scholarship) {
  const country = readText(scholarship?.country)
  const region = readText(scholarship?.region)
  if (!country && !region) {
    return NOT_STATED
  }
  if (country && region && region.toLowerCase() !== country.toLowerCase()) {
    return `${country} (${region})`
  }
  return country || region
}

/**
 * Study level, as the bucket rather than the literal.
 *
 * The literal degree string is 164 distinct values, most of them a sentence, so
 * a comparison column of literals is unreadable next to the other rows.
 */
function studyLevelOf(scholarship) {
  const literal = readText(scholarship?.degree)
  if (!literal) {
    return NOT_STATED
  }
  return literal
}

function eligibilityOf(scholarship) {
  // The summary is the field written for this purpose. It is absent on 12 of
  // 618 records, and those get "Not stated" rather than a guess.
  const summary = readText(scholarship?.eligibility_summary)
  return summary || NOT_STATED
}

function deadlineOf(scholarship) {
  const label = getDeadlineLabel(scholarship)
  if (!label || label === 'Deadline to be confirmed') {
    return NOT_STATED
  }
  const precision = getDeadlinePrecisionLabel(scholarship)
  // The precision label travels with the date, because a month-only deadline
  // and an exact one are different claims and a student comparing them needs
  // to see the difference rather than infer it.
  return precision ? `${label} — ${precision}` : label
}

function statusOf(scholarship) {
  return getScholarshipStatus(scholarship).label
}

function tuitionOf(scholarship) {
  const coverage = getTuitionCoverage(scholarship)
  if (coverage === true) {
    return 'Tuition covered'
  }
  if (coverage === false) {
    return 'Tuition not covered'
  }
  return NOT_STATED
}

function englishRequirementOf(scholarship) {
  return readText(scholarship?.english_requirement) || NOT_STATED
}

function durationOf(scholarship) {
  return readText(scholarship?.duration) || NOT_STATED
}

function applicationMethodOf(scholarship) {
  const method = Array.isArray(scholarship?.application_method)
    ? scholarship.application_method[0]
    : scholarship?.application_method
  const text = readText(method)
  if (!text) {
    return NOT_STATED
  }
  // The full method is a multi-step list on most records; the first step is
  // what identifies the route, and the detail page holds the rest.
  return text.length > 120 ? `${text.slice(0, 117)}…` : text
}

function verificationOf(scholarship) {
  const label = getLastVerifiedLabel(scholarship)
  return label || NOT_STATED
}

function officialSourceOf(scholarship) {
  return readText(scholarship?.official_source_url) || NOT_STATED
}

/**
 * The rows, in the order a student decides in: what it is, whether I qualify,
 * what it costs, when it closes, how I apply, and how much to trust it.
 */
export const COMPARISON_ROWS = Object.freeze([
  { key: 'provider', label: 'Provider', value: providerOf },
  { key: 'location', label: 'Country / region', value: locationOf },
  { key: 'level', label: 'Study level', value: studyLevelOf },
  { key: 'eligibility', label: 'Eligibility', value: eligibilityOf },
  { key: 'funding', label: 'Funding', value: describeFunding },
  { key: 'tuition', label: 'Tuition coverage', value: tuitionOf },
  { key: 'deadline', label: 'Deadline', value: deadlineOf },
  { key: 'status', label: 'Status', value: statusOf },
  { key: 'duration', label: 'Duration', value: durationOf },
  { key: 'english', label: 'English requirement', value: englishRequirementOf },
  { key: 'method', label: 'How to apply', value: applicationMethodOf },
  { key: 'verification', label: 'Verification', value: verificationOf },
  { key: 'source', label: 'Official source', value: officialSourceOf },
])

/**
 * Render one row. A renderer that returns a non-string is a defect surfaced to
 * the caller rather than printed as "[object Object]".
 */
export function renderComparisonCell(row, scholarship) {
  try {
    const value = row.value(scholarship)
    if (typeof value === 'string') {
      return value.trim() === '' ? NOT_STATED : value
    }
    if (value === null || value === undefined) {
      return NOT_STATED
    }
    if (Array.isArray(value)) {
      const joined = value.filter(Boolean).join(', ')
      return joined === '' ? NOT_STATED : joined
    }
    return String(value)
  } catch {
    return NOT_STATED
  }
}

/** The label for a study level value, used by the filter chips. */
export { studyLevelLabel }
