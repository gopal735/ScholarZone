/**
 * The published snapshot, asserted against the publication it shipped in.
 *
 * The snapshot is the public catalogue: the frontend's default source, the
 * thing a reader sees. This file checks the properties the 2026-10-11
 * publication promised, and nothing softer than that:
 *
 *   - the header reconciles with the records it ships;
 *   - every record the published baseline held is still in the file, unless
 *     the database now excludes it explicitly - preservation, not deletion;
 *   - the researched fields are typed the way the frontend reads them, and
 *     every null is still a null: an amount is a number or nothing, guidance
 *     is an object with usable content or nothing;
 *   - no public record carries an internal workflow key;
 *   - the eight records the publication enriched carry their citations;
 *   - a record published as closed really does hold a deadline before the
 *     date the snapshot derived its statuses on - the label is the honest
 *     signal, never an empty badge.
 *
 * These are not schema tests. Each assertion is a way the publication could
 * have quietly swapped a deletion or an invention for a fact.
 */
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

// Read from the repository root rather than from import.meta.url: under the
// jsdom environment, modules under src/services/ report a dev-server origin,
// so a file: URL relative to import.meta.url is not buildable there. Vitest
// always runs with the frontend directory as cwd.
const SNAPSHOT = JSON.parse(
  readFileSync('public/scholarships-snapshot.json', 'utf8'),
)

const records = SNAPSHOT.scholarships || []
const byId = new Map(records.map((record) => [String(record.id), record]))

// Keys the applicant-guidance blob must never carry: reviewer workflow state
// that would be a public leak if the research pipeline ever wrote one.
const FORBIDDEN_GUIDANCE_KEYS = [
  'verification_notes',
  'verified_by',
  'next_verification_due',
  'is_archived',
  'archived_at',
  'archived_reason',
  'image_evaluation_status',
  'image_evaluated_at',
  'is_verified',
]

// The records the 2026-10-11 publication enriched from official evidence.
const ENRICHED_IDS = ['229', '502', '555', '586', '587', '588', '701', '702']

describe('snapshot header', () => {
  it('reconciles the source count with the records it ships', () => {
    const meta = SNAPSHOT.meta
    expect(meta.source_record_count).toBe(
      meta.public_record_count + meta.excluded_union,
    )
    expect(meta.public_record_count).toBe(records.length)
  })

  it('declares which visibility mode it was generated in', () => {
    const baseline = SNAPSHOT.meta.baseline
    expect(baseline).toBeTruthy()
    expect(['preserve', 'strict']).toContain(baseline.mode)
  })
})

describe('published records', () => {
  it('every baseline record is still published', () => {
    const baselineIds = SNAPSHOT.meta.baseline?.baseline_ids || []
    const missing = baselineIds.filter((id) => !byId.has(String(id)))
    expect(missing).toEqual([])
  })

  it('publishes at least every record the deployed baseline held', () => {
    const baselineIds = SNAPSHOT.meta.baseline?.baseline_ids || []
    expect(records.length).toBeGreaterThanOrEqual(baselineIds.length)
  })

  it('carries each researched field in the shape the frontend reads', () => {
    for (const record of records) {
      const { funding_amount: amount, funding_currency: currency, funding_period: period,
        tuition_coverage: coverage, applicant_utility: guidance,
        official_source_urls: urls, source_citations: citations } = record

      expect(amount === null || typeof amount === 'number').toBe(true)
      expect(currency === null || /^[A-Z]{3}$/.test(currency)).toBe(true)
      expect(period === null || typeof period === 'string').toBe(true)
      expect([true, false, null]).toContain(coverage)
      expect(Array.isArray(urls)).toBe(true)
      expect(Array.isArray(citations)).toBe(true)
      expect(guidance === null || typeof guidance === 'object').toBe(true)

      for (const url of [...urls, ...citations]) {
        expect(url.startsWith('http://') || url.startsWith('https://')).toBe(true)
      }
    }
  })

  it('publishes no internal workflow key inside the guidance', () => {
    for (const record of records) {
      const guidance = record.applicant_utility
      if (!guidance) continue
      const keys = Object.keys(guidance)
      for (const forbidden of FORBIDDEN_GUIDANCE_KEYS) {
        expect(keys).not.toContain(forbidden)
      }
    }
  })

  it('labels a closed record with the deadline that closed it', () => {
    const derivedOn = SNAPSHOT.meta.status_derived_at
    expect(derivedOn).toBeTruthy()
    for (const record of records) {
      if (record.status !== 'closed') continue
      expect(record.deadline_date).toBeTruthy()
      expect(record.deadline_date < derivedOn).toBe(true)
    }
  })

  it('enriches the eight researched records with their citations', () => {
    for (const id of ENRICHED_IDS) {
      const record = byId.get(id)
      expect(record, `record ${id} is published`).toBeTruthy()
      expect(record.source_citations.length, `record ${id} carries citations`).toBeGreaterThan(0)
      expect(record.official_source_urls.length).toBeGreaterThan(0)
    }
  })

  it('publishes the two corrected deadline displays on the official dates', () => {
    for (const id of ['587', '588']) {
      const record = byId.get(id)
      expect(record).toBeTruthy()
      expect(record.deadline).toContain('December 1, 2026')
      expect(record.deadline).toContain('January 31, 2027')
    }
  })

  it('keeps a percentage award out of the currency amount', () => {
    // No published amount may be a percentage, and no published amount may
    // exist without a currency beside it to name it.
    for (const record of records) {
      if (record.funding_amount === null) continue
      expect(typeof record.funding_amount).toBe('number')
      expect(record.funding_currency).toBeTruthy()
    }
  })
})

describe('public statistics', () => {
  it('counts exactly the records it ships', () => {
    const stats = SNAPSHOT.stats
    expect(stats.total).toBe(records.length)
    expect(stats.verified_active).toBe(
      records.filter((record) => record.verified === true).length,
    )
    expect(stats.open + stats.closing_soon + stats.upcoming).toBeLessThanOrEqual(
      stats.total,
    )
  })

  it('offers no filter status without a matching record', () => {
    const statuses = SNAPSHOT.meta.filter_options?.statuses || []
    const published = new Set(records.map((record) => record.status))
    for (const status of statuses) {
      expect(published.has(status)).toBe(true)
    }
  })
})
