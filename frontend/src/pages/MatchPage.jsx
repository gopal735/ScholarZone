import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { useMatchProfile, MATCH_MODE, MATCH_STATUS } from '../hooks/useMatchProfile'
import { useCountIntelligence } from '../hooks/useCountIntelligence'
import { useReducedMotion } from '../hooks/useReducedMotion'
import { fetchMatchProfileOptions } from '../services/matchService'
import CountAnalytics from '../components/match/CountAnalytics'
import MatchProfileForm from '../components/match/MatchProfileForm'
import MatchResultSummary from '../components/match/MatchResultSummary'
import MatchResults from '../components/match/MatchResults'
import ProfileStrengthPanel from '../components/match/ProfileStrengthPanel'
import ProfileTextParser from '../components/match/ProfileTextParser'
import HowThisIsCalculated from '../components/match/HowThisIsCalculated'
import { HowToUse } from '../features/tutorials'
import './MatchPage.css'

const DEEP_LINK_KEYS = {
  citizenship: 'citizenship',
  field: 'intendedField',
  degree: 'intendedDegreeLevel',
  country: 'countryFilter',
}

export function MatchPage() {
  const {
    status,
    mode,
    isBusy,
    profile,
    fieldErrors,
    changeMode,
    setField,
    togglePreferredCountry,
    description,
    updateDescription,
    parsed,
    isParsing,
    parseError,
    parseDescription,
    dismissParsed,
    results,
    error,
    submit,
    reset,
    restore,
  } = useMatchProfile()

  const [searchParams, setSearchParams] = useSearchParams()
  const [options, setOptions] = useState(null)
  const [optionsError, setOptionsError] = useState(null)
  const [optionsAttempt, setOptionsAttempt] = useState(0)
  const [countryFilter, setCountryFilter] = useState('')
  const reducedMotion = useReducedMotion()

  // The browser tab read "ScholarZone · Where Ambition Meets Opportunity" on
  // every route, so a tab left open on /match was indistinguishable from the
  // home page. This sets the tab title for this route only and puts it back on
  // the way out; the rest of the app's titles are left exactly as they are.
  useEffect(() => {
    const previous = document.title
    document.title = 'Match · ScholarZone'
    return () => {
      document.title = previous
    }
  }, [])

  // The options request is what fills the form's selects and the country
  // datalist. When it fails the form is NOT withdrawn — citizenship is a free
  // input and every select degrades to its "not decided yet" option, so the
  // page stays usable and the answer already given is kept.
  //
  // What a failed request must never do is leave the student with no way back:
  // this used to print "Refresh the page to try again", which throws away the
  // profile draft. The attempt counter makes Try again re-run this effect, so
  // the retry is an in-place one. The status goes to the developer console and
  // a plain reference line; the raw error never reaches the page.
  useEffect(() => {
    let cancelled = false
    fetchMatchProfileOptions()
      .then((payload) => {
        if (cancelled) return
        setOptions(payload)
        setOptionsError(null)
      })
      .catch((error) => {
        if (cancelled) return
        console.error('Match options request failed:', error)
        const status = typeof error?.status === 'number' ? error.status : null
        setOptionsError({
          message:
            'ScholarZone could not load the answer lists for this form, so the dropdowns are empty for now.',
          status,
        })
      })
    return () => {
      cancelled = true
    }
  }, [optionsAttempt])

  // A deep link fills the profile once, on arrival, and is then cleared from the
  // URL. Leaving it there would re-apply the link over a profile the student has
  // since edited, every time they navigated back to the page.
  const appliedLink = useRef(false)
  useEffect(() => {
    const link = searchParams.get('link')
    if (!link || appliedLink.current) return
    appliedLink.current = true
    let payload = null
    try {
      payload = JSON.parse(link)
    } catch {
      // A malformed link is not worth surfacing; the page still works without it.
      setSearchParams({}, { replace: true })
      return
    }
    if (payload && typeof payload === 'object') {
      Object.entries(DEEP_LINK_KEYS).forEach(([sourceKey, targetKey]) => {
        if (typeof payload[sourceKey] === 'string' && payload[sourceKey] !== '') {
          setField(targetKey, payload[sourceKey])
        }
      })
    }
    setSearchParams({}, { replace: true })
  }, [searchParams, setSearchParams, setField])

  const handleSubmit = (event) => {
    event?.preventDefault?.()
    const next = { ...profile }
    if (countryFilter !== '') next.countryFilter = countryFilter
    submit(next)
  }

  const showForm = status !== MATCH_STATUS.SUCCESS
  const showResults = status === MATCH_STATUS.SUCCESS || status === MATCH_STATUS.EMPTY

  // The filter state the counting engine is asked about. Held here rather than inside
  // the results component so one state drives the cards, the facet counts and the
  // zero-result alternatives together. Two states is how a filter ends up applied to
  // the list but not to the counts.
  const [countFilters, setCountFilters] = useState({})
  const counts = useCountIntelligence(
    showResults ? profile : null,
    countFilters,
    { asOf: results?.as_of },
  )

  return (
    // A section, not a main: Layout already renders the document's single
    // main landmark, and a second one inside it is invalid HTML that leaves
    // assistive tech with two "main" landmarks to choose between.
        <section className="match-page">
          {/* Contextual help, above the form. The profile form is the primary
              task here, so the guide sits above it rather than between the form
              and the run button. */}
          <HowToUse route="/match" />
          <div className="match-page__inner">
        <h1 className="match-page__title">Match</h1>
        <p className="match-page__lede">
          Tell ScholarZone about yourself and it will check every published eligibility rule
          first, then rank what you can actually apply for.
        </p>

        {optionsError ? (
          <div className="match-page__error match-page__error--options" role="alert" data-testid="match-options-error">
            <p>{optionsError.message} Your answers stay on this device, so fill the form in and try again.</p>
            <p className="match-page__error-status">
              {optionsError.status ? `Reference: HTTP ${optionsError.status}. ` : ''}
              Details are in your browser console.
            </p>
            <button
              type="button"
              className="match-page__error-action"
              onClick={() => setOptionsAttempt((attempt) => attempt + 1)}
            >
              Try again
            </button>
          </div>
        ) : null}

        {status === MATCH_STATUS.CALCULATING ? (
          <section
            className="match-loading"
            role="status"
            aria-live="polite"
            data-testid="match-loading"
          >
            <div className="match-loading__bar" aria-hidden="true">
              <span />
            </div>
            <p>Checking every published eligibility rule before scoring.</p>
            <ol className="match-loading__steps">
              <li>Loading your profile options</li>
              <li>Reading published requirements from each scholarship</li>
              <li>Applying the eligibility gate</li>
              <li>Scoring what survived the gate</li>
            </ol>
          </section>
        ) : null}

        {status === MATCH_STATUS.ERROR ? (
          <div className="match-page__error" role="alert" data-testid="match-error">
            <p>{error?.message ?? 'Something went wrong.'}</p>
            {error?.status ? (
              <p className="match-page__error-status">
                Reference: HTTP {error.status}
              </p>
            ) : null}
            <button type="button" className="match-page__error-action" onClick={handleSubmit}>
              Try again
            </button>
          </div>
        ) : null}

        {showForm ? (
          <>
            <ProfileTextParser
              value={description}
              onChange={updateDescription}
              onParse={parseDescription}
              onDismiss={dismissParsed}
              parsed={parsed}
              isParsing={isParsing}
              error={parseError}
              reducedMotion={reducedMotion}
            />

            <MatchProfileForm
              mode={mode}
              onModeChange={(next) => changeMode(next === 'deep' ? MATCH_MODE.DEEP : MATCH_MODE.QUICK)}
              profile={profile}
              options={options}
              onChange={setField}
              onToggleCountry={togglePreferredCountry}
              onSubmit={handleSubmit}
              isBusy={isBusy}
              fieldErrors={fieldErrors}
            >
              <div className="match-form__country">
                <label className="match-field__label" htmlFor="match-country-filter">
                  Narrow the catalogue to one country (optional)
                </label>
                <input
                  className="match-control"
                  id="match-country-filter"
                  list="match-country-filter-options"
                  value={countryFilter}
                  aria-invalid={fieldErrors.countryFilter ? 'true' : undefined}
                  aria-describedby={
                    fieldErrors.countryFilter ? 'match-country-filter-error' : undefined
                  }
                  onChange={(event) => setCountryFilter(event.target.value)}
                  data-testid="country-filter"
                />
                <datalist id="match-country-filter-options">
                  {(options?.countries ?? []).map((name) => (
                    <option key={name} value={name} />
                  ))}
                </datalist>
                {fieldErrors.countryFilter ? (
                  <p className="match-form__error" id="match-country-filter-error" role="alert">
                    {fieldErrors.countryFilter}
                  </p>
                ) : null}
              </div>
            </MatchProfileForm>

            {results?.profile_strength ? (
              <ProfileStrengthPanel strength={results.profile_strength} />
            ) : null}
          </>
        ) : null}

        {showResults && results ? (
          <>
            <MatchResultSummary summary={results.summary} />

            {results.profile_strength ? (
              <ProfileStrengthPanel strength={results.profile_strength} />
            ) : null}

            <MatchResults
              results={results}
              reducedMotion={reducedMotion}
              prefill={{ countryFilter: countryFilter || profile.countryFilter }}
              intelligence={counts.intelligence}
              intelligenceError={counts.error}
              onFilterChange={setCountFilters}
              onRestart={() => {
                setCountryFilter('')
                restore()
              }}
            />

            {/* Collapsed by default. The counts, the integrity verdict and where they
                came from are one click away for anyone who wants them, and out of the
                way for anyone who does not. */}
            <CountAnalytics
              intelligence={counts.intelligence}
              error={counts.error}
              status={counts.status}
            />

            <HowThisIsCalculated
              explanation={results.explanation}
              results={results.results}
            />

            <section className="match-results__reset">
              <h2>Start again</h2>
              <p>Clears the profile on this device and the results, and returns to step one.</p>
              <button type="button" className="match-results__restart" onClick={reset} data-testid="match-reset">
                Reset my profile
              </button>
            </section>
          </>
        ) : null}
      </div>
    </section>
  )
}

export default MatchPage
