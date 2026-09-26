const BUTTON_VARIANTS = new Set(['primary', 'secondary', 'ghost', 'icon'])
const BUTTON_SIZES = new Set(['sm', 'md', 'lg'])

export default function GlassButton({
  as: Element = 'button',
  variant = 'primary',
  size = 'md',
  loading = false,
  loadingLabel = 'Working',
  disabled = false,
  className = '',
  children,
  type,
  ...rest
}) {
  const isNativeButton = Element === 'button'
  const resolvedVariant = BUTTON_VARIANTS.has(variant) ? variant : 'primary'
  const resolvedSize = BUTTON_SIZES.has(size) ? size : 'md'
  const isDisabled = Boolean(disabled) || Boolean(loading)

  const classes = [
    'sz-glass-button',
    `sz-glass-button--${resolvedVariant}`,
    `sz-glass-button--${resolvedSize}`,
    loading ? 'is-loading' : null,
    className,
  ]
    .filter(Boolean)
    .join(' ')

  const elementProps = isNativeButton
    ? { type: type ?? 'button', disabled: isDisabled }
    : type
      ? { type }
      : {}

  const guardedProps = isDisabled
    ? { tabIndex: -1, 'aria-disabled': true, onClick: undefined, onMouseDown: undefined }
    : {}

  return (
    <Element className={classes} aria-busy={loading || undefined} {...elementProps} {...rest} {...guardedProps}>
      {loading && <span className="sz-glass-button__spinner" aria-hidden="true" />}
      <span className="sz-glass-button__label">{children}</span>
      {loading && <span className="sz-sr-only" role="status">{loadingLabel}</span>}
    </Element>
  )
}
