import { describe, expect, it } from 'vitest'
import { toScholarship } from '../staticScholarshipService'

describe('toScholarship opening_date preservation', () => {
  it('preserves opening_date and opening_display', () => {
    const out = toScholarship({ id: 1, title: 'T', country: 'X', degree: 'M', funding: 'F', opening_date: '2026-12-01', opening_display: 'Dec 2026', status: 'open', verification_status: 'active' })
    expect(out.opening_date).toBe('2026-12-01')
    expect(out.opening_display).toBe('Dec 2026')
  })
  it('does not fabricate opening_date when missing', () => {
    const out = toScholarship({ id: 2, title: 'T2', country: 'X', degree: 'M', funding: 'F', status: 'open', verification_status: 'active' })
    expect(out.opening_date).toBeUndefined()
  })
})
