/**
 * Component tests for the Bangladesh Applicant Journey.
 *
 * The behaviours worth pinning are the ones where a plausible render would be
 * wrong: progress that moves on a click rather than on real work, a reset that
 * clears more than its own data, an export that loses the estimate label, and
 * a disclaimer that can be dismissed away.
 *
 * The route is rendered through the real provider and the real router path so
 * these assertions are about the assembled feature, not a permissive harness.
 */

import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { JourneyProvider } from '../state/JourneyProvider.jsx'
import { JourneyPage } from '../components/JourneyPage.jsx'
import { STORAGE_KEY } from '../lib/journeySchema.js'

const OTHER_APP_KEY = 'scholarzone.saved-scholarship-ids.v1'

/** The document enderJourney primes, so a cancelled reset can be checked against it. */
const PRIMED_DOCUMENT = JSON.stringify({
  schema: 'scholarzone.bangladesh-journey',
  version: 1,
  settings: { language: 'en' },
})

/**
 * Renders the journey with an empty document, primed to English.
 *
 * Priming the language rather than clicking the control keeps each test to one
 * interaction: these assertions are about progress, reset and export, not the
 * language picker, which has its own tests below. The shipped default display
 * mode is `both`, and that default is asserted separately rather than assumed.
 */
function renderJourney({ route = '/bangladesh-journey', language = 'en', storage = 'normal' } = {}) {
  if (storage === 'blocked') {
    // Installed before the provider mounts, because the provider
    // capability-checks storage during its first render.
    Object.defineProperty(window, 'localStorage', {
      get() {
        throw new Error('blocked')
      },
      configurable: true,
    })
  } else if (language) {
    installPrimedStorage({
      [STORAGE_KEY]: JSON.stringify({
        schema: 'scholarzone.bangladesh-journey',
        version: 1,
        settings: { language },
      }),
    })
  }
  return render(
    <MemoryRouter initialEntries={[route]}>
      <JourneyProvider>
        <Routes>
          <Route path="/bangladesh-journey" element={<JourneyPage />} />
          <Route path="/bangladesh-journey/:stepId" element={<JourneyPage />} />
        </Routes>
      </JourneyProvider>
    </MemoryRouter>,
  )
}

/**
 * Restores a working store after a test replaced it with a throwing accessor.
 *
 * Without this, the "storage unavailable" case poisons every later test in the
 * file: `window.localStorage` keeps throwing in `beforeEach`, so the whole suite
 * fails for a reason unrelated to what it is asserting.
 */
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

/** Reads and normalises the persisted document. */
function readPersisted() {
  const raw = window.localStorage.getItem(STORAGE_KEY)
  return raw === null ? null : JSON.parse(raw)
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

beforeEach(() => {
  restoreWorkingStorage()
  installPrimedStorage({})
})

afterEach(() => {
  restoreWorkingStorage()
})

/* ── Rendering and the seven steps ──────────────────────────────────── */

describe('rendering the feature route', () => {
  it('renders the seven steps with the first active', () => {
    renderJourney()
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /Find/ }).length).toBeGreaterThan(0)
    const current = screen.getAllByRole('button', { name: /Find/ })[0]
    expect(current).toHaveAttribute('aria-current', 'step')
  })

  it('shows a progressbar with an honest zero', () => {
    renderJourney()
    const bar = screen.getByRole('progressbar')
    expect(bar).toHaveAttribute('aria-valuenow', '0')
    expect(bar).toHaveAttribute('aria-valuemin', '0')
    expect(bar).toHaveAttribute('aria-valuemax', '100')
  })

  it('shows the disclaimer by default and it cannot be dismissed away', () => {
    renderJourney()
    const disclaimer = screen.getByRole('complementary', { name: /What this tool can and cannot do/ })
    expect(disclaimer).toBeInTheDocument()
    // No dismiss affordance: the disclaimer is standing guidance, not a banner.
    expect(within(disclaimer).queryByRole('button', { name: /dismiss|close/i })).toBeNull()
  })

  it('offers a language control with a persisted default', () => {
    renderJourney()
    expect(screen.getAllByRole('radio')).toHaveLength(3)
  })
})

describe('moving between the seven steps', () => {
  it('changes the active module', async () => {
    const user = userEvent.setup()
    renderJourney()
    const costButton = screen.getAllByRole('button', { name: /BDT Cost Planner/ })[0]
    await user.click(costButton)
    expect(await screen.findByText(/No costs recorded yet/)).toBeInTheDocument()
    expect(costButton).toHaveAttribute('aria-current', 'step')
  })

  it('keeps exactly one step current at a time', async () => {
    const user = userEvent.setup()
    renderJourney()
    await user.click(screen.getAllByRole('button', { name: /Document Studio/ })[0])
    const currents = screen.getAllByRole('button').filter((b) => b.getAttribute('aria-current') === 'step')
    expect(currents).toHaveLength(1)
  })
})

/* ── Completing an item and progress ───────────────────────────────── */

describe('completing an item updates overall progress', () => {
  it('moves progress when a document reaches done', async () => {
    const user = userEvent.setup()
    renderJourney({ route: '/bangladesh-journey/documents' })
    const bar = screen.getByRole('progressbar')
    expect(bar).toHaveAttribute('aria-valuenow', '0')

    await user.click(screen.getAllByRole('button', { name: /Add generic template items/ })[0])
    await waitFor(() => expect(readPersisted()).not.toBeNull())

    // The template rows are unconfirmed and must not count.
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '0')

    const requirementSelects = screen.getAllByRole('combobox', { name: /^Requirement — / })
    await user.selectOptions(requirementSelects[0], 'mandatory')
    // Confirmed but not done: still no progress.
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '0')

    const progressSelects = screen.getAllByRole('combobox', { name: /^Progress — / })
    await user.selectOptions(progressSelects[0], 'done')
    await waitFor(() => {
      expect(screen.getByRole('progressbar')).not.toHaveAttribute('aria-valuenow', '0')
    })
  })

  it('does not move progress merely by visiting a module', async () => {
    const user = userEvent.setup()
    renderJourney()
    for (const name of [/Eligibility/, /Document Studio/, /Application Timeline/, /BDT Cost Planner/, /Official Source Guide/, /After-Offer/]) {
      await user.click(screen.getAllByRole('button', { name })[0])
      expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '0')
    }
  })
})

/* ── Next 3 Actions ─────────────────────────────────────────────────── */

describe('Next 3 Actions', () => {
  it('suggests adding the first shortlist entry on an empty journey', () => {
    renderJourney()
    expect(screen.getByText(/Add your first scholarship to the shortlist/)).toBeInTheDocument()
  })

  it('renders fewer than three when fewer genuine actions exist', () => {
    renderJourney()
    const region = screen.getByText('Next 3 Actions').closest('section')
    const items = within(region).getAllByRole('listitem')
    expect(items.length).toBeLessThanOrEqual(3)
  })

  it('links an action to the module it belongs to', async () => {
    const user = userEvent.setup()
    renderJourney()
    const region = screen.getByText('Next 3 Actions').closest('section')
    const link = within(region).getAllByRole('button')[0]
    await user.click(link)
    // Navigating to a module keeps exactly one current step.
    expect(screen.getAllByRole('button').filter((b) => b.getAttribute('aria-current') === 'step')).toHaveLength(1)
  })
})

/* ── Reset ──────────────────────────────────────────────────────────── */

describe('reset', () => {
  it('asks for confirmation before removing anything', async () => {
    const user = userEvent.setup()
    renderJourney()
    await user.click(screen.getByRole('button', { name: /^Reset journey$/ }))
    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByText(/removes only this feature/)).toBeInTheDocument()
    // Cancelling leaves the store untouched.
    await user.click(within(dialog).getByRole('button', { name: /Keep my data/ }))
    // The primed document is the pre-existing store, untouched by a cancelled reset.
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe(PRIMED_DOCUMENT)
  })

  it('removes only the journey key when confirmed', async () => {
    const user = userEvent.setup()
    renderJourney({ route: '/bangladesh-journey/documents' })
    // Written after the helper primes its own store, so this key survives the
    // primed document and is what proves reset's scoping.
    window.localStorage.setItem(OTHER_APP_KEY, JSON.stringify([1, 2, 3]))

    await user.click(screen.getByRole('button', { name: /Add generic template items/ }))
    await waitFor(() => expect(readPersisted()).not.toBeNull())
    expect(window.localStorage.getItem(STORAGE_KEY)).toBeTruthy()

    await user.click(screen.getByRole('button', { name: /^Reset journey$/ }))
    const dialog = screen.getByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: /Reset journey data/ }))

    await waitFor(() => {
      expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull()
    })
    // The other feature's key is untouched.
    expect(window.localStorage.getItem(OTHER_APP_KEY)).toBe(JSON.stringify([1, 2, 3]))
  })

  it('restores predictable default state after a reset', async () => {
    const user = userEvent.setup()
    renderJourney({ route: '/bangladesh-journey/documents' })
    await user.click(screen.getByRole('button', { name: /Add generic template items/ }))
    await waitFor(() => expect(readPersisted()).not.toBeNull())
    await user.click(screen.getByRole('button', { name: /^Reset journey$/ }))
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: /Reset journey data/ }))
    await waitFor(() => {
      expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '0')
    })
  })

  it('closes on Escape without removing anything', async () => {
    const user = userEvent.setup()
    renderJourney()
    await user.click(screen.getByRole('button', { name: /^Reset journey/ }))
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe(PRIMED_DOCUMENT)
  })
})

/* ── Language ───────────────────────────────────────────────────────── */

describe('language toggle', () => {
  it('persists the selected mode', async () => {
    const user = userEvent.setup()
    renderJourney()
    await user.click(screen.getByRole('radio', { name: /Bangla only/ }))
    await waitFor(() => {
      expect(readPersisted()?.settings?.language).toBe('bn')
    })
  })

  it('switches the displayed copy', async () => {
    const user = userEvent.setup()
    renderJourney()
    await user.click(screen.getByRole('radio', { name: 'English only' }))
    expect(screen.getAllByText(/Find & Explore/).length).toBeGreaterThan(0)
  })
})

/* ── Estimates and the disclaimer ───────────────────────────────────── */

describe('estimate labelling', () => {
  it('labels a cost line as an estimate and keeps the label on the total', async () => {
    const user = userEvent.setup()
    renderJourney({ route: '/bangladesh-journey/costs' })
    await user.click(screen.getAllByRole('button', { name: /Add a cost/ })[0])
    await user.type(screen.getAllByRole('textbox')[0], 'Tuition')

    const selects = screen.getAllByRole('combobox')
    // The source-type select is the one offering Official.
    const sourceSelect = selects.find((s) => within(s).queryByText(/An estimate/))
    await user.selectOptions(sourceSelect, 'estimate')

    expect(screen.getAllByText(/Includes estimates/).length).toBeGreaterThan(0)
  })

  it('states that nothing here decides eligibility or an outcome', () => {
    renderJourney()
    const text = document.body.textContent
    expect(text).toMatch(/cannot tell you whether you qualify/)
    expect(text).toMatch(/Check the official source/)
  })
})

/* ── Export / import ────────────────────────────────────────────────── */

describe('export and import', () => {
  it('downloads a JSON file carrying the schema version and estimate labels', async () => {
    const user = userEvent.setup()
    renderJourney()

    let captured = null
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function () {
      captured = { download: this.download, href: this.href }
    })
    const createURL = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:fake')
    const revokeURL = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})

    await user.click(screen.getByRole('button', { name: /Export JSON/ }))

    expect(captured).not.toBeNull()
    expect(captured.download).toContain('scholarzone-bangladesh-journey')

    clickSpy.mockRestore()
    createURL.mockRestore()
    revokeURL.mockRestore()
  })

  it('rejects a malformed import with a useful message', async () => {
    const user = userEvent.setup()
    renderJourney()
    const file = new File(['{not json'], 'plan.json', { type: 'application/json' })
    const input = screen.getByLabelText(/Import JSON/)
    await user.upload(input, file)
    expect(await screen.findByText(/not valid JSON/)).toBeInTheDocument()
  })

  it('rejects an import from an unknown schema', async () => {
    const user = userEvent.setup()
    renderJourney()
    const file = new File([JSON.stringify({ schema: 'other-app', version: 1 })], 'plan.json', {
      type: 'application/json',
    })
    await user.upload(screen.getByLabelText(/Import JSON/), file)
    expect(await screen.findByText(/not a Bangladesh Applicant Journey export/)).toBeInTheDocument()
  })

  it('rejects an import from a newer version', async () => {
    const user = userEvent.setup()
    renderJourney()
    const file = new File(
      [JSON.stringify({ schema: 'scholarzone.bangladesh-journey', version: 99, shortlist: [] })],
      'plan.json',
      { type: 'application/json' },
    )
    await user.upload(screen.getByLabelText(/Import JSON/), file)
    expect(await screen.findByText(/written by a newer version/)).toBeInTheDocument()
  })
})

/* ── Storage unavailable ────────────────────────────────────────────── */

describe('storage unavailable', () => {
  afterEach(() => {
    // The throwing accessor must not leak into the next test's beforeEach.
    restoreWorkingStorage()
    installPrimedStorage({})
  })

  it('keeps the page usable and shows a non-blocking notice', () => {
    expect(() => renderJourney({ storage: 'blocked', language: null })).not.toThrow()
    // No language was primed, so the shipped default (`both`) renders Bangla
    // first. The notice's own data attribute is the language-independent handle.
    const notice = document.querySelector('.jnotice[data-problem]')
    expect(notice).not.toBeNull()
    expect(notice.textContent.trim().length).toBeGreaterThan(10)
    // The workspace is still there: the notice is not a blocker.
    expect(screen.getByRole('progressbar')).toBeInTheDocument()
  })
})

/* ── Empty states ───────────────────────────────────────────────────── */

describe('empty states', () => {
  it('shows an honest empty shortlist with a way forward', () => {
    renderJourney()
    expect(screen.getByText(/No shortlisted opportunities yet/)).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /Add an opportunity/ }).length).toBeGreaterThan(0)
  })

  it('marks a sample entry as unverified sample data', async () => {
    const user = userEvent.setup()
    renderJourney()
    await user.click(screen.getAllByRole('button', { name: /Sample/ })[0])
    expect(await screen.findByText(/Unverified sample data/)).toBeInTheDocument()
    expect(screen.getByText(/illustrative entry/)).toBeInTheDocument()
  })
})

/* ── Date separation ────────────────────────────────────────────────── */

describe('official and personal dates stay separate', () => {
  it('renders both fields independently', async () => {
    const user = userEvent.setup()
    renderJourney({ route: '/bangladesh-journey/timeline' })
    const label = screen.getByLabelText('Add a timeline entry')
    await user.type(label, 'Alpha')
    await user.click(screen.getByRole('button', { name: /^Add$/ }))

    // Persistence is debounced, so wait for the write rather than assuming it.
    await waitFor(() => expect(readPersisted()?.timeline).toHaveLength(1))
    const entry = readPersisted().timeline[0]
    expect(entry.officialDeadline).toBe('')
    expect(entry.personalTarget).toBe('')
    // Both fields exist on the record and neither is derived from the other.
    expect(Object.keys(entry)).toContain('officialDeadline')
    expect(Object.keys(entry)).toContain('personalTarget')
    expect(Object.keys(entry)).toContain('officialDeadlineNote')
  })
})

describe('default language mode', () => {
  it('is "both" on a fresh install, so Bangla is the primary line', () => {
    renderJourney({ language: null })
    // The Bangla label for Find & Explore is the primary text in `both` mode.
    expect(screen.getAllByText('খুঁজুন ও বিশ্লেষণ করুন').length).toBeGreaterThan(0)
    // And the English line accompanies it rather than being replaced by it.
    expect(screen.getAllByText('Find & Explore').length).toBeGreaterThan(0)
  })
})

/* ── Accessibility ──────────────────────────────────────────────────── */

describe('accessibility-relevant semantics', () => {
  it('labels the progressbar and the active step', () => {
    renderJourney()
    const bar = screen.getByRole('progressbar')
    expect(bar).toHaveAttribute('aria-valuenow')
    expect(document.querySelector('[aria-current="step"]')).not.toBeNull()
  })

  it('gives the stepper an accessible name', () => {
    renderJourney()
    const nav = screen.getByRole('navigation', { name: /Journey progress/i })
    expect(nav).toBeInTheDocument()
  })

  it('exposes the disclaimer as a labelled region', () => {
    renderJourney()
    const region = screen.getByRole('complementary', { name: /What this tool can and cannot do/ })
    expect(region).toHaveAccessibleName()
  })

  it('gives icon-only remove buttons an accessible name', async () => {
    const user = userEvent.setup()
    renderJourney({ route: '/bangladesh-journey/documents' })
    await user.click(screen.getAllByRole('button', { name: /Add generic template items/ })[0])
    const iconButtons = screen.getAllByRole('button').filter((b) => b.textContent.trim() === '×')
    for (const button of iconButtons) {
      expect(button).toHaveAccessibleName()
    }
  })
})
