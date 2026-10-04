/**
 * Turning a mentor response into words and tones.
 *
 * Every function here is a label or a formatting decision, kept out of the
 * components so the phrasing can be tested without rendering anything.
 *
 * Three refusals matter more than the labels, and each one exists because the
 * alternative is a lie told in the interface:
 *
 * 1. An unknown deadline is never rendered as "0 days left". The server already
 *    refuses to produce that string; this module refuses to invent it if a value
 *    ever arrives without one.
 * 2. A missing measurement is rendered as unmeasured, never as 0%. Nothing was
 *    counted, so nothing scored zero.
 * 3. Tone is never the only signal. Every tone returned here is accompanied by
 *    the server's own words, which the interface renders as text, so colour is
 *    a reinforcement rather than the message.
 */

/** The two ways an answer can be sourced, said plainly to the reader. */
export const SOURCE_VERIFIED = 'ScholarZone verified data'
export const SOURCE_GUIDANCE = 'General guidance'

/**
 * How an answer should be labelled as a source.
 *
 * A refusal is better than an answer presented as verified data. When the server
 * says nothing in the answer is a measurement, that is what the reader is told.
 */
export function sourceLabel(answer) {
  if (!answer) return SOURCE_GUIDANCE
  if (answer.general_guidance_only) return SOURCE_GUIDANCE
  if (!answer.known || answer.known.length === 0) return SOURCE_GUIDANCE
  return SOURCE_VERIFIED
}

/** True only when the answer cites at least one canonical measurement. */
export function isGrounded(answer) {
  return Boolean(answer && answer.known && answer.known.length > 0)
}

/**
 * A tone for one piece of evidence, derived from the server's own words.
 *
 * Returns a class suffix rather than a colour, so the stylesheet stays the only
 * place that knows what a tone looks like.
 */
export function evidenceTone(entry) {
  if (!entry) return 'neutral'
  const verification = (entry.verification || '').toLowerCase()
  if (verification.includes('no longer listed')) return 'muted'
  if (verification.includes('confirm')) return 'warning'
  if (verification.includes('verified')) return 'success'
  if (entry.field && entry.field.includes('evaluate_deadline')) return 'neutral'
  return 'neutral'
}

/** The word shown next to an evidence value, so tone is never the only signal. */
export function evidenceStatusWord(entry) {
  if (!entry) return ''
  if (entry.verification) return entry.verification
  return entry.basis || ''
}

/**
 * Deadline wording for an evidence value, refusing to fabricate a count.
 *
 * The server composes the sentence from `evaluate_deadline`; this exists to
 * guarantee that a bare or malformed value can never be displayed as a count of
 * zero days.
 */
export function deadlineText(value) {
  const text = (value || '').trim()
  if (!text) return 'No published deadline ScholarZone can count down to.'
  return text
}

/** True when the value describes a closed or finished round. */
export function isClosedDeadline(value) {
  return /closed|passed/i.test(value || '')
}

/**
 * Progress text.
 *
 * `null` means nothing was counted. That is not zero progress and it is not a
 * full checklist, so it is reported as unmeasured.
 */
export function progressText(percent) {
  if (percent === null || percent === undefined) return 'Not measured'
  const value = Number(percent)
  if (!Number.isFinite(value)) return 'Not measured'
  return `${Math.round(value * 10) / 10}% of counted tasks complete`
}

/** True when a number is genuinely absent rather than zero. */
export function isUnmeasured(percent) {
  return percent === null || percent === undefined || !Number.isFinite(Number(percent))
}

/**
 * A short description of where the answer came from, for the status strip.
 *
 * "disabled" is reported honestly rather than dressed up: in the default
 * deployment the mentor composes every answer itself from catalogue records, and
 * saying so is more trustworthy than implying a model wrote it.
 */
export function providerText(mode, used) {
  if (used && mode && mode !== 'disabled') return 'Composed with assistance'
  return 'Composed from ScholarZone records'
}

/** The priority band as a word, so ordering is explained rather than implied. */
export function priorityText(priority) {
  const value = Number(priority)
  if (!Number.isFinite(value)) return 'Suggested'
  if (value <= 10) return 'Start here'
  if (value <= 20) return 'In progress'
  if (value <= 40) return 'Needs attention'
  if (value <= 50) return 'Closing soon'
  return 'When you have time'
}

/** The composer placeholder, phrased as an invitation rather than a command. */
export const COMPOSER_LABEL = 'Ask what to do next'
export const COMPOSER_PLACEHOLDER =
  'What should I do now? You can name a scholarship or application, for example "what is application 9 missing".'