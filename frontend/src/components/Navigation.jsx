import { useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useSavedScholarships } from '../hooks/useSavedScholarships'
import { useCompare } from '../hooks/useCompare'
import { useTheme } from '../hooks/useTheme'
import './Navigation.css'

export default function Navigation() {
  const { status } = useAuth()
  const { savedIds } = useSavedScholarships()
  const { compareIds } = useCompare()
  const { theme, toggleTheme } = useTheme()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  // Prevent body scroll when mobile drawer is open
  useEffect(() => {
    if (mobileMenuOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [mobileMenuOpen])

  // Escape key closes mobile drawer
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') setMobileMenuOpen(false)
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  const navItems = [
    { to: '/scholarships', label: 'Directory', desc: 'Browse verified opportunities' },
    { to: '/match', label: 'Match', badge: '✨', desc: 'Check eligibility by GPA & IELTS' },
    { to: '/countries', label: 'Destinations', desc: 'Living costs & country guides' },
    { to: '/applications', label: 'Applications', desc: 'Track tasks, SOPs & deadlines' },
    { to: '/assistant', label: 'AI Assistant', badge: '🤖', desc: 'Scholarship discovery, comparison & guidance' },
    {
      to: '/compare',
      label: 'Compare',
      count: compareIds.length,
      desc: 'Side-by-side funding breakdown',
    },
    {
      to: '/saved',
      label: 'Shortlist',
      count: savedIds.length,
      desc: 'Saved bookmarks for fast access',
    },
  ]

  return (
    <>
      <header className="sz-nav-header nav" role="banner">
        <NavLink to="/" className="logo" aria-label="ScholarZone Home">
          <i>
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M4 18C7 6 17 6 20 18" />
              <circle cx="4" cy="18" r="1.7" />
              <circle cx="20" cy="18" r="1.7" />
            </svg>
          </i>
          <span>ScholarZone</span>
        </NavLink>

        {/* Desktop Navigation Links */}
        <nav className="desktop-nav" aria-label="Primary navigation">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => (isActive ? 'active' : '')}
            >
              <span>{item.label}</span>
              {item.badge && <span className="nav-item-badge">{item.badge}</span>}
              {typeof item.count === 'number' && item.count > 0 && (
                <span className="nav-item-count">{item.count}</span>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Controls */}
        <div className="nav-controls">
          <button
            className="tg"
            id="th"
            type="button"
            onClick={toggleTheme}
            aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
          >
            <svg className="sun" viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="12" cy="12" r="4" />
              <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
            </svg>
            <svg className="moon" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M20 14.5A8 8 0 019.5 4 8 8 0 1020 14.5z" />
            </svg>
          </button>

          {status === 'authenticated' ? (
            <NavLink to="/dashboard" className="btn nav-auth-btn">
              Dashboard
            </NavLink>
          ) : (
            <NavLink to="/login" className="btn nav-auth-btn">
              Sign in
            </NavLink>
          )}

          {/* Mobile Menu Toggle Button */}
          <button
            type="button"
            className="sz-menu-toggle"
            aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={mobileMenuOpen}
            onClick={() => setMobileMenuOpen((open) => !open)}
          >
            {mobileMenuOpen ? (
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M6 18L18 6M6 6l12 12" />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M3 12h18M3 6h18M3 18h18" />
              </svg>
            )}
          </button>
        </div>
      </header>

      {/* Mobile Drawer Backdrop */}
      {mobileMenuOpen && (
        <div
          className="sz-mobile-backdrop"
          onClick={() => setMobileMenuOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Mobile Drawer */}
      <aside
        className={`sz-mobile-drawer ${mobileMenuOpen ? 'is-open' : ''}`}
        aria-label="Mobile Navigation"
        aria-hidden={!mobileMenuOpen}
      >
        <div className="sz-mobile-drawer__header">
          <div className="sz-mobile-drawer__logo">
            <i>
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M4 18C7 6 17 6 20 18" />
                <circle cx="4" cy="18" r="1.7" />
                <circle cx="20" cy="18" r="1.7" />
              </svg>
            </i>
            <span>ScholarZone</span>
          </div>
          <button
            type="button"
            className="sz-mobile-close"
            onClick={() => setMobileMenuOpen(false)}
            aria-label="Close menu"
          >
            ✕
          </button>
        </div>

        <div className="sz-mobile-drawer__quick-auth">
          {status === 'authenticated' ? (
            <NavLink
              to="/dashboard"
              className="sz-mobile-auth-card"
              onClick={() => setMobileMenuOpen(false)}
            >
              <div className="sz-mobile-auth-card__info">
                <strong>Your Dashboard</strong>
                <span>View tracked applications & matches</span>
              </div>
              <span className="sz-mobile-arrow">&rarr;</span>
            </NavLink>
          ) : (
            <div className="sz-mobile-auth-actions">
              <NavLink
                to="/login"
                className="btn sz-btn--primary"
                onClick={() => setMobileMenuOpen(false)}
              >
                Sign in
              </NavLink>
              <NavLink
                to="/register"
                className="btn ghost"
                onClick={() => setMobileMenuOpen(false)}
              >
                Create Account
              </NavLink>
            </div>
          )}
        </div>

        <nav className="sz-mobile-drawer__links">
          <p className="sz-mobile-label">Student Tools & Directory</p>
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `sz-mobile-link ${isActive ? 'is-active' : ''}`
              }
              onClick={() => setMobileMenuOpen(false)}
            >
              <div className="sz-mobile-link__content">
                <div className="sz-mobile-link__title">
                  <span>{item.label}</span>
                  {item.badge && <span className="nav-item-badge">{item.badge}</span>}
                </div>
                <small className="sz-mobile-link__desc">{item.desc}</small>
              </div>
              {typeof item.count === 'number' && item.count > 0 && (
                <span className="nav-item-count">{item.count}</span>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="sz-mobile-drawer__footer">
          <p>Verified scholarship discovery & planning for ambitious students.</p>
        </div>
      </aside>
    </>
  )
}
