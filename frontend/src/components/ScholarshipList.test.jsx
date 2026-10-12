/**
 * The catalogue's URL-bound state, as rendered.
 *
 * The page-level tests in ScholarshipsPage.test.jsx cover the page chrome. These
 * cover the part that was the actual defect: search, filters, sort and page
 * lived in React state only, so a filtered view could not be shared,
 * bookmarked, or reached with the Back button, and a reload after page 4
 * returned to page 1.
 *
 * A `MemoryRouter` with an initial entry is the whole mechanism: if state is in
 * the URL, a route entered with a query string renders that state, and if it is
 * in React state it renders the default and these fail.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useLayoutEffect } from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import ScholarshipList from './ScholarshipList.jsx'
import { CompareProvider } from '../context/CompareContext.jsx'
import { SavedScholarshipsProvider } from '../context/SavedScholarshipsContext.jsx'
import { AuthContext } from '../context/authContext'
import { clearSnapshotCache } from '../services/staticScholarshipService'
import { NO_FILTER } from '../services/catalogueQuery.js'

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
    'deadline-earliest', 'deadline-latest', 'deadline-soon', 'fully-funded',
    'name-asc', 'name-desc', 'recently-added', 'recently-updated', 'recommended',
  ],
  filter_options: {
    countries: ['Singapore', 'Sweden', 'USA'],
    degrees: ['Bachelor', 'Master', 'PhD'],
    funding_types: ['Fully Funded', 'Partial'],
    statuses: ['open', 'upcoming'],
    deadline_months: [1, 11, 12],
    regions: ['Europe', 'Asia', 'North America'],
  },
}

function record(overrides = {}) {
  return {
    id: 1,
    title: 'KTH India Scholarship',
    name: 'KTH India Scholarship',
    official_source: 'KTH Royal Institute of Technology',
    country: 'Sweden',
    region: 'Europe',
    degree: 'Master',
    degree_levels: 'Master',
    funding: 'Fully Funded',
    funding_type: 'Fully Funded',
    tuition_coverage: true,
    deadline: '2026-12-31',
    deadline_date: '2026-12-31',
    deadline_precision: 'exact',
    status: 'open',
    verification_status: 'active',
    last_verified_at: '2026-10-01',
    official_source_url: 'https://www.kth.se/en/studies/master/admissions/scholarships',
    eligibility_summary: 'Applicants from India with a bachelor degree.',
    english_requirement: 'IELTS 6.5',
    duration: '2 years',
    updated_at: '2026-10-01T00:00:00',
    ...overrides,
  }
}

const SNAPSHOT = {
  meta: SNAPSHOT_META,
  stats: { total: 3, countries: 3 },
  scholarships: [
    record(),
    record({
      id: 3,
      title: 'Another USA Scholarship',
      country: 'USA',
      region: 'North America',
      degree: 'Bachelor',
      degree_levels: "Bachelor's",
      funding: 'Partial',
      funding_type: 'Partial',
      tuition_coverage: false,
      deadline: '2026-11-30',
      deadline_date: '2026-11-30',
      deadline_precision: 'exact',
      status: 'open',
      updated_at: '2026-09-20T00:00:00',
    }),
    record({
      id: 2,
      title: 'NUS Research Scholarship',
      country: 'Singapore',
      region: 'Asia',
      degree: 'PhD',
      degree_levels: 'PhD',
      funding: 'Partial',
      funding_type: 'Partial',
      tuition_coverage: null,
      deadline: null,
      deadline_date: null,
      deadline_precision: 'unknown',
      status: 'upcoming',
      verification_status: 'needs_review',
      last_verified_at: null,
      official_source_url: 'https://nusgs.nus.edu.sg/scholarships',
      eligibility_summary: 'Any nationality with a relevant bachelor degree.',
      updated_at: '2026-10-02T00:00:00',
    }),
  ],
}

/**
 * The route's address bar, read from inside the router.
 *
 * Recorded in a layout effect rather than during render, so the component stays
 * pure: a state change that does not reach the URL shows up here as an
 * unchanged value, which is exactly the failure mode these tests exist to
 * catch. `useLayoutEffect` keeps it synchronous with the DOM update, so an
 * assertion immediately after an interaction sees the committed URL.
 */
let currentSearch = ''
function SearchProbe() {
  const location = useLocation()
  useLayoutEffect(() => {
    currentSearch = location.search
  }, [location.search])
  return null
}

/**
 * The catalogue, with the providers its cards need.
 *
 * `ScholarshipActions` renders inside every card and reads both the saved and
 * the compare stores, so a list rendered without them throws before any card
 * appears - which is why this wraps them rather than the page-level test's
 * more elaborate setup.
 */
function renderCatalogue(ui, initialEntry = '/scholarships') {
  const authValue = { status: 'unauthenticated', user: null, login: vi.fn(), register: vi.fn(), logout: vi.fn() }
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <AuthContext.Provider value={authValue}>
        <CompareProvider>
          <SavedScholarshipsProvider>
            <SearchProbe />
            <Routes>
              <Route path="/scholarships" element={ui} />
            </Routes>
          </SavedScholarshipsProvider>
        </CompareProvider>
      </AuthContext.Provider>
    </MemoryRouter>,
  )
}

function stubSnapshotFetch() {
  const apiCalls = []
  const mock = vi.fn(async (url) => {
    if (String(url).includes('scholarships-snapshot.json')) {
      return { ok: true, status: 200, json: async () => SNAPSHOT }
    }
    apiCalls.push(String(url))
    return { ok: false, status: 404, json: async () => ({ detail: 'not found' }) }
  })
  vi.stubGlobal('fetch', mock)
  return apiCalls
}

// The snapshot is a module-level cache, so each test has to start from an
// unloaded one or the first test's data serves the rest.
beforeEach(() => {
  clearSnapshotCache()
  currentSearch = ''
})

const field = (id) => document.getElementById(id)

describe('catalogue state is addressable', () => {
  it('renders the search term that arrived in the URL', async () => {
    stubSnapshotFetch()
    renderCatalogue(<ScholarshipList />, '/scholarships?q=kth')

    expect(await screen.findByPlaceholderText('Search scholarships...')).toHaveValue('kth')
    // And only the matching record is shown.
    await waitFor(() => {
      expect(screen.getByText('KTH India Scholarship')).toBeInTheDocument()
    })
  })

  it('renders a filter that arrived in the URL', async () => {
    stubSnapshotFetch()
    renderCatalogue(<ScholarshipList />, '/scholarships?country=Singapore')

    await waitFor(() => {
      expect(screen.getByText('NUS Research Scholarship')).toBeInTheDocument()
    })
    expect(field('scholarship-country')).toHaveValue('Singapore')
    // The unfiltered records are not rendered alongside it.
    expect(screen.queryByText('KTH India Scholarship')).not.toBeInTheDocument()
  })

  it('renders the study level and region that arrived in the URL', async () => {
    stubSnapshotFetch()
    // Record 1 is master's-eligible and in Europe, so both filters include it.
    renderCatalogue(<ScholarshipList />, '/scholarships?level=master&region=Europe')

    expect(field('scholarship-level')).toHaveValue('master')
    expect(field('scholarship-region')).toHaveValue('Europe')
    await waitFor(() => {
      expect(screen.getByText('KTH India Scholarship')).toBeInTheDocument()
    })
    // Record 3 is bachelor's and in North America, so both filters exclude it.
    expect(screen.queryByText('Another USA Scholarship')).not.toBeInTheDocument()
  })

  it('renders the sort that arrived in the URL', async () => {
    stubSnapshotFetch()
    renderCatalogue(<ScholarshipList />, '/scholarships?sort=name-desc')

    expect(field('scholarship-sort')).toHaveValue('name-desc')
    await screen.findByText('NUS Research Scholarship')
  })

  it('writes a filter change back to the URL', async () => {
    stubSnapshotFetch()
    renderCatalogue(<ScholarshipList />, '/scholarships')
    await screen.findByText('KTH India Scholarship')

    await userEvent.selectOptions(field('scholarship-country'), 'USA')

    await waitFor(() => {
      expect(currentSearch).toContain('country=USA')
    })
    // Nothing else was reset: the same URL keeps whatever else was set, and a
    // fresh render of this address shows the same view.
    expect(screen.queryByText('KTH India Scholarship')).not.toBeInTheDocument()
    expect(await screen.findByText('Another USA Scholarship')).toBeInTheDocument()
  })

  it('writes a search change back to the URL', async () => {
    stubSnapshotFetch()
    renderCatalogue(<ScholarshipList />, '/scholarships')
    await screen.findByText('KTH India Scholarship')

    await userEvent.type(screen.getByPlaceholderText('Search scholarships...'), 'nus')

    await waitFor(() => {
      expect(currentSearch).toContain('q=nus')
    })
    expect(field('scholarship-country')).toHaveValue(NO_FILTER)
  })

  it('preserves a search while a filter changes, rather than resetting everything', async () => {
    // The one-action reset used to be the only way to undo a filter, and it
    // also cleared the search box, the sort and the page.
    stubSnapshotFetch()
    renderCatalogue(<ScholarshipList />, '/scholarships?q=nus&sort=name-asc')
    await screen.findByText('NUS Research Scholarship')

    await userEvent.selectOptions(field('scholarship-region'), 'Asia')

    await waitFor(() => {
      expect(currentSearch).toContain('q=nus')
    })
    expect(currentSearch).toContain('sort=name-asc')
    expect(currentSearch).toContain('region=Asia')
  })

  it('does not reset the page when a page number is chosen', async () => {
    stubSnapshotFetch()
    renderCatalogue(<ScholarshipList />, '/scholarships?page=1')
    await screen.findByText('KTH India Scholarship')

    // A filter change does move to page 1, because page 3 of a one-record
    // result set is an empty page.
    await userEvent.selectOptions(field('scholarship-country'), 'Sweden')

    await waitFor(() => {
      expect(currentSearch).toContain('country=Sweden')
    })
    expect(currentSearch).not.toContain('page=')
  })
})

describe('active filters are individually removable', () => {
  it('shows a chip for each active filter and removes only that one', async () => {
    stubSnapshotFetch()
    renderCatalogue(<ScholarshipList />, '/scholarships?q=nus&country=Singapore&region=Asia')
    await screen.findByText('NUS Research Scholarship')

    const chips = screen.getAllByRole('button', { name: /Remove this filter/i })
    expect(chips.length).toBe(3)

    await userEvent.click(chips[1])

    await waitFor(() => {
      expect(currentSearch).not.toContain('country=Singapore')
    })
    // The other two are untouched.
    expect(currentSearch).toContain('q=nus')
    expect(currentSearch).toContain('region=Asia')
  })

  it('shows no chip for an unfiltered view', async () => {
    stubSnapshotFetch()
    renderCatalogue(<ScholarshipList />, '/scholarships')
    await screen.findByText('KTH India Scholarship')

    expect(screen.queryByRole('button', { name: /Remove this filter/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Reset all/i })).not.toBeInTheDocument()
  })

  it('shows no chip for the default sort alone', async () => {
    // "Recommended" is the default, not a choice; a chip whose removal appears
    // to change nothing is noise.
    stubSnapshotFetch()
    renderCatalogue(<ScholarshipList />, '/scholarships')
    await screen.findByText('KTH India Scholarship')

    expect(screen.queryByRole('button', { name: /Recommended/i })).not.toBeInTheDocument()
  })

  it('clears every filter in one action', async () => {
    stubSnapshotFetch()
    renderCatalogue(<ScholarshipList />, '/scholarships?q=nus&country=Singapore&region=Asia&sort=name-asc')
    await screen.findByText('NUS Research Scholarship')

    await userEvent.click(screen.getByRole('button', { name: /Reset all/i }))

    await waitFor(() => {
      expect(currentSearch).toBe('')
    })
    expect(await screen.findByText('KTH India Scholarship')).toBeInTheDocument()
  })
})

describe('empty results are diagnosable', () => {
  it('says what the search did and offers a way out', async () => {
    stubSnapshotFetch()
    renderCatalogue(<ScholarshipList />, '/scholarships?q=zzzznotathing')

    await waitFor(() => {
      expect(screen.getByText('No matching scholarships')).toBeInTheDocument()
    })
    expect(screen.getByText(/every word in/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Reset search and filters/i })).toBeInTheDocument()
  })

  it('offers to remove the last active filter first', async () => {
    stubSnapshotFetch()
    renderCatalogue(<ScholarshipList />, '/scholarships?country=Sweden&level=postdoc')

    await waitFor(() => {
      expect(screen.getByText('No matching scholarships')).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: /^Remove/ })).toBeInTheDocument()
  })
})

describe('every filter control is reachable', () => {
  it('renders a labelled control for each supported filter', async () => {
    stubSnapshotFetch()
    renderCatalogue(<ScholarshipList />, '/scholarships')
    await screen.findByText('KTH India Scholarship')

    // By id, and by the label's own text where the label is unambiguous. The
    // search field's label names every filter, so a label-text query for
    // "Country" also matches it.
    for (const id of [
      'scholarship-search', 'scholarship-country', 'scholarship-level', 'scholarship-region',
      'scholarship-funding', 'scholarship-tuition', 'scholarship-deadline-month',
      'scholarship-status', 'scholarship-sort',
    ]) {
      expect(field(id), `no control with id ${id}`).toBeInTheDocument()
      expect(field(id).tagName === 'INPUT' || field(id).tagName === 'SELECT').toBe(true)
    }
    expect(screen.getByLabelText('Study level')).toBe(field('scholarship-level'))
    expect(screen.getByLabelText('Sort by')).toBe(field('scholarship-sort'))
  })

  it('offers a level bucket for records that state no level, rather than hiding them', async () => {
    // A record naming no level used to be reachable from no level view at all.
    stubSnapshotFetch()
    renderCatalogue(<ScholarshipList />, '/scholarships?level=unspecified')

    const options = [...field('scholarship-level').options].map((o) => o.value)
    expect(options).toContain('unspecified')
    expect(options).toContain('bachelor')
    expect(options).toContain('master')
    expect(options).toContain('doctoral')
    expect(options).toContain('postdoc')
    expect(options).toContain('any')
  })

  it('does not offer a status the public catalogue excludes', async () => {
    stubSnapshotFetch()
    renderCatalogue(<ScholarshipList />, '/scholarships')
    await screen.findByText('KTH India Scholarship')

    const statuses = [...field('scholarship-status').options].map((o) => o.value)
    expect(statuses).not.toContain('closed')
    expect(statuses).toContain('upcoming')
  })

  it('names the `/` shortcut without stealing it from a text field', async () => {
    stubSnapshotFetch()
    renderCatalogue(<ScholarshipList />, '/scholarships')
    const input = await screen.findByPlaceholderText('Search scholarships...')

    // The shortcut must not fire while the user is typing in the field itself.
    await userEvent.type(input, '/')
    expect(input).toHaveValue('/')
  })
})

describe('the snapshot is the only source, and it is labelled', () => {
  it('asks the database for nothing while rendering the catalogue', async () => {
    const apiCalls = stubSnapshotFetch()
    renderCatalogue(<ScholarshipList />, '/scholarships')
    await screen.findByText('KTH India Scholarship')

    // The free-first contract: no catalogue endpoint is consulted.
    const catalogueEndpoints = apiCalls.filter((url) => /\/api\/scholarships/.test(url))
    expect(catalogueEndpoints).toEqual([])
  })
})
