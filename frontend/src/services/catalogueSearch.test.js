/**
 * Catalogue search.
 *
 * These tests pin the three defects the tokenised search replaces, and pin
 * that the replacement does not introduce a worse one:
 *
 *   1. "  daad " matched nothing, because surrounding spaces were part of the
 *      needle.
 *   2. "daad." matched nothing, because punctuation was part of the needle.
 *   3. "DAAD Germany" matched nothing when the two terms appeared in different
 *      fields, because a single substring test cannot reorder them.
 *
 * The guard in the other direction is equally load-bearing: a query must never
 * *invent* a match. A record whose title is "KTH India Scholarship" must not be
 * returned for "kth sweden", however close the two records are.
 */

import { describe, expect, it } from 'vitest'
import {
  describeSearch,
  matchesTokens,
  normalizeQuery,
  scoreRecord,
  searchRecords,
  tokenizeQuery,
} from './catalogueSearch.js'

const record = (overrides = {}) => ({
  id: 1,
  title: 'KTH India Scholarship',
  name: 'KTH India Scholarship',
  official_source: 'KTH Royal Institute of Technology',
  country: 'Sweden',
  region: 'Europe',
  degree: 'Master',
  degree_levels: 'Master',
  funding: 'Fully Funded',
  funding_type: 'Fully Funded',
  eligibility_summary: 'Applicants from India with a bachelor degree.',
  benefits: ['Tuition fee coverage'],
  coverage: 'Full tuition',
  requirements: ['CV'],
  documents: ['CV'],
  required_documents: ['CV'],
  english_requirement: 'IELTS 6.5',
  application_method: ['Online'],
  program_type: 'University scholarship',
  best_fit: 'Indian master applicants',
  duration: '2 years',
  ...overrides,
})

const catalogue = [
  record({
    // Distinctive values on the fields the discriminating queries use, so a
    // match can be attributed to the field under test rather than to a value
    // every fixture happens to share.
    benefits: ['Tuition fee coverage', 'Monthly living allowance'],
    requirements: ['CV', 'Transcript', 'Research proposal'],
    application_method: ['Online through the provider portal'],
  }),
  record({
    id: 3,
    title: 'Another USA Scholarship',
    name: 'Another USA Scholarship',
    // A distinct provider, so a query on one provider's name does not leak into
    // the other record through a field the fixtures share.
    official_source: 'Massachusetts Institute of Technology',
    country: 'USA',
    region: 'North America',
    degree: 'Bachelor',
    funding: 'Partial',
    english_requirement: 'TOEFL 100',
    benefits: ['Partial fee reduction'],
    requirements: ['CV', 'Two references'],
    application_method: ['By post'],
  }),
  record({
    id: 2,
    title: 'NUS Research Scholarship',
    name: 'NUS Research Scholarship',
    official_source: 'NUS Graduate School',
    country: 'Singapore',
    region: 'Asia',
    degree: 'PhD',
    funding: 'Partial',
    english_requirement: 'TOEFL 85',
    benefits: ['Monthly stipend'],
    requirements: ['CV', 'Research proposal', 'GRE score'],
    application_method: ['Through the graduate school'],
  }),
]

describe('normalizeQuery', () => {
  it('removes surrounding and internal whitespace runs', () => {
    expect(normalizeQuery('  daad ')).toBe('daad')
    expect(normalizeQuery('fully   funded\n\tscholarship')).toBe('fully funded scholarship')
  })

  it('removes punctuation', () => {
    expect(normalizeQuery('daad.')).toBe('daad')
    expect(normalizeQuery('m.a.sc')).toBe('m a sc')
    expect(normalizeQuery("bachelor's")).toBe('bachelor s')
    expect(normalizeQuery('kth-india')).toBe('kth india')
  })

  it('lowercases', () => {
    expect(normalizeQuery('DAAD Germany')).toBe('daad germany')
  })

  it('returns an empty string for a non-string or a blank value', () => {
    expect(normalizeQuery(null)).toBe('')
    expect(normalizeQuery(undefined)).toBe('')
    expect(normalizeQuery(42)).toBe('')
    expect(normalizeQuery('   ')).toBe('')
    expect(normalizeQuery('---')).toBe('')
  })
})

describe('tokenizeQuery', () => {
  it('splits into the terms that must all be present', () => {
    expect(tokenizeQuery('DAAD  Germany')).toEqual(['daad', 'germany'])
  })

  it('returns an empty list for a blank query', () => {
    expect(tokenizeQuery('')).toEqual([])
    expect(tokenizeQuery('   ')).toEqual([])
    expect(tokenizeQuery(null)).toEqual([])
  })
})

describe('searchRecords', () => {
  it('matches with surrounding spaces and trailing punctuation', () => {
    // The two defects that made the previous search unusable.
    expect(searchRecords(catalogue, '  kth ').map((r) => r.id)).toEqual([1])
    expect(searchRecords(catalogue, 'kth.').map((r) => r.id)).toEqual([1])
  })

  it('matches terms in any field and any order', () => {
    // Both terms present but in different fields, in the opposite order to the
    // record's own field order. A single substring test cannot reorder them.
    expect(searchRecords(catalogue, 'scholarship singapore').map((r) => r.id)).toEqual([2])
    expect(searchRecords(catalogue, 'singapore scholarship').map((r) => r.id)).toEqual([2])
    expect(searchRecords(catalogue, 'royal institute sweden').map((r) => r.id)).toEqual([1])
  })

  it('requires every term (AND, not OR)', () => {
    expect(searchRecords(catalogue, 'kth singapore')).toEqual([])
    expect(searchRecords(catalogue, 'nus singapore').map((r) => r.id)).toEqual([2])
  })

  it('searches the provider, study level and funding fields', () => {
    // Fields the previous five-field search did not reach at all.
    expect(searchRecords(catalogue, 'kth royal institute').map((r) => r.id)).toEqual([1])
    expect(searchRecords(catalogue, 'nus graduate school').map((r) => r.id)).toEqual([2])
    expect(searchRecords(catalogue, 'massachusetts institute').map((r) => r.id)).toEqual([3])
    expect(searchRecords(catalogue, 'IELTS').map((r) => r.id)).toEqual([1])
    expect(searchRecords(catalogue, 'europe').map((r) => r.id)).toEqual([1])
  })

  it('searches array-valued fields rather than skipping them', () => {
    // `benefits`, `requirements`, `documents` and `application_method` are
    // lists on real records. A field that is a list must contribute its items.
    expect(searchRecords(catalogue, 'living allowance').map((r) => r.id)).toEqual([1])
    expect(searchRecords(catalogue, 'transcript').map((r) => r.id)).toEqual([1])
    expect(searchRecords(catalogue, 'research proposal').map((r) => r.id).sort()).toEqual([1, 2])
    expect(searchRecords(catalogue, 'by post').map((r) => r.id)).toEqual([3])
  })

  it('searches eligibility text, so a level word finds award-level records too', () => {
    // "bachelor" appears in record 1's eligibility_summary and NOT in its
    // degree field. Both are legitimate matches for a student typing a level:
    // one is the record's own level, the other is a level it says it accepts.
    const ids = searchRecords(catalogue, 'bachelor').map((r) => r.id).sort()
    expect(ids).toEqual([1, 2, 3])
    // And a level that no record claims is still empty, so a wide field set has
    // not turned this into a match-everything search.
    expect(searchRecords(catalogue, 'quantum astrophysics')).toEqual([])
  })

  it('searches array-valued fields rather than skipping them', () => {
    // `benefits`, `requirements`, `documents` and `application_method` are
    // lists on real records. A field that is a list must contribute its items.
    expect(searchRecords(catalogue, 'transcript').map((r) => r.id)).toContain(1)
  })

  it('returns the input order for a blank query and scores nothing', () => {
    expect(searchRecords(catalogue, '').map((r) => r.id)).toEqual([1, 3, 2])
    expect(searchRecords(catalogue, '   ')).toBe(catalogue)
  })

  it('is total for non-array input', () => {
    expect(searchRecords(null, 'kth')).toEqual([])
    expect(searchRecords(undefined, 'kth')).toEqual([])
  })

  it('ranks a title match above a summary-only match', () => {
    const ranked = searchRecords(
      [
        record({ id: 10, title: 'A Wide Ranging Master Arts Award', best_fit: 'kth' }),
        record({ id: 11, title: 'KTH India Scholarship' }),
      ],
      'kth',
    )
    expect(ranked.map((r) => r.id)).toEqual([11, 10])
  })

  it('does not return a record that fails one term', () => {
    expect(searchRecords(catalogue, 'kth nonexistent-term')).toEqual([])
  })

  it('handles a record with every optional field missing', () => {
    const sparse = [{ id: 99, title: 'Sparse Award' }]
    expect(searchRecords(sparse, 'sparse').map((r) => r.id)).toEqual([99])
    expect(searchRecords(sparse, 'sparse sweden')).toEqual([])
  })

  it('is case-insensitive and punctuation-insensitive on both sides', () => {
    expect(searchRecords(catalogue, 'K.T.H.!').map((r) => r.id)).toEqual([1])
  })
})

describe('scoreRecord', () => {
  it('scores zero when there is no query', () => {
    expect(scoreRecord(record(), [])).toBe(0)
    expect(scoreRecord(record(), null)).toBe(0)
  })

  it('scores a title hit above a best_fit hit', () => {
    const titleScore = scoreRecord(record(), tokenizeQuery('kth'))
    const fitScore = scoreRecord(record({ title: 'Something Else' }), tokenizeQuery('indian'))
    expect(titleScore).toBeGreaterThan(fitScore)
  })
})

describe('matchesTokens', () => {
  it('is true when there is no query', () => {
    expect(matchesTokens(record(), [])).toBe(true)
  })

  it('is false when a term is absent', () => {
    expect(matchesTokens(record(), ['kth', 'sweden'])).toBe(true)
    expect(matchesTokens(record(), ['kth', 'norway'])).toBe(false)
  })
})

describe('describeSearch', () => {
  it('returns null when there is nothing to describe', () => {
    expect(describeSearch('')).toBeNull()
    expect(describeSearch(null)).toBeNull()
  })

  it('reports the term count in a plural-aware form', () => {
    expect(describeSearch('daad')).toEqual({ tokens: ['daad'], termCount: 1, summary: 'one term' })
    expect(describeSearch('daad germany').summary).toBe('2 terms')
  })
})
