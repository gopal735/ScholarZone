/**
 * The mentor's composer.
 *
 * A question box rather than a chat transcript. The mentor keeps no history in
 * 1.0 - there is no conversation table and nothing is stored - so a message list
 * would imply a thread that does not exist and quietly teach a student to
 * assume their questions are being retained.
 *
 * The textarea is a real label rather than a placeholder, because a placeholder
 * disappears on focus and takes the only description of the field with it. The
 * character count is announced politely rather than interrupting, and the
 * limit is stated up front instead of being discovered by being refused.
 */

import { useId } from 'react'

import { COMPOSER_LABEL, COMPOSER_PLACEHOLDER } from '../../services/mentorPresentation'

export default function MentorComposer({
  value,
  onChange,
  onSubmit,
  busy,
  maxLength,
  disabled,
}) {
  const fieldId = useId()
  const hintId = `${fieldId}-hint`
  const remaining = Math.max(0, maxLength - value.length)
  const atLimit = remaining === 0

  return (
    <form
      className="mentor-composer"
      onSubmit={(event) => {
        event.preventDefault()
        onSubmit()
      }}
    >
      <label className="mentor-composer__label" htmlFor={fieldId}>
        {COMPOSER_LABEL}
      </label>
      <textarea
        id={fieldId}
        className="sz-input mentor-composer__input"
        rows={3}
        value={value}
        maxLength={maxLength}
        disabled={disabled || busy}
        placeholder={COMPOSER_PLACEHOLDER}
        aria-describedby={hintId}
        data-testid="mentor-composer-input"
        onChange={(event) => onChange(event.target.value)}
      />
      <p className="mentor-composer__hint" id={hintId}>
        Answers come only from ScholarZone&rsquo;s own records, and anything it
        has not measured is reported as unknown.
      </p>
      <div className="mentor-composer__footer">
        <p className="mentor-composer__count" data-testid="mentor-composer-count">
          {atLimit ? 'Maximum length reached' : `${remaining} characters left`}
        </p>
        <button
          type="submit"
          className="sz-btn sz-btn--primary"
          disabled={disabled || busy || value.trim().length === 0}
          data-testid="mentor-composer-submit"
        >
          {busy ? 'Thinking' : 'Ask'}
        </button>
      </div>
    </form>
  )
}