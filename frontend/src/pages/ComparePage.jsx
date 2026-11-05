import { Link } from 'react-router-dom'
import { useScholarshipDirectory } from '../hooks/useScholarshipDirectory'
import { useCompare } from '../hooks/useCompare'
import { getDeadlineLabel } from '../utils/scholarshipPresentation'
import { readFundingDetails } from '../utils/scholarshipDetail'
import './ComparePage.css'

function formatCoverage(scholarship) {
  const parts = []

  // Structured funding details by track
  const fundingDetails = readFundingDetails(scholarship.funding_details)
  if (fundingDetails.length > 0) {
    fundingDetails.forEach((track) => {
      const trackParts = []
      if (track.programme || track.track_name) {
        trackParts.push(`${track.programme || ''}${track.programme && track.track_name ? ' — ' : ''}${track.track_name || ''}`)
      }
      if (track.amount != null && track.currency) {
        trackParts.push(`${Number(track.amount).toLocaleString()} ${track.currency}${track.payment_period ? ` / ${track.payment_period}` : ''}`)
      } else if (track.amount != null) {
        trackParts.push(`${Number(track.amount).toLocaleString()}${track.payment_period ? ` / ${track.payment_period}` : ''}`)
      }
      if (track.tuition_coverage != null) trackParts.push(`Tuition: ${track.tuition_coverage ? 'Covered' : 'Not covered'}`)
      if (track.living_cost_coverage != null) trackParts.push(`Living costs: ${track.living_cost_coverage ? 'Covered' : 'Not covered'}`)
      if (track.accommodation_coverage != null) trackParts.push(`Accommodation: ${track.accommodation_coverage ? 'Covered' : 'Not covered'}`)
      if (track.travel_coverage != null) trackParts.push(`Travel: ${track.travel_coverage ? 'Covered' : 'Not covered'}`)
      if (track.insurance_coverage != null) trackParts.push(`Insurance: ${track.insurance_coverage ? 'Covered' : 'Not covered'}`)
      if (track.conditions) trackParts.push(`Conditions: ${track.conditions}`)
      if (trackParts.length > 0) {
        parts.push(trackParts.join('; '))
      }
    })
    return parts.join(' | ')
  }

  // Top-level canonical fields
  const coverageItems = []
  if (scholarship.tuition_coverage !== null && scholarship.tuition_coverage !== undefined) {
    coverageItems.push(`Tuition: ${scholarship.tuition_coverage ? 'Covered' : 'Not covered'}`)
  }
  if (scholarship.living_cost_coverage !== null && scholarship.living_cost_coverage !== undefined) {
    coverageItems.push(`Living costs: ${scholarship.living_cost_coverage ? 'Covered' : 'Not covered'}`)
  }
  if (scholarship.travel_coverage !== null && scholarship.travel_coverage !== undefined) {
    coverageItems.push(`Travel: ${scholarship.travel_coverage ? 'Covered' : 'Not covered'}`)
  }
  if (scholarship.fully_funded !== null && scholarship.fully_funded !== undefined) {
    coverageItems.push(`Fully funded: ${scholarship.fully_funded ? 'Yes' : 'No'}`)
  }
  if (scholarship.funding_amount != null && scholarship.funding_currency) {
    coverageItems.push(`Amount: ${scholarship.funding_amount.toLocaleString()} ${scholarship.funding_currency}${scholarship.funding_period ? ` / ${scholarship.funding_period}` : ''}`)
  }

  if (coverageItems.length > 0) {
    return coverageItems.join('; ')
  }

  // Fallback to coverage array
  if (scholarship.coverage && Array.isArray(scholarship.coverage) && scholarship.coverage.length > 0) {
    return scholarship.coverage.join('; ')
  }
  if (scholarship.coverage && typeof scholarship.coverage === 'string') {
    return scholarship.coverage
  }

  return 'See official portal for detailed coverage'
}

const comparisonRows = [
  ['Country / Destination', (s) => s.country],
  ['Degree Level', (s) => s.degree],
  ['Funding Status', (s) => s.funding],
  [
    'Financial Coverage',
    (s) => formatCoverage(s),
  ],
  ['Awarding Body / Provider', (s) => s.provider || 'Official awarding body'],
  ['Application Deadline', getDeadlineLabel],
  [
    'Official Verification',
    (s) =>
      s.verified ? '✅ Verified official provider' : 'Confirm with provider',
  ],
  [
    'Official Portal',
    (s) => {
      const url = s.officialUrl || s.official_url
      return url ? (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="compare-ext-link"
        >
          Official Portal &rarr;
        </a>
      ) : (
        <Link to={`/scholarships/${s.id}`} className="compare-ext-link">
          View Details &rarr;
        </Link>
      )
    },
  ],
]

export default function ComparePage() {
  const { compareIds, clearCompare, maxItems, toggleCompare } = useCompare()
  const { scholarships, isLoading } = useScholarshipDirectory()
  const selectedScholarships = compareIds
    .map((compareId) =>
      scholarships.find((scholarship) => String(scholarship.id) === compareId)
    )
    .filter(Boolean)

  const unselectedSuggestions = scholarships
    .filter((s) => !compareIds.includes(String(s.id)))
    .slice(0, 4)

  return (
    <section className="compare-page">
      <div className="compare-page__heading">
        <div>
          <p className="compare-page__eyebrow">Decision support</p>
          <h1>Compare scholarships</h1>
          <p>
            Review funding coverage, living stipends, and deadlines side by side
            before deciding what to explore next.
          </p>
        </div>
        <span className="compare-page__count">
          {selectedScholarships.length} of {maxItems} selected
        </span>
      </div>

      {isLoading ? (
        <div className="compare-page__empty" aria-busy="true">
          <h2>Loading comparison…</h2>
        </div>
      ) : selectedScholarships.length === 0 ? (
        <div className="compare-page__empty">
          <span className="compare-page__empty-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <path d="M8 4H4v4m12-4h4v4M8 20H4v-4m12 4h4v-4M8 8h8v8H8z" />
            </svg>
          </span>
          <h2>Nothing selected for comparison yet.</h2>
          <p>
            Select up to {maxItems} scholarships from the directory to compare
            their funding coverage, living allowances, and requirements here.
          </p>
          <div style={{ marginTop: '14px', marginBottom: '24px' }}>
            <Link to="/scholarships" className="p-btn compare-page__action">
              Explore scholarships directory <span aria-hidden="true">&rarr;</span>
            </Link>
          </div>

          {unselectedSuggestions.length > 0 && (
            <div
              className="compare-suggested"
              style={{ textAlign: 'left', width: '100%', maxWidth: '780px' }}
            >
              <h3>Or quickly compare premier international scholarships:</h3>
              <p>One-click to add flagship full-ride opportunities:</p>
              <div className="compare-suggested__grid">
                {unselectedSuggestions.map((s) => (
                  <div key={s.id} className="compare-suggested__card">
                    <div>
                      <strong>{s.title}</strong>
                      <span>
                        {s.country} &middot; {s.funding}
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => toggleCompare(s.id)}
                    >
                      + Add to Compare
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <>
          <div className="compare-page__toolbar">
            <p>Selections are saved on this device.</p>
            <button type="button" onClick={clearCompare}>
              Clear comparison
            </button>
          </div>

          <div
            className="compare-page__table-wrap"
            tabIndex="0"
            aria-label="Scholarship comparison table"
          >
            <table className="compare-page__table">
              <thead>
                <tr>
                  <th scope="col">Scholarship</th>
                  {selectedScholarships.map((scholarship) => (
                    <th scope="col" key={scholarship.id}>
                      <Link to={`/scholarships/${scholarship.id}`}>
                        {scholarship.title}
                      </Link>
                      <button
                        type="button"
                        onClick={() => toggleCompare(scholarship.id)}
                      >
                        Remove <span aria-hidden="true">&times;</span>
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {comparisonRows.map(([label, field]) => (
                  <tr key={label}>
                    <th scope="row">{label}</th>
                    {selectedScholarships.map((scholarship) => (
                      <td key={scholarship.id}>
                        {typeof field === 'function'
                          ? field(scholarship)
                          : scholarship[field]}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {selectedScholarships.length < maxItems && unselectedSuggestions.length > 0 && (
            <div className="compare-suggested">
              <h3>Add another scholarship to your comparison</h3>
              <p>Compare up to {maxItems} opportunities simultaneously:</p>
              <div className="compare-suggested__grid">
                {unselectedSuggestions.slice(0, 3).map((s) => (
                  <div key={s.id} className="compare-suggested__card">
                    <div>
                      <strong>{s.title}</strong>
                      <span>
                        {s.country} &middot; {s.funding}
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => toggleCompare(s.id)}
                    >
                      + Add to Compare
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </section>
  )
}
