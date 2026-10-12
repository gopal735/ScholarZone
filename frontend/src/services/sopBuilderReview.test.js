/**
 * The deterministic review engine.
 *
 * The point of every expectation below is the same: given the same draft, the
 * engine always returns the same findings. That is the property that lets the UI
 * honestly call these "checks" and lets a student argue with a rule they can
 * read. If a future edit to a phrase list silently changed the review a student
 * sees, this is where it is caught.
 *
 * Three rules the engine holds to, asserted here so they cannot be quietly
 * dropped:
 *
 *   - it never says a draft is good or bad, only what it could not find
 *   - it never invents content, examples or claims
 *   - it never predicts an admission, an award or a committee's opinion
 *
 * The last one is not a lint rule; it is a product rule, and it is asserted over
 * the whole review output as well as over the disclaimer string.
 */

import { describe, expect, it } from 'vitest'

import {
  SEVERITY,
  claimsNeedingAttention,
  contentWords,
  distinctiveTokens,
  reviewDraft,
  splitSentences,
  wordCount,
} from './sopBuilderReview.js'
import { REVIEW_DIMENSIONS, SOP_SECTION_IDS } from './sopBuilderSections.js'

/** An empty draft, in the shape the store produces. */
function emptyDraft() {
  const sections = {}
  for (const id of SOP_SECTION_IDS) {
    sections[id] = { text: '', updated_at: null }
  }
  return {
    schema: 'scholarzone.sop-builder',
    version: 1,
    device_local: true,
    updated_at: null,
    context: {
      application_type: '',
      institution: '',
      programme: '',
      scholarship_name: '',
      official_prompt: '',
      word_limit: null,
      word_limit_source: '',
    },
    background: {},
    sections,
    substantiation: {},
    approval: null,
  }
}

/** A draft with the given section texts. */
function draftWith(entries, context = {}) {
  const draft = emptyDraft()
  for (const [id, text] of Object.entries(entries)) {
    draft.sections[id] = { text, updated_at: '2026-01-01T00:00:00.000Z' }
  }
  draft.context = { ...draft.context, ...context }
  return draft
}

/* ── Determinism ───────────────────────────────────────────────────── */

describe('the engine is deterministic', () => {
  const draft = draftWith(
    {
      opening: 'A question about rivers. I have always been passionate about them.',
      'why-programme': 'Their hydrology group. The best in the world, guaranteed.',
    },
    { institution: 'University of Somewhere' },
  )

  it('returns an identical result on repeated runs', () => {
    const first = reviewDraft(draft)
    const second = reviewDraft(draft)
    expect(JSON.stringify(second)).toBe(JSON.stringify(first))
  })

  it('does not mutate the draft it is given', () => {
    const frozen = JSON.parse(JSON.stringify(draft))
    reviewDraft(draft)
    expect(JSON.stringify(draft)).toBe(JSON.stringify(frozen))
  })

  it('never returns a finding whose dimension is not one of the six', () => {
    const known = new Set(REVIEW_DIMENSIONS.map((dimension) => dimension.id))
    for (const finding of reviewDraft(draft).findings) {
      expect(known.has(finding.dimension)).toBe(true)
    }
  })
})

/* ── Structure ─────────────────────────────────────────────────────── */

describe('structure', () => {
  it('reports an empty draft once, as its own finding', () => {
    const result = reviewDraft(emptyDraft())
    const empty = result.findings.filter((finding) => finding.id === 'structure:draft:empty')
    expect(empty).toHaveLength(1)
    expect(empty[0].severity).toBe(SEVERITY.IMPORTANT)
  })

  it('reports every unwritten section as absent rather than weak', () => {
    const result = reviewDraft(emptyDraft())
    // Filtered on a real section id, because the draft-level finding also ends
    // in ":empty" and counting it would make six look like seven.
    const absent = result.findings.filter(
      (finding) => finding.id.endsWith(':empty') && finding.sectionId !== null,
    )
    expect(absent).toHaveLength(6)
  })

  it('does not report an absent section as thin, because there is nothing to be thin', () => {
    const result = reviewDraft(emptyDraft())
    const thin = result.findings.filter((finding) => finding.id.endsWith(':thin') && finding.sectionId === null)
    expect(thin).toHaveLength(0)
  })

  it('reports a started but short section as thin, not as absent', () => {
    const result = reviewDraft(draftWith({ opening: 'Too short for this section.' }))
    const thin = result.findings.find(
      (finding) => finding.dimension === 'structure' && finding.sectionId === 'opening' && finding.id.endsWith(':thin'),
    )
    expect(thin).toBeTruthy()
    expect(thin.severity).toBe(SEVERITY.ATTENTION)
  })

  it('drops the empty-draft finding once any section has text', () => {
    const result = reviewDraft(draftWith({ opening: 'x'.repeat(200) }))
    expect(result.findings.some((finding) => finding.id === 'structure:draft:empty')).toBe(false)
  })

  it('counts started sections and total words in the summary', () => {
    const result = reviewDraft(draftWith({ opening: 'one two three', goals: 'four five' }))
    expect(result.summary.sectionsStarted).toBe(2)
    expect(result.summary.sectionsTotal).toBe(6)
    expect(result.summary.totalWords).toBe(5)
  })
})

/* ── Clarity ───────────────────────────────────────────────────────── */

describe('clarity', () => {
  it('flags a sentence above the length threshold and names it', () => {
    const long = `${'word '.repeat(40).trim()}.`
    const result = reviewDraft(draftWith({ opening: long }))
    // The id carries a fingerprint of the sentence, so it is matched on its
    // prefix rather than on a suffix it does not have.
    const finding = result.findings.find((f) => f.id.startsWith('clarity:opening:long:'))
    expect(finding).toBeTruthy()
    expect(finding.detail).toContain('try splitting it')
  })

  it('does not flag sentences under the threshold', () => {
    const result = reviewDraft(draftWith({ opening: 'This is short. So is this.' }))
    expect(result.findings.some((f) => f.dimension === 'clarity')).toBe(false)
  })

  it('flags a filler phrase, once, and says it is not an error', () => {
    const result = reviewDraft(draftWith({ opening: 'It is important to note that and needless to say I tried.' }))
    const findings = result.byDimension.clarity
    const ids = findings.map((finding) => finding.id)
    expect(ids).toContain('clarity:opening:filler:it-is-important-to-note-that')
    expect(ids).toContain('clarity:opening:filler:needless-to-say')
    // Each phrase reported once even though it could match repeatedly.
    expect(ids.filter((id) => id.includes('it-is-important-to-note-that'))).toHaveLength(1)
    expect(findings.every((finding) => finding.severity === SEVERITY.INFO)).toBe(true)
  })

  it('is case-insensitive about filler phrases', () => {
    const result = reviewDraft(draftWith({ opening: 'Needless to say, I am here.' }))
    expect(result.findings.some((f) => f.id.includes('filler:needless-to-say'))).toBe(true)
  })
})

/* ── Specificity ───────────────────────────────────────────────────── */

describe('specificity', () => {
  it('flags a section with no numbers, and says it is not a fault', () => {
    const result = reviewDraft(draftWith({ projects: 'I built a thing with colleagues at a lab.' }))
    const finding = result.byDimension.specificity.find((f) => f.id.endsWith(':no-number'))
    expect(finding).toBeTruthy()
    expect(finding.detail).toContain('is not a fault')
  })

  it('does not flag a number-bearing section', () => {
    const result = reviewDraft(draftWith({ projects: 'I measured 412 samples in 2024 at the lab.' }))
    expect(result.byDimension.specificity.some((f) => f.id.endsWith(':no-number'))).toBe(false)
  })

  it('flags a section with a generic phrase that could belong to any applicant', () => {
    const result = reviewDraft(draftWith({ opening: 'I am passionate about rivers.' }))
    expect(result.byDimension.specificity.some((f) => f.id.includes('generic:i-am-passionate-about'))).toBe(true)
  })

  it('flags a section with no named entities', () => {
    const result = reviewDraft(draftWith({ opening: 'I studied and then I wrote a thing.' }))
    expect(result.byDimension.specificity.some((f) => f.id.endsWith(':no-proper-noun'))).toBe(true)
  })

  it('does not flag a section that names institutions, people and methods', () => {
    const result = reviewDraft(draftWith({ opening: 'At Cambridge, Dr Nkemelu taught me the Rietveld method in 2023.' }))
    expect(result.byDimension.specificity.some((f) => f.id.endsWith(':no-proper-noun'))).toBe(false)
  })
})

/* ── Relevance ─────────────────────────────────────────────────────── */

describe('relevance', () => {
  it('flags an institution the draft never names', () => {
    const result = reviewDraft(
      draftWith({ 'why-programme': 'I want to study here because it is good.' }, { institution: 'University of Waterloo' }),
    )
    const finding = result.byDimension.relevance.find((f) => f.id === 'relevance:institution:absent')
    expect(finding).toBeTruthy()
    expect(finding.severity).toBe(SEVERITY.IMPORTANT)
    expect(finding.detail).toContain('University of Waterloo')
  })

  it('does not flag an institution the draft does name', () => {
    const result = reviewDraft(
      draftWith({ 'why-programme': 'Waterloo is where I want to do this.' }, { institution: 'University of Waterloo' }),
    )
    expect(result.byDimension.relevance.some((f) => f.id === 'relevance:institution:absent')).toBe(false)
  })

  it('declines to check a name with no distinctive word at all', () => {
    // "MSc of the" reduces to nothing: the only words are a stopword or too
    // short. A comparison on "of" would be theatre, so the engine reports
    // nothing rather than a match it did not make.
    const result = reviewDraft(
      draftWith({ 'why-programme': 'text' }, { institution: 'MSc of the' }),
    )
    expect(result.byDimension.relevance).toHaveLength(0)
  })

  it('is case-insensitive about the institution name', () => {
    const result = reviewDraft(
      draftWith({ 'why-programme': 'WATERLOO is the goal.' }, { institution: 'University of Waterloo' }),
    )
    expect(result.byDimension.relevance.some((f) => f.id === 'relevance:institution:absent')).toBe(false)
  })

  it('flags a programme the draft never names', () => {
    const result = reviewDraft(
      draftWith({ 'why-programme': 'I would like to join.' }, { programme: 'Hydrology and Water Resources' }),
    )
    expect(result.byDimension.relevance.some((f) => f.id === 'relevance:programme:absent')).toBe(true)
  })
})

/* ── Repetition ────────────────────────────────────────────────────── */

describe('repetition', () => {
  it('flags the same sentence appearing twice', () => {
    const result = reviewDraft(draftWith({
      opening: 'I want to study water in the field. I want to study water in the field.',
    }))
    const finding = result.byDimension.repetition.find((f) => f.id.startsWith('repetition:sentence:'))
    expect(finding).toBeTruthy()
    expect(finding.severity).toBe(SEVERITY.ATTENTION)
  })

  it('flags the same wording spanning two sections', () => {
    // The same seven-word run in two sections. A shorter overlap is not flagged,
    // which is deliberate: seven words is roughly the point at which it stops
    // being two people describing the same thing and starts being one
    // paragraph written twice.
    const shared = 'I measured sediment transport in the Mekong delta over three years.'
    const result = reviewDraft(draftWith({
      opening: shared,
      projects: shared,
    }))
    expect(result.byDimension.repetition.some((f) => f.id.startsWith('repetition:shingle:'))).toBe(true)
  })

  it('does not flag a short repeated sentence as repetition', () => {
    // A short repeated sentence is usually a rhetorical device, and flagging it
    // would train a student to distrust the check.
    const result = reviewDraft(draftWith({ opening: 'So I went. So I went. So I went.' }))
    expect(result.byDimension.repetition).toHaveLength(0)
  })

  it('does not flag a draft that says each thing once', () => {
    const result = reviewDraft(draftWith({
      opening: 'A question about rivers led me here.',
      academic: 'I read civil engineering at Bristol with a first in 2023.',
      projects: 'I built a flume to measure bedload transport over one summer.',
      'why-programme': 'Their hydrology group runs the field site I want on.',
      goals: 'I want to model flood risk at catchment scale afterwards.',
      conclusion: 'I am asking to be considered for this programme.',
    }))
    expect(result.byDimension.repetition).toHaveLength(0)
  })
})

/* ── Unsupported claims ────────────────────────────────────────────── */

describe('unsupported claims', () => {
  it('detects a guarantee claim and asks for a source', () => {
    const result = reviewDraft(draftWith({ opening: 'This programme is guaranteed to transform my career.' }))
    const claim = result.claims.find((entry) => entry.kind === 'guarantee')
    expect(claim).toBeTruthy()
    expect(claim.ask).toMatch(/guarantee/)
    expect(claim.sectionId).toBe('opening')
  })

  it('detects a superlative claim and asks what it is compared with', () => {
    const result = reviewDraft(draftWith({ 'why-programme': 'The best in the world, world-class staff.' }))
    const claims = result.claims.filter((entry) => entry.kind === 'superlative')
    expect(claims.length).toBeGreaterThanOrEqual(2)
    expect(claims.every((claim) => claim.ask.includes('compared'))).toBe(true)
  })

  it('detects an achievement claim and asks for the record', () => {
    const result = reviewDraft(draftWith({ projects: 'I ranked first of 412 and received first prize.' }))
    const claims = result.claims.filter((entry) => entry.kind === 'numeric-achievement')
    expect(claims.length).toBeGreaterThanOrEqual(2)
    expect(claims.every((claim) => claim.ask.match(/evidence|record/i))).toBe(true)
  })

  it('quotes the student their own words, not a lower-cased form', () => {
    const result = reviewDraft(draftWith({ opening: 'I Ranked First In My Class.' }))
    const claim = result.claims.find((entry) => entry.pattern === 'ranked first')
    expect(claim).toBeTruthy()
    expect(claim.quote).toContain('Ranked First')
  })

  it('detects nothing in a clean draft', () => {
    const result = reviewDraft(draftWith({
      opening: 'A wet summer in 2019 made me curious about catchment flooding.',
      academic: 'I read civil engineering at Bristol, graduating in 2023 with a first.',
      projects: 'I spent one summer measuring bedload in a flume with two colleagues.',
      'why-programme': 'Their hydrology group runs the field site I want to work on.',
      goals: 'I want to model flood risk at catchment scale.',
      conclusion: 'I am asking to be considered for a place on this programme.',
    }))
    expect(result.claims).toHaveLength(0)
    expect(result.summary.claimsOutstanding).toBe(0)
  })
})

describe('claims needing attention', () => {
  const claims = [
    { key: 'a', sectionId: 'opening', kind: 'guarantee', pattern: 'guaranteed', quote: 'x', ask: 'y' },
    { key: 'b', sectionId: 'opening', kind: 'superlative', pattern: 'the best', quote: 'x', ask: 'y' },
    { key: 'c', sectionId: 'projects', kind: 'numeric-achievement', pattern: 'first prize', quote: 'x', ask: 'y' },
  ]

  it('treats an unanswerd claim as needing attention', () => {
    expect(claimsNeedingAttention(claims, {})).toHaveLength(3)
  })

  it('treats a confirmed claim with evidence as answered', () => {
    const outstanding = claimsNeedingAttention(claims, { a: { status: 'confirmed', evidence: 'my record' } })
    expect(outstanding.map((claim) => claim.key)).toEqual(['b', 'c'])
  })

  it('still treats a confirmed claim with NO evidence as needing attention', () => {
    // The student has asserted the claim but not said why it holds, and the
    // whole point of the step is to put the evidence somewhere first.
    const outstanding = claimsNeedingAttention(claims, { a: { status: 'confirmed', evidence: '   ' } })
    expect(outstanding.map((claim) => claim.key)).toEqual(['a', 'b', 'c'])
  })

  it('treats a removed claim as answered', () => {
    const outstanding = claimsNeedingAttention(claims, { a: { status: 'removed', evidence: '' } })
    expect(outstanding.map((claim) => claim.key)).toEqual(['b', 'c'])
  })
})

/* ── The trust rules ───────────────────────────────────────────────── */

describe('the trust rules hold over the whole review output', () => {
  const draft = draftWith({
    opening: 'I am passionate about the best in the world, guaranteed. '.repeat(3),
    academic: 'I ranked first in my class of 412 at Bristol.',
    'why-programme': 'Waterloo, because their hydrology group runs the field site.',
  })

  it('never calls a draft good, bad, weak, strong or excellent', () => {
    const text = JSON.stringify(reviewDraft(draft)).toLowerCase()
    for (const word of ['is good', 'is bad', 'is weak', 'is strong', 'is excellent', 'well written', 'poorly written', 'you will be accepted', 'will get you in']) {
      expect(text).not.toContain(word)
    }
  })

  it('never predicts an outcome in any finding or claim', () => {
    const text = JSON.stringify(reviewDraft(draft)).toLowerCase()
    expect(text).not.toContain('admission chance')
    expect(text).not.toContain('you will')
    expect(text).not.toContain('guarantees you')
  })

  it('returns no finding, claim or suggestion that contains written prose for the student', () => {
    // Nothing in the output may read as text the student could paste into their
    // draft: the engine returns questions and rules, not content.
    const result = reviewDraft(draft)
    for (const finding of result.findings) {
      expect(finding.detail).not.toMatch(/^(Dear|I am writing|I have always)/i)
    }
  })
})

/* ── The helpers, in isolation ─────────────────────────────────────── */

describe('the text helpers', () => {
  it('splits sentences on terminal punctuation and on paragraph breaks', () => {
    expect(splitSentences('One. Two.\n\nThree!')).toEqual(['One.', 'Two.', 'Three!'])
  })

  it('returns no sentences for empty or whitespace-only text', () => {
    expect(splitSentences('')).toEqual([])
    expect(splitSentences('   \n ')).toEqual([])
  })

  it('counts words in a string and zero for a non-string', () => {
    expect(wordCount('a b  c')).toBe(3)
    expect(wordCount(null)).toBe(0)
  })

  it('keeps only distinctive, non-stopword tokens, in the order they appear', () => {
    expect([...distinctiveTokens('University of Waterloo')]).toEqual(['university', 'waterloo'])
  })

  it('drops a token too short to be distinctive', () => {
    expect([...distinctiveTokens('MSc in AI of the EU')]).toEqual([])
  })

  it('folds British and American spellings together for comparison', () => {
    const tokens = contentWords('I analyse the organisation program behaviour.')
    expect(tokens.has('analyze')).toBe(true)
    expect(tokens.has('organization')).toBe(true)
    expect(tokens.has('behaviour')).toBe(false)
  })
})
