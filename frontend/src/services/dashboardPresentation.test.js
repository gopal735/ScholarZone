/**
 * Presentation logic.
 *
 * Every case here exists because the wrong answer is not a cosmetic bug. The
 * engine sends `null` for a fit score it could not evaluate, for a deadline it
 * could not pin down, and for a completeness measure with nothing to measure.
 * Turning any of those into a number is how "we do not know" becomes "zero",
 * which a reader cannot distinguish from a real measurement.
 */

import { describe, expect, it } from 'vitest'
import {
  deadlineText,
  fitLabel,
  isExactDeadline,
  readinessLabel,
  strengthPercent,
  titleCaseKey,
  verificationLabel,
} from '../services/dashboardPresentation'

describe('titleCaseKey', () => {
  it('renders an engine bucket key as words', () => {
    expect(titleCaseKey('CLOSING_SOON')).toBe('Closing soon')
    expect(titleCaseKey('READY_WITH_CHECKS')).toBe('Ready with checks')
  })

  it('returns an empty string for an absent value rather than throwing', () => {
    expect(titleCaseKey(null)).toBe('')
    expect(titleCaseKey(undefined)).toBe('')
  })
})

describe('verificationLabel', () => {
  it("uses the server's own display field when it sent one", () => {
    expect(verificationLabel({ verification_display: 'Confirm with provider' })).toBe(
      'Confirm with provider',
    )
  })

  it('never says Verified for a record that is not verified', () => {
    expect(verificationLabel({ verified: false })).toBe('Confirm with provider')
    expect(verificationLabel({ verification_status: 'needs_review' })).toBe('Confirm with provider')
  })

  it('says Verified only when the server said so', () => {
    expect(verificationLabel({ verified: true })).toBe('Verified')
  })
})

describe('deadlineText', () => {
  it('counts down using the engine figure', () => {
    expect(deadlineText({ days_remaining: 14 })).toBe('14 days left')
    expect(deadlineText({ days_remaining: 1 })).toBe('1 day left')
    expect(deadlineText({ days_remaining: 0 })).toBe('Closes today')
  })

  it('reports a passed deadline as closed rather than as a negative count', () => {
    expect(deadlineText({ days_remaining: -3 })).toBe('Closed')
  })

  it('never renders an unknown deadline as zero days left', () => {
    // This is the case that matters: a rolling or unpublished deadline is an
    // open round, and "0 days left" would read as overdue.
    expect(deadlineText({ days_remaining: null, deadline: 'Reviewed on a rolling basis' })).toBe(
      'Reviewed on a rolling basis',
    )
  })

  it('says so plainly when nothing is published at all', () => {
    expect(deadlineText({ days_remaining: null, deadline: null })).toBe('No fixed date published')
  })
})

describe('isExactDeadline', () => {
  it('is true only for a day-specific published date', () => {
    expect(isExactDeadline({ deadline_precision: 'exact' })).toBe(true)
    expect(isExactDeadline({ deadline_precision: 'month' })).toBe(false)
    expect(isExactDeadline({ deadline_precision: 'rolling' })).toBe(false)
    expect(isExactDeadline({})).toBe(false)
  })
})

describe('fitLabel', () => {
  it('prefers the engine band display over any local formatting', () => {
    expect(fitLabel({ fit_label_display: 'Very strong fit', fit_score: 88 })).toBe('Very strong fit')
  })

  it('names the absence rather than showing a zero', () => {
    expect(fitLabel({ fit_score: null })).toBe('Not evaluated')
  })

  it('shows the score only when there is one', () => {
    expect(fitLabel({ fit_score: 72 })).toBe('72 fit score')
  })
})

describe('readinessLabel', () => {
  it('keeps readiness separate from fit', () => {
    expect(readinessLabel({ readiness_label: 'Ready' })).toBe('Ready')
    expect(readinessLabel({ readiness_label: null })).toBe('Readiness not evaluated')
  })
})

describe('strengthPercent', () => {
  it('returns null when there is nothing measured', () => {
    expect(strengthPercent(null)).toBeNull()
    expect(strengthPercent(undefined)).toBeNull()
  })

  it('clamps rather than emitting an unrenderable width', () => {
    expect(strengthPercent(74.4)).toBe(74)
    expect(strengthPercent(-5)).toBe(0)
    expect(strengthPercent(140)).toBe(100)
  })
})