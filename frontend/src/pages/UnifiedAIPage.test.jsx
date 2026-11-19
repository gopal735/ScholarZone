import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { AuthContext } from '../context/authContext'
import UnifiedAIPage from './UnifiedAIPage'

vi.mock('../services/unifiedAI', async () => {
  const actual = await vi.importActual('../services/unifiedAI')
  return {
    askUnifiedAI: vi.fn(),
    getAIStatus: vi.fn(async () => ({ mentor: false, remoteAI: false, localAI: false, grounded: true, activeMode: 'grounded' })),
    formatUnifiedResponse: actual.formatUnifiedResponse,
    setLocalAIEnabled: vi.fn(),
    isLocalAIEnabled: vi.fn(() => false),
    classifyRoute: vi.fn(() => 'mentor'),
  }
})
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

function renderPage(authStatus = 'unauthenticated') {
  return render(
    <MemoryRouter>
      <AuthContext.Provider value={{ status: authStatus, user: authStatus === 'authenticated' ? { id: 1, email: 'a@b.com' } : null, login: vi.fn(), register: vi.fn(), logout: vi.fn(), refreshSession: vi.fn() }}>
        <UnifiedAIPage />
      </AuthContext.Provider>
    </MemoryRouter>
  )
}

describe('UnifiedAIPage crash safety', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getAIStatus).mockResolvedValue({ mentor: false, remoteAI: false, localAI: false, grounded: true, activeMode: 'grounded' })
  })

  it('does not crash when message.content is undefined', async () => {
    vi.mocked(askUnifiedAI).mockResolvedValue({ answer: undefined, sources: [], grounded: true })
    renderPage('unauthenticated')
    const input = await screen.findByPlaceholderText(/Ask about scholarships/i)
    await userEvent.type(input, 'test question')
    await userEvent.click(screen.getByRole('button', { name: /Send question/i }))
    await waitFor(() => {
      expect(screen.getByText(/No response available/i)).toBeInTheDocument()
    })
  })

  it('does not crash when message.content is null', async () => {
    vi.mocked(askUnifiedAI).mockResolvedValue({ answer: null, sources: [], grounded: true })
    renderPage('unauthenticated')
    const input = await screen.findByPlaceholderText(/Ask about scholarships/i)
    await userEvent.type(input, 'test question')
    await userEvent.click(screen.getByRole('button', { name: /Send question/i }))
    await waitFor(() => {
      expect(screen.getByText(/No response available/i)).toBeInTheDocument()
    })
  })

  it('renders structured mentor response without crash', async () => {
    const mentorResp = {
      kind: 'mentor',
      mentorResponse: {
        request_id: 'req123',
        as_of: '2026-11-18',
        intent: 'NEXT_ACTION',
        intent_label: 'What should I do next?',
        supported: true,
        headline: 'Focus on your DAAD application.',
        why: 'Nearest deadline and highest fit.',
        known: [{ key: 'fit', label: 'Fit Score', value: '85', field: 'fit_score', basis: 'Match 2.0' }],
        unknown: ['IELTS score not verified.'],
        next_steps: [{ code: 'APPLY', title: 'Submit DAAD', detail: 'Complete before deadline.', priority: 1, href: '/applications', action_label: 'Go' }],
        caveats: ['Dates may change.'],
        notes: ['Based on profile.'],
        general_guidance_only: false,
        provider_mode: 'disabled',
        provider_used: false,
      },
      grounded: true,
    }
    vi.mocked(askUnifiedAI).mockResolvedValue(mentorResp)
    vi.mocked(getAIStatus).mockResolvedValue({ mentor: true, remoteAI: false, localAI: false, grounded: true, activeMode: 'mentor' })
    renderPage('authenticated')
    const input = await screen.findByPlaceholderText(/Ask about your scholarships/i)
    await userEvent.type(input, 'what should I do?')
    await userEvent.click(screen.getByRole('button', { name: /Send question/i }))
    await waitFor(() => {
      expect(screen.getByText(/Focus on your DAAD application/i)).toBeInTheDocument()
    })
    expect(screen.getByText(/Nearest deadline and highest fit/i)).toBeInTheDocument()
    expect(screen.getByText(/Fit Score/i)).toBeInTheDocument()
    expect(screen.getByText(/Submit DAAD/i)).toBeInTheDocument()
    expect(screen.getByText(/Dates may change/i)).toBeInTheDocument()
    expect(screen.getByText(/Based on profile/i)).toBeInTheDocument()
    expect(screen.getAllByText(/Grounded Mentor/i).length).toBeGreaterThan(0)
  })
})
describe('UnifiedAIPage auth routing', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getAIStatus).mockResolvedValue({ mentor: false, remoteAI: false, localAI: false, grounded: true, activeMode: 'grounded' })
  })

  it('shows Grounded Search badge for anonymous user', async () => {
    renderPage('unauthenticated')
    await waitFor(() => {
      expect(screen.getByText(/Grounded Search/i)).toBeInTheDocument()
    })
  })

  it('shows sign-in prompt for anonymous user', async () => {
    renderPage('unauthenticated')
    await waitFor(() => {
      expect(screen.getByText(/Sign in for personalized Mentor/i)).toBeInTheDocument()
    })
  })

  it('submits public question through askUnifiedAI with isAuthenticated false', async () => {
    vi.mocked(askUnifiedAI).mockResolvedValue({ answer: 'grounded answer', sources: [], grounded: true })
    renderPage('unauthenticated')
    const input = await screen.findByPlaceholderText(/Ask about scholarships/i)
    await userEvent.type(input, 'Find fully funded Master\'s in Germany')
    await userEvent.click(screen.getByRole('button', { name: /Send question/i }))
    await waitFor(() => {
      expect(askUnifiedAI).toHaveBeenCalledWith('Find fully funded Master\'s in Germany', expect.objectContaining({ isAuthenticated: false }))
    })
  })

  it('shows Mentor mode only after authentication', async () => {
    vi.mocked(getAIStatus).mockResolvedValue({ mentor: true, remoteAI: false, localAI: false, grounded: true, activeMode: 'mentor' })
    renderPage('authenticated')
    await waitFor(() => {
      expect(screen.getByText(/Grounded Mentor/i)).toBeInTheDocument()
    })
  })
})
