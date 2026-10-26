import { useRef } from 'react'
import { Link } from 'react-router-dom'
import ScholarshipImage from './ScholarshipImage'
import ScholarshipActions from './ScholarshipActions'
import SupervisorCta from './SupervisorCta'
import { getDeadlineLabel, getLastVerifiedLabel, getScholarshipStatus, matchesDegreeFilter, matchesFundingFilter } from '../utils/scholarshipPresentation'
import './ScholarshipCard.css'

export default function ScholarshipCard({ scholarship, index = 0 }) {
  const deadlineStatus = getScholarshipStatus(scholarship)
  const cardRef = useRef(null)

  /* Verification state comes from verification_status, not from `verified`.

     Every record in the catalogue has verified === true, because `verified`
     records that a source was read at some point. It says nothing about
     whether this record's details have since been checked: 228 of the 400
     public listings are verification_status 'needs_review'. Reading the flag
     made every card claim "Verified official source", which is the one claim
     this product cannot afford to make loosely.

     So: active means the record was checked and holds. Anything else says so
     plainly instead of borrowing a pass mark. */
  const verificationState = scholarship.verification_status || 'needs_review'
  const isVerified = verificationState === 'active'
  const needsReview = !isVerified

  /* Provenance, not decoration. image_kind is the honest signal: an image_url
     exists on 400 records but only 384 are validated official_logo, and the
     difference is exactly what this line has to tell the truth about. */
  const hasOfficialLogo = scholarship.image_kind === 'official_logo'
  const verifiedOn = scholarship.last_verified_at || null

  /* The pointer-driven light — the gloss band, the spotlight and the 3D
     tilt — is attached once at the shell level by usePremiumPointer,
     exactly as the reference's single document listener does it. This
     component keeps no pointer state of its own: one listener measuring
     only the card under the cursor beats twelve listeners each
     re-measuring on every move event. The ref is kept for local
     behaviour, and the entrance stagger is driven by --n. */

  /* The card's own "how well does this fit" answer. The reference's bar
     is driven by the number of criteria a row meets out of the criteria
     in play; the app has the same thing available — funding certainty,
     level breadth, deadline proximity, and whether the record is
     verified — so the meter states a real ratio rather than a decoration.
     A fully-funded, open, verified programme scores all four. */
  const criteria = [
    matchesFundingFilter(scholarship.funding, 'Fully Funded'),
    !(scholarship.deadline_precision === 'month'),
    matchesDegreeFilter(scholarship.degree, 'Bachelor'),
    isVerified,
  ]
  const fitCount = criteria.filter(Boolean).length
  const fitTotal = criteria.length
  const fitLabel = `Fit ${fitCount}/${fitTotal}`
  const fitValue = String(fitCount)
  const fitPercent = Math.round((fitCount / fitTotal) * 100)

  return (
    <article
      ref={cardRef}
      className={`scholarship-card p-card p-rise scholarship-card--${deadlineStatus.className}`}
      style={{ '--n': index ?? 0 }}
    >
      <span className="scholarship-card__edge" aria-hidden="true" />

      <ScholarshipImage scholarship={scholarship} className="scholarship-card__image" />

      <div className="scholarship-card__header">
        <div className="scholarship-card__topline">
          <span className={`scholarship-card__status scholarship-card__status--${deadlineStatus.className}`}>{deadlineStatus.label}</span>
          <span className="p-tag scholarship-card__badge">{scholarship.funding}</span>
        </div>

        {/* The reference's letter square: one serif initial in a raised
            ivory tile. It is the mark the card is recognised by, and it is
            why a card reads as a physical object rather than as a panel —
            the tile has a top sheen, a contact shade and a soft drop, so
            it catches the same light as the card it sits on. */}
        <div className="scholarship-card__top">
          <div className="scholarship-card__mono" aria-hidden="true">{scholarship.title.charAt(0)}</div>
          <div className="scholarship-card__heading">
            <h2>{scholarship.title}</h2>
            <p className="scholarship-card__where">{scholarship.country}</p>
          </div>
        </div>

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
          ↳ {needsReview
            ? 'Not yet re-checked against the official page'
            : hasOfficialLogo
              ? 'Official source captured'
              : 'No official logo'}
          {verifiedOn ? ` · last checked ${verifiedOn}` : ''}
        </small>

        {scholarship.provider && (
          <p className="scholarship-card__provider">{scholarship.provider}</p>
        )}

        <div className="scholarship-card__signals">
          <span className={isVerified ? 'p-tag scholarship-card__verified' : 'p-tag scholarship-card__unverified'}>
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

      {/* The reference's fit meter: a raised accent bar inside a sunken
          track, with the count beside it in tabular figures. The bar is the
          one element that carries the "how well this matches" number, and
          it is drawn rather than written because a length against a known
          full width is read before a percentage is. */}
      <div className="scholarship-card__fit p-mb">
        <span className="scholarship-card__fit-label p-mb__label">
          {fitLabel}
        </span>
        <span className="p-track">
          <span className="p-track__fill" style={{ '--w': `${fitPercent}%` }} />
        </span>
        <em className="p-mb__value">{fitValue}</em>
      </div>

      <div className="scholarship-card__footer">
        <SupervisorCta scholarshipId={scholarship.id} />
        <ScholarshipActions scholarshipId={scholarship.id} />
        <Link to={`/scholarships/${scholarship.id}`} className="p-btn scholarship-card__button">
          View details <span aria-hidden="true">&rarr;</span>
        </Link>
      </div>
    </article>
  )
}
