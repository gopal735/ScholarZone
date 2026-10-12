/**
 * Money primitives for the Bangladesh Applicant Journey.
 *
 * The governing rule: an amount the student typed is a string, and it stays a
 * string until it is proven to be a number. Nothing here rounds silently,
 * substitutes a rate the student did not supply, or turns a self-entered figure
 * into an official one.
 *
 * Three consequences of that rule are worth naming, because each one is a
 * defect in a naive implementation:
 *
 * - **Bangla digits are normalised, not rejected.** A student typing ৫০,০০০ in a
 *   Bangla keyboard is entering fifty thousand. Normalising on the way into
 *   arithmetic, while keeping the original text visible, is the only behaviour
 *   that is both correct and honest.
 * - **A negative amount is an error, not zero.** Clamping to zero would make a
 *   typo look like a deliberate entry of nothing.
 * - **Totals carry their provenance.** A total built partly from estimates says
 *   so, forever, in every surface that shows it.
 */

export const AMOUNT_MAX = 999_999_999_999

/** Accepted thousands and decimal separators in a typed amount. */
const AMOUNT_SHAPE = /^-?\d+(\.\d+)?$/
const SEPARATORS = /[,\s_]/g

/**
 * The ten Bangla digits, U+09E6..U+09EF.
 *
 * The range matters and is easy to get wrong: U+09E0..U+09E5 are Bengali
 * currency signs, not digits, so starting the table at U+09E0 shifts every
 * index by six and maps ০ to a rupee symbol instead of zero. The digit
 * conversion is defined by index, so this array must be exactly ten entries
 * in ascending order.
 */
const BANGLA_DIGITS = [
  '\u09E6', '\u09E7', '\u09E8', '\u09E9', '\u09EA',
  '\u09EB', '\u09EC', '\u09ED', '\u09EE', '\u09EF',
]

/**
 * Convert Bangla digits ০–৯ to ASCII, leaving everything else untouched.
 *
 * Applied per character so a mixed string keeps its non-digits, and so a
 * non-string input is returned unchanged rather than thrown.
 */
export function normalizeBanglaDigits(value) {
  if (typeof value !== 'string') return value
  let out = ''
  for (const char of value) {
    const index = BANGLA_DIGITS.indexOf(char)
    out += index === -1 ? char : String(index)
  }
  return out
}

/** True when the raw text contains at least one Bangla digit. */
export function hasBanglaDigits(value) {
  if (typeof value !== 'string') return false
  return BANGLA_DIGITS.some((digit) => value.includes(digit))
}

/**
 * Normalise a typed amount into a plain decimal string, or explain why it
 * cannot be.
 *
 * Returns `{ ok: true, value: string }` where `value` is a canonical decimal
 * string with separators removed and Bangla digits converted, or
 * `{ ok: false, reason: 'empty' | 'not-a-number' | 'negative' | 'too-large' }`.
 *
 * The result is a *string*, not a Number, because a Number silently loses the
 * student's own precision and a 17-digit amount would become 1e17. The string
 * is only parsed at the point of arithmetic.
 */
export function normalizeAmount(raw) {
  if (typeof raw !== 'string') {
    return { ok: false, reason: 'empty' }
  }
  const withAscii = normalizeBanglaDigits(raw)
  const stripped = withAscii.trim().replace(SEPARATORS, '')
  if (stripped === '') {
    return { ok: false, reason: 'empty' }
  }
  if (!AMOUNT_SHAPE.test(stripped)) {
    return { ok: false, reason: 'not-a-number' }
  }
  if (stripped.startsWith('-')) {
    return { ok: false, reason: 'negative' }
  }
  // Two decimal places is the ceiling a fee, a fare or a stipend is ever quoted
  // in. A third place is almost always a typo, and accepting it would produce a
  // total that looks more precise than its inputs.
  const [whole, fraction = ''] = stripped.split('.')
  const trimmedFraction = fraction.slice(0, 2)
  const canonical = trimmedFraction ? `${whole}.${trimmedFraction}` : whole
  const numeric = Number(canonical)
  if (!Number.isFinite(numeric)) {
    return { ok: false, reason: 'not-a-number' }
  }
  if (numeric > AMOUNT_MAX) {
    return { ok: false, reason: 'too-large' }
  }
  return { ok: true, value: canonical }
}

/** A normalised amount as a Number, or null when it is not usable. */
export function amountToNumber(normalized) {
  if (!normalized || normalized.ok !== true) return null
  const value = Number(normalized.value)
  return Number.isFinite(value) ? value : null
}

/** Decimal addition on canonical strings, returning a canonical string. */
function addStrings(a, b) {
  const scale = 100
  const left = Math.round(Number(a) * scale)
  const right = Math.round(Number(b) * scale)
  const total = (left + right) / scale
  return total.toFixed(2).replace(/\.?0+$/, '') || '0'
}

/**
 * Convert an amount into BDT using a rate the student supplied.
 *
 * Returns null when either the amount or the rate is unusable. The function
 * never falls back to a remembered rate: an approximate conversion without a
 * stated rate is the single easiest way to mislead someone planning a budget.
 */
export function convertToBdt(amountRaw, bdtPerUnitRaw) {
  const amount = amountToNumber(normalizeAmount(amountRaw))
  const rate = amountToNumber(normalizeAmount(bdtPerUnitRaw))
  if (amount === null || rate === null || rate <= 0) return null
  const converted = (amount * rate).toFixed(2)
  return { amount: converted, rateUsed: String(rate) }
}

/**
 * Sum a set of amounts in one currency.
 *
 * Returns `{ total: string, usable: boolean }`. `usable` is false when at least
 * one entry could not be read, because a sum that silently skips an unreadable
 * entry understates the total and looks authoritative.
 */
export function sumAmounts(rawValues) {
  let total = '0'
  let usable = true
  for (const raw of rawValues) {
    if (raw === null || raw === undefined || String(raw).trim() === '') {
      usable = false
      continue
    }
    const normalized = normalizeAmount(String(raw))
    if (!normalized.ok) {
      usable = false
      continue
    }
    total = addStrings(total, normalized.value)
  }
  return { total, usable }
}

/** The cost categories the planner records. Funding is separate by design. */
export const COST_CATEGORIES = [
  'tuition',
  'living',
  'travel',
  'insurance',
  'visa',
  'other',
]

export const FUNDING_CATEGORY = 'funding'

/** Every provenance label a figure may carry. */
export const SOURCE_TYPES = ['official', 'user-entered', 'estimate']
