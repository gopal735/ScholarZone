/**
 * /applications — the Application Workspace.
 *
 * One list request on mount and one per selection. The list and the detail come
 * from the same server aggregation, so a card can never describe an application
 * differently from the workspace opened from it.
 *
 * Load state is an explicit machine rather than a set of booleans, following the
 * pattern the Match page and the dashboard established. That is what stops this
 * page showing an empty state while a request is in flight.
 *
 * The route is `noindex`: it is a private workspace behind an account, and there
 * is nothing in it for a search index.
 */

import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import ApplicationCard from '../components/applications/ApplicationCard'
import ApplicationWorkspace from '../components/applications/ApplicationWorkspace'
import {
  ApplicationUnauthenticatedError,
  fetchApplications,
} from '../services/applicationsService'
import './ApplicationsPage.css'

const PAGE_STATUS = Object.freeze({
  LOADING: 'loading',
  READY: 'ready',
  ERROR: 'error',
  UNAUTHENTICATED: 'unauthenticated',
})

export default function ApplicationsPage() {
  const [status, setStatus] = useState(PAGE_STATUS.LOADING)
  const [payload, setPayload] = useState(null)
  const [error, setError] = useState(null)
  // The open application is addressed by the URL, not by component state, so a
  // refresh or a pasted link lands on the same workspace instead of dropping the
  // reader back to the list.
  const { applicationId } = useParams()
  const navigate = useNavigate()

  // Retry only. The mount path sets its own state inside promise callbacks, so
  // this is the single place that enters LOADING synchronously.
  const load = useCallback(async () => {
    setStatus(PAGE_STATUS.LOADING)
    try {
      const data = await fetchApplications()
      setPayload(data)
      setError(null)
      setStatus(PAGE_STATUS.READY)
    } catch (caught) {
      setPayload(null)
      if (caught instanceof ApplicationUnauthenticatedError) {
        setStatus(PAGE_STATUS.UNAUTHENTICATED)
        return
      }
      setError(caught)
      setStatus(PAGE_STATUS.ERROR)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    fetchApplications().then(
      (data) => {
        if (cancelled) return
        setPayload(data)
        setStatus(PAGE_STATUS.READY)
      },
      (caught) => {
        if (cancelled) return
        setPayload(null)
        setStatus(
          caught instanceof ApplicationUnauthenticatedError
            ? PAGE_STATUS.UNAUTHENTICATED
            : PAGE_STATUS.ERROR,
        )
        setError(caught)
      },
    )
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const previous = document.title
    document.title = 'Applications · ScholarZone'
    const robots = document.createElement('meta')
    robots.name = 'robots'
    robots.content = 'noindex, nofollow'
    robots.setAttribute('data-sz-seo', 'true')
    document.head.appendChild(robots)
    return () => {
      document.title = previous
      document.head.removeChild(robots)
    }
  }, [])

  if (status === PAGE_STATUS.LOADING) {
    return (
      <div className="applications-page" aria-busy="true">
        <p className="sz-sr-only" role="status">
          Loading your applications
        </p>
        <div className="applications-page__inner">
          <div className="applications-page__skeleton" data-testid="applications-loading">
            <span />
            <span />
            <span />
          </div>
        </div>
      </div>
    )
  }

  if (status === PAGE_STATUS.UNAUTHENTICATED) {
    return (
      <div className="applications-page">
        <div className="applications-page__inner">
          <div className="empty-state" data-testid="applications-signed-out">
            <h1>Your applications</h1>
            <p>Sign in to track the scholarships you are applying to.</p>
            <Link to="/login" className="sz-btn sz-btn--primary">
              Sign in
            </Link>
          </div>
        </div>
      </div>
    )
  }

  if (status === PAGE_STATUS.ERROR) {
    return (
      <div className="applications-page">
        <div className="applications-page__inner">
          <div className="applications-page__error" role="alert" data-testid="applications-error">
            <h1>Your applications could not load</h1>
            <p>{error ? error.message : 'Something went wrong.'}</p>
            <button type="button" className="sz-btn sz-btn--primary" onClick={load}>
              Try again
            </button>
          </div>
        </div>
      </div>
    )
  }

  const applications = payload.applications

  return (
    <div className="applications-page">
      <div className="applications-page__inner">
        <header className="applications-page__header">
          <div>
            <p className="page-eyebrow">Application workspace</p>
            <h1 className="applications-page__title">
              {applicationId ? 'Your application' : 'Your applications'}
            </h1>
            <p className="applications-page__lede">
              {applicationId
                ? 'Everything you have tracked for this opportunity.'
                : 'Every scholarship you are applying to, with its deadline, your progress and what to do next.'}
            </p>
          </div>
          {!applicationId && applications.length > 0 ? (
            <Link to="/dashboard" className="sz-btn sz-btn--secondary">
              Your dashboard
            </Link>
          ) : null}
        </header>

        {applicationId ? (
          <ApplicationWorkspace
            applicationId={Number(applicationId)}
            onClose={() => navigate('/applications')}
          />
        ) : applications.length === 0 ? (
          <div className="empty-state" data-testid="applications-empty">
            <h2>You have not started an application yet.</h2>
            <p>
              Save a scholarship you are considering, or open one you have matched with, and start
              tracking it here.
            </p>
            <Link to="/scholarships" className="sz-btn sz-btn--primary">
              Browse scholarships
            </Link>
          </div>
        ) : (
          <>
            <p className="applications-page__count">
              {applications.length} application{applications.length === 1 ? '' : 's'}, nearest deadline
              first
            </p>
            <ul className="applications-list">
              {applications.map((application) => (
                <ApplicationCard
                  key={application.id}
                  application={application}
                  onSelect={(selected) => navigate(`/applications/${selected.id}`)}
                />
              ))}
            </ul>
          </>
        )}
      </div>
    </div>
  )
}