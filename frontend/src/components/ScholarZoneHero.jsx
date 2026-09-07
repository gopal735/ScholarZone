import { useState, useEffect, useMemo } from 'react'
import { fetchScholarships } from '../services/scholarshipService'
import './ScholarZoneHero.css'

function ScholarshipCard({ card, index }) {
  return (
    <article
      className="sz-hero-card"
      style={{ animationDelay: `${index * 0.1}s` }}
    >
      <div className="sz-hero-card__inner">
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
      </div>
    </article>
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
      <div className="sz-hero__content">
        <div className="sz-hero__text">
          <div className="sz-hero__badge">
            <span className="sz-hero__badge-dot" />
            Verified scholarships, clearly organised
          </div>

          <h1 className="sz-hero__heading">
            Find the right <em>scholarship</em> with confidence.
          </h1>

          <p className="sz-hero__description">
            ScholarZone brings funding, degree level, location and deadlines into one focused directory
            — so you spend less time searching and more time preparing your application.
          </p>

          <div className="sz-hero__actions">
            <a href="/scholarships" className="sz-hero__cta sz-hero__cta--primary">
              Explore Scholarships
              <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor">
                <path d="M8 0a1 1 0 01.707.293l3.5 3.5a1 1 0 01-1.414 1.414L9 3.414V11a1 1 0 11-2 0V3.414L5.293 5.207a1 1 0 01-1.414-1.414l3.5-3.5A1 1 0 018 0z" transform="rotate(90 8 8)" />
              </svg>
            </a>
            <a href="/countries" className="sz-hero__cta sz-hero__cta--secondary">
              How ScholarZone Works
            </a>
          </div>

          {!isLoading && (
            <LiveDataIndicator
              count={stats.count}
              countries={stats.countries}
              fullyFunded={stats.fullyFunded}
              verified={stats.verified}
            />
          )}
        </div>

        <div className="sz-hero__cards">
          <div className="sz-hero__cards-stack">
            {displayScholarships.map((card, index) => (
              <ScholarshipCard
                key={card.id}
                card={card}
                index={index}
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
        </div>
      </div>
    </section>
  )
}
