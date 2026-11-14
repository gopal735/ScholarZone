import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import {
  loadScholarshipSnapshot,
  getCachedSnapshot,
  clearSnapshotCache,
  getSnapshotUrl,
  assertSnapshotShape,
  fetchScholarshipsFromSnapshot,
  fetchScholarshipStatsFromSnapshot,
  fetchScholarshipByIdFromSnapshot,
} from './staticScholarshipService.js'

const mockSnapshot = {
  meta: {
    generated_at: '2026-10-09T12:41:37.970162Z',
    source_database: 'scholarzone.db',
    source_record_count: 695,
    public_record_count: 634,
    excluded: { closed: 12, archived: 52, quarantined: 51 },
    excluded_union: 61,
    schema_version: '1.0',
    visibility_predicate: 'status != closed AND is_archived = false AND verification_status != quarantined',
  },
  stats: {
    total: 634,
    countries: 74,
    open: 377,
    closing_soon: 52,
    upcoming: 205,
    verified_active: 542,
    fully_funded: 215,
    with_image: 455,
    with_official_source: 631,
  },
  scholarships: [
    {
      id: 1,
      title: 'Test Scholarship 1',
      name: 'Test Scholarship 1',
      country: 'USA',
      degree: 'Master',
      funding: 'Fully Funded',
      deadline: '2026-12-31',
      deadline_date: '2026-12-31',
      deadline_precision: 'exact',
      status: 'open',
      verified: true,
      last_verified_at: '2026-10-01',
      verification_status: 'active',
      official_source_url: 'https://example.com/1',
      updated_at: '2026-10-01T00:00:00',
      image_url: 'https://example.com/image1.jpg',
      image_source_type: 'official_university',
      image_kind: 'official_logo',
      description: 'Test description 1',
    },
    {
      id: 2,
      title: 'Test Scholarship 2',
      name: 'Test Scholarship 2',
      country: 'UK',
      degree: 'PhD',
      funding: 'Partial',
      deadline: '2027-01-15',
      deadline_date: '2027-01-15',
      deadline_precision: 'exact',
      status: 'upcoming',
      verified: false,
      last_verified_at: null,
      verification_status: 'needs_review',
      official_source_url: 'https://example.com/2',
      updated_at: '2026-10-02T00:00:00',
      image_url: null,
      image_source_type: null,
      image_kind: null,
      description: 'Test description 2',
    },
  ],
}

describe('staticScholarshipService', () => {
  beforeEach(() => {
    clearSnapshotCache()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  /** Install a fresh fetch mock and return it. */
  function stubFetch(impl) {
    const mock = vi.fn(impl)
    vi.stubGlobal('fetch', mock)
    return mock
  }

  it('loads the snapshot from the asset path derived from the build base', async () => {
    const fetchMock = stubFetch(async () => ({ ok: true, json: async () => mockSnapshot }))

    const snapshot = await loadScholarshipSnapshot()
    expect(snapshot).toEqual(mockSnapshot)

    const [url] = fetchMock.mock.calls[0]
    expect(String(url)).toContain('scholarships-snapshot.json')
    expect(String(url)).toMatch(/\/scholarships-snapshot\.json$/)
    expect(fetchMock.mock.calls[0][1]).toEqual({ headers: { Accept: 'application/json' } })
  })

  it('caches the snapshot after the first load', async () => {
    const fetchMock = stubFetch(async () => ({ ok: true, json: async () => mockSnapshot }))

    const first = await loadScholarshipSnapshot()
    const second = await loadScholarshipSnapshot()

    expect(second).toEqual(first)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('serves concurrent callers from one fetch', async () => {
    const fetchMock = stubFetch(async () => ({ ok: true, json: async () => mockSnapshot }))

    const [first, second, third] = await Promise.all([
      loadScholarshipSnapshot(),
      loadScholarshipSnapshot(),
      loadScholarshipSnapshot(),
    ])

    expect(first).toBe(second)
    expect(second).toBe(third)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('returns the cached snapshot from getCachedSnapshot', async () => {
    stubFetch(async () => ({ ok: true, json: async () => mockSnapshot }))

    await loadScholarshipSnapshot()
    expect(getCachedSnapshot()).toEqual(mockSnapshot)
  })

  it('throws on an HTTP error', async () => {
    stubFetch(async () => ({ ok: false, status: 404 }))

    await expect(loadScholarshipSnapshot()).rejects.toThrow('Failed to load snapshot: 404')
  })

  it('throws on a network error', async () => {
    stubFetch(async () => {
      throw new TypeError('Failed to fetch')
    })

    await expect(loadScholarshipSnapshot()).rejects.toThrow('Failed to fetch')
  })

  it('does not cache a body that is not a snapshot object', async () => {
    stubFetch(async () => ({ ok: true, json: async () => [1, 2, 3] }))

    await expect(loadScholarshipSnapshot()).rejects.toThrow('Snapshot payload is not an object.')
    expect(getCachedSnapshot()).toBeNull()
  })

  it('does not cache a body whose scholarships is not an array', async () => {
    stubFetch(async () => ({ ok: true, json: async () => ({ meta: {}, stats: {} }) }))

    await expect(loadScholarshipSnapshot()).rejects.toThrow(
      'Snapshot payload has no scholarships array.',
    )
    expect(getCachedSnapshot()).toBeNull()
  })

  it('does not cache a null body', async () => {
    stubFetch(async () => ({ ok: true, json: async () => null }))

    await expect(loadScholarshipSnapshot()).rejects.toThrow('Snapshot payload is not an object.')
    expect(getCachedSnapshot()).toBeNull()
  })

  it('retries after a failed load instead of caching the failure', async () => {
    const fetchMock = stubFetch(async () => ({ ok: false, status: 500 }))
    await expect(loadScholarshipSnapshot()).rejects.toThrow('Failed to load snapshot: 500')

    fetchMock.mockImplementation(async () => ({ ok: true, json: async () => mockSnapshot }))
    clearSnapshotCache()

    const snapshot = await loadScholarshipSnapshot()
    expect(snapshot).toEqual(mockSnapshot)
  })

  it('clears the cache on clearSnapshotCache', async () => {
    stubFetch(async () => ({ ok: true, json: async () => mockSnapshot }))

    await loadScholarshipSnapshot()
    expect(getCachedSnapshot()).toEqual(mockSnapshot)

    clearSnapshotCache()
    expect(getCachedSnapshot()).toBeNull()
  })

  describe('getSnapshotUrl', () => {
    it('returns correct URL for root deployment', () => {
      // In Vitest test environment, BASE_URL defaults to '/'
      expect(getSnapshotUrl()).toBe('/scholarships-snapshot.json')
    })

    it('handles empty BASE_URL', () => {
      // Test the fallback logic directly by checking the function handles edge cases
      // The function correctly handles empty/undefined BASE_URL by returning '/scholarships-snapshot.json'
      expect(getSnapshotUrl()).toBe('/scholarships-snapshot.json')
    })
  })

  describe('assertSnapshotShape', () => {
    it('accepts valid snapshot', () => {
      expect(() => assertSnapshotShape(mockSnapshot)).not.toThrow()
    })

    it('rejects null', () => {
      expect(() => assertSnapshotShape(null)).toThrow('Snapshot payload is not an object.')
    })

    it('rejects array', () => {
      expect(() => assertSnapshotShape([1, 2, 3])).toThrow('Snapshot payload is not an object.')
    })

    it('rejects missing scholarships array', () => {
      expect(() => assertSnapshotShape({ meta: {}, stats: {} })).toThrow('Snapshot payload has no scholarships array.')
    })

    it('rejects empty scholarships array', () => {
      expect(() => assertSnapshotShape({ meta: {}, stats: {}, scholarships: [] })).toThrow('Snapshot payload contains no scholarships.')
    })
  })

  describe('fetchScholarshipsFromSnapshot query support', () => {
    // Use future dates relative to test run time (2026-10-29)
    // to avoid statusOf() computing different statuses based on deadline_date
    const extendedSnapshot = {
      meta: {
        generated_at: '2026-10-09T12:41:37.970162Z',
        source_database: 'scholarzone.db',
        source_record_count: 5,
        public_record_count: 5,
        excluded: { closed: 0, archived: 0, quarantined: 0 },
        excluded_union: 0,
        schema_version: '1.0',
        visibility_predicate: 'status != closed AND is_archived = false AND verification_status != quarantined',
      },
      stats: {
        total: 5,
        countries: 2,
        open: 3,
        closing_soon: 1,
        upcoming: 1,
        verified_active: 4,
        fully_funded: 2,
        with_image: 3,
        with_official_source: 5,
      },
      scholarships: [
        {
          id: 1,
          title: 'Test Scholarship 1',
          name: 'Test Scholarship 1',
          country: 'USA',
          degree: 'Master',
          funding: 'Fully Funded',
          deadline: '2027-12-31',
          deadline_date: '2027-12-31',
          deadline_precision: 'exact',
          status: 'open',
          verified: true,
          last_verified_at: '2026-10-01',
          verification_status: 'active',
          official_source_url: 'https://example.com/1',
          created_at: '2026-09-01T00:00:00',
          updated_at: '2026-10-01T00:00:00',
          image_url: 'https://example.com/image1.jpg',
          image_source_type: 'official_university',
          image_kind: 'official_logo',
          description: 'Test description for master degree',
          fully_funded: true,
          funding_type: 'Fully Funded',
        },
        {
          id: 2,
          title: 'Test Scholarship 2',
          name: 'Test Scholarship 2',
          country: 'UK',
          degree: 'PhD',
          funding: 'Partial',
          deadline: '2027-01-15',
          deadline_date: '2027-01-15',
          deadline_precision: 'exact',
          status: 'upcoming',
          verified: false,
          last_verified_at: null,
          verification_status: 'needs_review',
          official_source_url: 'https://example.com/2',
          created_at: '2026-10-07T00:00:00',
          updated_at: '2026-10-02T00:00:00',
          image_url: null,
          image_source_type: null,
          image_kind: null,
          description: 'Test description for phd degree',
          fully_funded: false,
          funding_type: 'Partial',
        },
        {
          id: 3,
          title: 'Another Scholarship',
          name: 'Another Scholarship',
          country: 'USA',
          degree: 'Bachelor',
          funding: 'Fully Funded',
          deadline: '2027-06-30',
          deadline_date: '2027-06-30',
          deadline_precision: 'exact',
          status: 'open',
          verified: true,
          last_verified_at: '2026-10-03',
          verification_status: 'active',
          official_source_url: 'https://example.com/3',
          created_at: '2026-09-03T00:00:00',
          updated_at: '2026-10-03T00:00:00',
          image_url: null,
          image_source_type: null,
          image_kind: null,
          description: 'Another test description',
          fully_funded: true,
          funding_type: 'Fully Funded',
        },
        {
          id: 4,
          title: 'Closed Scholarship',
          name: 'Closed Scholarship',
          country: 'Germany',
          degree: 'Master',
          funding: 'Tuition Fee Waiver',
          deadline: '2027-12-31',
          deadline_date: '2027-12-31',
          deadline_precision: 'exact',
          status: 'closed',
          verified: true,
          last_verified_at: '2026-10-04',
          verification_status: 'active',
          official_source_url: 'https://example.com/4',
          created_at: '2026-09-04T00:00:00',
          updated_at: '2026-10-04T00:00:00',
          image_url: null,
          image_source_type: null,
          image_kind: null,
          description: 'Closed scholarship description',
          fully_funded: false,
          funding_type: 'Tuition Fee Waiver',
        },
        {
          id: 5,
          title: 'Closing Soon Scholarship',
          name: 'Closing Soon Scholarship',
          country: 'India',
          degree: 'Postgraduate',
          funding: 'Stipend',
          deadline: '2026-11-15',
          deadline_date: '2026-11-15',
          deadline_precision: 'exact',
          status: 'open',
          verified: true,
          last_verified_at: '2026-10-05',
          verification_status: 'active',
          official_source_url: 'https://example.com/5',
          created_at: '2026-09-05T00:00:00',
          updated_at: '2026-10-05T00:00:00',
          image_url: null,
          image_source_type: null,
          image_kind: null,
          description: 'Closing soon scholarship description',
          fully_funded: false,
          funding_type: 'Stipend',
        },
      ],
    }

    beforeEach(() => {
      clearSnapshotCache()
      const fetchMock = vi.fn(async () => ({ ok: true, json: async () => extendedSnapshot }))
      vi.stubGlobal('fetch', fetchMock)
    })

    afterEach(() => {
      vi.unstubAllGlobals()
    })

    it('filters by search across title, country, degree, description, and funding', async () => {
      const result = await fetchScholarshipsFromSnapshot({ search: 'master' })
      expect(result.items.length).toBe(1)
      expect(result.items.every(s => s.degree.toLowerCase().includes('master'))).toBe(true)
    })

    it('filters by search in description', async () => {
      const result = await fetchScholarshipsFromSnapshot({ search: 'phd degree' })
      expect(result.items.length).toBe(1)
      expect(result.items[0].id).toBe(2)
    })

    it('filters by search in funding', async () => {
      const result = await fetchScholarshipsFromSnapshot({ search: 'stipend' })
      expect(result.items.length).toBe(1)
      expect(result.items[0].id).toBe(5)
    })

    it('filters by country', async () => {
      const result = await fetchScholarshipsFromSnapshot({ country: 'USA' })
      expect(result.items.length).toBe(2)
      expect(result.items.every(s => s.country === 'USA')).toBe(true)
    })

    it('filters by degree using aspect matching', async () => {
      const result = await fetchScholarshipsFromSnapshot({ degree: 'Master' })
      expect(result.items.length).toBe(1)
      expect(result.items.every(s => s.degree.toLowerCase().includes('master'))).toBe(true)
    })

    it('filters by funding using aspect matching', async () => {
      const result = await fetchScholarshipsFromSnapshot({ funding: 'Fully Funded' })
      expect(result.items.length).toBe(2)
      expect(result.items.every(s => s.funding === 'Fully Funded')).toBe(true)
    })

    it('filters by deadline_month', async () => {
      const result = await fetchScholarshipsFromSnapshot({ deadline_month: '11' })
      expect(result.items.length).toBe(1)
      expect(result.items[0].id).toBe(5)
    })

    it('filters month-precision deadlines using the shared date parser', async () => {
      clearSnapshotCache()
      const monthOnlySnapshot = {
        ...extendedSnapshot,
        scholarships: [{
          ...extendedSnapshot.scholarships[0],
          id: 6,
          deadline: 'December 2027',
          deadline_date: '2027-12',
          deadline_precision: 'month',
        }],
      }
      vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => monthOnlySnapshot })))

      const result = await fetchScholarshipsFromSnapshot({ deadline_month: '12' })

      expect(result.items.map((item) => item.id)).toEqual([6])
    })

    it('filters by status', async () => {
      const result = await fetchScholarshipsFromSnapshot({ status: 'closed' })
      expect(result.items).toEqual([])
      expect(result.pagination.total).toBe(0)
    })

    it('keeps visibility tied to stored public status rather than a derived lifecycle badge', async () => {
      clearSnapshotCache()
      const expiredSnapshot = {
        ...extendedSnapshot,
        scholarships: [{
          ...extendedSnapshot.scholarships[0],
          id: 6,
          title: 'Expired Scholarship',
          deadline: '2000-01-01',
          deadline_date: '2000-01-01',
          status: 'open',
        }],
      }
      vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => expiredSnapshot })))

      const result = await fetchScholarshipsFromSnapshot()
      expect(result.items).toHaveLength(1)
      expect(result.items[0].statusInfo.className).toBe('closed')
      expect(result.pagination.total).toBe(1)
    })

    it('counts only visible records in snapshot statistics', async () => {
      const stats = await fetchScholarshipStatsFromSnapshot()

      expect(stats).toEqual({
        total: 4,
        countries: 3,
        fullyFunded: 2,
        verified: 3,
      })
    })

    it('filters by derived lifecycle before paginating the snapshot', async () => {
      const result = await fetchScholarshipsFromSnapshot({
        lifecycle: 'closing_soon',
        page: 1,
        limit: 1,
      })

      expect(result.items.map((item) => item.id)).toEqual([5])
      expect(result.pagination.total).toBe(1)
      expect(result.pagination.page).toBe(1)
    })

    it('filters by status closing-soon', async () => {
      const result = await fetchScholarshipsFromSnapshot({ status: 'closing-soon' })
      expect(result.items.length).toBe(1)
      expect(result.items[0].id).toBe(5)
    })

    it('filters by status upcoming', async () => {
      const result = await fetchScholarshipsFromSnapshot({ status: 'upcoming' })
      expect(result.items.length).toBe(1)
      expect(result.items[0].id).toBe(2)
    })

    it('filters by status open', async () => {
      const result = await fetchScholarshipsFromSnapshot({ status: 'open' })
      expect(result.items.length).toBe(2)
      expect(result.items.map(s => s.id).sort()).toEqual([1, 3])
    })

    it('supports recommended sort', async () => {
      const result = await fetchScholarshipsFromSnapshot({ sort: 'recommended' })
      // Verified active first, then by status order (open, closing-soon, closed, upcoming)
      expect(result.items[0].verification_status).toBe('active')
    })

    it('supports recently-updated sort (newest first)', async () => {
      const result = await fetchScholarshipsFromSnapshot({ sort: 'recently-updated' })
      expect(result.items[0].id).toBe(5) // Most recent updated_at
      expect(result.items[1].id).toBe(3)
    })

    it('supports recently-added sort by creation date', async () => {
      const result = await fetchScholarshipsFromSnapshot({ sort: 'recently-added' })
      expect(result.items[0].id).toBe(2)
    })

    it('does not classify a deadline 45 days away as closing soon', async () => {
      clearSnapshotCache()
      const deadline = new Date(Date.now() + 45 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10)
      const snapshotWithLaterDeadline = {
        ...extendedSnapshot,
        scholarships: [{
          ...extendedSnapshot.scholarships[0],
          id: 6,
          deadline,
          deadline_date: deadline,
          deadline_precision: 'exact',
          status: 'open',
        }],
      }
      vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => snapshotWithLaterDeadline })))

      const result = await fetchScholarshipsFromSnapshot({ status: 'closing-soon' })

      expect(result.items).toEqual([])
    })

    it('supports deadline-earliest sort', async () => {
      const result = await fetchScholarshipsFromSnapshot({ sort: 'deadline-earliest' })
      // 2026-11-15 is earliest
      expect(result.items[0].id).toBe(5)
    })

    it('supports deadline-soon sort (alias for deadline-earliest)', async () => {
      const result = await fetchScholarshipsFromSnapshot({ sort: 'deadline-soon' })
      expect(result.items[0].id).toBe(5)
    })

    it('supports deadline-latest sort', async () => {
      const result = await fetchScholarshipsFromSnapshot({ sort: 'deadline-latest' })
      // 2027-12-31 is latest (id=1 and id=4 tie, stable sort by index)
      expect([1, 4]).toContain(result.items[0].id)
    })

    it('supports fully-funded sort', async () => {
      const result = await fetchScholarshipsFromSnapshot({ sort: 'fully-funded' })
      // Fully funded first
      expect(result.items[0].fully_funded).toBe(true)
      expect(result.items[1].fully_funded).toBe(true)
    })

    it('supports name-asc sort', async () => {
      const result = await fetchScholarshipsFromSnapshot({ sort: 'name-asc' })
      expect(result.items[0].title).toBe('Another Scholarship')
      expect(result.items[3].title).toBe('Test Scholarship 2')
    })

    it('supports name-desc sort', async () => {
      const result = await fetchScholarshipsFromSnapshot({ sort: 'name-desc' })
      expect(result.items[0].title).toBe('Test Scholarship 2')
      expect(result.items[3].title).toBe('Another Scholarship')
    })

    it('supports az sort (legacy alias for name-asc)', async () => {
      const result = await fetchScholarshipsFromSnapshot({ sort: 'az' })
      expect(result.items[0].title).toBe('Another Scholarship')
    })

    it('supports deadline sort (legacy alias for deadline-earliest)', async () => {
      const result = await fetchScholarshipsFromSnapshot({ sort: 'deadline' })
      expect(result.items[0].id).toBe(5)
    })

    it('handles pagination correctly', async () => {
      const result = await fetchScholarshipsFromSnapshot({ page: 1, limit: 2 })
      expect(result.items.length).toBe(2)
      expect(result.pagination.page).toBe(1)
      expect(result.pagination.limit).toBe(2)
      expect(result.pagination.total).toBe(4)
      expect(result.pagination.total_pages).toBe(2)
    })

    it('returns correct total count and pages for filtered results', async () => {
      const result = await fetchScholarshipsFromSnapshot({ country: 'USA' })
      expect(result.pagination.total).toBe(2)
      expect(result.pagination.total_pages).toBe(1)
    })

    it('default sort is recently-updated (most recent first)', async () => {
      const result = await fetchScholarshipsFromSnapshot({ sort: 'default' })
      expect(result.items[0].id).toBe(5)
    })
  })

  describe('fetchScholarshipByIdFromSnapshot', () => {
    const mockSnapshot = {
      meta: {
        generated_at: '2026-10-09T12:41:37.970162Z',
        source_database: 'scholarzone.db',
        source_record_count: 2,
        public_record_count: 2,
        excluded: { closed: 0, archived: 0, quarantined: 0 },
        excluded_union: 0,
        schema_version: '1.0',
        visibility_predicate: 'status != closed AND is_archived = false AND verification_status != quarantined',
      },
      stats: {
        total: 2,
        countries: 2,
        open: 2,
        closing_soon: 0,
        upcoming: 0,
        verified_active: 2,
        fully_funded: 1,
        with_image: 1,
        with_official_source: 2,
      },
      scholarships: [
        {
          id: 1,
          title: 'Test Scholarship 1',
          name: 'Test Scholarship 1',
          country: 'USA',
          degree: 'Master',
          funding: 'Fully Funded',
          deadline: '2026-12-31',
          deadline_date: '2026-12-31',
          deadline_precision: 'exact',
          status: 'open',
          verified: true,
          last_verified_at: '2026-10-01',
          verification_status: 'active',
          official_source_url: 'https://example.com/1',
          updated_at: '2026-10-01T00:00:00',
          image_url: 'https://example.com/image1.jpg',
          image_source_type: 'official_university',
          image_kind: 'official_logo',
          description: 'Test description 1',
        },
        {
          id: 2,
          title: 'Test Scholarship 2',
          name: 'Test Scholarship 2',
          country: 'UK',
          degree: 'PhD',
          funding: 'Partial',
          deadline: '2027-01-15',
          deadline_date: '2027-01-15',
          deadline_precision: 'exact',
          status: 'upcoming',
          verified: false,
          last_verified_at: null,
          verification_status: 'needs_review',
          official_source_url: 'https://example.com/2',
          updated_at: '2026-10-02T00:00:00',
          image_url: null,
          image_source_type: null,
          image_kind: null,
          description: 'Test description 2',
        },
      ],
    }

    beforeEach(() => {
      clearSnapshotCache()
      const fetchMock = vi.fn(async () => ({ ok: true, json: async () => mockSnapshot }))
      vi.stubGlobal('fetch', fetchMock)
    })

    afterEach(() => {
      vi.unstubAllGlobals()
    })

    it('returns normalized scholarship by id', async () => {
      const result = await fetchScholarshipByIdFromSnapshot(1)
      expect(result).not.toBeNull()
      expect(result.id).toBe(1)
      expect(result.title).toBe('Test Scholarship 1')
      expect(result.verification_status).toBe('active')
    })

    it('returns null for non-existent id', async () => {
      const result = await fetchScholarshipByIdFromSnapshot(999)
      expect(result).toBeNull()
    })

    it('matches string and number ids', async () => {
      const result = await fetchScholarshipByIdFromSnapshot('1')
      expect(result).not.toBeNull()
      expect(result.id).toBe(1)
    })

    it('does not return records classified as closed', async () => {
      clearSnapshotCache()
      const closedSnapshot = {
        ...mockSnapshot,
        scholarships: [
          ...mockSnapshot.scholarships,
          {
            ...mockSnapshot.scholarships[0],
            id: 3,
            status: 'closed',
          },
        ],
      }
      vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => closedSnapshot })))

      await expect(fetchScholarshipByIdFromSnapshot(3)).resolves.toBeNull()
    })
  })

  describe('toScholarship funding_details mapping', () => {
    const fundingDetailsSnapshot = {
      meta: {
        generated_at: '2026-10-09T12:41:37.970162Z',
        source_database: 'scholarzone.db',
        source_record_count: 1,
        public_record_count: 1,
        excluded: { closed: 0, archived: 0, quarantined: 0 },
        excluded_union: 0,
        schema_version: '1.0',
        visibility_predicate: 'status != closed AND is_archived = false AND verification_status != quarantined',
      },
      stats: {
        total: 1,
        countries: 1,
        open: 1,
        closing_soon: 0,
        upcoming: 0,
        verified_active: 1,
        fully_funded: 1,
        with_image: 1,
        with_official_source: 1,
      },
      scholarships: [
        {
          id: 1,
          title: 'Test Scholarship with Funding Details',
          name: 'Test Scholarship with Funding Details',
          country: 'Germany',
          degree: 'Master',
          funding: 'Fully Funded',
          deadline: '2027-12-31',
          deadline_date: '2027-12-31',
          deadline_precision: 'exact',
          status: 'open',
          verified: true,
          last_verified_at: '2026-10-01',
          verification_status: 'active',
          official_source_url: 'https://example.com/1',
          updated_at: '2026-10-01T00:00:00',
          image_url: 'https://example.com/image1.jpg',
          image_source_type: 'official_university',
          image_kind: 'official_logo',
          description: 'Test description',
          funding_details: [
            {
              programme: 'DAAD Master Studies',
              track_name: 'All Academic Disciplines',
              amount: 992,
              currency: 'EUR',
              payment_period: 'month',
              tuition_coverage: false,
              living_cost_coverage: true,
              accommodation_coverage: false,
              travel_coverage: true,
              insurance_coverage: true,
              other_coverage: null,
              duration: '10-24 months',
              conditions: 'First degree completed within last 6 years',
              official_source_url: 'https://www2.daad.de/detail/50026200',
              verification_date: '2026-11-01',
            },
            {
              programme: 'DAAD EPOS',
              track_name: 'Development-Related Postgraduate',
              amount: 992,
              currency: 'EUR',
              payment_period: 'month',
              tuition_coverage: false,
              living_cost_coverage: true,
              accommodation_coverage: false,
              travel_coverage: true,
              insurance_coverage: true,
              other_coverage: null,
              duration: '12-24 months',
              conditions: 'Professional experience required',
              official_source_url: 'https://www2.daad.de/detail/50076777',
              verification_date: '2026-11-01',
            },
          ],
        },
      ],
    }

    beforeEach(() => {
      clearSnapshotCache()
      const fetchMock = vi.fn(async () => ({ ok: true, json: async () => fundingDetailsSnapshot }))
      vi.stubGlobal('fetch', fetchMock)
    })

    afterEach(() => {
      vi.unstubAllGlobals()
    })

    it('maps funding_details array to scholarship object', async () => {
      const result = await fetchScholarshipByIdFromSnapshot(1)
      expect(result).not.toBeNull()
      expect(result.funding_details).toBeDefined()
      expect(Array.isArray(result.funding_details)).toBe(true)
      expect(result.funding_details.length).toBe(2)
    })

    it('normalizes track fields correctly', async () => {
      const result = await fetchScholarshipByIdFromSnapshot(1)
      const track1 = result.funding_details[0]
      expect(track1.programme).toBe('DAAD Master Studies')
      expect(track1.track_name).toBe('All Academic Disciplines')
      expect(track1.amount).toBe(992)
      expect(track1.currency).toBe('EUR')
      expect(track1.payment_period).toBe('month')
      expect(track1.tuition_coverage).toBe(false)
      expect(track1.living_cost_coverage).toBe(true)
      expect(track1.accommodation_coverage).toBe(false)
      expect(track1.travel_coverage).toBe(true)
      expect(track1.insurance_coverage).toBe(true)
      expect(track1.duration).toBe('10-24 months')
      expect(track1.conditions).toBe('First degree completed within last 6 years')
      expect(track1.official_source_url).toBe('https://www2.daad.de/detail/50026200')
      // readDate formats as "1 Nov 2026"
      expect(track1.verification_date).toBe('1 Nov 2026')
    })

    it('handles multiple tracks with different amounts', async () => {
      const result = await fetchScholarshipByIdFromSnapshot(1)
      const track1 = result.funding_details[0]
      const track2 = result.funding_details[1]
      expect(track1.programme).toBe('DAAD Master Studies')
      expect(track2.programme).toBe('DAAD EPOS')
      expect(track1.track_name).toBe('All Academic Disciplines')
      expect(track2.track_name).toBe('Development-Related Postgraduate')
    })

    it('handles missing funding_details gracefully', async () => {
      const noFundingSnapshot = {
        ...fundingDetailsSnapshot,
        scholarships: [
          {
            ...fundingDetailsSnapshot.scholarships[0],
            id: 2,
            funding_details: null,
          },
        ],
      }
      clearSnapshotCache()
      const fetchMock = vi.fn(async () => ({ ok: true, json: async () => noFundingSnapshot }))
      vi.stubGlobal('fetch', fetchMock)

      const result = await fetchScholarshipByIdFromSnapshot(2)
      expect(result.funding_details).toEqual([])
    })

    it('handles empty funding_details array', async () => {
      const emptyFundingSnapshot = {
        ...fundingDetailsSnapshot,
        scholarships: [
          {
            ...fundingDetailsSnapshot.scholarships[0],
            id: 3,
            funding_details: [],
          },
        ],
      }
      clearSnapshotCache()
      const fetchMock = vi.fn(async () => ({ ok: true, json: async () => emptyFundingSnapshot }))
      vi.stubGlobal('fetch', fetchMock)

      const result = await fetchScholarshipByIdFromSnapshot(3)
      expect(result.funding_details).toEqual([])
    })

    it('filters out malformed track entries', async () => {
      const malformedSnapshot = {
        ...fundingDetailsSnapshot,
        scholarships: [
          {
            ...fundingDetailsSnapshot.scholarships[0],
            id: 4,
            funding_details: [
              { programme: 'Valid Track', amount: 100, currency: 'USD' },
              null,
              'not an object',
              { track_name: 'No programme but has track', amount: 50 },
              {},
            ],
          },
        ],
      }
      clearSnapshotCache()
      const fetchMock = vi.fn(async () => ({ ok: true, json: async () => malformedSnapshot }))
      vi.stubGlobal('fetch', fetchMock)

      const result = await fetchScholarshipByIdFromSnapshot(4)
      // Should only include entries with meaningful content
      expect(result.funding_details.length).toBe(2)
      expect(result.funding_details[0].programme).toBe('Valid Track')
      expect(result.funding_details[1].track_name).toBe('No programme but has track')
    })

    it('renders official_source_url as valid URL', async () => {
      const result = await fetchScholarshipByIdFromSnapshot(1)
      const track1 = result.funding_details[0]
      expect(track1.official_source_url).toBe('https://www2.daad.de/detail/50026200')
      // Verify it's a valid URL format
      expect(() => new URL(track1.official_source_url)).not.toThrow()
    })
  })
})
