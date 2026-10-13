/**
 * Registry invariants for the tutorial catalogue.
 *
 * The registry is data, so these are assertions about data rather than about
 * rendering. What they exist to prevent:
 *
 *   - a route with no tutorial, which is the failure a help centre hides best;
 *   - a tutorial id reused after removal, so a dismissal silently re-shows
 *     someone a guide they had hidden;
 *   - a half-translated guide, which is worse than an English one for the reader
 *     who needs the Bangla;
 *   - a tutorial published for a feature that is switched off, which tells a
 *     reader to visit a route that renders the not-found page;
 *   - an admin guide shelved next to scholarship browsing;
 *   - an outcome claim, which is the one promise this feature must never make.
 *
 * The route table in `ROUTES` is the audit's own assertion, so enabling the
 * consistency auditor's flag fails this file rather than leaving a stale guide.
 */

import { describe, expect, it } from 'vitest';

import {
  CATEGORY_ORDER,
  FEATURE_STATUS,
  AUDIENCE,
  KNOWN_GOALS,
  ROUTES,
  ROUTES_WITHOUT_TUTORIAL,
  TUTORIALS,
  adminTutorials,
  publicTutorials,
  routesOf,
  tutorialForRoute,
  tutorialsForGoal,
  tutorialsInCategory,
  validateRegistry,
} from '../lib/registry.js';

/** Every prose field that must carry both languages. */
const TRANSLATED_FIELDS = [
  ['purpose', (t) => t.purpose],
  ['whenToUse', (t) => t.whenToUse],
  ['interpretResult', (t) => t.interpretResult],
  ['recovery', (t) => t.recovery],
  ['storage', (t) => t.storage],
  ['notGuarantee', (t) => t.notGuarantee],
];

describe('the registry validates against itself', () => {
  it('reports no problems', () => {
    expect(validateRegistry()).toEqual([]);
  });

  it('is deterministic, so a report cannot change between runs', () => {
    expect(JSON.stringify(validateRegistry())).toBe(JSON.stringify(validateRegistry()));
  });
});

describe('tutorial identity', () => {
  it('has unique ids', () => {
    const ids = TUTORIALS.map((t) => t.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('has an id for every entry', () => {
    for (const tutorial of TUTORIALS) {
      expect(typeof tutorial.id).toBe('string');
      expect(tutorial.id.trim()).not.toBe('');
    }
  });

  it('claims no route twice, so one route has one tutorial', () => {
    const claimed = new Map();
    for (const tutorial of TUTORIALS) {
      for (const route of routesOf(tutorial)) {
        expect(claimed.get(route)).toBeUndefined();
        claimed.set(route, tutorial.id);
      }
    }
  });
});

describe('route coverage', () => {
  it('covers every route the app declares that has a tutorial', () => {
    for (const [route, entry] of Object.entries(ROUTES)) {
      const owner = tutorialForRoute(route);
      if (entry.tutorial === null) {
        expect(owner).toBeNull();
      } else {
        expect(owner?.id).toBe(entry.tutorial);
      }
    }
  });

  it('covers every route except the one behind a disabled feature', () => {
    const uncovered = Object.entries(ROUTES)
      .filter(([, entry]) => entry.tutorial !== null)
      .filter(([route]) => !tutorialForRoute(route));
    expect(uncovered).toEqual([]);
  });

  it('names the disabled route explicitly rather than leaving a silent gap', () => {
    // The consistency auditor's /consistency-review, disabled by its own flag.
    // If this list ever shrinks, the feature was enabled and needs a tutorial.
    expect(ROUTES_WITHOUT_TUTORIAL).toEqual(['/consistency-review']);
  });

  it('does not publish a tutorial for a disabled feature', () => {
    for (const tutorial of TUTORIALS) {
      if (tutorial.status === FEATURE_STATUS.DISABLED) {
        expect(publicTutorials()).not.toContain(tutorial);
      }
    }
  });

  it('does not expose the disabled route in the goal index either', () => {
    // A reader following a goal must not be sent to a route that renders the
    // not-found page while the feature is off.
    for (const goal of KNOWN_GOALS) {
      for (const tutorial of tutorialsForGoal(goal)) {
        expect(tutorial.status).toBe(FEATURE_STATUS.ENABLED);
      }
    }
  });
});

describe('language coverage', () => {
  it('carries both languages for every translated field, in every tutorial', () => {
    for (const tutorial of TUTORIALS) {
      for (const [name, read] of TRANSLATED_FIELDS) {
        const value = read(tutorial);
        expect(value, `${tutorial.id}.${name} is present`).toBeTruthy();
        expect(value.en.trim(), `${tutorial.id}.${name}.en`).not.toBe('');
        expect(value.bn.trim(), `${tutorial.id}.${name}.bn`).not.toBe('');
      }
    }
  });

  it('carries both languages for every guided step', () => {
    for (const tutorial of TUTORIALS) {
      expect(tutorial.steps.length, `${tutorial.id} has steps`).toBeGreaterThan(0);
      for (const step of tutorial.steps) {
        expect(step.title.en.trim(), `${tutorial.id} step title.en`).not.toBe('');
        expect(step.title.bn.trim(), `${tutorial.id} step title.bn`).not.toBe('');
        expect(step.body.en.trim(), `${tutorial.id} step body.en`).not.toBe('');
        expect(step.body.bn.trim(), `${tutorial.id} step body.bn`).not.toBe('');
      }
    }
  });

  it('carries both languages for every mistake and field guide', () => {
    for (const tutorial of TUTORIALS) {
      for (const entry of tutorial.mistakes) {
        expect(entry.mistake.en.trim()).not.toBe('');
        expect(entry.mistake.bn.trim()).not.toBe('');
        expect(entry.fix.en.trim()).not.toBe('');
        expect(entry.fix.bn.trim()).not.toBe('');
      }
      for (const entry of tutorial.fields) {
        expect(entry.name.en.trim()).not.toBe('');
        expect(entry.name.bn.trim()).not.toBe('');
        expect(entry.meaning.en.trim()).not.toBe('');
        expect(entry.meaning.bn.trim()).not.toBe('');
      }
    }
  });

  it('writes actual Bangla script, not a Latin placeholder', () => {
    // A guide whose Bangla is machine-transliterated English is unreadable to
    // the reader who needs it most, and no other assertion would catch it.
    const hasBangla = /[\u0980-\u09FF]/;
    for (const tutorial of TUTORIALS) {
      expect(hasBangla.test(tutorial.purpose.bn), `${tutorial.id}.purpose.bn`).toBe(true);
      expect(hasBangla.test(tutorial.storage.bn), `${tutorial.id}.storage.bn`).toBe(true);
      expect(hasBangla.test(tutorial.notGuarantee.bn), `${tutorial.id}.notGuarantee.bn`).toBe(true);
    }
  });
});

describe('the trust rules', () => {
  it('never asserts an admission, award or selection outcome', () => {
    const phrases = [
      'will get you',
      'guarantees you',
      'ensure you get',
      'you will be accepted',
      'will be awarded',
    ];
    for (const tutorial of TUTORIALS) {
      const text = JSON.stringify(tutorial).toLowerCase();
      for (const phrase of phrases) {
        expect(text, `${tutorial.id} must not assert "${phrase}"`).not.toContain(phrase);
      }
    }
  });

  it('carries a limitations section on every single tutorial', () => {
    // Omission is the failure that matters: a reader should never be told what a
    // feature does without also being told what it does not do.
    for (const tutorial of TUTORIALS) {
      expect(tutorial.notGuarantee, `${tutorial.id} has notGuarantee`).toBeTruthy();
      expect(tutorial.notGuarantee.en.trim().length).toBeGreaterThan(10);
    }
  });

  it('says where the data is kept on every tutorial', () => {
    for (const tutorial of TUTORIALS) {
      expect(tutorial.storage.en.trim(), `${tutorial.id}.storage`).not.toBe('');
    }
  });
});

describe('audience separation', () => {
  it('marks exactly one tutorial admin-only, and excludes it from the public list', () => {
    const admin = adminTutorials();
    expect(admin.map((t) => t.id)).toEqual(['admin']);
    for (const tutorial of admin) {
      expect(tutorial.adminOnly).toBe(true);
      expect(tutorial.audience).toBe(AUDIENCE.ADMIN);
      expect(publicTutorials()).not.toContain(tutorial);
    }
  });

  it('lists every public route as public or signed-in, never admin', () => {
    for (const tutorial of publicTutorials()) {
      expect([AUDIENCE.PUBLIC, AUDIENCE.AUTH]).toContain(tutorial.audience);
    }
  });
});

describe('the index readers', () => {
  it('returns null for an unknown route rather than throwing', () => {
    expect(tutorialForRoute('/nope')).toBeNull();
    expect(tutorialForRoute(undefined)).toBeNull();
    expect(tutorialForRoute(null)).toBeNull();
  });

  it('groups by category, and every category has something in it', () => {
    for (const category of CATEGORY_ORDER) {
      expect(tutorialsInCategory(category).length, category).toBeGreaterThan(0);
    }
  });

  it('keeps every category known, so a typo fails rather than hiding a tutorial', () => {
    for (const tutorial of TUTORIALS) {
      expect(CATEGORY_ORDER).toContain(tutorial.category);
    }
  });

  it('keeps every goal known, for the same reason', () => {
    for (const tutorial of TUTORIALS) {
      for (const goal of tutorial.goals) {
        expect(KNOWN_GOALS).toContain(goal);
      }
    }
  });

  it('reaches a scholarship from the discover goal and a statement from the write goal', () => {
    expect(tutorialsForGoal('findScholarships').map((t) => t.id)).toContain('scholarships');
    expect(tutorialsForGoal('writeMyStatement').map((t) => t.id)).toEqual(['statement']);
  });
});
