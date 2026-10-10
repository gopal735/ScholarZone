import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import {
  fetchScholarships,
  fetchScholarshipById,
  fetchScholarshipStats,
  CATALOGUE_MODES,
  getCatalogueMode,
  setCatalogueMode,
} from './scholarshipService.js'
import { clearSnapshotCache } from './staticScholarshipService.js'

const mockSnapshot = {
  meta: {
    generated_at: '2026-10-10T12:41:37.970162Z',
    source_database: 'scholarzone.db',
    source_record_count: 695,
    public_record_count: 634,
    excluded: { closed: 12, archived: 52, quarantined: 51 },
    excluded_union: 61,
    schema_version: '1.0',
    visibility_predicate: 'status != closed AND is_archived = false AND verification_status != quarantined',
    // Ordered ID lists, computed by the generator from the same ORDER BY
    // expressions the repository applies to the live list. Each is defined to
    // be exactly what the backend SQL produces for equivalent rows, so a test
    // that passes against this fixture is asserting the live ordering and not
    // a plausible-looking substitute.
    sort_orders: {
      // created_at DESC, id ASC. The narrative is id 2 newest, then 1, then 3.
      'recently-added': [2, 1, 3],
      // is_verified DESC, status priority ASC, updated_at DESC, id ASC.
      // ids 1 and 3 are verified/open; id 1's updated_at is newer.
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

/**
 * The live API path.
 *
 * These tests are for the explicitly opted-in `api` catalogue mode, where the
 * API is tried first and the snapshot is used only when the API genuinely
 * cannot answer. Static mode is the default and is covered by its own describe
 * below, which never contacts the API at all.
 */
describe('scholarshipService live API path (explicit catalogueMode)', () => {
  beforeEach(() => {
    clearSnapshotCache()
    vi.resetAllMocks()
    setCatalogueMode(CATALOGUE_MODES.API)
    // @ts-ignore - Vitest provides global fetch mock
    globalThis.fetch = vi.fn()
  })

  afterEach(() => {
    setCatalogueMode(CATALOGUE_MODES.STATIC)
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
    expect(result.snapshot_meta.generated_at).toBe(mockSnapshot.meta.generated_at)
    // The orderings are omitted from a counts response; the rest of the header
    // is the snapshot's own, unchanged.
    expect(result.snapshot_meta).not.toHaveProperty('sort_orders')
    expect(result.snapshot_meta.source_record_count).toBe(695)
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

/* ------------------------------------------------------------------------
   Cancellation, de-duplication and fallback contract
   Every test below observes behaviour a caller can see: the number of
   network requests issued, which URL was requested, and what each consumer
   resolved or rejected with. Nothing asserts on an internal helper, and
   nothing waits on a timer - concurrency is controlled with an explicit
   deferred promise that the test settles when it wants the next thing to
   happen.
   ---------------------------------------------------------------------- */

/** A promise the test settles by hand, so ordering is never timing-dependent. */
function deferred() {
  let resolve
  let reject
  const promise = new Promise((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

function apiListResponse(items) {
  return {
    ok: true,
    status: 200,
    json: async () => ({
      items,
      pagination: { page: 1, limit: 12, total: items.length, total_pages: 1 },
    }),
  }
}

function apiDetailResponse(item) {
  return { ok: true, status: 200, json: async () => item }
}

function apiStatusResponse(status, detail) {
  return { ok: false, status, json: async () => ({ detail }) }
}

const ABORT_MESSAGE = 'The operation was aborted.'

function expectAbort(promise) {
  return expect(promise).rejects.toThrow(ABORT_MESSAGE)
}

/**
 * Cancellation and de-duplication on the live API path.
 *
 * These pin the fallback decision (a cancelled caller must never be handed
 * snapshot data), the isolation of one consumer's signal from another's
 * request, and the release of the in-flight entry. The same properties are
 * re-proven on the static path in its own describe below.
 */
describe('scholarshipService cancellation and request de-duplication', () => {
  beforeEach(() => {
    // A brand-new mock per test, installed with `vi.stubGlobal` rather than a
    // plain assignment. `restoreMocks: true` in vitest.config.js restores
    // replaced globals after each test, so `vi.unstubAllGlobals()` is the
    // matching teardown and keeps one test's stub from surviving into the
    // next one.
    clearSnapshotCache()
    vi.unstubAllGlobals()
    setCatalogueMode(CATALOGUE_MODES.API)
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    setCatalogueMode(CATALOGUE_MODES.STATIC)
  })

  /* ---------------------------------------------- Caller cancellation ---------------------------------------------- */

  it('an already-aborted signal rejects with AbortError for list requests', async () => {
    const controller = new AbortController()
    controller.abort()

    await expectAbort(fetchScholarships({}, { signal: controller.signal }))
  })

  it('an already-aborted signal rejects with AbortError for detail requests', async () => {
    const controller = new AbortController()
    controller.abort()

    await expectAbort(fetchScholarshipById(1, { signal: controller.signal }))
  })

  it('an already-aborted signal rejects with AbortError for stats requests', async () => {
    const controller = new AbortController()
    controller.abort()

    await expectAbort(fetchScholarshipStats({ signal: controller.signal }))
  })

  it('an already-aborted signal starts no API request (list)', async () => {
    const controller = new AbortController()
    controller.abort()

    await expectAbort(fetchScholarships({}, { signal: controller.signal }))

    // The de-duplication layer must turn the caller away before it reaches
    // the point where a request is created, so the wire is never touched.
    expect(globalThis.fetch).not.toHaveBeenCalled()
  })

  it('an already-aborted signal starts no API request (detail)', async () => {
    const controller = new AbortController()
    controller.abort()

    await expectAbort(fetchScholarshipById(1, { signal: controller.signal }))

    expect(globalThis.fetch).not.toHaveBeenCalled()
  })

  it('an already-aborted signal starts no API request (stats)', async () => {
    const controller = new AbortController()
    controller.abort()

    await expectAbort(fetchScholarshipStats({ signal: controller.signal }))

    expect(globalThis.fetch).not.toHaveBeenCalled()
  })

  it('an already-aborted signal never requests the snapshot (list)', async () => {
    const controller = new AbortController()
    controller.abort()

    await expectAbort(fetchScholarships({}, { signal: controller.signal }))

    expect(globalThis.fetch).not.toHaveBeenCalled()
    const snapshotCalls = globalThis.fetch.mock.calls.filter(
      (call) => String(call[0]).includes('scholarships-snapshot.json'),
    )
    expect(snapshotCalls).toHaveLength(0)
  })

  it('an already-aborted detail request never requests the snapshot', async () => {
    const controller = new AbortController()
    controller.abort()

    await expectAbort(fetchScholarshipById(1, { signal: controller.signal }))

    const snapshotCalls = globalThis.fetch.mock.calls.filter(
      (call) => String(call[0]).includes('scholarships-snapshot.json'),
    )
    expect(snapshotCalls).toHaveLength(0)
  })

  it('an already-aborted stats request never requests the snapshot', async () => {
    const controller = new AbortController()
    controller.abort()

    await expectAbort(fetchScholarshipStats({ signal: controller.signal }))

    const snapshotCalls = globalThis.fetch.mock.calls.filter(
      (call) => String(call[0]).includes('scholarships-snapshot.json'),
    )
    expect(snapshotCalls).toHaveLength(0)
  })

  /* ------------------------------------------- Shared-consumer isolation ------------------------------------------- */

  it('cancelling one list consumer does not cancel another shared consumer', async () => {
    const api = deferred()
    globalThis.fetch.mockReturnValueOnce(api.promise)

    const controller1 = new AbortController()
    const controller2 = new AbortController()

    const first = fetchScholarships({}, { signal: controller1.signal })
    const second = fetchScholarships({}, { signal: controller2.signal })

    controller1.abort()
    await expectAbort(first)

    // The shared request must still be running for the consumer that did not
    // cancel, so nothing has been aborted on the wire.
    api.resolve(apiListResponse([{ id: 1, title: 'Shared Result', country: 'USA' }]))

    const result = await second
    expect(result.source).toBe('api')
    expect(result.items).toHaveLength(1)
    expect(result.items[0].title).toBe('Shared Result')
  })

  it('cancelling one detail consumer does not cancel another shared consumer', async () => {
    const api = deferred()
    globalThis.fetch.mockReturnValueOnce(api.promise)

    const controller1 = new AbortController()
    const controller2 = new AbortController()

    const first = fetchScholarshipById(1, { signal: controller1.signal })
    const second = fetchScholarshipById(1, { signal: controller2.signal })

    controller1.abort()
    await expectAbort(first)

    api.resolve(apiDetailResponse({ id: 1, title: 'Detail Result', country: 'USA' }))

    const result = await second
    expect(result.id).toBe(1)
    expect(result.title).toBe('Detail Result')
  })

  it('cancelling one stats consumer does not cancel another shared consumer', async () => {
    const api = deferred()
    globalThis.fetch.mockReturnValueOnce(api.promise)

    const controller1 = new AbortController()
    const controller2 = new AbortController()

    const first = fetchScholarshipStats({ signal: controller1.signal })
    const second = fetchScholarshipStats({ signal: controller2.signal })

    controller1.abort()
    await expectAbort(first)

    api.resolve(apiDetailResponse({ total: 100, countries: 10 }))

    const result = await second
    expect(result.total).toBe(100)
  })

  it('cancelling the second consumer does not break the first (list)', async () => {
    const api = deferred()
    globalThis.fetch.mockReturnValueOnce(api.promise)

    const controller1 = new AbortController()
    const controller2 = new AbortController()

    const first = fetchScholarships({}, { signal: controller1.signal })
    const second = fetchScholarships({}, { signal: controller2.signal })

    controller2.abort()
    await expectAbort(second)

    api.resolve(apiListResponse([{ id: 7, title: 'Survivor', country: 'UK' }]))

    const result = await first
    expect(result.source).toBe('api')
    expect(result.items[0].title).toBe('Survivor')
  })

  it('cancelling the second consumer does not break the first (detail)', async () => {
    const api = deferred()
    globalThis.fetch.mockReturnValueOnce(api.promise)

    const controller1 = new AbortController()
    const controller2 = new AbortController()

    const first = fetchScholarshipById(4, { signal: controller1.signal })
    const second = fetchScholarshipById(4, { signal: controller2.signal })

    controller2.abort()
    await expectAbort(second)

    api.resolve(apiDetailResponse({ id: 4, title: 'Survivor Detail' }))

    const result = await first
    expect(result.title).toBe('Survivor Detail')
  })

  it('cancelling the second consumer does not break the first (stats)', async () => {
    const api = deferred()
    globalThis.fetch.mockReturnValueOnce(api.promise)

    const controller1 = new AbortController()
    const controller2 = new AbortController()

    const first = fetchScholarshipStats({ signal: controller1.signal })
    const second = fetchScholarshipStats({ signal: controller2.signal })

    controller2.abort()
    await expectAbort(second)

    api.resolve(apiDetailResponse({ total: 55 }))

    const result = await first
    expect(result.total).toBe(55)
  })

  /* -------------- The shared request is not bound to one caller's signal -------------- */

  it('the shared list request is issued without any consumer AbortSignal', async () => {
    globalThis.fetch.mockResolvedValueOnce(apiListResponse([]))

    const controller = new AbortController()
    await fetchScholarships({}, { signal: controller.signal })

    expect(globalThis.fetch).toHaveBeenCalledTimes(1)
    const [, init] = globalThis.fetch.mock.calls[0]
    // Handing one component's signal to fetch would let that component's
    // unmount abort the data another component is still reading.
    expect(init.signal).toBeUndefined()
  })

  it('the shared detail request is issued without any consumer AbortSignal', async () => {
    globalThis.fetch.mockResolvedValueOnce(apiDetailResponse({ id: 9 }))

    const controller = new AbortController()
    await fetchScholarshipById(9, { signal: controller.signal })

    const [, init] = globalThis.fetch.mock.calls[0]
    expect(init.signal).toBeUndefined()
  })

  it('the shared stats request is issued without any consumer AbortSignal', async () => {
    globalThis.fetch.mockResolvedValueOnce(apiDetailResponse({ total: 1 }))

    const controller = new AbortController()
    await fetchScholarshipStats({ signal: controller.signal })

    const [, init] = globalThis.fetch.mock.calls[0]
    expect(init.signal).toBeUndefined()
  })

  /* ------------ Cancellation before, during and after the shared request ------------ */

  it('cancellation immediately after the request is issued does not load the snapshot', async () => {
    const api = deferred()
    globalThis.fetch.mockReturnValueOnce(api.promise)

    const controller = new AbortController()
    const first = fetchScholarships({}, { signal: controller.signal })
    controller.abort()

    await expectAbort(first)

    // The underlying request is allowed to finish for whoever else wants it,
    // but this caller must not receive its outcome.
    api.resolve(apiListResponse([{ id: 1, title: 'Ignored', country: 'USA' }]))
    await api.promise

    expect(globalThis.fetch).toHaveBeenCalledTimes(1)
    expect(String(globalThis.fetch.mock.calls[0][0])).not.toContain('scholarships-snapshot.json')
  })

  it('cancellation is never replaced by a snapshot success', async () => {
    // The API fails, so a fallback would succeed if it were allowed. The
    // cancelled caller must still see AbortError rather than snapshot data.
    globalThis.fetch
      .mockRejectedValueOnce(new TypeError('Network error'))
      .mockResolvedValueOnce({ ok: true, json: async () => mockSnapshot })

    const controller = new AbortController()
    controller.abort()

    await expectAbort(fetchScholarships({}, { signal: controller.signal }))

    expect(globalThis.fetch).not.toHaveBeenCalled()
  })

  it('cancellation is never replaced by a snapshot failure either', async () => {
    // The API fails AND the snapshot fails. The cancelled caller must still
    // receive the AbortError, not the snapshot's error.
    globalThis.fetch
      .mockRejectedValueOnce(new TypeError('Network error'))
      .mockResolvedValueOnce({ ok: false, status: 500 })

    const controller = new AbortController()
    controller.abort()

    await expectAbort(fetchScholarships({}, { signal: controller.signal }))

    expect(globalThis.fetch).not.toHaveBeenCalled()
  })

  it('a cancelled consumer keeps its AbortError when the shared request later fails', async () => {
    const api = deferred()
    globalThis.fetch.mockReturnValueOnce(api.promise)

    const cancelledController = new AbortController()
    const survivorController = new AbortController()

    const cancelled = fetchScholarships({}, { signal: cancelledController.signal })
    // A separate consumer on the same key. It must not be affected by the
    // other caller's cancellation, nor by the failure that follows it.
    const survivor = fetchScholarships({}, { signal: survivorController.signal })

    cancelledController.abort()
    await expectAbort(cancelled)

    // The shared request fails for a reason that WOULD justify a fallback.
    // The cancelled caller has already settled with AbortError, so it is not
    // retrofitted with the network error and never falls back. The survivor
    // gets the network error and does fall back to the snapshot.
    api.reject(new TypeError('Network error'))

    globalThis.fetch.mockResolvedValueOnce({ ok: true, json: async () => mockSnapshot })
    const survivorResult = await survivor
    expect(survivorResult.source).toBe('snapshot')
  })

  it('cancellation does not disturb a later caller for the same key', async () => {
    const api = deferred()
    globalThis.fetch.mockReturnValueOnce(api.promise)

    const cancelledController = new AbortController()
    const survivorController = new AbortController()

    const cancelled = fetchScholarships({}, { signal: cancelledController.signal })
    // A survivor pins the shared request in flight so "later" is unambiguously
    // after the key has been released, rather than merely after a `then` hop.
    const survivor = fetchScholarships({}, { signal: survivorController.signal })

    cancelledController.abort()
    await expectAbort(cancelled)

    // Settle the abandoned request and wait for the survivor to receive it,
    // which guarantees the release has already run.
    api.resolve(apiListResponse([{ id: 1, title: 'Original', country: 'USA' }]))
    await expect((await survivor).items[0].title).toBe('Original')

    globalThis.fetch.mockResolvedValueOnce(
      apiListResponse([{ id: 2, title: 'Fresh Request', country: 'USA' }]),
    )

    const result = await fetchScholarships({})
    expect(result.source).toBe('api')
    expect(result.items[0].title).toBe('Fresh Request')
    expect(globalThis.fetch).toHaveBeenCalledTimes(2)
  })

  /* ------------------------------------------------- In-flight lifecycle ------------------------------------------------- */

  it('concurrent callers sharing a valid key issue one request, not several', async () => {
    globalThis.fetch.mockResolvedValue(apiListResponse([{ id: 1, title: 'Shared', country: 'USA' }]))

    await Promise.all([
      fetchScholarships({ page: 1, limit: 12 }),
      fetchScholarships({ page: 1, limit: 12 }),
      fetchScholarships({ page: 1, limit: 12 }),
    ])

    expect(globalThis.fetch).toHaveBeenCalledTimes(1)
  })

  it('the in-flight entry is released after success', async () => {
    globalThis.fetch.mockResolvedValueOnce(apiListResponse([{ id: 1, title: 'First', country: 'USA' }]))

    const first = await fetchScholarships({})
    expect(first.items[0].title).toBe('First')

    globalThis.fetch.mockResolvedValueOnce(apiListResponse([{ id: 2, title: 'Second', country: 'UK' }]))
    const second = await fetchScholarships({})

    // A fresh request proves the entry was not held after it settled.
    expect(globalThis.fetch).toHaveBeenCalledTimes(2)
    expect(second.items[0].title).toBe('Second')
  })

  it('the in-flight entry is released after failure', async () => {
    globalThis.fetch.mockResolvedValueOnce(apiStatusResponse(500, 'Server error'))

    // Fails, then falls back - so the key must not be left holding a rejected
    // promise for the next caller to inherit.
    globalThis.fetch.mockResolvedValueOnce({ ok: true, json: async () => mockSnapshot })
    const first = await fetchScholarships({})
    expect(first.source).toBe('snapshot')

    globalThis.fetch.mockResolvedValueOnce(apiListResponse([{ id: 3, title: 'After Failure', country: 'DE' }]))
    const second = await fetchScholarships({})

    expect(second.source).toBe('api')
    expect(second.items[0].title).toBe('After Failure')
  })

  it('the in-flight entry is released after the only consumer aborts', async () => {
    const api = deferred()
    globalThis.fetch.mockReturnValueOnce(api.promise)

    const controller = new AbortController()
    const first = fetchScholarships({}, { signal: controller.signal })
    controller.abort()
    await expectAbort(first)

    // While the abandoned request is still pending a new caller joins it,
    // which is correct: the key names a request, not a consumer.
    const joined = fetchScholarships({})
    expect(globalThis.fetch).toHaveBeenCalledTimes(1)

    // Settle it, then wait for the join to be delivered before asserting
    // anything about the key's state.
    api.resolve(apiListResponse([{ id: 1, title: 'Shared', country: 'USA' }]))
    const joinedResult = await joined
    expect(joinedResult.items[0].title).toBe('Shared')

    // Now the key is free, and a later caller gets a fresh request.
    globalThis.fetch.mockResolvedValueOnce(apiListResponse([{ id: 2, title: 'Released', country: 'FR' }]))
    const later = await fetchScholarships({})
    expect(later.items[0].title).toBe('Released')
    expect(globalThis.fetch).toHaveBeenCalledTimes(2)
  })

  it('a rejected shared request does not poison a consumer sharing it later', async () => {
    const api = deferred()
    globalThis.fetch.mockReturnValueOnce(api.promise)

    // Neither caller is cancelled, so both observe the same failure and both
    // fall back. The point is that the failed key is released afterwards
    // rather than holding a rejected entry for the next caller to inherit.
    const one = fetchScholarships({}, { signal: new AbortController().signal })
    const two = fetchScholarships({}, { signal: new AbortController().signal })

    api.reject(new TypeError('Network error'))

    globalThis.fetch.mockResolvedValue({ ok: true, json: async () => mockSnapshot })
    const [firstResult, secondResult] = await Promise.all([one, two])
    expect(firstResult.source).toBe('snapshot')
    expect(secondResult.source).toBe('snapshot')

    // A later caller must get a fresh request, not the rejected entry.
    globalThis.fetch.mockResolvedValueOnce(
      apiListResponse([{ id: 5, title: 'Recovered', country: 'ES' }]),
    )
    const later = await fetchScholarships({})
    expect(later.source).toBe('api')
    expect(later.items[0].title).toBe('Recovered')
  })

  /* --------------------------------------------------- Fallback contract --------------------------------------------------- */

  it('a genuine network TypeError triggers snapshot fallback', async () => {
    globalThis.fetch
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce({ ok: true, json: async () => mockSnapshot })

    const result = await fetchScholarships({})
    expect(result.source).toBe('snapshot')
    expect(result.items).toHaveLength(3)
  })

  it('a recognized TimeoutError triggers snapshot fallback', async () => {
    globalThis.fetch
      .mockRejectedValueOnce(new DOMException('The operation timed out.', 'TimeoutError'))
      .mockResolvedValueOnce({ ok: true, json: async () => mockSnapshot })

    const result = await fetchScholarships({})
    expect(result.source).toBe('snapshot')
    expect(result.items).toHaveLength(3)
  })

  it('a timeout is never confused with a caller cancellation', async () => {
    const controller = new AbortController()
    controller.abort()

    await expectAbort(fetchScholarships({}, { signal: controller.signal }))

    expect(globalThis.fetch).not.toHaveBeenCalled()
  })

  it('an unclassified DOMException does not trigger fallback', async () => {
    globalThis.fetch.mockRejectedValueOnce(new DOMException('Unexpected', 'DataError'))

    await expect(fetchScholarships({})).rejects.toThrow('Unexpected')
    expect(globalThis.fetch).toHaveBeenCalledTimes(1)
  })

  it.each([500, 501, 502, 503, 504, 599])(
    'HTTP %i triggers snapshot fallback',
    async (status) => {
      globalThis.fetch
        .mockResolvedValueOnce(apiStatusResponse(status, `Error ${status}`))
        .mockResolvedValueOnce({ ok: true, json: async () => mockSnapshot })

      const result = await fetchScholarships({})
      expect(result.source).toBe('snapshot')
      expect(result.items).toHaveLength(3)
    },
  )

  it.each([400, 401, 403, 404, 422])(
    'HTTP %i propagates without loading the snapshot',
    async (status) => {
      globalThis.fetch.mockResolvedValueOnce(apiStatusResponse(status, `Error ${status}`))

      await expect(fetchScholarships({})).rejects.toThrow(`Error ${status}`)
      expect(globalThis.fetch).toHaveBeenCalledTimes(1)
      expect(String(globalThis.fetch.mock.calls[0][0])).not.toContain('scholarships-snapshot.json')
    },
  )

  it.each([400, 401, 403, 404, 422])(
    'HTTP %i propagates for a detail request without loading the snapshot',
    async (status) => {
      globalThis.fetch.mockResolvedValueOnce(apiStatusResponse(status, `Error ${status}`))

      await expect(fetchScholarshipById(1)).rejects.toThrow(`Error ${status}`)
      expect(globalThis.fetch).toHaveBeenCalledTimes(1)
    },
  )

  it.each([400, 401, 403, 404, 422])(
    'HTTP %i propagates for a stats request without loading the snapshot',
    async (status) => {
      globalThis.fetch.mockResolvedValueOnce(apiStatusResponse(status, `Error ${status}`))

      await expect(fetchScholarshipStats()).rejects.toThrow(`Error ${status}`)
      expect(globalThis.fetch).toHaveBeenCalledTimes(1)
    },
  )

  it('a detail API 404 is preserved even though the same ID exists in the snapshot', async () => {
    // ID 1 is present in mockSnapshot. A stale snapshot must not resurrect a
    // record the live API says is gone.
    globalThis.fetch.mockResolvedValueOnce(apiStatusResponse(404, 'Scholarship not found'))

    await expect(fetchScholarshipById(1)).rejects.toThrow('Scholarship not found')
    expect(globalThis.fetch).toHaveBeenCalledTimes(1)
  })

  it('a detail API 404 for a string ID is preserved too', async () => {
    // Detail callers arrive from a route parameter, which is a string.
    globalThis.fetch.mockResolvedValueOnce(apiStatusResponse(404, 'Scholarship not found'))

    await expect(fetchScholarshipById('1')).rejects.toThrow('Scholarship not found')
    expect(globalThis.fetch).toHaveBeenCalledTimes(1)
  })

  it('a snapshot loading failure surfaces its own error, not an API error', async () => {
    globalThis.fetch.mockResolvedValueOnce(apiStatusResponse(503, 'Service unavailable'))

    // The fallback itself fails. The snapshot's error is what the caller must
    // see, so a broken snapshot is not hidden behind an API-shaped message.
    globalThis.fetch.mockResolvedValueOnce({ ok: false, status: 404 })

    await expect(fetchScholarships({})).rejects.toThrow('Failed to load snapshot: 404')
  })

  it('a malformed snapshot body is surfaced, not cached as an empty catalogue', async () => {
    globalThis.fetch
      .mockResolvedValueOnce(apiStatusResponse(503, 'Service unavailable'))
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ nope: true }) })

    await expect(fetchScholarships({})).rejects.toThrow(
      'Snapshot payload has no scholarships array.',
    )

    // It must not have been cached: a later attempt is free to retry.
    globalThis.fetch
      .mockResolvedValueOnce(apiStatusResponse(503, 'Service unavailable'))
      .mockResolvedValueOnce({ ok: true, json: async () => mockSnapshot })

    const result = await fetchScholarships({})
    expect(result.source).toBe('snapshot')
  })

  it('a detail 404 from the snapshot is preserved on the fallback path', async () => {
    globalThis.fetch.mockResolvedValueOnce(apiStatusResponse(503, 'Service unavailable'))
    globalThis.fetch.mockResolvedValueOnce({ ok: true, json: async () => mockSnapshot })

    await expect(fetchScholarshipById(999)).rejects.toThrow('Scholarship not found in snapshot')
  })

  it('a detail lookup by string ID resolves from the snapshot', async () => {
    // React Router supplies the id as a string; the snapshot carries ints.
    globalThis.fetch.mockResolvedValueOnce(apiStatusResponse(503, 'Service unavailable'))
    globalThis.fetch.mockResolvedValueOnce({ ok: true, json: async () => mockSnapshot })

    const result = await fetchScholarshipById('2')
    expect(result.id).toBe(2)
    expect(result.title).toBe('Test Scholarship 2')
  })

  /* ------------------- Fallback parity for filtering, sorting and paging ------------------- */

  it('filters by country during fallback', async () => {
    await fallbackList({ country: 'USA' }, (result) => {
      expect(result.items).toHaveLength(2)
      expect(result.items.every((s) => s.country === 'USA')).toBe(true)
    })
  })

  it('filters by degree during fallback', async () => {
    await fallbackList({ degree: 'PhD' }, (result) => {
      expect(result.items).toHaveLength(1)
      expect(result.items[0].id).toBe(2)
    })
  })

  it('filters by funding during fallback', async () => {
    await fallbackList({ funding: 'Fully Funded' }, (result) => {
      expect(result.items).toHaveLength(2)
    })
  })

  it('filters by search during fallback', async () => {
    await fallbackList({ search: 'Another' }, (result) => {
      expect(result.items).toHaveLength(1)
      expect(result.items[0].title).toBe('Another USA Scholarship')
    })
  })

  it('filters by deadline month during fallback', async () => {
    await fallbackList({ deadline_month: 12 }, (result) => {
      expect(result.items.map((s) => s.id)).toEqual([1])
    })
  })

  it('filters by status during fallback', async () => {
    await fallbackList({ status: 'upcoming' }, (result) => {
      expect(result.items).toHaveLength(1)
      expect(result.items[0].status).toBe('upcoming')
    })
  })

  it('paginates during fallback', async () => {
    await fallbackList({ page: 1, limit: 2 }, (result) => {
      expect(result.items).toHaveLength(2)
      expect(result.pagination).toEqual({ page: 1, limit: 2, total: 3, total_pages: 2 })
    })
  })

  it('sorts by deadline-earliest during fallback', async () => {
    await fallbackList({ sort: 'deadline-earliest' }, (result) => {
      expect(result.items.map((s) => s.id)).toEqual([3, 1, 2]) // Nov 30, Dec 31, Jan 15
    })
  })

  it('sorts by deadline-latest during fallback', async () => {
    await fallbackList({ sort: 'deadline-latest' }, (result) => {
      expect(result.items.map((s) => s.id)).toEqual([2, 1, 3]) // Jan 15, Dec 31, Nov 30
    })
  })

  it('places records without a deadline last during fallback', async () => {
    const snapshot = snapshotWith([
      { ...mockSnapshot.scholarships[0], id: 11, deadline_date: null },
      { ...mockSnapshot.scholarships[0], id: 12, deadline_date: '2027-06-01' },
    ])
    globalThis.fetch
      .mockResolvedValueOnce(apiStatusResponse(500, 'Server error'))
      .mockResolvedValueOnce({ ok: true, json: async () => snapshot })

    const result = await fetchScholarships({ sort: 'deadline-earliest' })
    expect(result.items.map((s) => s.id)).toEqual([12, 11])
  })

  it('sorts by name ascending during fallback', async () => {
    await fallbackList({ sort: 'name-asc' }, (result) => {
      expect(result.items.map((s) => s.title)).toEqual([
        'Another USA Scholarship',
        'Test Scholarship 1',
        'Test Scholarship 2',
      ])
    })
  })

  it('ranks unverified records after verified ones using the derived flag', async () => {
    // Record 2 is needs_review; records 1 and 3 are active. Records 1 and 3
    // are both open, so they are separated by the documented id tie-break
    // (the API's `recommended` ordering finishes with `id.asc()`).
    await fallbackList({ sort: 'recommended' }, (result) => {
      expect(result.items.map((s) => s.id)).toEqual([1, 3, 2])
    })
  })

  it('sorts fully-funded using exact equality, matching the API ordering', async () => {
    const snapshot = snapshotWith([
      {
        ...mockSnapshot.scholarships[0],
        id: 21,
        title: 'Qualified funding',
        funding: 'Fully Funded (4-year bond)',
        updated_at: '2026-01-01T00:00:00',
      },
      {
        ...mockSnapshot.scholarships[0],
        id: 22,
        title: 'Exactly fully funded',
        funding: 'fully funded',
        updated_at: '2026-01-01T00:00:00',
      },
      {
        ...mockSnapshot.scholarships[0],
        id: 23,
        title: 'Partially funded',
        funding: 'Partially Funded',
        updated_at: '2026-01-01T00:00:00',
      },
    ])
    globalThis.fetch
      .mockResolvedValueOnce(apiStatusResponse(500, 'Server error'))
      .mockResolvedValueOnce({ ok: true, json: async () => snapshot })

    const result = await fetchScholarships({ sort: 'fully-funded' })
    // Only the exact match is promoted, matching the repository's
    // `lower(funding) == 'fully funded'` ordering predicate.
    expect(result.items.map((s) => s.id)).toEqual([22, 21, 23])
  })

  it('sorts recently-added by the newest available timestamp, deterministically', async () => {
    const snapshot = snapshotWith([
      { ...mockSnapshot.scholarships[0], id: 31, updated_at: '2026-01-01T00:00:00' },
      { ...mockSnapshot.scholarships[0], id: 32, updated_at: '2026-05-01T00:00:00' },
      { ...mockSnapshot.scholarships[0], id: 33, updated_at: '2026-03-01T00:00:00' },
    ])
    globalThis.fetch
      .mockResolvedValueOnce(apiStatusResponse(500, 'Server error'))
      .mockResolvedValueOnce({ ok: true, json: async () => snapshot })

    const result = await fetchScholarships({ sort: 'recently-added' })
    expect(result.items.map((s) => s.id)).toEqual([32, 33, 31])
  })

  it('breaks a sorting tie by id so the order is stable', async () => {
    const snapshot = snapshotWith([
      { ...mockSnapshot.scholarships[0], id: 42, updated_at: '2026-01-01T00:00:00' },
      { ...mockSnapshot.scholarships[0], id: 41, updated_at: '2026-01-01T00:00:00' },
    ])
    globalThis.fetch
      .mockResolvedValueOnce(apiStatusResponse(500, 'Server error'))
      .mockResolvedValueOnce({ ok: true, json: async () => snapshot })

    const result = await fetchScholarships({ sort: 'recently-updated' })
    expect(result.items.map((s) => s.id)).toEqual([41, 42])
  })

  it('ignores an unparseable timestamp rather than ordering by NaN', async () => {
    const snapshot = snapshotWith([
      { ...mockSnapshot.scholarships[0], id: 51, title: 'Bad date', updated_at: 'not-a-date' },
      { ...mockSnapshot.scholarships[0], id: 52, title: 'Good date', updated_at: '2026-02-02T00:00:00' },
    ])
    globalThis.fetch
      .mockResolvedValueOnce(apiStatusResponse(500, 'Server error'))
      .mockResolvedValueOnce({ ok: true, json: async () => snapshot })

    const result = await fetchScholarships({ sort: 'recently-updated' })
    // A record with no usable date sorts last instead of poisoning the
    // comparison, and the tie is then broken by id.
    expect(result.items.map((s) => s.id)).toEqual([52, 51])
  })

  it('serves statistics from the snapshot during fallback', async () => {
    // The mocked snapshot's own stats block is what is served, so the
    // assertion is against that fixture rather than against the record count.
    const stats = { ...mockSnapshot.stats, total: 3, countries: 2, verified_active: 2 }
    globalThis.fetch
      .mockResolvedValueOnce(apiStatusResponse(503, 'Service unavailable'))
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ ...mockSnapshot, stats }),
      })

    const result = await fetchScholarshipStats()
    expect(result.source).toBe('snapshot')
    expect(result.total).toBe(3)
    expect(result.countries).toBe(2)
  })

  it('exposes only the fields the public response schema declares', async () => {
    // The service passes a snapshot record through unchanged; it is the
    // snapshot's job to carry only public fields, and the generator's
    // allowlist is what guarantees that. What is asserted here is the
    // observable promise: a fallback record carries the fields consumers
    // read, and nothing the public schema does not declare.
    globalThis.fetch
      .mockResolvedValueOnce(apiStatusResponse(503, 'Service unavailable'))
      .mockResolvedValueOnce({ ok: true, json: async () => mockSnapshot })

    const result = await fetchScholarships({})
    const item = result.items[0]

    for (const field of [
      'verification_notes',
      'verified_by',
      'next_verification_due',
      'archived_at',
      'archived_reason',
      'auto_delete_candidate_since',
      'deletion_protected',
      'image_evaluation_status',
      'image_evaluated_at',
    ]) {
      expect(item).not.toHaveProperty(field)
    }

    // And the public fields consumers actually read are present.
    for (const field of ['id', 'title', 'country', 'verified', 'verification_status', 'deadline']) {
      expect(item).toHaveProperty(field)
    }
  })
})

/** Fail the API, then serve the mocked snapshot, and assert on the fallback. */
async function fallbackList(query, assert) {
  globalThis.fetch
    .mockResolvedValueOnce(apiStatusResponse(500, 'Server error'))
    .mockResolvedValueOnce({ ok: true, json: async () => mockSnapshot })

  const result = await fetchScholarships({ ...query })
  assert(result)
  return result
}

/**
 * A snapshot carrying the given records and nothing else.
 *
 * `sort_orders` is deliberately dropped. The tests using this helper assert the
 * comparator path - the behaviour a snapshot without a precomputed ordering for
 * the mode falls back to - and inheriting the main fixture's orderings would
 * silently switch them onto the other path. Use `snapshotWithOrders` when the
 * precomputed ordering is what is under test.
 */
function snapshotWith(scholarships) {
  const meta = { ...mockSnapshot.meta }
  delete meta.sort_orders
  delete meta.sort_order_modes
  return { meta, stats: mockSnapshot.stats, scholarships }
}

/**
 * A snapshot carrying the given records AND the given orderings.
 *
 * Both halves are supplied explicitly, because the point of the ordering tests
 * is that a precomputed ordering applies to a set of records the ordering was
 * generated from - and that the service copes when it was not.
 */
function snapshotWithOrders(scholarships, sortOrders) {
  return { meta: { ...mockSnapshot.meta, sort_orders: sortOrders }, stats: mockSnapshot.stats, scholarships }
}

/* ------------------------------------------------------------------------
   Snapshot ordering: the precomputed-order path

   The repository's `_sort_expressions` orders `recently-added` by `created_at`
   and `recommended` by the legacy `is_verified` column. Neither is a public
   field, so before this change the fallback could not reproduce either order:
   `recently-added` came out in a materially different order and `recommended`
   differed on roughly four records in five.

   The fix computes both orderings with the repository's own SQL and stores them
   as ordered ID lists in `meta.sort_orders`. These tests pin that contract, and
   each one fails if the ordering is dropped or approximated again.
   ---------------------------------------------------------------------- */

describe('snapshot ordering uses the precomputed order', () => {
  beforeEach(() => {
    clearSnapshotCache()
    vi.unstubAllGlobals()
    vi.stubGlobal('fetch', vi.fn())
  })

  /** Fail the API, then serve `snapshot`. */
  async function fallbackWith(snapshot, query) {
    // Persistent rather than queued: this is called once per mode in the tests
    // below, and a queue would run dry after the first one. The two requests are
    // told apart by the asset path, because the API URL is absolute.
    globalThis.fetch.mockImplementation(async (url) => {
      if (String(url).includes('scholarships-snapshot.json')) {
        return { ok: true, status: 200, json: async () => snapshot }
      }
      return { ok: false, status: 503, json: async () => ({ detail: 'unavailable' }) }
    })
    return fetchScholarships(query)
  }

  it('recently-added follows the ordering computed from the live sort rule', async () => {
    const result = await fallbackWith(mockSnapshot, { sort: 'recently-added' })

    // The fixture's ordering is created_at DESC, id ASC. Without the ordering,
    // the fallback had to use a timestamp it did have and produced a different
    // list for 632 of 634 records.
    expect(result.items.map((s) => s.id)).toEqual([2, 1, 3])
  })

  it('recommended follows the ordering computed from the live sort rule', async () => {
    const result = await fallbackWith(mockSnapshot, { sort: 'recommended' })
    expect(result.items.map((s) => s.id)).toEqual([1, 3, 2])
  })

  it('an unset sort resolves to the recommended ordering', async () => {
    const result = await fallbackWith(mockSnapshot, {})
    expect(result.items.map((s) => s.id)).toEqual([1, 3, 2])
  })

  it('default follows the recommended ordering', async () => {
    const result = await fallbackWith(mockSnapshot, { sort: 'default' })
    expect(result.items.map((s) => s.id)).toEqual([1, 3, 2])
  })

  it('every mode advertised by the snapshot produces that exact ordering', async () => {
    const expected = {
      'recently-added': [2, 1, 3],
      'recently-updated': [2, 1, 3],
      'deadline-soon': [3, 1, 2],
      'deadline-earliest': [3, 1, 2],
      'deadline-latest': [2, 1, 3],
      'fully-funded': [1, 3, 2],
      'name-asc': [3, 1, 2],
      'name-desc': [2, 1, 3],
    }

    for (const [mode, ids] of Object.entries(expected)) {
      // Separate per mode, so a failure names the mode rather than one of nine.
      const result = await fallbackWith(mockSnapshot, { sort: mode })
      expect(result.items.map((s) => s.id), `sort mode: ${mode}`).toEqual(ids)
    }
  })

  it('an ordering is applied after filtering, not instead of it', async () => {
    // Country USA leaves ids 1 and 3. The full recommended order is [1, 3, 2],
    // so the subset must keep 1 before 3 rather than reverting to insertion or
    // id order.
    const result = await fallbackWith(mockSnapshot, { sort: 'recommended', country: 'USA' })
    expect(result.items.map((s) => s.id)).toEqual([1, 3])
  })

  it('a filtered subset keeps the ordering even when the order disagrees with id', async () => {
    // The ordering puts id 3 first. Restricting the total order to the subset
    // must not collapse to id order, which would silently reorder everything.
    const result = await fallbackWith(mockSnapshot, { sort: 'name-asc', country: 'USA' })
    expect(result.items.map((s) => s.id)).toEqual([3, 1])
  })

  it('a single record survives any ordering', async () => {
    const result = await fallbackWith(mockSnapshot, { sort: 'recently-added', status: 'upcoming' })
    expect(result.items.map((s) => s.id)).toEqual([2])
  })

  it('an empty result set stays empty', async () => {
    const result = await fallbackWith(mockSnapshot, { sort: 'recently-added', country: 'Nowhere' })
    expect(result.items).toEqual([])
    expect(result.pagination.total).toBe(0)
  })

  it('pagination applies after ordering', async () => {
    const result = await fallbackWith(mockSnapshot, { sort: 'recently-updated', page: 2, limit: 1 })
    expect(result.items.map((s) => s.id)).toEqual([1])
    expect(result.pagination).toEqual({ page: 2, limit: 1, total: 3, total_pages: 3 })
  })

  it('a record absent from the ordering is placed last, not discarded', async () => {
    // A snapshot can be stale for a subset of records: the ordering names ids the
    // file no longer ships, and the file ships an id the ordering never saw.
    // Neither may be dropped, and neither may be placed randomly.
    const snapshot = snapshotWithOrders(
      [...mockSnapshot.scholarships, { id: 99, title: 'Not In Order', country: 'Canada', funding: 'Fully Funded', updated_at: '2026-01-01T00:00:00', verified: true, status: 'open' }],
      { 'recently-added': [2, 1, 3, 404] },
    )

    const result = await fallbackWith(snapshot, { sort: 'recently-added' })
    expect(result.items.map((s) => s.id)).toEqual([2, 1, 3, 99])
  })

  it('an ordering that is not a list is ignored rather than throwing', async () => {
    const snapshot = snapshotWithOrders(mockSnapshot.scholarships, { 'recently-added': 'nonsense' })
    const result = await fallbackWith(snapshot, { sort: 'recently-added' })

    // Falls back to the comparator, which uses updated_at when created_at is
    // absent. The important part is that a malformed field cannot 500 the page.
    expect(result.items.length).toBe(3)
    expect(result.source).toBe('snapshot')
  })

  it('an ordering with duplicate ids still yields each record once', async () => {
    const snapshot = snapshotWithOrders(mockSnapshot.scholarships, { 'recently-added': [2, 2, 1, 3, 1] })
    const result = await fallbackWith(snapshot, { sort: 'recently-added' })

    expect(result.items.map((s) => s.id)).toEqual([2, 1, 3])
  })

  it('an ordering of a different length does not truncate the result', async () => {
    const snapshot = snapshotWithOrders(mockSnapshot.scholarships, { 'recently-added': [2] })
    const result = await fallbackWith(snapshot, { sort: 'recently-added' })

    expect(result.items.map((s) => s.id)).toEqual([2, 1, 3])
  })

  it('a snapshot with no orderings at all falls back to the comparators', async () => {
    const result = await fallbackWith(snapshotWith(mockSnapshot.scholarships), { sort: 'recently-added' })

    // The comparator path uses updated_at DESC (created_at is not a public
    // field, so it cannot do better): 2 (Oct 2), 1 (Oct 1), 3 (Sep 20).
    expect(result.items.map((s) => s.id)).toEqual([2, 1, 3])
    expect(result.source).toBe('snapshot')
  })

  it('an unknown sort mode does not crash and resolves to the recommended order', async () => {
    const result = await fallbackWith(mockSnapshot, { sort: 'not-a-real-mode' })
    expect(result.items.map((s) => s.id)).toEqual([1, 3, 2])
  })

  it('the ordering is exposed for transparency but carries no private column', async () => {
    const result = await fallbackWith(mockSnapshot, { sort: 'recently-added' })

    // The orderings are IDs only. `created_at` and `is_verified` are the columns
    // the live ordering is derived from, and neither may appear in the payload -
    // that would widen the public schema to work around a sort mismatch.
    expect(result.snapshot_meta.sort_orders['recently-added']).toEqual([2, 1, 3])
    for (const record of result.items) {
      expect(record).not.toHaveProperty('created_at')
      expect(record).not.toHaveProperty('is_verified')
    }
  })

  it('the "All" sentinel the catalogue controls send is not treated as a filter', async () => {
    // The directory controls send the literal string 'All' when nothing is
    // selected. `request()` strips it before building a URL, so the live API
    // never saw it; the snapshot filter used to match against the word and
    // returned zero records, which turned into a blank homepage the moment the
    // snapshot became the default source.
    serveSnapshotOnly(mockSnapshot)

    const result = await fetchScholarships({
      search: '',
      country: 'All',
      degree: 'All',
      funding: 'All',
      deadline_month: 'All',
      status: 'All',
      sort: 'recommended',
      page: 1,
      limit: 12,
    })

    expect(result.source).toBe('snapshot')
    expect(result.items).toHaveLength(3)
    expect(result.pagination.total).toBe(3)
  })

  it('a blank filter value is not treated as a filter either', async () => {
    serveSnapshotOnly(mockSnapshot)

    const result = await fetchScholarships({ country: '   ', status: '', degree: null })
    expect(result.items).toHaveLength(3)
  })

  it('a real filter still narrows the result', async () => {
    // The fix must not simply disable filtering.
    serveSnapshotOnly(mockSnapshot)

    const byCountry = await fetchScholarships({ country: 'USA' })
    expect(byCountry.items.map((s) => s.id)).toEqual([1, 3])

    const byStatus = await fetchScholarships({ status: 'upcoming' })
    expect(byStatus.items.map((s) => s.id)).toEqual([2])

    const byFunding = await fetchScholarships({ funding: 'Fully Funded' })
    expect(byFunding.items.map((s) => s.id)).toEqual([1, 3])
  })

  it('a filter is applied before the ordering, so ordering is of the subset', async () => {
    serveSnapshotOnly(mockSnapshot)

    const result = await fetchScholarships({ country: 'USA', sort: 'name-asc' })
    expect(result.items.map((s) => s.id)).toEqual([3, 1])
  })

  it('detail and stats requests are unaffected by the ordering change', async () => {
    // Static mode: one snapshot request serves all three operations, and no
    // API request is made at all.
    globalThis.fetch.mockImplementation(async (url) => {
      expect(String(url)).toContain('scholarships-snapshot.json')
      return { ok: true, status: 200, json: async () => mockSnapshot }
    })

    const detail = await fetchScholarshipById(3)
    expect(detail.id).toBe(3)

    const stats = await fetchScholarshipStats()
    expect(stats.total).toBe(634)
    expect(globalThis.fetch).not.toHaveBeenCalledWith(
      expect.stringContaining('/api/'),
      expect.anything(),
    )
  })

  it('a stats response does not carry the list orderings', async () => {
    // The orderings are nine arrays of every public id. They exist to reproduce
    // the API's list ordering, so they belong in a list response - a counts
    // response should not carry the ordering of the whole catalogue with it.
    const result = await fallbackWith(mockSnapshot, {})

    const stats = await fetchScholarshipStats()
    expect(stats.source).toBe('snapshot')
    expect(stats.snapshot_meta).not.toHaveProperty('sort_orders')
    expect(stats.snapshot_meta.sort_order_modes).toBeDefined()
    expect(result.source).toBe('snapshot')
  })

  it('a list response does expose the orderings, because it needs them', async () => {
    const result = await fallbackWith(mockSnapshot, { sort: 'recently-added' })
    expect(result.snapshot_meta.sort_orders['recently-added']).toEqual([2, 1, 3])
  })
})

/** Fail nothing: in static mode no API request is made, so nothing to fail. */
function serveSnapshotOnly(snapshot) {
  globalThis.fetch.mockImplementation(async (url) => {
    if (String(url).includes('scholarships-snapshot.json')) {
      return { ok: true, status: 200, json: async () => snapshot }
    }
    // Any request to the API is a defect in static mode, and this makes it
    // visible rather than silently returning something plausible.
    throw new Error(`Unexpected API request in static mode: ${url}`)
  })
}

/* ------------------------------------------------------------------------
   Static-first: the public catalogue is served from the bundled snapshot

   These tests prove the property the free-tier architecture needs: an
   ordinary public listing, detail or stats request is answered from the
   version-controlled snapshot without contacting the database at all.

   That matters because the free-tier failure was a quota. A request that is
   never made cannot be throttled, cannot be slow, and cannot be the reason a
   page fails - which is the difference between a catalogue that happens to
   work when the database is up and one that works because it does not depend
   on the database.
   ---------------------------------------------------------------------- */

describe('static-first public catalogue', () => {
  beforeEach(() => {
    clearSnapshotCache()
    vi.resetAllMocks()
    setCatalogueMode(CATALOGUE_MODES.STATIC)
    globalThis.fetch = vi.fn()
  })

  afterEach(() => {
    setCatalogueMode(CATALOGUE_MODES.STATIC)
  })

  it('is in static mode by default, without any caller opting in', () => {
    expect(getCatalogueMode()).toBe(CATALOGUE_MODES.STATIC)
  })

  it('a public listing is answered from the snapshot with no API request', async () => {
    serveSnapshotOnly(mockSnapshot)

    const result = await fetchScholarships({ page: 1, limit: 12 })

    expect(result.source).toBe('snapshot')
    expect(result.items).toHaveLength(3)

    const apiCalls = globalThis.fetch.mock.calls.filter(
      (call) => !String(call[0]).includes('scholarships-snapshot.json'),
    )
    expect(apiCalls).toHaveLength(0)
    expect(String(globalThis.fetch.mock.calls[0][0])).toContain('scholarships-snapshot.json')
  })

  it('a public detail lookup is answered from the snapshot with no API request', async () => {
    serveSnapshotOnly(mockSnapshot)

    const detail = await fetchScholarshipById(2)

    expect(detail.id).toBe(2)
    expect(detail.title).toBe('Test Scholarship 2')
    const apiCalls = globalThis.fetch.mock.calls.filter(
      (call) => !String(call[0]).includes('scholarships-snapshot.json'),
    )
    expect(apiCalls).toHaveLength(0)
  })

  it('public statistics are answered from the snapshot with no API request', async () => {
    serveSnapshotOnly(mockSnapshot)

    const stats = await fetchScholarshipStats()

    expect(stats.source).toBe('snapshot')
    expect(stats.total).toBe(634)
    const apiCalls = globalThis.fetch.mock.calls.filter(
      (call) => !String(call[0]).includes('scholarships-snapshot.json'),
    )
    expect(apiCalls).toHaveLength(0)
  })

  it('the whole catalogue is usable with the API entirely unreachable', async () => {
    // The database is over quota and the API is gone. Nothing about the
    // catalogue should change.
    const apiCalls = []
    globalThis.fetch.mockImplementation(async (url) => {
      if (String(url).includes('scholarships-snapshot.json')) {
        return { ok: true, status: 200, json: async () => mockSnapshot }
      }
      apiCalls.push(url)
      throw new TypeError('Failed to fetch')
    })

    const result = await fetchScholarships({ search: 'Scholarship', limit: 50 })
    expect(result.source).toBe('snapshot')
    expect(result.items.length).toBeGreaterThan(0)

    const detail = await fetchScholarshipById('3')
    expect(detail.id).toBe(3)

    const stats = await fetchScholarshipStats()
    expect(stats.total).toBe(634)

    // The API was never touched, so it cannot have been the thing that failed.
    expect(apiCalls).toHaveLength(0)
  })

  it('filtering, sorting and pagination all work without any API request', async () => {
    serveSnapshotOnly(mockSnapshot)

    const byCountry = await fetchScholarships({ country: 'USA' })
    expect(byCountry.items.map((s) => s.id)).toEqual([1, 3])

    const bySort = await fetchScholarships({ sort: 'deadline-earliest' })
    expect(bySort.items.map((s) => s.id)).toEqual([3, 1, 2])

    const pageTwo = await fetchScholarships({ page: 2, limit: 2 })
    expect(pageTwo.items.map((s) => s.id)).toEqual([2])
    expect(pageTwo.pagination).toEqual({ page: 2, limit: 2, total: 3, total_pages: 2 })
  })

  it('an empty result is an empty result, not an error', async () => {
    serveSnapshotOnly(mockSnapshot)

    const result = await fetchScholarships({ search: 'no such scholarship exists' })
    expect(result.items).toEqual([])
    expect(result.pagination.total).toBe(0)
  })

  /* ── Honesty about the data ─────────────────────────────────────── */

  it('the snapshot provenance is exposed, so the UI can disclose it', async () => {
    serveSnapshotOnly(mockSnapshot)

    const result = await fetchScholarships({})
    const meta = result.snapshot_meta

    expect(meta.generated_at).toBeDefined()
    expect(meta.source_database).toBe('scholarzone.db')
    expect(meta.visibility_predicate).toContain('closed')
    // And it says explicitly that the public set is a validation of the
    // local database - not a statement about production.
    expect(meta.source_record_count).toBe(695)
    expect(meta.public_record_count).toBe(634)
  })

  it('verified status is derived, never fabricated', async () => {
    // Record 2 is needs_review. It must not be reported as verified just
    // because a UI badge wants a number of verified records to show.
    serveSnapshotOnly(mockSnapshot)

    const list = await fetchScholarships({ limit: 50 })
    const byId = Object.fromEntries(list.items.map((s) => [s.id, s]))

    expect(byId[2].verified).toBe(false)
    expect(byId[2].verification_status).toBe('needs_review')
    expect(byId[1].verified).toBe(true)
    expect(byId[1].verification_status).toBe('active')

    // The statistic agrees with the records rather than being its own number.
    const stats = await fetchScholarshipStats()
    const derived = list.items.filter((s) => s.verified === true).length
    expect(stats.verified_active).toBeGreaterThanOrEqual(0)
    expect(derived).toBe(2)
  })

  it('only public fields are exposed, with no internal workflow state', async () => {
    serveSnapshotOnly(mockSnapshot)

    const result = await fetchScholarships({})
    for (const item of result.items) {
      for (const field of [
        'verification_notes',
        'verified_by',
        'next_verification_due',
        'is_archived',
        'archived_at',
        'is_verified',
        'created_at',
      ]) {
        expect(item).not.toHaveProperty(field)
      }
      // The official source link is what a student needs to confirm a
      // deadline, so it has to survive into the response.
      expect(item).toHaveProperty('official_source_url')
    }
  })

  it('the notice can tell whether the source was the snapshot or the API', async () => {
    serveSnapshotOnly(mockSnapshot)

    const result = await fetchScholarships({})
    expect(result.source).toBe('snapshot')
    expect(result.snapshot_meta).toBeDefined()
  })

  /* ── Cancellation on the static path ────────────────────────────── */

  it('an already-aborted caller starts no snapshot load', async () => {
    const controller = new AbortController()
    controller.abort()

    await expectAbort(fetchScholarships({}, { signal: controller.signal }))
    expect(globalThis.fetch).not.toHaveBeenCalled()
  })

  it('cancelling one static consumer does not break another', async () => {
    // Two catalogue surfaces mount together. Unmounting one must not cancel
    // the snapshot the other is still reading.
    let resolveSnapshot
    globalThis.fetch.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveSnapshot = resolve
      }),
    )

    const controller1 = new AbortController()
    const controller2 = new AbortController()

    const first = fetchScholarships({}, { signal: controller1.signal })
    const second = fetchScholarships({}, { signal: controller2.signal })

    controller1.abort()
    await expectAbort(first)

    resolveSnapshot({ ok: true, status: 200, json: async () => mockSnapshot })

    const result = await second
    expect(result.source).toBe('snapshot')
    expect(result.items).toHaveLength(3)
  })

  it('a cancelled static consumer does not poison later requests', async () => {
    let resolveSnapshot
    globalThis.fetch.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveSnapshot = resolve
      }),
    )

    const controller = new AbortController()
    const cancelled = fetchScholarships({}, { signal: controller.signal })
    controller.abort()
    await expectAbort(cancelled)

    // Let the abandoned load settle, so the key is released.
    resolveSnapshot({ ok: true, status: 200, json: async () => mockSnapshot })
    await new Promise((resolve) => setTimeout(resolve, 0))

    serveSnapshotOnly(mockSnapshot)
    const later = await fetchScholarships({})
    expect(later.items).toHaveLength(3)
  })

  /* ── Opting in to the live API is explicit ──────────────────────── */

  it('the live API is reachable only by opting in', async () => {
    serveSnapshotOnly(mockSnapshot)
    globalThis.fetch.mockClear()

    globalThis.fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        items: [{ id: 99, title: 'Live Record', country: 'Japan' }],
        pagination: { page: 1, limit: 12, total: 1, total_pages: 1 },
      }),
    })

    const result = await fetchScholarships({}, { catalogueMode: CATALOGUE_MODES.API })

    expect(result.source).toBe('api')
    expect(result.items[0].title).toBe('Live Record')
    expect(String(globalThis.fetch.mock.calls[0][0])).toContain('/api/')
  })

  it('opting out of the API restores static mode without touching it', async () => {
    setCatalogueMode(CATALOGUE_MODES.API)
    expect(getCatalogueMode()).toBe(CATALOGUE_MODES.API)

    setCatalogueMode(CATALOGUE_MODES.STATIC)
    expect(getCatalogueMode()).toBe(CATALOGUE_MODES.STATIC)

    serveSnapshotOnly(mockSnapshot)
    const result = await fetchScholarships({})
    expect(result.source).toBe('snapshot')
  })

  it('an unknown catalogue mode is rejected rather than silently coerced', async () => {
    // Coercing would mean a caller who asked for the live API silently got the
    // snapshot and could not tell the difference.
    await expect(
      fetchScholarships({}, { catalogueMode: 'production' }),
    ).rejects.toThrow('Unknown catalogue mode')

    await expect(
      fetchScholarshipById(1, { catalogueMode: 'neon' }),
    ).rejects.toThrow('Unknown catalogue mode')

    await expect(
      fetchScholarshipStats({ catalogueMode: 'direct' }),
    ).rejects.toThrow('Unknown catalogue mode')

    expect(() => setCatalogueMode('nonsense')).toThrow('Unknown catalogue mode')
  })

  it('an explicit static choice is honoured even when the module is set to api', async () => {
    setCatalogueMode(CATALOGUE_MODES.API)
    serveSnapshotOnly(mockSnapshot)

    const result = await fetchScholarships({}, { catalogueMode: CATALOGUE_MODES.STATIC })

    expect(result.source).toBe('snapshot')
    const apiCalls = globalThis.fetch.mock.calls.filter(
      (call) => !String(call[0]).includes('scholarships-snapshot.json'),
    )
    expect(apiCalls).toHaveLength(0)
  })
})

/* ------------------------------------------------------------------------
   Database-dependent features must not be presented as working

   Static JSON restores public browsing and nothing else. Accounts, saved
   scholarships, applications, matching and dashboards still need the
   database. If those surfaces claim to work while it is unavailable, a
   student is told a saved list was saved when it was not - which is the kind
   of quiet failure that costs trust.
   ---------------------------------------------------------------------- */

describe('database-dependent features are honestly separate', () => {
  beforeEach(() => {
    clearSnapshotCache()
    vi.resetAllMocks()
    setCatalogueMode(CATALOGUE_MODES.STATIC)
    globalThis.fetch = vi.fn()
  })

  it('a snapshot-only catalogue leaves no API request for a saved list', async () => {
    serveSnapshotOnly(mockSnapshot)

    await fetchScholarships({})

    // There is no saved-scholarships endpoint call anywhere in the static
    // path, because the static path has no notion of a user.
    const apiCalls = globalThis.fetch.mock.calls.filter(
      (call) => !String(call[0]).includes('scholarships-snapshot.json'),
    )
    expect(apiCalls).toHaveLength(0)
  })

  it('the snapshot carries no per-user state at all', async () => {
    serveSnapshotOnly(mockSnapshot)

    const result = await fetchScholarships({})
    const blob = JSON.stringify(result)

    for (const field of [
      'saved_scholarships',
      'application_records',
      'student_profiles',
      'student_sessions',
      'user_sessions',
      'users',
      'professor_profiles',
    ]) {
      expect(blob).not.toContain(field)
    }
  })

  it('a record carries no per-user or per-session marker', async () => {
    serveSnapshotOnly(mockSnapshot)

    const result = await fetchScholarships({})
    for (const item of result.items) {
      expect(item).not.toHaveProperty('user_id')
      expect(item).not.toHaveProperty('session_id')
      expect(item).not.toHaveProperty('owner_id')
      expect(item).not.toHaveProperty('account_id')
      expect(item).not.toHaveProperty('saved_at')
    }
  })
})
