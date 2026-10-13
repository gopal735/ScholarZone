import { useMemo, useState } from 'react'
import { useJourney } from '../../hooks/useJourney.js'
import { useJourneyI18n } from '../../i18n/useJourneyI18n.js'
import { COST_CATEGORIES, FUNDING_CATEGORY, normalizeAmount, hasBanglaDigits } from '../../lib/money.js'
import { computeCostSummary, computeBdtView } from '../../lib/costs.js'
import { BilingualText, Field, StatusChip } from '../ui/primitives.jsx'

const CATEGORY_LABEL_KEY = {
  tuition: 'costs.category.tuition',
  living: 'costs.category.living',
  travel: 'costs.category.travel',
  insurance: 'costs.category.insurance',
  visa: 'costs.category.visa',
  other: 'costs.category.other',
  funding: 'costs.category.funding',
}

const SOURCE_LABEL_KEY = {
  official: 'costs.sourceType.official',
  'user-entered': 'costs.sourceType.user-entered',
  estimate: 'costs.sourceType.estimate',
}

/** Inline error copy, keyed by the reason `normalizeAmount` returns. */
const AMOUNT_ERROR_KEY = {
  empty: 'costs.invalid.empty',
  'not-a-number': 'costs.invalid.notANumber',
  negative: 'costs.invalid.negative',
  'too-large': 'costs.invalid.tooLarge',
}

/**
 * Module 5 — BDT Cost Planner.
 *
 * Every figure carries a provenance type and a source label, and a total derived
 * from any estimate is labelled as such everywhere it appears — the module, the
 * summary card, the export and the print view. That label is computed from the
 * provenance fields, not from the numbers, so a large user-entered figure and a
 * large official one are distinguished the same way in both directions.
 *
 * No tuition, living-cost, visa-fee or insurance amount is ever supplied by this
 * tool, and no exchange rate is ever remembered. A blank field means "not yet
 * known" and is rendered as exactly that.
 */
export function CostPlannerModule() {
  const { t, both } = useJourneyI18n()
  const { state, dispatch, actions } = useJourney()
  const heading = both('costs.title')

  const summary = useMemo(() => computeCostSummary(state), [state])
  const bdt = useMemo(() => computeBdtView(state), [state])

  const [amountErrors, setAmountErrors] = useState({})

  const onAmountChange = (id, raw) => {
    const normalized = normalizeAmount(raw)
    if (raw.trim() === '') {
      setAmountErrors((prev) => ({ ...prev, [id]: null }))
    } else if (!normalized.ok) {
      setAmountErrors((prev) => ({ ...prev, [id]: t(AMOUNT_ERROR_KEY[normalized.reason]) }))
    } else {
      setAmountErrors((prev) => ({ ...prev, [id]: null }))
    }
    dispatch({ type: actions.COSTS_UPDATE, payload: { id, changes: { amount: raw } } })
  }

  const addCost = () => {
    dispatch({
      type: actions.COSTS_ADD,
      payload: {
        label: '',
        category: 'tuition',
        amount: '',
        currency: 'BDT',
        sourceType: 'user-entered',
        sourceLabel: '',
        sourceDate: '',
        note: '',
      },
    })
  }

  const update = (id, changes) => dispatch({ type: actions.COSTS_UPDATE, payload: { id, changes } })
  const remove = (id) => dispatch({ type: actions.COSTS_REMOVE, payload: { id } })
  const setRate = (changes) => dispatch({ type: actions.COSTS_SET_RATE, payload: changes })

  const provenanceTone = summary.containsEstimate ? 'warning' : 'success'

  return (
    <section className="jmodule" aria-labelledby="costs-title">
      <header className="jmodule__head">
        <h2 className="jmodule__title" id="costs-title">
          <span className="jbilingual__primary">{heading.primary}</span>
          {heading.secondary ? (
            <span className="jbilingual__secondary" lang="en">
              {heading.secondary}
            </span>
          ) : null}
        </h2>
        <p className="jmodule__intro">{t('costs.intro')}</p>
      </header>

      <p className="jnotice jnotice--info">{t('costs.noFabrication')}</p>

      <div className="jlist__actions">
        <button type="button" className="jbtn jbtn--quiet" onClick={addCost}>
          {t('costs.add')}
        </button>
      </div>

      {state.costs.items.length === 0 ? (
        <div className="jempty">
          <p className="jempty__title">{t('costs.empty.title')}</p>
          <p className="jempty__body">{t('costs.empty.body')}</p>
          <div className="jempty__actions">
            <button type="button" className="jbtn jbtn--primary" onClick={addCost}>
              {t('costs.add')}
            </button>
          </div>
        </div>
      ) : null}

      <ul className="jcosts">
        {state.costs.items.map((item) => (
          <li className="jcosts__item" key={item.id}>
            <div className="jcosts__row">
              <Field label={t('costs.label')}>
                {({ id, ...rest }) => (
                  <input
                    id={id}
                    {...rest}
                    className="jinput"
                    value={item.label}
                    onChange={(event) => update(item.id, { label: event.target.value })}
                  />
                )}
              </Field>

              <Field label={t('costs.category')}>
                {({ id, ...rest }) => (
                  <select
                    id={id}
                    {...rest}
                    className="jselect"
                    value={item.category}
                    onChange={(event) => update(item.id, { category: event.target.value })}
                  >
                    {[...COST_CATEGORIES, FUNDING_CATEGORY].map((value) => (
                      <option value={value} key={value}>
                        {t(CATEGORY_LABEL_KEY[value])}
                      </option>
                    ))}
                  </select>
                )}
              </Field>

              <Field
                label={t('costs.amount')}
                hint={hasBanglaDigits(item.amount) ? t('costs.banglaDigits') : undefined}
                error={amountErrors[item.id]}
              >
                {({ id, ...rest }) => (
                  <input
                    id={id}
                    {...rest}
                    className={`jinput${amountErrors[item.id] ? ' jinput--invalid' : ''}`}
                    inputMode="decimal"
                    value={item.amount}
                    onChange={(event) => onAmountChange(item.id, event.target.value)}
                  />
                )}
              </Field>

              <Field label={t('costs.currency')}>
                {({ id, ...rest }) => (
                  <input
                    id={id}
                    {...rest}
                    className="jinput jinput--currency"
                    value={item.currency}
                    onChange={(event) => update(item.id, { currency: event.target.value.toUpperCase() })}
                  />
                )}
              </Field>
            </div>

            <div className="jcosts__row">
              <Field label={t('costs.sourceType')}>
                {({ id, ...rest }) => (
                  <select
                    id={id}
                    {...rest}
                    className="jselect"
                    value={item.sourceType}
                    onChange={(event) => update(item.id, { sourceType: event.target.value })}
                  >
                    {['official', 'user-entered', 'estimate'].map((value) => (
                      <option value={value} key={value}>
                        {t(SOURCE_LABEL_KEY[value])}
                      </option>
                    ))}
                  </select>
                )}
              </Field>

              <Field label={t('costs.sourceLabel')}>
                {({ id, ...rest }) => (
                  <input
                    id={id}
                    {...rest}
                    className="jinput"
                    value={item.sourceLabel}
                    onChange={(event) => update(item.id, { sourceLabel: event.target.value })}
                  />
                )}
              </Field>

              <Field label={t('costs.sourceDate')}>
                {({ id, ...rest }) => (
                  <input
                    id={id}
                    {...rest}
                    type="date"
                    className="jinput jinput--date"
                    value={item.sourceDate}
                    onChange={(event) => update(item.id, { sourceDate: event.target.value })}
                  />
                )}
              </Field>

              <button
                type="button"
                className="jbtn jbtn--icon jcosts__remove"
                onClick={() => remove(item.id)}
                aria-label={`${t('costs.remove')} — ${item.label || item.category}`}
              >
                ×
              </button>
            </div>
          </li>
        ))}
      </ul>

      <div className="jrate">
        <h3 className="jrate__title">{t('costs.rate.title')}</h3>
        <p className="jrate__body">{t('costs.rate.body')}</p>
        <div className="jrate__row">
          <Field label={t('costs.rate.bdtPerUnit')} error={amountErrors.rate}>
            {({ id, ...rest }) => (
              <input
                id={id}
                {...rest}
                className={`jinput${amountErrors.rate ? ' jinput--invalid' : ''}`}
                inputMode="decimal"
                value={state.costs.rate.bdtPerUnit}
                onChange={(event) => {
                  const normalized = normalizeAmount(event.target.value)
                  if (event.target.value.trim() === '') setAmountErrors((prev) => ({ ...prev, rate: null }))
                  else if (!normalized.ok) setAmountErrors((prev) => ({ ...prev, rate: t(AMOUNT_ERROR_KEY[normalized.reason]) }))
                  else setAmountErrors((prev) => ({ ...prev, rate: null }))
                  setRate({ bdtPerUnit: event.target.value })
                }}
              />
            )}
          </Field>
          <Field label={t('costs.rate.effectiveDate')}>
            {({ id, ...rest }) => (
              <input
                id={id}
                {...rest}
                type="date"
                className="jinput jinput--date"
                value={state.costs.rate.effectiveDate}
                onChange={(event) => setRate({ effectiveDate: event.target.value })}
              />
            )}
          </Field>
          <Field label={t('costs.rate.label')}>
            {({ id, ...rest }) => (
              <input
                id={id}
                {...rest}
                className="jinput"
                value={state.costs.rate.label}
                onChange={(event) => setRate({ label: event.target.value })}
              />
            )}
          </Field>
        </div>
      </div>

      <div className="jtotals" aria-label={t('costs.title')}>
        <h3 className="jtotals__title">{t('costs.totalCost')}</h3>
        <p className="jtotals__value">{summary.state === 'no-costs' ? '—' : summary.totalCost}</p>

        <h3 className="jtotals__title">{t('costs.totalFunding')}</h3>
        <p className="jtotals__value">{summary.totalFundingUsable && summary.totalFunding !== '0' ? summary.totalFunding : '—'}</p>

        <h3 className="jtotals__title">{t('costs.gap')}</h3>
        <p className="jtotals__value">
          {summary.gap === null ? '—' : summary.gap}
          {summary.state === 'surplus' ? (
            <StatusChip tone="success" className="jtotals__flag">
              {t('costs.surplus')}
            </StatusChip>
          ) : null}
          {summary.state === 'no-costs' ? <span className="jtotals__flag">{t('costs.noCosts')}</span> : null}
          {summary.state === 'no-funding' ? (
            <span className="jtotals__flag">{t('costs.noFunding')}</span>
          ) : null}
        </p>
      </div>

      <div className="jprovenance" aria-live="polite">
        <StatusChip tone={provenanceTone}>
          {summary.containsEstimate ? t('costs.containsEstimates') : t('costs.officialOnly')}
        </StatusChip>
        {summary.containsEstimate ? <StatusChip tone="info">{t('costs.containsUserEntered')}</StatusChip> : null}
      </div>

      <p className="jmodule__footnote">{t('costs.formula.body')}</p>

      <div className="jbdt">
        <h3 className="jbdt__title">{t('costs.bdtView')}</h3>
        {bdt.rateUsed === null ? (
          <p className="jbdt__none">{t('costs.bdtView.none')}</p>
        ) : (
          <>
            <p className="jbdt__meta">
              {t('costs.bdtView.converted')} · 1 = {bdt.rateUsed} BDT
              {bdt.effectiveDate ? ` · ${bdt.effectiveDate}` : ''}
            </p>
            <p className="jbdt__line">
              {t('costs.totalCost')}: <strong>{bdt.totalCostBdt}</strong> · {t('costs.totalFunding')}: <strong>{bdt.totalFundingBdt}</strong>
              {bdt.gapBdt !== null ? ` · ${t('costs.gap')}: <strong>${bdt.gapBdt}</strong>` : ''}
            </p>
            {bdt.unconverted.length > 0 ? (
              <p className="jbdt__warning">{t('costs.bdtView.unconverted')}</p>
            ) : null}
          </>
        )}
      </div>
    </section>
  )
}

export { BilingualText }
