/**
 * The researched-fields presentation, asserted one rule at a time.
 *
 * These tests exist because the researched enrichment is the newest thing the
 * detail page renders, and its contract is primarily about refusal: a null
 * amount stays null, an unconfirmed amount never becomes a number, an
 * unmatched citation never becomes a link, and guidance without content
 * never becomes a section. A display that fills the gaps in would look
 * better in a screenshot and be worse in a catalogue of facts.
 */
import { describe, expect, it } from 'vitest'
import {
  buildApplicantGuidance,
  buildOfficialLinks,
  buildQuickFacts,
  formatFundingValue,
} from './scholarshipDetail.js'

describe('formatFundingValue', () => {
  it('formats a confirmed amount with its currency and period', () => {
    expect(formatFundingValue(47400, 'EUR', 'per year')).toBe('€47,400 per year')
  })

  it('falls back to the ISO code for a currency the formatter cannot symbolise', () => {
    expect(formatFundingValue(1000, 'CLP', 'per academic year')).toBe(
      'CLP 1,000 per academic year',
    )
  })

  it('returns null for every unconfirmed state', () => {
    expect(formatFundingValue(null, 'EUR', 'per year')).toBeNull()
    expect(formatFundingValue('', 'EUR', 'per year')).toBeNull()
    expect(formatFundingValue('75%', 'EUR', 'per year')).toBeNull()
    expect(formatFundingValue('fully funded', 'EUR', 'per year')).toBeNull()
  })

  it('never rounds a confirmed figure', () => {
    expect(formatFundingValue(47000.5, 'USD')).toBe('US$47,000.50')
  })
})

describe('buildQuickFacts', () => {
  it('places the researched amount under the funding label', () => {
    const facts = buildQuickFacts({
      funding: 'Fully Funded',
      funding_amount: 42000,
      funding_currency: 'CAD',
      funding_period: 'per year',
      degree: 'PhD',
    })
    const labels = facts.map((fact) => fact.id)
    expect(labels).toContain('funding')
    expect(labels).toContain('funding_amount')
    expect(labels.indexOf('funding')).toBeLessThan(labels.indexOf('funding_amount'))
  })

  it('publishes a true coverage claim and stays silent otherwise', () => {
    const covered = buildQuickFacts({ funding: 'Award', tuition_coverage: true })
    expect(covered.find((fact) => fact.id === 'tuition_coverage')).toBeTruthy()

    for (const coverage of [false, null, undefined]) {
      const facts = buildQuickFacts({ funding: 'Award', tuition_coverage: coverage })
      expect(facts.find((fact) => fact.id === 'tuition_coverage')).toBeUndefined()
    }
  })

  it('shows no amount row when no figure was confirmed', () => {
    const facts = buildQuickFacts({
      funding: 'Fully Funded',
      funding_amount: null,
      funding_currency: null,
      funding_period: null,
    })
    expect(facts.find((fact) => fact.id === 'funding_amount')).toBeUndefined()
  })
})

describe('buildOfficialLinks', () => {
  it('renders the canonical entry points first, then the research citations', () => {
    const links = buildOfficialLinks({
      application_link: 'https://example.org/apply',
      official_source_url: 'https://example.org/source',
      source_citations: ['https://example.org/citation'],
      official_source_urls: ['https://example.org/further'],
    })
    expect(links.map((link) => link.id)).toEqual([
      'application',
      'source',
      'citation-1',
      'official-1',
    ])
    expect(links[2].label).toBe('Official citation')
  })

  it('de-duplicates a research citation that is the same URL as a canonical link', () => {
    const links = buildOfficialLinks({
      official_source_url: 'https://example.org/source',
      source_citations: ['https://example.org/source'],
      official_source_urls: ['https://example.org/source'],
    })
    expect(links.map((link) => link.url)).toEqual(['https://example.org/source'])
  })

  it('discards anything that is not an absolute http(s) URL', () => {
    const links = buildOfficialLinks({
      source_citations: ['not-a-url', '/relative/path', 'ftp://files.example.org/x'],
      official_source_urls: [null, '', 42],
    })
    expect(links).toEqual([])
  })
})

describe('buildApplicantGuidance', () => {
  it('renders the authored sections in a fixed reading order', () => {
    const guidance = buildApplicantGuidance({
      alerts: ['Watch the notice board.'],
      summary: 'What this award is unusual about.',
    })
    expect(guidance.sections.map((section) => section.id)).toEqual(['summary', 'alerts'])
    expect(guidance.sections[0].prose).toBe(true)
    expect(guidance.sections[1].prose).toBe(true)
  })

  it('joins an alert trigger with its message', () => {
    const guidance = buildApplicantGuidance({
      alerts: [{ trigger: 'Site shows closed', message: 'Watch in September.' }],
    })
    expect(guidance.sections[0].items).toEqual(['Site shows closed — Watch in September.'])
  })

  it('drops a section whose value carries nothing usable', () => {
    const guidance = buildApplicantGuidance({
      summary: null,
      best_fit: '   ',
      alerts: [null, ''],
      estimated_uncovered_costs: null,
    })
    expect(guidance).toBeNull()
  })

  it('returns null for every absent-or-empty blob', () => {
    expect(buildApplicantGuidance(null)).toBeNull()
    expect(buildApplicantGuidance({})).toBeNull()
    expect(buildApplicantGuidance('summary')).toBeNull()
  })
})
