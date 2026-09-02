import { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { countryImages, FALLBACK_IMAGE } from '../data/countryImages'
import { countryThemes, defaultTheme } from '../data/countryThemes'
import './CountryPage.css'
import '../styles/liquid-bg.css'

const FEATURED_COUNTRIES = ['Japan', 'USA', 'Germany', 'UK', 'Australia', 'Canada']

const COUNTRY_ORDER = [
  'Japan', 'USA', 'Germany', 'UK', 'Australia', 'Canada',
  'France', 'Italy', 'Spain', 'Netherlands', 'Switzerland',
  'Sweden', 'Singapore', 'China', 'India', 'South Korea',
  'Taiwan', 'Austria', 'Belgium',
]

function SkeletonCard({ tier }) {
  return (
    <div className={`country-editorial-card country-editorial-card--${tier}`} aria-hidden="true">
      <div className="country-editorial-card__image-wrap">
        <div className="country-editorial-card__skeleton" />
      </div>
    </div>
  )
}

export default function CountryPage() {
  const [counts, setCounts] = useState({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const countryNames = useMemo(() => {
    const all = Object.keys(countryImages)
    const ordered = COUNTRY_ORDER.filter((name) => all.includes(name))
    const remaining = all.filter((name) => !ordered.includes(name))
    return [...ordered, ...remaining]
  }, [])

  useEffect(() => {
    let cancelled = false

    async function fetchCounts() {
      try {
        const results = await Promise.allSettled(
          countryNames.map((name) =>
            fetch(`/api/scholarships?country=${encodeURIComponent(name)}&limit=1`)
              .then((r) => r.json())
              .then((data) => ({ name, total: data?.pagination?.total ?? 0 }))
              .catch(() => ({ name, total: 0 }))
          )
        )

        if (!cancelled) {
          const map = {}
          results.forEach((res) => {
            if (res.status === 'fulfilled') {
              map[res.value.name] = res.value.total
            }
          })
          setCounts(map)
          setLoading(false)
        }
      } catch (e) {
        if (!cancelled) {
          setError(e)
          setLoading(false)
        }
      }
    }

    fetchCounts()
    return () => {
      cancelled = true
    }
  }, [countryNames])

  const getTier = (name) => {
    if (!FEATURED_COUNTRIES.includes(name)) return 'tier3'
    const idx = FEATURED_COUNTRIES.indexOf(name)
    return idx < 2 ? 'tier1' : 'tier2'
  }

  return (
    <div className="country-explorer">
      <div className="liquid-bg" aria-hidden="true">
        <div className="liquid-bg__orb liquid-bg__orb--1" />
        <div className="liquid-bg__orb liquid-bg__orb--2" />
        <div className="liquid-bg__orb liquid-bg__orb--3" />
        <div className="liquid-bg__orb liquid-bg__orb--4" />
        <div className="liquid-bg__orb liquid-bg__orb--5" />
        <div className="liquid-bg__orb liquid-bg__orb--6" />
      </div>

      <div className="country-explorer__content">
        <header className="country-explorer__header">
          <span className="country-explorer__kicker">Destinations</span>
          <h1 className="country-explorer__title">Explore Destinations</h1>
          <p className="country-explorer__subtitle">
            Discover scholarships across the world&rsquo;s top study abroad destinations.
          </p>
          <div className="country-explorer__rule" aria-hidden="true" />
        </header>

        <div className="country-editorial-grid">
          {loading
            ? countryNames.map((name) => (
                <SkeletonCard key={name} tier={getTier(name)} />
              ))
            :               countryNames.map((name, idx) => {
                const total = counts[name] || 0
                const theme = countryThemes[name] || defaultTheme
                const tier = getTier(name)
                const image = countryImages[name] || FALLBACK_IMAGE

                return (
                  <Link
                    key={name}
                    to={`/scholarships?country=${encodeURIComponent(name)}`}
                    state={{
                      primary: theme.primary,
                      secondary: theme.secondary,
                      tertiary: theme.tertiary,
                      accent: theme.accent,
                      base: theme.base,
                    }}
                    className={`country-editorial-card country-editorial-card--${tier}`}
                    aria-label={`${name}: ${total} scholarships`}
                  >
                    <div className="country-editorial-card__image-wrap">
                      <img
                        src={image}
                        alt=""
                        width="800"
                        height="600"
                        loading={idx < 4 ? 'eager' : 'lazy'}
                        decoding="async"
                        fetchPriority={idx < 4 ? 'high' : undefined}
                        onLoad={(e) => e.currentTarget.classList.add('loaded')}
                        onError={(e) => {
                          e.currentTarget.onerror = null
                          e.currentTarget.src = FALLBACK_IMAGE
                        }}
                      />
                      <div className="country-editorial-card__overlay" />
                    </div>
                    <div className="country-editorial-card__content">
                      <h2 className="country-editorial-card__name">{name}</h2>
                      <div className="country-editorial-card__meta">
                        <span className="country-editorial-card__count">
                          {total} {total === 1 ? 'scholarship' : 'scholarships'}
                        </span>
                        <span className="country-editorial-card__explore">
                          Explore <span aria-hidden="true">&rarr;</span>
                        </span>
                      </div>
                    </div>
                  </Link>
                )
              })}
        </div>

        {error && (
          <p className="country-explorer__error">
            Unable to load live counts. Showing available destinations only.
          </p>
        )}
      </div>
    </div>
  )
}
