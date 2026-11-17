import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { askAIAssistant, setAIEnabled } from '../aiAssistant'
import { clearSnapshotCache } from '../staticScholarshipService'

describe('aiAssistant zero-day and invalid duration validation', () => {
  beforeEach(() => {
    setAIEnabled(false)
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-11-17T12:00:00Z'))
    vi.stubGlobal('fetch', vi.fn())
    clearSnapshotCache()
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    setAIEnabled(false)
    clearSnapshotCache()
  })

  it('within 0 days is explicitly rejected', async () => {
    const res = await askAIAssistant({ question: 'Which scholarships have deadlines within 0 days?' })
    expect(res.grounded).toBe(true)
    expect(res.answer).toMatch(/Invalid deadline window/i)
    expect(vi.mocked(fetch)).not.toHaveBeenCalled()
  })

  it('within -1 days is explicitly rejected', async () => {
    const res = await askAIAssistant({ question: 'Which scholarships have deadlines within -1 days?' })
    expect(res.grounded).toBe(true)
    expect(res.answer).toMatch(/Invalid deadline window/i)
  })

  it('within 1 day works', async () => {
    const snap = {
      meta: { generated_at: '2026-11-17T00:00:00Z', public_record_count: 1 },
      stats: { total: 1 },
      scholarships: [
        { id: 1, title: 'Soon', country: 'X', degree: 'Master', funding: 'F', deadline: '2026-11-18', deadline_date: '2026-11-18', deadline_precision: 'exact', status: 'open', verification_status: 'active', official_source_url: 'https://example.edu/soon' },
      ],
    }
    vi.mocked(fetch).mockImplementation(async (url) => {
      if (String(url).includes('scholarships-snapshot')) return { ok: true, json: async () => snap }
      return { ok: false, status: 500, json: async () => ({}) }
    })
    const res = await askAIAssistant({ question: 'Which scholarships have deadlines within 1 day?' })
    expect(res.grounded).toBe(true)
  })

  it('within 30 days works', async () => {
    const snap = {
      meta: { generated_at: '2026-11-17T00:00:00Z', public_record_count: 1 },
      stats: { total: 1 },
      scholarships: [
        { id: 1, title: 'Soon', country: 'X', degree: 'Master', funding: 'F', deadline: '2026-11-20', deadline_date: '2026-11-20', deadline_precision: 'exact', status: 'open', verification_status: 'active', official_source_url: 'https://example.edu/soon' },
      ],
    }
    vi.mocked(fetch).mockImplementation(async (url) => {
      if (String(url).includes('scholarships-snapshot')) return { ok: true, json: async () => snap }
      return { ok: false, status: 500, json: async () => ({}) }
    })
    const res = await askAIAssistant({ question: 'Which scholarships have deadlines within 30 days?' })
    expect(res.grounded).toBe(true)
    expect(res.answer).toMatch(/deadline/i)
  })

  it('within 365 days works', async () => {
    const res = await askAIAssistant({ question: 'Which scholarships have deadlines within 365 days?' })
    expect(res.grounded).toBe(true)
  })

  it('within 366 days is explicitly rejected', async () => {
    const res = await askAIAssistant({ question: 'Which scholarships have deadlines within 366 days?' })
    expect(res.grounded).toBe(true)
    expect(res.answer).toMatch(/365 days or fewer/i)
    expect(vi.mocked(fetch)).not.toHaveBeenCalled()
  })

  it('within 1000 days is explicitly rejected', async () => {
    const res = await askAIAssistant({ question: 'Which scholarships have deadlines within 1000 days?' })
    expect(res.grounded).toBe(true)
    expect(res.answer).toMatch(/365 days or fewer/i)
    expect(vi.mocked(fetch)).not.toHaveBeenCalled()
  })

  it('comma-separated 1,000 days is explicitly rejected as malformed', async () => {
    const res = await askAIAssistant({ question: 'Which scholarships have deadlines within 1,000 days?' })
    expect(res.grounded).toBe(true)
    expect(res.answer).toMatch(/Invalid deadline window/i)
    expect(vi.mocked(fetch)).not.toHaveBeenCalled()
  })

  it('oversized duration is explicitly rejected', async () => {
    const res = await askAIAssistant({ question: 'Which scholarships have deadlines within 999999999999 days?' })
    expect(res.grounded).toBe(true)
    expect(res.answer).toMatch(/Invalid deadline window/i)
    expect(vi.mocked(fetch)).not.toHaveBeenCalled()
  })

  it('no explicit duration follows intentional default', async () => {
    const snap = {
      meta: { generated_at: '2026-11-17T00:00:00Z', public_record_count: 1 },
      stats: { total: 1 },
      scholarships: [
        { id: 1, title: 'Soon', country: 'X', degree: 'Master', funding: 'F', deadline: '2026-11-20', deadline_date: '2026-11-20', deadline_precision: 'exact', status: 'open', verification_status: 'active', official_source_url: 'https://example.edu/soon' },
      ],
    }
    vi.mocked(fetch).mockImplementation(async (url) => {
      if (String(url).includes('scholarships-snapshot')) return { ok: true, json: async () => snap }
      return { ok: false, status: 500, json: async () => ({}) }
    })
    const res = await askAIAssistant({ question: 'What are the upcoming deadlines soon?' })
    expect(res.grounded).toBe(true)
  })

  it('application question with duration is not deadline retrieval', async () => {
    const res = await askAIAssistant({ question: 'What documents are needed for MEXT if I apply in the next 30 days?' })
    expect(res.grounded).toBe(true)
    expect(res.answer).not.toMatch(/Scholarships with deadlines in the next/i)
  })

  it('document question with duration is not deadline retrieval', async () => {
    const res = await askAIAssistant({ question: 'How to prepare documents over the next 30 days?' })
    expect(res.grounded).toBe(true)
    expect(res.answer).not.toMatch(/Scholarships with deadlines in the next/i)
  })

  it('eligibility question with duration is not deadline retrieval', async () => {
    const res = await askAIAssistant({ question: 'Am I eligible if I start next month?' })
    expect(res.grounded).toBe(true)
    expect(res.answer).not.toMatch(/Scholarships with deadlines in the next/i)
  })
})
