const BADGE_VARIANTS = new Set(['neutral', 'verified', 'funding', 'status', 'warning'])
const BADGE_SIZES = new Set(['sm', 'md'])

const DEFAULT_ICONS = {
  verified: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 12.5 9 17.5 20 6.5" />
    </svg>
  ),
  funding: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3v18M16.5 7.2c0-1.7-2-3-4.5-3s-4.5 1.3-4.5 3 1.8 2.7 4.5 3.3 4.5 1.6 4.5 3.3-2 3-4.5 3-4.5-1.3-4.5-3" />
    </svg>
  ),
}

export default function GlassBadge({
  variant = 'neutral',
  size = 'md',
  icon,
  className = '',
  children,
  ...rest
}) {
  const resolvedVariant = BADGE_VARIANTS.has(variant) ? variant : 'neutral'
  const resolvedSize = BADGE_SIZES.has(size) ? size : 'md'
  const resolvedIcon = icon ?? DEFAULT_ICONS[resolvedVariant] ?? null

  const classes = [
    'sz-glass-badge',
    `sz-glass-badge--${resolvedVariant}`,
    `sz-glass-badge--${resolvedSize}`,
    className,
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <span className={classes} {...rest}>
      {resolvedIcon && <span className="sz-glass-badge__icon">{resolvedIcon}</span>}
      {children}
    </span>
  )
}
