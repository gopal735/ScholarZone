import CardExpandSection from './CardExpandSection'
import {
  deriveApplicationEffort,
  deriveCostGap,
  deriveCountrySnapshot,
  deriveDocumentReuse,
  deriveMobilityBurden,
  deriveSupervisorAvailability,
  deriveVisaComplexity,
  DATA_PROVENANCE,
} from '../../utils/cardPresentation'

/* Level 3 — Practical planning.
   Answers: how much effort, what is the cost gap, how
   heavy is mobility, how complex is the visa, which
   documents can be reused, what does the country look
   like for a career, is a supervisor available. */
export default function CardLevel3Planning({ scholarship, countryIntelligence }) {
  const effort = deriveApplicationEffort(scholarship)
  const costGap = deriveCostGap(scholarship)
  const mobility = deriveMobilityBurden(scholarship)
  const visa = deriveVisaComplexity(scholarship)
  const documentReuse = deriveDocumentReuse(scholarship)
  const supervisor = deriveSupervisorAvailability(scholarship)
  const countrySnapshot = deriveCountrySnapshot(scholarship, countryIntelligence)

  return (
    <CardExpandSection level={3} title="Practical planning" summary={effort.label}>
      <div className="card-block">
        <h4 className="card-block__title">Application effort</h4>
        <p className="card-facts-inline">
          <span className={`card-effort card-effort--${effort.complexity}`}>{effort.label}</span>
          <span className="card-note">
            {effort.documentsCount} documents · {effort.essayCount} essays · {effort.referenceCount} references
          </span>
        </p>
      </div>

      <div className="card-block">
        <h4 className="card-block__title">Cost gap</h4>
        <p className={`card-status card-status--${costGap.status}`}>{costGap.label}</p>
        <p className="card-note">{costGap.note}</p>
      </div>

      <div className="card-block">
        <h4 className="card-block__title">Mobility burden</h4>
        <p className={`card-status card-status--${mobility.intensity}`}>{mobility.label}</p>
        <p className="card-note">{mobility.note}</p>
      </div>

      <div className="card-block">
        <h4 className="card-block__title">Visa complexity</h4>
        <p className={`card-status card-status--${visa.level}`}>{visa.label}</p>
        <p className="card-note">{visa.note}</p>
      </div>

      <div className="card-block">
        <h4 className="card-block__title">Document reuse</h4>
        {documentReuse.reusable.length > 0 && (
          <p className="card-facts-inline">
            <span className="card-note">Reusable across applications:</span>
          </p>
        )}
        {documentReuse.reusable.length > 0 && (
          <ul className="card-list">
            {documentReuse.reusable.map((doc, index) => (
              <li key={index}>{doc}</li>
            ))}
          </ul>
        )}
        {documentReuse.mustCustomize.length > 0 && (
          <p className="card-facts-inline">
            <span className="card-note">Must be customised per application:</span>
          </p>
        )}
        {documentReuse.mustCustomize.length > 0 && (
          <ul className="card-list">
            {documentReuse.mustCustomize.map((doc, index) => (
              <li key={index}>{doc}</li>
            ))}
          </ul>
        )}
      </div>

      <div className="card-block">
        <h4 className="card-block__title">Country career snapshot</h4>
        {countrySnapshot.available ? (
          <>
            <p className="card-note">
              {countrySnapshot.country}
              {countrySnapshot.overallScore !== null && (
                <> · overall score <strong>{countrySnapshot.overallScore}</strong></>
              )}
            </p>
            <p className="card-provenance">{countrySnapshot.careerDataNote}</p>
          </>
        ) : (
          <p className="card-note">{countrySnapshot.label}</p>
        )}
      </div>

      <div className="card-block">
        <h4 className="card-block__title">Supervisor availability</h4>
        <p className="card-note">{supervisor.label}</p>
        {supervisor.note && <p className="card-note">{supervisor.note}</p>}
        {supervisor.sourceUrl && (
          <a
            href={supervisor.sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="card-link"
          >
            Source <span aria-hidden="true">&rarr;</span>
          </a>
        )}
        {supervisor.provenance === DATA_PROVENANCE.OFFICIAL && (
          <p className="card-provenance">Official state with source — no response rate is claimed.</p>
        )}
      </div>
    </CardExpandSection>
  )
}
