/**
 * Application readiness for one opportunity.
 *
 * A third number, deliberately kept apart from fit and confidence: "can I act on
 * this today?" It is not a score about the student's chances.
 *
 * The checklist is derived entirely from the dimensions the engine evaluated. A
 * task is never marked done without evidence behind it - an unchecked item stays
 * unchecked, because marking it complete would be a claim we cannot support.
 */
export function MatchReadiness({ readiness, blockers = [], unverified = [] }) {
  if (!readiness) return null

  const hasScore = typeof readiness.score === 'number'
  const band = readiness.band ? String(readiness.band).toLowerCase() : 'unknown'
  const components = readiness.components ?? []

  const checklist = [
    ...blockers.map((item) => ({
      key: `blocker-${item.kind}`,
      label: 'Review the blocking eligibility condition',
      detail: item.summary,
      state: 'blocked',
    })),
    ...unverified.map((item) => ({
      key: `unverified-${item.kind}`,
      label: `Verify: ${item.summary}`,
      detail: 'A published rule we could not check against your details.',
      state: 'open',
    })),
    ...components.map((item) => ({
      key: `component-${item.name}`,
      label: item.label,
      detail: item.detail,
      state: item.status === 'EVALUATED' ? 'measured' : 'unknown',
      score: typeof item.score === 'number' ? item.score : null,
    })),
  ]

  return (
    <section className={`match-readiness is-${band}`} aria-label="Application readiness">
      <div className="match-readiness__head">
        <span className="match-readiness__label">Application readiness</span>
        {hasScore ? (
          <>
            <strong className="match-readiness__score">{Math.round(readiness.score)}</strong>
            <span className="match-readiness__word">{readiness.label}</span>
          </>
        ) : (
          <strong className="match-readiness__score match-readiness__none">&mdash;</strong>
        )}
      </div>

      {readiness.detail ? <p className="match-readiness__detail">{readiness.detail}</p> : null}

      {checklist.length > 0 ? (
        <ul className="match-readiness__checklist">
          {checklist.map((item) => (
            <li key={item.key} className={`is-${item.state}`}>
              <span aria-hidden="true" className="match-readiness__box">
                {item.state === 'blocked' ? '✕' : '□'}
              </span>
              <span className="match-readiness__task">
                <span className="match-readiness__task-label">{item.label}</span>
                {item.detail ? (
                  <span className="match-readiness__task-detail">{item.detail}</span>
                ) : null}
              </span>
              <span className="match-visually-hidden">
                {item.state === 'blocked'
                  ? 'blocking condition'
                  : item.state === 'measured'
                    ? `measured, ${item.score}`
                    : 'still to do'}
              </span>
            </li>
          ))}
        </ul>
      ) : null}

      {hasScore ? (
        <p className="match-readiness__footnote">
          Readiness is not fit and not confidence. It measures how much of this
          application you can already act on.
        </p>
      ) : null}
    </section>
  )
}

export default MatchReadiness