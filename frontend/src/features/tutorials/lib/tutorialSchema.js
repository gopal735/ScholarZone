/**
 * Schema and version for the tutorials feature's own preferences.
 *
 * Split from the storage module for the same reason the journey splits them:
 * the shape, the key and the version are one decision, and a test that pins
 * them should not have to import a storage implementation to do it.
 *
 * What this store holds, and what it deliberately does not:
 *
 *   - it holds *this feature's* preferences only: which tutorial was dismissed,
 *     and which language the reader picked;
 *   - it holds no scholarship records, no statement drafts, no application
 *     documents and no journey data. Those belong to their own namespaced keys,
 *     and copying them here would put a copy of a student's document somewhere
 *     the rest of the app does not know about;
 *   - it never talks to the network. There is no analytics, no telemetry and no
 *     server round trip for a preference the browser can hold.
 */

export const SCHEMA = 'scholarzone.tutorials'
export const VERSION = 1

/**
 * The single key this feature owns.
 *
 * Namespaced with the feature's own schema, so a reset removes exactly this and
 * nothing else. Saved-scholarships, the compare list, the plan workspace, the
 * statement builder, the journey and the theme choice all live under their own
 * keys and are untouched by anything in this module.
 */
export const STORAGE_KEY = `${SCHEMA}.v${VERSION}`

/**
 * The default preference document.
 *
 * `dismissed` holds tutorial ids, not slugs or indexes, so renaming a tutorial
 * does not silently re-show it to someone who dismissed the old name. `language`
 * starts as `en`: the site's existing UI is English, so a reader who has never
 * seen the language control should not have Bangla appear as a surprise.
 */
export function defaultTutorialState() {
  return {
    schema: SCHEMA,
    version: VERSION,
    language: 'en',
    dismissed: {},
  }
}

/**
 * The shape a stored document must have to be used.
 *
 * Anything else is treated as corrupt and replaced with the default. This is
 * stricter than it needs to be for two keys, and that is the point: a preference
 * store that half-parses is one that quietly keeps a dismissal the reader
 * thought they had cleared.
 */
export function isPreferenceDocument(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return false
  }
  if (value.schema !== SCHEMA) {
    return false
  }
  if (value.version !== VERSION) {
    return false
  }
  if (typeof value.language !== 'string') {
    return false
  }
  if (!value.dismissed || typeof value.dismissed !== 'object' || Array.isArray(value.dismissed)) {
    return false
  }
  for (const entry of Object.values(value.dismissed)) {
    if (typeof entry !== 'boolean') {
      return false
    }
  }
  return true
}

/**
 * Normalise an untrusted document into the default or default-plus-known-keys.
 *
 * Dismissed keys whose value is not `true` are dropped rather than coerced, so a
 * `false` that arrived from a half-written write is treated as "not dismissed"
 * instead of "dismissed".
 */
export function normalizePreferenceDocument(raw) {
  const base = defaultTutorialState()
  if (!isPreferenceDocument(raw)) {
    return base
  }

  const dismissed = {}
  for (const [key, value] of Object.entries(raw.dismissed)) {
    if (value === true) {
      dismissed[key] = true
    }
  }

  const language = raw.language === 'bn' || raw.language === 'both' ? raw.language : 'en'

  return { ...base, language, dismissed }
}

/** The problem codes a read can produce, kept in one place for the UI. */
export const STORAGE_PROBLEM = Object.freeze({
  UNAVAILABLE: 'unavailable',
  CORRUPT_JSON: 'corrupt-json',
  INVALID_SCHEMA: 'invalid-schema',
  WRITE_FAILED: 'write-failed',
})
