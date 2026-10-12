/**
 * Catalogue state <-> URL parameters.
 *
 * The catalogue held search, filters, sort and page in React state only, and
 * read exactly one parameter (`country`) on the way in without writing any on
 * the way out. A filtered view was therefore unshareable, unbookmarkable, and
 * lost on reload.
 *
 * These tests pin the round-trip that fixes it, and the two ways a round-trip
 * can betray a student: losing a value they set, or resurrecting one they
 * cleared. A hand-edited URL is the third case, and it must never reach a
 * component as a state object the component cannot honour.
 */

import { describe, expect, it } from 'vitest'
import {
  activeFilterChips,
  catalogueStateFromSearch,
  catalogueStateToParams,
  CATALOGUE_PARAM_KEYS,
  DEFAULT_CATALOGUE_STATE,
  DEADLINE_MONTHS,
  hasActiveFilters,
  NO_FILTER,
  readCatalogueState,
  SORT_MODES,
  STATUS_MODES,
  writeCatalogueState,
} from './catalogueQuery.js'

describe('readCatalogueState', () => {
  it('returns the unfiltered default for an empty query', () => {
    const state = readCatalogueState(new URLSearchParams(''))
    expect(state).toEqual(DEFAULT_CATALOGUE_STATE)
  })

  it('is total for a missing or malformed params object', () => {
    expect(readCatalogueState(null)).toEqual(DEFAULT_CATALOGUE_STATE)
    expect(readCatalogueState(undefined)).toEqual(DEFAULT_CATALOGUE_STATE)
    expect(readCatalogueState({})).toEqual(DEFAULT_CATALOGUE_STATE)
  })

  it('reads every filter', () => {
    const state = readCatalogueState(new URLSearchParams(
      'q=daad&country=Germany&level=doctoral&funding=Fully%20Funded&status=open&month=4&region=Europe&tuition=yes',
    ))
    expect(state.search).toBe('daad')
    expect(state.country).toBe('Germany')
    expect(state.studyLevel).toBe('doctoral')
    expect(state.funding).toBe('Fully Funded')
    expect(state.status).toBe('open')
    expect(state.deadlineMonth).toBe('4')
    expect(state.region).toBe('Europe')
    expect(state.tuitionCoverage).toBe('yes')
  })

  it('reads a recognised sort mode', () => {
    for (const mode of SORT_MODES) {
      const state = readCatalogueState(new URLSearchParams(`sort=${mode.value}`))
      expect(state.sortBy).toBe(mode.value)
    }
  })

  it('drops an unrecognised sort mode instead of propagating it', () => {
    // "cheapest" is not a mode this catalogue has. Letting it through would
    // hand a component a sort key it cannot honour while the URL still
    // advertised the request.
    const state = readCatalogueState(new URLSearchParams('sort=cheapest'))
    expect(state.sortBy).toBe(DEFAULT_CATALOGUE_STATE.sortBy)
  })

  it('drops a malformed page rather than producing a non-integer page', () => {
    expect(readCatalogueState(new URLSearchParams('page=abc')).page).toBe(1)
    expect(readCatalogueState(new URLSearchParams('page=0')).page).toBe(1)
    expect(readCatalogueState(new URLSearchParams('page=-4')).page).toBe(1)
    expect(readCatalogueState(new URLSearchParams('page=2.7')).page).toBe(2)
  })

  it('clamps an absurd page instead of rendering an empty catalogue', () => {
    expect(readCatalogueState(new URLSearchParams('page=999999')).page).toBe(10000)
  })

  it('drops a deadline month outside 1-12', () => {
    expect(readCatalogueState(new URLSearchParams('month=13')).deadlineMonth).toBe(NO_FILTER)
    expect(readCatalogueState(new URLSearchParams('month=0')).deadlineMonth).toBe(NO_FILTER)
    expect(readCatalogueState(new URLSearchParams('month=abc')).deadlineMonth).toBe(NO_FILTER)
  })

  it('treats an explicit "all" as no filter', () => {
    const state = readCatalogueState(new URLSearchParams('country=all&status=all'))
    expect(state.country).toBe(NO_FILTER)
    expect(state.status).toBe(NO_FILTER)
  })

  it('is total for a malformed params object', () => {
    expect(readCatalogueState({ get: 'not a function' })).toEqual(DEFAULT_CATALOGUE_STATE)
  })
})

describe('writeCatalogueState', () => {
  it('writes no parameter for the unfiltered default', () => {
    expect(catalogueStateToParams(DEFAULT_CATALOGUE_STATE).toString()).toBe('')
  })

  it('omits page 1 and the default sort from the URL', () => {
    const params = catalogueStateToParams({ search: 'daad', page: 1, sortBy: DEFAULT_CATALOGUE_STATE.sortBy })
    expect(params.toString()).toBe('q=daad')
  })

  it('writes a page above 1', () => {
    const params = catalogueStateToParams({ search: 'daad', page: 3 })
    expect(params.get('page')).toBe('3')
  })

  it('deletes a parameter whose value has been cleared back to the default', () => {
    const params = new URLSearchParams('q=daad&country=Germany')
    writeCatalogueState(params, { search: '', country: NO_FILTER })
    expect(params.toString()).toBe('')
  })

  it('is total for a missing state object', () => {
    expect(catalogueStateToParams(null).toString()).toBe('')
    expect(catalogueStateToParams(undefined).toString()).toBe('')
  })

  it('returns the params object it was given, for chaining', () => {
    const params = new URLSearchParams()
    expect(writeCatalogueState(params, { search: 'daad' })).toBe(params)
  })
})

describe('round trip', () => {
  it('survives write -> read for every filter', () => {
    const original = {
      search: 'fully funded master',
      country: 'Germany',
      studyLevel: 'master',
      funding: 'Fully Funded',
      status: 'open',
      deadlineMonth: '4',
      region: 'Europe',
      tuitionCoverage: 'yes',
      sortBy: 'deadline-soon',
      page: 3,
    }
    const params = catalogueStateToParams(original)
    const restored = readCatalogueState(params)
    expect(restored).toEqual(original)
  })

  it('round-trips every exported sort mode and status mode', () => {
    for (const mode of [...SORT_MODES, ...STATUS_MODES]) {
      const key = SORT_MODES.includes(mode) ? 'sortBy' : 'status'
      const restored = readCatalogueState(catalogueStateToParams({ [key]: mode.value }))
      expect(restored[key]).toBe(mode.value)
    }
  })

  it('round-trips every deadline month', () => {
    for (const month of DEADLINE_MONTHS) {
      const restored = readCatalogueState(catalogueStateToParams({ deadlineMonth: month.value }))
      expect(restored.deadlineMonth).toBe(month.value)
    }
  })

  it('round-trips a query with characters that must be encoded', () => {
    const original = { search: "bachelor's & master's", country: 'Korea, South' }
    const restored = readCatalogueState(catalogueStateToParams(original))
    expect(restored.search).toBe(original.search)
    expect(restored.country).toBe(original.country)
  })

  it('loses nothing when a value is set and then cleared', () => {
    const params = new URLSearchParams()
    writeCatalogueState(params, { search: 'daad', country: 'Germany', page: 2 })
    writeCatalogueState(params, { search: 'daad', country: NO_FILTER, page: 2 })
    expect(params.get('q')).toBe('daad')
    expect(params.get('country')).toBeNull()
    expect(params.get('page')).toBe('2')
  })
})

describe('catalogueStateFromSearch', () => {
  it('accepts a query string with or without the leading question mark', () => {
    expect(catalogueStateFromSearch('?q=daad').search).toBe('daad')
    expect(catalogueStateFromSearch('q=daad').search).toBe('daad')
  })

  it('is total for a non-string', () => {
    expect(catalogueStateFromSearch(null)).toEqual(DEFAULT_CATALOGUE_STATE)
    expect(catalogueStateFromSearch(undefined)).toEqual(DEFAULT_CATALOGUE_STATE)
    expect(catalogueStateFromSearch(42)).toEqual(DEFAULT_CATALOGUE_STATE)
  })
})

describe('hasActiveFilters', () => {
  it('is false for the unfiltered default', () => {
    expect(hasActiveFilters(DEFAULT_CATALOGUE_STATE)).toBe(false)
  })

  it('is true when a filter is set', () => {
    expect(hasActiveFilters({ ...DEFAULT_CATALOGUE_STATE, country: 'Germany' })).toBe(true)
  })

  it('is false when only the sort or page differs', () => {
    // Sorting and paging are not filters; the reset control should not appear
    // because a student reordered a list they were already reading.
    expect(hasActiveFilters({ ...DEFAULT_CATALOGUE_STATE, sortBy: 'name-asc' })).toBe(false)
    expect(hasActiveFilters({ ...DEFAULT_CATALOGUE_STATE, page: 4 })).toBe(false)
  })

  it('is total for a non-object', () => {
    expect(hasActiveFilters(null)).toBe(false)
    expect(hasActiveFilters(undefined)).toBe(false)
  })
})

describe('activeFilterChips', () => {
  it('is empty when nothing is filtered', () => {
    expect(activeFilterChips(DEFAULT_CATALOGUE_STATE)).toEqual([])
  })

  it('names one chip per active filter, with the key to clear', () => {
    const chips = activeFilterChips({
      ...DEFAULT_CATALOGUE_STATE,
      search: 'daad',
      country: 'Germany',
      studyLevel: 'master',
      tuitionCoverage: 'yes',
    })
    expect(chips.map((chip) => chip.key).sort()).toEqual(['country', 'search', 'studyLevel', 'tuitionCoverage'])
    expect(chips.find((chip) => chip.key === 'country').label).toBe('Germany')
    expect(chips.find((chip) => chip.key === 'studyLevel').label).toBe("Master's")
    expect(chips.find((chip) => chip.key === 'tuitionCoverage').label).toBe('Tuition covered')
  })

  it('includes the sort as a removable chip', () => {
    const chips = activeFilterChips({ ...DEFAULT_CATALOGUE_STATE, sortBy: 'name-asc' })
    expect(chips.map((chip) => chip.key)).toEqual(['sortBy'])
  })

  it('does not include the page', () => {
    // A page number is not a filter; resetting it would move the student
    // somewhere they did not ask to go.
    expect(activeFilterChips({ ...DEFAULT_CATALOGUE_STATE, page: 5 })).toEqual([])
  })
})

describe('parameter names', () => {
  it('exposes a stable mapping of state key to URL parameter', () => {
    expect(CATALOGUE_PARAM_KEYS.search).toBe('q')
    expect(CATALOGUE_PARAM_KEYS.contry).toBeUndefined()
    expect(Object.values(CATALOGUE_PARAM_KEYS)).toContain('level')
    expect(Object.values(CATALOGUE_PARAM_KEYS)).toContain('tuition')
  })
})
