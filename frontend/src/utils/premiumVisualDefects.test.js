/**
 * Regression tests for the cross-surface defects found during the premium
 * visual audit.
 *
 * Two of these pin CSS-level failures that a browser measurement caught and a
 * jsdom test cannot, because `vitest.config` runs with `css: false` - computed
 * styles are not available to a component test. So the guard reads the
 * stylesheet instead, and asserts on the selector that has to win:
 *
 *   1. `.visually-hidden` was defined only in ScholarshipList.css, which
 *      ComparePage.jsx does not import. A direct load of /compare rendered the
 *      table caption "2 scholarships compared across 13 attributes." as
 *      visible text. The fix is that index.css owns it.
 *   2. A "Not stated" cell was styled identically to a populated one, so the
 *      page explained that unknown is not "no" and then drew them the same
 *      way. The first fix used a class-only selector, which
 *      `.compare-page__table td` beat on specificity (0-1-1 vs 0-1-0) - a
 *      browser measurement still returned weight 600 and primary ink on the
 *      unknown cell. The selector now carries the element.
 */

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const read = (relative) => readFileSync(resolve(process.cwd(), relative), 'utf8')

/**
 * Every rule in a stylesheet, as `{selector, body}` pairs.
 *
 * Declarative rather than a `slice` from a match: the first `.compare-page__table
 * td` in ComparePage.css is inside the shared `th, td` block, and a slice-based
 * test read that one's body and reported the fix as missing when it was present
 * in the rule it was meant to check.
 */
const rulesOf = (css) => {
  // Comments out first: a stylesheet-authored comment inside a selector block
  // (which ComparePage.css uses, and which is good practice) would otherwise be
  // glued onto the selector string and make every exact match fail.
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

/**
 * The body of the single rule whose last selector contains `needle`.
 *
 * "Contains" rather than "equals": a group selector such as
 * `.sz-sr-only, .visually-hidden` has to be findable by its distinctive member,
 * and `.compare-page__table td.compare-page__cell--unknown` has to be findable
 * without the caller retyping the whole compound. Where an exact match matters
 * the assertions check the returned selector separately.
 */
const ruleBody = (css, needle) => {
  const rules = rulesOf(css)
  const rule = rules.find((candidate) => {
    const last = candidate.selector.split(',').pop().trim()
    return last.endsWith(needle)
  })
  return rule ? rule.body : null
}

describe('the visually-hidden utility is owned globally', () => {
  const indexCss = read('src/index.css')

  it('defines `visually-hidden` in the global stylesheet', () => {
    // The name three components use. It used to exist only in
    // ScholarshipList.css, so every one of them rendered un-hidden text on a
    // direct load.
    expect(indexCss).toMatch(/\.visually-hidden\s*[,{]/)
  })

  it('defines it with the clip-path form that keeps it in the a11y tree', () => {
    const rule = ruleBody(indexCss, '.visually-hidden')
    expect(rule, 'the .visually-hidden rule is missing from index.css').not.toBeNull()
    expect(rule).toContain('position: absolute')
    expect(rule).toContain('clip-path: inset(50%)')
    // `display: none` or `visibility: hidden` would remove it from the tree.
    expect(rule).not.toMatch(/display:\s*none/)
    expect(rule).not.toMatch(/visibility:\s*hidden/)
  })

  it('is one rule covering both names, not two that can drift', () => {
    // One declaration block for both names is what stops the legacy name and
    // the widely-used name diverging.
    expect(indexCss).toMatch(/\.sz-sr-only,\s*\.visually-hidden\s*\{/)
  })

  it('is not redefined with conflicting values anywhere else', () => {
    // The local definition in ScholarshipList.css is harmless while it agrees;
    // a second rule with a different hiding mechanism is not.
    // The point of the fix is single ownership, so anything else that defines
    // it must use the same clip-path technique.
    const otherFiles = [
      'src/components/ScholarshipList.css',
      'src/pages/ComparePage.css',
      'src/pages/PlanPage.css',
      'src/components/PremiumScholarshipCard.css',
    ]
    for (const file of otherFiles) {
      const rule = ruleBody(read(file), '.visually-hidden')
      if (rule === null) {
        continue
      }
      expect(rule, `${file} redefines .visually-hidden differently`).toContain('clip-path: inset(50%)')
      expect(rule, `${file} redefines .visually-hidden differently`).not.toMatch(/display:\s*none/)
    }
  })
})

describe('an unknown comparison cell is drawn differently from a value', () => {
  const compareCss = read('src/pages/ComparePage.css')
  const rules = rulesOf(compareCss)

  /** The rule whose last selector is exactly the given one. */
  const findRule = (selector) => rules.find((rule) => {
    const last = rule.selector.split(',').pop().trim()
    return last === selector
  })

  it('styles the unknown cell with a selector that beats the base cell rule', () => {
    // This is the regression that a browser run found: `.compare-page__table td`
    // is specificity 0-1-1 and `.compare-page__cell--unknown` alone is 0-1-0,
    // so the class-only rule loses no matter what order it appears in.
    const unknown = findRule('.compare-page__table td.compare-page__cell--unknown')
    expect(unknown, 'the unknown-cell rule is missing').toBeTruthy()
  })

  it('styles it at a quieter weight and colour than a populated cell', () => {
    const unknown = findRule('.compare-page__table td.compare-page__cell--unknown')
    expect(unknown, 'the unknown-cell rule is missing').toBeTruthy()
    expect(unknown.body).toContain('font-weight: 400')

    // The standalone `td` rule, not the shared `th, td` block that precedes it.
    const base = rules.find((rule) => rule.selector === '.compare-page__table td')
    expect(base, 'the populated-cell rule is missing').toBeTruthy()
    expect(base.body).toContain('font-weight: 600')
  })

  it('carries the element in the unknown selector, so specificity is real', () => {
    // The mechanism behind the previous assertions: a compound selector of
    // two classes plus an element beats one class plus an element. A class-only
    // selector looks correct in the file and still loses.
    const unknown = findRule('.compare-page__table td.compare-page__cell--unknown')
    expect(unknown, 'the unknown-cell rule is missing').toBeTruthy()

    const classes = unknown.selector.match(/\./g) || []
    const elements = unknown.selector.match(/\b(td|th|p|span)\b/g) || []

    expect(unknown.selector).toContain(' td')
    expect(classes.length).toBeGreaterThanOrEqual(2)
    // The element is the part that raises 0-1-0 to 0-2-1.
    expect(elements).toContain('td')

    const base = rules.find((rule) => rule.selector === '.compare-page__table td')
    expect(base).toBeTruthy()
    expect(base.selector).not.toContain('unknown')
  })

  it('marks the unknown in a way that survives without colour', () => {
    // Italic plus an icon plus the words "Not stated": a colour-blind reader
    // and a greyscale print both still see the difference.
    expect(compareCss).toContain('.compare-page__unknown-icon')
    const unknown = findRule('.compare-page__table td.compare-page__cell--unknown')
    expect(unknown.body).toContain('font-style: italic')
  })

  it('gives the funding-exclusion note real styling', () => {
    // `.compare-page__note` had no rule at all, so the page's explanation for
    // the missing funding column rendered as a default browser paragraph.
    const note = findRule('.compare-page__note')
    expect(note, '.compare-page__note has no rule').toBeTruthy()
    expect(note.body).toMatch(/margin|padding/)
  })

  it('gives the unresolved-selection notice real styling and a button', () => {
    // Also unstyled before. And the notice told the student to remove the id,
    // when the only remove control on the page was rendered per *resolved*
    // scholarship - so an unresolved id could never be cleared.
    const notice = findRule('.compare-page__unresolved')
    expect(notice, '.compare-page__unresolved has no rule').toBeTruthy()
    expect(notice.body).toMatch(/padding|margin/)
    expect(rules.some((rule) => rule.selector === '.compare-page__unresolved button')).toBe(true)
  })
})

describe('the card deadline is not a bold paragraph', () => {
  const cardCss = read('src/components/ScholarshipCard.css')
  const rules = rulesOf(cardCss)

  it('sets a prose deadline at body weight', () => {
    // The ESKAS record's 244-character provider sentence used to render at
    // font-weight 700 with line-height 1.35 - the heaviest weight on the card
    // spent on the longest string in the catalogue.
    const rule = ruleBody(cardCss, '.scholarship-card__deadline-value--prose')
    expect(rule).not.toBeNull()
    expect(rule).toContain('font-weight: 400')
  })

  it('sets a real date at a medium weight rather than a headline weight', () => {
    const rule = ruleBody(cardCss, '.scholarship-card__deadline-value')
    expect(rule).not.toBeNull()
    expect(rule).toContain('font-weight: 600')
    expect(rule).not.toContain('font-weight: 700')
  })

  it('renders the deadline row left-aligned and stacked', () => {
    // It used to be a right-aligned flex row that gave the value ~178px.
    expect(ruleBody(cardCss, '.scholarship-card__details dd')).toContain('text-align: left')
    expect(ruleBody(cardCss, '.scholarship-card__detail--deadline')).toContain('flex-direction: column')
  })

  it('lets a funding badge wrap instead of truncating to one line', () => {
    // Measured in a browser: scrollWidth 398 against clientWidth 355, so 18
    // of 65 visible characters survived.
    //
    // The rule is a group covering all four pills, so the assertion targets the
    // group by its first two members rather than by `badge` alone - which would
    // also match `.scholarship-card__badge--category`.
    const group = rules.find((rule) => (
      rule.selector.startsWith('.scholarship-card__badge, .scholarship-card__status')
    ))
    expect(group, 'the shared pill rule is missing').toBeTruthy()
    expect(group.body).toContain('-webkit-line-clamp: 2')
    expect(group.body).not.toMatch(/white-space:\s*nowrap/)
  })
})
