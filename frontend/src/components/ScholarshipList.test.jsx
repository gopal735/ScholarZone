import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import ScholarshipList from './ScholarshipList'

vi.mock('./ScholarshipCard', () => ({
  default: ({ scholarship }) => (
    <article className="scholarship-card">
      <div className="scholarship-card__heading">
        <h2>{scholarship.title}</h2>
      </div>
    </article>
  ),
}))

const scholarships = [
  {
    id: 1,
    title: 'Alpha Grant',
    country: 'Germany',
    degree: "Master's",
    funding: 'Fully Funded',
    deadline: 'December 2028',
    deadline_date: '2028-12',
    deadline_precision: 'month',
    status: 'open',
    verification_status: 'active',
    created_at: '2026-01-01T00:00:00',
    updated_at: '2026-04-01T00:00:00',
  },
  {
    id: 2,
    title: 'Beta Grant',
    country: 'Japan',
    degree: 'PhD',
    funding: 'Stipend',
    deadline: '2028-04-15',
    deadline_date: '2028-04-15',
    deadline_precision: 'exact',
    status: 'open',
    verification_status: 'active',
    created_at: '2026-04-01T00:00:00',
    updated_at: '2026-02-01T00:00:00',
  },
  {
    id: 3,
    title: 'Gamma Grant',
    country: 'United States',
    degree: "Bachelor's",
    funding: 'Partially Funded',
    deadline: '2028-01-31',
    deadline_date: '2028-01-31',
    deadline_precision: 'exact',
    status: 'open',
    verification_status: 'active',
    created_at: '2026-03-01T00:00:00',
    updated_at: '2026-03-01T00:00:00',
  },
  {
    id: 4,
    title: 'Delta Grant',
    country: 'United Kingdom',
    degree: "Master's",
    funding: 'Tuition Fee Waiver',
    deadline: '2000-01-01',
    deadline_date: '2000-01-01',
    deadline_precision: 'exact',
    status: 'open',
    verification_status: 'active',
    created_at: '2026-02-01T00:00:00',
    updated_at: '2026-01-01T00:00:00',
  },
  {
    id: 5,
    title: 'Epsilon Grant',
    country: 'Canada',
    degree: 'Postgraduate',
    funding: 'Research Funding',
    deadline: '',
    status: 'open',
    verification_status: 'needs_review',
    created_at: '2026-05-01T00:00:00',
    updated_at: '2026-05-01T00:00:00',
  },
]

describe('ScholarshipList filters and sorting', () => {
  it('starts with an empty search and unfiltered controls, with deadline months from data', () => {
    const { container } = render(<ScholarshipList items={scholarships} />)

    expect(screen.getByRole('searchbox', { name: 'Search scholarships by name' })).toHaveValue('')
    expect(screen.getByLabelText('Country')).toHaveValue('All')
    expect(screen.getByLabelText('Degree')).toHaveValue('All')
    expect(screen.getByLabelText('Funding')).toHaveValue('All')
    // Deadline month dropdown now only shows months present in the data (Jan, Apr, Dec) + All
    expect(screen.getByLabelText('Deadline month').querySelectorAll('option')).toHaveLength(4)
    expect(screen.getByLabelText('Deadline month')).toHaveValue('All')
    expect(screen.getByLabelText('Status')).toHaveValue('All')
    expect(screen.getByRole('button', { name: 'All Lifecycles' })).toHaveAttribute('aria-pressed', 'true')
    expect(container.querySelector('.filter-sort')).not.toHaveClass('is-active')
    expect(container.querySelectorAll('.scholarship-card')).toHaveLength(5)
  })

  it('applies search, every dropdown filter and lifecycle filters, and reset restores all records', () => {
    const { container } = render(<ScholarshipList items={scholarships} />)
    const resultCount = () => Number(container.querySelector('.scholarship-list__summary strong').textContent)

    fireEvent.change(screen.getByRole('searchbox', { name: 'Search scholarships by name' }), { target: { value: 'Gamma' } })
    expect(resultCount()).toBe(1)
    fireEvent.click(screen.getByRole('button', { name: 'Clear scholarship search' }))

    fireEvent.change(screen.getByLabelText('Country'), { target: { value: 'Germany' } })
    expect(resultCount()).toBe(1)
    fireEvent.change(screen.getByLabelText('Country'), { target: { value: 'All' } })

    fireEvent.change(screen.getByLabelText('Degree'), { target: { value: 'PhD' } })
    expect(resultCount()).toBe(1)
    fireEvent.change(screen.getByLabelText('Degree'), { target: { value: 'All' } })

    fireEvent.change(screen.getByLabelText('Funding'), { target: { value: 'Stipend' } })
    expect(resultCount()).toBe(1)
    fireEvent.change(screen.getByLabelText('Funding'), { target: { value: 'All' } })

    fireEvent.change(screen.getByLabelText('Deadline month'), { target: { value: '12' } })
    expect(resultCount()).toBe(1)
    fireEvent.change(screen.getByLabelText('Deadline month'), { target: { value: 'All' } })

    // Status filter no longer has 'closed' option (excluded from public catalogue)
    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'open' } })
    // Only 3 records have lifecycle "open" (Alpha, Beta, Gamma)
    // Delta has past deadline -> "closed", Epsilon has no deadline -> "unknown"
    expect(resultCount()).toBe(3)
    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'All' } })

    fireEvent.click(screen.getByRole('button', { name: 'Check deadline' }))
    expect(resultCount()).toBe(1)
    fireEvent.click(screen.getByRole('button', { name: 'Reset all' }))
    expect(resultCount()).toBe(5)
  })

  it('sorts recently added by creation date and names alphabetically', () => {
    const { container } = render(<ScholarshipList items={scholarships} />)
    const cardTitles = () => Array.from(
      container.querySelectorAll('.scholarship-card__heading h2'),
      (heading) => heading.textContent,
    )
    const sort = screen.getByLabelText('Sort by')

    fireEvent.change(sort, { target: { value: 'recently-added' } })
    expect(cardTitles()[0]).toBe('Epsilon Grant')

    fireEvent.change(sort, { target: { value: 'name-asc' } })
    expect(cardTitles()[0]).toBe('Alpha Grant')
    expect(cardTitles()[2]).toBe('Delta Grant')
  })
})