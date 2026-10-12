import { useMemo, useState } from 'react'
import { useJourney } from '../../hooks/useJourney.js'
import { useJourneyI18n } from '../../i18n/useJourneyI18n.js'
import { TIMELINE_PROGRESS } from '../../lib/journeySchema.js'
import { byDateCriterion, personalDateStatus } from '../../lib/dates.js'
import { BilingualText, Field, StatusChip } from '../ui/primitives.jsx'

const PROGRESS_LABEL_KEY = {
  not_started: 'timeline.progress.notStarted',
  in_progress: 'timeline.progress.inProgress',
  submitted: 'timeline.progress.submitted',
  done: 'timeline.progress.done',
}

/**
 * Module 4 — Application Timeline.
 *
 * The two dates are separate in storage, in state, in the form, in the sort and
 * in the printed report. Nothing copies one into the other, and the sort
 * criterion is selected rather than defaulted, because "sort by deadline" and
 * "sort by my target" are different questions.
 *
 * Overdue and approaching are evaluated **only** against the student's personal
 * target. An official deadline is a fact recorded from the provider and is never
 * treated as overdue, since the feature has no way to know whether the student
 * has already applied. That is the whole reason the two fields exist.
 */
export function TimelineModule() {
  const { t, both } = useJourneyI18n()
  const { state, dispatch, actions } = useJourney()
  const [sortBy, setSortBy] = useState('personalTarget')
  const [label, setLabel] = useState('')
  const [error, setError] = useState(null)
  const heading = both('timeline.title')

  const ordered = useMemo(
    () => [...state.timeline].sort(byDateCriterion(sortBy)),
    [state.timeline, sortBy],
  )

  const add = () => {
    const clean = label.trim()
    if (clean === '') {
      setError(t('documents.duplicate'))
      return
    }
    setError(null)
    setLabel('')
    dispatch({
      type: actions.TIMELINE_ADD,
      payload: { label: clean, progress: 'not_started', officialDeadline: '', personalTarget: '' },
    })
  }

  const update = (id, changes) => dispatch({ type: actions.TIMELINE_UPDATE, payload: { id, changes } })
  const remove = (id) => dispatch({ type: actions.TIMELINE_REMOVE, payload: { id } })

  const addFromShortlist = (shortlistId) => {
    const entry = state.shortlist.find((item) => item.id === shortlistId)
    if (!entry) return
    dispatch({
      type: actions.TIMELINE_ADD,
      payload: {
        shortlistId: entry.id,
        label: entry.name,
        progress: 'not_started',
        officialDeadline: entry.deadlineDate,
        personalTarget: '',
      },
    })
  }

  const overdueCount = state.timeline.filter(
    (item) => personalDateStatus(item.personalTarget).state === 'overdue',
  ).length

  return (
    <section className="jmodule" aria-labelledby="timeline-title">
      <header className="jmodule__head">
        <h2 className="jmodule__title" id="timeline-title">
          <span className="jbilingual__primary">{heading.primary}</span>
          {heading.secondary ? (
            <span className="jbilingual__secondary" lang="en">
              {heading.secondary}
            </span>
          ) : null}
        </h2>
        <p className="jmodule__intro">{t('timeline.intro')}</p>
      </header>

      <p className="jnotice jnotice--info">{t('timeline.reminderBody')}</p>

      {state.timeline.length === 0 ? (
        <div className="jempty">
          <p className="jempty__title">{t('timeline.empty.title')}</p>
          <p className="jempty__body">{t('timeline.empty.body')}</p>
        </div>
      ) : null}

      <div className="jform jform--inline">
        <Field label={t('timeline.add')} error={error}>
          {({ id, ...rest }) => (
            <input
              id={id}
              {...rest}
              className="jinput"
              value={label}
              onChange={(event) => {
                setLabel(event.target.value)
                setError(null)
              }}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault()
                  add()
                }
              }}
            />
          )}
        </Field>
        <button type="button" className="jbtn jbtn--primary" onClick={add}>
          {t('common.add')}
        </button>
        {state.shortlist.length > 0 ? (
          <label className="jselect-label">
            {t('timeline.fromShortlist')}
            <select
              className="jselect"
              value=""
              onChange={(event) => {
                if (event.target.value) addFromShortlist(event.target.value)
              }}
            >
              <option value="">—</option>
              {state.shortlist
                .filter((entry) => !state.timeline.some((item) => item.shortlistId === entry.id))
                .map((entry) => (
                  <option value={entry.id} key={entry.id}>
                    {entry.name}
                  </option>
                ))}
            </select>
          </label>
        ) : null}
      </div>

      {overdueCount > 0 ? (
        <p className="jnotice jnotice--warning" role="status">
          {overdueCount} · {t('timeline.overdue')}
        </p>
      ) : null}

      <div className="jsort">
        <span className="jsort__label">{t('timeline.sortBy')}</span>
        <label className="jradio">
          <input
            type="radio"
            name="sort"
            value="personalTarget"
            checked={sortBy === 'personalTarget'}
            onChange={() => setSortBy('personalTarget')}
          />
          <span>{t('timeline.sort.personalTarget')}</span>
        </label>
        <label className="jradio">
          <input
            type="radio"
            name="sort"
            value="officialDeadline"
            checked={sortBy === 'officialDeadline'}
            onChange={() => setSortBy('officialDeadline')}
          />
          <span>{t('timeline.sort.officialDeadline')}</span>
        </label>
      </div>

      <ul className="jcards">
        {ordered.map((entry) => {
          const personal = personalDateStatus(entry.personalTarget)
          const tone =
            personal.state === 'overdue'
              ? 'danger'
              : personal.state === 'approaching'
                ? 'warning'
                : personal.state === 'upcoming'
                  ? 'info'
                  : 'neutral'
          return (
            <li className="jcard" key={entry.id}>
              <div className="jcard__head">
                <h3 className="jcard__title">{entry.label || t('common.unknown')}</h3>
                <StatusChip tone={tone}>
                  {personal.state === 'overdue'
                    ? t('timeline.overdue')
                    : personal.state === 'approaching'
                      ? t('timeline.approaching')
                      : personal.state === 'upcoming'
                        ? t('timeline.upcoming')
                        : t('timeline.noDate')}
                </StatusChip>
              </div>

              <dl className="jcard__facts">
                <div>
                  <dt>{t('timeline.officialDeadline')}</dt>
                  <dd>
                    {entry.officialDeadline || (
                      <span className="jmuted">{t('timeline.officialUnknown')}</span>
                    )}
                    {entry.officialDeadlineNote ? ` · ${entry.officialDeadlineNote}` : ''}
                  </dd>
                </div>
                <div>
                  <dt>{t('timeline.personalTarget')}</dt>
                  <dd>
                    {entry.personalTarget || (
                      <span className="jmuted">{t('common.dateNotSet')}</span>
                    )}
                    {personal.state === 'overdue' ? (
                      <span className="jcard__flag"> · {Math.abs(personal.days)} {t('timeline.daysOverdue')}</span>
                    ) : null}
                    {personal.state === 'approaching' ? (
                      <span className="jcard__flag"> · {personal.days} {t('timeline.daysIn')}</span>
                    ) : null}
                  </dd>
                </div>
              </dl>

            <div className="jcard__controls">
              <label className="jselect-label">
                {t('timeline.progress')}
                <select
                  className="jselect"
                  value={entry.progress}
                  onChange={(event) => update(entry.id, { progress: event.target.value })}
                >
                  {TIMELINE_PROGRESS.map((value) => (
                    <option value={value} key={value}>
                      {t(PROGRESS_LABEL_KEY[value])}
                    </option>
                  ))}
                </select>
              </label>
              {/*
                Two independent date controls, deliberately adjacent so the
                separation is visible rather than implied by the storage shape.
                Neither writes to the other's field, and both carry accessible
                names — an unlabelled date picker is unidentifiable to a screen
                reader, and the two look identical.
              */}
              <label className="jselect-label">
                {t('timeline.officialDeadline')}
                <input
                  type="date"
                  className="jinput jinput--date"
                  aria-label={`${t('timeline.officialDeadline')} — ${entry.label}`}
                  value={entry.officialDeadline}
                  onChange={(event) => update(entry.id, { officialDeadline: event.target.value })}
                />
              </label>
              <label className="jselect-label">
                {t('timeline.personalTarget')}
                <input
                  type="date"
                  className="jinput jinput--date"
                  aria-label={`${t('timeline.personalTarget')} — ${entry.label}`}
                  value={entry.personalTarget}
                  onChange={(event) => update(entry.id, { personalTarget: event.target.value })}
                />
              </label>
              <label className="jselect-label">
                {t('timeline.officialDeadlineNote')}
                <input
                  className="jinput"
                  aria-label={`${t('timeline.officialDeadlineNote')} — ${entry.label}`}
                  value={entry.officialDeadlineNote}
                  onChange={(event) => update(entry.id, { officialDeadlineNote: event.target.value })}
                />
              </label>
              <button type="button" className="jbtn jbtn--quiet" onClick={() => remove(entry.id)}>
                {t('timeline.remove')}
              </button>
            </div>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

export { BilingualText }
