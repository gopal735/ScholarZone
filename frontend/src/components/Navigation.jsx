import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useSavedScholarships } from '../hooks/useSavedScholarships'
import { useTheme } from '../hooks/useTheme'
import './Navigation.css'

export default function Navigation() {
  const { status } = useAuth()
  const { savedIds } = useSavedScholarships()
  const { theme, toggleTheme } = useTheme()
  const location = useLocation()
  const navigate = useNavigate()

  const isHome = location.pathname === '/'

  const handleAnchor = (e, id) => {
    e.preventDefault()
    if (isHome) {
      const el = document.getElementById(id)
      if (el) {
        el.scrollIntoView({ behavior: 'smooth' })
      }
    } else {
      navigate(`/#${id}`)
    }
  }

  const handleShowreel = () => {
    window.dispatchEvent(new CustomEvent('sz-trigger-showreel'))
  }

  return (
    <header className="sz-nav-header nav" role="banner">
      <NavLink to="/" className="logo" aria-label="ScholarZone Home">
        <i>
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4 18C7 6 17 6 20 18" />
            <circle cx="4" cy="18" r="1.7" />
            <circle cx="20" cy="18" r="1.7" />
          </svg>
        </i>
        ScholarZone
      </NavLink>

      <nav aria-label="Primary navigation">
        <a href="#top" onClick={(e) => handleAnchor(e, 'top')}>Match</a>
        <a href="#tools" onClick={(e) => handleAnchor(e, 'tools')}>Toolkit</a>
        <a href="#learn" onClick={(e) => handleAnchor(e, 'learn')}>Learn</a>
        <a href="#how" onClick={(e) => handleAnchor(e, 'how')}>How it works</a>
        <NavLink to="/scholarships" className={({ isActive }) => (isActive ? 'active' : '')}>
          Directory
        </NavLink>
        <NavLink to="/saved" className={({ isActive }) => (isActive ? 'active' : '')}>
          Saved {savedIds.length > 0 && `· ${savedIds.length}`}
        </NavLink>
      </nav>

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

        <button
          className="btn showreel-btn"
          id="play"
          type="button"
          onClick={handleShowreel}
        >
          Watch showreel
        </button>

        {status === 'authenticated' ? (
          <NavLink to="/dashboard" className="btn nav-auth-btn">Dashboard</NavLink>
        ) : (
          <NavLink to="/login" className="btn nav-auth-btn">Sign in</NavLink>
        )}
      </div>
    </header>
  )
}

