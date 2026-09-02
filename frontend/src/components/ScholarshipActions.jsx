import { useState } from 'react'
import { useCompare } from '../hooks/useCompare'
import { useSavedScholarships } from '../hooks/useSavedScholarships'
import './ScholarshipActions.css'

export default function ScholarshipActions({ scholarshipId, variant = 'card' }) {
  const { isSaved, toggleSaved } = useSavedScholarships()
  const { compareIds, isCompared, maxItems, toggleCompare } = useCompare()
  const [compareFeedback, setCompareFeedback] = useState('')
  const saved = isSaved(scholarshipId)
  const compared = isCompared(scholarshipId)
  const canAddComparison = compared || compareIds.length < maxItems

  function handleCompare() {
    const result = toggleCompare(scholarshipId)

    if (result.action === 'limit') {
      setCompareFeedback(`You can compare up to ${maxItems} scholarships at once.`)
      return
    }

    setCompareFeedback('')
  }

  return (
    <div className={`scholarship-actions scholarship-actions--${variant}`}>
      <div className="scholarship-actions__buttons">
        <button
          type="button"
          className={`scholarship-actions__button ${saved ? 'is-active' : ''}`}
          aria-pressed={saved}
          onClick={() => toggleSaved(scholarshipId)}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M6 4.5A1.5 1.5 0 0 1 7.5 3h9A1.5 1.5 0 0 1 18 4.5v16l-6-3.5L6 20.5v-16Z" />
          </svg>
          {saved ? 'Saved' : 'Save'}
        </button>

        <button
          type="button"
          className={`scholarship-actions__button ${compared ? 'is-active is-compare' : ''} ${!canAddComparison ? 'is-at-limit' : ''}`}
          aria-pressed={compared}
          aria-describedby={!canAddComparison ? `compare-limit-${scholarshipId}` : undefined}
          onClick={handleCompare}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M8 4H4v4m12-4h4v4M8 20H4v-4m12 4h4v-4M8 8h8v8H8z" />
          </svg>
          {compared ? 'Selected' : 'Compare'}
        </button>
      </div>

      {compareFeedback && (
        <p id={`compare-limit-${scholarshipId}`} className="scholarship-actions__feedback" role="status">
          {compareFeedback}
        </p>
      )}
    </div>
  )
}
