import { useJourney } from '../../hooks/useJourney.js'
import { useJourneyI18n } from '../../i18n/useJourneyI18n.js'
import { ENGLISH_TEST_STATUSES } from '../../lib/journeySchema.js'
import { BilingualText, Field } from '../ui/primitives.jsx'

const ENGLISH_OPTIONS = [
  { value: 'not_taken', labelKey: 'eligibility.english.notTaken' },
  { value: 'booked', labelKey: 'eligibility.english.booked' },
  { value: 'taken', labelKey: 'eligibility.english.taken' },
  { value: 'not_required', labelKey: 'eligibility.english.notRequired' },
]

/**
 * Module 2 — Eligibility Readiness.
 *
 * The results field is stored verbatim, with no conversion between grading
 * scales, and the module says so. The reason is in the copy rather than in a
 * comment: this tool does not know which scale a given programme requires, so
 * any conversion would be a guess presented as arithmetic. A student who entered
 * a CGPA sees their CGPA, not a percentage nobody computed for them.
 *
 * The readiness summary is explicitly a count of fields entered, not a score and
 * not a probability. There is no percentage chance of admission anywhere in this
 * feature.
 */
export function EligibilityModule() {
  const { t, both } = useJourneyI18n()
  const { state, dispatch, actions } = useJourney()
  const e = state.eligibility
  const heading = both('eligibility.title')

  const set = (changes) => dispatch({ type: actions.ELIGIBILITY_SET, payload: changes })

  const entered = [
    e.qualificationLevel,
    e.degreeTitle,
    e.resultsText,
    e.englishTestStatus !== 'not_taken' ? 'set' : '',
    e.citizenshipNotes,
    e.residencyNotes,
  ].filter((value) => typeof value === 'string' && value.trim() !== '').length

  return (
    <section className="jmodule" aria-labelledby="eligibility-title">
      <header className="jmodule__head">
        <h2 className="jmodule__title" id="eligibility-title">
          <span className="jbilingual__primary">{heading.primary}</span>
          {heading.secondary ? (
            <span className="jbilingual__secondary" lang="en">
              {heading.secondary}
            </span>
          ) : null}
        </h2>
        <p className="jmodule__intro">{t('eligibility.intro')}</p>
      </header>

      <div className="jform">
        <Field label={t('eligibility.qualificationLevel')}>
          {({ id, ...rest }) => (
            <input
              id={id}
              {...rest}
              className="jinput"
              value={e.qualificationLevel}
              onChange={(event) => set({ qualificationLevel: event.target.value })}
            />
          )}
        </Field>

        <Field label={t('eligibility.degreeTitle')}>
          {({ id, ...rest }) => (
            <input
              id={id}
              {...rest}
              className="jinput"
              value={e.degreeTitle}
              onChange={(event) => set({ degreeTitle: event.target.value })}
            />
          )}
        </Field>

        <Field label={t('eligibility.results')} hint={t('eligibility.resultsHint')}>
          {({ id, ...rest }) => (
            <input
              id={id}
              {...rest}
              className="jinput"
              value={e.resultsText}
              onChange={(event) => set({ resultsText: event.target.value })}
            />
          )}
        </Field>

        <Field label={t('eligibility.academicNotes')}>
          {({ id, ...rest }) => (
            <textarea
              id={id}
              {...rest}
              className="jinput jinput--area"
              value={e.academicNotes}
              onChange={(event) => set({ academicNotes: event.target.value })}
            />
          )}
        </Field>

        <div className="jform__row">
          <Field label={t('eligibility.englishStatus')}>
            {({ id, ...rest }) => (
              <select
                id={id}
                {...rest}
                className="jselect"
                value={e.englishTestStatus}
                onChange={(event) => set({ englishTestStatus: event.target.value })}
              >
                {ENGLISH_OPTIONS.map((option) => (
                  <option value={option.value} key={option.value}>
                    {t(option.labelKey)}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <Field label={t('eligibility.englishScore')}>
            {({ id, ...rest }) => (
              <input
                id={id}
                {...rest}
                className="jinput"
                value={e.englishScoreText}
                onChange={(event) => set({ englishScoreText: event.target.value })}
              />
            )}
          </Field>
        </div>

        <div className="jform__row">
          <Field label={t('eligibility.citizenship')}>
            {({ id, ...rest }) => (
              <input
                id={id}
                {...rest}
                className="jinput"
                value={e.citizenshipNotes}
                onChange={(event) => set({ citizenshipNotes: event.target.value })}
              />
            )}
          </Field>
          <Field label={t('eligibility.residency')}>
            {({ id, ...rest }) => (
              <input
                id={id}
                {...rest}
                className="jinput"
                value={e.residencyNotes}
                onChange={(event) => set({ residencyNotes: event.target.value })}
              />
            )}
          </Field>
        </div>

        <Field label={t('eligibility.notes')}>
          {({ id, ...rest }) => (
            <textarea
              id={id}
              {...rest}
              className="jinput jinput--area"
              value={e.eligibilityNotes}
              onChange={(event) => set({ eligibilityNotes: event.target.value })}
            />
          )}
        </Field>
      </div>

      <div className="jsummary">
        <h3 className="jsummary__title">{t('eligibility.summary.title')}</h3>
        <p className="jsummary__body">{t('eligibility.summary.body')}</p>
        <p className="jsummary__count">
          <strong>{entered}</strong> {t('eligibility.summary.fieldsEntered')}
        </p>
        <ul className="jsummary__list">
          <li>{e.resultsText ? t('eligibility.summary.resultsStored') : t('eligibility.summary.noResults')}</li>
          <li>{t('eligibility.summary.noConversion')}</li>
          <li>{t('eligibility.summary.cannotDecide')}</li>
        </ul>
        <p className="jnotice jnotice--info">{t('eligibility.warning.noDecision')}</p>
      </div>
    </section>
  )
}

export { BilingualText, ENGLISH_TEST_STATUSES }
