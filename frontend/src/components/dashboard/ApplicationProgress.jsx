/**
 * Application progress, in the lightweight 1.0 form.
 *
 * This is deliberately not the Application Workspace. It records one of five
 * states per opportunity, shows when it last changed, and offers Continue -
 * which opens the scholarship. There is no document checklist, no deadline
 * reminder, no submission tracking, and nothing that would need a workflow
 * engine behind it.
 *
 * The state list is the server's vocabulary, sent with the response. Adding a
 * sixth state is therefore a server change rather than a frontend edit that
 * could drift from it.
 */

import { Link } from 'react-router-dom'
import { deadlineText } from '../../services/dashboardPresentation'

const STATE_LABELS = {
  saved: 'Saved',
  planning: 'Planning',
  in_progress: 'In progress',
  submitted: 'Submitted',
  withdrawn: 'Withdrawn',
}

const STATE_ORDER = ['saved', 'planning', 'in_progress', 'submitted', 'withdrawn']

export default function ApplicationProgress({ applications, states, onChangeState, onRemove }) {
  const availableStates = states && states.length > 0 ? states : STATE_ORDER

  if (!applications || applications.length === 0) {
    return (
      <section className="dashboard-section" aria-labelledby="applications-heading">
        <div className="dashboard-section__header">
          <div>
            <p className="page-eyebrow">Applications</p>
            <h2 className="dashboard-section__title" id="applications-heading">
              Application progress
            </h2>
          </div>
        </div>
        <div className="empty-state">
          <h3>Start by saving an opportunity.</h3>
          <p>When you save a scholarship you can mark it as planning, in progress or submitted.</p>
          <Link to="/scholarships" className="sz-btn sz-btn--primary">
            Browse scholarships
          </Link>
        </div>
      </section>
    )
  }

  return (
    <section className="dashboard-section" aria-labelledby="applications-heading">
      <div className="dashboard-section__header">
        <div>
          <p className="page-eyebrow">Applications</p>
          <h2 className="dashboard-section__title" id="applications-heading">
            Application progress
          </h2>
        </div>
        <p className="dashboard-section__universe">{applications.length} in progress</p>
      </div>

      <ul className="application-list">
        {applications.map((item) => {
          const scholarship = item.scholarship
          return (
            <li className="application-item" key={scholarship.scholarship_id}>
              <div className="application-item__main">
                <h3 className="application-item__title">
                  <Link to={scholarship.detail_url}>{scholarship.name}</Link>
                </h3>
                <p className="application-item__meta">
                  {scholarship.country} · {scholarship.degree}
                </p>
                <p className="application-item__timing">
                  <span>{deadlineText(item)}</span>
                  <span className="application-item__updated">
                    Updated {new Date(item.updated_at).toLocaleDateString()}
                  </span>
                </p>
              </div>

              <div className="application-item__controls">
                <div className="application-item__field">
                  <label className="application-item__label" htmlFor={`state-${scholarship.scholarship_id}`}>
                    State
                  </label>
                  <select
                    id={`state-${scholarship.scholarship_id}`}
                    className="sz-input application-item__select"
                    value={item.state}
                    onChange={(event) => onChangeState(scholarship.scholarship_id, event.target.value)}
                  >
                    {availableStates.map((state) => (
                      <option key={state} value={state}>
                        {STATE_LABELS[state] || state}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="application-item__actions">
                  <Link
                    to={scholarship.detail_url}
                    className="sz-btn sz-btn--primary application-item__continue"
                  >
                    Continue
                  </Link>
                  <button
                    type="button"
                    className="sz-btn sz-btn--ghost"
                    onClick={() => onRemove(scholarship.scholarship_id)}
                  >
                    Remove
                  </button>
                </div>
              </div>
            </li>
          )
        })}
      </ul>
    </section>
  )
}