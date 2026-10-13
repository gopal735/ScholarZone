/**
 * The shared value a "no filter" select takes.
 *
 * Every catalogue select shows "All …" when it is not filtering, and every one
 * of them has to agree on the string that means it. Before this existed as a
 * constant of its own, three modules each had the 'all' literal: the URL state
 * module, the study-level matcher and the tuition matcher. They were correct
 * only by coincidence, and a change to one would have made a page where one
 * filter silently stopped matching everything.
 *
 * A leaf module with no imports, so every consumer can import it without
 * creating a cycle.
 */

/** The value a select carries when it is not filtering. */
export const NO_FILTER = 'all'

/** True when a filter value means "do not filter". */
export function isNoFilterValue(value) {
  if (value === null || value === undefined) {
    return true
  }
  if (typeof value !== 'string') {
    return false
  }
  const normalized = value.trim()
  return normalized === '' || normalized.toLowerCase() === NO_FILTER
}
