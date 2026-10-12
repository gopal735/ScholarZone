import { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Navigation from './Navigation'
import { RouteErrorBoundary } from './AppErrorBoundary'

export default function Layout() {
  const [isScrolled, setIsScrolled] = useState(false)
  const location = useLocation()

  const isHomePage = location.pathname === '/'

  useEffect(() => {
    if (!isHomePage) return

    const hero = document.querySelector('.sz-hero')
    if (!hero) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        setIsScrolled(!entry.isIntersecting)
      },
      { threshold: 0, rootMargin: '-80px 0px 0px 0px' }
    )

    observer.observe(hero)
    return () => observer.disconnect()
  }, [isHomePage])

  const headerClass = `site-header ${isScrolled || !isHomePage ? 'is-scrolled' : ''}`

  return (
    <div className="app-shell">
      {/* Cinematic light field. Purely decorative, so it is hidden from
          assistive tech and never takes pointer events. */}
      <div className="app-atmosphere" aria-hidden="true">
        <span className="app-atmosphere__wash app-atmosphere__wash--key" />
        <span className="app-atmosphere__wash app-atmosphere__wash--rim" />
        <span className="app-atmosphere__wash app-atmosphere__wash--deep" />
        <span className="app-atmosphere__sheen" />
      </div>

      <div className="watermark" aria-hidden="true">ScholarZone</div>

      <header className={headerClass}>
        <Navigation />
      </header>

      <main className="app-content">
        {/* A throw inside a route is contained here: the header, the
            navigation and the footer above and below this boundary stay
            mounted, so the page is never left blank and the user can still
            get somewhere. The app-level boundary in main.jsx remains the
            last line of defence for a failure outside the route itself. */}
        <RouteErrorBoundary>
          <Outlet />
        </RouteErrorBoundary>
      </main>

      <footer className="app-footer">
        <p>ScholarZone &middot; Where Ambition Meets Opportunity.</p>
      </footer>
    </div>
  )
}
