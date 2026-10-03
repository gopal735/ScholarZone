/**
 * How complete the student's own input is.
 *
 * Deliberately not fit and not confidence, and the copy says so. Two students
 * with an identical profile strength can have completely different matches, and
 * a strong profile does not make any particular scholarship a better match.
 */
export function ProfileStrengthPanel({ strength }) {
  if (!strength) return null

  const hasScore = typeof strength.score === 'number'
  const band = strength.band ? String(strength.band).toLowerCase() : 'unknown'
  const complete = Array.isArray(strength.complete) ? strength.complete : []
  const missing = Math.max(0, (strength.components?.length ?? 0) - complete.length)

  return (
    <section className="match-strength" aria-labelledby="match-strength-heading">
      <div className="match-strength__head">
        <h3 id="match-strength-heading">Profile strength</h3>
        <p className="match-strength__caption">
          How much about you we know. This is not your score, and it is not your chance of
          admission.
        </p>
      </div>

      <div className={`match-strength__band is-${band}`}>
        <span className="match-strength__label">Match readiness</span>
        {hasScore ? (
          <>
            <strong>{Math.round(strength.score)}</strong>
            <span className="match-strength__word">{strength.label ?? 'Profile'}</span>
          </>
        ) : (
          <>
            <strong className="match-strength__none">&mdash;</strong>
            <span className="match-strength__word">
              Not enough information yet to describe your profile
            </span>
          </>
        )}
      </div>

      {strength.detail ? (
        <p className="match-strength__detail">{strength.detail}</p>
      ) : null}

      {complete.length > 0 || (strength.components?.length ?? 0) > 0 ? (
        <ul className="match-strength__checklist">
          {(strength.components ?? []).map((item) => {
            const isDone = item.status === 'EVALUATED'
            return (
              <li key={item.name} className={isDone ? 'is-done' : 'is-missing'}>
                <span aria-hidden="true">{isDone ? '✓' : '○'}</span>
                <span className="match-strength__group">{item.label}</span>
                <span className="match-strength__group-detail">{item.detail}</span>
                <span className="match-visually-hidden">
                  {isDone ? 'provided' : 'not provided'}
                </span>
              </li>
            )
          })}
        </ul>
      ) : null}

      {missing > 0 ? (
        <p className="match-strength__missing">
          {missing} of {strength.components?.length ?? 0} groups still incomplete
        </p>
      ) : null}

      {strength.improvements?.length > 0 ? (
        <div className="match-strength__improvements">
          <h4>Sharpen your matches</h4>
          <ul>
            {strength.improvements.map((item) => (
              <li key={item.code}>{item.message}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  )
}

export default ProfileStrengthPanel