import { NavLink } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useCompare } from '../hooks/useCompare'
import { useSavedScholarships } from '../hooks/useSavedScholarships'
import ThemeToggle from './ThemeToggle'
import './Navigation.css'

export default function Navigation() {
  const { status } = useAuth()
  const { compareIds } = useCompare()
  const { savedIds } = useSavedScholarships()

  return (
    <nav className="nav-bar" aria-label="Primary navigation">
      <NavLink to="/" className="nav-brand">
        <span className="nav-brand__mark" aria-hidden="true">S</span>
        <span>ScholarZone</span>
      </NavLink>

      <div className="nav-menu">
        <div className="nav-links">
          <NavLink to="/" end className={({ isActive }) => (isActive ? 'active' : '')}>Home</NavLink>
          <NavLink to="/scholarships" className={({ isActive }) => (isActive ? 'active' : '')}>Scholarships</NavLink>
          <NavLink to="/countries" className={({ isActive }) => (isActive ? 'active' : '')}>Countries</NavLink>
        </div>

        <div className="nav-utilities">
          <NavLink to="/saved" className={({ isActive }) => `nav-utility-link ${isActive ? 'active' : ''}`} aria-label={`Saved scholarships: ${savedIds.length}`}>
            Saved {savedIds.length > 0 && <span>{savedIds.length}</span>}
          </NavLink>
          <NavLink to="/compare" className={({ isActive }) => `nav-utility-link ${isActive ? 'active' : ''}`} aria-label={`Compare scholarships: ${compareIds.length}`}>
            Compare {compareIds.length > 0 && <span>{compareIds.length}</span>}
          </NavLink>
          {status === 'checking' ? (
            <span className="nav-session-status">Checking&hellip;</span>
          ) : (
            <NavLink to="/login" className={({ isActive }) => `nav-sign-in ${isActive ? 'active' : ''}`}>Sign in</NavLink>
          )}
          <ThemeToggle />
        </div>
      </div>
    </nav>
  )
}
