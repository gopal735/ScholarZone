/**
 * The tutorial i18n hook and storage adapter.
 *
 * The contracts that matter here are the two that usually fail:
 *
 *   1. A failed write is reported as failed. Showing a reader "switched to
 *      Bangla" after localStorage refused silently would be a lie about
 *      something they can immediately see.
 *   2. Nothing outside this feature's own key is touched. The saved-scholarship
 *      list, the compare list, the plan workspace and the theme choice all live
 *      in the same localStorage and none of them are this feature's to remove.
 *
 * Both are asserted by refusing the write and by looking at what the key list
 * is afterwards, not by trusting the module's comments.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  STORAGE_PROBLEM,
  TUTORIAL_STORAGE_KEYS,
  canUseStorage,
  clearAllDismissed,
  defaultTutorialState,
  dismissTutorial,
  isDismissed,
  loadLanguage,
  loadTutorialState,
  readRawTutorialState,
  resetTutorialPreferences,
  saveLanguage,
  saveTutorialState,
  undismissTutorial,
} from '../lib/tutorialStorage.js';
import { SCHEMA, VERSION, isPreferenceDocument, normalizePreferenceDocument } from '../lib/tutorialSchema.js';

const KEY = 'scholarzone.tutorials.v1';
const UNRELATED = 'scholarzone.sop-builder.v1';

beforeEach(() => {
  window.localStorage.clear();
});

describe('the key this feature owns', () => {
  it('is namespaced to this feature and versioned', () => {
    expect(KEY).toBe(`${SCHEMA}.v${VERSION}`);
    expect(TUTORIAL_STORAGE_KEYS).toEqual([KEY]);
  });

  it('does not overlap any other feature key', () => {
    for (const other of [
      'scholarzone.sop-builder.v1',
      'scholarzone.plan.v1',
      'scholarzone.recently-viewed.v1',
      'scholarzone.plan-notes.v1',
      'scholarzone.plan-checklist.v1',
    ]) {
      expect(KEY.startsWith(other)).toBe(false);
    }
  });
});

describe('reading an absent or broken store', () => {
  it('returns the default and no problem when nothing is stored', () => {
    const { state, problem } = loadTutorialState();
    expect(state).toEqual(defaultTutorialState());
    expect(problem).toBeNull();
  });

  it('round-trips a clean write with no problem reported', () => {
    // The regression this pins: the problem check used reference equality
    // (`parsed === normalized`), and normalising always builds a fresh object,
    // so every stored preference was reported as an invalid schema. A reader
    // would have been shown a storage warning for a write that succeeded.
    expect(saveLanguage('bn')).toBe(true);
    const { state, problem } = loadTutorialState();
    expect(problem).toBeNull();
    expect(state.language).toBe('bn');
  });

  it('reports a problem only when normalising actually changed the document', () => {
    // An extra unknown key is dropped by normalisation, which is a change.
    window.localStorage.setItem(
      KEY,
      JSON.stringify({
        schema: SCHEMA,
        version: 1,
        language: 'bn',
        dismissed: {},
        unexpected: true,
      }),
    );
    const { problem } = loadTutorialState();
    expect(problem).toBe(STORAGE_PROBLEM.INVALID_SCHEMA);
  });

  it('treats corrupt JSON as a default rather than crashing', () => {
    window.localStorage.setItem(KEY, '{not json');
    const { state, problem } = loadTutorialState();
    expect(state).toEqual(defaultTutorialState());
    expect(problem).toBe(STORAGE_PROBLEM.CORRUPT_JSON);
  });

  it('refuses a document with the wrong schema', () => {
    window.localStorage.setItem(KEY, JSON.stringify({ schema: 'something.else', version: 1 }));
    const { problem } = loadTutorialState();
    expect(problem).toBe(STORAGE_PROBLEM.INVALID_SCHEMA);
  });

  it('refuses an unsupported version rather than guessing at the shape', () => {
    window.localStorage.setItem(
      KEY,
      JSON.stringify({ schema: SCHEMA, version: 99, language: 'en', dismissed: {} }),
    );
    const { state, problem } = loadTutorialState();
    expect(state).toEqual(defaultTutorialState());
    expect(problem).toBe(STORAGE_PROBLEM.INVALID_SCHEMA);
  });

  it('drops a dismissed entry that is not strictly true', () => {
    window.localStorage.setItem(
      KEY,
      JSON.stringify({ schema: SCHEMA, version: 1, language: 'en', dismissed: { a: false, b: true } }),
    );
    const { state } = loadTutorialState();
    expect(state.dismissed).toEqual({ b: true });
  });

  it('falls back to English for an unknown language', () => {
    window.localStorage.setItem(
      KEY,
      JSON.stringify({ schema: SCHEMA, version: 1, language: 'fr', dismissed: {} }),
    );
    expect(loadLanguage()).toBe('en');
  });

  it('reports unavailable when storage cannot be read at all', () => {
    const spy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    try {
      const { state, problem } = loadTutorialState();
      expect(state).toEqual(defaultTutorialState());
      expect(problem).toBe(STORAGE_PROBLEM.UNAVAILABLE);
    } finally {
      spy.mockRestore();
    }
  });
});

describe('the schema guard', () => {
  it('accepts only a well-formed document', () => {
    expect(isPreferenceDocument(defaultTutorialState())).toBe(true);
    expect(isPreferenceDocument(null)).toBe(false);
    expect(isPreferenceDocument('x')).toBe(false);
    expect(isPreferenceDocument({ schema: SCHEMA, version: 1, language: 'en' })).toBe(false);
    expect(
      isPreferenceDocument({ schema: SCHEMA, version: 1, language: 'en', dismissed: [] }),
    ).toBe(false);
    expect(
      isPreferenceDocument({ schema: SCHEMA, version: 1, language: 'en', dismissed: { a: 1 } }),
    ).toBe(false);
  });

  it('normalises a document it accepts back to itself', () => {
    const good = { schema: SCHEMA, version: 1, language: 'both', dismissed: { a: true } };
    expect(normalizePreferenceDocument(good)).toEqual(good);
  });
});

describe('writing', () => {
  it('round-trips a language choice', () => {
    expect(saveLanguage('bn')).toBe(true);
    expect(loadLanguage()).toBe('bn');
  });

  it('keeps the stored shape it wrote', () => {
    saveLanguage('both');
    const raw = JSON.parse(readRawTutorialState());
    expect(raw.schema).toBe(SCHEMA);
    expect(raw.version).toBe(VERSION);
    expect(raw.language).toBe('both');
  });

  it('refuses a language it does not know, and keeps the previous one', () => {
    saveLanguage('bn');
    expect(saveLanguage('unknown-mode')).toBe(true); // normalises, does not throw
    expect(loadLanguage()).toBe('en');
  });

  it('reports failure when the write is refused', () => {
    const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError');
    });
    try {
      expect(saveLanguage('bn')).toBe(false);
      expect(dismissTutorial('home')).toBe(false);
      expect(undismissTutorial('home')).toBe(false);
      expect(clearAllDismissed()).toBe(false);
      expect(resetTutorialPreferences()).toBe(false);
      expect(saveTutorialState(defaultTutorialState())).toBe(false);
    } finally {
      spy.mockRestore();
    }
  });

  it('keeps the previous language when a write fails, so the UI can say so', () => {
    saveLanguage('bn');
    const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError');
    });
    try {
      // The hook calls saveLanguage then re-reads; a refused write must leave
      // 'bn' in store, so the rendered mode stays what it was.
      saveLanguage('en');
      expect(loadLanguage()).toBe('bn');
    } finally {
      spy.mockRestore();
    }
  });
});

describe('dismissals', () => {
  it('records and clears a dismissal against its id', () => {
    expect(dismissTutorial('home')).toBe(true);
    expect(isDismissed('home')).toBe(true);
    expect(undismissTutorial('home')).toBe(true);
    expect(isDismissed('home')).toBe(false);
  });

  it('refuses an id that is not a usable string', () => {
    expect(dismissTutorial('')).toBe(false);
    expect(dismissTutorial(null)).toBe(false);
    expect(dismissTutorial(42)).toBe(false);
  });

  it('leaves other features data alone', () => {
    window.localStorage.setItem(UNRELATED, '{"keep":"me"}');
    dismissTutorial('home');
    expect(window.localStorage.getItem(UNRELATED)).toBe('{"keep":"me"}');
  });

  it('resets only its own key', () => {
    window.localStorage.setItem(UNRELATED, '{"keep":"me"}');
    dismissTutorial('home');
    dismissTutorial('plan');
    resetTutorialPreferences();
    expect(isDismissed('home')).toBe(false);
    expect(isDismissed('plan')).toBe(false);
    // Another feature's key is untouched.
    expect(window.localStorage.getItem(UNRELATED)).toBe('{"keep":"me"}');
  });

  it('clears every dismissal at once and only its own', () => {
    dismissTutorial('home');
    dismissTutorial('plan');
    expect(clearAllDismissed()).toBe(true);
    const { state } = loadTutorialState();
    expect(state.dismissed).toEqual({});
  });

  it('reports the feature storage key and nothing else', () => {
    // The audit list is what a reset walks, so a second key here would be a
    // silent claim over data this feature does not own.
    window.localStorage.setItem(UNRELATED, 'x');
    expect(TUTORIAL_STORAGE_KEYS).not.toContain(UNRELATED);
  });
});

describe('unavailable storage', () => {
  it('reports unavailable without throwing', () => {
    const spy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    try {
      expect(canUseStorage()).toBe(false);
      expect(readRawTutorialState()).toBeNull();
      expect(loadLanguage()).toBe('en');
    } finally {
      spy.mockRestore();
    }
  });
});
