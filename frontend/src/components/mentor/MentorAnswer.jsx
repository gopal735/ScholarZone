/**
 * The mentor's answer.
 *
 * The layout is the argument. A student asking "what should I do now?" is at
 * risk of the failure mode where a confident paragraph buries the fact that half
 * of it rests on measurements nobody took. So the four kinds of statement are
 * visually separate and cannot be read as one voice:
 *
 *   1. Mentor guidance      - what ScholarZone suggests, in words
 *   2. Verified facts       - what the catalogue and engines actually hold
 *   3. Evidence             - which canonical field each fact came from
 *   4. What is not known    - named, not omitted
 *
 * The unknown section is not an error state and never renders as one. It is the
 * most valuable part of the answer when a question cannot be fully grounded,
 * which is why it sits above the fold rather than in a disclosure.
 *
 * Every tone carries a word as well as a colour, so nothing here depends on
 * seeing the page.
 */

import { Link } from 'react-router-dom'

import {
  evidenceStatusWord,
  evidenceTone,
  priorityText,
  providerText,
  sourceLabel,
} from '../../services/mentorPresentation'

function EvidenceChip({ entry }) {
  const tone = evidenceTone(entry)
  const status = evidenceStatusWord(entry)
  return (
    <li className={`mentor-evidence__item mentor-evidence__item--${tone}`}>
      <div className="mentor-evidence__head">
        <span className="mentor-evidence__label">{entry.label}</span>
        {status ? (
          <span className={`mentor-evidence__status sz-badge sz-badge--${tone}`}>
            {status}
          </span>
        ) : null}
      </div>
      <p className="mentor-evidence__value">{entry.value}</p>
      <p className="mentor-evidence__basis">
        <span className="mentor-evidence__basis-name">{entry.basis}</span>
        <span className="mentor-evidence__basis-field">{entry.field}</span>
      </p>
      {entry.scholarship_id ? (
        <Link
          className="mentor-evidence__link"
          to={`/scholarships/${entry.scholarship_id}`}
        >
          Open this scholarship
        </Link>
      ) : null}
    </li>
  )
}

function UnknownList({ items }) {
  if (!items || items.length === 0) return null
  return (
    <section className="mentor-answer__section" aria-labelledby="mentor-unknown-heading">
      <h3 className="mentor-answer__heading" id="mentor-unknown-heading">
        What is not known
      </h3>
      <p className="mentor-answer__section-note">
        ScholarZone will not fill these gaps with a guess. Each one is a real
        limitation, not a failure to load.
      </p>
      <ul className="mentor-answer__unknown">
        {items.map((item) => (
          <li key={item} className="mentor-answer__unknown-item">
            {item}
          </li>
        ))}
      </ul>
    </section>
  )
}

function NextActions({ actions }) {
  if (!actions || actions.length === 0) return null
  return (
    <section className="mentor-answer__section" aria-labelledby="mentor-next-heading">
      <h3 className="mentor-answer__heading" id="mentor-next-heading">
        What to do next
      </h3>
      <p className="mentor-answer__section-note">
        Ordered by ScholarZone&rsquo;s own fixed priority bands. The order is a
        property of that table, not a score and not a countdown.
      </p>
      <ol className="mentor-answer__actions">
        {actions.map((action) => (
          <li key={action.code} className="mentor-action">
            <div className="mentor-action__head">
              <span className="mentor-action__band sz-badge sz-badge--accent">
                {priorityText(action.priority)}
              </span>
              <h4 className="mentor-action__title">{action.title}</h4>
            </div>
            <p className="mentor-action__detail">{action.detail}</p>
            <Link className="sz-btn sz-btn--secondary mentor-action__cta" to={action.href}>
              {action.action_label}
            </Link>
          </li>
        ))}
      </ol>
    </section>
  )
}


function DiscoveryResults({ answer }) {
  // Only render for discovery answers (search_status present).
  if (!answer || !answer.search_status) return null
  const verified = Array.isArray(answer?.verified_matches) ? answer.verified_matches : []
  const potential = Array.isArray(answer?.potential_matches) ? answer.potential_matches : []
  const status = answer?.search_status
  const diagnostics = answer?.diagnostics || {}
  if (status === 'AMBIGUOUS_FILTER' || status === 'UNSUPPORTED_FILTER') {
    let message = status === 'AMBIGUOUS_FILTER'
      ? 'The location filter is ambiguous; please clarify.'
      : 'The requested location has no catalogue coverage yet.'
    return (
      <section className="mentor-answer__section" aria-labelledby="mentor-discovery-heading">
        <h3 className="mentor-answer__heading" id="mentor-discovery-heading">Scholarship results</h3>
        <p className="mentor-answer__section-note">{message}</p>
      </section>
    )
  }
  if (verified.length === 0 && potential.length === 0) {
    // Explicit diagnostic empty state instead of silently returning null.
    let message = 'No scholarship matches found.'
    if (status === 'NO_PUBLIC_CANDIDATES') message = 'No public scholarship candidates available.'
    else if (status === 'NO_DEGREE_MATCHES') message = 'No scholarships match the requested degree level.'
    else if (status === 'NO_REGION_MATCHES') message = 'No scholarships match the requested region.'
    else if (status === 'UNSUPPORTED_FILTER') message = 'The requested location has no catalogue coverage yet.'
    else if (status === 'AMBIGUOUS_FILTER') message = 'The location filter is ambiguous; please clarify.'
    else if (status === 'NO_VERIFIED_STIPEND_MATCHES') message = 'No verified stipend matches found; only unverified or excluded records exist.'
    else if (status === 'SEARCH_UNAVAILABLE' || status === 'SEARCH_ERROR') message = 'Search is currently unavailable. Please try again later.'
    return (
      <section className="mentor-answer__section" aria-labelledby="mentor-discovery-heading">
        <h3 className="mentor-answer__heading" id="mentor-discovery-heading">Scholarship results</h3>
        <p className="mentor-answer__section-note">{message}</p>
        {diagnostics && Object.keys(diagnostics).length > 0 ? (
          <p className="mentor-answer__section-note">
            Diagnostics: {Object.entries(diagnostics).map(([k, v]) => `${k}=${v}`).join(', ')}
          </p>
        ) : null}
      </section>
    )
  }
  return (
    <section className="mentor-answer__section" aria-labelledby="mentor-discovery-heading">
      <h3 className="mentor-answer__heading" id="mentor-discovery-heading">
        Scholarship results
      </h3>
      {verified.length > 0 ? (
        <ul className="mentor-evidence">
          {verified.map((m) => (
            <li key={m.scholarship_id} className="mentor-evidence__item">
              <div className="mentor-evidence__head">
                {m.scholarship_id ? (
                  <Link className="mentor-evidence__label" to={`/scholarships/${m.scholarship_id}`}>{m.title}</Link>
                ) : (
                  <span className="mentor-evidence__label">{m.title}</span>
                )}
              </div>
              <p className="mentor-evidence__value">{m.country} — {m.funding_classification}</p>
              {m.official_source_url ? (
                <a href={m.official_source_url} target="_blank" rel="noopener noreferrer">Official source</a>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
      {potential.length > 0 ? (
        <ul className="mentor-evidence">
          {potential.map((m) => (
            <li key={m.scholarship_id} className="mentor-evidence__item">
              <div className="mentor-evidence__head">
                {m.scholarship_id ? (
                  <Link className="mentor-evidence__label" to={`/scholarships/${m.scholarship_id}`}>{m.title}</Link>
                ) : (
                  <span className="mentor-evidence__label">{m.title}</span>
                )}
              </div>
              <p className="mentor-evidence__value">{m.country} — {m.funding_classification}</p>
              {Array.isArray(m.warnings) && m.warnings.length > 0 ? (
                <p className="mentor-answer__section-note">{m.warnings.join(' ')}</p>
              ) : null}
              {m.official_source_url ? (
                <a href={m.official_source_url} target="_blank" rel="noopener noreferrer">Official source</a>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  )
}

export default function MentorAnswer({ answer }) {
  const source = sourceLabel(answer)

  return (
    <article
      className="mentor-answer"
      aria-labelledby="mentor-answer-heading"
      data-testid="mentor-answer"
    >
      <header className="mentor-answer__header">
        <p className="mentor-answer__source">{source}</p>
        <h2 className="mentor-answer__headline" id="mentor-answer-heading">
          {answer.headline}
        </h2>
        <p className="mentor-answer__why">{answer.why}</p>
        <p className="mentor-answer__origin">{providerText(answer.provider_mode, answer.provider_used)}</p>
      </header>

      {answer.notes && answer.notes.length > 0 ? (
        <section className="mentor-answer__section" aria-labelledby="mentor-notes-heading">
          <h3 className="mentor-answer__heading" id="mentor-notes-heading">
            About your question
          </h3>
          <ul className="mentor-answer__notes">
            {answer.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <UnknownList items={answer.unknown} />

      {answer.known && answer.known.length > 0 ? (
        <section
          className="mentor-answer__section"
          aria-labelledby="mentor-evidence-heading"
        >
          <h3 className="mentor-answer__heading" id="mentor-evidence-heading">
            What ScholarZone verified
          </h3>
          <ul className="mentor-evidence">
            {answer.known.map((entry) => (
              <EvidenceChip key={entry.key} entry={entry} />
            ))}
          </ul>
        </section>
      ) : null}

      <DiscoveryResults answer={answer} />

      {answer.caveats && answer.caveats.length > 0 ? (
        <section className="mentor-answer__section" aria-labelledby="mentor-caveat-heading">
          <h3 className="mentor-answer__heading" id="mentor-caveat-heading">
            Limits on this answer
          </h3>
          <ul className="mentor-answer__notes">
            {answer.caveats.map((caveat) => (
              <li key={caveat}>{caveat}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <NextActions actions={answer.next_steps} />

      {answer.supported === false ? (
        <section className="mentor-answer__section" aria-labelledby="mentor-redirect-heading">
          <h3 className="mentor-answer__heading" id="mentor-redirect-heading">
            What I can answer
          </h3>
          <p className="mentor-answer__section-note">{answer.why}</p>
          <ul className="mentor-answer__redirects">
            {(answer.redirects || []).map((redirect) => (
              <li key={redirect}>{redirect}</li>
            ))}
          </ul>
        </section>
      ) : null}
    </article>
  )
}

export { EvidenceChip, UnknownList, NextActions }