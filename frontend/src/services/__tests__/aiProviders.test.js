import { describe, it, expect, vi, beforeEach } from 'vitest'
import { 
  getAIStatus, 
  formatUnifiedResponse,
  checkLocalAIModelReady,
  isLocalAIEnabled,
  setLocalAIEnabled
} from '../unifiedAI'
import { askAIAssistant, checkAIAvailability, setAIEnabled } from '../aiAssistant'

describe('AI Provider Claims', () => {
  beforeEach(() => {
    // Reset localStorage
    localStorage.clear()
    vi.clearAllMocks()
  })

  describe('Local AI Status', () => {
    it('returns localAIModelReady: false when Transformers.js not implemented', async () => {
      const status = await getAIStatus()
      expect(status.localAIModelReady).toBe(false)
    })

    it('does not claim local_ai active when only localStorage is set', async () => {
      setLocalAIEnabled(true)
      const status = await getAIStatus()
      // localAI should be false because localAIModelReady is false
      expect(status.localAI).toBe(false)
      // But localAIEnabled should be true
      expect(status.localAIEnabled).toBe(true)
    })

    it('does not set activeMode to local_ai when model not ready', async () => {
      setLocalAIEnabled(true)
      const status = await getAIStatus()
      expect(status.activeMode).not.toBe('local_ai')
    })

    it('checkLocalAIModelReady returns false (Transformers.js not implemented)', async () => {
      const ready = await checkLocalAIModelReady()
      expect(ready).toBe(false)
    })

    it('isLocalAIEnabled returns localStorage value', () => {
      expect(isLocalAIEnabled()).toBe(false)
      setLocalAIEnabled(true)
      expect(isLocalAIEnabled()).toBe(true)
      setLocalAIEnabled(false)
      expect(isLocalAIEnabled()).toBe(false)
    })
  })

  describe('Remote AI Status', () => {
    it('checkAIAvailability returns false when backend not available', async () => {
      const available = await checkAIAvailability()
      expect(available).toBe(false)
    })

    it('askAIAssistant falls back to grounded retrieval when AI not enabled', async () => {
      setAIEnabled(false)
      const response = await askAIAssistant({ question: 'test question' })
      expect(response.grounded).toBe(true)
      expect(response.sources).toBeDefined()
    })

    it('does not claim generative AI when using grounded fallback', async () => {
      setAIEnabled(false)
      const response = await askAIAssistant({ question: 'test question' })
      // Grounded fallback should be clearly labeled
      expect(response.grounded).toBe(true)
    })
  })

  describe('AI Mode Labels', () => {
    it('formatUnifiedResponse labels grounded mode correctly', () => {
      const response = { answer: 'test', sources: [], grounded: true }
      const formatted = formatUnifiedResponse(response, 'grounded')
      expect(formatted.label).toBe('📋 Grounded Search')
      expect(formatted.grounded).toBe(true)
    })

    it('formatUnifiedResponse labels mentor mode correctly', () => {
      const response = { answer: 'test', sources: [], grounded: true }
      const formatted = formatUnifiedResponse(response, 'mentor')
      expect(formatted.label).toBe('📋 Grounded Mentor')
      expect(formatted.grounded).toBe(true)
    })

    it('formatUnifiedResponse labels local_ai mode correctly', () => {
      const response = { answer: 'test', sources: [], grounded: false }
      const formatted = formatUnifiedResponse(response, 'local_ai')
      expect(formatted.label).toBe('🤖 Local AI')
      expect(formatted.grounded).toBe(false)
    })

    it('formatUnifiedResponse labels remote_ai mode correctly', () => {
      const response = { answer: 'test', sources: [], grounded: false }
      const formatted = formatUnifiedResponse(response, 'remote_ai')
      expect(formatted.label).toBe('☁️ Remote AI')
      expect(formatted.grounded).toBe(false)
    })
  })

  describe('Bengali Support', () => {
    it('extractKeywords handles Bengali characters', async () => {
      // This test documents current limitation - no Bengali stopwords
      const { askAIAssistant } = await import('../aiAssistant')
      // The grounded fallback uses English stopwords only
      // Bengali queries would work but with reduced accuracy
      const response = await askAIAssistant({ question: 'জার্মানিতে পূর্ণ মুদ্রাবৃত্তি মাস্টার স্কলারশিপ' })
      expect(response.grounded).toBe(true)
    })
  })

  describe('No Mandatory Paid Provider', () => {
    it('works without any AI enabled (grounded fallback always available)', async () => {
      setAIEnabled(false)
      localStorage.removeItem('sz-local-ai-enabled')
      
      const status = await getAIStatus()
      expect(status.grounded).toBe(true)
      expect(status.activeMode).toBe('grounded')
    })

    it('does not require paid LLM API for basic functionality', async () => {
      setAIEnabled(false)
      const response = await askAIAssistant({ question: 'Find scholarships in Germany' })
      expect(response.grounded).toBe(true)
      expect(response.sources.length).toBeGreaterThanOrEqual(0)
    })
  })
})