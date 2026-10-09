import { describe, it, expect, beforeEach, vi } from 'vitest'
import { loadScholarshipSnapshot, getCachedSnapshot, clearSnapshotCache } from './staticScholarshipService.js'

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
    vi.resetAllMocks()
    // @ts-ignore - Vitest provides global fetch mock
    globalThis.fetch = vi.fn()
  })

  it('loads snapshot from /scholarships-snapshot.json', async () => {
    // @ts-ignore
    globalThis.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockSnapshot,
    })

    const snapshot = await loadScholarshipSnapshot()
    expect(snapshot).toEqual(mockSnapshot)
    // @ts-ignore
    expect(globalThis.fetch).toHaveBeenCalledWith('/scholarships-snapshot.json', {
      headers: { Accept: 'application/json' },
    })
  })

  it('caches snapshot after first load', async () => {
    // @ts-ignore
    globalThis.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockSnapshot,
    })

    await loadScholarshipSnapshot()
    const cached = await loadScholarshipSnapshot()

    expect(cached).toEqual(mockSnapshot)
    // @ts-ignore
    expect(globalThis.fetch).toHaveBeenCalledTimes(1)
  })

  it('returns cached snapshot from getCachedSnapshot', async () => {
    // @ts-ignore
    globalThis.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockSnapshot,
    })

    await loadScholarshipSnapshot()
    const cached = getCachedSnapshot()

    expect(cached).toEqual(mockSnapshot)
  })

  it('throws on fetch failure', async () => {
    // @ts-ignore
    globalThis.fetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
    })

    await expect(loadScholarshipSnapshot()).rejects.toThrow('Failed to load snapshot: 404')
  })

  it('throws on network error', async () => {
    // @ts-ignore
    globalThis.fetch.mockRejectedValueOnce(new Error('Network error'))

    await expect(loadScholarshipSnapshot()).rejects.toThrow('Network error')
  })

  it('clears cache on clearSnapshotCache', async () => {
    // @ts-ignore
    globalThis.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockSnapshot,
    })

    await loadScholarshipSnapshot()
    expect(getCachedSnapshot()).toEqual(mockSnapshot)

    clearSnapshotCache()
    expect(getCachedSnapshot()).toBeNull()
  })
})