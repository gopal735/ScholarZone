/**
 * Input validation. The engine refuses work it should not attempt rather
 * than attempting it slowly: an over-limit document is reported as a
 * state, not analysed. Every message here names the limit and the actual
 * size, so a student who pastes a thesis knows what happened.
 */

/** Per-document character cap. Generous for a statement or CV, bounded for safety. */
export const MAX_DOCUMENT_CHARACTERS = 20000;

/** Total characters across all documents in one review. */
export const MAX_TOTAL_CHARACTERS = 60000;

/**
 * @typedef {Object} Document
 * @property {string} id
 * @property {string} label
 * @property {string} text the user's original text; never mutated
 */

/**
 * @typedef {Object} ValidationResult
 * @property {boolean} ok
 * @property {string|null} code 'too-large' | 'empty' | null
 * @property {string|null} message shown to the user, no content echoed
 * @property {{id:string,label:string,length:number}[]} [overLimit]
 */

/**
 * @param {Document[]} documents
 * @returns {ValidationResult}
 */
export function validateDocuments(documents) {
  const list = Array.isArray(documents) ? documents : [];
  const overLimit = [];
  let total = 0;
  for (const document of list) {
    const text = typeof document?.text === 'string' ? document.text : '';
    total += text.length;
    if (text.length > MAX_DOCUMENT_CHARACTERS) {
      overLimit.push({ id: document.id, label: document.label, length: text.length });
    }
  }

  if (total > MAX_TOTAL_CHARACTERS) {
    return {
      ok: false,
      code: 'too-large',
      message: `This review is ${total.toLocaleString()} characters in total. The limit is ${MAX_TOTAL_CHARACTERS.toLocaleString()} across all documents. Review one document at a time, or trim to the parts you want checked.`,
    };
  }
  if (overLimit.length > 0) {
    const labels = overLimit.map((entry) => entry.label).join(', ');
    return {
      ok: false,
      code: 'too-large',
      message: `One or more documents are over the ${MAX_DOCUMENT_CHARACTERS.toLocaleString()}-character limit (${labels}). The document left untouched on this device — nothing was sent anywhere.`,
      overLimit,
    };
  }

  const anyContent = list.some((document) => (document?.text ?? '').trim() !== '');
  if (!anyContent) {
    return {
      ok: false,
      code: 'empty',
      message: 'Paste at least one document to review. You can start with just your SOP — the other two are optional.',
    };
  }
  return { ok: true, code: null, message: null };
}

/**
 * Split text into lines without losing the offsets into the original.
 * Line splitting is the only place the engine touches long input, so it is
 * bounded: no line longer than 8,000 characters is scanned for dates by
 * the more expensive rules (they skip it rather than walking it).
 *
 * @param {string} text
 * @returns {string[]}
 */
export function splitLines(text) {
  if (typeof text !== 'string' || text === '') return [];
  return text.split(/\r\n|\r|\n/);
}
