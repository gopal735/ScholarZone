/**
 * Saved scholarships, gaps, and next actions.
 *
 * Gaps and next actions both arrive from the server, already deduplicated and
 * already ordered by the server's fixed priority bands. Neither list is sorted,
 * ranked, filtered or re-worded here. In particular no urgency is computed: a
 * deadline is called "closing" because the matching engine put it in the
 * closing-soon bucket, not because this file compared a date to now.
 *
 * Every gap resolves to a real page. A gap a student cannot close would be worse
 * than no gap, so the server sends an href with each one and the link uses it.
 */

import { Link } from 'react-router-dom'
import { deadlineText, verificationLabel } from '../../services/dashboardPresentation'

export function SavedScholarships({ saved, onRemove }) {
  if (!saved || saved.length === 0) {
    return (
      <section className="dashboard-section" aria-labelledby="saved-heading">
        <div className="dashboard-section__header">
          <div>
            <p className="page-eyebrow">Shortlist</p>
            <h2 className="dashboard-section__title" id="saved-heading">
              Saved scholarships
            </h2>
          </div>
        </div>
        <div className="empty-state">
          <h3>Save scholarships you are considering.</h3>
          <p>Use Save on any scholarship to keep it here with its deadline and readiness.</p>
          <Link to="/scholarships" className="sz-btn sz-btn--primary">
            Browse scholarships
          </Link>
        </div>
      </section>
    )
  }

  return (
    <section className="dashboard-section" aria-labelledby="saved-heading">
      <div className="dashboard-section__header">
        <div>
          <p className="page-eyebrow">Shortlist</p>
          <h2 className="dashboard-section__title" id="saved-heading">
            Saved scholarships
          </h2>
        </div>
        {saved.length >= 2 ? (
          <Link to="/compare" className="sz-btn sz-btn--secondary">
            Compare saved
          </Link>
        ) : null}
      </div>

      <ul className="saved-list">
        {saved.map((item) => {
          const scholarship = item.scholarship
          return (
            <li className="saved-item" key={scholarship.scholarship_id}>
              <div className="saved-item__main">
                <h3 className="saved-item__title">
                  <Link to={scholarship.detail_url}>{scholarship.name}</Link>
                </h3>
                <p className="saved-item__meta">
                  {scholarship.country} · {scholarship.degree}
                </p>
              </div>
              <dl className="saved-item__facts">
                <div className="saved-item__fact">
                  <dt>Deadline</dt>
                  <dd>{deadlineText(item)}</dd>
                </div>
                <div className="saved-item__fact">
                  <dt>Readiness</dt>
                  <dd>{item.readiness_label || 'Not evaluated'}</dd>
                </div>
                <div className="saved-item__fact">
                  <dt>Verification</dt>
                  <dd>
                    <span className={scholarship.verified ? 'is-verified' : 'is-unconfirmed'}>
                      {verificationLabel(scholarship)}
                    </span>
                  </dd>
                </div>
                <div className="saved-item__fact">
                  <dt>State</dt>
                  <dd>{item.application_state ? item.application_state.replace(/_/g, ' ') : 'Not started'}</dd>
                </div>
              </dl>
              <button
                type="button"
                className="sz-btn sz-btn--ghost"
                onClick={() => onRemove(scholarship.scholarship_id)}
              >
                Remove
              </button>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

export function ProfileGaps({ gaps }) {
  if (!gaps || gaps.length === 0) {
    return (
      <section className="dashboard-section" aria-labelledby="gaps-heading">
        <div className="dashboard-section__header">
          <div>
            <p className="page-eyebrow">Improve your profile</p>
            <h2 className="dashboard-section__title" id="gaps-heading">
              Nothing missing
            </h2>
          </div>
        </div>
        <p className="dashboard-section__note">
          Every field ScholarZone measures has been supplied, so nothing here is unevaluated.
        </p>
      </section>
    )
  }

  return (
    <section className="dashboard-section" aria-labelledby="gaps-heading">
      <div className="dashboard-section__header">
        <div>
          <p className="page-eyebrow">Improve your profile</p>
          <h2 className="dashboard-section__title" id="gaps-heading">
            What is missing
          </h2>
        </div>
        <p className="dashboard-section__universe">{gaps.length} open</p>
      </div>
      <ul className="gap-list">
        {gaps.map((gap) => (
          <li className="gap-item" key={`${gap.code}-${gap.component || ''}`}>
            <p className="gap-item__message">{gap.message}</p>
            {gap.action_label ? (
              <Link className="sz-btn sz-btn--secondary gap-item__action" to={gap.href}>
                {gap.action_label}
              </Link>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  )
}

export function NextActions({ actions }) {
  if (!actions || actions.length === 0) return null

  return (
    <section className="dashboard-section" aria-labelledby="next-actions-heading">
      <div className="dashboard-section__header">
        <div>
          <p className="page-eyebrow">Next</p>
          <h2 className="dashboard-section__title" id="next-actions-heading">
            Next actions
          </h2>
        </div>
        <p className="dashboard-section__universe">In the order ScholarZone suggests</p>
      </div>
      <ol className="next-action-list">
        {actions.map((action) => (
          <li className="next-action" key={action.code}>
            <div className="next-action__body">
              <h3 className="next-action__title">{action.title}</h3>
              <p className="next-action__detail">{action.detail}</p>
            </div>
            <Link className="sz-btn sz-btn--primary next-action__cta" to={action.href}>
              {action.action_label}
            </Link>
          </li>
        ))}
      </ol>
    </section>
  )
}