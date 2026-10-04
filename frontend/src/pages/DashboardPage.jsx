/**
 * The student dashboard.
 *
 * One request on mount and one after every mutation. The sections are not
 * fetched separately: the server assembles them together so they cannot describe
 * different populations, and a dashboard whose shortlist count disagreed with
 * its shortlist would be worse than no dashboard at all.
 *
 * Load state is an explicit machine rather than a set of ad-hoc booleans,
 * following the pattern the Match page established. That is what stops this page
 * showing an empty state while a request is still in flight, or keeping stale
 * results on screen after a failure - the failure clears the payload, because
 * stale results would answer a profile the student has already changed.
 *
 * This route is deliberately not indexed. It is a personal workspace behind an
 * account, so it carries `noindex, nofollow` like any other private surface.
 */

import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import ApplicationProgress from '../components/dashboard/ApplicationProgress'
import DeadlineWatch from '../components/dashboard/DeadlineWatch'
import MatchList from '../components/dashboard/MatchList'
import OpportunitySummary from '../components/dashboard/OpportunitySummary'
import ProfileSnapshot from '../components/dashboard/ProfileSnapshot'
import {
  NextActions,
  ProfileGaps,
  SavedScholarships,
} from '../components/dashboard/DashboardSections'
import { useReducedMotion } from '../hooks/useReducedMotion'
import {
  DashboardUnauthenticatedError,
  fetchDashboard,
  removeSavedScholarship,
  saveScholarship,
  setApplicationState,
} from '../services/dashboardService'
import './DashboardPage.css'

/** Explicit load states. See the module comment for why this is not a boolean. */
const DASHBOARD_STATUS = Object.freeze({
  CHECKING: 'checking',
  LOADING: 'loading',
  READY: 'ready',
  ERROR: 'error',
  UNAUTHENTICATED: 'unauthenticated',
})

export default function DashboardPage() {
  const [status, setStatus] = useState(DASHBOARD_STATUS.CHECKING)
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const reducedMotion = useReducedMotion()
  const navigate = useNavigate()

  /**
   * Applying a result is separated from fetching it.
   *
   * This split is what lets the mount effect set state inside promise callbacks
   * only - the shape the codebase's other data hooks use - while the retry button
   * and the post-mutation reload reuse exactly the same state transitions. It
   * also means there is one place that decides what a failed load does: it clears
   * the payload, because stale results would answer a profile the student has
   * already changed.
   */
  const applyResult = useCallback((payload) => {
    setData(payload)
    setStatus(DASHBOARD_STATUS.READY)
    setError(null)
  }, [])

  const applyError = useCallback((caught) => {
    setData(null)
    if (caught instanceof DashboardUnauthenticatedError) {
      setStatus(DASHBOARD_STATUS.UNAUTHENTICATED)
      return
    }
    setError(caught)
    setStatus(DASHBOARD_STATUS.ERROR)
  }, [])

  useEffect(() => {
    let cancelled = false
    fetchDashboard().then(
      (payload) => {
        if (!cancelled) applyResult(payload)
      },
      (caught) => {
        if (!cancelled) applyError(caught)
      },
    )
    return () => {
      cancelled = true
    }
  }, [applyResult, applyError])

  /** The only place the view enters LOADING: an explicit reader action. */
  const handleRetry = useCallback(() => {
    setStatus(DASHBOARD_STATUS.LOADING)
    fetchDashboard().then(applyResult, applyError)
  }, [applyResult, applyError])

  useEffect(() => {
    const previous = document.title
    document.title = 'Your dashboard · ScholarZone'

    // A personal workspace has nothing to offer a search index.
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

  /** Run a mutation, then reload so every section reflects it together. */
  const mutate = useCallback(
    async (operation, successNotice) => {
      setNotice(null)
      try {
        await operation()
        setNotice({ type: 'success', message: successNotice })
        // Reloading the whole aggregate rather than patching one section is
        // what stops the saved count and the saved list from ever disagreeing.
        applyResult(await fetchDashboard())
      } catch (caught) {
        if (caught instanceof DashboardUnauthenticatedError) {
          applyError(caught)
          return
        }
        setNotice({ type: 'error', message: caught.message || 'That did not save. Please try again.' })
      }
    },
    [applyResult, applyError],
  )

  const handleSave = useCallback(
    (scholarshipId, shouldSave) => {
      mutate(
        () => (shouldSave ? saveScholarship(scholarshipId) : removeSavedScholarship(scholarshipId)),
        shouldSave ? 'Saved to your shortlist.' : 'Removed from your shortlist.',
      )
    },
    [mutate],
  )

  const handleStateChange = useCallback(
    (scholarshipId, state) => {
      mutate(() => setApplicationState(scholarshipId, state), 'Application state updated.')
    },
    [mutate],
  )

  const handleRemoveApplication = useCallback(
    (scholarshipId) => {
      mutate(() => setApplicationState(scholarshipId, 'withdrawn'), 'Marked as withdrawn.')
    },
    [mutate],
  )

  const savedIds = new Set((data ? data.saved : []).map((item) => String(item.scholarship.scholarship_id)))

  if (status === DASHBOARD_STATUS.CHECKING || status === DASHBOARD_STATUS.LOADING) {
    return (
      <div className="dashboard" aria-busy="true">
        <p className="sz-sr-only" role="status">
          Loading your dashboard
        </p>
        <div className="dashboard__inner">
          <div className="dashboard-skeleton" data-testid="dashboard-loading">
            <span className="dashboard-skeleton__bar" />
            <span className="dashboard-skeleton__bar dashboard-skeleton__bar--short" />
            <span className="dashboard-skeleton__tiles">
              <span />
              <span />
              <span />
              <span />
            </span>
            <span className="dashboard-skeleton__bar dashboard-skeleton__bar--tall" />
          </div>
        </div>
      </div>
    )
  }

  if (status === DASHBOARD_STATUS.UNAUTHENTICATED) {
    return (
      <div className="dashboard">
        <div className="dashboard__inner">
          <div className="empty-state" data-testid="dashboard-signed-out">
            <h1>Your dashboard</h1>
            <p>Sign in to see your matches, deadlines and applications in one place.</p>
            <Link to="/login" className="sz-btn sz-btn--primary">
              Sign in
            </Link>
          </div>
        </div>
      </div>
    )
  }

  if (status === DASHBOARD_STATUS.ERROR) {
    return (
      <div className="dashboard">
        <div className="dashboard__inner">
          <div className="dashboard__error" role="alert" data-testid="dashboard-error">
            <h1>Your dashboard could not load</h1>
            <p>{error ? error.message : 'Something went wrong.'}</p>
            <button type="button" className="sz-btn sz-btn--primary" onClick={handleRetry}>
              Try again
            </button>
          </div>
        </div>
      </div>
    )
  }

  const hasProfile = data.has_profile

  return (
    <div className={`dashboard${reducedMotion ? ' is-reduced-motion' : ''}`}>
      <div className="dashboard__inner">
        <header className="dashboard__header">
          <div>
            <p className="page-eyebrow">ScholarZone</p>
            <h1 className="dashboard__title">Your scholarship command center</h1>
            <p className="dashboard__lede">
              {hasProfile
                ? 'Everything below is measured against your saved profile on '
                : 'Build a profile and ScholarZone can measure this against your '}
              <span className="dashboard__as-of">as of {data.as_of}</span>.
            </p>
          </div>
        </header>

        {/*
          Two elements, deliberately.

          The visually-hidden live region is always in the DOM so a screen
          reader has the region registered before its content changes -
          otherwise the first announcement is frequently missed. Because it is
          hidden it costs no layout, which is the point: as a visible flex item
          it sat at zero height and still consumed a gap above and below, putting
          112px of dead space between the heading and the first section.

          The visible banner is rendered only when there is a message, and is
          hidden from assistive technology so the two are not announced twice.
        */}
        <p className="sz-sr-only" role="status" aria-live="polite">
          {notice ? notice.message : ''}
        </p>
        {notice ? (
          <p className={`dashboard__notice dashboard__notice--${notice.type}`} aria-hidden="true">
            {notice.message}
          </p>
        ) : null}

        {hasProfile ? (
          <>
            <OpportunitySummary summary={data.summary} consistency={data.consistency} />
            <NextActions actions={data.next_actions} />
          </>
        ) : (
          <section className="dashboard-section" aria-labelledby="getting-started-heading">
            <div className="dashboard-section__header">
              <div>
                <p className="page-eyebrow">Getting started</p>
                <h2 className="dashboard-section__title" id="getting-started-heading">
                  Build your scholarship profile
                </h2>
              </div>
            </div>
            <div className="empty-state">
              <h3>Tell ScholarZone about yourself to start matching.</h3>
              <p>
                Your academic profile, target degree and language results are checked against every
                published eligibility rule in the directory.
              </p>
              <Link to="/match" className="sz-btn sz-btn--primary">
                Start matching
              </Link>
            </div>
          </section>
        )}

        <ProfileSnapshot
          profile={data.profile}
          strength={data.profile_strength}
          onEditProfile={() => navigate('/match')}
        />

        {hasProfile ? <MatchList matches={data.matches} truncated={data.matches_truncated} onSave={handleSave} savedIds={savedIds} /> : null}

        <ApplicationProgress
          applications={data.applications}
          states={data.application_states}
          onChangeState={handleStateChange}
          onRemove={handleRemoveApplication}
        />

        <DeadlineWatch deadlines={data.deadlines} />

        <SavedScholarships saved={data.saved} onRemove={(id) => handleSave(id, false)} />

        {hasProfile ? <ProfileGaps gaps={data.gaps} /> : null}
      </div>
    </div>
  )
}