/**
 * Route → tutorial id, without the prose.
 *
 * Split from `registry.js` so a feature page can learn *whether* it has a
 * tutorial without downloading every tutorial's text. `HowToUse` is mounted on
 * seven pages, so importing the full registry there pulled 138 kB of two-language
 * prose into the initial bundle for every reader, including the ones who never
 * open a guide. The prose is loaded when a guide is actually opened.
 *
 * Kept as data rather than derived from `App.jsx`: the router is not importable
 * from here, and a test that re-parsed the route file would be testing its own
 * regex rather than the catalogue.
 */

/**
 * Every route the app declares, and the tutorial that covers it.
 *
 * `tutorial` is null where a route deliberately has no tutorial. A dynamic
 * segment is listed with its placeholder, exactly as the router declares it.
 */
export const ROUTES = Object.freeze({
  '/': { tutorial: 'home', audience: 'public' },
  '/countries': { tutorial: 'countries', audience: 'public' },
  '/scholarships': { tutorial: 'scholarships', audience: 'public' },
  '/match': { tutorial: 'match', audience: 'public' },
  '/scholarships/:id': { tutorial: 'scholarship-details', audience: 'public' },
  '/login': { tutorial: 'account', audience: 'public' },
  '/register': { tutorial: 'account', audience: 'public' },
  '/saved': { tutorial: 'saved', audience: 'public' },
  '/plan': { tutorial: 'plan', audience: 'public' },
  '/statement': { tutorial: 'statement', audience: 'public' },
  '/dashboard': { tutorial: 'dashboard', audience: 'auth' },
  '/applications': { tutorial: 'applications', audience: 'auth' },
  '/applications/:applicationId': { tutorial: 'applications', audience: 'auth' },
  '/mentor': { tutorial: 'mentor', audience: 'auth' },
  '/compare': { tutorial: 'compare', audience: 'public' },
  '/bangladesh-journey': { tutorial: 'bangladesh-journey', audience: 'public' },
  '/bangladesh-journey/:stepId': { tutorial: 'bangladesh-journey', audience: 'public' },
  '/admin': { tutorial: 'admin', audience: 'admin' },
  '/admin/verification': { tutorial: 'admin', audience: 'admin' },
  '/admin/scholarships': { tutorial: 'admin', audience: 'admin' },
  // Behind the feature's own `enabled` flag, which is committed false. Listed so
  // the audit shows the route exists and is deliberately uncovered: it renders
  // the not-found page, and a tutorial telling a reader to visit it would be
  // sending them somewhere useful-looking that returns 404.
  '/consistency-review': { tutorial: null, audience: 'public', disabled: true },
})

/**
 * Routes with a disabled feature that has no tutorial while it is off.
 *
 * A test asserts this list, so enabling the flag produces a coverage failure
 * rather than a stale guide.
 */
export const ROUTES_WITHOUT_TUTORIAL = Object.freeze(
  Object.entries(ROUTES)
    .filter(([, entry]) => entry.tutorial === null)
    .map(([route]) => route),
)

/** The tutorial id for a route, or null. */
export function tutorialIdForRoute(route) {
  if (typeof route !== 'string') return null
  return ROUTES[route]?.tutorial ?? null
}

/** Whether a route has a published tutorial at all. */
export function routeHasTutorial(route) {
  return tutorialIdForRoute(route) !== null
}

/** The audience a route declares, or null for an unknown route. */
export function audienceForRoute(route) {
  if (typeof route !== 'string') return null
  return ROUTES[route]?.audience ?? null
}
