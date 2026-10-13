/**
 * Import validation and normalisation.
 *
 * The rules here exist because an import file is the one path where data enters
 * the feature that the student did not type into a form, so it is the one path
 * where a malformed value can reach state.
 *
 * - **Nothing is applied until the whole file is validated.** A rejected file
 *   leaves existing progress untouched, and a partially valid file is normalised
 *   rather than half-applied.
 * - **Imported content is data, never code.** The file is parsed with
 *   `JSON.parse` and nothing is `eval`ed, and no imported string is ever passed
 *   to `dangerouslySetInnerHTML` anywhere in this feature.
 * - **Duplicate ids are re-issued, not merged.** Merging silently would let one
 *   record overwrite another; the schema layer re-issues ids instead.
 */

import {
  SCHEMA,
  VERSION,
  normalizeJourneyDocument,
  migrateJourneyDocument,
} from './journeySchema.js'

export const IMPORT_SCHEMA = SCHEMA
export const IMPORT_VERSION = VERSION

/** Byte ceiling for an imported file, so a pasted binary cannot be accepted. */
export const MAX_IMPORT_BYTES = 2 * 1024 * 1024

/**
 * Validate a parsed import payload.
 *
 * Returns `{ ok: true, document }` or `{ ok: false, reason, message }` where
 * `reason` is one of `not-an-object`, `unknown-schema`, `no-version`,
 * `newer-version`, `no-migration`, `too-large`, `empty`.
 */
export function validateImportPayload(parsed) {
  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
    return { ok: false, reason: 'not-an-object', message: 'not-an-object' }
  }

  if (typeof parsed.schema === 'string' && parsed.schema !== SCHEMA) {
    return { ok: false, reason: 'unknown-schema', message: 'unknown-schema' }
  }

  if (parsed.version === undefined || parsed.version === null) {
    return { ok: false, reason: 'no-version', message: 'no-version' }
  }

  if (typeof parsed.version !== 'number' || !Number.isFinite(parsed.version)) {
    return { ok: false, reason: 'no-version', message: 'no-version' }
  }

  const migrated = migrateJourneyDocument(parsed)
  if (!migrated.ok) {
    return {
      ok: false,
      reason: migrated.reason,
      message: migrated.reason,
      foundVersion: migrated.foundVersion,
    }
  }

  return { ok: true, document: migrated.document }
}

/**
 * Read a File into a validated document.
 *
 * Resolves with `{ ok: true, document }` or `{ ok: false, reason, message }`.
 * Never rejects: a read failure is a reason, and turning it into an exception
 * would push error handling into every call site.
 */
export async function readImportFile(file) {
  if (!file) {
    return { ok: false, reason: 'empty', message: 'empty' }
  }
  if (typeof file.size === 'number' && file.size > MAX_IMPORT_BYTES) {
    return { ok: false, reason: 'too-large', message: 'too-large' }
  }

  let text
  try {
    text = await file.text()
  } catch {
    return { ok: false, reason: 'unreadable', message: 'unreadable' }
  }

  if (typeof text !== 'string' || text.trim() === '') {
    return { ok: false, reason: 'empty', message: 'empty' }
  }

  let parsed
  try {
    parsed = JSON.parse(text)
  } catch {
    return { ok: false, reason: 'invalid-json', message: 'invalid-json' }
  }

  return validateImportPayload(parsed)
}

/**
 * Merge an imported document onto existing progress, after confirmation.
 *
 * The imported document replaces the current one wholesale rather than being
 * merged field by field, because a half-merge of two documents that disagree
 * about the same record is not a meaningful result. The replacement is the
 * caller's explicit choice, requested behind a confirmation step, and the
 * current document is returned alongside so the caller can undo in-session if
 * it needs to.
 */
export function planReplacement(currentDocument, importedDocument) {
  return {
    previous: currentDocument,
    next: normalizeJourneyDocument(importedDocument),
  }
}
