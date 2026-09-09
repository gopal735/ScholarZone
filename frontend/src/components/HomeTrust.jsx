import './HomeTrust.css'

export default function HomeTrust() {
  return (
    <section className="home-trust" id="verification-process" aria-label="Verification and trust">
      <div className="home-trust__inner">
        <div className="home-trust__header">
          <span className="sz-section__eyebrow">Trust & Verification</span>
          <h2 className="sz-section__title">Built on official sources, not guesswork.</h2>
          <p className="sz-section__description">
            Every listing is tied to verifiable data. Here is what that means for you.
          </p>
        </div>
        <div className="home-trust__grid">
          <div className="home-trust__item">
            <div className="home-trust__icon">
              <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
                <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
              </svg>
            </div>
            <h3>Official sources</h3>
            <p>Listings are linked to official university portals, government databases, and institutional announcements — not random aggregators.</p>
          </div>
          <div className="home-trust__item">
            <div className="home-trust__icon">
              <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="m9 12 2 2 4-4m5-4v6c0 5-3.4 8.7-8 10-4.6-1.3-8-5-8-10V6l8-3 8 3Z" />
              </svg>
            </div>
            <h3>Verification status</h3>
            <p>Every scholarship carries a verification status and last-verified date. You always know the confidence level before you invest time.</p>
          </div>
          <div className="home-trust__item">
            <div className="home-trust__icon">
              <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 6v6l4 2" />
              </svg>
            </div>
            <h3>Freshness</h3>
            <p>Deadlines, eligibility, and funding details are re-verified on a rolling basis. Closing-soon alerts help you prioritise.</p>
          </div>
          <div className="home-trust__item">
            <div className="home-trust__icon">
              <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                <path d="M15 3h6v6" />
                <path d="M10 14 21 3" />
              </svg>
            </div>
            <h3>Direct application</h3>
            <p>Apply through official links. No middleman, no outdated third-party forms. You go straight to the source.</p>
          </div>
        </div>
      </div>
    </section>
  )
}
