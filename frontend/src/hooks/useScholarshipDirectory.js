import { useEffect, useState } from 'react'
import { scholarships as fallbackScholarships } from '../data/scholarships'
import { fetchScholarships } from '../services/scholarshipService'

const DIRECTORY_LIMIT = 100

export function useScholarshipDirectory() {
  const [scholarships, setScholarships] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [isUsingFallback, setIsUsingFallback] = useState(false)

  useEffect(() => {
    const controller = new AbortController()

    fetchScholarships({ page: 1, limit: DIRECTORY_LIMIT }, { signal: controller.signal })
      .then((directory) => {
        if (controller.signal.aborted) {
          return
        }

        setScholarships(directory.items)
        setIsUsingFallback(false)
      })
      .catch(() => {
        if (controller.signal.aborted) {
          return
        }

        setScholarships(fallbackScholarships)
        setIsUsingFallback(true)
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false)
        }
      })

    return () => controller.abort()
  }, [])

  return { scholarships, isLoading, isUsingFallback }
}
