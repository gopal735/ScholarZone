import { useEffect, useState } from 'react'
import { scholarships as fallbackScholarships } from '../data/scholarships'
import { fetchAllScholarships } from '../services/scholarshipService'

/**
 * The catalogue, in full, for pages that resolve ids against it.
 *
 * This hook used to fetch the first 100 records. That was fine for the home
 * page, which only ever previews a handful, but two other surfaces were built
 * on top of it and were not: `/saved` and `/compare` both hold a list of ids the
 * student chose and resolve each one with `scholarships.find(...)`. The
 * snapshot carries 618 public records, so 518 of them were unreachable through
 * those pages - a student who saved record 500 was shown an empty shortlist and
 * had no way to tell that from having saved nothing.
 *
 * It is the whole catalogue rather than a bigger window on purpose. A window
 * still fails, just later, and the snapshot is a single asset that any
 * catalogue surface has already loaded, so the marginal cost of holding all of
 * it is a filter over 618 objects.
 *
 * `isLoading` stays true until the first attempt settles, so every consumer
 * keeps its loading state; `isUsingFallback` and `error` keep their meaning.
 */
export function useScholarshipDirectory() {
  const [scholarships, setScholarships] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [isUsingFallback, setIsUsingFallback] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    const controller = new AbortController()

    fetchAllScholarships({ signal: controller.signal })
      .then((records) => {
        if (controller.signal.aborted) {
          return
        }

        setScholarships(records)
        setIsUsingFallback(false)
        setError(null)
      })
      .catch((error) => {
        if (controller.signal.aborted) {
          return
        }

        // The bundled snapshot is the source of truth for public browsing, so
        // a failure here is the snapshot being unreadable rather than the
        // database being unavailable. The seed list is a stand-in that keeps
        // the page renderable and is labelled as such by the consumer.
        setScholarships(fallbackScholarships)
        setIsUsingFallback(true)
        setError(error)
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false)
        }
      })

    return () => controller.abort()
  }, [])

  return { scholarships, isLoading, isUsingFallback, error }
}
