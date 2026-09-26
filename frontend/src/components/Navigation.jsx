import { NavLink } from 'react-router-dom'
import { LazyMotion, domAnimation, m } from 'motion/react'
import { useAuth } from '../hooks/useAuth'
import { useCompare } from '../hooks/useCompare'
import { useSavedScholarships } from '../hooks/useSavedScholarships'
import { useReducedMotion } from '../hooks/useReducedMotion'
import ThemeToggle from './ThemeToggle'
import './Navigation.css'

const ENTER_TRANSITION = { duration: 0.45, ease: [0.16, 1, 0.3, 1] }
const COUNT_SPRING = { type: 'spring', stiffness: 520, damping: 28 }

function UtilityCount({ count, animate }) {
  if (count <= 0) return null

  if (!animate) {
    return <span>{count}</span>
  }

  return (
    <m.span
      key={count}
      initial={{ scale: 0.72, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={COUNT_SPRING}
    >
      {count}
    </m.span>
  )
}

function CountedUtilityLink({ to, label, count, className, animate }) {
  return (
    <NavLink to={to} className={({ isActive }) => `${className} ${isActive ? 'active' : ''}`} aria-label={`${label}: ${count}`}>
      {label}
      <UtilityCount count={count} animate={animate} />
    </NavLink>
  )
}

export default function Navigation() {
  const { status } = useAuth()
  const { compareIds } = useCompare()
  const { savedIds } = useSavedScholarships()
  const prefersReducedMotion = useReducedMotion()

  return (
    <LazyMotion features={domAnimation} strict={false}>
      <m.nav
        className="nav-bar"
        aria-label="Primary navigation"
        initial={prefersReducedMotion ? false : { opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={ENTER_TRANSITION}
      >
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
            <CountedUtilityLink to="/saved" label="Saved" count={savedIds.length} className="nav-utility-link" animate={!prefersReducedMotion} />
            <CountedUtilityLink to="/compare" label="Compare" count={compareIds.length} className="nav-utility-link" animate={!prefersReducedMotion} />
            {status === 'checking' ? (
              <span className="nav-session-status">Checking&hellip;</span>
            ) : (
              <NavLink to="/login" className={({ isActive }) => `nav-sign-in ${isActive ? 'active' : ''}`}>Sign in</NavLink>
            )}
            <ThemeToggle />
          </div>
        </div>
      </m.nav>
    </LazyMotion>
  )
}
