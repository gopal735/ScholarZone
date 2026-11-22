import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import MentorAnswer from './MentorAnswer'

const BASE_ANSWER = {
  request_id: 'r1',
  as_of: '2026-06-01',
  intent: 'SCHOLARSHIP_DISCOVERY',
  intent_label: 'Scholarship discovery',
  supported: true,
  headline: 'Scholarship discovery results',
  why: 'ScholarZone searched the public catalogue.',
  known: [],
  unknown: [],
  next_steps: [],
  caveats: [],
  notes: [],
  general_guidance_only: false,
  provider_mode: 'disabled',
  provider_used: false,
  answer_schema_version: 1,
  diagnostics: {},
}

describe('MentorAnswer discovery rendering', () => {
  it('AMBIGUOUS_FILTER renders explanation and no cards even with stale results', () => {
    const answer = {
      ...BASE_ANSWER,
      search_status: 'AMBIGUOUS_FILTER',
      verified_matches: [
        { scholarship_id: 1, title: 'Stale Verified', country: 'Germany', funding_classification: 'X', warnings: [] },
      ],
      potential_matches: [
        { scholarship_id: 2, title: 'Stale Potential', country: 'France', funding_classification: 'Y', warnings: [] },
      ],
    }
    render(
      <MemoryRouter>
        <MentorAnswer answer={answer} />
      </MemoryRouter>,
    )
    expect(screen.getByText(/ambiguous; please clarify/i)).toBeInTheDocument()
    expect(screen.queryByText('Stale Verified')).not.toBeInTheDocument()
    expect(screen.queryByText('Stale Potential')).not.toBeInTheDocument()
  })

  it('UNSUPPORTED_FILTER renders explanation and no cards', () => {
    const answer = {
      ...BASE_ANSWER,
      search_status: 'UNSUPPORTED_FILTER',
      verified_matches: [
        { scholarship_id: 3, title: 'Unrelated Verified', country: 'Germany', funding_classification: 'X', warnings: [] },
      ],
      potential_matches: [
        { scholarship_id: 4, title: 'Unrelated Potential', country: 'France', funding_classification: 'Y', warnings: [] },
      ],
    }
    render(
      <MemoryRouter>
        <MentorAnswer answer={answer} />
      </MemoryRouter>,
    )
    expect(screen.getByText(/no catalogue coverage yet/i)).toBeInTheDocument()
    expect(screen.queryByText('Unrelated Verified')).not.toBeInTheDocument()
    expect(screen.queryByText('Unrelated Potential')).not.toBeInTheDocument()
  })

  it('RESOLVED_NO_CATALOGUE_DATA renders empty state without worldwide results', () => {
    const answer = {
      ...BASE_ANSWER,
      search_status: 'RESOLVED_NO_CATALOGUE_DATA',
      verified_matches: [],
      potential_matches: [],
    }
    render(
      <MemoryRouter>
        <MentorAnswer answer={answer} />
      </MemoryRouter>,
    )
    expect(screen.getByText(/No scholarship matches found/i)).toBeInTheDocument()
  })

  it('valid discovery renders verified and potential with distinction', () => {
    const answer = {
      ...BASE_ANSWER,
      search_status: 'POTENTIAL_MATCHES_FOUND',
      verified_matches: [
        { scholarship_id: 10, title: 'Verified Match', country: 'Germany', funding_classification: 'STIPEND_TEXT_CANDIDATE', warnings: ['Stipend mention found, but it has not been independently verified.'] },
      ],
      potential_matches: [
        { scholarship_id: 11, title: 'Potential Match', country: 'France', funding_classification: 'FUNDING_SUPPORT_CONFIRMED_STIPEND_UNCLEAR', warnings: ['Funding is described, but stipend evidence is not established.'] },
      ],
    }
    render(
      <MemoryRouter>
        <MentorAnswer answer={answer} />
      </MemoryRouter>,
    )
    expect(screen.getByText('Verified Match')).toBeInTheDocument()
    expect(screen.getByText('Potential Match')).toBeInTheDocument()
    expect(screen.getByText(/stipend evidence is not established/i)).toBeInTheDocument()
  })

  it('scholarship cards link to internal detail page when id exists', () => {
    const answer = {
      ...BASE_ANSWER,
      search_status: 'POTENTIAL_MATCHES_FOUND',
      verified_matches: [],
      potential_matches: [
        { scholarship_id: 42, title: 'Detail Link Match', country: 'Germany', funding_classification: 'X', warnings: [], official_source_url: 'https://example.com/official' },
      ],
    }
    render(
      <MemoryRouter>
        <MentorAnswer answer={answer} />
      </MemoryRouter>,
    )
    const link = screen.getByRole('link', { name: 'Detail Link Match' })
    expect(link).toHaveAttribute('href', '/scholarships/42')
  })

  it('retains official source link separately from internal detail link', () => {
    const answer = {
      ...BASE_ANSWER,
      search_status: 'POTENTIAL_MATCHES_FOUND',
      verified_matches: [],
      potential_matches: [
        { scholarship_id: 7, title: 'Source Match', country: 'Germany', funding_classification: 'X', warnings: [], official_source_url: 'https://example.com/official' },
      ],
    }
    render(
      <MemoryRouter>
        <MentorAnswer answer={answer} />
      </MemoryRouter>,
    )
    const official = screen.getByRole('link', { name: /Official source/i })
    expect(official).toHaveAttribute('href', 'https://example.com/official')
    expect(official).toHaveAttribute('target', '_blank')
  })

  it('FUNDING_EVIDENCE_CONFLICT does not display record as confirmed funding', () => {
    const answer = {
      ...BASE_ANSWER,
      search_status: 'POTENTIAL_MATCHES_FOUND',
      verified_matches: [],
      potential_matches: [
        {
          scholarship_id: 99,
          title: 'Conflict Match',
          country: 'Germany',
          funding_classification: 'FUNDING_EVIDENCE_CONFLICT',
          warnings: ['Funding evidence conflicts across source fields; treat as uncertain.'],
          official_source_url: null,
        },
      ],
    }
    render(
      <MemoryRouter>
        <MentorAnswer answer={answer} />
      </MemoryRouter>,
    )
    expect(screen.getByText('Conflict Match')).toBeInTheDocument()
    expect(screen.getByText(/FUNDING_EVIDENCE_CONFLICT/)).toBeInTheDocument()
    expect(screen.getByText(/treat as uncertain/i)).toBeInTheDocument()
    expect(screen.queryByText(/confirmed funding/i)).not.toBeInTheDocument()
  })
})
