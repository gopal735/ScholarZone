import { useCallback, useEffect, useState } from 'react'
import { fetchScholarships } from '../services/scholarshipService'

const DIRECTORY_LIMIT = 100

export function useScholarshipDirectory() {
  const [scholarships, setScholarships] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [requestVersion, setRequestVersion] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setIsLoading(true)

    fetchScholarships({ page: 1, limit: DIRECTORY_LIMIT }, { signal: controller.signal })
      .then((directory) => {
        if (controller.signal.aborted) return
        setScholarships(Array.isArray(directory?.items) ? directory.items : [])
        setError(null)
      })
      .catch((caughtError) => {
        if (controller.signal.aborted) return
        setScholarships([])
        setError(caughtError)
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

  const retry = useCallback(() => {
    setRequestVersion((value) => value + 1)
  }, [])

  return {
    scholarships,
    isLoading,
    error,
    retry,
    refetch: retry,
    isUsingSnapshot: false,
    isUsingLocalFallback: false,
    fromSnapshot: false,
    staticMode: false,
  }
}