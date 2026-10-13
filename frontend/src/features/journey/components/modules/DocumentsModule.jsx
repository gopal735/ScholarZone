import { useState } from 'react'
import { useJourney } from '../../hooks/useJourney.js'
import { useJourneyI18n } from '../../i18n/useJourneyI18n.js'
import { buildDocumentTemplateRows } from '../../data/seed.js'
import { DOCUMENT_PROGRESS, DOCUMENT_REQUIREMENTS } from '../../lib/journeySchema.js'
import { isIsoDate, todayIso } from '../../lib/dates.js'
import { BilingualText, Field, StatusChip } from '../ui/primitives.jsx'

const PROGRESS_LABEL_KEY = {
  not_started: 'documents.progress.notStarted',
  in_progress: 'documents.progress.inProgress',
  done: 'documents.progress.done',
}
const REQUIREMENT_LABEL_KEY = {
  mandatory: 'documents.requirement.mandatory',
  conditional: 'documents.requirement.conditional',
  unconfirmed: 'documents.requirement.unconfirmed',
}

/**
 * Module 3 — Document Studio.
 *
 * A checklist, not an uploader. Nothing is transmitted anywhere, and the module
 * says so, because a student who believes documents were uploaded would use the
 * tool very differently.
 *
 * Every seeded row arrives as `unconfirmed` + `template`, and an unconfirmed row
 * is excluded from progress. That is the mechanism that lets the feature offer a
 * starter checklist without ever asserting that a given document is required for
 * a given programme: until the student confirms it, it does not count for or
 * against them.
 */
export function DocumentsModule() {
  const { t, both } = useJourneyI18n()
  const { state, dispatch, actions } = useJourney()
  const [title, setTitle] = useState('')
  const [error, setError] = useState(null)
  const [expiryError, setExpiryError] = useState({})
  const heading = both('documents.title')

  const addCustom = () => {
    const clean = title.trim()
    if (clean === '') {
      setError(t('documents.duplicate'))
      return
    }
    if (state.documents.some((item) => item.title.trim().toLowerCase() === clean.toLowerCase())) {
      setError(t('documents.duplicate'))
      return
    }
    setError(null)
    setTitle('')
    dispatch({
      type: actions.DOCUMENTS_ADD,
      payload: { title: clean, requirement: 'unconfirmed', progress: 'not_started', template: false },
    })
  }

  const addTemplate = () => {
    const rows = buildDocumentTemplateRows()
    for (const row of rows) {
      dispatch({ type: actions.DOCUMENTS_ADD, payload: { ...row } })
    }
  }

  const update = (id, changes) => dispatch({ type: actions.DOCUMENTS_UPDATE, payload: { id, changes } })
  const remove = (id) => dispatch({ type: actions.DOCUMENTS_REMOVE, payload: { id } })

  const confirmed = state.documents.filter((item) => !item.template).length

  const onExpiryChange = (id, value) => {
    // A typed expiry is kept as the student typed it, but a value that is not a
    // real date is reported inline rather than silently discarded, because a
    // silently-dropped expiry is the failure that matters for a passport.
    if (value === '') {
      setExpiryError((prev) => ({ ...prev, [id]: null }))
      update(id, { expiryDate: '' })
      return
    }
    if (!isIsoDate(value)) {
      setExpiryError((prev) => ({ ...prev, [id]: t('sources.invalidUrl') }))
      return
    }
    setExpiryError((prev) => ({ ...prev, [id]: null }))
    update(id, { expiryDate: value })
  }

  return (
    <section className="jmodule" aria-labelledby="documents-title">
      <header className="jmodule__head">
        <h2 className="jmodule__title" id="documents-title">
          <span className="jbilingual__primary">{heading.primary}</span>
          {heading.secondary ? (
            <span className="jbilingual__secondary" lang="en">
              {heading.secondary}
            </span>
          ) : null}
        </h2>
        <p className="jmodule__intro">{t('documents.intro')}</p>
      </header>

      <p className="jnotice jnotice--info">{t('documents.notUploaded')}</p>

      <div className="jlist__actions">
        <button type="button" className="jbtn jbtn--quiet" onClick={addTemplate}>
          {t('documents.addTemplate')}
        </button>
      </div>

      <div className="jform jform--inline">
        <Field label={t('documents.addCustom')} error={error}>
          {({ id, ...rest }) => (
            <input
              id={id}
              {...rest}
              className="jinput"
              value={title}
              onChange={(event) => {
                setTitle(event.target.value)
                setError(null)
              }}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault()
                  addCustom()
                }
              }}
            />
          )}
        </Field>
        <button type="button" className="jbtn jbtn--primary" onClick={addCustom}>
          {t('common.add')}
        </button>
      </div>

      {state.documents.length === 0 ? (
        <div className="jempty">
          <p className="jempty__title">{t('documents.empty.title')}</p>
          <p className="jempty__body">{t('documents.empty.body')}</p>
        </div>
      ) : null}

      <p className="jmodule__count">
        {state.documents.length} {t('documents.countLabel')} · {confirmed} {t('documents.confirmedCount')}
      </p>

      <table className="jtable">
        <thead>
          <tr>
            <th scope="col">{t('documents.title2')}</th>
            <th scope="col">{t('documents.requirement')}</th>
            <th scope="col">{t('documents.progress')}</th>
            <th scope="col">{t('documents.expiry')}</th>
            <th scope="col">{t('common.remove')}</th>
          </tr>
        </thead>
        <tbody>
          {state.documents.map((item) => {
            const expired = isIsoDate(item.expiryDate) && item.expiryDate < todayIso()
            return (
              <tr className={`jtable__row${item.template ? ' jtable__row--template' : ''}`} key={item.id}>
                <th scope="row" className="jtable__title" data-label={t('documents.title2')}>
                  <span className="jtable__title-text">{item.title || t('common.unknown')}</span>
                  {item.template ? <StatusChip tone="warning">{t('documents.templateBadge')}</StatusChip> : null}
                  {expired ? <StatusChip tone="danger">{t('documents.expired')}</StatusChip> : null}
                  {item.note ? <span className="jtable__note">{item.note}</span> : null}
                </th>
                <td data-label={t('documents.requirement')}>
                  <select
                    className="jselect"
                    aria-label={`${t('documents.requirement')} — ${item.title}`}
                    value={item.requirement}
                    onChange={(event) => update(item.id, { requirement: event.target.value, template: false })}
                  >
                    {DOCUMENT_REQUIREMENTS.map((value) => (
                      <option value={value} key={value}>
                        {t(REQUIREMENT_LABEL_KEY[value])}
                      </option>
                    ))}
                  </select>
                  {item.requirement === 'unconfirmed' ? (
                    <span className="jtable__hint">{t('documents.requirementHint')}</span>
                  ) : null}
                </td>
                <td data-label={t('documents.progress')}>
                  <select
                    className="jselect"
                    aria-label={`${t('documents.progress')} — ${item.title}`}
                    value={item.progress}
                    onChange={(event) => update(item.id, { progress: event.target.value })}
                  >
                    {DOCUMENT_PROGRESS.map((value) => (
                      <option value={value} key={value}>
                        {t(PROGRESS_LABEL_KEY[value])}
                      </option>
                    ))}
                  </select>
                </td>
                <td data-label={t('documents.expiry')}>
                  <input
                    type="date"
                    className="jinput jinput--date"
                    aria-label={`${t('documents.expiry')} — ${item.title}`}
                    value={item.expiryDate}
                    onChange={(event) => onExpiryChange(item.id, event.target.value)}
                  />
                  {expiryError[item.id] ? <span className="jtable__hint">{expiryError[item.id]}</span> : null}
                </td>
                <td data-label={t('common.remove')}>
                  <button
                    type="button"
                    className="jbtn jbtn--icon"
                    onClick={() => remove(item.id)}
                    aria-label={`${t('documents.remove')} — ${item.title}`}
                  >
                    ×
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </section>
  )
}

export { BilingualText }
