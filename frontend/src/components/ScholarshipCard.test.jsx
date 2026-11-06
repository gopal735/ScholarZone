import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import ScholarshipCard from './ScholarshipCard'

vi.mock('./ScholarshipImage', () => ({ default: () => null }))
vi.mock('./ScholarshipActions', () => ({ default: () => null }))
vi.mock('./SupervisorCta', () => ({ default: () => null }))
vi.mock('./LifecycleBadge', () => ({ default: () => null }))

const scholarships = [
  {
    id: 'ready',
    title: 'Ready Scholarship',
    country: 'Germany',
    degree: "Master's",
    funding: 'Fully Funded',
    deadline: 'August 1, 2028',
    deadline_date: '2028-08-01',
    deadline_precision: 'exact',
    status: 'open',
    verification_status: 'active',
    eligibility_summary: "Applicants must hold a bachelor's degree.",
  },
  {
    id: 'review',
    title: 'Scholarship to Review',
    country: 'Japan',
    degree: 'PhD',
    funding: 'Stipend',
    status: 'open',
    verification_status: 'needs_review',
  },
]

describe('ScholarshipCard application checks', () => {
  it('shows factual checks instead of a generic fit score', () => {
    render(
      <MemoryRouter>
        {scholarships.map((scholarship) => (
          <ScholarshipCard key={scholarship.id} scholarship={scholarship} />
        ))}
      </MemoryRouter>,
    )

    const [readyChecks, reviewChecks] = screen.getAllByLabelText('Application checks')

    expect(within(readyChecks).getByText('Eligibility details').nextElementSibling).toHaveTextContent('Listed')
    expect(within(readyChecks).getByText('Exact deadline').nextElementSibling).toHaveTextContent('Listed')
    expect(within(readyChecks).getByText('Official verification').nextElementSibling).toHaveTextContent('Verified')
    expect(within(reviewChecks).getByText('Eligibility details').nextElementSibling).toHaveTextContent('Check criteria')
    expect(within(reviewChecks).getByText('Exact deadline').nextElementSibling).toHaveTextContent('Confirm date')
    expect(within(reviewChecks).getByText('Official verification').nextElementSibling).toHaveTextContent('Review source')
    expect(screen.queryByText(/Fit \d\/\d/)).not.toBeInTheDocument()
  })
})
