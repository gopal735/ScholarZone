import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { askAIAssistant, setAIEnabled } from '../aiAssistant'

describe('askAIAssistant deadline intent routing', () => {
  beforeEach(() => {
    setAIEnabled(false)
    vi.stubGlobal('fetch', vi.fn())
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    setAIEnabled(false)
  })

  it('routes deadline question with duration to deadline retrieval', async () => {
    const snap = {
      meta: { generated_at: '2026-11-17T00:00:00Z', public_record_count: 1 },
      stats: { total: 1 },
      scholarships: [
        { id: 1, title: 'SoonScholarship', country: 'X', degree: 'Master', funding: 'F', deadline: '2026-11-20', deadline_date: '2026-11-20', deadline_precision: 'exact', status: 'open', verification_status: 'active' },
      ],
    }
    vi.mocked(fetch).mockImplementation(async (url) => {
      if (String(url).includes('scholarships-snapshot')) {
        return { ok: true, json: async () => snap }
      }
      return { ok: false, status: 500, json: async () => ({}) }
    })
    const res = await askAIAssistant({ question: 'Which scholarships have deadlines within 30 days?' })
    expect(res.grounded).toBe(true)
    expect(res.answer).toMatch(/deadline/i)
  })

  it('does not route application question with duration to deadline retrieval', async () => {
    const res = await askAIAssistant({ question: 'What documents are needed for MEXT if I apply in the next 30 days?' })
    expect(res.grounded).toBe(true)
    expect(res.answer).not.toMatch(/Scholarships with deadlines in the next/i)
  })

  it('does not route document question with duration to deadline retrieval', async () => {
    const res = await askAIAssistant({ question: 'How to prepare documents over the next 30 days?' })
    expect(res.grounded).toBe(true)
    expect(res.answer).not.toMatch(/Scholarships with deadlines in the next/i)
  })

  it('does not route eligibility question with duration to deadline retrieval', async () => {
    const res = await askAIAssistant({ question: 'Am I eligible if I start next month?' })
    expect(res.grounded).toBe(true)
    expect(res.answer).not.toMatch(/Scholarships with deadlines in the next/i)
  })

  it('deadline question without explicit number still works', async () => {
    const res = await askAIAssistant({ question: 'What are the upcoming deadlines soon?' })
    expect(res.grounded).toBe(true)
  })
})
