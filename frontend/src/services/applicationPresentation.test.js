/**
 * Presentation logic for the application workspace.
 *
 * The refusals are the point of this file. An unknown deadline must never read
 * as "0 days left" - the provider publishing no fixed date means the round is
 * open, and zero days reads as overdue. A null progress must never read as 0% -
 * nothing was measured. Both are easy to get wrong by reaching for a default,
 * and both would mislead a student deciding whether to act.
 */

import { describe, expect, it } from 'vitest'
import {
  availableOutcomes,
  availableTransitions,
  checklistSourceLabel,
  deadlineText,
  deadlineUrgency,
  hasExactDeadline,
  nextActionHint,
  outcomeLabel,
  progressText,
  progressValue,
  stateLabel,
} from '../services/applicationPresentation'

const BASE = {
  id: 1,
  scholarship_id: 42,
  name: 'Rotterdam Scholarship',
  country: 'Netherlands',
  degree: 'Master',
  provider: 'Example University',
  funding: 'Full',
  detail_url: '/scholarships/42',
  official_source_url: 'https://example.org/p',
  state: 'in_progress',
  outcome: 'pending',
  availability: { is_available: true, reason: null },
  deadline_text: 'Applications close 1 August 2026',
  deadline_date: '2026-08-01',
  deadline_precision: 'exact',
  days_remaining: 61,
  is_overdue: false,
  is_actionable: true,
  progress_percent: 50,
  checklist_total: 4,
  checklist_completed: 2,
  next_open_task: 'Prepare your application materials',
  updated_at: '2026-05-20T00:00:00Z',
  version: 3,
}

describe('deadlineText', () => {
  it('uses the engine count', () => {
    expect(deadlineText({ ...BASE, days_remaining: 14 })).toBe('14 days left')
    expect(deadlineText({ ...BASE, days_remaining: 1 })).toBe('1 day left')
    expect(deadlineText({ ...BASE, days_remaining: 0 })).toBe('Closes today')
  })

  it('reports a passed deadline as passed rather than as a negative count', () => {
    expect(deadlineText({ ...BASE, days_remaining: -3, is_overdue: true })).toBe('Deadline has passed')
  })

  it('never renders an unknown deadline as zero days', () => {
    // The single most damaging error available here: a rolling or unpublished
    // deadline would read as overdue.
    expect(deadlineText({ ...BASE, days_remaining: null, deadline_text: 'Reviewed on a rolling basis' })).toBe(
      'Reviewed on a rolling basis',
    )
  })

  it('says so plainly when nothing is published', () => {
    expect(deadlineText({ ...BASE, days_remaining: null, deadline_text: null })).toBe(
      'No fixed date published',
    )
  })
})

describe('deadlineUrgency', () => {
  it('grades the engine count into bands', () => {
    expect(deadlineUrgency({ ...BASE, days_remaining: -1, is_overdue: true })).toBe('overdue')
    expect(deadlineUrgency({ ...BASE, days_remaining: 5 })).toBe('urgent')
    expect(deadlineUrgency({ ...BASE, days_remaining: 25 })).toBe('soon')
    expect(deadlineUrgency({ ...BASE, days_remaining: 90 })).toBe('comfortable')
  })

  it('reports no urgency for a deadline that cannot be counted', () => {
    expect(deadlineUrgency({ ...BASE, days_remaining: null })).toBe('none')
    // Month precision is not day-specific, so it is not "closing soon".
    expect(deadlineUrgency({ ...BASE, days_remaining: 5, deadline_precision: 'month' })).toBe('none')
  })
})

describe('hasExactDeadline', () => {
  it('requires both an exact precision and a count', () => {
    expect(hasExactDeadline({ ...BASE })).toBe(true)
    expect(hasExactDeadline({ ...BASE, deadline_precision: 'month' })).toBe(false)
    expect(hasExactDeadline({ ...BASE, days_remaining: null })).toBe(false)
  })
})

describe('progress', () => {
  it('describes counted tasks only', () => {
    expect(progressText({ ...BASE })).toBe('50% · 2 of 4 tasks')
    expect(progressValue({ ...BASE })).toBe(50)
  })

  it('measures nothing when there is nothing to measure', () => {
    const unmeasured = { ...BASE, progress_percent: null, checklist_total: 0 }
    // Not 0%, and not 100%: no bar at all.
    expect(progressText(unmeasured)).toBeNull()
    expect(progressValue(unmeasured)).toBeNull()
  })

  it('treats a zero total as unmeasured even if a percentage arrived', () => {
    expect(progressValue({ ...BASE, checklist_total: 0 })).toBeNull()
    expect(progressText({ ...BASE, checklist_total: 0 })).toBeNull()
  })

  it('clamps the accessible value', () => {
    expect(progressValue({ ...BASE, progress_percent: 140 })).toBe(100)
    expect(progressValue({ ...BASE, progress_percent: -5 })).toBe(0)
  })
})

describe('nextActionHint', () => {
  it('prefers an open task over advice', () => {
    expect(nextActionHint(BASE)).toBe('Next: Prepare your application materials')
  })

  it('says when everything is done', () => {
    expect(nextActionHint({ ...BASE, next_open_task: null })).toBe('Every tracked task is complete.')
  })

  it('explains an unlisted scholarship instead of offering an action', () => {
    const unlisted = {
      ...BASE,
      availability: { is_available: false, reason: 'This scholarship is no longer listed.' },
    }
    expect(nextActionHint(unlisted)).toBe('This scholarship is no longer listed, so it cannot be applied to.')
  })

  it('guides a submitted application towards its outcome', () => {
    expect(nextActionHint({ ...BASE, state: 'submitted', outcome: 'pending' })).toBe(
      'Submitted. Record the outcome when the provider replies.',
    )
    expect(nextActionHint({ ...BASE, state: 'submitted', outcome: 'accepted' })).toBe(
      'Submitted. Outcome: accepted.',
    )
  })

  it('reports no tasks rather than an empty completion', () => {
    expect(nextActionHint({ ...BASE, next_open_task: null, checklist_total: 0 })).toBe(
      'No tracked tasks for this application.',
    )
  })
})

describe('transition tables', () => {
  it('never offers a reopen out of submitted', () => {
    // The server refuses it, so the interface must not offer it either.
    expect(availableTransitions('submitted')).toEqual(['withdrawn'])
  })

  it('mirrors the server table exactly', () => {
    expect(availableTransitions('saved')).toEqual(['planning', 'in_progress', 'withdrawn'])
    expect(availableTransitions('planning')).toEqual(['saved', 'in_progress', 'withdrawn'])
    expect(availableTransitions('in_progress')).toEqual(['planning', 'submitted', 'withdrawn'])
    expect(availableTransitions('withdrawn')).toEqual(['saved', 'planning'])
  })

  it('offers outcomes only once submitted', () => {
    expect(availableOutcomes('in_progress')).toEqual([])
    expect(availableOutcomes('submitted')).toEqual([
      'pending',
      'accepted',
      'rejected',
      'waitlisted',
      'withdrawn',
    ])
  })
})

describe('labels', () => {
  it('renders the server vocabularies', () => {
    expect(stateLabel('in_progress')).toBe('In progress')
    expect(outcomeLabel('waitlisted')).toBe('Waitlisted')
  })

  it('passes an unknown value through rather than blanking it', () => {
    expect(stateLabel('something_new')).toBe('something_new')
    expect(outcomeLabel('something_new')).toBe('something_new')
  })

  it('distinguishes where a checklist task came from', () => {
    expect(checklistSourceLabel('published_requirement')).toBe('From this provider')
    expect(checklistSourceLabel('match_evidence')).toBe('From your match')
    expect(checklistSourceLabel('generic')).toBe('General preparation step')
  })
})