import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { clearSnapshotCache, fetchScholarshipsFromSnapshot } from '../staticScholarshipService'

const FIXED_NOW = new Date('2026-11-17T12:00:00Z')

const snap = {
  meta: { generated_at: '2026-11-17T00:00:00Z', public_record_count: 5 },
  stats: { total: 5 },
  scholarships: [
    { id: 1, title: 'Expired', country: 'X', degree: 'Master', funding: 'F', deadline: '2026-11-16', deadline_date: '2026-11-16', deadline_precision: 'exact', status: 'open', verification_status: 'active' },
    { id: 2, title: 'Today', country: 'X', degree: 'Master', funding: 'F', deadline: '2026-11-17', deadline_date: '2026-11-17', deadline_precision: 'exact', status: 'open', verification_status: 'active' },
    { id: 3, title: 'Day30', country: 'X', degree: 'Master', funding: 'F', deadline: '2026-12-17', deadline_date: '2026-12-17', deadline_precision: 'exact', status: 'open', verification_status: 'active' },
    { id: 4, title: 'Day31', country: 'X', degree: 'Master', funding: 'F', deadline: '2026-12-18', deadline_date: '2026-12-18', deadline_precision: 'exact', status: 'open', verification_status: 'active' },
    { id: 5, title: 'NoDeadline', country: 'X', degree: 'Master', funding: 'F', deadline: '', status: 'open', verification_status: 'active' },
    { id: 6, title: 'DisplayOnly', country: 'X', degree: 'Master', funding: 'F', deadline: '2026-11-20', deadline_display: '2026-11-20', deadline_date: null, deadline_precision: 'exact', status: 'open', verification_status: 'active' },
    { id: 7, title: 'MonthPrecision', country: 'X', degree: 'Master', funding: 'F', deadline: '2026-12-01', deadline_date: '2026-12-01', deadline_precision: 'month', status: 'open', verification_status: 'active' },
  ],
}

describe('static deadline_within_days parity', () => {
  beforeEach(() => {
    clearSnapshotCache()
    vi.useFakeTimers()
    vi.setSystemTime(FIXED_NOW)
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => snap })))
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('includes today and day 30, excludes expired/day31/null', async () => {
    const res = await fetchScholarshipsFromSnapshot({ deadline_within_days: 30, limit: 50 })
    const titles = res.items.map((i) => i.title)
    expect(titles).toContain('Today')
    expect(titles).toContain('Day30')
    expect(titles).not.toContain('Expired')
    expect(titles).not.toContain('Day31')
    expect(titles).not.toContain('NoDeadline')
    expect(titles).not.toContain('DisplayOnly')
    expect(titles).toContain('MonthPrecision')
  })

  it('ignores unsupported values above 365 (no silent wider window)', async () => {
    const res = await fetchScholarshipsFromSnapshot({ deadline_within_days: 400, limit: 50 })
    // Unsupported window returns no unfiltered records (not a silent wider window).
    expect(res.items).toHaveLength(0)
  })
})
