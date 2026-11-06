import { describe, it, expect } from 'vitest'
import { 
  classifyLifecycle, 
  parseDate, 
  parseOpeningDateFromPeriod, 
  getDaysDifference, 
  hasVerifiedFutureCycle,
  formatCountdown,
  formatOpeningCountdown,
  LIFECYCLE
} from '../lifecycle'

describe('Lifecycle Classification', () => {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const todayUTC = new Date(Date.UTC(today.getFullYear(), today.getMonth(), today.getDate()))
  
  const tomorrow = new Date(today)
  tomorrow.setDate(tomorrow.getDate() + 1)
  const tomorrowUTC = new Date(todayUTC)
  tomorrowUTC.setUTCDate(tomorrowUTC.getUTCDate() + 1)
  
  const in15Days = new Date(today)
  in15Days.setDate(in15Days.getDate() + 15)
  const in15DaysUTC = new Date(todayUTC)
  in15DaysUTC.setUTCDate(in15DaysUTC.getUTCDate() + 15)
  
  const in30Days = new Date(today)
  in30Days.setDate(in30Days.getDate() + 30)
  const in30DaysUTC = new Date(todayUTC)
  in30DaysUTC.setUTCDate(in30DaysUTC.getUTCDate() + 30)
  
  const in31Days = new Date(today)
  in31Days.setDate(in31Days.getDate() + 31)
  const in31DaysUTC = new Date(todayUTC)
  in31DaysUTC.setUTCDate(in31DaysUTC.getUTCDate() + 31)
  
  const in60Days = new Date(today)
  in60Days.setDate(in60Days.getDate() + 60)
  const in60DaysUTC = new Date(todayUTC)
  in60DaysUTC.setUTCDate(in60DaysUTC.getUTCDate() + 60)
  
  const in61Days = new Date(today)
  in61Days.setDate(in61Days.getDate() + 61)
  const in61DaysUTC = new Date(todayUTC)
  in61DaysUTC.setUTCDate(in61DaysUTC.getUTCDate() + 61)
  
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)
  const yesterdayUTC = new Date(todayUTC)
  yesterdayUTC.setUTCDate(yesterdayUTC.getUTCDate() - 1)
  
  const lastMonth = new Date(today)
  lastMonth.setMonth(lastMonth.getMonth() - 1)
  const lastMonthUTC = new Date(todayUTC)
  lastMonthUTC.setUTCMonth(lastMonthUTC.getUTCMonth() - 1)
  
  const nextYear = new Date(today)
  nextYear.setFullYear(nextYear.getFullYear() + 1)
  const nextYearUTC = new Date(todayUTC)
  nextYearUTC.setUTCFullYear(nextYearUTC.getUTCFullYear() + 1)

  // Helper to format as YYYY-MM-DD for date fields
  const fmt = (d) => `${d.getUTCFullYear()}-${String(d.getUTCMonth()+1).padStart(2,'0')}-${String(d.getUTCDate()).padStart(2,'0')}`

  describe('parseDate', () => {
    it('parses deadline_date ISO string', () => {
      const scholarship = { deadline_date: fmt(nextYearUTC), deadline_precision: 'exact' }
      const result = parseDate(scholarship, 'deadline')
      expect(result.date).toEqual(new Date(fmt(nextYearUTC) + 'T00:00:00Z'))
      expect(result.isExact).toBe(true)
    })

    it('parses opening_date ISO string', () => {
      const scholarship = { opening_date: fmt(in15DaysUTC), deadline_precision: 'exact' }
      const result = parseDate(scholarship, 'opening')
      expect(result.date).toEqual(new Date(fmt(in15DaysUTC) + 'T00:00:00Z'))
      expect(result.isExact).toBe(true)
    })

    it('falls back to deadline_display', () => {
      const scholarship = { deadline_display: fmt(in30DaysUTC) }
      const result = parseDate(scholarship, 'deadline')
      expect(result.date).toEqual(new Date(fmt(in30DaysUTC) + 'T00:00:00Z'))
    })

    it('falls back to legacy deadline field', () => {
      const scholarship = { deadline: fmt(in30DaysUTC) }
      const result = parseDate(scholarship, 'deadline')
      expect(result.date).toEqual(new Date(fmt(in30DaysUTC) + 'T00:00:00Z'))
    })

    it('parses month-only deadlines through the end of that month', () => {
      const scholarship = { deadline_date: '2027-02-01', deadline_precision: 'month' }
      const result = parseDate(scholarship, 'deadline')
      expect(result.date).toEqual(new Date('2027-02-28T00:00:00Z'))
      expect(result.isExact).toBe(false)
    })

    it('parses month and year deadline labels', () => {
      const scholarship = { deadline_display: 'October 2027', deadline_precision: 'month' }
      const result = parseDate(scholarship, 'deadline')
      expect(result.date).toEqual(new Date('2027-10-31T00:00:00Z'))
    })

    it('returns null for missing dates', () => {
      const scholarship = {}
      const result = parseDate(scholarship, 'deadline')
      expect(result.date).toBeNull()
      expect(result.isExact).toBe(false)
    })

    it('handles invalid date strings', () => {
      const scholarship = { deadline_date: 'invalid-date' }
      const result = parseDate(scholarship, 'deadline')
      expect(result.date).toBeNull()
    })
  })

  describe('parseOpeningDateFromPeriod', () => {
    it('extracts ISO date from "opens 2026-01-15"', () => {
      const scholarship = { application_period: 'Call opens 2026-01-15' }
      const result = parseOpeningDateFromPeriod(scholarship)
      expect(result.date).toEqual(new Date('2026-01-15T00:00:00Z'))
      expect(result.isExact).toBe(true)
    })

    it('extracts month year from "call opens January 2026"', () => {
      const scholarship = { application_period: 'Call opens January 2026' }
      const result = parseOpeningDateFromPeriod(scholarship)
      expect(result.date).toEqual(new Date('2026-01-01T00:00:00Z'))
      expect(result.isExact).toBe(false)
    })

    it('extracts from "2027 cycle: call opens 2027-02-01"', () => {
      const scholarship = { application_period: '2027 cycle: call opens 2027-02-01' }
      const result = parseOpeningDateFromPeriod(scholarship)
      expect(result.date).toEqual(new Date('2027-02-01T00:00:00Z'))
      expect(result.isExact).toBe(true)
    })

    it('handles "re-opens in early February"', () => {
      const scholarship = { application_period: 'Re-opens in early February' }
      const result = parseOpeningDateFromPeriod(scholarship)
      expect(result.date).toBeTruthy()
      expect(result.isExact).toBe(false)
    })

    it('returns null for missing period', () => {
      const scholarship = {}
      const result = parseOpeningDateFromPeriod(scholarship)
      expect(result.date).toBeNull()
    })

    it('returns null for non-matching text', () => {
      const scholarship = { application_period: 'Applications accepted year-round' }
      const result = parseOpeningDateFromPeriod(scholarship)
      expect(result.date).toBeNull()
    })
  })

  describe('getDaysDifference', () => {
    it('returns positive for future dates', () => {
      const diff = getDaysDifference(tomorrowUTC)
      expect(diff).toBe(1)
    })

    it('returns 0 for today', () => {
      const diff = getDaysDifference(todayUTC)
      expect(diff).toBe(0)
    })

    it('returns negative for past dates', () => {
      const diff = getDaysDifference(yesterdayUTC)
      expect(diff).toBe(-1)
    })

    it('returns null for null input', () => {
      const diff = getDaysDifference(null)
      expect(diff).toBeNull()
    })
  })

  describe('hasVerifiedFutureCycle', () => {
    it('detects future year in application_period with "opens"', () => {
      const scholarship = { application_period: '2027 cycle opens 2027-01-01' }
      const result = hasVerifiedFutureCycle(scholarship)
      expect(result).toBe(true)
    })

    it('detects future opening_date', () => {
      const scholarship = { opening_date: fmt(nextYearUTC) }
      const result = hasVerifiedFutureCycle(scholarship)
      expect(result).toBe(true)
    })

    it('returns false for past opening_date', () => {
      const scholarship = { opening_date: fmt(lastMonthUTC) }
      const result = hasVerifiedFutureCycle(scholarship)
      expect(result).toBe(false)
    })

    it('returns false for missing dates', () => {
      const scholarship = {}
      const result = hasVerifiedFutureCycle(scholarship)
      expect(result).toBe(false)
    })

    it('returns false for generic text without future indicators', () => {
      const scholarship = { application_period: 'Applications accepted year-round' }
      const result = hasVerifiedFutureCycle(scholarship)
      expect(result).toBe(false)
    })

    it('recognises a documented recurring schedule as a future cycle', () => {
      const scholarship = {
        deadline_display: 'Three calls annually: March 15, July 15, November 15',
      }
      expect(hasVerifiedFutureCycle(scholarship)).toBe(true)
    })
  })

  describe('classifyLifecycle - CLOSED', () => {
    it('returns CLOSED for explicit status=closed without future cycle', () => {
      const scholarship = { status: 'closed', deadline_date: fmt(lastMonthUTC) }
      const result = classifyLifecycle(scholarship)
      expect(result.status).toBe(LIFECYCLE.CLOSED)
    })

    it('returns CLOSED for is_archived without future cycle', () => {
      const scholarship = { is_archived: true, deadline_date: fmt(lastMonthUTC) }
      const result = classifyLifecycle(scholarship)
      expect(result.status).toBe(LIFECYCLE.CLOSED)
    })

    it('returns CLOSED for past deadline without future cycle', () => {
      const scholarship = { status: 'open', deadline_date: fmt(lastMonthUTC) }
      const result = classifyLifecycle(scholarship)
      expect(result.status).toBe(LIFECYCLE.CLOSED)
    })

    it('does NOT return CLOSED for archived WITH verified future cycle', () => {
      const scholarship = { 
        is_archived: true, 
        deadline_date: fmt(lastMonthUTC),
        application_period: '2027 cycle opens 2027-01-01'
      }
      const result = classifyLifecycle(scholarship)
      expect(result.status).not.toBe(LIFECYCLE.CLOSED)
      expect([LIFECYCLE.UPCOMING, LIFECYCLE.OPENING]).toContain(result.status)
    })

    it('does NOT return CLOSED for past deadline WITH verified future cycle', () => {
      const scholarship = { 
        status: 'open', 
        deadline_date: fmt(lastMonthUTC),
        opening_date: fmt(nextYearUTC)
      }
      const result = classifyLifecycle(scholarship)
      expect(result.status).not.toBe(LIFECYCLE.CLOSED)
      expect([LIFECYCLE.UPCOMING, LIFECYCLE.OPENING]).toContain(result.status)
    })

    it('keeps a closed current round visible as upcoming when a recurring cycle is documented', () => {
      const scholarship = {
        status: 'closed',
        deadline_date: fmt(lastMonthUTC),
        deadline_display: 'Three calls annually: March 15, July 15, November 15',
      }
      const result = classifyLifecycle(scholarship)
      expect(result.status).toBe(LIFECYCLE.UPCOMING)
    })
  })

  describe('classifyLifecycle - CLOSING_SOON', () => {
    it('returns CLOSING_SOON for deadline within 30 days', () => {
      const scholarship = { status: 'open', deadline_date: fmt(in15DaysUTC) }
      const result = classifyLifecycle(scholarship)
      expect(result.status).toBe(LIFECYCLE.CLOSING_SOON)
    })

    it('returns CLOSING_SOON for deadline today', () => {
      const scholarship = { status: 'open', deadline_date: fmt(todayUTC) }
      const result = classifyLifecycle(scholarship)
      expect(result.status).toBe(LIFECYCLE.CLOSING_SOON)
    })

    it('returns CLOSING_SOON for deadline tomorrow', () => {
      const scholarship = { status: 'open', deadline_date: fmt(tomorrowUTC) }
      const result = classifyLifecycle(scholarship)
      expect(result.status).toBe(LIFECYCLE.CLOSING_SOON)
    })

    it('returns CLOSING_SOON at exactly 30 days boundary', () => {
      const scholarship = { status: 'open', deadline_date: fmt(in30DaysUTC) }
      const result = classifyLifecycle(scholarship)
      expect(result.status).toBe(LIFECYCLE.CLOSING_SOON)
    })
  })

  describe('classifyLifecycle - UPCOMING', () => {
    it('returns UPCOMING for explicit status=upcoming', () => {
      const scholarship = { status: 'upcoming', opening_date: fmt(in61DaysUTC) }
      const result = classifyLifecycle(scholarship)
      expect(result.status).toBe(LIFECYCLE.UPCOMING)
    })

    it('returns UPCOMING for opening_date > 60 days', () => {
      const scholarship = { status: 'open', opening_date: fmt(in61DaysUTC) }
      const result = classifyLifecycle(scholarship)
      expect(result.status).toBe(LIFECYCLE.UPCOMING)
    })

    it('returns UPCOMING for opening_date at exactly 61 days', () => {
      const scholarship = { status: 'open', opening_date: fmt(in61DaysUTC) }
      const result = classifyLifecycle(scholarship)
      expect(result.status).toBe(LIFECYCLE.UPCOMING)
    })
  })

  describe('classifyLifecycle - OPENING', () => {
    it('returns OPENING for opening_date within 60 days', () => {
      const scholarship = { status: 'open', opening_date: fmt(in15DaysUTC) }
      const result = classifyLifecycle(scholarship)
      expect(result.status).toBe(LIFECYCLE.OPENING)
    })

    it('returns OPENING for opening_date today', () => {
      const scholarship = { status: 'open', opening_date: fmt(todayUTC) }
      const result = classifyLifecycle(scholarship)
      expect(result.status).toBe(LIFECYCLE.OPENING)
    })

    it('returns OPENING at exactly 60 days boundary', () => {
      const scholarship = { status: 'open', opening_date: fmt(in60DaysUTC) }
      const result = classifyLifecycle(scholarship)
      expect(result.status).toBe(LIFECYCLE.OPENING)
    })

    it('returns OPENING for opening_date tomorrow', () => {
      const scholarship = { status: 'open', opening_date: fmt(tomorrowUTC) }
      const result = classifyLifecycle(scholarship)
      expect(result.status).toBe(LIFECYCLE.OPENING)
    })
  })

  describe('classifyLifecycle - OPEN', () => {
    it('returns OPEN for status=open with deadline > 30 days', () => {
      const scholarship = { status: 'open', deadline_date: fmt(in31DaysUTC) }
      const result = classifyLifecycle(scholarship)
      expect(result.status).toBe(LIFECYCLE.OPEN)
    })

    it('returns OPEN for status=open with no opening_date and deadline far future', () => {
      const scholarship = { status: 'open', deadline_date: fmt(nextYearUTC) }
      const result = classifyLifecycle(scholarship)
      expect(result.status).toBe(LIFECYCLE.OPEN)
    })
  })

  describe('classifyLifecycle - UNKNOWN', () => {
    it('returns UNKNOWN for missing dates and unknown status', () => {
      const scholarship = { status: 'unknown' }
      const result = classifyLifecycle(scholarship)
      expect(result.status).toBe(LIFECYCLE.UNKNOWN)
      expect(result.label).toBe('Check deadline')
      expect(result.description).toMatch(/official source before applying/)
    })

    it('returns UNKNOWN for missing deadline and opening_date', () => {
      const scholarship = { status: 'open' }
      const result = classifyLifecycle(scholarship)
      expect(result.status).toBe(LIFECYCLE.UNKNOWN)
    })
  })

  describe('formatCountdown', () => {
    it('formats "Deadline passed" for negative days', () => {
      expect(formatCountdown(-1, true)).toBe('Deadline passed')
    })

    it('formats "Deadline today" for 0 days', () => {
      expect(formatCountdown(0, true)).toBe('Deadline today')
    })

    it('formats "1 day left" for 1 day', () => {
      expect(formatCountdown(1, true)).toBe('1 day left')
    })

    it('formats "N days left" for 2-7 days', () => {
      expect(formatCountdown(3, true)).toBe('3 days left')
      expect(formatCountdown(7, true)).toBe('7 days left')
    })

    it('formats "N days left" for 8-30 days', () => {
      expect(formatCountdown(15, true)).toBe('15 days left')
    })

    it('uses ~ prefix for non-exact dates > 30 days', () => {
      expect(formatCountdown(45, false)).toBe('~45 days left')
    })

    it('shows exact number for exact dates > 30 days', () => {
      expect(formatCountdown(45, true)).toBe('45 days left')
    })

    it('returns null for null input', () => {
      expect(formatCountdown(null, true)).toBeNull()
    })
  })

  describe('formatOpeningCountdown', () => {
    it('formats "Opened" for negative days', () => {
      expect(formatOpeningCountdown(-1, true)).toBe('Opened')
    })

    it('formats "Opens today" for 0 days', () => {
      expect(formatOpeningCountdown(0, true)).toBe('Opens today')
    })

    it('formats "Opens tomorrow" for 1 day', () => {
      expect(formatOpeningCountdown(1, true)).toBe('Opens tomorrow')
    })

    it('formats "Opens in N days" for 2-7 days', () => {
      expect(formatOpeningCountdown(3, true)).toBe('Opens in 3 days')
    })

    it('formats "Opens in N days" for 8-30 days', () => {
      expect(formatOpeningCountdown(15, true)).toBe('Opens in 15 days')
    })

    it('uses ~ prefix for non-exact dates > 30 days', () => {
      expect(formatOpeningCountdown(45, false)).toBe('Opens in ~45 days')
    })

    it('returns null for null input', () => {
      expect(formatOpeningCountdown(null, true)).toBeNull()
    })
  })

  describe('Precedence order', () => {
    it('CLOSED takes precedence over CLOSING_SOON', () => {
      const scholarship = { 
        status: 'closed', 
        deadline_date: fmt(tomorrowUTC) 
      }
      const result = classifyLifecycle(scholarship)
      expect(result.status).toBe(LIFECYCLE.CLOSED)
    })

    it('UPCOMING takes precedence over CLOSING_SOON (future opening supersedes deadline)', () => {
      const scholarship = { 
        opening_date: fmt(in61DaysUTC),
        deadline_date: fmt(in15DaysUTC)
      }
      const result = classifyLifecycle(scholarship)
      expect(result.status).toBe(LIFECYCLE.UPCOMING)
    })

    it('UPCOMING takes precedence over OPENING', () => {
      const scholarship = { 
        opening_date: fmt(in61DaysUTC),
        deadline_date: fmt(in61DaysUTC)
      }
      const result = classifyLifecycle(scholarship)
      expect(result.status).toBe(LIFECYCLE.UPCOMING)
    })

    it('OPENING takes precedence over OPEN', () => {
      const scholarship = { 
        status: 'open',
        opening_date: fmt(in15DaysUTC),
        deadline_date: fmt(nextYearUTC)
      }
      const result = classifyLifecycle(scholarship)
      expect(result.status).toBe(LIFECYCLE.OPENING)
    })
  })
})