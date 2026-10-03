/**
 * Filter groups, derived from the facets the API returns.
 *
 * The values are never hardcoded here. A hardcoded list drifts from the engine:
 * a new funding state or a new fit band would appear in the data and not in the
 * picker, which is indistinguishable from a value that does not exist. So each
 * group names the facet it reads and takes its options from that facet, with the
 * counts the API computed over the same result set the cards render from.
 */

export const FILTER_GROUPS = [
  {
    key: 'eligibility',
    label: 'Eligibility',
    facet: 'eligibility_states',
    read: (result) => result.eligibility,
  },
  {
    key: 'fit',
    label: 'Fit',
    facet: 'fit_bands',
    read: (result) => result.fit_label,
  },
  {
    key: 'funding',
    label: 'Funding',
    facet: 'funding_states',
    read: (result) => result.funding_state,
  },
  {
    key: 'country',
    label: 'Country',
    facet: 'countries',
    read: (result) => result.country,
  },
  {
    key: 'degree',
    label: 'Degree',
    facet: 'degree_levels',
    read: (result) => result.degree_levels,
  },
  {
    key: 'confidence',
    label: 'Confidence',
    facet: 'confidence_bands',
    read: (result) => result.confidence_label,
  },
  {
    key: 'deadline',
    label: 'Deadline',
    facet: 'deadline_buckets',
    read: (result) => result.timing_bucket,
  },
]

export const FILTER_GROUP_BY_KEY = Object.fromEntries(
  FILTER_GROUPS.map((group) => [group.key, group]),
)

export function facetLabel(facets, groupKey, value) {
  const group = FILTER_GROUP_BY_KEY[groupKey]
  if (!group || !facets) return value
  const bucket = (facets[group.facet] ?? []).find((item) => item.value === value)
  return bucket?.label ?? value
}

export function facetOptions(facets, groupKey) {
  const group = FILTER_GROUP_BY_KEY[groupKey]
  if (!group || !facets) return []
  return facets[group.facet] ?? []
}

/**
 * One source of truth for what a filter does.
 *
 * Returns true when a result survives the active filters. An unfiltered group
 * passes everything through, so no filter group can accidentally exclude rows
 * that were never selected.
 */
export function matchesFilters(result, filters) {
  return FILTER_GROUPS.every((group) => {
    const selected = filters[group.key]
    if (selected === '' || selected === undefined || selected === null) return true
    return group.read(result) === selected
  })
}

/**
 * Zero-result alternatives, as the API computed them.
 *
 * This used to count client-side: drop one filter at a time and count the rows that
 * survived. That is a business count performed in the browser, and it is wrong in
 * two ways that matter. It counts the *rendered page* rather than the analysed
 * universe, so a truncated response would offer an alternative whose count the API
 * never confirmed; and it can only ever relax a filter, so it can never offer the
 * change that actually helps - adding a related field, or widening a country
 * preference.
 *
 * The backend does this properly: one controlled dimension changed at a time, over
 * the same candidate universe, recomputed with the same filter logic. This function
 * now only maps its answer into the shape the empty state renders.
 *
 * @param {object|null} alternatives - the API's `zero_result.alternatives`
 * @param {object} labelByDimension - maps an API dimension key to a readable label
 */
export function alternativesFor(alternatives, labelByDimension = {}) {
  if (!Array.isArray(alternatives)) return []

  return alternatives
    .map((option) => ({
      key: option.changed_dimension,
      // The API's wording is already written for a reader; the dimension label is
      // only a fallback for a response that predates it.
      label: option.change_label ?? labelByDimension[option.changed_dimension] ?? option.changed_dimension,
      count: option.result_count,
      isRemoval: option.is_removal === true,
    }))
    .filter((option) => option.count > 0)
}