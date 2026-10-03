import { FILTER_GROUPS, facetOptions } from './matchFilterConfig'

/**
 * Result filters, driven entirely by the API's own facets.
 *
 * Two properties are load-bearing here:
 *
 *   * every option carries the count the API computed for it, so a number next
 *     to a filter value is the number of cards that choice produces
 *   * clearing the filters calls ``onChange(null)`` rather than sending a
 *     partially empty object, because a reset that routed a different shape than
 *     a change did used to leave one filter stuck
 */
export function MatchFilters({ facets, filters, onChange, totalShown, totalAvailable, onReset }) {
  if (!facets) return null

  return (
    <section className="match-filters" aria-labelledby="match-filters-heading">
      <div className="match-filters__intro">
        <p id="match-filters-heading">Filter your results</p>
        <span>
          Showing {totalShown} of {totalAvailable} returned scholarship
          {totalAvailable === 1 ? '' : 's'}. Counts come from the engine, not from this page.
        </span>
      </div>

      <div className="match-filters__controls">
        {FILTER_GROUPS.map((group) => {
          const options = facetOptions(facets, group.key)
          if (options.length < 1) return null

          const selectId = `match-filter-${group.key}`
          return (
            <div className="match-filter" key={group.key}>
              <label htmlFor={selectId}>{group.label}</label>
              <select
                id={selectId}
                data-testid={`filter-${group.key}`}
                value={filters[group.key] ?? ''}
                onChange={(event) => onChange(group.key, event.target.value)}
              >
                <option value="">All {group.label.toLowerCase()}</option>
                {options.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label} ({option.count})
                  </option>
                ))}
              </select>
            </div>
          )
        })}

        <button type="button" className="match-filters__reset" onClick={onReset}>
          Reset filters
        </button>
      </div>
    </section>
  )
}

export default MatchFilters