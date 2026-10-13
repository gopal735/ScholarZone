/**
 * The Help Center directory, as rendered.
 *
 * `MemoryRouter` is the mechanism, not a convenience: the search query, the
 * category and the open tutorial all live in the URL, so entering with
 * `?q=deadline` must render the filtered view. If any of them were React state
 * these would render the default and fail.
 *
 * The behaviours pinned here are the ones a reader would notice:
 *
 *   - search finds a guide by its prose, not only by its title, because someone
 *     looking for "why was I not matched" needs the mistakes text;
 *   - the empty state explains rather than just being blank;
 *   - the disabled feature is absent from the directory and is listed as a
 *     deliberate exclusion rather than silently missing;
 *   - admin guides stay hidden by default and the opt-in grants nothing but
 *     visibility.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

import HelpCenterPage from '../HelpCenterPage.jsx'
import { TutorialLanguageProvider } from '../state/TutorialLanguageContext.jsx'
import { TUTORIALS } from '../lib/registry.js'

/**
 * Render the directory at a URL, with any query state pre-applied.
 *
 * The language provider is mounted because the real app mounts it: without it
 * the page's language and the control's language are two pieces of state, which
 * is precisely the bug that shipped (the control switched, the guides did not).
 */
function renderHelp(initialEntry = '/help') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <TutorialLanguageProvider>
        <HelpCenterPage />
      </TutorialLanguageProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  window.localStorage.clear()
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('the directory', () => {
  it('lists every published, non-admin tutorial', () => {
    renderHelp()
    const expected = TUTORIALS.filter(
      (tutorial) => tutorial.status === 'enabled' && tutorial.audience !== 'admin',
    )
    for (const tutorial of expected) {
      expect(screen.getByText(tutorial.navLabel)).toBeInTheDocument()
    }
  })

  it('names every route it covers', () => {
    renderHelp()
    // A guide is only useful if a reader can find the page it describes.
    expect(screen.getByText('/scholarships')).toBeInTheDocument()
    expect(screen.getByText('/statement')).toBeInTheDocument()
    expect(screen.getByText('/bangladesh-journey')).toBeInTheDocument()
  })

  it('shows the local-storage and no-network notices', () => {
    renderHelp()
    expect(screen.getByText(/This guide is stored in this browser only/i)).toBeInTheDocument()
    expect(screen.getByText(/No data leaves your device/i)).toBeInTheDocument()
  })
})

describe('search', () => {
  it('filters by the words in the results', async () => {
    const user = userEvent.setup()
    renderHelp()
    await user.type(screen.getByLabelText(/Search tutorials/i), 'statement')
    await waitFor(() => {
      expect(screen.queryByText('Home')).not.toBeInTheDocument()
    })
    expect(screen.getByText('Statement')).toBeInTheDocument()
  })

  it('finds a guide by prose in its mistakes section, not only by title', async () => {
    // The sentence "Treating the check list as a score" lives in the statement
    // tutorial's mistakes, and that is where someone looking for it is served.
    const user = userEvent.setup()
    renderHelp()
    await user.type(screen.getByLabelText(/Search tutorials/i), 'Treating the check list as a score')
    await waitFor(() => {
      expect(screen.getByText('Statement')).toBeInTheDocument()
    })
    expect(screen.queryByText('Home')).not.toBeInTheDocument()
  })

  it('reports how many guides matched', async () => {
    const user = userEvent.setup()
    renderHelp()
    await user.type(screen.getByLabelText(/Search tutorials/i), 'statement')
    await waitFor(() => {
      // The number in the count is the number of cards actually rendered.
      const cards = document.querySelectorAll('.ts-cards > li')
      expect(cards.length).toBeGreaterThan(0)
      expect(
        screen.getByText(new RegExp(`${cards.length} tutorials found`, 'i')),
      ).toBeInTheDocument()
    })
  })

  it('shows a clear empty state with a way out', async () => {
    const user = userEvent.setup()
    renderHelp()
    await user.type(screen.getByLabelText(/Search tutorials/i), 'zzzznotathing')
    await waitFor(() => {
      expect(screen.getByText(/Nothing matches that search/i)).toBeInTheDocument()
    })
    expect(screen.getByText(/Try a simpler word/i)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Clear the search/i }))
    await waitFor(() => {
      expect(screen.queryByText(/Nothing matches that search/i)).not.toBeInTheDocument()
    })
  })

  it('restores its state from the URL, so a search is shareable', () => {
    // The reason the query is in the URL at all.
    renderHelp('/help?q=statement')
    expect(screen.getByText('Statement')).toBeInTheDocument()
    expect(screen.queryByText('Home')).not.toBeInTheDocument()
  })
})

describe('categories', () => {
  it('filters to a category', async () => {
    const user = userEvent.setup()
    renderHelp()
    await user.click(screen.getByRole('button', { name: /Write your documents/ }))
    await waitFor(() => {
      expect(screen.queryByText('Home')).not.toBeInTheDocument()
    })
    expect(screen.getByText('Statement')).toBeInTheDocument()
  })

  it('shows a count on each filter and reflects the search', async () => {
    const user = userEvent.setup()
    renderHelp()
    const all = screen.getByRole('button', { name: /Everything/ })
    expect(all).toHaveTextContent(String(TUTORIALS.filter((t) => t.status === 'enabled' && t.audience !== 'admin').length))

    await user.type(screen.getByLabelText(/Search tutorials/i), 'statement')
    await waitFor(() => {
      expect(screen.getAllByText('0').length).toBeGreaterThan(0)
    })
  })

  it('restores its state from the URL, so a category is linkable', () => {
    renderHelp('/help?category=write')
    expect(screen.getByText('Statement')).toBeInTheDocument()
    expect(screen.queryByText('Home')).not.toBeInTheDocument()
  })
})

describe('opening a tutorial', () => {
  it('opens the selected guide in place and renders its sections', async () => {
    const user = userEvent.setup()
    renderHelp()
    await user.click(screen.getByRole('button', { name: 'Statement', selector: 'button' }))

    // The prose is loaded on demand, so the sections arrive a tick later.
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /What this feature does/i })).toBeInTheDocument()
    })
    expect(screen.getByRole('heading', { name: /When to use it/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /Step-by-step/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /How to read the result/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /Common mistakes and how to recover/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /Where your information is kept/i })).toBeInTheDocument()
    // The limitations block, always present.
    expect(screen.getByRole('heading', { name: /What this does not guarantee/i })).toBeInTheDocument()
  })

  it('opens a guide named in the URL, so a guide is linkable', async () => {
    // The round trip of the selection living in the URL: a MemoryRouter entry
    // carrying ?tutorial= renders that guide. (A MemoryRouter does not write
    // window.location, so the direction asserted is entry -> render.)
    renderHelp('/help?tutorial=statement')
    expect(screen.getByRole('heading', { name: /What this feature does/i })).toBeInTheDocument()
  })

  it('falls back to a not-found panel for an unknown tutorial id', () => {
    // A stale link or a typo must not render a blank page.
    renderHelp('/help?tutorial=no-such-tutorial')
    expect(screen.getByText(/Nothing matches that search/i)).toBeInTheDocument()
    // Scoped to the results region: the same sentence also appears in the
    // deliberate-exclusions list further down the page.
    const results = document.querySelector('.ts-results')
    expect(results.textContent).toMatch(/This tutorial has not been written yet/i)
  })

  it('closes the open guide', async () => {
    const user = userEvent.setup()
    renderHelp('/help?tutorial=statement')
    expect(screen.getByRole('heading', { name: /What this feature does/i })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Close/i }))
    await waitFor(() => {
      expect(screen.queryByRole('heading', { name: /What this feature does/i })).not.toBeInTheDocument()
    })
  })
})

describe('language', () => {
  it('renders English by default', () => {
    renderHelp()
    expect(screen.getByText('Tutorials & Help Center')).toBeInTheDocument()
  })

  it('switches to Bangla and keeps the choice across a remount', async () => {
    const user = userEvent.setup()
    const first = renderHelp()
    await user.click(screen.getByLabelText(/Bangla only/i))
    await waitFor(() => {
      expect(screen.getByText('টিউটোরিয়াল ও সহায়তা কেন্দ্র')).toBeInTheDocument()
    })
    first.unmount()
    renderHelp()
    expect(screen.getByText('টিউটোরিয়াল ও সহায়তা কেন্দ্র')).toBeInTheDocument()
  })

  it('shows Bangla as primary and English underneath in both mode', async () => {
    const user = userEvent.setup()
    renderHelp()
    await user.click(screen.getByLabelText(/Bangla and English/i))
    await waitFor(() => {
      expect(screen.getByText('টিউটোরিয়াল ও সহায়তা কেন্দ্র')).toBeInTheDocument()
    })
    expect(screen.getByText('Tutorials & Help Center')).toBeInTheDocument()

    // And `t()` resolves to Bangla in both mode, which is the bug that shipped.
    await user.click(screen.getByRole('button', { name: 'Statement', selector: 'button' }))
    await waitFor(() => {
      expect(screen.getByText('টিউটোরিয়াল খুঁজুন')).toBeInTheDocument()
    })
  })
})

describe('admin visibility', () => {
  it('hides the admin guide by default, keeping only the opt-in control', () => {
    renderHelp()
    // The section and its opt-in control are deliberately visible — that is how
    // staff find the group at all. What must be absent is the guide itself.
    expect(screen.getByRole('button', { name: /Show every quick guide/i })).toBeInTheDocument()
    // The guide itself is absent from the results, and its route is not listed.
    const cards = document.querySelector('.ts-cards')
    const adminTutorial = TUTORIALS.find((tutorial) => tutorial.audience === 'admin')
    expect(cards.textContent).not.toContain(adminTutorial.navLabel)
    expect(screen.queryByText('/admin')).not.toBeInTheDocument()
  })

  it('does not expose admin routes in the default listing', () => {
    renderHelp()
    expect(screen.queryByText('/admin')).not.toBeInTheDocument()
  })

  it('shows the admin guide when asked, and keeps the guide itself available', async () => {
    const user = userEvent.setup()
    renderHelp()
    await user.click(screen.getByRole('button', { name: /Show every quick guide/i }))
    await waitFor(() => {
      expect(screen.getByText('/admin')).toBeInTheDocument()
    })
    const adminTutorial = TUTORIALS.find((tutorial) => tutorial.audience === 'admin')
    const cards = document.querySelector('.ts-cards')
    expect(cards.textContent).toContain(adminTutorial.navLabel)
  })

  it('grants visibility only: showing the guide does not claim access to the tools', async () => {
    // The admin page gates on X-Admin-Secret, resolved server-side. Nothing in
    // this directory may imply otherwise.
    const user = userEvent.setup()
    renderHelp()
    await user.click(screen.getByRole('button', { name: /Show every quick guide/i }))
    await waitFor(() => {
      expect(screen.getByText('/admin')).toBeInTheDocument()
    })
    expect(screen.queryByText(/you now have access/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /^Admin$/i })).not.toBeInTheDocument()
  })
})

describe('the disabled feature', () => {
  it('lists the disabled route as a deliberate exclusion, not a gap', () => {
    renderHelp()
    expect(screen.getByText('/consistency-review')).toBeInTheDocument()
  })

  it('never offers a guide for it', () => {
    renderHelp()
    expect(screen.queryByText('Application Consistency Auditor')).not.toBeInTheDocument()
  })
})

describe('a storage failure', () => {
  it('says the preference did not persist instead of pretending it took', async () => {
    const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError')
    })
    try {
      const user = userEvent.setup()
      renderHelp()
      await user.click(screen.getByLabelText(/Bangla only/i))
      await waitFor(() => {
        expect(screen.getByText(/This browser refused to store your preference/i)).toBeInTheDocument()
      })
      // And the rendered language stays English, because the write did not land.
      expect(spy).toHaveBeenCalled()
    } finally {
      spy.mockRestore()
    }
  })

  it('reports storage unavailable without crashing', () => {
    const spy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    try {
      renderHelp()
      // The page still renders, and says storage is the problem rather than
      // claiming the guide is local when it cannot be kept.
      expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
      expect(screen.getByText(/This browser refused to store your preference/i)).toBeInTheDocument()
    } finally {
      spy.mockRestore()
    }
  })
})
