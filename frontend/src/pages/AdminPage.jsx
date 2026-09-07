import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import '../styles/glass.css'
import './AdminPage.css'
import { fetchReviewQueue, approveReview, rejectReview } from '../services/adminImageReviewService'

const API = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

function useCountUp(value, duration = 900) {
  const [display, setDisplay] = useState(0)
  useEffect(() => {
    const end = Number(value) || 0
    if (end === 0) return
    const startTime = performance.now()
    let raf
    const step = (now) => {
      const elapsed = now - startTime
      const progress = Math.min(elapsed / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      setDisplay(Math.floor(eased * end))
      if (progress < 1) raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [value, duration])
  return display
}

function useTilt(intensity = 8) {
  const ref = useRef(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const onMove = (e) => {
      const rect = el.getBoundingClientRect()
      const x = e.clientX - rect.left
      const y = e.clientY - rect.top
      const cx = rect.width / 2
      const cy = rect.height / 2
      const rotateX = ((y - cy) / cy) * -intensity
      const rotateY = ((x - cx) / cx) * intensity
      el.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale3d(1.008,1.008,1.008)`
    }
    const onLeave = () => {
      el.style.transform = 'perspective(1000px) rotateX(0) rotateY(0) scale3d(1,1,1)'
      el.style.transition = 'transform 0.6s cubic-bezier(0.34, 1.56, 0.64, 1)'
    }
    const onEnter = () => {
      el.style.transition = 'transform 0.15s ease-out'
    }
    el.addEventListener('mousemove', onMove)
    el.addEventListener('mouseleave', onLeave)
    el.addEventListener('mouseenter', onEnter)
    return () => {
      el.removeEventListener('mousemove', onMove)
      el.removeEventListener('mouseleave', onLeave)
      el.removeEventListener('mouseenter', onEnter)
    }
  }, [intensity])
  return ref
}

function StatOrb({ color, index }) {
  const colorMap = {
    blue: { accent: '#0a84ff', glow: 'rgba(10,132,255,0.30)', bg: 'rgba(10,132,255,0.10)' },
    orange: { accent: '#ff9f0a', glow: 'rgba(255,159,10,0.30)', bg: 'rgba(255,159,10,0.10)' },
    green: { accent: '#30d158', glow: 'rgba(48,209,88,0.30)', bg: 'rgba(48,209,88,0.10)' },
  }
  const theme = colorMap[color] || colorMap.blue
  return (
    <div
      className="stat-orb"
      style={{
        '--orb-accent': theme.accent,
        '--orb-glow': theme.glow,
        '--orb-bg': theme.bg,
        animationDelay: `${index * 100}ms`,
      }}
    />
  )
}

function MetricCard({ label, value, color, index }) {
  const display = useCountUp(value)
  const tiltRef = useTilt(5)
  const colorMap = {
    blue: { accent: '#0a84ff', glow: 'rgba(10,132,255,0.35)', bg: 'rgba(10,132,255,0.10)' },
    orange: { accent: '#ff9f0a', glow: 'rgba(255,159,10,0.35)', bg: 'rgba(255,159,10,0.10)' },
    green: { accent: '#30d158', glow: 'rgba(48,209,88,0.35)', bg: 'rgba(48,209,88,0.10)' },
  }
  const theme = colorMap[color] || colorMap.blue
  return (
    <div
      ref={tiltRef}
      className="metric-tile"
      style={{
        '--accent': theme.accent,
        '--accent-glow': theme.glow,
        '--accent-bg': theme.bg,
        animationDelay: `${index * 80}ms`,
      }}
    >
      <StatOrb color={color} index={index} />
      <div className="metric-card-inner">
        <span className="metric-value">{display}</span>
        <span className="metric-label">{label}</span>
      </div>
    </div>
  )
}

function FeaturedScholarship({ scholarship, onVerify, onFlag }) {
  const [loading, setLoading] = useState(false)
  const tiltRef = useTilt(4)
  const status = scholarship.verification_status || 'active'
  const lastVerified = scholarship.last_verified_at
    ? new Date(scholarship.last_verified_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
    : 'Never'
  const nextDue = scholarship.next_verification_due
    ? new Date(scholarship.next_verification_due).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
    : '—'
  const statusConfig = {
    active: { label: 'Active', cls: 'status-pill--active', dot: 'status-dot--active' },
    needs_review: { label: 'Needs Review', cls: 'status-pill--review', dot: 'status-dot--review' },
    inactive: { label: 'Inactive', cls: 'status-pill--inactive', dot: 'status-dot--inactive' },
  }
  const st = statusConfig[status] || statusConfig.active

  async function handle(action) {
    setLoading(true)
    await action()
    setLoading(false)
  }

  return (
    <div
      ref={tiltRef}
      className={`featured-hero ${status === 'needs_review' ? 'featured-hero--alert' : ''}`}
      style={{ animationDelay: '0.12s' }}
    >
      <div className="featured-hero-glow" />
      <div className="featured-hero-inner">
        <div className="featured-header">
          <div className="featured-badge">
            <span className={`status-dot ${st.dot}`} />
            <span className={`status-pill ${st.cls}`}>{st.label}</span>
          </div>
          <span className="featured-id">#{scholarship.id}</span>
        </div>
        <h2 className="featured-title">{scholarship.title}</h2>
        <p className="featured-country">{scholarship.country}</p>
        <div className="featured-meta-row">
          <div className="featured-meta-item">
            <span className="meta-label">Last Verified</span>
            <span className="meta-value">{lastVerified}</span>
          </div>
          <div className="featured-meta-item">
            <span className="meta-label">Next Due</span>
            <span className="meta-value">{nextDue}</span>
          </div>
          <div className="featured-meta-item">
            <span className="meta-label">Source</span>
            <a className="meta-link" href={scholarship.official_source} target="_blank" rel="noreferrer">Official Source</a>
          </div>
        </div>
        <div className="featured-actions">
          <button
            className={`glass-btn glass-btn--active ${loading ? 'btn-loading' : ''}`}
            disabled={loading}
            onClick={() => handle(() => onVerify(scholarship.id))}
          >
            {loading ? <span className="btn-spinner" /> : <span className="btn-icon">✓</span>}
            <span className="btn-text">{loading ? '' : 'Verify'}</span>
          </button>
          <button
            className={`glass-btn glass-btn--review ${loading ? 'btn-loading' : ''}`}
            disabled={loading}
            onClick={() => handle(() => onFlag(scholarship.id))}
          >
            {loading ? <span className="btn-spinner" /> : <span className="btn-icon">⚑</span>}
            <span className="btn-text">{loading ? '' : 'Flag'}</span>
          </button>
        </div>
      </div>
    </div>
  )
}

function ScholarshipCard({ scholarship, onVerify, onFlag, index }) {
  const [loading, setLoading] = useState(false)
  const tiltRef = useTilt(4)
  const status = scholarship.verification_status || 'active'
  const statusConfig = {
    active: { label: 'Active', cls: 'status-pill--active', dot: 'status-dot--active' },
    needs_review: { label: 'Needs Review', cls: 'status-pill--review', dot: 'status-dot--review' },
    inactive: { label: 'Inactive', cls: 'status-pill--inactive', dot: 'status-dot--inactive' },
  }
  const st = statusConfig[status] || statusConfig.active

  async function handle(action) {
    setLoading(true)
    await action()
    setLoading(false)
  }

  return (
    <div
      ref={tiltRef}
      className={`scholarship-card ${status === 'needs_review' ? 'scholarship-card--alert' : ''}`}
      style={{ animationDelay: `${0.2 + index * 40}ms` }}
    >
      <div className="scholarship-card-header">
        <span className={`status-pill ${st.cls}`}>
          <span className={`status-dot ${st.dot}`} />
          {st.label}
        </span>
        <span className="scholarship-card-id">#{scholarship.id}</span>
      </div>
      <h3 className="scholarship-card-title">{scholarship.title}</h3>
      <p className="scholarship-card-country">{scholarship.country}</p>
      <div className="scholarship-card-actions">
        <button
          className={`glass-btn glass-btn--sm glass-btn--active ${loading ? 'btn-loading' : ''}`}
          disabled={loading}
          onClick={() => handle(() => onVerify(scholarship.id))}
        >
          {loading ? <span className="btn-spinner" /> : <span className="btn-icon">✓</span>}
          <span className="btn-text">{loading ? '' : 'Verify'}</span>
        </button>
        <button
          className={`glass-btn glass-btn--sm glass-btn--review ${loading ? 'btn-loading' : ''}`}
          disabled={loading}
          onClick={() => handle(() => onFlag(scholarship.id))}
        >
          {loading ? <span className="btn-spinner" /> : <span className="btn-icon">⚑</span>}
          <span className="btn-text">{loading ? '' : 'Flag'}</span>
        </button>
      </div>
    </div>
  )
}

function NeedsReviewPanel({ scholarships, onVerify, onFlag }) {
  const [loading, setLoading] = useState(false)
  const tiltRef = useTilt(3)
  async function handle(action) {
    setLoading(true)
    await action()
    setLoading(false)
  }

  return (
    <div ref={tiltRef} className="priority-panel" style={{ animationDelay: '0.22s' }}>
      <div className="priority-panel-inner">
        <div className="priority-panel-header">
          <div className="priority-panel-title-group">
            <span className="priority-panel-icon" aria-hidden="true">⚡</span>
            <h3 className="priority-panel-title">Needs Review</h3>
          </div>
          <span className="priority-panel-count">{scholarships.length}</span>
        </div>
        <div className="priority-panel-list">
          {scholarships.slice(0, 5).map((s, i) => (
            <div key={s.id} className="priority-panel-item" style={{ animationDelay: `${0.3 + i * 60}ms` }}>
              <div className="priority-panel-item-info">
                <span className="priority-panel-item-title">{s.title}</span>
                <span className="priority-panel-item-country">{s.country}</span>
              </div>
              <div className="priority-panel-item-actions">
                <button
                  className={`glass-btn glass-btn--sm glass-btn--active ${loading ? 'btn-loading' : ''}`}
                  disabled={loading}
                  onClick={() => handle(() => onVerify(s.id))}
                >
                  {loading ? <span className="btn-spinner" /> : <span className="btn-icon">✓</span>}
                  <span className="btn-text">{loading ? '' : 'Verify'}</span>
                </button>
                <button
                  className={`glass-btn glass-btn--sm glass-btn--review ${loading ? 'btn-loading' : ''}`}
                  disabled={loading}
                  onClick={() => handle(() => onFlag(s.id))}
                >
                  {loading ? <span className="btn-spinner" /> : <span className="btn-icon">⚑</span>}
                  <span className="btn-text">{loading ? '' : 'Flag'}</span>
                </button>
              </div>
            </div>
          ))}
          {scholarships.length === 0 && (
            <div className="priority-panel-empty">
              <p>All caught up — no items need review</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function ReviewCard({ review, index, onApprove, onReject, onOpenSource, actionLoading }) {
  const tiltRef = useTilt(4)

  const imageSrc = review.image_url
  const hasImage = Boolean(imageSrc)

  return (
    <div
      ref={tiltRef}
      className="review-card"
      style={{ animationDelay: `${index * 60}ms` }}
    >
      <div className="review-card-inner">
        <div className="review-card-header">
          <div className="review-card-title-group">
            <span className="review-card-id">#{review.scholarship_id}</span>
            <h3 className="review-card-title">{review.scholarship_title || 'Untitled Scholarship'}</h3>
          </div>
          <span className={`status-pill status-pill--review`}>
            <span className="status-dot status-dot--review" />
            {review.confidence || 'MEDIUM'}
          </span>
        </div>

        <div className="review-card-body">
          {hasImage && (
            <div className="review-card-image">
              <img src={imageSrc} alt={review.scholarship_title || 'Review candidate'} />
            </div>
          )}
          <div className="review-card-meta">
            <div className="review-meta-row">
              <span className="review-meta-label">Image Kind</span>
              <span className="review-meta-value">{review.image_kind}</span>
            </div>
            <div className="review-meta-row">
              <span className="review-meta-label">Source Type</span>
              <span className="review-meta-value">{review.source_type || '—'}</span>
            </div>
            <div className="review-meta-row">
              <span className="review-meta-label">Reason</span>
              <span className="review-meta-value">{review.reason_for_review || '—'}</span>
            </div>
            {review.relevance_evidence && (
              <div className="review-meta-row">
                <span className="review-meta-label">Relevance</span>
                <span className="review-meta-value review-meta-value--multiline">{review.relevance_evidence}</span>
              </div>
            )}
            <div className="review-meta-row">
              <span className="review-meta-label">Licensing</span>
              <span className="review-meta-value">{review.licensing_status || 'Unknown'}</span>
            </div>
            {review.licensing_evidence && (
              <div className="review-meta-row">
                <span className="review-meta-label">License Evidence</span>
                <span className="review-meta-value review-meta-value--multiline">{review.licensing_evidence}</span>
              </div>
            )}
            {review.source_page && (
              <div className="review-meta-row">
                <span className="review-meta-label">Source Page</span>
                <a className="review-meta-link" href={review.source_page} target="_blank" rel="noreferrer">
                  {review.source_page}
                </a>
              </div>
            )}
          </div>
        </div>

        <div className="review-card-actions">
          <button
            className={`glass-btn glass-btn--active ${actionLoading ? 'btn-loading' : ''}`}
            disabled={actionLoading}
            onClick={onApprove}
          >
            {actionLoading ? <span className="btn-spinner" /> : <span className="btn-icon">✓</span>}
            <span className="btn-text">{actionLoading ? '' : 'Approve'}</span>
          </button>
          <button
            className={`glass-btn glass-btn--inactive ${actionLoading ? 'btn-loading' : ''}`}
            disabled={actionLoading}
            onClick={onReject}
          >
            {actionLoading ? <span className="btn-spinner" /> : <span className="btn-icon">✕</span>}
            <span className="btn-text">{actionLoading ? '' : 'Reject'}</span>
          </button>
          {review.source_page && (
            <button
              className="glass-btn glass-btn--ghost"
              onClick={onOpenSource}
            >
              <span className="btn-icon">↗</span>
              <span className="btn-text">Open Source</span>
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

function Orb({ style, size, blur }) {
  return <div className="ambient-orb" style={{ ...style, width: size, height: size, filter: `blur(${blur})` }} />
}

export default function AdminPage() {
  const [scholarships, setScholarships] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('all')
  const [loadedOnce, setLoadedOnce] = useState(false)
  const [adminSecret, setAdminSecret] = useState('')
  const [activeTab, setActiveTab] = useState('scholarships')
  const [reviewQueue, setReviewQueue] = useState([])
  const [reviewLoading, setReviewLoading] = useState(false)
  const [reviewError, setReviewError] = useState(null)
  const [reviewActionLoading, setReviewActionLoading] = useState({})
  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API}/scholarships?limit=100`)
      const data = await res.json()
      setScholarships(data.items || [])
      setLoadedOnce(true)
    } catch {
      setError('Failed to load scholarships.')
    } finally {
      setLoading(false)
    }
  }, [])

  const didInit = useRef(false)
  useEffect(() => {
    if (!didInit.current) {
      didInit.current = true
      load()
    }
  }, [load])

  async function verify(id) {
    await fetch(`${API}/scholarships/${id}/verify`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        verification_status: 'active',
        verified_by: 'admin',
        verification_notes: 'Verified via admin dashboard',
      }),
    })
    load()
  }

  async function flag(id) {
    await fetch(`${API}/scholarships/${id}/verify`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        verification_status: 'needs_review',
        verified_by: 'admin',
        verification_notes: 'Flagged for review via admin dashboard',
      }),
    })
    load()
  }

  async function loadReviewQueue() {
    if (!adminSecret) return
    setReviewLoading(true)
    setReviewError(null)
    try {
      const data = await fetchReviewQueue(adminSecret)
      setReviewQueue(Array.isArray(data) ? data : [])
    } catch (err) {
      setReviewError(err.message)
      setReviewQueue([])
    } finally {
      setReviewLoading(false)
    }
  }

  function switchTab(tab) {
    setActiveTab(tab)
    if (tab === 'image-review' && adminSecret) {
      loadReviewQueue()
    }
  }

  async function handleApprove(reviewId) {
    setReviewActionLoading(prev => ({ ...prev, [reviewId]: true }))
    try {
      await approveReview(reviewId, adminSecret, '')
      await loadReviewQueue()
    } catch (err) {
      setReviewError(err.message)
    } finally {
      setReviewActionLoading(prev => ({ ...prev, [reviewId]: false }))
    }
  }

  async function handleReject(reviewId) {
    setReviewActionLoading(prev => ({ ...prev, [reviewId]: true }))
    try {
      await rejectReview(reviewId, adminSecret, '')
      await loadReviewQueue()
    } catch (err) {
      setReviewError(err.message)
    } finally {
      setReviewActionLoading(prev => ({ ...prev, [reviewId]: false }))
    }
  }

  const today = new Date().toISOString().slice(0, 10)
  const verifiedToday = useMemo(() => scholarships.filter(s => s.last_verified_at === today).length, [scholarships, today])
  const reviewCount = useMemo(() => scholarships.filter(s => s.verification_status === 'needs_review').length, [scholarships])

  const featured = useMemo(() => {
    if (scholarships.length === 0) return null
    const review = scholarships.find(s => s.verification_status === 'needs_review')
    if (review) return review
    return scholarships[0]
  }, [scholarships])

  const gridItems = useMemo(() => {
    const q = search.toLowerCase()
    const base = scholarships.filter(s => {
      const matchSearch = !q || s.title.toLowerCase().includes(q) || s.country.toLowerCase().includes(q)
      const matchFilter =
        filter === 'all' ? true :
        filter === 'review' ? s.verification_status === 'needs_review' :
        s.verification_status === filter
      return matchSearch && matchFilter
    })
    const exclude = featured?.id
    return exclude ? base.filter(s => s.id !== exclude) : base
  }, [scholarships, search, filter, featured])

  return (
    <div className="admin-page">
      <div className="ambient-bg" aria-hidden="true">
        <Orb size="900px" blur="180px" style={{ top: '-18%', left: '-12%', background: 'rgba(196,164,74,0.08)', animation: 'orbFloat1 26s ease-in-out infinite' }} />
        <Orb size="700px" blur="200px" style={{ top: '40%', right: '-14%', background: 'rgba(27,42,74,0.10)', animation: 'orbFloat2 30s ease-in-out infinite' }} />
        <Orb size="500px" blur="160px" style={{ bottom: '-10%', left: '20%', background: 'rgba(255,255,255,0.02)', animation: 'orbFloat3 22s ease-in-out infinite reverse' }} />
      </div>

      <div className="admin-inner">
        <nav className="admin-nav glass-panel">
          <div className="admin-nav-inner">
            <div className="admin-brand">
              <span className="admin-brand-dot" aria-hidden="true" />
              <span className="admin-brand-text">ScholarZone</span>
            </div>
            <div className="admin-nav-meta">
              <span className="nav-stat">{scholarships.length} scholarships</span>
              <div className="admin-tabs">
                <button
                  className={`admin-tab ${activeTab === 'scholarships' ? 'admin-tab--active' : ''}`}
                  onClick={() => switchTab('scholarships')}
                >
                  Scholarships
                </button>
                <button
                  className={`admin-tab ${activeTab === 'image-review' ? 'admin-tab--active' : ''}`}
                  onClick={() => switchTab('image-review')}
                >
                  Image Review
                  {reviewQueue.length > 0 && <span className="admin-tab-badge">{reviewQueue.length}</span>}
                </button>
              </div>
              <input
                type="password"
                className="admin-secret-input"
                placeholder="Admin secret"
                value={adminSecret}
                onChange={e => setAdminSecret(e.target.value)}
              />
              <button className="glass-btn glass-btn--ghost glass-btn--sm" onClick={load}>
                <span className="btn-icon">↺</span>
                <span className="btn-text">Refresh</span>
              </button>
            </div>
          </div>
        </nav>

        <header className="admin-header">
          <div className="header-text">
            <div className="header-eyebrow">Verification Control</div>
            <h1 className="admin-title">Scholarship<br />Intelligence</h1>
            <p className="admin-sub">Review, verify and manage scholarship listings</p>
          </div>
        </header>

        <div className="hero-layout">
          <div className="hero-main" style={{ animationDelay: '0.06s' }}>
            {featured ? (
              <FeaturedScholarship scholarship={featured} onVerify={verify} onFlag={flag} />
            ) : (
              <div className="featured-placeholder">
                <p>No scholarships available</p>
              </div>
            )}
          </div>
          <div className="hero-side" style={{ animationDelay: '0.10s' }}>
            <div className="metric-stack">
              <MetricCard label="Total Scholarships" value={scholarships.length} color="blue" index={0} />
              <MetricCard label="Needs Review" value={reviewCount} color="orange" index={1} />
              <MetricCard label="Verified Today" value={verifiedToday} color="green" index={2} />
            </div>
            <NeedsReviewPanel scholarships={scholarships.filter(s => s.verification_status === 'needs_review')} onVerify={verify} onFlag={flag} />
          </div>
        </div>

        <div className="glass-panel controls-bar">
          <div className="controls-inner">
            <div className="search-wrap">
              <span className="search-icon" aria-hidden="true">⌕</span>
              <input
                className="glass-input"
                placeholder="Search scholarships, countries…"
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
              {search && (
                <button className="search-clear" onClick={() => setSearch('')} aria-label="Clear search">×</button>
              )}
            </div>
            <div className="filter-tabs">
              {[
                { key: 'all', label: 'All' },
                { key: 'active', label: 'Active' },
                { key: 'review', label: 'Needs Review' },
                { key: 'inactive', label: 'Inactive' },
              ].map(f => (
                <button
                  key={f.key}
                  className={`glass-btn filter-tab ${filter === f.key ? 'filter-tab--on' : ''}`}
                  onClick={() => setFilter(f.key)}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>
          <div className="controls-meta">
            <span className="result-count">{gridItems.length} {gridItems.length === 1 ? 'result' : 'results'}</span>
          </div>
        </div>

        {activeTab === 'image-review' && (
          <div className="review-section">
            <div className="review-section-header">
              <h2 className="review-section-title">Image Review Queue</h2>
              <button className="glass-btn glass-btn--ghost glass-btn--sm" onClick={loadReviewQueue} disabled={reviewLoading || !adminSecret}>
                {reviewLoading ? <span className="btn-spinner" /> : <span className="btn-icon">↺</span>}
                <span className="btn-text">{reviewLoading ? '' : 'Refresh'}</span>
              </button>
            </div>

            {reviewError && (
              <div className="glass state-box state-box--error">
                <p>{reviewError}</p>
                <button className="glass-btn" onClick={loadReviewQueue}>Retry</button>
              </div>
            )}

            {!reviewError && reviewLoading && (
              <div className="glass state-box">
                <div className="spinner" />
                <p>Loading review queue…</p>
              </div>
            )}

            {!reviewError && !reviewLoading && reviewQueue.length === 0 && (
              <div className="glass empty-state">
                <div className="empty-icon" aria-hidden="true">✓</div>
                <p className="empty-title">All caught up</p>
                <p className="empty-sub">No pending image reviews</p>
              </div>
            )}

            {!reviewError && !reviewLoading && reviewQueue.length > 0 && (
              <div className="review-grid">
                {reviewQueue.map((review, index) => (
                  <ReviewCard
                    key={review.id}
                    review={review}
                    index={index}
                    onApprove={() => handleApprove(review.id)}
                    onReject={() => handleReject(review.id)}
                    onOpenSource={() => window.open(review.source_page, '_blank', 'noopener,noreferrer')}
                    actionLoading={reviewActionLoading[review.id]}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {loading && !loadedOnce && (
          <div className="glass state-box">
            <div className="spinner" />
            <p>Loading scholarships…</p>
          </div>
        )}

        {error && (
          <div className="glass state-box state-box--error">
            <p>{error}</p>
            <button className="glass-btn" onClick={load}>Retry</button>
          </div>
        )}

        {!loading && !error && (
          <div className="scholarship-grid glass-scroll">
            {gridItems.length === 0 ? (
              <div className="glass empty-state">
                <div className="empty-icon" aria-hidden="true">⊘</div>
                <p className="empty-title">No scholarships found</p>
                <p className="empty-sub">Try adjusting your search or filters</p>
              </div>
            ) : gridItems.map((s, i) => (
              <ScholarshipCard
                key={s.id}
                scholarship={s}
                onVerify={verify}
                onFlag={flag}
                index={i}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
