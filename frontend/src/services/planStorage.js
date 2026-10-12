/**
 * Browser-local planning state: recently viewed, per-scholarship notes, and an
 * application-progress checklist.
 *
 * This is the anonymous half of the workspace. The signed-in half already
 * exists and is server-backed - `/dashboard/applications` holds a weighted
 * checklist, private notes and a state machine, and `/dashboard/saved` holds
 * the shortlist. That is not duplicated here. What this module adds is the part
 * that has to work before anyone creates an account: a record of what was
 * opened, a place to write a note while reading, and a checklist a student can
 * tick through against a saved scholarship.
 *
 * Three rules hold throughout, and they are the reason this is a service rather
 * than three components writing `localStorage` directly:
 *
 *   1. It is never described as cloud-synced. The copy in the UI says the data
 *      is in this browser, because it is.
 *   2. A write that fails is not retried as if it succeeded. `localStorage`
 *      throws when it is full or disabled (Safari private mode, storage
 *      partitioning), and the caller is told so instead of being shown a
 *      control that appears to work.
 *   3. Nothing is fabricated. A record that was never viewed produces an empty
 *      list, not a placeholder entry.
 *
 * The key naming follows the convention already in the repository -
 * `scholarzone.<feature>.v<N>` - so a future schema change can bump the suffix
 * without colliding.
 */

const RECENTLY_VIEWED_KEY = 'scholarzone.recently-viewed.v1'
const SCHOLARSHIP_NOTES_KEY = 'scholarzone.plan-notes.v1'
const CHECKLIST_KEY = 'scholarzone.plan-checklist.v1'

/** How many recently-viewed ids to retain. */
export const RECENTLY_VIEWED_LIMIT = 12

/** How many characters a note may hold. */
export const MAX_NOTE_LENGTH = 4000

/** The checklist items offered per scholarship. */
export const CHECKLIST_ITEMS = Object.freeze([
  { value: 'read-details', label: 'Read the full scholarship page' },
  { value: 'open-official-source', label: 'Open the official provider page' },
  { value: 'check-eligibility', label: 'Check every eligibility rule against your profile' },
  { value: 'gather-documents', label: 'Gather the required documents' },
  { value: 'language-test', label: 'Book the language test if one is required' },
  { value: 'referees', label: 'Ask referees for a letter' },
  { value: 'personal-statement', label: 'Draft the personal statement' },
  { value: 'submit', label: 'Submit the application' },
])

function canUseStorage() {
  try {
    return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined'
  } catch {
    // A sandboxed iframe throws on access rather than returning undefined.
    return false
  }
}

/**
 * Normalise one id to the form the rest of the app reads, or null.
 *
 * The pattern is the one `clientPreferenceStorage` already uses, so an id
 * written here is findable by the same `String(scholarship.id) === id` lookup
 * the shortlist and the comparison use.
 *
 * A finite number is accepted and stringified, because a route parameter or a
 * dataset field genuinely arrives as one. `null`, `undefined`, a boolean and
 * anything else are refused: `String(null)` is the four characters "null",
 * which passes a naive character-class check perfectly well, and an id of
 * "null" would be stored as a real viewing history for a scholarship that does
 * not exist.
 */
function normalizeId(value) {
  if (typeof value === 'number') {
    return Number.isFinite(value) ? String(value) : null
  }
  if (typeof value !== 'string') {
    return null
  }
  const normalized = value.trim()
  return normalized === '' ? null : (/^[a-zA-Z0-9_-]{1,64}$/.test(normalized) ? normalized : null)
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
    // Corrupt JSON is treated as absent rather than crashing the page, and a
    // later write replaces it.
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

function readStringMap(key) {
  const raw = readJson(key, {})
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) {
    return {}
  }

  const map = {}
  for (const [id, value] of Object.entries(raw)) {
    const normalized = normalizeId(id)
    if (!normalized) {
      continue
    }
    if (typeof value !== 'string') {
      continue
    }
    map[normalized] = value
  }
  return map
}

function readCheckedMap(key) {
  const raw = readJson(key, {})
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) {
    return {}
  }

  const map = {}
  for (const [id, value] of Object.entries(raw)) {
    const normalized = normalizeId(id)
    if (!normalized || !Array.isArray(value)) {
      continue
    }
    // Only the known item values are retained, so a renamed item in a future
    // release cannot leave an unremovable tick behind.
    const known = new Set(CHECKLIST_ITEMS.map((item) => item.value))
    map[normalized] = [...new Set(value.filter((entry) => known.has(entry)))].sort()
  }
  return map
}

/* ── Recently viewed ─────────────────────────────────────────────────── */

/** Most-recent-first ids, already de-duplicated and capped. */
export function readRecentlyViewed() {
  const raw = readJson(RECENTLY_VIEWED_KEY, [])
  if (!Array.isArray(raw)) {
    return []
  }

  const seen = new Set()
  const ids = []
  for (const value of raw) {
    const normalized = normalizeId(value)
    if (!normalized || seen.has(normalized)) {
      continue
    }
    seen.add(normalized)
    ids.push(normalized)
    if (ids.length >= RECENTLY_VIEWED_LIMIT) {
      break
    }
  }
  return ids
}

/**
 * Record a view. Returns true when the write succeeded.
 *
 * The id becomes the most recent entry, and any earlier occurrence is removed,
 * so the list is a recency order rather than a first-seen order.
 */
export function pushRecentlyViewed(id) {
  const normalized = normalizeId(id)
  if (!normalized) {
    return false
  }

  const next = [normalized, ...readRecentlyViewed().filter((entry) => entry !== normalized)]
    .slice(0, RECENTLY_VIEWED_LIMIT)

  return writeJson(RECENTLY_VIEWED_KEY, next)
}

export function clearRecentlyViewed() {
  return writeJson(RECENTLY_VIEWED_KEY, [])
}

/* ── Per-scholarship notes ───────────────────────────────────────────── */

/** Every note, keyed by scholarship id. */
export function readScholarshipNotes() {
  return readStringMap(SCHOLARSHIP_NOTES_KEY)
}

/**
 * Read one note. An id with no stored note returns an empty string, which is
 * what a controlled textarea expects - never `null`, and never a placeholder.
 */
export function readScholarshipNote(id) {
  const normalized = normalizeId(id)
  if (!normalized) {
    return ''
  }
  const notes = readScholarshipNotes()
  return typeof notes[normalized] === 'string' ? notes[normalized] : ''
}

/** Write one note. An empty string removes the entry rather than storing it. */
export function writeScholarshipNote(id, note) {
  const normalized = normalizeId(id)
  if (!normalized) {
    return false
  }

  if (typeof note !== 'string') {
    return false
  }

  const trimmed = note.slice(0, MAX_NOTE_LENGTH)
  const notes = readScholarshipNotes()

  if (trimmed.trim() === '') {
    delete notes[normalized]
  } else {
    notes[normalized] = trimmed
  }

  return writeJson(SCHOLARSHIP_NOTES_KEY, notes)
}

export function deleteScholarshipNote(id) {
  const normalized = normalizeId(id)
  if (!normalized) {
    return false
  }
  const notes = readScholarshipNotes()
  if (!(normalized in notes)) {
    return true
  }
  delete notes[normalized]
  return writeJson(SCHOLARSHIP_NOTES_KEY, notes)
}

/* ── Application-progress checklist ──────────────────────────────────── */

/** Every checklist, keyed by scholarship id. */
export function readChecklists() {
  return readCheckedMap(CHECKLIST_KEY)
}

export function readChecklist(id) {
  const normalized = normalizeId(id)
  if (!normalized) {
    return []
  }
  const checklists = readChecklists()
  return Array.isArray(checklists[normalized]) ? checklists[normalized] : []
}

/** Set one checklist item for one scholarship. */
export function setChecklistItem(id, item, checked) {
  const normalized = normalizeId(id)
  if (!normalized) {
    return false
  }

  const known = new Set(CHECKLIST_ITEMS.map((entry) => entry.value))
  if (!known.has(item)) {
    return false
  }

  const checklists = readChecklists()
  const current = Array.isArray(checklists[normalized]) ? checklists[normalized] : []

  const next = checked === false
    ? current.filter((entry) => entry !== item)
    : [...new Set([...current, item])].sort()

  checklists[normalized] = next
  return writeJson(CHECKLIST_KEY, checklists)
}

export function clearChecklist(id) {
  const normalized = normalizeId(id)
  if (!normalized) {
    return false
  }
  const checklists = readChecklists()
  if (!(normalized in checklists)) {
    return true
  }
  delete checklists[normalized]
  return writeJson(CHECKLIST_KEY, checklists)
}

/** Progress for one scholarship as a fraction of the checklist. */
export function getChecklistProgress(id) {
  const checked = readChecklist(id)
  return {
    checked: checked.length,
    total: CHECKLIST_ITEMS.length,
    // A fraction rather than a percentage, so the consumer formats it once.
    fraction: CHECKLIST_ITEMS.length === 0 ? 0 : checked.length / CHECKLIST_ITEMS.length,
    complete: checked.length === CHECKLIST_ITEMS.length,
  }
}

/* ── Export / import ─────────────────────────────────────────────────── */

/**
 * Everything this module owns, as a plain object.
 *
 * Exported deliberately as a versioned envelope rather than the three raw
 * objects separately, so an import can tell "a ScholarZone plan" from any
 * other JSON a student might have pointed at it.
 */
export function exportPlan() {
  return {
    schema: 'scholarzone.plan',
    version: 1,
    exported_at: new Date().toISOString(),
    // False, and stated in the payload itself, so a restored file carries the
    // same honest caveat with it.
    device_local: true,
    recently_viewed: readRecentlyViewed(),
    notes: readScholarshipNotes(),
    checklists: readChecklists(),
  }
}

/**
 * Restore from a previously exported plan.
 *
 * Validates before it writes anything. A file that is not the expected shape
 * is rejected with a reason rather than partially applied, so a student who
 * points at the wrong file is told so instead of silently losing half their
 * notes.
 *
 * @returns {{ok: true} | {ok: false, reason: string}}
 */
export function importPlan(payload) {
  if (payload === null || typeof payload !== 'object' || Array.isArray(payload)) {
    return { ok: false, reason: 'This file is not a ScholarZone plan export.' }
  }

  if (payload.schema !== 'scholarzone.plan') {
    return { ok: false, reason: 'This file does not declare itself a ScholarZone plan export.' }
  }

  if (payload.version !== 1) {
    return { ok: false, reason: `Unsupported plan export version ${JSON.stringify(payload.version)}.` }
  }

  const notes = {}
  if (payload.notes !== null && payload.notes !== undefined) {
    if (typeof payload.notes !== 'object' || Array.isArray(payload.notes)) {
      return { ok: false, reason: 'The notes section is not an object.' }
    }
    for (const [id, value] of Object.entries(payload.notes)) {
      const normalized = normalizeId(id)
      if (!normalized || typeof value !== 'string') {
        continue
      }
      notes[normalized] = value.slice(0, MAX_NOTE_LENGTH)
    }
  }

  const checklists = {}
  if (payload.checklists !== null && payload.checklists !== undefined) {
    if (typeof payload.checklists !== 'object' || Array.isArray(payload.checklists)) {
      return { ok: false, reason: 'The checklists section is not an object.' }
    }
    const known = new Set(CHECKLIST_ITEMS.map((entry) => entry.value))
    for (const [id, value] of Object.entries(payload.checklists)) {
      const normalized = normalizeId(id)
      if (!normalized || !Array.isArray(value)) {
        continue
      }
      checklists[normalized] = [...new Set(value.filter((entry) => known.has(entry)))].sort()
    }
  }

  let recentlyViewed = []
  if (payload.recently_viewed !== null && payload.recently_viewed !== undefined) {
    if (!Array.isArray(payload.recently_viewed)) {
      return { ok: false, reason: 'The recently-viewed section is not a list.' }
    }
    const seen = new Set()
    for (const value of payload.recently_viewed) {
      const normalized = normalizeId(value)
      if (!normalized || seen.has(normalized)) {
        continue
      }
      seen.add(normalized)
      recentlyViewed.push(normalized)
      if (recentlyViewed.length >= RECENTLY_VIEWED_LIMIT) {
        break
      }
    }
  }

  // All three writes only begin after validation has passed, so a rejected
  // file cannot leave a half-restored plan behind.
  const notesOk = writeJson(SCHOLARSHIP_NOTES_KEY, notes)
  const checklistsOk = writeJson(CHECKLIST_KEY, checklists)
  const recentOk = writeJson(RECENTLY_VIEWED_KEY, recentlyViewed)

  if (!notesOk || !checklistsOk || !recentOk) {
    return { ok: false, reason: 'This browser refused to store the plan (storage may be full or disabled).' }
  }

  return { ok: true }
}

/** The full local plan store, as one object a component can use. */
export const planStorage = {
  readRecentlyViewed,
  pushRecentlyViewed,
  clearRecentlyViewed,
  readScholarshipNotes,
  readScholarshipNote,
  writeScholarshipNote,
  deleteScholarshipNote,
  readChecklists,
  readChecklist,
  setChecklistItem,
  clearChecklist,
  getChecklistProgress,
  exportPlan,
  importPlan,
}
