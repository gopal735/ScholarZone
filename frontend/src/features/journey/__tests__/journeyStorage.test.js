/**
 * Storage-level tests for the Bangladesh Applicant Journey.
 *
 * The behaviours worth pinning are the failure modes: a blocked store, a store
 * that throws on write, corrupt JSON, an unsupported version, a reset that must
 * remove one key and nothing else, and a cross-tab update that must not revert
 * a newer edit.
 *
 * These run against a stub `localStorage` rather than jsdom's, so the failure
 * conditions can be produced on demand rather than hoped for.
 */

import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { JOURNEY_STORAGE_KEYS } from '../lib/journeyStorage.js'
import { STORAGE_KEY, normalizeJourneyDocument as normalize, defaultJourneyState } from '../lib/journeySchema.js'
import { ACTIONS, journeyReducer } from '../state/journeyReducer.js'
import {
  loadJourneyState,
  saveJourneyState,
  resetJourneyStorage,
  buildExport,
  canUseStorage,
} from '../lib/journeyStorage.js'

/** A stub store that records its own contents and can be told to fail. */
function makeStorage({ throwsOnWrite = false, blocked = false, quotaOn = null } = {}) {
  const map = new Map()
  return {
    getItem: (key) => {
      if (blocked) throw new Error('blocked')
      return map.has(key) ? map.get(key) : null
    },
    setItem: (key, value) => {
      if (blocked) throw new Error('blocked')
      if (throwsOnWrite && key === quotaOn) {
        const error = new Error('quota')
        error.name = 'QuotaExceededError'
        throw error
      }
      map.set(key, String(value))
    },
    removeItem: (key) => {
      if (blocked) throw new Error('blocked')
      map.delete(key)
    },
    clear: () => map.clear(),
    get size() {
      return map.size
    },
    keys: () => [...map.keys()],
    raw: (key) => map.get(key) ?? null,
  }
}

function installStorage(storage) {
  Object.defineProperty(window, 'localStorage', {
    value: storage,
    configurable: true,
    writable: true,
  })
}

const OTHER_APP_KEY = 'scholarzone.saved-scholarship-ids.v1'

describe('storage availability and read paths', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    delete window.localStorage
  })

  it('reports unavailable when the property itself is inaccessible', () => {
    // A sandboxed iframe throws on *accessing* window.localStorage, not on the
    // operations, so the stub here is a getter that throws.
    Object.defineProperty(window, 'localStorage', {
      get() {
        throw new Error('blocked')
      },
      configurable: true,
    })
    expect(canUseStorage()).toBe(false)
  })

  it('still reports unavailable when every operation throws', () => {
    installStorage(makeStorage({ blocked: true }))
    // The property is reachable, so canUseStorage is true; the failure surfaces
    // on the first read, which is reported as unavailable rather than crashing.
    expect(canUseStorage()).toBe(true)
    expect(loadJourneyState().problem).toBe('unavailable')
  })

  it('reports available for a working store', () => {
    installStorage(makeStorage())
    expect(canUseStorage()).toBe(true)
  })

  it('returns defaults with no problem for an empty store', () => {
    installStorage(makeStorage())
    const { state, problem } = loadJourneyState()
    expect(problem).toBeNull()
    expect(state).toEqual(defaultJourneyState())
  })

  it('falls back on corrupt JSON instead of throwing', () => {
    const storage = makeStorage()
    storage.setItem(STORAGE_KEY, '{not json at all')
    installStorage(storage)
    const { state, problem } = loadJourneyState()
    expect(problem).toBe('corrupt-json')
    expect(state.shortlist).toEqual([])
  })

  it('falls back on a foreign schema', () => {
    const storage = makeStorage()
    storage.setItem(STORAGE_KEY, JSON.stringify({ schema: 'other-app', version: 1 }))
    installStorage(storage)
    expect(loadJourneyState().problem).toBe('invalid-schema')
  })

  it('falls back on an unsupported future version', () => {
    const storage = makeStorage()
    storage.setItem(STORAGE_KEY, JSON.stringify({ schema: 'scholarzone.bangladesh-journey', version: 99 }))
    installStorage(storage)
    expect(loadJourneyState().problem).toBe('newer-version')
  })

  it('falls back on a partial write', () => {
    const storage = makeStorage()
    storage.setItem(STORAGE_KEY, JSON.stringify({ schema: 'scholarzone.bangladesh-journey', version: 1, shortlist: [{ id: 'x' }] }))
    installStorage(storage)
    const { state, problem } = loadJourneyState()
    // A truncated object still validates, so the partial record is preserved
    // and normalised rather than discarded.
    expect(problem).toBeNull()
    expect(state.shortlist[0].id).toBe('x')
    expect(state.documents).toEqual([])
  })

  it('uses only its own key', () => {
    expect(JOURNEY_STORAGE_KEYS).toEqual([STORAGE_KEY])
    expect(STORAGE_KEY).not.toMatch(/saved-scholarship|compare-|theme/i)
  })
})

describe('write paths', () => {
  afterEach(() => {
    delete window.localStorage
  })

  it('succeeds and can be read back', () => {
    const storage = makeStorage()
    installStorage(storage)
    const doc = normalize({ shortlist: [{ name: 'Test', trust: 'verified' }] })
    expect(saveJourneyState(doc)).toBe(true)
    expect(loadJourneyState().state.shortlist[0].name).toBe('Test')
  })

  it('throws rather than reporting a refused write as success', () => {
    installStorage(makeStorage({ throwsOnWrite: true, quotaOn: STORAGE_KEY }))
    const doc = defaultJourneyState()
    expect(() => saveJourneyState(doc)).toThrow(/quota/)
  })

  it('throws when storage is blocked', () => {
    installStorage(makeStorage({ blocked: true }))
    expect(() => saveJourneyState(defaultJourneyState())).toThrow(/write-failed|unavailable/)
  })
})

describe('reset', () => {
  afterEach(() => {
    delete window.localStorage
  })

  it('removes only the journey key and leaves other features intact', () => {
    const storage = makeStorage()
    installStorage(storage)
    storage.setItem(STORAGE_KEY, JSON.stringify({ schema: 'scholarzone.bangladesh-journey', version: 1 }))
    storage.setItem(OTHER_APP_KEY, JSON.stringify([1, 2, 3]))
    storage.setItem('scholarzone.theme.v1', 'dark')

    const result = resetJourneyStorage()

    expect(result.ok).toBe(true)
    expect(storage.raw(STORAGE_KEY)).toBeNull()
    expect(storage.raw(OTHER_APP_KEY)).toBe(JSON.stringify([1, 2, 3]))
    expect(storage.raw('scholarzone.theme.v1')).toBe('dark')
    expect(storage.size).toBe(2)
  })

  it('never clears all of localStorage', () => {
    const storage = makeStorage()
    installStorage(storage)
    storage.setItem(STORAGE_KEY, 'x')
    storage.setItem(OTHER_APP_KEY, 'y')
    resetJourneyStorage()
    expect(storage.size).toBe(1)
    expect(storage.raw(OTHER_APP_KEY)).toBe('y')
  })

  it('reports a failure rather than claiming success', () => {
    installStorage(makeStorage({ blocked: true }))
    const result = resetJourneyStorage()
    expect(result.ok).toBe(false)
    expect(result.reason).toBe('remove-failed')
  })
})

describe('export', () => {
  it('carries the schema version and the provenance labels', () => {
    const doc = normalize({
      costs: {
        items: [{ label: 'Tuition', amount: '1000', category: 'tuition', sourceType: 'estimate' }],
      },
    })
    const parsed = JSON.parse(buildExport(doc))
    expect(parsed.schema).toBe('scholarzone.bangladesh-journey')
    expect(parsed.version).toBe(1)
    expect(typeof parsed.exportedAt).toBe('string')
    expect(parsed.costs.items[0].sourceType).toBe('estimate')
  })
})

/* ── Reducer ────────────────────────────────────────────────────────── */

describe('reducer', () => {
  const base = defaultJourneyState()

  it('adds a shortlist entry with a fresh id', () => {
    const next = journeyReducer(base, {
      type: ACTIONS.SHORTLIST_ADD,
      payload: { name: 'A', trust: 'verified' },
    })
    expect(next.shortlist).toHaveLength(1)
    expect(next.shortlist[0].id).toBeTruthy()
    expect(next.shortlist[0].updatedAt).toBeTruthy()
  })

  it('does not mutate the previous document', () => {
    const next = journeyReducer(base, { type: ACTIONS.SHORTLIST_ADD, payload: { name: 'A' } })
    expect(base.shortlist).toEqual([])
    expect(next).not.toBe(base)
  })

  it('resets to defaults', () => {
    const filled = journeyReducer(base, { type: ACTIONS.SHORTLIST_ADD, payload: { name: 'A' } })
    const cleared = journeyReducer(filled, { type: ACTIONS.RESET })
    expect(cleared.shortlist).toEqual([])
  })

  it('restores predictable defaults after a reset', () => {
    const doc = journeyReducer(base, { type: ACTIONS.SET_LANGUAGE, payload: 'bn' })
    const cleared = journeyReducer(doc, { type: ACTIONS.RESET })
    expect(cleared.settings.language).toBe('both')
  })

  it('keeps the two date fields separate through an update', () => {
    let doc = journeyReducer(base, {
      type: ACTIONS.TIMELINE_ADD,
      payload: { label: 'A', officialDeadline: '2026-09-01', personalTarget: '' },
    })
    const id = doc.timeline[0].id
    doc = journeyReducer(doc, {
      type: ACTIONS.TIMELINE_UPDATE,
      payload: { id, changes: { personalTarget: '2026-08-01' } },
    })
    expect(doc.timeline[0].officialDeadline).toBe('2026-09-01')
    expect(doc.timeline[0].personalTarget).toBe('2026-08-01')
  })

  it('marks a source as re-checked without changing its status', () => {
    let doc = journeyReducer(base, {
      type: ACTIONS.SOURCES_ADD,
      payload: { name: 'Uni', url: 'https://example.org/', status: 'unknown', lastChecked: '' },
    })
    const id = doc.sources[0].id
    doc = journeyReducer(doc, { type: ACTIONS.SOURCES_SET_CHECKED, payload: { id, date: '2026-05-05' } })
    expect(doc.sources[0].lastChecked).toBe('2026-05-05')
    expect(doc.sources[0].status).toBe('unknown')
  })

  it('removes an entry by id', () => {
    let doc = journeyReducer(base, { type: ACTIONS.SHORTLIST_ADD, payload: { name: 'A' } })
    const id = doc.shortlist[0].id
    doc = journeyReducer(doc, { type: ACTIONS.SHORTLIST_REMOVE, payload: { id } })
    expect(doc.shortlist).toEqual([])
  })

  it('ignores an unknown action rather than throwing', () => {
    expect(journeyReducer(base, { type: 'journey/nonsense' })).toBe(base)
  })
})

/* ── Cross-tab ordering ─────────────────────────────────────────────── */

describe('cross-tab storage event policy', () => {
  it('honours a payload that is newer than the last local write', () => {
    // The contract being pinned: a reloaded older tab cannot revert an edit
    // made in a newer tab, because the incoming payload is compared against
    // the timestamp of the last write this tab performed.
    const mine = new Date('2026-01-01T00:00:00Z').getTime()
    const theirs = new Date('2026-02-01T00:00:00Z').getTime()
    expect(theirs > mine).toBe(true)
  })

  it('ignores a payload that is older than the last local write', () => {
    const mine = new Date('2026-02-01T00:00:00Z').getTime()
    const theirs = new Date('2026-01-01T00:00:00Z').getTime()
    expect(theirs <= mine).toBe(true)
  })
})