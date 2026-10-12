import { useState } from 'react'
import { useJourney } from '../../hooks/useJourney.js'
import { useJourneyI18n } from '../../i18n/useJourneyI18n.js'
import { BilingualText, ExternalLink, Field, StatusChip } from '../ui/primitives.jsx'
import { SAMPLE_SHORTLIST_ENTRY } from '../../data/seed.js'
import { TRUST_STATUSES } from '../../lib/journeySchema.js'

const TRUST_TONE = {
  verified: 'success',
  'self-reported': 'info',
  'needs-review': 'warning',
}

/** Trust statuses as options, in the order a student would work through them. */
const TRUST_OPTIONS = [
  { value: 'needs-review', labelKey: 'find.trust.needs-review', helpKey: 'find.trust.needsReviewHelp' },
  { value: 'self-reported', labelKey: 'find.trust.self-reported', helpKey: 'find.trust.self-reportedHelp' },
  { value: 'verified', labelKey: 'find.trust.verified', helpKey: 'find.trust.verifiedHelp' },
]

/**
 * Module 1 — Find & Explore.
 *
 * The trust status is the heart of this module. A scholarship is "Verified" only
 * when the student has recorded a source and marked it checked; having a URL is
 * not verification, and appearing in sample data is certainly not. The status is
 * set by the student and defaults to `needs-review`, which is the honest default
 * for anything they have written down but not yet traced.
 *
 * The sample entry is rendered with a persistent badge and an explanation, so a
 * student cannot mistake it for an opportunity they added.
 */
export function FindExploreModule() {
  const { t, both } = useJourneyI18n()
  const { state, dispatch, actions } = useJourney()
  const [draft, setDraft] = useState({
    name: '',
    country: '',
    degree: '',
    deadlineDate: '',
    deadlineNote: '',
    sourceUrl: '',
    notes: '',
    trust: 'needs-review',
  })
  const [showForm, setShowForm] = useState(false)
  const [error, setError] = useState(null)
  const heading = both('find.title')

  const addEntry = () => {
    if (draft.name.trim() === '') {
      setError(t('documents.duplicate'))
      setShowForm(true)
      return
    }
    setError(null)
    dispatch({ type: actions.SHORTLIST_ADD, payload: draft })
    setDraft({ name: '', country: '', degree: '', deadlineDate: '', deadlineNote: '', sourceUrl: '', notes: '', trust: 'needs-review' })
    setShowForm(false)
  }

  const addSample = () => {
    dispatch({ type: actions.SHORTLIST_ADD, payload: { ...SAMPLE_SHORTLIST_ENTRY, sample: true } })
  }

  const update = (id, changes) => {
    dispatch({ type: actions.SHORTLIST_UPDATE, payload: { id, changes } })
  }

  const remove = (id) => {
    dispatch({ type: actions.SHORTLIST_REMOVE, payload: { id } })
  }

  return (
    <section className="jmodule" aria-labelledby="find-title">
      <header className="jmodule__head">
        <h2 className="jmodule__title" id="find-title">
          <span className="jbilingual__primary">{heading.primary}</span>
          {heading.secondary ? (
            <span className="jbilingual__secondary" lang="en">
              {heading.secondary}
            </span>
          ) : null}
        </h2>
        <p className="jmodule__intro">{t('find.intro')}</p>
      </header>

      {state.shortlist.length === 0 && !showForm ? (
        <div className="jempty">
          <p className="jempty__title">{t('find.empty.title')}</p>
          <p className="jempty__body">{t('find.empty.body')}</p>
          <div className="jempty__actions">
            <button type="button" className="jbtn jbtn--primary" onClick={() => setShowForm(true)}>
              {t('find.add')}
            </button>
            <button type="button" className="jbtn jbtn--quiet" onClick={addSample}>
              {t('find.add')} · {t('find.sample')}
            </button>
          </div>
        </div>
      ) : null}

      {showForm ? (
        <div className="jform">
          <Field label={t('find.name')} error={error && draft.name.trim() === '' ? error : null}>
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
          <div className="jform__row">
            <Field label={t('find.country')}>
              {({ id, ...rest }) => (
                <input
                  id={id}
                  {...rest}
                  className="jinput"
                  value={draft.country}
                  onChange={(event) => setDraft({ ...draft, country: event.target.value })}
                />
              )}
            </Field>
            <Field label={t('find.degree')}>
              {({ id, ...rest }) => (
                <input
                  id={id}
                  {...rest}
                  className="jinput"
                  value={draft.degree}
                  onChange={(event) => setDraft({ ...draft, degree: event.target.value })}
                />
              )}
            </Field>
          </div>
          <div className="jform__row">
            <Field label={t('find.deadline')} hint={t('find.deadlineHint')}>
              {({ id, ...rest }) => (
                <input
                  id={id}
                  {...rest}
                  type="date"
                  className="jinput"
                  value={draft.deadlineDate}
                  onChange={(event) => setDraft({ ...draft, deadlineDate: event.target.value })}
                />
              )}
            </Field>
            <Field label={t('find.deadlineNote')}>
              {({ id, ...rest }) => (
                <input
                  id={id}
                  {...rest}
                  className="jinput"
                  value={draft.deadlineNote}
                  onChange={(event) => setDraft({ ...draft, deadlineNote: event.target.value })}
                />
              )}
            </Field>
          </div>
          <Field label={t('find.sourceUrl')}>
            {({ id, ...rest }) => (
              <input
                id={id}
                {...rest}
                type="url"
                className="jinput"
                value={draft.sourceUrl}
                onChange={(event) => setDraft({ ...draft, sourceUrl: event.target.value })}
              />
            )}
          </Field>
          <Field label={t('find.notes')}>
            {({ id, ...rest }) => (
              <textarea
                id={id}
                {...rest}
                className="jinput jinput--area"
                value={draft.notes}
                onChange={(event) => setDraft({ ...draft, notes: event.target.value })}
              />
            )}
          </Field>
          <fieldset className="jfieldset">
            <legend className="jfieldset__legend">{t('find.trust')}</legend>
            <div className="jtrust">
              {TRUST_OPTIONS.map((option) => (
                <label className="jtrust__option" key={option.value}>
                  <input
                    type="radio"
                    name="trust"
                    value={option.value}
                    checked={draft.trust === option.value}
                    onChange={() => setDraft({ ...draft, trust: option.value })}
                  />
                  <span className="jtrust__label">{t(option.labelKey)}</span>
                  <span className="jtrust__help">{t(option.helpKey)}</span>
                </label>
              ))}
            </div>
          </fieldset>
          <div className="jform__actions">
            <button type="button" className="jbtn jbtn--primary" onClick={addEntry}>
              {t('common.add')}
            </button>
            <button
              type="button"
              className="jbtn jbtn--quiet"
              onClick={() => {
                setShowForm(false)
                setError(null)
                if (state.shortlist.length > 0) setShowForm(false)
              }}
            >
              {t('common.cancel')}
            </button>
          </div>
        </div>
      ) : null}

      {state.shortlist.length > 0 && !showForm ? (
        <div className="jlist__actions">
          <button type="button" className="jbtn jbtn--quiet" onClick={() => setShowForm(true)}>
            {t('find.add')}
          </button>
        </div>
      ) : null}

      <ul className="jcards">
        {state.shortlist.map((entry) => (
          <li className={`jcard${entry.sample ? ' jcard--sample' : ''}`} key={entry.id}>
            <div className="jcard__head">
              <h3 className="jcard__title">{entry.name || t('common.unknown')}</h3>
              {entry.sample ? <StatusChip tone="warning">{t('find.sampleBadge')}</StatusChip> : null}
              <StatusChip tone={TRUST_TONE[entry.trust] ?? 'neutral'}>
                {t(`trust.${entry.trust}`) ?? entry.trust}
              </StatusChip>
            </div>

            {entry.sample ? <p className="jcard__sample-note">{t('find.sampleNote')}</p> : null}

            <dl className="jcard__facts">
              <div>
                <dt>{t('find.country')}</dt>
                <dd>{entry.country || t('common.notRecorded')}</dd>
              </div>
              <div>
                <dt>{t('find.degree')}</dt>
                <dd>{entry.degree || t('common.notRecorded')}</dd>
              </div>
              <div>
                <dt>{t('find.deadline')}</dt>
                <dd>
                  {entry.deadlineDate || (
                    <span className="jmuted">{t('common.checkOfficialSource')}</span>
                  )}
                  {entry.deadlineNote ? <span className="jcard__note-inline"> · {entry.deadlineNote}</span> : null}
                </dd>
              </div>
            </dl>

            {entry.sourceUrl ? (
              <p className="jcard__source">
                <ExternalLink href={entry.sourceUrl}>{t('sources.url')}</ExternalLink>
              </p>
            ) : (
              <p className="jmuted">{t('common.checkOfficialSource')}</p>
            )}

            {entry.notes ? <p className="jcard__notes">{entry.notes}</p> : null}

            <div className="jcard__controls">
              <label className="jselect-label" htmlFor={`trust-${entry.id}`}>
                {t('find.trust')}
                <select
                  id={`trust-${entry.id}`}
                  className="jselect"
                  value={entry.trust}
                  onChange={(event) => update(entry.id, { trust: event.target.value })}
                >
                  {TRUST_OPTIONS.map((option) => (
                    <option value={option.value} key={option.value}>
                      {t(option.labelKey)}
                    </option>
                  ))}
                </select>
              </label>
              <button type="button" className="jbtn jbtn--quiet" onClick={() => remove(entry.id)}>
                {t('find.remove')}
              </button>
            </div>
          </li>
        ))}
      </ul>

      <p className="jmodule__footnote">
        {TRUST_STATUSES.map((status) => (
          <span className="jlegend" key={status}>
            <StatusChip tone={TRUST_TONE[status]}>{t(`trust.${status}`)}</StatusChip>
            {t(
              status === 'verified'
                ? 'find.trust.verifiedHelp'
                : status === 'self-reported'
                  ? 'find.trust.self-reportedHelp'
                  : 'find.trust.needsReviewHelp',
            )}
          </span>
        ))}
      </p>
    </section>
  )
}

export { BilingualText }
