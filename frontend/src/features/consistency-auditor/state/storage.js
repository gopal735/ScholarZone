/**
 * The storage adapter — the only module in this feature that touches
 * browser storage, and it does so only when the user has opted in.
 *
 * Contract, enforced by the integration tests:
 *
 *   - Nothing is written before `enableSaving()` is called. Reading is
 *     harmless, so a read of an unset key returns null.
 *   - Everything this feature writes lives under one prefix. "Clear all
 *     data" walks ONLY that prefix.
 *   - The content of documents is never one of the things written. What is
 *     persisted is the review state (which finding IDs are dismissed or
 *     reviewed), which is why the finding IDs are text-free by design.
 *   - There is no fallback to a wider key when namespaced storage is full:
 *     the write fails and the UI says so, rather than writing outside the
 *     namespace.
 */

/** The namespace every key this feature writes lives under. */
export const STORAGE_PREFIX = 'sz.consistencyAuditor.v1.';

const REVIEW_KEY = `${STORAGE_PREFIX}review`;
const CONSENT_KEY = `${STORAGE_PREFIX}consent`;

/** @returns {boolean} */
function storageAvailable() {
  try {
    return typeof window !== 'undefined' && !!window.localStorage;
  } catch {
    return false; // storage blocked by a privacy setting must not throw
  }
}

/**
 * Create the adapter. `enabled` starts false: the caller must opt in
 * explicitly through `enableSaving()`.
 */
export function createStorage() {
  /** @type {{documents:boolean,reviewed:boolean}} */
  const preferences = { documents: false, reviewed: false };

  return {
    prefix: STORAGE_PREFIX,

    /** True when storage is usable at all (not blocked, present). */
    get available() {
      return storageAvailable();
    },

    /** True when the user has opted in to saving. */
    get saving() {
      return preferences.documents || preferences.reviewed;
    },

    /**
     * Opt in. `what` names which part of the state the user chose to save:
     * the storage key and the in-memory flag both become live here, and the
     * UI explains what that means BEFORE calling this.
     *
     * @param {{documents?: boolean, reviewed?: boolean}} what
     */
    enableSaving(what) {
      preferences.documents = Boolean(what?.documents);
      preferences.reviewed = Boolean(what?.reviewed);
      if (storageAvailable()) {
        try {
          window.localStorage.setItem(CONSENT_KEY, JSON.stringify(preferences));
        } catch {
          return false;
        }
      }
      return this.saving;
    },

    /** Read back the stored preference, so a reload restores the state. */
    restorePreference() {
      if (!storageAvailable()) return false;
      const raw = window.localStorage.getItem(CONSENT_KEY);
      if (!raw) return false;
      try {
        const parsed = JSON.parse(raw);
        preferences.documents = Boolean(parsed?.documents);
        preferences.reviewed = Boolean(parsed?.reviewed);
      } catch {
        return false;
      }
      return this.saving;
    },

    /**
     * Read the persisted review state: the finding IDs the user dismissed or
     * marked reviewed. Never document content.
     *
     * @returns {{dismissed:string[], reviewed:string[]}}
     */
    readReviewState() {
      const empty = { dismissed: [], reviewed: [] };
      if (!storageAvailable() || !preferences.reviewed) return empty;
      const raw = window.localStorage.getItem(REVIEW_KEY);
      if (!raw) return empty;
      try {
        const parsed = JSON.parse(raw);
        return {
          dismissed: Array.isArray(parsed?.dismissed) ? parsed.dismissed.filter((v) => typeof v === 'string') : [],
          reviewed: Array.isArray(parsed?.reviewed) ? parsed.reviewed.filter((v) => typeof v === 'string') : [],
        };
      } catch {
        return empty;
      }
    },

    /**
     * Persist the review state. Refuses quietly when saving is off or
     * storage is full: a state save that cannot happen is not an error the
     * student needs a stack trace for.
     *
     * @param {{dismissed:string[], reviewed:string[]}} state
     * @returns {boolean}
     */
    writeReviewState(state) {
      if (!storageAvailable() || !preferences.reviewed) return false;
      try {
        window.localStorage.setItem(
          REVIEW_KEY,
          JSON.stringify({ dismissed: state.dismissed ?? [], reviewed: state.reviewed ?? [] }),
        );
        return true;
      } catch {
        return false;
      }
    },

    /**
     * Remove ONLY this feature's keys. The localStorage key list is walked
     * and every key starting with the prefix is removed; nothing else is
     * touched, and unknown keys are left exactly as they were.
     *
     * @returns {{removed:number}} how many keys were removed
     */
    clearAll() {
      let removed = 0;
      if (storageAvailable()) {
        for (const key of Object.keys(window.localStorage)) {
          if (key.startsWith(STORAGE_PREFIX)) {
            window.localStorage.removeItem(key);
            removed += 1;
          }
        }
      }
      preferences.documents = false;
      preferences.reviewed = false;
      return { removed };
    },
  };
}
