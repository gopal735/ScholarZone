import { useEffect, useMemo, useRef, useState } from 'react'
import ScholarshipCard from './ScholarshipCard'
import { scholarships } from '../data/scholarships'
import { fetchScholarships } from '../services/scholarshipService'
import { getScholarshipStatus, matchesDegreeFilter, matchesFundingFilter } from '../utils/scholarshipPresentation'
import './ScholarshipList.css'

const PAGE_SIZE = 12
const SEARCH_DEBOUNCE_MS = 250
const STATUS_ORDER = { open: 0, 'closing-soon': 1, closed: 2 }

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
          return Number(matchesFundingFilter(second.scholarship.funding, 'Fully Funded')) - Number(matchesFundingFilter(first.scholarship.funding, 'Fully Funded'))
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
    // The same aspect matching the API applies, so the fallback and the
    // live directory never disagree about which rows a filter selects.
    const matchDegree = matchesDegreeFilter(scholarship.degree, degree)
    const matchFunding = matchesFundingFilter(scholarship.funding, funding)
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
  const [loadState, setLoadState] = useState(isDirectory ? 'loading' : 'local')
  const [apiError, setApiError] = useState('')
  const searchInputRef = useRef(null)
  const requestIdRef = useRef(0)

  const localResults = useMemo(
    () => filterLocalScholarships(localItems, { search, country, degree, funding, deadlineMonth, status, sortBy }),
    [localItems, search, country, degree, funding, deadlineMonth, status, sortBy],
  )

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
        // A snapshot answer is still a fallback, not a live directory. The
        // service tags it so the visitor is told which of the two they are
        // looking at: a catalogue that silently changes its provenance is
        // worse than one that announces it, and the honest label is what
        // makes the rest of the page (pagination, "verified" counts) make
        // sense while the API is down.
        setLoadState(directory.fromSnapshot ? 'fallback' : 'success')
      } catch (error) {
        if (controller.signal.aborted || requestId !== requestIdRef.current) {
          return
        }

        setApiError(error instanceof Error ? error.message : 'The live scholarship directory is unavailable.')
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
  /* The snapshot already answered the query — filter, sort and pagination
     are applied inside the static service, against the same semantics the
     API uses. Running the local pipeline over it as well would filter the
     page the snapshot returned rather than the whole catalogue, and would
     silently disagree with the snapshot's own reported total.

     ``localResults`` stays for the caller-supplied list and for a total
     API failure: those are the cases where there is no server to have
     applied the query for us. */
  const isSnapshot = Boolean(apiDirectory?.fromSnapshot)
  const currentItems = isDirectory && !isUsingFallback
    ? apiDirectory.items
    : isSnapshot
      ? apiDirectory.items
      : localResults
  const pagination = isDirectory && !isUsingFallback
    ? apiDirectory.pagination
    : isSnapshot
      ? apiDirectory.pagination
      : null
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
      <div className="filter-section" role="search">
        <div className="filter-section__intro">
          <p>Find your fit</p>
          <span>Search names, countries, degrees or funding, then refine by deadline and listing status.</span>
        </div>

        <div className="filter-section__controls">
          {/* The reference's sunken well: a search field is a hole in the
              surface you reach into, so it takes the well treatment rather
              than a raised panel. The ruling lines the reference paints
              inside its textarea are what make it read as a place to write,
              not as a readout. */}
          <div className={`filter-search p-well ${search ? 'has-value' : ''}`}>
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
            <select className="p-sel"
              id="scholarship-country"
              value={country}
              onChange={(event) => {
                setCountry(event.target.value)
                setPage(1)
              }}
            >
              <option value="All">All countries</option>
              <option value="India">India</option>
              <option value="Germany">Germany</option>
              <option value="Europe">Europe</option>
              <option value="South Korea">South Korea</option>
            </select>
          </div>

          <div className={`filter-control ${degree !== 'All' ? 'is-active' : ''}`}>
            <label htmlFor="scholarship-degree">Degree</label>
            <select className="p-sel"
              id="scholarship-degree"
              value={degree}
              onChange={(event) => {
                setDegree(event.target.value)
                setPage(1)
              }}
            >
              <option value="All">All degrees</option>
              {/* Values are the level words the API's filter buckets match on.
                  The catalogue stores "Master's, PhD" style labels, so a
                  verbatim label matched nothing: "UG (Bachelor's/Associate)"
                  used to be sent as-is and returned zero rows. */}
              <option value="Bachelor">Bachelor / Undergraduate</option>
              <option value="Master">Master</option>
              <option value="PhD">PhD / Doctoral</option>
              <option value="Postgraduate">Postgraduate</option>
            </select>
          </div>

          <div className={`filter-control ${funding !== 'All' ? 'is-active' : ''}`}>
            <label htmlFor="scholarship-funding">Funding</label>
            <select className="p-sel"
              id="scholarship-funding"
              value={funding}
              onChange={(event) => {
                setFunding(event.target.value)
                setPage(1)
              }}
            >
              <option value="All">All funding</option>
              {/* Same contract as the degree select: the API matches the
                  aspect, not the verbatim label, so these values are the
                  dominant catalogue terms. */}
              <option value="Fully Funded">Fully funded</option>
              <option value="Tuition Fee Waiver">Tuition waiver</option>
              <option value="Stipend">Stipend</option>
              <option value="Partially Funded">Partial funding</option>
            </select>
          </div>

          <div className={`filter-control ${deadlineMonth !== 'All' ? 'is-active' : ''}`}>
            <label htmlFor="scholarship-deadline-month">Deadline month</label>
            <select
              className="p-sel"
              id="scholarship-deadline-month"
              value={deadlineMonth}
              onChange={(event) => {
                setDeadlineMonth(event.target.value)
                setPage(1)
              }}
            >
              <option value="All">Any month</option>
              <option value="1">January</option>
              <option value="4">April</option>
              <option value="10">October</option>
            </select>
          </div>

          <div className={`filter-control ${status !== 'All' ? 'is-active' : ''}`}>
            <label htmlFor="scholarship-status">Status</label>
            <select className="p-sel"
              id="scholarship-status"
              value={status}
              onChange={(event) => {
                setStatus(event.target.value)
                setPage(1)
              }}
            >
              <option value="All">All statuses</option>
              <option value="open">Open</option>
              <option value="closing-soon">Closing soon</option>
              <option value="closed">Closed</option>
            </select>
          </div>

          <div className={`filter-control filter-sort ${sortBy !== 'default' ? 'is-active' : ''}`}>
            <label htmlFor="scholarship-sort">Sort by</label>
            <select
              className="p-sel"
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
            <strong>Showing the snapshot catalogue.</strong>
            <span>
              {apiDirectory?.fromSnapshot
                ? 'The live directory is unavailable right now, so these results come from the version-controlled public snapshot. Browsing works; saving, applying and supervisor contact stay unavailable until the database is back.'
                : 'Showing local scholarship data instead.'}
            </span>
          </div>
          <button type="button" onClick={retryRequest}>Retry</button>
        </div>
      )}

      <div className="scholarship-list__summary" aria-live="polite">
        <p><strong>{totalResults}</strong> {resultLabel} found</p>
        <span>{isRefreshing ? 'Updating results...' : isUsingFallback ? (apiDirectory?.fromSnapshot ? 'Pagination is applied inside the snapshot, so it stays consistent. Supervisor features need the database.' : 'Local fallback does not use server pagination.') : hasActiveControls ? 'Matching your current search and filters.' : 'Compare funding, location and key dates.'}</span>
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
          {currentItems.map((scholarship, index) => (
            <ScholarshipCard key={scholarship.id} scholarship={scholarship} index={index} />
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
