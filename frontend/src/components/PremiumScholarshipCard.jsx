import { useState } from 'react'
import { Link } from 'react-router-dom'
import ScholarshipImage from './ScholarshipImage'
import ScholarshipActions from './ScholarshipActions'
import { getLastVerifiedLabel, getScholarshipStatus } from '../utils/scholarshipPresentation'
import {
  deriveApplicationEffort,
  deriveContactSupport,
  deriveCostGap,
  deriveCountrySnapshot,
  deriveDeadline,
  deriveDocumentReuse,
  deriveFAQ,
  deriveFundingAmount,
  deriveFundingCoverage,
  deriveFundingTruth,
  deriveMatchScore,
  deriveMobilityBurden,
  deriveNextAction,
  deriveOfficialSources,
  deriveReadiness,
  deriveRecordKind,
  deriveRiskFlags,
  deriveSelectionCriteria,
  deriveSupervisorAvailability,
  deriveTerms,
  deriveTuitionStatus,
  deriveUnknowns,
  deriveVisaComplexity,
  normalizeRecord,
  parseJsonColumn,
  DATA_PROVENANCE,
  FUNDING_TRUTH,
} from '../utils/cardPresentation'
import './PremiumScholarshipCard.css'

/* ── The Premium card ─────────────────────────────
   Four levels, one tab switcher. Level 1 is the
   decision front; Levels 2–4 open on demand.

   Every value passes through cardPresentation, which
   enforces the data contract:
   - fully_funded is never read from a display label
   - unknown renders as "Not published", never "None"
   - estimated and official data are tagged separately
   - no fake dates — an unknown precision stays a window
   - match score, readiness and confidence are distinct
   - community testimony is never an official outcome
   - a category is labelled as a category, not a programme

   The panels read the catalogue's flat columns
   (tuition_coverage, fully_funded, deadline_display,
   ...) — the shape the API actually returns — not a
   hypothetical nested schema. */

const LEVEL_META = {
  1: { label: 'Overview', icon: '◉' },
  2: { label: 'Eligibility', icon: '◈' },
  3: { label: 'Planning', icon: '◇' },
  4: { label: 'Evidence', icon: '◆' },
}

function levelClassName(level) {
  return `premium-card__level--${level}`
}

function coerceText(value) {
  if (value === null || value === undefined) return null
  if (typeof value === 'string') return value.trim() || null
  if (Array.isArray(value)) {
    const joined = value.filter(Boolean).join(', ')
    return joined || null
  }
  if (typeof value === 'object') return null
  return String(value).trim() || null
}

function coerceList(items) {
  if (!Array.isArray(items)) return []
  return items.filter((item) => {
    const text = typeof item === 'string' ? item : item?.name || item?.label || ''
    return Boolean(text.trim())
  }).map((item) => (typeof item === 'string' ? item : item?.name || item?.label || String(item)))
}

function Badge({ children, tone = 'neutral' }) {
  if (!children) return null
  return <span className={`premium-card__badge premium-card__badge--${tone}`}>{children}</span>
}

function DataRow({ label, value, className = '' }) {
  const text = coerceText(value)
  if (!text) return null
  return (
    <div className={`premium-card__data-row ${className}`.trim()}>
      <dt>{label}</dt>
      <dd>{text}</dd>
    </div>
  )
}

function FlagList({ items, tone = 'warning' }) {
  const entries = coerceList(items)
  if (!entries.length) return null
  return (
    <ul className={`premium-card__flag-list premium-card__flag-list--${tone}`}>
      {entries.map((entry) => (
        <li key={entry}>{entry}</li>
      ))}
    </ul>
  )
}

function SourceChip({ source }) {
  const text = coerceText(source)
  if (!text) return null
  return <span className="premium-card__source-chip">{text}</span>
}

function VerifiedBadge({ status, date }) {
  const normalized = (status || '').toLowerCase()
  const isVerified = normalized === 'active' || normalized === 'verified'
  const label = isVerified ? 'Verified official source' : 'Needs verification'
  const tone = isVerified ? 'success' : 'warning'
  return (
    <span className={`premium-card__verified-badge premium-card__verified-badge--${tone}`}>
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path
          d="m8 12 2.2 2.2L16 9m4-3v6c0 5-3.4 8.7-8 10-4.6-1.3-8-5-8-10V6l8-3 8 3Z"
          fill="none"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="2"
        />
      </svg>
      {label}
      {date ? <span className="premium-card__verified-date"> · {date}</span> : null}
    </span>
  )
}

function MatchScore({ score, label }) {
  const numeric = typeof score === 'number' ? score : null
  const display = numeric !== null ? `${Math.round(numeric * 100)}%` : coerceText(label) || 'Not scored'
  const tone = numeric === null ? 'neutral' : numeric >= 0.75 ? 'success' : numeric >= 0.4 ? 'warning' : 'danger'
  return (
    <div className={`premium-card__match-score premium-card__match-score--${tone}`}>
      <span className="premium-card__match-score__value">{display}</span>
      <span className="premium-card__match-score__label">Match</span>
    </div>
  )
}

function ProgressBar({ value, label, tone }) {
  const numeric = typeof value === 'number' ? value : null
  const clamped = numeric !== null ? Math.max(0, Math.min(1, numeric)) : null
  const percent = clamped !== null ? `${Math.round(clamped * 100)}%` : null
  const resolvedTone = tone || (numeric === null ? 'neutral' : numeric >= 0.7 ? 'success' : numeric >= 0.4 ? 'warning' : 'danger')
  return (
    <div className="premium-card__progress">
      <div className="premium-card__progress__header">
        <span className="premium-card__progress__label">{label}</span>
        <span className="premium-card__progress__value">{percent ?? '—'}</span>
      </div>
      <div className="premium-card__progress__track">
        <div
          className={`premium-card__progress__fill premium-card__progress__fill--${resolvedTone}`}
          style={{ width: percent || '0%' }}
        />
      </div>
    </div>
  )
}

function LevelSwitcher({ current, onChange }) {
  return (
    <div className="premium-card__switcher" role="tablist" aria-label="Card detail level">
      {Object.entries(LEVEL_META).map(([level, meta]) => {
        const isActive = String(current) === String(level)
        return (
          <button
            key={level}
            type="button"
            role="tab"
            aria-selected={isActive}
            className={`premium-card__switcher__tab ${isActive ? 'premium-card__switcher__tab--active' : ''}`}
            onClick={() => onChange(Number(level))}
          >
            <span aria-hidden="true">{meta.icon}</span>
            <span className="premium-card__switcher__label">{meta.label}</span>
          </button>
        )
      })}
    </div>
  )
}

function ActionButtons({ scholarship }) {
  const detailHref = `/scholarships/${scholarship.id}`
  const applyHref = scholarship.application_link || scholarship.official_application_url
  return (
    <div className="premium-card__actions">
      <Link to={detailHref} className="premium-card__action premium-card__action--primary">
        View details
      </Link>
      {applyHref ? (
        <a
          href={applyHref}
          target="_blank"
          rel="noreferrer noopener"
          className="premium-card__action premium-card__action--secondary"
        >
          Apply
        </a>
      ) : (
        <Link to={detailHref} className="premium-card__action premium-card__action--secondary">
          Apply
        </Link>
      )}
      <span className="premium-card__action premium-card__action--save">
        <ScholarshipActions scholarshipId={scholarship.id} />
      </span>
    </div>
  )
}

/* Level 1 — the decision front. Only what a reader
   needs to decide. */
function OverviewPanel({ scholarship, matchResult }) {
  const fundingTruth = deriveFundingTruth(scholarship)
  const fundingAmount = deriveFundingAmount(scholarship)
  const tuitionStatus = deriveTuitionStatus(scholarship)
  const deadline = deriveDeadline(scholarship)
  const matchScore = deriveMatchScore(scholarship, matchResult)
  const nextAction = deriveNextAction(scholarship, matchResult)
  const recordKind = deriveRecordKind(scholarship)
  const verifiedOn = scholarship.last_verified_at || scholarship.last_verified_date || null
  const hasOfficialLogo = scholarship.image_kind === 'official_logo'
  const providerName = coerceText(scholarship.provider?.name) || coerceText(scholarship.provider) || coerceText(scholarship.official_source)
  const degreeText = scholarship.degree
  const destinationText = scholarship.country

  return (
    <div className={`premium-card__panel ${levelClassName(1)}`}>
      <div className="premium-card__panel__header">
        <div className="premium-card__identity">
          <ScholarshipImage scholarship={scholarship} className="premium-card__image" />
          <div>
            <h2>{scholarship.title}</h2>
            {recordKind.kind === 'category' && (
              <p className="premium-card__category">{recordKind.label}</p>
            )}
            {providerName ? <p className="premium-card__provider">{providerName}</p> : null}
            <div className="premium-card__signals">
              <VerifiedBadge status={scholarship.verification_status} date={getLastVerifiedLabel(verifiedOn)} />
              {hasOfficialLogo ? (
                <Badge tone="success">Official logo</Badge>
              ) : (
                <Badge tone="neutral">No logo</Badge>
              )}
            </div>
          </div>
        </div>
        <MatchScore score={matchScore.scored ? matchScore.score / 100 : null} label={matchScore.label} />
      </div>

      <dl className="premium-card__data premium-card__data--primary">
        <DataRow label="Degree · Destination" value={`${degreeText} · ${destinationText}`} />
        <DataRow
          label="Funding"
          value={fundingAmount.display ? `${fundingAmount.display}${fundingAmount.period ? ` / ${fundingAmount.period}` : ''}` : fundingTruth.label}
        />
        <DataRow label="Tuition" value={tuitionStatus.label} />
        <DataRow label="Deadline" value={deadline.label} />
        {!deadline.isExact && deadline.label !== 'Deadline not published' && (
          <DataRow label="Deadline precision" value={deadline.precision} />
        )}
      </dl>

      {fundingTruth.note && <p className="premium-card__funding-note">{fundingTruth.note}</p>}

      <div className="premium-card__next-action">
        <span className="premium-card__next-action__label">Next action</span>
        <span className="premium-card__next-action__value">{nextAction.label}</span>
      </div>

      <ActionButtons scholarship={scholarship} />
    </div>
  )
}

/* Level 2 — quick decision. */
function DecisionPanel({ scholarship, matchResult }) {
  const matchScore = deriveMatchScore(scholarship, matchResult)
  const readiness = deriveReadiness(scholarship)
  const riskFlags = deriveRiskFlags(scholarship)
  const fundingCoverage = deriveFundingCoverage(scholarship)
  const unknowns = deriveUnknowns(scholarship)
  const recordKind = deriveRecordKind(scholarship)
  const eligibilitySummary = scholarship.eligibility_summary
  const eligibilityItems = parseJsonColumn(scholarship.eligibility)

  const readinessItems = [
    { label: 'Deadline', present: readiness.missing.includes('deadline') === false },
    { label: 'Funding', present: readiness.missing.includes('funding') === false },
    { label: 'Eligibility', present: readiness.missing.includes('eligibility') === false },
    { label: 'Documents', present: readiness.missing.includes('documents') === false },
    { label: 'Apply link', present: readiness.missing.includes('application_link') === false },
  ]

  return (
    <div className={`premium-card__panel ${levelClassName(2)}`}>
      <div className="premium-card__panel__header">
        <h3>Quick decision</h3>
        <MatchScore score={matchScore.scored ? matchScore.score / 100 : null} label={matchScore.label} />
      </div>

      <div className="premium-card__panel__body">
        {recordKind.kind === 'category' && (
          <p className="premium-card__category-note">{recordKind.note}</p>
        )}

        <section className="premium-card__section">
          <h4>Why it matches</h4>
          {matchScore.scored ? (
            <p className="premium-card__match-line">
              <strong>{matchScore.label}</strong>
              <span className="premium-card__provenance">derived from your Match profile</span>
            </p>
          ) : (
            <p className="premium-card__empty">{matchScore.hint}</p>
          )}
          {eligibilitySummary && <p className="premium-card__text">{eligibilitySummary}</p>}
          {eligibilityItems.length > 0 && <FlagList items={eligibilityItems} tone="success" />}
        </section>

        <section className="premium-card__section">
          <h4>Application readiness</h4>
          <div className="premium-card__readiness">
            {readinessItems.map((item) => (
              <ProgressBar
                key={item.label}
                label={item.label}
                value={item.present ? 1 : 0}
                tone={item.present ? 'success' : 'danger'}
              />
            ))}
          </div>
          <DataRow label="Status" value={readiness.label} />
          <DataRow label="Fields published" value={`${readiness.present} of ${readiness.total}`} />
        </section>

        <section className="premium-card__section">
          <h4>What is missing</h4>
          {unknowns.length ? (
            <ul className="premium-card__unknown-list">
              {unknowns.map((unknown) => (
                <li key={unknown.field}>
                  <strong>{unknown.field}</strong> — {unknown.note}
                </li>
              ))}
            </ul>
          ) : (
            <p className="premium-card__empty">No major gaps on this record.</p>
          )}
        </section>

        <section className="premium-card__section">
          <h4>Funding coverage</h4>
          <DataRow label="Tuition" value={fundingCoverage.tuition} />
          <DataRow label="Living costs" value={fundingCoverage.living} />
          <DataRow label="Travel" value={fundingCoverage.travel} />
          {fundingCoverage.items.length > 0 && <FlagList items={fundingCoverage.items} tone="success" />}
          {fundingCoverage.provenance === DATA_PROVENANCE.DERIVED && (
            <p className="premium-card__provenance">No itemised benefits published on this record.</p>
          )}
        </section>

        <section className="premium-card__section">
          <h4>Risk flags</h4>
          {riskFlags.length ? (
            <ul className="premium-card__risk-list">
              {riskFlags.map((flag) => (
                <li key={flag.label} className={`premium-card__risk premium-card__risk--${flag.severity}`}>
                  <strong>{flag.label}</strong>
                  <span>{flag.detail}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="premium-card__empty">No risk flags on this record.</p>
          )}
        </section>
      </div>
    </div>
  )
}

/* Level 3 — practical planning. */
function PlanningPanel({ scholarship, countryIntelligence }) {
  const effort = deriveApplicationEffort(scholarship)
  const costGap = deriveCostGap(scholarship)
  const mobility = deriveMobilityBurden(scholarship)
  const visa = deriveVisaComplexity(scholarship)
  const documentReuse = deriveDocumentReuse(scholarship)
  const supervisor = deriveSupervisorAvailability(scholarship)
  const countrySnapshot = deriveCountrySnapshot(scholarship, countryIntelligence)
  const fundingTruth = deriveFundingTruth(scholarship)

  return (
    <div className={`premium-card__panel ${levelClassName(3)}`}>
      <div className="premium-card__panel__header">
        <h3>Practical planning</h3>
      </div>

      <div className="premium-card__panel__body">
        <section className="premium-card__section">
          <h4>Application effort</h4>
          <DataRow label="Complexity" value={effort.label} />
          <DataRow label="Documents" value={effort.documentsCount} />
          <DataRow label="Essays" value={effort.essayCount} />
          <DataRow label="References" value={effort.referenceCount} />
        </section>

        <section className="premium-card__section">
          <h4>Cost reality</h4>
          <DataRow label="Funding status" value={fundingTruth.label} />
          <DataRow label="Cost gap" value={costGap.label} />
          {costGap.note && <p className="premium-card__text">{costGap.note}</p>}
        </section>

        <section className="premium-card__section">
          <h4>Mobility burden</h4>
          <DataRow label="Intensity" value={mobility.label} />
          {mobility.note && <p className="premium-card__text">{mobility.note}</p>}
        </section>

        <section className="premium-card__section">
          <h4>Visa complexity</h4>
          <DataRow label="Visa" value={visa.label} />
          {visa.note && <p className="premium-card__text">{visa.note}</p>}
        </section>

        <section className="premium-card__section">
          <h4>Document reuse</h4>
          {documentReuse.reusable.length > 0 && (
            <div className="premium-card__reuse-group">
              <strong>Reusable across applications</strong>
              <FlagList items={documentReuse.reusable} tone="success" />
            </div>
          )}
          {documentReuse.mustCustomize.length > 0 && (
            <div className="premium-card__reuse-group">
              <strong>Must be customised per application</strong>
              <FlagList items={documentReuse.mustCustomize} tone="warning" />
            </div>
          )}
        </section>

        <section className="premium-card__section">
          <h4>Country career snapshot</h4>
          {countrySnapshot.available ? (
            <>
              <DataRow label="Country" value={countrySnapshot.country} />
              {countrySnapshot.overallScore !== null && (
                <DataRow label="Overall score" value={countrySnapshot.overallScore} />
              )}
              <p className="premium-card__provenance">{countrySnapshot.careerDataNote}</p>
            </>
          ) : (
            <p className="premium-card__empty">{countrySnapshot.label}</p>
          )}
        </section>

        <section className="premium-card__section">
          <h4>Supervisor availability</h4>
          <DataRow label="State" value={supervisor.label} />
          {supervisor.note && <p className="premium-card__text">{supervisor.note}</p>}
          {supervisor.sourceUrl && (
            <a href={supervisor.sourceUrl} target="_blank" rel="noreferrer noopener" className="premium-card__source-link">
              Source <span aria-hidden="true">&rarr;</span>
            </a>
          )}
          {supervisor.provenance === DATA_PROVENANCE.OFFICIAL && (
            <p className="premium-card__provenance">Official state with source — no response rate is claimed.</p>
          )}
        </section>
      </div>
    </div>
  )
}

/* Level 4 — deep evidence. */
function EvidencePanel({ scholarship, changeLog }) {
  const documents = parseJsonColumn(scholarship.documents)
  const selection = deriveSelectionCriteria(scholarship)
  const terms = deriveTerms(scholarship)
  const sources = deriveOfficialSources(scholarship)
  const unknowns = deriveUnknowns(scholarship)
  const faq = deriveFAQ(scholarship)
  const contact = deriveContactSupport(scholarship)
  const requirements = parseJsonColumn(scholarship.requirements)

  return (
    <div className={`premium-card__panel ${levelClassName(4)}`}>
      <div className="premium-card__panel__header">
        <h3>Deep evidence</h3>
        <span className="premium-card__evidence-badge">{sources.length} sources</span>
      </div>

      <div className="premium-card__panel__body">
        <section className="premium-card__section">
          <h4>Official sources</h4>
          {sources.length ? (
            <ul className="premium-card__source-list">
              {sources.map((source) => (
                <li key={source.url}>
                  <a href={source.url} target="_blank" rel="noreferrer noopener" className="premium-card__source-link">
                    {source.title} <span aria-hidden="true">&rarr;</span>
                  </a>
                  <SourceChip source={source.source_type} />
                  <span className="premium-card__source-date">supports: {source.supports.join(', ')}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="premium-card__empty">No official source published on this record.</p>
          )}
        </section>

        <section className="premium-card__section">
          <h4>Official documents</h4>
          {documents.length ? (
            <FlagList items={documents} tone="neutral" />
          ) : (
            <p className="premium-card__empty">No document checklist published on this record.</p>
          )}
          {requirements.length > 0 && (
            <div className="premium-card__reuse-group">
              <strong>Requirements</strong>
              <FlagList items={requirements} tone="warning" />
            </div>
          )}
        </section>

        <section className="premium-card__section">
          <h4>Selection criteria</h4>
          {selection.criteria.length ? (
            <ul className="premium-card__criteria-list">
              {selection.criteria.map((criterion) => (
                <li key={criterion.name}>
                  <strong>{criterion.name}</strong> — {criterion.detail}
                </li>
              ))}
            </ul>
          ) : (
            <p className="premium-card__empty">No selection criteria published on this record.</p>
          )}
          {!selection.officialWeightingAvailable && (
            <p className="premium-card__provenance">The provider does not publish an official weighting.</p>
          )}
        </section>

        <section className="premium-card__section">
          <h4>Terms and conditions</h4>
          {terms.academicRequirements.length > 0 && (
            <div className="premium-card__reuse-group">
              <strong>Requirements to maintain</strong>
              <FlagList items={terms.academicRequirements} tone="neutral" />
            </div>
          )}
          {terms.coverageConditions.length > 0 && (
            <div className="premium-card__reuse-group">
              <strong>Coverage conditions</strong>
              <FlagList items={terms.coverageConditions} tone="neutral" />
            </div>
          )}
          {terms.academicRequirements.length === 0 && terms.coverageConditions.length === 0 && (
            <p className="premium-card__empty">No terms published on this record.</p>
          )}
        </section>

        <section className="premium-card__section">
          <h4>Unknowns</h4>
          {unknowns.length ? (
            <ul className="premium-card__unknown-list">
              {unknowns.map((unknown) => (
                <li key={unknown.field}>
                  <strong>{unknown.field}</strong> — {unknown.note}
                </li>
              ))}
            </ul>
          ) : (
            <p className="premium-card__empty">No known gaps on this record.</p>
          )}
        </section>

        <section className="premium-card__section">
          <h4>Data quality</h4>
          <DataRow label="Coverage" value={scholarship.data_quality?.coverage_level} />
          {Array.isArray(scholarship.data_quality?.estimated_fields) && scholarship.data_quality.estimated_fields.length > 0 && (
            <div className="premium-card__reuse-group">
              <strong>Estimated by research (not official)</strong>
              <FlagList items={scholarship.data_quality.estimated_fields} tone="warning" />
            </div>
          )}
          {Array.isArray(scholarship._estimated_fields) && scholarship._estimated_fields.length > 0 && (
            <div className="premium-card__reuse-group">
              <strong>Derived from title (estimated)</strong>
              <FlagList items={scholarship._estimated_fields} tone="warning" />
            </div>
          )}
          {Array.isArray(scholarship.data_quality?.missing_key_fields) && scholarship.data_quality.missing_key_fields.length > 0 && (
            <div className="premium-card__reuse-group">
              <strong>Missing key fields</strong>
              <FlagList items={scholarship.data_quality.missing_key_fields} tone="warning" />
            </div>
          )}
          <p className="premium-card__provenance">
            Estimated and official data are kept separate. Community testimony is never shown as an official outcome.
          </p>
        </section>

        {changeLog && changeLog.length > 0 && (
          <section className="premium-card__section">
            <h4>Change log</h4>
            <ul className="premium-card__changelog">
              {changeLog.slice(0, 8).map((entry, idx) => (
                <li key={idx}>
                  <span>{entry.created_at || entry.date || 'Undated'}</span>
                  <span>{coerceText(entry.field_name || entry.field) || 'Update'}</span>
                  <span>{coerceText(entry.change_type) || 'updated'}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        <section className="premium-card__section">
          <h4>Contact and support</h4>
          <DataRow label="Provider" value={contact.provider} />
          {contact.officialUrl && (
            <a href={contact.officialUrl} target="_blank" rel="noreferrer noopener" className="premium-card__source-link">
              Official page <span aria-hidden="true">&rarr;</span>
            </a>
          )}
          {contact.applicationPortal && (
            <a href={contact.applicationPortal} target="_blank" rel="noreferrer noopener" className="premium-card__source-link">
              Application portal <span aria-hidden="true">&rarr;</span>
            </a>
          )}
          <p className="premium-card__provenance">{contact.note}</p>
        </section>

        <section className="premium-card__section">
          <h4>FAQ</h4>
          {faq.map((item) => (
            <div key={`${item.category}-${item.question}`} className="premium-card__faq-item">
              <p className="premium-card__faq-question">{item.question}</p>
              <p className="premium-card__faq-answer">{item.answer}</p>
            </div>
          ))}
        </section>
      </div>
    </div>
  )
}

export default function PremiumScholarshipCard({ scholarship, matchResult, countryIntelligence, changeLog }) {
  const [level, setLevel] = useState(1)
  /* Flatten either source shape — catalogue columns or the
     rich research schema — into the one field set every
     panel reads. Done once here, not per panel. */
  const record = normalizeRecord(scholarship)
  const deadlineStatus = getScholarshipStatus(record)
  const fundingTruth = deriveFundingTruth(record)

  return (
    <article
      className={`premium-card premium-card--${deadlineStatus.className} premium-card--${fundingTruth.truth}`}
      aria-label={`${record.title} scholarship card`}
    >
      <span className="premium-card__edge" aria-hidden="true" />

      <LevelSwitcher current={level} onChange={setLevel} />

      <div className="premium-card__stage" role="tabpanel" aria-label={`Level ${level} details`}>
        {level === 1 && <OverviewPanel scholarship={record} matchResult={matchResult} />}
        {level === 2 && <DecisionPanel scholarship={record} matchResult={matchResult} />}
        {level === 3 && <PlanningPanel scholarship={record} countryIntelligence={countryIntelligence} />}
        {level === 4 && <EvidencePanel scholarship={record} changeLog={changeLog} />}
      </div>
    </article>
  )
}

/* FUNDING_TRUTH is re-exported for callers that need to
   branch on the funding truth outside the card. */
export { FUNDING_TRUTH }
