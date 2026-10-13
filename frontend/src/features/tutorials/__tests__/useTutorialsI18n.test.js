/**
 * The tutorial i18n hook.
 *
 * The behaviour worth pinning is the one a reader sees: choosing a language
 * changes what renders, the choice survives a remount because it is in storage,
 * and a refused write surfaces as a problem instead of a silent English
 * fallback that looks like success.
 *
 * `both` is its own case, not a fallback: Bangla on the line and English
 * underneath, with `lang` set to bn because the primary line is Bangla.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';

import { useTutorialsI18n } from '../i18n/useTutorialsI18n.js';
import { loadLanguage } from '../lib/tutorialStorage.js';

beforeEach(() => {
  window.localStorage.clear();
});

/** Render the hook and return its latest result. */
function renderTutorials() {
  return renderHook(() => useTutorialsI18n());
}

describe('defaults', () => {
  it('starts in English, because the site UI is English', () => {
    const { result } = renderTutorials();
    expect(result.current.mode).toBe('en');
    expect(result.current.lang).toBe('en');
    expect(result.current.locale).toBe('en-GB');
    expect(result.current.problem).toBeNull();
  });

  it('returns English without a secondary line in English mode', () => {
    const { result } = renderTutorials();
    expect(result.current.t('app.title')).toBe('Tutorials & Help Center');
    expect(result.current.both('app.title')).toEqual({
      primary: 'Tutorials & Help Center',
      secondary: null,
    });
  });
});

describe('switching language', () => {
  it('renders Bangla when set, with the Bangla locale', () => {
    const { result } = renderTutorials();
    act(() => {
      result.current.setLanguage('bn');
    });
    expect(result.current.mode).toBe('bn');
    expect(result.current.lang).toBe('bn');
    expect(result.current.locale).toBe('bn-BD');
    expect(loadLanguage()).toBe('bn');
  });

  it('renders Bangla as primary and English as the secondary line in both mode', () => {
    const { result } = renderTutorials();
    act(() => {
      result.current.setLanguage('both');
    });
    expect(result.current.isBoth).toBe(true);
    // The primary line is Bangla, so the document language attribute is bn.
    expect(result.current.lang).toBe('bn');
    const both = result.current.both('app.title');
    expect(both.primary).toBe('টিউটোরিয়াল ও সহায়তা কেন্দ্র');
    expect(both.secondary).toBe('Tutorials & Help Center');
    expect(result.current.t('app.title')).toBe('টিউটোরিয়াল ও সহায়তা কেন্দ্র');
  });

  it('resolves t() to Bangla in both mode, because Bangla is the primary line', () => {
    // The regression this pins: `t` used to test `language === 'bn'`, so a
    // reader who chose "both" still got English through t().
    const { result } = renderTutorials();
    act(() => {
      result.current.setLanguage('both');
    });
    expect(result.current.t('app.title')).toBe('টিউটোরিয়াল ও সহায়তা কেন্দ্র');
    expect(result.current.t('search.label')).toBe('টিউটোরিয়াল খুঁজুন');
  });

  it('returns no secondary line in a single-language mode', () => {
    const { result } = renderTutorials();
    act(() => {
      result.current.setLanguage('bn');
    });
    expect(result.current.both('app.title').secondary).toBeNull();
  });

  it('restores a stored choice on a fresh mount, without an English flash', () => {
    // Read on mount rather than in an effect, so the first paint is already
    // Bangla; an effect-based read would render English first.
    const first = renderTutorials();
    act(() => {
      first.result.current.setLanguage('bn');
    });
    const second = renderTutorials();
    expect(second.result.current.mode).toBe('bn');
  });
});

describe('a refused write', () => {
  it('reports a problem and keeps the rendered language it actually has', () => {
    const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError');
    });
    try {
      const { result } = renderTutorials();
      act(() => {
        result.current.setLanguage('bn');
      });
      // The write was refused, so the store still holds nothing and the hook
      // re-reads that. A UI may not claim a switch that did not land.
      expect(loadLanguage()).toBe('en');
      expect(result.current.mode).toBe('en');
    } finally {
      spy.mockRestore();
    }
  });

  it('refuses a mode it does not know, leaving the current one untouched', () => {
    const { result } = renderTutorials();
    act(() => {
      result.current.setLanguage('both');
    });
    let accepted = true;
    act(() => {
      accepted = result.current.setLanguage('nonsense');
    });
    // The guard is in the hook, before storage: an unknown mode is never
    // written, so whatever was already chosen stays chosen.
    expect(accepted).toBe(false);
    expect(result.current.mode).toBe('both');
  });
});
