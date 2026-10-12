/**
 * Regression tests for the rendering and layout defects found in the UI audit.
 *
 * Two kinds of test live here, because jsdom can only prove one of them:
 *
 * - Behaviour is rendered and asserted (error boundary, navigation badge, Match
 *   options retry, the pager's keys).
 * - Layout is proven the way this suite already proves it: by reading the
 *   stylesheet. A jsdom query has no viewport, so a media-query or track-sizing
 *   assertion there would be theatre. The declarations that fix each
 *   browser-verified defect are pinned instead.
 */

import { describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import Navigation from './Navigation.jsx'
import { RouteErrorBoundary } from './AppErrorBoundary.jsx'
import App from '../App.jsx'
import { CompareProvider } from '../context/CompareContext.jsx'
import { SavedScholarshipsProvider } from '../context/SavedScholarshipsContext.jsx'
import { AuthContext } from '../context/authContext'
import { ThemeProvider } from '../context/ThemeContext.jsx'

const read = (relative) => readFileSync(resolve(process.cwd(), relative), 'utf8')

/** `--space-N` tokens from the theme, so a padding can be read in pixels. */
const SPACE_TOKENS = (() => {
  const theme = read('src/theme.css')
  const tokens = {}
  const pattern = /--space-(\d+):\s*(\d+(?:\.\d+)?)px/g
  let match
  while ((match = pattern.exec(theme)) !== null) {
    tokens[`--space-${match[1]}`] = parseFloat(match[2])
  }
  return tokens
})()

/** `var(--space-N)` in a shorthand, in pixels. */
function spaceTokenValue(token) {
  const name = `--space-${token.replace(/[^0-9]/g, '')}`
  return SPACE_TOKENS[name]
}

/**
 * `@media` blocks removed, with braces balanced.
 *
 * A selector can legitimately appear in both the base layer and a media
 * block, so the base-layer lookup has to be able to see one without the other.
 */
function stripMediaBlocks(css) {
  let out = ''
  let index = 0
  while (index < css.length) {
    const at = css.indexOf('@media', index)
    if (at === -1) {
      out += css.slice(index)
      break
    }
    out += css.slice(index, at)
    let depth = 0
    let cursor = css.indexOf('{', at)
    while (cursor !== -1 && cursor < css.length) {
      if (css[cursor] === '{') {
        depth += 1
      } else if (css[cursor] === '}') {
        depth -= 1
        if (depth === 0) {
          cursor += 1
          break
        }
      }
      cursor += 1
    }
    index = cursor
  }
  return out
}

/**
 * Every rule in a stylesheet as `{ selector, body }`, with comments stripped so
 * a declaration inside a rule cannot be mistaken for the next selector.
 */
function rulesOf(css) {
  const normalised = css.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\r\n/g, '\n')
  const rules = []
  const pattern = /([^{}]+)\{([^{}]*)\}/g
  let match
  while ((match = pattern.exec(normalised)) !== null) {
    const selector = match[1].trim().replace(/\s+/g, ' ')
    if (selector === '' || selector.startsWith('@')) {
      continue
    }
    rules.push({ selector, body: match[2] })
  }
  return rules
}

/** The body of the single base-layer rule whose selector matches exactly. */
function ruleBody(css, selector) {
  const found = rulesOf(stripMediaBlocks(css)).filter((rule) => rule.selector === selector)
  expect(found.length, `expected exactly one rule for ${selector}`).toBe(1)
  return found[0].body
}

const PLAN_CSS = read('src/pages/PlanPage.css')
const LEDGER_CSS = read('src/Ledger.css')

/* ── Plan page: no element may widen the page ───────────────────────────── */

describe('plan rows cannot widen the page', () => {
  /**
   * Reproduced in the browser at 1440/1920/390 with the catalogue's longest
   * title (192 chars) and longest deadline (244 chars) seeded into plan
   * storage: the grid track grew to the rows' min-content and the document
   * scrolled sideways by roughly a thousand pixels.
   */
  it('lets the deadline label wrap instead of reserving its width', () => {
    const body = ruleBody(PLAN_CSS, '.plan-page__record-list li span, .plan-page__timeline ul li span')
    expect(body).toMatch(/white-space:\s*normal/)
    // A single unbroken token is the other way the same hole re-opens.
    expect(body).toMatch(/overflow-wrap:\s*anywhere/)
  })

  it('releases the grid item automatic minimum on every row model', () => {
    expect(ruleBody(PLAN_CSS, '.plan-page__record-list li, .plan-page__timeline ul li'))
      .toMatch(/min-width:\s*0/)
    expect(ruleBody(PLAN_CSS, '.plan-page__timeline > li')).toMatch(/min-width:\s*0/)
    expect(ruleBody(PLAN_CSS, '.plan-page__checklist')).toMatch(/min-width:\s*0/)
    expect(ruleBody(PLAN_CSS, '.plan-page__checklist-head h3')).toMatch(/min-width:\s*0/)
  })

  it('lets the award name in a checklist heading break', () => {
    expect(ruleBody(PLAN_CSS, '.plan-page__checklist-head h3')).toMatch(/overflow-wrap:\s*anywhere/)
  })

  it('keeps the file-import control from forcing the row wide', () => {
    // 331px of label plus an unshrinkable file input, on a ~298px line at
    // 390px: 13px past the viewport.
    expect(ruleBody(PLAN_CSS, '.plan-page__import')).toMatch(/flex-wrap:\s*wrap/)
    expect(ruleBody(PLAN_CSS, '.plan-page__import input')).toMatch(/min-width:\s*0/)
  })

  it('has no nowrap left on any plan-page rule', () => {
    const nowrap = rulesOf(PLAN_CSS).filter((rule) => /white-space:\s*nowrap/.test(rule.body))
    expect(nowrap.map((rule) => rule.selector)).toEqual([])
  })
})

/* ── Hero satellites and provenance pill ────────────────────────────────── */

describe('hero satellites cover media, never text', () => {
  const chipBody = (selector) => rulesOf(LEDGER_CSS)
    .filter((rule) => rule.selector === selector)
    .map((rule) => rule.body)
    .join(' ')

  /**
   * Reproduced at 1440/1280/1024: the deadline satellite crossed the card's
   * lower-left corner, so it sat on the card's own deadline row and on the
   * caption below; the funding satellite came down over the OFFICIAL pill.
   */
  it('anchors both satellites to the top edge, not the bottom', () => {
    expect(chipBody('.sz-hero__chip--deadline')).toMatch(/top:\s*-?\d+%/)
    expect(chipBody('.sz-hero__chip--deadline')).toMatch(/bottom:\s*auto/)
    expect(chipBody('.sz-hero__chip--funding')).toMatch(/top:\s*-?\d+%/)
  })

  it('caps each satellite so the pair cannot meet in the middle', () => {
    expect(chipBody('.sz-hero__chip--deadline')).toMatch(/max-width:\s*4[0-9]%/)
    expect(chipBody('.sz-hero__chip--funding')).toMatch(/max-width:\s*4[0-9]%/)
  })

  it('reserves space around the logo so the pill and satellites miss it', () => {
    const logo = ruleBody(
      LEDGER_CSS,
      ".sz-hero__showcase-card .scholarship-image[data-fit='contain'] .scholarship-image__img",
    )
    const padding = /padding:\s*([^;]+);/.exec(logo)
    expect(padding, 'the hero logo rule must set padding').not.toBeNull()
    const [top, , bottom] = padding[1].trim().split(/\s+/)
    const topPx = spaceTokenValue(top)
    const bottomPx = spaceTokenValue(bottom)
    // A ~96px top clears a 104px satellite; ~56px at the bottom clears the
    // 24px provenance pill that anchors in the band's lower corner.
    expect(topPx, `top padding ${top}`).toBeGreaterThanOrEqual(96)
    expect(bottomPx, `bottom padding ${bottom}`).toBeGreaterThanOrEqual(48)
  })
})

/* ── Route failures keep the shell up ───────────────────────────────────── */

describe('route error boundary keeps the page usable', () => {
  it('replaces only the failing section, and retries in place', async () => {
    const user = userEvent.setup()
    let shouldThrow = true

    function Flaky() {
      if (shouldThrow) {
        throw new Error('boom')
      }
      return <p>section recovered</p>
    }

    render(
      <RouteErrorBoundary>
        <Flaky />
      </RouteErrorBoundary>,
    )

    // The boundary's own recovery state, not a blank node.
    expect(screen.getByRole('alert')).toHaveTextContent(/could not be displayed/i)

    // The route renders again once the failure is addressed, without a page
    // reload: the retry bumps the key, which React treats as new content.
    shouldThrow = false
    await user.click(screen.getByRole('button', { name: /try again/i }))
    expect(screen.getByText('section recovered')).toBeInTheDocument()
  })

  it('leaves the shell rendering and the main content non-empty', () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    const authValue = {
      status: 'unauthenticated',
      user: null,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
    }

    // /plan renders without a network request, so a non-empty main is not an
    // accident of a fetch resolving. App carries the routes, so the boundary
    // under test has real route content to render.
    render(
      <MemoryRouter initialEntries={['/plan']}>
        <ThemeProvider>
          <AuthContext.Provider value={authValue}>
            <CompareProvider>
              <SavedScholarshipsProvider>
                <App />
              </SavedScholarshipsProvider>
            </CompareProvider>
          </AuthContext.Provider>
        </ThemeProvider>
      </MemoryRouter>,
    )

    // The page's own header and footer are selected directly: /plan contains
    // an unnamed `<section>` whose `<header>` is also exposed as a banner, so
    // role queries would match two.
    expect(document.querySelector('.site-header')).toBeInTheDocument()
    expect(document.querySelector('.app-footer')).toBeInTheDocument()
    const main = screen.getByRole('main')
    expect(main.textContent.length).toBeGreaterThan(0)
    errorSpy.mockRestore()
  })
})

/* ── Navigation: no badge without a count ───────────────────────────────── */

describe('navigation counts', () => {
  function renderNav() {
    const authValue = {
      status: 'unauthenticated',
      user: null,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
    }
    return render(
      <MemoryRouter>
        <ThemeProvider>
          <AuthContext.Provider value={authValue}>
            <CompareProvider>
              <SavedScholarshipsProvider>
                <Navigation />
              </SavedScholarshipsProvider>
            </CompareProvider>
          </AuthContext.Provider>
        </ThemeProvider>
      </MemoryRouter>,
    )
  }

  it('renders no Applications pill and no undefined label', () => {
    renderNav()
    const applications = screen.getByRole('link', { name: /applications/i })
    // A count of nothing used to fall through the `count <= 0` guard —
    // `undefined <= 0` is false — leaving an empty pill and the accessible
    // name "Applications: undefined".
    expect(applications.getAttribute('aria-label')).toBeNull()
    expect(applications.textContent.replace(/\s+/g, ' ').trim()).toBe('Applications')
  })

  it('still shows a real count where one exists', () => {
    window.localStorage.setItem('scholarzone.saved-scholarship-ids.v1', JSON.stringify(['5']))
    renderNav()
    try {
      const saved = screen.getByRole('link', { name: /^Saved/i })
      expect(saved.getAttribute('aria-label')).toBe('Saved: 1')
      expect(saved.textContent).toContain('1')
    } finally {
      window.localStorage.clear()
    }
  })
})

/* ── Catalogue pager: one marker per gap ────────────────────────────────── */

describe('pager keys', () => {
  it('never emits the same ellipsis marker twice', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    // 120 records is ten pages at the directory's page size. On page 1, seven
    // consecutive candidates fall outside the one-page window, which is the
    // shape that produced duplicate `ellipsis-end` keys: the guard only
    // checked for `ellipsis-start`, so every one of them pushed its own
    // marker.
    const snapshot = {
      meta: { sort_orders: { recommended: [] } },
      stats: { total: 120, countries: 1 },
      scholarships: Array.from({ length: 120 }, (_, index) => ({
        id: index + 1,
        title: `Scholarship ${index + 1}`,
        name: `Scholarship ${index + 1}`,
        official_source: 'Provider',
        country: 'Sweden',
        region: 'Europe',
        degree: 'Master',
        degree_levels: 'Master',
        funding: 'Fully Funded',
        funding_type: 'Fully Funded',
        tuition_coverage: true,
        deadline: '2026-12-31',
        deadline_date: '2026-12-31',
        deadline_precision: 'exact',
        status: 'open',
        verification_status: 'active',
        last_verified_at: '2026-10-01',
        official_source_url: 'https://example.org/scholarship',
        eligibility_summary: 'Applicants from India.',
        updated_at: '2026-10-01T00:00:00',
      })),
    }

    vi.stubGlobal('fetch', vi.fn(async (url) => {
      if (String(url).includes('scholarships-snapshot.json')) {
        return { ok: true, status: 200, json: async () => snapshot }
      }
      return { ok: false, status: 404, json: async () => ({ detail: 'not found' }) }
    }))

    const ScholarshipList = (await import('./ScholarshipList.jsx')).default
    render(
      <MemoryRouter initialEntries={['/scholarships']}>
        <ThemeProvider>
          <AuthContext.Provider value={{ status: 'unauthenticated', user: null, login: vi.fn(), register: vi.fn(), logout: vi.fn() }}>
            <CompareProvider>
              <SavedScholarshipsProvider>
                {/* `items` is deliberately not an array: that is what selects the
                    server-paginated directory path. */}
                <ScholarshipList items={null} />
              </SavedScholarshipsProvider>
            </CompareProvider>
          </AuthContext.Provider>
        </ThemeProvider>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByRole('navigation', { name: /scholarship pages/i })).toBeInTheDocument()
    })
    // The gap's single marker is a child of the pager's list, so it rendered.
    expect(document.querySelectorAll('.scholarship-pagination__pages li[aria-hidden="true"]').length)
      .toBeLessThanOrEqual(2)

    const duplicateKeyWarnings = errorSpy.mock.calls.filter((call) =>
      /same key/.test(String(call[0])))
    expect(duplicateKeyWarnings).toEqual([])
    vi.unstubAllGlobals()
    errorSpy.mockRestore()
  })
})
