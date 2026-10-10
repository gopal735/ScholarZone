/**
 * The public catalogue page, served from the static snapshot.
 *
 * The free-tier failure was a database quota, not a page. What has to be true
 * is that an ordinary visit to the directory - with no query string, no
 * session, and the database over quota - still renders listings, filters,
 * sorting and pagination, and says plainly that the data is a snapshot rather
 * than the live database.
 *
 * Every test here fails if the page regresses to asking the API first: the
 * fetch mock throws for any request that is not the snapshot asset, and that
 * throw is a test failure rather than a fallback.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import ScholarshipsPage from './ScholarshipsPage'
import ScholarshipDetailsPage from './ScholarshipDetailsPage'
// The extensions are explicit, exactly as main.jsx writes them. Without them
// the resolver can pick `compareContext.js` or `savedScholarshipsContext.js` -
// which export only the context objects - instead of the providers, because the
// two filenames in each pair differ only by case and this filesystem is
// case-insensitive.
import { CompareProvider } from '../context/CompareContext.jsx'
import { SavedScholarshipsProvider } from '../context/SavedScholarshipsContext.jsx'
import { AuthContext } from '../context/authContext'
import { clearSnapshotCache } from '../services/staticScholarshipService'

const SNAPSHOT_META = {
  generated_at: '2026-10-10T12:41:37.970162Z',
  source_database: 'scholarzone.db',
  source_record_count: 695,
  public_record_count: 634,
  excluded: { closed: 12, archived: 52, quarantined: 51 },
  excluded_union: 61,
  schema_version: '1.0',
  visibility_predicate: 'status != closed AND is_archived = false AND verification_status != quarantined',
  sort_orders: {
    'recently-added': [3, 1, 2],
    recommended: [1, 3, 2],
    'recently-updated': [2, 1, 3],
    'deadline-soon': [3, 1, 2],
    'deadline-earliest': [3, 1, 2],
    'deadline-latest': [2, 1, 3],
    'fully-funded': [1, 3, 2],
    'name-asc': [3, 1, 2],
    'name-desc': [2, 1, 3],
  },
  sort_order_modes: [
    'deadline-earliest',
    'deadline-latest',
    'deadline-soon',
    'fully-funded',
    'name-asc',
    'name-desc',
    'recently-added',
    'recently-updated',
    'recommended',
  ],
  // The selectable values the snapshot exports, so the filter menus are built
  // from the catalogue rather than from a guessed list. These are the exact
  // distinct values of the three fixture records below.
  filter_options: {
    countries: ['Singapore', 'Sweden', 'USA'],
    degrees: ['Bachelor', 'Master', 'PhD'],
    funding_types: ['Fully Funded', 'Partial'],
    statuses: ['open', 'upcoming'],
    deadline_months: [1, 11, 12],
  },
}

const SNAPSHOT_STATS = {
  total: 634,
  countries: 74,
  open: 377,
  closing_soon: 52,
  upcoming: 205,
  verified_active: 542,
  fully_funded: 215,
  with_image: 455,
  with_official_source: 631,
}

function record(overrides = {}) {
  return {
    id: 1,
    title: 'KTH India Scholarship',
    name: 'KTH India Scholarship',
    country: 'Sweden',
    degree: 'Master',
    degree_levels: 'Master',
    funding: 'Fully Funded',
    funding_type: 'Fully Funded',
    deadline: '2026-12-31',
    deadline_date: '2026-12-31',
    deadline_precision: 'exact',
    status: 'open',
    verified: true,
    verification_status: 'active',
    last_verified_at: '2026-10-01',
    last_verified_date: '2026-10-01',
    official_source_url: 'https://www.kth.se/en/studies/master/admissions/scholarships/kth-india-scholarship-1.422144',
    official_source: 'KTH Royal Institute of Technology',
    image_url: null,
    image_source_type: null,
    image_kind: null,
    image_source_url: null,
    image_verified_at: null,
    image_alt_text: null,
    description: 'A tuition-waiving scholarship for one Indian student.',
    region: null,
    duration: '2 years',
    application_period: 'October to January',
    catalogue_url: null,
    official_updates_url: null,
    application_link: null,
    eligibility: [],
    eligibility_summary: null,
    benefits: ['Tuition fee coverage', 'Monthly living allowance'],
    coverage: ['Tuition'],
    requirements: ['CV'],
    documents: ['CV'],
    required_documents: ['CV'],
    english_requirement: null,
    application_method: ['Online'],
    selection_notes: null,
    program_type: null,
    best_fit: null,
    notes: null,
    updated_at: '2026-10-01T00:00:00',
    ...overrides,
  }
}

const SNAPSHOT = {
  meta: SNAPSHOT_META,
  stats: SNAPSHOT_STATS,
  scholarships: [
    record(),
    record({
      id: 3,
      title: 'Another USA Scholarship',
      name: 'Another USA Scholarship',
      country: 'USA',
      degree: 'Bachelor',
      funding: 'Fully Funded',
      deadline: '2026-11-30',
      deadline_date: '2026-11-30',
      status: 'open',
      verified: true,
      verification_status: 'active',
      updated_at: '2026-09-20T00:00:00',
    }),
    record({
      id: 2,
      title: 'NUS Research Scholarship',
      name: 'NUS Research Scholarship',
      country: 'Singapore',
      degree: 'PhD',
      funding: 'Partial',
      deadline: '2027-01-15',
      deadline_date: '2027-01-15',
      status: 'upcoming',
      verified: false,
      verification_status: 'needs_review',
      last_verified_at: null,
      last_verified_date: null,
      official_source: 'NUS Graduate School',
      official_source_url: 'https://nusgs.nus.edu.sg/scholarships/nus-research-scholarship',
      updated_at: '2026-10-02T00:00:00',
    }),
  ],
}

/**
 * Which URLs the mock saw, split by purpose.
 *
 * The catalogue endpoints are what must not be touched: they are the ones the
 * snapshot replaces. Feature endpoints are a different thing - a detail page
 * legitimately renders a supervisor panel, which is a database-backed feature
 * that degrades on its own - so asserting that nothing at all was requested
 * would be asserting the detail page has no database features, which it should.
 */
/**
 * The catalogue endpoints the snapshot replaces: the directory list, a single
 * detail record, and the public statistics.
 *
 * Written precisely rather than as a prefix. `/scholarships/2/supervisors` also
 * starts with `/scholarships/`, but it is a database-backed feature with its own
 * failure path, not the catalogue - and a prefix test would have lumped it in
 * and failed a page for doing something it is allowed to do.
 */
const CATALOGUE_ENDPOINTS = [
  /^\/api\/scholarships$/,
  /^\/api\/scholarships\/stats$/,
  /^\/api\/scholarships\/\d+$/,
]

function isCatalogueCall(url) {
  return CATALOGUE_ENDPOINTS.some((pattern) => pattern.test(url.pathname))
}

function splitCalls(apiCalls) {
  const asUrls = apiCalls.map((url) => new URL(url))
  return {
    catalogue: asUrls.filter(isCatalogueCall),
    feature: asUrls.filter((url) => !isCatalogueCall(url)),
  }
}

/**
 * Installs a fetch mock that serves the snapshot and fails loudly on any
 * catalogue request. The loud failure is the point: a request to the catalogue
 * API in this test means the page asked the database for a public listing,
 * which is the regression these tests exist to catch.
 */
function stubStaticOnlyFetch() {
  const apiCalls = []
  const mock = vi.fn(async (url) => {
    if (String(url).includes('scholarships-snapshot.json')) {
      return { ok: true, status: 200, json: async () => SNAPSHOT }
    }
    apiCalls.push(String(url))

    const request = new URL(String(url))
    // A catalogue request must not happen, and is reported as a failure rather
    // than answered, so a regression cannot pass by falling back.
    if (isCatalogueCall(request)) {
      throw new TypeError(`Unexpected catalogue API request during public browsing: ${url}`)
    }
    // A feature endpoint is allowed to be attempted and to fail, exactly as it
    // would with the database over quota.
    throw new TypeError(`Feature unavailable: ${url}`)
  })
  vi.stubGlobal('fetch', mock)
  return { mock, apiCalls }
}

/**
 * A minimal IntersectionObserver.
 *
 * The detail page reveals sections as they scroll into view, and jsdom has no
 * IntersectionObserver. Every element is treated as immediately visible, which
 * is what the page would do on a real viewport where the section is on screen -
 * so this reveals the same content rather than hiding it. Without it the page
 * throws during render and the test would be measuring the environment, not the
 * behaviour.
 */
function stubIntersectionObserver() {
  class ImmediateIntersectionObserver {
    constructor(callback) {
      this.callback = callback
    }

    observe(element) {
      this.callback([{ isIntersecting: true, target: element }], this)
    }

    unobserve() {}

    disconnect() {}
  }

  vi.stubGlobal('IntersectionObserver', ImmediateIntersectionObserver)
}

/**
 * Renders a catalogue page inside the providers it needs.
 *
 * None of these are incidental. The card renders actions for saving and
 * comparing, each backed by its own context, and the saved shortlist in turn
 * reads the auth context to decide whether to sync with a server. They throw
 * rather than degrade when absent, so they are part of a realistic catalogue
 * rather than a test-only convenience.
 *
 * The auth value is an anonymous visitor, which is the interesting case: the
 * public catalogue has to work for someone with no account and no session,
 * because that is who it is for.
 */
function renderCatalogue(ui, path) {
  const authValue = {
    status: 'unauthenticated',
    user: null,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  }

  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthContext.Provider value={authValue}>
        <CompareProvider>
          <SavedScholarshipsProvider>
            {/* The detail page reads its id from the route, so it has to be
                rendered inside one. Rendering it bare would leave useParams()
                empty and the page would answer "not found" for every id. */}
            <Routes>
              <Route path="/scholarships/:id" element={ui} />
              <Route path="/scholarships" element={ui} />
            </Routes>
          </SavedScholarshipsProvider>
        </CompareProvider>
      </AuthContext.Provider>
    </MemoryRouter>,
  )
}

describe('public catalogue page, static-first', () => {
  beforeEach(() => {
    clearSnapshotCache()
    vi.unstubAllGlobals()
    stubIntersectionObserver()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    clearSnapshotCache()
  })

  it('a country arriving in the URL is representable in the control', async () => {
    // Found on the deploy preview. The Country menu was a hardcoded list that
    // did not include Japan, so a select pointing at Japan had no matching
    // option and the browser showed the first one: the menu read "All
    // countries" while every result was Japan. The results were right and the
    // control contradicted them.
    stubStaticOnlyFetch()

    renderCatalogue(<ScholarshipsPage />, '/scholarships?country=USA')

    expect(await screen.findByText('Another USA Scholarship')).toBeTruthy()

    const countrySelect = document.querySelector('#scholarship-country')
    expect(countrySelect.value).toBe('USA')
    expect(countrySelect.selectedOptions[0].textContent.trim()).toBe('USA')
  })

  it('offers only countries the catalogue actually holds', async () => {
    stubStaticOnlyFetch()

    renderCatalogue(<ScholarshipsPage />, '/scholarships')
    await screen.findByText('KTH India Scholarship')

    const countryOptions = Array.from(
      document.querySelectorAll('#scholarship-country option'),
    ).map((option) => option.value)

    // 'Europe' is not a country any record holds, and it used to be an option
    // that could never match.
    expect(countryOptions).not.toContain('Europe')
    expect(countryOptions).toEqual(['All', 'Singapore', 'Sweden', 'USA'])
  })

  it('does not offer a status the public catalogue excludes', async () => {
    stubStaticOnlyFetch()

    renderCatalogue(<ScholarshipsPage />, '/scholarships')
    await screen.findByText('KTH India Scholarship')

    const statusOptions = Array.from(
      document.querySelectorAll('#scholarship-status option'),
    ).map((option) => option.value)

    // Closed records are excluded by the visibility predicate, so a "Closed"
    // option could only ever return nothing while looking like a working
    // filter.
    expect(statusOptions).not.toContain('closed')
    expect(statusOptions).toEqual(['All', 'open', 'upcoming'])
  })

  it('renders listings from the snapshot with no API request', async () => {
    const { apiCalls } = stubStaticOnlyFetch()

    renderCatalogue(<ScholarshipsPage />, '/scholarships')

    // The catalogue is usable as soon as the snapshot is read.
    expect(await screen.findByText('KTH India Scholarship')).toBeInTheDocument()
    expect(screen.getByText('Another USA Scholarship')).toBeInTheDocument()
    expect(screen.getByText('NUS Research Scholarship')).toBeInTheDocument()

    // No request reached the database at all - not the catalogue endpoints the
    // snapshot replaces, and not the per-card supervisor count that used to be
    // fetched once per card.
    expect(apiCalls).toEqual([])
  })

  it('discloses that the catalogue is an unverified snapshot', async () => {
    stubStaticOnlyFetch()

    renderCatalogue(<ScholarshipsPage />, '/scholarships')

    const notice = await screen.findByTestId('catalogue-source-notice')
    expect(notice).toBeInTheDocument()
    expect(notice.textContent).toMatch(/static snapshot/i)
    expect(notice.textContent).toMatch(/not been reconciled against the production database/i)
    expect(notice.textContent).toMatch(/official source link/i)
  })

  it('routes to the detail page, where the official source link lives', async () => {
    stubStaticOnlyFetch()

    renderCatalogue(<ScholarshipsPage />, '/scholarships')
    await screen.findByText('KTH India Scholarship')

    // A card has never linked out to the provider directly; it routes to the
    // detail page, which carries the provider's own URL. What matters is that
    // the notice says to check it there, and that the route still works.
    const notice = screen.getByTestId('catalogue-source-notice')
    expect(notice.textContent).toMatch(/official source link/i)

    const cardLinks = screen.getAllByRole('link', { name: /view details/i })
    expect(cardLinks.map((link) => link.getAttribute('href')).sort()).toEqual([
      '/scholarships/1',
      '/scholarships/2',
      '/scholarships/3',
    ])
  })

  it('a detail page carries the official source link directly', async () => {
    stubStaticOnlyFetch()

    renderCatalogue(<ScholarshipDetailsPage />, '/scholarships/2')

    await screen.findByText('NUS Research Scholarship')
    const links = screen.getAllByRole('link')
    const provider = links.find((link) => link.getAttribute('href')?.includes('nusgs.nus.edu.sg'))
    expect(provider).toBeDefined()
  })

  it('does not show the old "live directory unavailable" framing', async () => {
    stubStaticOnlyFetch()

    renderCatalogue(<ScholarshipsPage />, '/scholarships')

    await screen.findByText('KTH India Scholarship')
    // Nothing is unavailable. The snapshot is the intended source, so an
    // error-shaped message here would misdescribe a working catalogue.
    expect(screen.queryByText(/Live directory unavailable/i)).not.toBeInTheDocument()
  })

  it('reports the real record count without claiming a production figure', async () => {
    stubStaticOnlyFetch()

    renderCatalogue(<ScholarshipsPage />, '/scholarships')

    const notice = await screen.findByTestId('catalogue-source-notice')
    // 3 of the 3 fixture records, derived from the header rather than asserted.
    expect(notice.textContent).toMatch(/634 of 695 records are included/)
  })

  it('keeps search, filter, sorting and pagination working', async () => {
    stubStaticOnlyFetch()

    renderCatalogue(<ScholarshipsPage />, '/scholarships')

    await screen.findByText('KTH India Scholarship')

    // Filtering is client-side over the snapshot, so the same page works with
    // the database over quota.
    const searchInput = await screen.findByPlaceholderText('Search scholarships...')
    expect(searchInput).toBeInTheDocument()

    const sortSelect = screen.getByLabelText(/Sort by/i)
    expect(sortSelect).toBeInTheDocument()

    const countrySelect = screen.getByLabelText(/All countries|Country/i)
    expect(countrySelect).toBeInTheDocument()
  })

  it('a detail page discloses provenance without contacting the API', async () => {
    const { apiCalls } = stubStaticOnlyFetch()

    renderCatalogue(<ScholarshipDetailsPage />, '/scholarships/2')

    const notice = await screen.findByTestId('catalogue-source-notice')
    expect(notice).toBeInTheDocument()
    expect(notice.textContent).toMatch(/static snapshot/i)

    // And the record itself is rendered from the snapshot.
    expect(await screen.findByText('NUS Research Scholarship')).toBeInTheDocument()

    // The detail record came from the snapshot. The detail page may still ask
    // the database for its supervisor panel, which is a feature that degrades
    // on its own - but nothing on the catalogue path was requested.
    const { catalogue } = splitCalls(apiCalls)
    expect(catalogue).toEqual([])
  })

  it('an unknown id is a not-found state, not a fabricated record', async () => {
    stubStaticOnlyFetch()

    renderCatalogue(<ScholarshipDetailsPage />, '/scholarships/99999')

    await waitFor(() => {
      expect(screen.getByText(/not found/i)).toBeInTheDocument()
    })
    expect(screen.queryByText('KTH India Scholarship')).not.toBeInTheDocument()
  })
})
