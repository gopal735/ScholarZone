/* The supervisor affordance on a scholarship card.
 *
 * Small on purpose. A card's job is to route someone to a detail page, and a
 * supervisor count is a fact about that page rather than something to advertise
 * on a grid of forty.
 *
 * The count appears only when there is something verified to count. A zero is
 * never rendered as "0" — that reads as "this scholarship has no supervisors",
 * which is a claim the system cannot make. The honest zero states that nothing is
 * verified yet and leaves the reason to the detail page.
 *
 * There is no percentage, no "increase your chances" badge, and no number that is
 * not a count of verified records.
 */

import { useEffect, useState } from 'react'
import { fetchSupervisorSummary } from '../services/supervisorService'
import './SupervisorCta.css'

const LABELS = {
  verified: (count) => `Potential Supervisors · ${count}`,
  none: 'Potential Supervisors',
}

function labelFor(coverage) {
  if (!coverage) return null
  if (coverage.verified_supervisor_count > 0) {
    return LABELS.verified(coverage.verified_supervisor_count)
  }
  return LABELS.none
}

export default function SupervisorCta({ scholarshipId }) {
  const [coverage, setCoverage] = useState(null)
  const [state, setState] = useState('loading')

  useEffect(() => {
    const controller = new AbortController()
    let active = true

    fetchSupervisorSummary(scholarshipId, { signal: controller.signal })
      .then((summary) => {
        if (!active) return
        setCoverage(summary)
        setState('ready')
      })
      .catch((error) => {
        if (!active || error.name === 'AbortError') return
        // A failure here must not disturb the card. The feature simply renders
        // nothing, exactly as it would for a record with no coverage row.
        setState('unavailable')
      })

    return () => {
      active = false
      controller.abort()
    }
  }, [scholarshipId])

  /* Nothing renders until there is a verified count to show. This keeps a grid
     of cards quiet and avoids a row of identical "no supervisors" labels, which
     would read as a site-wide problem rather than as per-record state. */
  if (state !== 'ready' || !coverage || coverage.verified_supervisor_count < 1) {
    return null
  }

  const stale = coverage.coverage_status === 'verified_supervisors' && coverage.last_checked_at === null

  return (
    <span className="sz-supervisor-cta">
      <span className="sz-supervisor-cta__label">{labelFor(coverage)}</span>
      {stale ? (
        <span className="sz-sr-only">Verification date not yet recorded</span>
      ) : null}
    </span>
  )
}