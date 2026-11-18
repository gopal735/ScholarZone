import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { AuthContext } from '../context/authContext'
import UnifiedAIPage from './UnifiedAIPage'

vi.mock('../services/unifiedAI', () => ({
  askUnifiedAI: vi.fn(),
  getAIStatus: vi.fn(async () => ({ mentor: false, remoteAI: false, localAI: false, grounded: true, activeMode: 'grounded' })),
  formatUnifiedResponse: (r, mode) => ({ answer: r.answer, sources: r.sources || [], grounded: r.grounded ?? true, model: r.model, tokensUsed: r.tokensUsed, sourceType: mode === 'mentor' ? 'mentor' : 'grounded', label: mode === 'mentor' ? 'Grounded Mentor' : 'Grounded Search' }),
  setLocalAIEnabled: vi.fn(),
  isLocalAIEnabled: vi.fn(() => false),
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

function renderPage(authStatus = 'unauthenticated') {
  return render(
    <MemoryRouter>
      <AuthContext.Provider value={{ status: authStatus, user: authStatus === 'authenticated' ? { id: 1, email: 'a@b.com' } : null, login: vi.fn(), register: vi.fn(), logout: vi.fn(), refreshSession: vi.fn() }}>
        <UnifiedAIPage />
      </AuthContext.Provider>
    </MemoryRouter>
  )
}

describe('UnifiedAIPage auth routing', () => {
  beforeEach(() => {
    vi.clearAllMocks()
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
