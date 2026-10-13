/**
 * Regression smoke tests: the existing application still works alongside the
 * new feature.
 *
 * These are deliberately blunt. A new feature that changes a shared stylesheet,
 * a shared context, the router or the global font stack must not be able to do
 * so quietly, and the cheapest way to catch that is to assert the existing
 * surfaces still render and that the new feature is additive rather than a
 * replacement.
 *
 * Pages are rendered directly inside the providers they need, following the
 * convention `ScholarshipsPage.test.jsx` already uses, rather than mounting the
 * whole `App` — that keeps each assertion about the page's own contract instead
 * of about the provider stack.
 *
 * The Scholarship Catalogue and SOP Builder are the two features most likely to
 * be disturbed: the catalogue is the page most visitors land on, and the SOP
 * Builder is the other browser-local workspace that shares the storage
 * conventions this feature follows.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import ScholarshipsPage from '../../../pages/ScholarshipsPage'
import SopBuilderPage from '../../../pages/SopBuilderPage'
import { CompareProvider } from '../../../context/CompareContext.jsx'
import { SavedScholarshipsProvider } from '../../../context/SavedScholarshipsContext.jsx'
import { AuthContext } from '../../../context/authContext'
import { STORAGE_KEY as JOURNEY_STORAGE_KEY } from '../lib/journeySchema.js'
import { resetJourneyStorage } from '../lib/journeyStorage.js'

/**
 * The catalogue reads its snapshot through this module, so it is the seam a
 * regression test has to hold. The payload shape matches what the snapshot
 * index actually carries, and every field is the catalogue's own contract
 * rather than a convenient shape: a title, a country, a degree level and an
 * official source URL.
 */
vi.mock('../../../services/staticScholarshipService', async () => {
  const actual = await vi.importActual('../../../services/staticScholarshipService')
  const LISTING = {
    id: 1,
    title: 'Rhodes Scholarship',
    country: 'United Kingdom',
    degree_level: "Master's",
    funding_type: 'Full',
    deadline_text: 'Applications close 1 August 2027',
    source_url: 'https://example.org/rhodes',
    image_url: null,
    verified: true,
    is_active: true,
  }
  return {
    ...actual,
    loadScholarshipSnapshot: vi.fn().mockResolvedValue({
      scholarships: [LISTING],
      count: 1,
      total: 1,
      page: 1,
      total_pages: 1,
      per_page: 20,
    }),
    getCachedSnapshot: vi.fn().mockReturnValue(null),
  }
})

const authValue = {
  status: 'anonymous',
  user: null,
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
}

function renderCatalogue() {
  return render(
    <MemoryRouter initialEntries={['/scholarships']}>
      <AuthContext.Provider value={authValue}>
        <CompareProvider>
          <SavedScholarshipsProvider>
            <Routes>
              <Route path="/scholarships" element={<ScholarshipsPage />} />
            </Routes>
          </SavedScholarshipsProvider>
        </CompareProvider>
      </AuthContext.Provider>
    </MemoryRouter>,
  )
}

function renderSopBuilder() {
  return render(
    <MemoryRouter initialEntries={['/statement']}>
      <Routes>
        <Route path="/statement" element={<SopBuilderPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  window.localStorage.clear()
})

describe('catalogue regression', () => {
  it('still renders a scholarship list', async () => {
    renderCatalogue()
    expect(await screen.findByText(/Rhodes Scholarship/)).toBeInTheDocument()
  })

  it('still links a listing to its detail route', async () => {
    renderCatalogue()
    await screen.findByText(/Rhodes Scholarship/)
    const links = screen.getAllByRole('link')
    const detail = links.find((link) => (link.getAttribute('href') || '').match(/\/scholarships\/\d+/))
    // The catalogue keeps producing detail links, which is the contract the
    // whole page is built on.
    expect(detail).toBeDefined()
  })
})

describe('SOP Builder regression', () => {
  it('still renders its workspace', async () => {
    renderSopBuilder()
    // The SOP Builder is the other browser-local workspace. Its own heading has
    // to still appear, which is what proves the new feature did not shadow it.
    const heading = await screen.findByRole('heading', { level: 1 })
    expect(heading).toBeInTheDocument()
    expect(heading.textContent.length).toBeGreaterThan(0)
  })

  it('does not read or write the journey storage key', () => {
    window.localStorage.setItem(
      'scholarzone.sop-builder.v1',
      JSON.stringify({ schema: 'scholarzone.sop-builder', version: 1 }),
    )
    renderSopBuilder()
    // Opening another feature must not have created or consumed the journey key.
    expect(window.localStorage.getItem(JOURNEY_STORAGE_KEY)).toBeNull()
    expect(window.localStorage.getItem('scholarzone.sop-builder.v1')).not.toBeNull()
  })
})

describe('the new feature is additive', () => {
  it('uses a key no other feature owns', () => {
    expect(JOURNEY_STORAGE_KEY).toBe('scholarzone.bangladesh-journey.v1')
    expect(JOURNEY_STORAGE_KEY).not.toBe('scholarzone.sop-builder.v1')
    expect(JOURNEY_STORAGE_KEY).not.toMatch(/saved-scholarship|compare-|^sz\./)
  })

  it('leaves other keys alone when resetting itself', () => {
    window.localStorage.setItem('scholarzone.sop-builder.v1', 'x')
    window.localStorage.setItem('unrelated.key', 'y')
    // A key of the journey's own also exists, and must be the one removed.
    window.localStorage.setItem(JOURNEY_STORAGE_KEY, '{}')

    const result = resetJourneyStorage()

    expect(result.ok).toBe(true)
    expect(window.localStorage.getItem(JOURNEY_STORAGE_KEY)).toBeNull()
    expect(window.localStorage.getItem('scholarzone.sop-builder.v1')).toBe('x')
    expect(window.localStorage.getItem('unrelated.key')).toBe('y')
  })
})
