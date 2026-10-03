import { Link } from 'react-router-dom'

import ScholarshipImage from '../ScholarshipImage'
import { MatchReadiness } from './MatchReadiness'

function eligibilityTone(result) {
  if (result.eligibility === 'ELIGIBLE') return 'eligible'
  if (result.eligibility === 'NEEDS_VERIFICATION') return 'verify'
  return 'blocked'
}

function eligibilityLabel(result) {
  if (result.eligibility === 'ELIGIBLE') return 'Eligible'
  if (result.eligibility === 'NEEDS_VERIFICATION') return 'Needs verification'
  return 'Not eligible'
}

/**
 * Reason codes that assert something in the student's favour.
 *
 * The engine returns one reason per thing it established, which is the right
 * granularity for an audit trail but not for a heading called "Why this matches
 * you". A reason such as "no academic result was supplied" is true and useful -
 * it belongs under what needs attention, where the gaps already say it - and
 * putting it next to a tick mark would claim it as a reason the student matches.
 *
 * Anything not listed here is treated as context rather than as a match.
 */
const MATCH_REASON_CODES = new Set([
  'ACADEMIC_ABOVE_MINIMUM',
  'ACADEMIC_MEETS_MINIMUM',
  'ACADEMIC_AT_PUBLISHED_MINIMUM',
  'ACADEMIC_SUBJECT_MATCH',
  'FIELD_EXACT',
  'FIELD_RELATED',
  'FUNDING_FULL_MATCH',
  'FUNDING_TUITION_MATCH',
  'REQUIREMENTS_DOCUMENTED',
  'LANGUAGE_MEETS_REQUIREMENT',
  'LANGUAGE_EXCEEDS_REQUIREMENT',
  'LANGUAGE_NOT_REQUIRED',
  'PREFERENCE_COUNTRY_MATCH',
  'DEADLINE_COMFORTABLE',
  'DEADLINE_APPROACHING',
  'DEADLINE_WORKABLE',
  'ELIGIBILITY_VERIFIED',
  'ELIGIBILITY_NO_PUBLISHED_CONDITIONS',
])

function matchReasons(result) {
  return (result.reasons ?? []).filter((reason) => MATCH_REASON_CODES.has(reason.code))
}

/**
 * The card hierarchy is a reading order, not a data dump:
 *
 *   which scholarship -> how good a fit -> whether you can apply at all
 *   -> how much we trust the record -> what is missing -> what to do next
 *
 * The arithmetic stays collapsed behind "How this score is calculated". A student
 * deciding between two scholarships needs the comparison and the caveat first;
 * the effective weights are the answer to a second question.
 */
function MatchCard({ result, isCompared, onToggleCompare, compareDisabled }) {
  const tone = eligibilityTone(result)
  const hasFit = typeof result.fit_score === 'number'
  const needsVerification = result.eligibility === 'NEEDS_VERIFICATION'

  const topReasons = matchReasons(result).slice(0, 3)
  const attention = (result.gaps ?? []).slice(0, 3)
  const blockers = result.eligibility_detail?.blockers ?? []
  const unverified = result.eligibility_detail?.unverified ?? []
  const nextActions = (result.actions ?? []).slice()
  const primaryAction = nextActions.find((item) => item.url) ?? nextActions[0]

  return (
    <article
      className={`match-card is-${tone}`}
      data-testid="match-card"
      data-scholarship-id={result.scholarship_id}
      data-eligibility={result.eligibility}
      data-fit-label={result.fit_label}
      aria-labelledby={`match-card-${result.scholarship_id}-title`}
    >
      <div className="match-card__header">
        <div className="match-card__logo">
          <ScholarshipImage
            src={result.image_url}
            alt={result.image_alt_text || `${result.scholarship_name} logo`}
          />
        </div>

        <div className="match-card__identity">
          <h3 id={`match-card-${result.scholarship_id}-title`}>
            <Link to={result.detail_url}>{result.scholarship_name}</Link>
          </h3>
          <p className="match-card__institution">
            {result.institution || 'Institution not published'}
          </p>
          <p className="match-card__meta">
            <span>{result.country}</span>
            {result.degree_levels ? <span>{result.degree_levels}</span> : null}
            {result.field_label ? <span>{result.field_label}</span> : null}
            {result.days_to_deadline !== null && result.days_to_deadline !== undefined ? (
              <span>
                {result.days_to_deadline} days left
                {result.deadline_precision === 'month' ? ' (month-only estimate)' : ''}
              </span>
            ) : (
              <span>No fixed deadline published</span>
            )}
          </p>
        </div>

        <div className="match-card__score">
          <span className="match-card__score-label">Fit</span>
          <span
            className={`match-card__score-value${hasFit ? '' : ' is-unscored'}`}
            data-testid="match-fit-score"
          >
            {hasFit ? (
              <>
                {result.fit_score}
                <small> / 100</small>
              </>
            ) : (
              'N/A'
            )}
          </span>
          {hasFit ? (
            <span className={`match-card__fit-label is-${tone}`} data-testid="match-fit-label">
              {result.fit_label_display}
            </span>
          ) : (
            <span className="match-card__fit-label is-blocked">{result.fit_label_display}</span>
          )}
          {needsVerification ? (
            <span className="match-visually-hidden">
              Fit is shown, but this scholarship needs verification before you can rely on it.
            </span>
          ) : null}
        </div>
      </div>

      <p className={`match-card__eligibility is-${tone}`} data-testid="match-eligibility">
        <strong>{eligibilityLabel(result)}</strong>
        {result.eligibility_detail?.detail ? ` — ${result.eligibility_detail.detail}` : ''}
      </p>

      <p className="match-card__confidence" data-testid="match-confidence">
        {result.confidence_label_display} confidence · {result.data_coverage}% data coverage
      </p>

      {blockers.length > 0 ? (
        <div className="match-card__blockers" data-testid="match-blockers">
          <h4>What does not apply to you</h4>
          <ul className="match-reasons">
            {blockers.map((item, index) => (
              <li key={`${item.kind}-${index}`}>
                <span aria-hidden="true">✕</span>
                <span>{item.summary}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="match-card__explanation">
        <div className="match-card__block">
          <h4>Why this matches you</h4>
          {topReasons.length > 0 ? (
            <ul className="match-reasons" data-testid="match-reasons">
              {topReasons.map((reason) => (
                <li key={reason.code}>
                  <span aria-hidden="true">✓</span>
                  <span>{reason.message}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="match-reasons" data-testid="match-reasons">
              Nothing about this scholarship was confirmed as a match for your profile.
            </p>
          )}
        </div>

        <div className="match-card__block">
          <h4>What may need attention</h4>
          {attention.length > 0 ? (
            <ul className="match-gaps" data-testid="match-gaps">
              {attention.map((gap) => (
                <li key={`${gap.code}-${gap.component ?? 'general'}`}>
                  <span aria-hidden="true">○</span>
                  <span>{gap.message}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="match-gaps">Nothing outstanding for this scholarship.</p>
          )}
        </div>
      </div>

      <MatchReadiness readiness={result.readiness} blockers={blockers} unverified={unverified} />

      <div className="match-card__next">
        <h4>Next best action</h4>
        {primaryAction ? (
          primaryAction.url ? (
            <a
              className="match-card__cta"
              href={primaryAction.url}
              target="_blank"
              rel="noopener noreferrer"
              data-testid="match-primary-action"
            >
              {primaryAction.url_label || 'Visit Official Source'}
            </a>
          ) : (
            <p data-testid="match-primary-action">{primaryAction.message}</p>
          )
        ) : (
          <p>No action outstanding.</p>
        )}
        {nextActions.length > 1 ? (
          <details className="match-card__more-actions">
            <summary>{nextActions.length - 1} more suggested action{nextActions.length - 1 === 1 ? '' : 's'}</summary>
            <ul>
              {nextActions.slice(1).map((item) => (
                <li key={item.code}>
                  {item.url ? (
                    <a href={item.url} target="_blank" rel="noopener noreferrer">
                      {item.url_label || item.message}
                    </a>
                  ) : (
                    item.message
                  )}
                </li>
              ))}
            </ul>
          </details>
        ) : null}
      </div>

      <details className="how-calc match-card__how">
        <summary>How this score is calculated</summary>
        <div className="how-calc__body">
          <ul className="how-calc__components">
            {(result.score_breakdown ?? []).map((component) => (
              <li
                key={component.name}
                className={`how-calc__component${component.score === null ? ' is-unevaluated' : ''}`}
              >
                <span className="how-calc__name">{component.label}</span>
                <span className="how-calc__weight">
                  {Math.round(component.weight * 100)}%
                </span>
                <span className="how-calc__value">
                  {component.score === null ? (
                    <abbr title="Not evaluated">—</abbr>
                  ) : (
                    component.score
                  )}
                </span>
                <p className="how-calc__detail">{component.detail}</p>
              </li>
            ))}
          </ul>

          <p className="how-calc__coverage">
            Coverage: {result.data_coverage}% · Evaluated: {result.evaluated_components} of{' '}
            {result.total_components}
          </p>

          <details className="how-calc__advanced">
            <summary>Advanced: effective weight, contribution and sensitivity</summary>
            <ul className="how-calc__components">
              {(result.score_breakdown ?? [])
                .filter((component) => component.effective_weight !== null)
                .map((component) => (
                  <li key={`effective-${component.name}`} className="how-calc__component">
                    <span className="how-calc__name">{component.label}</span>
                    <span className="how-calc__weight">
                      effective {(component.effective_weight * 100).toFixed(1)}%
                    </span>
                    <span className="how-calc__value">
                      +{component.contribution?.toFixed(2)}
                    </span>
                  </li>
                ))}
            </ul>
            {result.sensitivity ? (
              <p className="how-calc__coverage">
                If every unevaluated dimension turned out badly, this score could fall to{' '}
                {result.sensitivity.lower_bound}; if they all turned out perfectly, it could
                reach {result.sensitivity.upper_bound}. {result.sensitivity.caveat}
              </p>
            ) : (
              <p className="how-calc__coverage">
                Every dimension was evaluated, so there is no unknown left to model.
              </p>
            )}
            <p className="how-calc__coverage">
              Missing information is not treated as zero. An unevaluated dimension is
              removed from the calculation and reported as a gap instead.
            </p>
          </details>
        </div>
      </details>

      {result.requirements?.length > 0 ? (
        <details className="match-card__published">
          <summary>Published requirements ({result.requirements.length})</summary>
          <dl>
            {result.requirements.map((item, index) => (
              <div key={`${item.kind}-${index}`}>
                <dt>
                  <span
                    className={`match-requirement-status is-${String(item.status).toLowerCase()}`}
                  >
                    {item.status}
                  </span>
                  {item.kind.replace(/_/g, ' ').toLowerCase()}
                </dt>
                <dd>
                  {item.summary}
                  {item.raw_quote ? <q> {item.raw_quote}</q> : null}
                  {item.provenance_url ? (
                    <>
                      {' '}
                      <a
                        href={item.provenance_url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        Source
                      </a>
                    </>
                  ) : null}
                </dd>
              </div>
            ))}
          </dl>
        </details>
      ) : null}

      <footer className="match-card__footer">
        <Link className="match-card__link" to={result.detail_url}>
          View full details
        </Link>
        {onToggleCompare ? (
          <label className="match-card__compare">
            <input
              type="checkbox"
              checked={Boolean(isCompared)}
              disabled={compareDisabled && !isCompared}
              onChange={() => onToggleCompare(result.scholarship_id)}
              data-testid="compare-toggle"
            />
            Compare
          </label>
        ) : null}
      </footer>
    </article>
  )
}

export default MatchCard