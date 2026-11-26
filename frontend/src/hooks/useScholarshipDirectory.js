import { useEffect, useState } from 'react'
import { fetchScholarships } from '../services/scholarshipService'

const DIRECTORY_LIMIT = 100

export function useScholarshipDirectory() {
  const [scholarships, setScholarships] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [requestVersion, setRequestVersion] = useState(0)

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
  }, [requestVersion])

  useEffect(() => {
    if (typeof window === 'undefined') return undefined
    const interval = window.setInterval(() => setRequestVersion((value) => value + 1), 45000)
    const onFocus = () => setRequestVersion((value) => value + 1)
    window.addEventListener('focus', onFocus)
    const onVisibility = () => {
      if (document.visibilityState === 'visible') onFocus()
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      window.clearInterval(interval)
      window.removeEventListener('focus', onFocus)
      document.removeEventListener('visibilitychange', onVisibility)
    }
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
