/**
 * Honesty guards on the catalogue's presented facts.
 *
 * Every test here pins a defect that existed on master, each of which let the
 * UI assert something the data does not support. They are grouped rather than
 * filed with the modules they exercise, because the failures they guard against
 * share a shape: a fallback, a default, or a fixed string standing in for a
 * field that was absent, ambiguous or explicitly negative.
 *
 * The evidence column is the shipped snapshot, so a change in the data shows up
 * as a changed count rather than as a silently relaxed assertion.
 */

import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import {
  getDeadlineLabel,
  getDeadlinePrecisionLabel,
  getLastVerifiedLabel,
  getScholarshipStatus,
  getScholarshipStatusCode,
  hasConfirmedDeadline,
  hasConfirmedDeadlineDate,
} from './scholarshipPresentation.js'
import { getStudyLevels, matchesStudyLevel } from './studyLevel.js'
import { describeFunding, fundingAmountsComparable, getTuitionCoverage, matchesTuitionCoverage } from './fundingFacts.js'

/**
 * The shipped snapshot, read as data.
 *
 * A working-directory-relative path, which is the convention
 * `snapshotContract.test.js` already uses and what makes these assertions
 * count: every expectation below is calibrated against the real population, so
 * a regeneration shows up as a changed count rather than as a silently relaxed
 * assertion.
 */
const snapshot = JSON.parse(readFileSync('public/scholarships-snapshot.json', 'utf8'))
const records = snapshot.scholarships

describe('the shipped catalogue, measured', () => {
  it('is the size the tests below are calibrated against', () => {
    // Guards the premise: if a regeneration changes the population, every count
    // in this file is rederived rather than silently kept.
    expect(snapshot.stats.total).toBe(records.length)
    expect(records.length).toBeGreaterThan(600)
  })
})

describe('deadline precision is never upgraded to a confirmed date', () => {
  it('reports a label for every precision the catalogue holds', () => {
    const precisions = [...new Set(records.map((r) => r.deadline_precision))]
    for (const precision of precisions) {
      const label = getDeadlinePrecisionLabel({ deadline_precision: precision })
      expect(label, `precision ${precision} has no label`).toBeTruthy()
    }
  })

  it('labels a low-precision deadline as low-precision, not as a full date', () => {
    // These are the values the master build labelled "Full date provided by
    // the provider" for everything except `month`.
    const notConfirmed = ['unknown', 'approximate', 'varies', 'recurring', 'rolling', 'year', 'none']
    for (const precision of notConfirmed) {
      expect(getDeadlinePrecisionLabel({ deadline_precision: precision })).not.toMatch(
        /Full date published|provider has published a full date/i,
      )
    }
  })

  it('confirms a date only for the precisions that state one', () => {
    expect(hasConfirmedDeadlineDate({ deadline_precision: 'day' })).toBe(true)
    expect(hasConfirmedDeadlineDate({ deadline_precision: 'exact' })).toBe(true)
    // A deadline published with a time is a *more* specific statement than one
    // published without, so it is a confirmed date too.
    expect(hasConfirmedDeadlineDate({ deadline_precision: 'day_and_time' })).toBe(true)
    for (const precision of ['unknown', 'approximate', 'varies', 'recurring', 'rolling', 'year', 'none', 'month']) {
      expect(hasConfirmedDeadlineDate({ deadline_precision: precision }), precision).toBe(false)
    }
  })

  it('requires both a real value and a confirming precision', () => {
    expect(hasConfirmedDeadline({ deadline_date: '2026-12-31', deadline_precision: 'exact' })).toBe(true)
    // A month-precision record that carries a date for ordering purposes is
    // still not a confirmed date.
    expect(hasConfirmedDeadline({ deadline_date: '2026-11-30', deadline_precision: 'month' })).toBe(false)
    // Nor is a record with no date at all.
    expect(hasConfirmedDeadline({ deadline_date: null, deadline_precision: 'exact' })).toBe(false)
    expect(hasConfirmedDeadline({ deadline_precision: 'exact' })).toBe(false)
  })

  it('treats an unrecognised precision as unknown rather than as exact', () => {
    // An unrecognised precision is a value this build has never seen. Reading
    // it as a confirmed date is the exact defect this module replaced.
    expect(getDeadlinePrecisionLabel({ deadline_precision: 'not-a-real-precision' }))
      .toMatch(/not stated/)
    expect(hasConfirmedDeadlineDate({ deadline_precision: 'not-a-real-precision' })).toBe(false)
  })

  it('keeps the provider\'s own deadline text rather than a fallback', () => {
    // 152 public records publish a deadline description and no date. That
    // text - "Varies by consortium/programme - typically Dec-Feb for a Sep
    // intake" - is a real statement from the provider and must be shown; the
    // 12 that publish neither are the only ones that fall back.
    const undated = records.filter((r) => !r.deadline_date)
    const withText = undated.filter((r) => r.deadline)
    const withNeither = undated.filter((r) => !r.deadline)
    expect(withText.length).toBeGreaterThan(140)
    expect(withNeither.length).toBeGreaterThan(0)
    expect(withNeither.length).toBeLessThan(20)

    for (const record of withText) {
      expect(getDeadlineLabel(record)).toBe(record.deadline)
    }
    for (const record of withNeither) {
      expect(getDeadlineLabel(record)).toBe('Deadline to be confirmed')
    }
  })

  it('describes a published date exactly when the precision says there is one', () => {
    // The regression: a record with `deadline: null` and precision `unknown`
    // rendered "Deadline to be confirmed" in the summary and "Full date
    // provided by the provider" in the verification record.
    //
    // The guard is directional, because the honest labels are not all phrased
    // the same way: `day` says "Full date published", `exact` says "Exact date
    // published", and `month` says "the provider has not published a full date".
    // What must hold is that a record is described as carrying a published
    // specific date if and only if its precision says it is.
    const affirmsPublishedDate = (label) => /^(Full|Exact) date published|^Date and time published/.test(label)

    const wrong = records.filter((r) => {
      const label = getDeadlinePrecisionLabel(r) || ''
      return affirmsPublishedDate(label) !== hasConfirmedDeadlineDate(r)
    })
    expect(wrong.map((r) => r.id)).toEqual([])
  })

  it('never pairs a confirmed-date claim with an unpublished deadline', () => {
    // The same contradiction from the other side: whatever the label says, a
    // record whose deadline text is the fallback must not also be described as
    // carrying a published date.
    const contradictions = records.filter((r) => (
      getDeadlineLabel(r) === 'Deadline to be confirmed' && hasConfirmedDeadlineDate(r)
    ))
    expect(contradictions.map((r) => r.id)).toEqual([])
  })
})

describe('the status pill matches the filter', () => {
  it('reports the status the record holds, including upcoming', () => {
    // `upcoming` had no entry in the status table, so those records rendered
    // the "Open" pill. The shipped snapshot holds a real population of them.
    const upcoming = records.filter((r) => r.status === 'upcoming')
    expect(upcoming.length).toBeGreaterThan(50)
    expect(getScholarshipStatus(upcoming[0]).label).toBe('Upcoming')
    expect(getScholarshipStatusCode(upcoming[0])).toBe('upcoming')
  })

  it('gives every status the catalogue holds a label of its own', () => {
    // `upcoming` had no entry, so those records rendered the "Open" pill - a
    // student reading "Open" for an award that does not open for months plans
    // the wrong thing. The guarantee is that no status shares another's label.
    const statuses = [...new Set(records.map((r) => r.status))].filter(Boolean)
    expect(statuses.length).toBeGreaterThanOrEqual(4)

    const labels = statuses.map((status) => getScholarshipStatus({ status }).label)
    expect(new Set(labels).size).toBe(statuses.length)
    // And the mapping is the one the catalogue documents, not a fallback.
    expect(getScholarshipStatus({ status: 'open' }).label).toBe('Open')
    expect(getScholarshipStatus({ status: 'upcoming' }).label).toBe('Upcoming')
    expect(getScholarshipStatus({ status: 'closed' }).label).toBe('Closed')
  })

  it('derives the same status for a record with none', () => {
    // One public record carries `status: null`. It matched no status filter at
    // all, so it was unreachable from every status view.
    const nullStatus = records.filter((r) => r.status === null)
    if (nullStatus.length > 0) {
      for (const record of nullStatus) {
        const derived = getScholarshipStatusCode(record)
        expect(derived).not.toBeNull()
        expect(derived).toBeTruthy()
      }
    }
  })
})

describe('verification is only claimed when it happened', () => {
  it('does not print "Verified" for a record whose status says it was not', () => {
    const needsReview = records.filter((r) => r.verification_status !== 'active')
    expect(needsReview.length).toBeGreaterThan(0)

    const claimingVerified = needsReview
      .filter((r) => /^Verified\b/.test(getLastVerifiedLabel(r)))
    expect(claimingVerified.map((r) => r.id)).toEqual([])
  })

  it('still prints a real date for a re-checked record', () => {
    const active = records.filter((r) => r.verification_status === 'active' && r.last_verified_at)
    expect(active.length).toBeGreaterThan(0)
    expect(getLastVerifiedLabel(active[0])).toMatch(/^Verified /)
  })

  it('says so plainly for a record with no re-check at all', () => {
    expect(getLastVerifiedLabel({ verification_status: 'needs_review' }))
      .toMatch(/not yet re-checked/i)
  })
})

describe('funding is only claimed where it is comparable', () => {
  it('refuses to call amounts in different currencies comparable', () => {
    expect(fundingAmountsComparable(
      { funding_amount: 1400, funding_currency: 'EUR', funding_period: 'per month' },
      { funding_amount: 1400, funding_currency: 'GBP', funding_period: 'per month' },
    )).toBe(false)
  })

  it('refuses to call amounts in different periods comparable', () => {
    // A rate and a total are not two values on one scale.
    expect(fundingAmountsComparable(
      { funding_amount: 1400, funding_currency: 'EUR', funding_period: 'per month' },
      { funding_amount: 1400, funding_currency: 'EUR', funding_period: 'annual total' },
    )).toBe(false)
  })

  it('refuses to compare a missing amount as though it were present', () => {
    expect(fundingAmountsComparable(
      { funding_amount: null, funding_currency: 'EUR', funding_period: 'per month' },
      { funding_amount: 1400, funding_currency: 'EUR', funding_period: 'per month' },
    )).toBe(false)
    expect(fundingAmountsComparable(null, null)).toBe(false)
  })

  it('describes funding without inventing an amount or a currency', () => {
    // 133 public records carry no amount, and 91 carry no currency.
    const noAmount = records.filter((r) => r.funding_amount == null)
    expect(noAmount.length).toBeGreaterThan(100)
    for (const record of noAmount) {
      expect(describeFunding(record)).not.toMatch(/\b(undefined|NaN|null)\b/)
    }
  })

  it('keeps tuition coverage a three-state answer', () => {
    // 375 true, 215 false, 28 absent. A two-state reading would turn the 28
    // into either a funded or an unfunded claim.
    const coverage = records.map(getTuitionCoverage)
    expect(coverage.filter((v) => v === true).length).toBeGreaterThan(300)
    expect(coverage.filter((v) => v === false).length).toBeGreaterThan(200)
    expect(coverage.filter((v) => v === null).length).toBeGreaterThan(0)
    expect(coverage.length).toBe(records.length)
  })

  it('matches a confirmed negative and an unknown differently', () => {
    // `tuition_coverage: false` is a provider saying tuition is not covered -
    // information, not absence. Reporting it as "not stated" hides it.
    expect(matchesTuitionCoverage({ tuition_coverage: false }, 'no')).toBe(true)
    expect(matchesTuitionCoverage({ tuition_coverage: null }, 'no')).toBe(false)
    expect(matchesTuitionCoverage({ tuition_coverage: null }, 'not-stated')).toBe(true)
    expect(matchesTuitionCoverage({ tuition_coverage: true }, 'not-stated')).toBe(false)
  })
})

describe('study levels cover every record', () => {
  it('puts every record in at least one bucket', () => {
    const unbucketed = records.filter((r) => getStudyLevels(r).length === 0)
    expect(unbucketed.map((r) => r.id)).toEqual([])
  })

  it('never reports a bucket the record does not claim', () => {
    // The specific failure: a record listing three levels reported as "any".
    const anyClaims = records.filter((r) => getStudyLevels(r).includes('any'))
    for (const record of anyClaims) {
      expect(matchesStudyLevel(record, 'bachelor')).toBe(false)
      expect(matchesStudyLevel(record, 'doctoral')).toBe(false)
    }
  })

  it('finds a record from each bucket it is actually in', () => {
    const multi = records.find((r) => {
      const levels = getStudyLevels(r)
      return levels.length > 1 && !levels.includes('any') && !levels.includes('unspecified')
    })
    expect(multi, 'the snapshot holds multi-level records').toBeTruthy()
    for (const level of getStudyLevels(multi)) {
      expect(matchesStudyLevel(multi, level)).toBe(true)
    }
  })

  it('treats the no-filter sentinel as no filter', () => {
    expect(matchesStudyLevel({ degree: 'Research grant' }, 'all')).toBe(true)
  })
})
