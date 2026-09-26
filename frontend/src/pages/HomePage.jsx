import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import ScholarshipShowcase from '../components/ScholarshipShowcase'
import ScholarZoneHero from '../components/ScholarZoneHero'
import TrustFlow from '../components/TrustFlow'
import SaveCompareSteps from '../components/SaveCompareSteps'
import FeaturedStory from '../components/FeaturedStory'
import { useScholarshipDirectory } from '../hooks/useScholarshipDirectory'
import './HomePage.css'

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

const countryCategories = [
  { name: 'United Kingdom', flag: '🇬🇧', query: { country: 'United Kingdom' } },
  { name: 'United States', flag: '🇺🇸', query: { country: 'United States' } },
  { name: 'Germany', flag: '🇩🇪', query: { country: 'Germany' } },
  { name: 'Canada', flag: '🇨🇦', query: { country: 'Canada' } },
  { name: 'Australia', flag: '🇦🇺', query: { country: 'Australia' } },
  { name: 'Europe', flag: '🇪🇺', query: { country: 'Europe' } },
]

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

export default function HomePage() {
  const { scholarships, isLoading } = useScholarshipDirectory()

  const totalScholarships = scholarships.length
  const fullyFundedCount = scholarships.filter((s) => s.funding === 'Fully Funded').length
  const countriesCount = new Set(scholarships.map((s) => s.country)).size
  const verifiedCount = scholarships.filter((s) => s.verified || s.verification_status === 'active').length

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
            <strong>{isLoading ? '—' : formatNumber(totalScholarships)}+</strong>
            <span>Scholarships</span>
          </div>
          <div className="sz-trust-bar__divider" aria-hidden="true" />
          <div className="sz-trust-bar__item">
            <strong>{isLoading ? '—' : countriesCount}</strong>
            <span>Countries</span>
          </div>
          <div className="sz-trust-bar__divider" aria-hidden="true" />
          <div className="sz-trust-bar__item">
            <strong>{isLoading ? '—' : formatNumber(verifiedCount)}</strong>
            <span>Verified</span>
          </div>
          <div className="sz-trust-bar__divider" aria-hidden="true" />
          <div className="sz-trust-bar__item">
            <strong>{isLoading ? '—' : formatNumber(fullyFundedCount)}</strong>
            <span>Fully Funded</span>
          </div>
        </div>
      </ScrollReveal>

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
            <div className="sz-browse__tags">
              {countryCategories.map((cat) => (
                <Link
                  key={cat.name}
                  to={`/scholarships?country=${encodeURIComponent(cat.name)}`}
                  className="sz-tag"
                >
                  <span className="sz-tag__flag" aria-hidden="true">{cat.flag}</span>
                  {cat.name}
                </Link>
              ))}
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
      <section className="sz-section sz-section--stats" aria-label="ScholarZone statistics">
        <ScrollReveal className="sz-stats">
          <div className="sz-stats__item">
            <strong>{isLoading ? '—' : formatNumber(totalScholarships)}</strong>
            <span>Total opportunities</span>
          </div>
          <div className="sz-stats__item">
            <strong>{isLoading ? '—' : countriesCount}</strong>
            <span>Countries covered</span>
          </div>
          <div className="sz-stats__item">
            <strong>{isLoading ? '—' : formatNumber(fullyFundedCount)}</strong>
            <span>Fully funded</span>
          </div>
          <div className="sz-stats__item">
            <strong>{isLoading ? '—' : formatNumber(verifiedCount)}</strong>
            <span>Verified active</span>
          </div>
        </ScrollReveal>
      </section>

      {/* 09 — FINAL CTA */}
      <section className="sz-section sz-section--cta" aria-label="Get started">
        <ScrollReveal className="sz-cta-banner">
          <h2>Start with the directory</h2>
          <p>Browse every opportunity on ScholarZone, save the ones worth applying to, and compare them properly.</p>
          <div className="sz-cta-banner__actions">
            <Link to="/scholarships" className="sz-cta sz-cta--primary">
              Browse All Scholarships
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
