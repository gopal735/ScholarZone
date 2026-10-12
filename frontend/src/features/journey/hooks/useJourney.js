import { useContext } from 'react'
import { JourneyContext } from '../state/journeyContext.js'

/**
 * Read the journey store.
 *
 * Throws when used outside the provider rather than returning null, because a
 * silently undefined store produces a page that renders nothing and reports
 * nothing. The provider is mounted at the route boundary, so the throw is a
 * build-time-visible wiring mistake rather than a runtime mystery.
 */
export function useJourney() {
  const context = useContext(JourneyContext)
  if (context === null) {
    throw new Error('useJourney must be used inside a JourneyProvider')
  }
  return context
}
