/**
 * Browser-local storage for the tutorials feature.
 *
 * Follows the pattern every other browser-local store in this repository follows
 * (`journeyStorage.js`, `sopBuilderStorage.js`, `planStorage.js`), for the three
 * reasons those files document:
 *
 *   1. Storage access is capability-checked, not assumed. A sandboxed iframe
 *      throws on `window.localStorage` rather than returning undefined, so the
 *      check itself needs guarding.
 *   2. A failed write reports failure. localStorage throws on quota exhaustion
 *      and in storage-partitioned contexts; showing a reader a "dismissed" state
 *      after a silent failure is the one outcome worse than a visible error.
 *   3. Nothing is fabricated. An empty or corrupt store yields the default, and
 *      the reader is told the copy is local only.
 *
 * A reset removes only this feature's key. The saved-scholarship list, the
 * compare list, the plan workspace, the statement builder, the journey and the
 * theme choice all live under their own keys and belong to the rest of
 * ScholarZone, so nothing here touches them.
 */

import {
  STORAGE_KEY,
  STORAGE_PROBLEM,
  defaultTutorialState,
  normalizePreferenceDocument,
} from './tutorialSchema.js'

/** The one key this feature owns. Exported so tests and reset agree. */
export const TUTORIAL_STORAGE_KEYS = Object.freeze([STORAGE_KEY])

/** True when localStorage can be read and written at all. */
export function canUseStorage() {
  try {
    if (typeof window === 'undefined') return false
    const probe = window.localStorage
    if (!probe) return false
    // A partitioned sandbox can throw on the access itself rather than on a
    // write, so the read is inside the guard.
    probe.getItem(STORAGE_KEY)
    return true
  } catch {
    return false
  }
}

/**
 * Read and normalise the stored preferences.
 *
 * Returns `{ state, problem }`, where `problem` is null on a clean read and one
 * of the `STORAGE_PROBLEM` codes otherwise. `state` is always usable — on any
 * problem it is the default document, so the page renders rather than crashing
 * and the reader can still get to a tutorial.
 */
export function loadTutorialState() {
  if (!canUseStorage()) {
    return { state: defaultTutorialState(), problem: STORAGE_PROBLEM.UNAVAILABLE }
  }

  let raw
  try {
    raw = window.localStorage.getItem(STORAGE_KEY)
  } catch {
    return { state: defaultTutorialState(), problem: STORAGE_PROBLEM.UNAVAILABLE }
  }

  if (raw === null) {
    return { state: defaultTutorialState(), problem: null }
  }

  let parsed
  try {
    parsed = JSON.parse(raw)
  } catch {
    return { state: defaultTutorialState(), problem: STORAGE_PROBLEM.CORRUPT_JSON }
  }

  const normalized = normalizePreferenceDocument(parsed)
  // Structural comparison, not reference: normalizePreferenceDocument always
  // builds a fresh object, so `parsed === normalized` is never true and every
  // stored preference was wrongly reported as an invalid schema. The round trip
  // through JSON is cheap for two keys and the only honest way to ask "did
  // normalising change anything?".
  const problem =
    JSON.stringify(parsed) === JSON.stringify(normalized) ? null : STORAGE_PROBLEM.INVALID_SCHEMA
  return { state: normalized, problem }
}

/**
 * Write the whole preference document. Returns true only on success.
 *
 * The only write path, so there is exactly one place a failure can be reported
 * from and exactly one place a caller has to handle it.
 */
export function saveTutorialState(next) {
  if (!canUseStorage()) {
    return false
  }

  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
    return true
  } catch {
    return false
  }
}

/** Read the raw stored string, for a test pinning the exact serialised shape. */
export function readRawTutorialState() {
  if (!canUseStorage()) return null
  try {
    return window.localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

/** The language mode currently stored, for a component that needs it on mount. */
export function loadLanguage() {
  return loadTutorialState().state.language
}

/**
 * Set the language. Returns true on success, false when storage refused.
 *
 * A failed write is not retried as a success: the caller keeps its previous
 * value and says so, because a reader who switched to Bangla and kept seeing
 * English has been told something untrue.
 */
export function saveLanguage(language) {
  const state = loadTutorialState().state
  return saveTutorialState({ ...state, language: language === 'bn' || language === 'both' ? language : 'en' })
}

/** Whether one tutorial is currently dismissed. */
export function isDismissed(tutorialId) {
  return loadTutorialState().state.dismissed[tutorialId] === true
}

/**
 * Dismiss a tutorial. Returns true on success.
 *
 * A dismissal is stored against the tutorial's id, and it is this feature's own
 * preference — it is not the same thing as deleting anything, and the tutorial
 * stays available from the Help Center afterwards.
 */
export function dismissTutorial(tutorialId) {
  if (typeof tutorialId !== 'string' || tutorialId.trim() === '') {
    return false
  }
  const state = loadTutorialState().state
  return saveTutorialState({
    ...state,
    dismissed: { ...state.dismissed, [tutorialId]: true },
  })
}

/** Clear one dismissal, so the tutorial offers itself again. */
export function undismissTutorial(tutorialId) {
  const state = loadTutorialState().state
  const dismissed = { ...state.dismissed }
  delete dismissed[tutorialId]
  return saveTutorialState({ ...state, dismissed })
}

/** Every dismissal at once. Returns true on success. */
export function clearAllDismissed() {
  const state = loadTutorialState().state
  return saveTutorialState({ ...state, dismissed: {} })
}

/**
 * Erase this feature's preferences from this browser.
 *
 * A write of the empty document rather than a `removeItem`, so the next read
 * still returns the right shape. Only this feature's key is touched: the label
 * on the control that calls this says exactly that, because anything stronger
 * would be a claim about data this module does not own.
 */
export function resetTutorialPreferences() {
  return saveTutorialState(defaultTutorialState())
}

/** Everything the module owns, as one object a component can bind to. */
export const tutorialStorage = {
  canUseStorage,
  loadTutorialState,
  saveTutorialState,
  readRawTutorialState,
  loadLanguage,
  saveLanguage,
  isDismissed,
  dismissTutorial,
  undismissTutorial,
  clearAllDismissed,
  resetTutorialPreferences,
}

export { STORAGE_PROBLEM, defaultTutorialState }
