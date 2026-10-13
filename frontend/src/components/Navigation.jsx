import { NavLink } from 'react-router-dom'
import { enabled as consistencyAuditorEnabled } from '../features/consistency-auditor'
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
  // A link with no real count — Applications — passes nothing. `undefined <= 0`
  // is false, so the old guard let an absent count through and the nav rendered
  // an empty pill whose accessible name read "Applications: undefined".
  if (typeof count !== 'number' || count <= 0) return null

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
  // The count is only part of the accessible name when there is one, so a
  // countless link reads as its own label.
  const hasCount = typeof count === 'number' && count > 0
  return (
    <NavLink
      to={to}
      className={({ isActive }) => `${className} ${isActive ? 'active' : ''}`}
      aria-label={hasCount ? `${label}: ${count}` : undefined}
    >
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
            <NavLink to="/match" className={({ isActive }) => (isActive ? 'active' : '')}>Match</NavLink>
            <NavLink to="/countries" className={({ isActive }) => (isActive ? 'active' : '')}>Countries</NavLink>
            {/* The applicant journey. It sits in the primary row because it is a
                destination in its own right, not an account utility, and the
                "New" marker is a plain span rather than a count — there is
                nothing to count, and a badge that says "New" forever is a lie
                the moment the feature stops being new. It is marked
                aria-hidden so the accessible name stays the link's own label,
                and the route is announced as "Bangladesh Journey" alone. */}
            <NavLink to="/bangladesh-journey" className={({ isActive }) => `nav-utility-link nav-link--journey ${isActive ? 'active' : ''}`}>
              BD Journey
              <span className="nav-badge nav-badge--new" aria-hidden="true">New</span>
            </NavLink>
          </div>

          <div className="nav-utilities">
            <CountedUtilityLink to="/applications" label="Applications" className="nav-utility-link" animate={!prefersReducedMotion} />
            <CountedUtilityLink to="/saved" label="Saved" count={savedIds.length} className="nav-utility-link" animate={!prefersReducedMotion} />
            {/* The local planning surface: checklist, deadlines, notes and a
                backup. It is the anonymous half of the workspace, so it is
                reachable without an account. */}
            <NavLink to="/plan" className={({ isActive }) => `nav-utility-link ${isActive ? 'active' : ''}`}>
              Plan
            </NavLink>
            {/* The statement-of-purpose builder: the second browser-local
                workspace, with no account, no server and no sync. It sits beside
                Plan rather than under it, because it answers a different question
                and a student drafting a statement should not have to go through
                the checklist to reach it. */}
            <NavLink to="/statement" className={({ isActive }) => `nav-utility-link ${isActive ? 'active' : ''}`}>
              Statement
            </NavLink>
            <CountedUtilityLink to="/compare" label="Compare" count={compareIds.length} className="nav-utility-link" animate={!prefersReducedMotion} />
            {/* The mentor is a reading surface over the records the three links
                above already point at, so it sits with them rather than in the
                primary row. It resolves its own access state from the server, so
                like the dashboard this link is a convenience and never the thing
                that decides whether someone may see it. */}
            <NavLink to="/mentor" className={({ isActive }) => `nav-utility-link ${isActive ? 'active' : ''}`}>
              Mentor
            </NavLink>
            {/* The consistency review runs entirely in the browser and is
                gated by its own module flag, so the link is absent while the
                feature is off - nothing dead in the navigation. */}
            {consistencyAuditorEnabled && (
              <NavLink
                to="/consistency-review"
                className={({ isActive }) => `nav-utility-link ${isActive ? 'active' : ''}`}
              >
                Review
              </NavLink>
            )}
            {/* Tutorials and help. In the utility row rather than the primary
                row because it is reference material rather than a destination:
                a student comes to the catalogue to act, and to help when they
                are unsure how.

                The visible label is "Help & Tutorials" and it is the accessible
                name too. A previous version showed "Help" and carried
                "Help and tutorials:" in a screen-reader-only span, so a sighted
                reader on a narrow viewport got a word that does not say what the
                link is for while a screen-reader user got the full phrase. One
                label for both, because the visible text is the label. */}
            <NavLink to="/help" className={({ isActive }) => `nav-utility-link ${isActive ? 'active' : ''}`}>
              Help &amp; Tutorials
            </NavLink>
            {status === 'checking' ? (
              <span className="nav-session-status">Checking&hellip;</span>
            ) : status === 'authenticated' ? (
              // An account exists, so the useful destination is the workspace
              // rather than the sign-in form. The dashboard reads its own access
              // state from the server, so this link is a convenience, never the
              // thing that decides whether someone may see it.
              <NavLink to="/dashboard" className={({ isActive }) => `nav-sign-in ${isActive ? 'active' : ''}`}>
                Dashboard
              </NavLink>
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
