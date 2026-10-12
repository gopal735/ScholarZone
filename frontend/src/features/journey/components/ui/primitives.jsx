import { useId } from 'react'

/**
 * A grouped form control.
 *
 * One place to attach a label, a hint and an inline error, so a control can
 * never be rendered unlabelled. The error is associated with `aria-describedby`
 * rather than only announced visually, which is what makes an inline validation
 * message reach a screen-reader user rather than only a sighted one.
 */
export function Field({ label, hint, error, children, id: providedId, required }) {
  const autoId = useId()
  const id = providedId ?? autoId
  const hintId = hint ? `${id}-hint` : undefined
  const errorId = error ? `${id}-error` : undefined
  const describedBy = [errorId, hintId].filter(Boolean).join(' ') || undefined

  return (
    <div className="jfield">
      <label className="jfield__label" htmlFor={id}>
        {label}
        {required ? <span className="jfield__required"> *</span> : null}
      </label>
      {hint ? (
        <p className="jfield__hint" id={hintId}>
          {hint}
        </p>
      ) : null}
      {/*
        `aria-invalid` is passed as the string "true" or omitted entirely, never
        as a boolean: React logs a warning for `invalid={false}` on a DOM
        element and warns for a lowercase `aria-*` mismatch, and a warning in the
        console on every character typed in a validated field is noise that hides
        the real ones.
      */}
      {typeof children === 'function'
        ? children({
            id,
            'aria-describedby': describedBy,
            'aria-invalid': error ? 'true' : undefined,
          })
        : children}
      {error ? (
        <p className="jfield__error" id={errorId}>
          {error}
        </p>
      ) : null}
    </div>
  )
}

/**
 * A status chip that carries its meaning in text.
 *
 * Never colour alone: every tone pairs with a word, so the chip still reads
 * correctly for a colour-blind reader and in a forced-colors mode that drops
 * backgrounds entirely.
 */
export function StatusChip({ tone = 'neutral', children, className = '' }) {
  return <span className={`jchip jchip--${tone} ${className}`.trim()}>{children}</span>
}

/** An external link with the security attributes the rest of the app uses. */
export function ExternalLink({ href, children, className = '' }) {
  if (!href) return null
  return (
    <a className={className} href={href} target="_blank" rel="noopener noreferrer">
      {children}
      <span className="jlink__icon" aria-hidden="true">
        ↗
      </span>
    </a>
  )
}

/**
 * A bilingual heading.
 *
 * In `both` mode the Bangla line is the heading and English sits underneath as a
 * quiet secondary. In `bn` and `en` only the primary line renders, because
 * repeating every sentence twice is worse for reading than choosing one.
 */
export function BilingualText({ primary, secondary, as: Tag = 'span', className = '' }) {
  if (!secondary) {
    return <Tag className={className}>{primary}</Tag>
  }
  return (
    <Tag className={`${className} jbilingual`.trim()}>
      <span className="jbilingual__primary">{primary}</span>
      <span className="jbilingual__secondary" lang="en">
        {secondary}
      </span>
    </Tag>
  )
}
