/**
 * The mentor page.
 *
 * The tests are organised around what a student must never be shown. A
 * rendering test that only asserts the happy path would pass just as happily if
 * the unknown section were deleted, or if a signed-out visitor saw an answer, or
 * if a rate-limit refusal were rendered as a generic failure. So each of those
 * has its own case.
 *
 * Access is asserted from the server's answer, not from the auth context: the
 * page is fed a 401 through the service and must reach its signed-out state,
 * which is the behaviour that actually protects the data.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

import MentorPage from './MentorPage'
import { AuthContext } from '../context/authContext'

vi.mock('../services/mentorService', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    askMentor: vi.fn(),
    fetchMentorOverview: vi.fn(),
  }
})

import { askMentor, fetchMentorOverview } from '../services/mentorService'

const OVERVIEW = {
  supported_intents: ['What to do next', 'Deadlines'],
  intents: ['NEXT_ACTION', 'DEADLINE'],
  redirects: ['What should I do right now?', 'What deadlines should I care about?'],
  max_message_length: 2000,
  assistance_available: false,
}

const ANSWER = {
  request_id: 'abc123',
  as_of: '2026-06-01',
  intent: 'NEXT_ACTION',
  intent_label: 'What to do next',
  supported: true,
  headline: 'Finish the checklist on your Rotterdam application',
  why: 'Your application is the highest priority because 2 counted tasks remain.',
  known: [
    {
      key: 'scholarship-7-identity',
      label: 'Scholarship',
      value: 'Rotterdam Scholarship (record 7)',
      field: 'scholarship.title',
      basis: 'ScholarZone catalogue',
      verification: 'Verified',
      source_url: 'https://provider.example/programme',
      scholarship_id: 7,
    },
    {
      key: 'scholarship-7-deadline',
      label: 'Deadline',
      value: 'No published deadline ScholarZone can count down to.',
      field: 'deadline (evaluate_deadline)',
      basis: 'ScholarZone catalogue',
      verification: 'Verified',
      source_url: null,
      scholarship_id: 7,
    },
  ],
  unknown: ['Rotterdam Scholarship: no fit score has been measured.'],
  next_steps: [
    {
      code: 'continue_application_7',
      title: 'Continue Rotterdam Scholarship',
      detail: 'You marked this one in progress.',
      priority: 20,
      href: '/scholarships/7',
      action_label: 'Continue',
    },
  ],
  caveats: [],
  notes: [],
  general_guidance_only: false,
  provider_mode: 'disabled',
  provider_used: false,
  supported_intents: ['What to do next'],
  redirects: [],
}

/**
 * Render without waiting. Used by the loading cases, which need to observe the
 * page before the overview has resolved.
 */
function renderOnly({ authStatus = 'authenticated' } = {}) {
  const user = { id: 1, email: 'student@example.com', created_at: '2026-01-01T00:00:00Z' }
  return render(
    <MemoryRouter>
      <AuthContext.Provider
        value={{ status: authStatus, user, login: vi.fn(), register: vi.fn(), logout: vi.fn() }}
      >
        <MentorPage />
      </AuthContext.Provider>
    </MemoryRouter>,
  )
}

/**
 * Render and wait for the ready state.
 *
 * The page resolves its vocabulary from the server before it can render anything
 * interactive, so a test that reaches for the composer immediately after mount
 * would be reading a page that is still loading. Awaiting here is what makes the
 * failure messages honest.
 */
async function renderPage(options = {}) {
  const result = renderOnly(options)
  await screen.findByTestId('mentor-composer-input')
  return result
}

beforeEach(() => {
  fetchMentorOverview.mockResolvedValue(OVERVIEW)
  askMentor.mockResolvedValue(ANSWER)
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('loading', () => {
  it('announces that it is loading rather than showing an empty mentor', async () => {
    let resolveOverview
    fetchMentorOverview.mockReturnValue(
      new Promise((resolve) => {
        resolveOverview = resolve
      }),
    )
    renderOnly()

    expect(screen.getByTestId('mentor-loading')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent(/loading your mentor/i)
    // Never an empty state while a request is in flight.
    expect(screen.queryByTestId('mentor-signed-out')).not.toBeInTheDocument()

    resolveOverview(OVERVIEW)
    await waitFor(() => expect(screen.queryByTestId('mentor-loading')).not.toBeInTheDocument())
  })

  it('still offers the composer when the overview cannot be loaded', async () => {
    fetchMentorOverview.mockRejectedValue(new Error('offline'))
    renderOnly()
    await waitFor(() => expect(screen.getByTestId('mentor-composer-input')).toBeInTheDocument())
    // The suggestion list is a convenience; losing it must not break the page.
    expect(screen.queryByTestId('mentor-suggestions-heading')).not.toBeInTheDocument()
  })
})

describe('authentication', () => {
  it('offers a sign-in route to a visitor the server rejects', async () => {
    const { MentorUnauthenticatedError } = await import('../services/mentorService')
    askMentor.mockRejectedValue(new MentorUnauthenticatedError('Sign in to continue.'))

await renderPage()
    await userEvent.type(screen.getByTestId('mentor-composer-input'), 'what next?')
    await userEvent.click(screen.getByTestId('mentor-composer-submit'))

    await waitFor(() => expect(screen.getByTestId('mentor-signed-out')).toBeInTheDocument())
    expect(screen.getByRole('link', { name: /sign in/i })).toHaveAttribute('href', '/login')
  })

  it('shows no answer at all when the session is refused', async () => {
    const { MentorUnauthenticatedError } = await import('../services/mentorService')
    askMentor.mockRejectedValue(new MentorUnauthenticatedError('Sign in to continue.'))

    await renderPage()
    await userEvent.click(screen.getByTestId('mentor-composer-submit'))

    await waitFor(() => expect(screen.queryByTestId('mentor-answer')).not.toBeInTheDocument())
  })
})

describe('asking', () => {
  it('sends the typed question and renders the grounded answer', async () => {
    await renderPage()
    await userEvent.type(screen.getByTestId('mentor-composer-input'), 'What should I do now?')
    await userEvent.click(screen.getByTestId('mentor-composer-submit'))

    await waitFor(() => expect(screen.getByTestId('mentor-answer')).toBeInTheDocument())
    expect(askMentor).toHaveBeenCalledWith('What should I do now?')
    expect(screen.getByRole('heading', { name: ANSWER.headline })).toBeInTheDocument()
  })

  it('asks straight away when a suggested question is chosen', async () => {
    await renderPage()
    await userEvent.click(
      await screen.findByRole('button', { name: OVERVIEW.redirects[0] }),
    )
    await waitFor(() => expect(askMentor).toHaveBeenCalledWith(OVERVIEW.redirects[0]))
    await waitFor(() => expect(screen.getByTestId('mentor-answer')).toBeInTheDocument())
  })

  it('will not send an empty question', async () => {
    await renderPage()
    expect(screen.getByTestId('mentor-composer-submit')).toBeDisabled()
    await userEvent.type(screen.getByTestId('mentor-composer-input'), '   ')
    expect(screen.getByTestId('mentor-composer-submit')).toBeDisabled()
    expect(askMentor).not.toHaveBeenCalled()
  })

  it('shows how much of the message budget is left', async () => {
    await renderPage()
    const input = screen.getByTestId('mentor-composer-input')
    await userEvent.type(input, 'hello')
    expect(screen.getByTestId('mentor-composer-count')).toHaveTextContent(
      `${OVERVIEW.max_message_length - 5} characters left`,
    )
    // The limit is enforced by the field itself, so it cannot be exceeded.
    expect(input).toHaveAttribute('maxlength', String(OVERVIEW.max_message_length))
  })
})

describe('evidence and uncertainty', () => {
  it('shows the evidence with the canonical basis and field behind it', async () => {
    await renderPage()
    await userEvent.type(screen.getByTestId('mentor-composer-input'), 'deadlines?')
    await userEvent.click(screen.getByTestId('mentor-composer-submit'))

const answer = await screen.findByTestId('mentor-answer')
    expect(within(answer).getByText('What ScholarZone verified')).toBeInTheDocument()
    expect(within(answer).getAllByText('ScholarZone catalogue').length).toBeGreaterThan(0)
    expect(within(answer).getByText('deadline (evaluate_deadline)')).toBeInTheDocument()
  })

  it('names what is unknown instead of omitting it', async () => {
    await renderPage()
    await userEvent.type(screen.getByTestId('mentor-composer-input'), 'why this match?')
    await userEvent.click(screen.getByTestId('mentor-composer-submit'))

    const answer = await screen.findByTestId('mentor-answer')
    expect(within(answer).getByText('What is not known')).toBeInTheDocument()
    expect(
      within(answer).getByText('Rotterdam Scholarship: no fit score has been measured.'),
    ).toBeInTheDocument()
  })

  it('never renders an unknown deadline as zero days', async () => {
    askMentor.mockResolvedValue({
      ...ANSWER,
      known: [
        {
          key: 'deadline',
          label: 'Deadline',
          value: 'No published deadline ScholarZone can count down to.',
          field: 'deadline (evaluate_deadline)',
          basis: 'ScholarZone catalogue',
          verification: 'Verified',
          source_url: null,
          scholarship_id: 7,
        },
      ],
    })
    await renderPage()
    await userEvent.type(screen.getByTestId('mentor-composer-input'), 'deadline?')
    await userEvent.click(screen.getByTestId('mentor-composer-submit'))

    const answer = await screen.findByTestId('mentor-answer')
    expect(answer.textContent).not.toMatch(/0 days left/i)
    expect(
      within(answer).getByText('No published deadline ScholarZone can count down to.'),
    ).toBeInTheDocument()
  })

  it('says when nothing at all could be grounded', async () => {
    askMentor.mockResolvedValue({
      ...ANSWER,
      known: [],
      unknown: ['Your profile is empty.'],
      headline: 'There is nothing to advise on yet',
      next_steps: [],
    })
    await renderPage()
    await userEvent.type(screen.getByTestId('mentor-composer-input'), 'advise me')
    await userEvent.click(screen.getByTestId('mentor-composer-submit'))

    expect(await screen.findByTestId('mentor-no-grounded-data')).toBeInTheDocument()
    expect(screen.getByText('What is not known')).toBeInTheDocument()
  })

  it('labels general guidance as general guidance', async () => {
    askMentor.mockResolvedValue({
      ...ANSWER,
      known: [],
      general_guidance_only: true,
      supported: false,
      headline: 'I cannot ground that one',
      why: 'I can only answer from ScholarZone records.',
      redirects: ['What should I do right now?'],
      next_steps: [],
    })
    await renderPage()
    await userEvent.type(screen.getByTestId('mentor-composer-input'), 'tell me a joke')
    await userEvent.click(screen.getByTestId('mentor-composer-submit'))

    const answer = await screen.findByTestId('mentor-answer')
    expect(within(answer).getByText('General guidance')).toBeInTheDocument()
    expect(within(answer).getByText('What I can answer')).toBeInTheDocument()
    expect(within(answer).getByText('What should I do right now?')).toBeInTheDocument()
  })
})

describe('navigation out of an answer', () => {
  it('links to the scholarship an evidence row came from', async () => {
    await renderPage()
    await userEvent.type(screen.getByTestId('mentor-composer-input'), 'why this?')
    await userEvent.click(screen.getByTestId('mentor-composer-submit'))

const answer = await screen.findByTestId('mentor-answer')
    const links = within(answer).getAllByRole('link', { name: /open this scholarship/i })
    expect(links.length).toBeGreaterThan(0)
    for (const link of links) expect(link).toHaveAttribute('href', '/scholarships/7')
  })

  it('links a next action to where it can be done', async () => {
    await renderPage()
    await userEvent.type(screen.getByTestId('mentor-composer-input'), 'what next?')
    await userEvent.click(screen.getByTestId('mentor-composer-submit'))

    const answer = await screen.findByTestId('mentor-answer')
    expect(within(answer).getByRole('link', { name: 'Continue' })).toHaveAttribute(
      'href',
      '/scholarships/7',
    )
  })
})

describe('failures', () => {
  it('offers a retry when the question fails', async () => {
    askMentor.mockRejectedValueOnce(new Error('We could not reach ScholarZone.'))
    await renderPage()
    await userEvent.type(screen.getByTestId('mentor-composer-input'), 'what next?')
    await userEvent.click(screen.getByTestId('mentor-composer-submit'))

    const failure = await screen.findByTestId('mentor-error')
    expect(failure).toHaveAttribute('role', 'alert')
    expect(within(failure).getByRole('button', { name: /try again/i })).toBeInTheDocument()
  })

  it('does not leave a previous answer on screen after a failure', async () => {
    await renderPage()
    await userEvent.type(screen.getByTestId('mentor-composer-input'), 'what next?')
    await userEvent.click(screen.getByTestId('mentor-composer-submit'))
    await screen.findByTestId('mentor-answer')

    askMentor.mockRejectedValueOnce(new Error('We could not reach ScholarZone.'))
    await userEvent.click(screen.getByTestId('mentor-composer-submit'))

    await screen.findByTestId('mentor-error')
    // A stale answer would be answering a question the student did not ask.
    expect(screen.queryByTestId('mentor-answer')).not.toBeInTheDocument()
  })

  it('explains a rate limit using the wait the server asked for', async () => {
    const { MentorRateLimitedError } = await import('../services/mentorService')
    askMentor.mockRejectedValue(
      new MentorRateLimitedError('You have asked many questions in a short time.', 42),
    )
    await renderPage()
    await userEvent.type(screen.getByTestId('mentor-composer-input'), 'what next?')
    await userEvent.click(screen.getByTestId('mentor-composer-submit'))

    const notice = await screen.findByRole('alert')
    expect(notice).toHaveTextContent(/about 42 seconds/i)
  })

  it('retries with the same question when asked to', async () => {
    askMentor.mockRejectedValueOnce(new Error('We could not reach ScholarZone.'))
    await renderPage()
    await userEvent.type(screen.getByTestId('mentor-composer-input'), 'what next?')
    await userEvent.click(screen.getByTestId('mentor-composer-submit'))

    const failure = await screen.findByTestId('mentor-error')
    await userEvent.click(within(failure).getByRole('button', { name: /try again/i }))

    await waitFor(() => expect(screen.getByTestId('mentor-answer')).toBeInTheDocument())
  })
})

describe('privacy', () => {
  it('marks the page noindex and restores the title on unmount', async () => {
    const { unmount } = await renderPage()
    await waitFor(() =>
      expect(document.querySelector('meta[name="robots"]')).toHaveAttribute(
        'content',
        'noindex, nofollow',
      ),
    )
    expect(document.title).toBe('Mentor · ScholarZone')
    unmount()
    expect(document.querySelector('meta[name="robots"]')).toBeNull()
  })

  it('states that questions are not stored', async () => {
    await renderPage()
    expect(screen.getByText(/answered and discarded/i)).toBeInTheDocument()
  })
})

describe('accessibility', () => {
  it('gives the answer a single level-two heading under a level-one page title', async () => {
    await renderPage()
    await userEvent.type(screen.getByTestId('mentor-composer-input'), 'what next?')
    await userEvent.click(screen.getByTestId('mentor-composer-submit'))

    await screen.findByTestId('mentor-answer')
    expect(screen.getByRole('heading', { level: 1, name: 'Mentor' })).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 2, name: ANSWER.headline }),
    ).toBeInTheDocument()
  })

  it('labels every section of the answer for assistive technology', async () => {
    await renderPage()
    await userEvent.type(screen.getByTestId('mentor-composer-input'), 'what next?')
    await userEvent.click(screen.getByTestId('mentor-composer-submit'))

    const answer = await screen.findByTestId('mentor-answer')
    for (const name of ['What is not known', 'What ScholarZone verified', 'What to do next']) {
      expect(within(answer).getByRole('heading', { name })).toBeInTheDocument()
    }
  })

it('gives the composer a real label rather than only a placeholder', async () => {
    await renderPage()
    expect(screen.getByLabelText('Ask what to do next')).toBeInTheDocument()
  })

it('reaches the composer and the submit control by keyboard', async () => {
    await renderPage()
    const input = screen.getByTestId('mentor-composer-input')
    input.focus()
    expect(document.activeElement).toBe(input)

    // Typed first, because the submit control is correctly disabled - and
    // therefore not focusable - while the question is empty.
    await userEvent.type(input, 'deadlines?')
    await userEvent.tab()
    expect(document.activeElement).toBe(screen.getByTestId('mentor-composer-submit'))
  })

  it('never relies on colour alone for a trust state', async () => {
    await renderPage()
    await userEvent.type(screen.getByTestId('mentor-composer-input'), 'why this?')
    await userEvent.click(screen.getByTestId('mentor-composer-submit'))

const answer = await screen.findByTestId('mentor-answer')
    // The trust word is present as text, not only as a colour on the chip.
    expect(within(answer).getAllByText('Verified').length).toBeGreaterThan(0)
  })

  it('moves focus to a newly arrived answer', async () => {
    await renderPage()
    await userEvent.type(screen.getByTestId('mentor-composer-input'), 'what next?')
    await userEvent.click(screen.getByTestId('mentor-composer-submit'))

    await screen.findByTestId('mentor-answer')
    await waitFor(() =>
      expect(document.activeElement).toBe(
        screen.getByTestId('mentor-answer').closest('.mentor-page__answer'),
      ),
    )
  })
})

describe('responsive and motion', () => {
  it('honours a reduced-motion preference', async () => {
    const { setReducedMotion } = await import('../test/setup')
    setReducedMotion(true)
    await renderPage()
    expect(document.querySelector('.mentor-page.is-reduced-motion')).toBeInTheDocument()
    setReducedMotion(false)
  })

  // Breakpoints are not asserted here on purpose. jsdom has no viewport, so a
  // media-query assertion in this environment would pass or fail for reasons
  // that have nothing to do with the stylesheet. Responsive behaviour is verified
  // in the browser instead, by measuring overflow at each real width.
})
  describe('evidence sources', () => {
    // A "Verified" badge is only meaningful if the reader can open the page the
    // figure came from. These cover both halves of that: the link appears when a
    // source exists, and nothing is rendered when it does not.
    async function renderWithKnown(known) {
      askMentor.mockResolvedValue({ ...ANSWER, known })
      await renderPage()
      await userEvent.type(screen.getByTestId('mentor-composer-input'), 'what are my deadlines?')
      await userEvent.click(screen.getByTestId('mentor-composer-submit'))
      await waitFor(() => expect(screen.getByTestId('mentor-answer')).toBeInTheDocument())
    }

    it('links to the official source when the evidence carries one', async () => {
      await renderWithKnown([
        {
          key: 'scholarship-7-deadline',
          label: 'Deadline',
          value: '30 days left.',
          field: 'deadline',
          basis: 'ScholarZone catalogue',
          verification: 'Verified',
          source_url: 'https://provider.example/programme',
          scholarship_id: 7,
        },
      ])
      const link = screen.getAllByTestId('mentor-evidence-source')[0]
      expect(link).toHaveAttribute('href', 'https://provider.example/programme')
      expect(link).toHaveAttribute('target', '_blank')
      expect(link).toHaveAttribute('rel', expect.stringContaining('noreferrer'))
    })

    it('renders no source link when the evidence has none', async () => {
      await renderWithKnown([
        {
          key: 'scholarship-7-deadline',
          label: 'Deadline',
          value: 'No published deadline to count down to.',
          field: 'deadline',
          basis: 'ScholarZone catalogue',
          verification: null,
          source_url: null,
          scholarship_id: 7,
        },
      ])
      expect(screen.queryAllByTestId('mentor-evidence-source')).toHaveLength(0)
    })
  })
