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

import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import {
  fundingBadgeLabel,
  isFullyFundedStatement,
  matchesTuitionCoverage,
} from './fundingFacts.js'
import { formatDeadlineDate, presentCardDeadline } from './cardDeadlinePresentation.js'

/**
 * Category inference is conservative.
 *
 * These pin the review finding: a substring matcher reads "fully funded"
 * inside a sentence that says the opposite of it. "This award is not fully
 * funded, but includes a monthly stipend" would receive a "Fully funded"
 * badge, which is the one claim this product cannot afford to assert loosely.
 */
describe('a negated funding statement is never classified as fully funded', () => {
  it('rejects a negation standing in front of the funding term', () => {
    for (const text of [
      'This award is not fully funded, but includes a monthly stipend',
      'Not fully funded; tuition waiver only',
      'This is not a fully funded award',
      'No full funding available for this programme',
      'The programme is never fully funded',
      'It is not a fully funded scholarship despite the title',
      'This is not a fully funded scholarship, only a partial tuition waiver',
    ]) {
      expect(isFullyFundedStatement(text), text).toBe(false)
    }
  })

  it('rejects a funding-level partial qualifier that void the claim', () => {
    for (const text of [
      'Fully funded or partially funded depending on the faculty',
      'Fully funded or part funded depending on your college',
      'The award may be funded fully or in part depending on the department',
    ]) {
      expect(isFullyFundedStatement(text), text).toBe(false)
    }
  })

  it('does not let a later clause rescue a negated first one', () => {
    // Clause-level splitter: the second clause is affirmative, the first denies.
    expect(isFullyFundedStatement('Not fully funded; a monthly stipend is available')).toBe(false)
    expect(isFullyFundedStatement('Not fully funded, but a stipend is included')).toBe(false)
  })

  it('still accepts an affirmative statement that happens to contain "no"', () => {
    // The proximate-negation rule exists for this case: a broad "no" test would
    // reject an unambiguously fully funded award.
    expect(isFullyFundedStatement('The award is fully funded with no obligation')).toBe(true)
    expect(isFullyFundedStatement('Fully Funded, no commitment required')).toBe(true)
  })

  it('accepts a qualifier that applies to a component rather than the award', () => {
    // "partial living stipend" qualifies the stipend; the award is still fully
    // funded per the provider's own field. Audited record id=472.
    expect(isFullyFundedStatement('Full funding (partial living stipend)')).toBe(true)
  })

  it('accepts the four categories the snapshot actually uses', () => {
    // The real records, so the guard is known not to over-reject.
    for (const text of [
      'Fully Funded (full tuition up to two years plus a NOK 50,000 per semester living-expense stipend)',
      'Fully Funded (salaried employment as a PhD research fellow / stipendiat)',
      'Fully funded government scholarship (tuition + stipend + airfare + insurance)',
      'Fully Funded with Repayment Obligation at Associate and Bachelor\'s Level',
    ]) {
      expect(isFullyFundedStatement(text), text).toBe(true)
    }
  })

  it('is total for a non-string or a blank value', () => {
    for (const bad of [null, undefined, '', '   ', 42, {}]) {
      expect(isFullyFundedStatement(bad)).toBe(false)
    }
  })
})

describe('a negated statement gets a truthful badge, not a fully funded one', () => {
  it('labels a negated full-funding claim by what the award does cover', () => {
    // The reviewer's exact sentence. The truthful badge names the stipend, not
    // the funding it denies.
    const out = fundingBadgeLabel({
      funding: 'This award is not fully funded, but includes a monthly stipend for living costs',
    })
    expect(out.label).not.toBe('Fully funded')
    expect(out.full).toBe('This award is not fully funded, but includes a monthly stipend for living costs')
  })

  it('uses a neutral label when the statement supports no category at all', () => {
    const out = fundingBadgeLabel({
      funding: 'An award that is not fully funded and whose other terms are unconfirmed',
    })
    expect(out.label).not.toBe('Fully funded')
    // Neutral: a truncated phrase of the record's own words, not an assertion.
    expect(out.full).toBe('An award that is not fully funded and whose other terms are unconfirmed')
    expect(out.truncated).toBe(true)
  })

  it('a conflicting statement is never fully funded', () => {
    const out = fundingBadgeLabel({ funding: 'Fully funded or partially funded depending on the faculty' })
    expect(out.label).not.toBe('Fully funded')
  })

  it('still labels an unambiguous full funding award correctly', () => {
    const out = fundingBadgeLabel({ funding: 'Fully Funded (3-year service commitment)' })
    expect(out.label).toBe('Fully funded')
    expect(out.full).toBe('Fully Funded (3-year service commitment)')
  })

  it('recovers a full funding award that the substring matcher mislabelled', () => {
    // id=472 in the shipped snapshot: "Full funding (partial living stipend)"
    // was labelled "Stipend" because the word "fully" was missing.
    const out = fundingBadgeLabel({ funding: 'Full funding (partial living stipend)' })
    expect(out.label).toBe('Fully funded')
  })
})

describe('tuition is never inferred as covered', () => {
  it('says "support", not "coverage", for a partial waiver', () => {
    // The label is the weaker of the two claims on purpose. A 20% waiver is
    // tuition support and is not tuition coverage.
    expect(fundingBadgeLabel({ funding: 'Tuition Fee Waiver (20% of tuition fees)' }).label).toBe('Tuition support')
    expect(fundingBadgeLabel({ funding: 'Tuition Fee Waiver (50% of tuition fees)' }).label).toBe('Tuition support')
  })

  it('says support for a waiver whose extent the record does not state', () => {
    expect(fundingBadgeLabel({ funding: 'Tuition Fee Waiver (full or part; some faculties add a grant)' }).label)
      .toBe('Tuition support')
  })

  it('never derives coverage from a mention alone', () => {
    // No funding word at all in the tuition direction, and no coverage claim.
    const out = fundingBadgeLabel({ funding: 'Monthly stipend, housing grant, health insurance, and travel card' })
    expect(out.label).toBe('Stipend')
    expect(out.label).not.toContain('Tuition')
  })
})

describe('funding badge text is never silently clipped', () => {  it('shortens a long published funding string to a badge that fits', () => {
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

/**
 * Whole-catalogue guard.
 *
 * The assertions above are about the rule; this is about the data it is applied
 * to. It reads the shipped snapshot - which this change must not modify - and
 * pins the badge for every record whose funding text is long enough for
 * inference to happen, so a change to the matcher that reclassifies a real
 * award fails here rather than reaching a card.
 */
describe('the whole public catalogue classifies conservatively', () => {
  const snapshot = JSON.parse(readFileSync('public/scholarships-snapshot.json', 'utf8'))

  const inferred = []
  for (const record of snapshot.scholarships) {
    const out = fundingBadgeLabel(record)
    if (out.truncated) {
      inferred.push({ id: record.id, label: out.label, funding: record.funding })
    }
  }

  it('has a known population of inferable funding statements', () => {
    // The count is pinned so a snapshot regeneration that changes which records
    // need a shortened label is a deliberate decision rather than a surprise.
    expect(inferred.length).toBe(40)
  })

  it('never labels a record fully funded when its text denies it', () => {
    const denied = inferred.filter(
      (entry) => entry.label === 'Fully funded' && !isFullyFundedStatement(entry.funding),
    )
    expect(denied.map((entry) => entry.id)).toEqual([])
  })

  it('labels only records whose text affirms full funding', () => {
    const fullyFunded = inferred.filter((entry) => entry.label === 'Fully funded')
    expect(fullyFunded.map((entry) => entry.id)).toEqual([277, 278, 360, 437, 472, 692])
  })

  it('labels no record fully funded from a negated or partial statement', () => {
    // The whole safety property, stated as a scan over the data.
    const negatedOrPartial = snapshot.scholarships.filter((record) => (
      typeof record.funding === 'string'
      && /not\s+(?:a\s+)?(?:fully\s+)?fund|partial(ly)?\s+(funding|funded)|part[\s-]?funded/i.test(record.funding)
    ))
    for (const record of negatedOrPartial) {
      expect(fundingBadgeLabel(record).label, `record ${record.id}`).not.toBe('Fully funded')
    }
  })

  it('preserves the full published funding text for every record', () => {
    for (const record of snapshot.scholarships) {
      const out = fundingBadgeLabel(record)
      const published = record.funding
      const isBlank = typeof published !== 'string' || published.trim() === ''

      if (isBlank) {
        // Nothing to preserve, so nothing is invented either.
        expect(out.full).toBeNull()
        continue
      }

      // The card's tooltip and screen-reader text carry `full`, so it has to be
      // the record's own wording, byte for byte.
      expect(out.full).toBe(published)
    }
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
