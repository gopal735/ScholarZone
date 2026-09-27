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

  return candidates
    .filter((candidate) => candidate.url)
    .map((candidate) => ({ ...candidate, host: readHost(candidate.url) }))
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
 * Quick facts for the overview grid.
 * Only populated fields appear, so the panel never shows a row of "—".
 */
export function buildQuickFacts(scholarship) {
  if (!scholarship) return []

  const facts = [
    { id: 'funding', label: 'Funding', value: readText(scholarship.funding) },
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
  const entries = [
    { id: 'status', label: 'Verification status', value: status },
    { id: 'verified', label: 'Last verified', value: readDate(scholarship.last_verified_at) },
    { id: 'due', label: 'Next review due', value: readDate(scholarship.next_verification_due) },
    { id: 'by', label: 'Verified by', value: readText(scholarship.verified_by) },
    { id: 'updated', label: 'Record updated', value: readDate(scholarship.updated_at) },
    {
      id: 'precision',
      label: 'Deadline precision',
      value: scholarship.deadline_precision === 'month'
        ? 'Month only — the provider has not published a full date'
        : 'Full date provided by the provider',
    },
  ].filter((entry) => entry.value)

  const image = {
    source: imageSourceLabel(scholarship.image_source_type),
    kind: imageKindLabel(scholarship.image_kind),
    verified: readDate(scholarship.image_verified_at),
    sourceUrl: readUrl(scholarship.image_source_url),
  }

  const hasImage = Boolean(image.source || image.kind || image.verified || image.sourceUrl)

  if (entries.length === 0 && !hasImage && !readText(scholarship.verification_notes)) {
    return null
  }

  return {
    entries,
    notes: readText(scholarship.verification_notes),
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
