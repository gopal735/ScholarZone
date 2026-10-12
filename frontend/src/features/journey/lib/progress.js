/**
 * Progress, per-step completion and next-action selection.
 *
 * These are pure functions over a normalised journey document, and every rule
 * is written down here rather than inferred from a component. The three rules
 * that matter most:
 *
 * 1. **Progress counts finished work, not visited screens.** Nothing in this
 *    file reads a `visited` or `opened` flag, because there is none. Opening a
 *    module cannot move the number.
 * 2. **Unknown and inapplicable items are excluded, by an explicit rule.** A
 *    document the student has not confirmed applies to them does not count
 *    against them, and a timeline entry with no target date has nothing to
 *    measure. Both exclusions are stated per module below.
 * 3. **Zero countable items is 0%, not 100%.** An empty journey is unfinished,
 *    and reporting 100% would be the worst possible lie.
 *
 * A module with no countable items contributes neither numerator nor
 * denominator, so it cannot drag a partially complete journey down to a figure
 * the student did not earn.
 */

import { APPROACHING_DAYS, personalDateStatus, parseIsoDate, todayIso } from './dates.js'
import { normalizeAmount, amountToNumber } from './money.js'
import { FUNDING_CATEGORY } from './money.js'

export const JOURNEY_STEPS = Object.freeze([
  { id: 'find', module: 'find', index: 1 },
  { id: 'eligibility', module: 'eligibility', index: 2 },
  { id: 'documents', module: 'documents', index: 3 },
  { id: 'timeline', module: 'timeline', index: 4 },
  { id: 'costs', module: 'costs', index: 5 },
  { id: 'sources', module: 'sources', index: 6 },
  { id: 'departure', module: 'departure', index: 7 },
])

const STEP_IDS = new Set(JOURNEY_STEPS.map((step) => step.id))

export function isStep(stepId) {
  return STEP_IDS.has(stepId)
}

/** Trimmed non-empty text, for field-presence checks only. */
function filled(value) {
  return typeof value === 'string' && value.trim() !== ''
}

/**
 * The eligibility field that is always present because it is a select with a
 * default. Counted as unfilled until the student actively chooses something
 * else, otherwise an untouched form contributes to both numerator and
 * denominator.
 */
const ENGLISH_TEST_STATUS_DEFAULT = 'not_taken'

/* ── Per-module rules ─────────────────────────────────────────────────── */

/**
 * Find & Explore: an entry counts once it carries the three fields that make it
 * an identifiable opportunity *and* a trust status the student has actually
 * decided. `needs-review` is deliberately not a completed state: the student has
 * written something down but has not yet said where it came from.
 */
function findModuleCounts(doc) {
  let countable = 0
  let complete = 0
  for (const entry of doc.shortlist) {
    countable += 1
    const decided = filled(entry.name) && filled(entry.country) && filled(entry.degree) && entry.trust !== 'needs-review'
    if (decided) complete += 1
  }
  return { countable, complete }
}

/**
 * Eligibility Readiness: the six fields the student supplies about
 * themselves. Each is individually optional in the UI and collectively
 * countable here, so a partially filled profile measures as partially done.
 * No field is ever pre-filled or inferred.
 *
 * The module contributes **nothing** until the student has entered at least
 * one of those fields. Without that rule an untouched record reports 1 of 6
 * complete — 17% of the whole journey for having opened a form, which is
 * precisely the "progress for merely visiting" behaviour the module is
 * required not to have.
 */
function eligibilityModuleCounts(doc) {
  const fields = [
    doc.eligibility.qualificationLevel,
    doc.eligibility.degreeTitle,
    doc.eligibility.resultsText,
    doc.eligibility.englishTestStatus,
    doc.eligibility.citizenshipNotes,
    doc.eligibility.residencyNotes,
  ]
  const filled = fields.filter((value) => {
    if (value === ENGLISH_TEST_STATUS_DEFAULT) return false
    return typeof value === 'string' ? value.trim() !== '' : false
  })
  if (filled.length === 0) {
    return { countable: 0, complete: 0 }
  }
  return { countable: fields.length, complete: filled.length }
}

/**
 * Document Studio: only confirmed documents count. A template row the student
 * has not yet confirmed is excluded from both numerator and denominator, so
 * seeding a checklist cannot inflate progress and an unexamined row cannot
 * penalise it.
 */
function documentsModuleCounts(doc) {
  let countable = 0
  let complete = 0
  for (const item of doc.documents) {
    if (item.template) continue
    countable += 1
    if (item.progress === 'done') complete += 1
  }
  return { countable, complete }
}

/**
 * Application Timeline: only entries with a personal target date are countable.
 * An entry with no target has no work to measure, and an official deadline is
 * not a substitute: it is a fact from the provider, not a commitment the
 * student made.
 */
function timelineModuleCounts(doc) {
  let countable = 0
  let complete = 0
  for (const entry of doc.timeline) {
    if (!parseIsoDate(entry.personalTarget)) continue
    countable += 1
    if (entry.progress === 'submitted' || entry.progress === 'done') complete += 1
  }
  return { countable, complete }
}

/**
 * Cost Planner: a cost or funding line counts once it has a usable amount, and
 * is complete once it also carries a source label, a source date and a
 * provenance type. A figure with no stated origin is the situation the module
 * exists to surface, so it is counted as incomplete rather than ignored.
 */
function costsModuleCounts(doc) {
  let countable = 0
  let complete = 0
  for (const item of doc.costs.items) {
    const amount = normalizeAmount(item.amount)
    if (!amount.ok) continue
    countable += 1
    const labelled =
      filled(item.sourceLabel) &&
      filled(item.sourceDate) &&
      (item.sourceType === 'official' || item.sourceType === 'user-entered' || item.sourceType === 'estimate')
    if (labelled) complete += 1
  }
  return { countable, complete }
}

/**
 * Official Source Guide: a source counts once it has a name and a readable
 * URL, and is complete only once the student has recorded a check date and a
 * status that is not `unknown`. Clicking "mark as re-checked" advances the date
 * but does not certify the content, so `checked-by-me` is complete and
 * `independently-verified` is the only stronger claim.
 */
function sourcesModuleCounts(doc) {
  let countable = 0
  let complete = 0
  for (const source of doc.sources) {
    if (!filled(source.name) || !filled(source.url)) continue
    countable += 1
    if (filled(source.lastChecked) && source.status !== 'unknown') complete += 1
  }
  return { countable, complete }
}

/**
 * After-Offer & Departure: every remaining task counts, because the student
 * removes a task that does not apply to them. Removing is the documented
 * exclusion mechanism here, which is what keeps this module honest without an
 * "applicable" toggle that nothing would ever set.
 */
function departureModuleCounts(doc) {
  let countable = 0
  let complete = 0
  for (const task of doc.departure) {
    if (filled(task.title)) countable += 1
    if (filled(task.title) && task.progress === 'done') complete += 1
  }
  return { countable, complete }
}

const COUNTERS = {
  find: findModuleCounts,
  eligibility: eligibilityModuleCounts,
  documents: documentsModuleCounts,
  timeline: timelineModuleCounts,
  costs: costsModuleCounts,
  sources: sourcesModuleCounts,
  departure: departureModuleCounts,
}

/** Counts for one step, always shape-stable. */
export function stepCounts(doc, stepId) {
  if (!isStep(stepId)) return { countable: 0, complete: 0 }
  return COUNTERS[stepId](doc)
}

/**
 * Counts for every step, in display order.
 *
 * Returns an object keyed by step id, so a renderer can read any step without
 * recomputing and a test can assert one module in isolation.
 */
export function allStepCounts(doc) {
  const out = {}
  for (const step of JOURNEY_STEPS) {
    out[step.id] = stepCounts(doc, step.id)
  }
  return out
}

/**
 * Overall completion, 0–100.
 *
 * `0` when there is nothing countable at all, which is the empty-journey case
 * and the zero-task case. Rounded to a whole percent because a figure like
 * 33.333% reads as a precision this calculation does not have.
 */
export function overallCompletion(doc) {
  let countable = 0
  let complete = 0
  for (const step of JOURNEY_STEPS) {
    const counts = stepCounts(doc, step.id)
    countable += counts.countable
    complete += counts.complete
  }
  if (countable === 0) return 0
  return Math.round((complete / countable) * 100)
}

/* ── Next actions ─────────────────────────────────────────────────────── */

/**
 * Priority bands for suggested actions.
 *
 * Lower runs first. The order is a judgement about what a student can act on
 * now, and it is deterministic so the same document always produces the same
 * three suggestions:
 *
 *   1. A personal target date that has passed — the only urgency in this
 *      feature, and it is urgency the student created themselves.
 *   2. A live application with no target date — the next thing to decide.
 *   3. A document the student confirmed applies but has not done.
 *   4. A gap in the student's own record.
 *   5. A template row not yet confirmed.
 *   6. A shortlist entry with no decided trust status.
 *   7. A cost figure with no stated origin.
 *   8. A source with no recorded check.
 *   9. A departure task not yet started.
 */
const PRIORITY = {
  overdueTarget: 10,
  missingTarget: 20,
  documentInProgress: 30,
  eligibilityGap: 40,
  unconfirmedDocument: 50,
  shortlistTrust: 60,
  costProvenance: 70,
  sourceUnchecked: 80,
  departureTask: 90,
  emptyShortlist: 5,
}

/**
 * Candidate actions for a document, before ordering and truncation.
 *
 * Each action carries a stable `key`, the step it belongs to, and the params a
 * translation needs. Nothing here formats a user-facing string, so the
 * selection logic is independently testable without the dictionary.
 */
export function candidateActions(doc, referenceIso = todayIso()) {
  const actions = []

  if (doc.shortlist.length === 0) {
    actions.push({ key: 'empty-shortlist', stepId: 'find', priority: PRIORITY.emptyShortlist, params: {} })
  }

  for (const entry of doc.shortlist) {
    if (entry.trust === 'needs-review' && filled(entry.name)) {
      actions.push({
        key: 'shortlist-trust',
        stepId: 'find',
        priority: PRIORITY.shortlistTrust,
        params: { shortlistId: entry.id, name: entry.name.trim() },
      })
    }
  }

  if (!filled(doc.eligibility.qualificationLevel) || !filled(doc.eligibility.degreeTitle) || !filled(doc.eligibility.resultsText)) {
    actions.push({ key: 'eligibility-gap', stepId: 'eligibility', priority: PRIORITY.eligibilityGap, params: {} })
  }

  for (const item of doc.documents) {
    if (item.template) {
      actions.push({
        key: 'unconfirmed-document',
        stepId: 'documents',
        priority: PRIORITY.unconfirmedDocument,
        params: { documentId: item.id, title: item.title.trim() },
      })
      continue
    }
    if (item.progress === 'in_progress' && item.requirement !== 'unconfirmed') {
      actions.push({
        key: 'document-in-progress',
        stepId: 'documents',
        priority: PRIORITY.documentInProgress,
        params: { documentId: item.id, title: item.title.trim(), requirement: item.requirement },
      })
    }
  }

  for (const entry of doc.timeline) {
    const status = personalDateStatus(entry.personalTarget, referenceIso)
    if (status.state === 'overdue') {
      actions.push({
        key: 'overdue-target',
        stepId: 'timeline',
        priority: PRIORITY.overdueTarget,
        params: { timelineId: entry.id, label: entry.label.trim(), days: Math.abs(status.days) },
      })
    } else if (status.state === 'unknown' && filled(entry.label)) {
      actions.push({
        key: 'missing-target',
        stepId: 'timeline',
        priority: PRIORITY.missingTarget,
        params: { timelineId: entry.id, label: entry.label.trim() },
      })
    }
  }

  for (const item of doc.costs.items) {
    const amount = normalizeAmount(item.amount)
    if (!amount.ok) continue
    if (!filled(item.sourceLabel)) {
      actions.push({
        key: 'cost-provenance',
        stepId: 'costs',
        priority: PRIORITY.costProvenance,
        params: { costId: item.id, label: item.label.trim() || 'cost' },
      })
    }
  }

  for (const source of doc.sources) {
    if (!filled(source.name) || !filled(source.url)) continue
    if (!filled(source.lastChecked) || source.status === 'unknown') {
      actions.push({
        key: 'source-unchecked',
        stepId: 'sources',
        priority: PRIORITY.sourceUnchecked,
        params: { sourceId: source.id, name: source.name.trim() },
      })
    }
  }

  for (const task of doc.departure) {
    if (filled(task.title) && task.progress === 'not_started') {
      actions.push({
        key: 'departure-task',
        stepId: 'departure',
        priority: PRIORITY.departureTask,
        params: { departureId: task.id, title: task.title.trim() },
      })
    }
  }

  return actions
}

/**
 * The next three actions, deterministically ordered.
 *
 * Ordering is by priority, then by the order the action was discovered, which
 * is itself document order. `limit` defaults to three and is honoured downward
 * only: a document with two genuine actions returns two, and one with none
 * returns an empty array. An empty array is a valid, meaningful result and is
 * rendered as a calm "nothing needs attention" state rather than padded.
 */
export function nextActions(doc, { limit = 3, referenceIso = todayIso() } = {}) {
  const ordered = [...candidateActions(doc, referenceIso)].sort((a, b) => {
    if (a.priority !== b.priority) return a.priority - b.priority
    return 0
  })
  const rank = new Map()
  candidateActions(doc, referenceIso).forEach((action, index) => rank.set(action.key + JSON.stringify(action.params), index))
  return ordered
    .sort((a, b) => {
      if (a.priority !== b.priority) return a.priority - b.priority
      return (
        (rank.get(a.key + JSON.stringify(a.params)) ?? 0) -
        (rank.get(b.key + JSON.stringify(b.params)) ?? 0)
      )
    })
    .slice(0, Math.max(0, limit))
}

/* ── Checklist summary ────────────────────────────────────────────────── */

/**
 * A per-step summary line for the side rail.
 *
 * `label` is the step's name and `counts` are the module's numerator and
 * denominator. `percent` mirrors `overallCompletion`'s rule for a zero
 * denominator: 0, not 100.
 */
export function checklistSummary(doc) {
  return JOURNEY_STEPS.map((step) => {
    const counts = stepCounts(doc, step.id)
    return {
      stepId: step.id,
      index: step.index,
      countable: counts.countable,
      complete: counts.complete,
      percent: counts.countable === 0 ? 0 : Math.round((counts.complete / counts.countable) * 100),
    }
  })
}

export { APPROACHING_DAYS, FUNDING_CATEGORY, amountToNumber }
