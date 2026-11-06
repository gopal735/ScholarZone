import { describe, expect, it } from 'vitest'
import { getScholarshipStatus } from '../scholarshipPresentation'

describe('getScholarshipStatus', () => {
  it('uses the derived lifecycle instead of a stale stored open status', () => {
    expect(getScholarshipStatus({
      status: 'open',
      deadline_date: '2000-01-01',
    }).className).toBe('closed')
  })

  it('keeps upcoming opportunities out of the open state', () => {
    expect(getScholarshipStatus({
      status: 'upcoming',
      deadline_date: '2999-01-01',
    }).className).toBe('upcoming')
  })
})
