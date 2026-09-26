const SURFACE_LEVELS = new Set([1, 2, 3, 4])

export default function GlassSurface({
  as: Element = 'div',
  level = 1,
  interactive = false,
  lift = false,
  tone,
  className = '',
  children,
  ...rest
}) {
  const requestedLevel = Number(level)
  const resolvedLevel = SURFACE_LEVELS.has(requestedLevel) ? requestedLevel : 1

  const classes = [
    'sz-glass',
    `sz-glass--${resolvedLevel}`,
    tone === 'muted' ? 'sz-glass--muted' : null,
    interactive ? 'sz-glass--interactive' : null,
    lift ? 'sz-glass--lift' : null,
    className,
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <Element className={classes} {...rest}>
      {children}
    </Element>
  )
}
