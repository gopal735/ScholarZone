/**
 * Draft export: plain text and Markdown.
 *
 * The exports are where the trust rules have to survive outside the app. A file
 * the student keeps has to tell them, unaided, four things: that it is their own
 * work held on their device; that a word limit is only official if a source was
 * recorded; which claims they answered and which are still open; and that nothing
 * here predicts an outcome. Both formats are asserted for all four, because a
 * declaration that survived one format and not the other would make the pair
 * untrustworthy.
 */

import { describe, expect, it } from 'vitest'

import { exportFileName, toMarkdown, toPlainText } from './sopBuilderExport.js'
import { SOP_SECTIONS } from './sopBuilderSections.js'
import { reviewDraft } from './sopBuilderReview.js'

/** A normalised draft, built by hand so the test owns every value in it. */
function draft(overrides = {}) {
  const sections = {}
  for (const section of SOP_SECTIONS) {
    sections[section.id] = { text: '', updated_at: null }
  }
  sections.opening = { text: 'A wet summer in 2019 made me curious about flooding.', updated_at: '2026-01-01T00:00:00.000Z' }
  sections['why-programme'] = { text: 'Their hydrology group runs the field site I want on.', updated_at: '2026-01-01T00:00:00.000Z' }

  return {
    schema: 'scholarzone.sop-builder',
    version: 1,
    device_local: true,
    updated_at: null,
    context: {
      application_type: "Master's",
      institution: 'University of Waterloo',
      programme: 'Hydrology',
      scholarship_name: '',
      official_prompt: '',
      word_limit: null,
      word_limit_source: '',
      ...(overrides.context || {}),
    },
    background: overrides.background !== undefined
      ? overrides.background
      : { academic: 'BSc Civil Engineering, Bristol, 2023.' },
    sections: overrides.sections || sections,
    substantiation: overrides.substantiation || {},
    approval: overrides.approval || null,
  }
}

/** A draft with a detectable claim, for the ledger expectations. */
function draftWithClaim(claimText, substantiation = {}) {
  return draft({
    sections: Object.fromEntries(
      SOP_SECTIONS.map((section) => [section.id, { text: claimText, updated_at: null }]),
    ),
    substantiation,
  })
}

describe('both formats declare the same four things', () => {
  const contexts = [
    { label: 'plain text', render: toPlainText },
    { label: 'markdown', render: toMarkdown },
  ]

  for (const { label, render } of contexts) {
    it(`${label}: says the draft is the student's own work, held locally`, () => {
      const output = render(draft())
      expect(output).toMatch(/your own draft/i)
      expect(output).toMatch(/ScholarZone did not generate, rewrite or approve/i)
    })

    it(`${label}: never claims a limit is official without a source`, () => {
      const unsourced = render(draft({ context: { word_limit: 1500, word_limit_source: '' } }))
      expect(unsourced).toMatch(/no source is/i)
      expect(unsourced).toMatch(/does not treat it as an official limit/i)
    })

    it(`${label}: reports a sourced limit and defers to the source`, () => {
      const sourced = render(draft({ context: { word_limit: 1500, word_limit_source: 'guidelines page' } }))
      expect(sourced).toMatch(/1500/)
      expect(sourced).toMatch(/source as the authority/i)
    })

    it(`${label}: says nothing predicts an outcome`, () => {
      const output = render(draft())
      expect(output).toMatch(/Nothing in this document predicts an admission/i)
    })

    it(`${label}: reports the claim ledger`, () => {
      const output = render(
        draftWithClaim('I ranked first in my class.', {
          'opening:numeric-achievement:ranked first': { status: 'confirmed', evidence: 'I have the letter.' },
        }),
      )
      expect(output).toMatch(/claim\(s\) detected/i)
    })
  }
})

describe('both formats carry the student content verbatim', () => {
  it('includes every section with its word count, and marks an unwritten one', () => {
    const output = toPlainText(draft())
    for (const section of SOP_SECTIONS) {
      expect(output).toContain(section.title.toUpperCase())
    }
    expect(output).toContain('A wet summer in 2019 made me curious about flooding.')
    expect(output).toContain('(nothing written yet)')
  })

  it('includes the word count beside each section, and counts the student text', () => {
    const output = toPlainText(draft())
    // "A wet summer in 2019 made me curious about flooding." is 10 words.
    expect(output).toContain('10 words')
  })

  it('includes the background the student wrote, labelled as theirs', () => {
    expect(toPlainText(draft())).toContain('BSc Civil Engineering, Bristol, 2023.')
    expect(toMarkdown(draft())).toContain('BSc Civil Engineering, Bristol, 2023.')
  })

  it('includes an approval stamp when the student approved, and says so when not', () => {
    expect(toPlainText(draft())).toMatch(/You have not yet confirmed/i)
    const approved = toPlainText(draft({ approval: { confirmed: true, confirmed_at: '2026-01-02T00:00:00.000Z' } }))
    expect(approved).toMatch(/You confirmed you have reviewed this draft on 2026-01-02/)
  })
})

describe('the prompt is labelled as the student own paste', () => {
  it('says so in plain text and echoes the prompt', () => {
    const output = toPlainText(draft({
      context: { official_prompt: 'Why this programme, in 500 words?' },
    }))
    expect(output).toMatch(/prompt you pasted yourself/i)
    expect(output).toMatch(/has not verified it against the provider/i)
    expect(output).toContain('Why this programme, in 500 words?')
  })

  it('uses markdown blockquotes for the declarations so they are visibly metadata', () => {
    const output = toMarkdown(draft())
    expect(output.startsWith('# ScholarZone statement draft')).toBe(true)
    expect(output).toMatch(/^> /m)
  })
})

/** The claim keys a draft with the given text in every section actually produces. */
function claimKeysFor(claimText) {
  const probe = draftWithClaim(claimText, {})
  return reviewDraft(probe).claims.map((claim) => claim.key)
}

/**
 * A draft where every section carries the claim text, and the given keys are
 * resolved with `status`/`evidence`.
 *
 * `resolve` takes a real claim key and returns a record or undefined, so the
 * expectations do not hard-code a key and silently stop testing anything when a
 * pattern list changes.
 */
function draftWithResolvedClaims(claimText, resolve) {
  const substantiation = {}
  for (const key of claimKeysFor(claimText)) {
    const record = resolve(key)
    if (record) {
      substantiation[key] = record
    }
  }
  return draftWithClaim(claimText, substantiation)
}

describe('the claim ledger distinguishes the four states', () => {
  it('marks an unanswered claim', () => {
    const output = toPlainText(draftWithClaim('I ranked first in my class.'))
    expect(output).toMatch(/UNANSWERED —/)
  })

  it('marks a confirmed-without-evidence claim distinctly from a confirmed one', () => {
    const firstKey = claimKeysFor('I ranked first in my class.')[0]
    const confirmed = toPlainText(
      draftWithResolvedClaims('I ranked first in my class.', (key) => ({
        status: 'confirmed',
        evidence: key === firstKey ? '' : 'My transcript.',
      })),
    )
    expect(confirmed).toMatch(/CONFIRMED WITHOUT EVIDENCE —/)
    expect(confirmed).toMatch(/CONFIRMED BY YOU —/)
    expect(confirmed).toContain('Your evidence: My transcript.')
  })

  it('warns when claims are still outstanding', () => {
    const output = toPlainText(draftWithClaim('I ranked first in my class.'))
    expect(output).toMatch(/still outstanding/)
    expect(output).toMatch(/Read them again before you rely on this draft/)
  })

  it('marks a claim the student chose to remove, and then has none outstanding', () => {
    const output = toPlainText(
      draftWithResolvedClaims('I ranked first in my class.', () => ({ status: 'removed', evidence: '' })),
    )
    expect(output).toMatch(/REMOVED BY YOU —/)
    expect(output).not.toMatch(/still outstanding/)
  })
})

describe('the file name', () => {
  it('is built from the student own context and the date, stopwords included', () => {
    // The stem is a slug of what the student typed, so "University of Waterloo"
    // keeps "of" as a hyphen-separated word. A stopword-stripped stem would be
    // a filename the student does not recognise as theirs.
    expect(exportFileName(draft({ context: { institution: 'University of Waterloo', programme: 'Hydrology' } })))
      .toBe(`sop-builder-university-of-waterloo-hydrology-${new Date().toISOString().slice(0, 10)}`)
  })

  it('falls back to a neutral stem when nothing is typed', () => {
    expect(exportFileName(draft({ context: { institution: '', programme: '', scholarship_name: '' } })))
      .toBe(`sop-builder-draft-${new Date().toISOString().slice(0, 10)}`)
  })
})

describe('empty input', () => {
  it('produces a complete, readable file for a completely empty draft', () => {
    const output = toPlainText(draft({
      context: { institution: '', programme: '' },
      background: {},
    }))
    expect(output).toContain('SCHOLARZONE STATEMENT DRAFT')
    // Every section is present and marked, rather than absent, so a student
    // comparing the file against the page can see nothing was dropped.
    for (const section of SOP_SECTIONS) {
      expect(output).toContain(section.title.toUpperCase())
    }
    expect(output).toContain('(nothing written yet)')
    expect(output).not.toContain('undefined')
    expect(output).not.toContain('null')
  })

  it('produces no undefined or null for a draft missing fields entirely', () => {
    const output = toPlainText({
      schema: 'scholarzone.sop-builder',
      version: 1,
      context: {},
      background: {},
      sections: {},
      substantiation: {},
    })
    expect(output).not.toContain('undefined')
    expect(output).not.toContain('[object Object]')
  })

  it('does not throw for a null draft in either format', () => {
    expect(() => toPlainText(null)).not.toThrow()
    expect(() => toMarkdown(null)).not.toThrow()
  })
})
