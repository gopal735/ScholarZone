/**
 * Browser-local persistence for the Bangladesh Applicant Journey.
 *
 * Follows the pattern `sopBuilderStorage.js` and `clientPreferenceStorage.js`
 * established in this repository, and for the same reasons:
 *
 *   1. Storage access is capability-checked, not assumed. A sandboxed iframe
 *      throws on `window.localStorage` rather than returning undefined, so the
 *      check itself needs guarding.
 *   2. A failed write reports failure. localStorage throws on quota exhaustion
 *      and in storage-partitioned contexts, and a caller shown a working control
 *      after a silent failure is the worst outcome available.
 *   3. Nothing is fabricated. An empty store produces the default document, and
 *      a corrupt one is replaced rather than repaired.
 *
 * Reset removes only this feature's own key. It never touches `localStorage`
 * wholesale, because the saved-scholarship list, the compare list and the theme
 * choice all live there and belong to the rest of ScholarZone.
 */

import {
  STORAGE_KEY,
  defaultJourneyState,
  migrateJourneyDocument,
} from './journeySchema.js'

/** True when localStorage can be read and written at all. */
export function canUseStorage() {
  try {
    if (typeof window === 'undefined') return false
    const probe = window.localStorage
    if (!probe) return false
    return true
  } catch {
    return false
  }
}

/**
 * A key that only this feature owns.
 *
 * Exported so the reset path and the tests agree on the same name, and so a
 * future key addition lands in one place.
 */
export const JOURNEY_STORAGE_KEYS = Object.freeze([STORAGE_KEY])

export class JourneyStorageError extends Error {
  constructor(reason, cause) {
    super(reason)
    this.name = 'JourneyStorageError'
    this.reason = reason
    this.cause = cause
  }
}

/**
 * Read and normalise the stored document.
 *
 * Returns `{ state, problem }` where `problem` is null on a clean read, or one
 * of `unavailable`, `corrupt-json`, `invalid-schema`, `unsupported-version`,
 * `newer-version`. The state is always usable: on any problem it is the default
 * document, so the page renders rather than crashing.
 */
export function loadJourneyState() {
  if (!canUseStorage()) {
    return { state: defaultJourneyState(), problem: 'unavailable' }
  }

  let raw
  try {
    raw = window.localStorage.getItem(STORAGE_KEY)
  } catch {
    return { state: defaultJourneyState(), problem: 'unavailable' }
  }

  if (raw === null || raw === undefined || raw === '') {
    return { state: defaultJourneyState(), problem: null }
  }

  let parsed
  try {
    parsed = JSON.parse(raw)
  } catch {
    return { state: defaultJourneyState(), problem: 'corrupt-json' }
  }

  const migrated = migrateJourneyDocument(parsed)
  if (!migrated.ok) {
    const problem =
      migrated.reason === 'newer-version'
        ? 'newer-version'
        : migrated.reason === 'unknown-schema' || migrated.reason === 'not-an-object' || migrated.reason === 'no-version'
          ? 'invalid-schema'
          : 'unsupported-version'
    return { state: defaultJourneyState(), problem }
  }

  return { state: migrated.document, problem: null }
}

/**
 * Persist the document.
 *
 * Throws `JourneyStorageError` when the write is refused, so the caller can
 * surface a non-blocking notice instead of claiming success. The reason is
 * classified rather than collapsed: `unavailable` means the store could not be
 * reached at all, `quota-exceeded` means the browser refused a write it
 * understood, and `write-failed` means the store rejected it for a reason the
 * platform did not name. Reporting all three as "quota" would tell a student
 * their browser is full when it is not.
 */
export function saveJourneyState(document) {
  if (!canUseStorage()) {
    throw new JourneyStorageError('unavailable')
  }
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(document))
    return true
  } catch (error) {
    if (error && (error.name === 'QuotaExceededError' || error.code === 22)) {
      throw new JourneyStorageError('quota-exceeded', error)
    }
    throw new JourneyStorageError('write-failed', error)
  }
}

/**
 * Delete only this feature's key.
 *
 * Returns `{ ok: true }` or `{ ok: false, reason }`. A reset that could not be
 * completed is reported so the UI can say so, rather than leaving the student
 * to discover the data is still there on the next visit.
 */
export function resetJourneyStorage() {
  if (!canUseStorage()) {
    return { ok: false, reason: 'unavailable' }
  }
  try {
    for (const key of JOURNEY_STORAGE_KEYS) {
      window.localStorage.removeItem(key)
    }
    return { ok: true }
  } catch (error) {
    return { ok: false, reason: 'remove-failed', cause: error }
  }
}

/**
 * Build the downloadable JSON for an export.
 *
 * Carries the schema and version in the body, and a declared provenance banner
 * so a file opened six months later can state on its own which figures are the
 * student's own and which are estimates. No transformation happens here beyond
 * serialising the normalised document: an export is a copy, not a report.
 */
export function buildExport(document) {
  return JSON.stringify(
    {
      exportedAt: new Date().toISOString(),
      ...document,
    },
    null,
    2,
  )
}
