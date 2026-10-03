import { useSearchParams, Link } from 'react-router-dom'
import { useEffect } from 'react'
import { useScholarshipDirectory } from '../hooks/useScholarshipDirectory'
import ScholarshipList from '../components/ScholarshipList'
import './ScholarshipsPage.css'
import { CANONICAL_ORIGIN } from '../services/canonicalOrigin'

export default function ScholarshipsPage() {
  const [searchParams] = useSearchParams()
  const countryParam = searchParams.get('country') || undefined
  const { isUsingFallback } = useScholarshipDirectory()

  const headerTitle = countryParam || 'All Scholarships'
  const headerDescription = countryParam
    ? `Compare scholarship opportunities in ${countryParam} by funding, degree level and deadline.`
    : 'Compare key funding details, degree levels, countries and deadlines in one focused directory.'

  // SEO meta tags
  useEffect(() => {
    const baseUrl = CANONICAL_ORIGIN
    const canonicalUrl = countryParam
      ? `${baseUrl}/scholarships?country=${encodeURIComponent(countryParam)}`
      : `${baseUrl}/scholarships`
    const title = countryParam ? `${countryParam} Scholarships | ScholarZone` : 'All Scholarships | ScholarZone'
    // No catalogue size here. This page does not fetch the stats endpoint, so
    // any number written into the string would be a claim the page cannot back
    // and would drift the moment a record is added.
    //
    // No blanket verification claim either. The directory does not verify
    // everything it lists: a record whose official page could not be reached is
    // published as "Confirm with provider" precisely so it is never mistaken for
    // one that was. Writing "Every listing has a verified official source" into a
    // meta tag asserts on the catalogue's behalf what each card deliberately
    // withholds, and search engines index that sentence as a claim about us.
    const description = countryParam
      ? `Compare scholarship opportunities in ${countryParam} by funding, degree level and deadline. Each listing states whether its details were re-checked against the awarding body’s own page.`
      : 'Compare key funding details, degree levels, countries and deadlines in one focused directory. Each listing states whether its details were re-checked against the awarding body’s own official page.'

    // Remove existing SEO tags
    document.querySelectorAll('[data-sz-seo]').forEach(el => el.remove())
    
    const metaTags = [
      { name: 'description', content: description },
      { property: 'og:title', content: title },
      { property: 'og:description', content: description },
      { property: 'og:url', content: canonicalUrl },
      { property: 'og:type', content: 'website' },
      { name: 'twitter:card', content: 'summary_large_image' },
      { name: 'twitter:title', content: title },
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
    canonical.href = canonicalUrl
    canonical.setAttribute('data-sz-seo', 'true')
    document.head.appendChild(canonical)
    
    return () => {
      document.querySelectorAll('[data-sz-seo]').forEach(el => el.remove())
    }
  }, [countryParam])

  return (
    <div className="scholarships-page">
      <div className="scholarships-page__content">
        <div className="page-heading">
          <div>
            <p className="page-eyebrow">Scholarship discovery</p>
            <h1>{headerTitle}</h1>
            <p className="page-description">{headerDescription}</p>
            {/* The directory answers "what is there". Match answers "what fits me",
                from the same catalogue, so it sits beside the description as the
                other way in rather than as a promotion above the results. */}
            <p className="page-match-link">
              <Link to="/match" className="page-match-link__cta">
                Find My Matches
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M5 12h14M13 5l7 7-7 7" />
                </svg>
              </Link>
              <span>Tell ScholarZone your profile and it will check every published eligibility rule.</span>
            </p>
          </div>

          <div className="page-heading__trust">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="m9 12 2 2 4-4m5-4v6c0 5-3.4 8.7-8 10-4.6-1.3-8-5-8-10V6l8-3 8 3Z" />
            </svg>
            <p>
              <strong>Trust the details, then verify.</strong>
              <span>Always check the official provider before you apply.</span>
            </p>
          </div>
        </div>
        <ScholarshipList initialCountry={countryParam} />
        {isUsingFallback && (
          <div className="scholarships-page__fallback-notice" role="status">
            <span>⚠️ Live directory unavailable — showing local data.</span>
          </div>
        )}
      </div>
    </div>
  )
}
