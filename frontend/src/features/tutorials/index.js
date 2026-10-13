/**
 * Tutorials & Help Center — the feature module's public surface.
 *
 * Two entry points, deliberately separate:
 *
 *   - `HelpCenterPage` is the directory at `/help`, lazy-loaded because it is
 *     the heaviest thing in the feature and a reader who never opens it should
 *     not pay for the registry's prose in the initial bundle;
 *   - `HowToUse` is the contextual entry mounted on a feature page, and it is
 *     tiny — it reads one tutorial from the registry and renders it.
 *
 * `useHelpCenter` is exported so the tests, and any future surface, can drive
 * the same search and dismissal state the page drives.
 */

export { default as HelpCenterPage } from './HelpCenterPage.jsx'
export { HowToUse } from './components/HowToUse.jsx'
export { TutorialDetail } from './components/TutorialDetail.jsx'
export { useHelpCenter } from './hooks/useHelpCenter.js'
export { useTutorialsI18n } from './i18n/useTutorialsI18n.js'
export { TutorialLanguageProvider } from './state/TutorialLanguageContext.jsx'
export { LANGUAGE_MODES, translate } from './i18n/strings.js'

export {
  AUDIENCE,
  CATEGORY_ORDER,
  FEATURE_STATUS,
  KNOWN_GOALS,
  ROUTES,
  ROUTES_WITHOUT_TUTORIAL,
  TUTORIALS,
  adminTutorials,
  publicTutorials,
  routesOf,
  tutorialForRoute,
  tutorialsForGoal,
  tutorialsInCategory,
  validateRegistry,
} from './lib/registry.js'

export {
  TUTORIAL_STORAGE_KEYS,
  canUseStorage,
  dismissTutorial,
  undismissTutorial,
} from './lib/tutorialStorage.js'
export { SCHEMA, VERSION } from './lib/tutorialSchema.js'
