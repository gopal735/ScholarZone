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
import { REVIEW_DIMENSIONS, SOP_SECTION_IDS, SOP_SECTIONS } from './sopBuilderSections.js'

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
  it('reports an empty draft as one not-started flag, not as seven findings', () => {
    // The regression this pins: an empty draft used to produce six per-section
    // findings plus one draft-level finding, so a document nobody had opened
    // the editor for looked like a draft in trouble.
    const result = reviewDraft(emptyDraft())
    expect(result.notStarted).toBe(true)
    expect(result.findings).toHaveLength(0)
    expect(result.summary.findingsImportant).toBe(0)
  })

  it('reports every unwritten section as guidance rather than as weak', () => {
    const result = reviewDraft(emptyDraft())
    // The six section entries survive, but on the guidance channel.
    const absent = result.sectionGuidance.filter((entry) => entry.status === 'empty')
    expect(absent).toHaveLength(6)
    expect(absent.map((entry) => entry.sectionId).sort()).toEqual(
      [
        'opening',
        'academic-preparation',
        'projects',
        'why-programme',
        'goals',
        'conclusion',
      ].sort(),
    )
    // No severity: a section with nothing in it is a fact, not a defect.
    expect(absent.every((entry) => entry.severity === null)).toBe(true)
  })

  it('does not report an absent section as thin, because there is nothing to be thin', () => {
    const result = reviewDraft(emptyDraft())
    expect(result.sectionGuidance.some((entry) => entry.status === 'thin')).toBe(false)
  })

  it('reports a started but short section as thin guidance, not as absent', () => {
    const result = reviewDraft(draftWith({ opening: 'Too short for this section.' }))
    const thin = result.sectionGuidance.find(
      (entry) => entry.sectionId === 'opening' && entry.status === 'thin',
    )
    expect(thin).toBeTruthy()
    expect(thin.words).toBe(5)
    // Not a finding. Other checks may still fire on the same section's text -
    // what must not happen is the section's *completeness* appearing as a
    // finding, so the assertion is that no finding is in the structure
    // dimension or carries completion wording.
    expect(result.findings.some((finding) => finding.dimension === 'structure')).toBe(false)
    expect(
      result.findings.some((finding) => /words so far|nothing written yet/i.test(finding.title)),
    ).toBe(false)
  })

  it('clears the not-started flag once any section has text', () => {
    const result = reviewDraft(draftWith({ opening: 'x'.repeat(200) }))
    expect(result.notStarted).toBe(false)
  })

  it('counts started sections, remaining sections and total words in the summary', () => {
    const result = reviewDraft(draftWith({ opening: 'one two three', goals: 'four five' }))
    expect(result.summary.sectionsStarted).toBe(2)
    expect(result.summary.sectionsTotal).toBe(6)
    expect(result.summary.sectionsRemaining).toBe(4)
    expect(result.summary.totalWords).toBe(5)
  })

  /* Section floors, for the fixtures below. Kept literal so a change to
     `minimumWords` shows up as a failure here rather than as a silently
     mis-written fixture. */
  const FLOOR = Object.freeze({
    opening: 60,
    'academic-preparation': 80,
    projects: 120,
    'why-programme': 100,
    goals: 70,
    conclusion: 45,
  })

  /* ── Empty vs partially written vs genuinely triggered ───────────── */

  describe('an empty draft', () => {
    const result = reviewDraft(emptyDraft())

    it('produces no findings at all', () => {
      expect(result.findings).toHaveLength(0)
    })

    it('flags nothing as important, so the empty state is not an alarm', () => {
      expect(result.summary.findingsImportant).toBe(0)
      expect(result.findings.filter((finding) => finding.severity === SEVERITY.IMPORTANT)).toHaveLength(0)
    })

    it('still describes all six sections as unwritten, on the guidance channel', () => {
      expect(result.sectionGuidance).toHaveLength(6)
      expect(result.sectionGuidance.every((entry) => entry.status === 'empty')).toBe(true)
    })

    it('detects no claims, because there is nothing to detect', () => {
      expect(result.claims).toHaveLength(0)
      expect(result.summary.claimsDetected).toBe(0)
    })

    it('still reports zero sections started, which keeps the progress indicator honest', () => {
      expect(result.summary.sectionsStarted).toBe(0)
      expect(result.summary.sectionsRemaining).toBe(6)
    })
  })

  describe('a partially written draft', () => {
    // Two sections past their floors, four untouched. This is the state where
    // the old engine reported six alarming empty-section findings alongside
    // actual findings about the text that existed.
    const opening =
      'A wet summer in 2019 at Bristol, spending a fortnight measuring how quickly the ' +
      'Malago rose after a summer storm, is what made me curious about catchment flooding, ' +
      'and I have spent the two years since then trying to understand why the published models ' +
      'were wrong, and what a modeller can honestly say about a gauge record that has gaps in it.'
    const goals =
      'I want to be able to model flood risk at catchment scale using the imperfect gauge ' +
      'data that a real agency actually holds, and to be honest in print about how much ' +
      'confidence that model can carry. Whether that ends up in a forecasting service or in ' +
      'research, I do not know yet, and I would rather find out here than decide now. What the ' +
      'programme has to give me is a way to be wrong about a forecast in a way I can measure.'
    const result = reviewDraft(draftWith({ opening, goals }))

    it('uses fixtures that actually clear the section floors', () => {
      expect(wordCount(opening)).toBeGreaterThanOrEqual(FLOOR.opening)
      expect(wordCount(goals)).toBeGreaterThanOrEqual(FLOOR.goals)
    })

    it('reports the four untouched sections as guidance, and the two written ones not at all', () => {
      const empty = result.sectionGuidance.filter((entry) => entry.status === 'empty')
      expect(empty.map((entry) => entry.sectionId).sort()).toEqual(
        ['academic-preparation', 'conclusion', 'projects', 'why-programme'].sort(),
      )
      // Written sections are absent from the guidance channel entirely once
      // they have passed their floor.
      expect(result.sectionGuidance.some((entry) => entry.sectionId === 'opening')).toBe(false)
      expect(result.sectionGuidance.some((entry) => entry.sectionId === 'goals')).toBe(false)
    })

    it('is not in the not-started state', () => {
      expect(result.notStarted).toBe(false)
    })

    it('scopes every finding to a section that actually has text', () => {
      for (const finding of result.findings) {
        expect(['opening', 'goals']).toContain(finding.sectionId)
      }
    })

    it('reports four sections remaining, matching the guidance channel', () => {
      expect(result.summary.sectionsRemaining).toBe(4)
      expect(result.summary.sectionsStarted).toBe(2)
    })
  })

  describe('a genuinely triggered finding', () => {
    // The checks must still run once text exists. Each case triggers one
    // specific check and asserts the finding that should come out of it, so a
    // future edit that silences a check is caught here.
    it('still flags a long sentence when the draft has text', () => {
      const result = reviewDraft(draftWith({ opening: 'x '.repeat(40).trim() + '.' }))
      expect(result.findings.some((f) => f.dimension === 'clarity')).toBe(true)
    })

    it('still flags an institution the draft never names', () => {
      const result = reviewDraft(
        draftWith({ 'why-programme': 'I would like to join.' }, { institution: 'University of Waterloo' }),
      )
      expect(result.findings.some((f) => f.dimension === 'relevance')).toBe(true)
    })

    it('still flags a repeated sentence', () => {
      const shared = 'I measured sediment transport in the Mekong delta over three years.'
      const result = reviewDraft(draftWith({ opening: shared, projects: shared }))
      expect(result.findings.some((f) => f.dimension === 'repetition')).toBe(true)
    })

    it('still flags a superlative claim and asks what it is compared with', () => {
      const result = reviewDraft(draftWith({ 'why-programme': 'The best in the world, world-class staff.' }))
      expect(result.claims.some((c) => c.kind === 'superlative')).toBe(true)
    })

    it('keeps the guidance and the findings channels separate for one and the same draft', () => {
      // A written-but-empty section and a triggered finding about a different
      // section: the two lists must not merge into one.
      const whyProgramme =
        'While the course list describes the modules plainly, what draws me here is the field ' +
        'programme described in the second year of the handbook, and the two people whose ' +
        'readings I have been working through since my first semester, because the approach ' +
        'they take to sparse seasonal records is exactly the problem I want to spend three ' +
        'years on. The department gauge archive runs back decades and covers the kind of small ' +
        'mixed agricultural catchments that the published models fit worst, which is where I ' +
        'would like to start. I would bring my own flume calibration records and a starter set ' +
        'of readings from a catchment that nobody has yet fitted a model to properly.'
      const result = reviewDraft(
        draftWith(
          { academic: 'CS.', 'why-programme': whyProgramme },
          { institution: 'University of Waterloo' },
        ),
      )

      expect(wordCount(whyProgramme)).toBeGreaterThanOrEqual(FLOOR['why-programme'])

      // The section id is 'academic-preparation', not 'academic' - the id is
      // looked up from the module rather than typed, so a rename cannot leave
      // this assertion silently matching nothing.
      const academicId = SOP_SECTIONS.find((s) => s.title === 'Academic preparation').id
      const guidanceForAcademic = result.sectionGuidance.filter((e) => e.sectionId === academicId)
      expect(guidanceForAcademic).toHaveLength(1)
      expect(guidanceForAcademic[0].status).toBe('empty')

      const relevance = result.findings.filter((f) => f.dimension === 'relevance')
      expect(relevance).toHaveLength(1)
      expect(relevance[0].sectionId).toBe('why-programme')

      // Neither list contains the other's entries.
      expect(result.findings.some((f) => f.dimension === 'structure')).toBe(false)
      // why-programme cleared its floor, so nothing is pending as thin.
      expect(result.sectionGuidance.some((e) => e.status === 'thin')).toBe(false)
    })

    it('reports no guidance once every section has passed its floor', () => {
      const complete = {
        opening:
          'A wet summer in 2019 at Bristol, spending a fortnight measuring how quickly the ' +
          'Malago rose after a summer storm, is what made me curious about catchment flooding, ' +
          'and I have spent the two years since then trying to understand why the published ' +
          'models were wrong, and what a modeller can honestly say about a gauge record that ' +
          'has gaps in it.',
        // Keyed by the real section id, not by a shorthand: `draftWith` writes
        // straight into the section map, so a key that is not an id silently
        // leaves the real section empty and this test would pass for the wrong
        // reason. The loop below is what catches it.
        'academic-preparation':
          'I read civil engineering at Bristol between 2019 and 2023, graduating with a first, ' +
          'and took fluid mechanics, open channel hydrology, stochastic methods for engineers, ' +
          'and a field course in which we surveyed and modelled a real catchment for a local ' +
          'council. Since then I have taught myself Python and pandas to work with gauge data, ' +
          'which is the one thing a degree did not cover. I completed a short course in spatial ' +
          'statistics and learned to fit a mixed effects model to count data with gaps and ' +
          'clunky entries from three different logging systems.',
        projects:
          'With two colleagues I built a tilting flume in a disused loading bay and ran 412 ' +
          'controlled measurements of bedload transport over a single summer, three days a week, ' +
          'whenever the weather allowed the equipment to stay bolted in place. I was responsible ' +
          'for the sediment feed and the discharge measurements, fitted the calibration myself ' +
          'after the first fortnight produced readings that disagreed with each other by a ' +
          'third, and wrote the two thousand line analysis script that turned raw sensor output ' +
          'into usable numbers. We never got the paper we hoped for out of it, and I still think ' +
          'about which measurement we should have taken instead. The data is still there and two ' +
          'people have asked me for it since, which is more than most of the other work I did ' +
          'that year.',
        'why-programme':
          'Hydrology at the University of Waterloo runs the Grand River field site, which is the ' +
          'one place I know of that publishes hourly gauge records continuously since 1962, and ' +
          'Professor Nkemelu has written the two papers I have read most closely on gap filling ' +
          'in messy count data over the last five years. What I would bring that the group does ' +
          'not already have is three years of hands-on experience with a flume and a set of ' +
          'sensor records from a site nobody has modelled properly yet. In my first year I would ' +
          'want to work on that data rather than on a synthetic corpus, because the failure modes ' +
          'I already know how to spot are the ones that live in a gauge record.',
        goals:
          'I want to be able to model flood risk at catchment scale using the imperfect gauge ' +
          'data that a real agency actually holds, and to be honest in print about how much ' +
          'confidence that model can carry. Whether that ends up in a forecasting service or in ' +
          'research, I do not know yet, and I would rather find out here than decide now. What ' +
          'the programme has to give me is a way to be wrong about a forecast in a way I can ' +
          'measure.',
        conclusion:
          'The flume, the gauges and that summer of disagreeing measurements are all in the same ' +
          'line, and I am asking to be considered for a place on this programme. Everything I ' +
          'have written above is my own work, and I would welcome the chance to do more of it ' +
          'here.',
      }

      for (const section of SOP_SECTIONS) {
        expect(wordCount(complete[section.id])).toBeGreaterThanOrEqual(section.minimumWords)
      }

      const result = reviewDraft(draftWith(complete))
      expect(result.sectionGuidance).toHaveLength(0)
    })
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
