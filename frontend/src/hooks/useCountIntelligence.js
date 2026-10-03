import { useCallback, useEffect, useRef, useState } from 'react'

import { facetBuckets, fetchCountIntelligence, hasActiveFilters } from '../services/countIntelligence'

/**
 * The sections requested by default.
 *
 * `distributions` is included because the panel offers a "Show the distributions"
 * disclosure, and a disclosure with nothing behind it is worse than no disclosure.
 */
export const DEFAULT_CAPABILITIES = [
  'summary',
  'facets',
  'integrity',
  'explain',
  'zero_result',
  'distributions',
]

/**
 * Count intelligence for a filter state.
 *
 * Three properties this hook is responsible for, all of them about staleness:
 *
 * **No stale counts.** Every response is tagged with the id of the request that
 * produced it. A response that arrives after the reader has moved on is discarded
 * rather than painted over newer state, which is the race that makes a badge read
 * "Germany (5)" above a list of forty cards.
 *
 * **The reader's filters are the API's.** Selecting a filter calls the backend and
 * renders what comes back. Nothing is derived from the previous response, so a
 * facet count can never disagree with the cards it filters.
 *
 * **A failed count is not a zero.** An error is an error and is reported as one.
 * Falling back to counting the rendered list would produce a confident number that
 * nobody can audit.
 *
 * The inactive case, and the loading case, are both *derived* rather than assigned.
 * Storing them means calling `setState` inside the effect body, which forces a
 * second render pass on every keystroke and every reset, and produces state that was
 * a function of the props to begin with. Only a settled response is stored.
 */
const EMPTY = { data: null, error: null }

export function useCountIntelligence(profile, filters, { enabled = true, asOf } = {}) {
  const [state, setState] = useState(EMPTY)
  const requestId = useRef(0)

  const active = enabled && Boolean(profile) && hasActiveFilters(filters)

  // The stored response for the current filter state.
  const intelligence = active ? state.data : null
  const error = active ? state.error : null
  const status = !active ? 'idle' : error ? 'error' : intelligence ? 'ready' : 'loading'

  useEffect(() => {
    // With nothing filtered, the Match response already carries authoritative
    // counts, so there is nothing to ask for. Skipping the request keeps the default
    // view free of an extra round trip.
    if (!active) return undefined

    const id = ++requestId.current
    let cancelled = false

    fetchCountIntelligence(profile, filters, { asOf })
      .then((response) => {
        // A response for a superseded filter state is discarded rather than painted
        // over the current one. That race is what puts a stale facet count above a
        // list it no longer describes.
        if (cancelled || id !== requestId.current) return
        setState({ data: response, error: null })
      })
      .catch((caught) => {
        if (cancelled || id !== requestId.current) return
        setState({ data: null, error: caught })
      })

    return () => {
      cancelled = true
    }
  }, [active, profile, filters, asOf])

  const reset = useCallback(() => {
    // Invalidate any in-flight response so it cannot repaint after a reset.
    requestId.current += 1
    setState(EMPTY)
  }, [])

  return {
    active,
    intelligence,
    status,
    error,
    isLoading: status === 'loading',
    /** The API's count of records surviving the active filters. Null when unknown. */
    matched: intelligence?.results?.matched ?? null,
    facets: facetBuckets(intelligence, 'countries'),
    alternatives: intelligence?.zero_result?.alternatives ?? [],
    integrity: intelligence?.integrity ?? null,
    explanations: intelligence?.explanations ?? null,
    reset,
  }
}

export default useCountIntelligence