import { useState } from 'react'

import MatchCard from './MatchCard'
import MatchCompare, { MAX_COMPARE } from './MatchCompare'
import MatchFilters from './MatchFilters'
import { FILTER_GROUPS, alternativesFor, matchesFilters } from './matchFilterConfig'

const EMPTY_FILTERS = {
  eligibility: '',
  fit: '',
  funding: '',
  country: '',
  degree: '',
  confidence: '',
  deadline: '',
}

/**
 * API dimension -> local filter key.
 *
 * The counting contract names its dimensions in upper case because they are a
 * published vocabulary; the filter config uses the lower-case key that identifies a
 * form control. Translating here means a change suggested by the API can be applied
 * without the alternative list knowing either vocabulary.
 */
const FILTER_KEY_BY_DIMENSION = {
  COUNTRY: 'country',
  DEGREE: 'degree',
  FIELD: 'field',
  FUNDING: 'funding',
  ELIGIBILITY: 'eligibility',
  FIT: 'fit',
  CONFIDENCE: 'confidence',
  COVERAGE: 'coverage',
  READINESS: 'readiness',
  DEADLINE: 'deadline',
}

function emptyState({ totalResults, onResetProfile }) {
  return (
    <div className="match-empty" data-testid="match-empty">
      <h2>No scholarships matched</h2>
      <p>
        Nothing in ScholarZone&rsquo;s catalogue matched this profile exactly. That is a
        fact about the catalogue right now, not a judgement about you.
      </p>
      <button type="button" onClick={onResetProfile}>
        Edit your profile
      </button>
      <p className="match-empty__count">
        {totalResults} scholarship{totalResults === 1 ? ' was' : 's were'} analysed.
      </p>
    </div>
  )
}

export function MatchResults({
  results,
  onRestart,
  reducedMotion = false,
  prefill = {},
  intelligence = null,
  intelligenceError = null,
  onFilterChange,
}) {
const [filters, setFilters] = useState(EMPTY_FILTERS)
  const [compareIds, setCompareIds] = useState([])

  // One place changes the filter state, and it always tells the page. The page owns
  // the single source of truth because the cards, the facet counts and the
  // zero-result alternatives all have to agree; two states is how a filter ends up
  // applied to the list but not to the counts.
  const applyFilters = (next) => {
    setFilters(next)
    onFilterChange?.(next)
  }

  if (!results) return null

  const all = results.results ?? []
  const facets = results.facets

  // Card visibility is rendering, not a business count: which rows to draw. Every
  // number a reader sees about how many there are comes from the API instead - see
  // `countIntelligence.js`.
  const visible = all.filter((result) => matchesFilters(result, filters))
  const authoritativeCount = intelligence?.results?.matched ?? null
  const totalAnalysed = results.summary?.total_candidates ?? null

  // Facet counts describe the returned page, and the note under the filters says
  // so, because "Germany (5)" has to mean five cards are one click away.
  const handleFilterChange = (key, value) => applyFilters({ ...filters, [key]: value })

  // A reset routes through the same setter shape a change does. Routing a
  // different object - which is what used to leave one filter stuck - is the bug
  // this guard exists to prevent.
  const handleResetFilters = () => applyFilters({ ...EMPTY_FILTERS })

  const toggleCompare = (id) => {
    setCompareIds((current) => {
      if (current.includes(id)) return current.filter((item) => item !== id)
      if (current.length >= MAX_COMPARE) return current
      return [...current, id]
    })
  }

  const clearCompare = () => setCompareIds([])

  if (all.length === 0) return emptyState({ totalResults: 0, onResetProfile: onRestart })

  const compared = all.filter((result) => compareIds.includes(result.scholarship_id))

  return (
    <section className="match-results" aria-label="Match results">
      {all.length > 1 ? (
        <MatchFilters
          facets={facets}
          filters={filters}
          onChange={handleFilterChange}
          onReset={handleResetFilters}
          totalShown={visible.length}
          totalAvailable={all.length}
        />
      ) : null}

      <MatchCompare
        results={all}
        selectedIds={compareIds}
        onClear={clearCompare}
      />

      {/*
        The headline number comes from the API and describes the analysed universe,
        which can be larger than the number of cards on screen - the page is
        truncated. Saying "10 scholarships shown" above five cards is simply false,
        so the two figures are stated separately and labelled for what they are.
      */}
      <p className="match-results__summary" role="status" aria-live="polite">
        {authoritativeCount === 0 || visible.length === 0 ? (
          'No scholarships match these filters.'
        ) : authoritativeCount !== null && authoritativeCount !== visible.length ? (
          <>
            {authoritativeCount} of {totalAnalysed ?? authoritativeCount} analysed
            scholarship{authoritativeCount === 1 ? '' : 's'} match
            {authoritativeCount === 1 ? 'es' : ''} your filters.{' '}
            {visible.length} listed here.
          </>
        ) : (
          <>
            {visible.length} scholarship{visible.length === 1 ? '' : 's'} listed.
          </>
        )}
        {prefill.countryFilter ? ` Country filter: ${prefill.countryFilter}.` : ''}
      </p>

      {visible.length > 0 ? (
        <ol className={`match-results__list${reducedMotion ? ' is-reduced-motion' : ''}`}>
          {visible.map((result) => (
            <li key={result.scholarship_id}>
              <MatchCard
                result={result}
                isCompared={compareIds.includes(result.scholarship_id)}
                isCompareSelected={compareIds.includes(result.scholarship_id)}
                compareDisabled={compareIds.length >= MAX_COMPARE}
                onToggleCompare={toggleCompare}
              />
            </li>
          ))}
        </ol>
      ) : (
<div className="match-empty" data-testid="filter-empty">
          <h2>No exact matches</h2>
          <p>
            Nothing in ScholarZone&rsquo;s analysed catalogue matches every filter you
            have selected. These are the changes that would actually bring results
            back, each one changing a single thing and counted over the same
            scholarships.
          </p>
          {intelligenceError ? (
            <p role="status">
              These counts could not be loaded, so no alternatives are shown. A missing
              count is reported as missing rather than estimated.
            </p>
          ) : null}
          <ul className="match-empty__alternatives">
            {alternativesFor(
              // The API's own alternatives when they were requested. Without a
              // response there is nothing to offer, and offering nothing is honest;
              // guessing from the rendered page is what this replaced.
              intelligence?.zero_result?.alternatives ?? [],
              Object.fromEntries(
                FILTER_GROUPS.map((group) => [group.key, group.label]),
              ),
            ).map((option) => (
              <li key={`${option.key}-${option.label}`}>
                <button
                  type="button"
                  onClick={() =>
                    applyFilters({ ...filters, [FILTER_KEY_BY_DIMENSION[option.key] ?? option.key]: '' })
                  }
                >
                  {/*
                    The API's `change_label` is already written for a reader
                    ("Remove \"Degree\""), so it is rendered as-is. Wrapping it again
                    here produced `Remove "Remove "Degree""`, which is both wrong and
                    the kind of thing that survives review because it still reads as
                    a sentence at a glance.
                  */}
                  {option.label} &rarr; {option.count} result
                  {option.count === 1 ? '' : 's'}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {compared.length >= 2 ? (
        <div className="match-results__compare" aria-live="polite">
          {compared.map((result) => (
            <p key={result.scholarship_id} className="match-visually-hidden">
              Selected for comparison: {result.scholarship_name}
            </p>
          ))}
        </div>
      ) : null}

      <footer className="match-results__footer">
        <p>
          Fit is a weighted comparison against your profile, not a prediction of admission.
          Confidence describes how much verified information a record carries, and
          readiness describes how much of the application you can act on today. Missing
          information is never counted as zero.
        </p>
        <button type="button" className="match-results__restart" onClick={onRestart}>
          Edit my profile
        </button>
      </footer>
    </section>
  )
}

export default MatchResults