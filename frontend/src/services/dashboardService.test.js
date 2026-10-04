/**
 * The dashboard API client.
 *
 * Two behaviours are load-bearing. A 401 must become a distinguishable error so
 * a view can send the reader to sign in, rather than a generic failure that looks
 * like a network problem. And concurrent callers must share one request rather
 * than each issuing their own - a component that unmounts mid-flight must not
 * cancel data another part of the page is still reading.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  DashboardApiError,
  DashboardUnauthenticatedError,
  fetchDashboard,
  removeSavedScholarship,
  saveScholarship,
  setApplicationState,
} from './dashboardService'

function jsonResponse(body, { status = 200 } = {}) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  }
}

describe('dashboardService', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('sends cookies so the server can identify the caller', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    await fetchDashboard()

    // Without this the request is anonymous and a signed-in reader looks signed
    // out - the failure would look like a product bug rather than a missing flag.
    expect(fetchMock.mock.calls[0][1].credentials).toBe('include')
  })

  it('raises a distinguishable error on 401', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ detail: 'Sign in to continue.' }, { status: 401 })))

    const error = await fetchDashboard().catch((caught) => caught)
    expect(error).toBeInstanceOf(DashboardUnauthenticatedError)
    expect(error.status).toBe(401)
    expect(error.message).toBe('Sign in to continue.')
  })

  it('reports a network failure as such rather than as a bad request', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    const error = await fetchDashboard().catch((caught) => caught)
    expect(error).toBeInstanceOf(DashboardApiError)
    // Not a 401, and not a message blaming the reader's request.
    expect(error.status).toBe(0)
    expect(error.message).toMatch(/could not reach/i)
  })

  it('falls back to a safe message when the failure is not JSON', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => {
          throw new Error('not json')
        },
      }),
    )

    const error = await fetchDashboard().catch((caught) => caught)
    expect(error).toBeInstanceOf(DashboardApiError)
    expect(error.status).toBe(500)
    expect(error.message).toBe('Something went wrong.')
  })

  it('shares one request between concurrent callers', async () => {
    let resolveRequest
    const fetchMock = vi.fn().mockReturnValue(
      new Promise((resolve) => {
        resolveRequest = resolve
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const first = fetchDashboard()
    const second = fetchDashboard()
    resolveRequest(jsonResponse({ ok: true }))
    await Promise.all([first, second])

    // Two simultaneous mounts must not mean two round trips.
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('issues a fresh request after the shared one settles', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    await fetchDashboard()
    await fetchDashboard()

    // De-duplication is in-flight only. Nothing is cached between loads, so a
    // later caller cannot be served stale data.
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('passes an explicit as_of through so a response is reproducible', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    await fetchDashboard({ asOf: '2026-06-01' })

    expect(fetchMock.mock.calls[0][0]).toContain('as_of=2026-06-01')
  })

  it('saves a scholarship with a POST', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ scholarship_id: 7, saved: true, saved_count: 1 }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await saveScholarship(7)

    expect(fetchMock.mock.calls[0][0]).toContain('/dashboard/saved?scholarship_id=7')
    expect(fetchMock.mock.calls[0][1].method).toBe('POST')
    expect(result.saved_count).toBe(1)
  })

  it('removes a saved scholarship with a DELETE', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ scholarship_id: 7, saved: false, saved_count: 0 }))
    vi.stubGlobal('fetch', fetchMock)

    await removeSavedScholarship(7)

    expect(fetchMock.mock.calls[0][0]).toContain('/dashboard/saved/7')
    expect(fetchMock.mock.calls[0][1].method).toBe('DELETE')
  })

  it('sends an application state in the body, never a user id', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ scholarship_id: 7, state: 'in_progress' }))
    vi.stubGlobal('fetch', fetchMock)

    await setApplicationState(7, 'in_progress')

    const [, options] = fetchMock.mock.calls[0]
    expect(options.method).toBe('PUT')
    // The body carries only the state. Ownership is resolved from the session
    // cookie by the server, so a user id here would be both redundant and a
    // vector for identifying someone else's row.
    expect(JSON.parse(options.body)).toEqual({ state: 'in_progress' })
  })
})