import { useEffect, useState } from 'react'
import { fetchScholarships } from '../services/scholarshipService'

const DIRECTORY_LIMIT = 100

export function useScholarshipDirectory() {
  const [scholarships, setScholarships] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const controller = new AbortController()

    fetchScholarships({ page: 1, limit: DIRECTORY_LIMIT }, { signal: controller.signal })
      .then((directory) => {
        if (controller.signal.aborted) return
        setScholarships(directory.items)
        setError(null)
      })
      .catch((error) => {
        if (controller.signal.aborted) return
        setScholarships([])
        setError(error)
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false)
        }
      })

    return () => controller.abort()
  }, [])

  return {
    scholarships,
    isLoading,
    isUsingSnapshot: false,
    isUsingLocalFallback: false,
    fromSnapshot: false,
    staticMode: false,
    error,
  }
}
