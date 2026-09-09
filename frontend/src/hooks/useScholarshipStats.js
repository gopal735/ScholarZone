import { useEffect, useState } from 'react'
import { fetchScholarshipStats } from '../services/scholarshipService'

const EMPTY_STATS = {
  total: 0,
  countries: 0,
  open: 0,
  closing_soon: 0,
  upcoming: 0,
  verified_active: 0,
  fully_funded: 0,
  with_image: 0,
  with_official_source: 0,
}

/**
  * Fetches live scholarship statistics from GET /scholarships/stats.
 *
 * Exposes three intentional states:
 *   - 'loading'  : request in flight, no data yet
 *   - 'success'  : stats populated from the API
 *   - 'error'    : API unreachable or failed — stats stay at EMPTY_STATS
 *
 * On error we never fall back to hardcoded values; the UI renders a neutral
 * unavailable state instead.
 */
export function useScholarshipStats() {
  const [stats, setStats] = useState(EMPTY_STATS)
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState(null)

  useEffect(() => {
    const controller = new AbortController()

    fetchScholarshipStats({ signal: controller.signal })
      .then((payload) => {
        if (controller.signal.aborted) return
        setStats({ ...EMPTY_STATS, ...payload })
        setStatus('success')
      })
      .catch((err) => {
        if (controller.signal.aborted) return
        setError(err)
        setStats(EMPTY_STATS)
        setStatus('error')
      })

    return () => controller.abort()
  }, [])

  return { stats, status, error, isLoading: status === 'loading', isReady: status === 'success', isUnavailable: status === 'error' }
}