/**
 * Side-by-side comparison of two or three scholarships.
 *
 * Factual differences only. There is deliberately no "winner", no "best" and no
 * "guaranteed" column: the engine measures fit against a profile, and a
 * comparison that named a winner would be asserting something it cannot support.
 */
const MAX_COMPARE = 3
const MIN_COMPARE = 2

function fitDisplay(result) {
  if (typeof result.fit_score !== 'number') return 'N/A'
  return `${result.fit_score}`
}

const ROWS = [
  {
    key: 'fit',
    label: 'Fit',
    render: (result) =>
      typeof result.fit_score === 'number'
        ? `${fitDisplay(result)} · ${result.fit_label_display}`
        : 'Not available',
  },
  {
    key: 'eligibility',
    label: 'Eligibility',
    render: (result) => result.eligibility_detail?.detail ?? result.eligibility,
  },
  {
    key: 'confidence',
    label: 'Confidence',
    render: (result) => `${result.confidence_label_display} (${result.confidence_score})`,
  },
  {
    key: 'coverage',
    label: 'Data coverage',
    render: (result) => `${result.data_coverage}%`,
  },
  {
    key: 'funding',
    label: 'Funding',
    render: (result) =>
      result.funding_state
        ? String(result.funding_state).replace(/_/g, ' ').toLowerCase()
        : 'Not established',
  },
  {
    key: 'field',
    label: 'Field',
    render: (result) => result.field_label ?? 'Not published',
  },
  {
    key: 'deadline',
    label: 'Deadline',
    render: (result) =>
      result.deadline_display
        ? `${result.deadline_display}${result.deadline_precision === 'month' ? ' (month only)' : ''}`
        : 'No fixed date published',
  },
  {
    key: 'readiness',
    label: 'Readiness',
    render: (result) =>
      typeof result.readiness?.score === 'number'
        ? `${Math.round(result.readiness.score)} · ${result.readiness.label}`
        : 'Not evaluated',
  },
  {
    key: 'gaps',
    label: 'Key gaps',
    render: (result) => {
      const gaps = result.gaps ?? []
      if (gaps.length === 0) return 'None reported'
      return gaps
        .slice(0, 3)
        .map((item) => item.message)
        .join(' ')
    },
  },
]

export function MatchCompare({ results, selectedIds, onClear }) {
  const selected = (results ?? []).filter((item) => selectedIds.includes(item.scholarship_id))
  const atMax = selected.length >= MAX_COMPARE

  if (selected.length < MIN_COMPARE) {
    return (
      <p className="match-compare__hint" data-testid="compare-hint">
        Select {MIN_COMPARE} or {MAX_COMPARE} scholarships to compare them side by side.
        {atMax ? ' You have the maximum selected.' : ''}
      </p>
    )
  }

  return (
    <section className="match-compare" aria-labelledby="match-compare-heading">
      <div className="match-compare__head">
        <h3 id="match-compare-heading">Comparing {selected.length} scholarships</h3>
        <button type="button" className="match-compare__clear" onClick={onClear}>
          Clear comparison
        </button>
      </div>

      <div className="match-compare__scroll">
        <table className="match-compare__table" data-testid="compare-table">
          <caption className="match-visually-hidden">
            Factual differences between the selected scholarships
          </caption>
          <thead>
            <tr>
              <th scope="col">Measure</th>
              {selected.map((item) => (
                <th key={item.scholarship_id} scope="col">
                  <span className="match-compare__name">{item.scholarship_name}</span>
                  <span className="match-compare__meta">
                    {item.country}
                    {item.degree_levels ? ` · ${item.degree_levels}` : ''}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => (
              <tr key={row.key}>
                <th scope="row">{row.label}</th>
                {selected.map((item) => (
                  <td key={item.scholarship_id}>{row.render(item)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="match-compare__note">
        Factual differences only. ScholarZone does not name a winner, and nothing here
        is a prediction of admission.
      </p>
    </section>
  )
}

export { MAX_COMPARE, MIN_COMPARE }

export default MatchCompare