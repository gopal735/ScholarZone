/**
 * Date primitives for the Bangladesh Applicant Journey.
 *
 * Two invariants live here, and both exist because the obvious implementation
 * of either breaks a real case.
 *
 * 1. **A date is a calendar day, not an instant.** Every persisted date is the
 *    string `YYYY-MM-DD` and it is parsed into local midnight. The usual
 *    `new Date('2026-08-01')` parses that as UTC midnight, which is 01:00 on
 *    1 August in Dhaka-only... and 31 July in New York, so the same string
 *    renders as two different days depending on where the browser is. Splitting
 *    the string and constructing a local date removes the timezone from the
 *    path entirely.
 *
 * 2. **An official deadline and a student's own target date are never the same
 *    field.** They are read, stored, sorted and exported separately by
 *    convention: nothing in this module combines them, and nothing copies one
 *    into the other. See `deadlineStatus`, which only ever evaluates the
 *    student's own target.
 */

export const APPROACHING_DAYS = 14

const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/

/**
 * Parse `YYYY-MM-DD` into a local-midnight Date.
 *
 * Returns null for anything that is not a real calendar day, including
 * `2026-02-30`. A null return is the only failure signal: callers render an
 * explicit unknown state rather than guessing.
 */
export function parseIsoDate(value) {
  if (typeof value !== 'string') return null
  const match = ISO_DATE.exec(value.trim())
  if (!match) return null

  const year = Number(match[1])
  const month = Number(match[2])
  const day = Number(match[3])

  if (month < 1 || month > 12 || day < 1 || day > 31) return null

  const date = new Date(year, month - 1, day)
  // The round-trip is what rejects 31 April and 30 February: the Date object
  // rolls them into the following month, so the components no longer match.
  if (
    date.getFullYear() !== year ||
    date.getMonth() !== month - 1 ||
    date.getDate() !== day
  ) {
    return null
  }

  return date
}

/** True when the string is a real, representable calendar day. */
export function isIsoDate(value) {
  return parseIsoDate(value) !== null
}

/** Local-midnight today as `YYYY-MM-DD`. Injected so tests own "now". */
export function toIsoDate(date) {
  const year = String(date.getFullYear()).padStart(4, '0')
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function todayIso(now = new Date()) {
  return toIsoDate(now)
}

/**
 * Whole days from `fromIso` to `toIso`.
 *
 * Positive when `toIso` is later. Null when either date is missing or
 * unparseable, so a caller can never mistake "cannot tell" for "zero days".
 */
export function daysBetween(fromIso, toIso) {
  const from = parseIsoDate(fromIso)
  const to = parseIsoDate(toIso)
  if (!from || !to) return null
  const MS_PER_DAY = 24 * 60 * 60 * 1000
  return Math.round((to.getTime() - from.getTime()) / MS_PER_DAY)
}

/**
 * Classify the student's own target date against a reference day.
 *
 * Deliberately evaluates only the personal target. An official deadline is a
 * fact the student records from the provider and is never treated as overdue:
 * the feature does not know whether the student has already applied, and
 * inventing an alarm the student never set is exactly the kind of manufactured
 * urgency this feature must not produce.
 */
export function personalDateStatus(personalTargetIso, referenceIso = todayIso()) {
  const days = daysBetween(referenceIso, personalTargetIso)
  if (days === null) {
    return { state: 'unknown', days: null }
  }
  if (days < 0) {
    return { state: 'overdue', days }
  }
  if (days <= APPROACHING_DAYS) {
    return { state: 'approaching', days }
  }
  return { state: 'upcoming', days }
}

/**
 * Days until an official deadline, or null when it is not recorded.
 *
 * Read-only description of a fact the student entered. "Missing" is a state of
 * the record, not of the world: the provider may or may not have published one.
 */
export function officialDeadlineInfo(officialDeadlineIso, referenceIso = todayIso()) {
  const days = daysBetween(referenceIso, officialDeadlineIso)
  return { recorded: days !== null, days }
}

/**
 * Sort comparator over an array of records carrying the two date kinds.
 *
 * `criterion` is which field to sort by and is required: the two never fall
 * back to each other. Records with no value for the chosen criterion sort last
 * (they have nothing to order by), and a stable secondary sort on the record's
 * own label keeps the output deterministic when both are missing.
 */
export function byDateCriterion(criterion) {
  return (a, b) => {
    const left = parseIsoDate(a?.[criterion])
    const right = parseIsoDate(b?.[criterion])
    if (!left && !right) return String(a?.label ?? '').localeCompare(String(b?.label ?? ''))
    if (!left) return 1
    if (!right) return -1
    return left.getTime() - right.getTime()
  }
}
