import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { askAIAssistant, setAIEnabled } from '../aiAssistant'

describe('askAIAssistant HTTP error classification', () => {
  beforeEach(() => {
    setAIEnabled(true)
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    setAIEnabled(false)
  })

  it('falls back to grounded retrieval on 429', async () => {
    vi.mocked(fetch).mockResolvedValue({ ok: false, status: 429, json: async () => ({}) })
    const result = await askAIAssistant({ question: 'test' })
    expect(result.grounded).toBe(true)
  })

  it('falls back to grounded retrieval on 502', async () => {
    vi.mocked(fetch).mockResolvedValue({ ok: false, status: 502, json: async () => ({}) })
    const result = await askAIAssistant({ question: 'test' })
    expect(result.grounded).toBe(true)
  })

  it('falls back to grounded retrieval on 503', async () => {
    vi.mocked(fetch).mockResolvedValue({ ok: false, status: 503, json: async () => ({}) })
    const result = await askAIAssistant({ question: 'test' })
    expect(result.grounded).toBe(true)
  })

  it('falls back to grounded retrieval on 504', async () => {
    vi.mocked(fetch).mockResolvedValue({ ok: false, status: 504, json: async () => ({}) })
    const result = await askAIAssistant({ question: 'test' })
    expect(result.grounded).toBe(true)
  })

  it('throws structured error on 500 (not treated as provider unavailable)', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ detail: 'Internal database error' }),
    })
    await expect(askAIAssistant({ question: 'test' })).rejects.toMatchObject({
      code: 'SERVER_ERROR',
      status: 500,
    })
  })

  it('returns remote answer on 200', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ answer: 'hello', sources: [], grounded: false }),
    })
    const result = await askAIAssistant({ question: 'test' })
    expect(result.answer).toBe('hello')
    expect(result.grounded).toBe(false)
  })

  it('falls back to grounded retrieval on malformed JSON success body', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => { throw new Error('bad json') },
    })
    const result = await askAIAssistant({ question: 'test' })
    expect(result.grounded).toBe(true)
  })
})
