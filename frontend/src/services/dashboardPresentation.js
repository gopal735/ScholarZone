/**
 * Turning server values into words.
 *
 * Every function here is a label, not a calculation. The server has already
 * decided what a fit band means, how many days remain and whether a record is
 * verified; this file only chooses how to write that down. Nothing recomputes a
 * score, counts a list or derives a deadline, because a browser that re-derives
 * a published number is a second source of truth for a rule that already has one.
 *
 * The verification labels are the important case. `verified` arrives from the
 * server already derived from the authoritative `verification_status`, and a
 * record needing confirmation must never be written as "Verified". The fallback
 * wording is deliberately "Confirm with provider" rather than "Unverified": an
 * outstanding confirmation is not a refutation, and the interface has no basis
 * for the second.
 */

/**
 * An engine bucket key as words: `CLOSING_SOON` -> "Closing soon".
 *
 * Sentence case rather than Title Case, matching the rest of the interface. The
 * input is an internal key, so the capitalisation is this function's decision
 * rather than something the reader chose.
 */
export function titleCaseKey(value) {
  if (!value) return ''
  const words = String(value)
    .split('_')
    .filter(Boolean)
    .map((word) => word.toLowerCase())
  if (words.length === 0) return ''
  words[0] = words[0].charAt(0).toUpperCase() + words[0].slice(1)
  return words.join(' ')
}

/** The trust label, from the server's own display field. */
export function verificationLabel(record) {
  if (record && typeof record.verification_display === 'string' && record.verification_display) {
    return record.verification_display
  }
  return record && record.verified ? 'Verified' : 'Confirm with provider'
}

/**
 * A deadline for a person, using the engine's own figure.
 *
 * `days_remaining` is null for a rolling, recurring or unpublished deadline. That
 * is an open round rather than a missing date, so it reads as the published
 * wording and never as "0 days left", which would read as overdue.
 */
export function deadlineText(item) {
  if (typeof item.days_remaining === 'number') {
    if (item.days_remaining < 0) return 'Closed'
    if (item.days_remaining === 0) return 'Closes today'
    if (item.days_remaining === 1) return '1 day left'
    return `${item.days_remaining} days left`
  }
  if (item.deadline) return item.deadline
  return 'No fixed date published'
}

/** Whether the deadline is precise enough to count down against. */
export function isExactDeadline(item) {
  return item.deadline_precision === 'exact'
}

/**
 * A fit score for display, or an honest absence.
 *
 * `fit_score` is null when nothing could be evaluated or the eligibility gate
 * refused the record. Showing "0" there would present a missing measurement as
 * a bad one, so the label names the reason instead.
 */
export function fitLabel(record) {
  if (record.fit_label_display) return record.fit_label_display
  if (typeof record.fit_score === 'number') return `${Math.round(record.fit_score)} fit score`
  return 'Not evaluated'
}

/** Readiness, or its absence. Readiness is never collapsed into fit. */
export function readinessLabel(record) {
  if (!record.readiness_label) return 'Readiness not evaluated'
  return record.readiness_label
}

/**
 * An accessible progress value, clamped and never inverted.
 *
 * A percentage is only emitted when there is a score to express. The bar itself
 * is decorative and hidden from assistive technology; the number is the content.
 */
export function strengthPercent(score) {
  if (typeof score !== 'number') return null
  return Math.max(0, Math.min(100, Math.round(score)))
}