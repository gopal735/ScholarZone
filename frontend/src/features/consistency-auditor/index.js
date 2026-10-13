/**
 * Application Consistency Auditor V1 — the feature module's public surface.
 *
 * `enabled` is the single switch. It is committed as false: the route is
 * not reachable and the navigation link is not rendered, so the feature
 * ships inert. Turning it on is a one-line change plus the corresponding
 * route/nav lines (see README "Rollback").
 */
export const enabled = false;

export { STORAGE_PREFIX, createStorage } from './state/storage.js';
export { createReviewState } from './state/reviewState.js';
export { review, CATEGORIES, CATEGORY_ORDER, CONFIDENCE, MAX_DOCUMENT_CHARACTERS, MAX_TOTAL_CHARACTERS } from './engine/index.js';
