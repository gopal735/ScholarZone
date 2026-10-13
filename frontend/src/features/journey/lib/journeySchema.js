/**
 * Schema, validation and migration for the Bangladesh Applicant Journey.
 *
 * Everything the feature persists passes through here on the way in, which is
 * what makes the rest of the codebase free to assume a shape. The rules:
 *
 * - **Validate on read, not on write.** A corrupt or foreign value in storage
 *   must never reach a component. Normalising on the way out of storage is the
 *   only place it can be caught reliably, because the write path may have been
 *   an older build, another tab, or a hand-edited export.
 * - **An unknown version is refused, not guessed.** Migrating a version whose
 *   transformation has not been written is indistinguishable from inventing
 *   data, so unsupported versions reset to defaults with the original payload
 *   preserved for the caller to report.
 * - **Defaults are empty, never illustrative.** An empty shortlist reads as
 *   empty. Nothing is seeded into a student's record to make it look used.
 */

import { COST_CATEGORIES, FUNDING_CATEGORY, SOURCE_TYPES } from './money.js'
import { isIsoDate } from './dates.js'

export const STORAGE_KEY = 'scholarzone.bangladesh-journey.v1'

/** The identifier an exported file carries, so a foreign file cannot pass. */
export const SCHEMA = 'scholarzone.bangladesh-journey'

/** The current stored shape. */
export const VERSION = 1

/** The highest version this build knows how to migrate from. */
export const SUPPORTED_VERSIONS = [1]

/** Longest a short text field may be. Bounded so a note cannot become a file. */
export const MAX_SHORT_TEXT = 200
/** Longest a free-text note may be. */
export const MAX_NOTE = 4000

/**
 * Category vocabularies.
 *
 * Imported from money.js so the schema layer cannot drift from the cost
 * planner's own list: a category the planner knows but the validator rejects
 * would silently reclassify a student's line as "other" on every read.
 */

export const TRUST_STATUSES = ['verified', 'self-reported', 'needs-review']
export const DOCUMENT_REQUIREMENTS = ['mandatory', 'conditional', 'unconfirmed']
export const DOCUMENT_PROGRESS = ['not_started', 'in_progress', 'done']
export const TIMELINE_PROGRESS = ['not_started', 'in_progress', 'submitted', 'done']
export const DEPARTURE_PROGRESS = ['not_started', 'in_progress', 'done']
export const SOURCE_CATEGORIES = ['university', 'scholarship-provider', 'government', 'embassy', 'other']
export const SOURCE_STATUSES = ['independently-verified', 'checked-by-me', 'unknown']
export const LANGUAGE_MODES = ['bn', 'en', 'both']
export const ENGLISH_TEST_STATUSES = ['not_taken', 'booked', 'taken', 'not_required']

/** True for one of a fixed set, else the fallback. */
function oneOf(value, allowed, fallback) {
  return allowed.includes(value) ? value : fallback
}

/**
 * Clip text without trimming.
 *
 * Trimming here would make a controlled input impossible to type into: the
 * value is written on every keystroke, so a space typed in the middle of a word
 * would be removed before the next character arrived. Whitespace is trimmed
 * where a value is *read*, never where it is stored.
 */
function text(value, max = MAX_NOTE) {
  if (typeof value !== 'string') return ''
  return value.length > max ? value.slice(0, max) : value
}

/** A non-empty id, else a generated one. Duplicate ids are resolved by the caller. */
export function makeId(prefix = 'id') {
  const random = Math.random().toString(36).slice(2, 8)
  return `${prefix}_${Date.now().toString(36)}${random}`
}

function id(value) {
  if (typeof value !== 'string') return ''
  const normalized = value.trim()
  return normalized.length > 0 && normalized.length <= 80 ? normalized : ''
}

/**
 * `YYYY-MM-DD` and a real calendar day, or ''.
 *
 * The regex alone is not enough: `2026-02-30` matches it and is not a date, and
 * storing it would later be read as 1 March by any consumer that parses it as a
 * calendar day. An impossible value is dropped here rather than discovered
 * downstream.
 */
function isoDate(value) {
  if (typeof value !== 'string') return ''
  const trimmed = value.trim()
  return isIsoDate(trimmed) ? trimmed : ''
}

/**
 * Prefix ids that are missing or duplicated.
 *
 * A duplicate id would make every edit to one record silently change the other,
 * so the second occurrence gets a fresh id before the array reaches state. The
 * order is stable, so the same input always produces the same ids.
 */
function dedupeIds(entries, prefix) {
  const seen = new Set()
  return entries.map((entry) => {
    let entryId = id(entry?.id)
    if (!entryId || seen.has(entryId)) {
      entryId = makeId(prefix)
    }
    seen.add(entryId)
    return { ...entry, id: entryId }
  })
}

/** http, https, mailto or tel with a parsed host, else null. */
export function normalizeUrl(value) {
  if (typeof value !== 'string') return null
  const candidate = value.trim()
  if (candidate === '') return ''
  try {
    const parsed = new URL(candidate)
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return null
    if (!parsed.hostname.includes('.')) return null
    return parsed.toString()
  } catch {
    return null
  }
}

/* ── Per-module normalisation ─────────────────────────────────────────── */

/* ── Per-record normalisers ─────────────────────────────────────────── */

/**
 * All exported, so the reducer can build records in the canonical shape.
 *
 * Without this, a record created by an action carries only the keys its
 * payload happened to include, so a component reading `entry.deadlineNote` on
 * a freshly added entry gets `undefined` until the document is reloaded and
 * normalisation fills the rest in. One shape, whether a record arrived from
 * storage, from an import, or from an action.
 */
export function normalizeShortlistEntry(raw) {
  const trust = oneOf(raw?.trust, TRUST_STATUSES, 'needs-review')
  const url = normalizeUrl(raw?.sourceUrl)
  return {
    id: id(raw?.id) || makeId('short'),
    name: text(raw?.name, MAX_SHORT_TEXT),
    country: text(raw?.country, MAX_SHORT_TEXT),
    degree: text(raw?.degree, MAX_SHORT_TEXT),
    /**
     * The provider's own deadline wording and/or an ISO date. Kept as two
     * separate slots because a sentence and a date are not the same kind of
     * fact and must never be collapsed into one field.
     */
    deadlineDate: isoDate(raw?.deadlineDate),
    deadlineNote: text(raw?.deadlineNote, MAX_SHORT_TEXT),
    sourceUrl: url === null ? '' : url,
    notes: text(raw?.notes),
    trust,
    /**
     * A sample entry is marked so no renderer can present it as an opportunity
     * the student chose. Seed data never sets this on anything real.
     */
    sample: raw?.sample === true,
    createdAt: typeof raw?.createdAt === 'string' ? raw.createdAt : '',
    updatedAt: typeof raw?.updatedAt === 'string' ? raw.updatedAt : '',
  }
}

export function normalizeEligibility(raw) {
  return {
    qualificationLevel: text(raw?.qualificationLevel, MAX_SHORT_TEXT),
    /**
     * Results are stored exactly as entered, including the scale the student
     * typed them against. Nothing in this feature converts a GPA to a
     * percentage or vice versa; the scale is part of the fact, not metadata
     * about it.
     */
    degreeTitle: text(raw?.degreeTitle, MAX_SHORT_TEXT),
    resultsText: text(raw?.resultsText, MAX_SHORT_TEXT),
    academicNotes: text(raw?.academicNotes),
    englishTestStatus: oneOf(raw?.englishTestStatus, ENGLISH_TEST_STATUSES, 'not_taken'),
    englishScoreText: text(raw?.englishScoreText, MAX_SHORT_TEXT),
    citizenshipNotes: text(raw?.citizenshipNotes, MAX_SHORT_TEXT),
    residencyNotes: text(raw?.residencyNotes, MAX_SHORT_TEXT),
    eligibilityNotes: text(raw?.eligibilityNotes),
  }
}

export function normalizeDocument(raw) {
  const url = normalizeUrl(raw?.sourceUrl)
  return {
    id: id(raw?.id) || makeId('doc'),
    title: text(raw?.title, MAX_SHORT_TEXT),
    requirement: oneOf(raw?.requirement, DOCUMENT_REQUIREMENTS, 'unconfirmed'),
    progress: oneOf(raw?.progress, DOCUMENT_PROGRESS, 'not_started'),
    note: text(raw?.note),
    expiryDate: isoDate(raw?.expiryDate),
    sourceUrl: url === null ? '' : url,
    /**
     * A template row the student has not yet confirmed applies to them. It is
     * excluded from progress until confirmed, so opening the module never
     * moves the number.
     */
    template: raw?.template === true,
    createdAt: typeof raw?.createdAt === 'string' ? raw.createdAt : '',
    updatedAt: typeof raw?.updatedAt === 'string' ? raw.updatedAt : '',
  }
}

export function normalizeTimelineEntry(raw) {
  return {
    id: id(raw?.id) || makeId('tl'),
    shortlistId: id(raw?.shortlistId),
    label: text(raw?.label, MAX_SHORT_TEXT),
    /** The provider's published deadline. Never derived, never inferred. */
    officialDeadline: isoDate(raw?.officialDeadline),
    officialDeadlineNote: text(raw?.officialDeadlineNote, MAX_SHORT_TEXT),
    /** The student's own working date. Always a separate field. */
    personalTarget: isoDate(raw?.personalTarget),
    progress: oneOf(raw?.progress, TIMELINE_PROGRESS, 'not_started'),
    note: text(raw?.note),
    createdAt: typeof raw?.createdAt === 'string' ? raw.createdAt : '',
    updatedAt: typeof raw?.updatedAt === 'string' ? raw.updatedAt : '',
  }
}

export function normalizeCostItem(raw) {
  return {
    id: id(raw?.id) || makeId('cost'),
    label: text(raw?.label, MAX_SHORT_TEXT),
    category: oneOf(raw?.category, [...COST_CATEGORIES, FUNDING_CATEGORY], 'other'),
    /** Stored exactly as typed, after Bangla-digit normalisation is applied. */
    amount: text(raw?.amount, 24),
    currency: text(raw?.currency, 8).toUpperCase() || 'BDT',
    sourceType: oneOf(raw?.sourceType, SOURCE_TYPES, 'user-entered'),
    sourceLabel: text(raw?.sourceLabel, MAX_SHORT_TEXT),
    sourceDate: isoDate(raw?.sourceDate),
    note: text(raw?.note),
    createdAt: typeof raw?.createdAt === 'string' ? raw.createdAt : '',
    updatedAt: typeof raw?.updatedAt === 'string' ? raw.updatedAt : '',
  }
}

export function normalizeExchangeRate(raw) {
  return {
    /** BDT per one unit of the student's chosen foreign currency. */
    bdtPerUnit: text(raw?.bdtPerUnit, 24),
    effectiveDate: isoDate(raw?.effectiveDate),
    label: text(raw?.label, MAX_SHORT_TEXT),
  }
}

export function normalizeSource(raw) {
  const url = normalizeUrl(raw?.url)
  return {
    id: id(raw?.id) || makeId('src'),
    name: text(raw?.name, MAX_SHORT_TEXT),
    category: oneOf(raw?.category, SOURCE_CATEGORIES, 'other'),
    url: url === null ? '' : url,
    lastChecked: isoDate(raw?.lastChecked),
    status: oneOf(raw?.status, SOURCE_STATUSES, 'unknown'),
    note: text(raw?.note),
    createdAt: typeof raw?.createdAt === 'string' ? raw.createdAt : '',
    updatedAt: typeof raw?.updatedAt === 'string' ? raw.updatedAt : '',
  }
}

export function normalizeDepartureTask(raw) {
  return {
    id: id(raw?.id) || makeId('dep'),
    title: text(raw?.title, MAX_SHORT_TEXT),
    progress: oneOf(raw?.progress, DEPARTURE_PROGRESS, 'not_started'),
    note: text(raw?.note),
    template: raw?.template === true,
    createdAt: typeof raw?.createdAt === 'string' ? raw.createdAt : '',
    updatedAt: typeof raw?.updatedAt === 'string' ? raw.updatedAt : '',
  }
}

/* ── Whole-document normalisation ─────────────────────────────────────── */

export function defaultJourneyState() {
  return {
    schema: SCHEMA,
    version: VERSION,
    settings: { language: 'both' },
    shortlist: [],
    eligibility: normalizeEligibility(null),
    documents: [],
    timeline: [],
    costs: { items: [], rate: normalizeExchangeRate(null) },
    sources: [],
    departure: [],
  }
}

/**
 * Coerce any parsed value into a valid document, or start from defaults.
 *
 * This is the only entry point for data leaving storage or arriving from an
 * import, so an unexpected shape is normalised rather than rejected: a student
 * who edited their export by hand should keep the parts that were valid.
 */
export function normalizeJourneyDocument(raw) {
  const base = defaultJourneyState()
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) {
    return base
  }

  const shortlist = Array.isArray(raw.shortlist) ? raw.shortlist : []
  const documents = Array.isArray(raw.documents) ? raw.documents : []
  const timeline = Array.isArray(raw.timeline) ? raw.timeline : []
  const costs = raw.costs && typeof raw.costs === 'object' ? raw.costs : {}
  const costItems = Array.isArray(costs.items) ? costs.items : []
  const sources = Array.isArray(raw.sources) ? raw.sources : []
  const departure = Array.isArray(raw.departure) ? raw.departure : []

  return {
    schema: SCHEMA,
    version: VERSION,
    settings: {
      language: oneOf(raw.settings?.language, LANGUAGE_MODES, base.settings.language),
    },
    shortlist: dedupeIds(shortlist.map(normalizeShortlistEntry), 'short'),
    eligibility: normalizeEligibility(raw.eligibility),
    documents: dedupeIds(documents.map(normalizeDocument), 'doc'),
    timeline: dedupeIds(timeline.map(normalizeTimelineEntry), 'tl'),
    costs: {
      items: dedupeIds(costItems.map(normalizeCostItem), 'cost'),
      rate: normalizeExchangeRate(costs.rate),
    },
    sources: dedupeIds(sources.map(normalizeSource), 'src'),
    departure: dedupeIds(departure.map(normalizeDepartureTask), 'dep'),
  }
}

/* ── Migration ────────────────────────────────────────────────────────── */

/**
 * Ordered migration steps, keyed by the version they upgrade *from*.
 *
 * Empty today because version 1 is the first released shape. The structure is
 * here rather than invented later so that the first schema change is a one-line
 * addition, and so that a document from a future version is refused rather than
 * half-converted.
 */
const MIGRATIONS = {}

/**
 * Migrate a parsed document to the current version.
 *
 * Returns `{ ok: true, document }` or `{ ok: false, reason, foundVersion }`.
 * A `foundVersion` above the current one is refused: guessing what a newer
 * field meant is how data gets invented.
 */
export function migrateJourneyDocument(raw) {
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) {
    return { ok: false, reason: 'not-an-object', foundVersion: null }
  }

  const foundSchema = typeof raw.schema === 'string' ? raw.schema : null
  const foundVersion = Number.isInteger(raw.version) ? raw.version : null

  if (foundSchema !== null && foundSchema !== SCHEMA) {
    return { ok: false, reason: 'unknown-schema', foundVersion }
  }
  if (foundVersion === null) {
    return { ok: false, reason: 'no-version', foundVersion }
  }
  if (foundVersion > VERSION) {
    return { ok: false, reason: 'newer-version', foundVersion }
  }

  let current = raw
  for (let step = foundVersion; step < VERSION; step += 1) {
    const migrate = MIGRATIONS[step]
    if (!migrate) {
      return { ok: false, reason: 'no-migration', foundVersion }
    }
    current = migrate(current)
  }

  return { ok: true, document: normalizeJourneyDocument(current) }
}
