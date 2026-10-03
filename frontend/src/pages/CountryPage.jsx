import { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { countryImages, FALLBACK_IMAGE } from '../data/countryImages'
import { countryThemes, defaultTheme } from '../data/countryThemes'
import { fetchScholarships } from '../services/scholarshipService'
import './CountryPage.css'
import { CANONICAL_ORIGIN } from '../services/canonicalOrigin'

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

  const countryNames = useMemo(() => {
    const all = Object.keys(countryImages)
    const ordered = COUNTRY_ORDER.filter((name) => all.includes(name))
    const remaining = all.filter((name) => !ordered.includes(name))
    return [...ordered, ...remaining]
  }, [])

  useEffect(() => {
    let cancelled = false

    // Bounded concurrency. This page needs one count per country, and it
    // fired all of them at once — 38 parallel requests on the last count,
    // which is what makes the country grid arrive slowly and then land in one
    // burst. Six at a time matches the per-origin connection limit, so the
    // browser is never asked to hold more open sockets than it can use, and
    // the counts that arrive first can paint immediately instead of waiting
    // on the slowest.
    //
    // The requests still go through fetchScholarships rather than a bare
    // fetch('/api/...'): the literal path ignored VITE_API_BASE_URL, so this
    // page was the one place that could not be pointed at another host.
    const CONCURRENCY = 6

    async function fetchCounts() {
      const counts = new Map()
      let cursor = 0

      async function worker() {
        while (cursor < countryNames.length) {
          const name = countryNames[cursor]
          cursor += 1
          try {
            const data = await fetchScholarships({ country: name, limit: 1 })
            counts.set(name, data?.pagination?.total ?? 0)
          } catch {
            counts.set(name, 0)
          }
          if (!cancelled) {
            setCounts(Object.fromEntries(counts))
          }
        }
      }

      try {
        await Promise.all(
          Array.from({ length: Math.min(CONCURRENCY, countryNames.length) }, worker),
        )
      } catch {
        // Individual failures are already recorded as zero above.
      }

      if (!cancelled) {
        setLoading(false)
      }
    }

    fetchCounts()
    return () => {
      cancelled = true
    }
  }, [countryNames])

  // SEO meta tags
  useEffect(() => {
    const baseUrl = CANONICAL_ORIGIN
    
    document.querySelectorAll('[data-sz-seo]').forEach(el => el.remove())
    
    const metaTags = [
      { name: 'description', content: 'Explore scholarships by country. Discover verified scholarship opportunities across the world\'s top study abroad destinations with verified official sources.' },
      { property: 'og:title', content: 'Explore Destinations | ScholarZone' },
      { property: 'og:description', content: 'Discover verified scholarship opportunities across the world\'s top study abroad destinations with verified official sources.' },
      { property: 'og:url', content: `${baseUrl}/countries` },
      { property: 'og:type', content: 'website' },
      { name: 'twitter:card', content: 'summary_large_image' },
      { name: 'twitter:title', content: 'Explore Destinations | ScholarZone' },
      { name: 'twitter:description', content: 'Discover verified scholarship opportunities across the world\'s top study destinations.' },
      { name: 'robots', content: 'index, follow' },
    ]
    
    document.querySelectorAll('[data-sz-seo]').forEach(el => el.remove())
    
    metaTags.forEach(meta => {
      const el = document.createElement('meta')
      Object.entries(meta).forEach(([k, v]) => { if (v) el.setAttribute(k, v) })
      el.setAttribute('data-sz-seo', 'true')
      document.head.appendChild(el)
    })
    
    const canonical = document.createElement('link')
    canonical.rel = 'canonical'
    canonical.href = `${baseUrl}/countries`
    canonical.setAttribute('data-sz-seo', 'true')
    document.head.appendChild(canonical)
    
    const script = document.createElement('script')
    script.type = 'application/ld+json'
    script.setAttribute('data-sz-seo', 'true')
    script.textContent = JSON.stringify({
      '@context': 'https://schema.org',
      '@type': 'CollectionPage',
      name: 'Explore Destinations',
      description: 'Discover verified scholarship opportunities across the world\'s top study abroad destinations.',
      url: `${baseUrl}/countries`,
      mainEntity: {
        '@type': 'ItemList',
        itemListElement: []
      }
    }, null, 2)
    script.setAttribute('data-sz-seo', 'true')
    document.head.appendChild(script)
    
    return () => {
      document.querySelectorAll('[data-sz-seo]').forEach(el => el.remove())
    }
  }, [])

  const getTier = (name) => {
    if (!FEATURED_COUNTRIES.includes(name)) return 'tier3'
    const idx = FEATURED_COUNTRIES.indexOf(name)
    return idx < 2 ? 'tier1' : 'tier2'
  }

  return (
    <div className="country-explorer">
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
            : countryNames.map((name, idx) => {
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
                          {total} scholarship{total !== 1 ? 's' : ''}
                        </span>
                        <span className="country-editorial-card__tier">{tier}</span>
                      </div>
                    </div>
                  </Link>
                )
              })}
        </div>
      </div>
    </div>
  )
}