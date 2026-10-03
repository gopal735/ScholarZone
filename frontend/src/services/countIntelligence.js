/**
 * Count Intelligence 2.0 client.
 *
 * One request, one response. Results, summary, facets, integrity, provenance,
 * explanations and zero-result alternatives all arrive together, computed by the
 * backend over a single candidate set.
 *
 * The rule this module exists to enforce: the frontend performs no business
 * counting. There is no `results.filter(...).length` anywhere in the Match surface
 * for a number a reader sees. Filtering a list to decide which cards to render is
 * fine - that is rendering. Deciding how many scholarships exist in a country is
 * the counting engine's job, and reimplementing it here is how a facet badge and a
 * result count drift apart by one.
 *
 * What the frontend may do locally, and does: select which cards are highlighted,
 * and remember what the reader picked. Both are UI state with no business meaning.
 */

import { profilePayload } from './matchService'

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

export class CountApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'CountApiError'
    this.status = status
  }
}

/**
 * The dimensions the API accepts, keyed the way `matchFilterConfig` names them.
 *
 * Values are sent verbatim: a degree string is a published string, and a country
 * name is a country name. Nothing is normalised or title-cased on the way out,
 * because the backend matches them against what the catalogue actually stores.
 */
export function filtersToRequest(filters) {
  // The filter controls are single-value selects, so a selected dimension arrives as
  // a bare string; the API takes a list per dimension. Normalising here is what keeps
  // the two vocabularies apart - and getting it wrong is silent, because an empty
  // list is a perfectly valid request that simply describes no filter at all.
  const compact = (value) => {
    if (Array.isArray(value)) return value.filter(Boolean)
    if (typeof value === 'string' && value !== '') return [value]
    return []
  }
  const one = (value) => (value === '' || value === undefined || value === null ? null : value)

  return {
    countries: compact(filters.country),
    region: one(filters.region),
    degree: compact(filters.degree),
    field: compact(filters.field),
    funding: compact(filters.funding),
    eligibility: compact(filters.eligibility),
    fit: compact(filters.fit),
    confidence: compact(filters.confidence),
    coverage: compact(filters.coverage),
    readiness: compact(filters.readiness),
    deadline: compact(filters.deadline),
  }
}

/**
 * Whether anything is actually constrained.
 *
 * Used to skip the request entirely when no filter is active, so the common case
 * costs nothing and cannot be made slow by a redundant round trip.
 */
export function hasActiveFilters(filters) {
  const request = filtersToRequest(filters)
  return (
    request.region !== null ||
    Object.entries(request).some(([key, value]) => key !== 'region' && Array.isArray(value) && value.length > 0)
  )
}

/**
 * Fetch counts, facets and zero-result help for a filter state.
 *
 * `capabilities` selects which sections are computed. The default set is the one a
 * reader needs on the first screen: the summary, the facets with self-exclusion,
 * the integrity verdict, and the explanation of the headline number.
 */
export async function fetchCountIntelligence(
  profile,
  filters,
  { capabilities, asOf, signal } = {},
) {
  const sections = capabilities ?? [
    'summary',
    'facets',
    'integrity',
    'explain',
    'zero_result',
    'distributions',
  ]

  const query = asOf ? `?as_of=${encodeURIComponent(asOf)}` : ''

  const response = await fetch(`${apiBaseUrl}/v2/counts/intelligence${query}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal,
    body: JSON.stringify({
      // The same translation the Match endpoint uses. The counting endpoint accepts
      // the identical profile body, and a second translation of one form would drift.
      profile: profilePayload(profile),
      filters: filtersToRequest(filters),
      capabilities: sections,
    }),
  })

  if (!response.ok) {
    throw new CountApiError('Could not load counts for these filters.', response.status)
  }
  return response.json()
}

/** The complete count contract, for anything that needs to check a number. */
export async function fetchCountContract({ signal } = {}) {
  const response = await fetch(`${apiBaseUrl}/v2/counts/contract`, { signal })
  if (!response.ok) {
    throw new CountApiError('Could not load the count contract.', response.status)
  }
  return response.json()
}

/**
 * Read one bucket from the API's facet payload.
 *
 * The API names buckets with `key`; the Match response names them with `value`. This
 * is the one place that difference is handled, so no component has to know it.
 */
export function facetBuckets(intelligence, family) {
  return intelligence?.facets?.families?.[family] ?? []
}

/**
 * The count a facet badge shows.
 *
 * Reads the API's count. It never counts anything itself, including when the value
 * is absent - a missing bucket means zero records carried that value, which the API
 * omits deliberately rather than publishing a zero nobody clicked.
 */
export function facetCount(intelligence, family, key) {
  const bucket = facetBuckets(intelligence, family).find((item) => item.key === key)
  return bucket?.count ?? 0
}