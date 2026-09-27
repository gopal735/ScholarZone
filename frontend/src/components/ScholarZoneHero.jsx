import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import ScholarshipCard from './ScholarshipCard'
import ScholarshipCardSkeleton from './ScholarshipCardSkeleton'
import { getDeadlineLabel } from '../utils/scholarshipPresentation'
import { useScholarshipDirectory } from '../hooks/useScholarshipDirectory'
import { fetchScholarshipStats, fetchScholarships } from '../services/scholarshipService'
import './ScholarZoneHero.css'

/* Pointer input is ignored on touch and coarse pointers: there is no
   hover state there, and the planes would be left offset after a tap.
   Evaluated once at module load rather than per render. */
const CAN_TILT =
  typeof window !== 'undefined' &&
  window.matchMedia('(hover: hover) and (pointer: fine)').matches

const MAX_PREVIEW = 4

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

/* The hero's visual centrepiece.
 *
 * Built from live directory data, so it can never drift from the
 * product. The composition follows the reference pattern: one large
 * media plane, with two smaller information cards overlapping its lower
 * edge at different depths. The overlap is what produces the sense of
 * layered space — a single card on a canvas reads as a card, a card with
 * two satellites crossing its boundary reads as a scene.
 *
 * The centrepiece is built from live directory data, so it can never
 * drift out of sync with the product. Nothing in it is a mockup.
 * ═════════════════════════════════════════════════════════════════════ */
function HeroShowcase({ scholarship, ref, onPointerMove, onPointerLeave }) {
  return (
    <div className="sz-hero__showcase" ref={ref} onPointerMove={onPointerMove} onPointerLeave={onPointerLeave}>
      <div className="sz-hero__stage">
        {/* Depth plane 1 — furthest back, offset up-left. */}
        <span className="sz-hero__plane sz-hero__plane--far" aria-hidden="true" />

        <div className="sz-hero__frame">
          <div className="sz-hero__showcase-card">
            {scholarship ? (
              <ScholarshipCard scholarship={scholarship} />
            ) : (
              <ScholarshipCardSkeleton />
            )}
            {scholarship ? (
              <>
                <aside className="sz-hero__chip sz-hero__chip--deadline" aria-label={`Application deadline: ${getDeadlineLabel(scholarship)}`}>
                  <span className="sz-hero__chip-label">Deadline</span>
                  <strong className="sz-hero__chip-value">{getDeadlineLabel(scholarship)}</strong>
                  <span className="sz-hero__chip-note">
                    {scholarship.deadline_precision === 'month' ? 'Month only' : 'Confirmed date'}
                  </span>
                </aside>

                <aside className="sz-hero__chip sz-hero__chip--funding">
                  <span className="sz-hero__chip-label">Funding</span>
                  <strong className="sz-hero__chip-value">{scholarship.funding}</strong>
                  <span className="sz-hero__chip-note">{scholarship.degree}</span>
                </aside>
              </>
            ) : null}
          </div>

          {/* Depth plane 2 — offset down-right, closest to the viewer. */}
          <span className="sz-hero__plane sz-hero__plane--near" aria-hidden="true" />
        </div>

        <p className="sz-hero__showcase-note">
          Every listing is checked against the awarding body&rsquo;s own page before it
          appears here.
        </p>
      </div>
    </div>
  )
}

export default function ScholarZoneHero() {
  const { scholarships, isLoading, isUsingFallback, error } = useScholarshipDirectory()
  const [stats, setStats] = useState(null)
  const [statsLoading, setStatsLoading] = useState(true)
  const [recentScholarships, setRecentScholarships] = useState([])
  const [recentLoading, setRecentLoading] = useState(true)
  const [recentError, setRecentError] = useState(null)

  const showcaseRef = useRef(null)

  // Fetch live stats from dedicated endpoint
  useEffect(() => {
    let cancelled = false
    fetchScholarshipStats()
      .then((data) => {
        if (!cancelled) {
          setStats({
            count: data.total,
            countries: data.countries,
            fullyFunded: data.fully_funded,
            verified: data.verified_active,
          })
          setStatsLoading(false)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setStatsLoading(false)
        }
      })
    return () => { cancelled = true }
  }, [])

  // Fetch recently added scholarships for preview section
  useEffect(() => {
    let cancelled = false
    fetchScholarships({ sort: 'recently-added', limit: MAX_PREVIEW })
      .then((directory) => {
        if (!cancelled) {
          setRecentScholarships(directory.items)
          setRecentLoading(false)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setRecentError(err)
          setRecentLoading(false)
        }
      })
    return () => { cancelled = true }
  }, [])

  const previewScholarships = useMemo(
    () => (recentScholarships.length > 0 ? recentScholarships : scholarships.slice(0, MAX_PREVIEW)),
    [recentScholarships, scholarships]
  )

  // Select a scholarship with an image for the hero showcase
  // Prefer recently added with images, then fall back to directory data
  const showcaseScholarship = useMemo(() => {
    // First try recently added
    let withImage = previewScholarships.find((s) => s.image_url)
    if (withImage) return withImage
    // Then try the full directory data
    withImage = scholarships.find((s) => s.image_url)
    if (withImage) return withImage
    // Fall back to first available
    return previewScholarships[0] ?? scholarships[0]
  }, [previewScholarships, scholarships])

  /* Writes two custom properties to one node. No state, no animation
     frame, no measurement beyond the rect the browser already has for
     hit-testing. The three planes read them and offset by different
     fractions, which is what produces the parallax. */
  const handlePointerMove = useCallback((event) => {
    const node = showcaseRef.current
    if (!node) return

    const rect = node.getBoundingClientRect()
    if (rect.width === 0 || rect.height === 0) return

    const x = (event.clientX - rect.left) / rect.width - 0.5
    const y = (event.clientY - rect.top) / rect.height - 0.5

    // Capped at 7px. Enough to separate the planes, not enough to read
    // as the page following the cursor.
    node.style.setProperty('--sx-px', `${(x * 7).toFixed(2)}px`)
    node.style.setProperty('--sx-py', `${(y * 7).toFixed(2)}px`)
  }, [])

  const handlePointerLeave = useCallback(() => {
    const node = showcaseRef.current
    if (!node) return
    node.style.setProperty('--sx-px', '0px')
    node.style.setProperty('--sx-py', '0px')
  }, [])

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

          {isLoading ? (
            <div className="sz-hero__loading" aria-label="Loading scholarship data">
              <span className="sz-hero__loading-spinner" aria-hidden="true" />
              <span>Loading scholarship data...</span>
            </div>
          ) : (
            <>
              {stats && !isUsingFallback && (
                <LiveDataIndicator
                  count={stats.count}
                  countries={stats.countries}
                  fullyFunded={stats.fullyFunded}
                  verified={stats.verified}
                />
              )}
              {statsLoading && !isUsingFallback && !stats && (
                <div className="sz-hero__loading" aria-label="Loading directory figures">
                  <span className="sz-hero__loading-spinner" aria-hidden="true" />
                  <span>Loading directory figures...</span>
                </div>
              )}
              {isUsingFallback && (
                <p className="sz-hero__fallback-notice" role="status">
                  ⚠️ Live directory unavailable — showing local data.
                </p>
              )}
              {!stats && !statsLoading && !isUsingFallback && (
                <p className="sz-hero__fallback-notice" role="status">
                  ⚠️ Live stats unavailable — showing directory data.
                </p>
              )}
            </>
          )}

          {error && (
            <div className="sz-hero__error" role="alert">
              <span>⚠️ Failed to load scholarship data. </span>
              <button type="button" onClick={() => window.location.reload()}>
                Retry
              </button>
            </div>
          )}
        </div>

        <HeroShowcase
          ref={showcaseRef}
          scholarship={showcaseScholarship}
          onPointerMove={CAN_TILT ? handlePointerMove : undefined}
          onPointerLeave={CAN_TILT ? handlePointerLeave : undefined}
        />
      </div>

      <section className="sz-hero__preview" aria-label="Recently added opportunities">
        <div className="sz-hero__preview-head">
          <h2 className="sz-hero__preview-title">Recently added</h2>
          <Link to="/scholarships" className="sz-hero__preview-link">
            View the full directory <span aria-hidden="true">&rarr;</span>
          </Link>
        </div>

        {(recentLoading || isLoading) ? (
          <div className="sz-hero__grid" aria-hidden="true">
            {[1, 2, 3, 4].map((item) => (
              <ScholarshipCardSkeleton key={item} />
            ))}
          </div>
        ) : recentError ? (
          <div className="sz-hero__grid">
            {previewScholarships.map((scholarship) => (
              <ScholarshipCard key={scholarship.id} scholarship={scholarship} />
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
