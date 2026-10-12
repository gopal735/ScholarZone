/**
 * The reducer for the Bangladesh Applicant Journey.
 *
 * Every transition is an explicit, named action against a normalised document,
 * so a state change can be reasoned about without reading a component. Two
 * rules hold throughout:
 *
 * - **Nothing is mutated.** Each case returns a new document, and every nested
 *   collection is rebuilt rather than edited in place, so React sees a changed
 *   reference and a later change cannot corrupt an earlier one.
 * - **Ids are re-issued on collision at the schema layer.** The reducer does not
 *   look for duplicate ids; `normalizeJourneyDocument` has already done it by the
 *   time a document reaches state.
 */

import {
  defaultJourneyState,
  normalizeJourneyDocument,
  makeId,
  normalizeShortlistEntry,
  normalizeDocument,
  normalizeTimelineEntry,
  normalizeCostItem,
  normalizeSource,
  normalizeDepartureTask,
} from '../lib/journeySchema.js'

/**
 * Stamp a record with a fresh `updatedAt`.
 *
 * An ISO timestamp identifies the edit; it is never rendered as a date without
 * a date field alongside it, so a reader cannot mistake it for the student's own
 * deadline.
 */
function stamp(record) {
  const now = new Date().toISOString()
  return { ...record, updatedAt: now, createdAt: record.createdAt || now }
}

/**
 * Build a new record in the canonical shape.
 *
 * Running the payload through the module's own normaliser is what makes a
 * freshly added entry byte-identical in shape to one that came back from
 * storage: a component reading `entry.deadlineNote` sees `''` rather than
 * `undefined`, and a partial action cannot create a record with holes in it.
 */
function createRecord(prefix, payload, normalise) {
  const withId = { id: makeId(prefix), ...payload }
  return stamp(normalise(withId))
}

/** Inserted at the top of a list so the newest entry is seen first. */
function prepend(list, entry) {
  return [entry, ...list]
}

/**
 * Replace one record, merging the changes onto it.
 *
 * The merge is the point: every `*_UPDATE` action carries a partial, and a
 * replace rather than a merge would drop the fields the partial did not
 * mention — so editing a status would silently blank the record's name, its
 * source URL and its other date. `stamp` then refreshes `updatedAt` and leaves
 * `createdAt` alone, so a record's age survives an edit.
 */
function replaceById(list, id, changes) {
  return list.map((item) =>
    item.id === id ? stamp({ ...item, ...(typeof changes === 'function' ? changes(item) : changes) }) : item,
  )
}

export const ACTIONS = Object.freeze({
  HYDRATE: 'journey/hydrate',
  SET_LANGUAGE: 'journey/set-language',
  RESET: 'journey/reset',

  SHORTLIST_ADD: 'journey/shortlist-add',
  SHORTLIST_UPDATE: 'journey/shortlist-update',
  SHORTLIST_REMOVE: 'journey/shortlist-remove',
  SHORTLIST_TOGGLE_SHORTLISTED: 'journey/shortlist-toggle-shortlisted',

  ELIGIBILITY_SET: 'journey/eligibility-set',

  DOCUMENTS_ADD: 'journey/documents-add',
  DOCUMENTS_UPDATE: 'journey/documents-update',
  DOCUMENTS_REMOVE: 'journey/documents-remove',

  TIMELINE_ADD: 'journey/timeline-add',
  TIMELINE_UPDATE: 'journey/timeline-update',
  TIMELINE_REMOVE: 'journey/timeline-remove',

  COSTS_ADD: 'journey/costs-add',
  COSTS_UPDATE: 'journey/costs-update',
  COSTS_REMOVE: 'journey/costs-remove',
  COSTS_SET_RATE: 'journey/costs-set-rate',

  SOURCES_ADD: 'journey/sources-add',
  SOURCES_UPDATE: 'journey/sources-update',
  SOURCES_REMOVE: 'journey/sources-remove',
  SOURCES_SET_CHECKED: 'journey/sources-set-checked',

  DEPARTURE_ADD: 'journey/departure-add',
  DEPARTURE_UPDATE: 'journey/departure-update',
  DEPARTURE_REMOVE: 'journey/departure-remove',
})

export function journeyReducer(state, action) {
  switch (action.type) {
    case ACTIONS.HYDRATE:
      return normalizeJourneyDocument(action.payload)

    case ACTIONS.SET_LANGUAGE:
      return {
        ...state,
        settings: { ...state.settings, language: action.payload },
      }

    case ACTIONS.RESET:
      return defaultJourneyState()

    /* ── Module 1 ── */
    case ACTIONS.SHORTLIST_ADD: {
      const entry = createRecord('short', action.payload, normalizeShortlistEntry)
      return { ...state, shortlist: prepend(state.shortlist, entry) }
    }
    case ACTIONS.SHORTLIST_UPDATE:
      return { ...state, shortlist: replaceById(state.shortlist, action.payload.id, action.payload.changes) }
    case ACTIONS.SHORTLIST_REMOVE:
      return { ...state, shortlist: state.shortlist.filter((item) => item.id !== action.payload.id) }

    /* ── Module 2 ── */
    case ACTIONS.ELIGIBILITY_SET:
      return { ...state, eligibility: { ...state.eligibility, ...action.payload } }

    /* ── Module 3 ── */
    case ACTIONS.DOCUMENTS_ADD: {
      const entry = createRecord('doc', action.payload, normalizeDocument)
      return { ...state, documents: prepend(state.documents, entry) }
    }
    case ACTIONS.DOCUMENTS_UPDATE:
      return { ...state, documents: replaceById(state.documents, action.payload.id, action.payload.changes) }
    case ACTIONS.DOCUMENTS_REMOVE:
      return { ...state, documents: state.documents.filter((item) => item.id !== action.payload.id) }

    /* ── Module 4 ── */
    case ACTIONS.TIMELINE_ADD: {
      const entry = createRecord('tl', action.payload, normalizeTimelineEntry)
      return { ...state, timeline: prepend(state.timeline, entry) }
    }
    case ACTIONS.TIMELINE_UPDATE:
      return { ...state, timeline: replaceById(state.timeline, action.payload.id, action.payload.changes) }
    case ACTIONS.TIMELINE_REMOVE:
      return { ...state, timeline: state.timeline.filter((item) => item.id !== action.payload.id) }

    /* ── Module 5 ── */
    case ACTIONS.COSTS_ADD: {
      const entry = createRecord('cost', action.payload, normalizeCostItem)
      return { ...state, costs: { ...state.costs, items: prepend(state.costs.items, entry) } }
    }
    case ACTIONS.COSTS_UPDATE:
      return {
        ...state,
        costs: { ...state.costs, items: replaceById(state.costs.items, action.payload.id, action.payload.changes) },
      }
    case ACTIONS.COSTS_REMOVE:
      return {
        ...state,
        costs: { ...state.costs, items: state.costs.items.filter((item) => item.id !== action.payload.id) },
      }
    case ACTIONS.COSTS_SET_RATE:
      return { ...state, costs: { ...state.costs, rate: { ...state.costs.rate, ...action.payload } } }

    /* ── Module 6 ── */
    case ACTIONS.SOURCES_ADD: {
      const entry = createRecord('src', action.payload, normalizeSource)
      return { ...state, sources: prepend(state.sources, entry) }
    }
    case ACTIONS.SOURCES_UPDATE:
      return { ...state, sources: replaceById(state.sources, action.payload.id, action.payload.changes) }
    case ACTIONS.SOURCES_REMOVE:
      return { ...state, sources: state.sources.filter((item) => item.id !== action.payload.id) }
    case ACTIONS.SOURCES_SET_CHECKED:
      return {
        ...state,
        sources: replaceById(state.sources, action.payload.id, { lastChecked: action.payload.date }),
      }

    /* ── Module 7 ── */
    case ACTIONS.DEPARTURE_ADD: {
      const entry = createRecord('dep', action.payload, normalizeDepartureTask)
      return { ...state, departure: prepend(state.departure, entry) }
    }
    case ACTIONS.DEPARTURE_UPDATE:
      return { ...state, departure: replaceById(state.departure, action.payload.id, action.payload.changes) }
    case ACTIONS.DEPARTURE_REMOVE:
      return { ...state, departure: state.departure.filter((item) => item.id !== action.payload.id) }

    default:
      return state
  }
}
