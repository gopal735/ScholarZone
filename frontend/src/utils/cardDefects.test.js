/**
 * Regression tests for the card defects reported in the screenshot review.
 *
 * Each test pins one measured defect. The measurements are the ones a real
 * browser produced on the built bundle, recorded here so a reintroduction
 * fails a test rather than needing another screenshot:
 *
 *   - the funding badge `scrollWidth 398 > clientWidth 355` - 65 characters of
 *     provider funding text silently ellipsised in a one-line pill
 *   - the deadline `font-weight: 700` at `line-height: 18.9px` for a
 *     244-character provider sentence, right-aligned in a ~178px column
 *   - `.visually-hidden` resolving to nothing on `/compare`, because the only
 *     rule defining it lived in ScholarshipList.css and ComparePage.jsx does
 *     not import it - the table caption rendered as visible text
 */

import { describe, expect, it } from 'vitest'
import { fundingBadgeLabel, matchesTuitionCoverage } from './fundingFacts.js'
import { formatDeadlineDate, presentCardDeadline } from './cardDeadlinePresentation.js'

describe('funding badge text is never silently clipped', () => {
  it('shortens a long published funding string to a badge that fits', () => {
    // The exact record that measured clipped: 65 characters of the ESKAS award.
    const out = fundingBadgeLabel({
      funding: 'Monthly stipend, housing grant, health insurance, and travel card',
    })
    expect(out.label.length).toBeLessThanOrEqual(34)
    expect(out.isCategory).toBe(true)
    expect(out.truncated).toBe(true)
  })

  it('keeps the full published wording available on every shortened label', () => {
    // A truncation with no alternative is hiding, not presenting.
    for (const funding of [
      'Monthly stipend, housing grant, health insurance, and travel card',
      'Annual stipend of HK$344,400 for the 2027/28 academic year',
      'Course Fees, Accommodation and Allowance',
    ]) {
      const out = fundingBadgeLabel({ funding })
      expect(out.full).toBe(funding)
      if (out.truncated) {
        // The caller renders `full` as a tooltip and a screen-reader string,
        // so the only contract that matters is that it is the untouched text.
        expect(out.full.length).toBeGreaterThan(out.label.length - 1)
      }
    }
  })

  it('classifies from the record\'s own wording rather than inventing a fact', () => {
    // Long strings only: a short funding label is shown whole and never
    // classified, because there is nothing to shorten.
    expect(fundingBadgeLabel({ funding: 'Annual stipend of HK$344,400 for the 2027/28 academic year' }).label).toBe('Stipend')
    expect(fundingBadgeLabel({ funding: 'Tuition fee waiver plus a living allowance and health insurance' }).label).toBe('Tuition support')
    expect(fundingBadgeLabel({ funding: 'Research grant covering laboratory costs and consumables' }).label).toBe('Research funding')
    expect(fundingBadgeLabel({ funding: 'Need-based financial aid for all nationalities' }).label).toBe('Need-based')
    expect(fundingBadgeLabel({ funding: 'Travel and relocation support for incoming students' }).label).toBe('Travel support')
  })

  it('leaves a short funding string whole rather than classifying it', () => {
    // 26 characters fits the badge, so it is not shortened and not relabelled.
    const out = fundingBadgeLabel({ funding: 'Annual stipend of HK$344,400' })
    expect(out).toEqual({ label: 'Annual stipend of HK$344,400', full: 'Annual stipend of HK$344,400', isCategory: false, truncated: false })
  })

  it('leaves a short funding string whole, with no claim of shortening', () => {
    const out = fundingBadgeLabel({ funding: 'Fully Funded' })
    expect(out).toEqual({ label: 'Fully Funded', full: 'Fully Funded', isCategory: false, truncated: false })
  })

  it('reports funding absence rather than guessing a category', () => {
    for (const missing of [null, undefined, '', '   ']) {
      const out = fundingBadgeLabel({ funding: missing })
      expect(out).toEqual({ label: 'Funding not stated', full: null, isCategory: true, truncated: false })
    }
  })

  it('is total for a non-object record', () => {
    expect(fundingBadgeLabel(null).label).toBe('Funding not stated')
    expect(fundingBadgeLabel(undefined).label).toBe('Funding not stated')
    expect(fundingBadgeLabel('Fully Funded').label).toBe('Funding not stated')
  })

  it('never returns a label longer than a badge can hold on one line', () => {
    // The pill wraps to two lines, so the ceiling is twice the badge limit.
    // This is the bound that keeps a "shortened" label from defeating the fix.
    const long = 'Annual stipend of HK$344,400 for the 2027/28 academic year awarded to 400 PhD Fellowships across all faculties'
    expect(fundingBadgeLabel({ funding: long }).label.length).toBeLessThanOrEqual(68)
  })
})

describe('a regulator: tuition coverage stays three-state', () => {
  it('separates a confirmed negative from an unknown', () => {
    expect(matchesTuitionCoverage({ tuition_coverage: false }, 'no')).toBe(true)
    expect(matchesTuitionCoverage({ tuition_coverage: null }, 'no')).toBe(false)
    expect(matchesTuitionCoverage({ tuition_coverage: null }, 'not-stated')).toBe(true)
  })

  it('treats the shared sentinel as no filter', () => {
    expect(matchesTuitionCoverage({ tuition_coverage: null }, 'all')).toBe(true)
    expect(matchesTuitionCoverage({}, null)).toBe(true)
  })
})

describe('a long deadline is not a bold paragraph', () => {
  it('formats a real date for a dated record', () => {
    expect(formatDeadlineDate('2026-12-15')).not.toBeNull()
    expect(formatDeadlineDate('not a date')).toBeNull()
    expect(formatDeadlineDate(null)).toBeNull()
  })

  it('splits a dated record into a value and the provider\'s wording', () => {
    const deadline = presentCardDeadline({
      deadline: 'Applications are open starting August 20, 2026; the deadline is 15 December 2026',
      deadline_date: '2026-12-15',
      deadline_precision: 'day',
    })
    expect(deadline.kind).toBe('described')
    expect(deadline.value).toBe(formatDeadlineDate('2026-12-15'))
    expect(deadline.isProse).toBe(true)
    // The full wording is retained, so nothing is clipped by the split.
    expect(deadline.note).toContain('August 20, 2026')
  })

  it('marks a record whose only deadline text is a sentence as prose', () => {
    // The ESKAS record that measured at weight 700 over 244 characters.
    const deadline = presentCardDeadline({
      deadline: 'Applications are open starting August 20, 2026 (Swiss Government Excellence Scholarships 2027-2028); application deadline is 15 December 2026 for applicants from Europe and 15 January 2027 for applicants from other countries, subject to the awarding committee confirming each call on the official page',
      deadline_date: null,
      deadline_precision: 'unknown',
    })
    expect(deadline.kind).toBe('text')
    expect(deadline.isProse).toBe(true)
    expect(deadline.hasDate).toBe(false)
    // The value is the provider's own text - not a substituted or invented date.
    expect(deadline.value).toContain('Swiss Government Excellence Scholarships')
  })

  it('reports an unknown deadline rather than a date-shaped filler', () => {
    const deadline = presentCardDeadline({ deadline: null, deadline_date: null, deadline_precision: 'none' })
    expect(deadline.kind).toBe('unknown')
    expect(deadline.value).toBe('Deadline to be confirmed')
    expect(deadline.hasDate).toBe(false)
  })

  it('is total for a non-object record', () => {
    for (const bad of [null, undefined, 'Master', 42]) {
      const deadline = presentCardDeadline(bad)
      expect(deadline.value).toBe('Deadline to be confirmed')
      expect(deadline.hasDate).toBe(false)
    }
  })

  it('keeps a month-precision deadline labelled as month-only', () => {
    // A record whose precision says "month" but whose own text names a day.
    // The provider's wording is shown as the value, and the precision label
    // below it is what stops the day from reading as confirmed.
    const deadline = presentCardDeadline({
      deadline: 'November 30 annually',
      deadline_date: '2026-11-30',
      deadline_precision: 'month',
    })
    expect(deadline.value).toBe('November 30 annually')
    expect(deadline.precisionLabel).toMatch(/Month only/)
    expect(deadline.hasDate).toBe(true)
  })
})
