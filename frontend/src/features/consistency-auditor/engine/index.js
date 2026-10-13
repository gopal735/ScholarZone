/**
 * Application Consistency Auditor V1 — the analysis engine.
 *
 * Pure: no DOM, no network, no storage, no timers. `review()` is the only
 * public entry point, it takes documents, validates them, runs the rule
 * groups, sorts the findings deterministically, and returns a result. The
 * same input produces the same output, including the finding IDs, which
 * the determinism test proves.
 *
 * The engine never mutates the documents it is given. Normalisation works
 * on internal copies; findings carry offsets into the ORIGINAL strings so
 * the UI can display excerpts exactly as written.
 *
 * Budget: the whole review is expected to finish in well under 500 ms for
 * three documents of 20,000 characters each on a mid-range device. The
 * ReDoS-style adversarial test in engine.test.js bounds it.
 */

import { validateDocuments } from './validator.js';
import { compareFindings } from './findings.js';
import { runDateRules } from './rules/dates.js';
import { runEntityRules } from './rules/entities.js';
import { runClaimRules } from './rules/claims.js';

/**
 * @typedef {Object} ReviewOptions
 * @property {boolean} [includeClaims] run the claim-question rules (default true)
 */

/**
 * Run one review.
 *
 * @param {import('./validator.js').Document[]} documents
 * @param {ReviewOptions} [options]
 * @returns {{ok: true, findings: import('./findings.js').Finding[]}
 *          | {ok: false, code: string, message: string}}
 */
export function review(documents, options = {}) {
  const validation = validateDocuments(documents);
  if (!validation.ok) {
    return { ok: false, code: validation.code, message: validation.message };
  }
  const list = documents.map((document) => ({
    id: document.id,
    label: document.label,
    text: typeof document.text === 'string' ? document.text : '',
  }));

  let findings = [];
  try {
    findings = findings.concat(runDateRules(list));
    findings = findings.concat(runEntityRules(list));
    if (options.includeClaims !== false) {
      findings = findings.concat(runClaimRules(list));
    }
  } catch {
    // A rule must never take the page down, and the message must never
    // carry document text: the error's own message is discarded and a
    // generic one is returned instead.
    return {
      ok: false,
      code: 'engine-error',
      message: 'The review could not run on this input. Nothing was sent anywhere, and your documents are untouched.',
    };
  }

  findings.sort(compareFindings);
  return { ok: true, findings };
}

/**
 * The public surface, exported once so the UI imports one module rather
 * than reaching into the engine's internals.
 */
export { CATEGORIES, CATEGORY_ORDER, CONFIDENCE } from './findings.js';
export { MAX_DOCUMENT_CHARACTERS, MAX_TOTAL_CHARACTERS } from './validator.js';
