import { useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import ScholarshipImage from './ScholarshipImage'
import ScholarshipActions from './ScholarshipActions'
import { getDeadlineLabel, getLastVerifiedLabel, getScholarshipStatus } from '../utils/scholarshipPresentation'
import './ScholarshipCard.css'

/* Pointer input is ignored on touch and coarse pointers — there is no
   hover state there, and a highlight would be left stuck after a tap.
   The stylesheet also neutralises the layer for those input types; this
   just avoids attaching listeners at all. Evaluated once at module load
   rather than per card per render. */
const CAN_TILT =
  typeof window !== 'undefined' &&
  window.matchMedia('(hover: hover) and (pointer: fine)').matches

export default function ScholarshipCard({ scholarship }) {
  const deadlineStatus = getScholarshipStatus(scholarship)
  const isVerified = scholarship.verified ?? true
  const cardRef = useRef(null)

  /* Provenance, not decoration. image_kind is the honest signal: an image_url
     exists on 401 records but only 387 are validated official_logo, and the
     difference is exactly what this line has to tell the truth about. */
  const hasOfficialLogo = scholarship.image_kind === 'official_logo'
  const verifiedOn = scholarship.last_verified_at || null

  /* Writes two custom properties straight to the node. No React state
     and no animation loop, so a pointer sweep across a grid only costs a
     style recalc on the one card under the cursor. The card lifts on
     its own in CSS; only the light position is driven from here, which
     is what keeps the interaction from reading as a pivoting object. */
  const handlePointerMove = useCallback((event) => {
    const card = cardRef.current
    if (!card) return

    const rect = card.getBoundingClientRect()
    if (rect.width === 0 || rect.height === 0) return

    const x = (event.clientX - rect.left) / rect.width
    const y = (event.clientY - rect.top) / rect.height

    card.style.setProperty('--lg-hx', `${x * 100}%`)
    card.style.setProperty('--lg-hy', `${y * 100}%`)
  }, [])

  const handlePointerLeave = useCallback(() => {
    const card = cardRef.current
    if (!card) return

    card.style.setProperty('--lg-hx', '50%')
    card.style.setProperty('--lg-hy', '0%')
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

        {/* The Provenance Rule. The square is the identity: filled when the
            record carries a validated official logo, hollow when it does not.
            Keyed on image_kind rather than image_url on purpose — 401 records
            carry an image but only 387 of them are official_logo, and the rest
            must read as unproven rather than borrow a mark they have not
            earned. The hollow state is part of the design, not a gap. */}
        <div
          className={`scholarship-card__title-rule${
            hasOfficialLogo ? '' : ' scholarship-card__title-rule--unverified'
          }`}
          aria-hidden="true"
        />
        <small className="scholarship-card__citation">
          ↳ {hasOfficialLogo ? 'Official source captured' : 'No official logo'}
          {verifiedOn ? ` · ${verifiedOn}` : ''}
        </small>

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
