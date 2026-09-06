import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import ScholarshipImage from '../components/ScholarshipImage'
import ScholarshipActions from '../components/ScholarshipActions'
import { fetchScholarshipById, ScholarshipApiError } from '../services/scholarshipService'
import { useScholarshipDirectory } from '../hooks/useScholarshipDirectory'
import { getDeadlineLabel, getLastVerifiedLabel, getScholarshipStatus } from '../utils/scholarshipPresentation'
import './ScholarshipDetailsPage.css'

function BackToDirectory({ compact = false }) {
  return (
    <Link to="/scholarships" className="scholarship-details__back">
      <span aria-hidden="true">&larr;</span> {compact ? 'All scholarships' : 'Back to scholarships'}
    </Link>
  )
}

function MissingScholarship() {
  return (
    <section className="scholarship-details scholarship-details--missing">
      <BackToDirectory compact />
      <div className="scholarship-details__empty">
        <span className="scholarship-details__empty-icon" aria-hidden="true">?</span>
        <p className="scholarship-details__eyebrow">Scholarship directory</p>
        <h1>Scholarship not found</h1>
        <p>The scholarship you requested is unavailable or the link is incorrect.</p>
        <Link to="/scholarships" className="scholarship-details__action">
          Browse scholarships <span aria-hidden="true">&rarr;</span>
        </Link>
      </div>
    </section>
  )
}

function LoadingScholarship() {
  return (
    <section className="scholarship-details" aria-busy="true" aria-label="Loading scholarship details">
      <BackToDirectory />
      <div className="scholarship-details__loading" aria-hidden="true">
        <span className="scholarship-details__loading-line scholarship-details__loading-line--status" />
        <span className="scholarship-details__loading-line scholarship-details__loading-line--title" />
        <span className="scholarship-details__loading-line scholarship-details__loading-line--description" />
        <span className="scholarship-details__loading-line scholarship-details__loading-line--description" />
      </div>
    </section>
  )
}

function DetailsLoadError({ onRetry }) {
  return (
    <section className="scholarship-details scholarship-details--missing">
      <BackToDirectory compact />
      <div className="scholarship-details__empty">
        <span className="scholarship-details__empty-icon" aria-hidden="true">!</span>
        <p className="scholarship-details__eyebrow">Connection issue</p>
        <h1>Scholarship details couldn&apos;t be loaded</h1>
        <p>Please try again. You can also return to the directory and continue exploring available opportunities.</p>
        <button type="button" className="scholarship-details__action" onClick={onRetry}>Try again</button>
      </div>
    </section>
  )
}

function DetailsChecklist({ eyebrow, title, items, emptyMessage }) {
  return (
    <article className="scholarship-details__panel scholarship-details__list-panel">
      <div className="scholarship-details__panel-heading">
        <div>
          <p className="scholarship-details__eyebrow">{eyebrow}</p>
          <h2>{title}</h2>
        </div>
      </div>
      {items.length > 0 ? (
        <ul className="scholarship-details__checklist">
          {items.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}
        </ul>
      ) : (
        <p className="scholarship-details__pending-copy">{emptyMessage}</p>
      )}
    </article>
  )
}

export default function ScholarshipDetailsPage() {
  const { id } = useParams()
  const [scholarship, setScholarship] = useState(null)
  const [loadState, setLoadState] = useState('loading')
  const [retryVersion, setRetryVersion] = useState(0)
  const requestIdRef = useRef(0)
  const { scholarships: allScholarships } = useScholarshipDirectory()
  const scholarshipId = Number(id)
  const hasValidScholarshipId = Number.isInteger(scholarshipId) && scholarshipId > 0

  useEffect(() => {
    if (!hasValidScholarshipId) {
      return undefined
    }

    const controller = new AbortController()
    const requestId = requestIdRef.current + 1
    requestIdRef.current = requestId
    const localScholarship = allScholarships.find((item) => item.id === scholarshipId)

    const startRequest = window.setTimeout(() => {
      setScholarship(null)
      setLoadState('loading')

      fetchScholarshipById(scholarshipId, { signal: controller.signal })
        .then((response) => {
          if (controller.signal.aborted || requestId !== requestIdRef.current) {
            return
          }

          setScholarship(response)
          setLoadState('success')
        })
        .catch((error) => {
          if (controller.signal.aborted || requestId !== requestIdRef.current) {
            return
          }

          if (error instanceof ScholarshipApiError && error.status === 404) {
            setLoadState('missing')
            return
          }

          if (localScholarship) {
            setScholarship(localScholarship)
            setLoadState('fallback')
            return
          }

          setLoadState('error')
        })
    }, 0)

    return () => {
      window.clearTimeout(startRequest)
      controller.abort()
    }
  }, [hasValidScholarshipId, retryVersion, scholarshipId, allScholarships])

  if (!hasValidScholarshipId) {
    return <MissingScholarship />
  }

  if (loadState === 'loading') {
    return <LoadingScholarship />
  }

  if (loadState === 'missing') {
    return <MissingScholarship />
  }

  if (loadState === 'error' || !scholarship) {
    return <DetailsLoadError onRetry={() => setRetryVersion((version) => version + 1)} />
  }

  const isVerified = scholarship.verified ?? true
  const deadlineStatus = getScholarshipStatus(scholarship)
  const benefits = Array.isArray(scholarship.benefits) ? scholarship.benefits : []
  const eligibility = Array.isArray(scholarship.eligibility) ? scholarship.eligibility : []
  const requirements = Array.isArray(scholarship.requirements) ? scholarship.requirements : []
  const relatedScholarships = allScholarships.filter((item) => (
    item.id !== scholarship.id && (item.country === scholarship.country || item.degree === scholarship.degree)
  )).slice(0, 3)

  return (
    <section className="scholarship-details">
      <BackToDirectory />

      {loadState === 'fallback' && (
        <div className="scholarship-details__source-notice" role="status">
          Live details are unavailable. Showing local scholarship data instead.
          <button type="button" onClick={() => setRetryVersion((version) => version + 1)}>Retry</button>
        </div>
      )}

      <div className="scholarship-details__hero">
        {scholarship.image_url && (
          <div className="scholarship-details__image">
            <ScholarshipImage scholarship={scholarship} className="scholarship-details__image-wrapper" />
          </div>
        )}

        <div className="scholarship-details__hero-content">
          <div className="scholarship-details__status">
            <span className={isVerified ? 'scholarship-details__verified' : 'scholarship-details__unverified'}>
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="m8 12 2.5 2.5L16 9m4-3v6c0 5-3.4 8.7-8 10-4.6-1.3-8-5-8-10V6l8-3 8 3Z" />
              </svg>
              {isVerified ? 'Verified listing' : 'Confirm with provider'}
            </span>
            <span className="scholarship-details__funding">{scholarship.funding}</span>
            <span className={`scholarship-details__status-badge scholarship-details__status-badge--${deadlineStatus.className}`}>{deadlineStatus.label}</span>
          </div>

          <h1>{scholarship.title}</h1>

          <div className="scholarship-details__meta" aria-label="Scholarship summary">
            <span>{scholarship.country}</span>
            <span>{scholarship.degree} degree</span>
          </div>

          <p className="scholarship-details__intro">
            {scholarship.description || 'Review the essential funding and study details, then confirm requirements with the scholarship provider before you apply.'}
          </p>

          <p className="scholarship-details__verified-date">{getLastVerifiedLabel(scholarship.last_verified_at)}</p>

          <ScholarshipActions scholarshipId={scholarship.id} variant="details" />
        </div>

        <aside className={`scholarship-details__deadline scholarship-details__deadline--${deadlineStatus.className}`} aria-label={`Application deadline: ${getDeadlineLabel(scholarship)}`}>
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M7 3v3m10-3v3M4 9h16M5 5h14a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Z" />
          </svg>
          <div>
            <span>Application deadline</span>
            <strong>{getDeadlineLabel(scholarship)}</strong>
          </div>
        </aside>
      </div>

      <div className="scholarship-details__content">
        <article className="scholarship-details__panel scholarship-details__panel--overview">
          <div className="scholarship-details__panel-heading">
            <div>
              <p className="scholarship-details__eyebrow">Opportunity overview</p>
              <h2>Key information</h2>
            </div>
            <span className="scholarship-details__panel-mark" aria-hidden="true">01</span>
          </div>

          <dl className="scholarship-details__facts">
            <div>
              <dt>Country or region</dt>
              <dd>{scholarship.country}</dd>
            </div>
            <div>
              <dt>Degree level</dt>
              <dd>{scholarship.degree}</dd>
            </div>
            <div>
              <dt>Funding coverage</dt>
              <dd>{scholarship.funding}</dd>
            </div>
          </dl>
        </article>

        <aside className="scholarship-details__panel scholarship-details__next-steps">
          <div className="scholarship-details__panel-heading">
            <div>
              <p className="scholarship-details__eyebrow">Apply with confidence</p>
              <h2>Before you apply</h2>
            </div>
            <span className="scholarship-details__panel-mark" aria-hidden="true">02</span>
          </div>
          <p>Prepare your documents early and use the official scholarship source to confirm eligibility, requirements and dates.</p>
          <Link to="/scholarships" className="scholarship-details__text-link">
            Continue exploring <span aria-hidden="true">&rarr;</span>
          </Link>
        </aside>
      </div>

      <div className="scholarship-details__section-grid">
        <DetailsChecklist
          eyebrow="Funding support"
          title="Benefits"
          items={benefits}
          emptyMessage="Provider-specific benefits have not been supplied for this listing yet."
        />
        <DetailsChecklist
          eyebrow="Who can apply"
          title="Eligibility"
          items={eligibility}
          emptyMessage="Eligibility details are awaiting confirmation from the official provider."
        />
        <DetailsChecklist
          eyebrow="Prepare your application"
          title="Requirements"
          items={requirements}
          emptyMessage="Application requirements are not available in the current provider data."
        />
      </div>

      <div className="scholarship-details__section-grid scholarship-details__section-grid--secondary">
        <article className="scholarship-details__panel scholarship-details__timeline">
          <div className="scholarship-details__panel-heading">
            <div>
              <p className="scholarship-details__eyebrow">Plan ahead</p>
              <h2>Application timeline</h2>
            </div>
          </div>
          <dl>
            <div><dt>Listing status</dt><dd>{deadlineStatus.label}</dd></div>
            <div><dt>Deadline</dt><dd>{getDeadlineLabel(scholarship)}</dd></div>
            <div><dt>Date precision</dt><dd>{scholarship.deadline_precision === 'month' ? 'Month provided by source' : 'Provider date'}</dd></div>
          </dl>
        </article>

        <article className="scholarship-details__panel scholarship-details__source">
          <div className="scholarship-details__panel-heading">
            <div>
              <p className="scholarship-details__eyebrow">Apply safely</p>
              <h2>Official application source</h2>
            </div>
          </div>
          {scholarship.application_link || scholarship.official_source_url ? (
            <a href={scholarship.application_link || scholarship.official_source_url} target="_blank" rel="noreferrer" className="scholarship-details__source-link">
              {scholarship.official_source || 'Visit official application page'} <span aria-hidden="true">&nearr;</span>
            </a>
          ) : (
            <p className="scholarship-details__pending-copy">An official application link has not been confirmed for this listing. Verify directly with the provider before applying.</p>
          )}
        </article>
      </div>

      <section className="scholarship-details__related" aria-labelledby="related-scholarships-heading">
        <div className="scholarship-details__related-heading">
          <div>
            <p className="scholarship-details__eyebrow">Keep exploring</p>
            <h2 id="related-scholarships-heading">Related scholarships</h2>
          </div>
          <Link to="/scholarships" className="scholarship-details__text-link">Browse all <span aria-hidden="true">&rarr;</span></Link>
        </div>
        {relatedScholarships.length > 0 ? (
          <div className="scholarship-details__related-grid">
            {relatedScholarships.map((item) => (
              <Link key={item.id} to={`/scholarships/${item.id}`} className="scholarship-details__related-card">
                <span>{item.funding}</span>
                <strong>{item.title}</strong>
                <small>{item.country} / {item.degree}</small>
              </Link>
            ))}
          </div>
        ) : (
          <p className="scholarship-details__pending-copy">More related opportunities will appear as the directory grows.</p>
        )}
      </section>
    </section>
  )
}
