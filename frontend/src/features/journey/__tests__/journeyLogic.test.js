/**
 * Pure-logic tests for the Bangladesh Applicant Journey.
 *
 * Grouped by the rules that are expensive to get wrong: progress arithmetic,
 * the funding-gap formula, date handling with the two date kinds kept apart,
 * Bangla-digit normalisation, and storage/import validation.
 */

import { describe, expect, it } from 'vitest'
import {
  parseIsoDate,
  isIsoDate,
  toIsoDate,
  daysBetween,
  personalDateStatus,
  officialDeadlineInfo,
  byDateCriterion,
} from '../lib/dates.js'
import {
  normalizeBanglaDigits,
  hasBanglaDigits,
  normalizeAmount,
  amountToNumber,
  convertToBdt,
  sumAmounts,
} from '../lib/money.js'
import { computeCostSummary, computeBdtView } from '../lib/costs.js'
import {
  overallCompletion,
  stepCounts,
  nextActions,
  checklistSummary,
  candidateActions,
  JOURNEY_STEPS,
} from '../lib/progress.js'
import {
  normalizeJourneyDocument,
  defaultJourneyState,
  migrateJourneyDocument,
  SCHEMA,
  VERSION,
  STORAGE_KEY,
} from '../lib/journeySchema.js'
import { validateImportPayload } from '../lib/journeyImportExport.js'

/* ── Dates ──────────────────────────────────────────────────────────── */

describe('date parsing', () => {
  it('parses a calendar day without crossing a timezone', () => {
    const date = parseIsoDate('2026-08-01')
    expect(date).not.toBeNull()
    expect(date.getFullYear()).toBe(2026)
    expect(date.getMonth()).toBe(7)
    expect(date.getDate()).toBe(1)
  })

  it('rejects impossible calendar days rather than rolling them', () => {
    expect(parseIsoDate('2026-02-30')).toBeNull()
    expect(parseIsoDate('2026-04-31')).toBeNull()
    expect(parseIsoDate('2026-13-01')).toBeNull()
    expect(parseIsoDate('not-a-date')).toBeNull()
    expect(parseIsoDate('')).toBeNull()
    expect(parseIsoDate(null)).toBeNull()
  })

  it('accepts a real leap day and rejects the one that is not', () => {
    expect(isIsoDate('2024-02-29')).toBe(true)
    expect(isIsoDate('2025-02-29')).toBe(false)
  })

  it('round-trips through local components', () => {
    expect(toIsoDate(new Date(2026, 0, 5))).toBe('2026-01-05')
  })

  it('counts whole days in both directions', () => {
    expect(daysBetween('2026-01-01', '2026-01-11')).toBe(10)
    expect(daysBetween('2026-01-11', '2026-01-01')).toBe(-10)
    expect(daysBetween('2026-01-01', '2026-01-01')).toBe(0)
  })

  it('returns null rather than zero when a date is missing', () => {
    expect(daysBetween('2026-01-01', '')).toBeNull()
    expect(daysBetween('', '2026-01-01')).toBeNull()
  })
})

describe('personal date status', () => {
  it('is unknown when no target is recorded', () => {
    expect(personalDateStatus('', '2026-01-10')).toEqual({ state: 'unknown', days: null })
  })

  it('is overdue strictly before the reference day', () => {
    expect(personalDateStatus('2026-01-05', '2026-01-06').state).toBe('overdue')
    expect(personalDateStatus('2026-01-06', '2026-01-06').state).toBe('approaching')
  })

  it('is approaching within the 14-day window and upcoming beyond it', () => {
    expect(personalDateStatus('2026-01-24', '2026-01-10').state).toBe('approaching')
    expect(personalDateStatus('2026-01-25', '2026-01-10').state).toBe('upcoming')
  })

  it('never treats an official deadline as overdue', () => {
    // The whole reason the two fields exist: an official deadline in the past
    // is a fact about the record, not a missed personal commitment.
    const official = officialDeadlineInfo('2020-01-01', '2026-01-10')
    expect(official.recorded).toBe(true)
    expect(official.days).toBeLessThan(0)
    // The same string as a personal target is a real overdue commitment.
    expect(personalDateStatus('2020-01-01', '2026-01-10').state).toBe('overdue')
  })
})

describe('date sorting', () => {
  const rows = [
    { label: 'a', officialDeadline: '2026-09-01', personalTarget: '2026-01-01' },
    { label: 'b', officialDeadline: '2026-08-01', personalTarget: '' },
    { label: 'c', officialDeadline: '2026-07-01', personalTarget: '2026-03-01' },
  ]

  it('sorts by the chosen criterion only', () => {
    expect([...rows].sort(byDateCriterion('officialDeadline')).map((r) => r.label)).toEqual(['c', 'b', 'a'])
    expect([...rows].sort(byDateCriterion('personalTarget')).map((r) => r.label)).toEqual(['a', 'c', 'b'])
  })

  it('puts records with no value last', () => {
    const sorted = [...rows].sort(byDateCriterion('personalTarget'))
    expect(sorted[sorted.length - 1].label).toBe('b')
  })
})

/* ── Money ──────────────────────────────────────────────────────────── */

describe('Bangla digit normalisation', () => {
  it('converts Bangla digits to ASCII', () => {
    expect(normalizeBanglaDigits('৫০,০০০')).toBe('50,000')
    expect(normalizeBanglaDigits('৩.৫')).toBe('3.5')
    expect(normalizeBanglaDigits('১২৩৪৫৬৭৮৯০')).toBe('1234567890')
  })

  it('leaves non-digits untouched', () => {
    expect(normalizeBanglaDigits('Tk ১২০০')).toBe('Tk 1200')
  })

  it('detects the presence of Bangla digits', () => {
    expect(hasBanglaDigits('৫০০')).toBe(true)
    expect(hasBanglaDigits('500')).toBe(false)
    expect(hasBanglaDigits(500)).toBe(false)
  })
})

describe('amount normalisation', () => {
  it('accepts Bangla digits, separators and decimals', () => {
    expect(normalizeAmount('৫০,০০০')).toEqual({ ok: true, value: '50000' })
    expect(normalizeAmount('১,২০,০০০.৫০')).toEqual({ ok: true, value: '120000.50' })
    expect(normalizeAmount(' 1 200 ')).toEqual({ ok: true, value: '1200' })
  })

  it('rejects empty, non-numeric, negative and oversized values', () => {
    expect(normalizeAmount('').ok).toBe(false)
    expect(normalizeAmount('   ').reason).toBe('empty')
    expect(normalizeAmount('abc').reason).toBe('not-a-number')
    expect(normalizeAmount('12.3.4').reason).toBe('not-a-number')
    expect(normalizeAmount('-50').reason).toBe('negative')
    expect(normalizeAmount('১০০০০০০০০০০০০').reason).toBe('too-large')
  })

  it('never silently changes a valid amount', () => {
    // The value the student typed survives as the canonical form; only the
    // digit script and separators are resolved.
    expect(normalizeAmount('850.25').value).toBe('850.25')
    expect(amountToNumber(normalizeAmount('850.25'))).toBe(850.25)
  })
})

describe('currency conversion', () => {
  it('converts with the rate the student supplied', () => {
    expect(convertToBdt('1200', '117.5')).toEqual({ amount: '141000.00', rateUsed: '117.5' })
  })

  it('returns null when no usable rate is supplied', () => {
    expect(convertToBdt('1200', '')).toBeNull()
    expect(convertToBdt('1200', 'abc')).toBeNull()
    expect(convertToBdt('1200', '0')).toBeNull()
  })
})

describe('amount summing', () => {
  it('sums and flags unreadable entries rather than dropping them', () => {
    expect(sumAmounts(['10', '20.5'])).toEqual({ total: '30.5', usable: true })
    expect(sumAmounts(['10', ''])).toEqual({ total: '10', usable: false })
    expect(sumAmounts([])).toEqual({ total: '0', usable: true })
  })
})

/* ── Cost summary ───────────────────────────────────────────────────── */

function docWith(items, rate = {}) {
  return normalizeJourneyDocument({
    schema: SCHEMA,
    version: VERSION,
    costs: { items, rate },
  })
}

describe('cost summary and funding gap', () => {
  it('reports no-costs when nothing usable is recorded', () => {
    const doc = docWith([{ label: 'Tuition', amount: '', category: 'tuition' }])
    const summary = computeCostSummary(doc)
    expect(summary.state).toBe('no-costs')
    expect(summary.gap).toBeNull()
  })

  it('computes the gap as cost minus funding', () => {
    const doc = docWith([
      { label: 'Tuition', amount: '100000', category: 'tuition', sourceType: 'official' },
      { label: 'Living', amount: '50000', category: 'living', sourceType: 'estimate' },
      { label: 'Award', amount: '80000', category: 'funding', sourceType: 'official' },
    ])
    const summary = computeCostSummary(doc)
    expect(summary.totalCost).toBe('150000')
    expect(summary.totalFunding).toBe('80000')
    expect(summary.gap).toBe(70000)
    expect(summary.state).toBe('gap')
  })

  it('reports a surplus rather than clamping to zero', () => {
    const doc = docWith([
      { label: 'Tuition', amount: '100000', category: 'tuition', sourceType: 'official' },
      { label: 'Award', amount: '120000', category: 'funding', sourceType: 'official' },
    ])
    const summary = computeCostSummary(doc)
    expect(summary.gap).toBe(-20000)
    expect(summary.state).toBe('surplus')
  })

  it('treats the full cost as the gap when no funding is recorded', () => {
    const doc = docWith([{ label: 'Tuition', amount: '90000', category: 'tuition', sourceType: 'estimate' }])
    const summary = computeCostSummary(doc)
    expect(summary.state).toBe('no-funding')
    expect(summary.gap).toBe(90000)
  })

  it('marks a total as containing estimates when any input is one', () => {
    const officialOnly = docWith([
      { label: 'Tuition', amount: '100000', category: 'tuition', sourceType: 'official' },
    ])
    const withEstimate = docWith([
      { label: 'Tuition', amount: '100000', category: 'tuition', sourceType: 'official' },
      { label: 'Living', amount: '20000', category: 'living', sourceType: 'estimate' },
    ])
    expect(computeCostSummary(officialOnly).containsEstimate).toBe(false)
    expect(computeCostSummary(officialOnly).containsOfficialOnly).toBe(true)
    expect(computeCostSummary(withEstimate).containsEstimate).toBe(true)
  })

  it('lists unreadable lines instead of dropping them', () => {
    const doc = docWith([
      { label: 'Tuition', amount: 'abc', category: 'tuition' },
      { label: 'Living', amount: '20000', category: 'living' },
    ])
    const summary = computeCostSummary(doc)
    expect(summary.unusableItemIds).toHaveLength(1)
    expect(summary.totalCostUsable).toBe(false)
  })
})

describe('BDT conversion view', () => {
  it('converts each line with the recorded rate', () => {
    const doc = docWith(
      [
        { label: 'Tuition', amount: '1000', currency: 'EUR', category: 'tuition' },
        { label: 'Living', amount: '2000', currency: 'BDT', category: 'living' },
      ],
      { bdtPerUnit: '120', effectiveDate: '2026-01-01' },
    )
    const view = computeBdtView(doc)
    expect(view.rateUsed).toBe('120')
    expect(view.lines.find((line) => line.converted === '120000.00')).toBeDefined()
    expect(view.totalCostBdt).toBe('122000')
    expect(view.unconverted).toHaveLength(0)
  })

  it('reports unconverted lines when no rate is recorded', () => {
    const doc = docWith([{ label: 'Tuition', amount: '1000', currency: 'EUR', category: 'tuition' }])
    const view = computeBdtView(doc)
    expect(view.rateUsed).toBeNull()
    expect(view.unconverted).toHaveLength(1)
  })
})

/* ── Progress ───────────────────────────────────────────────────────── */

describe('progress', () => {
  it('is 0 for an empty document', () => {
    expect(overallCompletion(defaultJourneyState())).toBe(0)
  })

  it('is 0 when a collection exists but nothing is countable', () => {
    const doc = normalizeJourneyDocument({
      shortlist: [{ name: 'A', trust: 'needs-review' }],
      // A template row is not countable, so the module contributes nothing.
      documents: [{ title: 'Passport', template: true, requirement: 'unconfirmed' }],
    })
    expect(overallCompletion(doc)).toBe(0)
    expect(stepCounts(doc, 'documents').countable).toBe(0)
  })

  it('does not count a shortlist entry until its trust status is decided', () => {
    const doc = normalizeJourneyDocument({
      shortlist: [{ name: 'A', country: 'UK', degree: 'MSc', trust: 'needs-review' }],
    })
    expect(stepCounts(doc, 'find')).toEqual({ countable: 1, complete: 0 })
  })

  it('counts a shortlist entry once name, country, degree and status are set', () => {
    const doc = normalizeJourneyDocument({
      shortlist: [{ name: 'A', country: 'UK', degree: 'MSc', trust: 'self-reported' }],
    })
    expect(stepCounts(doc, 'find')).toEqual({ countable: 1, complete: 1 })
    expect(overallCompletion(doc)).toBeGreaterThan(0)
  })

  it('moves the number when a document is confirmed and completed', () => {
    const doc = normalizeJourneyDocument({
      documents: [
        { title: 'Passport', template: false, requirement: 'mandatory', progress: 'not_started' },
      ],
    })
    expect(stepCounts(doc, 'documents')).toEqual({ countable: 1, complete: 0 })
    const done = normalizeJourneyDocument({
      documents: [
        { title: 'Passport', template: false, requirement: 'mandatory', progress: 'done' },
      ],
    })
    expect(stepCounts(done, 'documents')).toEqual({ countable: 1, complete: 1 })
    expect(overallCompletion(done)).toBeGreaterThan(overallCompletion(doc))
  })

  it('excludes a timeline entry with no personal target', () => {
    const doc = normalizeJourneyDocument({
      timeline: [{ label: 'A', officialDeadline: '2026-09-01', personalTarget: '' }],
    })
    expect(stepCounts(doc, 'timeline').countable).toBe(0)
  })

  it('counts a submitted timeline entry as complete', () => {
    const doc = normalizeJourneyDocument({
      timeline: [{ label: 'A', personalTarget: '2026-09-01', progress: 'submitted' }],
    })
    expect(stepCounts(doc, 'timeline')).toEqual({ countable: 1, complete: 1 })
  })

  it('produces a summary row per step with a 0 percent floor', () => {
    const rows = checklistSummary(defaultJourneyState())
    expect(rows).toHaveLength(JOURNEY_STEPS.length)
    expect(rows.every((row) => row.percent === 0)).toBe(true)
  })

  it('never reports 100% for an empty journey', () => {
    expect(overallCompletion(defaultJourneyState())).toBe(0)
  })
})

/* ── Next actions ───────────────────────────────────────────────────── */

describe('next actions', () => {
  it('suggests adding a first shortlist entry when nothing exists', () => {
    const actions = nextActions(defaultJourneyState())
    expect(actions[0].key).toBe('empty-shortlist')
    expect(actions[0].stepId).toBe('find')
  })

  it('returns fewer than three when fewer than three exist', () => {
    const doc = normalizeJourneyDocument({
      shortlist: [{ name: 'A', country: 'UK', degree: 'MSc', trust: 'verified' }],
    })
    const actions = nextActions(doc)
    expect(actions.length).toBeLessThanOrEqual(3)
    expect(actions.length).toBeGreaterThan(0)
  })

  it('returns an empty list when everything is genuinely complete', () => {
    const doc = normalizeJourneyDocument({
      shortlist: [{ name: 'A', country: 'UK', degree: 'MSc', trust: 'verified' }],
      eligibility: {
        qualificationLevel: 'BSc',
        degreeTitle: 'Computer Science',
        resultsText: 'CGPA 3.6 / 4.00',
        englishTestStatus: 'taken',
        citizenshipNotes: 'Bangladeshi',
        residencyNotes: 'Dhaka',
      },
      documents: [{ title: 'Passport', template: false, requirement: 'mandatory', progress: 'done' }],
      timeline: [{ label: 'A', personalTarget: '2026-12-01', progress: 'done' }],
      costs: {
        items: [{ label: 'Tuition', amount: '1000', category: 'tuition', sourceType: 'official', sourceLabel: 'Site', sourceDate: '2026-01-01' }],
      },
      sources: [{ name: 'Uni', url: 'https://example.org/', lastChecked: '2026-01-01', status: 'independently-verified' }],
      departure: [{ title: 'Read conditions', progress: 'done' }],
    })
    expect(nextActions(doc)).toEqual([])
  })

  it('orders an overdue personal target above everything else', () => {
    const doc = normalizeJourneyDocument({
      shortlist: [{ name: 'A', country: 'UK', degree: 'MSc', trust: 'verified' }],
      timeline: [{ label: 'Alpha', personalTarget: '2020-01-01', progress: 'not_started' }],
      departure: [{ title: 'Read conditions', progress: 'not_started' }],
    })
    const actions = nextActions(doc, { referenceIso: '2026-10-01' })
    expect(actions[0].key).toBe('overdue-target')
  })

  it('is deterministic for the same document', () => {
    const doc = normalizeJourneyDocument({
      shortlist: [{ name: 'A', country: 'UK', degree: 'MSc', trust: 'needs-review' }],
      documents: [{ title: 'Passport', template: true, requirement: 'unconfirmed' }],
      departure: [{ title: 'Read conditions', progress: 'not_started' }],
    })
    const first = nextActions(doc)
    const second = nextActions(doc)
    expect(first).toEqual(second)
  })

  it('respects the limit and never pads', () => {
    const doc = normalizeJourneyDocument({
      shortlist: [{ name: 'A', country: 'UK', degree: 'MSc', trust: 'needs-review' }],
    })
    // Two genuine actions exist here: the undecided trust status and the gap
    // in the student's own record. The panel shows both, rather than padding
    // to three with work that does not exist.
    const actions = nextActions(doc, { limit: 3 })
    expect(actions.length).toBe(2)
    expect(candidateActions(doc).length).toBeGreaterThanOrEqual(2)
  })

  it('links every action to a real step', () => {
    const doc = normalizeJourneyDocument({
      shortlist: [{ name: 'A', country: 'UK', degree: 'MSc', trust: 'needs-review' }],
      departure: [{ title: 'Read conditions', progress: 'not_started' }],
    })
    const stepIds = new Set(JOURNEY_STEPS.map((step) => step.id))
    for (const action of nextActions(doc, { limit: 10 })) {
      expect(stepIds.has(action.stepId)).toBe(true)
    }
  })
})

/* ── Schema, validation and migration ───────────────────────────────── */

describe('document normalisation', () => {
  it('starts empty rather than illustrative', () => {
    const doc = defaultJourneyState()
    expect(doc.shortlist).toEqual([])
    expect(doc.documents).toEqual([])
    expect(doc.timeline).toEqual([])
    expect(doc.costs.items).toEqual([])
    expect(doc.sources).toEqual([])
    expect(doc.departure).toEqual([])
  })

  it('refuses a non-object', () => {
    expect(normalizeJourneyDocument(null).shortlist).toEqual([])
    expect(normalizeJourneyDocument('nope').shortlist).toEqual([])
    expect(normalizeJourneyDocument(42).shortlist).toEqual([])
  })

  it('re-issues duplicate ids rather than merging records', () => {
    const doc = normalizeJourneyDocument({
      shortlist: [
        { id: 'same', name: 'First' },
        { id: 'same', name: 'Second' },
      ],
    })
    expect(doc.shortlist).toHaveLength(2)
    expect(doc.shortlist[0].id).not.toBe(doc.shortlist[1].id)
  })

  it('marks an invalid URL as absent rather than storing it', () => {
    const doc = normalizeJourneyDocument({
      sources: [{ name: 'X', url: 'not a url at all' }, { name: 'Y', url: 'https://example.org/a' }],
    })
    expect(doc.sources[0].url).toBe('')
    expect(doc.sources[1].url).toBe('https://example.org/a')
  })

  it('drops an impossible date instead of storing it', () => {
    const doc = normalizeJourneyDocument({
      timeline: [{ label: 'A', officialDeadline: '2026-02-30', personalTarget: '2026-02-28' }],
    })
    expect(doc.timeline[0].officialDeadline).toBe('')
    expect(doc.timeline[0].personalTarget).toBe('2026-02-28')
  })

  it('clamps a free-text field instead of unbounded growth', () => {
    const doc = normalizeJourneyDocument({ shortlist: [{ name: 'x'.repeat(5000) }] })
    expect(doc.shortlist[0].name.length).toBeLessThanOrEqual(200)
  })

  it('defaults an unknown trust status to needs-review', () => {
    const doc = normalizeJourneyDocument({ shortlist: [{ name: 'A', trust: 'trusted-by-a-dream' }] })
    expect(doc.shortlist[0].trust).toBe('needs-review')
  })
})

describe('migration', () => {
  it('accepts the current version unchanged', () => {
    const result = migrateJourneyDocument({ schema: SCHEMA, version: VERSION, shortlist: [] })
    expect(result.ok).toBe(true)
  })

  it('refuses a version it does not know how to upgrade', () => {
    const result = migrateJourneyDocument({ schema: SCHEMA, version: VERSION + 1, shortlist: [] })
    expect(result.ok).toBe(false)
    expect(result.reason).toBe('newer-version')
  })

  it('refuses a document with no version', () => {
    expect(migrateJourneyDocument({ schema: SCHEMA, shortlist: [] }).ok).toBe(false)
    expect(migrateJourneyDocument({ schema: SCHEMA }).reason).toBe('no-version')
  })

  it('refuses a foreign schema', () => {
    const result = migrateJourneyDocument({ schema: 'some-other-app', version: 1 })
    expect(result.ok).toBe(false)
    expect(result.reason).toBe('unknown-schema')
  })

  it('refuses a non-object', () => {
    expect(migrateJourneyDocument(null).reason).toBe('not-an-object')
    expect(migrateJourneyDocument([]).reason).toBe('not-an-object')
  })
})

/* ── Import validation ──────────────────────────────────────────────── */

describe('import validation', () => {
  it('accepts an export of the current schema', () => {
    const result = validateImportPayload({ schema: SCHEMA, version: VERSION, shortlist: [] })
    expect(result.ok).toBe(true)
  })

  it('rejects a foreign schema', () => {
    expect(validateImportPayload({ schema: 'other', version: 1 }).reason).toBe('unknown-schema')
  })

  it('rejects a newer version', () => {
    expect(validateImportPayload({ schema: SCHEMA, version: 9 }).reason).toBe('newer-version')
  })

  it('rejects a file with no version', () => {
    expect(validateImportPayload({ schema: SCHEMA }).reason).toBe('no-version')
  })

  it('rejects a non-object', () => {
    expect(validateImportPayload(null).reason).toBe('not-an-object')
    expect(validateImportPayload('text').reason).toBe('not-an-object')
  })
})

/* ── Storage key and shape ──────────────────────────────────────────── */

describe('storage key', () => {
  it('is namespaced to this feature and versioned', () => {
    expect(STORAGE_KEY).toBe('scholarzone.bangladesh-journey.v1')
    expect(STORAGE_KEY).not.toMatch(/saved-scholarship/i)
    expect(STORAGE_KEY).not.toMatch(/^localStorage$/)
  })
})
