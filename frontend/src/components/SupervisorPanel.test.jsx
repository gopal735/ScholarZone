/**
 * The supervisor discovery panel.
 *
 * What is pinned here is the honesty of the states, because that is the part a
 * later change is most likely to break quietly. A panel that renders every
 * outcome as "no supervisors found" is wrong in the direction that matters: it
 * turns an access failure and an unsearched record into a finding about the
 * university.
 *
 * Every test drives the component through its real fetch path with `fetch`
 * mocked, so what is under test is the component's rendering of a server
 * response, not a hand-built prop object.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

import { AuthProvider } from '../context/AuthContext.jsx'
import SupervisorPanel from './SupervisorPanel'

/* Renders the panel inside the provider the application always mounts, and
   the provider tree the application actually mounts. The visitor's session is
   decided by what the fetch mock answers for /auth/me, so a test declares it
   there rather than here. */
function renderPanel(props) {
  return render(
    <AuthProvider>
      <SupervisorPanel {...props} />
    </AuthProvider>,
  )
}

function coverageResponse({
  status = 'verified_supervisors',
  count = 1,
  pending = false,
  supervisors = [],
} = {}) {
  return {
    ok: true,
    status: 200,
    json: async () => ({
      scholarship_id: 7,
      coverage: {
        coverage_status: status,
        verified_supervisor_count: count,
        evidence_state: 'complete',
        last_checked_at: '2026-09-01T00:00:00+00:00',
        discovery_pending: pending,
      },
      supervisors,
    }),
  }
}

function professor(overrides = {}) {
  return {
    id: 1,
    name: 'Dr Ada Lovelace',
    title: 'Professor',
    institution: 'Test University',
    department: 'Computer Science',
    research_areas: ['Machine Learning'],
    official_profile_url: 'https://uni1.edu/people/ada-lovelace',
    official_email: null,
    official_email_verified: false,
    lab_url: null,
    relationship_type: 'potential_supervisor',
    availability: [],
    research_alignment: {
      band: 'insufficient_evidence',
      matched_interests: [],
      matched_areas: [],
      explanation: 'No research interests were supplied.',
    },
    evidence_source_url: 'https://uni1.edu/people/faculty',
    evidence_source_type: 'official_department_page',
    evidence_summary: null,
    verified_at: '2026-09-01T00:00:00+00:00',
    last_verified_at: '2026-09-01T00:00:00+00:00',
    sources: [],
    ...overrides,
  }
}

function mockFetch(handler, { signedIn = false } = {}) {
  const spy = vi.fn(async (url, options) => {
    if (String(url).includes('/auth/me')) {
      if (!signedIn) {
        return { ok: false, status: 401, json: async () => ({ detail: 'Authentication required.' }) }
      }
      return {
        ok: true,
        status: 200,
        json: async () => ({ user: { id: 1, email: 'student@example.com', full_name: 'Student' } }),
      }
    }
    return handler(url, options)
  })
  globalThis.fetch = spy
  return spy
}

afterEach(() => {
  vi.restoreAllMocks()
  window.localStorage.clear()
})

describe('SupervisorPanel states', () => {
  it('reports a completed search that found nothing, without claiming none exist', async () => {
    mockFetch(async () =>
      coverageResponse({ status: 'no_verified_supervisor_found', count: 0, supervisors: [] }),
    )

    renderPanel({ scholarshipId: 7 })

    const message = await screen.findByText(/No verified supervisors found yet/i)
    expect(message).toBeTruthy()
    // The refusal to over-claim is the point, and it must survive a rewrite.
    expect(message.textContent).toMatch(/not that no professors exist/i)
  })

  it('distinguishes an unsearched record from a negative result', async () => {
    mockFetch(async () =>
      coverageResponse({ status: 'search_pending', count: 0, pending: true, supervisors: [] }),
    )

    renderPanel({ scholarshipId: 7 })

    expect(await screen.findByText(/has not been completed/i)).toBeTruthy()
    expect(screen.queryByText(/No verified supervisors found yet/i)).toBeNull()
  })

  it('reports a blocked source as a temporary access problem', async () => {
    mockFetch(async () => coverageResponse({ status: 'source_blocked', count: 0, supervisors: [] }))

    renderPanel({ scholarshipId: 7 })

    const message = await screen.findByText(/could not be reached for verification/i)
    expect(message).toBeTruthy()
    expect(message.textContent).toMatch(/not a finding about the university/i)
  })

  it('distinguishes an unreadable javascript-rendered directory from a negative result', async () => {
    // This is the state the real-world pilot produced against three universities.
    // It must not read as "no supervisors found", because nobody established
    // that this university has none.
    mockFetch(async () =>
      coverageResponse({ status: 'source_requires_rendering', count: 0, supervisors: [] }),
    )

    renderPanel({ scholarshipId: 7 })

    const message = await screen.findByText(/only after the page loads in a browser/i)
    expect(message).toBeTruthy()
    expect(message.textContent).toMatch(/not because the university has none/i)
    expect(screen.queryByText(/No verified supervisors found yet/i)).toBeNull()
  })

  it('reports a hidden relationship awaiting official confirmation', async () => {
    mockFetch(async () => coverageResponse({ status: 'needs_verification', count: 0, supervisors: [] }))

    renderPanel({ scholarshipId: 7 })

    expect(await screen.findByText(/only on secondary sources/i)).toBeTruthy()
    expect(screen.queryByText(/No verified supervisors found yet/i)).toBeNull()
  })

  it('shows a verified professor with the evidence behind them', async () => {
    mockFetch(async () =>
      coverageResponse({
        status: 'verified_supervisors',
        count: 1,
        supervisors: [
          professor({
            availability: [
              {
                scope: 'masters_supervision',
                state: 'not_published',
                source_url: 'https://uni1.edu/people/ada-lovelace',
                verified_at: '2026-09-01T00:00:00+00:00',
              },
            ],
          }),
        ],
      }),
    )

    renderPanel({ scholarshipId: 7 })

    expect(await screen.findByText('Dr Ada Lovelace')).toBeTruthy()
    // Scoped to the badge: the panel heading also contains these words, and an
    // unscoped match here would pass whichever of the two rendered.
    expect(
      document.querySelector('.sz-supervisor__relationship')?.textContent,
    ).toBe('Potential supervisor')
    // Absence is stated, never implied by silence.
    expect(screen.getByText(/Not published on the official page/i)).toBeTruthy()
    // No verified address means an instruction, not a blank.
    expect(screen.getByText(/No verified email/i)).toBeTruthy()
  })

  it('never renders a probability or a success rate', async () => {
    mockFetch(async () =>
      coverageResponse({ count: 1, supervisors: [professor()] }),
    )

    const { container } = renderPanel({ scholarshipId: 7 })
    await screen.findByText('Dr Ada Lovelace')

    const text = container.textContent.toLowerCase()
    for (const forbidden of ['%', 'acceptance chance', 'admission chance', 'response rate', 'success rate']) {
      expect(text).not.toContain(forbidden)
    }
  })

  it('surfaces an error state rather than an empty panel', async () => {
    mockFetch(async () => ({ ok: false, status: 500, json: async () => ({ detail: 'boom' }) }))

    renderPanel({ scholarshipId: 7 })

    expect(await screen.findByRole('alert')).toBeTruthy()
    expect(screen.getByText(/unavailable right now/i)).toBeTruthy()
  })

  it('does not quote a backend parse error at the reader', async () => {
    /* Found on the live deploy preview. When the API's host is serving the SPA
       rather than the backend, a request to it answers 200 with the app's own
       index.html, so `response.json()` throws `Unexpected token '<', "<!doctype
       "... is not valid JSON`. That message was rendered into the page verbatim:
       it names a parser, quotes the reader's HTML at them, and says nothing
       about what actually failed - which is one optional lookup, not the
       scholarship they are reading. */

    const parseFailure = Object.assign(new Error('Unexpected token \'<\', "<!doctype "... is not valid JSON'), {
      name: 'SyntaxError',
    })
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})

    mockFetch(async () => {
      throw parseFailure
    })

    renderPanel({ scholarshipId: 7 })

    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toMatch(/unavailable right now/i)

    // The detail this panel is about is on the same page, and a failure here
    // must not read as though it went missing.
    expect(alert.textContent).toMatch(/scholarship details above are not affected/i)
    expect(alert.textContent).not.toMatch(/doctype/i)
    expect(alert.textContent).not.toMatch(/Unexpected token/i)

    // The technical detail is kept for whoever is debugging, not for the reader.
    expect(warn).toHaveBeenCalled()
    warn.mockRestore()
  })

  it('shows a loading state before any response arrives', () => {
    mockFetch(() => new Promise(() => {}))

    renderPanel({ scholarshipId: 7 })

    expect(screen.getByText(/Looking for published faculty information/i)).toBeTruthy()
  })

  it('treats a signed-out visitor as an invitation, not an error', async () => {
    // The public list must render identically whether or not anyone is signed in.
    // Only the outreach tracker treats 401 specially.
    mockFetch(async (url) => {
      if (String(url).includes('/outreach')) {
        return { ok: false, status: 401, json: async () => ({ detail: 'Authentication required.' }) }
      }
      return coverageResponse({ count: 1, supervisors: [professor()] })
    })

    renderPanel({ scholarshipId: 7 })

    expect(await screen.findByText('Dr Ada Lovelace')).toBeTruthy()
    // Signed out: the panel renders the public list unchanged and invites the
    // visitor to sign in, without asking the server for private records.
    // The auth provider gates its children until the session check settles, so
    // this waits rather than asserting on the first render.
    expect(await screen.findByText(/Sign in to prepare an email/i)).toBeTruthy()
  })

  it('does not render a professor whose email is stored but unverified', async () => {
    mockFetch(async () =>
      coverageResponse({
        count: 1,
        supervisors: [professor({ official_email: 'guess@uni1.edu', official_email_verified: false })],
      }),
    )

    renderPanel({ scholarshipId: 7 })
    await screen.findByText('Dr Ada Lovelace')

    expect(screen.queryByText('guess@uni1.edu')).toBeNull()
  })
})
