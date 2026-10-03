import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import ScholarshipShowcase from '../components/ScholarshipShowcase'
import ScholarZoneHero from '../components/ScholarZoneHero'
import TrustFlow from '../components/TrustFlow'
import SaveCompareSteps from '../components/SaveCompareSteps'
import FeaturedStory from '../components/FeaturedStory'
import { useScholarshipDirectory } from '../hooks/useScholarshipDirectory'
import { useScholarshipStats } from '../hooks/useScholarshipStats'
import './HomePage.css'
import { CANONICAL_ORIGIN } from '../services/canonicalOrigin'

const discoveryCollections = [
  {
    title: 'Recently added',
    description: 'New opportunities entering the directory.',
    query: { sort: 'recently-added' },
  },
  {
    title: 'Deadline soon',
    description: 'Prioritise opportunities with the nearest recorded deadlines.',
    query: { sort: 'deadline-soon' },
  },
  {
    title: 'Fully funded opportunities',
    description: 'Explore listings marked as fully funded.',
    query: { funding: 'Fully Funded', sort: 'fully-funded' },
  },
]

// Countries are derived from the catalogue at render time, so this constant is
// gone rather than extended. It listed six countries while the catalogue holds
// forty-seven, which is how forty-one of them became unfindable from the
// homepage.
const degreeCategories = [
  { name: 'Masters', query: { degree: 'Master' } },
  { name: 'PhD', query: { degree: 'PhD' } },
  { name: 'Bachelors', query: { degree: 'Bachelor' } },
  { name: 'Postgraduate', query: { degree: 'Postgraduate' } },
]

const fundingCategories = [
  { name: 'Fully Funded', query: { funding: 'Fully Funded' } },
  { name: 'Partial', query: { funding: 'Partial' } },
  { name: 'Tuition Waiver', query: { funding: 'Tuition Waiver' } },
]

function useScrollReveal() {
  const ref = useRef(null)
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    const element = ref.current
    if (!element) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true)
          observer.unobserve(element)
        }
      },
      { threshold: 0.08, rootMargin: '0px 0px -40px 0px' }
    )

    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  return [ref, isVisible]
}

function ScrollReveal({ children, className = '', delay = 0 }) {
  const [ref, isVisible] = useScrollReveal()
  return (
    <div
      ref={ref}
      className={`sz-reveal ${isVisible ? 'is-visible' : ''} ${className}`}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </div>
  )
}

function formatNumber(value) {
  if (value >= 1000) {
    return `${(value / 1000).toFixed(value >= 10000 ? 0 : 1)}k`
  }
  return String(value)
}

/**
 * A flag for a country name, derived rather than fetched.
 *
 * Regional indicator symbols are the two-letter code point per letter
 * (U+1F1E6 + charcode), so no dependency and no image request is needed.
 *
 * Only countries whose catalogue name is exactly the ISO code resolve on their
 * own. The catalogue stores full names — "Singapore", "Slovakia" — so the common
 * cases come from a small lookup. Anything outside it returns null: the
 * catalogue also holds values like "Europe" or "Canada (host)", and showing
 * the wrong country's flag there would be worse than showing none, because an
 * applicant reads a flag as a claim.
 */
const ISO_CODES = {
  Australia: 'AU', Austria: 'AT', Belgium: 'BE', Brazil: 'BR', Canada: 'CA',
  China: 'CN', 'Czech Republic': 'CZ', Denmark: 'DK', Egypt: 'EG', Estonia: 'EE',
  Finland: 'FI', France: 'FR', Germany: 'DE', Ghana: 'GH', Greece: 'GR',
  Hungary: 'HU', Iceland: 'IS', India: 'IN', Indonesia: 'ID', Ireland: 'IE',
  Israel: 'IL', Italy: 'IT', Japan: 'JP', Jordan: 'JO', Kenya: 'KE',
  Latvia: 'LV', Lithuania: 'LT', Luxembourg: 'LU', Malaysia: 'MY',
  Malta: 'MT', Mexico: 'MX', Morocco: 'MA', Netherlands: 'NL',
  'New Zealand': 'NZ', Nigeria: 'NG', Norway: 'NO', Pakistan: 'PK',
  Philippines: 'PH', Poland: 'PL', Portugal: 'PT', Romania: 'RO',
  Russia: 'RU', Rwanda: 'RW', 'Saudi Arabia': 'SA', Senegal: 'SN',
  Serbia: 'RS', Singapore: 'SG', Slovakia: 'SK', Slovenia: 'SI',
  'South Africa': 'ZA', 'South Korea': 'KR', Spain: 'ES', Sweden: 'SE',
  Switzerland: 'CH', Taiwan: 'TW', Tanzania: 'TZ', Thailand: 'TH',
  Tunisia: 'TN', Turkey: 'TR', Uganda: 'UG', Ukraine: 'UA',
  'United Arab Emirates': 'AE', 'United Kingdom': 'GB',
  'United States': 'US', Vietnam: 'VN',
}

function flagFor(name) {
  const cleaned = (name || '').trim()
  const code = ISO_CODES[cleaned] || (/^[A-Za-z]{2}$/.test(cleaned) ? cleaned.toUpperCase() : null)
  if (!code) {
    return null
  }
  return String.fromCodePoint(
    ...[...code].map((ch) => 0x1f1e6 + ch.charCodeAt(0) - 65),
  )
}

export default function HomePage() {
  const { scholarships, isLoading, isUsingFallback } = useScholarshipDirectory()
  // The catalogue total for the search snippet. The directory is paginated,
  // so its array length is one page, not the catalogue.
  const { stats, status: statsStatus } = useScholarshipStats()

  const totalScholarships = scholarships.length
  const fullyFundedCount = scholarships.filter((s) => s.funding === 'Fully Funded').length
  const countriesCount = new Set(scholarships.map((s) => s.country)).size
  // The authoritative verification state, and nothing else.
  //
  // `s.verified ||` used to stand here. That boolean means a source was inspected
  // at some point, and it is true on every public record, so it counted every
  // record as verified and made this figure the catalogue size by another route.
  // verification_status is the current state; the boolean is history.
  const verifiedCount = scholarships.filter((s) => s.verification_status === 'active').length

  // Countries come from the catalogue, not from a list written by hand.
  //
  // The six-entry constant this replaced (UK, US, Germany, Canada, Australia,
  // "Europe") was presented to applicants as country discovery while the
  // catalogue holds 47. A hardcoded shortlist is not a shortcut, it is a
  // category the other 41 countries cannot be found under.
  const cataloguedCountries = useMemo(() => {
    const counts = new Map()
    for (const s of scholarships) {
      const name = (s.country || '').trim()
      if (!name) {
        continue
      }
      counts.set(name, (counts.get(name) || 0) + 1)
    }
    return [...counts.entries()]
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name))
  }, [scholarships])

  // The catalogue total for the search snippet, computed outside the effect
  // below: a dependency array is evaluated in the outer scope, so a value
  // declared within the effect cannot be listed as a dependency of it.
  //
  // It comes from the stats endpoint, not from scholarships.length — the
  // directory is paginated, so that array is one page and stating its length
  // as the catalogue size understates it fourfold.
  const catalogueSize =
    statsStatus === 'success' && stats.total > 0 ? stats.total : null

  // Same rule for countries: the snippet was reporting 42 from one page while
  // the bands on the same page showed 47.
  const countriesStat =
    statsStatus === 'success' && stats.countries > 0 ? stats.countries : countriesCount

  const description = catalogueSize
    ? `Discover ${catalogueSize} verified scholarships across ${countriesStat} countries. Search by country, degree, funding type and deadline. Every listing has been checked against the awarding body's own official page.`
    : 'Search verified scholarships by country, degree, funding type and deadline. Every listing has been checked against the awarding body’s own official page.'

  // SEO meta tags
  useEffect(() => {
    const baseUrl = CANONICAL_ORIGIN

    // Remove existing SEO tags
    document.querySelectorAll('[data-sz-seo]').forEach(el => el.remove())

    const metaTags = [
      { name: 'description', content: description },
      { property: 'og:title', content: 'ScholarZone – Verified Scholarship Directory' },
      { property: 'og:description', content: description },
      { property: 'og:url', content: `${baseUrl}/` },
      { property: 'og:type', content: 'website' },
      { property: 'og:image', content: `${baseUrl}/og-image.png` },
      { name: 'twitter:card', content: 'summary_large_image' },
      { name: 'twitter:title', content: 'ScholarZone – Verified Scholarship Directory' },
      { name: 'twitter:description', content: description },
      { name: 'robots', content: 'index, follow' },
    ]
    
    metaTags.forEach(meta => {
      const el = document.createElement('meta')
      Object.entries(meta).forEach(([k, v]) => { if (v) el.setAttribute(k, v) })
      el.setAttribute('data-sz-seo', 'true')
      document.head.appendChild(el)
    })
    
    const canonical = document.createElement('link')
    canonical.rel = 'canonical'
    canonical.href = `${baseUrl}/`
    canonical.setAttribute('data-sz-seo', 'true')
    document.head.appendChild(canonical)
    
    // JSON-LD structured data for WebSite
    const script = document.createElement('script')
    script.type = 'application/ld+json'
    script.setAttribute('data-sz-seo', 'true')
    script.textContent = JSON.stringify({
      '@context': 'https://schema.org',
      '@type': 'WebSite',
      name: 'ScholarZone',
      url: `${baseUrl}/`,
      potentialAction: {
        '@type': 'SearchAction',
        target: {
          '@type': 'EntryPoint',
          urlTemplate: `${baseUrl}/scholarships?search={search_term_string}`
        },
        'query-input': 'required name=search_term_string'
      }
    }, null, 2)
    script.setAttribute('data-sz-seo', 'true')
    document.head.appendChild(script)
    
    return () => {
      document.querySelectorAll('[data-sz-seo]').forEach(el => el.remove())
    }
    // The description now carries the live catalogue size, so it has to be
    // rebuilt when the count arrives rather than only on mount — otherwise the
    // search snippet keeps whatever number was there on first paint.
  }, [catalogueSize, countriesStat])

  /* The story needs a stable set to step through. Taking the first few
     in directory order keeps it deterministic between renders, and the
     count is clamped again inside the component in case the directory
     shrinks underneath it. */
  const featuredItems = useMemo(() => scholarships.slice(0, 5), [scholarships])

  return (
    <div className="sz-home">
      {/* HERO SECTION */}
      <ScholarZoneHero />

      {/* TRUST BAR */}
      <ScrollReveal className="sz-trust-bar">
        <div className="sz-trust-bar__inner">
          <div className="sz-trust-bar__item">
            {/* The live catalogue total from the stats endpoint, not
                totalScholarships — the directory is paginated, so that array is
                one page and rendered as "100+". The "+" is gone too: a live
                count is not a growth claim, and 100+ understated the catalogue
                fourfold while claiming to exceed it. */}
            <strong>
              {statsStatus === 'success' && stats.total > 0
                ? formatNumber(stats.total)
                : isLoading
                  ? '—'
                  : formatNumber(totalScholarships)}
            </strong>
            <span>Scholarships</span>
          </div>
          <div className="sz-trust-bar__divider" aria-hidden="true" />
          <div className="sz-trust-bar__item">
            <strong>
              {statsStatus === 'success' && stats.countries > 0
                ? stats.countries
                : isLoading
                  ? '—'
                  : countriesCount}
            </strong>
            <span>Countries</span>
          </div>
          <div className="sz-trust-bar__divider" aria-hidden="true" />
          {/* verified and fully-funded counts also come from the stats endpoint.
              Filtering the directory array counted one page, which is why this
              read 100 verified and 21 fully funded against a catalogue of
              around four hundred. */}
          <div className="sz-trust-bar__item">
            <strong>
              {statsStatus === 'success' && stats.verified_active > 0
                ? formatNumber(stats.verified_active)
                : isLoading
                  ? '—'
                  : formatNumber(verifiedCount)}
            </strong>
            <span>Verified</span>
          </div>
          <div className="sz-trust-bar__divider" aria-hidden="true" />
          <div className="sz-trust-bar__item">
            <strong>
              {statsStatus === 'success' && stats.fully_funded > 0
                ? formatNumber(stats.fully_funded)
                : isLoading
                  ? '—'
                  : formatNumber(fullyFundedCount)}
            </strong>
            <span>Fully Funded</span>
          </div>
        </div>
      </ScrollReveal>

      {isUsingFallback && (
        <div className="sz-home__fallback-notice" role="status">
          <span>⚠️ Live directory unavailable — showing local data.</span>
        </div>
      )}

      {/* 03 — TRUST: the verification model, as a connected sequence */}
      <section className="sz-section sz-section--verify" aria-label="How ScholarZone verifies listings">
        <ScrollReveal className="sz-section__header">
          <span className="sz-section__eyebrow">Verification</span>
          <h2 className="sz-section__title">Every listing has a provenance</h2>
          <p className="sz-section__description">
            A scholarship page can look authoritative and still be out of date. ScholarZone records
            where each listing came from and publishes a verification status alongside it, so you can
            tell a confirmed opportunity from one that needs a second look.
          </p>
        </ScrollReveal>

        <ScrollReveal className="sz-flow-wrap">
          <TrustFlow />
        </ScrollReveal>
      </section>

      {/* 04 — HOW SCHOLARZONE WORKS: the editorial feature band */}
      <section className="sz-section sz-section--why" aria-label="Why ScholarZone">
        <ScrollReveal className="sz-section__header sz-section__header--left">
          <span className="sz-section__eyebrow">Why ScholarZone</span>
          <h2 className="sz-section__title">Built for the decision, not the scroll</h2>
        </ScrollReveal>

        <div className="sz-why-grid">
          <ScrollReveal className="sz-why-card" delay={0}>
            <div className="sz-why-card__icon" aria-hidden="true">
              <svg viewBox="0 0 24 24">
                <path d="m9 12 2 2 4-4m5-4v6c0 5-3.4 8.7-8 10-4.6-1.3-8-5-8-10V6l8-3 8 3Z" />
              </svg>
            </div>
            <h3>Verified listings</h3>
            <p>Each scholarship is checked against official sources. Status is published on the listing so you know what you are working with.</p>
          </ScrollReveal>

          <ScrollReveal className="sz-why-card" delay={100}>
            <div className="sz-why-card__icon" aria-hidden="true">
              <svg viewBox="0 0 24 24">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 6v6l4 2" />
              </svg>
            </div>
            <h3>Tracked deadlines</h3>
            <p>Opening and closing dates are recorded and updated. Closing-soon status surfaces what needs attention first.</p>
          </ScrollReveal>

          <ScrollReveal className="sz-why-card" delay={200}>
            <div className="sz-why-card__icon" aria-hidden="true">
              <svg viewBox="0 0 24 24">
                <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z" />
                <circle cx="12" cy="10" r="3" />
              </svg>
            </div>
            <h3>Global coverage</h3>
            <p>Opportunities across dozens of countries and every degree level — from undergraduate bursaries to doctoral funding.</p>
          </ScrollReveal>

          <ScrollReveal className="sz-why-card" delay={300}>
            <div className="sz-why-card__icon" aria-hidden="true">
              <svg viewBox="0 0 24 24">
                <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                <path d="M14 2v6h6M16 13H8M16 17H8M10 9H8" />
              </svg>
            </div>
            <h3>Structured detail</h3>
            <p>Funding, eligibility, required documents and the application link — in one structured view you can act on.</p>
          </ScrollReveal>
        </div>
      </section>

      {/* 02 — FEATURED STORY: one active opportunity centre-stage with
          its neighbours cropping at the page edges. */}
      <section className="sz-section sz-section--story" aria-label="Featured opportunity">
        <ScrollReveal className="sz-section__header">
          <span className="sz-section__eyebrow">Featured</span>
          <h2 className="sz-section__title">Worth a closer look</h2>
          <p className="sz-section__description">
            Step through a few of the opportunities currently in the directory. Each one links
            straight to its full listing.
          </p>
        </ScrollReveal>

        <ScrollReveal className="sz-story-wrap">
          <FeaturedStory items={featuredItems} label="Featured scholarships" />
        </ScrollReveal>
      </section>

      {/* 03 — DISCOVERY COLLECTIONS */}
      <section className="sz-section sz-section--featured" aria-label="Featured scholarships">
        <ScrollReveal className="sz-section__header">
          <span className="sz-section__eyebrow">Recently added</span>
          <h2 className="sz-section__title">New &amp; closing soon</h2>
          <p className="sz-section__description">
            New opportunities and those with approaching deadlines — updated from official sources.
          </p>
        </ScrollReveal>

        <div className="sz-showcase-grid">
          {discoveryCollections.map((collection) => (
            <ScholarshipShowcase key={collection.title} {...collection} />
          ))}
        </div>
      </section>

      {/* 06 — COUNTRIES / GLOBAL REACH: browse by category */}
      <section className="sz-section sz-section--browse" aria-label="Browse by category">
        <ScrollReveal className="sz-section__header">
          <span className="sz-section__eyebrow">Global reach</span>
          <h2 className="sz-section__title">Find by what matters to you</h2>
        </ScrollReveal>

        <div className="sz-browse">
          <ScrollReveal className="sz-browse__group" delay={0}>
            <h3 className="sz-browse__label">Country</h3>
            <div className="sz-browse__tags sz-browse__tags--countries">
              {cataloguedCountries.slice(0, 18).map((cat) => (
                <Link
                  key={cat.name}
                  to={`/scholarships?country=${encodeURIComponent(cat.name)}`}
                  className="sz-tag"
                >
                  <span className="sz-tag__flag" aria-hidden="true">{flagFor(cat.name)}</span>
                  {cat.name}
                  <span className="sz-tag__count">{cat.count}</span>
                </Link>
              ))}
              {cataloguedCountries.length > 18 && (
                <Link to="/countries" className="sz-tag sz-tag--all">
                  View all {cataloguedCountries.length} countries
                </Link>
              )}
            </div>
          </ScrollReveal>

          <ScrollReveal className="sz-browse__group" delay={100}>
            <h3 className="sz-browse__label">Degree</h3>
            <div className="sz-browse__tags">
              {degreeCategories.map((cat) => (
                <Link
                  key={cat.name}
                  to={`/scholarships?degree=${encodeURIComponent(cat.name)}`}
                  className="sz-tag"
                >
                  {cat.name}
                </Link>
              ))}
            </div>
          </ScrollReveal>

          <ScrollReveal className="sz-browse__group" delay={200}>
            <h3 className="sz-browse__label">Funding</h3>
            <div className="sz-browse__tags">
              {fundingCategories.map((cat) => (
                <Link
                  key={cat.name}
                  to={`/scholarships?funding=${encodeURIComponent(cat.name)}`}
                  className="sz-tag"
                >
                  {cat.name}
                </Link>
              ))}
            </div>
          </ScrollReveal>
        </div>
      </section>

      {/* 07 — SAVE + COMPARE */}
      <section className="sz-section sz-section--decide" aria-label="Save and compare scholarships">
        <ScrollReveal className="sz-section__header">
          <span className="sz-section__eyebrow">Decide</span>
          <h2 className="sz-section__title">Narrow it down, then commit</h2>
          <p className="sz-section__description">
            Scholarship search is only useful if it helps you choose. Save what looks serious, put
            the shortlist side by side, and apply directly with the awarding body.
          </p>
        </ScrollReveal>

        <ScrollReveal className="sz-decision-wrap">
          <SaveCompareSteps />
        </ScrollReveal>
      </section>

      {/* 08 — STATISTICS: the figures the directory actually holds */}
      {/* Every tile here reads the same authoritative stats endpoint as the trust
          bar above, and falls back to the same values. Two of them used to read
          the paginated directory array instead, which made this section publish
          "100 Total opportunities" and "100 Verified active" directly beneath a
          trust bar reading 394 and 372 — two different numbers for the same claim
          on one page, both of them an artefact of a page size. */}
      <section className="sz-section sz-section--stats" aria-label="ScholarZone statistics">
        <ScrollReveal className="sz-stats">
          <div className="sz-stats__item">
            <strong>
              {statsStatus === 'success' && stats.total > 0
                ? formatNumber(stats.total)
                : isLoading
                  ? '—'
                  : formatNumber(totalScholarships)}
            </strong>
            <span>Total opportunities</span>
          </div>
          <div className="sz-stats__item">
            <strong>
              {statsStatus === 'success' && stats.countries > 0
                ? stats.countries
                : isLoading
                  ? '—'
                  : countriesCount}
            </strong>
            <span>Countries covered</span>
          </div>
          <div className="sz-stats__item">
            <strong>
              {statsStatus === 'success' && stats.fully_funded > 0
                ? formatNumber(stats.fully_funded)
                : isLoading
                  ? '—'
                  : formatNumber(fullyFundedCount)}
            </strong>
            <span>Fully funded</span>
          </div>
          <div className="sz-stats__item">
            <strong>
              {statsStatus === 'success' && stats.verified_active > 0
                ? formatNumber(stats.verified_active)
                : isLoading
                  ? '—'
                  : formatNumber(verifiedCount)}
            </strong>
            <span>Verified active</span>
          </div>
        </ScrollReveal>
      </section>

      {/* 09 — FINAL CTA */}
      <section className="sz-section sz-section--cta" aria-label="Get started">
        <ScrollReveal className="sz-cta-banner">
          <h2>Start with the directory</h2>
          <p>Browse every opportunity on ScholarZone, save the ones worth applying to, and compare them properly.</p>
          {/* The two paths a visitor actually has. Browsing lists everything;
              Match narrows the same catalogue against one person's profile, so
              the sentence says which is which rather than promoting either. It
              claims no outcome — Match reports eligibility and fit from published
              rules, it does not promise a scholarship. */}
          <p>
            Already know what you are looking for? Match checks your profile against every
            published eligibility rule and ranks what you can actually apply for.
          </p>
          <div className="sz-cta-banner__actions">
            <Link to="/scholarships" className="sz-cta sz-cta--primary">
              Browse All Scholarships
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M5 12h14M13 5l7 7-7 7" />
              </svg>
            </Link>
            <Link to="/match" className="sz-cta sz-cta--secondary">
              Find My Matches
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M5 12h14M13 5l7 7-7 7" />
              </svg>
            </Link>
            <Link to="/countries" className="sz-cta sz-cta--ghost">
              Explore by Country
            </Link>
          </div>
        </ScrollReveal>
      </section>
    </div>
  )
}
