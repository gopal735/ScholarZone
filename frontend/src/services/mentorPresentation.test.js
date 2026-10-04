/**
 * The mentor's wording.
 *
 * These are the assertions that keep the interface from telling a small lie: an
 * unknown deadline is never a count of zero, an unmeasured value is never a
 * score of zero, and an answer with nothing measured in it is never presented
 * as ScholarZone verified data.
 */

import { describe, expect, it } from 'vitest'

import {
  deadlineText,
  evidenceTone,
  isClosedDeadline,
  isGrounded,
  isUnmeasured,
  priorityText,
  progressText,
  providerText,
  sourceLabel,
  SOURCE_GUIDANCE,
  SOURCE_VERIFIED,
} from './mentorPresentation'

describe('source labelling', () => {
  it('calls an answer with evidence verified data', () => {
    expect(sourceLabel({ known: [{ key: 'a' }], general_guidance_only: false })).toBe(
      SOURCE_VERIFIED,
    )
  })

  it('refuses to call an ungrounded answer verified data', () => {
    expect(sourceLabel({ known: [], general_guidance_only: false })).toBe(SOURCE_GUIDANCE)
    expect(sourceLabel({ known: [{ key: 'a' }], general_guidance_only: true })).toBe(
      SOURCE_GUIDANCE,
    )
    expect(sourceLabel(null)).toBe(SOURCE_GUIDANCE)
  })

  it('knows when an answer is grounded', () => {
    expect(isGrounded({ known: [{ key: 'a' }] })).toBe(true)
    expect(isGrounded({ known: [] })).toBe(false)
    expect(isGrounded(null)).toBe(false)
  })
})

describe('deadlines', () => {
  it('never turns a missing deadline into zero days', () => {
    expect(deadlineText('')).not.toMatch(/0 days/)
    expect(deadlineText(null)).not.toMatch(/0 days/)
    expect(deadlineText(undefined)).toMatch(/no published deadline/i)
  })

  it('passes a real count through unchanged', () => {
    expect(deadlineText('12 days left.')).toBe('12 days left.')
  })

  it('recognises a closed round', () => {
    expect(isClosedDeadline('Closed - the published date passed 30 days ago.')).toBe(true)
    expect(isClosedDeadline('12 days left.')).toBe(false)
  })
})

describe('progress', () => {
  it('reports an unmeasured checklist as unmeasured rather than zero', () => {
    expect(progressText(null)).toBe('Not measured')
    expect(progressText(undefined)).toBe('Not measured')
    expect(progressText(null)).not.toMatch(/0/)
  })

  it('reports a real percentage', () => {
    expect(progressText(17)).toBe('17% of counted tasks complete')
    expect(progressText(11.1)).toBe('11.1% of counted tasks complete')
  })

  it('knows the difference between absent and zero', () => {
    expect(isUnmeasured(null)).toBe(true)
    expect(isUnmeasured(0)).toBe(false)
  })
})

describe('evidence tone', () => {
  it('pairs each tone with a word the interface also renders', () => {
    expect(evidenceTone({ verification: 'Verified' })).toBe('success')
    expect(evidenceTone({ verification: 'Confirm with provider' })).toBe('warning')
    expect(evidenceTone({ verification: 'No longer listed' })).toBe('muted')
    expect(evidenceTone(null)).toBe('neutral')
  })
})

describe('priority wording', () => {
  it('names the band rather than implying a score', () => {
    expect(priorityText(10)).toBe('Start here')
    expect(priorityText(20)).toBe('In progress')
    expect(priorityText(50)).toBe('Closing soon')
    expect(priorityText(90)).toBe('When you have time')
  })

  it('falls back rather than rendering NaN', () => {
    expect(priorityText('nonsense')).toBe('Suggested')
  })
})

describe('provider wording', () => {
  it('is honest that the default answer is composed from records', () => {
    expect(providerText('disabled', false)).toBe('Composed from ScholarZone records')
  })

  it('only claims assistance when assistance was actually used', () => {
    expect(providerText('configured', true)).toBe('Composed with assistance')
    expect(providerText('configured', false)).toBe('Composed from ScholarZone records')
  })
})