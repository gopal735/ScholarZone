import { useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import ScholarshipImage from './ScholarshipImage'
import ScholarshipActions from './ScholarshipActions'
import { getDeadlineLabel, getLastVerifiedLabel, getScholarshipStatus } from '../utils/scholarshipPresentation'
import './ScholarshipCard.css'

/* Max tilt in degrees. Deliberately small: the surface should appear to
   turn slightly under the pointer, never to tip toward the viewer. */
const MAX_TILT = 3

/* Pointer input is ignored on touch and coarse pointers — there is no
   hover state there, and a tilt would be left stuck after a tap. The
   stylesheet also neutralises the transform for those input types; this
   just avoids attaching listeners at all. Evaluated once at module load
   rather than per card per render. */
const CAN_TILT =
  typeof window !== 'undefined' &&
  window.matchMedia('(hover: hover) and (pointer: fine)').matches

export default function ScholarshipCard({ scholarship }) {
  const deadlineStatus = getScholarshipStatus(scholarship)
  const isVerified = scholarship.verified ?? true
  const cardRef = useRef(null)

  /* Writes four custom properties straight to the node. No React state
     and no animation loop, so a pointer sweep across a grid only costs a
     style recalc on the one card under the cursor. CSS owns the easing
     and the transition back to rest. */
  const handlePointerMove = useCallback((event) => {
    const card = cardRef.current
    if (!card) return

    const rect = card.getBoundingClientRect()
    if (rect.width === 0 || rect.height === 0) return

    const x = (event.clientX - rect.left) / rect.width
    const y = (event.clientY - rect.top) / rect.height

    card.style.setProperty('--lg-ry', `${(x - 0.5) * 2 * MAX_TILT}deg`)
    card.style.setProperty('--lg-rx', `${(0.5 - y) * 2 * MAX_TILT}deg`)
    card.style.setProperty('--lg-hx', `${x * 100}%`)
    card.style.setProperty('--lg-hy', `${y * 100}%`)
  }, [])

  const handlePointerLeave = useCallback(() => {
    const card = cardRef.current
    if (!card) return

    card.style.setProperty('--lg-ry', '0deg')
    card.style.setProperty('--lg-rx', '0deg')
  }, [])

  return (
    <article
      ref={cardRef}
      className={`scholarship-card scholarship-card--${deadlineStatus.className}`}
      onPointerMove={CAN_TILT ? handlePointerMove : undefined}
      onPointerLeave={CAN_TILT ? handlePointerLeave : undefined}
    >
      <span className="scholarship-card__edge" aria-hidden="true" />

      <ScholarshipImage scholarship={scholarship} className="scholarship-card__image" />

      <div className="scholarship-card__header">
        <div className="scholarship-card__topline">
          <span className={`scholarship-card__status scholarship-card__status--${deadlineStatus.className}`}>{deadlineStatus.label}</span>
          <span className="scholarship-card__badge">{scholarship.funding}</span>
        </div>

        <h2>{scholarship.title}</h2>

        {scholarship.provider && (
          <p className="scholarship-card__provider">{scholarship.provider}</p>
        )}

        <div className="scholarship-card__signals">
          <span className={isVerified ? 'scholarship-card__verified' : 'scholarship-card__unverified'}>
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="m8 12 2.2 2.2L16 9m4-3v6c0 5-3.4 8.7-8 10-4.6-1.3-8-5-8-10V6l8-3 8 3Z" />
            </svg>
            {isVerified ? 'Verified official source' : 'Confirm with provider'}
          </span>
          {scholarship.last_verified_at && (
            <span className="scholarship-card__verification-date">{getLastVerifiedLabel(scholarship.last_verified_at)}</span>
          )}
        </div>
      </div>

      <dl className="scholarship-card__details">
        <div className={`scholarship-card__detail scholarship-card__detail--deadline scholarship-card__detail--${deadlineStatus.className}`}>
          <dt>Deadline</dt>
          <dd>{getDeadlineLabel(scholarship)}</dd>
        </div>
        <div className="scholarship-card__detail">
          <dt>Location</dt>
          <dd>{scholarship.country}</dd>
        </div>
        <div className="scholarship-card__detail">
          <dt>Level</dt>
          <dd>{scholarship.degree}</dd>
        </div>
      </dl>

      <div className="scholarship-card__footer">
        <ScholarshipActions scholarshipId={scholarship.id} />
        <Link to={`/scholarships/${scholarship.id}`} className="scholarship-card__button">
          View details <span aria-hidden="true">&rarr;</span>
        </Link>
      </div>
    </article>
  )
}
