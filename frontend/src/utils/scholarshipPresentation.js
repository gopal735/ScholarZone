/**
 * Presentation helpers that must stay honest about what the catalogue knows.
 *
 * Three rules, each of which exists because a real record in the shipped
 * snapshot breaks the naive version:
 *
 *   1. A status is only reported as what the record says. `upcoming` is a
 *      value the snapshot holds on 107 of 618 records, and it used to have no
 *      entry here, so those 107 all rendered the "Open" pill. A student
 *      reading "Open" for an award that does not open for months plans the
 *      wrong thing.
 *   2. A deadline is only "confirmed" when the record's own precision says it
 *      is. Every precision other than `exact` and `day` is a provider telling
 *      us the date is approximate, rolling, recurring or simply unknown, and
 *      labelling those as a full confirmed date contradicts the "Deadline to
 *      be confirmed" the same page renders.
 *   3. A verification date is only a verification date when the record was
 *      actually verified. `last_verified_at` is populated on records whose
 *      `verification_status` is `needs_review`, so printing "Verified <date>"
 *      there claims the opposite of what the status field says.
 */

/** Status values the catalogue holds, in urgency order for sorting. */
const STATUS_METADATA = {
  open: { label: 'Open', className: 'open' },
  'closing-soon': { label: 'Closing soon', className: 'closing-soon' },
  upcoming: { label: 'Upcoming', className: 'upcoming' },
  closed: { label: 'Closed', className: 'closed' },
}

/**
 * Precisions that mean the provider has published a specific date.
 *
 * `day`, `exact` and `day_and_time` are the three. Everything else - unknown,
 * approximate, month, varies, recurring, rolling, year, none - is a provider
 * stating that the date is not a single confirmed day, so none of them may be
 * described as one.
 *
 * `day_and_time` belongs here for the reason it was left out at first: it is a
 * *more* specific statement than `day`, not a vaguer one. A deadline published
 * with a time is a published specific date, and treating it as not-confirmed
 * would make the deadline planner drop the 42 records that have the clearest
 * deadlines of all.
 */
const CONFIRMED_DATE_PRECISIONS = new Set(['day', 'exact', 'day_and_time'])

/**
 * The label for a deadline precision, without claiming more than the record
 * does.
 *
 * A value outside the known set is reported as unknown rather than as exact:
 * an unrecognised precision is a value this build has never seen, and treating
 * it as a confirmed date would be the exact defect this function replaced.
 */
const PRECISION_LABELS = {
  exact: 'Exact date published by the provider',
  day: 'Full date published by the provider',
  day_and_time: 'Date and time published by the provider',
  month: 'Month only — the provider has not published a full date',
  approximate: 'Approximate date — the provider has not published an exact date',
  recurring: 'Recurring date — confirm each year’s date with the provider',
  rolling: 'Rolling deadline — applications close once places are filled',
  varies: 'Deadline varies by programme or host institution',
  year: 'Year only — the provider has not published a full date',
  none: 'The provider publishes no closing date',
  unknown: 'Deadline precision not stated by the provider',
}

/** True when the record's own precision states a single confirmed date. */
export function hasConfirmedDeadlineDate(scholarship) {
  return CONFIRMED_DATE_PRECISIONS.has(scholarship?.deadline_precision)
}

/** The deadline-precision label, or null when nothing may be claimed. */
export function getDeadlinePrecisionLabel(scholarship) {
  const precision = scholarship?.deadline_precision
  if (typeof precision !== 'string' || precision.trim() === '') {
    return null
  }
  return PRECISION_LABELS[precision.trim()] ?? PRECISION_LABELS.unknown
}

/** True when a deadline value exists and is parseable as a date. */
function hasDeadlineValue(scholarship) {
  if (typeof scholarship?.deadline_date !== 'string' || scholarship.deadline_date.trim() === '') {
    return false
  }
  return !Number.isNaN(new Date(`${scholarship.deadline_date}T00:00:00`).getTime())
}

function getDerivedStatus(deadlineDate) {
  if (!deadlineDate) {
    return 'open'
  }

  const deadline = new Date(`${deadlineDate}T00:00:00`)
  if (Number.isNaN(deadline.getTime())) {
    return 'open'
  }

  const today = new Date()
  today.setHours(0, 0, 0, 0)
  if (deadline < today) {
    return 'closed'
  }

  const closingSoonThreshold = new Date(today)
  closingSoonThreshold.setDate(today.getDate() + 30)
  return deadline <= closingSoonThreshold ? 'closing-soon' : 'open'
}

/**
 * The status a record should display and be filtered by.
 *
 * The record's own `status` wins. When it is absent - one public record has
 * none - the status is derived from the deadline, which is what the card has
 * always shown. Deriving in both the display and the filter, rather than in
 * the display alone, is what stops the status control from disagreeing with
 * the pill beside it: a card reading "Closing soon" inside a view filtered to
 * "Open" is a control that contradicts the page it is on.
 */
export function getScholarshipStatus(scholarship) {
  const status = scholarship?.status || getDerivedStatus(scholarship?.deadline_date)
  return STATUS_METADATA[status] || STATUS_METADATA.open
}

/** The raw status code a record should be filtered by. */
export function getScholarshipStatusCode(scholarship) {
  const displayed = getScholarshipStatus(scholarship)
  const entry = Object.entries(STATUS_METADATA).find(([, value]) => value === displayed)
  return entry ? entry[0] : getDerivedStatus(scholarship?.deadline_date)
}

export function getDeadlineLabel(scholarship) {
  return scholarship?.deadline || scholarship?.deadline_date || 'Deadline to be confirmed'
}

/**
 * True when a deadline should be presented as a confirmed date.
 *
 * Requires both a real value and a precision the provider actually stated.
 * Either alone is not enough: a `month`-precision record that carries a
 * date for ordering purposes must not be described as a confirmed date, and a
 * record with no date at all must not be described as anything.
 */
export function hasConfirmedDeadline(scholarship) {
  return hasDeadlineValue(scholarship) && hasConfirmedDeadlineDate(scholarship)
}

/**
 * The verification line for a record, which only claims verification that
 * happened.
 *
 * A record whose `verification_status` is not `active` has not been re-checked
 * against the awarding body, so a `last_verified_at` on it is a record of an
 * earlier attempt, not a current confirmation. Printing "Verified <date>"
 * there contradicted the "Confirm with provider" pill on the same card.
 */
export function getLastVerifiedLabel(scholarship, options = {}) {
  const isVerified = scholarship?.verification_status === 'active'
  const value = scholarship?.last_verified_at

  if (!value) {
    return isVerified ? 'Verification date pending' : 'Not yet re-checked against the awarding body'
  }

  const verifiedDate = new Date(`${value}T00:00:00`)
  if (Number.isNaN(verifiedDate.getTime())) {
    return isVerified ? 'Verification date pending' : 'Not yet re-checked against the awarding body'
  }

  const formatted = new Intl.DateTimeFormat(options.locale, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(verifiedDate)

  // `compact` drops the trailing instruction. A card prints it next to the
  // "Confirm with provider" badge, and once the row reads
  // "Confirm with provider | Last checked 10 Oct 2026; confirm with provider"
  // the three signals stop reading as three facts.
  if (options.compact) {
    return isVerified ? `Verified ${formatted}` : `Last checked ${formatted}`
  }

  return isVerified ? `Verified ${formatted}` : `Last checked ${formatted}; confirm with the provider`
}

export { STATUS_METADATA }
