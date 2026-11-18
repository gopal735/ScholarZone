import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchSupervisors, fetchGlobalSupervisors } from '../services/supervisorService'
import './SupervisorsPage.css'

/* Research interests are typed by the student and kept in this browser only.
   They are sent with the request and never stored server-side, because an
   interest ScholarZone inferred from anything other than an explicit sentence
   would be an invented fact about a person. */
const INTEREST_STORAGE_KEY = 'sz.researchInterests'

function readInterests() {
  try {
    const raw = window.localStorage.getItem(INTEREST_STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed.filter((item) => typeof item === 'string') : []
  } catch {
    // A blocked or corrupt storage must not break the page.
    return []
  }
}

function saveInterests(interests) {
  try {
    window.localStorage.setItem(INTEREST_STORAGE_KEY, JSON.stringify(interests))
  } catch {
    // Storage may be unavailable.
  }
}

const DEGREE_OPTIONS = [
  { value: 'BACHELOR', label: "Bachelor's" },
  { value: 'MASTER', label: "Master's" },
  { value: 'PHD', label: 'PhD' },
]

const LIFECYCLE_OPTIONS = [
  { value: 'OPEN', label: 'Open' },
  { value: 'UPCOMING', label: 'Upcoming' },
]

const CONTACT_TYPE_OPTIONS = [
  { value: 'RESEARCH_SUPERVISOR', label: 'Research Supervisor' },
  { value: 'PROGRAMME_FACULTY', label: 'Programme Faculty' },
  { value: 'COURSE_INSTRUCTOR', label: 'Course Instructor' },
  { value: 'DEPARTMENT_CONTACT', label: 'Department Contact' },
  { value: 'UNIVERSITY_LEADERSHIP', label: 'University Leadership' },
  { value: 'PROGRAMME_OFFICE', label: 'Programme Office' },
  { value: 'POTENTIAL_SUPERVISOR', label: 'Potential Supervisor (legacy)' },
  { value: 'PROGRAM_FACULTY', label: 'Program Faculty (legacy)' },
  { value: 'RESEARCH_GROUP', label: 'Research Group (legacy)' },
  { value: 'PROGRAM_RELEVANT_FACULTY', label: 'Program Relevant Faculty (legacy)' },
]

function getRelationshipLabel(type) {
  const labels = {
    'RESEARCH_SUPERVISOR': 'Research Supervisor',
    'PROGRAMME_FACULTY': 'Programme Faculty',
    'COURSE_INSTRUCTOR': 'Course Instructor',
    'DEPARTMENT_CONTACT': 'Department Contact',
    'UNIVERSITY_LEADERSHIP': 'University Leadership',
    'PROGRAMME_OFFICE': 'Programme Office',
    'POTENTIAL_SUPERVISOR': 'Potential Supervisor',
    'PROGRAM_FACULTY': 'Program Faculty',
    'RESEARCH_GROUP': 'Research Group',
    'PROGRAM_RELEVANT_FACULTY': 'Program Relevant Faculty',
  }
  return labels[type] || type
}

function getRelationshipColor(type) {
  const colors = {
    'RESEARCH_SUPERVISOR': 'success',
    'PROGRAMME_FACULTY': 'primary',
    'COURSE_INSTRUCTOR': 'warning',
    'DEPARTMENT_CONTACT': 'info',
    'UNIVERSITY_LEADERSHIP': 'secondary',
    'PROGRAMME_OFFICE': 'muted',
    'POTENTIAL_SUPERVISOR': 'success',
    'PROGRAM_FACULTY': 'primary',
    'RESEARCH_GROUP': 'info',
    'PROGRAM_RELEVANT_FACULTY': 'warning',
  }
  return colors[type] || 'muted'
}

function SupervisorCard({ result }) {
  const {
    scholarship_title,
    scholarship_id,
    country,
    degree_level,
    effective_lifecycle,
    deadline,
    host_institution,
    official_name,
    academic_title,
    institution,
    department,
    research_areas,
    relationship_type,
    official_email,
    official_email_verified,
    official_profile_url,
    research_group_url,
    research_alignment,
    source_url,
    last_verified_at,
  } = result

  const relationshipLabel = getRelationshipLabel(relationship_type)
  const relationshipColor = getRelationshipColor(relationship_type)

  return (
    <article className="sz-supervisor-card">
      <header className="sz-supervisor-card__header">
        <div className="sz-supervisor-card__scholarship">
          <Link to={`/scholarships/${scholarship_id}`} className="sz-supervisor-card__scholarship-link">
            <h4 className="sz-supervisor-card__scholarship-title">{scholarship_title}</h4>
          </Link>
          <div className="sz-supervisor-card__scholarship-meta">
            <span className="sz-supervisor-card__country">{country}</span>
            <span className={`sz-supervisor-card__lifecycle sz-supervisor-card__lifecycle--${effective_lifecycle.toLowerCase()}`}>
              {effective_lifecycle}
            </span>
            {deadline && <time className="sz-supervisor-card__deadline" dateTime={deadline}>Deadline: {deadline.slice(0, 10)}</time>}
          </div>
        </div>
      </header>

      <div className="sz-supervisor-card__professor">
        <div className="sz-supervisor-card__professor-header">
          <div>
            <h5 className="sz-supervisor-card__professor-name">{official_name}</h5>
            <p className="sz-supervisor-card__professor-affiliation">
              {[academic_title, department, institution].filter(Boolean).join(' \u00b7 ')}
            </p>
          </div>
          <span className={`sz-supervisor-card__relationship sz-supervisor-card__relationship--${relationshipColor}`}>
            {relationshipLabel}
          </span>
        </div>

        {research_areas?.length ? (
          <ul className="sz-supervisor-card__research-areas">
            {research_areas.slice(0, 4).map((area) => (
              <li key={area}>{area}</li>
            ))}
            {research_areas.length > 4 && (
              <li className="sz-supervisor-card__more-areas">+{research_areas.length - 4} more</li>
            )}
          </ul>
        ) : (
          <p className="sz-supervisor-card__no-areas">No research areas published on the official profile.</p>
        )}

        <div className="sz-supervisor-card__alignment">
          <span className={`sz-supervisor-card__alignment-band sz-supervisor-card__alignment-band--${research_alignment?.band || 'insufficient_evidence'}`}>
            {research_alignment?.explanation || 'No research interests provided for comparison.'}
          </span>
        </div>

        <dl className="sz-supervisor-card__contact">
          <div>
            <dt>Official profile</dt>
            <dd>
              <a href={official_profile_url} target="_blank" rel="noreferrer noopener">
                View official profile
              </a>
            </dd>
          </div>
          <div>
            <dt>Email</dt>
            <dd>
              {official_email_verified && official_email ? (
                <>
                  <a href={`mailto:${official_email}`}>{official_email}</a>
                  <span className="sz-supervisor-card__verified-note">Published on the official page</span>
                </>
              ) : (
                <span className="sz-supervisor-card__unverified-note">
                  No verified email. Use the university profile or contact page.
                </span>
              )}
            </dd>
          </div>
          {research_group_url ? (
            <div>
              <dt>Research group</dt>
              <dd>
                <a href={research_group_url} target="_blank" rel="noreferrer noopener">
                  Lab or group page
                </a>
              </dd>
            </div>
          ) : null}
        </dl>

        <details className="sz-supervisor-card__sources">
          <summary>Where this came from</summary>
          <p>
            Read from{' '}
            <a href={source_url} target="_blank" rel="noreferrer noopener">
              the official faculty page
            </a>
            {last_verified_at ? ` \u00b7 last checked ${last_verified_at.slice(0, 10)}` : ''}
          </p>
        </details>
      </div>
    </article>
  )
}

function Filters({ 
  degreeLevels, setDegreeLevels, 
  lifecycle, setLifecycle, 
  country, setCountry,
  institution, setInstitution,
  contactTypes, setContactTypes,
  verifiedEmailOnly, setVerifiedEmailOnly,
  onReset 
}) {
  return (
    <div className="sz-supervisors-page__filters">
      <div className="sz-supervisors-page__filter-group">
        <label htmlFor="degree-filter">Degree level</label>
        <select
          id="degree-filter"
          multiple
          value={degreeLevels}
          onChange={(e) => {
            const selected = Array.from(e.target.selectedOptions).map(o => o.value)
            setDegreeLevels(selected)
          }}
        >
          {DEGREE_OPTIONS.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      <div className="sz-supervisors-page__filter-group">
        <label htmlFor="lifecycle-filter">Lifecycle</label>
        <select
          id="lifecycle-filter"
          multiple
          value={lifecycle}
          onChange={(e) => {
            const selected = Array.from(e.target.selectedOptions).map(o => o.value)
            setLifecycle(selected)
          }}
        >
          {LIFECYCLE_OPTIONS.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      <div className="sz-supervisors-page__filter-group">
        <label htmlFor="contact-type-filter">Contact type</label>
        <select
          id="contact-type-filter"
          multiple
          value={contactTypes}
          onChange={(e) => {
            const selected = Array.from(e.target.selectedOptions).map(o => o.value)
            setContactTypes(selected)
          }}
        >
          {CONTACT_TYPE_OPTIONS.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      <div className="sz-supervisors-page__filter-group">
        <label htmlFor="country-filter">Country</label>
        <input
          id="country-filter"
          type="text"
          value={country}
          placeholder="e.g. Germany, Finland"
          onChange={(e) => setCountry(e.target.value)}
        />
      </div>

      <div className="sz-supervisors-page__filter-group">
        <label htmlFor="institution-filter">Institution</label>
        <input
          id="institution-filter"
          type="text"
          value={institution}
          placeholder="e.g. Technical University of Munich"
          onChange={(e) => setInstitution(e.target.value)}
        />
      </div>

      <div className="sz-supervisors-page__filter-group">
        <label>
          <input
            type="checkbox"
            checked={verifiedEmailOnly}
            onChange={(e) => setVerifiedEmailOnly(e.target.checked)}
          />
          Verified email only
        </label>
      </div>

      <button type="button" className="sz-supervisors-page__reset-btn" onClick={onReset}>
        Reset filters
      </button>
    </div>
  )
}

export default function SupervisorsPage() {
  const [interestsInput, setInterestsInput] = useState(() => readInterests().join(', '))
  const [degreeLevels, setDegreeLevels] = useState([])
  const [lifecycle, setLifecycle] = useState([])
  const [country, setCountry] = useState('')
  const [institution, setInstitution] = useState('')
  const [contactTypes, setContactTypes] = useState([])
  const [verifiedEmailOnly, setVerifiedEmailOnly] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [state, setState] = useState('idle') // idle, loading, ready, error
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)

  const runSearch = useCallback(async (signal, interests) => {
    setState('loading')
    setError(null)
    try {
      const response = await fetch('/api/supervisors/search', {
        method: 'POST',
        signal,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          research_interests: interests,
          degree_levels: degreeLevels,
          lifecycle,
          country: country || undefined,
          institution: institution || undefined,
          contact_types: contactTypes,
          verified_email_only: verifiedEmailOnly,
          page,
          page_size: pageSize,
        }),
        credentials: 'include',
      })

      if (response.status === 401) {
        // Not an error for public endpoint, but handle anyway
      }
      if (!response.ok) {
        let message = 'Something went wrong. Please try again.'
        try {
          const payload = await response.json()
          if (typeof payload.detail === 'string') {
            message = payload.detail
          } else if (payload.error_code === 'schema_not_ready') {
            message = 'Supervisor discovery schema is not ready. Please try again later.'
          }
        } catch {
          // Non-JSON failure
        }
        throw new Error(message)
      }

      const data = await response.json()
      setResults(data)
      setState('ready')
    } catch (caught) {
      if (caught.name === 'AbortError') return
      setError(caught.message || 'Could not load supervisor information.')
      setState('error')
    }
  }, [degreeLevels, lifecycle, country, institution, contactTypes, verifiedEmailOnly, page, pageSize])

  const saveInterestsAndSearch = useCallback(() => {
    const next = interestsInput
      .split(',')
      .map((value) => value.trim())
      .filter(Boolean)
      .slice(0, 20)
    saveInterests(next)
    setPage(1)
    runSearch(undefined, next)
  }, [interestsInput, runSearch])

  const handleFilterChange = useCallback(() => {
    setPage(1)
    runSearch(undefined, readInterests())
  }, [runSearch])

  const handleReset = useCallback(() => {
    setDegreeLevels([])
    setLifecycle([])
    setCountry('')
    setInstitution('')
    setContactTypes([])
    setVerifiedEmailOnly(false)
    setPage(1)
    runSearch(undefined, readInterests())
  }, [runSearch])

  useEffect(() => {
    const controller = new AbortController()
    runSearch(controller.signal, readInterests())
    return () => controller.abort()
  }, [])

  // Reset page when filters change
  useEffect(() => {
    setPage(1)
  }, [degreeLevels, lifecycle, country, institution, contactTypes, verifiedEmailOnly])

  // Search when interests change
  useEffect(() => {
    runSearch(undefined, readInterests())
  }, [interestsInput])

  const totalPages = results?.total_pages || 0
  const total = results?.total || 0

  return (
    <div className="sz-supervisors-page">
      <header className="sz-supervisors-page__header">
        <div>
          <p className="sz-supervisors-page__eyebrow">Supervisor discovery</p>
          <h1>Find Potential Supervisors</h1>
        </div>
        <p className="sz-supervisors-page__description">
          Explore faculty research areas and official university contacts linked to currently open and upcoming scholarships.
        </p>
      </header>

      <section className="sz-supervisors-page__interests" aria-labelledby="interests-heading">
        <h2 id="interests-heading" className="sz-sr-only">Your research interests</h2>
        <label htmlFor="sz-interests">Your research interests</label>
        <input
          id="sz-interests"
          type="text"
          value={interestsInput}
          placeholder="e.g. machine learning, public health, renewable energy"
          onChange={(event) => setInterestsInput(event.target.value)}
        />
        <button type="button" onClick={saveInterestsAndSearch}>
          Compare
        </button>
        <p className="sz-supervisors-page__interests-note">
          Used only to compare your words with published faculty areas. Stored in this browser, never inferred from anything else.
        </p>
      </section>

      <Filters
        degreeLevels={degreeLevels}
        setDegreeLevels={handleFilterChange}
        lifecycle={lifecycle}
        setLifecycle={handleFilterChange}
        country={country}
        setCountry={handleFilterChange}
        institution={institution}
        setInstitution={handleFilterChange}
        contactTypes={contactTypes}
        setContactTypes={handleFilterChange}
        verifiedEmailOnly={verifiedEmailOnly}
        setVerifiedEmailOnly={handleFilterChange}
        onReset={handleReset}
      />

      {state === 'loading' && (
        <div className="sz-supervisors-page__loading" aria-live="polite">
          Searching for published faculty information…
        </div>
      )}

      {state === 'error' && (
        <div className="sz-supervisors-page__error" role="alert">
          Supervisor information is unavailable right now. {error}
          <button type="button" onClick={() => runSearch(undefined, readInterests())}>
            Try again
          </button>
        </div>
      )}

      {state === 'ready' && results && (
        <>
          {results.items.length === 0 ? (
            <div className="sz-supervisors-page__empty">
              <p>No verified supervisors found matching your criteria.</p>
              <p>This does not mean there are no supervisors — it means ScholarZone has not verified any on an official page for the current filters.</p>
              <p>Try adjusting your filters or removing research interests to broaden the search.</p>
            </div>
          ) : (
            <>
              <div className="sz-supervisors-page__results-count">
                Showing {results.items.length} of {total} result{total !== 1 ? 's' : ''}
              </div>
              <div className="sz-supervisors-page__results">
                {results.items.map((result, index) => (
                  <SupervisorCard key={`${result.professor_id}-${result.scholarship_id}`} result={result} />
                ))}
              </div>
              {totalPages > 1 && (
                <nav className="sz-supervisors-page__pagination" aria-label="Pagination">
                  <button
                    type="button"
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={page === 1}
                    aria-label="Previous page"
                  >
                    Previous
                  </button>
                  <span className="sz-supervisors-page__page-info">
                    Page {page} of {totalPages}
                  </span>
                  <button
                    type="button"
                    onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                    disabled={page >= totalPages}
                    aria-label="Next page"
                  >
                    Next
                  </button>
                </nav>
              )}
            </>
          )}
        </>
      )}
    </div>
  )
}