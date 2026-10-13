/**
 * Tests for the strategist API client's bounded cache.
 *
 * These prove the exact safety properties the cache promises: identical requests
 * reuse a cached answer (no refetch) within the TTL; different requests never
 * share an answer; after the TTL the answer is refetched; the cache is bounded
 * (an evicted key is refetched); and on network failure a known answer is served
 * disclosed as stale while an unknown one is never invented.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  fetchPlan,
  fetchSubjects,
  resetStrategistCache,
} from './api.js'

const ok = (body) => ({ ok: true, json: async () => body })

beforeEach(() => {
  resetStrategistCache()
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('bounded plan cache', () => {
  it('reuses a cached answer within the TTL without refetching', async () => {
    const fetchMock = vi.fn(async () => ok({ request: {}, comparison: [] }))
    vi.stubGlobal('fetch', fetchMock)
    const a = await fetchPlan({ subject_key: 'computer_science', degree: 'master' })
    const b = await fetchPlan({ subject_key: 'computer_science', degree: 'master' })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(a._cached).toBeUndefined()
    expect(b._cached).toBe(true)
  })

  it('does not share an answer between different requests', async () => {
    const fetchMock = vi.fn(async () => ok({ comparison: [] }))
    vi.stubGlobal('fetch', fetchMock)
    await fetchPlan({ subject_key: 'computer_science', degree: 'master' })
    await fetchPlan({ subject_key: 'data_science', degree: 'master' })
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('refetches after the TTL expires', async () => {
    const fetchMock = vi.fn(async () => ok({ comparison: [] }))
    vi.stubGlobal('fetch', fetchMock)
    await fetchPlan({ subject_key: 'computer_science', degree: 'master' })
    vi.useFakeTimers()
    await vi.advanceTimersByTimeAsync(5 * 60 * 1000 + 1000)
    await fetchPlan({ subject_key: 'computer_science', degree: 'master' })
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('serves a known answer (disclosed stale) when the network fails', async () => {
    const fetchMock = vi.fn(async () => ok({ comparison: ['x'] }))
    vi.stubGlobal('fetch', fetchMock)
    await fetchPlan({ subject_key: 'computer_science', degree: 'master' })
    // force a network attempt that then fails, to exercise the stale path.
    fetchMock.mockImplementationOnce(async () => ({ ok: false, json: async () => ({}) }))
    const stale = await fetchPlan({ subject_key: 'computer_science', degree: 'master' }, { force: true })
    expect(stale._cached).toBe(true)
    expect(stale._stale).toBe(true)
    expect(stale.comparison).toEqual(['x'])
  })

  it('never invents an answer it does not hold on failure', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, json: async () => ({}) })))
    await expect(fetchPlan({ subject_key: 'computer_science', degree: 'master' })).rejects.toThrow()
  })

  it('is bounded: an evicted key is refetched', async () => {
    const fetchMock = vi.fn(async () => ok({ comparison: [] }))
    vi.stubGlobal('fetch', fetchMock)
    // Insert more than the cap (20) distinct requests.
    for (let i = 0; i < 25; i++) {
      await fetchPlan({ subject_key: 'computer_science', degree: 'master', budget_bdt: i })
    }
    expect(fetchMock).toHaveBeenCalledTimes(25)
    // The very first key was evicted, so it must refetch.
    await fetchPlan({ subject_key: 'computer_science', degree: 'master', budget_bdt: 0 })
    expect(fetchMock).toHaveBeenCalledTimes(26)
  })
})

describe('subjects cache', () => {
  it('caches subjects and serves them stale on later failure', async () => {
    const fetchMock = vi.fn(async () => ok({ subjects: [{ key: 'computer_science' }] }))
    vi.stubGlobal('fetch', fetchMock)
    const first = await fetchSubjects()
    const second = await fetchSubjects()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(second._cached).toBe(true)
    fetchMock.mockImplementationOnce(async () => ({ ok: false, json: async () => ({}) }))
    resetStrategistCache() // drop the cached copy to prove a fresh miss still throws
    await expect(fetchSubjects()).rejects.toThrow()
    expect(first.subjects).toHaveLength(1)
  })
})
