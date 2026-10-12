/**
 * Catalogue state <-> URL query parameters.
 *
 * The catalogue held its search, filters, sort and page in React state only.
 * `ScholarshipsPage` read exactly one parameter, `country`, on the way in and
 * never wrote any of them on the way out. Three consequences a student hits
 * immediately:
 *
 *   - A filtered view cannot be shared or bookmarked. Copying the address bar
 *     produces a link to the unfiltered directory.
 *   - The browser's Back button does not step through filter changes. It
 *     leaves the page, because nothing was ever pushed onto the history entry.
 *   - A reload after refining to page 4 returns to page 1 of everything.
 *
 * So state is serialised to the query string and back. The serialisation is
 * pure and tested separately from React, because the failure mode worth testing
 * is a round-trip that loses or invents a value, not what a component does with
 * it.
 *
 * Two decisions are deliberate:
 *
 *   - Only active values are written. A URL with `?country=All&degree=All` is
 *     noise, and it also reads as "someone filtered by All" to anything that
 *     inspects the link.
 *   - An unrecognised value is dropped rather than propagated. A hand-edited
 *     `?sort=cheapest` must not reach a component as a sort key it cannot
 *     honour, because the component would either throw or silently fall back
 *     while the URL still advertised the request.
 *
// The canonical strategy is untouched. `robots.txt` already disallows `/*?*`
// and `ScholarshipsPage` already declares `noindex, follow` for any query
 * variant, so a shared filter link stays shareable without becoming a page
 * search engines are asked to index.
 */

import { NO_FILTER } from './catalogueValues.js'
import { studyLevelLabel } from '../utils/studyLevel.js'
import { tuitionCoverageLabel } from '../utils/fundingFacts.js'

// Re-exported so components that already import the sentinel from here keep
// working, and so exactly one place owns the value.
export { NO_FILTER }

/** The filter keys, with the URL parameter name each maps to. */
export const CATALOGUE_PARAM_KEYS = Object.freeze({
  search: 'q',
  country: 'country',
  studyLevel: 'level',
  funding: 'funding',
  status: 'status',
  deadlineMonth: 'month',
  region: 'region',
  tuitionCoverage: 'tuition',
  sortBy: 'sort',
  page: 'page',
})

export const SORT_MODES = Object.freeze([
  { value: 'relevance', label: 'Best match' },
  { value: 'recommended', label: 'Recommended' },
  { value: 'deadline-soon', label: 'Deadline: soonest first' },
  { value: 'deadline-latest', label: 'Deadline: latest first' },
  { value: 'name-asc', label: 'Name: A to Z' },
  { value: 'name-desc', label: 'Name: Z to A' },
  { value: 'fully-funded', label: 'Fully funded first' },
  { value: 'recently-updated', label: 'Recently updated' },
  { value: 'recently-added', label: 'Recently added' },
])

export const STATUS_MODES = Object.freeze([
  { value: 'open', label: 'Open' },
  { value: 'closing-soon', label: 'Closing soon' },
  { value: 'upcoming', label: 'Upcoming' },
  { value: 'closed', label: 'Closed' },
])

export const DEADLINE_MONTHS = Object.freeze(
  Array.from({ length: 12 }, (_, index) => ({
    value: String(index + 1),
    label: new Intl.DateTimeFormat('en', { month: 'long' }).format(new Date(2026, index, 1)),
  })),
)

/** The state a catalogue page holds, in its default (unfiltered) form. */
export const DEFAULT_CATALOGUE_STATE = Object.freeze({
  search: '',
  country: 'all',
  studyLevel: 'all',
  funding: 'all',
  status: 'all',
  deadlineMonth: 'all',
  region: 'all',
  tuitionCoverage: 'all',
  sortBy: 'recommended',
  page: 1,
})

const MAX_PAGE = 10_000

/** True for a string that carries usable text. Never coerces a falsy value. */
function isText(value) {
  return typeof value === 'string' && value.trim() !== ''
}

/**
 * Read catalogue state out of a `URLSearchParams`-shaped object.
 *
 * Every value is validated against what it is allowed to be, and a value that
 * fails is dropped to its default. That is what makes a hand-edited URL safe:
 * the component never sees a sort mode or a page number it cannot honour.
 *
 * @param {URLSearchParams|{get: (k: string) => string|null}} params
 * @returns {object} a complete catalogue state object
 */
export function readCatalogueState(params) {
  const read = (key) => {
    if (!params || typeof params.get !== 'function') {
      return null
    }
    return params.get(key)
  }

  const state = { ...DEFAULT_CATALOGUE_STATE }

  const search = read(CATALOGUE_PARAM_KEYS.search)
  if (isText(search)) {
    state.search = search.trim()
  }

  const country = read(CATALOGUE_PARAM_KEYS.country)
  if (isText(country) && country !== NO_FILTER) {
    state.country = country.trim()
  }

  const studyLevel = read(CATALOGUE_PARAM_KEYS.studyLevel)
  if (isText(studyLevel) && studyLevel !== NO_FILTER) {
    state.studyLevel = studyLevel.trim()
  }

  const funding = read(CATALOGUE_PARAM_KEYS.funding)
  if (isText(funding) && funding !== NO_FILTER) {
    state.funding = funding.trim()
  }

  const status = read(CATALOGUE_PARAM_KEYS.status)
  if (isText(status) && status !== NO_FILTER) {
    state.status = status.trim()
  }

  const deadlineMonth = read(CATALOGUE_PARAM_KEYS.deadlineMonth)
  if (isText(deadlineMonth) && deadlineMonth !== NO_FILTER) {
    const month = Number(deadlineMonth.trim())
    if (Number.isInteger(month) && month >= 1 && month <= 12) {
      state.deadlineMonth = String(month)
    }
  }

  const region = read(CATALOGUE_PARAM_KEYS.region)
  if (isText(region) && region !== NO_FILTER) {
    state.region = region.trim()
  }

  const tuitionCoverage = read(CATALOGUE_PARAM_KEYS.tuitionCoverage)
  if (isText(tuitionCoverage) && tuitionCoverage !== NO_FILTER) {
    state.tuitionCoverage = tuitionCoverage.trim()
  }

  const sortBy = read(CATALOGUE_PARAM_KEYS.sortBy)
  if (isText(sortBy)) {
    const trimmed = sortBy.trim()
    if (SORT_MODES.some((mode) => mode.value === trimmed)) {
      state.sortBy = trimmed
    }
  }

  const page = read(CATALOGUE_PARAM_KEYS.page)
  if (isText(page)) {
    const parsed = Number(page.trim())
    // A fractional or negative page is not a page. Clamped rather than
    // rejected so `?page=0` still shows the first page instead of defaulting
    // to it with no explanation, but a non-numeric value is dropped entirely.
    if (Number.isFinite(parsed)) {
      state.page = Math.min(Math.max(1, Math.floor(parsed)), MAX_PAGE)
    }
  }

  return state
}

/**
 * Write catalogue state into a `URLSearchParams`.
 *
 * Only values that differ from the default are written, and the object is
 * mutated in place so a caller can build one URL rather than two.
 */
export function writeCatalogueState(params, state) {
  if (!params || typeof params.set !== 'function') {
    return params
  }

  const next = { ...DEFAULT_CATALOGUE_STATE, ...(state || {}) }

  const entries = [
    [CATALOGUE_PARAM_KEYS.search, next.search],
    [CATALOGUE_PARAM_KEYS.country, next.country],
    [CATALOGUE_PARAM_KEYS.studyLevel, next.studyLevel],
    [CATALOGUE_PARAM_KEYS.funding, next.funding],
    [CATALOGUE_PARAM_KEYS.status, next.status],
    [CATALOGUE_PARAM_KEYS.deadlineMonth, next.deadlineMonth],
    [CATALOGUE_PARAM_KEYS.region, next.region],
    [CATALOGUE_PARAM_KEYS.tuitionCoverage, next.tuitionCoverage],
    [CATALOGUE_PARAM_KEYS.sortBy, next.sortBy],
    [CATALOGUE_PARAM_KEYS.page, next.page],
  ]

  for (const [key, value] of entries) {
    if (value === undefined || value === null || value === '' || value === NO_FILTER) {
      params.delete(key)
      continue
    }

    // Page 1 is the default and is omitted, so a link to the first page of a
    // filtered view is not longer than it needs to be.
    if (key === CATALOGUE_PARAM_KEYS.page && Number(value) <= 1) {
      params.delete(key)
      continue
    }

    if (key === CATALOGUE_PARAM_KEYS.sortBy && value === DEFAULT_CATALOGUE_STATE.sortBy) {
      params.delete(key)
      continue
    }

    params.set(key, String(value))
  }

  return params
}

/** Build a fresh `URLSearchParams` from catalogue state. */
export function catalogueStateToParams(state) {
  const params = new URLSearchParams()
  return writeCatalogueState(params, state)
}

/** Read catalogue state out of a query string, with or without a leading `?`. */
export function catalogueStateFromSearch(search) {
  const normalized = typeof search === 'string' ? search.replace(/^\?/, '') : ''
  return readCatalogueState(new URLSearchParams(normalized))
}

/** The keys a URL carries that are not part of catalogue state. */
export function foreignParams(params, catalogueKeys = Object.values(CATALOGUE_PARAM_KEYS)) {
  if (!params || typeof params.forEach !== 'function') {
    return []
  }

  const allowed = new Set(catalogueKeys)
  const extra = []
  params.forEach((value, key) => {
    if (!allowed.has(key)) {
      extra.push(key)
    }
  })
  return extra
}

/**
 * True when a state differs from the unfiltered default, so the page can show
 * a reset control and a result count that reflects a filter.
 */
export function hasActiveFilters(state) {
  if (!state || typeof state !== 'object') {
    return false
  }

  const keys = Object.keys(DEFAULT_CATALOGUE_STATE).filter((key) => (
    key !== 'page' && key !== 'sortBy'
  ))

  return keys.some((key) => {
    const value = state[key]
    return value !== undefined && value !== null && value !== '' && value !== NO_FILTER
  })
}

/** Human labels for the filter values that are codes rather than data. */
export function filterLabel(key, value) {
  if (value === NO_FILTER || value === '' || value === null || value === undefined) {
    return null
  }

  switch (key) {
    case 'studyLevel':
      return studyLevelLabel(value)
    case 'sortBy': {
      const mode = SORT_MODES.find((entry) => entry.value === value)
      return mode ? mode.label : value
    }
    case 'status': {
      const mode = STATUS_MODES.find((entry) => entry.value === value)
      return mode ? mode.label : value
    }
    case 'deadlineMonth': {
      const month = DEADLINE_MONTHS.find((entry) => entry.value === String(value))
      return month ? month.label : value
    }
    case 'tuitionCoverage':
      return tuitionCoverageLabel(value)
    default:
      return String(value)
  }
}

/**
 * The removable chips the filter bar renders, one per active filter.
 *
 * Each carries the state key it clears, so a caller can remove exactly one
 * filter without resetting the others - the failure mode the brief calls out
 * as "never reset the entire catalogue unnecessarily after a small
 * interaction".
 */
export function activeFilterChips(state) {
  if (!state || typeof state !== 'object') {
    return []
  }

  const chipKeys = ['search', 'country', 'studyLevel', 'funding', 'status', 'region', 'tuitionCoverage', 'deadlineMonth', 'sortBy']

  return chipKeys
    .map((key) => {
      // The default sort is not an active choice. Without this guard the chip
      // row renders "Recommended" on a page where nobody chose a sort, which
      // is both noise and a control whose removal appears to change nothing.
      if (key === 'sortBy' && state.sortBy === DEFAULT_CATALOGUE_STATE.sortBy) {
        return null
      }
      const label = filterLabel(key, state[key])
      if (!label) {
        return null
      }
      return { key, label, value: state[key] }
    })
    .filter(Boolean)
}
