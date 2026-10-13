/**
 * The contextual "How to use this" entry.
 *
 * The behaviours that matter are the ones a reader on a feature page would
 * notice:
 *
 *   - it opens the right guide, matched from the route rather than a name someone
 *     has to remember to update;
 *   - it renders nothing on a route with no tutorial, rather than a button whose
 *     panel says the guide is missing;
 *   - a dismissal is remembered and can be reopened, and it is remembered per
 *     tutorial so hiding one does not hide them all;
 *   - it does not steal focus on mount, because a page that jumps somewhere when
 *     it loads is worse for a keyboard user than no help at all;
 *   - Escape closes it and returns focus to the trigger;
 *   - it cannot cover a primary action, because it renders in flow rather than as
 *     an overlay.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

import { HowToUse } from '../components/HowToUse.jsx'
import { TutorialLanguageProvider } from '../state/TutorialLanguageContext.jsx'

beforeEach(() => {
  window.localStorage.clear()
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

/** Mount the entry on a route, in a router and with the shared language. */
function renderHowTo(route) {
  return render(
    <MemoryRouter initialEntries={['/somewhere']}>
      <TutorialLanguageProvider>
        <HowToUse route={route} />
      </TutorialLanguageProvider>
    </MemoryRouter>,
  )
}

describe('presence', () => {
  it('renders on a route that has a tutorial', () => {
    renderHowTo('/scholarships')
    expect(screen.getByRole('button', { name: /How to use this/i })).toBeInTheDocument()
  })

  it('renders on a route reached through a parameter', () => {
    renderHowTo('/scholarships/:id')
    expect(screen.getByRole('button', { name: /How to use this/i })).toBeInTheDocument()
  })

  it('renders on an authenticated route', () => {
    renderHowTo('/applications')
    expect(screen.getByRole('button', { name: /How to use this/i })).toBeInTheDocument()
  })

  it('renders nothing on the disabled route', () => {
    // /consistency-review is behind the feature's own flag and deliberately has
    // no tutorial, so a button would open a panel saying the guide is missing.
    renderHowTo('/consistency-review')
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('renders nothing on a route with no tutorial at all', () => {
    renderHowTo('/no-such-route')
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})

describe('opening', () => {
  it('is closed on mount and does not steal focus', () => {
    renderHowTo('/scholarships')
    const trigger = screen.getByRole('button', { name: /How to use this/i })
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    // Nothing on the page is focused before the reader asks for anything.
    expect(document.activeElement).toBe(document.body)
  })

  it('opens the tutorial for that route', async () => {
    const user = userEvent.setup()
    renderHowTo('/scholarships')
    await user.click(screen.getByRole('button', { name: /How to use this/i }))
    // The prose is loaded on demand, so the guide arrives a tick after the panel.
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /What this feature does/i })).toBeInTheDocument()
    })
    // The guide is the catalogue one, not whichever happened to be first.
    expect(screen.getByText(/The catalogue\./i)).toBeInTheDocument()
  })

  it('opens the right tutorial for a different route', async () => {
    const user = userEvent.setup()
    renderHowTo('/statement')
    await user.click(screen.getByRole('button', { name: /How to use this/i }))
    expect(screen.getByText(/A guided workspace for writing your own statement/i)).toBeInTheDocument()
  })

  it('reports its expanded state to assistive tech', async () => {
    const user = userEvent.setup()
    renderHowTo('/plan')
    const trigger = screen.getByRole('button', { name: /How to use this/i })
    await user.click(trigger)
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    expect(trigger).toHaveAttribute('aria-controls')
  })

  it('closes again', async () => {
    const user = userEvent.setup()
    renderHowTo('/plan')
    const trigger = screen.getByRole('button', { name: /How to use this/i })
    await user.click(trigger)
    await user.click(screen.getByRole('button', { name: /Close/i }))
    expect(screen.queryByRole('heading', { name: /What this feature does/i })).not.toBeInTheDocument()
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
  })

  it('closes on Escape and returns focus to the trigger', async () => {
    const user = userEvent.setup()
    renderHowTo('/plan')
    const trigger = screen.getByRole('button', { name: /How to use this/i })
    await user.click(trigger)
    await user.keyboard('{Escape}')
    await waitFor(() => {
      expect(screen.queryByRole('heading', { name: /What this feature does/i })).not.toBeInTheDocument()
    })
    // Focus goes back to where it came from, not to the top of the document.
    expect(document.activeElement).toBe(trigger)
  })

  it('renders in flow, not as an overlay', async () => {
    const user = userEvent.setup()
    const { container } = renderHowTo('/plan')
    await user.click(screen.getByRole('button', { name: /How to use this/i }))
    const panel = container.querySelector('.ts-howto__panel')
    expect(panel).not.toBeNull()
    // A modal would set dialog semantics or a fixed position; neither is set, so
    // the page stays reachable underneath.
    expect(panel.getAttribute('role')).toBe('region')
    expect(container.querySelector('[role="dialog"]')).toBeNull()
  })
})

describe('dismissal', () => {
  it('remembers a dismissal and re-shows it on request', async () => {
    const user = userEvent.setup()
    renderHowTo('/plan')
    await user.click(screen.getByRole('button', { name: /How to use this/i }))
    await user.click(screen.getByRole('button', { name: /Hide this for now/i }))
    await user.click(screen.getByRole('button', { name: /Close/i }))

    // The stored state says dismissed, and the panel stays closed until asked.
    const stored = JSON.parse(window.localStorage.getItem('scholarzone.tutorials.v1'))
    expect(stored.dismissed.plan).toBe(true)

    await user.click(screen.getByRole('button', { name: /How to use this/i }))
    expect(screen.getByRole('heading', { name: /What this feature does/i })).toBeInTheDocument()
  })

  it('does not clear the dismissal by itself, so the reader keeps the choice', async () => {
    // An earlier version reopened the guide from the trigger, which overrode a
    // choice the reader had just made and wrote to storage on every open. The
    // guide's own control reopens it instead.
    const user = userEvent.setup()
    renderHowTo('/plan')
    const trigger = screen.getByRole('button', { name: /How to use this/i })
    await user.click(trigger)
    await user.click(screen.getByRole('button', { name: /Hide this for now/i }))
    await user.click(screen.getByRole('button', { name: /Close/i }))
    await user.click(trigger)

    const stored = JSON.parse(window.localStorage.getItem('scholarzone.tutorials.v1'))
    expect(stored.dismissed.plan).toBe(true)
  })

  it('reopens from inside the guide when the reader changes their mind', async () => {
    const user = userEvent.setup()
    renderHowTo('/plan')
    await user.click(screen.getByRole('button', { name: /How to use this/i }))
    await user.click(screen.getByRole('button', { name: /Hide this for now/i }))
    // Now the guide's own control offers to put it back.
    await user.click(screen.getByRole('button', { name: /Show the quick guide again/i }))
    const stored = JSON.parse(window.localStorage.getItem('scholarzone.tutorials.v1'))
    expect(stored.dismissed.plan).toBeUndefined()
  })

  it('dismisses one tutorial without dismissing another', async () => {
    const user = userEvent.setup()
    const first = renderHowTo('/plan')
    await user.click(screen.getByRole('button', { name: /How to use this/i }))
    await user.click(screen.getByRole('button', { name: /Hide this for now/i }))
    first.unmount()

    // A different page's guide is unaffected.
    renderHowTo('/match')
    const trigger = screen.getByRole('button', { name: /How to use this/i })
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    await user.click(trigger)
    expect(screen.getByRole('heading', { name: /What this feature does/i })).toBeInTheDocument()
  })
})

describe('language', () => {
  it('shows the guide in the shared language, set elsewhere', async () => {
    // The whole point of the shared provider: a choice stored by the Help Center
    // reaches a panel on another page. The preference is set before mounting
    // because the provider reads it once on mount.
    window.localStorage.setItem(
      'scholarzone.tutorials.v1',
      JSON.stringify({ schema: 'scholarzone.tutorials', version: 1, language: 'bn', dismissed: {} }),
    )
    const user = userEvent.setup()
    render(
      <MemoryRouter initialEntries={['/somewhere']}>
        <TutorialLanguageProvider>
          <HowToUse route="/plan" />
        </TutorialLanguageProvider>
      </MemoryRouter>,
    )
    // The trigger is labelled in the reader's language, which is the point: a
    // Bangla reader gets the Bangla label, not an English one.
    await user.click(screen.getByRole('button', { name: /কীভাবে ব্যবহার করবেন/i }))
    await waitFor(() => {
      expect(screen.getByText('এই ফিচার কী করে')).toBeInTheDocument()
    })
  })
})

describe('a refused write', () => {
  it('reports the failure rather than pretending the dismissal took', async () => {
    const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError')
    })
    try {
      const user = userEvent.setup()
      renderHowTo('/plan')
      await user.click(screen.getByRole('button', { name: /How to use this/i }))
      await user.click(screen.getByRole('button', { name: /Hide this for now/i }))
      await waitFor(() => {
        expect(screen.getByText(/This browser refused to store your preference/i)).toBeInTheDocument()
      })
    } finally {
      spy.mockRestore()
    }
  })
})
