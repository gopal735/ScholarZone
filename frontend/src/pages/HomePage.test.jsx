import { fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import HomePage from './HomePage'

vi.mock('../hooks/useScholarshipDirectory', () => ({
  useScholarshipDirectory: () => ({ scholarships: [], staticMode: true }),
}))

vi.mock('../hooks/useScholarshipStats', () => ({
  useScholarshipStats: () => ({ stats: null }),
}))

vi.mock('../hooks/useSavedScholarships', () => ({
  useSavedScholarships: () => ({ savedIds: [], toggleSaved: vi.fn() }),
}))

describe('HomePage goal finder defaults', () => {
  beforeEach(() => {
    localStorage.setItem('sz-goal', "I want a fully funded PhD in Japan. IELTS 7.")
  })

  it('opens with a blank goal and no extracted or manually selected criteria', () => {
    const { container } = render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('textbox', { name: /Describe your goal/ })).toHaveValue('')
    expect(container.querySelectorAll('.chip')).toHaveLength(0)
    expect(screen.getAllByRole('button', { name: 'Any', exact: true })).toHaveLength(2)
    expect(screen.getAllByRole('button', { name: 'Any', exact: true }).every((button) => button.getAttribute('aria-pressed') === 'true')).toBe(true)
    expect(screen.getByRole('combobox', { name: 'Country' })).toHaveValue('Any')
  })

  it('teaches students what to verify before saving a scholarship', () => {
    const { container } = render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    )

    const guide = screen.getByRole('complementary', {
      name: 'A stronger application starts with three checks.',
    })
    expect(within(guide).getAllByRole('listitem')).toHaveLength(3)
    expect(within(guide).getByText('Check your fit')).toBeInTheDocument()
    expect(within(guide).getByText('Read the funding')).toBeInTheDocument()
    expect(within(guide).getByText('Verify the deadline')).toBeInTheDocument()
    expect(container.querySelector('.mq')).not.toBeInTheDocument()

    const scholarshipCard = container.querySelector('.sc')
    expect(within(scholarshipCard).getByText('No filters applied')).toBeInTheDocument()
    expect(within(scholarshipCard).getByRole('link', { name: /check eligibility and deadline/i }))
      .toHaveAttribute('target', '_blank')
  })

  it('clears goal criteria and manual filters together', () => {
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('button', { name: /PhD in Japan/ }))
    expect(screen.getByRole('combobox', { name: 'Country' })).toHaveValue('Japan')
    expect(within(screen.getByRole('group', { name: 'Level' })).getByRole('button', { name: 'PhD' }))
      .toHaveAttribute('aria-pressed', 'true')

    fireEvent.click(screen.getByRole('button', { name: 'Clear', exact: true }))

    expect(screen.getByRole('textbox', { name: /Describe your goal/ })).toHaveValue('')
    expect(screen.getByRole('combobox', { name: 'Country' })).toHaveValue('Any')
    expect(within(screen.getByRole('group', { name: 'Level' })).getByRole('button', { name: 'Any' }))
      .toHaveAttribute('aria-pressed', 'true')
    expect(within(screen.getByRole('group', { name: 'Funding' })).getByRole('button', { name: 'Any' }))
      .toHaveAttribute('aria-pressed', 'true')
  })

  it('shows the bilingual application guide without a moving scholarship ticker', () => {
    const { container } = render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: 'A stronger application starts with three checks.' })).toBeInTheDocument()
    expect(screen.getByText('আপনার যোগ্যতা, লক্ষ্য ও সময়সীমার সঙ্গে মানানসই বৃত্তি খুঁজুন।')).toBeInTheDocument()
    expect(screen.getByText('Read the funding')).toBeInTheDocument()
    expect(container.querySelector('.mq')).not.toBeInTheDocument()
  })
})
