import { useEffect, useState, useRef } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Navigation from './Navigation'
import { usePremiumPointer } from '../hooks/usePremiumPointer'

export default function Layout() {
  const [scrollPct, setScrollPct] = useState(0)
  const location = useLocation()

  usePremiumPointer()

  // Track page scroll for the top progress bar and vertical route indicator
  useEffect(() => {
    const handleScroll = () => {
      const scrollHeight = document.documentElement.scrollHeight - window.innerHeight
      if (scrollHeight > 0) {
        const pct = Math.min(100, Math.max(0, (window.scrollY / scrollHeight) * 100))
        setScrollPct(pct)
      }
    }

    window.addEventListener('scroll', handleScroll, { passive: true })
    handleScroll()
    return () => window.removeEventListener('scroll', handleScroll)
  }, [location.pathname])

  // Pointer follower glow
  const glowRef = useRef(null)
  useEffect(() => {
    const handlePointerMove = (e) => {
      if (glowRef.current) {
        glowRef.current.style.transform = `translate(${e.clientX}px, ${e.clientY}px)`
      }
    }
    window.addEventListener('pointermove', handlePointerMove, { passive: true })
    return () => window.removeEventListener('pointermove', handlePointerMove)
  }, [])

  return (
    <div className="app-shell">
      {/* Top Reading Scroll Progress Bar */}
      <div id="pg" style={{ width: `${scrollPct}%` }} aria-hidden="true" />

      {/* Floating Pointer Glow Light */}
      <div className="glow" id="glow" ref={glowRef} aria-hidden="true" />

      {/* Academic Sketches SVG Symbol Library */}
      <svg width="0" height="0" style={{ position: 'absolute' }} aria-hidden="true">
        <defs>
          <symbol id="d-book" viewBox="0 0 64 64">
            <path d="M4 14C14 8 24 8 32 14C40 8 50 8 60 14V50C50 44 40 44 32 50C24 44 14 44 4 50ZM32 14V50" />
          </symbol>
          <symbol id="d-cap" viewBox="0 0 64 64">
            <path d="M32 12 60 24 32 36 4 24ZM16 31V43C16 48 48 48 48 43V31M58 26V42" />
            <circle cx="58" cy="45" r="2" />
          </symbol>
          <symbol id="d-atom" viewBox="0 0 64 64">
            <ellipse cx="32" cy="32" rx="27" ry="10" />
            <ellipse cx="32" cy="32" rx="27" ry="10" transform="rotate(60 32 32)" />
            <ellipse cx="32" cy="32" rx="27" ry="10" transform="rotate(120 32 32)" />
            <circle cx="32" cy="32" r="3" />
          </symbol>
          <symbol id="d-bulb" viewBox="0 0 64 64">
            <path d="M24 46H40M26 52H38M32 8A15 15 0 0 0 23 35C25 37 26 40 26 43H38C38 40 39 37 41 35A15 15 0 0 0 32 8Z" />
          </symbol>
          <symbol id="d-pencil" viewBox="0 0 64 64">
            <path d="M10 54 14 42 44 12 52 20 22 50ZM40 16 48 24M14 42 22 50" />
          </symbol>
          <symbol id="d-compass" viewBox="0 0 64 64">
            <circle cx="32" cy="12" r="4" />
            <path d="M32 16 16 56M32 16 48 56M22 40H42" />
          </symbol>
          <symbol id="d-globe" viewBox="0 0 64 64">
            <circle cx="32" cy="32" r="24" />
            <ellipse cx="32" cy="32" rx="10" ry="24" />
            <path d="M8 32H56M12 20H52M12 44H52" />
          </symbol>
          <symbol id="d-graph" viewBox="0 0 64 64">
            <path d="M8 8V56H56M12 48C24 46 28 30 36 28S50 12 56 10" />
          </symbol>
          <symbol id="d-flask" viewBox="0 0 64 64">
            <path d="M26 8H38M28 8V24L14 52C13 55 15 57 18 57H46C49 57 51 55 50 52L36 24V8" />
          </symbol>
        </defs>
      </svg>

      {/* Floating navigation header */}
      <Navigation />

      {/* Vertical left route line with golden travel bead */}
      <div className="route" aria-hidden="true">
        <b style={{ height: `${scrollPct}%` }} />
        <i style={{ top: `${scrollPct}%` }} />
      </div>

      <main className="app-content">
        <Outlet />
      </main>
    </div>
  )
}
