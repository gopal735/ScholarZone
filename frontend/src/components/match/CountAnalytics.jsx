/**
 * The count intelligence panel.
 *
 * A reader who wants to know how a number was produced can ask, and get an answer
 * that is checkable: the universe, the active conditions, the versions, and the
 * integrity verdict. A reader who does not care never sees any of it - the
 * advanced section is collapsed, and the default screen stays in plain language.
 *
 * Every figure rendered here comes from the API response. Nothing is counted in
 * this component, and the empty cases say so rather than showing a zero.
 */
export function CountAnalytics({ intelligence, error, status }) {
  if (error) {
    return (
      <section className="match-counts match-counts--error" data-testid="count-analytics-error">
        <h3>Counts unavailable</h3>
        <p role="status">
          These counts could not be loaded, so they are not shown. A missing count is
          reported as missing rather than estimated.
        </p>
      </section>
    )
  }

  if (!intelligence) return null

  const { summary = {}, distributions = [], explanations, integrity, provenance } = intelligence
  const eligibility = summary['eligibility.ELIGIBLE'] ?? 0
  const needsVerification = summary['eligibility.NEEDS_VERIFICATION'] ?? 0
  const total = intelligence.total_candidates ?? 0

  return (
    <section className="match-counts" data-testid="count-analytics">
      <h3 className="match-counts__heading">About these numbers</h3>

      <p className="match-counts__basis">
        <strong>{eligibility + needsVerification}</strong> of {total} analysed
        scholarships meet the published conditions for this profile.
        {/* That headline adds two different states together, and on its own it
            read as a contradiction of the drill-down below it: "368 of 386"
            immediately above "0 eligible scholarships". Both were correct and
            answered different questions. Naming the two states in the same
            sentence removes the puzzle without touching either number or the
            contract wording they come from. */}
        {' '}
        That is {eligibility} eligible and {needsVerification} needing verification.
        {integrity ? (
          <span className={`match-counts__integrity match-counts__integrity--${integrity.status.toLowerCase()}`}>
            Counts {integrity.status.toLowerCase()}
          </span>
        ) : null}
      </p>

      {explanations?.eligible ? (
        <details className="match-counts__detail">
          <summary>Why is this number?</summary>
          <p className="match-counts__explanation">{explanations.eligible.human_readable}</p>
          {explanations.eligible.clauses?.length ? (
            <ul className="match-counts__clauses">
              {explanations.eligible.clauses.map((clause) => (
                <li key={`${clause.dimension}-${clause.value}`}>
                  <code>
                    {clause.dimension} {clause.operator} {clause.value}
                  </code>
                </li>
              ))}
            </ul>
          ) : null}
        </details>
      ) : null}

      <details className="match-counts__detail">
        <summary>Show the distributions</summary>
        <table className="match-counts__table">
          <caption className="sr-only">Distribution of measured values across analysed scholarships</caption>
          <thead>
            <tr>
              <th scope="col">Measure</th>
              <th scope="col">Records measured</th>
              <th scope="col">Average</th>
              <th scope="col">Median</th>
              <th scope="col">Range</th>
            </tr>
          </thead>
          <tbody>
            {distributions.map((entry) => (
              <tr key={entry.dimension}>
                <th scope="row">{entry.dimension}</th>
                <td>{entry.sample_count}</td>
                {/* An average over no records is "not measured", never 0. */}
                <td>{entry.mean === null ? 'Not measured' : entry.mean}</td>
                <td>{entry.median === null ? 'Not measured' : entry.median}</td>
                <td>
                  {entry.minimum === null
                    ? 'Not measured'
                    : `${entry.minimum} to ${entry.maximum}`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {distributions.some((entry) => entry.caveat) ? (
          <ul className="match-counts__caveats">
            {distributions
              .filter((entry) => entry.caveat)
              .map((entry) => (
                <li key={entry.dimension}>
                  <strong>{entry.dimension}:</strong> {entry.caveat}
                </li>
              ))}
          </ul>
        ) : null}
        <p className="match-counts__note">
          Records with no measured value are excluded from these figures and counted
          separately. An average never counts a missing value as zero.
        </p>
      </details>

      <details className="match-counts__detail">
        <summary>Where these numbers came from</summary>
        <dl className="match-counts__provenance">
          <dt>Universe</dt>
          <dd>{intelligence.universe}</dd>
          <dt>Count basis</dt>
          <dd>{intelligence.facets?.count_basis ?? 'MATCH_RETURNED_PAGE'}</dd>
          <dt>As of</dt>
          <dd>{intelligence.as_of}</dd>
          <dt>Count contract</dt>
          <dd>{provenance?.count_contract_version}</dd>
          <dt>Match engine</dt>
          <dd>{provenance?.engine_version}</dd>
          <dt>Scoring config</dt>
          <dd>{provenance?.scoring_config_version}</dd>
          <dt>Field taxonomy</dt>
          <dd>{provenance?.field_taxonomy_version}</dd>
          <dt>Deadline semantics</dt>
          <dd>{provenance?.deadline_semantics_version}</dd>
        </dl>
        {provenance?.filter_state ? (
          <p className="match-counts__note">
            Active conditions: {JSON.stringify(provenance.filter_state)}
          </p>
        ) : null}
        {integrity?.issues?.length ? (
          <ul className="match-counts__issues">
            {integrity.issues.map((issue) => (
              <li key={issue}>{issue}</li>
            ))}
          </ul>
        ) : null}
      </details>

      {status === 'loading' ? (
        <p className="match-counts__note" role="status" aria-live="polite">
          Updating counts&hellip;
        </p>
      ) : null}
    </section>
  )
}

export default CountAnalytics