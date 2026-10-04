/**
 * The Application Workspace page and its components.
 *
 * The behaviours worth pinning are the ones where a plausible-looking render
 * would be wrong: showing a progress bar for an application with nothing
 * measured, offering a state transition the server refuses, letting a conflict
 * overwrite the reader's edit, or keeping an action available for a scholarship
 * that has left the public universe.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import ApplicationsPage from './ApplicationsPage'
import ApplicationCard from '../components/applications/ApplicationCard'
import { AuthContext } from '../context/authContext'

vi.mock('../services/applicationsService', async () => {
  const actual = await vi.importActual('../services/applicationsService')
  return {
    ...actual,
    fetchApplications: vi.fn(),
    fetchApplication: vi.fn(),
    updateApplication: vi.fn(),
    setChecklistItem: vi.fn(),
  }
})

import {
  ApplicationConflictError,
  ApplicationUnauthenticatedError,
  fetchApplication,
  fetchApplications,
  setChecklistItem,
  updateApplication,
} from '../services/applicationsService'

const BASE_APPLICATION = {
  id: 1,
  scholarship_id: 42,
  name: 'Rotterdam Scholarship',
  country: 'Netherlands',
  degree: 'Master',
  provider: 'Example University',
  funding: 'Full',
  detail_url: '/scholarships/42',
  official_source_url: 'https://example.org/p',
  state: 'in_progress',
  state_label: 'In progress',
  outcome: 'pending',
  outcome_label: 'No response yet',
  availability: { is_available: true, reason: null },
  deadline_text: 'Applications close 1 August 2026',
  deadline_date: '2026-08-01',
  deadline_precision: 'exact',
  days_remaining: 61,
  is_overdue: false,
  is_actionable: true,
  progress_percent: 50,
  checklist_total: 4,
  checklist_completed: 2,
  next_open_task: 'Prepare your application materials',
  notes: null,
  open_gaps: [],
  checklist: [
    {
      key: 'review_eligibility',
      label: 'Review the eligibility criteria',
      description: 'Read every published requirement.',
      action_target: null,
      source: 'generic',
      source_detail: null,
      position: 0,
      weight: 1,
      completed: true,
      completed_at: '2026-05-10T00:00:00Z',
      is_counted: true,
    },
    {
      key: 'prepare_application_materials',
      label: 'Prepare your application materials',
      description: null,
      action_target: '/scholarships/42',
      source: 'generic',
      source_detail: null,
      position: 1,
      weight: 1,
      completed: false,
      completed_at: null,
      is_counted: true,
    },
  ],
  progress_label: 'Tasks completed',
  fit_score: 88,
  fit_label_display: 'Very strong fit',
  confidence_score: 81,
  readiness_label: 'Ready',
  verification_status: 'active',
  verified: true,
  verification_display: 'Verified',
  created_at: '2026-05-01T00:00:00Z',
  updated_at: '2026-05-20T00:00:00Z',
  version: 3,
}

const LIST_PAYLOAD = {
  applications: [BASE_APPLICATION],
  count: 1,
  universe: 'user_applications',
  states: ['in_progress', 'planning', 'saved', 'submitted', 'withdrawn'],
  outcomes: ['accepted', 'pending', 'rejected', 'waitlisted', 'withdrawn'],
}

function renderPage({ route = '/applications' } = {}) {
  const user = { id: 1, email: 'student@example.com', created_at: '2026-01-01T00:00:00Z' }
  return render(
    <MemoryRouter initialEntries={[route]}>
      <AuthContext.Provider value={{ status: 'authenticated', user, login: vi.fn(), register: vi.fn(), logout: vi.fn() }}>
        <Routes>
          <Route path="/applications" element={<ApplicationsPage />} />
          <Route path="/applications/:applicationId" element={<ApplicationsPage />} />
        </Routes>
      </AuthContext.Provider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.mocked(fetchApplications).mockReset()
  vi.mocked(fetchApplication).mockReset()
  vi.mocked(updateApplication).mockReset()
  vi.mocked(setChecklistItem).mockReset()
  document.title = ''
  document.querySelectorAll('meta[name="robots"]').forEach((node) => node.remove())
})

describe('ApplicationsPage access states', () => {
  it('sends a signed-out reader to sign in rather than showing an empty list', async () => {
    vi.mocked(fetchApplications).mockRejectedValue(new ApplicationUnauthenticatedError('Sign in to continue.'))

    renderPage()

    expect(await screen.findByTestId('applications-signed-out')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login')
  })

  it('shows an honest empty state with a way forward', async () => {
    vi.mocked(fetchApplications).mockResolvedValue({
      ...LIST_PAYLOAD,
      applications: [],
      count: 0,
    })

    renderPage()

    expect(await screen.findByTestId('applications-empty')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Browse scholarships' })).toHaveAttribute(
      'href',
      '/scholarships',
    )
  })

  it('offers a retry when the list cannot load', async () => {
    vi.mocked(fetchApplications).mockRejectedValue(new Error('We could not reach ScholarZone.'))

    renderPage()

    expect(await screen.findByTestId('applications-error')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })

  it('marks itself noindex while mounted', async () => {
    vi.mocked(fetchApplications).mockResolvedValue(LIST_PAYLOAD)

    const { unmount } = renderPage()
    await screen.findByText('Rotterdam Scholarship')

    expect(document.querySelector('meta[name="robots"]')).toHaveAttribute('content', 'noindex, nofollow')

    unmount()
    expect(document.querySelector('meta[name="robots"]')).toBeNull()
  })

  it('renders each application in the list', async () => {
    vi.mocked(fetchApplications).mockResolvedValue(LIST_PAYLOAD)

    renderPage()

    await screen.findByText('Rotterdam Scholarship')
    expect(screen.getByText('1 application, nearest deadline first')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Open workspace' })).toBeInTheDocument()
  })
})

describe('ApplicationCard presentation', () => {
  it('puts the deadline second, before progress', async () => {
    vi.mocked(fetchApplications).mockResolvedValue(LIST_PAYLOAD)
    renderPage()
    await screen.findByText('Rotterdam Scholarship')

    const card = screen.getByRole('heading', { name: 'Rotterdam Scholarship' }).closest('article')
    const text = card.textContent
    expect(text.indexOf('61 days left')).toBeLessThan(text.indexOf('Tasks completed'))
  })

  it('never renders a progress bar for an unmeasured application', () => {
    render(
      <MemoryRouter>
        <ApplicationCard
          application={{ ...BASE_APPLICATION, progress_percent: null, checklist_total: 0, checklist_completed: 0 }}
          onSelect={() => {}}
        />
      </MemoryRouter>,
    )

    expect(screen.getByText('No tracked tasks yet')).toBeInTheDocument()
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
  })

  it('expresses urgency as a word as well as a colour', () => {
    render(
      <MemoryRouter>
        <ApplicationCard application={{ ...BASE_APPLICATION, days_remaining: 5 }} onSelect={() => {}} />
      </MemoryRouter>,
    )

    // Never colour alone.
    expect(screen.getByText('Closing soon')).toBeInTheDocument()
    expect(screen.getByText('5 days left')).toBeInTheDocument()
  })

  it('drops the scholarship link for an unlisted scholarship', () => {
    render(
      <MemoryRouter>
        <ApplicationCard
          application={{
            ...BASE_APPLICATION,
            availability: { is_available: false, reason: 'This scholarship is no longer listed.' },
          }}
          onSelect={() => {}}
        />
      </MemoryRouter>,
    )

    expect(screen.getByText('This scholarship is no longer listed.')).toBeInTheDocument()
    // No link out to a round that cannot be applied to.
    expect(screen.queryByRole('link', { name: 'View scholarship' })).not.toBeInTheDocument()
    // The record itself is still readable.
    expect(screen.getByRole('heading', { name: 'Rotterdam Scholarship' })).toBeInTheDocument()
  })

  it('never labels a record needing confirmation as verified', () => {
    render(
      <MemoryRouter>
        <ApplicationCard
          application={{
            ...BASE_APPLICATION,
            verification_status: 'needs_review',
            verified: false,
            verification_display: 'Confirm with provider',
          }}
          onSelect={() => {}}
        />
      </MemoryRouter>,
    )

    expect(screen.getByText('Confirm with provider')).toBeInTheDocument()
    expect(screen.queryByText('Verified')).not.toBeInTheDocument()
  })
})

describe('ApplicationWorkspace', () => {
  async function openWorkspace() {
    vi.mocked(fetchApplications).mockResolvedValue(LIST_PAYLOAD)
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Open workspace' }))
    return screen.findByRole('heading', { name: 'Rotterdam Scholarship', level: 2 })
  }

  it('addresses the workspace by URL so a refresh lands on it', async () => {
    vi.mocked(fetchApplications).mockResolvedValue(LIST_PAYLOAD)
    vi.mocked(fetchApplication).mockResolvedValue(BASE_APPLICATION)

    renderPage({ route: '/applications/1' })

    // Rendered straight from the address, with no click and no state to lose.
    await screen.findByRole('heading', { name: 'Rotterdam Scholarship', level: 2 })
    expect(screen.queryByTestId('applications-empty')).toBeNull()
  })

  it('renders the checklist with real checkboxes and their provenance', async () => {
    vi.mocked(fetchApplication).mockResolvedValue(BASE_APPLICATION)
    await openWorkspace()

    const checkboxes = screen.getAllByRole('checkbox')
    expect(checkboxes).toHaveLength(2)
    expect(checkboxes[0]).toBeChecked()
    expect(checkboxes[1]).not.toBeChecked()

    // Every task says where it came from, so a generic step is never read as a
    // claim about what this provider requires.
    expect(screen.getAllByText(/General preparation step/)).toHaveLength(2)
  })

  it('sends the version it read with a checklist change', async () => {
    vi.mocked(fetchApplication).mockResolvedValue(BASE_APPLICATION)
    setChecklistItem.mockResolvedValue({
      ...BASE_APPLICATION,
      version: 4,
      progress_percent: 75,
      checklist_completed: 3,
    })
    await openWorkspace()

    await userEvent.click(screen.getAllByRole('checkbox')[1])

    await vi.waitFor(() => expect(setChecklistItem).toHaveBeenCalled())
    // The version is what proves what was read; omitting it is the lost update.
    expect(setChecklistItem).toHaveBeenCalledWith(1, 'prepare_application_materials', {
      completed: true,
      expectedVersion: 3,
    })
  })

  it('moves the checkbox immediately rather than after the round trip', async () => {
    vi.mocked(fetchApplication).mockResolvedValue(BASE_APPLICATION)
    // A write the server has not answered yet. A reader who clicks and sees
    // nothing happen clicks again.
    let release
    setChecklistItem.mockReturnValue(new Promise((settle) => { release = settle }))

    await openWorkspace()
    const box = screen.getAllByRole('checkbox')[1]
    expect(box).not.toBeChecked()

    await userEvent.click(box)

    // Applied optimistically, before the request settles.
    expect(screen.getAllByRole('checkbox')[1]).toBeChecked()

    release({ ...BASE_APPLICATION, version: 4, progress_percent: 75, checklist_completed: 3 })
    await vi.waitFor(() => expect(setChecklistItem).toHaveBeenCalled())
  })

  it('rolls the checkbox back when the write is refused', async () => {
    vi.mocked(fetchApplication).mockResolvedValue(BASE_APPLICATION)
    const { ApplicationApiError } = await import('../services/applicationsService')
    setChecklistItem.mockRejectedValue(new ApplicationApiError('Server refused the change.', 500))
    vi.mocked(fetchApplication)
      .mockResolvedValueOnce(BASE_APPLICATION)
      .mockResolvedValue(BASE_APPLICATION)

    await openWorkspace()
    await userEvent.click(screen.getAllByRole('checkbox')[1])

    expect(await screen.findByText('Server refused the change.')).toBeInTheDocument()
    // The optimistic tick is undone from the server's record, not left lying.
    await vi.waitFor(() => expect(screen.getAllByRole('checkbox')[1]).not.toBeChecked())
  })

  it('offers only the transitions the server allows', async () => {
    vi.mocked(fetchApplication).mockResolvedValue(BASE_APPLICATION)
    await openWorkspace()

    const select = screen.getByLabelText('Move to')
    const values = within(select).getAllByRole('option').map((option) => option.value)
    // Submitted is reachable from in_progress; in_progress is not reachable back
    // from submitted, and the select reflects the server table.
    expect(values).toEqual(['in_progress', 'planning', 'submitted', 'withdrawn'])
  })

  it('hides the outcome control before an application is submitted', async () => {
    vi.mocked(fetchApplication).mockResolvedValue(BASE_APPLICATION)
    await openWorkspace()

    // An outcome the provider never sent is not something ScholarZone may offer.
    expect(screen.queryByLabelText('Outcome')).not.toBeInTheDocument()
  })

  it('offers the outcome control once submitted and refuses to offer a reopen', async () => {
    vi.mocked(fetchApplication).mockResolvedValue({
      ...BASE_APPLICATION,
      state: 'submitted',
      outcome: 'pending',
    })
    await openWorkspace()

    expect(screen.getByLabelText('Outcome')).toBeInTheDocument()
    expect(
      screen.getByText(/cannot be reopened, because the provider already holds it/),
    ).toBeInTheDocument()
    const stateSelect = screen.getByLabelText('Move to')
    expect(within(stateSelect).getAllByRole('option').map((o) => o.value)).toEqual(['submitted', 'withdrawn'])
  })

  it('stops a conflict from overwriting and offers a reload', async () => {
    vi.mocked(fetchApplication).mockResolvedValue(BASE_APPLICATION)
    updateApplication.mockRejectedValue(
      new ApplicationConflictError('This application was changed somewhere else.'),
    )
    await openWorkspace()

    await userEvent.selectOptions(screen.getByLabelText('Move to'), 'submitted')

    const notice = await screen.findByTestId('application-conflict')
    expect(notice).toHaveTextContent('changed somewhere else')
    // Nothing was applied on top of the newer edit.
    expect(screen.queryByText('Moved to submitted.')).toBeNull()
    expect(screen.getByRole('button', { name: 'Reload the latest version' })).toBeInTheDocument()
  })

  it('saves a note with the version and shows it back', async () => {
    vi.mocked(fetchApplication).mockResolvedValue(BASE_APPLICATION)
    updateApplication.mockResolvedValue({
      ...BASE_APPLICATION,
      version: 4,
      notes: 'Panel interview in March; referee is Dr Okafor.',
    })
    await openWorkspace()

    const field = screen.getByLabelText('Your private notes for this application')
    await userEvent.type(field, 'Panel interview in March; referee is Dr Okafor.')
    await userEvent.click(screen.getByRole('button', { name: 'Save note' }))

    await vi.waitFor(() => expect(updateApplication).toHaveBeenCalled())
    expect(updateApplication).toHaveBeenCalledWith(1, {
      expectedVersion: 3,
      notes: 'Panel interview in March; referee is Dr Okafor.',
    })
    expect(await screen.findByText('Note saved.')).toBeInTheDocument()
  })

  it('separates fit from progress explicitly', async () => {
    vi.mocked(fetchApplication).mockResolvedValue(BASE_APPLICATION)
    await openWorkspace()

    expect(screen.getByText(/Fit is how well you match/)).toBeInTheDocument()
    expect(screen.getByText('50% \u00b7 2 of 4 tasks')).toBeInTheDocument()
    expect(
      screen.getByRole('progressbar', { name: 'Application progress' }),
    ).toHaveAttribute('aria-valuenow', '50')
  })

  it('shows no fit panel content when there is no match result', async () => {
    vi.mocked(fetchApplication).mockResolvedValue({
      ...BASE_APPLICATION,
      fit_score: null,
      fit_label_display: null,
      confidence_score: null,
      readiness_label: null,
    })
    await openWorkspace()

    expect(screen.getByText(/No match result for this scholarship yet/)).toBeInTheDocument()
  })

  it('removes the provider link for an unlisted scholarship', async () => {
    vi.mocked(fetchApplication).mockResolvedValue({
      ...BASE_APPLICATION,
      availability: { is_available: false, reason: 'This scholarship is no longer listed.' },
    })
    vi.mocked(fetchApplications).mockResolvedValue(LIST_PAYLOAD)
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Open workspace' }))
    await screen.findByRole('heading', { name: 'Rotterdam Scholarship', level: 2 })

    expect(screen.queryByRole('link', { name: /provider/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'View the scholarship' })).not.toBeInTheDocument()
  })
})