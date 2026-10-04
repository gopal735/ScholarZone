/**
 * Deadline Watch.
 *
 * The order is the server's, not this component's: nearest actionable deadline,
 * then readiness, then scholarship id as a stable tiebreaker. Re-sorting here
 * would risk disagreeing with the rule the server already applied, and a table
 * that reshuffles between two identical loads is a table nobody trusts.
 *
 * Days remaining is always the engine's own figure. A null day count means the
 * deadline is rolling, recurring or simply unpublished - an open round rather
 * than a missing date - so it is written as the published wording and sorted
 * last by the server. It is never rendered as "0 days left", which would read as
 * overdue and would be the more damaging error of the two.
 */

import { Link } from 'react-router-dom'
import { deadlineText, verificationLabel } from '../../services/dashboardPresentation'

export default function DeadlineWatch({ deadlines }) {
  if (!deadlines || deadlines.length === 0) {
    return (
      <section className="dashboard-section" aria-labelledby="deadlines-heading">
        <div className="dashboard-section__header">
          <div>
            <p className="page-eyebrow">Deadlines</p>
            <h2 className="dashboard-section__title" id="deadlines-heading">
              Deadline watch
            </h2>
          </div>
        </div>
        <div className="empty-state">
          <h3>Nothing to watch yet.</h3>
          <p>Save a scholarship, or match your profile, and its deadline appears here.</p>
          <Link to="/scholarships" className="sz-btn sz-btn--primary">
            Browse scholarships
          </Link>
        </div>
      </section>
    )
  }

  const actionable = deadlines.filter((entry) => entry.is_actionable)

  return (
    <section className="dashboard-section" aria-labelledby="deadlines-heading">
      <div className="dashboard-section__header">
        <div>
          <p className="page-eyebrow">Deadlines</p>
          <h2 className="dashboard-section__title" id="deadlines-heading">
            Deadline watch
          </h2>
        </div>
        <p className="dashboard-section__universe">
          {actionable.length} with a published date you can act on
        </p>
      </div>

      {/*
        A real table, because this is tabular data a reader will compare across
        rows. The caption states what the ordering means rather than leaving it
        to be inferred.
      */}
      <div className="deadline-table__scroll">
        <table className="sz-table deadline-table">
          <caption className="deadline-table__caption">
            Nearest actionable deadline first, then readiness, then scholarship id.
          </caption>
          <thead>
            <tr>
              <th scope="col">Scholarship</th>
              <th scope="col">Deadline</th>
              <th scope="col">Readiness</th>
              <th scope="col">Fit</th>
              <th scope="col">Status</th>
              <th scope="col">Verification</th>
            </tr>
          </thead>
          <tbody>
            {deadlines.map((entry) => (
              <tr key={entry.scholarship_id} className={entry.is_actionable ? undefined : 'is-not-actionable'}>
                <th scope="row">
                  <Link to={entry.detail_url}>{entry.name}</Link>
                </th>
                <td>{deadlineText(entry)}</td>
                <td>{entry.readiness_label || 'Not evaluated'}</td>
                <td>{typeof entry.fit_score === 'number' ? Math.round(entry.fit_score) : 'Not evaluated'}</td>
                <td>
                  {entry.application_state ? (
                    <span className="sz-badge sz-badge--accent">
                      {entry.application_state.replace(/_/g, ' ')}
                    </span>
                  ) : entry.is_saved ? (
                    <span className="sz-badge">Saved</span>
                  ) : (
                    <span className="deadline-table__none">Not started</span>
                  )}
                </td>
                <td>
                  <span className={entry.verified ? 'deadline-table__verified' : 'deadline-table__unconfirmed'}>
                    {verificationLabel(entry)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}