import { useReducedMotion } from '../../hooks/useReducedMotion'

const ORB_LAYOUTS = [
  { size: '58%', top: '-16%', left: '-10%', shift: '22px', rise: '-16px', duration: '44s' },
  { size: '46%', top: '18%', right: '-8%', shift: '-20px', rise: '18px', duration: '52s', delay: '-8s' },
  { size: '40%', bottom: '-14%', left: '32%', shift: '16px', rise: '-14px', duration: '60s', delay: '-16s' },
  { size: '34%', top: '8%', left: '42%', shift: '-16px', rise: '20px', duration: '56s', delay: '-24s' },
]

const INTENSITIES = new Set(['soft', 'subtle', 'rich'])

export default function AmbientOrbs({ count = 2, intensity = 'subtle', className = '', ...rest }) {
  const prefersReducedMotion = useReducedMotion()
  const resolvedCount = Math.max(0, Math.min(Number(count) || 0, ORB_LAYOUTS.length))
  const resolvedIntensity = INTENSITIES.has(intensity) ? intensity : 'subtle'

  if (resolvedCount === 0) return null

  const classes = ['sz-ambient', `sz-ambient--${resolvedIntensity}`, className]
    .filter(Boolean)
    .join(' ')

  return (
    <div
      className={classes}
      aria-hidden="true"
      data-reduced-motion={prefersReducedMotion ? '' : undefined}
      {...rest}
    >
      {ORB_LAYOUTS.slice(0, resolvedCount).map((layout, index) => (
        <span
          key={index}
          className="sz-ambient__orb"
          data-variant={index % 3}
          style={{
            width: layout.size,
            height: layout.size,
            top: layout.top,
            left: layout.left,
            right: layout.right,
            bottom: layout.bottom,
            '--sz-orb-shift': layout.shift,
            '--sz-orb-rise': layout.rise,
            '--sz-orb-duration': layout.duration,
            '--sz-orb-delay': layout.delay,
          }}
        />
      ))}
    </div>
  )
}
