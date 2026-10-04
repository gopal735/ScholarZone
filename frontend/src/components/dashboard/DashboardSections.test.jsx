/**
 * Dashboard section rendering.
 *
 * Two properties are being defended. First, that an absence reads as an absence:
 * the engine's nulls must reach the page as "not evaluated" rather than as a
 * zero, because a reader cannot tell a zero apart from a real measurement.
 * Second, that every empty state is a usable dead end - a heading, an
 * explanation, and a link to the page that resolves it.
 */

import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import ApplicationProgress from './ApplicationProgress'
import DeadlineWatch from './DeadlineWatch'
import MatchList from './MatchList'
import OpportunitySummary from './OpportunitySummary'
import ProfileSnapshot from './ProfileSnapshot'
import {
  NextActions,
  ProfileGaps,
  SavedScholarships,
} from './DashboardSections'

function renderWithRouter(ui) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

const BASE_MATCH = {
  scholarship_id: 42,
  name: 'Rotterdam Scholarship',
  country: 'Netherlands',
  degree: 'Master',
  funding: 'full',
  detail_url: '/scholarships/42',
  official_source_url: 'https://example.org/programme',
  deadline: 'Applications close 1 September 2026',
  deadline_precision: 'exact',
  days_to_deadline: 90,
  timing_bucket: 'COMFORTABLE',
  eligibility: 'ELIGIBLE',
  fit_score: 88,
  fit_label: 'VERY_STRONG_FIT',
  fit_label_display: 'Very strong fit',
  confidence_score: 81,
  confidence_label: 'HIGH',
  data_coverage: 0.9,
  readiness_score: 80,
  readiness_band: 'READY',
  readiness_label: 'Ready',
  verification_status: 'active',
  verified: true,
  verification_display: 'Verified',
  why: [{ code: 'FIELD_EXACT_MATCH', message: 'Your field of study matches.', component: 'field' }],
  needs_attention: [
    {
      code: 'LANGUAGE_NOT_PROVIDED',
      message: 'Add your English test score.',
      category: 'MISSING_USER_INFORMATION',
      component: 'language',
      href: '/match',
      action_label: 'Complete your profile',
    },
  ],
  actions: [],
  unverified_requirements: [],
}

describe('OpportunitySummary', () => {
  const summary = {
    universe: 'match_analysed',
    total_candidates: 386,
    visible_candidate_count: 24,
    eligible_count: 120,
    needs_verification_count: 180,
    ineligible_count: 86,
    strong_match_count: 31,
    scored_count: 300,
    not_scored_count: 86,
    ready_to_apply_count: 44,
    open_with_deadline_count: 210,
    closing_soon_count: 12,
    truncated: true,
  }

  const consistency = {
    match_total_candidates: 386,
    count_total_candidates: 386,
    counts_agree: true,
    integrity_status: 'PASS',
    integrity_issues: [],
  }

  it('renders the server counts verbatim', () => {
    renderWithRouter(<OpportunitySummary summary={summary} consistency={consistency} />)

    expect(screen.getByText('31')).toBeInTheDocument()
    expect(screen.getByText('180')).toBeInTheDocument()
    expect(screen.getByText('44')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
  })

  it('states the universe rather than leaving it to be inferred', () => {
    renderWithRouter(<OpportunitySummary summary={summary} consistency={consistency} />)
    expect(screen.getByText(/386 opportunities analysed against your profile/)).toBeInTheDocument()
  })

  it('reports when the two engines disagree instead of hiding it', () => {
    renderWithRouter(
      <OpportunitySummary
        summary={summary}
        consistency={{ ...consistency, counts_agree: false, count_total_candidates: 385 }}
      />,
    )
    expect(screen.getByText(/engine totals disagree/)).toBeInTheDocument()
  })

  it('surfaces integrity issues rather than showing a clean-looking dashboard', () => {
    renderWithRouter(
      <OpportunitySummary
        summary={summary}
        consistency={{
          ...consistency,
          integrity_status: 'WARNING',
          integrity_issues: ['No historical baseline available.'],
        }}
      />,
    )
    expect(screen.getByText('No historical baseline available.')).toBeInTheDocument()
    expect(screen.getByText(/integrity WARNING/)).toBeInTheDocument()
  })
})

describe('ProfileSnapshot', () => {
  const profile = {
    is_empty: false,
    updated_at: null,
    fields: [
      { key: 'citizenship', label: 'Nationality', value: 'Bangladesh', is_supplied: true },
      { key: 'intended_field', label: 'Field of study', value: null, is_supplied: false },
      { key: 'overall_result', label: 'Academic result', value: '82 percentage', is_supplied: true },
    ],
  }

  const component = (name, score) => ({
    name,
    label: name,
    weight: 0.25,
    status: 'EVALUATED',
    score,
    detail: 'Detail',
    effective_weight: 0.25,
    contribution: score * 0.25,
  })

  it('shows a measured completeness score', () => {
    renderWithRouter(
      <ProfileSnapshot
        profile={profile}
        strength={{
          score: 74,
          label: 'Good',
          detail: 'Completeness only.',
          components: [component('academic', 100), component('language', 48)],
        }}
        onEditProfile={() => {}}
      />,
    )

    expect(screen.getByText('74%')).toBeInTheDocument()
    expect(screen.getByRole('progressbar', { name: 'Profile completeness' })).toHaveAttribute(
      'aria-valuenow',
      '74',
    )
  })

  it('does not render an empty progress bar for an unmeasured profile', () => {
    renderWithRouter(
      <ProfileSnapshot
        profile={{ ...profile, is_empty: true, fields: [] }}
        strength={{ score: null, label: null, detail: '', components: [] }}
        onEditProfile={() => {}}
      />,
    )

    // The whole point: nothing supplied is "not measured", never "0% complete".
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
    expect(screen.queryByText('0%')).not.toBeInTheDocument()
    expect(screen.getByText('Not measured yet')).toBeInTheDocument()
  })

  it('lists supplied and missing fields from the same source', () => {
    renderWithRouter(
      <ProfileSnapshot
        profile={profile}
        strength={{ score: 50, label: 'Partial', detail: '', components: [] }}
        onEditProfile={() => {}}
      />,
    )

    expect(screen.getByText('Bangladesh')).toBeInTheDocument()
    expect(screen.getByText(/Not supplied yet \(1\)/)).toBeInTheDocument()
  })

  it('routes to the profile editor', async () => {
    const onEdit = vi.fn()
    renderWithRouter(
      <ProfileSnapshot
        profile={profile}
        strength={{ score: 50, label: 'Partial', detail: '', components: [] }}
        onEditProfile={onEdit}
      />,
    )

    await userEvent.click(screen.getByRole('button', { name: 'Complete profile' }))
    expect(onEdit).toHaveBeenCalledOnce()
  })
})

describe('MatchList', () => {
  it('renders engine scores, structured evidence and the trust label', () => {
    renderWithRouter(
      <MatchList matches={[BASE_MATCH]} truncated={false} onSave={() => {}} savedIds={new Set()} />,
    )

    expect(screen.getByRole('link', { name: 'Rotterdam Scholarship' })).toHaveAttribute(
      'href',
      '/scholarships/42',
    )
    expect(screen.getByText('Very strong fit')).toBeInTheDocument()
    expect(screen.getByText('Ready')).toBeInTheDocument()
    expect(screen.getByText('Your field of study matches.')).toBeInTheDocument()
    expect(screen.getByText('Add your English test score.')).toBeInTheDocument()
    expect(screen.getByText('Verified')).toBeInTheDocument()
  })

  it('shows Confirm with provider for a record that is not verified', () => {
    const needsReview = {
      ...BASE_MATCH,
      verification_status: 'needs_review',
      verified: false,
      verification_display: 'Confirm with provider',
    }

    renderWithRouter(
      <MatchList matches={[needsReview]} truncated={false} onSave={() => {}} savedIds={new Set()} />,
    )

    expect(screen.getByText('Confirm with provider')).toBeInTheDocument()
    expect(screen.queryByText('Verified')).not.toBeInTheDocument()
  })

  it('never labels an unevaluated fit score as zero', () => {
    const unevaluated = {
      ...BASE_MATCH,
      fit_score: null,
      fit_label_display: 'Not evaluated',
      readiness_score: null,
      readiness_band: null,
      readiness_label: null,
    }

    renderWithRouter(
      <MatchList matches={[unevaluated]} truncated={false} onSave={() => {}} savedIds={new Set()} />,
    )

    expect(screen.getByText('Not evaluated')).toBeInTheDocument()
    expect(screen.getByText('Readiness not evaluated')).toBeInTheDocument()
  })

  it('marks a non-exact deadline as not day-specific', () => {
    const monthPrecision = {
      ...BASE_MATCH,
      deadline_precision: 'month',
      days_to_deadline: null,
      deadline: 'Applications close in September 2026',
    }

    renderWithRouter(
      <MatchList matches={[monthPrecision]} truncated={false} onSave={() => {}} savedIds={new Set()} />,
    )

    expect(screen.getByText('Applications close in September 2026')).toBeInTheDocument()
    expect(screen.getByText('date not day-specific')).toBeInTheDocument()
  })

  it('requires a quote and its source together, or neither', () => {
    const withSource = {
      ...BASE_MATCH,
      unverified_requirements: [
        {
          kind: 'ELIGIBILITY',
          status: 'UNKNOWN',
          summary: 'Minimum GPA published but not comparable.',
          raw_quote: 'Applicants must hold a 3.5 GPA.',
          provenance_url: 'https://example.org/eligibility',
        },
      ],
    }

    renderWithRouter(
      <MatchList matches={[withSource]} truncated={false} onSave={() => {}} savedIds={new Set()} />,
    )

    expect(screen.getByText('Applicants must hold a 3.5 GPA.')).toBeInTheDocument()

    // Scoped to the disclosure: the card footer carries its own "Official source"
    // link, and matching the wrong one would pass for the wrong reason.
    const disclosure = screen.getByText(/1 published requirement/).closest('details')
    expect(within(disclosure).getByRole('link', { name: 'Official source' })).toHaveAttribute(
      'href',
      'https://example.org/eligibility',
    )
  })

  it('omits the quote block entirely when the provider published none', () => {
    const withoutQuote = {
      ...BASE_MATCH,
      official_source_url: null,
      unverified_requirements: [
        {
          kind: 'ELIGIBILITY',
          status: 'UNKNOWN',
          summary: 'A requirement could not be evaluated.',
          raw_quote: null,
          provenance_url: null,
        },
      ],
    }

    renderWithRouter(
      <MatchList matches={[withoutQuote]} truncated={false} onSave={() => {}} savedIds={new Set()} />,
    )

    const disclosure = screen.getByText(/1 published requirement/).closest('details')
    expect(within(disclosure).queryByRole('link')).not.toBeInTheDocument()
    expect(within(disclosure).getByText('A requirement could not be evaluated.')).toBeInTheDocument()
  })

  it('offers a dead end rather than an empty section', () => {
    renderWithRouter(<MatchList matches={[]} truncated={false} onSave={() => {}} savedIds={new Set()} />)

    expect(screen.getByText('No current matches')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Adjust your profile' })).toHaveAttribute('href', '/match')
  })

  it('reports the save state as a pressed toggle', () => {
    renderWithRouter(
      <MatchList
        matches={[BASE_MATCH]}
        truncated={false}
        onSave={() => {}}
        savedIds={new Set(['42'])}
      />,
    )

    const toggle = screen.getByRole('button', { name: 'Saved' })
    expect(toggle).toHaveAttribute('aria-pressed', 'true')
  })
})

describe('DeadlineWatch', () => {
  const entry = {
    scholarship_id: 42,
    name: 'Rotterdam Scholarship',
    detail_url: '/scholarships/42',
    deadline: 'Applications close 1 September 2026',
    deadline_precision: 'exact',
    days_remaining: 14,
    timing_bucket: 'APPROACHING',
    is_actionable: true,
    readiness_label: 'Ready',
    fit_score: 88,
    application_state: 'in_progress',
    is_saved: true,
    verification_status: 'active',
    verified: true,
    verification_display: 'Verified',
  }

  it('renders the table in the order the server sent it', () => {
    renderWithRouter(
      <DeadlineWatch
        deadlines={[
          entry,
          {
            ...entry,
            scholarship_id: 7,
            name: 'Rolling Programme',
            days_remaining: null,
            is_actionable: false,
            deadline: 'Reviewed on a rolling basis',
            application_state: null,
          },
        ]}
      />,
    )

    const rows = screen.getAllByRole('row').slice(1)
    expect(within(rows[0]).getByRole('link', { name: 'Rotterdam Scholarship' })).toBeInTheDocument()
    expect(within(rows[1]).getByRole('link', { name: 'Rolling Programme' })).toBeInTheDocument()
  })

  it('states the ordering rule instead of leaving it implicit', () => {
    renderWithRouter(<DeadlineWatch deadlines={[entry]} />)
    expect(
      screen.getByText(/Nearest actionable deadline first, then readiness, then scholarship id/),
    ).toBeInTheDocument()
  })

  it('separates an actionable deadline from a rolling one', () => {
    renderWithRouter(
      <DeadlineWatch
        deadlines={[
          entry,
          {
            ...entry,
            scholarship_id: 7,
            days_remaining: null,
            is_actionable: false,
            deadline: 'Reviewed on a rolling basis',
            application_state: null,
          },
        ]}
      />,
    )

    expect(screen.getByText('14 days left')).toBeInTheDocument()
    // Never "0 days left": that would read as overdue for an open programme.
    expect(screen.getByText('Reviewed on a rolling basis')).toBeInTheDocument()
    expect(screen.queryByText('0 days left')).not.toBeInTheDocument()
  })

  it('offers a link to the directory when nothing is being tracked', () => {
    renderWithRouter(<DeadlineWatch deadlines={[]} />)
    expect(screen.getByRole('link', { name: 'Browse scholarships' })).toHaveAttribute(
      'href',
      '/scholarships',
    )
  })
})

describe('ApplicationProgress', () => {
  const application = {
    scholarship: {
      scholarship_id: 42,
      name: 'Rotterdam Scholarship',
      country: 'Netherlands',
      degree: 'Master',
      funding: 'Full',
      detail_url: '/scholarships/42',
      official_source_url: null,
      verification_status: 'active',
      verified: true,
      verification_display: 'Verified',
    },
    state: 'in_progress',
    state_label: 'In progress',
    created_at: '2026-05-01T00:00:00Z',
    updated_at: '2026-05-20T00:00:00Z',
    days_remaining: 14,
    deadline: 'Applications close 1 September 2026',
    readiness_label: 'Ready',
    fit_score: 88,
  }

  it('shows state, deadline and when it last changed', () => {
    renderWithRouter(
      <ApplicationProgress
        applications={[application]}
        states={['saved', 'planning', 'in_progress', 'submitted', 'withdrawn']}
        onChangeState={() => {}}
        onRemove={() => {}}
      />,
    )

    expect(screen.getByLabelText('State')).toHaveValue('in_progress')
    expect(screen.getByText('14 days left')).toBeInTheDocument()
    expect(screen.getByText(/Updated /)).toBeInTheDocument()
  })

  it('offers Continue into the scholarship context', () => {
    renderWithRouter(
      <ApplicationProgress
        applications={[application]}
        states={['in_progress']}
        onChangeState={() => {}}
        onRemove={() => {}}
      />,
    )

    expect(screen.getByRole('link', { name: 'Continue' })).toHaveAttribute('href', '/scholarships/42')
  })

  it('offers the server vocabulary rather than a hard-coded one', () => {
    renderWithRouter(
      <ApplicationProgress
        applications={[application]}
        states={['saved', 'planning']}
        onChangeState={() => {}}
        onRemove={() => {}}
      />,
    )

    const select = screen.getByLabelText('State')
    expect(within(select).getAllByRole('option').map((option) => option.value)).toEqual([
      'saved',
      'planning',
    ])
  })

  it('invites a first save when nothing is in progress', () => {
    renderWithRouter(
      <ApplicationProgress applications={[]} states={[]} onChangeState={() => {}} onRemove={() => {}} />,
    )
    expect(screen.getByText('Start by saving an opportunity.')).toBeInTheDocument()
  })
})

describe('SavedScholarships', () => {
  const saved = {
    scholarship: {
      scholarship_id: 42,
      name: 'Rotterdam Scholarship',
      country: 'Netherlands',
      degree: 'Master',
      funding: 'Full',
      detail_url: '/scholarships/42',
      official_source_url: null,
      verification_status: 'active',
      verified: true,
      verification_display: 'Verified',
    },
    saved_at: '2026-05-01T00:00:00Z',
    is_in_matches: true,
    days_remaining: 14,
    readiness_label: 'Ready',
    application_state: null,
  }

  it('shows deadline, readiness and verification for each saved item', () => {
    renderWithRouter(<SavedScholarships saved={[saved]} onRemove={() => {}} />)

    expect(screen.getByText('14 days left')).toBeInTheDocument()
    expect(screen.getAllByText('Ready').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Verified').length).toBeGreaterThan(0)
    expect(screen.getByText('Not started')).toBeInTheDocument()
  })

  it('offers comparison only once there is something to compare', () => {
    const { rerender } = renderWithRouter(<SavedScholarships saved={[saved]} onRemove={() => {}} />)
    expect(screen.queryByRole('link', { name: 'Compare saved' })).not.toBeInTheDocument()

    rerender(
      <MemoryRouter>
        <SavedScholarships saved={[saved, { ...saved, scholarship: { ...saved.scholarship, scholarship_id: 43 } }]} onRemove={() => {}} />
      </MemoryRouter>,
    )
    expect(screen.getByRole('link', { name: 'Compare saved' })).toHaveAttribute('href', '/compare')
  })

  it('explains how to start a shortlist', () => {
    renderWithRouter(<SavedScholarships saved={[]} onRemove={() => {}} />)
    expect(screen.getByText('Save scholarships you are considering.')).toBeInTheDocument()
  })
})

describe('ProfileGaps', () => {
  it('links every gap to the page that closes it', () => {
    renderWithRouter(
      <ProfileGaps
        gaps={[
          {
            code: 'LANGUAGE_NOT_PROVIDED',
            message: 'Add your English test score.',
            category: 'MISSING_USER_INFORMATION',
            component: 'language',
            href: '/match',
            action_label: 'Complete your profile',
          },
        ]}
      />,
    )

    expect(screen.getByText('Add your English test score.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Complete your profile' })).toHaveAttribute('href', '/match')
  })

  it('does not present an empty section as a failure', () => {
    renderWithRouter(<ProfileGaps gaps={[]} />)
    expect(screen.getByText('Nothing missing')).toBeInTheDocument()
  })
})

describe('NextActions', () => {
  it('renders the server order unchanged', () => {
    renderWithRouter(
      <NextActions
        actions={[
          {
            code: 'improve_profile',
            title: 'Complete your profile',
            detail: 'Detail',
            priority: 10,
            href: '/match',
            action_label: 'Complete your profile',
          },
          {
            code: 'review_deadline_9',
            title: 'Decide on Something',
            detail: '9 days remain.',
            priority: 50,
            href: '/scholarships/9',
            action_label: 'Review',
          },
        ]}
      />,
    )

    const items = screen.getAllByRole('listitem')
    expect(items[0]).toHaveTextContent('Complete your profile')
    expect(items[1]).toHaveTextContent('Decide on Something')
  })

  it('renders nothing when there is nothing to do', () => {
    const { container } = renderWithRouter(<NextActions actions={[]} />)
    expect(container).toBeEmptyDOMElement()
  })
})