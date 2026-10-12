import { useState } from 'react'
import { useJourney } from '../../hooks/useJourney.js'
import { useJourneyI18n } from '../../i18n/useJourneyI18n.js'
import { SOURCE_CATEGORIES, SOURCE_STATUSES, normalizeUrl } from '../../lib/journeySchema.js'
import { todayIso } from '../../lib/dates.js'
import { BilingualText, ExternalLink, Field, StatusChip } from '../ui/primitives.jsx'

const CATEGORY_LABEL_KEY = {
  university: 'sources.category.university',
  'scholarship-provider': 'sources.category.scholarship-provider',
  government: 'sources.category.government',
  embassy: 'sources.category.embassy',
  other: 'sources.category.other',
}

const STATUS_TONE = {
  'independently-verified': 'success',
  'checked-by-me': 'info',
  unknown: 'neutral',
}

const STATUS_LABEL_KEY = {
  'independently-verified': 'sources.status.independently-verified',
  'checked-by-me': 'sources.status.checked-by-me',
  unknown: 'sources.status.unknown',
}

/**
 * Module 6 — Official Source Guide.
 *
 * The three statuses are the point of the module, and the middle one is the one
 * a naive implementation gets wrong. `checked-by-me` records *that the student
 * looked*, and nothing more: the action stamps a date and leaves the status
 * wherever the student put it. `independently-verified` is a separate, stronger
 * claim the student can only make deliberately. A button click can never move a
 * source from one to the other, which is why "Mark as re-checked" only writes a
 * date.
 */
export function SourcesModule() {
  const { t, both } = useJourneyI18n()
  const { state, dispatch, actions } = useJourney()
  const [draft, setDraft] = useState({ name: '', category: 'university', url: '', status: 'unknown', note: '' })
  const [urlError, setUrlError] = useState(null)
  const heading = both('sources.title')

  const add = () => {
    const normalized = normalizeUrl(draft.url)
    if (normalized === null) {
      setUrlError(t('sources.invalidUrl'))
      return
    }
    setUrlError(null)
    dispatch({
      type: actions.SOURCES_ADD,
      payload: { ...draft, url: normalized === '' ? '' : normalized, lastChecked: '' },
    })
    setDraft({ name: '', category: 'university', url: '', status: 'unknown', note: '' })
  }

  const update = (id, changes) => dispatch({ type: actions.SOURCES_UPDATE, payload: { id, changes } })
  const remove = (id) => dispatch({ type: actions.SOURCES_REMOVE, payload: { id } })
  const markChecked = (id) => {
    // Only the date moves. The status is untouched, and the copy next to the
    // control says why.
    dispatch({ type: actions.SOURCES_SET_CHECKED, payload: { id, date: todayIso() } })
  }

  return (
    <section className="jmodule" aria-labelledby="sources-title">
      <header className="jmodule__head">
        <h2 className="jmodule__title" id="sources-title">
          <span className="jbilingual__primary">{heading.primary}</span>
          {heading.secondary ? (
            <span className="jbilingual__secondary" lang="en">
              {heading.secondary}
            </span>
          ) : null}
        </h2>
        <p className="jmodule__intro">{t('sources.intro')}</p>
      </header>

      <p className="jnotice jnotice--info">{t('sources.notACertificate')}</p>

      {state.sources.length === 0 ? (
        <div className="jempty">
          <p className="jempty__title">{t('sources.empty.title')}</p>
          <p className="jempty__body">{t('sources.empty.body')}</p>
        </div>
      ) : null}

      <div className="jform">
        <div className="jform__row">
          <Field label={t('sources.name')}>
            {({ id, ...rest }) => (
              <input
                id={id}
                {...rest}
                className="jinput"
                value={draft.name}
                onChange={(event) => setDraft({ ...draft, name: event.target.value })}
              />
            )}
          </Field>
          <Field label={t('sources.category')}>
            {({ id, ...rest }) => (
              <select
                id={id}
                {...rest}
                className="jselect"
                value={draft.category}
                onChange={(event) => setDraft({ ...draft, category: event.target.value })}
              >
                {SOURCE_CATEGORIES.map((value) => (
                  <option value={value} key={value}>
                    {t(CATEGORY_LABEL_KEY[value])}
                  </option>
                ))}
              </select>
            )}
          </Field>
        </div>
        <Field label={t('sources.url')} error={urlError ?? undefined}>
          {({ id, ...rest }) => (
            <input
              id={id}
              {...rest}
              type="url"
              className={`jinput${urlError ? ' jinput--invalid' : ''}`}
              value={draft.url}
              onChange={(event) => {
                setDraft({ ...draft, url: event.target.value })
                setUrlError(null)
              }}
            />
          )}
        </Field>
        <div className="jform__row">
          <Field label={t('sources.status')}>
            {({ id, ...rest }) => (
              <select
                id={id}
                {...rest}
                className="jselect"
                value={draft.status}
                onChange={(event) => setDraft({ ...draft, status: event.target.value })}
              >
                {SOURCE_STATUSES.map((value) => (
                  <option value={value} key={value}>
                    {t(STATUS_LABEL_KEY[value])}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <Field label={t('sources.note')}>
            {({ id, ...rest }) => (
              <input
                id={id}
                {...rest}
                className="jinput"
                value={draft.note}
                onChange={(event) => setDraft({ ...draft, note: event.target.value })}
              />
            )}
          </Field>
        </div>
        <div className="jform__actions">
          <button type="button" className="jbtn jbtn--primary" onClick={add}>
            {t('common.add')}
          </button>
        </div>
      </div>

      <ul className="jcards">
        {state.sources.map((source) => (
          <li className="jcard" key={source.id}>
            <div className="jcard__head">
              <h3 className="jcard__title">{source.name || t('common.unknown')}</h3>
              <StatusChip tone={STATUS_TONE[source.status] ?? 'neutral'}>
                {t(STATUS_LABEL_KEY[source.status]) ?? source.status}
              </StatusChip>
            </div>

            <p className="jcard__category">{t(CATEGORY_LABEL_KEY[source.category]) ?? source.category}</p>

            {source.url ? (
              <p className="jcard__source">
                <ExternalLink href={source.url}>{source.url}</ExternalLink>
              </p>
            ) : (
              <p className="jmuted">{t('sources.invalidUrl')}</p>
            )}

            <dl className="jcard__facts">
              <div>
                <dt>{t('sources.lastChecked')}</dt>
                <dd>
                  {source.lastChecked || (
                    <span className="jmuted">{t('sources.never')}</span>
                  )}
                </dd>
              </div>
            </dl>

            {source.note ? <p className="jcard__notes">{source.note}</p> : null}

            <div className="jcard__controls">
              <label className="jselect-label">
                {t('sources.status')}
                <select
                  className="jselect"
                  value={source.status}
                  onChange={(event) => update(source.id, { status: event.target.value })}
                >
                  {SOURCE_STATUSES.map((value) => (
                    <option value={value} key={value}>
                      {t(STATUS_LABEL_KEY[value])}
                    </option>
                  ))}
                </select>
              </label>
              <button type="button" className="jbtn jbtn--quiet" onClick={() => markChecked(source.id)}>
                {t('sources.recheck')}
              </button>
              <button type="button" className="jbtn jbtn--icon" onClick={() => remove(source.id)} aria-label={`${t('sources.remove')} — ${source.name}`}>
                ×
              </button>
            </div>
            <p className="jcard__hint">{t('sources.recheckHelp')}</p>
          </li>
        ))}
      </ul>
    </section>
  )
}

export { BilingualText }
