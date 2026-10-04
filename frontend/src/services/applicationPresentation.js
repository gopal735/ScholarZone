/**
 * Turning application state into words.
 *
 * Every function here is a label or a formatting decision. The deadline counts,
 * progress figures and state values all arrive computed from the server, and
 * this file only chooses how to write them down.
 *
 * Two refusals matter more than the labels. An unknown deadline is never
 * rendered as "0 days left", because the provider publishing no fixed date means
 * the round is open, and "0 days" reads as overdue. And a null progress is
 * rendered as unmeasured, never as 0%, because nothing was measured.
 */

const STATE_LABELS = {
  saved: 'Saved',
  planning: 'Planning',
  in_progress: 'In progress',
  submitted: 'Submitted',
  withdrawn: 'Withdrawn',
}

const OUTCOME_LABELS = {
  pending: 'No response yet',
  accepted: 'Accepted',
  rejected: 'Not successful',
  waitlisted: 'Waitlisted',
  withdrawn: 'Withdrawn',
}

export function stateLabel(state) {
  return STATE_LABELS[state] || state
}

export function outcomeLabel(outcome) {
  return OUTCOME_LABELS[outcome] || outcome
}

/**
 * A deadline for a person.
 *
 * `days_remaining` comes from the matching engine's own evaluator and is null
 * for a rolling, recurring or unpublished deadline. That is an open round, so it
 * shows the provider's own wording rather than a countdown.
 */
export function deadlineText(application) {
  if (typeof application.days_remaining === 'number') {
    if (application.is_overdue) return 'Deadline has passed'
    if (application.days_remaining === 0) return 'Closes today'
    if (application.days_remaining === 1) return '1 day left'
    return `${application.days_remaining} days left`
  }
  if (application.deadline_text) return application.deadline_text
  return 'No fixed date published'
}

/** True when the day count is precise enough to act on. */
export function hasExactDeadline(application) {
  return application.deadline_precision === 'exact' && typeof application.days_remaining === 'number'
}

/** Whether the deadline needs saying loudly. Never colour alone downstream. */
export function deadlineUrgency(application) {
  if (application.is_overdue) return 'overdue'
  if (!hasExactDeadline(application)) return 'none'
  if (application.days_remaining <= 14) return 'urgent'
  if (application.days_remaining <= 30) return 'soon'
  return 'comfortable'
}

/**
 * Progress as a person reads it.
 *
 * Returns null when nothing was measured - no counted tasks - so the interface
 * can say "no tracked tasks" rather than rendering an empty bar beside the word
 * "complete".
 */
export function progressText(application) {
  const percent = application.progress_percent
  if (typeof percent !== 'number') return null
  const done = application.checklist_completed
  const total = application.checklist_total
  if (total === 0) return null
  return `${Math.round(percent)}% · ${done} of ${total} tasks`
}

/** The bar's accessible value, or null when there is nothing to measure. */
export function progressValue(application) {
  if (typeof application.progress_percent !== 'number') return null
  if (application.checklist_total === 0) return null
  return Math.max(0, Math.min(100, Math.round(application.progress_percent)))
}

/**
 * What to do next, from the state the server reported.
 *
 * Deliberately not a priority engine. It reads the one thing that is true and
 * actionable about this application right now, and prefers an open task over any
 * advice, because an outstanding task is more concrete than a suggestion.
 */
export function nextActionHint(application) {
  if (!application.availability.is_available) {
    return 'This scholarship is no longer listed, so it cannot be applied to.'
  }
  if (application.state === 'withdrawn') {
    return 'You withdrew this application. You can reopen it while the round is open.'
  }
  if (application.state === 'submitted') {
    return application.outcome === 'pending'
      ? 'Submitted. Record the outcome when the provider replies.'
      : `Submitted. Outcome: ${outcomeLabel(application.outcome).toLowerCase()}.`
  }
  if (application.next_open_task) {
    return `Next: ${application.next_open_task}`
  }
  if (application.checklist_total === 0) {
    return 'No tracked tasks for this application.'
  }
  if (application.is_overdue) {
    return 'The deadline has passed. Withdraw the application or check whether the round reopened.'
  }
  return 'Every tracked task is complete.'
}

/**
 * Whether a state change is worth offering.
 *
 * The list is the server's transition table, restated for the select element, so
 * the interface cannot offer a move the API will refuse. Deriving it here rather
 * than hard-coding a second list means an illegal transition is unreachable from
 * the UI as well as rejected by the API.
 */
export const STATE_TRANSITIONS = {
  saved: ['planning', 'in_progress', 'withdrawn'],
  planning: ['saved', 'in_progress', 'withdrawn'],
  in_progress: ['planning', 'submitted', 'withdrawn'],
  submitted: ['withdrawn'],
  withdrawn: ['saved', 'planning'],
}

export function availableTransitions(state) {
  return STATE_TRANSITIONS[state] || []
}

/** Outcomes are only meaningful once submitted, so only offered then. */
export function availableOutcomes(state) {
  if (state !== 'submitted') return []
  return ['pending', 'accepted', 'rejected', 'waitlisted', 'withdrawn']
}

/** Where a checklist task came from, for the reader who wants to know why. */
export function checklistSourceLabel(source) {
  switch (source) {
    case 'published_requirement':
      return 'From this provider'
    case 'match_evidence':
      return 'From your match'
    case 'lifecycle':
      return 'From the application stage'
    default:
      return 'General preparation step'
  }
}