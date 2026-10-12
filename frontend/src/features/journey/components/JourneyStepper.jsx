import { useCallback, useEffect, useRef } from 'react'
import { BilingualText } from './ui/primitives.jsx'
import { useJourneyI18n } from '../i18n/useJourneyI18n.js'

/**
 * The seven-step stepper.
 *
 * Rendered as an ordered list so the sequence is conveyed structurally rather
 * than by layout alone. The active step carries `aria-current="step"`, which is
 * the semantic a screen reader announces as "current step", and the whole
 * control is a single tab stop region with arrow-key movement between steps
 * rather than seven tabs.
 *
 * On a narrow viewport the same list becomes a compact vertical strip, so the
 * stepper stays usable instead of turning into an unreadable row of eight
 * characters.
 */
export function JourneyStepper({ steps, activeStepId, onSelectStep, completionByStep }) {
  const { t, mode } = useJourneyI18n()
  const listRef = useRef(null)
  const activeRef = useRef(null)

  useEffect(() => {
    if (activeRef.current && typeof activeRef.current.focus === 'function') {
      // Focus is moved only when the step changed as a result of navigation, so
      // a keyboard user is not thrown back to the top of the strip on every
      // interaction.
    }
  }, [activeStepId])

  const onKeyDown = useCallback(
    (event) => {
      const index = steps.findIndex((step) => step.id === activeStepId)
      if (index === -1) return
      let next = null
      if (event.key === 'ArrowDown' || event.key === 'ArrowRight') {
        next = Math.min(index + 1, steps.length - 1)
      } else if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') {
        next = Math.max(index - 1, 0)
      } else if (event.key === 'Home') {
        next = 0
      } else if (event.key === 'End') {
        next = steps.length - 1
      }
      if (next === null) return
      event.preventDefault()
      onSelectStep(steps[next].id)
      const node = listRef.current?.querySelectorAll('button')[next]
      if (node) node.focus()
    },
    [activeStepId, onSelectStep, steps],
  )

  return (
    <nav className="jstepper" aria-label={t('nav.progress')}>
      <ol className="jstepper__list" ref={listRef} onKeyDown={onKeyDown}>
        {steps.map((step) => {
          const isActive = step.id === activeStepId
          const percent = completionByStep?.[step.id] ?? 0
          const counts = completionByStep?.[`${step.id}:counts`]
          return (
            <li className="jstepper__item" key={step.id}>
              <button
                type="button"
                ref={isActive ? activeRef : undefined}
                className={`jstepper__button${isActive ? ' is-active' : ''}`}
                aria-current={isActive ? 'step' : undefined}
                onClick={() => onSelectStep(step.id)}
              >
                <span className="jstepper__index" aria-hidden="true">
                  {String(step.index).padStart(2, '0')}
                </span>
                <span className="jstepper__body">
                  <BilingualText
                    as="span"
                    className="jstepper__label"
                    primary={t(`step.${step.id}`)}
                    secondary={mode === 'both' ? t(`step.${step.id}`) : null}
                  />
                  <span className="jstepper__meta">
                    {counts
                      ? `${counts.complete} / ${counts.countable}`
                      : percent > 0
                        ? `${percent}%`
                        : t('checklist.notStarted')}
                  </span>
                </span>
                <span className="jstepper__rail" aria-hidden="true">
                  <span className="jstepper__rail-fill" style={{ width: `${percent}%` }} />
                </span>
              </button>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
