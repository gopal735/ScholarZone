import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  anonymousJson,
  anonymousPostJson,
  isRefused,
} from './anonymousProbe'

describe('anonymous probes', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('never sends credentials, so a signed-in session cannot masquerade as anonymous', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      status: 401,
      text: async () => '{"detail":"Sign in to continue."}',
    })
    vi.stubGlobal('fetch', fetchMock)

    // A session exists; the probe must still be anonymous.
    await anonymousJson('/api/dashboard')

    const [, init] = fetchMock.mock.calls[0]
    expect(init.credentials).toBe('omit')
    expect(init.credentials).not.toBe('include')
  })

  it('sends JSON bodies anonymously too', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      status: 401,
      text: async () => '{}',
    })
    vi.stubGlobal('fetch', fetchMock)

    await anonymousPostJson('/api/mentor/message', { message: 'What now?' })

    const [path, init] = fetchMock.mock.calls[0]
    expect(path).toBe('/api/mentor/message')
    expect(init.method).toBe('POST')
    expect(init.credentials).toBe('omit')
    expect(JSON.parse(init.body)).toEqual({ message: 'What now?' })
  })

  it('reports a refused status rather than swallowing it', () => {
    expect(isRefused(401)).toBe(true)
    expect(isRefused(403)).toBe(true)
    expect(isRefused(200)).toBe(false)
  })

  it('returns the parsed body alongside the status', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        status: 200,
        text: async () => '{"intents":["NEXT_ACTION"]}',
      })
    )
    const result = await anonymousJson('/api/mentor/overview')
    expect(result.status).toBe(200)
    expect(result.body.intents).toEqual(['NEXT_ACTION'])
  })
})