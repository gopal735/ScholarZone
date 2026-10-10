import { useEffect, useMemo, useRef, useState } from 'react'
import ScholarshipCard from './ScholarshipCard'
import CatalogueSourceNotice from './CatalogueSourceNotice'
import { scholarships } from '../data/scholarships'
import { fetchScholarships } from '../services/scholarshipService'
import { getScholarshipStatus } from '../utils/scholarshipPresentation'
import './ScholarshipList.css'

const PAGE_SIZE = 12
const SEARCH_DEBOUNCE_MS = 250
const STATUS_ORDER = { open: 0, 'closing-soon': 1, closed: 2 }

/** Prepends the "no filter" entry to a list of selectable values. */
function All_PLUS(values) {
  return ['All', ...values]
}

/* The previous hardcoded option lists, kept only as a fallback for a response
   that carries no filter options. The snapshot does; an opted-in live API
   response does not. These names are not derived from the catalogue, so some of
   them may match nothing - which is exactly why the default path no longer uses
   them. */
const FALLBACK_COUNTRIES = ['India', 'Germany', 'Europe', 'South Korea']
const FALLBACK_DEGREES = ['Bachelor', 'Master', "UG (Bachelor's/Associate)"]
const FALLBACK_FUNDING = ['Fully Funded']
const FALLBACK_STATUSES = ['open', 'closing-soon', 'closed']
const FALLBACK_MONTHS = ['1', '4', '10']

/* Human labels for the values that are stored as codes. Months are the stored
   calendar month, not a name, so they need a lookup; statuses have the same
   problem. Everything else is shown as it is stored, because the stored value
   is what the filter matches on and renaming it would make the control lie. */
const MONTH_NAMES = [
  '', 'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

const STATUS_LABELS = {
  open: 'Open',
  'closing-soon': 'Closing soon',
  upcoming: 'Upcoming',
}

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
    return -1  }

  return direction === 'asc' ? firstValue - secondValue : secondValue - firstValue
}

function sortLocalScholarships(items, sortBy) {
  const indexedItems = items.map((scholarship, index) => ({ scholarship, index }))

  indexedItems.sort((first, second) => {
    const firstTitle = typeof first.scholarship.title === 'string' ? first.scholarship.title : ''
    const secondTitle = typeof second.scholarship.title === 'string' ? second.scholarship.title : ''
    const comparison = (() => {
      switch (sortBy) {
        case 'recommended':
          // Rank by the authoritative verification state. The legacy `verified`
          // boolean was used here and is true on every public record, so this
          // comparison was always zero and "recommended" silently meant
          // "any order at all".
          return Number(second.scholarship.verification_status === 'active') - Number(first.scholarship.verification_status === 'active')
            || STATUS_ORDER[getScholarshipStatus(first.scholarship).className] - STATUS_ORDER[getScholarshipStatus(second.scholarship).className]
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
          return Number(second.scholarship.funding === 'Fully Funded') - Number(first.scholarship.funding === 'Fully Funded')
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

function filterLocalScholarships(items, { search, country, degree, funding, deadlineMonth, status, sortBy }) {
  const normalizedSearch = search.trim().toLowerCase()
  const filteredItems = items.filter((scholarship) => {
    const title = typeof scholarship.title === 'string' ? scholarship.title : ''
    const searchableText = [title, scholarship.country, scholarship.degree, scholarship.funding, scholarship.description]
      .filter((value) => typeof value === 'string')
      .join(' ')
      .toLowerCase()
    const matchSearch = searchableText.includes(normalizedSearch)
    const matchCountry = country === 'All' || scholarship.country === country
    const matchDegree = degree === 'All' || scholarship.degree === degree
    const matchFunding = funding === 'All' || scholarship.funding === funding
    const matchDeadlineMonth = deadlineMonth === 'All' || getLocalDeadlineMonth(scholarship) === Number(deadlineMonth)
    const matchStatus = status === 'All' || getScholarshipStatus(scholarship).className === status

    return matchSearch && matchCountry && matchDegree && matchFunding && matchDeadlineMonth && matchStatus
  })

  return sortLocalScholarships(filteredItems, sortBy)
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

export default function ScholarshipList({ items, initialCountry }) {
  const isDirectory = !Array.isArray(items)
  const localItems = Array.isArray(items) ? items : scholarships
  const [search, setSearch] = useState('')
  const [country, setCountry] = useState(initialCountry ?? 'All')
  const [degree, setDegree] = useState('All')
  const [funding, setFunding] = useState('All')
  const [deadlineMonth, setDeadlineMonth] = useState('All')
  const [status, setStatus] = useState('All')
  const [sortBy, setSortBy] = useState('recommended')
  const [page, setPage] = useState(1)
  const [requestVersion, setRequestVersion] = useState(0)
  const [apiDirectory, setApiDirectory] = useState({ items: [], pagination: null })
  const [catalogueSource, setCatalogueSource] = useState(null)
  const [loadState, setLoadState] = useState(isDirectory ? 'loading' : 'local')
  const [apiError, setApiError] = useState('')
  const searchInputRef = useRef(null)
  const requestIdRef = useRef(0)

  const localResults = useMemo(
    () => filterLocalScholarships(localItems, { search, country, degree, funding, deadlineMonth, status, sortBy }),
    [localItems, search, country, degree, funding, deadlineMonth, status, sortBy],
  )

  /* The selectable values, from the catalogue that was actually loaded.

     These were hardcoded lists, and against this catalogue they were wrong in
     both directions: they offered values no record holds - `Europe` as a
     country, `closed` as a status, which the visibility predicate excludes by
     construction - while omitting nearly everything the catalogue does hold, so
     the Country menu named four of 74 countries and the Degree menu matched 1,
     3 and 1 records.

     The snapshot carries the distinct values it exports, so the menus are built
     from those. The consequence that made this worth fixing is that a value
     arriving in the URL is now representable: with a hardcoded list, a select
     pointing at `Japan` had no matching option and the browser silently showed
     the first one, so the menu read "All countries" while the results were all
     Japan - a control that contradicted the page it was on.

     When the response carries no filter options - an opted-in live API response
     does not - the previous lists are kept rather than the menus being emptied,
     so opting in does not remove the controls. */
  const filterOptions = catalogueSource?.meta?.filter_options || null

  const optionLists = useMemo(() => {
    if (filterOptions) {
      return {
        countries: All_PLUS(filterOptions.countries),
        degrees: All_PLUS(filterOptions.degrees),
        fundingTypes: All_PLUS(filterOptions.funding_types),
        statuses: All_PLUS(filterOptions.statuses),
        deadlineMonths: All_PLUS((filterOptions.deadline_months || []).map(String)),
      }
    }
    return {
      countries: All_PLUS(FALLBACK_COUNTRIES),
      degrees: All_PLUS(FALLBACK_DEGREES),
      fundingTypes: All_PLUS(FALLBACK_FUNDING),
      statuses: All_PLUS(FALLBACK_STATUSES),
      deadlineMonths: All_PLUS(FALLBACK_MONTHS),
    }
  }, [filterOptions])

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
            country,
            degree,
            funding,
            deadline_month: deadlineMonth === 'All' ? undefined : deadlineMonth,
            status,
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
          setPage(totalPages)
          return
        }

        setApiDirectory(directory)
        // Keep where the data came from so the provenance notice can say so,
        // and so a live refresh is visibly different from the static snapshot.
        setCatalogueSource({
          source: directory.source,
          meta: directory.snapshot_meta,
        })
        setLoadState('success')
      } catch (error) {
        if (controller.signal.aborted || requestId !== requestIdRef.current) {
          return
        }

        // The catalogue is served from a bundled snapshot, so a failure here
        // means the snapshot could not be read - not that the database is down,
        // which is no longer what ordinary browsing depends on.
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
  }, [country, deadlineMonth, degree, funding, isDirectory, page, requestVersion, search, sortBy, status])

  const hasActiveControls = Boolean(search) || country !== 'All' || degree !== 'All' || funding !== 'All' || deadlineMonth !== 'All' || status !== 'All' || sortBy !== 'recommended'
  const isInitialLoading = isDirectory && loadState === 'loading' && apiDirectory.items.length === 0
  const isRefreshing = isDirectory && loadState === 'refreshing'
  const isUsingFallback = isDirectory && loadState === 'fallback'
  const currentItems = isDirectory && !isUsingFallback ? apiDirectory.items : localResults
  const pagination = isDirectory && !isUsingFallback ? apiDirectory.pagination : null
  const totalResults = pagination?.total ?? currentItems.length
  const resultLabel = totalResults === 1 ? 'scholarship' : 'scholarships'
  const pageCount = pagination?.total_pages ?? 0

  function resetControls() {
    setSearch('')
    setCountry('All')
    setDegree('All')
    setFunding('All')
    setDeadlineMonth('All')
    setStatus('All')
    setSortBy('recommended')
    setPage(1)
  }

  function clearSearch() {
    setSearch('')
    setPage(1)
    searchInputRef.current?.focus()
  }

  function retryRequest() {
    setRequestVersion((version) => version + 1)
  }

  return (
    <section className="scholarship-list" aria-label="Scholarship directory">
      {/* Provenance. The catalogue is served from the bundled snapshot, which is
          what keeps it working while the database has no quota - but it also
          means a student should know the data is not live before relying on a
          deadline. Shows only when the response came from the snapshot. */}
      {isDirectory ? (
        <CatalogueSourceNotice
          source={catalogueSource?.source}
          meta={catalogueSource?.meta}
        />
      ) : null}

      <div className="filter-section" role="search">
        <div className="filter-section__intro">
          <p>Find your fit</p>
          <span>Search names, countries, degrees or funding, then refine by deadline and listing status.</span>
        </div>

        <div className="filter-section__controls">
          <div className={`filter-search ${search ? 'has-value' : ''}`}>
            <label className="visually-hidden" htmlFor="scholarship-search">Search scholarships by name</label>
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
              onChange={(event) => {
                setSearch(event.target.value)
                setPage(1)
              }}
              onKeyDown={(event) => {
                if (event.key === 'Escape' && search) {
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

          <div className={`filter-control ${country !== 'All' ? 'is-active' : ''}`}>
            <label htmlFor="scholarship-country">Country</label>
            <select
              id="scholarship-country"
              value={country}
              onChange={(event) => {
                setCountry(event.target.value)
                setPage(1)
              }}
            >
              {optionLists.countries.map((value) => (
                <option key={value} value={value}>
                  {value === 'All' ? 'All countries' : value}
                </option>
              ))}
            </select>
          </div>

          <div className={`filter-control ${degree !== 'All' ? 'is-active' : ''}`}>
            <label htmlFor="scholarship-degree">Degree</label>
            <select
              id="scholarship-degree"
              value={degree}
              onChange={(event) => {
                setDegree(event.target.value)
                setPage(1)
              }}
            >
              {optionLists.degrees.map((value) => (
                <option key={value} value={value}>
                  {value === 'All' ? 'All degrees' : value}
                </option>
              ))}
            </select>
          </div>

          <div className={`filter-control ${funding !== 'All' ? 'is-active' : ''}`}>
            <label htmlFor="scholarship-funding">Funding</label>
            <select
              id="scholarship-funding"
              value={funding}
              onChange={(event) => {
                setFunding(event.target.value)
                setPage(1)
              }}
            >
              {optionLists.fundingTypes.map((value) => (
                <option key={value} value={value}>
                  {value === 'All' ? 'All funding' : value}
                </option>
              ))}
            </select>
          </div>

          <div className={`filter-control ${deadlineMonth !== 'All' ? 'is-active' : ''}`}>
            <label htmlFor="scholarship-deadline-month">Deadline month</label>
            <select
              id="scholarship-deadline-month"
              value={deadlineMonth}
              onChange={(event) => {
                setDeadlineMonth(event.target.value)
                setPage(1)
              }}
            >
              {optionLists.deadlineMonths.map((value) => (
                <option key={value} value={value}>
                  {value === 'All' ? 'Any month' : MONTH_NAMES[Number(value)] || value}
                </option>
              ))}
            </select>
          </div>

          <div className={`filter-control ${status !== 'All' ? 'is-active' : ''}`}>
            <label htmlFor="scholarship-status">Status</label>
            <select
              id="scholarship-status"
              value={status}
              onChange={(event) => {
                setStatus(event.target.value)
                setPage(1)
              }}
            >
              {optionLists.statuses.map((value) => (
                <option key={value} value={value}>
                  {value === 'All' ? 'All statuses' : STATUS_LABELS[value] || value}
                </option>
              ))}
            </select>
          </div>

          <div className={`filter-control filter-sort ${sortBy !== 'default' ? 'is-active' : ''}`}>
            <label htmlFor="scholarship-sort">Sort by</label>
            <select
              id="scholarship-sort"
              value={sortBy}
              onChange={(event) => {
                setSortBy(event.target.value)
                setPage(1)
              }}
            >
              <option value="recommended">Recommended</option>
              <option value="recently-added">Recently added</option>
              <option value="recently-updated">Recently updated</option>
              <option value="deadline-soon">Deadline soon</option>
              <option value="fully-funded">Fully funded</option>
              <option value="deadline-earliest">Deadline: Earliest first</option>
              <option value="deadline-latest">Deadline: Latest first</option>
              <option value="name-asc">Name: A &rarr; Z</option>
              <option value="name-desc">Name: Z &rarr; A</option>
            </select>
          </div>

          {hasActiveControls && (
            <button type="button" className="filter-reset" onClick={resetControls}>
              Reset all
            </button>
          )}
        </div>
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
        <span>{isRefreshing ? 'Updating results...' : isUsingFallback ? 'Local fallback does not use server pagination.' : hasActiveControls ? 'Matching your current search and filters.' : 'Compare funding, location and key dates.'}</span>
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
          <p>Try broadening your search or reset the filters to explore every available opportunity.</p>
          <button type="button" className="empty-state__reset" onClick={resetControls}>Reset search and filters</button>
        </div>
      ) : (
        <div className="scholarship-grid" aria-busy={isRefreshing}>
          {currentItems.map((scholarship) => (
            <ScholarshipCard key={scholarship.id} scholarship={scholarship} />
          ))}
        </div>
      )}

      {pagination && pageCount > 1 && (
        <nav className="scholarship-pagination" aria-label="Scholarship pages">
          <button type="button" onClick={() => setPage((currentPage) => currentPage - 1)} disabled={page === 1 || isRefreshing}>
            Previous
          </button>
          <span>Page <strong>{page}</strong> of {pageCount}</span>
          <button type="button" onClick={() => setPage((currentPage) => currentPage + 1)} disabled={page === pageCount || isRefreshing}>
            Next
          </button>
        </nav>
      )}

      <span id="scholarship-search-hint" className="visually-hidden">Search scholarship names. Press Escape to clear your search.</span>
      {isUsingFallback && apiError && <span className="visually-hidden">{apiError}</span>}
    </section>
  )
}
