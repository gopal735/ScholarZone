/**
 * Lifecycle tests for JourneyProvider.
 *
 * These tests verify the provider's persistence lifecycle: hydration, debounced writes,
 * unmount flush, visibility/pagehide flush, cross-tab sync, reset suppression,
 * and import/export round-trips. They use the real router and provider hierarchy
 * to exercise the same boundaries as production.
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

function clickCostsStepper(user) {
  const costButtons = screen.getAllByRole('button', { name: /BDT Cost Planner|বিডিটি খরচ/i })
  const target = costButtons[0]
  return user.click(target)
}

async function waitForCostsModule() {
  await waitFor(() => {
    expect(screen.getByRole('progressbar')).toBeInTheDocument()
  })
  await waitFor(() => {
    const costButtons = screen.getAllByRole('button', { name: /BDT Cost Planner|বিডিটি খরচ/i })
    expect(costButtons[0]).toHaveAttribute('aria-current', 'step')
  })
  await waitFor(() => {
    const addCostButtons = screen.getAllByRole('button', { name: /Add cost|খরচ যোগ/i })
    expect(addCostButtons.length).toBeGreaterThan(0)
  })
}

beforeEach(() => {
  restoreWorkingStorage()
  installPrimedStorage({})
})

afterEach(() => {
  restoreWorkingStorage()
})

describe('JourneyProvider lifecycle: hydration and initial render', () => {
  it('hydrates from storage on mount and renders first step', () => {
    const primed = {
      schema: 'scholarzone.bangladesh-journey',
      version: 1,
      settings: { language: 'en' },
      shortlist: [{ id: 's1', name: 'Test Scholarship', country: 'UK', degree: 'CS', trust: 'official' }],
    }
    installPrimedStorage({ [STORAGE_KEY]: JSON.stringify(primed) })

    renderTestApp({ initialEntries: ['/bangladesh-journey'], resetStorage: false })

    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toBeInTheDocument()
    expect(screen.getByText('Test Scholarship')).toBeInTheDocument()
  })

  it('starts with empty state when storage is empty', () => {
    renderTestApp({ initialEntries: ['/bangladesh-journey'] })

    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '0')
    expect(screen.getByText(/No shortlisted opportunities yet|এখনও কোনো সুযোগ শর্টলিস্টে নেই/)).toBeInTheDocument()
  })
})

describe('JourneyProvider lifecycle: debounced persistence', () => {
  it('does not write synchronously on state change; debounce persists later', async () => {
    const user = userEvent.setup()
    renderTestApp({ initialEntries: ['/bangladesh-journey/costs'] })

    await clickCostsStepper(user)
    await waitForCostsModule()

    await user.click(screen.getAllByRole('button', { name: /Add cost|খরচ যোগ/i })[0])
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

describe('JourneyProvider lifecycle: step navigation preserves provider', () => {
  it('keeps JourneyProvider mounted and state intact when navigating between steps', async () => {
    const user = userEvent.setup()
    renderTestApp({ initialEntries: ['/bangladesh-journey'] })

    // Go to costs and add a cost
    await clickCostsStepper(user)
    await waitForCostsModule()

    await user.click(screen.getAllByRole('button', { name: /Add cost|খরচ যোগ/i })[0])
    await user.type(getCostLabelInput(), 'Nav Cost')

    // Navigate to documents
    await user.click(screen.getAllByRole('button', { name: /Document Studio|নথি কর্মশালা/i })[0])
    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /Document Studio|নথি কর্মশালা/i })[0]).toHaveAttribute('aria-current', 'step')
    })

    // Navigate back to costs - provider should still be mounted with state
    await clickCostsStepper(user)
    await waitForCostsModule()

    await waitFor(() => {
      const persisted = readPersisted()
      expect(persisted?.costs?.items).toHaveLength(1)
      expect(persisted?.costs?.items[0].label).toBe('Nav Cost')
    })
    expect(screen.getByRole('progressbar')).toBeInTheDocument()
  }, 15000)
})

describe('JourneyProvider lifecycle: browser history navigation', () => {
  it('synchronizes URL/step with provider mounted on history back/forward', async () => {
    const user = userEvent.setup()
    renderTestApp({ initialEntries: ['/bangladesh-journey'] })

    await user.click(screen.getAllByRole('button', { name: /Document Studio|নথি কর্মশালা/i })[0])
    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /Document Studio|নথি কর্মশালা/i })[0]).toHaveAttribute('aria-current', 'step')
    })
    expect(screen.getByRole('progressbar')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'History back' }))
    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /Find|খুঁজুন/i })[0]).toHaveAttribute('aria-current', 'step')
    })
    expect(screen.getByRole('progressbar')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'History forward' }))
    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /Document Studio|নথি কর্মশালা/i })[0]).toHaveAttribute('aria-current', 'step')
    })
    expect(screen.getByRole('progressbar')).toBeInTheDocument()
  }, 15000)
})

describe('JourneyProvider lifecycle: route exit flush', () => {
  it('flushes pending writes synchronously when leaving journey routes', async () => {
    const user = userEvent.setup()
    renderTestApp({ initialEntries: ['/bangladesh-journey/documents'] })

    await user.click(screen.getAllByRole('button', { name: /Add template|টেমপ্লেট আইটেম/i })[0])

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

describe('JourneyProvider lifecycle: visibility change flush', () => {
  it('flushes latest state when document becomes hidden', async () => {
    const user = userEvent.setup()
    renderTestApp({ initialEntries: ['/bangladesh-journey/costs'] })

    await clickCostsStepper(user)
    await waitForCostsModule()

    await user.click(screen.getAllByRole('button', { name: /Add cost|খরচ যোগ/i })[0])
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

    await user.click(screen.getAllByRole('button', { name: /Add cost|খরচ যোগ/i })[0])
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

describe('JourneyProvider lifecycle: pagehide flush', () => {
  it('flushes pending writes on pagehide event', async () => {
    const user = userEvent.setup()
    renderTestApp({ initialEntries: ['/bangladesh-journey/costs'] })

    await clickCostsStepper(user)
    await waitForCostsModule()

    await user.click(screen.getAllByRole('button', { name: /Add cost|খরচ যোগ/i })[0])
    await user.type(getCostLabelInput(), 'Pagehide Cost')

    // Debounce pending
    expect(readPersisted()?.costs?.items?.length ?? 0).toBe(0)

    act(() => {
      window.dispatchEvent(new Event('pagehide'))
    })

    await waitFor(() => {
      const persisted = readPersisted()
      expect(persisted?.costs?.items).toHaveLength(1)
      expect(persisted?.costs?.items[0].label).toBe('Pagehide Cost')
    }, 5000)
  }, 15000)
})

describe('JourneyProvider lifecycle: beforeunload flush', () => {
  it('flushes pending writes on beforeunload event', async () => {
    const user = userEvent.setup()
    renderTestApp({ initialEntries: ['/bangladesh-journey/costs'] })

    await clickCostsStepper(user)
    await waitForCostsModule()

    await user.click(screen.getAllByRole('button', { name: /Add cost|খরচ যোগ/i })[0])
    await user.type(getCostLabelInput(), 'Beforeunload Cost')

    // Debounce pending
    expect(readPersisted()?.costs?.items?.length ?? 0).toBe(0)

    act(() => {
      window.dispatchEvent(new Event('beforeunload'))
    })

    await waitFor(() => {
      const persisted = readPersisted()
      expect(persisted?.costs?.items).toHaveLength(1)
      expect(persisted?.costs?.items[0].label).toBe('Beforeunload Cost')
    }, 5000)
  }, 15000)
})

describe('JourneyProvider lifecycle: cross-tab storage sync', () => {
  it('applies newer state from another tab via storage event', async () => {
    // Start directly on costs route to avoid navigation issues
    renderTestApp({ initialEntries: ['/bangladesh-journey/costs'] })

    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /BDT Cost Planner|বিডিটি খরচ/i })[0]).toHaveAttribute('aria-current', 'step')
    })
    await waitFor(() => {
      const addCostButtons = screen.getAllByRole('button', { name: /Add cost|খরচ যোগ/i })
      expect(addCostButtons.length).toBeGreaterThan(0)
    })

    // Verify we're on the costs step before firing storage event
    expect(screen.getAllByRole('button', { name: /BDT Cost Planner|বিডিটি খরচ/i })[0]).toHaveAttribute('aria-current', 'step')

    // Simulate another tab writing newer state
    const newerState = {
      schema: 'scholarzone.bangladesh-journey',
      version: 1,
      settings: { language: 'en' },
      costs: {
        items: [
          { id: 'c1', label: 'Synced Cost', category: 'tuition', amount: '1000', currency: 'BDT', sourceType: 'user-entered', sourceLabel: 'Tab2', sourceDate: '2024-01-15', note: '' },
        ],
        rate: { bdtPerUnit: '1', effectiveDate: '', label: '' },
      },
      exportedAt: new Date(Date.now() + 1000).toISOString(),
    }

    act(() => {
      window.dispatchEvent(new StorageEvent('storage', {
        key: STORAGE_KEY,
        newValue: JSON.stringify(newerState),
        oldValue: window.localStorage.getItem(STORAGE_KEY),
      }))
    })

    // Wait for the state to be applied and the module to re-render
    // The cost label is in an input field's value, not as text content
    await waitFor(() => {
      const labelInputs = screen.getAllByLabelText(/^(Item|আইটেম)$/i)
      const syncedInput = labelInputs.find((input) => input.value === 'Synced Cost')
      expect(syncedInput).toBeInTheDocument()
    }, 5000)
  }, 15000)
})

describe('JourneyProvider lifecycle: reset suppresses persist', () => {
  it('removes journey key and prevents subsequent flushes from recreating it', async () => {
    const user = userEvent.setup()
    renderTestApp({ initialEntries: ['/bangladesh-journey/documents'] })

    await user.click(screen.getAllByRole('button', { name: /Add template|টেমপ্লেট আইটেম/i })[0])
    await waitFor(() => expect(readPersisted()).not.toBeNull(), 5000)

    await user.click(screen.getByRole('button', { name: /Reset journey|রিসেট/i }))
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: /Reset journey data|রিসেট/i }))

    await waitFor(() => {
      expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull()
    }, 5000)

    // Navigate away and back - key must not be recreated
    await user.click(screen.getByRole('button', { name: 'Go scholarships' }))
    await waitFor(() => expect(screen.getByTestId('scholarships-page')).toBeInTheDocument())

    await waitFor(() => {
      expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull()
    }, 1000)

    await user.click(screen.getByRole('button', { name: 'History back' }))
    await waitFor(() => expect(screen.getByRole('progressbar')).toBeInTheDocument())

    await waitFor(() => {
      expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull()
    }, 1000)
  }, 15000)
})

describe('JourneyProvider lifecycle: reset then navigate to costs module', () => {
  it('allows adding costs after reset by navigating via stepper', async () => {
    const user = userEvent.setup()
    renderTestApp({ initialEntries: ['/bangladesh-journey/costs'] })

    await clickCostsStepper(user)
    await waitForCostsModule()

    // Add a cost before reset
    await user.click(screen.getAllByRole('button', { name: /Add cost|খরচ যোগ/i })[0])
    await user.type(getCostLabelInput(), 'Pre-reset Cost')
    await waitFor(() => expect(readPersisted()?.costs?.items).toHaveLength(1), 5000)

    // Reset
    await user.click(screen.getByRole('button', { name: /Reset journey|রিসেট/i }))
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: /Reset journey data|রিসেট/i }))

    await waitFor(() => {
      expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull()
    }, 5000)

    // After reset, we're still on costs module but state is cleared
    // Need to navigate away and back via stepper to re-render module content
    await user.click(screen.getAllByRole('button', { name: /Document Studio|নথি কর্মশালা/i })[0])
    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /Document Studio|নথি কর্মশালা/i })[0]).toHaveAttribute('aria-current', 'step')
    })

    // Navigate back to costs via stepper click
    await clickCostsStepper(user)
    await waitForCostsModule()

    // Now add a new cost - the 'Add cost' button should be available
    await user.click(screen.getAllByRole('button', { name: /Add cost|খরচ যোগ/i })[0])
    await user.type(getCostLabelInput(), 'Post-reset Cost')
    await waitFor(() => {
      const persisted = readPersisted()
      expect(persisted?.costs?.items).toHaveLength(1)
      expect(persisted?.costs?.items[0].label).toBe('Post-reset Cost')
    }, 5000)
  }, 15000)
})

describe('JourneyProvider lifecycle: replace document (import)', () => {
  it('replaces state via import and persists new document', async () => {
    const user = userEvent.setup()
    renderTestApp({ initialEntries: ['/bangladesh-journey'] })

    const importDoc = {
      schema: 'scholarzone.bangladesh-journey',
      version: 1,
      settings: { language: 'en' },
      shortlist: [{ id: 'imp1', name: 'Imported Scholarship', country: 'CA', degree: 'Eng', trust: 'official' }],
      costs: { items: [], rate: { bdtPerUnit: '1', effectiveDate: '', label: '' } },
    }

    const file = new File([JSON.stringify(importDoc)], 'import.json', { type: 'application/json' })
    // The aria-label uses t('common.import') which is "JSON ইম্পোর্ট" in Bangla
    await user.upload(screen.getByLabelText(/Import JSON|JSON ইম্পোর্ট/), file)

    // Confirm the import dialog - button text is "আমার বর্তমান অগ্রগতি প্রতিস্থাপিত করুন" in Bangla
    await user.click(screen.getByRole('button', { name: /আমার বর্তমান অগ্রগতি প্রতিস্থাপিত করুন|Replace my current progress|import.confirm/i }))

    // Wait for dialog to close and state to update
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).toBeNull()
    }, 5000)

    await waitFor(() => {
      expect(screen.getByText('Imported Scholarship')).toBeInTheDocument()
    }, 5000)

    // Wait for debounced persist to complete
    await waitFor(() => {
      const persisted = readPersisted()
      expect(persisted?.shortlist).toHaveLength(1)
      expect(persisted?.shortlist[0].name).toBe('Imported Scholarship')
    }, 5000)
  }, 15000)
})

describe('JourneyProvider lifecycle: language persistence', () => {
  it('persists language selection and restores on reload', async () => {
    const user = userEvent.setup()
    renderTestApp({ initialEntries: ['/bangladesh-journey'] })

    // The radio label is "শুধু বাংলা" (Bangla only) in Bangla mode
    await user.click(screen.getByRole('radio', { name: /Bangla only|শুধু বাংলা/ }))
    await waitFor(() => {
      expect(readPersisted()?.settings?.language).toBe('bn')
    })

    // Simulate reload by re-rendering with same storage
    const persisted = readPersisted()
    installPrimedStorage({ [STORAGE_KEY]: JSON.stringify(persisted) })

    renderTestApp({ initialEntries: ['/bangladesh-journey'], resetStorage: false })

    expect(screen.getAllByText('খুঁজুন ও বিশ্লেষণ করুন').length).toBeGreaterThan(0)
  }, 15000)
})

describe('JourneyProvider lifecycle: storage unavailable handling', () => {
  // This test must run without the global beforeEach that installs working storage
  beforeEach(() => {
    restoreWorkingStorage()
  })

  afterEach(() => {
    restoreWorkingStorage()
    installPrimedStorage({})
  })

  it('keeps page usable and shows notice when storage is blocked', () => {
    // Define throwing storage before render using a Proxy (more reliable than Object.defineProperty)
    const throwingStorage = new Proxy({}, {
      get() {
        throw new Error('blocked')
      },
      set() {
        throw new Error('blocked')
      },
      has() {
        throw new Error('blocked')
      },
      deleteProperty() {
        throw new Error('blocked')
      },
    })
    
    // Replace localStorage with throwing proxy
    Object.defineProperty(window, 'localStorage', {
      value: throwingStorage,
      configurable: true,
      writable: true,
    })

    expect(() => {
      renderTestApp({ initialEntries: ['/bangladesh-journey'], resetStorage: false })
    }).not.toThrow()

    const notice = document.querySelector('.jnotice[data-problem]')
    expect(notice).not.toBeNull()
    expect(notice.textContent.trim().length).toBeGreaterThan(10)
    expect(screen.getByRole('progressbar')).toBeInTheDocument()
  })
})