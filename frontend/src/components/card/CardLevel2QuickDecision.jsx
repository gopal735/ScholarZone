import CardExpandSection from './CardExpandSection'
import {
  deriveFundingCoverage,
  deriveMatchScore,
  deriveReadiness,
  deriveRiskFlags,
  deriveUnknowns,
  deriveRecordKind,
  DATA_PROVENANCE,
} from '../../utils/cardPresentation'

/* Level 2 — Quick decision.
   Answers: may I be eligible, why does it match, what is
   missing, how ready is the record, what are the risks,
   what does the funding actually cover. */
export default function CardLevel2QuickDecision({ scholarship, matchResult }) {
  const matchScore = deriveMatchScore(scholarship, matchResult)
  const readiness = deriveReadiness(scholarship)
  const riskFlags = deriveRiskFlags(scholarship)
  const fundingCoverage = deriveFundingCoverage(scholarship)
  const unknowns = deriveUnknowns(scholarship)
  const recordKind = deriveRecordKind(scholarship)

  const eligibilityItems = [
    ...(Array.isArray(scholarship.eligibility) ? scholarship.eligibility : []),
  ]
  const eligibilitySummary = scholarship.eligibility_summary

  return (
    <CardExpandSection
      level={2}
      title="Quick decision"
      summary={readiness.label}
    >
      {recordKind.kind === 'category' && (
        <p className="card-note card-note--category">{recordKind.note}</p>
      )}

      <div className="card-block">
        <h4 className="card-block__title">Why it matches</h4>
        {matchScore.scored ? (
          <p className="card-match-score">
            <strong>{matchScore.label}</strong>
            <span className="card-provenance">derived from your Match profile</span>
          </p>
        ) : (
          <p className="card-note">{matchScore.hint}</p>
        )}
        {eligibilitySummary && <p className="card-text">{eligibilitySummary}</p>}
        {eligibilityItems.length > 0 && (
          <ul className="card-list">
            {eligibilityItems.map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>
        )}
      </div>

      <div className="card-block">
        <h4 className="card-block__title">Application readiness</h4>
        <p className="card-readiness">
          <span className={`card-readiness__badge card-readiness__badge--${readiness.level}`}>
            {readiness.label}
          </span>
          <span className="card-note">
            {readiness.present} of {readiness.total} key fields published
          </span>
        </p>
        {readiness.missing.length > 0 && (
          <p className="card-note">
            Missing: {readiness.missing.join(', ')}
          </p>
        )}
      </div>

      <div className="card-block">
        <h4 className="card-block__title">What is missing</h4>
        {unknowns.length === 0 ? (
          <p className="card-note">No major gaps on this record.</p>
        ) : (
          <ul className="card-list card-list--unknowns">
            {unknowns.map((unknown) => (
              <li key={unknown.field}>
                <strong>{unknown.field}</strong> — {unknown.note}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="card-block">
        <h4 className="card-block__title">Risk flags</h4>
        {riskFlags.length === 0 ? (
          <p className="card-note">No risk flags on this record.</p>
        ) : (
          <ul className="card-list">
            {riskFlags.map((flag) => (
              <li key={flag.label} className={`card-flag card-flag--${flag.severity}`}>
                <strong>{flag.label}</strong>
                <span>{flag.detail}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="card-block">
        <h4 className="card-block__title">Funding coverage</h4>
        <dl className="card-facts">
          <div className="card-facts__row">
            <dt>Tuition</dt>
            <dd>{fundingCoverage.tuition || 'Not published'}</dd>
          </div>
          <div className="card-facts__row">
            <dt>Living costs</dt>
            <dd>{fundingCoverage.living || 'Not published'}</dd>
          </div>
          <div className="card-facts__row">
            <dt>Travel</dt>
            <dd>{fundingCoverage.travel || 'Not published'}</dd>
          </div>
        </dl>
        {fundingCoverage.items.length > 0 && (
          <ul className="card-list">
            {fundingCoverage.items.map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>
        )}
        {fundingCoverage.provenance === DATA_PROVENANCE.DERIVED && (
          <p className="card-provenance">No itemised benefits published on this record.</p>
        )}
      </div>
    </CardExpandSection>
  )
}
