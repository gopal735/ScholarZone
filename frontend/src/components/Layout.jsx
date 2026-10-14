import { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Navigation from './Navigation'
import { usePremiumPointer } from '../hooks/usePremiumPointer'

export default function Layout() {
  const [isScrolled, setIsScrolled] = useState(false)
  const location = useLocation()

  /* The reference's one document-level pointer listener: card tilt,
     gloss, spotlight, magnetic buttons and the cursor glow. Installed
     once for the shell rather than per component, and a no-op on
     touch or with reduced motion. */
  usePremiumPointer()

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

      {/* The reference's ambient light sources: two aurora fields that
          drift behind the page, and the cursor glow that follows the
          pointer. All three are decorative and pointer-transparent. */}
      <div className="p-aur p-aur--a" aria-hidden="true" />
      <div className="p-aur p-aur--b" aria-hidden="true" />
      <div className="p-glow" aria-hidden="true" />

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

      {/* Film grain over everything, as the reference does on body::after.
          Last in the shell so it composites above content, and
          pointer-transparent so no interaction reaches it. */}
      <div className="p-noise" aria-hidden="true" />
    </div>
  )
}
