/**
 * Findings model and stable IDs.
 *
 * A finding's ID is derived from the rule that produced it plus a digest of
 * the NORMALISED excerpts it quotes. That has three consequences the tests
 * pin:
 *
 *   - same input produces the same IDs, run after run (determinism);
 *   - an ID identifies the comparison, not the moment it was made, so
 *     dismissing a finding survives a re-run of the same review but not a
 *     different one;
 *   - an ID never contains user text, so it is safe to persist.
 *
 * Nothing here stores or transmits the excerpt text: excerpts live only in
 * the in-memory result the engine returns, and the storage layer persists
 * IDs alone.
 */

/** The four categories. Nothing else may be emitted. */
export const CATEGORIES = {
  inconsistency: 'Possible factual inconsistency',
  variation: 'Formatting or naming variation',
  claim: 'Claim to substantiate',
  humanReview: 'Needs human review',
};

export const CATEGORY_ORDER = [
  CATEGORIES.inconsistency,
  CATEGORIES.variation,
  CATEGORIES.claim,
  CATEGORIES.humanReview,
];

/** Confidence describes the strength of the TEXT COMPARISON, never the truth of a claim. */
export const CONFIDENCE = {
  strong: 'Strong text match — the two texts state different facts',
  moderate: 'Moderate text match — a difference is likely but could be phrasing',
  weak: 'Weak text match — probably wording, worth a glance',
};

/**
 * @typedef {Object} Excerpt
 * @property {string} documentId
 * @property {string} documentLabel
 * @property {number} start offset in the original text
 * @property {number} end offset in the original text
 * @property {string} text the excerpt exactly as written
 */

/**
 * @typedef {Object} Finding
 * @property {string} id stable, text-free
 * @property {string} ruleId
 * @property {string} ruleName
 * @property {string} category one of CATEGORIES
 * @property {string} confidence one of CONFIDENCE
 * @property {string} reason plain English, never accusatory
 * @property {Excerpt[]} excerpts
 * @property {string} [question] present for claims to substantiate
 * @property {string[]} [support] matched support, when a claim was downgraded
 * @property {number} orderIndex position for the deterministic sort
 */

let counter = 0;

/**
 * A small non-cryptographic digest. It exists to make finding IDs stable
 * and short; it is not a security primitive and is never used for one.
 *
 * @param {string} value
 * @returns {string}
 */
export function digest(value) {
  let h1 = 0xdeadbeef;
  let h2 = 0x41c6ce57;
  for (let i = 0; i < value.length; i += 1) {
    const ch = value.charCodeAt(i);
    h1 = Math.imul(h1 ^ ch, 2654435761);
    h2 = Math.imul(h2 ^ ch, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  const body = ((h2 >>> 0).toString(16)).padStart(8, '0') + ((h1 >>> 0).toString(16)).padStart(8, '0');
  return body.slice(0, 10);
}

/**
 * @param {string} ruleId
 * @param {string[]} parts normalised excerpts, joined to identify the comparison
 * @returns {string}
 */
export function makeFindingId(ruleId, parts) {
  const key = parts.map((part) => String(part ?? '')).join(' ');
  return `${ruleId}-${digest(key)}`;
}

/**
 * The same helper under the name the engine's tests use. Both names refer
 * to one function so there is exactly one place an ID can be made.
 *
 * @param {string} ruleId
 * @param {string[]} parts
 * @returns {string}
 */
export const comparisonOf = makeFindingId;

/**
 * Deterministic ordering: category first, then document order, then rule
 * and id so two findings of the same category in the same document always
 * come out the same way round.
 *
 * @param {Finding} a
 * @param {Finding} b
 * @returns {number}
 */
export function compareFindings(a, b) {
  const categoryDelta = CATEGORY_ORDER.indexOf(a.category) - CATEGORY_ORDER.indexOf(b.category);
  if (categoryDelta !== 0) return categoryDelta;
  const firstA = a.excerpts[0];
  const firstB = b.excerpts[0];
  if (firstA && firstB && firstA.documentId !== firstB.documentId) {
    return firstA.documentId.localeCompare(firstB.documentId);
  }
  if (firstA && firstB && firstA.start !== firstB.start) {
    return firstA.start - firstB.start;
  }
  if (a.ruleId !== b.ruleId) return a.ruleId.localeCompare(b.ruleId);
  return a.id.localeCompare(b.id);
}

/**
 * Reset the internal order counter. Only tests call this, so a test's
 * ordering is reproducible from a cold start.
 */
export function __resetFindingCounter() {
  counter = 0;
}

/**
 * @returns {number}
 */
export function __nextOrder() {
  counter += 1;
  return counter;
}
