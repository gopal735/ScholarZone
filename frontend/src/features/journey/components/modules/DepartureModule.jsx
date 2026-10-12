import { useState } from 'react'
import { useJourney } from '../../hooks/useJourney.js'
import { useJourneyI18n } from '../../i18n/useJourneyI18n.js'
import { buildDepartureTemplateRows } from '../../data/seed.js'
import { DEPARTURE_PROGRESS } from '../../lib/journeySchema.js'
import { BilingualText } from '../ui/primitives.jsx'

const PROGRESS_LABEL_KEY = {
  not_started: 'departure.progress.notStarted',
  in_progress: 'departure.progress.inProgress',
  done: 'departure.progress.done',
}

/**
 * Module 7 — After-Offer & Departure.
 *
 * A generic checklist with no promises. Nothing here states or implies an
 * admission outcome, an award, a visa decision, a processing time or a departure
 * date, and the module carries a standing line saying whose decision each of
 * those actually is.
 *
 * The template rows are generic categories of work, not requirements: they do
 * not count against progress until the student keeps them, and removing a row is
 * the documented way to say "this does not apply to me".
 */
export function DepartureModule() {
  const { t, both } = useJourneyI18n()
  const { state, dispatch, actions } = useJourney()
  const [title, setTitle] = useState('')
  const heading = both('departure.title')

  const addCustom = () => {
    const clean = title.trim()
    if (clean === '') return
    dispatch({ type: actions.DEPARTURE_ADD, payload: { title: clean, progress: 'not_started', template: false } })
    setTitle('')
  }

  const addTemplate = () => {
    for (const row of buildDepartureTemplateRows()) {
      dispatch({ type: actions.DEPARTURE_ADD, payload: { ...row } })
    }
  }

  const update = (id, changes) => dispatch({ type: actions.DEPARTURE_UPDATE, payload: { id, changes } })
  const remove = (id) => dispatch({ type: actions.DEPARTURE_REMOVE, payload: { id } })

  return (
    <section className="jmodule" aria-labelledby="departure-title">
      <header className="jmodule__head">
        <h2 className="jmodule__title" id="departure-title">
          <span className="jbilingual__primary">{heading.primary}</span>
          {heading.secondary ? (
            <span className="jbilingual__secondary" lang="en">
              {heading.secondary}
            </span>
          ) : null}
        </h2>
        <p className="jmodule__intro">{t('departure.intro')}</p>
      </header>

      <p className="jnotice jnotice--warning">{t('departure.notAPromise')}</p>

      {state.departure.length === 0 ? (
        <div className="jempty">
          <p className="jempty__title">{t('departure.empty.title')}</p>
          <p className="jempty__body">{t('departure.empty.body')}</p>
        </div>
      ) : null}

      <div className="jlist__actions">
        <button type="button" className="jbtn jbtn--quiet" onClick={addTemplate}>
          {t('departure.addTemplate')}
        </button>
      </div>

      <div className="jform jform--inline">
        <label className="jfield">
          <span className="jfield__label">{t('departure.addCustom')}</span>
          <input
            className="jinput"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault()
                addCustom()
              }
            }}
          />
        </label>
        <button type="button" className="jbtn jbtn--primary" onClick={addCustom}>
          {t('common.add')}
        </button>
      </div>

      <p className="jmodule__count">
        {state.departure.length} {t('departure.countLabel')}
      </p>

      <ul className="jcards">
        {state.departure.map((task) => (
          <li className="jcard" key={task.id}>
            <div className="jcard__head">
              <h3 className="jcard__title">{task.title || t('common.unknown')}</h3>
            </div>
            {task.template ? <p className="jmuted">{t('documents.templateBadge')}</p> : null}
            {task.note ? <p className="jcard__notes">{task.note}</p> : null}
            <div className="jcard__controls">
              <label className="jselect-label">
                {t('departure.progress')}
                <select
                  className="jselect"
                  value={task.progress}
                  onChange={(event) => update(task.id, { progress: event.target.value })}
                >
                  {DEPARTURE_PROGRESS.map((value) => (
                    <option value={value} key={value}>
                      {t(PROGRESS_LABEL_KEY[value])}
                    </option>
                  ))}
                </select>
              </label>
              <label className="jselect-label">
                {t('departure.note')}
                <input
                  className="jinput"
                  value={task.note}
                  onChange={(event) => update(task.id, { note: event.target.value })}
                />
              </label>
              <button type="button" className="jbtn jbtn--icon" onClick={() => remove(task.id)} aria-label={`${t('departure.remove')} — ${task.title}`}>
                ×
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

export { BilingualText }
