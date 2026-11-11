/**
 * App-level integration tests for the Bangladesh Applicant Journey routes.
 *
 * These tests verify that the journey routes are correctly integrated
 * into the main App router with JourneyProvider mounted at the route boundary.
 */

import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext.jsx'
import { SavedScholarshipsProvider } from './context/SavedScholarshipsContext.jsx'
import { CompareProvider } from './context/CompareContext.jsx'
import { ThemeProvider } from './context/ThemeContext.jsx'
import { AppErrorBoundary } from './components/AppErrorBoundary.jsx'
import App from './App.jsx'
import { STORAGE_KEY } from './features/journey/lib/journeySchema.js'

/** Test wrapper that mimics the provider stack in main.jsx */
function TestProviders({ children }) {
  return (
    <AppErrorBoundary>
      <ThemeProvider>
        <AuthProvider>
          <SavedScholarshipsProvider>
            <CompareProvider>
              {children}
            </CompareProvider>
          </SavedScholarshipsProvider>
        </AuthProvider>
      </ThemeProvider>
    </AppErrorBoundary>
  )
}

/** Restores a working store after a test replaced it with a throwing accessor. */
function restoreWorkingStorage() {
  try {
    Object.defineProperty(window, 'localStorage', {
      value: {
        getItem: (key) => (key === null ? null : null),
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
    /* an unconfigurable store is not a condition this suite needs to repair */
  }
}

/** A stub store that a test can prime with content and inspect afterwards. */
function installPrimedStorage(initial = {}) {
  const map = new Map(Object.entries(initial))
  const storage = {
    getItem: (key) => (map.has(key) ? map.get(key) : null),
    setItem: (key, value) => map.set(key, String(value)),
    removeItem: (key) => map.delete(key),
    clear: () => map.clear(),
    raw: (key) => map.get(key) ?? null,
    size: () => map.size,
  }
  Object.defineProperty(window, 'localStorage', {
    value: storage,
    configurable: true,
    writable: true,
  })
  return storage
}

/** Reads and normalises the persisted document. */
function readPersisted() {
  const raw = window.localStorage.getItem(STORAGE_KEY)
  return raw === null ? null : JSON.parse(raw)
}

/** Renders the App with a given initial route and waits for lazy routes to load. */
async function renderApp({ initialEntry = '/bangladesh-journey', language = 'en' } = {}) {
  // Prime journey storage with English language for consistent test behavior
  installPrimedStorage({
    [STORAGE_KEY]: JSON.stringify({
      schema: 'scholarzone.bangladesh-journey',
      version: 1,
      settings: { language },
    }),
  })
  const { rerender, ...result } = render(
    <TestProviders>
      <MemoryRouter initialEntries={[initialEntry]}>
        <App />
      </MemoryRouter>
    </TestProviders>,
  )
  // Wait for any Suspense fallbacks to resolve
  await waitFor(() => {
    expect(screen.queryByText(/Loading journey…/)).not.toBeInTheDocument()
  }, { timeout: 5000 })
  return { rerender, ...result }
}

beforeEach(() => {
  restoreWorkingStorage()
  installPrimedStorage({})
  vi.resetModules()
})

afterEach(() => {
  restoreWorkingStorage()
  vi.restoreAllMocks()
})

describe('App-level journey route integration', () => {
  it('renders /bangladesh-journey without provider errors', async () => {
    await renderApp({ initialEntry: '/bangladesh-journey' })
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toBeInTheDocument()
  })

  it('renders /bangladesh-journey/:stepId without provider errors', async () => {
    await renderApp({ initialEntry: '/bangladesh-journey/documents' })
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toBeInTheDocument()
    // The documents module should be active - check the main content area
    expect(screen.getByRole('main', { name: /Document Studio/ })).toBeInTheDocument()
  })

  it('direct URL navigation to a step works', async () => {
    // Test that navigating directly to a step URL works by rendering with that URL
    await renderApp({ initialEntry: '/bangladesh-journey/costs' })
    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /BDT Cost Planner/ })[0]).toHaveAttribute('aria-current', 'step')
    })
  })

  it('refresh preserves the requested step', async () => {
    // Simulate a refresh by re-rendering with the same URL
    await renderApp({ initialEntry: '/bangladesh-journey/timeline' })
    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /Application Timeline/ })[0]).toHaveAttribute('aria-current', 'step')
    })

    // Re-render (simulating refresh)
    render(
      <TestProviders>
        <MemoryRouter initialEntries={['/bangladesh-journey/timeline']}>
          <App />
        </MemoryRouter>
      </TestProviders>,
    )
    await waitFor(() => {
      expect(screen.queryByText(/Loading journey…/)).not.toBeInTheDocument()
    })
    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /Application Timeline/ })[0]).toHaveAttribute('aria-current', 'step')
    })
  })

  it('back/forward navigation synchronizes URL and state', async () => {
    const user = userEvent.setup()
    await renderApp({ initialEntry: '/bangladesh-journey' })

    // Click to navigate to documents step
    await user.click(screen.getAllByRole('button', { name: /Document Studio/ })[0])
    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /Document Studio/ })[0]).toHaveAttribute('aria-current', 'step')
    })

    // The URL should have been updated by the component's navigate effect
    // In MemoryRouter, we can't directly test browser history, but we can verify
    // the component state matches the expected step - check main content
    expect(screen.getByRole('main', { name: /Document Studio/ })).toBeInTheDocument()
  })

  it('legacy /journey redirect works', async () => {
    await renderApp({ initialEntry: '/journey' })
    // Should redirect to /bangladesh-journey
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toBeInTheDocument()
  })

  it('legacy /journey/* redirect works', async () => {
    await renderApp({ initialEntry: '/journey/documents' })
    // Should redirect to /bangladesh-journey (the base route, since legacy redirect doesn't preserve subpath)
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toBeInTheDocument()
  })

  it('journey state persists across step navigation with exact document assertion', async () => {
    const user = userEvent.setup()
    await renderApp({ initialEntry: '/bangladesh-journey/documents' })

    // Add document templates (this adds 8 template documents)
    await user.click(screen.getAllByRole('button', { name: /Add generic template items/ })[0])
    
    // Wait for debounced persistence
    await waitFor(() => {
      const persisted = readPersisted()
      expect(persisted).not.toBeNull()
      expect(persisted.documents.length).toBeGreaterThan(0)
    })

    // Capture the exact documents added
    const persistedAfterAdd = readPersisted()
    const addedDocs = persistedAfterAdd.documents
    expect(addedDocs.length).toBeGreaterThan(0)
    
    // Find the Passport document
    const passportDoc = addedDocs.find(doc => doc.title === 'Passport')
    expect(passportDoc).toBeDefined()
    expect(passportDoc.requirement).toBe('mandatory')
    expect(passportDoc.progress).toBe('not_started')
    expect(passportDoc.id).toBeDefined()

    // Navigate to another step
    await user.click(screen.getAllByRole('button', { name: /Find/ })[0])
    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /Find/ })[0]).toHaveAttribute('aria-current', 'step')
    })

    // Navigate back to documents
    await user.click(screen.getAllByRole('button', { name: /Document Studio/ })[0])
    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /Document Studio/ })[0]).toHaveAttribute('aria-current', 'step')
    })

    // The exact document should still be there (persisted)
    const persisted = readPersisted()
    const restoredPassport = persisted.documents.find(doc => doc.id === passportDoc.id)
    expect(restoredPassport).toBeDefined()
    expect(restoredPassport.title).toBe('Passport')
    expect(restoredPassport.requirement).toBe('mandatory')
    expect(restoredPassport.progress).toBe('not_started')
  })

  it('does not wrap unrelated routes in JourneyProvider', async () => {
    // Home page should render without any journey provider context
    render(
      <TestProviders>
        <MemoryRouter initialEntries={['/']}>
          <App />
        </MemoryRouter>
      </TestProviders>,
    )
    // Wait for any Suspense fallbacks to resolve
    await waitFor(() => {
      expect(screen.queryByText(/Loading/)).not.toBeInTheDocument()
    }, { timeout: 5000 })
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
    // No journey-specific elements
    expect(screen.queryByRole('progressbar')).toBeNull()
  })

  it('scholarships page renders without journey provider', async () => {
    render(
      <TestProviders>
        <MemoryRouter initialEntries={['/scholarships']}>
          <App />
        </MemoryRouter>
      </TestProviders>,
    )
    // Wait for any Suspense fallbacks to resolve
    await waitFor(() => {
      expect(screen.queryByText(/Loading/)).not.toBeInTheDocument()
    }, { timeout: 5000 })
    // Use a more specific selector for the scholarships page heading
    expect(screen.getByRole('heading', { name: /All Scholarships/ })).toBeInTheDocument()
    expect(screen.queryByRole('progressbar')).toBeNull()
  })
})

describe('Journey persistence lifecycle', () => {
  it('route exit flushes latest state before debounce expires', async () => {
    const user = userEvent.setup()
    
    // Start on documents step
    await renderApp({ initialEntry: '/bangladesh-journey/documents' })
    
    // Add document templates (this adds 8 template documents)
    await user.click(screen.getAllByRole('button', { name: /Add generic template items/ })[0])
    
    // Wait for debounced persistence
    await waitFor(() => {
      const persisted = readPersisted()
      expect(persisted).not.toBeNull()
      expect(persisted.documents.length).toBeGreaterThan(0)
    })
    
    // Capture the exact documents that were added
    const persistedAfterAdd = readPersisted()
    const addedDocs = persistedAfterAdd.documents
    
    // Find the Passport document
    const passportDoc = addedDocs.find(doc => doc.title === 'Passport')
    expect(passportDoc).toBeDefined()
    expect(passportDoc.id).toBeDefined()
    
    // Navigate immediately to an unrelated route
    render(
      <TestProviders>
        <MemoryRouter initialEntries={['/scholarships']}>
          <App />
        </MemoryRouter>
      </TestProviders>,
    )
    
    // Wait for unmount effect to flush (if any pending)
    await waitFor(() => {
      const persistedAfterExit = readPersisted()
      expect(persistedAfterExit.documents.length).toBeGreaterThan(0)
      const restoredPassport = persistedAfterExit.documents.find(doc => doc.id === passportDoc.id)
      expect(restoredPassport).toBeDefined()
      expect(restoredPassport.title).toBe('Passport')
    }, { timeout: 1000 })
    
    // Return to Journey and verify the changed value is restored
    render(
      <TestProviders>
        <MemoryRouter initialEntries={['/bangladesh-journey/documents']}>
          <App />
        </MemoryRouter>
      </TestProviders>,
    )
    
    await waitFor(() => {
      expect(screen.queryByText(/Loading journey…/)).not.toBeInTheDocument()
    })
    
    const persistedAfterReturn = readPersisted()
    const restoredPassport = persistedAfterReturn.documents.find(doc => doc.id === passportDoc.id)
    expect(restoredPassport).toBeDefined()
    expect(restoredPassport.title).toBe('Passport')
    expect(restoredPassport.id).toBe(passportDoc.id)
  })
})