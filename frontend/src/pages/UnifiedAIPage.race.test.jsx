import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { useState } from 'react'
import { AuthContext } from '../context/authContext'
import UnifiedAIPage from './UnifiedAIPage'

vi.mock('../services/unifiedAI', () => ({
  askUnifiedAI: vi.fn(),
  getAIStatus: vi.fn(async () => ({ mentor: false, remoteAI: false, localAI: false, grounded: true, activeMode: 'grounded' })),
  formatUnifiedResponse: (r, mode) => ({ answer: r.answer, sources: r.sources || [], grounded: r.grounded ?? true, model: r.model, tokensUsed: r.tokensUsed, sourceType: mode === 'mentor' ? 'mentor' : 'grounded', label: mode === 'mentor' ? 'Grounded Mentor' : 'Grounded Search' }),
  setLocalAIEnabled: vi.fn(),
  isLocalAIEnabled: vi.fn(() => false),
  classifyRoute: (msg) => {
    if (!msg || typeof msg !== 'string') return 'mentor'
    const lower = msg.toLowerCase().trim()
    if (!lower) return 'mentor'
    // First-person eligibility
    if (/can\s+i\s+apply/i.test(msg)) return 'mentor'
    if (/am\s+i\s+eligible/i.test(msg)) return 'mentor'
    if (/with\s+my\s+(gpa|grades?|score|ielts|toefl|profile|academic)/i.test(msg)) return 'mentor'
    if (/my\s+(gpa|grades?|score|ielts|toefl|profile|academic)/i.test(msg)) return 'mentor'
    if (/based\s+on\s+my/i.test(msg)) return 'mentor'
    // Private mentor phrases
    if (lower.includes('my profile') || lower.includes('my application') || lower.includes('my eligibility')) return 'mentor'
    if (lower.includes('what should i do') || lower.includes('what are my next steps')) return 'mentor'
    // Discovery phrases
    if (lower.includes('find scholarship') || lower.includes('find scholarships')) return 'discovery'
    if (lower.includes('phd scholarship') || lower.includes('phd scholarships')) return 'discovery'
    if (lower.includes('fully funded')) return 'discovery'
    if (lower.includes('with stipend')) return 'discovery'
    if (lower.includes('scholarships in') || lower.includes('scholarship in')) return 'discovery'
    if (lower.includes('deadlines')) return 'discovery'
    if (lower.includes('search scholarships') || lower.includes('search scholarship')) return 'discovery'
    // Discovery verbs + scholarship noun
    const hasVerb = /\b(find|search|browse|show|list|discover|explore|which)\b/.test(lower)
    const hasNoun = /\b(scholarship|scholarships|opportunity|opportunities|grant|grants|funding)\b/.test(lower)
    if (hasVerb && hasNoun) return 'discovery'
    // Degree + funding/location
    const hasDegree = /\b(phd|doctoral|doctorate|master|masters|bachelor|undergraduate)\b/.test(lower)
    const hasLocation = /\b(europe|germany|uk|usa|canada|australia|japan|korea|china|india|france|italy|spain|netherlands)\b/.test(lower)
    if (hasDegree && hasLocation && hasNoun) return 'discovery'
    return 'mentor'
  },
}))
vi.mock('../services/aiAssistant', () => ({
  askAIAssistant: vi.fn(async () => ({ answer: 'grounded answer', sources: [], grounded: true })),
  checkAIAvailability: vi.fn(async () => false),
  isAIEnabled: vi.fn(() => false),
  setAIEnabled: vi.fn(),
  isLocalAIEnabled: vi.fn(() => false),
}))
vi.mock('../services/mentorService', () => ({
  fetchMentorOverview: vi.fn(async () => ({ supported_intents: [] })),
  MentorRateLimitedError: class extends Error {},
  MentorValidationError: class extends Error {},
  MentorUnavailableError: class extends Error {},
  MentorUnauthenticatedError: class extends Error {},
}))

import { askUnifiedAI, getAIStatus } from '../services/unifiedAI'

function deferred() {
  let resolve
  let reject
  const promise = new Promise((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

const mentorStatus = { mentor: true, remoteAI: false, localAI: false, grounded: true, activeMode: 'mentor' }
const groundedStatus = { mentor: false, remoteAI: false, localAI: false, grounded: true, activeMode: 'grounded' }

describe('UnifiedAIPage stale async safety', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('ignores stale mentor initialization after public initialization', async () => {
    const d1 = deferred()
    const d2 = deferred()
    let call = 0
    getAIStatus.mockImplementation(() => (call++ === 0 ? d1.promise : d2.promise))

    const setterRef = { current: null }
    function Harness() {
      const [status, setStatus] = useState('authenticated')
      setterRef.current = setStatus
      const auth = { status, user: status === 'authenticated' ? { id: 1, email: 'a@b.com' } : null, login: vi.fn(), register: vi.fn(), logout: vi.fn(), refreshSession: vi.fn() }
      return <AuthContext.Provider value={auth}><UnifiedAIPage /></AuthContext.Provider>
    }

    render(<MemoryRouter><Harness /></MemoryRouter>)
    await waitFor(() => expect(getAIStatus).toHaveBeenCalled())

    act(() => {
      setterRef.current('unauthenticated')
    })

    await act(async () => {
      d2.resolve(groundedStatus)
    })
    await waitFor(() => expect(screen.getByText(/Grounded Search/i)).toBeInTheDocument())

    await act(async () => {
      d1.resolve(mentorStatus)
    })
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(screen.getByText(/Grounded Search/i)).toBeInTheDocument()
    expect(screen.queryByText(/Grounded Mentor/i)).not.toBeInTheDocument()
  })

  it('ignores toggle completion after logout', async () => {
    const dInit = deferred()
    const dToggle = deferred()
    const dPublic = deferred()
    const queue = [dInit, dToggle, dPublic]
    getAIStatus.mockImplementation(() => queue.shift().promise)

    const setterRef = { current: null }
    function Harness() {
      const [status, setStatus] = useState('authenticated')
      setterRef.current = setStatus
      const auth = { status, user: status === 'authenticated' ? { id: 1, email: 'a@b.com' } : null, login: vi.fn(), register: vi.fn(), logout: vi.fn(), refreshSession: vi.fn() }
      return <AuthContext.Provider value={auth}><UnifiedAIPage /></AuthContext.Provider>
    }

    render(<MemoryRouter><Harness /></MemoryRouter>)

    await act(async () => {
      dInit.resolve(mentorStatus)
    })
    await waitFor(() => expect(screen.getByText(/Grounded Mentor/i)).toBeInTheDocument())

    await userEvent.click(screen.getByRole('button', { name: /AI Settings/i }))
    const checkbox = screen.getByRole('checkbox', { name: /Enable Local AI/i })
    await userEvent.click(checkbox)

    act(() => {
      setterRef.current('unauthenticated')
    })

    await act(async () => {
      dPublic.resolve(groundedStatus)
    })
    await waitFor(() => expect(screen.getByText(/Grounded Search/i)).toBeInTheDocument())

    await act(async () => {
      dToggle.resolve(mentorStatus)
    })
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(screen.getByText(/Grounded Search/i)).toBeInTheDocument()
    expect(screen.queryByText(/Grounded Mentor/i)).not.toBeInTheDocument()
  })
})

describe('UnifiedAIPage submission routing', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getAIStatus.mockResolvedValue(groundedStatus)
  })

  it('anonymous submission uses grounded routing', async () => {
    vi.mocked(askUnifiedAI).mockResolvedValue({ answer: 'grounded answer', sources: [], grounded: true })
    render(
      <MemoryRouter>
        <AuthContext.Provider value={{ status: 'unauthenticated', user: null, login: vi.fn(), register: vi.fn(), logout: vi.fn(), refreshSession: vi.fn() }}>
          <UnifiedAIPage />
        </AuthContext.Provider>
      </MemoryRouter>
    )
    const input = await screen.findByPlaceholderText(/Ask about scholarships/i)
    await userEvent.type(input, 'Find fully funded Master\'s in Germany')
    await userEvent.click(screen.getByRole('button', { name: /Send question/i }))
    await waitFor(() => {
      expect(askUnifiedAI).toHaveBeenCalledWith('Find fully funded Master\'s in Germany', expect.objectContaining({ isAuthenticated: false }))
    })
  })

  it('authenticated submission uses mentor routing', async () => {
    getAIStatus.mockResolvedValue(mentorStatus)
    vi.mocked(askUnifiedAI).mockResolvedValue({ answer: 'mentor answer', sources: [], grounded: true })
    render(
      <MemoryRouter>
        <AuthContext.Provider value={{ status: 'authenticated', user: { id: 1, email: 'a@b.com' }, login: vi.fn(), register: vi.fn(), logout: vi.fn(), refreshSession: vi.fn() }}>
          <UnifiedAIPage />
        </AuthContext.Provider>
      </MemoryRouter>
    )
    const input = await screen.findByPlaceholderText(/Ask about your scholarships/i)
    await userEvent.type(input, 'What are my saved scholarships?')
    await userEvent.click(screen.getByRole('button', { name: /Send question/i }))
    await waitFor(() => {
      expect(askUnifiedAI).toHaveBeenCalledWith('What are my saved scholarships?', expect.objectContaining({ isAuthenticated: true }))
    })
  })

  it('expired session triggers refreshSession fallback', async () => {
    getAIStatus.mockResolvedValue(mentorStatus)
    const refreshSession = vi.fn()
    vi.mocked(askUnifiedAI).mockResolvedValue({ answer: 'grounded answer', sources: [], grounded: true, authExpired: true })
    render(
      <MemoryRouter>
        <AuthContext.Provider value={{ status: 'authenticated', user: { id: 1, email: 'a@b.com' }, login: vi.fn(), register: vi.fn(), logout: vi.fn(), refreshSession }}>
          <UnifiedAIPage />
        </AuthContext.Provider>
      </MemoryRouter>
    )
    const input = await screen.findByPlaceholderText(/Ask about your scholarships/i)
    await userEvent.type(input, 'hello')
    await userEvent.click(screen.getByRole('button', { name: /Send question/i }))
    await waitFor(() => {
      expect(refreshSession).toHaveBeenCalled()
    })
  })
})
