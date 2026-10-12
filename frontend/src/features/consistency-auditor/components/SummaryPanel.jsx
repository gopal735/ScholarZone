import { CATEGORIES } from '../engine/findings.js';
import { STRINGS, CATEGORY_DESCRIPTIONS } from '../strings.js';

/**
 * Summary counts, and the category filter.
 *
 * The counts are over the UNRESOLVED items, because that is the list being
 * counted: a dismissed item is decided, and counting it as still open would
 * make the summary disagree with the list.
 */
export default function SummaryPanel({ findings, filter, onFilterChange, hasRun = false }) {
  const counts = {};
  for (const category of Object.values(CATEGORIES)) counts[category] = 0;
  for (const finding of findings) counts[finding.category] += 1;

  // A review that produced nothing is a result, not an empty state: the
  // summary says so instead of asking the user to paste a document they
  // already pasted.
  if (findings.length === 0 && !hasRun) {
    return (
      <section className="ca-summary ca-summary--empty" aria-labelledby="ca-summary-heading">
        <h3 id="ca-summary-heading">{STRINGS.summary.heading}</h3>
        <p>{STRINGS.summary.empty}</p>
      </section>
    );
  }

  return (
    <section className="ca-summary" aria-labelledby="ca-summary-heading">
      <h3 id="ca-summary-heading">{STRINGS.summary.heading}</h3>
      <p className="ca-summary__total" aria-live="polite">
        {STRINGS.summary.total(findings.length)}
      </p>

      <ul className="ca-summary__counts">
        {Object.values(CATEGORIES).map((category) => (
          <li key={category} className="ca-summary__count">
            <span className="ca-summary__count-value">{counts[category]}</span>
            <span className="ca-summary__count-label">{category}</span>
            <span className="ca-summary__count-desc">{CATEGORY_DESCRIPTIONS[category]}</span>
          </li>
        ))}
      </ul>

      <div className="ca-summary__filter">
        <label htmlFor="ca-filter">{STRINGS.findings.filterLabel}</label>
        <select
          id="ca-filter"
          value={filter}
          onChange={(event) => onFilterChange(event.target.value)}
        >
          <option value="all">{STRINGS.findings.filterAll}</option>
          {Object.values(CATEGORIES).map((category) => (
            <option key={category} value={category}>
              {category}
            </option>
          ))}
        </select>
        <p className="ca-summary__sort-note">{STRINGS.findings.sortNote}</p>
      </div>
    </section>
  );
}
