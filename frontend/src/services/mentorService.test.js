/**
 * The mentor API client.
 *
 * The behaviour worth pinning here is the failure taxonomy. A page that cannot
 * tell "you are signed out" from "the network is down" from "you are asking too
 * often" will offer a sign-in link to someone whose connection failed and a
 * retry to someone whose session is gone. Each status therefore gets its own
 * class, and the rate-limit case carries the server's own wait.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  MentorApiError,
  MentorRateLimitedError,
  MentorUnavailableError,
  MentorUnauthenticatedError,
  MentorValidationError,
  askMentor,
  fetchMentorOverview,
} from './mentorService'

function jsonResponse(body, { status = 200, headers = {} } = {}) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: (name) => headers[name] ?? null },
    json: async () => body,
  }
}

describe('mentorService', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('asks the server and returns the grounded answer', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ headline: 'ok' }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await askMentor('What should I do now?')

    expect(result.headline).toBe('ok')
    const [url, options] = fetchMock.mock.calls[0]
    expect(url).toMatch(/\/mentor\/message$/)
    expect(options.method).toBe('POST')
    // The session cookie is the only credential; a user id must never appear.
    expect(options.credentials).toBe('include')
    expect(JSON.parse(options.body)).toEqual({ message: 'What should I do now?' })
  })

  it('distinguishes a lost session from a failed network', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ detail: 'Sign in to continue.' }, { status: 401 })))
    await expect(askMentor('anything')).rejects.toBeInstanceOf(MentorUnauthenticatedError)

    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))
    const failure = await askMentor('anything').catch((error) => error)
    expect(failure).toBeInstanceOf(MentorApiError)
    expect(failure.status).toBe(0)
  })

  it('carries the server wait on a rate limit', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({ detail: 'Too many questions.' }, { status: 429, headers: { 'Retry-After': '45' } }),
      ),
    )
    const failure = await askMentor('anything').catch((error) => error)
    expect(failure).toBeInstanceOf(MentorRateLimitedError)
    expect(failure.retryAfterSeconds).toBe(45)
  })

  it('falls back to a sane wait when no header is present', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ detail: 'Slow down.' }, { status: 429 })))
    const failure = await askMentor('anything').catch((error) => error)
    expect(failure.retryAfterSeconds).toBeGreaterThan(0)
  })

  it('separates validation from unavailability', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ detail: 'Too long.' }, { status: 422 })))
    await expect(askMentor('x'.repeat(5000))).rejects.toBeInstanceOf(MentorValidationError)

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ detail: 'down' }, { status: 503 })))
    await expect(askMentor('anything')).rejects.toBeInstanceOf(MentorUnavailableError)
  })

  it('sends an identical repeated question once', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ headline: 'ok' }))
    vi.stubGlobal('fetch', fetchMock)

    await Promise.all([askMentor('What should I do now?'), askMentor('What should I do now?')])
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('does not cache: a later question always reaches the server', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ headline: 'ok' }))
    vi.stubGlobal('fetch', fetchMock)

    await askMentor('What should I do now?')
    await askMentor('What should I do now?')
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('treats different questions as different requests', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ headline: 'ok' }))
    vi.stubGlobal('fetch', fetchMock)

    await Promise.all([askMentor('What should I do now?'), askMentor('What are my deadlines?')])
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('loads the overview without asking a question', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ supported_intents: [] }))
    vi.stubGlobal('fetch', fetchMock)

    await fetchMentorOverview()
    const [url, options] = fetchMock.mock.calls[0]
    expect(url).toMatch(/\/mentor\/overview$/)
    expect(options.method).toBeUndefined()
  })
})