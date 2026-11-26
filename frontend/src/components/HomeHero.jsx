import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import ScholarshipCard from '../components/ScholarshipCard'
import { fetchScholarships } from '../services/scholarshipService'
import { scholarships as fallbackScholarships } from '../data/scholarships'
import './HomeHero.css'

function LiveIndicator({ stats, isLoading, isUnavailable }) {
  if (isUnavailable) {
    return (
      <div className="home-hero__indicator home-hero__indicator--offline" role="status">
        <span className="home-hero__indicator-dot" aria-hidden="true" />
        <span>Live directory unavailable</span>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="home-hero__indicator home-hero__indicator--loading" aria-busy="true">
        <span className="home-hero__indicator-dot" aria-hidden="true" />
        <span>Loading live data…</span>
      </div>
    )
  }

  return (
    <div className="home-hero__indicator" role="status" aria-live="polite">
      <span className="home-hero__indicator-dot" aria-hidden="true" />
      <span className="home-hero__indicator-label">Live directory</span>
      <span className="home-hero__indicator-sep" aria-hidden="true">|</span>
      <strong>{stats.total}</strong> opportunities
      <span className="home-hero__indicator-sep" aria-hidden="true">|</span>
      <strong>{stats.countries}</strong> countries
      <span className="home-hero__indicator-sep" aria-hidden="true">|</span>
      <strong>{stats.verified_active}</strong> verified
    </div>
  )
}

export default function HomeHero({ stats, isLoading, isUnavailable }) {
  const [preview, setPreview] = useState([])
  const [loading, setLoading] = useState(true)
  const [useFallback, setUseFallback] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    fetchScholarships({ page: 1, limit: 3 }, { signal: controller.signal })
      .then((data) => {
        if (controller.signal.aborted) return
        setPreview(data.items)
        setLoading(false)
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setPreview(fallbackScholarships.slice(0, 3))
          setUseFallback(true)
          setLoading(false)
        }
      })
    return () => controller.abort()
  }, [])

  return (
    <section className="home-hero" aria-label="ScholarZone introduction">
      <div className="home-hero__grid">
        <div className="home-hero__content">
          <div className="home-hero__eyebrow">Trusted scholarship intelligence</div>
          <h1 className="home-hero__title">
            Find the right <em>scholarship</em> with confidence.
          </h1>
          <p className="home-hero__description">
            Verified listings, official sources, and real deadlines — so you spend less time searching and more time preparing your application.
          </p>
          <div className="home-hero__actions">
            <Link to="/scholarships" className="sz-btn sz-btn--primary">
              Explore scholarships
              <svg viewBox="0 0 24 24" aria-hidden="true" width="16" height="16">
                <path d="M5 12h14M13 5l7 7-7 7" />
              </svg>
            </Link>
            <a href="#how-it-works" className="sz-btn sz-btn--secondary">How it works</a>
          </div>
          <LiveIndicator stats={stats} isLoading={isLoading} isUnavailable={isUnavailable} />
        </div>

        <div className="home-hero__preview">
          {loading ? (
            <div className="home-hero__skeleton" aria-hidden="true">
              <div className="home-hero__skeleton-card" />
              <div className="home-hero__skeleton-card" />
              <div className="home-hero__skeleton-card" />
            </div>
          ) : (
            <>
              {useFallback && (
                <p className="home-hero__fallback-notice" role="status">
                  Showing local directory data.
                </p>
              )}
              <div className="home-hero__cards">
                {preview.map((s, i) => (
                  <div key={s.id} className="home-hero__card" style={{ animationDelay: `${i * 0.08}s` }}>
                    <ScholarshipCard scholarship={s} />
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </section>
  )
}
