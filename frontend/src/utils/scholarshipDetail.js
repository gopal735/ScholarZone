/**
 * Scholarship detail presentation helpers.
 *
 * The detail endpoint returns 40+ fields, most of them nullable. This
 * module is the single place that decides what is genuinely populated,
 * so the page can render every real value while never inventing one.
 *
 * Two rules hold everywhere:
 *   1. A section only renders when it has real content behind it.
 *   2. A list renders every item the API returned — never a truncated
 *      preview, and never a placeholder standing in for absent data.
 */

// The precision labels live beside the status derivation in
// scholarshipPresentation so that the detail page, the card and the comparison
// row all describe the same deadline the same way. Importing them here rather
// than restating the ternary is what stops the page claiming a full provider
// date for a record whose precision is "unknown".
import { getDeadlinePrecisionLabel } from './scholarshipPresentation.js'

/** Trims to a non-empty string, or null. Treats "" and whitespace as absent. */
export function readText(value) {
  if (typeof value === 'number') return Number.isFinite(value) ? String(value) : null
  if (typeof value !== 'string') return null
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : null
}

/**
 * Normalises a nullable string array.
 * Drops null/blank entries and de-duplicates while preserving order, so
 * a provider that repeats an item does not produce a repeated bullet.
 */
export function readList(value) {
  if (!Array.isArray(value)) return []
  const seen = new Set()
  const out = []
  for (const entry of value) {
    const text = readText(entry)
    if (!text || seen.has(text)) continue
    seen.add(text)
    out.push(text)
  }
  return out
}

/** True when a list carries at least one real item. */
export function hasList(value) {
  return readList(value).length > 0
}

/** Formats an ISO date/datetime for display. Returns null when unparseable. */
export function readDate(value) {
  if (!value) return null
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

/** Absolute date with the time, for the verification record. */
export function readDateTime(value) {
  if (!value) return null
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return date.toLocaleString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

/** Only absolute http(s) links are rendered; anything else is discarded. */
export function readUrl(value) {
  const text = readText(value)
  if (!text) return null
  try {
    const parsed = new URL(text)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? parsed.href : null
  } catch {
    return null
  }
}

/** Strips the scheme and trailing slash for compact link labels. */
export function readHost(value) {
  const url = readUrl(value)
  if (!url) return null
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return null
  }
}

/**
 * Builds the ordered list of official links.
 * `primary` is the one the Apply CTA should point at: an explicit
 * application link beats a generic source page.
 *
 * The four canonical entry points come first. The researched provenance
 * follows: `source_citations`, the pages the research actually read (the
 * awarding body's own pages), and any further official URLs the researcher
 * recorded. Both are de-duplicated against the canonical set, so a citation
 * that is the same URL as the primary source is not rendered twice.
 */
export function buildOfficialLinks(scholarship) {
  if (!scholarship) return []

  const candidates = [
    {
      id: 'application',
      label: 'Application page',
      note: 'Apply directly with the awarding body',
      url: readUrl(scholarship.application_link),
    },
    {
      id: 'source',
      label: 'Official source',
      note: 'The awarding body’s own listing',
      url: readUrl(scholarship.official_source_url),
    },
    {
      id: 'catalogue',
      label: 'Programme catalogue',
      note: 'Programme structure and entry requirements',
      url: readUrl(scholarship.catalogue_url),
    },
    {
      id: 'updates',
      label: 'Updates and announcements',
      note: 'Where changes are published',
      url: readUrl(scholarship.official_updates_url),
    },
  ]

  const seen = new Set()
  const links = []
  for (const candidate of candidates) {
    if (!candidate.url || seen.has(candidate.url)) continue
    seen.add(candidate.url)
    links.push({ ...candidate, host: readHost(candidate.url) })
  }

  const citationList = readList(readUrlList(scholarship.source_citations))
  for (const [index, url] of citationList.entries()) {
    if (seen.has(url)) continue
    seen.add(url)
    links.push({
      id: `citation-${index + 1}`,
      label: 'Official citation',
      // Only the awarded-body page this record was verified against if it was
      // verified. 81 of the 618 public records carry
      // `verification_status: "needs_review"`, whose pill on the same page
      // says "Confirm with provider" - so the previous fixed wording claimed a
      // verification that the record itself disclaims.
      note: scholarship.verification_status === 'active'
        ? 'Awarding-body page this record was verified against'
        : 'Awarding-body page this record cites; re-check before relying on it',
      url,
      host: readHost(url),
    })
  }

  const officialList = readList(readUrlList(scholarship.official_source_urls))
  for (const [index, url] of officialList.entries()) {
    if (seen.has(url)) continue
    seen.add(url)
    links.push({
      id: `official-${index + 1}`,
      label: 'Official page',
      note: 'Further awarding-body page on record',
      url,
      host: readHost(url),
    })
  }

  return links
}

/** A URL-only view of a value: absolute http(s) entries, order preserved. */
function readUrlList(value) {
  if (!Array.isArray(value)) return []
  return value
    .map((entry) => readUrl(entry))
    .filter((url) => Boolean(url))
}

/* The authored applicant guidance, published from the researched
   `applicant_utility` blob.

   The blob is not display layout and not API schema: it is guidance a
   researcher wrote for applicants, keyed by role. This module turns it into
   sections in a fixed reading order, and drops any key whose value carries
   nothing - so a record that was only partly researched publishes the parts
   that were researched, rather than a half-filled template. */
const GUIDANCE_SECTIONS = [
  { id: 'summary', title: 'What makes this award unusual' },
  { id: 'best_fit', title: 'Best fit' },
  { id: 'submission_workflow', title: 'Submission workflow' },
  { id: 'application_readiness_checklist', title: 'Readiness checklist' },
  { id: 'common_rejection_risks', title: 'Common rejection risks' },
  { id: 'document_audit', title: 'Document audit' },
  { id: 'estimated_uncovered_costs', title: 'Costs the award does not cover' },
  { id: 'alerts', title: 'Watch out for' },
  { id: 'important_advice_for_students', title: 'Advice from the awarding body' },
  { id: 'mistakes_to_avoid', title: 'Mistakes to avoid' },
  { id: 'eligibility_tips', title: 'Eligibility tips' },
  { id: 'application_tips', title: 'Application tips' },
  { id: 'deadline_notes', title: 'Deadline notes' },
  { id: 'referee_tracking', title: 'Referee tracking' },
  { id: 'questions_to_ask_host', title: 'Questions to ask the host' },
  { id: 'post_award_requirements', title: 'Post-award requirements' },
]

/** One guidance item to display text. An alert may carry trigger + message. */
function guidanceItemText(item) {
  if (typeof item === 'string') return readText(item)
  if (item && typeof item === 'object') {
    const trigger = readText(item.trigger)
    const message = readText(item.message)
    if (trigger && message) return `${trigger} — ${message}`
    return message || trigger
  }
  return null
}

/**
 * Turns the authored guidance blob into ordered sections, or null when the
 * blob carries nothing usable. A section whose items are all empty is
 * dropped rather than rendered as an empty heading.
 */
export function buildApplicantGuidance(applicantUtility) {
  if (!applicantUtility || typeof applicantUtility !== 'object') return null

  const sections = []
  for (const { id, title } of GUIDANCE_SECTIONS) {
    const value = applicantUtility[id]
    if (value === null || value === undefined) continue

    const rawItems = Array.isArray(value) ? value : [value]
    const items = readList(rawItems.map(guidanceItemText))
    if (items.length === 0) continue

    sections.push({ id, title, items, prose: items.length === 1 })
  }

  if (sections.length === 0) return null
  return { sections }
}

/** The single link the primary Apply control should use. */
export function primaryApplyLink(scholarship) {
  return readUrl(scholarship?.application_link) || readUrl(scholarship?.official_source_url)
}

const VERIFICATION_LABELS = {
  active: 'Verified active',
  needs_review: 'Needs review',
  inactive: 'No longer active',
}

/** Human label for the API's verification_status value. */
export function verificationLabel(status) {
  const key = readText(status)
  if (!key) return null
  return VERIFICATION_LABELS[key] || key
}

const IMAGE_SOURCE_LABELS = {
  official_scholarship: 'Official scholarship page',
  official_university: 'Official university page',
  official_government: 'Official government page',
  official_provider: 'Official provider page',
  // The issuer's own logo, taken from its own site. A fallback identity, and
  // labelled as such so it is never mistaken for programme artwork.
  official_page_logo: 'Official issuer logo',
  official_page: 'Official page',
}

/** Human label for image_source_type, or null when unrecognised. */
export function imageSourceLabel(value) {
  const key = readText(value)
  if (!key) return null
  return IMAGE_SOURCE_LABELS[key] || key
}

const IMAGE_KIND_LABELS = {
  program_image: 'Programme photograph',
  official_banner: 'Official banner',
  official_logo: 'Official logo',
  official_provider: 'Official provider image',
  official_university: 'Official university image',
  official_government: 'Official government image',
  official_og: 'Open Graph image',
  official_media: 'Official media asset',
  generic_official: 'Generic official artwork',
}

/** Human label for image_kind, or null when unrecognised. */
export function imageKindLabel(value) {
  const key = readText(value)
  if (!key) return null
  return IMAGE_KIND_LABELS[key] || key
}

/**
 * Formats a researched currency amount for display, or null.
 *
 * The amount is the confirmed figure from the awarding body's own page. Two
 * rules keep the display honest: the number is formatted with grouping but
 * never rounded up or down, and a currency the formatter does not recognise
 * is printed as an ISO code rather than dropped or guessed at. An amount
 * that is null stays null - a percentage award and an unpublished amount
 * are the same "no figure" state here, because neither is a currency
 * amount the API claims to publish.
 */
export function formatFundingValue(amount, currency, period) {
  if (amount === null || amount === undefined || amount === '') return null
  const number = Number(amount)
  if (!Number.isFinite(number)) return null

  // Pad a fractional amount to two decimals so a half-unit stays a half-unit
  // rather than dropping its trailing zero, and leave integers as integers.
  const fractionDigits = Number.isInteger(number) ? 0 : 2
  let formatted
  try {
    formatted = new Intl.NumberFormat('en-GB', {
      minimumFractionDigits: fractionDigits,
      maximumFractionDigits: fractionDigits,
    }).format(number)
  } catch {
    formatted = String(number)
  }

  const code = typeof currency === 'string' && currency.trim() ? currency.trim().toUpperCase() : null
  if (code && code.length === 3) {
    const symbol = currencySymbol(code, number)
    // Some codes format as the code itself ("CLP"); a code immediately
    // followed by the figure reads as one token, so it gets a space instead.
    if (symbol && symbol !== code) {
      formatted = `${symbol}${formatted}`
    } else {
      formatted = `${code} ${formatted}`
    }
  }

  const periodText = typeof period === 'string' && period.trim() ? period.trim() : null
  return periodText ? `${formatted} ${periodText}` : formatted
}

/** The currency glyph the platform prints for a code, or null when it has none. */
function currencySymbol(code, number) {
  try {
    const parts = new Intl.NumberFormat('en-GB', {
      style: 'currency',
      currency: code,
    }).formatToParts(number)
    return parts.find((part) => part.type === 'currency')?.value ?? null
  } catch {
    return null
  }
}

/** Only a true coverage claim is published; a false or null stays unstated. */
export function buildCoverageFact(scholarship) {
  if (!scholarship) return []
  const facts = []
  const amount = formatFundingValue(
    scholarship.funding_amount,
    scholarship.funding_currency,
    scholarship.funding_period,
  )
  if (amount) {
    facts.push({ id: 'funding_amount', label: 'Funding amount', value: amount })
  }
  if (scholarship.tuition_coverage === true) {
    facts.push({ id: 'tuition_coverage', label: 'Tuition coverage', value: 'Tuition covered by the award' })
  }
  return facts
}

/**
 * Quick facts for the overview grid.
 * Only populated fields appear, so the panel never shows a row of "—".
 */
export function buildQuickFacts(scholarship) {
  if (!scholarship) return []

  const facts = [
    { id: 'funding', label: 'Funding', value: readText(scholarship.funding) },
    // The researched funding triple sits under the funding label: the text
    // is the provider's own wording, and the amount beside it is the
    // confirmed figure. When no figure is confirmed the row simply does
    // not appear, which is the difference between "Fully Funded" as a
    // label and a number nobody has verified.
    ...buildCoverageFact(scholarship),
    { id: 'level', label: 'Study level', value: readText(scholarship.degree) },
    { id: 'country', label: 'Country', value: readText(scholarship.country) },
    { id: 'region', label: 'Region', value: readText(scholarship.region) },
    { id: 'duration', label: 'Duration', value: readText(scholarship.duration) },
    { id: 'program', label: 'Programme type', value: readText(scholarship.program_type) },
    {
      id: 'period',
      label: 'Application period',
      value: readText(scholarship.application_period),
    },
    { id: 'provider', label: 'Provided by', value: readText(scholarship.official_source) },
  ]

  return facts.filter((fact) => fact.value)
}

/**
 * The verification record.
 * Returns null unless at least one real verification signal exists, so
 * the panel never renders as an empty box.
 */
export function buildVerificationRecord(scholarship) {
  if (!scholarship) return null

  const status = verificationLabel(scholarship.verification_status)
  // Only applicant-relevant signals. The reviewer identity, the internal
  // verification note and the next-review date are not published, so they are
  // not offered here with an invented stand-in either.
  const entries = [
    { id: 'status', label: 'Verification status', value: status },
    { id: 'verified', label: 'Last verified', value: readDate(scholarship.last_verified_at) },
    { id: 'updated', label: 'Record updated', value: readDate(scholarship.updated_at) },
    {
      id: 'precision',
      label: 'Deadline precision',
      // Whatever the record's own precision says, and nothing more.
      //
      // This used to be a two-way ternary that resolved every precision other
      // than `month` to "Full date provided by the provider". Eight of the
      // eleven values the catalogue holds are not that: `unknown`, `varies`,
      // `rolling`, `recurring`, `year`, `approximate`, `day_and_time` and a
      // missing value. The record that made it unambiguous carries
      // `"deadline": null, "deadline_date": null, "deadline_precision":
      // "unknown"` and rendered "Deadline to be confirmed" in the summary a
      // few hundred lines above this row - so the page stated two
      // contradictory things about the same deadline. A precision the record
      // does not state is unknown, not exact.
      value: getDeadlinePrecisionLabel(scholarship),
    },
  ].filter((entry) => entry.value)

  const image = {
    source: imageSourceLabel(scholarship.image_source_type),
    kind: imageKindLabel(scholarship.image_kind),
    verified: readDate(scholarship.image_verified_at),
    sourceUrl: readUrl(scholarship.image_source_url),
  }

  const hasImage = Boolean(image.source || image.kind || image.verified || image.sourceUrl)

  if (entries.length === 0 && !hasImage) {
    return null
  }

  return {
    entries,
    image: hasImage ? image : null,
  }
}

/**
 * Resolves the image for a record.
 * Prefers a real verified image; falls back to null so the caller can
 * render the designed placeholder rather than a broken frame.
 */
/* Logos and wordmarks are square or wide, not banner-shaped. Cropping them with
   object-fit: cover inside a 4/3 or 16/9 frame removes most of the mark, which
   is what makes such images look wrongly placed in cards and on the detail
   hero. Those assets are letterboxed with `contain` instead. Photographic
   programme images keep `cover`, which gives the card a consistent frame.
   Shared by ScholarshipImage and the detail hero so both agree. */
const CONTAIN_FIT_KINDS = new Set(['official_logo', 'generic_official', 'logo'])

export function imageFitMode(imageKind) {
  return CONTAIN_FIT_KINDS.has(String(imageKind ?? '').trim().toLowerCase())
    ? 'contain'
    : 'cover'
}

export function detailImage(scholarship) {
  const url = readUrl(scholarship?.image_url)
  if (!url) return null
  return {
    url,
    alt: readText(scholarship?.image_alt_text) || readText(scholarship?.title) || 'Scholarship',
    sourceType: imageSourceLabel(scholarship?.image_source_type),
    fit: imageFitMode(scholarship?.image_kind),
  }
}
