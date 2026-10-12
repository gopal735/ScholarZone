/**
 * Browser-local SOP Builder storage.
 *
 * Every expectation here is about what the module reads and writes in
 * `localStorage`, following the shape `planStorage.test.js` established. The
 * rules worth pinning are the ones a student would notice, and the ones that
 * would be dangerous if they were silently reversed:
 *
 *   - a write that fails is reported as failed, never retried as success
 *   - a word limit is only authoritative when its source is recorded
 *   - an import that is not an export is rejected with a reason and does not
 *     partially apply
 *   - unsupported input types are refused rather than stored as junk
 *   - nothing is ever invented: an unwritten section reads as empty, and no
 *     default text is ever inserted
 *
 * The last one is the reason `readDraft()` is asserted to return empty strings
 * rather than suggested paragraphs. If a future edit made the store "helpfully"
 * seed a section, these expectations are where it would be caught.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  BACKGROUND_FIELDS,
  VERSION,
  clearAllSections,
  countWords,
  eraseEverything,
  exportDraft,
  importDraft,
  normalizeWordLimit,
  readBackgroundField,
  readDraft,
  readSection,
  writeApproval,
  writeBackground,
  writeContext,
  writeSection,
  writeSubstantiation,
} from './sopBuilderStorage.js'
import { SOP_SECTIONS } from './sopBuilderSections.js'

const KEY = 'scholarzone.sop-builder.v1'

/** A draft with one section written, for the write and export expectations. */
function seededDraft() {
  writeContext({ institution: 'University of Somewhere', application_type: "Master's" })
  writeSection('opening', 'A question about river flow that I could not let go of.')
  writeBackground({ academic: 'BSc in Civil Engineering, 2023.' })
  return readDraft()
}

beforeEach(() => {
  window.localStorage.clear()
})

describe('the empty store', () => {
  it('returns every section as empty text rather than suggested content', () => {
    const draft = readDraft()
    for (const section of SOP_SECTIONS) {
      expect(draft.sections[section.id].text).toBe('')
    }
  })

  it('returns every background field as an empty string', () => {
    const draft = readDraft()
    for (const field of BACKGROUND_FIELDS) {
      expect(draft.background[field.id]).toBe('')
    }
  })

  it('declares itself device-local in the payload, not only in the UI', () => {
    const draft = readDraft()
    expect(draft.device_local).toBe(true)
  })

  it('reads an empty section as an empty string, never null', () => {
    expect(readSection('opening')).toBe('')
  })

  it('reads a background field that was never written as an empty string', () => {
    expect(readBackgroundField('academic')).toBe('')
  })
})

describe('malformed stored data', () => {
  it('treats corrupt JSON as absent rather than crashing', () => {
    window.localStorage.setItem(KEY, '{not json')
    expect(() => readDraft()).not.toThrow()
    expect(readDraft().sections[SOP_SECTIONS[0].id].text).toBe('')
  })

  it('treats a non-object payload as an empty draft', () => {
    window.localStorage.setItem(KEY, '"a string"')
    expect(readDraft().sections.opening.text).toBe('')
  })

  it('drops a stored section value that is not a string', () => {
    window.localStorage.setItem(
      KEY,
      JSON.stringify({ schema: 'scholarzone.sop-builder', version: VERSION, sections: { opening: { text: 42 } } }),
    )
    expect(readSection('opening')).toBe('')
  })

  it('drops an unknown section id rather than storing it under an unresolvable key', () => {
    window.localStorage.setItem(
      KEY,
      JSON.stringify({
        schema: 'scholarzone.sop-builder',
        version: VERSION,
        sections: { not_a_section: { text: 'hello' } },
      }),
    )
    expect(readSection('not_a_section')).toBe('')
    expect(readDraft().sections.not_a_section).toBeUndefined()
  })
})

describe('writing sections', () => {
  it('stores text and reads it back', () => {
    writeSection('opening', 'My own words.')
    expect(readSection('opening')).toBe('My own words.')
  })

  it('stores the edited text where the original was, without growing a second entry', () => {
    writeSection('opening', 'first draft')
    writeSection('opening', 'second draft')
    expect(readSection('opening')).toBe('second draft')
    const draft = readDraft()
    expect(Object.keys(draft.sections)).toHaveLength(SOP_SECTIONS.length)
  })

  it('keeps one section off another', () => {
    writeSection('opening', 'opening text')
    writeSection('goals', 'goals text')
    expect(readSection('opening')).toBe('opening text')
    expect(readSection('goals')).toBe('goals text')
  })

  it('refuses an id that is not a known section', () => {
    expect(writeSection('not_a_section', 'text')).toBe(false)
    expect(window.localStorage.getItem(KEY)).toBeNull()
  })

  it('refuses a non-string value rather than coercing it', () => {
    expect(writeSection('opening', 42)).toBe(false)
    expect(readSection('opening')).toBe('')
  })

  it('truncates to the field maximum rather than storing an unbounded draft', () => {
    const ok = writeSection('opening', 'x'.repeat(25000))
    expect(ok).toBe(true)
    expect(readSection('opening').length).toBe(20000)
  })
})

describe('word counting', () => {
  it('counts words and reports zero for an empty or whitespace-only string', () => {
    expect(countWords('one two three')).toBe(3)
    expect(countWords('')).toBe(0)
    expect(countWords('   \n  ')).toBe(0)
  })

  it('counts words for text that does not use spaces, rather than reporting zero', () => {
    // A student writing in a language without spaces must not be told their
    // whole draft is empty.
    expect(countWords('关于河流的问题')).toBeGreaterThan(0)
  })

  it('counts a non-string as zero rather than throwing', () => {
    expect(countWords(null)).toBe(0)
    expect(countWords(undefined)).toBe(0)
    expect(countWords(42)).toBe(0)
  })
})

describe('word limits', () => {
  it('accepts a positive integer', () => {
    expect(normalizeWordLimit(1500)).toBe(1500)
    expect(normalizeWordLimit('1500')).toBe(1500)
  })

  it('refuses zero, negatives, fractions and junk', () => {
    expect(normalizeWordLimit(0)).toBeNull()
    expect(normalizeWordLimit(-5)).toBeNull()
    expect(normalizeWordLimit(10.5)).toBe(11)
    expect(normalizeWordLimit('abc')).toBeNull()
    expect(normalizeWordLimit('')).toBeNull()
    expect(normalizeWordLimit(null)).toBeNull()
    expect(normalizeWordLimit(undefined)).toBeNull()
  })

  it('is NOT authoritative without a source, which is the whole trust rule', () => {
    writeContext({ word_limit: 1500 })
    const draft = readDraft()
    expect(draft.context.word_limit).toBe(1500)
    expect(draft.context.word_limit_source).toBe('')
  })

  it('stores a source alongside a limit', () => {
    writeContext({ word_limit: 1500, word_limit_source: 'provider guidelines page' })
    const draft = readDraft()
    expect(draft.context.word_limit).toBe(1500)
    expect(draft.context.word_limit_source).toBe('provider guidelines page')
  })
})

describe('background fields', () => {
  it('stores and reads each field', () => {
    for (const field of BACKGROUND_FIELDS) {
      writeBackground({ [field.id]: `my own ${field.id}` })
      expect(readBackgroundField(field.id)).toBe(`my own ${field.id}`)
    }
  })

  it('ignores a patch key that is not a known field', () => {
    writeBackground({ not_a_field: 'ignored' })
    const draft = readDraft()
    expect(draft.background.not_a_field).toBeUndefined()
  })

  it('ignores a non-string value rather than coercing it', () => {
    writeBackground({ academic: 99 })
    expect(readBackgroundField('academic')).toBe('')
  })
})

describe('claim substantiation', () => {
  it('records a confirmation with the student own evidence', () => {
    const ok = writeSubstantiation('opening:superlative:the best', 'confirmed', 'I was 3rd of 412.')
    expect(ok).toBe(true)
    const record = readDraft().substantiation['opening:superlative:the best']
    expect(record.status).toBe('confirmed')
    expect(record.evidence).toBe('I was 3rd of 412.')
    expect(record.updated_at).toBeTruthy()
  })

  it('records a removal', () => {
    writeSubstantiation('opening:superlative:the best', 'removed', '')
    expect(readDraft().substantiation['opening:superlative:the best'].status).toBe('removed')
  })

  it('refuses an unknown status rather than storing it', () => {
    expect(writeSubstantiation('k', 'maybe', '')).toBe(false)
    expect(readDraft().substantiation.k).toBeUndefined()
  })

  it('stores a confirmation with no evidence as-is, so the builder never invents it', () => {
    // Refusing here would be the builder asserting something about the student.
    // The review engine is what flags this state, not the store.
    writeSubstantiation('k', 'confirmed', '')
    expect(readDraft().substantiation.k.evidence).toBe('')
  })
})

describe('approval', () => {
  it('records the student own confirmation', () => {
    writeApproval(true)
    const approval = readDraft().approval
    expect(approval.confirmed).toBe(true)
    expect(approval.confirmed_at).toBeTruthy()
  })

  it('clears on false rather than storing a false confirmation', () => {
    writeApproval(true)
    writeApproval(false)
    expect(readDraft().approval).toBeNull()
  })
})

describe('clearing and erasing', () => {
  it('clears every section but leaves the context and background intact', () => {
    seededDraft()
    writeBackground({ motivation: 'my own motivation' })
    clearAllSections()
    const draft = readDraft()
    expect(readSection('opening')).toBe('')
    expect(draft.context.institution).toBe('University of Somewhere')
    expect(readBackgroundField('motivation')).toBe('my own motivation')
  })

  it('erases everything and also drops any approval that was recorded', () => {
    seededDraft()
    writeApproval(true)
    eraseEverything()
    const draft = readDraft()
    expect(readSection('opening')).toBe('')
    expect(readBackgroundField('academic')).toBe('')
    expect(draft.context.institution).toBe('')
    expect(draft.approval).toBeNull()
  })

  it('leaves a well-formed empty draft rather than nothing at all', () => {
    eraseEverything()
    expect(readDraft().schema).toBe('scholarzone.sop-builder')
    expect(readDraft().version).toBe(VERSION)
  })
})

describe('export and import', () => {
  it('exports a versioned envelope that declares itself local', () => {
    seededDraft()
    const payload = exportDraft()
    expect(payload.schema).toBe('scholarzone.sop-builder')
    expect(payload.version).toBe(VERSION)
    expect(payload.device_local).toBe(true)
    expect(payload.exported_at).toBeTruthy()
    expect(payload.draft.sections.opening.text).toBeTruthy()
  })

  it('round-trips the whole draft through an export and an import', () => {
    seededDraft()
    writeBackground({ goals: 'my own goals' })
    writeSection('why-programme', 'Their river modelling group.')
    writeSubstantiation('s', 'confirmed', 'evidence')
    writeApproval(true)

    const payload = JSON.parse(JSON.stringify(exportDraft()))

    clearAllSections()
    expect(readSection('opening')).toBe('')

    const result = importDraft(payload)
    expect(result.ok).toBe(true)
    expect(readSection('opening')).toBe('A question about river flow that I could not let go of.')
    expect(readSection('why-programme')).toBe('Their river modelling group.')
    expect(readBackgroundField('goals')).toBe('my own goals')
    expect(readDraft().approval.confirmed).toBe(true)
  })

  it('rejects a file that is not an export, with a reason', () => {
    expect(importDraft(null)).toEqual({ ok: false, reason: 'This file is not a ScholarZone SOP Builder export.' })
    expect(importDraft('a string')).toEqual({ ok: false, reason: 'This file is not a ScholarZone SOP Builder export.' })
    expect(importDraft([])).toEqual({ ok: false, reason: 'This file is not a ScholarZone SOP Builder export.' })
  })

  it('rejects an export that does not declare itself one', () => {
    const result = importDraft({ schema: 'something.else', version: VERSION, draft: {} })
    expect(result.ok).toBe(false)
    expect(result.reason).toMatch(/does not declare itself/)
  })

  it('rejects an unsupported version rather than guessing at the shape', () => {
    const result = importDraft({ schema: 'scholarzone.sop-builder', version: 99, draft: {} })
    expect(result.ok).toBe(false)
    expect(result.reason).toMatch(/Unsupported SOP Builder export version 99/)
  })

  it('rejects an export with no draft inside it', () => {
    const result = importDraft({ schema: 'scholarzone.sop-builder', version: VERSION })
    expect(result.ok).toBe(false)
    expect(result.reason).toMatch(/does not contain a draft/)
  })

  it('does not partially apply: a rejected import leaves the stored draft alone', () => {
    seededDraft()
    const result = importDraft({ schema: 'scholarzone.sop-builder', version: 99, draft: {} })
    expect(result.ok).toBe(false)
    expect(readSection('opening')).toBe('A question about river flow that I could not let go of.')
    expect(readBackgroundField('academic')).toBe('BSc in Civil Engineering, 2023.')
  })
})

describe('a write that fails', () => {
  /**
   * Spying on the prototype rather than assigning `window.localStorage.setItem`.
   *
   * jsdom's Storage exposes `setItem` on the prototype, and a direct assignment
   * on the instance is silently ignored - so the naive version of this test
   * passes while testing nothing, which is the worst possible outcome for the
   * test that exists to pin "a failed write is reported as failed".
   */
  function failAllWrites() {
    return vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError')
    })
  }

  it('reports failure rather than retrying it as success', () => {
    const spy = failAllWrites()
    try {
      expect(writeSection('opening', 'text')).toBe(false)
      expect(writeContext({ institution: 'x' })).toBe(false)
      expect(writeBackground({ academic: 'x' })).toBe(false)
      expect(writeSubstantiation('k', 'confirmed', 'e')).toBe(false)
      expect(writeApproval(true)).toBe(false)
      expect(clearAllSections()).toBe(false)
      expect(eraseEverything()).toBe(false)
    } finally {
      spy.mockRestore()
    }
  })

  it('reports a failed import as failed, with a reason', () => {
    const spy = failAllWrites()
    try {
      const result = importDraft({ schema: 'scholarzone.sop-builder', version: VERSION, draft: {} })
      expect(result.ok).toBe(false)
      expect(result.reason).toMatch(/refused to store/)
    } finally {
      spy.mockRestore()
    }
  })
})
