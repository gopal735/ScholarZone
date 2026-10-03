/**
 * The result header: real counts, from the API, never hardcoded.
 *
 * Every number below comes from the engine's own summary, which reconciles its
 * three eligibility states against the candidate universe. Nothing here is
 * computed in the browser: if the frontend recalculated a count it could disagree
 * with the list it is describing, and a dashboard that disagrees with itself is
 * worse than no dashboard.
 */
export function MatchResultSummary({ summary }) {
  if (!summary) return null

  const {
    total_candidates: totalCandidates = 0,
    visible_candidate_count: visibleCount = 0,
    eligible_count: eligible = 0,
    needs_verification_count: needsVerification = 0,
    ineligible_count: ineligible = 0,
    exceptional_count: exceptional = 0,
    very_strong_count: veryStrong = 0,
    strong_count: strong = 0,
    possible_count: possible = 0,
    low_count: low = 0,
    scored_count: scored = 0,
    not_scored_count: notScored = 0,
    high_confidence_count: highConfidence = 0,
    medium_confidence_count: mediumConfidence = 0,
    low_confidence_count: lowConfidence = 0,
    strong_or_better_count: strongOrBetter = 0,
    truncated = false,
  } = summary

  return (
    <section className="match-result-summary" aria-labelledby="match-summary-heading">
      <h2 id="match-summary-heading">Your match results</h2>
      <p className="match-result-summary__intro">
        {totalCandidates} scholarship{totalCandidates === 1 ? '' : 's'} analysed against the
        profile you gave us.
      </p>

      <dl className="match-result-summary__stats" data-testid="match-summary-stats">
        <div>
          <dt>Eligible</dt>
          <dd>{eligible}</dd>
        </div>
        <div>
          <dt>Need verification</dt>
          <dd>{needsVerification}</dd>
        </div>
        <div>
          <dt>Not eligible</dt>
          <dd>{ineligible}</dd>
        </div>
        <div>
          <dt>Exceptional fits</dt>
          <dd>{exceptional + veryStrong}</dd>
        </div>
        <div>
          <dt>High confidence</dt>
          <dd>{highConfidence}</dd>
        </div>
      </dl>

      <details className="match-result-summary__detail">
        <summary>Every count behind this result</summary>
        <dl className="match-result-summary__grid">
          <div>
            <dt>Analysed</dt>
            <dd>{totalCandidates}</dd>
          </div>
          <div>
            <dt>Scored</dt>
            <dd>{scored}</dd>
          </div>
          <div>
            <dt>Not scored</dt>
            <dd>{notScored}</dd>
          </div>
          <div>
            <dt>Strong or better</dt>
            <dd>{strongOrBetter}</dd>
          </div>
          <div>
            <dt>Exceptional</dt>
            <dd>{exceptional}</dd>
          </div>
          <div>
            <dt>Very strong</dt>
            <dd>{veryStrong}</dd>
          </div>
          <div>
            <dt>Strong</dt>
            <dd>{strong}</dd>
          </div>
          <div>
            <dt>Possible</dt>
            <dd>{possible}</dd>
          </div>
          <div>
            <dt>Low</dt>
            <dd>{low}</dd>
          </div>
          <div>
            <dt>Confidence: high</dt>
            <dd>{highConfidence}</dd>
          </div>
          <div>
            <dt>Confidence: medium</dt>
            <dd>{mediumConfidence}</dd>
          </div>
          <div>
            <dt>Confidence: low</dt>
            <dd>{lowConfidence}</dd>
          </div>
        </dl>
        <p className="match-result-summary__note">
          These counts describe every scholarship that was analysed. They are not a
          prediction of admission, and ScholarZone does not estimate your chances.
        </p>
      </details>

      {truncated ? (
        <p className="match-result-summary__truncated" data-testid="match-truncation">
          Showing the {visibleCount} highest-ranked of {totalCandidates} analysed
          scholarships. Ask for fewer or more specific filters to see the rest.
        </p>
      ) : null}
    </section>
  )
}

export default MatchResultSummary