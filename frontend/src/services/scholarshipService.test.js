import { describe, it, expect, beforeEach, vi } from 'vitest'
import { fetchScholarships, fetchScholarshipById, fetchScholarshipStats } from './scholarshipService.js'
import { clearSnapshotCache } from './staticScholarshipService.js'

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
    {
      id: 3,
      title: 'Another USA Scholarship',
      name: 'Another USA Scholarship',
      country: 'USA',
      degree: 'Bachelor',
      funding: 'Fully Funded',
      deadline: '2026-11-30',
      deadline_date: '2026-11-30',
      deadline_precision: 'exact',
      status: 'open',
      verified: true,
      last_verified_at: '2026-09-15',
      verification_status: 'active',
      official_source_url: 'https://example.com/3',
      updated_at: '2026-09-20T00:00:00',
      image_url: 'https://example.com/image3.jpg',
      image_source_type: 'official_government',
      image_kind: 'program_image',
      description: 'Test description 3',
    },
  ],
}

describe('scholarshipService with snapshot fallback', () => {
  beforeEach(() => {
    clearSnapshotCache()
    vi.resetAllMocks()
    // @ts-ignore - Vitest provides global fetch mock
    globalThis.fetch = vi.fn()
  })

  it('returns API data when API succeeds', async () => {
    // @ts-ignore
    globalThis.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        items: [{ id: 1, title: 'API Scholarship', country: 'USA' }],
        pagination: { page: 1, limit: 12, total: 1, total_pages: 1 },
      }),
    })

    const result = await fetchScholarships({})
    expect(result.items).toHaveLength(1)
    expect(result.items[0].title).toBe('API Scholarship')
    expect(result.source).toBe('api')
  })

  it('falls back to snapshot on network error', async () => {
    // @ts-ignore
    globalThis.fetch
      .mockRejectedValueOnce(new TypeError('Network error'))
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockSnapshot,
      })

    const result = await fetchScholarships({})
    expect(result.items).toHaveLength(3)
    expect(result.source).toBe('snapshot')
    expect(result.snapshot_meta).toEqual(mockSnapshot.meta)
  })

  it('falls back to snapshot on HTTP 500', async () => {
    // @ts-ignore
    globalThis.fetch
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({ detail: 'Internal server error' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockSnapshot,
      })

    const result = await fetchScholarships({})
    expect(result.items).toHaveLength(3)
    expect(result.source).toBe('snapshot')
  })

  it('falls back to snapshot on HTTP 503', async () => {
    // @ts-ignore
    globalThis.fetch
      .mockResolvedValueOnce({
        ok: false,
        status: 503,
        json: async () => ({ detail: 'Service unavailable' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockSnapshot,
      })

    const result = await fetchScholarships({})
    expect(result.items).toHaveLength(3)
    expect(result.source).toBe('snapshot')
  })

  it('falls back to snapshot on HTTP 502', async () => {
    // @ts-ignore
    globalThis.fetch
      .mockResolvedValueOnce({
        ok: false,
        status: 502,
        json: async () => ({ detail: 'Bad gateway' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockSnapshot,
      })

    const result = await fetchScholarships({})
    expect(result.items).toHaveLength(3)
    expect(result.source).toBe('snapshot')
  })

  it('does NOT fall back on HTTP 404 - propagates error', async () => {
    // @ts-ignore
    globalThis.fetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({ detail: 'Not found' }),
    })

    await expect(fetchScholarships({})).rejects.toThrow('Not found')
    // Should NOT have tried to load snapshot
    expect(globalThis.fetch).toHaveBeenCalledTimes(1)
  })

  it('does NOT fall back on HTTP 400 - propagates error', async () => {
    // @ts-ignore
    globalThis.fetch.mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: async () => ({ detail: 'Bad request' }),
    })

    await expect(fetchScholarships({})).rejects.toThrow('Bad request')
    expect(globalThis.fetch).toHaveBeenCalledTimes(1)
  })

  it('does NOT fall back on HTTP 401 - propagates error', async () => {
    // @ts-ignore
    globalThis.fetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Unauthorized' }),
    })

    await expect(fetchScholarships({})).rejects.toThrow('Unauthorized')
    expect(globalThis.fetch).toHaveBeenCalledTimes(1)
  })

  it('does NOT fall back on HTTP 403 - propagates error', async () => {
    // @ts-ignore
    globalThis.fetch.mockResolvedValueOnce({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Forbidden' }),
    })

    await expect(fetchScholarships({})).rejects.toThrow('Forbidden')
    expect(globalThis.fetch).toHaveBeenCalledTimes(1)
  })

  it('does NOT fall back on HTTP 422 - propagates error', async () => {
    // @ts-ignore
    globalThis.fetch.mockResolvedValueOnce({
      ok: false,
      status: 422,
      json: async () => ({ detail: 'Unprocessable entity' }),
    })

    await expect(fetchScholarships({})).rejects.toThrow('Unprocessable entity')
    expect(globalThis.fetch).toHaveBeenCalledTimes(1)
  })

  it('filters scholarships by country from snapshot on 5xx fallback', async () => {
    // @ts-ignore
    globalThis.fetch
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({ detail: 'Server error' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockSnapshot,
      })

    const result = await fetchScholarships({ country: 'USA' })
    expect(result.items).toHaveLength(2)
    expect(result.items.every(s => s.country === 'USA')).toBe(true)
  })

  it('filters scholarships by search from snapshot on 5xx fallback', async () => {
    // @ts-ignore
    globalThis.fetch
      .mockResolvedValueOnce({
        ok: false,
        status: 503,
        json: async () => ({ detail: 'Service unavailable' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockSnapshot,
      })

    const result = await fetchScholarships({ search: 'Another' })
    expect(result.items).toHaveLength(1)
    expect(result.items[0].title).toBe('Another USA Scholarship')
  })

  it('filters scholarships by status from snapshot on 5xx fallback', async () => {
    // @ts-ignore
    globalThis.fetch
      .mockResolvedValueOnce({
        ok: false,
        status: 502,
        json: async () => ({ detail: 'Bad gateway' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockSnapshot,
      })

    const result = await fetchScholarships({ status: 'upcoming' })
    expect(result.items).toHaveLength(1)
    expect(result.items[0].status).toBe('upcoming')
  })

  it('paginates results from snapshot on 5xx fallback', async () => {
    // @ts-ignore
    globalThis.fetch
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({ detail: 'Server error' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockSnapshot,
      })

    const result = await fetchScholarships({ page: 1, limit: 2 })
    expect(result.items).toHaveLength(2)
    expect(result.pagination).toEqual({ page: 1, limit: 2, total: 3, total_pages: 2 })
  })

  it('sorts scholarships by deadline-earliest from snapshot on 5xx fallback', async () => {
    // @ts-ignore
    globalThis.fetch
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({ detail: 'Server error' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockSnapshot,
      })

    const result = await fetchScholarships({ sort: 'deadline-earliest' })
    expect(result.items[0].id).toBe(3) // Nov 30
    expect(result.items[1].id).toBe(1) // Dec 31
    expect(result.items[2].id).toBe(2) // Jan 15
  })

  it('sorts scholarships by name-asc from snapshot on 5xx fallback', async () => {
    // @ts-ignore
    globalThis.fetch
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({ detail: 'Server error' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockSnapshot,
      })

    const result = await fetchScholarships({ sort: 'name-asc' })
    expect(result.items[0].title).toBe('Another USA Scholarship')
    expect(result.items[1].title).toBe('Test Scholarship 1')
    expect(result.items[2].title).toBe('Test Scholarship 2')
  })

  it('fetches scholarship by ID from snapshot on 5xx fallback', async () => {
    // @ts-ignore
    globalThis.fetch
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({ detail: 'Server error' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockSnapshot,
      })

    const result = await fetchScholarshipById(2)
    expect(result.id).toBe(2)
    expect(result.title).toBe('Test Scholarship 2')
  })

  it('throws 404 when scholarship not found in snapshot on 5xx fallback', async () => {
    // @ts-ignore
    globalThis.fetch
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({ detail: 'Server error' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockSnapshot,
      })

    await expect(fetchScholarshipById(999)).rejects.toThrow('Scholarship not found in snapshot')
  })

  it('does NOT fall back to snapshot for fetchScholarshipById on HTTP 404 - propagates 404', async () => {
    // @ts-ignore
    globalThis.fetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({ detail: 'Scholarship not found' }),
    })

    await expect(fetchScholarshipById(1)).rejects.toThrow('Scholarship not found')
    // Should NOT have tried to load snapshot
    expect(globalThis.fetch).toHaveBeenCalledTimes(1)
  })

  it('does NOT resurrect scholarship via snapshot when API returns 404 for that ID', async () => {
    // The ID exists in the snapshot, but the API says 404 (hidden/unavailable)
    // @ts-ignore
    globalThis.fetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({ detail: 'Scholarship not found' }),
    })

    // fetchScholarshipById(1) exists in mockSnapshot but API says 404
    await expect(fetchScholarshipById(1)).rejects.toThrow('Scholarship not found')
    // Should NOT have tried to load snapshot
    expect(globalThis.fetch).toHaveBeenCalledTimes(1)
  })

  it('fetches stats from snapshot on 5xx fallback', async () => {
    // @ts-ignore
    globalThis.fetch
      .mockResolvedValueOnce({
        ok: false,
        status: 503,
        json: async () => ({ detail: 'Service unavailable' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockSnapshot,
      })

    const result = await fetchScholarshipStats()
    expect(result.total).toBe(634)
    expect(result.countries).toBe(74)
    expect(result.source).toBe('snapshot')
    expect(result.snapshot_meta).toEqual(mockSnapshot.meta)
  })

  it('does NOT fall back to snapshot for stats on HTTP 404 - propagates error', async () => {
    // @ts-ignore
    globalThis.fetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({ detail: 'Stats not found' }),
    })

    await expect(fetchScholarshipStats()).rejects.toThrow('Stats not found')
    expect(globalThis.fetch).toHaveBeenCalledTimes(1)
  })

  it('does not expose internal fields from snapshot', async () => {
    // @ts-ignore
    globalThis.fetch
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({ detail: 'Server error' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockSnapshot,
      })

    const result = await fetchScholarships({})
    const item = result.items[0]
    
    // These fields should NOT be in the public response
    expect(item).not.toHaveProperty('verification_notes')
    expect(item).not.toHaveProperty('verified_by')
    expect(item).not.toHaveProperty('next_verification_due')
    expect(item).not.toHaveProperty('archived_at')
    expect(item).not.toHaveProperty('archived_reason')
    expect(item).not.toHaveProperty('auto_delete_candidate_since')
    expect(item).not.toHaveProperty('deletion_protected')
    expect(item).not.toHaveProperty('image_evaluation_status')
    expect(item).not.toHaveProperty('image_evaluated_at')
  })
})