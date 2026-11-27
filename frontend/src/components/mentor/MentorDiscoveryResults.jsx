function fundingLabel(cls) {
  switch (cls) {
    case 'STIPEND_TEXT_CANDIDATE': return 'Stipend mentioned (unverified)'
    case 'FUNDING_SUPPORT_CONFIRMED_STIPEND_UNCLEAR': return 'Funding described, stipend unclear'
    case 'FUNDING_UNVERIFIED': return 'Funding unverified'
    case 'FUNDING_EVIDENCE_CONFLICT': return 'Funding evidence conflicts'
    case 'STIPEND_EXPLICITLY_EXCLUDED': return 'No stipend (tuition only)'
    default: return cls || 'Unknown'
  }
}

export default function MentorDiscoveryResults({ payload, onPageChange, loading }) {
  if (!payload) return null
  const p = payload.pagination || {}
  const matches = payload.potential_matches || []
  const verified = payload.verified_matches || []
  return (
    <section className="mentor-discovery" data-testid="mentor-discovery-results" aria-label="Scholarship discovery results">
      <header className="mentor-discovery__header">
        <p className="mentor-discovery__status" data-testid="discovery-status">{payload.search_status}</p>
        <p className="mentor-discovery__summary" data-testid="discovery-summary">
          {payload.result_count} matching scholarships; showing {payload.returned_count || matches.length}.
        </p>
      </header>
      {verified.length > 0 && (
        <div className="mentor-discovery__group" data-testid="verified-matches">
          <h4>Verified matches</h4>
          <ul>
            {verified.map((m) => (
              <li key={m.scholarship_id} data-testid={`verified-match-${m.scholarship_id}`}>
                <strong>{m.title}</strong> — {m.country} {m.degree ? `(${m.degree})` : ''}
                <span className="mentor-discovery__funding">{fundingLabel(m.funding_classification)}</span>
                {m.official_source_url && (
                  <a href={m.official_source_url} target="_blank" rel="noopener noreferrer">Official source</a>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="mentor-discovery__group" data-testid="potential-matches">
        <h4>Potential matches</h4>
        {matches.length === 0 ? (
          <p data-testid="no-results">No scholarships found for this query.</p>
        ) : (
          <ul>
            {matches.map((m) => (
              <li key={m.scholarship_id} data-testid={`potential-match-${m.scholarship_id}`}>
                <strong>{m.title}</strong> — {m.country} {m.degree ? `(${m.degree})` : ''}
                <span className="mentor-discovery__funding">{fundingLabel(m.funding_classification)}</span>
                {m.funding_text && <span className="mentor-discovery__funding-text">{m.funding_text}</span>}
                {m.warnings && m.warnings.length > 0 && (
                  <ul className="mentor-discovery__warnings">
                    {m.warnings.map((w, i) => <li key={i}>{w}</li>)}
                  </ul>
                )}
                {m.official_source_url && (
                  <a href={m.official_source_url} target="_blank" rel="noopener noreferrer">Official source</a>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
      {p.total_pages > 1 && (
        <nav className="mentor-discovery__pagination" data-testid="discovery-pagination" aria-label="Pagination">
          <button
            data-testid="prev-page"
            disabled={loading || (p.page || 1) <= 1}
            onClick={() => onPageChange && onPageChange((p.page || 1) - 1)}
          >Previous</button>
          <span data-testid="page-info">Page {p.page || 1} of {p.total_pages}</span>
          <button
            data-testid="next-page"
            disabled={loading || !p.has_more}
            onClick={() => onPageChange && onPageChange((p.page || 1) + 1)}
          >Next</button>
        </nav>
      )}
    </section>
  )
}
