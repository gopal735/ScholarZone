/**
 * Discoverability of the flag-gated Study Abroad Planner.
 *
 * The strategist route is gated on its own feature flag, which created exactly
 * the failure this file guards against: an enabled route nobody could reach.
 * With the flag on, `/strategist` rendered but nothing linked to it - no
 * navigation entry, no homepage call to action - so the feature existed only
 * for someone who already knew the URL.
 *
 * The inverse matters at least as much: with the flag off, a link or a CTA
 * would be a dead end. So every entry point is asserted in both directions.
 *
 * The flag is read once at module load (`flags.js` reads
 * `import.meta.env` into a const), so it is mocked with a getter rather than
 * stubbed per test: `vi.stubEnv` would arrive after the module had already
 * evaluated the constant and would silently test nothing.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const flag = { enabled: false }

vi.mock('./flags.js', () => ({
  get enabled() {
    return flag.enabled
  },
}))

// Imported after the mock is registered so they all see the same flag object.
import Navigation from '../../components/Navigation.jsx'
import HomePage from '../../pages/HomePage.jsx'
import App from '../../App.jsx'
import { CompareProvider } from '../../context/CompareContext.jsx'
import { SavedScholarshipsProvider } from '../../context/SavedScholarshipsContext.jsx'
import { AuthContext } from '../../context/authContext'
import { ThemeProvider } from '../../context/ThemeContext.jsx'

const authValue = {
  status: 'unauthenticated',
  user: null,
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
}

function renderWithShell(ui, initialEntry = '/') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <ThemeProvider>
        <AuthContext.Provider value={authValue}>
          <CompareProvider>
            <SavedScholarshipsProvider>{ui}</SavedScholarshipsProvider>
          </CompareProvider>
        </AuthContext.Provider>
      </ThemeProvider>
    </MemoryRouter>,
  )
}

/** HomePage reads the catalogue and its statistics over the network. */
function stubCatalogue() {
  const snapshot = {
    meta: { sort_orders: { recommended: [] }, excluded: { quarantined: 0, closed: 0, archived: 0 } },
    stats: { total: 3, countries: 2, verified: 3 },
    scholarships: [],
  }
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url) => {
      if (String(url).includes('scholarships-snapshot.json')) {
        return { ok: true, status: 200, json: async () => snapshot }
      }
      return { ok: true, status: 200, json: async () => ({ items: [], pagination: { total: 0 }, scholarships: [] }) }
    }),
  )
}

beforeEach(() => {
  window.localStorage.clear()
  flag.enabled = false
})

/* ── navigation ───────────────────────────────────────────────────────── */

describe('Study Abroad Planner navigation', () => {
  it('is absent from the navigation while the strategist flag is off', () => {
    flag.enabled = false
    renderWithShell(<Navigation />)
    expect(screen.queryByRole('link', { name: /study abroad planner/i })).not.toBeInTheDocument()
  })

  it('appears in the navigation when the flag is on, and points at the route', () => {
    flag.enabled = true
    renderWithShell(<Navigation />)
    const link = screen.getByRole('link', { name: /study abroad planner/i })
    expect(link).toBeInTheDocument()
    expect(link.getAttribute('href')).toBe('/strategist')
  })

  it('names the same route the strategist component tree serves', () => {
    // The link and the route must never disagree: a nav entry for a path with no
    // route is a dead end, and a route with no nav entry is undiscoverable.
    flag.enabled = true
    const appSource = readApp()
    expect(appSource).toContain('path="/strategist"')
    expect(readNavigation()).toContain('to="/strategist"')
  })
})

/* ── homepage call to action ──────────────────────────────────────────── */

describe('homepage Study Abroad Planner call to action', () => {
  it('is not advertised while the flag is off', () => {
    flag.enabled = false
    stubCatalogue()
    renderWithShell(<HomePage />)
    expect(screen.queryByTestId('home-strategist-cta')).not.toBeInTheDocument()
  })

  it('names the comparison it performs when the flag is on', async () => {
    flag.enabled = true
    stubCatalogue()
    renderWithShell(<HomePage />)
    const cta = screen.getByTestId('home-strategist-cta')
    expect(cta).toBeInTheDocument()
    expect(cta.getAttribute('href')).toBe('/strategist')
    // The four axes the planner actually compares, in the copy: a claim of a
    // recommendation would be false, because the planner ranks on sources.
    const text = cta.textContent
    expect(text).toMatch(/cost/i)
    expect(text).toMatch(/funding/i)
    expect(text).toMatch(/career/i)
  })
})

/* ── route gating ─────────────────────────────────────────────────────── */

describe('/strategist route gating', () => {
  it('does not exist when the flag is off', async () => {
    flag.enabled = false
    stubCatalogue()
    renderWithShell(<App />, '/strategist')
    // The application's own not-found surface, not a blank page.
    await waitFor(() => expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument())
    expect(screen.queryByText(/wizard steps/i)).not.toBeInTheDocument()
  })

  it('serves the strategist page when the flag is on', async () => {
    flag.enabled = true
    stubCatalogue()
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url) => {
        const href = String(url)
        if (href.includes('v2/strategist/subjects')) {
          return { ok: true, status: 200, json: async () => ({ subjects: [] }) }
        }
        return { ok: true, status: 200, json: async () => ({ items: [], pagination: { total: 0 }, scholarships: [], stats: { total: 0 } }) }
      }),
    )
    renderWithShell(<App />, '/strategist')
    // The wizard's own step list is the proof the route resolved, rather than
    // the not-found surface.
    await waitFor(
      () => expect(screen.getByLabelText('Wizard steps')).toBeInTheDocument(),
      { timeout: 3000 },
    )
  })
})

/* ── fixture mode, for reviewers ──────────────────────────────────────── */

describe('fixture mode for review without a backend', () => {
  it('reads the fixture from the query string and answers without the network', async () => {
    // ?fixture=1 is the review path: a reviewer must be able to see the
    // planner without the flag-gated backend running. Imported here, not at
    // the top, so the build-time switch can be set under test.
    vi.resetModules()
    window.history.replaceState({}, '', '/strategist?fixture=1')
    const api = await import('./lib/api.js')
    const fetchSpy = vi.fn(async () => ({ ok: false, status: 404, json: async () => ({}) }))
    vi.stubGlobal('fetch', fetchSpy)
    const subjects = await api.fetchSubjects()
    expect(subjects.subjects.length).toBeGreaterThan(0)
    // No request reached the network: the fixture is bundled, not served.
    expect(fetchSpy).not.toHaveBeenCalled()
    vi.unstubAllGlobals()
    window.history.replaceState({}, '', '/')
    vi.resetModules()
  })

  it('uses the documented build-time variable name', () => {
    // The spelling is the contract: a typo here silently disables the
    // build-time switch while leaving the comment claiming it works.
    const source = readApiClient()
    expect(source).toContain('VITE_STRATEGIST_FIXTURE')
    expect(source).not.toContain('VITE_STATEGIST_FIXTURE')
  })
})

// Read from disk rather than the imported module: these assert the source of
// truth that a reviewer would see, and survive the module graph being reset.
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const readApp = () => readFileSync(resolve(process.cwd(), 'src/App.jsx'), 'utf8')
const readNavigation = () => readFileSync(resolve(process.cwd(), 'src/components/Navigation.jsx'), 'utf8')
const readApiClient = () =>
  readFileSync(resolve(process.cwd(), 'src/features/strategist/lib/api.js'), 'utf8')
