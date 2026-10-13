import { useCallback, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useJourney } from '../hooks/useJourney.js'
import { useJourneyI18n, LANGUAGE_MODES } from '../i18n/useJourneyI18n.js'
import {
  JOURNEY_STEPS,
  overallCompletion,
  checklistSummary,
  nextActions,
} from '../lib/progress.js'
import { JourneyStepper } from './JourneyStepper.jsx'
import { NextActions, ChecklistSummary } from './NextActions.jsx'
import { JourneyDisclaimer, StorageNotice } from './JourneyDisclaimer.jsx'
import { DataTools } from './DataTools.jsx'
import { FindExploreModule } from './modules/FindExploreModule.jsx'
import { EligibilityModule } from './modules/EligibilityModule.jsx'
import { DocumentsModule } from './modules/DocumentsModule.jsx'
import { TimelineModule } from './modules/TimelineModule.jsx'
import { CostPlannerModule } from './modules/CostPlannerModule.jsx'
import { SourcesModule } from './modules/SourcesModule.jsx'
import { DepartureModule } from './modules/DepartureModule.jsx'
import { JourneyErrorBoundary } from './JourneyErrorBoundary.jsx'
import { BilingualText } from './ui/primitives.jsx'
import '../journey.css'

const MODULES = {
  find: FindExploreModule,
  eligibility: EligibilityModule,
  documents: DocumentsModule,
  timeline: TimelineModule,
  costs: CostPlannerModule,
  sources: SourcesModule,
  departure: DepartureModule,
}

/**
 * The journey page.
 *
 * The layout is a three-region document: the stepper on the left, the active
 * module in the middle, and a right rail carrying the next actions, the
 * checklist summary and the data tools. On a narrow viewport the rail moves
 * below the module rather than beside it, which is what keeps the module's own
 * controls full-width and touch-sized.
 *
 * Progress is read from `overallCompletion` over the same normalised document
 * the modules edit, so the header figure, the stepper rails and the side rail
 * cannot disagree — there is exactly one calculation and every surface reads it.
 */
export function JourneyPage() {
  const { t, both, mode } = useJourneyI18n()
  const { state, setLanguage, storage } = useJourney()
  /**
   * The active step is initialised from the URL, so a reader can be sent to
   * "the timeline" rather than to the top of a workspace they then have to find
   * their way through. The URL is the starting point only: the stepper owns the
   * state afterwards, because a workspace that rewrites its address bar on every
   * click spends its time fighting the router.
   *
   * An unknown segment falls back to the first step rather than rendering
   * nothing, so a stale link still lands somewhere useful.
   */
  const { stepId: stepIdParam } = useParams()
  const initialStep = JOURNEY_STEPS.some((step) => step.id === stepIdParam) ? stepIdParam : JOURNEY_STEPS[0].id
  const [activeStepId, setActiveStepId] = useState(initialStep)

  const completion = useMemo(() => overallCompletion(state), [state])
  const summary = useMemo(() => checklistSummary(state), [state])
  const actions = useMemo(() => nextActions(state, { limit: 3 }), [state])

  const countsByStep = useMemo(() => {
    const out = {}
    for (const row of summary) {
      out[row.stepId] = row.percent
      out[`${row.stepId}:counts`] = { complete: row.complete, countable: row.countable }
    }
    return out
  }, [summary])

  const activeStep = JOURNEY_STEPS.find((step) => step.id === activeStepId) ?? JOURNEY_STEPS[0]
  const ActiveModule = MODULES[activeStep.id]
  const finishedSteps = summary.filter((row) => row.countable > 0 && row.complete === row.countable).length

  const goToStep = useCallback((stepId) => {
    setActiveStepId(stepId)
    if (typeof document !== 'undefined') {
      const node = document.getElementById('journey-main')
      if (node && typeof node.focus === 'function') node.focus()
    }
  }, [])

  const title = both('app.title')
  const tagline = both('app.tagline')

  return (
    <div className="jpage">
      <header className="jpage__head">
        <p className="jpage__eyebrow">
          <BilingualText primary={t('nav.new')} secondary={mode === 'both' ? 'New' : null} />
        </p>
        <h1 className="jpage__title">
          <span className="jbilingual__primary">{title.primary}</span>
          {title.secondary ? (
            <span className="jbilingual__secondary" lang="en">
              {title.secondary}
            </span>
          ) : null}
        </h1>
        <p className="jpage__tagline">
          <BilingualText primary={tagline.primary} secondary={tagline.secondary} />
        </p>

        <div className="jpage__bar">
          <div className="jprogress">
            <div className="jprogress__meta">
              <span className="jprogress__label">{t('header.completion')}</span>
              <span className="jprogress__value">{completion}% {t('header.complete')}</span>
            </div>
            <div
              className="jprogress__track"
              role="progressbar"
              aria-valuenow={completion}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-labelledby="jprogress-label"
            >
              <div className="jprogress__fill" style={{ width: `${completion}%` }} />
            </div>
            <span className="sz-sr-only" id="jprogress-label">
              {t('header.completion')}
            </span>
          </div>

          <p className="jpage__steps-done">
            {finishedSteps} {t('header.stepsDone')}
          </p>

          <fieldset className="jlang">
            <legend className="jlang__legend">{t('language.label')}</legend>
            {LANGUAGE_MODES.map((value) => (
              <label className={`jlang__option${mode === value ? ' is-active' : ''}`} key={value}>
                <input
                  type="radio"
                  name="language"
                  value={value}
                  checked={mode === value}
                  onChange={() => setLanguage(value)}
                />
                <span>
                  {value === 'bn'
                    ? t('language.banglaOnly')
                    : value === 'en'
                      ? t('language.englishOnly')
                      : t('language.bothLabel')}
                </span>
              </label>
            ))}
          </fieldset>
        </div>
      </header>

      <StorageNotice problem={storage.problem} />

      <div className="jpage__body">
        <div className="jpage__rail">
          <JourneyStepper
            steps={JOURNEY_STEPS}
            activeStepId={activeStepId}
            onSelectStep={goToStep}
            completionByStep={countsByStep}
          />
        </div>

        <main className="jpage__main" id="journey-main" tabIndex={-1} aria-labelledby="journey-current-title">
          <p className="jpage__crumb">
            {t('nav.step')} {activeStep.index} {t('nav.of')} {JOURNEY_STEPS.length}
          </p>
          <h2 className="sz-sr-only" id="journey-current-title">
            {t(`step.${activeStep.id}`)}
          </h2>
          <JourneyErrorBoundary key={activeStep.id}>
            <ActiveModule />
          </JourneyErrorBoundary>

          <nav className="jpage__pager" aria-label={t('nav.stepNav')}>
            <button
              type="button"
              className="jbtn jbtn--quiet"
              disabled={activeStep.index === 1}
              onClick={() => goToStep(JOURNEY_STEPS[activeStep.index - 2].id)}
            >
              {t('nav.previous')}
            </button>
            <button
              type="button"
              className="jbtn jbtn--primary"
              disabled={activeStep.index === JOURNEY_STEPS.length}
              onClick={() => goToStep(JOURNEY_STEPS[activeStep.index].id)}
            >
              {t('nav.next')}
            </button>
          </nav>

          <div className="jpage__tools">
            <DataTools />
          </div>
        </main>

        <aside className="jpage__side" aria-label={t('checklist.title')}>
          <NextActions actions={actions} onGoToStep={goToStep} />
          <ChecklistSummary summary={summary} activeStepId={activeStepId} onSelectStep={goToStep} />
        </aside>
      </div>

      <JourneyDisclaimer />
    </div>
  )
}

export default JourneyPage
