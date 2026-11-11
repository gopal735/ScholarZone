/**
 * Integration tests for the Bangladesh Applicant Journey via the real App routes.
 *
 * These tests render the actual App route configuration (without lazy loading)
 * inside MemoryRouter to verify provider boundaries, persistence lifecycle,
 * real route-exit flush, browser history navigation, and reset behavior.
 */

import { describe, expect, it, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, act, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route, Outlet, useNavigate } from 'react-router-dom'
import { JourneyProvider } from '../state/JourneyProvider.jsx'
import { JourneyPage } from '../components/JourneyPage.jsx'
import { STORAGE_KEY } from '../lib/journeySchema.js'
import { AuthProvider } from '../../../context/AuthContext.jsx'
import { SavedScholarshipsProvider } from '../../../context/SavedScholarshipsContext.jsx'
import { CompareProvider } from '../../../context/CompareContext.jsx'
import { ThemeProvider } from '../../../context/ThemeContext.jsx'

function restoreWorkingStorage() {
  try {
    Object.defineProperty(window, 'localStorage', {
      value: {
        getItem: () => null,
        setItem: () => {},
        removeItem: () => {},
        clear: () => {},
        key: () => null,
        length: 0,
      },
      configurable: true,
      writable: true,
    })
  } catch {
    /* ignore */
  }
}

function readPersisted() {
  const raw = window.localStorage.getItem(STORAGE_KEY)
  return raw === null ? null : JSON.parse(raw)
}

function installPrimedStorage(initial = {}) {
  const map = new Map(Object.entries(initial))
  const storage = {
    getItem: (key) => (map.has(key) ? map.get(key) : null),
    setItem: (key, value) => map.set(key, String(value)),
    removeItem: (key) => map.delete(key),
    clear: () => map.clear(),
  }
  Object.defineProperty(window, 'localStorage', {
    value: storage,
    configurable: true,
    writable: true,
  })
  return storage
}

/** Global application providers at application boundary, outside JourneyProvider. */
function Providers() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <SavedScholarshipsProvider>
          <CompareProvider>
            <Outlet />
          </CompareProvider>
        </SavedScholarshipsProvider>
      </AuthProvider>
    </ThemeProvider>
  )
}

/** JourneyProvider only around Bangladesh Journey routes (mirrors production). */
function TestJourneyRoutes() {
  return (
    <JourneyProvider>
      <Outlet />
    </JourneyProvider>
  )
}

function HistoryControls() {
  const navigate = useNavigate()
  return (
    <nav aria-label="Test navigation controls">
      <button type="button" onClick={() => navigate(-1)}>History back</button>
      <button type="button" onClick={() => navigate(1)}>History forward</button>
      <button type="button" onClick={() => navigate('/scholarships')}>Go scholarships</button>
      <button type="button" onClick={() => navigate('/dashboard')}>Go dashboard</button>
      <button type="button" onClick={() => navigate('/')}>Go home</button>
      <button type="button" onClick={() => navigate('/bangladesh-journey/documents')}>Go journey documents</button>
      <button type="button" onClick={() => navigate('/bangladesh-journey/costs')}>Go journey costs</button>
    </nav>
  )
}

/** Route hierarchy matches production App.jsx. */
function TestAppRoutes() {
  return (
    <Routes>
      <Route element={<Providers />}>
        <Route path="/" element={<div data-testid="home-page">Home</div>} />
        <Route path="/scholarships" element={<div data-testid="scholarships-page">Scholarships</div>} />
        <Route path="/dashboard" element={<div data-testid="dashboard-page">Dashboard</div>} />
        <Route element={<TestJourneyRoutes />}>
          <Route index path="/bangladesh-journey" element={<JourneyPage />} />
          <Route path="/bangladesh-journey/:stepId" element={<JourneyPage />} />
        </Route>
      </Route>
    </Routes>
  )
}

function renderTestApp({ initialEntries = ['/bangladesh-journey'], resetStorage = true } = {}) {
  if (resetStorage) installPrimedStorage({})
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <HistoryControls />
      <TestAppRoutes />
    </MemoryRouter>,
  )
}

function getCostLabelInput() {
  const inputs = screen.getAllByLabelText(/^(Item|আইটেম)$/i)
  const empty = inputs.find((el) => el.tagName === 'INPUT' && el.value === '')
  return empty ?? inputs[inputs.length - 1]
}

beforeEach(() => {
  restoreWorkingStorage()
  installPrimedStorage({})
})

afterEach(() => {
  restoreWorkingStorage()
})

describe('App integration: Journey routes render without context errors', () => {
  it('renders /bangladesh-journey without throwing', () => {
    expect(() => renderTestApp({ initialEntries: ['/bangladesh-journey'] })).not.toThrow()
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toBeInTheDocument()
  })

  it('renders /bangladesh-journey/:stepId without throwing', () => {
    expect(() => renderTestApp({ initialEntries: ['/bangladesh-journey/documents'] })).not.toThrow()
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toBeInTheDocument()
  })
})

describe('App integration: Correct provider boundaries', () => {
  it('journey routes have provider context while sibling routes do not', () => {
    renderTestApp({ initialEntries: ['/scholarships'] })
    expect(screen.getByTestId('scholarships-page')).toBeInTheDocument()
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
  })

  it('home and dashboard render outside JourneyProvider', () => {
    renderTestApp({ initialEntries: ['/'] })
    expect(screen.getByTestId('home-page')).toBeInTheDocument()
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()

    renderTestApp({ initialEntries: ['/dashboard'] })
    expect(screen.getByTestId('dashboard-page')).toBeInTheDocument()
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
  })
})

describe('App integration: Navigation between journey steps preserves state', () => {
  it('step navigation keeps JourneyProvider state mounted', async () => {
    const user = userEvent.setup()
    renderTestApp({ initialEntries: ['/bangladesh-journey'] })

    await user.click(screen.getAllByRole('button', { name: /বিডিটি খরচ|BDT Cost Planner/i })[0])
    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /বিডিটি খরচ|BDT Cost Planner/i })[0]).toHaveAttribute('aria-current', 'step')
    })
    expect(screen.getByRole('progressbar')).toBeInTheDocument()

    await user.click(screen.getAllByRole('button', { name: /খরচ যোগ|Add cost/i })[0])
    await user.type(getCostLabelInput(), 'Test Cost')

    await user.click(screen.getAllByRole('button', { name: /নথি কর্মশালা|Document Studio/i })[0])
    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /নথি কর্মশালা|Document Studio/i })[0]).toHaveAttribute('aria-current', 'step')
    })
    expect(screen.getByRole('progressbar')).toBeInTheDocument()

    await user.click(screen.getAllByRole('button', { name: /বিডিটি খরচ|BDT Cost Planner/i })[0])
    await waitFor(() => {
      const persisted = readPersisted()
      expect(persisted?.costs?.items).toHaveLength(1)
      expect(persisted?.costs?.items[0].label).toBe('Test Cost')
    })
    expect(screen.getByRole('progressbar')).toBeInTheDocument()
  }, 15000)
})

describe('App integration: Browser back/forward navigation', () => {
  it('navigate(-1) and navigate(1) synchronize URL/step with provider mounted', async () => {
    const user = userEvent.setup()
    renderTestApp({ initialEntries: ['/bangladesh-journey'] })

    await user.click(screen.getAllByRole('button', { name: /নথি কর্মশালা|Document Studio/i })[0])
    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /নথি কর্মশালা|Document Studio/i })[0]).toHaveAttribute('aria-current', 'step')
    })
    expect(screen.getByRole('progressbar')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'History back' }))
    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /খুঁজুন|Find/i })[0]).toHaveAttribute('aria-current', 'step')
    })
    expect(screen.getByRole('progressbar')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'History forward' }))
    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /নথি কর্মশালা|Document Studio/i })[0]).toHaveAttribute('aria-current', 'step')
    })
    expect(screen.getByRole('progressbar')).toBeInTheDocument()
  }, 15000)
})

describe('App integration: Real route-exit test with actual navigation', () => {
  it('navigates away in same router before debounce, flushes on provider unmount, restores exact Passport document', async () => {
    const user = userEvent.setup()
    renderTestApp({ initialEntries: ['/bangladesh-journey/documents'] })

    await user.click(screen.getAllByRole('button', { name: /টেমপ্লেট আইটেম|Add template/i })[0])

    // Keep debounce pending (400ms). Passport must not be persisted yet.
    expect(readPersisted()?.documents?.some((doc) => doc.title === 'Passport')).toBeFalsy()

    await user.click(screen.getByRole('button', { name: 'Go scholarships' }))
    await waitFor(() => {
      expect(screen.getByTestId('scholarships-page')).toBeInTheDocument()
    })
    // Provider unmounted when leaving journey routes.
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()

    // Check immediately without waiting for debounce: unmount flush must have written.
    const persistedAfterExit = readPersisted()
    expect(persistedAfterExit).not.toBeNull()
    expect(persistedAfterExit.documents.length).toBeGreaterThan(0)
    const passportDoc = persistedAfterExit.documents.find((doc) => doc.title === 'Passport')
    expect(passportDoc).toBeDefined()
    expect(typeof passportDoc.id).toBe('string')
    expect(passportDoc.id.length).toBeGreaterThan(0)
    expect(passportDoc.requirement).toBe('mandatory')
    expect(passportDoc.progress).toBe('not_started')

    await user.click(screen.getByRole('button', { name: 'History back' }))
    await waitFor(() => {
      expect(screen.getByRole('progressbar')).toBeInTheDocument()
    })

    const persistedAfterReturn = readPersisted()
    const restoredPassport = persistedAfterReturn.documents.find((doc) => doc.id === passportDoc.id)
    expect(restoredPassport).toBeDefined()
    expect(restoredPassport.title).toBe('Passport')
    expect(restoredPassport.requirement).toBe('mandatory')
    expect(restoredPassport.progress).toBe('not_started')
  }, 15000)
})

describe('App integration: Visibility and pagehide flush', () => {
  it('hidden -> visible -> edit -> pagehide flushes latest state', async () => {
    const user = userEvent.setup()
    renderTestApp({ initialEntries: ['/bangladesh-journey/costs'] })

    await user.click(screen.getAllByRole('button', { name: /খরচ যোগ|Add cost/i })[0])
    await user.type(getCostLabelInput(), 'First Cost')
    await waitFor(() => expect(readPersisted()?.costs?.items).toHaveLength(1), 5000)

    act(() => {
      Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true })
      document.dispatchEvent(new Event('visibilitychange'))
    })
    await waitFor(() => expect(readPersisted()?.costs?.items).toHaveLength(1), 5000)

    act(() => {
      Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })
      document.dispatchEvent(new Event('visibilitychange'))
    })

    await user.click(screen.getAllByRole('button', { name: /খরচ যোগ|Add cost/i })[0])
    await user.type(getCostLabelInput(), 'Second Cost')

    act(() => {
      window.dispatchEvent(new Event('pagehide'))
    })

    await waitFor(() => {
      const persisted = readPersisted()
      expect(persisted?.costs?.items).toHaveLength(2)
      const labels = persisted.costs.items.map((i) => i.label)
      expect(labels).toContain('First Cost')
      expect(labels).toContain('Second Cost')
    }, 5000)
  }, 15000)
})

describe('App integration: Reset does not recreate deleted data', () => {
  it('reset removes journey key and unmount/navigation does not recreate it', async () => {
    const user = userEvent.setup()
    renderTestApp({ initialEntries: ['/bangladesh-journey/documents'] })

    await user.click(screen.getAllByRole('button', { name: /টেমপ্লেট আইটেম|Add template/i })[0])
    await waitFor(() => expect(readPersisted()).not.toBeNull(), 5000)

    await user.click(screen.getByRole('button', { name: /রিসেট|Reset journey/i }))
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: /রিসেট|Reset journey data/i }))

    await waitFor(() => {
      expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull()
    }, 5000)

    await user.click(screen.getByRole('button', { name: 'Go scholarships' }))
    await waitFor(() => expect(screen.getByTestId('scholarships-page')).toBeInTheDocument())

    await waitFor(() => {
      expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull()
    }, 1000)
  }, 15000)
})

describe('App integration: Debounce behavior', () => {
  it('state changes do not trigger synchronous writes; debounce persists later', async () => {
    const user = userEvent.setup()
    renderTestApp({ initialEntries: ['/bangladesh-journey/costs'] })

    await user.click(screen.getAllByRole('button', { name: /খরচ যোগ|Add cost/i })[0])
    await user.type(getCostLabelInput(), 'Test Cost')

    // Debounce is 400ms; no immediate synchronous write on state change.
    expect(readPersisted()?.costs?.items?.length ?? 0).toBe(0)

    await waitFor(() => {
      const persisted = readPersisted()
      expect(persisted?.costs?.items).toHaveLength(1)
      expect(persisted?.costs?.items[0].label).toBe('Test Cost')
    }, { timeout: 5000 })
  }, 15000)
})
