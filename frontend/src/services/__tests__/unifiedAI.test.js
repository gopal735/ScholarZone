import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { askUnifiedAI, normalizeMentorResponse, formatUnifiedResponse } from '../unifiedAI'

// Real backend MentorAnswerResponse fixture
const realMentorResponse = {
  request_id: 'abc123def456',
  as_of: '2026-11-18',
  intent: 'NEXT_ACTION',
  intent_label: 'What should I do next?',
  supported: true,
  headline: 'Focus on your DAAD application this week.',
  why: 'Your DAAD application has the nearest deadline and highest fit score.',
  known: [
    { key: 'fit', label: 'Fit Score', value: '85', field: 'fit_score', basis: 'Match 2.0', verification: 'verified', source_url: 'https://example.com/daad', scholarship_id: 42 },
  ],
  unknown: ['Your IELTS score has not been verified.'],
  next_steps: [
    { code: 'APPLY', title: 'Submit DAAD application', detail: 'Complete your application before the deadline.', priority: 1, href: '/applications', action_label: 'Go to Applications' },
  ],
  caveats: ['Deadline dates may change.'],
  notes: ['Based on your current profile.'],
  general_guidance_only: false,
  provider_mode: 'disabled',
  provider_used: false,
  supported_intents: ['NEXT_ACTION', 'DEADLINE'],
  redirects: [],
}

describe('normalizeMentorResponse', () => {
  it('normalizes a real MentorAnswerResponse', () => {
    const result = normalizeMentorResponse(realMentorResponse)
    expect(result).not.toBeNull()
    expect(result.kind).toBe('mentor')
    expect(result.mentorResponse.headline).toBe('Focus on your DAAD application this week.')
    expect(result.mentorResponse.known).toHaveLength(1)
    expect(result.mentorResponse.unknown).toHaveLength(1)
    expect(result.mentorResponse.next_steps).toHaveLength(1)
    expect(result.mentorResponse.caveats).toHaveLength(1)
    expect(result.mentorResponse.notes).toHaveLength(1)
    expect(result.grounded).toBe(true)
  })

  it('returns null for null input', () => {
    expect(normalizeMentorResponse(null)).toBeNull()
  })

  it('returns null for undefined input', () => {
    expect(normalizeMentorResponse(undefined)).toBeNull()
  })

  it('returns null for non-object input', () => {
    expect(normalizeMentorResponse('string')).toBeNull()
    expect(normalizeMentorResponse(42)).toBeNull()
  })

  it('returns null for missing headline', () => {
    const rest = { ...realMentorResponse }
    delete rest.headline
    expect(normalizeMentorResponse(rest)).toBeNull()
  })

  it('returns null for empty headline', () => {
    expect(normalizeMentorResponse({ ...realMentorResponse, headline: '' })).toBeNull()
    expect(normalizeMentorResponse({ ...realMentorResponse, headline: '   ' })).toBeNull()
  })

  it('returns null for missing request_id', () => {
    const rest = { ...realMentorResponse }
    delete rest.request_id
    expect(normalizeMentorResponse(rest)).toBeNull()
  })

  it('returns null for missing intent', () => {
    const rest = { ...realMentorResponse }
    delete rest.intent
    expect(normalizeMentorResponse(rest)).toBeNull()
  })

  it('returns null for non-boolean supported', () => {
    expect(normalizeMentorResponse({ ...realMentorResponse, supported: 'yes' })).toBeNull()
  })

  it('returns null for non-boolean general_guidance_only', () => {
    expect(normalizeMentorResponse({ ...realMentorResponse, general_guidance_only: 1 })).toBeNull()
  })

  it('filters invalid evidence items', () => {
    const raw = {
      ...realMentorResponse,
      known: [
        { label: 'Valid', value: 'v', field: 'f', basis: 'b' },
        { label: '', value: 'v', field: 'f', basis: 'b' }, // invalid: empty label
        null,
        'string',
      ],
    }
    const result = normalizeMentorResponse(raw)
    expect(result.mentorResponse.known).toHaveLength(1)
  })

  it('filters invalid next steps', () => {
    const raw = {
      ...realMentorResponse,
      next_steps: [
        { title: 'Valid', detail: 'd', href: '/x', action_label: 'Go', code: 'C' },
        { title: '', detail: 'd', href: '/x', action_label: 'Go', code: 'C' }, // invalid
        null,
      ],
    }
    const result = normalizeMentorResponse(raw)
    expect(result.mentorResponse.next_steps).toHaveLength(1)
  })

  it('defaults missing arrays to empty', () => {
    const rest = { ...realMentorResponse }
    delete rest.known
    delete rest.unknown
    delete rest.next_steps
    delete rest.caveats
    delete rest.notes
    delete rest.redirects
    delete rest.supported_intents
    const result = normalizeMentorResponse(rest)
    expect(result.mentorResponse.known).toEqual([])
    expect(result.mentorResponse.unknown).toEqual([])
    expect(result.mentorResponse.next_steps).toEqual([])
    expect(result.mentorResponse.caveats).toEqual([])
    expect(result.mentorResponse.notes).toEqual([])
  })

  it('filters non-string array items', () => {
    const raw = { ...realMentorResponse, caveats: ['valid', 42, null, 'also valid'] }
    const result = normalizeMentorResponse(raw)
    expect(result.mentorResponse.caveats).toEqual(['valid', 'also valid'])
  })
})

describe('formatUnifiedResponse mentor', () => {
  it('formats a normalized mentor response', () => {
    const normalized = normalizeMentorResponse(realMentorResponse)
    const formatted = formatUnifiedResponse(normalized, 'mentor')
    expect(formatted.answer).toBeNull()
    expect(formatted.mentorResponse).not.toBeNull()
    expect(formatted.mentorResponse.headline).toBe('Focus on your DAAD application this week.')
    expect(formatted.sourceType).toBe('mentor')
    expect(formatted.label).toBe('📋 Grounded Mentor')
    expect(formatted.grounded).toBe(true)
  })
})

describe('askUnifiedAI with real mentor response', () => {
  it('returns normalized mentor response for authenticated user', async () => {
    vi.mocked(askMentor).mockResolvedValue(realMentorResponse)
    const res = await askUnifiedAI('hello', { isAuthenticated: true })
    expect(askMentor).toHaveBeenCalled()
    expect(res.kind).toBe('mentor')
    expect(res.mentorResponse).not.toBeNull()
    expect(res.mentorResponse.headline).toBe('Focus on your DAAD application this week.')
  })
})

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
import { MentorUnauthenticatedError, MentorRateLimitedError, MentorValidationError, MentorUnavailableError } from '../mentorService'
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
