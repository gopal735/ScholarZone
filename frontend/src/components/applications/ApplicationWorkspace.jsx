/**
 * The full workspace for one application.
 *
 * Everything on this screen is either the student's own data or a value copied
 * from a canonical engine. Nothing is recalculated here: the deadline count is
 * the matching engine's, fit and readiness are Match 2.0's, and progress is the
 * server's weighted task count.
 *
 * Three behaviours are worth calling out.
 *
 * **Progress and fit are shown as separate numbers.** They answer different
 * questions, and a strong fit with nothing done is a normal state rather than a
 * contradiction.
 *
 * **A conflict stops the edit.** On a 409 nothing is overwritten and the reader
 * is told to reload, because silently applying their change on top of someone
 * else's is how a lost update becomes a wrong one.
 *
 * **An unlisted scholarship loses its actions.** The record and the history stay,
 * and the affordances that would imply a live round - apply, open the provider -
 * disappear rather than leading somewhere that cannot help.
 */

import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  fetchApplication,
  setChecklistItem,
  updateApplication,
} from '../../services/applicationsService'
import {
  availableOutcomes,
  availableTransitions,
  checklistSourceLabel,
  deadlineText,
  deadlineUrgency,
  hasExactDeadline,
  nextActionHint,
  outcomeLabel,
  progressText,
  progressValue,
  stateLabel,
} from '../../services/applicationPresentation'

const MAX_NOTES = 5000

function ConflictNotice({ message, onReload }) {
  return (
    <div className="application-workspace__conflict" role="alert" data-testid="application-conflict">
      <p>{message}</p>
      <button type="button" className="sz-btn sz-btn--secondary" onClick={onReload}>
        Reload the latest version
      </button>
    </div>
  )
}

function Checklist({ application, onToggle, disabled }) {
  if (!application.checklist || application.checklist.length === 0) {
    return (
      <div className="application-workspace__checklist-empty">
        <h3>No tracked tasks</h3>
        <p>
          Nothing is being tracked for this application, so there is no progress to report. That is not
          a score of zero.
        </p>
      </div>
    )
  }

  return (
    <ul className="checklist">
      {application.checklist.map((item) => (
        <li className="checklist__item" key={item.key}>
          {/*
            A real checkbox rather than a styled div: it is keyboard-operable and
            announced as a checkbox without any ARIA being added by hand. The label
            carries the completion state in text as well, so it never depends on
            the tick alone.
          */}
          <label className={`checklist__label${item.completed ? ' is-complete' : ''}`}>
            <input
              type="checkbox"
              className="checklist__checkbox"
              checked={item.completed}
              disabled={disabled}
              onChange={() => onToggle(item.key, !item.completed)}
            />
            <span className="checklist__text">
              <span className="checklist__title">{item.label}</span>
              {item.description ? (
                <span className="checklist__description">{item.description}</span>
              ) : null}
              <span className="checklist__source">
                {checklistSourceLabel(item.source)}
                {item.source_detail ? ` · ${item.source_detail}` : ''}
                {item.is_counted ? '' : ' · not counted towards progress'}
              </span>
            </span>
            {item.completed && item.completed_at ? (
              <span className="checklist__completed-at">
                Done {new Date(item.completed_at).toLocaleDateString()}
              </span>
            ) : null}
          </label>
        </li>
      ))}
    </ul>
  )
}

export default function ApplicationWorkspace({ applicationId, onClose }) {
  const [application, setApplication] = useState(null)
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState(null)
  const [conflict, setConflict] = useState(null)
  const [notice, setNotice] = useState(null)
  const [notes, setNotes] = useState('')
  const [savingNotes, setSavingNotes] = useState(false)

  // Fetch and apply are split, so the mount effect performs no synchronous
  // setState - the component already starts in 'loading', and setting it again
  // from inside the effect would be a cascading render.
  const applyPayload = useCallback((payload) => {
    setApplication(payload)
    setNotes(payload.notes || '')
    setStatus('ready')
    setError(null)
    setConflict(null)
  }, [])

  const applyError = useCallback((caught) => {
    setError(caught)
    setStatus('error')
  }, [])

  const load = useCallback(async () => {
    try {
      applyPayload(await fetchApplication(applicationId))
    } catch (caught) {
      applyError(caught)
    }
  }, [applicationId, applyPayload, applyError])

  /**
   * Re-read the stored record without leaving the current view.
   *
   * Used after a refused write. A full `load` would flip the workspace back to
   * its skeleton, which unmounts the conflict notice and the reload button the
   * reader needs in order to understand what happened and recover.
   */
  const refreshSilently = useCallback(async () => {
    try {
      const latest = await fetchApplication(applicationId)
      setApplication(latest)
      setNotes(latest.notes || '')
      setError(null)
    } catch {
      // Leave what is on screen. It is the reader's work, and replacing it with
      // an error because a recovery fetch failed would destroy it.
    }
  }, [applicationId])

  useEffect(() => {
    let cancelled = false
    fetchApplication(applicationId).then(
      (payload) => {
        if (!cancelled) applyPayload(payload)
      },
      (caught) => {
        if (!cancelled) applyError(caught)
      },
    )
    return () => {
      cancelled = true
    }
  }, [applicationId, applyPayload, applyError])

  const mutate = async (operation, successMessage, { optimistic } = {}) => {
    setNotice(null)
    setConflict(null)

    // A checkbox is a control the reader has already operated. Waiting for a
    // round trip before it moves makes the click look ignored and invites a
    // second one, so the visible change is applied first and rolled back from the
    // server's answer if the write is refused.
    if (optimistic) {
      setApplication(optimistic)
    }

    try {
      const updated = await operation()
      setApplication(updated)
      setNotes(updated.notes || '')
      setNotice({ type: 'success', message: successMessage })
      return true
    } catch (caught) {
      if (caught && caught.status === 409) {
        // Do not overwrite anything. The reader decides what to keep.
        setConflict(caught.message)
        // The optimistic value may now disagree with the stored record, so the
        // authoritative copy is fetched - silently, so the conflict notice and
        // its reload button stay on screen.
        refreshSilently()
      } else {
        setNotice({ type: 'error', message: caught.message || 'That change did not save.' })
        if (optimistic) refreshSilently()
      }
      return false
    }
  }

  const changeState = (state) => {
    mutate(
      () => updateApplication(applicationId, { expectedVersion: application.version, state }),
      `Moved to ${stateLabel(state).toLowerCase()}.`,
    )
  }

  const changeOutcome = (outcome) => {
    mutate(
      () => updateApplication(applicationId, { expectedVersion: application.version, outcome }),
      `Outcome recorded as ${outcomeLabel(outcome).toLowerCase()}.`,
    )
  }

  const toggleItem = (key, completed) => {
    // Progress and the counters are recomputed here from the same weights the
    // server uses, purely so the bar moves with the tick. The server's numbers
    // replace these the moment it answers, so this is one frame of feedback and
    // never becomes a second source of truth.
    let next = null
    if (application) {
      const checklist = application.checklist.map((item) =>
        item.key === key ? { ...item, completed } : item,
      )
      const completedCount = checklist.filter((item) => item.completed && item.weight > 0).length
      const earned = checklist
        .filter((item) => item.completed && item.weight > 0)
        .reduce((sum, item) => sum + item.weight, 0)

      next = {
        ...application,
        checklist,
        checklist_completed: completedCount,
        progress_percent:
          application.checklist_total > 0
            ? Math.max(0, Math.min(100, Math.round((100 * earned) / application.checklist_total)))
            : null,
      }
    }

    mutate(
      () =>
        setChecklistItem(applicationId, key, { completed, expectedVersion: application.version }),
      completed ? 'Task completed.' : 'Task reopened.',
      { optimistic: next },
    )
  }

  const saveNotes = async (event) => {
    event.preventDefault()
    if (notes.length > MAX_NOTES) {
      setNotice({ type: 'error', message: `That note is longer than ${MAX_NOTES} characters.` })
      return
    }
    setSavingNotes(true)
    await mutate(
      () =>
        updateApplication(applicationId, {
          expectedVersion: application.version,
          notes,
        }),
      'Note saved.',
    )
    setSavingNotes(false)
  }

  if (status === 'loading') {
    return (
      <section className="application-workspace" aria-busy="true">
        <p className="sz-sr-only" role="status">
          Loading your application
        </p>
        <div className="application-workspace__skeleton" data-testid="application-loading">
          <span />
          <span />
          <span />
        </div>
      </section>
    )
  }

  if (status === 'error') {
    const unauthenticated = error && error.status === 401
    return (
      <section className="application-workspace">
        <div className="application-workspace__error" role="alert" data-testid="application-error">
          <h2>{unauthenticated ? 'Sign in to see this application' : 'This application could not load'}</h2>
          <p>{error.message}</p>
          {unauthenticated ? (
            <Link to="/login" className="sz-btn sz-btn--primary">
              Sign in
            </Link>
          ) : (
            <button type="button" className="sz-btn sz-btn--primary" onClick={load}>
              Try again
            </button>
          )}
        </div>
      </section>
    )
  }

  const progress = progressValue(application)
  const unlisted = !application.availability.is_available
  const transitions = availableTransitions(application.state)
  const outcomes = availableOutcomes(application.state)

  return (
    <section className="application-workspace" aria-labelledby="workspace-heading">
      <header className="application-workspace__header">
        <div>
          <p className="page-eyebrow">Application workspace</p>
          <h2 className="application-workspace__title" id="workspace-heading">
            {application.name}
          </h2>
          <p className="application-workspace__meta">
            {[application.country, application.degree, application.provider].filter(Boolean).join(' · ')}
          </p>
        </div>
        {onClose ? (
          <button type="button" className="sz-btn sz-btn--secondary" onClick={onClose}>
            Back to all applications
          </button>
        ) : null}
      </header>

      {conflict ? <ConflictNotice message={conflict} onReload={load} /> : null}

      <p
        className={`application-workspace__notice${notice ? ` application-workspace__notice--${notice.type}` : ''}`}
        role="status"
        aria-live="polite"
      >
        {notice ? notice.message : ''}
      </p>

      <div className="application-workspace__grid">
        <div className="application-workspace__main">
          <section className="application-workspace__panel" aria-labelledby="deadline-panel-heading">
            <h3 id="deadline-panel-heading">Deadline</h3>
            <p className={`application-workspace__deadline application-workspace__deadline--${deadlineUrgency(application)}`}>
              {deadlineText(application)}
            </p>
            {application.deadline_text && !hasExactDeadline(application) ? (
              <p className="application-workspace__panel-note">
                Published as “{application.deadline_text}” without a specific day.
              </p>
            ) : null}
            {unlisted ? (
              <p className="application-workspace__panel-note">{application.availability.reason}</p>
            ) : null}
          </section>

          <section className="application-workspace__panel" aria-labelledby="checklist-panel-heading">
            <h3 id="checklist-panel-heading">Your checklist</h3>
            {progress !== null ? (
              <div className="application-workspace__progress">
                <div
                  className="application-workspace__progress-track"
                  role="progressbar"
                  aria-valuenow={progress}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label="Application progress"
                >
                  <span
                    className="application-workspace__progress-fill"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <p className="application-workspace__progress-text">{progressText(application)}</p>
              </div>
            ) : (
              <p className="application-workspace__panel-note">
                Nothing to measure yet, so no progress is shown.
              </p>
            )}
            <Checklist application={application} onToggle={toggleItem} disabled={Boolean(conflict)} />
          </section>

          <section className="application-workspace__panel" aria-labelledby="notes-panel-heading">
            <h3 id="notes-panel-heading">Private notes</h3>
            <p className="application-workspace__panel-note">
              Only you can see these. They are stored as plain text and are never shown anywhere else
              in ScholarZone.
            </p>
            <form onSubmit={saveNotes} className="application-workspace__notes-form">
              <label className="visually-hidden" htmlFor="application-notes">
                Your private notes for this application
              </label>
              <textarea
                id="application-notes"
                className="sz-input application-workspace__notes"
                value={notes}
                maxLength={MAX_NOTES}
                rows={5}
                disabled={savingNotes}
                onChange={(event) => setNotes(event.target.value)}
              />
              <div className="application-workspace__notes-footer">
                <span className="application-workspace__notes-count">
                  {notes.length} / {MAX_NOTES}
                </span>
                <button type="submit" className="sz-btn sz-btn--primary" disabled={savingNotes}>
                  {savingNotes ? 'Saving…' : 'Save note'}
                </button>
              </div>
            </form>
          </section>
        </div>

        <aside className="application-workspace__aside" aria-labelledby="status-panel-heading">
          <section className="application-workspace__panel" aria-labelledby="status-panel-heading">
            <h3 id="status-panel-heading">Status</h3>
            <p className="application-workspace__state">{stateLabel(application.state)}</p>

            {transitions.length > 0 ? (
              <div className="application-workspace__field">
                <label className="application-workspace__label" htmlFor="state-select">
                  Move to
                </label>
                <select
                  id="state-select"
                  className="sz-input application-workspace__select"
                  value={application.state}
                  disabled={Boolean(conflict)}
                  onChange={(event) => changeState(event.target.value)}
                >
                  <option value={application.state}>{stateLabel(application.state)}</option>
                  {transitions.map((state) => (
                    <option key={state} value={state}>
                      {stateLabel(state)}
                    </option>
                  ))}
                </select>
              </div>
            ) : null}

            {/*
              Shown whenever the current state cannot be reopened, not only when
              it has no moves at all. A submitted application still has one legal
              move - withdraw - so keying this on "no transitions" would hide the
              explanation exactly where a student most needs to understand why the
              application they submitted cannot be put back in progress.
            */}
            {application.state === 'submitted' ? (
              <p className="application-workspace__panel-note">
                A submitted application cannot be reopened, because the provider already holds it.
              </p>
            ) : null}
            {application.state === 'withdrawn' ? (
              <p className="application-workspace__panel-note">
                You withdrew this. It can be reopened while the round is still open.
              </p>
            ) : null}

            {outcomes.length > 0 ? (
              <div className="application-workspace__field">
                <label className="application-workspace__label" htmlFor="outcome-select">
                  Outcome
                </label>
                <select
                  id="outcome-select"
                  className="sz-input application-workspace__select"
                  value={application.outcome}
                  disabled={Boolean(conflict)}
                  onChange={(event) => changeOutcome(event.target.value)}
                >
                  {outcomes.map((outcome) => (
                    <option key={outcome} value={outcome}>
                      {outcomeLabel(outcome)}
                    </option>
                  ))}
                </select>
              </div>
            ) : null}
          </section>

          <section className="application-workspace__panel" aria-labelledby="fit-panel-heading">
            <h3 id="fit-panel-heading">How this compares</h3>
            {typeof application.fit_score === 'number' ? (
              <dl className="application-workspace__facts">
                <div className="application-workspace__fact">
                  <dt>Match fit</dt>
                  <dd>
                    {Math.round(application.fit_score)}
                    {application.fit_label_display ? ` · ${application.fit_label_display}` : ''}
                  </dd>
                </div>
                <div className="application-workspace__fact">
                  <dt>Record confidence</dt>
                  <dd>{Math.round(application.confidence_score)}</dd>
                </div>
                {application.readiness_label ? (
                  <div className="application-workspace__fact">
                    <dt>Readiness</dt>
                    <dd>{application.readiness_label}</dd>
                  </div>
                ) : null}
              </dl>
            ) : (
              <p className="application-workspace__panel-note">
                No match result for this scholarship yet. Fit and readiness come from your profile,
                so complete it to see them here.
              </p>
            )}
            <p className="application-workspace__panel-note">
              Fit is how well you match. Progress is how far you have got. They are not the same
              number.
            </p>
          </section>

          <section className="application-workspace__panel" aria-labelledby="next-panel-heading">
            <h3 id="next-panel-heading">Next</h3>
            <p className="application-workspace__next">{nextActionHint(application)}</p>
            {!unlisted && application.official_source_url ? (
              <a
                className="application-workspace__source"
                href={application.official_source_url}
                target="_blank"
                rel="noreferrer noopener"
              >
                Open the provider&rsquo;s page
              </a>
            ) : null}
            {!unlisted ? (
              <Link to={application.detail_url} className="application-workspace__source">
                View the scholarship
              </Link>
            ) : null}
          </section>
        </aside>
      </div>
    </section>
  )
}