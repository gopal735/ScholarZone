import { useId, useState } from 'react'

/**
 * The optional free-text profile input.
 *
 * A student should be able to type one sentence instead of filling in a form.
 * What this component guarantees is that a parsed sentence never becomes a score
 * on its own:
 *
 *   1. parsing fills in the form fields, it does not calculate anything
 *   2. everything it read is shown back, with the exact phrase it matched
 *   3. anything it could NOT resolve is reported too, rather than dropped
 *   4. the student has to press Calculate My Matches themselves
 *
 * The parser is deterministic and local to ScholarZone, so it can be wrong in an
 * obvious way. Making it visible is the whole protection.
 */
export function ProfileTextParser({
  value,
  onChange,
  onParse,
  onDismiss,
  parsed,
  isParsing,
  error,
  reducedMotion = false,
}) {
  const fieldId = useId()
  const hintId = `${fieldId}-hint`
  const [localError, setLocalError] = useState(null)

  const trimmed = (value ?? '').trim()
  const shownError = error ?? localError

  const handleParse = () => {
    if (!trimmed) {
      setLocalError('Describe what you are looking for first, even in one sentence.')
      return
    }
    setLocalError(null)
    onParse(trimmed)
  }

  return (
    <section className="match-parser" aria-labelledby={`${fieldId}-heading`}>
      <h3 id={`${fieldId}-heading`} className="match-parser__heading">
        Tell us what you&rsquo;re looking for
      </h3>
      <p className="match-parser__hint" id={hintId}>
        Optional. Write one sentence in your own words and ScholarZone will fill in the
        form for you. You can edit everything before calculating.
      </p>

      <label className="match-parser__label" htmlFor={fieldId}>
        Describe your goal
      </label>
      <textarea
        id={fieldId}
        className="match-control match-parser__input"
        rows={3}
        value={value ?? ''}
        aria-describedby={hintId}
        aria-invalid={shownError ? 'true' : undefined}
        placeholder="I’m from Bangladesh and want a fully funded Master’s in Computer Science in Europe. I have IELTS 7."
        onChange={(event) => onChange(event.target.value)}
      />

      <div className="match-parser__actions">
        <button
          type="button"
          className="match-parser__button"
          onClick={handleParse}
          disabled={isParsing}
        >
          {isParsing ? 'Reading…' : 'Read my profile'}
        </button>
        {value ? (
          <button type="button" className="match-parser__clear" onClick={() => onChange('')}>
            Clear
          </button>
        ) : null}
      </div>

      {shownError ? (
        <p className="match-form__error" role="alert">
          {shownError}
        </p>
      ) : null}

      {parsed ? (
        <div
          className="match-parser__result"
          role="status"
          aria-live="polite"
          data-testid="parsed-profile"
        >
          <div className="match-parser__result-head">
            <h4>We understood your profile</h4>
            <button type="button" className="match-parser__clear" onClick={onDismiss}>
              Dismiss
            </button>
          </div>
          <p className="match-parser__note">{parsed.note}</p>

          {parsed.resolved?.length > 0 ? (
            <>
              <h5 className="match-parser__subheading">Filled in from your words</h5>
              <ul className="match-parser__chips">
                {parsed.resolved.map((item) => (
                  <li key={`${item.field}-${item.source}`} className="match-chip">
                    <span className="match-chip__label">
                      {item.field.replace(/_/g, ' ')}
                    </span>
                    <span className="match-chip__value">{item.display}</span>
                    <span className="match-chip__source">from &ldquo;{item.source}&rdquo;</span>
                  </li>
                ))}
              </ul>
            </>
          ) : null}

          {parsed.unresolved?.length > 0 ? (
            <>
              <h5 className="match-parser__subheading">We could not read these</h5>
              <ul className="match-parser__unresolved">
                {parsed.unresolved.map((item) => (
                  <li key={`${item.field}-${item.source}`}>
                    <strong>{item.field.replace(/_/g, ' ')}</strong>: {item.note}
                  </li>
                ))}
              </ul>
            </>
          ) : null}

          {parsed.empty ? (
            <p className="match-parser__note">
              We could not read anything from that sentence. Filling in the form still works.
            </p>
          ) : null}

          {!reducedMotion && parsed.resolved?.length > 0 ? (
            <p className="match-parser__footnote">
              Check the form below. Nothing is calculated until you press Calculate My Matches.
            </p>
          ) : null}
        </div>
      ) : null}
    </section>
  )
}

export default ProfileTextParser