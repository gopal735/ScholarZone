import { useEffect, useRef } from 'react'
import { useJourneyI18n } from '../i18n/useJourneyI18n.js'
import { JOURNEY_STEPS } from '../lib/progress.js'
import { StatusChip } from './ui/primitives.jsx'

/** Which step each action belongs to, for the "Go to" link text. */
const STEP_LABEL_KEY = {
  find: 'step.find.short',
  eligibility: 'step.eligibility.short',
  documents: 'step.documents.short',
  timeline: 'step.timeline.short',
  costs: 'step.costs.short',
  sources: 'step.sources.short',
  departure: 'step.departure.short',
}

/**
 * The "Next 3 Actions" panel.
 *
 * Rendered as a live region so a change is announced without the student having
 * to go looking for it. The action text is derived from the action's `key` and
 * `params`, never from a user-facing string held in state, which is what keeps
 * the selection logic testable without the dictionary loaded.
 *
 * When there are fewer than three genuine actions, the panel shows three or
 * fewer — never a padded suggestion. An empty result is rendered as a calm
 * statement rather than as an error.
 */
export function NextActions({ actions, onGoToStep }) {
  const { t, both } = useJourneyI18n()
  const liveRef = useRef(null)
  const firstRender = useRef(true)

  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false
      return
    }
    // Announce only a change, never the initial state.
    const node = liveRef.current
    if (node) {
      node.setAttribute('aria-live', 'polite')
    }
  }, [actions])

  const describe = (action) => {
    switch (action.key) {
      case 'empty-shortlist':
        return t('actions.emptyShortlist')
      case 'overdue-target': {
        if (action.params.days === 1) return t('actions.overdueOne').replace('{label}', action.params.label)
        return t('actions.overdue')
          .replace('{label}', action.params.label)
          .replace('{days}', String(action.params.days))
      }
      case 'missing-target':
        return t('actions.missingTarget').replace('{label}', action.params.label)
      case 'document-in-progress':
        return t('actions.documentInProgress').replace('{title}', action.params.title)
      case 'eligibility-gap':
        return t('actions.eligibilityGap')
      case 'unconfirmed-document':
        return t('actions.unconfirmedDocument').replace('{title}', action.params.title)
      case 'shortlist-trust':
        return t('actions.shortlistTrust').replace('{name}', action.params.name)
      case 'cost-provenance':
        return t('actions.costProvenance').replace('{label}', action.params.label)
      case 'source-unchecked':
        return t('actions.sourceUnchecked').replace('{name}', action.params.name)
      case 'departure-task':
        return t('actions.departureTask').replace('{title}', action.params.title)
      default:
        return action.key
    }
  }

  const heading = both('actions.title')

  return (
    <section className="jnext" aria-labelledby="jnext-heading">
      <h2 className="jnext__heading" id="jnext-heading">
        <span className="jbilingual__primary">{heading.primary}</span>
        {heading.secondary ? (
          <span className="jbilingual__secondary" lang="en">
            {heading.secondary}
          </span>
        ) : null}
      </h2>

      <div className="jnext__live" ref={liveRef} role="status">
        {actions.length === 0 ? (
          <div className="jnext__empty">
            <p className="jnext__empty-title">{t('actions.none.title')}</p>
            <p className="jnext__empty-body">{t('actions.none.body')}</p>
          </div>
        ) : (
          <ol className="jnext__list">
            {actions.map((action) => (
              <li className="jnext__item" key={`${action.key}-${JSON.stringify(action.params)}`}>
                <p className="jnext__text">{describe(action)}</p>
                <button type="button" className="jnext__link" onClick={() => onGoToStep(action.stepId)}>
                  {t('actions.goTo')} ·{' '}
                  <span>
                    {STEP_LABEL_KEY[action.stepId] ? t(STEP_LABEL_KEY[action.stepId]) : ''}
                  </span>
                </button>
              </li>
            ))}
          </ol>
        )}
      </div>
    </section>
  )
}

/** A per-step summary line, used in the side rail and the print view. */
export function ChecklistSummary({ summary, activeStepId, onSelectStep }) {
  const { t, both } = useJourneyI18n()
  const heading = both('checklist.title')

  return (
    <section className="jcheck" aria-labelledby="jcheck-heading">
      <h2 className="jcheck__heading" id="jcheck-heading">
        <span className="jbilingual__primary">{heading.primary}</span>
        {heading.secondary ? (
          <span className="jbilingual__secondary" lang="en">
            {heading.secondary}
          </span>
        ) : null}
      </h2>

      {summary.every((row) => row.countable === 0) ? (
        <p className="jcheck__empty">{t('checklist.empty')}</p>
      ) : (
        <ul className="jcheck__list">
          {summary.map((row) => {
            const step = JOURNEY_STEPS.find((candidate) => candidate.id === row.stepId)
            const isActive = row.stepId === activeStepId
            return (
              <li className={`jcheck__row${isActive ? ' is-active' : ''}`} key={row.stepId}>
                <button type="button" className="jcheck__button" onClick={() => onSelectStep(row.stepId)}>
                  <span className="jcheck__index" aria-hidden="true">
                    {String(step.index).padStart(2, '0')}
                  </span>
                  <span className="jcheck__label">{t(`step.${row.stepId}.short`)}</span>
                  <span className="jcheck__count">
                    {row.countable === 0 ? t('checklist.notStarted') : `${row.complete}/${row.countable}`}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

export { StatusChip }
