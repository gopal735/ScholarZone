import { useEffect, useState } from 'react'
import { fetchScholarshipStats } from '../services/scholarshipService'

/**
 * Normalize scholarship stats from both API and static snapshot.
 *
 * API returns: verified_active, fully_funded
 * Static snapshot returns: verified, fullyFunded (mapped from verified_active, fully_funded)
 *
 * This hook normalizes to a consistent internal format:
 * - verified (number)
 * - fullyFunded (number)
 * - total (number)
 * - countries (number)
 * - open (number)
 * - closingSoon (number)
 * - upcoming (number)
 */
function normalizeStats(rawStats) {
  if (!rawStats) return null

  return {
    total: rawStats.total ?? 0,
    countries: rawStats.countries ?? 0,
    open: rawStats.open ?? 0,
    closingSoon: rawStats.closing_soon ?? rawStats.closingSoon ?? 0,
    upcoming: rawStats.upcoming ?? 0,
    closed: rawStats.closed ?? 0,
    verified: rawStats.verified ?? rawStats.verified_active ?? 0,
    fullyFunded: rawStats.fullyFunded ?? rawStats.fully_funded ?? 0,
    withImage: rawStats.with_image ?? rawStats.withImage ?? 0,
    withOfficialSource: rawStats.with_official_source ?? rawStats.withOfficialSource ?? 0,
  }
}

export function useScholarshipStats() {
  const [stats, setStats] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false

    fetchScholarshipStats()
      .then((data) => {
        if (!cancelled) {
          setStats(normalizeStats(data))
          setIsLoading(false)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err)
          setIsLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [])

  return { stats, isLoading, error }
}