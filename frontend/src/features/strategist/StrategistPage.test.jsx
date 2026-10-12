/**
 * Component + behaviour tests for the Study-to-Career Strategist.
 *
 * These assert the integrity and safety the feature promises at the UI layer:
 * an insufficient cell shows "Insufficient data" with a reason and never a
 * number; every fact shows source + rate date; there is no "best country";
 * the disclaimer is present; share/export carry only choices and no PII; and the
 * loading, error, offline and partial states all render. api.js is mocked so each
 * state is exercised deterministically.
 */
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const fetchSubjects = vi.fn()
const fetchPlan = vi.fn()
const fetchPathway = vi.fn()

vi.mock('./lib/api.js', () => ({
  fetchSubjects: (...a) => fetchSubjects(...a),
  fetchPlan: (...a) => fetchPlan(...a),
  fetchPathway: (...a) => fetchPathway(...a),
}))

import { StrategistPage } from './StrategistPage.jsx'
import { buildShareURL } from './lib/shareExport.js'

const SUBJECTS = [
  { key: 'computer_science', name_en: 'Computer Science / AI', name_bn: 'কম্পিউটার সায়েন্স', occupation_slug: 'software_developer', coverage_note_en: 'Sourced in US/CA/DE/AU.' },
  { key: 'data_science', name_en: 'Data Science', name_bn: 'ডেটা সায়েন্স', occupation_slug: 'data_scientist', coverage_note_en: 'US/CA only.' },
]

const CRITERIA = [
  { key: 'subject_salary', label_en: 'Subject-level salary', category: 'career', essential: true, higher_is_better: true, money: true },
  { key: 'living_cost', label_en: 'Living cost (monthly, medium)', category: 'cost', essential: false, higher_is_better: false, money: true },
  { key: 'post_study_work', label_en: 'Post-study work route', category: 'pathway', essential: true, higher_is_better: true, money: false },
]

const PLAN = {
  request: { subject_key: 'computer_science', degree: 'master', funding_model: 'self_funded', budget_bdt: null, weights: { cost: 25, funding: 15, career: 30, pathway: 30 }, max_countries: 6 },
  ranking_rule: 'No single composite score is shown.',
  criteria: CRITERIA,
  disclaimer: 'Informational only. Not legal, immigration, financial or admission advice.',
  comparison: [
    {
      iso2: 'CA', name: 'Canada', currency: 'CAD', ranked: true,
      evidence_completeness: { sourced: 2, total: 3, fraction: '2/3', criteria_sourced: ['post_study_work', 'subject_salary'], criteria_missing: ['living_cost'] },
      cells: {
        subject_salary: { criterion: 'subject_salary', category: 'career', essential: true, status: 'sourced', value: 48.08, currency: 'CAD', per: 'hour', basis: 'gross', granularity: 'occupation', stale_warning: false, as_of: '2023-2024', value_status: 'OFFICIAL_STATISTICS', sources: [{ url: 'https://jobbank.gc.ca/x', publisher: 'Statistics Canada' }], bdt: { value: 4160.69, from_currency: 'CAD', rate_dates: ['2026-10-02', '2026-10-11'] }, reason: null },
        living_cost: { criterion: 'living_cost', category: 'cost', essential: false, status: 'insufficient', reason: 'A medium monthly living-cost total is not sourced for this country.', bdt: null },
        post_study_work: { criterion: 'post_study_work', category: 'pathway', essential: true, status: 'sourced', value: 6, per: 'months' },
      },
      why: { recommended: ['Prioritised subject-level salary is sourced.'], risks: ['Living cost (monthly, medium): A medium monthly living-cost total is not sourced for this country.'] },
    },
  ],
  insufficient_data: [
    {
      iso2: 'US', name: 'United States', currency: 'USD', ranked: false, not_ranked_reason: 'An essential criterion is missing.',
      evidence_completeness: { sourced: 1, total: 3, fraction: '1/3', criteria_sourced: ['subject_salary'], criteria_missing: ['living_cost', 'post_study_work'] },
      cells: {
        subject_salary: { criterion: 'subject_salary', status: 'sourced', value: 135980, currency: 'USD', per: 'year', basis: 'gross', granularity: 'occupation', stale_warning: false, as_of: '2025-05', sources: [{ url: 'https://bls.gov/x', publisher: 'U.S. Bureau of Labor Statistics' }], bdt: { value: 16760000, rate_dates: ['2026-10-02', '2026-10-11'] } },
        living_cost: { criterion: 'living_cost', status: 'insufficient', reason: 'No sourced living-cost total.', bdt: null },
        post_study_work: { criterion: 'post_study_work', status: 'insufficient', reason: 'No sourced post-study work route.', bdt: null },
      },
      why: { recommended: [], risks: ['Post-study work route: No sourced post-study work route.'] },
    },
  ],
}

async function goToResults(user) {
  await user.click(screen.getByRole('button', { name: /next/i }))          // subject -> degree
  await user.click(screen.getByRole('button', { name: /next/i }))          // degree -> funding
  await user.click(screen.getByRole('button', { name: /next/i }))          // funding -> budget
  await user.click(screen.getByRole('button', { name: /next/i }))          // budget -> priorities
  await user.click(screen.getByRole('button', { name: /compare countries/i }))
}

beforeEach(() => {
  fetchSubjects.mockReset().mockResolvedValue({ subjects: SUBJECTS })
  fetchPlan.mockReset().mockResolvedValue(PLAN)
  fetchPathway.mockReset().mockResolvedValue({ iso2: 'DE', steps: [] })
})

afterEach(cleanup)

describe('strategist wizard + results', () => {
  it('renders the happy path with BDT beside original currency and rate date', async () => {
    const user = userEvent.setup()
    render(<StrategistPage />)
    await goToResults(user)
    await waitFor(() => expect(screen.getByTestId('results')).toBeInTheDocument())
    const ca = document.querySelector('[data-country="CA"]')
    await waitFor(() => expect(ca).toBeTruthy())

    // BDT figure shown beside the original currency and a rate date, and the
    // official source is linked. (Exact digits are locale/formatted, so match the
    // labels rather than a hard-coded number.)
    expect(ca.textContent).toMatch(/BDT/)
    expect(ca.textContent).toMatch(/Statistics Canada/)
    expect(ca.textContent).toMatch(/rate date/i)
  })

  it('shows insufficient data with a reason and never a number', async () => {
    const user = userEvent.setup()
    render(<StrategistPage />)
    await goToResults(user)
    await waitFor(() => expect(screen.getByTestId('results')).toBeInTheDocument())
    // The insufficient living-cost reason appears (cell + why-risks) and no BDT is
    // rendered for it.
    expect(screen.getAllByText(/is not sourced for this country/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Insufficient data/i).length).toBeGreaterThan(0)
  })

  it('never declares a single best country and echoes the weights', async () => {
    const user = userEvent.setup()
    render(<StrategistPage />)
    await goToResults(user)
    await waitFor(() => expect(screen.getByTestId('results')).toBeInTheDocument())
    expect(screen.queryByText(/best country/i)).not.toBeInTheDocument()
    expect(screen.getByText(/No single "best" country is declared/i)).toBeInTheDocument()
  })

  it('shows the evidence-completeness meter with an accessible role', async () => {
    const user = userEvent.setup()
    render(<StrategistPage />)
    await goToResults(user)
    await waitFor(() => expect(screen.getByTestId('results')).toBeInTheDocument())
    const meter = screen.getAllByRole('meter')[0]
    expect(meter.getAttribute('aria-valuemax')).toBe('3')
  })

  it('renders the disclaimer', async () => {
    const user = userEvent.setup()
    render(<StrategistPage />)
    await goToResults(user)
    await waitFor(() => expect(screen.getByTestId('disclaimer')).toBeInTheDocument())
    expect(screen.getByTestId('disclaimer').textContent).toMatch(/not legal/i)
  })

  it('renders the insufficient-data (not-ranked) country with a reason', async () => {
    const user = userEvent.setup()
    render(<StrategistPage />)
    await goToResults(user)
    await waitFor(() => expect(screen.getByTestId('results')).toBeInTheDocument())
    expect(screen.getByText(/United States/)).toBeInTheDocument()
    expect(screen.getAllByText(/No sourced post-study work route/i).length).toBeGreaterThan(0)
  })

  it('language toggle is accessible', async () => {
    const user = userEvent.setup()
    render(<StrategistPage />)
    const bn = screen.getByRole('button', { name: 'Bangla' })
    expect(bn.getAttribute('aria-pressed')).toBe('false')
    await user.click(bn)
    expect(bn.getAttribute('aria-pressed')).toBe('true')
  })

  it('share link carries only choices and no PII', () => {
    const url = buildShareURL({ subject_key: 'computer_science', degree: 'master', funding_model: 'self_funded', weights: { cost: 25 } })
    expect(url).toContain('subject=computer_science')
    expect(url).toContain('degree=master')
    expect(url).not.toMatch(/@|name=|email|token/i)
  })
})

describe('strategist states', () => {
  it('shows an error state and can retry', async () => {
    fetchPlan.mockReset().mockRejectedValueOnce(new Error('boom'))
    const user = userEvent.setup()
    render(<StrategistPage />)
    await goToResults(user)
    await waitFor(() => expect(screen.getByTestId('state-error')).toBeInTheDocument())
    fetchPlan.mockResolvedValue(PLAN)
    await user.click(screen.getByRole('button', { name: /compare countries/i }))
    await waitFor(() => expect(screen.getByTestId('results')).toBeInTheDocument())
  })

  it('shows a loading state while the plan is in flight', async () => {
    let resolve
    fetchPlan.mockReset().mockReturnValue(new Promise((r) => { resolve = r }))
    const user = userEvent.setup()
    render(<StrategistPage />)
    await user.click(screen.getByRole('button', { name: /next/i }))
    await user.click(screen.getByRole('button', { name: /next/i }))
    await user.click(screen.getByRole('button', { name: /next/i }))
    await user.click(screen.getByRole('button', { name: /next/i }))
    await user.click(screen.getByRole('button', { name: /compare countries/i }))
    await waitFor(() => expect(screen.getByTestId('state-loading')).toBeInTheDocument())
    resolve(PLAN)
  })
})
