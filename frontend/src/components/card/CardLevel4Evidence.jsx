import CardExpandSection from './CardExpandSection'
import {
  deriveContactSupport,
  deriveFAQ,
  deriveOfficialSources,
  deriveSelectionCriteria,
  deriveTerms,
  deriveUnknowns,
  parseJsonColumn,
} from '../../utils/cardPresentation'

/* Level 4 — Deep evidence.
   The provenance layer: official documents, selection
   criteria, terms, source evidence, unknowns, change
   log, contact and FAQ. Everything here is traceable
   to a source or explicitly marked as not published. */
export default function CardLevel4Evidence({ scholarship, changeLog }) {
  const documents = parseJsonColumn(scholarship.documents)
  const selection = deriveSelectionCriteria(scholarship)
  const terms = deriveTerms(scholarship)
  const sources = deriveOfficialSources(scholarship)
  const unknowns = deriveUnknowns(scholarship)
  const faq = deriveFAQ(scholarship)
  const contact = deriveContactSupport(scholarship)

  return (
    <CardExpandSection level={4} title="Deep evidence" summary={`${sources.length} sources`}>
      <div className="card-block">
        <h4 className="card-block__title">Official documents</h4>
        {documents.length === 0 ? (
          <p className="card-note">No document checklist published on this record.</p>
        ) : (
          <ul className="card-list">
            {documents.map((doc, index) => (
              <li key={index}>{doc}</li>
            ))}
          </ul>
        )}
      </div>

      <div className="card-block">
        <h4 className="card-block__title">Selection criteria</h4>
        {selection.criteria.length === 0 ? (
          <p className="card-note">No selection criteria published on this record.</p>
        ) : (
          <ul className="card-list">
            {selection.criteria.map((criterion) => (
              <li key={criterion.name}>
                <strong>{criterion.name}</strong> — {criterion.detail}
              </li>
            ))}
          </ul>
        )}
        {!selection.officialWeightingAvailable && (
          <p className="card-provenance">The provider does not publish an official weighting.</p>
        )}
      </div>

      <div className="card-block">
        <h4 className="card-block__title">Terms and conditions</h4>
        {terms.academicRequirements.length > 0 && (
          <>
            <p className="card-facts-inline"><span className="card-note">Requirements:</span></p>
            <ul className="card-list">
              {terms.academicRequirements.map((requirement, index) => (
                <li key={index}>{requirement}</li>
              ))}
            </ul>
          </>
        )}
        {terms.coverageConditions.length > 0 && (
          <>
            <p className="card-facts-inline"><span className="card-note">Coverage conditions:</span></p>
            <ul className="card-list">
              {terms.coverageConditions.map((condition, index) => (
                <li key={index}>{condition}</li>
              ))}
            </ul>
          </>
        )}
        {terms.academicRequirements.length === 0 && terms.coverageConditions.length === 0 && (
          <p className="card-note">No terms published on this record.</p>
        )}
      </div>

      <div className="card-block">
        <h4 className="card-block__title">Source evidence</h4>
        {sources.length === 0 ? (
          <p className="card-note">No official source published on this record.</p>
        ) : (
          <ul className="card-list card-list--sources">
            {sources.map((source) => (
              <li key={source.url}>
                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="card-link"
                >
                  {source.title} <span aria-hidden="true">&rarr;</span>
                </a>
                <span className="card-provenance">
                  {source.source_type} · supports: {source.supports.join(', ')}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="card-block">
        <h4 className="card-block__title">Unknowns</h4>
        {unknowns.length === 0 ? (
          <p className="card-note">No known gaps on this record.</p>
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

      {changeLog && changeLog.length > 0 && (
        <div className="card-block">
          <h4 className="card-block__title">Change log</h4>
          <ul className="card-list card-list--changelog">
            {changeLog.map((entry, index) => (
              <li key={index}>
                <span className="card-changelog__date">{entry.created_at || entry.date}</span>
                <strong>{entry.field_name || entry.field}</strong>
                <span>{entry.change_type}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="card-block">
        <h4 className="card-block__title">Contact and support</h4>
        <dl className="card-facts">
          {contact.provider && (
            <div className="card-facts__row">
              <dt>Provider</dt>
              <dd>{contact.provider}</dd>
            </div>
          )}
          {contact.officialUrl && (
            <div className="card-facts__row">
              <dt>Official page</dt>
              <dd>
                <a href={contact.officialUrl} target="_blank" rel="noopener noreferrer" className="card-link">
                  Open <span aria-hidden="true">&rarr;</span>
                </a>
              </dd>
            </div>
          )}
          {contact.applicationPortal && (
            <div className="card-facts__row">
              <dt>Apply</dt>
              <dd>
                <a href={contact.applicationPortal} target="_blank" rel="noopener noreferrer" className="card-link">
                  Application portal <span aria-hidden="true">&rarr;</span>
                </a>
              </dd>
            </div>
          )}
        </dl>
        <p className="card-provenance">{contact.note}</p>
      </div>

      <div className="card-block">
        <h4 className="card-block__title">FAQ</h4>
        {faq.map((item) => (
          <div key={`${item.category}-${item.question}`} className="card-faq">
            <p className="card-faq__question">{item.question}</p>
            <p className="card-faq__answer">{item.answer}</p>
          </div>
        ))}
      </div>
    </CardExpandSection>
  )
}
