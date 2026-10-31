import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import ScholarshipImage from './ScholarshipImage'
import ScholarshipActions from './ScholarshipActions'
import SupervisorCta from './SupervisorCta'
import { getDeadlineLabel, getLastVerifiedLabel, getScholarshipStatus, matchesDegreeFilter, matchesFundingFilter } from '../utils/scholarshipPresentation'
import { getConfirmedOfficialLogo, getMonogramInitial } from '../utils/scholarshipLogos'
import { readText, readList, readUrl } from '../utils/scholarshipDetail'
import './ScholarshipCard.css'

export default function ScholarshipCard({ scholarship, index = 0, onOpenDetails }) {
  const deadlineStatus = getScholarshipStatus(scholarship)
  const cardRef = useRef(null)
  const [isExpanded, setIsExpanded] = useState(false)

  const verificationState = scholarship.verification_status || 'needs_review'
  const isVerified = verificationState === 'active'
  const needsReview = !isVerified

  const officialLogo = getConfirmedOfficialLogo(scholarship)
  const hasOfficialLogo = Boolean(officialLogo)
  const monogramInitial = getMonogramInitial(scholarship?.title)
  const verifiedOn = scholarship.last_verified_at || null

  // Academic eligibility fields
  const departments = readList(scholarship.departments)
  const eligibleFields = readList(scholarship.eligible_fields)
  const eligibleProgrammes = readList(scholarship.eligible_programmes)

  // Helper functions for expanded section
  const description = readText(scholarship.description)
  const eligibility = readList(scholarship.eligibility)
  const eligibilitySummary = readText(scholarship.eligibility_summary)
  const benefits = readList(scholarship.benefits)
  const coverage = readList(scholarship.coverage)
  const requirements = readList(scholarship.requirements)
  const documents = readList(scholarship.documents) || readList(scholarship.required_documents)
  const applicationMethod = readList(scholarship.application_method)
  const selectionNotes = readText(scholarship.selection_notes)
  const englishRequirement = readText(scholarship.english_requirement)
  const fundingAmount = scholarship.funding_amount
  const fundingCurrency = scholarship.funding_currency
  const fundingPeriod = scholarship.funding_period
  const fullyFunded = scholarship.fully_funded
  const tuitionCoverage = scholarship.tuition_coverage
  const livingCostCoverage = scholarship.living_cost_coverage
  const travelCoverage = scholarship.travel_coverage
  const duration = readText(scholarship.duration)
  const applicationPeriod = readText(scholarship.application_period)
  const programType = readText(scholarship.program_type)
  const officialSourceUrl = readUrl(scholarship.official_source_url)
  const catalogueUrl = readUrl(scholarship.catalogue_url)
  const officialUpdatesUrl = readUrl(scholarship.official_updates_url)
  const applicationLink = readUrl(scholarship.application_link)

  const toggleExpand = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setIsExpanded(!isExpanded)
  }

  /* The pointer-driven light — the gloss band, the spotlight and the 3D
     tilt — is attached once at the shell level by usePremiumPointer,
     exactly as the reference's single document listener does it. This
     component keeps no pointer state of its own: one listener measuring
     only the card under the cursor beats twelve listeners each
     re-measuring on every move event. The ref is kept for local
     behaviour, and the entrance stagger is driven by --n. */

  /* The card's own "how well does this fit" answer. The reference's bar
     is driven by the number of criteria a row meets out of the criteria
     in play; the app has the same thing available — funding certainty,
     level breadth, deadline proximity, and whether the record is
     verified — so the meter states a real ratio rather than a decoration.
     A fully-funded, open, verified programme scores all four. */
  const criteria = [
    matchesFundingFilter(scholarship.funding, 'Fully Funded'),
    !(scholarship.deadline_precision === 'month'),
    matchesDegreeFilter(scholarship.degree, 'Bachelor'),
    isVerified,
  ]
  const fitCount = criteria.filter(Boolean).length
  const fitTotal = criteria.length
  const fitLabel = `Fit ${fitCount}/${fitTotal}`
  const fitValue = String(fitCount)
  const fitPercent = Math.round((fitCount / fitTotal) * 100)

  return (
    <article
      ref={cardRef}
      className={`scholarship-card p-card p-rise scholarship-card--${deadlineStatus.className}`}
      style={{ '--n': index ?? 0 }}
    >
      <span className="scholarship-card__edge" aria-hidden="true" />

      <ScholarshipImage scholarship={scholarship} className="scholarship-card__image" />

      <div className="scholarship-card__header">
        <div className="scholarship-card__topline">
          <span className={`scholarship-card__status scholarship-card__status--${deadlineStatus.className}`}>{deadlineStatus.label}</span>
          <span className="p-tag scholarship-card__badge">{scholarship.funding}</span>
        </div>

        {/* The reference's letter square: one serif initial in a raised
            ivory tile. It is the mark the card is recognised by, and it is
            why a card reads as a physical object rather than as a panel —
            the tile has a top sheen, a contact shade and a soft drop, so
            it catches the same light as the card it sits on. */}
        <div className="scholarship-card__top">
          <div className="scholarship-card__mono" aria-label={hasOfficialLogo ? `${scholarship.title} official logo` : undefined}>
            {officialLogo ? (
              <img
                src={officialLogo.url}
                alt={officialLogo.altText}
                className="scholarship-card__logo-img"
                onError={(e) => {
                  e.currentTarget.style.display = 'none'
                  if (e.currentTarget.nextSibling) e.currentTarget.nextSibling.style.display = 'block'
                }}
              />
            ) : null}
            <span
              className="scholarship-card__mono-fallback"
              style={{ display: officialLogo ? 'none' : 'block' }}
              aria-hidden="true"
            >
              {monogramInitial}
            </span>
          </div>
          <div className="scholarship-card__heading">
            <h2>{scholarship.title}</h2>
            <p className="scholarship-card__where">{scholarship.country}</p>
          </div>
          {onOpenDetails && (
            <button
              type="button"
              className="scholarship-card__dtl-btn"
              onClick={() => onOpenDetails(scholarship)}
            >
              Details
            </button>
          )}
        </div>

        {/* The Provenance Rule. The square is the identity: filled when the
            record carries a validated official logo, hollow when it does not.
            Keyed on image_kind rather than image_url on purpose — 401 records
            carry an image but only 387 of them are official_logo, and the rest
            must read as unproven rather than borrow a mark they have not
            earned. The hollow state is part of the design, not a gap. */}
        <div
          className={`scholarship-card__title-rule${
            hasOfficialLogo ? '' : ' scholarship-card__title-rule--unverified'
          }`}
          aria-hidden="true"
        />
        <small className="scholarship-card__citation">
          ↳ {needsReview
            ? 'Not yet re-checked against the official page'
            : hasOfficialLogo
              ? 'Official source captured'
              : 'No official logo'}
          {verifiedOn ? ` · last checked ${verifiedOn}` : ''}
        </small>

        {scholarship.provider && (
          <p className="scholarship-card__provider">{scholarship.provider}</p>
        )}

        <div className="scholarship-card__signals">
          <span className={isVerified ? 'p-tag scholarship-card__verified' : 'p-tag scholarship-card__unverified'}>
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="m8 12 2.2 2.2L16 9m4-3v6c0 5-3.4 8.7-8 10-4.6-1.3-8-5-8-10V6l8-3 8 3Z" />
            </svg>
            {isVerified ? 'Verified official source' : 'Confirm with provider'}
          </span>
          {scholarship.last_verified_at && (
            <span className="scholarship-card__verification-date">{getLastVerifiedLabel(scholarship.last_verified_at)}</span>
          )}
        </div>
      </div>

      <dl className="scholarship-card__details">
        <div className={`scholarship-card__detail scholarship-card__detail--deadline scholarship-card__detail--${deadlineStatus.className}`}>
          <dt>Deadline</dt>
          <dd>{getDeadlineLabel(scholarship)}</dd>
        </div>
        <div className="scholarship-card__detail">
          <dt>Location</dt>
          <dd>{scholarship.country}</dd>
        </div>
        <div className="scholarship-card__detail">
          <dt>Level</dt>
          <dd>{scholarship.degree}</dd>
        </div>
        {(departments.length > 0 || eligibleFields.length > 0 || eligibleProgrammes.length > 0) && (
          <div className="scholarship-card__detail scholarship-card__detail--academic">
            <dt>Academic scope</dt>
            <dd className="scholarship-card__academic-preview">
              {departments.length > 0 && (
                <span className="scholarship-card__academic-item">
                  <span className="scholarship-card__academic-label">Departments:</span>
                  {departments.slice(0, 2).map((d, i) => (
                    <span key={i} className="scholarship-card__academic-value">{d}{departments.length > 2 && i === 1 ? ` +${departments.length - 2} more` : ''}</span>
                  ))}
                </span>
              )}
              {eligibleFields.length > 0 && (
                <span className="scholarship-card__academic-item">
                  <span className="scholarship-card__academic-label">Fields:</span>
                  {eligibleFields.slice(0, 2).map((f, i) => (
                    <span key={i} className="scholarship-card__academic-value">{f}{eligibleFields.length > 2 && i === 1 ? ` +${eligibleFields.length - 2} more` : ''}</span>
                  ))}
                </span>
              )}
              {eligibleProgrammes.length > 0 && (
                <span className="scholarship-card__academic-item">
                  <span className="scholarship-card__academic-label">Programmes:</span>
                  {eligibleProgrammes.slice(0, 1).map((p, i) => (
                    <span key={i} className="scholarship-card__academic-value">{p}{eligibleProgrammes.length > 1 ? ` +${eligibleProgrammes.length - 1} more` : ''}</span>
                  ))}
                </span>
              )}
            </dd>
          </div>
        )}
      </dl>

      {/* Expandable details section */}
      <button
        type="button"
        className={`scholarship-card__expand-btn ${isExpanded ? 'scholarship-card__expand-btn--open' : ''}`}
        onClick={toggleExpand}
        aria-expanded={isExpanded}
        aria-controls={`scholarship-details-${scholarship.id}`}
      >
        <span className="scholarship-card__expand-label">
          {isExpanded ? 'Show less' : 'Show details'}
        </span>
        <svg className="scholarship-card__expand-icon" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M7 10l5 5 5-5" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      <div
        id={`scholarship-details-${scholarship.id}`}
        className={`scholarship-card__expanded ${isExpanded ? 'scholarship-card__expanded--open' : ''}`}
        role="region"
        aria-labelledby={`scholarship-title-${scholarship.id}`}
        hidden={!isExpanded}
      >
        <div className="scholarship-card__expanded-inner">
          {/* Description */}
          {description && (
            <section className="scholarship-card__expanded-section">
              <h4 className="scholarship-card__expanded-title">Description</h4>
              <p className="scholarship-card__expanded-text">{description}</p>
            </section>
          )}

          {/* Programme info */}
          {(programType || duration || applicationPeriod) && (
            <section className="scholarship-card__expanded-section">
              <h4 className="scholarship-card__expanded-title">Programme</h4>
              <dl className="scholarship-card__expanded-facts">
                {programType && (
                  <>
                    <dt>Type</dt>
                    <dd>{programType}</dd>
                  </>
                )}
                {duration && (
                  <>
                    <dt>Duration</dt>
                    <dd>{duration}</dd>
                  </>
                )}
                {applicationPeriod && (
                  <>
                    <dt>Application period</dt>
                    <dd>{applicationPeriod}</dd>
                  </>
                )}
              </dl>
            </section>
          )}

{/* Funding details */}
          {((fundingAmount !== null && fundingAmount !== undefined) ||
            fundingCurrency || fundingPeriod || (fullyFunded !== null && fullyFunded !== undefined) ||
            (tuitionCoverage !== null && tuitionCoverage !== undefined) ||
            (livingCostCoverage !== null && livingCostCoverage !== undefined) ||
            (travelCoverage !== null && travelCoverage !== undefined)
          ) && (
            <section className="scholarship-card__expanded-section">
              <h4 className="scholarship-card__expanded-title">Funding</h4>
              <dl className="scholarship-card__expanded-facts">
                {fullyFunded !== null && fullyFunded !== undefined && (
                  <>
                    <dt>Fully funded</dt>
                    <dd>{fullyFunded === true ? 'Yes' : fullyFunded === false ? 'No' : 'Not confirmed'}</dd>
                  </>
                )}
                {fundingAmount !== null && fundingAmount !== undefined && (
                  <>
                    <dt>Amount</dt>
                    <dd>
                      {fundingAmount.toLocaleString()} {fundingCurrency || ''}
                      {fundingPeriod ? ` / ${fundingPeriod}` : ''}
                    </dd>
                  </>
                )}
                {tuitionCoverage !== null && tuitionCoverage !== undefined && (
                  <>
                    <dt>Tuition</dt>
                    <dd>{tuitionCoverage ? 'Covered' : 'Not covered'}</dd>
                  </>
                )}
                {livingCostCoverage !== null && livingCostCoverage !== undefined && (
                  <>
                    <dt>Living costs</dt>
                    <dd>{livingCostCoverage ? 'Covered' : 'Not covered'}</dd>
                  </>
                )}
                {travelCoverage !== null && travelCoverage !== undefined && (
                  <>
                    <dt>Travel</dt>
                    <dd>{travelCoverage ? 'Covered' : 'Not covered'}</dd>
                  </>
                )}
              </dl>
            </section>
          )}

          {/* Benefits & Coverage */}
          {(benefits.length > 0 || coverage.length > 0) && (
            <section className="scholarship-card__expanded-section">
              <h4 className="scholarship-card__expanded-title">Benefits & Coverage</h4>
              {benefits.length > 0 && (
                <div className="scholarship-card__expanded-list">
                  <h5>Benefits</h5>
                  <ul>
                    {benefits.map((benefit, idx) => (
                      <li key={idx}>{benefit}</li>
                    ))}
                  </ul>
                </div>
              )}
              {coverage.length > 0 && (
                <div className="scholarship-card__expanded-list">
                  <h5>Coverage</h5>
                  <ul>
                    {coverage.map((item, idx) => (
                      <li key={idx}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
            </section>
          )}

          {/* Eligibility */}
          {(eligibilitySummary || eligibility.length > 0) && (
            <section className="scholarship-card__expanded-section">
              <h4 className="scholarship-card__expanded-title">Eligibility</h4>
              {eligibilitySummary && (
                <p className="scholarship-card__expanded-text">{eligibilitySummary}</p>
              )}
              {eligibility.length > 0 && (
                <ul className="scholarship-card__expanded-list">
                  {eligibility.map((item, idx) => (
                    <li key={idx}>{item}</li>
                  ))}
                </ul>
              )}
            </section>
          )}

          {/* Academic Eligibility (Departments, Fields, Programmes) */}
          {(departments.length > 0 || eligibleFields.length > 0 || eligibleProgrammes.length > 0) && (
            <section className="scholarship-card__expanded-section">
              <h4 className="scholarship-card__expanded-title">Academic eligibility</h4>
              {departments.length > 0 && (
                <div className="scholarship-card__expanded-subsection">
                  <h5>Departments</h5>
                  <ul>
                    {departments.map((item, idx) => (
                      <li key={idx}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
              {eligibleFields.length > 0 && (
                <div className="scholarship-card__expanded-subsection">
                  <h5>Eligible fields of study</h5>
                  <ul>
                    {eligibleFields.map((item, idx) => (
                      <li key={idx}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
              {eligibleProgrammes.length > 0 && (
                <div className="scholarship-card__expanded-subsection">
                  <h5>Specific programmes</h5>
                  <ul>
                    {eligibleProgrammes.map((item, idx) => (
                      <li key={idx}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
            </section>
          )}

          {/* Requirements & Documents */}
          {(requirements.length > 0 || documents.length > 0) && (
            <section className="scholarship-card__expanded-section">
              <h4 className="scholarship-card__expanded-title">Requirements</h4>
              {requirements.length > 0 && (
                <ul className="scholarship-card__expanded-list">
                  {requirements.map((item, idx) => (
                    <li key={idx}>{item}</li>
                  ))}
                </ul>
              )}
              {documents.length > 0 && (
                <div className="scholarship-card__expanded-subsection">
                  <h5>Documents</h5>
                  <ul>
                    {documents.map((item, idx) => (
                      <li key={idx}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
            </section>
          )}

          {/* English requirement */}
          {englishRequirement && (
            <section className="scholarship-card__expanded-section">
              <h4 className="scholarship-card__expanded-title">English requirement</h4>
              <p className="scholarship-card__expanded-text">{englishRequirement}</p>
            </section>
          )}

          {/* Application method */}
          {applicationMethod.length > 0 && (
            <section className="scholarship-card__expanded-section">
              <h4 className="scholarship-card__expanded-title">How to apply</h4>
              <ol className="scholarship-card__expanded-list scholarship-card__expanded-list--ordered">
                {applicationMethod.map((step, idx) => (
                  <li key={idx}>{step}</li>
                ))}
              </ol>
            </section>
          )}

          {/* Selection notes */}
          {selectionNotes && (
            <section className="scholarship-card__expanded-section">
              <h4 className="scholarship-card__expanded-title">Selection</h4>
              <p className="scholarship-card__expanded-text">{selectionNotes}</p>
            </section>
          )}

          {/* Official links */}
          {(officialSourceUrl || catalogueUrl || officialUpdatesUrl || applicationLink) && (
            <section className="scholarship-card__expanded-section">
              <h4 className="scholarship-card__expanded-title">Official sources</h4>
              <ul className="scholarship-card__expanded-links">
                {officialSourceUrl && (
                  <li>
                    <a href={officialSourceUrl} target="_blank" rel="noopener noreferrer" className="scholarship-card__link">
                      <span>Official source</span>
                      <span aria-hidden="true">↗</span>
                    </a>
                  </li>
                )}
                {catalogueUrl && (
                  <li>
                    <a href={catalogueUrl} target="_blank" rel="noopener noreferrer" className="scholarship-card__link">
                      <span>Programme catalogue</span>
                      <span aria-hidden="true">↗</span>
                    </a>
                  </li>
                )}
                {officialUpdatesUrl && (
                  <li>
                    <a href={officialUpdatesUrl} target="_blank" rel="noopener noreferrer" className="scholarship-card__link">
                      <span>Updates & announcements</span>
                      <span aria-hidden="true">↗</span>
                    </a>
                  </li>
                )}
                {applicationLink && (
                  <li>
                    <a href={applicationLink} target="_blank" rel="noopener noreferrer" className="scholarship-card__link scholarship-card__link--apply">
                      <span>Apply now</span>
                      <span aria-hidden="true">↗</span>
                    </a>
                  </li>
                )}
              </ul>
            </section>
          )}
        </div>
      </div>

      {/* The reference's fit meter: a raised accent bar inside a sunken
          track, with the count beside it in tabular figures. The bar is the
          one element that carries the "how well this matches" number, and
          it is drawn rather than written because a length against a known
          full width is read before a percentage is. */}
      <div className="scholarship-card__fit p-mb">
        <span className="scholarship-card__fit-label p-mb__label">
          {fitLabel}
        </span>
        <span className="p-track">
          <span className="p-track__fill" style={{ '--w': `${fitPercent}%` }} />
        </span>
        <em className="p-mb__value">{fitValue}</em>
      </div>

      <div className="scholarship-card__footer">
        <SupervisorCta scholarshipId={scholarship.id} />
        <ScholarshipActions scholarshipId={scholarship.id} />
        <Link to={`/scholarships/${scholarship.id}`} className="p-btn scholarship-card__button">
          View details <span aria-hidden="true">&rarr;</span>
        </Link>
      </div>
    </article>
  )
}
