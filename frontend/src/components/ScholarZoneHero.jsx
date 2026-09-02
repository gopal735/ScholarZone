import { useState, useEffect, useMemo } from 'react'
import {
  motion,
  useMotionValue,
  useSpring,
  useTransform,
  useReducedMotion,
  AnimatePresence,
} from 'motion/react'
import { fetchScholarships } from '../services/scholarshipService'
import './ScholarZoneHero.css'

const SPRING_CONFIG = { stiffness: 50, damping: 20 }

function usePointerParallax() {
  const shouldReduceMotion = useReducedMotion()
  const rawX = useMotionValue(0)
  const rawY = useMotionValue(0)

  const springX = useSpring(rawX, SPRING_CONFIG)
  const springY = useSpring(rawY, SPRING_CONFIG)

  const transformX = useTransform(springX, [-0.5, 0.5], [-1, 1])
  const transformY = useTransform(springY, [-0.5, 0.5], [-1, 1])

  useEffect(() => {
    if (shouldReduceMotion) return

    const handlePointerMove = (e) => {
      const x = (e.clientX / window.innerWidth - 0.5) * 2
      const y = (e.clientY / window.innerHeight - 0.5) * 2
      rawX.set(x)
      rawY.set(y)
    }

    window.addEventListener('pointermove', handlePointerMove, { passive: true })
    return () => window.removeEventListener('pointermove', handlePointerMove)
  }, [shouldReduceMotion, rawX, rawY])

  return { transformX, transformY, shouldReduceMotion }
}

function ParallaxLayer({ children, depth, transformX, transformY, className }) {
  const offsetX = useTransform(transformX, (v) => v * depth * 15)
  const offsetY = useTransform(transformY, (v) => v * depth * 15)

  return (
    <motion.div className={className} style={{ x: offsetX, y: offsetY }}>
      {children}
    </motion.div>
  )
}

function ScholarshipCard({ card, index, shouldReduceMotion }) {
  const [isHovered, setIsHovered] = useState(false)

  const hoverLift = shouldReduceMotion ? 0 : -4
  const hoverScale = shouldReduceMotion ? 1 : 1.02

  return (
    <motion.article
      className="sz-hero-card"
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        delay: 0.5 + index * 0.1,
        duration: 0.6,
        ease: [0.16, 1, 0.3, 1],
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <motion.div
        className="sz-hero-card__inner"
        animate={{
          y: isHovered ? hoverLift : 0,
          scale: isHovered ? hoverScale : 1,
        }}
        transition={{ type: 'spring', stiffness: 300, damping: 20 }}
      >
        <div className="sz-hero-card__header">
          <span className="sz-hero-card__country">{card.country}</span>
          {card.verified && (
            <span className="sz-hero-card__verified">
              <svg viewBox="0 0 16 16" width="12" height="12" fill="currentColor">
                <path d="M8 0a8 8 0 100 16A8 8 0 008 0zm3.41 5.59a.75.75 0 010 1.06l-3.5 3.5a.75.75 0 01-1.06 0l-1.5-1.5a.75.75 0 011.06-1.06l.97.97 2.97-2.97a.75.75 0 011.06 0z" />
              </svg>
              <span>Verified</span>
            </span>
          )}
        </div>

        <h3 className="sz-hero-card__title">{card.title}</h3>

        <dl className="sz-hero-card__details">
          <div className="sz-hero-card__detail">
            <dt>Degree</dt>
            <dd>{card.degree}</dd>
          </div>
          <div className="sz-hero-card__detail">
            <dt>Funding</dt>
            <dd>{card.funding}</dd>
          </div>
        </dl>

        {card.deadline && (
          <p className="sz-hero-card__deadline">
            <span>Deadline</span>
            <span>{card.deadline}</span>
          </p>
        )}
      </motion.div>
    </motion.article>
  )
}

function AmbientGlow({ size, top, left, delay, color }) {
  return (
    <motion.div
      className="sz-hero-glow"
      style={{ width: size, height: size, top, left }}
      animate={{
        opacity: [0.4, 0.7, 0.4],
        scale: [1, 1.1, 1],
      }}
      transition={{
        duration: 6 + delay,
        repeat: Infinity,
        delay,
        ease: 'easeInOut',
      }}
    >
      <div className="sz-hero-glow__blob" style={{ background: color }} />
    </motion.div>
  )
}

function LiveDataIndicator({ count, countries, fullyFunded, verified }) {
  return (
    <div className="sz-hero__live-data">
      <span className="sz-hero__live-dot" />
      <span className="sz-hero__live-label">Live directory</span>
      <span className="sz-hero__live-stats">
        <strong>{count}</strong> opportunities
        <span className="sz-hero__live-divider">|</span>
        <strong>{countries}</strong> countries
        <span className="sz-hero__live-divider">|</span>
        <strong>{fullyFunded}</strong> fully funded
        <span className="sz-hero__live-divider">|</span>
        <strong>{verified}</strong> verified
      </span>
    </div>
  )
}

export default function ScholarZoneHero() {
  const [scholarships, setScholarships] = useState([])
  const [stats, setStats] = useState({ count: 0, countries: 0, fullyFunded: 0, verified: 0 })
  const [isLoading, setIsLoading] = useState(true)

  const { transformX, transformY, shouldReduceMotion } = usePointerParallax()

  useEffect(() => {
    const controller = new AbortController()

    fetchScholarships({ page: 1, limit: 100 }, { signal: controller.signal })
      .then((data) => {
        if (controller.signal.aborted) return

        const items = data.items
        setScholarships(items.slice(0, 4))

        const countries = new Set(items.map((s) => s.country).filter(Boolean))
        const fullyFunded = items.filter((s) => s.funding === 'Fully Funded').length
        const verified = items.filter((s) => s.verified).length

        setStats({
          count: items.length,
          countries: countries.size,
          fullyFunded,
          verified,
        })
        setIsLoading(false)
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false)
        }
      })

    return () => controller.abort()
  }, [])

  const displayScholarships = useMemo(() => {
    return scholarships.map((s, i) => ({
      ...s,
      _delay: i * 0.1,
    }))
  }, [scholarships])

  return (
    <section className="sz-hero" aria-label="ScholarZone introduction">
      <ParallaxLayer
        depth={0.03}
        transformX={transformX}
        transformY={transformY}
        className="sz-hero__glows"
      >
        {!shouldReduceMotion && (
          <>
            <AmbientGlow
              size={500}
              top="-10%"
              left="60%"
              delay={0}
              color="radial-gradient(circle, rgba(99, 143, 255, 0.15) 0%, transparent 70%)"
            />
            <AmbientGlow
              size={400}
              top="50%"
              left="80%"
              delay={2}
              color="radial-gradient(circle, rgba(130, 168, 255, 0.1) 0%, transparent 70%)"
            />
          </>
        )}
      </ParallaxLayer>

      <ParallaxLayer
        depth={0.02}
        transformX={transformX}
        transformY={transformY}
        className="sz-hero__grid"
      >
        <div className="sz-hero__grid-lines" />
      </ParallaxLayer>

      <div className="sz-hero__content">
        <div className="sz-hero__text">
          <motion.div
            className="sz-hero__badge"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          >
            <span className="sz-hero__badge-dot" />
            Verified scholarships, clearly organised
          </motion.div>

          <motion.h1
            className="sz-hero__heading"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          >
            Find the right <em>scholarship</em> with confidence.
          </motion.h1>

          <motion.p
            className="sz-hero__description"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.35, duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
          >
            ScholarZone brings funding, degree level, location and deadlines into one focused directory
            — so you spend less time searching and more time preparing your application.
          </motion.p>

          <motion.div
            className="sz-hero__actions"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          >
            <a href="/scholarships" className="sz-hero__cta sz-hero__cta--primary">
              Explore Scholarships
              <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor">
                <path d="M8 0a1 1 0 01.707.293l3.5 3.5a1 1 0 01-1.414 1.414L9 3.414V11a1 1 0 11-2 0V3.414L5.293 5.207a1 1 0 01-1.414-1.414l3.5-3.5A1 1 0 018 0z" transform="rotate(90 8 8)" />
              </svg>
            </a>
            <a href="/countries" className="sz-hero__cta sz-hero__cta--secondary">
              How ScholarZone Works
            </a>
          </motion.div>

          <AnimatePresence>
            {!isLoading && (
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.65, duration: 0.45 }}
              >
                <LiveDataIndicator
                  count={stats.count}
                  countries={stats.countries}
                  fullyFunded={stats.fullyFunded}
                  verified={stats.verified}
                />
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <ParallaxLayer
          depth={0.06}
          transformX={transformX}
          transformY={transformY}
          className="sz-hero__cards"
        >
          <div className="sz-hero__cards-stack">
            {displayScholarships.map((card, index) => (
              <ScholarshipCard
                key={card.id}
                card={card}
                index={index}
                shouldReduceMotion={shouldReduceMotion}
              />
            ))}
            {isLoading && (
              <>
                <div className="sz-hero-card sz-hero-card--skeleton" />
                <div className="sz-hero-card sz-hero-card--skeleton" />
                <div className="sz-hero-card sz-hero-card--skeleton" />
                <div className="sz-hero-card sz-hero-card--skeleton" />
              </>
            )}
          </div>
        </ParallaxLayer>
      </div>
    </section>
  )
}
