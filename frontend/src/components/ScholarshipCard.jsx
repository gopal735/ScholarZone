import { Link } from 'react-router-dom'
import ScholarshipImage from './ScholarshipImage'
import ScholarshipActions from './ScholarshipActions'
import { getDeadlineLabel, getLastVerifiedLabel, getScholarshipStatus } from '../utils/scholarshipPresentation'
import './ScholarshipCard.css'

export default function ScholarshipCard({ scholarship }) {
  const deadlineStatus = getScholarshipStatus(scholarship)
  const isVerified = scholarship.verified ?? true

  return (
    <article className={`scholarship-card scholarship-card--${deadlineStatus.className}`}>
      <ScholarshipImage scholarship={scholarship} className="scholarship-card__image" />

      <div className="scholarship-card__header">
        <div className="scholarship-card__topline">
          <span className="scholarship-card__badge">{scholarship.funding}</span>
          <span className={`scholarship-card__status scholarship-card__status--${deadlineStatus.className}`}>{deadlineStatus.label}</span>
        </div>

        <h2>{scholarship.title}</h2>

        <div className="scholarship-card__signals">
          <span className={isVerified ? 'scholarship-card__verified' : 'scholarship-card__unverified'}>
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="m8 12 2.5 2.5L16 9m4-3v6c0 5-3.4 8.7-8 10-4.6-1.3-8-5-8-10V6l8-3 8 3Z" />
            </svg>
            {isVerified ? 'Verified' : 'Confirm with provider'}
          </span>
          <span className="scholarship-card__verification-date">{getLastVerifiedLabel(scholarship.last_verified_at)}</span>
        </div>
      </div>

      <dl className="scholarship-card__details">
        <div className="scholarship-card__detail">
          <dt>Country / region</dt>
          <dd>{scholarship.country}</dd>
        </div>
        <div className="scholarship-card__detail">
          <dt>Degree level</dt>
          <dd>{scholarship.degree}</dd>
        </div>
        <div className={`scholarship-card__detail scholarship-card__detail--deadline scholarship-card__detail--${deadlineStatus.className}`}>
          <dt>Application deadline</dt>
          <dd>{getDeadlineLabel(scholarship)}</dd>
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
