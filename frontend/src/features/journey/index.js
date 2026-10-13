/**
 * Public entry point for the Bangladesh Applicant Journey.
 *
 * Everything the rest of the application needs to mount this feature is
 * re-exported here, so `App.jsx` imports one module rather than reaching into
 * the feature's internals. The provider, the page, the pure logic and the
 * storage service are all part of the feature's contract; its individual
 * components are not.
 */

export { JourneyProvider } from './state/JourneyProvider.jsx'
export { JourneyPage } from './components/JourneyPage.jsx'
export { JOURNEY_ROUTE } from './route.js'

export { journeyReducer, ACTIONS } from './state/journeyReducer.js'
export { useJourney } from './hooks/useJourney.js'
export { useJourneyI18n } from './i18n/useJourneyI18n.js'

export {
  overallCompletion,
  stepCounts,
  allStepCounts,
  nextActions,
  checklistSummary,
  candidateActions,
  JOURNEY_STEPS,
  isStep,
} from './lib/progress.js'

export {
  normalizeAmount,
  normalizeBanglaDigits,
  hasBanglaDigits,
  convertToBdt,
  sumAmounts,
} from './lib/money.js'

export {
  computeCostSummary,
  computeBdtView,
  fundingBySourceType,
} from './lib/costs.js'

export {
  parseIsoDate,
  isIsoDate,
  toIsoDate,
  todayIso,
  daysBetween,
  personalDateStatus,
  officialDeadlineInfo,
  byDateCriterion,
  APPROACHING_DAYS,
} from './lib/dates.js'

export {
  loadJourneyState,
  saveJourneyState,
  resetJourneyStorage,
  buildExport,
  JOURNEY_STORAGE_KEYS,
} from './lib/journeyStorage.js'

export {
  STORAGE_KEY,
  SCHEMA,
  VERSION,
} from './lib/journeySchema.js'

export {
  normalizeJourneyDocument,
  defaultJourneyState,
  migrateJourneyDocument,
} from './lib/journeySchema.js'

export { validateImportPayload, readImportFile, planReplacement } from './lib/journeyImportExport.js'

export { GENERIC_DOCUMENT_TEMPLATE, GENERIC_DEPARTURE_TEMPLATE, SAMPLE_SHORTLIST_ENTRY } from './data/seed.js'
