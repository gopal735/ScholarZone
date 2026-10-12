/**
 * The statement builder page, through the DOM.
 *
 * These assertions are about behaviour a student would notice, not about
 * implementation: that typing persists, that a reload keeps the draft, that the
 * word limit is only called authoritative with a source, that a claim must be
 * answered before the export stops complaining, and that the privacy labels are
 * on the page rather than only in the code's comments.
 *
 * The page reads localStorage directly, so the tests drive it the way a browser
 * would: render, type, unmount, render again. Nothing is mocked except the
 * download, which jsdom cannot perform.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

import SopBuilderPage from './SopBuilderPage'

const KEY = 'scholarzone.sop-builder.v1'

/** Render the page with the router context a route component receives. */
function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/statement']}>
      <SopBuilderPage />
    </MemoryRouter>,
  )
}

/** Type into a labelled field. */
async function typeIn(user, label, value) {
  const field = screen.getByLabelText(label)
  await user.clear(field)
  if (value) {
    await user.type(field, value)
  }
  return field
}

beforeEach(() => {
  window.localStorage.clear()
  vi.restoreAllMocks()
})

describe('the page opens with nothing invented', () => {
  it('shows the section guidance and an empty editor', () => {
    renderPage()
    expect(screen.getByRole('heading', { level: 1, name: /build your statement of purpose/i })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: /sections of your statement/i })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: /your opening and motivation/i })).toHaveValue('')
  })

  it('says the data is in this browser, with no server and no sync', () => {
    renderPage()
    // Two notices by design: one at the top, one beside the export controls.
    // The assertion is that both say the same thing, because a student who
    // scrolls to the buttons must not have to scroll back to find out where
    // their data is.
    const notices = screen.getAllByText(/There is no account, no server and no sync for this workspace/i)
    expect(notices).toHaveLength(2)
    expect(notices[0].closest('.sop-page')).toBeTruthy()
  })

  it('states that the review is deterministic and predicts nothing', () => {
    renderPage()
    expect(screen.getByText(/These are deterministic checks run over your own words/i)).toBeInTheDocument()
    expect(screen.getByText(/no check here predicts an admission/i)).toBeInTheDocument()
  })

  it('starts with no claims outstanding and no approval recorded', () => {
    renderPage()
    // queryByText, not getByText: an absent claim must be absent rather than
    // raising, which is the whole point of the assertion.
    expect(screen.queryByText('Needs your answer')).not.toBeInTheDocument()
    const approval = screen.getByRole('checkbox', { name: /I have read this whole draft/i })
    expect(approval).not.toBeChecked()
  })
})

describe('persistence', () => {
  it('keeps a section across a reload of the component', async () => {
    const user = userEvent.setup()
    const first = renderPage()
    await typeIn(user, /your opening and motivation/i, 'A question about rivers led me here.')
    // Unmounting and re-mounting is what a route change does; the store is the
    // only thing that survives it.
    first.unmount()
    renderPage()
    expect(screen.getByRole('textbox', { name: /your opening and motivation/i })).toHaveValue(
      'A question about rivers led me here.',
    )
  })

  it('writes the section into localStorage under the namespaced key', async () => {
    const user = userEvent.setup()
    renderPage()
    await typeIn(user, /your opening and motivation/i, 'A question about rivers.')
    const stored = JSON.parse(window.localStorage.getItem(KEY))
    expect(stored.sections.opening.text).toBe('A question about rivers.')
    expect(stored.device_local).toBe(true)
  })

  it('keeps a multi-word institution as it was typed, spaces included', async () => {
    // The regression guard for the bug where every keystroke wrote a trimmed
    // value, which made "University of Bristol" impossible to type.
    const user = userEvent.setup()
    renderPage()
    await typeIn(user, /^Institution$/, 'University of Bristol')
    expect(screen.getByLabelText(/^Institution$/)).toHaveValue('University of Bristol')
    const stored = JSON.parse(window.localStorage.getItem(KEY))
    expect(stored.context.institution).toBe('University of Bristol')
  })

  it('keeps the context, background and approval across a re-render', async () => {
    const user = userEvent.setup()
    const first = renderPage()

    await typeIn(user, /^Institution$/, 'University of Bristol')
    await typeIn(user, /Word limit \(optional\)/i, '1000')
    await typeIn(user, /Where the limit comes from/i, 'the provider guidelines page')
    await typeIn(user, /Academic background/i, 'BSc Civil Engineering, 2023.')

    first.unmount()
    renderPage()

    expect(screen.getByLabelText(/^Institution$/)).toHaveValue('University of Bristol')
    expect(screen.getByLabelText(/Word limit \(optional\)/i)).toHaveValue(1000)
    expect(screen.getByLabelText(/Where the limit comes from/i)).toHaveValue('the provider guidelines page')
    expect(screen.getByLabelText(/Academic background/i)).toHaveValue('BSc Civil Engineering, 2023.')
  })

  it('records an approval, and clears it when unchecked', async () => {
    const user = userEvent.setup()
    renderPage()
    const approval = screen.getByRole('checkbox', { name: /I have read this whole draft/i })
    await user.click(approval)
    expect(JSON.parse(window.localStorage.getItem(KEY)).approval.confirmed).toBe(true)

    await user.click(approval)
    expect(JSON.parse(window.localStorage.getItem(KEY)).approval).toBeNull()
  })
})

describe('the word limit is only authoritative with a source', () => {
  it('refuses to call a sourceless limit official', async () => {
    const user = userEvent.setup()
    renderPage()
    await typeIn(user, /Word limit \(optional\)/i, '500')
    expect(
      screen.getByText(/A limit of 500 is recorded but no source is/i),
    ).toBeInTheDocument()
    expect(
      screen.queryByText(/is recorded with a source/i),
    ).not.toBeInTheDocument()
  })

  it('reports the position against a sourced limit', async () => {
    const user = userEvent.setup()
    renderPage()
    await typeIn(user, /Word limit \(optional\)/i, '10')
    await typeIn(user, /Where the limit comes from/i, 'the provider guidelines page')
    await typeIn(user, /your opening and motivation/i, 'One two three four five six seven eight nine ten.')
    expect(screen.getByText(/^Against your recorded limit of 10/)).toBeInTheDocument()
  })
})

describe('editing across sections', () => {
  it('moves to the next section without losing what was typed', async () => {
    const user = userEvent.setup()
    renderPage()
    await typeIn(user, /your opening and motivation/i, 'Opening words.')

    await user.click(screen.getByRole('button', { name: /Academic preparation/ }))

    const editor = screen.getByRole('textbox', { name: /your academic preparation/i })
    expect(editor).toHaveValue('')
    await typeIn(user, /your academic preparation/i, 'Academic words.')

    await user.click(screen.getByRole('button', { name: /Opening and motivation/ }))
    expect(screen.getByRole('textbox', { name: /your opening and motivation/i })).toHaveValue('Opening words.')
    // queryByRole, not getByRole: asserting absence with the throwing form of
    // the query fails for the wrong reason.
    expect(screen.queryByRole('textbox', { name: /your academic preparation/i })).toBeNull()
  })

  it('shows the section guidance, its questions and its improvement tips', async () => {
    renderPage()
    // The writing school, not just an editor.
    expect(screen.getByRole('heading', { name: 'What to write' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Why it matters' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'How to improve it' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /Questions to answer before you write/ })).toBeInTheDocument()
  })

  it('counts words as they are typed', async () => {
    const user = userEvent.setup()
    renderPage()
    await typeIn(user, /your opening and motivation/i, 'one two three')
    expect(screen.getByText('3 words')).toBeInTheDocument()
  })
})

describe('the review', () => {
  it('reports an absent section rather than calling it weak', async () => {
    renderPage()
    expect(screen.getByText(/Opening and motivation: no text yet/i)).toBeInTheDocument()
  })

  it('reports an institution the draft never names', async () => {
    const user = userEvent.setup()
    renderPage()
    await typeIn(user, /^Institution$/, 'University of Bristol')
    expect(screen.getByText(/Your institution is never named/i)).toBeInTheDocument()
  })

  it('reports a claim the student must substantiate, with the ask attached', async () => {
    const user = userEvent.setup()
    renderPage()
    await typeIn(user, /your opening and motivation/i, 'I ranked first in my class of 412.')
    // "ranked first" and "first in my class" both match, so more than one claim
    // is expected; the assertion is that at least one is open and each carries
    // its ask.
    expect(screen.getAllByText('Needs your answer').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText(/states a measurable fact about you/i).length).toBeGreaterThanOrEqual(1)
  })
})

describe('the substantiation flow', () => {
  /** The evidence textareas and buttons, one per detected claim. */
  function claimControls() {
    return {
      evidence: screen.getAllByLabelText(/Your own evidence for this claim/i),
      confirm: screen.getAllByRole('button', { name: /Confirm with this evidence/i }),
      remove: screen.getAllByRole('button', { name: /I will remove this claim from the draft/i }),
    }
  }

  it('records the student evidence and stops reporting the claim as open', async () => {
    const user = userEvent.setup()
    renderPage()
    await typeIn(user, /your opening and motivation/i, 'I ranked first in my class of 412.')

    const { evidence, confirm } = claimControls()
    await user.type(evidence[0], 'My transcript, awarded May 2024.')
    await user.click(confirm[0])

    const stored = JSON.parse(window.localStorage.getItem(KEY))
    const records = Object.values(stored.substantiation)
    expect(records.some((entry) => entry.status === 'confirmed')).toBe(true)
    expect(records.some((entry) => entry.evidence === 'My transcript, awarded May 2024.')).toBe(true)
    expect(screen.getByText(/confirmed this with your own evidence/i)).toBeInTheDocument()
  })

  it('records a removal, and says it does not edit the draft', async () => {
    const user = userEvent.setup()
    renderPage()
    await typeIn(user, /your opening and motivation/i, 'I ranked first in my class of 412.')

    const { remove } = claimControls()
    await user.click(remove[0])

    // The claim is still in the student's text: the builder does not rewrite.
    expect(screen.getByRole('textbox', { name: /your opening and motivation/i })).toHaveValue(
      'I ranked first in my class of 412.',
    )
    expect(screen.getByText(/Marked for removal/i)).toBeInTheDocument()
  })

  it('keeps a claim outstanding when it is confirmed with no evidence', async () => {
    const user = userEvent.setup()
    renderPage()
    await typeIn(user, /your opening and motivation/i, 'I ranked first in my class of 412.')

    const { confirm } = claimControls()
    await user.click(confirm[0])

    expect(screen.getByText(/You confirmed this, but have not given your evidence/i)).toBeInTheDocument()
  })
})

describe('export', () => {
  /** jsdom cannot download, so the click is stubbed and the text is captured. */
  function captureDownload() {
    const captured = {}
    const originalCreate = document.createElement.bind(document)
    const create = vi.spyOn(document, 'createElement').mockImplementation((tag) => {
      const node = originalCreate(tag)
      if (tag === 'a') {
        node.click = () => {
          captured.href = node.href
          captured.download = node.download
        }
      }
      return node
    })
    const originalURL = URL.createObjectURL
    URL.createObjectURL = vi.fn((blob) => {
      captured.blob = blob
      return 'blob:mock'
    })
    URL.revokeObjectURL = vi.fn()
    return { captured, restore: () => { create.mockRestore(); URL.createObjectURL = originalURL } }
  }

  it('downloads a Markdown file whose name comes from the context', async () => {
    const user = userEvent.setup()
    const { captured, restore } = captureDownload()
    try {
      renderPage()
      await typeIn(user, /^Institution$/, 'University of Bristol')
      await typeIn(user, /^Programme$/, 'Hydrology')
      await user.click(screen.getByRole('button', { name: /Export as Markdown/i }))

      expect(captured.download).toMatch(/^sop-builder-university-of-bristol-hydrology-.*\.md$/)
      const text = await captured.blob.text()
      expect(text).toContain('# ScholarZone statement draft')
      // The declarations travel inside the file.
      expect(text).toMatch(/Nothing in this document predicts an admission/)
    } finally {
      restore()
    }
  })

  it('downloads a plain-text file carrying the student text', async () => {
    const user = userEvent.setup()
    const { captured, restore } = captureDownload()
    try {
      renderPage()
      await typeIn(user, /your opening and motivation/i, 'A question about rivers led me here.')
      await user.click(screen.getByRole('button', { name: /Export as plain text/i }))

      expect(captured.download).toMatch(/\.txt$/)
      const text = await captured.blob.text()
      expect(text).toContain('A question about rivers led me here.')
      expect(text).toContain('SCHOLARZONE STATEMENT DRAFT')
      expect(text).toMatch(/ScholarZone did not generate, rewrite or approve/)
    } finally {
      restore()
    }
  })

  it('shows a preview of the export on the page', () => {
    renderPage()
    expect(screen.getByLabelText(/Preview of the plain-text export/i)).toBeInTheDocument()
  })
})

describe('rejecting unsupported input', () => {
  it('rejects an import that is not an export, with a reason', async () => {
    const user = userEvent.setup()
    renderPage()
    const input = screen.getByLabelText(/Restore a draft you exported earlier/i)

    await user.upload(
      input,
      new File(['{"schema":"something.else","version":1,"draft":{}}'], 'plan.json', { type: 'application/json' }),
    )

    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent(/This file does not declare itself/i)
    })
  })

  it('rejects a file that cannot be parsed as JSON', async () => {
    const user = userEvent.setup()
    renderPage()
    const input = screen.getByLabelText(/Restore a draft you exported earlier/i)

    // Named .json so it passes the input's accept filter but is not JSON.
    await user.upload(input, new File(['not json at all'], 'notes.json', { type: 'application/json' }))

    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent(/could not be read as JSON/i)
    })
  })

  it('rejects an unsupported export version rather than guessing at its shape', async () => {
    const user = userEvent.setup()
    renderPage()
    const input = screen.getByLabelText(/Restore a draft you exported earlier/i)

    await user.upload(
      input,
      new File(
        [JSON.stringify({ schema: 'scholarzone.sop-builder', version: 99, draft: {} })],
        'old.json',
        { type: 'application/json' },
      ),
    )

    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent(/Unsupported SOP Builder export version 99/)
    })
  })

  it('restores a draft it exported, and says so', async () => {
    const user = userEvent.setup()

    // Export the payload the app itself would write, then clear and restore.
    const first = renderPage()
    await typeIn(user, /your opening and motivation/i, 'A question about rivers led me here.')
    const stored = JSON.parse(window.localStorage.getItem(KEY))
    first.unmount()

    window.localStorage.clear()
    renderPage()
    expect(screen.getByRole('textbox', { name: /your opening and motivation/i })).toHaveValue('')

    await user.upload(
      screen.getByLabelText(/Restore a draft you exported earlier/i),
      new File(
        [JSON.stringify({ schema: 'scholarzone.sop-builder', version: 1, device_local: true, draft: stored })],
        'draft.json',
        { type: 'application/json' },
      ),
    )

    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent(/Draft restored from the file/i)
    })
    expect(screen.getByRole('textbox', { name: /your opening and motivation/i })).toHaveValue(
      'A question about rivers led me here.',
    )
  })
})

describe('erasing', () => {
  it('clears every section and the context, because there is no server copy', async () => {
    // The opposite of a half-erase: if the copy is only in this browser, then
    // erasing here has to be the whole of it, or the label was a lie.
    const user = userEvent.setup()
    renderPage()
    await typeIn(user, /^Institution$/, 'University of Bristol')
    await typeIn(user, /your opening and motivation/i, 'Some words.')

    await user.click(screen.getByRole('button', { name: /Erase everything from this browser/i }))

    const stored = JSON.parse(window.localStorage.getItem(KEY))
    expect(stored.sections.opening.text).toBe('')
    expect(stored.context.institution).toBe('')
    expect(screen.getByRole('status')).toHaveTextContent(/Erased from this browser/i)
  })

  it('offers a control that clears only the section text', async () => {
    const user = userEvent.setup()
    renderPage()
    await typeIn(user, /^Institution$/, 'University of Bristol')
    await typeIn(user, /your opening and motivation/i, 'Some words.')

    await user.click(screen.getByRole('button', { name: /Clear all section text/i }))

    const stored = JSON.parse(window.localStorage.getItem(KEY))
    expect(stored.sections.opening.text).toBe('')
    expect(stored.context.institution).toBe('University of Bristol')
  })
})

describe('a failed write is reported, not retried as success', () => {
  it('shows an error when storage refuses the write', async () => {
    const user = userEvent.setup()
    const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError')
    })
    try {
      renderPage()
      await typeIn(user, /your opening and motivation/i, 'text')
      await waitFor(() => {
        expect(screen.getByRole('status')).toHaveTextContent(/This browser would not store that text/i)
      })
    } finally {
      spy.mockRestore()
    }
  })
})
