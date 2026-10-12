/**
 * Browser-local storage for the SOP Builder.
 *
 * The precedent this follows is `planStorage.js`, and deliberately so: the
 * planning workspace is the existing, reviewed example of a browser-local
 * student workspace in this codebase, and a second, different approach to
 * localStorage would be a second thing to get wrong. The same three rules apply
 * and are the reason this is a service rather than a component writing
 * `localStorage` directly:
 *
 *   1. It is never described as cloud-synced. The copy in the UI says the data
 *      is in this browser, because it is. There is no server endpoint for this
 *      feature and no account is involved.
 *   2. A write that fails is not retried as if it succeeded. `localStorage`
 *      throws when it is full or disabled (Safari private mode, storage
 *      partitioning), and the caller is told so rather than being shown a
 *      control that appears to work.
 *   3. Nothing is fabricated. A section the student never wrote reads as empty,
 *      never as a starter paragraph, and no default text is ever inserted.
 *
 * The key naming follows the convention already in the repository -
 * `scholarzone.<feature>.v<N>` - so a future schema change can bump the suffix
 * without colliding with an older build's data.
 */

import { SOP_SECTIONS } from './sopBuilderSections.js'

const STORAGE_KEY = 'scholarzone.sop-builder.v1'

/** The schema identifier an exported/imported plan carries. */
export const SCHEMA = 'scholarzone.sop-builder'

/** The version of the stored shape. */
export const VERSION = 1

/**
 * Longest free-text field the builder will store.
 *
 * Bounded so a student's workspace cannot become an unbounded filing system,
 * which is the same reason `MAX_NOTES_LENGTH` exists on the application
 * workspace. A draft is long; it is not unbounded.
 */
export const MAX_FIELD_LENGTH = 20000

/** Longest the student may call an institution or programme name. */
export const MAX_CONTEXT_FIELD_LENGTH = 200

/**
 * The fields the student fills in about their own background.
 *
 * Every one of these is the student's own account of themselves. Nothing in this
 * feature may fill one in, suggest content for one, or derive one from the
 * catalogue - inventing an achievement into a student's record is the single
 * failure the whole feature exists to avoid.
 */
export const BACKGROUND_FIELDS = Object.freeze([
  { id: 'academic', label: 'Academic background', hint: 'Degrees, institutions, GPA or class, key coursework.' },
  { id: 'projects', label: 'Projects and research', hint: 'What you built, ran or tested, and your own role.' },
  { id: 'achievements', label: 'Achievements', hint: 'Awards, publications, scholarships, results.' },
  { id: 'motivation', label: 'Motivation', hint: 'What draws you to this field and this programme.' },
  { id: 'goals', label: 'Goals', hint: 'What you want to be able to do afterwards.' },
  { id: 'constraints', label: 'Anything relevant to explain', hint: 'Gaps, changes of direction, circumstances you choose to explain.' },
])

function canUseStorage() {
  try {
    return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined'
  } catch {
    // A sandboxed iframe throws on access rather than returning undefined.
    return false
  }
}

function readJson(key, fallback) {
  if (!canUseStorage()) {
    return fallback
  }

  try {
    const raw = window.localStorage.getItem(key)
    if (!raw) {
      return fallback
    }
    const parsed = JSON.parse(raw)
    return parsed === null || parsed === undefined ? fallback : parsed
  } catch {
    // Corrupt JSON is treated as absent rather than crashing the page; the next
    // write replaces it, exactly as `planStorage` does.
    return fallback
  }
}

function writeJson(key, value) {
  if (!canUseStorage()) {
    return false
  }

  try {
    window.localStorage.setItem(key, JSON.stringify(value))
    return true
  } catch {
    return false
  }
}

/**
 * Clip a free-text field to its maximum.
 *
 * A string is returned unchanged when it is within the limit, sliced when it is
 * over, and an empty string when it is not a string at all. It never returns
 * null for a textarea's value, because a controlled textarea bound to null
 * becomes uncontrolled and the field stops tracking what the student typed.
 */
function clipText(value, max = MAX_FIELD_LENGTH) {
  if (typeof value !== 'string') {
    return ''
  }
  return value.length > max ? value.slice(0, max) : value
}

/**
 * Clip a short context field to its maximum.
 *
 * Deliberately does **not** trim. Trimming on write made the fields impossible
 * to type into: a controlled input writes the value on every keystroke, so
 * typing "University of Bristol" stored "University", then "Universityo", then
 * "Universityoo" - every space was removed the moment it was typed, and the
 * student could not enter a two-word institution at all.
 *
 * Stray leading and trailing whitespace is trimmed where the value is *used* -
 * in `wordLimitIsAuthoritative`, in the review engine's relevance check and in
 * the export's file stem - so nothing downstream sees junk, and a student can
 * still type a space mid-word.
 */
function clipContext(value) {
  return clipText(value, MAX_CONTEXT_FIELD_LENGTH)
}

/** The trimmed form of a short context field, for anything comparing it. */
export function trimmedContextField(value) {
  return typeof value === 'string' ? value.trim() : ''
}

/** An empty background record, so a read never has to guess a shape. */
function emptyBackground() {
  const background = {}
  for (const field of BACKGROUND_FIELDS) {
    background[field.id] = ''
  }
  return background
}

/** An empty section map keyed by section id. */
function emptySections() {
  const sections = {}
  for (const section of SOP_SECTIONS) {
    sections[section.id] = { text: '', updated_at: null }
  }
  return sections
}

/**
 * Normalise a word limit entered by the student.
 *
 * Returns a positive integer or null. A limit of 0, a negative number, a
 * non-integer and a non-numeric string all become null, because each of those
 * is a limit that cannot be checked against a word count. The student's own
 * typed value is kept separately, in `word_limit_source`, so the builder can
 * report that a limit is recorded but unverified.
 */
export function normalizeWordLimit(value) {
  if (value === null || value === undefined || value === '') {
    return null
  }
  const numeric = typeof value === 'number' ? value : Number(String(value).trim())
  if (!Number.isFinite(numeric)) {
    return null
  }
  const rounded = Math.round(numeric)
  return rounded > 0 ? rounded : null
}

/**
 * Whether a recorded word limit is authoritative.
 *
 * A limit counts as authoritative only when it has a source the student
 * recorded. A number typed with no source is a note to self, and reporting
 * "over your limit" against it would be asserting an official constraint that
 * nobody published. This is the whole rule, in one predicate.
 */
export function wordLimitIsAuthoritative(draft) {
  const limit = normalizeWordLimit(draft?.context?.word_limit)
  const source = typeof draft?.context?.word_limit_source === 'string'
    ? draft.context.word_limit_source.trim()
    : ''
  return limit !== null && source !== ''
}

/** Normalise the whole stored draft into the current shape. */
function normalizeDraft(raw) {
  const empty = {
    schema: SCHEMA,
    version: VERSION,
    device_local: true,
    updated_at: null,
    context: {
      application_type: '',
      institution: '',
      programme: '',
      scholarship_name: '',
      official_prompt: '',
      word_limit: null,
      word_limit_source: '',
    },
    background: emptyBackground(),
    sections: emptySections(),
    substantiation: {},
    approval: null,
  }

  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) {
    return empty
  }

  const context = raw.context && typeof raw.context === 'object' && !Array.isArray(raw.context)
    ? raw.context
    : {}

  const background = emptyBackground()
  if (raw.background && typeof raw.background === 'object' && !Array.isArray(raw.background)) {
    for (const field of BACKGROUND_FIELDS) {
      if (typeof raw.background[field.id] === 'string') {
        background[field.id] = clipText(raw.background[field.id])
      }
    }
  }

  const sections = emptySections()
  if (raw.sections && typeof raw.sections === 'object' && !Array.isArray(raw.sections)) {
    for (const section of SOP_SECTIONS) {
      const stored = raw.sections[section.id]
      if (stored && typeof stored === 'object' && !Array.isArray(stored)) {
        sections[section.id] = {
          text: clipText(stored.text),
          updated_at: typeof stored.updated_at === 'string' ? stored.updated_at : null,
        }
      }
    }
  }

  const substantiation = {}
  if (raw.substantiation && typeof raw.substantiation === 'object' && !Array.isArray(raw.substantiation)) {
    for (const [key, value] of Object.entries(raw.substantiation)) {
      if (!value || typeof value !== 'object' || Array.isArray(value)) {
        continue
      }
      if (value.status !== 'confirmed' && value.status !== 'removed') {
        continue
      }
      substantiation[key] = {
        status: value.status,
        evidence: clipText(value.evidence, 4000),
        updated_at: typeof value.updated_at === 'string' ? value.updated_at : null,
      }
    }
  }

  const approval = raw.approval && typeof raw.approval === 'object' && !Array.isArray(raw.approval)
    ? {
        confirmed: raw.approval.confirmed === true,
        confirmed_at: typeof raw.approval.confirmed_at === 'string' ? raw.approval.confirmed_at : null,
      }
    : null

  return {
    schema: SCHEMA,
    version: VERSION,
    // Always true. Stored rather than displayed, so an exported file carries the
    // same honest caveat with it, the way `exportPlan` does.
    device_local: true,
    updated_at: typeof raw.updated_at === 'string' ? raw.updated_at : null,
    context: {
      application_type: clipContext(context.application_type),
      institution: clipContext(context.institution),
      programme: clipContext(context.programme),
      scholarship_name: clipContext(context.scholarship_name),
      // The student's own paste of a provider's prompt. Stored verbatim and
      // labelled as theirs wherever it is shown; this feature never claims to
      // have verified it against the provider.
      official_prompt: clipText(context.official_prompt, 8000),
      word_limit: normalizeWordLimit(context.word_limit),
      word_limit_source: clipContext(context.word_limit_source),
    },
    background,
    sections,
    substantiation,
    approval,
  }
}

/* ── Reads ─────────────────────────────────────────────────────────── */

/** The whole draft, normalised. Never null, never throwing. */
export function readDraft() {
  return normalizeDraft(readJson(STORAGE_KEY, null))
}

/** One section's text. */
export function readSection(sectionId) {
  const draft = readDraft()
  const section = draft.sections[sectionId]
  return section && typeof section.text === 'string' ? section.text : ''
}

/** One background field's text. */
export function readBackgroundField(fieldId) {
  const draft = readDraft()
  return typeof draft.background[fieldId] === 'string' ? draft.background[fieldId] : ''
}

/**
 * Word count for one string.
 *
 * Whitespace-delimited, so a student who writes in a language that does not use
 * spaces still gets a count of some kind rather than a zero that reads as an
 * empty draft. It is a count, not a tokeniser: it does not claim to match any
 * provider's counting method, and the UI says so where a limit is checked.
 */
export function countWords(text) {
  if (typeof text !== 'string') {
    return 0
  }
  const trimmed = text.trim()
  return trimmed === '' ? 0 : trimmed.split(/\s+/).length
}

/* ── Writes ────────────────────────────────────────────────────────── */

/**
 * Replace the whole draft. Returns true when the write succeeded.
 *
 * This is the only write path. Every narrower operation reads, mutates and calls
 * this, so there is exactly one place a write can fail and exactly one place a
 * failure has to be reported.
 */
export function writeDraft(next) {
  const normalized = normalizeDraft({ ...next, device_local: true })
  return writeJson(STORAGE_KEY, { ...normalized, updated_at: new Date().toISOString() })
}

/** Patch the context fields. Returns true when the write succeeded. */
export function writeContext(patch) {
  const draft = readDraft()
  const context = { ...draft.context }
  for (const [key, value] of Object.entries(patch || {})) {
    if (!(key in context)) {
      continue
    }
    context[key] = value
  }
  return writeDraft({ ...draft, context })
}

/** Patch the background fields. Returns true when the write succeeded. */
export function writeBackground(patch) {
  const draft = readDraft()
  const background = { ...draft.background }
  for (const [key, value] of Object.entries(patch || {})) {
    if (!(key in background)) {
      continue
    }
    background[key] = typeof value === 'string' ? clipText(value) : background[key]
  }
  return writeDraft({ ...draft, background })
}

/**
 * Write one section's text. Returns true when the write succeeded.
 *
 * A non-string is refused rather than coerced, which is what
 * `planStorage.writeScholarshipNote` does too: a caller passing a number here is
 * a programming error, and storing `""` for it would report success for a write
 * that lost the value.
 */
export function writeSection(sectionId, text) {
  const known = SOP_SECTIONS.some((section) => section.id === sectionId)
  if (!known) {
    return false
  }
  if (typeof text !== 'string') {
    return false
  }
  const draft = readDraft()
  const sections = { ...draft.sections }
  sections[sectionId] = { text: clipText(text), updated_at: new Date().toISOString() }
  return writeDraft({ ...draft, sections })
}

/**
 * Record that a claim was substantiated or removed.
 *
 * `evidence` is the student's own account of why the claim is true. This feature
 * supplies nothing and suggests nothing: an empty evidence string on a
 * `confirmed` claim is stored as-is, because refusing it would be the builder
 * putting words in a student's mouth, and accepting it silently would be worse.
 * The review engine treats a confirmed-but-unevidenced claim as still needing
 * attention, which is the honest handling.
 */
export function writeSubstantiation(claimKey, status, evidence) {
  if (status !== 'confirmed' && status !== 'removed') {
    return false
  }
  const draft = readDraft()
  const substantiation = { ...draft.substantiation }
  substantiation[claimKey] = {
    status,
    evidence: clipText(evidence, 4000),
    updated_at: new Date().toISOString(),
  }
  return writeDraft({ ...draft, substantiation })
}

/** Remove one substantiation record, so the claim is unevaluated again. */
export function clearSubstantiation(claimKey) {
  const draft = readDraft()
  if (!(claimKey in draft.substantiation)) {
    return true
  }
  const substantiation = { ...draft.substantiation }
  delete substantiation[claimKey]
  return writeDraft({ ...draft, substantiation })
}

/**
 * Record or clear the student's final approval.
 *
 * The approval is a statement the student makes about their own draft, and it is
 * stored because the alternative - a button that just navigates on - leaves no
 * record that the review step was ever reached. It is never set to true by the
 * builder itself.
 */
export function writeApproval(confirmed) {
  const draft = readDraft()
  return writeDraft({
    ...draft,
    approval: confirmed === true ? { confirmed: true, confirmed_at: new Date().toISOString() } : null,
  })
}

/** Clear every section, leaving the context and background intact. */
export function clearAllSections() {
  const draft = readDraft()
  return writeDraft({ ...draft, sections: emptySections(), approval: null })
}

/**
 * Erase the whole workspace from this browser.
 *
 * A write of the empty draft rather than a `removeItem`, so the next read still
 * returns the right shape rather than depending on the storage being empty. The
 * label on the control that calls this says exactly what it erases and nothing
 * more: there is no server-side store for this feature, so there is no second
 * thing to claim.
 */
export function eraseEverything() {
  return writeDraft(normalizeDraft(null))
}

/* ── Export / import ───────────────────────────────────────────────── */

/**
 * Everything this module owns, as a plain object.
 *
 * Exported as a versioned envelope rather than the raw fields, so an import can
 * tell "a ScholarZone SOP draft" from any other JSON a student might have
 * pointed at it.
 */
export function exportDraft() {
  const draft = readDraft()
  return {
    schema: SCHEMA,
    version: VERSION,
    exported_at: new Date().toISOString(),
    // False is not an option here, and it is stated in the payload so a restored
    // file carries the same honest caveat with it.
    device_local: true,
    draft,
  }
}

/**
 * Restore from a previously exported draft.
 *
 * Validates before it writes anything. A file that is not the expected shape is
 * rejected with a reason rather than partially applied, so a student who points
 * at the wrong file is told so instead of silently losing half their draft.
 *
 * @returns {{ok: true} | {ok: false, reason: string}}
 */
export function importDraft(payload) {
  if (payload === null || typeof payload !== 'object' || Array.isArray(payload)) {
    return { ok: false, reason: 'This file is not a ScholarZone SOP Builder export.' }
  }

  if (payload.schema !== SCHEMA) {
    return { ok: false, reason: 'This file does not declare itself a ScholarZone SOP Builder export.' }
  }

  if (payload.version !== VERSION) {
    return {
      ok: false,
      reason: `Unsupported SOP Builder export version ${JSON.stringify(payload.version)}.`,
    }
  }

  const inner = payload.draft
  if (inner === null || typeof inner !== 'object' || Array.isArray(inner)) {
    return { ok: false, reason: 'This export does not contain a draft.' }
  }

  // Normalised first, then written whole, so a rejected file cannot leave a
  // half-restored draft behind.
  const normalized = normalizeDraft(inner)
  if (!writeDraft(normalized)) {
    return { ok: false, reason: 'This browser refused to store the draft (storage may be full or disabled).' }
  }

  return { ok: true }
}

/** The full local store, as one object a component can use. */
export const sopBuilderStorage = {
  readDraft,
  readSection,
  readBackgroundField,
  countWords,
  writeDraft,
  writeContext,
  writeBackground,
  writeSection,
  writeSubstantiation,
  clearSubstantiation,
  writeApproval,
  clearAllSections,
  eraseEverything,
  exportDraft,
  importDraft,
}
