import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import ScholarshipCard from './ScholarshipCard'
import CatalogueSourceNotice from './CatalogueSourceNotice'
import { scholarships as seedScholarships } from '../data/scholarships'
import { fetchScholarships } from '../services/scholarshipService'
import { searchRecords } from '../services/catalogueSearch.js'
import {
  activeFilterChips,
  catalogueStateToParams,
  DEFAULT_CATALOGUE_STATE,
  hasActiveFilters,
  NO_FILTER,
  readCatalogueState,
  SORT_MODES,
} from '../services/catalogueQuery.js'
import {
  STUDY_LEVELS,
  UNSPECIFIED_LEVEL,
  matchesStudyLevel,
  studyLevelLabel,
} from '../utils/studyLevel.js'
import { TUITION_COVERAGE_OPTIONS, matchesTuitionCoverage } from '../utils/fundingFacts.js'
import { getScholarshipStatusCode } from '../utils/scholarshipPresentation.js'
import './ScholarshipList.css'

const PAGE_SIZE = 12
const SEARCH_DEBOUNCE_MS = 250

/** Focus the search field with `/` unless the user is already typing. */
const SEARCH_SHORTCUT_KEY = '/'

/** Regions the snapshot actually carries, so the menu is never a guess. */
const FALLBACK_REGIONS = ['Europe', 'Asia', 'North America', 'Oceania', 'Latin America', 'Global', 'Africa', 'Middle East']

/* Human labels for the values that are stored as codes. Months are the stored
   calendar month, not a name, so they need a lookup. */
const MONTH_NAMES = [
  '', 'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

const STATUS_LABELS = {
  open: 'Open',
  'closing-soon': 'Closing soon',
  upcoming: 'Upcoming',
  closed: 'Closed',
}

const ALL = 'All'
const ALL_VALUE = NO_FILTER

function toValidTimestamp(value) {
  if (typeof value !== 'string' || value.trim() === '') {
    return null
  }

  const timestamp = Date.parse(value)
  return Number.isNaN(timestamp) ? null : timestamp
}

function compareNullableTimestamps(firstValue, secondValue, direction = 'asc') {
  if (firstValue === null && secondValue === null) {
    return 0
  }
  if (firstValue === null) {
    return 1
  }
  if (secondValue === null) {
    return -1
  }
  return direction === 'asc' ? firstValue - secondValue : secondValue - firstValue
}

/**
 * Urgency order for the local (non-snapshot) sort path.
 *
 * `upcoming` was missing, so the comparison returned `undefined` and the sort
 * silently left those records wherever they happened to be - 107 of 618 records.
 * A complete map is the whole fix: every status has a rank, so the comparison
 * is always a number.
 */
const STATUS_ORDER = { open: 0, 'closing-soon': 1, upcoming: 2, closed: 3 }

function sortLocalScholarships(items, sortBy) {
  const indexedItems = items.map((scholarship, index) => ({ scholarship, index }))

  indexedItems.sort((first, second) => {
    const firstTitle = typeof first.scholarship.title === 'string' ? first.scholarship.title : ''
    const secondTitle = typeof second.scholarship.title === 'string' ? second.scholarship.title : ''
    const comparison = (() => {
      switch (sortBy) {
        case 'relevance':
          // A relevance ordering is only meaningful with a query, which the
          // snapshot path already applied. With no query the order is the
          // recommended one rather than an arbitrary reshape.
          return 0
        case 'recommended':
          return Number(second.scholarship.verification_status === 'active')
            - Number(first.scholarship.verification_status === 'active')
            || STATUS_ORDER[getScholarshipStatusCode(first.scholarship)]
            - STATUS_ORDER[getScholarshipStatusCode(second.scholarship)]
        case 'recently-added':
        case 'recently-updated':
          return compareNullableTimestamps(
            toValidTimestamp(first.scholarship.updated_at || first.scholarship.created_at),
            toValidTimestamp(second.scholarship.updated_at || second.scholarship.created_at),
            'desc',
          )
        case 'deadline-earliest':
        case 'deadline-soon':
          return compareNullableTimestamps(
            toValidTimestamp(first.scholarship.deadline),
            toValidTimestamp(second.scholarship.deadline),
          )
        case 'deadline-latest':
          return compareNullableTimestamps(
            toValidTimestamp(first.scholarship.deadline),
            toValidTimestamp(second.scholarship.deadline),
            'desc',
          )
        case 'name-asc':
          return firstTitle.localeCompare(secondTitle, undefined, { sensitivity: 'base' })
        case 'name-desc':
          return secondTitle.localeCompare(firstTitle, undefined, { sensitivity: 'base' })
        case 'fully-funded':
          return Number(second.scholarship.funding === 'Fully Funded')
            - Number(first.scholarship.funding === 'Fully Funded')
        case 'default':
        default:
          return compareNullableTimestamps(
            toValidTimestamp(first.scholarship.updated_at),
            toValidTimestamp(second.scholarship.updated_at),
            'desc',
          )
      }
    })()

    return comparison || first.index - second.index
  })

  return indexedItems.map(({ scholarship }) => scholarship)
}

function getLocalDeadlineMonth(scholarship) {
  const timestamp = toValidTimestamp(scholarship.deadline_date || scholarship.deadline)
  return timestamp === null ? null : new Date(timestamp).getMonth() + 1
}

/**
 * The local filtering path, used only when the bundled snapshot cannot be read.
 *
 * It mirrors the snapshot path's semantics rather than being a second
 * implementation of them, because the two disagreed before this: the local
 * path filtered on a locally derived status while the service filtered on the
 * stored one, so the same URL produced different result sets depending on
 * which path answered. The filters themselves (`searchRecords`,
 * `matchesStudyLevel`, `matchesTuitionCoverage`, the status code helper) are
 * imported from the same modules the service uses.
 */
function filterLocalScholarships(items, { search, country, degree, funding, deadlineMonth, status, region, studyLevel, tuitionCoverage, sortBy }) {
  let filtered = [...items]

  if (search.trim() !== '') {
    // searchRecords applies AND token matching and ranks; the previous local
    // path used a single substring test, so "  daad " and "daad." both matched
    // nothing here while working on the snapshot path.
    filtered = searchRecords(filtered, search)
  }

  if (country && country !== ALL) {
    filtered = filtered.filter((s) => s.country?.toLowerCase() === country.toLowerCase())
  }

  if (studyLevel && studyLevel !== ALL) {
    filtered = filtered.filter((s) => matchesStudyLevel(s, studyLevel))
  }

  if (degree && degree !== ALL) {
    filtered = filtered.filter((s) => s.degree?.toLowerCase() === degree.toLowerCase())
  }

  if (funding && funding !== ALL) {
    filtered = filtered.filter((s) => s.funding?.toLowerCase() === funding.toLowerCase())
  }

  if (region && region !== ALL) {
    filtered = filtered.filter((s) => s.region?.toLowerCase() === region.toLowerCase())
  }

  if (tuitionCoverage && tuitionCoverage !== ALL) {
    filtered = filtered.filter((s) => matchesTuitionCoverage(s, tuitionCoverage))
  }

  if (deadlineMonth && deadlineMonth !== ALL) {
    filtered = filtered.filter((s) => getLocalDeadlineMonth(s) === Number(deadlineMonth))
  }

  if (status && status !== ALL) {
    filtered = filtered.filter((s) => getScholarshipStatusCode(s) === status)
  }

  return sortLocalScholarships(filtered, sortBy)
}

function LoadingCards() {
  return (
    <div className="scholarship-grid scholarship-grid--loading" aria-label="Loading scholarships" aria-busy="true">
      {[1, 2, 3].map((item) => (
        <div key={item} className="scholarship-card-skeleton" aria-hidden="true">
          <span className="scholarship-card-skeleton__line scholarship-card-skeleton__line--badge" />
          <span className="scholarship-card-skeleton__line scholarship-card-skeleton__line--title" />
          <span className="scholarship-card-skeleton__line" />
          <span className="scholarship-card-skeleton__line" />
          <span className="scholarship-card-skeleton__line scholarship-card-skeleton__line--deadline" />
          <span className="scholarship-card-skeleton__line scholarship-card-skeleton__line--button" />
        </div>
      ))}
    </div>
  )
}

/**
 * The catalogue.
 *
 * Two modes, and the difference between them is only where the records come
 * from. As a directory (`items` is absent) it fetches from the bundled
 * snapshot and pages server-side-in-memory; with `items` supplied it filters
 * the list it was handed, which is how `/saved` reuses this component.
 *
 * State lives in the URL, so a filtered view is shareable, bookmarkable and
 * survives a reload. It used to live in React state only, with one parameter
 * (`country`) read on the way in and none written on the way out - so copying
 * the address bar produced a link to the unfiltered directory, Back did not
 * step through filter changes, and a reload after page 4 returned to page 1.
 */
export default function ScholarshipList({ items, initialCountry }) {
  const isDirectory = !Array.isArray(items)
  const localItems = Array.isArray(items) ? items : seedScholarships

  const [searchParams, setSearchParams] = useSearchParams()
  const urlState = useMemo(() => readCatalogueState(searchParams), [searchParams])

  // The state object. It is derived from the URL rather than mirrored into
  // component state, so the two cannot drift and a Back navigation is a state
  // change rather than an event that has to be caught.
  const {
    search, country, studyLevel, funding, status, deadlineMonth, region, tuitionCoverage, sortBy, page,
  } = urlState

  // A country passed by the page that owns the route wins on first render
  // only, so a /countries link lands filtered and a student can still change
  // it afterwards without the page fighting them.
  const [seededCountry] = useState(() => initialCountry ?? null)
  const effectiveCountry = useMemo(() => {
    if (!isDirectory || seededCountry === null || country !== DEFAULT_CATALOGUE_STATE.country) {
      return country
    }
    return seededCountry
  }, [country, isDirectory, seededCountry])

  const [requestVersion, setRequestVersion] = useState(0)
  const [apiDirectory, setApiDirectory] = useState({ items: [], pagination: null })
  const [catalogueSource, setCatalogueSource] = useState(null)
  const [loadState, setLoadState] = useState(isDirectory ? 'loading' : 'local')
  const [apiError, setApiError] = useState('')
  const searchInputRef = useRef(null)
  const requestIdRef = useRef(0)
  const resultsRef = useRef(null)

  const localResults = useMemo(
    () => filterLocalScholarships(localItems, {
      search, country: effectiveCountry, degree: ALL, funding, deadlineMonth, status,
      region, studyLevel, tuitionCoverage, sortBy,
    }),
    [localItems, search, effectiveCountry, funding, deadlineMonth, status, region, studyLevel, tuitionCoverage, sortBy],
  )

  /* The selectable values, from the catalogue that was actually loaded. */
  const filterOptions = catalogueSource?.meta?.filter_options || null

  const optionLists = useMemo(() => {
    if (filterOptions) {
      return {
        countries: [ALL_VALUE, ...(filterOptions.countries || [])],
        degrees: [ALL_VALUE, ...(filterOptions.degrees || [])],
        fundingTypes: [ALL_VALUE, ...(filterOptions.funding_types || [])],
        statuses: [ALL_VALUE, ...(filterOptions.statuses || [])],
        deadlineMonths: [ALL_VALUE, ...(filterOptions.deadline_months || []).map(String)],
        regions: [ALL_VALUE, ...(filterOptions.regions || [])],
      }
    }
    return {
      countries: [ALL_VALUE],
      degrees: [ALL_VALUE],
      fundingTypes: [ALL_VALUE],
      statuses: [ALL_VALUE],
      deadlineMonths: [ALL_VALUE],
      regions: [ALL_VALUE, ...FALLBACK_REGIONS],
    }
  }, [filterOptions])

  // The seed country is not in the snapshot's country list if the page that
  // owns the route chose it from a different source. It is added so the select
  // can show it rather than silently displaying the first option - the exact
  // "control that contradicts the page it is on" defect this fixes.
  const countryOptions = useMemo(() => {
    if (seededCountry === null || !isDirectory || optionLists.countries.includes(seededCountry)) {
      return optionLists.countries
    }
    return [ALL_VALUE, seededCountry, ...optionLists.countries.slice(1)]
  }, [isDirectory, optionLists.countries, seededCountry])

  /**
   * Merge one change into the URL. Everything else is preserved, which is the
   * whole point: changing one filter must not reset the search box, the sort
   * order or the page the student is on.
   */
  function updateState(patch) {
    const next = { ...urlState, ...patch }

    // A filter change returns to the first page, because page 3 of a
    // one-record result set is an empty page. An explicit page change does
    // not, which is what makes pagination usable.
    if (!('page' in patch)) {
      next.page = 1
    }

    setSearchParams(catalogueStateToParams(next), { replace: false })
  }

  /** Remove exactly one filter, leaving the rest of the state alone. */
  function removeFilter(key) {
    updateState({ [key]: DEFAULT_CATALOGUE_STATE[key] })
  }

  /** Clear every filter and the query, in one action. */
  function resetControls() {
    // `country` is deliberately not carried over: the action is labelled "reset
    // all", and leaving a country behind would reset everything except the one
    // filter a student can see in the page heading above.
    setSearchParams(catalogueStateToParams(DEFAULT_CATALOGUE_STATE))
  }

  function clearSearch() {
    updateState({ search: '' })
    searchInputRef.current?.focus()
  }

  function retryRequest() {
    setRequestVersion((version) => version + 1)
  }

  /* `/` focuses the search field, unless the user is already typing in a
     control that uses the key. The exception is the point: swallowing `/`
     inside a text input would make it impossible to type a slash at all. */
  useEffect(() => {
    if (!isDirectory) {
      return undefined
    }

    function onKeyDown(event) {
      if (event.key !== SEARCH_SHORTCUT_KEY || event.defaultPrevented) {
        return
      }
      const target = event.target
      if (target instanceof HTMLElement && (
        target.tagName === 'INPUT'
        || target.tagName === 'TEXTAREA'
        || target.tagName === 'SELECT'
        || target.isContentEditable
      )) {
        return
      }
      // Modifier combinations belong to the browser and to the user.
      if (event.ctrlKey || event.metaKey || event.altKey) {
        return
      }

      event.preventDefault()
      searchInputRef.current?.focus()
      searchInputRef.current?.select()
    }

    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [isDirectory])

  useEffect(() => {
    if (!isDirectory) {
      return undefined
    }

    const controller = new AbortController()
    const requestId = requestIdRef.current + 1
    requestIdRef.current = requestId
    const delay = search ? SEARCH_DEBOUNCE_MS : 0

    const timer = window.setTimeout(async () => {
      setLoadState((currentState) => (currentState === 'success' || currentState === 'refreshing' ? 'refreshing' : 'loading'))
      setApiError('')

      try {
        const directory = await fetchScholarships(
          {
            search,
            country: effectiveCountry,
            level: studyLevel,
            funding,
            status,
            region,
            tuition: tuitionCoverage,
            deadline_month: deadlineMonth === ALL ? undefined : deadlineMonth,
            sort: sortBy,
            page,
            limit: PAGE_SIZE,
          },
          { signal: controller.signal },
        )

        if (controller.signal.aborted || requestId !== requestIdRef.current) {
          return
        }

        const totalPages = directory.pagination?.total_pages ?? 0
        if (totalPages > 0 && page > totalPages) {
          // A page past the end is corrected in the URL rather than in local
          // state, so the address bar stops advertising a page that has
          // nothing on it.
          setSearchParams(catalogueStateToParams({ ...urlState, page: totalPages }))
          return
        }

        setApiDirectory(directory)
        setCatalogueSource({
          source: directory.source,
          meta: directory.snapshot_meta,
        })
        setLoadState('success')
      } catch (error) {
        if (controller.signal.aborted || requestId !== requestIdRef.current) {
          return
        }

        setApiError(
          error instanceof Error
            ? error.message
            : 'The bundled scholarship snapshot could not be read.',
        )
        setLoadState('fallback')
      }
    }, delay)

    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [
    country, deadlineMonth, effectiveCountry, funding, isDirectory, page, region,
    requestVersion, search, sortBy, status, studyLevel, setSearchParams, tuitionCoverage, urlState,
  ])

  const hasActive = hasActiveFilters(urlState)
  const isInitialLoading = isDirectory && loadState === 'loading' && apiDirectory.items.length === 0
  const isRefreshing = isDirectory && loadState === 'refreshing'
  const isUsingFallback = isDirectory && loadState === 'fallback'
  const currentItems = isDirectory && !isUsingFallback ? apiDirectory.items : localResults
  const pagination = isDirectory && !isUsingFallback ? apiDirectory.pagination : null
  const totalResults = pagination?.total ?? currentItems.length
  const resultLabel = totalResults === 1 ? 'scholarship' : 'scholarships'
  const pageCount = pagination?.total_pages ?? 0
  const chips = activeFilterChips({ ...urlState, country: effectiveCountry })

  /** Page numbers for the pager, with ellipses for the gaps. */
  const pageNumbers = useMemo(() => {
    if (pageCount <= 1) {
      return []
    }
    const pages = []
    const window = 1
    for (let candidate = 1; candidate <= pageCount; candidate += 1) {
      if (
        candidate === 1
        || candidate === pageCount
        || Math.abs(candidate - page) <= window
      ) {
        pages.push(candidate)
      } else if (pages[pages.length - 1] !== 'ellipsis-start' && pages[pages.length - 1] !== 'ellipsis-end') {
        // A run of candidates outside the window collapses to one marker. The
        // guard checks both markers: two consecutive candidates past the end
        // used to push "ellipsis-end" twice, handing React duplicate keys —
        // which logs an error on every catalogue page with a wide-enough gap
        // and leaves React free to drop or duplicate the page buttons.
        pages.push(candidate > page ? 'ellipsis-end' : 'ellipsis-start')
      }
    }
    return pages
  }, [page, pageCount])

  return (
    <section className="scholarship-list" aria-label="Scholarship directory">
      {isDirectory ? (
        <CatalogueSourceNotice
          source={catalogueSource?.source}
          meta={catalogueSource?.meta}
        />
      ) : null}

      <div className="filter-section" role="search">
        <div className="filter-section__intro">
          <p>Find your fit</p>
          <span>Search names, providers, countries, study levels, funding or eligibility, then refine.</span>
        </div>

        <div className="filter-section__controls">
          <div className={`filter-search ${search ? 'has-value' : ''}`}>
            <label className="visually-hidden" htmlFor="scholarship-search">Search scholarships by name, provider, country, level or funding</label>
            <svg className="filter-search__icon" viewBox="0 0 24 24" aria-hidden="true">
              <path d="m21 21-4.35-4.35m2.35-5.65a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z" />
            </svg>
            <input
              ref={searchInputRef}
              id="scholarship-search"
              type="search"
              aria-describedby="scholarship-search-hint"
              placeholder="Search scholarships..."
              value={search}
              onChange={(event) => updateState({ search: event.target.value })}
              onKeyDown={(event) => {
                if (event.key === 'Escape' && search) {
                  // Escape clears only the search, not the filters beside it.
                  event.preventDefault()
                  clearSearch()
                }
              }}
            />
            {search && (
              <button type="button" className="filter-search__clear" onClick={clearSearch} aria-label="Clear scholarship search">
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="m6 6 12 12M18 6 6 18" />
                </svg>
              </button>
            )}
          </div>

          <div className={`filter-control ${effectiveCountry !== 'All' ? 'is-active' : ''}`}>
            <label htmlFor="scholarship-country">Country</label>
            <select
              id="scholarship-country"
              value={effectiveCountry}
              onChange={(event) => updateState({ country: event.target.value })}
            >
              {countryOptions.map((value) => (
                <option key={value} value={value}>
                  {value === ALL_VALUE ? 'All countries' : value}
                </option>
              ))}
            </select>
          </div>

          <div className={`filter-control ${studyLevel !== 'All' ? 'is-active' : ''}`}>
            <label htmlFor="scholarship-level">Study level</label>
            <select
              id="scholarship-level"
              value={studyLevel}
              onChange={(event) => updateState({ studyLevel: event.target.value })}
            >
              <option value={ALL_VALUE}>All levels</option>
              {STUDY_LEVELS.map((level) => (
                <option key={level.value} value={level.value}>{level.label}</option>
              ))}
              {/* Reachable so a student can find the records that name no
                  level, rather than having them vanish from every level view. */}
              <option value={UNSPECIFIED_LEVEL}>{studyLevelLabel(UNSPECIFIED_LEVEL)}</option>
            </select>
          </div>

          <div className={`filter-control ${region !== 'All' ? 'is-active' : ''}`}>
            <label htmlFor="scholarship-region">Region</label>
            <select
              id="scholarship-region"
              value={region}
              onChange={(event) => updateState({ region: event.target.value })}
            >
              {optionLists.regions.map((value) => (
                <option key={value} value={value}>
                  {value === ALL_VALUE ? 'All regions' : value}
                </option>
              ))}
            </select>
          </div>

          <div className={`filter-control ${funding !== 'All' ? 'is-active' : ''}`}>
            <label htmlFor="scholarship-funding">Funding type</label>
            <select
              id="scholarship-funding"
              value={funding}
              onChange={(event) => updateState({ funding: event.target.value })}
            >
              {optionLists.fundingTypes.map((value) => (
                <option key={value} value={value}>
                  {value === ALL_VALUE ? 'Any funding' : value}
                </option>
              ))}
            </select>
          </div>

          <div className={`filter-control ${tuitionCoverage !== 'All' ? 'is-active' : ''}`}>
            <label htmlFor="scholarship-tuition">Tuition</label>
            <select
              id="scholarship-tuition"
              value={tuitionCoverage}
              onChange={(event) => updateState({ tuitionCoverage: event.target.value })}
            >
              <option value={ALL_VALUE}>Any tuition coverage</option>
              {TUITION_COVERAGE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </div>

          <div className={`filter-control ${deadlineMonth !== 'All' ? 'is-active' : ''}`}>
            <label htmlFor="scholarship-deadline-month">Deadline month</label>
            <select
              id="scholarship-deadline-month"
              value={deadlineMonth}
              onChange={(event) => updateState({ deadlineMonth: event.target.value })}
            >
              {optionLists.deadlineMonths.map((value) => (
                <option key={value} value={value}>
                  {value === ALL_VALUE ? 'Any month' : MONTH_NAMES[Number(value)] || value}
                </option>
              ))}
            </select>
          </div>

          <div className={`filter-control ${status !== 'All' ? 'is-active' : ''}`}>
            <label htmlFor="scholarship-status">Status</label>
            <select
              id="scholarship-status"
              value={status}
              onChange={(event) => updateState({ status: event.target.value })}
            >
              {optionLists.statuses.map((value) => (
                <option key={value} value={value}>
                  {value === ALL_VALUE ? 'All statuses' : STATUS_LABELS[value] || value}
                </option>
              ))}
            </select>
          </div>

          <div className={`filter-control filter-sort ${sortBy !== 'recommended' ? 'is-active' : ''}`}>
            <label htmlFor="scholarship-sort">Sort by</label>
            <select
              id="scholarship-sort"
              value={sortBy}
              onChange={(event) => updateState({ sortBy: event.target.value })}
            >
              {SORT_MODES.map((mode) => (
                <option key={mode.value} value={mode.value}>{mode.label}</option>
              ))}
            </select>
          </div>

          {hasActive && (
            <button type="button" className="filter-reset" onClick={resetControls}>
              Reset all
            </button>
          )}
        </div>

        {/* Every active filter, individually removable. Removing one must not
            clear the others - the previous single "Reset all" was the only way
            to undo one filter, and it also reset the sort and the search. */}
        {chips.length > 0 && (
          <div className="filter-chips" aria-label="Active filters">
            {chips.map((chip) => (
              <button
                key={chip.key}
                type="button"
                className="filter-chip"
                onClick={() => removeFilter(chip.key)}
              >
                {chip.label}
                <span className="filter-chip__remove" aria-hidden="true">&times;</span>
                <span className="visually-hidden">Remove this filter</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {isUsingFallback && (
        <div className="scholarship-list__source-notice" role="status">
          <div>
            <strong>Catalogue snapshot unavailable.</strong>
            <span>Showing the bundled sample listings instead.</span>
          </div>
          <button type="button" onClick={retryRequest}>Retry</button>
        </div>
      )}

      <div className="scholarship-list__summary" aria-live="polite">
        <p><strong>{totalResults}</strong> {resultLabel} found</p>
        <span>
          {isRefreshing
            ? 'Updating results…'
            : isUsingFallback
              ? 'Local fallback does not use server pagination.'
              : hasActive
                ? 'Matching your current search and filters.'
                : 'Compare funding, location and key dates.'}
        </span>
      </div>

      {isInitialLoading ? (
        <LoadingCards />
      ) : currentItems.length === 0 ? (
        <div className="empty-state">
          <span className="empty-state__icon" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <path d="m21 21-4.35-4.35m2.35-5.65a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z" />
            </svg>
          </span>
          <span>No matching scholarships</span>
          {/* What the search actually did, so an empty result is diagnosable
              rather than a dead end: a student can see whether the query was
              read as three terms or as one. */}
          <p>
            {search.trim() !== ''
              ? `Nothing in the catalogue matches every word in “${search.trim()}”.`
              : 'Nothing in the catalogue matches these filters.'}
            {' '}
            Try a broader search, remove a filter, or reset to explore every available opportunity.
          </p>
          <div className="empty-state__actions">
            {chips.length > 0 && (
              <button
                type="button"
                className="empty-state__reset"
                onClick={() => removeFilter(chips[chips.length - 1].key)}
              >
                Remove “{chips[chips.length - 1].label}”
              </button>
            )}
            <button type="button" className="empty-state__reset" onClick={resetControls}>
              Reset search and filters
            </button>
          </div>
          <Link className="empty-state__link" to="/match">
            Find My Matches instead
          </Link>
        </div>
      ) : (
        <div className="scholarship-grid" aria-busy={isRefreshing} ref={resultsRef}>
          {currentItems.map((scholarship) => (
            <ScholarshipCard key={scholarship.id} scholarship={scholarship} />
          ))}
        </div>
      )}

      {pagination && pageCount > 1 && (
        <nav className="scholarship-pagination" aria-label="Scholarship pages">
          <button
            type="button"
            onClick={() => updateState({ page: Math.max(1, page - 1) })}
            disabled={page === 1 || isRefreshing}
          >
            Previous
          </button>

          {/* Numbered pages, so page 4 of 22 is reachable in one action rather
              than three. The current page is marked for assistive technology
              rather than only being bold. */}
          <ol className="scholarship-pagination__pages">
            {pageNumbers.map((entry) => (
              entry === 'ellipsis-start' || entry === 'ellipsis-end' ? (
                <li key={entry} aria-hidden="true">…</li>
              ) : (
                <li key={entry}>
                  <button
                    type="button"
                    onClick={() => updateState({ page: entry })}
                    disabled={isRefreshing}
                    aria-current={entry === page ? 'page' : undefined}
                    className={entry === page ? 'is-current' : undefined}
                  >
                    {entry}
                  </button>
                </li>
              )
            ))}
          </ol>

          <button
            type="button"
            onClick={() => updateState({ page: Math.min(pageCount, page + 1) })}
            disabled={page === pageCount || isRefreshing}
          >
            Next
          </button>
        </nav>
      )}

      <span id="scholarship-search-hint" className="visually-hidden">
        Search scholarship names, providers, countries, study levels and funding. Press Escape to clear
        your search. Press slash to jump back to this field.
      </span>
      {isUsingFallback && apiError && <span className="visually-hidden">{apiError}</span>}
    </section>
  )
}
