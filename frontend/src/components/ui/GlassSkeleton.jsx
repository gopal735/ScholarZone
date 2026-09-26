const SKELETON_VARIANTS = new Set(['text', 'title', 'block', 'circle', 'media'])

export default function GlassSkeleton({
  variant = 'text',
  lines = 1,
  animated,
  width,
  height,
  className = '',
  style,
  ...rest
}) {
  const resolvedVariant = SKELETON_VARIANTS.has(variant) ? variant : 'text'
  const rowCount = Math.max(1, Number(lines) || 1)
  const hasCustomWidth = width !== undefined

  const classes = [
    'sz-glass-skeleton',
    `sz-glass-skeleton--${resolvedVariant}`,
    animated === false ? 'is-static' : 'is-shimmer',
    className,
  ]
    .filter(Boolean)
    .join(' ')

  if (resolvedVariant === 'text' && rowCount > 1) {
    return (
      <span className="sz-glass-skeleton__group" style={style} {...rest}>
        {Array.from({ length: rowCount }, (_, index) => {
          const isLast = index === rowCount - 1
          const rowStyle = height !== undefined ? { height } : undefined
          const rowClass = isLast && !hasCustomWidth ? `${classes} sz-glass-skeleton--last` : classes

          return (
            <span
              key={index}
              aria-hidden="true"
              className={rowClass}
              style={hasCustomWidth || rowStyle ? { ...rowStyle, ...(hasCustomWidth ? { width } : {}) } : undefined}
            />
          )
        })}
      </span>
    )
  }

  return (
    <span
      aria-hidden="true"
      className={classes}
      style={{ ...(width !== undefined ? { width } : {}), ...(height !== undefined ? { height } : {}), ...style }}
      {...rest}
    />
  )
}
