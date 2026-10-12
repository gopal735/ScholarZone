import { Link } from 'react-router-dom'
import { useScholarshipDirectory } from '../hooks/useScholarshipDirectory'
import { useCompare } from '../hooks/useCompare'
import { COMPARISON_ROWS, NOT_STATED, renderComparisonCell } from '../services/comparisonRows.js'
import './ComparePage.css'

export default function ComparePage() {
  const { compareIds, clearCompare, maxItems, toggleCompare } = useCompare()
  // The full catalogue, not a window of it. The previous implementation
  // resolved ids against the first 100 records, so anything outside that
  // window silently vanished from this table.
  const { scholarships, isLoading } = useScholarshipDirectory()
  const byId = new Map(scholarships.map((scholarship) => [String(scholarship.id), scholarship]))

  // An id that is not in this device's catalogue is reported as such rather
  // than dropped. Dropping it is what made the old version look like the
  // selection had been lost.
  const unresolved = compareIds.filter((id) => !byId.has(id))
  const selectedScholarships = compareIds
    .map((id) => byId.get(id))
    .filter(Boolean)

  return (
    <section className="compare-page">
      <div className="compare-page__heading">
        <div>
          <p className="compare-page__eyebrow">Decision support</p>
          <h1>Compare scholarships</h1>
          <p>Review the decision-relevant details side by side, and see plainly where an award does not say.</p>
        </div>
        <span className="compare-page__count">{selectedScholarships.length} of {maxItems} selected</span>
      </div>

      {isLoading ? (
        <div className="compare-page__empty" aria-busy="true">
          <h2>Loading comparison&hellip;</h2>
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
        <p>
          Selections are saved on this device.
          {' '}
          {NOT_STATED} means the provider has not published the detail &mdash; it is not the same as
          a confirmed &ldquo;no&rdquo;.
        </p>
        <button type="button" onClick={clearCompare}>Clear comparison</button>
      </div>

      {/* A selection that cannot be resolved is reported, not hidden. The
          cause is almost always an export restored on a device whose snapshot
          is older, and the student needs to know which side is missing rather
          than wondering where the row went.

          The control that removes them used to not exist: the only remove
          button on this page is rendered per *resolved* scholarship, so an
          unresolved id could never be cleared and the notice was permanent. */}
      {unresolved.length > 0 && (
        <div className="compare-page__unresolved" role="status">
          <p>
            {unresolved.length === 1
              ? 'One selected scholarship is not in this device\u2019s catalogue.'
              : `${unresolved.length} selected scholarships are not in this device\u2019s catalogue.`}
            {' '}
            They were saved on a device whose catalogue had newer records.
          </p>
          <button
            type="button"
            onClick={() => {
              for (const id of unresolved) {
                toggleCompare(id)
              }
            }}
          >
            Remove {unresolved.length === 1 ? 'it' : 'them'}
          </button>
        </div>
      )}

          <div className="compare-page__table-wrap" tabIndex={0} role="region" aria-label="Scholarship comparison table">
            <table className="compare-page__table">
              <caption className="visually-hidden">
                {selectedScholarships.length} scholarships compared across {COMPARISON_ROWS.length} attributes.
              </caption>
              <thead>
                <tr>
                  <th scope="col">Attribute</th>
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
                {COMPARISON_ROWS.map((row) => (
                  <tr key={row.key}>
                    <th scope="row">{row.label}</th>
                    {selectedScholarships.map((scholarship) => {
                      const cell = renderComparisonCell(row, scholarship)
                      const isUnknown = cell === NOT_STATED
                      return (
                        <td
                          key={scholarship.id}
                          /* The distinction has to survive the styling, not
                             only the toolbar sentence beside the table. A
                             populated cell and an unknown one used to render
                             identically, so the page explained that "not
                             stated" is not a "no" and then drew them the same
                             way. The marker is colour-weight and a text cue,
                             so it does not rely on colour alone. */
                          className={isUnknown ? 'compare-page__cell--unknown' : undefined}
                          data-value={isUnknown ? 'not-stated' : undefined}
                        >
                          {isUnknown ? (
                            <>
                              <span className="compare-page__unknown-icon" aria-hidden="true">
                                <svg viewBox="0 0 24 24">
                                  <path d="M9.9 9a2.1 2.1 0 1 1 3.4 1.7c-.8.5-1.3 1-1.3 2M12 17h.01" />
                                </svg>
                              </span>
                              {cell}
                            </>
                          ) : cell}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Funding amount is absent from the table on purpose, and saying so
              keeps a future contributor from "fixing" the omission by adding a
              column that compares a EUR monthly rate against a KRW total. */}
          <p className="compare-page__note">
            Funding amounts are not compared: the catalogue publishes them in 42 currencies against
            228 different period descriptions, so the figures are not on one scale.
          </p>
        </>
      )}
    </section>
  )
}
