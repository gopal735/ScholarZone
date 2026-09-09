import { Link } from 'react-router-dom'
import './HomeFeatures.css'

const features = [
  {
    eyebrow: 'Discover',
    title: 'Browse verified opportunities',
    description: 'Scholarships gathered from official university portals, government databases, and institutional announcements — all in one directory.',
    cta: { label: 'Explore all scholarships', to: '/scholarships' },
    visual: 'card',
  },
  {
    eyebrow: 'Filter',
    title: 'Narrow by what matters',
    description: 'Filter by country, degree level, and funding type. Compare deadlines, eligibility, and required documents in a structured view.',
    cta: { label: 'Browse by country', to: '/countries' },
    visual: 'tags',
  },
  {
    eyebrow: 'Verify',
    title: 'Act with confidence',
    description: 'Every listing carries a verification status, last-verified date, and official source link. Apply directly through the source — no outdated info, no guesswork.',
    cta: { label: 'How verification works', to: '#verification-process' },
    visual: 'trust',
  },
]

function FeatureVisual({ type }) {
  if (type === 'card') {
    return (
      <div className="home-features__visual">
        <div className="home-features__mock-card">
          <div className="home-features__mock-image" />
          <div className="home-features__mock-body">
            <div className="home-features__mock-row">
              <span className="home-features__mock-badge">Verified</span>
              <span className="home-features__mock-badge">Fully Funded</span>
            </div>
            <div className="home-features__mock-line" style={{ width: '80%' }} />
            <div className="home-features__mock-line" style={{ width: '60%' }} />
            <div className="home-features__mock-meta">
              <span>United Kingdom</span>
              <span>Masters</span>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (type === 'tags') {
    return (
      <div className="home-features__visual">
        <div className="home-features__mock-tags">
          <span className="home-features__tag">United Kingdom</span>
          <span className="home-features__tag">United States</span>
          <span className="home-features__tag">Germany</span>
          <span className="home-features__tag">Canada</span>
          <span className="home-features__tag">Australia</span>
          <span className="home-features__tag">Masters</span>
          <span className="home-features__tag">PhD</span>
          <span className="home-features__tag">Fully Funded</span>
          <span className="home-features__tag">Partial</span>
        </div>
      </div>
    )
  }

  return (
    <div className="home-features__visual">
      <div className="home-features__mock-trust">
        <div className="home-features__mock-trust-row">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="m9 12 2 2 4-4m5-4v6c0 5-3.4 8.7-8 10-4.6-1.3-8-5-8-10V6l8-3 8 3Z" />
          </svg>
          <span>Verified listing</span>
        </div>
        <div className="home-features__mock-trust-row">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
          </svg>
          <span>Official source link</span>
        </div>
        <div className="home-features__mock-trust-row">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 6v6l4 2" />
          </svg>
          <span>Last verified 2 days ago</span>
        </div>
      </div>
    </div>
  )
}

export default function HomeFeatures() {
  return (
    <section className="home-features" id="how-it-works" aria-label="How ScholarZone works">
      <div className="home-features__header">
        <span className="sz-section__eyebrow">How it works</span>
        <h2 className="sz-section__title">From search to application, streamlined.</h2>
        <p className="sz-section__description">
          Every step is designed to reduce friction and increase confidence.
        </p>
      </div>

      <div className="home-features__list">
        {features.map((feature, index) => (
          <div key={feature.eyebrow} className="home-features__item" style={{ animationDelay: `${index * 0.1}s` }}>
            <div className="home-features__text">
              <span className="home-features__eyebrow">{feature.eyebrow}</span>
              <h3 className="home-features__title">{feature.title}</h3>
              <p className="home-features__desc">{feature.description}</p>
              <Link to={feature.cta.to} className="sz-btn sz-btn--secondary">
                {feature.cta.label}
                <svg viewBox="0 0 24 24" aria-hidden="true" width="16" height="16">
                  <path d="M5 12h14M13 5l7 7-7 7" />
                </svg>
              </Link>
            </div>
            <FeatureVisual type={feature.visual} />
          </div>
        ))}
      </div>
    </section>
  )
}
