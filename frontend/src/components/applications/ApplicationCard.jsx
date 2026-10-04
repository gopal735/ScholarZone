/**
 * One application in the workspace list.
 *
 * The information order is deliberate and fixed: what it is, when it closes, where
 * it stands, how ready the student is, how far they have got, what is outstanding,
 * and what to do next. The deadline sits second because it is the fact that
 * decides whether any of the rest is urgent, and burying it below a progress bar
 * is how a student misses a closing round.
 *
 * Urgency is never carried by colour alone. `deadlineUrgency` returns a word, and
 * that word is rendered as text beside the date.
 */

import { Link } from 'react-router-dom'
import {
  deadlineText,
  deadlineUrgency,
  hasExactDeadline,
  nextActionHint,
  outcomeLabel,
  progressText,
  progressValue,
  stateLabel,
} from '../../services/applicationPresentation'

function UrgencyTag({ application }) {
  const urgency = deadlineUrgency(application)
  if (urgency === 'none') return null

  const labels = {
    overdue: 'Deadline passed',
    urgent: 'Closing soon',
    soon: 'Approaching',
    comfortable: 'Open',
  }

  return (
    <span className={`application-item__urgency application-item__urgency--${urgency}`}>
      <svg viewBox="0 0 24 24" aria-hidden="true" className="application-item__urgency-icon">
        <path d="M12 8v5m0 3h.01M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z" />
      </svg>
      {labels[urgency]}
    </span>
  )
}

function ProgressRow({ application }) {
  const value = progressValue(application)
  const text = progressText(application)

  // Nothing to measure. No bar, no percentage, no implication of zero.
  if (value === null || text === null) {
    return (
      <p className="application-item__progress application-item__progress--unmeasured">
        No tracked tasks yet
      </p>
    )
  }

  return (
    <div className="application-item__progress">
      <div className="application-item__progress-head">
        <span className="application-item__progress-label">Tasks completed</span>
        <span className="application-item__progress-value">{text}</span>
      </div>
      <div
        className="application-item__progress-track"
        role="progressbar"
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Tasks completed for ${application.name}`}
      >
        <span className="application-item__progress-fill" style={{ width: `${value}%` }} />
      </div>
    </div>
  )
}

export default function ApplicationCard({ application, onSelect }) {
  const unlisted = !application.availability.is_available

  return (
    <li className={`application-item${unlisted ? ' application-item--unlisted' : ''}`}>
      <article aria-labelledby={`application-${application.id}-title`}>
        <header className="application-item__header">
          <div className="application-item__identity">
            <h3 className="application-item__title" id={`application-${application.id}-title`}>
              {unlisted ? (
                application.name
              ) : (
                <Link to={application.detail_url}>{application.name}</Link>
              )}
            </h3>
            <p className="application-item__meta">
              {[
                application.country,
                application.degree,
                application.provider,
              ]
                .filter(Boolean)
                .join(' · ')}
            </p>
          </div>
          <span className="application-item__state">{stateLabel(application.state)}</span>
        </header>

        {/*
          Deadline second, before anything else about progress. Urgency is a word
          as well as a rule, so it survives a monochrome display.
        */}
        <div className="application-item__deadline">
          <p className="application-item__deadline-text">{deadlineText(application)}</p>
          <UrgencyTag application={application} />
          {!hasExactDeadline(application) && application.deadline_text ? (
            <span className="application-item__deadline-note">date not day-specific</span>
          ) : null}
        </div>

        <dl className="application-item__facts">
          <div className="application-item__fact">
            <dt>Outcome</dt>
            <dd>{outcomeLabel(application.outcome)}</dd>
          </div>
          {application.readiness_label ? (
            <div className="application-item__fact">
              <dt>Readiness</dt>
              <dd>{application.readiness_label}</dd>
            </div>
          ) : null}
          {typeof application.fit_score === 'number' ? (
            <div className="application-item__fact">
              <dt>Match fit</dt>
              <dd>
                {Math.round(application.fit_score)}
                {application.fit_label_display ? ` · ${application.fit_label_display}` : ''}
              </dd>
            </div>
          ) : null}
          <div className="application-item__fact">
            <dt>Verification</dt>
            <dd>
              <span className={application.verified ? 'is-verified' : 'is-unconfirmed'}>
                {application.verification_display}
              </span>
            </dd>
          </div>
        </dl>

        <ProgressRow application={application} />

        <p className="application-item__next">{nextActionHint(application)}</p>

        {unlisted ? (
          <p className="application-item__unlisted-note">{application.availability.reason}</p>
        ) : null}

        <footer className="application-item__footer">
          <button
            type="button"
            className="sz-btn sz-btn--primary"
            onClick={() => onSelect(application)}
          >
            Open workspace
          </button>
          {!unlisted ? (
            <Link to={application.detail_url} className="sz-btn sz-btn--secondary">
              View scholarship
            </Link>
          ) : null}
          <span className="application-item__updated">
            Updated {new Date(application.updated_at).toLocaleDateString()}
          </span>
        </footer>
      </article>
    </li>
  )
}