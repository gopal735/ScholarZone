import { Children, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import ScholarshipActions from '../components/ScholarshipActions'
import { fetchScholarshipById, ScholarshipApiError } from '../services/scholarshipService'
import { useScholarshipDirectory } from '../hooks/useScholarshipDirectory'
import { getDeadlineLabel, getLastVerifiedLabel, getScholarshipStatus } from '../utils/scholarshipPresentation'
import {
  buildOfficialLinks,
  buildQuickFacts,
  buildVerificationRecord,
  detailImage,
  primaryApplyLink,
  readDate,
  readList,
  readText,
  verificationLabel,
} from '../utils/scholarshipDetail'
import './ScholarshipDetailsPage.css'
import { CANONICAL_ORIGIN } from '../services/canonicalOrigin'

/* Reveal on scroll, once. Each section plays a different role so the page
   does not read as one animation repeated down the column: headings
   rise, list items stagger, the image unmasks.

   `immediate` skips the observer entirely. The hero is above the fold
   and carries the LCP image, so gating it on an intersection would mean
   the largest paint waits on a callback. */
function useReveal({ threshold, immediate = false } = {}) {
  const ref = useRef(null)
  const [isVisible, setIsVisible] = useState(immediate)

  useEffect(() => {
    if (immediate) return undefined

    const element = ref.current
    if (!element) return undefined

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true)
          observer.unobserve(element)
        }
      },
      { threshold: threshold ?? 0.12, rootMargin: '0px 0px -56px 0px' }
    )

    observer.observe(element)
    return () => observer.disconnect()
  }, [immediate, threshold])

  return [ref, isVisible]
}

function Reveal({ as: Tag = 'div', className = '', delay = 0, threshold, immediate = false, children }) {
  const [ref, isVisible] = useReveal({ threshold, immediate })
  return (
    <Tag
      ref={ref}
      className={`sz-reveal ${isVisible ? 'is-visible' : ''} ${className}`.trim()}
      style={delay ? { transitionDelay: `${delay}ms` } : undefined}
    >
      {children}
    </Tag>
  )
}

/* ── Page states ─────────────────────────────────────────────────── */

function BackToDirectory({ label = 'All scholarships' }) {
  return (
    <Link to="/scholarships" className="sz-detail__back">
      <span aria-hidden="true">&larr;</span> {label}
    </Link>
  )
}

function PageMessage({ eyebrow, title, body, action, mark = '?' }) {
  return (
    <section className="sz-detail sz-detail--message">
      <BackToDirectory />
      <div className="sz-detail__empty">
        <span className="sz-detail__empty-mark" aria-hidden="true">{mark}</span>
        <p className="sz-detail__eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p>{body}</p>
        {action}
      </div>
    </section>
  )
}

function LoadingState() {
  return (
    <section className="sz-detail" aria-busy="true" aria-label="Loading scholarship details">
      <BackToDirectory />
      <div className="sz-detail__skeleton" aria-hidden="true">
        <span className="sz-detail__skeleton-media" />
        <span className="sz-detail__skeleton-line sz-detail__skeleton-line--title" />
        <span className="sz-detail__skeleton-line" />
        <span className="sz-detail__skeleton-line sz-detail__skeleton-line--short" />
      </div>
    </section>
  )
}

/* ── Building blocks ─────────────────────────────────────────────── */

/**
 * A labelled content block. Renders nothing at all when the data behind
 * it is absent, so the page never shows an empty shell for a section the
 * provider has not supplied. `children` is filtered for falsy values
 * first, because a block whose only children are `null` is as empty as
 * one with no children at all.
 */
function DetailBlock({ id, index, eyebrow, title, children, className = '' }) {
  const hasContent = Children.toArray(children).filter(Boolean).length > 0
  if (!hasContent) return null

  return (
    <Reveal as="section" className={`sz-detail__block ${className}`.trim()} aria-labelledby={id}>
      <header className="sz-detail__block-head">
        <div>
          {eyebrow ? <p className="sz-detail__eyebrow">{eyebrow}</p> : null}
          <h2 id={id}>{title}</h2>
        </div>
        {index ? <span className="sz-detail__index" aria-hidden="true">{index}</span> : null}
      </header>
      {children}
    </Reveal>
  )
}

/** Every item in the array is rendered. No truncation, ever. */
function DetailList({ items, ordered = false, variant = 'check' }) {
  if (!items.length) return null
  const List = ordered ? 'ol' : 'ul'
  return (
    <List className={`sz-detail__list sz-detail__list--${variant}`}>
      {items.map((item, index) => (
        <li key={`${item}-${index}`} className="sz-detail__list-item">
          <span className="sz-detail__list-index" aria-hidden="true">
            {ordered ? String(index + 1).padStart(2, '0') : null}
          </span>
          <span>{item}</span>
        </li>
      ))}
    </List>
  )
}

function KeyValueGrid({ entries }) {
  if (!entries.length) return null
  return (
    <dl className="sz-detail__facts">
      {entries.map((entry) => (
        <div className="sz-detail__fact" key={entry.id}>
          <dt>{entry.label}</dt>
          <dd>{entry.value}</dd>
        </div>
      ))}
    </dl>
  )
}

/* ── Page ────────────────────────────────────────────────────────── */

export default function ScholarshipDetailsPage() {
  const { id } = useParams()
  const [scholarship, setScholarship] = useState(null)
  const [loadState, setLoadState] = useState('loading')
  const [retryVersion, setRetryVersion] = useState(0)
  const [imageFailed, setImageFailed] = useState(false)
  const requestIdRef = useRef(0)
  const { scholarships: allScholarships } = useScholarshipDirectory()
  const scholarshipId = Number(id)
  const hasValidScholarshipId = Number.isInteger(scholarshipId) && scholarshipId > 0

  useEffect(() => {
    if (!hasValidScholarshipId) return undefined

    const controller = new AbortController()
    const requestId = requestIdRef.current + 1
    requestIdRef.current = requestId
    const localScholarship = allScholarships.find((item) => item.id === scholarshipId)

    const startRequest = window.setTimeout(() => {
      setScholarship(null)
      setLoadState('loading')
      setImageFailed(false)

      fetchScholarshipById(scholarshipId, { signal: controller.signal })
        .then((response) => {
          if (controller.signal.aborted || requestId !== requestIdRef.current) return
          setScholarship(response)
          setLoadState('success')
        })
        .catch((error) => {
          if (controller.signal.aborted || requestId !== requestIdRef.current) return

          if (error instanceof ScholarshipApiError && error.status === 404) {
            setLoadState('missing')
            return
          }

          // Fallback is only ever used when the API could not be reached
          // at all. A successful API response is never overwritten.
          if (localScholarship) {
            setScholarship(localScholarship)
            setLoadState('fallback')
            return
          }

          setLoadState('error')
        })
    }, 0)

    return () => {
      window.clearTimeout(startRequest)
      controller.abort()
    }
  }, [hasValidScholarshipId, retryVersion, scholarshipId, allScholarships])

  // SEO: inject meta tags and JSON-LD structured data
  useEffect(() => {
    /* A scholarship that does not exist must not look indexable. The server
       already answers 404 for an unknown path, but a client-side navigation to
       a bad id renders inside a live page with status 200, and Google can index
       that as a thin duplicate. Saying noindex here is the honest signal in
       both cases; it is removed as soon as a real record renders. */
    document.querySelectorAll('[data-sz-seo]').forEach(el => el.remove())
    if (loadState !== 'success' || !scholarship) {
      const noindex = document.createElement('meta')
      noindex.name = 'robots'
      noindex.content = 'noindex, follow'
      noindex.setAttribute('data-sz-seo', 'true')
      document.head.appendChild(noindex)
      return () => {
        document.querySelectorAll('[data-sz-seo]').forEach(el => el.remove())
      }
    }
    if (!scholarship) return
    const baseUrl = CANONICAL_ORIGIN
    const canonicalUrl = `${baseUrl}/scholarships/${scholarship.id}`
    const imageUrl = detailImage(scholarship)?.url
    const providerName = readText(scholarship.official_source)
    const description = readText(scholarship.description)
    const eligibility = readList(scholarship.eligibility)
    const descriptionText = description || `${scholarship.title} – ${providerName || 'Scholarship'} opportunity.`
    
    // Remove existing SEO tags we may have added
    document.querySelectorAll('[data-sz-seo]').forEach(el => el.remove())
    
    const metaTags = [
      { name: 'description', content: descriptionText.slice(0, 160) },
      { property: 'og:title', content: scholarship.title },
      { property: 'og:description', content: descriptionText.slice(0, 300) },
      { property: 'og:url', content: canonicalUrl },
      { property: 'og:type', content: 'website' },
      { property: 'og:image', content: imageUrl || '' },
      { name: 'twitter:card', content: 'summary_large_image' },
      { name: 'twitter:title', content: scholarship.title },
      { name: 'twitter:description', content: descriptionText.slice(0, 300) },
      { name: 'twitter:image', content: imageUrl || '' },
      { name: 'robots', content: 'index, follow' },
    ]
    
    metaTags.forEach(meta => {
      const el = document.createElement('meta')
      Object.entries(meta).forEach(([k, v]) => { if (v) el.setAttribute(k, v) })
      el.setAttribute('data-sz-seo', 'true')
      document.head.appendChild(el)
    })
    
    // Canonical link
    const canonical = document.createElement('link')
    canonical.rel = 'canonical'
    canonical.href = canonicalUrl
    canonical.setAttribute('data-sz-seo', 'true')
    document.head.appendChild(canonical)
    
    /* Structured data.
       The previous implementation declared '@type': 'Scholarship'. That type
       is not a Google rich-result type, so it earned nothing, and it asserted
       a thing schema.org does not define for a listing page. The page is
       genuinely an editorial article about one specific award, so it is
       described as a ScholarArticle, with the issuer and the breadcrumbs
       attached as a graph. Every value below is copied from data rendered
       elsewhere on this same page; nothing is invented, and no rating,
       review, award or popularity figure is asserted. */
    const publisher = providerName || undefined
    const structuredData = {
      '@context': 'https://schema.org',
      '@graph': [
        {
          '@type': 'ScholarArticle',
          headline: scholarship.title,
          name: scholarship.title,
          description: descriptionText,
          url: canonicalUrl,
          ...(imageUrl ? { image: imageUrl } : {}),
          ...(publisher ? { publisher: { '@type': 'Organization', name: publisher } } : {}),
          ...(scholarship.degree ? { educationalLevel: scholarship.degree } : {}),
          ...(eligibility.length > 0 ? { about: eligibility.join('; ') } : {}),
          ...(scholarship.official_source_url
            ? { sameAs: [scholarship.official_source_url] }
            : {}),
          ...(scholarship.last_verified_at
            ? { dateModified: String(scholarship.last_verified_at).slice(0, 10) }
            : {}),
          isAccessibleForFree: true,
        },
        {
          '@type': 'BreadcrumbList',
          itemListElement: [
            { '@type': 'ListItem', position: 1, name: 'Home', item: `${baseUrl}/` },
            { '@type': 'ListItem', position: 2, name: 'Scholarships', item: `${baseUrl}/scholarships` },
            { '@type': 'ListItem', position: 3, name: scholarship.title, item: canonicalUrl },
          ],
        },
      ],
    }

    const script = document.createElement('script')
    script.type = 'application/ld+json'
    script.setAttribute('data-sz-seo', 'true')
    script.textContent = JSON.stringify(structuredData, null, 2)
    document.head.appendChild(script)
    
    // Cleanup
    return () => {
      document.querySelectorAll('[data-sz-seo]').forEach(el => el.remove())
    }
  }, [scholarship, loadState])

  const showTrustNote = loadState === 'fallback'
  const providerName = readText(scholarship?.official_source)

  const related = allScholarships
    .filter((item) => item.id !== scholarshipId && (
      item.country === scholarship?.country || item.degree === scholarship?.degree
    ))
    .slice(0, 3)

  if (!hasValidScholarshipId) {
    return (
      <PageMessage
        mark="?"
        eyebrow="Scholarship directory"
        title="Scholarship not found"
        body="The scholarship you requested is unavailable or the link is incorrect."
        action={<Link to="/scholarships" className="sz-detail__action">Browse scholarships <span aria-hidden="true">&rarr;</span></Link>}
      />
    )
  }

  if (loadState === 'loading') return <LoadingState />

  if (loadState === 'missing') {
    return (
      <PageMessage
        mark="?"
        eyebrow="Scholarship directory"
        title="Scholarship not found"
        body="The scholarship you requested is unavailable or the link is incorrect."
        action={<Link to="/scholarships" className="sz-detail__action">Browse scholarships <span aria-hidden="true">&rarr;</span></Link>}
      />
    )
  }

  if (loadState === 'error' || !scholarship) {
    return (
      <PageMessage
        mark="!"
        eyebrow="Connection issue"
        title="Scholarship details couldn’t be loaded"
        body="Please try again. You can also return to the directory and keep exploring."
        action={<button type="button" className="sz-detail__action" onClick={() => setRetryVersion((v) => v + 1)}>Try again</button>}
      />
    )
  }

  const isVerified = scholarship.verified ?? true
  const deadlineStatus = getScholarshipStatus(scholarship)
  const image = detailImage(scholarship)
  const applyUrl = primaryApplyLink(scholarship)
  const applyHost = (() => {
    if (!applyUrl) return null
    try { return new URL(applyUrl).hostname.replace(/^www\./, '') } catch { return null }
  })()

  const description = readText(scholarship.description)
  const quickFacts = buildQuickFacts(scholarship)
  const benefits = readList(scholarship.benefits)
  const coverage = readList(scholarship.coverage)
  const eligibilitySummary = readText(scholarship.eligibility_summary)
  const eligibility = readList(scholarship.eligibility)
  const requirements = readList(scholarship.requirements)
  const documents = readList(scholarship.documents) || readList(scholarship.required_documents)
  const applicationMethod = readList(scholarship.application_method)
  const englishRequirement = readText(scholarship.english_requirement)
const bestFit = readText(scholarship.best_fit)
  const selectionNotes = readText(scholarship.selection_notes)
  const notes = readText(scholarship.notes)
  const officialLinks = buildOfficialLinks(scholarship)
  const verification = buildVerificationRecord(scholarship)
  const verificationState = verificationLabel(scholarship.verification_status)

  return (
    <article className="sz-detail">
      <BackToDirectory />

      {showTrustNote && (
        <p className="sz-detail__notice" role="status">
          Live details are unavailable. Showing local scholarship data instead.
          <button type="button" onClick={() => setRetryVersion((v) => v + 1)}>Retry</button>
        </p>
      )}

      {/* 01 — HERO: image-led, editorial. The image is the anchor and the
          title is set against it rather than beneath a generic banner. */}
      <header className="sz-detail-hero">
        <Reveal className="sz-detail-hero__media" immediate>
          {image && !imageFailed ? (
            <img
              className="sz-detail-hero__image"
              data-fit={image.fit ?? 'cover'}
              src={image.url}
              alt={image.alt}
              loading="eager"
              decoding="async"
              onError={() => setImageFailed(true)}
            />
          ) : (
            /* The designed placeholder doubles as the failure state, so a
               dead image URL degrades to a composed surface rather than a
               broken frame leaking the alt text. */
            <div className="sz-detail-hero__placeholder" role="img" aria-label={image?.alt ?? scholarship.title}>
              <span>{scholarship.country}</span>
            </div>
          )}
          {image?.sourceType ? (
            <span className="sz-detail-hero__image-credit">{image.sourceType}</span>
          ) : null}
        </Reveal>

        <Reveal className="sz-detail-hero__content" delay={80} immediate>
          <div className="sz-detail-hero__badges">
            <span className={`sz-detail-pill sz-detail-pill--status sz-detail-pill--${deadlineStatus.className}`}>
              {deadlineStatus.label}
            </span>
            <span className={`sz-detail-pill ${isVerified ? 'sz-detail-pill--verified' : 'sz-detail-pill--unverified'}`}>
              {isVerified ? 'Verified listing' : 'Confirm with provider'}
            </span>
            {verificationState ? (
              <span className="sz-detail-pill sz-detail-pill--quiet">{verificationState}</span>
            ) : null}
          </div>

          <h1 className="sz-detail-hero__title">{scholarship.title}</h1>

          <p className="sz-detail-hero__meta">
            {[readText(scholarship.country), readText(scholarship.region), readText(scholarship.degree)]
              .filter(Boolean)
              .join(' · ')}
          </p>

          {providerName ? (
            <p className="sz-detail-hero__provider">
              Provided by <strong>{providerName}</strong>
            </p>
          ) : null}

          <div className="sz-detail-hero__actions">
            {applyUrl ? (
              <a
                href={applyUrl}
                target="_blank"
                rel="noreferrer"
                className="sz-detail-hero__apply"
              >
                Apply on the official site
                <span aria-hidden="true">↗</span>
              </a>
            ) : (
              <span className="sz-detail-hero__apply sz-detail-hero__apply--disabled" aria-disabled="true">
                No application link published yet
              </span>
            )}
            <ScholarshipActions scholarshipId={scholarship.id} variant="details" />
          </div>

          {applyHost ? (
            <p className="sz-detail-hero__host">
              You will be sent to <span>{applyHost}</span> — apply only on the official site.
            </p>
          ) : null}
        </Reveal>
      </header>

      {/* Sticky summary — the deadline and the two decisions stay reachable
          while the reader works through a long record. */}
      <Reveal className="sz-detail-summary" threshold={0.05}>
        <div className="sz-detail-summary__deadline">
          <span>Application deadline</span>
          <strong className={`sz-detail-summary__value--${deadlineStatus.className}`}>
            {getDeadlineLabel(scholarship)}
          </strong>
          {scholarship.deadline_precision === 'month' ? (
            <em>Month only — confirm the exact date with the provider</em>
          ) : null}
        </div>
        <div className="sz-detail-summary__facts">
          {quickFacts.slice(0, 4).map((fact) => (
            <div key={fact.id}>
              <span>{fact.label}</span>
              <strong>{fact.value}</strong>
            </div>
          ))}
        </div>
        {applyUrl ? (
          <a href={applyUrl} target="_blank" rel="noreferrer" className="sz-detail-summary__apply">
            Apply <span aria-hidden="true">↗</span>
          </a>
        ) : null}
      </Reveal>

      {/* 02 — QUICK FACTS */}
      <DetailBlock
        id="facts"
        index="01"
        eyebrow="At a glance"
        title="Key information"
        className="sz-detail__block--facts"
      >
        <KeyValueGrid entries={quickFacts} />
      </DetailBlock>

      {/* 03 — ABOUT */}
      <DetailBlock
        id="about"
        index="02"
        eyebrow="About"
        title="Overview"
        className="sz-detail__block--prose"
      >
        {description ? <p className="sz-detail__prose">{description}</p> : null}
        {bestFit ? (
          <aside className="sz-detail__callout">
            <span className="sz-detail__callout-label">Best fit</span>
            <p>{bestFit}</p>
          </aside>
        ) : null}
      </DetailBlock>

      {/* 04 — BENEFITS + COVERAGE. The wrapper always renders; each
          block drops itself when its list is empty, and the auto-fit
          grid collapses to one column. */}
      {(benefits.length > 0 || coverage.length > 0) && (
        <Reveal className="sz-detail__block sz-detail__block--pair" threshold={0.08}>
          <DetailBlock id="benefits" eyebrow="Funding support" title="Benefits">
            <DetailList items={benefits} />
          </DetailBlock>
          <DetailBlock id="coverage" eyebrow="What it pays for" title="Coverage">
            <DetailList items={coverage} />
          </DetailBlock>
        </Reveal>
      )}

      {/* 05 — ELIGIBILITY */}
      {(eligibilitySummary || eligibility.length > 0) && (
        <DetailBlock
          id="eligibility"
          index="03"
          eyebrow="Who can apply"
          title="Eligibility"
          className="sz-detail__block--prose"
        >
          {eligibilitySummary ? (
            <p className="sz-detail__lead">{eligibilitySummary}</p>
          ) : null}
          <DetailList items={eligibility} />
        </DetailBlock>
      )}

      {/* 06 — REQUIREMENTS + DOCUMENTS */}
      {(requirements.length > 0 || documents.length > 0) && (
        <Reveal className="sz-detail__block sz-detail__block--pair" threshold={0.08}>
          <DetailBlock id="requirements" eyebrow="Prepare your application" title="Requirements">
            <DetailList items={requirements} />
          </DetailBlock>
          <DetailBlock id="documents" eyebrow="Paperwork" title="Documents">
            <DetailList items={documents} />
          </DetailBlock>
        </Reveal>
      )}

      {/* 07 — ENGLISH REQUIREMENT */}
      <DetailBlock
        id="english"
        index="04"
        eyebrow="Language"
        title="English requirement"
        className="sz-detail__block--prose"
      >
        {englishRequirement ? <p className="sz-detail__prose">{englishRequirement}</p> : null}
      </DetailBlock>

      {/* 08 — APPLICATION METHOD */}
      <DetailBlock
        id="how-to-apply"
        index="05"
        eyebrow="How to apply"
        title="Application method"
        className="sz-detail__block--prose"
      >
        {applicationMethod.length > 0 ? (
          <DetailList items={applicationMethod} ordered />
        ) : null}
      </DetailBlock>

      {/* 09 — SELECTION NOTES + GENERAL NOTES */}
      {(selectionNotes || notes) && (
        <Reveal className="sz-detail__block sz-detail__block--pair" threshold={0.08}>
          <DetailBlock id="selection" eyebrow="Selection" title="Selection notes">
            {selectionNotes ? <p className="sz-detail__prose">{selectionNotes}</p> : null}
          </DetailBlock>
          <DetailBlock id="notes" eyebrow="Additional" title="Listing notes">
            {notes ? <p className="sz-detail__prose">{notes}</p> : null}
          </DetailBlock>
        </Reveal>
      )}

      {/* 10 — OFFICIAL SOURCE */}
      {officialLinks.length > 0 && (
        <DetailBlock
          id="official"
          index="06"
          eyebrow="Apply safely"
          title="Official sources"
          className="sz-detail__block--sources"
        >
          <ul className="sz-detail__links">
            {officialLinks.map((link) => (
              <li key={link.id}>
                <a href={link.url} target="_blank" rel="noreferrer" className="sz-detail__link">
                  <span className="sz-detail__link-body">
                    <strong>{link.label}</strong>
                    <em>{link.note}</em>
                  </span>
                  <span className="sz-detail__link-host">
                    {link.host} <span aria-hidden="true">↗</span>
                  </span>
                </a>
              </li>
            ))}
          </ul>
        </DetailBlock>
      )}

      {/* 11 — VERIFICATION RECORD */}
      {verification ? (
        <DetailBlock
          id="verification"
          index="07"
          eyebrow="Provenance"
          title="Verification record"
          className="sz-detail__block--verification"
        >
          <div className="sz-detail__verify">
            <KeyValueGrid entries={verification.entries} />
            {verification.notes ? (
              <p className="sz-detail__prose sz-detail__prose--muted">{verification.notes}</p>
            ) : null}
            {verification.image ? (
              <div className="sz-detail__verify-image">
                <span className="sz-detail__eyebrow">Image provenance</span>
                <KeyValueGrid
                  entries={[
                    { id: 'src', label: 'Image source', value: verification.image.source },
                    { id: 'kind', label: 'Asset type', value: verification.image.kind },
                    { id: 'at', label: 'Image verified', value: verification.image.verified },
                  ].filter((entry) => entry.value)}
                />
                {verification.image.sourceUrl ? (
                  <a
                    href={verification.image.sourceUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="sz-detail__text-link"
                  >
                    View the source page <span aria-hidden="true">↗</span>
                  </a>
                ) : null}
              </div>
            ) : null}
          </div>
        </DetailBlock>
      ) : null}

      {/* 12 — FINAL CTA */}
      <Reveal as="section" className="sz-detail__closing" threshold={0.1}>
        <div className="sz-detail__closing-inner">
          <p className="sz-detail__eyebrow">Next step</p>
          <h2>{applyUrl ? 'Apply through the official source' : 'Confirm the details with the provider'}</h2>
          <p>
            {applyUrl
              ? 'ScholarZone does not accept applications. Continue on the awarding body’s own site so your details reach them directly.'
              : 'No application link has been confirmed for this listing. Check the official sources above before applying.'}
          </p>
          <div className="sz-detail__closing-actions">
            {applyUrl ? (
              <a href={applyUrl} target="_blank" rel="noreferrer" className="sz-detail-hero__apply">
                Apply on the official site <span aria-hidden="true">↗</span>
              </a>
            ) : null}
            <Link to="/scholarships" className="sz-detail__text-link">
              Keep browsing <span aria-hidden="true">&rarr;</span>
            </Link>
          </div>
          <p className="sz-detail__closing-meta">
            {getLastVerifiedLabel(scholarship.last_verified_at)}
            {readDate(scholarship.updated_at) ? ` · updated ${readDate(scholarship.updated_at)}` : ''}
          </p>
        </div>
      </Reveal>

      {/* 13 — RELATED */}
      {related.length > 0 && (
        <Reveal as="section" className="sz-detail__related" threshold={0.08}>
          <header className="sz-detail__related-head">
            <div>
              <p className="sz-detail__eyebrow">Keep exploring</p>
              <h2>Related scholarships</h2>
            </div>
            <Link to="/scholarships" className="sz-detail__text-link">
              Browse all <span aria-hidden="true">&rarr;</span>
            </Link>
          </header>
          <ul className="sz-detail__related-grid">
            {related.map((item) => (
              <li key={item.id}>
                <Link to={`/scholarships/${item.id}`} className="sz-detail__related-card">
                  <span className="sz-detail__related-funding">{item.funding}</span>
                  <strong>{item.title}</strong>
                  <small>{[item.country, item.degree].filter(Boolean).join(' · ')}</small>
                </Link>
              </li>
            ))}
          </ul>
        </Reveal>
      )}
    </article>
  )
}
