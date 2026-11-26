import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { askAIAssistant, setAIEnabled } from '../aiAssistant'

describe('aiAssistant month-precision recovery path', () => {
  beforeEach(() => {
    setAIEnabled(false)
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-11-17T12:00:00Z'))
    vi.stubGlobal('fetch', vi.fn())
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    setAIEnabled(false)
  })

  it('includes month-precision December 1 record via snapshot recovery', async () => {
    const snap = {
      scholarships: [
        { id: 1, title: 'MonthPrecision', country: 'X', degree: 'Master', funding: 'F', deadline: '2026-12-01', deadline_date: '2026-12-01', deadline_precision: 'month', status: 'open', verification_status: 'active', official_source_url: 'https://example.edu/mp' },
        { id: 2, title: 'Expired', country: 'X', degree: 'Master', funding: 'F', deadline: '2026-11-10', deadline_date: '2026-11-10', deadline_precision: 'exact', status: 'open', verification_status: 'active', official_source_url: 'https://example.edu/exp' },
      ],
    }
    vi.mocked(fetch).mockImplementation(async (url) => {
      if (String(url).includes('/scholarships')) {
        return { ok: true, json: async () => ({ items: [snap.scholarships[0]], pagination: { page: 1, limit: 20, total: 1, total_pages: 1 } }) }
      }
      return { ok: false, status: 500, json: async () => ({}) }
    })
    const res = await askAIAssistant({ question: 'Which scholarships have deadlines within 30 days?' })
    expect(res.grounded).toBe(true)
    expect(res.answer).toMatch(/MonthPrecision/)
    expect(res.answer).not.toMatch(/Expired/)
  })

  it('excludes record with null deadline_date even if deadline_display present', async () => {
    const snap = {
      scholarships: [
        { id: 3, title: 'DisplayOnly', country: 'X', degree: 'Master', funding: 'F', deadline: '2026-11-20', deadline_display: '2026-11-20', deadline_date: null, deadline_precision: 'exact', status: 'open', verification_status: 'active', official_source_url: 'https://example.edu/do' },
      ],
    }
    vi.mocked(fetch).mockImplementation(async (url) => {
      if (String(url).includes('/scholarships')) {
        return { ok: true, json: async () => ({ items: [], pagination: { page: 1, limit: 20, total: 0, total_pages: 0 } }) }
      }
      return { ok: false, status: 500, json: async () => ({}) }
    })
    const res = await askAIAssistant({ question: 'Which scholarships have deadlines within 30 days?' })
    expect(res.grounded).toBe(true)
    expect(res.answer).not.toMatch(/DisplayOnly/)
  })
})
