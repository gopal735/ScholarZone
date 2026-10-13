import { useCallback, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import {
  ROUTES_WITHOUT_TUTORIAL,
  TUTORIALS,
  tutorialForRoute,
} from '../lib/registry.js'
import {
  canUseStorage,
  dismissTutorial,
  loadTutorialState,
  undismissTutorial,
} from '../lib/tutorialStorage.js'
import { useSharedTutorialState } from '../state/tutorialsContext.js'

/**
 * `routesOf`, tolerant of a malformed entry.
 *
 * The registry exports its own; this one exists because the search index below
 * walks every tutorial and a throw there would blank the whole Help Center over
 * one bad record. A malformed entry yields no searchable routes rather than a
 * crash.
 */
function routesOf(tutorial) {
  if (!tutorial || typeof tutorial !== 'object') return []
  const routes = Array.isArray(tutorial.routes) ? tutorial.routes.slice() : []
  if (typeof tutorial.route === 'string' && !routes.includes(tutorial.route)) {
    routes.push(tutorial.route)
  }
  return routes.filter((route) => typeof route === 'string')
}

/**
 * The Help Center surface, as one composable piece of state.
 *
 * Split from the pages that render it because three places need the same
 * answers: the `/help` directory, the contextual entry on a feature page, and
 * the tests that assert all three agree. A hook here means the search, the
 * category filter, the dismissal and the audience rule have one implementation
 * rather than one per page.
 *
 * ## What the audience rule is and is not
 *
 * `includeAdmin` decides what the *directory* shows. It is a **visibility**
 * rule, not an authorisation one, and the distinction matters: it exists so an
 * admin guide is not shelved next to scholarship browsing and so an admin item
 * never appears for a reader who is not staff. It grants nothing. The admin
 * routes still resolve their own access server-side, and a non-staff reader who
 * typed `/admin` directly would still be refused there. This hook must not
 * become the thing that decides who may use a page — that would be a second,
 * weaker authority than the server.
 *
 * It defaults to `false`, which is the safe direction, and the tests assert the
 * default keeps admin content out.
 *
 * ## Storage failure is visible, not swallowed
 *
 * Every write is followed by a re-read, and the visible state becomes whatever
 * actually landed. A refused write therefore leaves the previous dismissal
 * state in place — the opposite of what was asked for — so the UI reports
 * `problem` rather than claiming the dismissal took effect.
 */
export function useHelpCenter({ includeAdmin = false } = {}) {
  const [params, setParams] = useSearchParams()

  // Dismissals live in the shared provider, not here. Two components calling
  // this hook each used to hold their own copy: hiding a guide in the panel
  // updated the copy the trigger could not see, so the guide reappeared as if
  // nothing had happened. The local fallback keeps a standalone render working.
  const shared = useSharedTutorialState()
  const [localDraft, setLocalDraft] = useState(() => loadTutorialState().state)
  const [localProblem, setLocalProblem] = useState(() => loadTutorialState().problem)

  const problem = shared ? shared.problem : localProblem

  /** Re-read from storage after a write, so what is shown is what persisted. */
  const refresh = useCallback(() => {
    const loaded = loadTutorialState()
    setLocalDraft(loaded.state)
    setLocalProblem(loaded.problem)
  }, [])

  // Query, category and selection live in the URL rather than in local state.
  // A search someone can share, bookmark or reload is worth more than one that
  // resets on navigation, and it is what lets a feature page link to /help with
  // a category already applied.
  const query = params.get('q') || ''
  const category = params.get('category') || 'all'
  const selectedId = params.get('tutorial') || null

  const setParam = useCallback(
    (key, value) => {
      const next = new URLSearchParams(params)
      if (value === null || value === '' || value === undefined) {
        next.delete(key)
      } else {
        next.set(key, value)
      }
      setParams(next, { replace: true })
    },
    [params, setParams],
  )

  const setQuery = useCallback((value) => setParam('q', value), [setParam])
  const setCategory = useCallback(
    (value) => setParam('category', value === 'all' ? null : value),
    [setParam],
  )
  const setSelectedId = useCallback((value) => setParam('tutorial', value), [setParam])

  /**
   * The visible pool: published tutorials only, minus admin ones unless asked.
   *
   * Filtered *before* search and category, so a category holding only admin
   * guides shows nothing to a public reader rather than a heading with an empty
   * list under it.
   */
  const base = useMemo(() => {
    const published = TUTORIALS.filter((tutorial) => tutorial.status === 'enabled')
    return includeAdmin
      ? published
      : published.filter((tutorial) => tutorial.audience !== 'admin')
  }, [includeAdmin])

  /**
   * Search index over the whole tutorial, not just its title.
   *
   * Searching only titles found the page but not the answer: someone looking
   * for "why was I not matched" needs the mistakes and the limitations prose,
   * which is where that sentence actually lives.
   */
  const searchable = useCallback(
    (tutorial) =>
      [
        tutorial.navLabel,
        ...routesOf(tutorial),
        tutorial.purpose?.en,
        tutorial.purpose?.bn,
        tutorial.whenToUse?.en,
        tutorial.whenToUse?.bn,
        ...(tutorial.steps || []).flatMap((step) => [
          step.title?.en,
          step.title?.bn,
          step.body?.en,
          step.body?.bn,
        ]),
        ...(tutorial.mistakes || []).flatMap((mistake) => [
          mistake.mistake?.en,
          mistake.mistake?.bn,
          mistake.fix?.en,
          mistake.fix?.bn,
        ]),
        ...(tutorial.goals || []),
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase(),
    [],
  )

  const results = useMemo(() => {
    const needle = query.trim().toLowerCase()
    const matched =
      needle === '' ? base : base.filter((tutorial) => searchable(tutorial).includes(needle))
    return category === 'all' ? matched : matched.filter((t) => t.category === category)
  }, [base, category, query, searchable])

  /** Counts per category, so a filter can show a number instead of hiding it. */
  const categoryCounts = useMemo(() => {
    const needle = query.trim().toLowerCase()
    const pool = needle === '' ? base : base.filter((tutorial) => searchable(tutorial).includes(needle))
    const counts = { all: pool.length }
    for (const tutorial of pool) {
      counts[tutorial.category] = (counts[tutorial.category] || 0) + 1
    }
    return counts
  }, [base, query, searchable])

  /** Goal index: the "I want to…" entries that actually have something behind them. */
  const goalIndex = useMemo(() => {
    const needle = query.trim().toLowerCase()
    const pool = needle === '' ? base : base.filter((tutorial) => searchable(tutorial).includes(needle))
    const counts = {}
    for (const tutorial of pool) {
      for (const goal of tutorial.goals || []) {
        counts[goal] = (counts[goal] || 0) + 1
      }
    }
    return counts
  }, [base, query, searchable])

  const selected = useMemo(() => {
    if (!selectedId) return null
    return (
      tutorialForRoute(selectedId) ||
      TUTORIALS.find((tutorial) => tutorial.id === selectedId) ||
      null
    )
  }, [selectedId])

  const isDismissed = useCallback(
    (tutorialId) =>
      shared
        ? shared.isDismissed(tutorialId)
        : localDraft.dismissed?.[tutorialId] === true,
    [shared, localDraft.dismissed],
  )

  const dismiss = useCallback(
    (tutorialId) => (shared ? shared.dismiss(tutorialId) : (refresh(), dismissTutorial(tutorialId))),
    [shared, refresh],
  )

  const reopen = useCallback(
    (tutorialId) => (shared ? shared.reopen(tutorialId) : (refresh(), undismissTutorial(tutorialId))),
    [shared, refresh],
  )

  const open = useCallback((tutorialId) => setSelectedId(tutorialId), [setSelectedId])
  const close = useCallback(() => setSelectedId(null), [setSelectedId])
  const clearSearch = useCallback(() => setParam('q', null), [setParam])

  return {
    // search and filters
    query,
    setQuery,
    clearSearch,
    category,
    setCategory,
    categoryCounts,
    goalIndex,
    // results and selection
    results,
    selected,
    open,
    close,
    // dismissal
    isDismissed,
    dismiss,
    reopen,
    // state reporting
    problem,
    storageAvailable: canUseStorage(),
    excludedRoutes: Array.from(ROUTES_WITHOUT_TUTORIAL),
    routesOf,
  }
}
