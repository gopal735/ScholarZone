/**
 * Your matches, and why each one matches.
 *
 * The fit score, confidence and readiness on these cards were computed by Match
 * 2.0 and arrive unchanged. So does every line of "why it matches" and "needs
 * attention": those are the engine's own structured `reasons` and `gaps`, with
 * their codes intact, not sentences written here. There is no generator in this
 * file, because a generated explanation is an assertion the engine never made.
 *
 * Three absences are handled explicitly rather than smoothed over, because each
 * one would otherwise read as a bad result rather than a missing measurement:
 * a `fit_score` of null (not evaluated, or the eligibility gate refused the
 * record), a `readiness_label` of null, and a deadline with no fixed date.
 */

import { Link } from 'react-router-dom'
import {
  deadlineText,
  fitLabel,
  isExactDeadline,
  readinessLabel,
  verificationLabel,
} from '../../services/dashboardPresentation'

function EvidenceList({ title, items, variant }) {
  if (!items || items.length === 0) return null
  return (
    <div className={`match-card__evidence match-card__evidence--${variant}`}>
      <h4 className="match-card__evidence-title">{title}</h4>
      <ul className="match-card__evidence-list">
        {items.map((item) => (
          <li className="match-card__evidence-item" key={`${item.code}-${item.component || ''}`}>
            <span className="match-card__evidence-message">{item.message}</span>
            {item.component ? (
              <span className="match-card__evidence-component">{titleCase(item.component)}</span>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  )
}

function titleCase(value) {
  return String(value)
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ')
}

export default function MatchList({ matches, truncated, onSave, savedIds }) {
  if (!matches || matches.length === 0) {
    return (
      <section className="dashboard-section" aria-labelledby="matches-heading">
        <div className="dashboard-section__header">
          <div>
            <p className="page-eyebrow">Your matches</p>
            <h2 className="dashboard-section__title" id="matches-heading">
              No current matches
            </h2>
          </div>
        </div>
        <div className="empty-state">
          <h3>Nothing matches this profile yet.</h3>
          <p>
            That usually means a published requirement cannot be checked against what you have supplied,
            rather than that there is nothing available.
          </p>
          <Link to="/match" className="sz-btn sz-btn--primary">
            Adjust your profile
          </Link>
        </div>
      </section>
    )
  }

  return (
    <section className="dashboard-section" aria-labelledby="matches-heading">
      <div className="dashboard-section__header">
        <div>
          <p className="page-eyebrow">Your matches</p>
          <h2 className="dashboard-section__title" id="matches-heading">
            Recommended scholarships
          </h2>
        </div>
        {truncated ? (
          <p className="dashboard-section__universe" role="status">
            Showing the strongest {matches.length}. Every count above describes all analysed
            opportunities.
          </p>
        ) : null}
      </div>

      <ul className="match-list">
        {matches.map((match) => {
          const isSaved = savedIds.has(String(match.scholarship_id))
          return (
            <li className="match-card" key={match.scholarship_id}>
              <article aria-labelledby={`match-${match.scholarship_id}-title`}>
                <header className="match-card__header">
                  <div className="match-card__heading">
                    <h3 className="match-card__title" id={`match-${match.scholarship_id}-title`}>
                      <Link to={match.detail_url}>{match.name}</Link>
                    </h3>
                    <p className="match-card__meta">
                      {match.country} · {match.degree}
                      {match.funding ? ` · ${titleCase(match.funding)} funding` : ''}
                    </p>
                  </div>
                  <div className="match-card__badges">
                    {/*
                      The trust state is never colour alone: the server's own
                      label travels with the badge, so "Confirm with provider"
                      reads the same whether or not colour is perceived.
                    */}
                    <span
                      className={`sz-badge ${match.verified ? 'sz-badge--success' : 'sz-badge--warning'}`}
                    >
                      {match.verified ? (
                        <svg viewBox="0 0 24 24" aria-hidden="true" className="match-card__badge-icon">
                          <path d="m9 12 2 2 4-4m5-4v6c0 5-3.4 8.7-8 10-4.6-1.3-8-5-8-10V6l8-3 8 3Z" />
                        </svg>
                      ) : (
                        <svg viewBox="0 0 24 24" aria-hidden="true" className="match-card__badge-icon">
                          <path d="M12 8v5m0 3h.01M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z" />
                        </svg>
                      )}
                      {verificationLabel(match)}
                    </span>
                  </div>
                </header>

                <dl className="match-card__scores">
                  <div className="match-card__score">
                    <dt>Fit</dt>
                    <dd>
                      {fitLabel(match)}
                      {typeof match.fit_score === 'number' ? (
                        <span className="match-card__score-number">{Math.round(match.fit_score)}</span>
                      ) : null}
                    </dd>
                  </div>
                  <div className="match-card__score">
                    <dt>Confidence</dt>
                    <dd>
                      {titleCase(match.confidence_label)}
                      <span className="match-card__score-number">{Math.round(match.confidence_score)}</span>
                    </dd>
                  </div>
                  <div className="match-card__score">
                    <dt>Readiness</dt>
                    <dd>{readinessLabel(match)}</dd>
                  </div>
                  <div className="match-card__score">
                    <dt>Deadline</dt>
                    <dd>
                      {deadlineText(match)}
                      {isExactDeadline(match) ? null : (
                        <span className="match-card__score-note">date not day-specific</span>
                      )}
                    </dd>
                  </div>
                </dl>

                <EvidenceList title="Why it matches" items={match.why} variant="why" />
                <EvidenceList title="Needs attention" items={match.needs_attention} variant="attention" />

                {match.unverified_requirements.length > 0 ? (
                  <details className="match-card__requirements">
                    <summary className="match-card__requirements-summary">
                      {match.unverified_requirements.length} published requirement
                      {match.unverified_requirements.length === 1 ? '' : 's'} not confirmed
                    </summary>
                    <ul className="match-card__requirements-list">
                      {match.unverified_requirements.map((requirement) => (
                        <li className="match-card__requirement" key={`${requirement.kind}-${requirement.summary}`}>
                          <p className="match-card__requirement-summary">{requirement.summary}</p>
                          {/*
                            The provider's own wording and where it came from
                            travel together. Match's rule is that a reader who
                            cannot produce both may not state a requirement at
                            all, so neither is ever shown without the other.
                          */}
                          {requirement.raw_quote ? (
                            <blockquote className="match-card__requirement-quote">
                              {requirement.raw_quote}
                            </blockquote>
                          ) : null}
                          {requirement.provenance_url ? (
                            <a
                              className="match-card__requirement-source"
                              href={requirement.provenance_url}
                              target="_blank"
                              rel="noreferrer noopener"
                            >
                              Official source
                            </a>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  </details>
                ) : null}

                <footer className="match-card__footer">
                  {match.official_source_url ? (
                    <a
                      className="match-card__source"
                      href={match.official_source_url}
                      target="_blank"
                      rel="noreferrer noopener"
                    >
                      Official source
                    </a>
                  ) : (
                    <span className="match-card__source match-card__source--missing">No official source published</span>
                  )}
                  <button
                    type="button"
                    className="sz-btn sz-btn--secondary"
                    aria-pressed={isSaved}
                    onClick={() => onSave(match.scholarship_id, !isSaved)}
                  >
                    {isSaved ? 'Saved' : 'Save'}
                  </button>
                </footer>
              </article>
            </li>
          )
        })}
      </ul>
    </section>
  )
}