import { useEffect, useState } from 'react'
import { scholarships as fallbackScholarships } from '../data/scholarships'
import { fetchScholarships } from '../services/scholarshipService'

const DIRECTORY_LIMIT = 100

/* The share of the catalogue a single page shows. Home's showcase, its
   collections and its marquee all draw from this, so it needs enough rows
   to fill those and no more — a bigger limit costs a larger response on
   the first paint for content the visitor has to scroll to reach anyway.
 */
export function useScholarshipDirectory() {
  const [scholarships, setScholarships] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [isUsingFallback, setIsUsingFallback] = useState(false)
  const [fromSnapshot, setFromSnapshot] = useState(false)
  const [staticMode, setStaticMode] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    const controller = new AbortController()

    fetchScholarships({ page: 1, limit: DIRECTORY_LIMIT }, { signal: controller.signal })
      .then((directory) => {
        if (controller.signal.aborted) {
          return
        }

        setScholarships(directory.items)
        // A snapshot answer resolves successfully but is still a fallback:
        // the API did not serve this page. The three flags are set together
        // so a caller never has to infer provenance from an error that did
        // not happen.
        const isSnapshot = Boolean(directory.fromSnapshot)
        const isStatic = Boolean(directory.staticMode)
        setFromSnapshot(isSnapshot)
        setStaticMode(isStatic)
        // Static mode is a deliberate architectural choice, not a failure.
        // Only treat as "fallback" when we actually fell back due to API failure.
        setIsUsingFallback(isSnapshot && !isStatic)
        setError(null)
      })
      .catch((error) => {
        if (controller.signal.aborted) {
          return
        }

        setScholarships(fallbackScholarships)
        setIsUsingFallback(true)
        setFromSnapshot(false)
        setStaticMode(false)
        setError(error)
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false)
        }
      })

    return () => controller.abort()
  }, [])

  return { scholarships, isLoading, isUsingFallback, fromSnapshot, staticMode, error }
}
