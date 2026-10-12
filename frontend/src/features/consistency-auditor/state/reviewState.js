/**
 * Review state.
 *
 * Deliberately simple, and deliberately session-shaped:
 *
 *   - A finding is "resolved" when the user dismissed it or marked it
 *     reviewed. Dismissed findings stay dismissed for the life of the
 *     unchanged session — they do not come back on a re-render, and they do
 *     not come back on a re-run of the SAME documents.
 *   - When a document changes, the affected findings are dropped and the
 *     review is marked stale: the UI shows "Documents changed — run a fresh
 *     review" and never presents the previous results as current. Nothing
 *     is silently preserved.
 *   - Dismiss can be undone, and dismissed items stay viewable.
 *   - Persistence is opt-in, per finding ID only, and lives in the same
 *     namespaced storage the clear action removes.
 */

import { createStorage } from './storage.js';

/** @typedef {{findings: any[], reviewedSet: Set<string>, dismissedSet: Set<string>, stale: boolean, ranAt: string|null}} ReviewState */

export function createReviewState({ storage } = {}) {
  const store = storage ?? createStorage();

  /** @type {ReviewState} */
  const state = {
    findings: [],
    reviewedSet: new Set(),
    dismissedSet: new Set(),
    stale: false,
    ranAt: null,
  };

  const listeners = new Set();
  const notify = () => {
    for (const listener of listeners) listener(state);
  };

  const persist = () => {
    store.writeReviewState({
      dismissed: [...state.dismissedSet],
      reviewed: [...state.reviewedSet],
    });
  };

  return {
    storage: store,
    state,

    /** @param {() => void} listener */
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },

    /** Start a review: adopt the engine's findings, preserving user decisions whose IDs are still present. */
    beginReview(findings) {
      const activeIds = new Set(findings.map((finding) => finding.id));
      const dismissed = new Set([...state.dismissedSet].filter((id) => activeIds.has(id)));
      const reviewed = new Set([...state.reviewedSet].filter((id) => activeIds.has(id)));
      state.findings = findings;
      state.dismissedSet = dismissed;
      state.reviewedSet = reviewed;
      state.stale = false;
      state.ranAt = new Date().toISOString();
      persist();
      notify();
    },

    /**
     * The documents changed, so every finding from the previous run is no
     * longer evidence about the current text. The results are dropped
     * rather than kept-and-labelled, so nothing stale can be shown.
     */
    invalidate() {
      state.findings = [];
      state.reviewedSet = new Set();
      state.dismissedSet = new Set();
      state.stale = true;
      state.ranAt = null;
      persist();
      notify();
    },

    /** @param {string} id */
    dismiss(id) {
      if (!state.dismissedSet.has(id)) {
        state.dismissedSet.add(id);
        persist();
        notify();
      }
    },

    /** @param {string} id */
    undoDismiss(id) {
      if (state.dismissedSet.delete(id)) {
        persist();
        notify();
      }
    },

    /** @param {string} id */
    markReviewed(id) {
      if (!state.reviewedSet.has(id)) {
        state.reviewedSet.add(id);
        persist();
        notify();
      }
    },

    /**
     * Restore decisions from the namespaced store, when the user opted in.
     * Only IDs that match findings in the CURRENT review survive; the rest
     * are stale and are dropped.
     */
    restoreFromStorage(findings) {
      const restored = store.readReviewState();
      const activeIds = new Set(findings.map((finding) => finding.id));
      state.dismissedSet = new Set(restored.dismissed.filter((id) => activeIds.has(id)));
      state.reviewedSet = new Set(restored.reviewed.filter((id) => activeIds.has(id)));
      notify();
      return { dismissed: state.dismissedSet.size, reviewed: state.reviewedSet.size };
    },

    /** Restore the save preference (so a reload remembers the consent). */
    restorePreference() {
      return store.restorePreference();
    },

    /** @param {{documents?: boolean, reviewed?: boolean}} what */
    enableSaving(what) {
      const enabled = store.enableSaving(what);
      if (enabled) persist();
      notify();
      return enabled;
    },

    /** @returns {{removed:number}} */
    clearAll() {
      const result = store.clearAll();
      state.findings = [];
      state.dismissedSet = new Set();
      state.reviewedSet = new Set();
      state.stale = false;
      notify();
      return result;
    },

    /**
     * The findings the list should show: unresolved ones in engine order.
     *
     * @param {boolean} [includeDismissed]
     */
    visible(includeDismissed = false) {
      let list = state.findings;
      if (!includeDismissed) {
        list = list.filter((finding) => !state.dismissedSet.has(finding.id));
      }
      return list;
    },

    /** @returns {any[]} */
    dismissed() {
      return state.findings.filter((finding) => state.dismissedSet.has(finding.id));
    },

    /** @returns {boolean} */
    isReviewed(id) {
      return state.reviewedSet.has(id);
    },

    /** @returns {boolean} */
    isDismissed(id) {
      return state.dismissedSet.has(id);
    },
  };
}
