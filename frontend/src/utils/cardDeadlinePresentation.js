/**
 * How a deadline is presented on a card.
 *
 * The catalogue publishes deadlines in two different shapes, and the card used
 * to render whichever it got as one bold right-aligned value. Measured on the
 * shipped snapshot, the `deadline` field reaches 244 characters on one record
 * and 310 on another, and those are the provider's own sentences - "Applications
 * are open starting August 20, 2026 ... application deadline is 15 December
 * 2026 for ...". Rendering a 244-character sentence at `font-weight: 700` and
 * `line-height: 1.35` is what made the deadline block the loudest thing on the
 * card and the hardest to scan.
 *
 * So the deadline is split into the two things a student actually reads:
 *
 *   - the **value** - a date, when the record carries one. Short, so it can be
 *     set at a readable weight without shouting.
 *   - the **note** - the provider's own wording, at body weight, left-aligned,
 *     with a comfortable line height. This is where a long sentence belongs,
 *     and it is always shown in full rather than clamped, because the detail
 *     page is not the only place a student looks.
 *
 * When no date exists the value is the provider's text, still at body weight,
 * because there is no date to promote and inventing one is not an option. When
 * neither exists the value says so plainly.
 *
 * Nothing here is fabricated. Every string is either a formatted `deadline_date`
 * the record carries, or the record's own `deadline` text, or the record's own
 * `deadline_precision` label.
 */

import { getDeadlinePrecisionLabel } from './scholarshipPresentation.js'

/** Above this, a deadline string is treated as prose rather than as a value. */
const PROSE_THRESHOLD = 48

/** Above this, the value line is clamped rather than allowed to run away. */
const MAX_VALUE_CHARS = 60

/** True for a date string that parses to a real day. */
function parseDeadlineDate(value) {
  if (typeof value !== 'string' || value.trim() === '') {
    return null
  }

  // `deadline_date` is ISO `YYYY-MM-DD` throughout the snapshot; a time
  // component would make the appended `T00:00:00` malformed, so one is tolerated
  // by parsing the leading date part on its own.
  const trimmed = value.trim()
  const datePart = trimmed.includes('T') ? trimmed.split('T')[0] : trimmed
  const parsed = new Date(`${datePart}T00:00:00`)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

const DATE_FORMAT = new Intl.DateTimeFormat(undefined, {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
})

/** `20 Aug 2026` from a real date, or null when there is none. */
export function formatDeadlineDate(value) {
  const parsed = parseDeadlineDate(value)
  return parsed === null ? null : DATE_FORMAT.format(parsed)
}

/** The record's own deadline text, trimmed, or null. */
function readDeadlineText(scholarship) {
  const text = scholarship?.deadline
  if (typeof text !== 'string' || text.trim() === '') {
    return null
  }
  return text.trim()
}

/**
 * True when the provider's deadline text is a short, date-shaped value rather
 * than a sentence. A 12-character ISO date and a 244-character explanation are
 * not the same kind of thing and should not be set the same way.
 */
function looksLikeADate(text) {
  if (text === null) {
    return false
  }
  if (text.length > PROSE_THRESHOLD) {
    return false
  }
  // A sentence has spaces and ends with punctuation; a date rarely does. This
  // is a presentation heuristic only - it never discards the text.
  return !/[.;]/.test(text.slice(-1)) || /^\d{4}-\d{2}-\d{2}$/.test(text)
}

/**
 * Split a scholarship's deadline into a value and a note.
 *
 * @param {object|null|undefined} scholarship
 * @returns {{
 *   kind: 'dated' | 'described' | 'text' | 'unknown',
 *   value: string,
 *   note: string|null,
 *   precisionLabel: string|null,
 *   isProse: boolean,
 *   hasDate: boolean,
 * }}
 */
export function presentCardDeadline(scholarship) {
  const precisionLabel = getDeadlinePrecisionLabel(scholarship)
  const providerText = readDeadlineText(scholarship)
  const formattedDate = formatDeadlineDate(scholarship?.deadline_date)

  if (formattedDate !== null && providerText !== null) {
    // A real date plus the provider's own wording. The date is the value; the
    // wording is the note, because it is the authoritative phrasing and often
    // carries the part the date does not - who it applies to, which round it is,
    // whether it varies by programme.
    const textIsProse = !looksLikeADate(providerText)

    if (textIsProse) {
      return {
        kind: 'described',
        value: formattedDate,
        note: providerText,
        precisionLabel,
        isProse: true,
        hasDate: true,
      }
    }

    // Both are short and agree in spirit: the date alone carries it, so the
    // provider text becomes the note only if it says something the date does
    // not - which here it does, by being the published form.
    return {
      kind: 'dated',
      value: providerText.length <= MAX_VALUE_CHARS ? providerText : formattedDate,
      note: providerText.length <= MAX_VALUE_CHARS ? null : null,
      precisionLabel,
      isProse: false,
      hasDate: true,
    }
  }

  if (formattedDate !== null) {
    return {
      kind: 'dated',
      value: formattedDate,
      note: null,
      precisionLabel,
      isProse: false,
      hasDate: true,
    }
  }

  if (providerText !== null) {
    // No machine-readable date. The provider's wording is the only truthful
    // value, and it is returned as prose so the caller sets it at body weight
    // rather than promoting a sentence to a value.
    return {
      kind: 'text',
      value: providerText,
      note: null,
      precisionLabel,
      isProse: true,
      hasDate: false,
    }
  }

  return {
    kind: 'unknown',
    value: 'Deadline to be confirmed',
    note: null,
    precisionLabel,
    isProse: false,
    hasDate: false,
  }
}
