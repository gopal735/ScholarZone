import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import {
  loadScholarshipSnapshot,
  getCachedSnapshot,
  clearSnapshotCache,
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

    // The URL is resolved against Vite's base rather than hardcoded to '/',
    // so it is correct on a deployment served from a repository subpath as
    // well as one served from the domain root.
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

    // A second, successful attempt is allowed rather than being permanently
    // short-circuited by the failed one.
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
})
