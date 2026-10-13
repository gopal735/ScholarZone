import { useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import ScholarshipImage from './ScholarshipImage'
import ScholarshipActions from './ScholarshipActions'
import { formatFundingValue } from '../utils/scholarshipDetail'
import { getLastVerifiedLabel, getScholarshipStatus } from '../utils/scholarshipPresentation'
import { presentCardDeadline } from '../utils/cardDeadlinePresentation'
import { fundingBadgeLabel } from '../utils/fundingFacts'
import './ScholarshipCard.css'

/* Pointer input is ignored on touch and coarse pointers — there is no
   hover state there, and a highlight would be left stuck after a tap.
   The stylesheet also neutralises the layer for those input types; this
   just avoids attaching listeners at all. Evaluated once at module load
   rather than per card per render. */
const CAN_TILT =
  typeof window !== 'undefined' &&
  window.matchMedia('(hover: hover) and (pointer: fine)').matches

export default function ScholarshipCard({ scholarship }) {
  const deadlineStatus = getScholarshipStatus(scholarship)
  const cardRef = useRef(null)

  /* Verification state comes from verification_status, not from `verified`.

     Every record in the catalogue has verified === true, because `verified`
     records that a source was read at some point. It says nothing about
     whether this record's details have since been checked. Reading the flag
     made every card claim "Verified official source", which is the one claim
     this product cannot afford to make loosely.

     So: active means the record was checked and holds. Anything else says so
     plainly instead of borrowing a pass mark. */
  const verificationState = scholarship.verification_status || 'needs_review'
  const isVerified = verificationState === 'active'

  /* Provenance, not decoration. image_kind is the honest signal: an image_url
     exists on 445 of the 618 public records but only 404 of them are
     validated official_logo, and the difference is exactly what the title
     rule's fill and the provenance line both have to tell the truth about. */
  const hasOfficialLogo = scholarship.image_kind === 'official_logo'

  /* Writes two custom properties straight to the node. No React state
     and no animation loop, so a pointer sweep across a grid only costs a
     style recalc on the one card under the cursor. The card lifts on
     its own in CSS; only the light position is driven from here, which
     is what keeps the interaction from reading as a pivoting object. */
  const handlePointerMove = useCallback((event) => {
    const card = cardRef.current
    if (!card) return

    const rect = card.getBoundingClientRect()
    if (rect.width === 0 || rect.height === 0) return

    const x = (event.clientX - rect.left) / rect.width
    const y = (event.clientY - rect.top) / rect.height

    card.style.setProperty('--lg-hx', `${x * 100}%`)
    card.style.setProperty('--lg-hy', `${y * 100}%`)
  }, [])

  const handlePointerLeave = useCallback(() => {
    const card = cardRef.current
    if (!card) return

    card.style.setProperty('--lg-hx', '50%')
    card.style.setProperty('--lg-hy', '0%')
  }, [])

  /* The researched funding amount, formatted. Null whenever no figure was
     confirmed, so the row appears only where the awarding body publishes a
     number - the same honesty rule the detail page applies, at card scale. */
  const fundingAmount = formatFundingValue(
    scholarship.funding_amount,
    scholarship.funding_currency,
    scholarship.funding_period,
  )

  /* The funding indicator and the deadline, split into a value and a note.

     Both used to render the raw provider string directly. `funding` reaches 310
     characters on the shipped snapshot and `deadline` reaches 244, and each was
     set at the card's heaviest weight in a one-line truncated pill. The split
     keeps the scannable part scannable and gives the long part room, and the
     full text stays available - in the badge's own tooltip and screen-reader
     text, and in full on the detail page. */
  const funding = fundingBadgeLabel(scholarship)
  const deadline = presentCardDeadline(scholarship)

  /* A short, own-words-free summary. The detail page holds the whole
     eligibility summary; the card needs one line that tells a student whether
     this is worth opening, so it is clamped rather than truncated mid-word. */
  const summary = typeof scholarship.eligibility_summary === 'string'
    && scholarship.eligibility_summary.trim() !== ''
    ? scholarship.eligibility_summary.trim()
    : null

  return (
    <article
      ref={cardRef}
      className={`scholarship-card scholarship-card--${deadlineStatus.className}`}
      onPointerMove={CAN_TILT ? handlePointerMove : undefined}
      onPointerLeave={CAN_TILT ? handlePointerLeave : undefined}
    >
      <span className="scholarship-card__edge" aria-hidden="true" />

      <ScholarshipImage scholarship={scholarship} className="scholarship-card__image" />

      <div className="scholarship-card__header">
        <div className="scholarship-card__topline">
          <span className={`scholarship-card__status scholarship-card__status--${deadlineStatus.className}`}>{deadlineStatus.label}</span>
          {/* The funding indicator. It is a badge, so it has to fit one, and
              the label is chosen to: a scannable category when the provider's
              funding text supports one, the short text itself when it is already
              short. The full published wording is never discarded - it is on the
              element as a tooltip, in the accessibility tree, and on the detail
              page - so nothing is hidden behind a truncation. */}
          <span
            className={`scholarship-card__badge${funding.isCategory ? ' scholarship-card__badge--category' : ''}`}
            title={funding.truncated ? funding.full : undefined}
          >
            {funding.label}
            {funding.truncated && (
              <span className="visually-hidden"> ({funding.full})</span>
            )}
          </span>
        </div>

        <h2>{scholarship.title}</h2>

        {summary && <p className="scholarship-card__summary">{summary}</p>}

        {scholarship.provider && (
          <p className="scholarship-card__provider">{scholarship.provider}</p>
        )}

        {/* The Provenance Rule. The square is the identity: filled when the
            record carries a validated official logo, hollow when it does not.
            Keyed on image_kind rather than image_url on purpose — 445 records
            carry an image but only 404 of them are official_logo, and the rest
            must read as unproven rather than borrow a mark they have not
            earned. The hollow state is part of the design, not a gap.

            It stays `aria-hidden` because the same fact is now stated in words
            in the signals row below; the fill is the visual half, not a
            replacement for it. */}
        <div
          className={`scholarship-card__title-rule${
            hasOfficialLogo ? '' : ' scholarship-card__title-rule--unverified'
          }`}
          aria-hidden="true"
        />
        <div className="scholarship-card__signals">
          <span className={isVerified ? 'scholarship-card__verified' : 'scholarship-card__unverified'}>
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="m8 12 2.2 2.2L16 9m4-3v6c0 5-3.4 8.7-8 10-4.6-1.3-8-5-8-10V6l8-3 8 3Z" />
            </svg>
            {isVerified ? 'Verified official source' : 'Confirm with provider'}
          </span>
          {scholarship.last_verified_at && (
            <span className="scholarship-card__verification-date">
              {/* Compact: the badge beside it already says "Confirm with
                  provider", and printing the instruction again here left three
                  badges in the row saying two things. */}
              {getLastVerifiedLabel(scholarship, { compact: true })}
            </span>
          )}
          {/* Provenance of the image, as text.

              The crowded citation line that used to sit here named this
              explicitly - "Official source captured", "No official logo" - and
              removing it left the title-rule's fill as the only signal, which
              is `aria-hidden` and therefore invisible to a screen reader. A
              student who cannot see the fill has no way to know whether the
              image above is a validated official logo or a stock picture, which
              is exactly the distinction the record carries.

              So it is said once, in words, at the smallest size on the card.
              The numbers are the shipped snapshot's: 445 records carry an image
              and 404 of them are validated official_logo, so the negative is
              the common case and has to be as legible as the positive. */}
          <span className="scholarship-card__provenance">
            {hasOfficialLogo ? 'Official logo captured' : 'No official logo'}
          </span>
        </div>
      </div>

      {/* The deadline, split three ways.
            - label: what the row is
            - value: the date, when there is one
            - note: the provider's own wording, at body weight, left-aligned,
              with a line height that a 244-character sentence can be read at.
          A record with no date keeps its provider text as the value rather than
          being promoted to a headline, and a record with no date and no text
          says so. Nothing is invented to fill the space. */}
      <dl className="scholarship-card__details">
        <div className={`scholarship-card__detail scholarship-card__detail--deadline scholarship-card__detail--${deadlineStatus.className}`}>
          <dt>Deadline</dt>
          <dd>
            <span className={`scholarship-card__deadline-value${deadline.isProse ? ' scholarship-card__deadline-value--prose' : ''}`}>{deadline.value}</span>
            {deadline.note && (
              <span className="scholarship-card__deadline-note">{deadline.note}</span>
            )}
            {deadline.precisionLabel && (
              <span className="scholarship-card__deadline-precision">{deadline.precisionLabel}</span>
            )}
          </dd>
        </div>
        <div className="scholarship-card__detail">
          <dt>Location</dt>
          <dd>{scholarship.country}</dd>
        </div>
        <div className="scholarship-card__detail">
          <dt>Level</dt>
          <dd>{scholarship.degree}</dd>
        </div>
      </dl>

      {fundingAmount ? (
        <p className="scholarship-card__amount">
          <span>Funding amount</span>
          <strong>{fundingAmount}</strong>
        </p>
      ) : null}

      <div className="scholarship-card__footer">
        {/* No supervisor teaser here. It cost one database request per card -
            twelve per directory page, a hundred on a country page - for a count
            the detail page already shows in full through SupervisorPanel. The
            public catalogue is served from the bundled snapshot precisely so
            that browsing does not reach the database, and a grid of cards that
            each make a request is the opposite of that. The detail page keeps
            the complete picture. */}
        <ScholarshipActions scholarshipId={scholarship.id} />
        <Link to={`/scholarships/${scholarship.id}`} className="scholarship-card__button">
          View details <span aria-hidden="true">&rarr;</span>
        </Link>
      </div>
    </article>
  )
}
