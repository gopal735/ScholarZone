/**
 * The opportunity summary: real counts, from the server, over a named universe.
 *
 * Every number here arrived in `summary`, which the server took from Match 2.0
 * and Count Intelligence 2.0. Nothing is counted in the browser - not the length
 * of a list, not a percentage, not a total. If the frontend recalculated a count
 * it could disagree with the list it is describing, and a dashboard that
 * disagrees with itself is worse than no dashboard.
 *
 * The universe is stated in the section, because a count without one is
 * meaningless: 386 opportunities in the directory and 386 analysed against this
 * profile are the same figure today for different reasons, and would not be if a
 * filter were applied.
 */

import { titleCaseKey } from '../../services/dashboardPresentation'

function StatTile({ label, value, note }) {
  return (
    <div className="summary__tile">
      <dt className="summary__tile-label">{label}</dt>
      <dd className="summary__tile-value">{typeof value === 'number' ? value.toLocaleString() : value}</dd>
      {note ? <p className="summary__tile-note">{note}</p> : null}
    </div>
  )
}

export default function OpportunitySummary({ summary, consistency }) {
  const tiles = [
    {
      label: 'Strong matches',
      value: summary.strong_match_count,
      note: 'Exceptional, very strong or strong fit for this profile.',
    },
    {
      label: 'Eligible',
      value: summary.eligible_count,
      note: 'Cleared every published eligibility rule.',
    },
    {
      label: 'Needs verification',
      value: summary.needs_verification_count,
      note: 'A published rule could not be checked against your profile.',
    },
    {
      label: 'Ready to apply',
      value: summary.ready_to_apply_count,
      note: 'Eligible with nothing outstanding to check first.',
    },
    {
      label: 'Closing soon',
      value: summary.closing_soon_count,
      note: 'A published deadline falls within 14 days.',
    },
  ]

  return (
    <section className="dashboard-section" aria-labelledby="summary-heading">
      <div className="dashboard-section__header">
        <div>
          <p className="page-eyebrow">Opportunities</p>
          <h2 className="dashboard-section__title" id="summary-heading">
            What is open for you
          </h2>
        </div>
        <p className="dashboard-section__universe">
          {summary.total_candidates.toLocaleString()} opportunities analysed against your profile
        </p>
      </div>

      <dl className="summary__tiles">
        {tiles.map((tile) => (
          <StatTile key={tile.label} label={tile.label} value={tile.value} note={tile.note} />
        ))}
      </dl>

      {/*
        The two engines that produced these numbers are compared on the server.
        Surfacing the verdict is what stops a reader having to trust it: if the
        universes ever disagreed, this would say so rather than showing two
        plausible totals side by side.
      */}
      <p className="summary__provenance">
        Counts from {titleCaseKey(summary.universe)} ·{' '}
        {consistency.counts_agree ? 'Match and Count Intelligence agree' : 'engine totals disagree'} ·
        integrity {consistency.integrity_status}
      </p>
      {consistency.integrity_issues.length > 0 ? (
        <ul className="summary__issues">
          {consistency.integrity_issues.map((issue) => (
            <li key={issue}>{issue}</li>
          ))}
        </ul>
      ) : null}
    </section>
  )
}