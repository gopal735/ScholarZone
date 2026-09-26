import { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Navigation from './Navigation'

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
      {/* Living light field. Purely decorative, so it is hidden from
          assistive tech and never takes pointer events. */}
      <div className="app-atmosphere" aria-hidden="true">
        <span className="app-atmosphere__wash app-atmosphere__wash--pearl" />
        <span className="app-atmosphere__wash app-atmosphere__wash--champagne" />
        <span className="app-atmosphere__wash app-atmosphere__wash--beige" />
        <span className="app-atmosphere__wash app-atmosphere__wash--clay" />
        <span className="app-atmosphere__sheen" />
      </div>

      <div className="watermark" aria-hidden="true">ScholarZone</div>

      <header className={headerClass}>
        <Navigation />
      </header>

      <main className="app-content">
        <Outlet />
      </main>

      <footer className="app-footer">
        <p>ScholarZone &middot; Where Ambition Meets Opportunity.</p>
      </footer>
    </div>
  )
}
