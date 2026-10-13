// The Study-to-Career Strategist wizard and results.
//
// One experience across subject -> degree -> funding -> budget(BDT) -> priorities
// -> results. Every constraint the feature states is enforced here rather than
// beautified away: results are criterion-by-criterion with no single magic score;
// missing evidence is shown as "Insufficient data" with its reason and never as
// zero; BDT is shown beside the original currency with the exchange-rate date;
// no country is declared the universal best; stale figures carry a re-verify note.
//
// Mobile-first: the flow is a single column of large, reachable controls; the
// results reflow to two columns only on wide viewports. Loading, empty, error,
// partial and offline states are all designed, and there is a real disclaimer.
import { useCallback, useEffect, useMemo, useState } from 'react'
import { fetchSubjects, fetchPlan, fetchPathway } from './lib/api.js'
import { buildShareURL, readChoicesFromURL, saveShortlist, readShortlist, exportPDF } from './lib/shareExport.js'
import { useStrategistI18n } from './i18n/useStrategistI18n.js'
import {
  BiText, SectionTitle, Loading, ErrorState, EmptyState, OfflineBanner,
  StatusBadge, SourceLink, EvidenceMeter,
} from './components/ui.jsx'
import './strategist.css'

const STEPS = ['subject', 'degree', 'funding', 'budget', 'priorities', 'results']
const DEFAULT_WEIGHTS = { cost: 25, funding: 15, career: 30, pathway: 30 }

function useOnline() {
  const [online, setOnline] = useState(typeof navigator === 'undefined' ? true : navigator.onLine)
  useEffect(() => {
    const on = () => setOnline(true)
    const off = () => setOnline(false)
    window.addEventListener('online', on)
    window.addEventListener('offline', off)
    return () => {
      window.removeEventListener('online', on)
      window.removeEventListener('offline', off)
    }
  }, [])
  return online
}

function currencyCell(cell) {
  if (cell.status !== 'sourced' || cell.value == null) return null
  const bdt = cell.bdt || {}
  return { value: cell.value, currency: cell.currency, per: cell.per, bdt: bdt.value, bdtDates: bdt.rate_dates || [] }
}

export function StrategistPage() {
  const { t, mode, setLanguage, formatNumber, formatBdt } = useStrategistI18n()
  const online = useOnline()
  const initial = useMemo(() => readChoicesFromURL(window.location.search), [])

  const [step, setStep] = useState(0)
  const [subjects, setSubjects] = useState([])
  const [subject, setSubject] = useState(initial.subject_key || 'computer_science')
  const [degree, setDegree] = useState(initial.degree || 'master')
  const [funding, setFunding] = useState(initial.funding_model || 'self_funded')
  const [budget, setBudget] = useState('')
  const [weights, setWeights] = useState({ ...DEFAULT_WEIGHTS, ...(initial.weights || {}) })

  const [plan, setPlan] = useState(null)
  const [status, setStatus] = useState('idle') // idle | loading | ready | error
  const [pathwayIso, setPathwayIso] = useState(null)
  const [pathway, setPathway] = useState(null)
  const [shortlist, setShortlist] = useState(readShortlist)
  const [toast, setToast] = useState(null)

  useEffect(() => {
    let alive = true
    fetchSubjects()
      .then((body) => alive && setSubjects(body.subjects || []))
      .catch(() => {})
    return () => { alive = false }
  }, [])

  const load = useCallback(async (overrides = {}) => {
    setStatus('loading')
    try {
      const body = await fetchPlan({
        subject_key: subject, degree, funding_model: funding,
        budget_bdt: budget ? Number(budget) : null, weights,
        ...overrides,
      })
      setPlan(body)
      setStatus('ready')
    } catch {
      setStatus('error')
    }
  }, [subject, degree, funding, budget, weights])

  const showResults = useCallback(() => {
    setStep(STEPS.length - 1)
    load()
  }, [load])

  // What-if controls live on the results view: changing budget or funding re-runs
  // the plan immediately from the control's handler (an event, not an effect), and
  // the new value is passed through so the closure is never stale.
  const gotoStep = useCallback((i) => {
    if (i === STEPS.length - 1) {
      setStep(i)
      load()
    } else {
      setStep(i)
    }
  }, [load])

  const toggleShortlist = (iso2) => {
    const next = shortlist.includes(iso2) ? shortlist.filter((x) => x !== iso2) : [...shortlist, iso2]
    setShortlist(next)
    saveShortlist(next)
    setToast(t('shortlist.saved').en)
  }

  const doShare = async () => {
    const url = buildShareURL({ subject_key: subject, degree, funding_model: funding, weights })
    try {
      await navigator.clipboard.writeText(url)
    } catch {
      window.prompt('Copy this link:', url)
    }
    setToast(t('shortlist.shared').en)
  }

  const doPdf = () => {
    exportPDF()
    setToast(t('shortlist.pdfNote').en)
  }

  const openPathway = async (iso2) => {
    setPathwayIso(iso2)
    setPathway(null)
    try {
      setPathway(await fetchPathway(iso2))
    } catch {
      setPathway({ error: true })
    }
  }

  const ranked = plan?.comparison || []
  const unranked = plan?.insufficient_data || []

  return (
    <section className="strategist" aria-labelledby="strategist-title">
      <header className="strategist-header">
        <h1 id="strategist-title" className="strategist-h1">
          <BiText pair={t('page.title')} mode={mode} />
        </h1>
        <p className="strategist-subtitle">
          <BiText pair={t('page.subtitle')} mode={mode} />
        </p>
        <div className="strategist-lang" role="group" aria-label={t('language.label').en}>
          {['en', 'bn', 'both'].map((m) => (
            <button
              key={m}
              type="button"
              className={`strategist-chip ${mode === m ? 'is-active' : ''}`}
              aria-pressed={mode === m}
              onClick={() => setLanguage(m)}
            >
              {t(`language.${m}`).en}
            </button>
          ))}
        </div>
      </header>

      {!online && <OfflineBanner t={t} mode={mode} />}

      <ol className="strategist-steps" aria-label="Wizard steps">
        {STEPS.map((s, i) => (
          <li key={s} className={i === step ? 'is-current' : i < step ? 'is-done' : ''}>
            <button
              type="button"
              onClick={() => gotoStep(i)}
              aria-current={i === step ? 'step' : undefined}
            >
              <span className="strategist-step-num" aria-hidden="true">{i + 1}</span>
              <BiText pair={t(`step.${s}`)} mode={mode} />
            </button>
          </li>
        ))}
      </ol>

      <section className="strategist-panel" aria-live="polite">
        {step === 0 && (
          <fieldset>
            <legend><BiText pair={t('subject.pick')} mode={mode} as="span" /></legend>
            <div className="strategist-options">
              {(subjects.length ? subjects : []).map((s) => (
                <label key={s.key} className={`strategist-option ${subject === s.key ? 'is-active' : ''}`}>
                  <input type="radio" name="subject" value={s.key} checked={subject === s.key}
                    onChange={() => setSubject(s.key)} />
                  <span><BiText pair={{ en: s.name_en, bn: s.name_bn }} mode={mode} /></span>
                </label>
              ))}
              {!subjects.length && <p><BiText pair={t('state.loading')} mode={mode} /></p>}
            </div>
            {subject && <p className="strategist-note"><BiText pair={coverageNote(subjects, subject)} mode={mode} /></p>}
            <nav className="strategist-nav"><button type="button" className="strategist-btn strategist-btn-primary" onClick={() => setStep(1)}>{t('btn.next').en}</button></nav>
          </fieldset>
        )}

        {step === 1 && (
          <fieldset>
            <legend><BiText pair={t('degree.pick')} mode={mode} as="span" /></legend>
            <div className="strategist-options">
              {['bachelor', 'master', 'phd'].map((d) => (
                <label key={d} className={`strategist-option ${degree === d ? 'is-active' : ''}`}>
                  <input type="radio" name="degree" value={d} checked={degree === d} onChange={() => setDegree(d)} />
                  <span><BiText pair={t(`degree.${d}`)} mode={mode} /></span>
                </label>
              ))}
            </div>
            <nav className="strategist-nav">
              <button type="button" className="strategist-btn" onClick={() => setStep(0)}>{t('btn.back').en}</button>
              <button type="button" className="strategist-btn strategist-btn-primary" onClick={() => setStep(2)}>{t('btn.next').en}</button>
            </nav>
          </fieldset>
        )}

        {step === 2 && (
          <fieldset>
            <legend><BiText pair={t('funding.pick')} mode={mode} as="span" /></legend>
            <div className="strategist-options">
              {['fully_funded', 'tuition_only', 'partial', 'self_funded'].map((f) => (
                <label key={f} className={`strategist-option ${funding === f ? 'is-active' : ''}`}>
                  <input type="radio" name="funding" value={f} checked={funding === f} onChange={() => setFunding(f)} />
                  <span><BiText pair={t(`funding.${f}`)} mode={mode} /></span>
                </label>
              ))}
            </div>
            <nav className="strategist-nav">
              <button type="button" className="strategist-btn" onClick={() => setStep(1)}>{t('btn.back').en}</button>
              <button type="button" className="strategist-btn strategist-btn-primary" onClick={() => setStep(3)}>{t('btn.next').en}</button>
            </nav>
          </fieldset>
        )}

        {step === 3 && (
          <div>
            <label className="strategist-field">
              <span><BiText pair={t('budget.label')} mode={mode} /></span>
              <input type="number" min="0" inputMode="numeric" value={budget}
                onChange={(e) => setBudget(e.target.value)} placeholder="3000000" />
            </label>
            <p className="strategist-note"><BiText pair={t('budget.hint')} mode={mode} /></p>
            <nav className="strategist-nav">
              <button type="button" className="strategist-btn" onClick={() => setStep(2)}>{t('btn.back').en}</button>
              <button type="button" className="strategist-btn strategist-btn-primary" onClick={() => setStep(4)}>{t('btn.next').en}</button>
            </nav>
          </div>
        )}

        {step === 4 && (
          <div>
            <p className="strategist-note"><BiText pair={t('priorities.explain')} mode={mode} /></p>
            {['cost', 'funding', 'career', 'pathway'].map((k) => (
              <label className="strategist-field strategist-slider" key={k}>
                <span><BiText pair={t(`priorities.${k}`)} mode={mode} /></span>
                <input type="range" min="0" max="100" value={weights[k]}
                  onChange={(e) => setWeights((w) => ({ ...w, [k]: Number(e.target.value) }))}
                  aria-valuetext={String(weights[k])} />
                <output>{weights[k]}</output>
              </label>
            ))}
            <nav className="strategist-nav">
              <button type="button" className="strategist-btn" onClick={() => setStep(3)}>{t('btn.back').en}</button>
              <button type="button" className="strategist-btn strategist-btn-primary" onClick={showResults}>{t('btn.compare').en}</button>
            </nav>
          </div>
        )}

        {step === 5 && (
          <div className="strategist-results" data-testid="results">
            {status === 'loading' && <Loading label={t('state.loading')} mode={mode} />}
            {status === 'error' && <ErrorState onRetry={load} t={t} mode={mode} />}
            {status === 'ready' && plan && (
              <>
                <SectionTitle id="results-title"><BiText pair={t('results.title')} mode={mode} /></SectionTitle>
                <p className="strategist-note"><BiText pair={t('results.noSame')} mode={mode} /></p>
                <p className="strategist-note" data-testid="essential-criteria">
                  <strong><BiText pair={t('results.essential')} mode={mode} />:</strong>{' '}
                  {(plan.request?.essential_criteria || []).join(', ')}
                </p>
                {plan.selection_rule && (
                  <p className="strategist-note" data-testid="selection-rule">{plan.selection_rule}</p>
                )}

                <div className="strategist-actions">
                  <button type="button" className="strategist-btn" onClick={doShare}>{t('shortlist.share').en}</button>
                  <button type="button" className="strategist-btn" onClick={doPdf}>{t('shortlist.pdf').en}</button>
                </div>

                <section className="strategist-whatif" aria-label={t('whatif.title').en} data-testid="whatif">
                  <BiText pair={t('whatif.title')} mode={mode} as="h3" />
                  <label className="strategist-field strategist-slider">
                    <span><BiText pair={t('budget.label')} mode={mode} /></span>
                    <input type="number" min="0" inputMode="numeric" value={budget}
                      onChange={(e) => {
                        setBudget(e.target.value)
                        load({ budget_bdt: e.target.value ? Number(e.target.value) : null })
                      }} />
                  </label>
                  <fieldset className="strategist-whatif-funding">
                    <legend><BiText pair={t('funding.pick')} mode={mode} as="span" /></legend>
                    <div className="strategist-options">
                      {['fully_funded', 'tuition_only', 'partial', 'self_funded'].map((f) => (
                        <label key={f} className={`strategist-option ${funding === f ? 'is-active' : ''}`}>
                          <input type="radio" name="whatif-funding" value={f} checked={funding === f}
                            onChange={() => { setFunding(f); load({ funding_model: f }) }} />
                          <span><BiText pair={t(`funding.${f}`)} mode={mode} /></span>
                        </label>
                      ))}
                    </div>
                  </fieldset>
                </section>

                <section aria-labelledby="ranked-title">
                  <h3 id="ranked-title" className="strategist-h3"><BiText pair={t('results.ranked')} mode={mode} /></h3>
                  {ranked.length === 0 && <EmptyState t={t} mode={mode} />}
                  {ranked.map((c) => <CountryResult key={c.iso2} country={c} plan={plan} t={t} mode={mode}
                    formatBdt={formatBdt} formatNumber={formatNumber} shortlisted={shortlist.includes(c.iso2)}
                    onShortlist={() => toggleShortlist(c.iso2)} onPathway={() => openPathway(c.iso2)} />)}
                </section>

                <section aria-labelledby="notranked-title">
                  <h3 id="notranked-title" className="strategist-h3"><BiText pair={t('results.notRanked')} mode={mode} /></h3>
                  <p className="strategist-note"><BiText pair={t('results.partial')} mode={mode} /></p>
                  {unranked.map((c) => <CountryResult key={c.iso2} country={c} plan={plan} t={t} mode={mode}
                    formatBdt={formatBdt} formatNumber={formatNumber} shortlisted={shortlist.includes(c.iso2)}
                    onShortlist={() => toggleShortlist(c.iso2)} onPathway={() => openPathway(c.iso2)} />)}
                </section>

                <p className="strategist-disclaimer" data-testid="disclaimer"><BiText pair={t('notLegal')} mode={mode} /></p>

                {pathwayIso && (
                  <section className="strategist-pathway" aria-labelledby="pathway-title" data-testid="pathway">
                    <h3 id="pathway-title" className="strategist-h3"><BiText pair={t('pathway.title')} mode={mode} /></h3>
                    {!pathway && <Loading label={t('state.loading')} mode={mode} />}
                    {pathway?.error && <ErrorState onRetry={() => openPathway(pathwayIso)} t={t} mode={mode} />}
                    {pathway?.steps && (
                      <ol className="strategist-timeline">
                        {pathway.steps.map((s) => (
                          <li key={s.step} className={`strategist-step-item is-${s.status}`}>
                            <div className="strategist-step-head">
                              <strong>{s.step.replace(/_/g, ' ')}</strong>
                              <StatusBadge status={s.status === 'sourced' ? 'sourced' : 'bad'}>
                                {s.status === 'sourced' ? t('status').en : t('insufficient').en}
                              </StatusBadge>
                              {s.stale_warning && <span className="strategist-reverify">⚠ {t('reverify').en}</span>}
                            </div>
                            {s.status === 'insufficient' ? (
                              <p className="strategist-reason">{s.reason}</p>
                            ) : (
                              <>
                                {s.value != null && <p>{formatNumber(s.value)} {s.per || ''}</p>}
                                {s.condition && <p className="strategist-condition">{s.condition}</p>}
                                {s.official_link
                                  ? <SourceLink source={{ url: s.official_link, publisher: t('source').en }} />
                                  : s.source_missing_reason
                                    ? <p className="strategist-reason">{s.source_missing_reason}</p> : null}
                                {s.as_of && <p className="strategist-meta">{t('checked').en}: {s.as_of}</p>}
                              </>
                            )}
                          </li>
                        ))}
                      </ol>
                    )}
                  </section>
                )}
              </>
            )}
          </div>
        )}
      </section>

      {toast && (
        <div className="strategist-toast" role="status" data-testid="toast" onClick={() => setToast(null)}>
          {toast}
        </div>
      )}

      <footer className="strategist-footer">
        <BiText pair={t('page.subtitle')} mode={mode} />
      </footer>
    </section>
  )
}

function coverageNote(subjects, key) {
  const found = subjects.find((s) => s.key === key)
  return found ? { en: found.coverage_note_en, bn: found.coverage_note_en } : { en: '', bn: '' }
}

function CountryResult({ country, plan, t, mode, formatBdt, formatNumber, shortlisted, onShortlist, onPathway }) {
  return (
    <article className="strategist-card" data-country={country.iso2} data-ranked={country.ranked}>
      <header className="strategist-card-head">
        <h4>{country.name} ({country.iso2})</h4>
        <EvidenceMeter completeness={country.evidence_completeness} />
      </header>

      <ul className="strategist-cells">
        {plan.criteria.map((meta) => {
          const cell = country.cells[meta.key]
          const money = currencyCell(cell)
          return (
            <li key={meta.key} data-criterion={meta.key} data-status={cell.status}>
              <span className="strategist-cell-label">{meta.label_en}</span>
              {cell.status === 'sourced' ? (
                <span className="strategist-cell-value">
                  {money ? (
                    <>
                      <span className="strategist-bdt">≈ {formatBdt(money.bdt)} BDT</span>
                      <span className="strategist-orig"> · {t('bdt.original').en}: {formatNumber(money.value)} {money.currency}/{money.per}</span>
                      <span className="strategist-meta"> · {t('bdt.rateDate').en}: {(money.bdtDates[1] || money.bdtDates[0])}</span>
                    </>
                  ) : (
                    <>{cell.value != null ? `${formatNumber(cell.value)} ${cell.per || ''}` : t('status').en}</>
                  )}
                  {cell.basis === 'gross' && <span className="strategist-meta"> · {money ? 'gross' : ''}</span>}
                  {cell.stale_warning && <span className="strategist-reverify"> ⚠ {t('reverify').en}</span>}
                  {cell.sources && cell.sources.length > 0 && (
                    <SourceLink source={cell.sources[0]} />
                  )}
                </span>
              ) : (
                <span className="strategist-insufficient">
                  <StatusBadge status="bad">{t('insufficient').en}</StatusBadge>
                  <span className="strategist-reason">{cell.reason}</span>
                </span>
              )}
              {(meta.key === 'tuition' || meta.key === 'living_cost') && cell.budget_interpretation && (
                <span className="strategist-budget" data-testid={`budget-${meta.key}`}>
                  <span className="strategist-cell-label"><BiText pair={t('results.budget')} mode={mode} /></span>
                  <span className="strategist-meta"> {cell.budget_interpretation.note}</span>
                </span>
              )}
              {cell.scenario && (
                <span className="strategist-funding" data-testid="funding-scenario">
                  <span className="strategist-cell-label"><BiText pair={t('results.funding')} mode={mode} /></span>
                  <span className="strategist-meta"> {cell.scenario.note}{cell.scenario.model_note ? ` ${cell.scenario.model_note}` : ''}</span>
                </span>
              )}
            </li>
          )
        })}
      </ul>

      <div className="strategist-why">
        <div className="strategist-why-pos">
          <strong><BiText pair={t('results.whyRecommended')} mode={mode} /></strong>
          <ul>{country.why.recommended.length ? country.why.recommended.map((r, i) => <li key={i}>{r}</li>) : <li>—</li>}</ul>
        </div>
        <div className="strategist-why-neg">
          <strong><BiText pair={t('results.whyExcluded')} mode={mode} /></strong>
          <ul>{country.why.risks.length ? country.why.risks.map((r, i) => <li key={i}>{r}</li>) : <li>—</li>}</ul>
        </div>
      </div>

      <footer className="strategist-card-foot">
        <button type="button" className="strategist-btn" aria-pressed={shortlisted}
          onClick={onShortlist}>
          {shortlisted ? '★ ' : '☆ '}{t('shortlist.save').en}
        </button>
        <button type="button" className="strategist-btn" onClick={onPathway}>{t('pathway.title').en}</button>
      </footer>
    </article>
  )
}
