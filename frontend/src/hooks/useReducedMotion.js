import { useEffect, useState } from 'react'

const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)'

function canMatchMedia() {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function'
}

function getInitialPreference() {
  if (!canMatchMedia()) return false
  return window.matchMedia(REDUCED_MOTION_QUERY).matches
}

export function useReducedMotion() {
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(getInitialPreference)

  useEffect(() => {
    if (!canMatchMedia()) return undefined

    const mediaQuery = window.matchMedia(REDUCED_MOTION_QUERY)
    const handleChange = (event) => setPrefersReducedMotion(event.matches)

    mediaQuery.addEventListener('change', handleChange)

    return () => mediaQuery.removeEventListener('change', handleChange)
  }, [])

  return prefersReducedMotion
}
