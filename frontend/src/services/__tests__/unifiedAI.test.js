import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { askUnifiedAI } from '../unifiedAI'
import { MentorUnauthenticatedError, MentorRateLimitedError, MentorValidationError, MentorUnavailableError } from '../mentorService'

vi.mock('../mentorService', () => ({
  askMentor: vi.fn(),
  MentorUnauthenticatedError: class extends Error { constructor(m){super(m);this.name='MentorUnauthenticatedError'} },
  MentorRateLimitedError: class extends Error { constructor(m, r){super(m);this.name='MentorRateLimitedError';this.retryAfterSeconds=r} },
  MentorValidationError: class extends Error { constructor(m){super(m);this.name='MentorValidationError'} },
  MentorUnavailableError: class extends Error { constructor(m,s){super(m);this.name='MentorUnavailableError';this.status=s} },
  fetchMentorOverview: vi.fn(),
}))
vi.mock('../aiAssistant', () => ({
  askAIAssistant: vi.fn(async () => ({ answer: 'grounded answer', sources: [], grounded: true })),
  checkAIAvailability: vi.fn(async () => false),
  isAIEnabled: vi.fn(() => false),
  setAIEnabled: vi.fn(),
  isLocalAIEnabled: vi.fn(() => false),
}))

import { askMentor } from '../mentorService'
import { askAIAssistant } from '../aiAssistant'

describe('askUnifiedAI routing', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })
  afterEach(() => vi.clearAllMocks())

  it('anonymous: calls askAIAssistant, not askMentor', async () => {
    const res = await askUnifiedAI('hello', { isAuthenticated: false })
    expect(askAIAssistant).toHaveBeenCalled()
    expect(askMentor).not.toHaveBeenCalled()
    expect(res.answer).toBe('grounded answer')
  })

  it('authenticated: calls askMentor, not askAIAssistant', async () => {
    vi.mocked(askMentor).mockResolvedValue({ answer: 'mentor answer', sources: [], grounded: true })
    const res = await askUnifiedAI('hello', { isAuthenticated: true })
    expect(askMentor).toHaveBeenCalled()
    expect(askAIAssistant).not.toHaveBeenCalled()
    expect(res.answer).toBe('mentor answer')
  })

  it('expired session: falls back to grounded, sets authExpired', async () => {
    vi.mocked(askMentor).mockRejectedValue(new MentorUnauthenticatedError('expired'))
    vi.mocked(askAIAssistant).mockResolvedValue({ answer: 'grounded answer', sources: [], grounded: true })
    const res = await askUnifiedAI('hello', { isAuthenticated: true })
    expect(askMentor).toHaveBeenCalled()
    expect(askAIAssistant).toHaveBeenCalled()
    expect(res.authExpired).toBe(true)
    expect(res.answer).toBe('grounded answer')
  })

  it('expired session + fallback failure: throws original auth error', async () => {
    vi.mocked(askMentor).mockRejectedValue(new MentorUnauthenticatedError('expired'))
    vi.mocked(askAIAssistant).mockRejectedValue(new Error('network'))
    await expect(askUnifiedAI('hello', { isAuthenticated: true })).rejects.toBeInstanceOf(MentorUnauthenticatedError)
  })

  it('429: throws MentorRateLimitedError', async () => {
    vi.mocked(askMentor).mockRejectedValue(new MentorRateLimitedError('slow', 30))
    await expect(askUnifiedAI('hello', { isAuthenticated: true })).rejects.toBeInstanceOf(MentorRateLimitedError)
  })

  it('422: throws MentorValidationError', async () => {
    vi.mocked(askMentor).mockRejectedValue(new MentorValidationError('bad'))
    await expect(askUnifiedAI('hello', { isAuthenticated: true })).rejects.toBeInstanceOf(MentorValidationError)
  })

  it('500: throws MentorUnavailableError', async () => {
    vi.mocked(askMentor).mockRejectedValue(new MentorUnavailableError('down', 500))
    await expect(askUnifiedAI('hello', { isAuthenticated: true })).rejects.toBeInstanceOf(MentorUnavailableError)
  })
})
