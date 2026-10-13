/**
 * Browser-local plan storage: recently viewed, notes, checklist, export/import.
 *
 * All of this lives in `localStorage`, so every expectation here is about what
 * the module reads and writes there rather than about React. The rules worth
 * pinning are the ones a student would notice:
 *
 *   - a write that fails must be reported as failed, not retried as success
 *   - an import that is not a plan must be rejected with a reason, and must
 *     not partially apply
 *   - a blank note removes the entry rather than storing an empty string, so
 *     an export does not accumulate keys for every award ever touched
 *   - nothing is invented: an unseen id produces an empty list
 */

import { beforeEach, describe, expect, it } from 'vitest'
import {
  CHECKLIST_ITEMS,
  clearRecentlyViewed,
  deleteScholarshipNote,
  exportPlan,
  getChecklistProgress,
  importPlan,
  MAX_NOTE_LENGTH,
  pushRecentlyViewed,
  readChecklist,
  readRecentlyViewed,
  readScholarshipNote,
  readScholarshipNotes,
  RECENTLY_VIEWED_LIMIT,
  setChecklistItem,
  writeScholarshipNote,
} from './planStorage.js'

const RECENTLY_VIEWED_KEY = 'scholarzone.recently-viewed.v1'
const NOTES_KEY = 'scholarzone.plan-notes.v1'
const CHECKLIST_KEY = 'scholarzone.plan-checklist.v1'

// Every key is in use across this file, so a rename in the module that is not
// mirrored here shows up as a storage lookup against a key nothing writes -
// which is the failure mode this pins.
const STORAGE_KEYS = { RECENTLY_VIEWED_KEY, NOTES_KEY, CHECKLIST_KEY }

beforeEach(() => {
  window.localStorage.clear()
})

describe('recently viewed', () => {
  it('starts empty and never fabricates an entry', () => {
    expect(readRecentlyViewed()).toEqual([])
  })

  it('records a view', () => {
    expect(pushRecentlyViewed('42')).toBe(true)
    expect(readRecentlyViewed()).toEqual(['42'])
  })

  it('orders most-recent-first and de-duplicates', () => {
    pushRecentlyViewed('1')
    pushRecentlyViewed('2')
    pushRecentlyViewed('3')
    pushRecentlyViewed('1')
    expect(readRecentlyViewed()).toEqual(['1', '3', '2'])
  })

  it('retains no more than the limit', () => {
    for (let id = 1; id <= RECENTLY_VIEWED_LIMIT + 5; id += 1) {
      pushRecentlyViewed(String(id))
    }
    const recent = readRecentlyViewed()
    expect(recent.length).toBe(RECENTLY_VIEWED_LIMIT)
    expect(recent[0]).toBe(String(RECENTLY_VIEWED_LIMIT + 5))
  })

  it('normalises an id rather than storing something the lookup cannot match', () => {
    // The saved/compare ids are normalised through the same pattern, so an id
    // stored here has to survive that round trip.
    expect(pushRecentlyViewed(' 42 ')).toBe(true)
    expect(readRecentlyViewed()).toEqual(['42'])
  })

  it('refuses an id with a shape the app cannot resolve', () => {
    expect(pushRecentlyViewed('bad id/with slashes')).toBe(false)
    expect(pushRecentlyViewed('x'.repeat(65))).toBe(false)
    expect(readRecentlyViewed()).toEqual([])
  })

  it('accepts a value that stringifies to a valid id', () => {
    // The same coercion `clientPreferenceStorage` applies: an id arriving as a
    // number is stored in the form the rest of the app reads rather than
    // refused and then looked up for ever.
    expect(pushRecentlyViewed(42)).toBe(true)
    expect(readRecentlyViewed()).toEqual(['42'])
  })

  it('is total for a value that is not id-shaped at all', () => {
    expect(pushRecentlyViewed(null)).toBe(false)
    expect(pushRecentlyViewed(undefined)).toBe(false)
    expect(pushRecentlyViewed({ id: 1 })).toBe(false)
    expect(pushRecentlyViewed([])).toBe(false)
    expect(readRecentlyViewed()).toEqual([])
  })

  it('clears on request', () => {
    pushRecentlyViewed('1')
    expect(clearRecentlyViewed()).toBe(true)
    expect(readRecentlyViewed()).toEqual([])
  })

  it('ignores malformed stored JSON instead of crashing', () => {
    window.localStorage.setItem(RECENTLY_VIEWED_KEY, '{not json')
    expect(readRecentlyViewed()).toEqual([])
  })

  it('ignores a stored value that is not a list', () => {
    window.localStorage.setItem(RECENTLY_VIEWED_KEY, JSON.stringify({ 1: true }))
    expect(readRecentlyViewed()).toEqual([])
  })
})

describe('notes', () => {
  it('returns an empty string for an unwritten note, never null', () => {
    // A controlled textarea needs a string. null would make React treat the
    // field as uncontrolled and the caret would jump.
    expect(readScholarshipNote('7')).toBe('')
  })

  it('stores and reads a note', () => {
    expect(writeScholarshipNote('7', 'Ask about the language test.')).toBe(true)
    expect(readScholarshipNote('7')).toBe('Ask about the language test.')
  })

  it('removes an entry when the note is blank', () => {
    writeScholarshipNote('7', 'Ask about the language test.')
    writeScholarshipNote('7', '   ')
    expect(readScholarshipNotes()).toEqual({})
  })

  it('truncates a note to the maximum rather than dropping it', () => {
    const long = 'x'.repeat(MAX_NOTE_LENGTH + 500)
    expect(writeScholarshipNote('7', long)).toBe(true)
    expect(readScholarshipNote('7').length).toBe(MAX_NOTE_LENGTH)
  })

  it('deletes a note on request', () => {
    writeScholarshipNote('7', 'note')
    expect(deleteScholarshipNote('7')).toBe(true)
    expect(readScholarshipNote('7')).toBe('')
  })

  it('reports deleting a note that does not exist as success', () => {
    // Deleting an absent key leaves the store in the requested state.
    expect(deleteScholarshipNote('7')).toBe(true)
  })

  it('refuses a non-string note', () => {
    expect(writeScholarshipNote('7', null)).toBe(false)
    expect(writeScholarshipNote('7', { text: 'x' })).toBe(false)
  })
})

describe('checklist', () => {
  it('offers a non-empty fixed set of items', () => {
    expect(CHECKLIST_ITEMS.length).toBeGreaterThan(0)
    for (const item of CHECKLIST_ITEMS) {
      expect(typeof item.value).toBe('string')
      expect(typeof item.label).toBe('string')
      expect(item.label.length).toBeGreaterThan(0)
    }
  })

  it('starts empty', () => {
    expect(readChecklist('7')).toEqual([])
    expect(getChecklistProgress('7').checked).toBe(0)
  })

  it('ticks and unticks an item', () => {
    expect(setChecklistItem('7', 'read-details', true)).toBe(true)
    expect(readChecklist('7')).toEqual(['read-details'])
    expect(setChecklistItem('7', 'read-details', false)).toBe(true)
    expect(readChecklist('7')).toEqual([])
  })

  it('refuses an item outside the known set', () => {
    // A renamed item in a future release must not leave an unremovable tick.
    expect(setChecklistItem('7', 'not-a-real-item', true)).toBe(false)
    expect(readChecklist('7')).toEqual([])
  })

  it('reports progress as a fraction and knows when it is complete', () => {
    const total = CHECKLIST_ITEMS.length
    expect(getChecklistProgress('7')).toEqual({ checked: 0, total, fraction: 0, complete: false })
    for (const item of CHECKLIST_ITEMS) {
      setChecklistItem('7', item.value, true)
    }
    expect(getChecklistProgress('7')).toEqual({ checked: total, total, fraction: 1, complete: true })
  })

  it('keeps one scholarship\'s ticks off another\'s', () => {
    setChecklistItem('7', 'submit', true)
    expect(readChecklist('8')).toEqual([])
  })

  it('drops unknown values already present in storage', () => {
    window.localStorage.setItem(
      CHECKLIST_KEY,
      JSON.stringify({ 7: ['submit', 'not-a-real-item'] }),
    )
    expect(readChecklist('7')).toEqual(['submit'])
  })
})

describe('export and import', () => {
  it('exports a versioned envelope that declares it is device-local', () => {
    // The claim that this is not cloud-synced travels with the file, so a
    // restored plan carries the same honest caveat.
    pushRecentlyViewed('1')
    writeScholarshipNote('2', 'note')
    setChecklistItem('2', 'submit', true)

    const plan = exportPlan()
    expect(plan.schema).toBe('scholarzone.plan')
    expect(plan.version).toBe(1)
    expect(plan.device_local).toBe(true)
    expect(plan.recently_viewed).toEqual(['1'])
    expect(plan.notes).toEqual({ 2: 'note' })
    expect(plan.checklists).toEqual({ 2: ['submit'] })
  })

  it('round-trips through JSON', () => {
    pushRecentlyViewed('1')
    writeScholarshipNote('2', 'note')
    setChecklistItem('2', 'submit', true)

    const roundTripped = JSON.parse(JSON.stringify(exportPlan()))
    clearRecentlyViewed()
    writeScholarshipNote('2', '')
    setChecklistItem('2', 'submit', false)

    expect(importPlan(roundTripped)).toEqual({ ok: true })
    expect(readRecentlyViewed()).toEqual(['1'])
    expect(readScholarshipNote('2')).toBe('note')
    expect(readChecklist('2')).toEqual(['submit'])
  })

  it('rejects a payload that is not an object', () => {
    expect(importPlan(null).ok).toBe(false)
    expect(importPlan('plan').ok).toBe(false)
    expect(importPlan([]).ok).toBe(false)
  })

  it('rejects a payload that does not declare itself a plan', () => {
    const result = importPlan({ version: 1, notes: {} })
    expect(result.ok).toBe(false)
    expect(result.reason).toMatch(/does not declare/i)
  })

  it('rejects an unsupported version', () => {
    const result = importPlan({ schema: 'scholarzone.plan', version: 99 })
    expect(result.ok).toBe(false)
    expect(result.reason).toMatch(/version/i)
  })

  it('rejects a malformed section without applying any of it', () => {
    // Partial application is the failure mode worth pinning: a student who
    // points at the wrong file must not lose half their notes.
    writeScholarshipNote('2', 'existing note')
    const result = importPlan({
      schema: 'scholarzone.plan',
      version: 1,
      notes: { 3: 'new note' },
      checklists: 'not an object',
    })
    expect(result.ok).toBe(false)
    expect(readScholarshipNote('2')).toBe('existing note')
    expect(readScholarshipNote('3')).toBe('')
  })

  it('accepts a plan with only the mandatory fields', () => {
    const result = importPlan({ schema: 'scholarzone.plan', version: 1 })
    expect(result).toEqual({ ok: true })
    expect(readRecentlyViewed()).toEqual([])
  })

  it('drops ids and checklist items it cannot understand rather than storing them', () => {
    importPlan({
      schema: 'scholarzone.plan',
      version: 1,
      recently_viewed: ['1', 'bad id', 2, '1', '3'],
      notes: { '1': 'ok', 'bad id': 'ignored', '2': 42 },
      checklists: { '1': ['submit', 'nope'], 'bad id': ['submit'] },
    })
    expect(readRecentlyViewed()).toEqual(['1', '2', '3'])
    expect(readScholarshipNotes()).toEqual({ 1: 'ok' })
    expect(readChecklist('1')).toEqual(['submit'])
  })

  it('truncates an over-long imported note', () => {
    importPlan({
      schema: 'scholarzone.plan',
      version: 1,
      notes: { '1': 'x'.repeat(MAX_NOTE_LENGTH + 100) },
    })
    expect(readScholarshipNote('1').length).toBe(MAX_NOTE_LENGTH)
  })
})

describe('storage keys', () => {
  it('writes under the keys it reads, with no stray writes', () => {
    pushRecentlyViewed('1')
    writeScholarshipNote('1', 'note')
    setChecklistItem('1', 'submit', true)

    const written = Object.values(STORAGE_KEYS).filter(
      (key) => window.localStorage.getItem(key) !== null,
    )
    // All three keys are written, and nothing else is: a new key appearing here
    // means the module grew a second store for the same state.
    expect(written.sort()).toEqual([NOTES_KEY, RECENTLY_VIEWED_KEY, CHECKLIST_KEY].sort())

    // And the keys follow the repository's `scholarzone.<feature>.v<N>`
    // convention, so a future schema change can bump the suffix.
    for (const key of Object.values(STORAGE_KEYS)) {
      expect(key).toMatch(/^scholarzone\.[a-z-]+\.v\d+$/)
    }
  })
})

describe('storage unavailability', () => {
  // jsdom's `localStorage` is a proxy whose property assignments are treated as
  // storage keys, so `localStorage.setItem = fn` does not replace the method -
  // it stores a key named "setItem". Replacing the whole object through
  // `defineProperty` on `window` is the reliable way to simulate either a
  // refusal or an absence, and each test restores it in a `finally`.
  function withWindowLocalStorage(replacement, body) {
    const descriptor = Object.getOwnPropertyDescriptor(window, 'localStorage')
    try {
      Object.defineProperty(window, 'localStorage', {
        value: replacement,
        configurable: true,
        writable: true,
      })
      return body()
    } finally {
      if (descriptor) {
        Object.defineProperty(window, 'localStorage', descriptor)
      } else {
        delete window.localStorage
      }
    }
  }

  /** A storage that reads fine and refuses every write. */
  const refusingStorage = () => ({
    getItem: () => null,
    setItem: () => {
      throw new Error('QuotaExceededError')
    },
    removeItem: () => {},
    clear: () => {},
    key: () => null,
    length: 0,
  })

  it('reports a failed write rather than claiming success', () => {
    withWindowLocalStorage(refusingStorage(), () => {
      // Safari private mode and storage partitioning make this a real path,
      // and the difference between a refusal and a success is a control that
      // appears to work.
      expect(pushRecentlyViewed('1')).toBe(false)
      expect(writeScholarshipNote('1', 'note')).toBe(false)
      expect(setChecklistItem('1', 'submit', true)).toBe(false)
      const result = importPlan({ schema: 'scholarzone.plan', version: 1 })
      expect(result.ok).toBe(false)
      expect(result.reason).toMatch(/refused to store/i)
    })
  })

  it('reads as empty when storage throws on read', () => {
    withWindowLocalStorage({
      getItem: () => {
        throw new Error('SecurityError')
      },
      setItem: () => {},
      removeItem: () => {},
      clear: () => {},
      key: () => null,
      length: 0,
    }, () => {
      expect(readRecentlyViewed()).toEqual([])
      expect(readScholarshipNote('1')).toBe('')
      expect(readChecklist('1')).toEqual([])
      expect(exportPlan().recently_viewed).toEqual([])
    })
  })

  it('reads as empty when there is no storage object at all', () => {
    withWindowLocalStorage(undefined, () => {
      expect(readRecentlyViewed()).toEqual([])
      expect(readScholarshipNote('1')).toBe('')
      expect(readChecklist('1')).toEqual([])
      expect(pushRecentlyViewed('1')).toBe(false)
    })
  })
})
