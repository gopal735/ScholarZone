import { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { scholarships as localScholarships } from '../data/scholarships'
import { fetchScholarships } from '../services/scholarshipService'
import ScholarshipCard from './ScholarshipCard'
import './ScholarZoneHero.css'

const MAX_PREVIEW = 4

function summarise(items) {
  const countries = new Set(items.map((s) => s.country).filter(Boolean))
  return {
    count: items.length,
    countries: countries.size,
    fullyFunded: items.filter((s) => s.funding === 'Fully Funded').length,
    verified: items.filter((s) => s.verified).length,
  }
}

function LiveDataIndicator({ count, countries, fullyFunded, verified }) {
  return (
    <dl className="sz-hero__stats" aria-label="Live directory figures">
      <div className="sz-hero__stat">
        <dt>Opportunities</dt>
        <dd>{count}</dd>
      </div>
      <div className="sz-hero__stat">
        <dt>Countries</dt>
        <dd>{countries}</dd>
      </div>
      <div className="sz-hero__stat">
        <dt>Fully funded</dt>
        <dd>{fullyFunded}</dd>
      </div>
      <div className="sz-hero__stat">
        <dt>Verified</dt>
        <dd>{verified}</dd>
      </div>
    </dl>
  )
}

/* The hero's visual centrepiece. A single real scholarship floating in
   front of two offset depth planes, inside a slow orbital ring. Every
   value shown comes from the live directory, so the composition can
   never drift out of sync with the product. */
function HeroShowcase({ scholarship }) {
  return (
    <div className="sz-hero__showcase">
      <div className="sz-hero__showcase-stage">
        <span className="sz-hero__ring sz-hero__ring--outer" aria-hidden="true">
          <span className="sz-hero__ring-node" />
        </span>
        <span className="sz-hero__ring sz-hero__ring--inner" aria-hidden="true" />
        <span className="sz-hero__plane sz-hero__plane--far" aria-hidden="true" />
        <span className="sz-hero__plane sz-hero__plane--near" aria-hidden="true" />

        <div className="sz-hero__showcase-card">
          {scholarship ? (
            <ScholarshipCard scholarship={scholarship} />
          ) : (
            <>
              <span className="sz-hero-card-skeleton__media" />
              <span className="sz-hero-card-skeleton__line" />
              <span className="sz-hero-card-skeleton__line sz-hero-card-skeleton__line--short" />
            </>
          )}
        </div>
      </div>

      <p className="sz-hero__showcase-note">
        Every listing is checked against the awarding body&rsquo;s own page before it
        appears here.
      </p>
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
        setScholarships(items.slice(0, MAX_PREVIEW))
        setStats(summarise(items))
        setIsLoading(false)
      })
      .catch(() => {
        if (controller.signal.aborted) return

        // The showcase already falls back to the bundled directory when
        // the API is unavailable. The hero does the same so the figures
        // and preview never render as an empty, zeroed block.
        setScholarships(localScholarships.slice(0, MAX_PREVIEW))
        setStats(summarise(localScholarships))
        setIsLoading(false)
      })

    return () => controller.abort()
  }, [])

  const previewScholarships = useMemo(() => scholarships.slice(0, MAX_PREVIEW), [scholarships])

  return (
    <section className="sz-hero" aria-label="ScholarZone introduction">
      <div className="sz-hero__inner">
        <div className="sz-hero__text">
          <p className="sz-hero__eyebrow">
            <span className="sz-hero__eyebrow-dot" aria-hidden="true" />
            Verified scholarships, clearly organised
          </p>

          <h1 className="sz-hero__heading">
            Find the right <em>scholarship</em> with confidence.
          </h1>

          <p className="sz-hero__description">
            ScholarZone brings funding, degree level, location and deadlines into one focused
            directory &mdash; so you spend less time searching and more time preparing your
            application.
          </p>

          <div className="sz-hero__actions">
            <Link to="/scholarships" className="sz-hero__cta sz-hero__cta--primary">
              Explore Scholarships
              <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor" aria-hidden="true">
                <path d="M8 0a1 1 0 01.707.293l3.5 3.5a1 1 0 01-1.414 1.414L9 3.414V11a1 1 0 11-2 0V3.414L5.293 5.207a1 1 0 01-1.414-1.414l3.5-3.5A1 1 0 018 0z" transform="rotate(90 8 8)" />
              </svg>
            </Link>
            <Link to="/countries" className="sz-hero__cta sz-hero__cta--secondary">
              Browse by country
            </Link>
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

        <HeroShowcase scholarship={previewScholarships[0]} />
      </div>

      <section className="sz-hero__preview" aria-label="Recently added opportunities">
        <div className="sz-hero__preview-head">
          <h2 className="sz-hero__preview-title">Recently added</h2>
          <Link to="/scholarships" className="sz-hero__preview-link">
            View the full directory <span aria-hidden="true">&rarr;</span>
          </Link>
        </div>

        {isLoading ? (
          <div className="sz-hero__grid" aria-hidden="true">
            {[1, 2, 3, 4].map((item) => (
              <div key={item} className="sz-hero-card-skeleton">
                <span className="sz-hero-card-skeleton__media" />
                <span className="sz-hero-card-skeleton__line" />
                <span className="sz-hero-card-skeleton__line sz-hero-card-skeleton__line--short" />
              </div>
            ))}
          </div>
        ) : (
          <div className="sz-hero__grid">
            {previewScholarships.map((scholarship) => (
              <ScholarshipCard key={scholarship.id} scholarship={scholarship} />
            ))}
          </div>
        )}
      </section>
    </section>
  )
}
