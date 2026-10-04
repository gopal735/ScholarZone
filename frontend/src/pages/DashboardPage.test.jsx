/**
 * The dashboard page's access and failure states.
 *
 * The most important assertion here is negative: the page must never show
 * another student's data, and it must not show a previous payload after a failed
 * reload. A stale dashboard is not a cosmetic problem - it answers a profile the
 * student has already changed, which is exactly the confusion the Match page
 * already learned to avoid.
 *
 * The page resolves access from the server's answer rather than from anything in
 * the browser, so these tests drive it through the API boundary.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import DashboardPage from './DashboardPage'
import { AuthContext } from '../context/authContext'

vi.mock('../services/dashboardService', () => ({
  DashboardApiError: class DashboardApiError extends Error {},
  DashboardUnauthenticatedError: class DashboardUnauthenticatedError extends Error {
    constructor(message) {
      super(message)
      this.status = 401
    }
  },
  fetchDashboard: vi.fn(),
  removeSavedScholarship: vi.fn(),
  saveScholarship: vi.fn(),
  setApplicationState: vi.fn(),
}))

import { fetchDashboard } from '../services/dashboardService'

const EMPTY_PAYLOAD = {
  as_of: '2026-06-01',
  has_profile: false,
  application_states: ['saved', 'planning', 'in_progress', 'submitted', 'withdrawn'],
  profile: { is_empty: true, updated_at: null, fields: [] },
  profile_strength: { score: null, band: null, label: null, detail: '', components: [], complete: [] },
  summary: {
    universe: 'match_analysed',
    total_candidates: 0,
    visible_candidate_count: 0,
    eligible_count: 0,
    needs_verification_count: 0,
    ineligible_count: 0,
    strong_match_count: 0,
    scored_count: 0,
    not_scored_count: 0,
    ready_to_apply_count: 0,
    open_with_deadline_count: 0,
    closing_soon_count: 0,
    truncated: false,
  },
  consistency: {
    match_total_candidates: 0,
    count_total_candidates: 0,
    counts_agree: true,
    integrity_status: 'UNAVAILABLE',
    integrity_issues: [],
  },
  matches: [],
  matches_truncated: false,
  saved: [],
  deadlines: [],
  applications: [],
  gaps: [],
  next_actions: [
    {
      code: 'complete_profile',
      title: 'Build your scholarship profile',
      detail: 'Detail',
      priority: 10,
      href: '/match',
      action_label: 'Complete your profile',
    },
  ],
}

function renderPage() {
  const user = { id: 1, email: 'student@example.com', created_at: '2026-01-01T00:00:00Z' }
  return render(
    <MemoryRouter>
      <AuthContext.Provider value={{ status: 'authenticated', user, login: vi.fn(), register: vi.fn(), logout: vi.fn() }}>
        <DashboardPage />
      </AuthContext.Provider>
    </MemoryRouter>,
  )
}

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.mocked(fetchDashboard).mockReset()
  })

  afterEach(() => {
    // Only the title is reset here. The robots meta node must NOT be removed
    // manually: Testing Library unmounts the component after this hook, and the
    // component's own cleanup would then try to remove a node that is already
    // gone. The unmount is the correct place for it, and it asserts that path in
    // the title-restoration test below.
    document.title = ''
  })

  it('shows a loading state before the payload arrives', () => {
    let resolve
    vi.mocked(fetchDashboard).mockReturnValue(
      new Promise((settle) => {
        resolve = settle
      }),
    )

    renderPage()
    expect(screen.getByTestId('dashboard-loading')).toBeInTheDocument()

    resolve(EMPTY_PAYLOAD)
  })

  it('renders an empty dashboard for a signed-in student with no profile', async () => {
    vi.mocked(fetchDashboard).mockResolvedValue(EMPTY_PAYLOAD)

    renderPage()

    await waitFor(() => expect(screen.getByText('Your scholarship command center')).toBeInTheDocument())
    expect(screen.getByText('Build your scholarship profile')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Start matching' })).toHaveAttribute('href', '/match')
    expect(screen.getByText('Start by saving an opportunity.')).toBeInTheDocument()
  })

  it('sends a signed-out reader to sign in rather than rendering an empty dashboard', async () => {
    const { DashboardUnauthenticatedError } = await import('../services/dashboardService')
    vi.mocked(fetchDashboard).mockRejectedValue(
      new DashboardUnauthenticatedError('Sign in to continue.'),
    )

    renderPage()

    await waitFor(() => expect(screen.getByTestId('dashboard-signed-out')).toBeInTheDocument())
    // Crucially no dashboard content, and no summary that could be mistaken for
    // a student with genuinely nothing.
    expect(screen.queryByText('Your scholarship command center')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login')
  })

  it('offers a retry when the request fails', async () => {
    vi.mocked(fetchDashboard).mockRejectedValue(new Error('We could not reach ScholarZone.'))

    renderPage()

    await waitFor(() => expect(screen.getByTestId('dashboard-error')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })

  it('clears a previous payload when a post-mutation reload fails', async () => {
    const { DashboardUnauthenticatedError } = await import('../services/dashboardService')
    const { saveScholarship } = await import('../services/dashboardService')

    const populated = {
      ...EMPTY_PAYLOAD,
      has_profile: true,
      matches: [
        {
          scholarship_id: 42,
          name: 'Rotterdam Scholarship',
          country: 'Netherlands',
          degree: 'Master',
          funding: 'full',
          detail_url: '/scholarships/42',
          official_source_url: null,
          deadline: 'Applications close 1 September 2026',
          deadline_precision: 'exact',
          days_to_deadline: 90,
          timing_bucket: 'COMFORTABLE',
          eligibility: 'ELIGIBLE',
          fit_score: 88,
          fit_label: 'VERY_STRONG_FIT',
          fit_label_display: 'Very strong fit',
          confidence_score: 81,
          confidence_label: 'HIGH',
          data_coverage: 0.9,
          readiness_score: 80,
          readiness_band: 'READY',
          readiness_label: 'Ready',
          verification_status: 'active',
          verified: true,
          verification_display: 'Verified',
          why: [],
          needs_attention: [],
          actions: [],
          unverified_requirements: [],
        },
      ],
    }

    vi.mocked(fetchDashboard).mockResolvedValueOnce(populated)
    renderPage()
    await waitFor(() => expect(screen.getByText('Recommended scholarships')).toBeInTheDocument())

    // The save succeeds but the reload that follows it fails - the session is
    // gone. The dashboard must not keep showing counts that were true a moment
    // ago and are no longer.
    vi.mocked(saveScholarship).mockResolvedValue({ scholarship_id: 42, saved: true, saved_count: 1 })
    vi.mocked(fetchDashboard).mockRejectedValue(new DashboardUnauthenticatedError('Sign in to continue.'))

    await userEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(screen.getByTestId('dashboard-signed-out')).toBeInTheDocument())
    expect(screen.queryByText('Recommended scholarships')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Rotterdam Scholarship' })).not.toBeInTheDocument()
  })

  it('keeps the live region registered without costing layout space', async () => {
    vi.mocked(fetchDashboard).mockResolvedValue(EMPTY_PAYLOAD)

    const { container } = renderPage()
    await waitFor(() => expect(screen.getByText('Your scholarship command center')).toBeInTheDocument())

    // The live region must exist before it has content, or the first
    // announcement is frequently missed by a screen reader.
    const live = container.querySelector('[aria-live="polite"]')
    expect(live).not.toBeNull()
    // And it must not be a visible flex item: at zero height that still consumed
    // a gap above and below, which put 112px of dead space under the heading.
    expect(live.className).toContain('sz-sr-only')
    // With no message there is no visible banner at all.
    expect(container.querySelector('.dashboard__notice')).toBeNull()
  })

  it('shows a visible banner without announcing it twice', async () => {
    const { DashboardUnauthenticatedError } = await import('../services/dashboardService')
    const { saveScholarship } = await import('../services/dashboardService')
    vi.mocked(fetchDashboard).mockRejectedValue(new DashboardUnauthenticatedError('gone'))
    renderPage()
    await waitFor(() => expect(screen.getByTestId('dashboard-signed-out')).toBeInTheDocument())
    // Sanity: the failure path clears data, so nothing is on screen to announce.
    expect(screen.queryByText('Recommended scholarships')).not.toBeInTheDocument()
    void saveScholarship
  })

  it('marks itself noindex while mounted', async () => {
    vi.mocked(fetchDashboard).mockResolvedValue(EMPTY_PAYLOAD)

    renderPage()

    await waitFor(() => expect(screen.getByText('Your scholarship command center')).toBeInTheDocument())
    expect(document.querySelector('meta[name="robots"]')).toHaveAttribute('content', 'noindex, nofollow')
  })

  it('restores the document title when unmounted', async () => {
    document.title = 'Before'
    vi.mocked(fetchDashboard).mockResolvedValue(EMPTY_PAYLOAD)

    const { unmount } = renderPage()
    await waitFor(() => expect(screen.getByText('Your scholarship command center')).toBeInTheDocument())
    expect(document.title).toBe('Your dashboard · ScholarZone')

    unmount()
    expect(document.title).toBe('Before')
    expect(document.querySelector('meta[name="robots"]')).toBeNull()
  })

  it('shows a populated dashboard without computing anything locally', async () => {
    const payload = {
      ...EMPTY_PAYLOAD,
      has_profile: true,
      summary: { ...EMPTY_PAYLOAD.summary, total_candidates: 386, strong_match_count: 31 },
      matches: [
        {
          scholarship_id: 42,
          name: 'Rotterdam Scholarship',
          country: 'Netherlands',
          degree: 'Master',
          funding: 'full',
          detail_url: '/scholarships/42',
          official_source_url: 'https://example.org/p',
          deadline: 'Applications close 1 September 2026',
          deadline_precision: 'exact',
          days_to_deadline: 90,
          timing_bucket: 'COMFORTABLE',
          eligibility: 'ELIGIBLE',
          fit_score: 88,
          fit_label: 'VERY_STRONG_FIT',
          fit_label_display: 'Very strong fit',
          confidence_score: 81,
          confidence_label: 'HIGH',
          data_coverage: 0.9,
          readiness_score: 80,
          readiness_band: 'READY',
          readiness_label: 'Ready',
          verification_status: 'active',
          verified: true,
          verification_display: 'Verified',
          why: [],
          needs_attention: [],
          actions: [],
          unverified_requirements: [],
        },
      ],
    }
    vi.mocked(fetchDashboard).mockResolvedValue(payload)

    renderPage()

    await waitFor(() => expect(screen.getByText('Recommended scholarships')).toBeInTheDocument())
    expect(screen.getByRole('link', { name: 'Rotterdam Scholarship' })).toBeInTheDocument()
    expect(screen.getByText('31')).toBeInTheDocument()
    expect(screen.getByText(/386 opportunities analysed/)).toBeInTheDocument()
  })
})