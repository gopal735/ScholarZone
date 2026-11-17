import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { askAIAssistant, setAIEnabled } from '../aiAssistant'
import { clearSnapshotCache } from '../staticScholarshipService'

describe('aiAssistant cycle-year preservation and duration boundaries', () => {
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
  })

  function mockSnapshot(snap) {
    vi.mocked(fetch).mockImplementation(async (url) => {
      if (String(url).includes('scholarships-snapshot')) {
        return { ok: true, json: async () => snap }
      }
      return { ok: false, status: 500, json: async () => ({}) }
    })
  }

  const snap2027 = {
    meta: { generated_at: '2026-11-17T00:00:00Z', public_record_count: 1 },
    stats: { total: 1 },
    scholarships: [
      { id: 1, title: 'MEXT 2027 Scholarship', country: 'Japan', degree: 'Master', funding: 'F', deadline: '2026-11-20', deadline_date: '2026-11-20', deadline_precision: 'exact', status: 'open', verification_status: 'active', official_source_url: 'https://example.edu/mext' },
    ],
  }

  it('preserves 2027 cycle year in search (MEXT 2027)', async () => {
    mockSnapshot(snap2027)
    const res = await askAIAssistant({ question: 'Which MEXT 2027 scholarships have deadlines within 30 days?' })
    expect(res.grounded).toBe(true)
    expect(res.answer).toMatch(/MEXT 2027/)
  })

  it('preserves 2027 for GKS within 60 days', async () => {
    const snap = {
      meta: { generated_at: '2026-11-17T00:00:00Z', public_record_count: 1 },
      stats: { total: 1 },
      scholarships: [
        { id: 2, title: 'GKS 2027 Scholarship', country: 'Korea', degree: 'Master', funding: 'F', deadline: '2026-11-20', deadline_date: '2026-11-20', deadline_precision: 'exact', status: 'open', verification_status: 'active', official_source_url: 'https://example.edu/gks' },
      ],
    }
    mockSnapshot(snap)
    const res = await askAIAssistant({ question: 'GKS 2027 scholarships closing in 60 days' })
    expect(res.grounded).toBe(true)
    expect(res.answer).toMatch(/GKS 2027/)
  })

  it('rejects 366 days explicitly', async () => {
    const res = await askAIAssistant({ question: 'Which scholarships have deadlines within 366 days?' })
    expect(res.grounded).toBe(true)
    expect(res.answer).toMatch(/365 days or fewer/i)
  })

  it('rejects 1000 days explicitly', async () => {
    const res = await askAIAssistant({ question: 'Which scholarships have deadlines within 1000 days?' })
    expect(res.grounded).toBe(true)
    expect(res.answer).toMatch(/365 days or fewer/i)
  })

  it('rejects 10000 days explicitly', async () => {
    const res = await askAIAssistant({ question: 'Which scholarships have deadlines within 10000 days?' })
    expect(res.grounded).toBe(true)
    expect(res.answer).toMatch(/365 days or fewer/i)
  })

  it('does not silently convert 1000 days to 30', async () => {
    const res = await askAIAssistant({ question: 'Which scholarships have deadlines within 1000 days?' })
    expect(res.answer).not.toMatch(/in the next 30 days/i)
  })

  it('1 day works', async () => {
    mockSnapshot(snap2027)
    const res = await askAIAssistant({ question: 'Which scholarships have deadlines within 1 day?' })
    expect(res.grounded).toBe(true)
  })

  it('365 days works', async () => {
    mockSnapshot(snap2027)
    const res = await askAIAssistant({ question: 'Which scholarships have deadlines within 365 days?' })
    expect(res.grounded).toBe(true)
  })

  it('comma-separated duration is explicitly rejected', async () => {
    const res = await askAIAssistant({ question: 'Which scholarships have deadlines within 1,000 days?' })
    expect(res.grounded).toBe(true)
    expect(res.answer).toMatch(/Invalid deadline window/i)
  })

  it('oversized duration is explicitly rejected', async () => {
    const res = await askAIAssistant({ question: 'Which scholarships have deadlines within 999999999999 days?' })
    expect(res.grounded).toBe(true)
    expect(res.answer).toMatch(/Invalid deadline window/i)
  })

  it('zero days is explicitly rejected (not converted to 30)', async () => {
    const res = await askAIAssistant({ question: 'Which scholarships have deadlines within 0 days?' })
    expect(res.grounded).toBe(true)
    expect(res.answer).toMatch(/Invalid deadline window/i)
  })

  it('MEXT 2027 included, MEXT 2026 excluded (both in window)', async () => {
    const snap = {
      meta: { generated_at: '2026-11-17T00:00:00Z', public_record_count: 2 },
      stats: { total: 2 },
      scholarships: [
        { id: 1, title: 'MEXT 2027 Scholarship', country: 'Japan', degree: 'Master', funding: 'F', deadline: '2026-11-20', deadline_date: '2026-11-20', deadline_precision: 'exact', status: 'open', verification_status: 'active', official_source_url: 'https://example.edu/mext2027' },
        { id: 2, title: 'MEXT 2026 Scholarship', country: 'Japan', degree: 'Master', funding: 'F', deadline: '2026-11-20', deadline_date: '2026-11-20', deadline_precision: 'exact', status: 'open', verification_status: 'active', official_source_url: 'https://example.edu/mext2026' },
      ],
    }
    vi.mocked(fetch).mockImplementation(async (url) => {
      if (String(url).includes('scholarships-snapshot')) {
        return { ok: true, json: async () => snap }
      }
      return { ok: false, status: 500, json: async () => ({}) }
    })
    clearSnapshotCache()
    const res = await askAIAssistant({ question: 'Which 2027 MEXT scholarships have deadlines within 30 days?' })
    expect(res.grounded).toBe(true)
    expect(res.answer).toMatch(/MEXT 2027/)
    expect(res.answer).not.toMatch(/MEXT 2026/)
  })
})
