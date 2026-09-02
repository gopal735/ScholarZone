import { Link } from 'react-router-dom'
import { useScholarshipDirectory } from '../hooks/useScholarshipDirectory'
import { useCompare } from '../hooks/useCompare'
import { getDeadlineLabel } from '../utils/scholarshipPresentation'
import './ComparePage.css'

const comparisonRows = [
  ['Country / region', 'country'],
  ['Degree level', 'degree'],
  ['Funding', 'funding'],
  ['Application deadline', getDeadlineLabel],
]

export default function ComparePage() {
  const { compareIds, clearCompare, maxItems, toggleCompare } = useCompare()
  const { scholarships, isLoading } = useScholarshipDirectory()
  const selectedScholarships = compareIds
    .map((compareId) => scholarships.find((scholarship) => String(scholarship.id) === compareId))
    .filter(Boolean)

  return (
    <section className="compare-page">
      <div className="compare-page__heading">
        <div>
          <p className="compare-page__eyebrow">Decision support</p>
          <h1>Compare scholarships</h1>
          <p>Review the key details side by side before deciding what to explore next.</p>
        </div>
        <span className="compare-page__count">{selectedScholarships.length} of {maxItems} selected</span>
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
          <p>Select up to {maxItems} scholarships from the directory to compare their key details here.</p>
          <Link to="/scholarships" className="compare-page__action">
            Explore scholarships <span aria-hidden="true">&rarr;</span>
          </Link>
        </div>
      ) : (
        <>
          <div className="compare-page__toolbar">
            <p>Selections are saved on this device.</p>
            <button type="button" onClick={clearCompare}>Clear comparison</button>
          </div>

          <div className="compare-page__table-wrap" tabIndex="0" aria-label="Scholarship comparison table">
            <table className="compare-page__table">
              <thead>
                <tr>
                  <th scope="col">Scholarship</th>
                  {selectedScholarships.map((scholarship) => (
                    <th scope="col" key={scholarship.id}>
                      <Link to={`/scholarships/${scholarship.id}`}>{scholarship.title}</Link>
                      <button type="button" onClick={() => toggleCompare(scholarship.id)}>
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
                      <td key={scholarship.id}>{typeof field === 'function' ? field(scholarship) : scholarship[field]}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  )
}
