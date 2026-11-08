import { useEffect, useState, useCallback } from 'react'
import { useJourney } from '../../hooks/useJourney.js'
import { useJourneyI18n } from '../../i18n/useJourneyI18n.js'
import { BilingualText, ExternalLink, Field, StatusChip } from '../ui/primitives.jsx'
import { SAMPLE_SHORTLIST_ENTRY } from '../../data/seed.js'
import { TRUST_STATUSES } from '../../lib/journeySchema.js'
import { fetchScholarships } from '../../../../services/scholarshipService'

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
 *
 * Catalogue integration: students can browse the live ScholarZone scholarship
 * directory, search and filter, and add any listing to their personal shortlist.
 * The added entry inherits the scholarship's title, country, degree level and
 * official source URL, with trust status defaulting to "needs-review" so the
 * student must still confirm the details themselves.
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
  const [showCatalogue, setShowCatalogue] = useState(false)
  const [error, setError] = useState(null)
  const [catalogueScholarships, setCatalogueScholarships] = useState([])
  const [catalogueLoading, setCatalogueLoading] = useState(false)
  const [catalogueError, setCatalogueError] = useState(null)
  const [catalogueSearch, setCatalogueSearch] = useState('')
  const [catalogueCountry, setCatalogueCountry] = useState('All')
  const [catalogueDegree, setCatalogueDegree] = useState('All')
  const [catalogueFunding, setCatalogueFunding] = useState('All')
  const [cataloguePage, setCataloguePage] = useState(1)
  const [catalogueTotalPages, setCatalogueTotalPages] = useState(1)
  const [selectedScholarshipIds, setSelectedScholarshipIds] = useState(new Set())
  const heading = both('find.title')

  // Load scholarships from catalogue when browsing
  const loadCatalogue = useCallback(async (page = 1) => {
    setCatalogueLoading(true)
    setCatalogueError(null)
    try {
      const result = await fetchScholarships({
        page,
        limit: 12,
        search: catalogueSearch || undefined,
        country: catalogueCountry !== 'All' ? catalogueCountry : undefined,
        degree: catalogueDegree !== 'All' ? catalogueDegree : undefined,
        funding: catalogueFunding !== 'All' ? catalogueFunding : undefined,
        sort: 'recommended',
      })
      setCatalogueScholarships(result.items)
      setCatalogueTotalPages(result.pagination.total_pages)
      setCataloguePage(page)
    } catch (err) {
      setCatalogueError(t('common.unknown'))
      console.error('Failed to load catalogue:', err)
    } finally {
      setCatalogueLoading(false)
    }
  }, [catalogueSearch, catalogueCountry, catalogueDegree, catalogueFunding, t])

  // Load first page when catalogue is opened
  useEffect(() => {
    if (!showCatalogue) return
    const doLoad = async () => {
      await loadCatalogue(1)
    }
    doLoad()
  }, [showCatalogue, loadCatalogue])

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      if (showCatalogue) {
        loadCatalogue(1)
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [catalogueSearch, showCatalogue, loadCatalogue])

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

  const addFromCatalogue = (scholarship) => {
    // Check if already in shortlist
    const exists = state.shortlist.some((entry) => entry.catalogueId === scholarship.id)
    if (exists) {
      setError(t('documents.duplicate'))
      return
    }
    dispatch({
      type: actions.SHORTLIST_ADD,
      payload: {
        name: scholarship.title,
        country: scholarship.country,
        degree: scholarship.degree,
        deadlineDate: scholarship.deadline_date || '',
        deadlineNote: scholarship.deadline || '',
        sourceUrl: scholarship.official_source_url || scholarship.catalogue_url || '',
        notes: `Added from ScholarZone catalogue. ${scholarship.funding ? `Funding: ${scholarship.funding}. ` : ''}${scholarship.description ? scholarship.description.slice(0, 200) : ''}`,
        trust: 'needs-review',
        catalogueId: scholarship.id,
        officialSource: scholarship.official_source,
        verificationStatus: scholarship.verification_status,
      },
    })
    setSelectedScholarshipIds((prev) => {
      const next = new Set(prev)
      next.add(scholarship.id)
      return next
    })
    setError(null)
  }

  const addMultipleFromCatalogue = () => {
    selectedScholarshipIds.forEach((id) => {
      const scholarship = catalogueScholarships.find((s) => s.id === id)
      if (scholarship) {
        addFromCatalogue(scholarship)
      }
    })
    setSelectedScholarshipIds(new Set())
  }

  const toggleSelection = (id) => {
    setSelectedScholarshipIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
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

      {/* Empty state with catalogue option */}
      {state.shortlist.length === 0 && !showForm && !showCatalogue ? (
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
            <button type="button" className="jbtn jbtn--secondary" onClick={() => setShowCatalogue(true)}>
              {t('find.browseCatalogue') || 'Browse catalogue'}
            </button>
          </div>
        </div>
      ) : null}

      {/* Catalogue browser */}
      {showCatalogue && (
        <div className="jcatalogue">
          <div className="jcatalogue__header">
            <h3>{t('find.catalogueTitle') || 'ScholarZone Catalogue'}</h3>
            <button type="button" className="jbtn jbtn--quiet" onClick={() => setShowCatalogue(false)}>
              {t('common.close')}
            </button>
          </div>

          {/* Filters */}
          <div className="jcatalogue__filters">
            <div className="jcatalogue__search">
              <label htmlFor="catalogue-search" className="sz-sr-only">{t('find.search')}</label>
              <input
                id="catalogue-search"
                type="search"
                className="jinput"
                placeholder={t('find.searchPlaceholder') || 'Search scholarships…'}
                value={catalogueSearch}
                onChange={(e) => setCatalogueSearch(e.target.value)}
              />
            </div>
            <div className="jcatalogue__filter-row">
              <Field label={t('find.filterCountry')}>
                {({ id, ...rest }) => (
                  <select id={id} {...rest} className="jselect" value={catalogueCountry} onChange={(e) => { setCatalogueCountry(e.target.value); setCataloguePage(1); }}>
                    <option value="All">{t('common.allCountries') || 'All countries'}</option>
                    {/* Countries would be loaded dynamically in a full implementation */}
                    <option value="United States">United States</option>
                    <option value="United Kingdom">United Kingdom</option>
                    <option value="Canada">Canada</option>
                    <option value="Australia">Australia</option>
                    <option value="Germany">Germany</option>
                    <option value="Japan">Japan</option>
                    <option value="China">China</option>
                    <option value="South Korea">South Korea</option>
                    <option value="Bangladesh">Bangladesh</option>
                    <option value="India">India</option>
                  </select>
                )}
              </Field>
              <Field label={t('find.filterDegree')}>
                {({ id, ...rest }) => (
                  <select id={id} {...rest} className="jselect" value={catalogueDegree} onChange={(e) => { setCatalogueDegree(e.target.value); setCataloguePage(1); }}>
                    <option value="All">{t('common.allDegrees') || 'All levels'}</option>
                    <option value="Bachelor">Bachelor</option>
                    <option value="Master">Master</option>
                    <option value="PhD">PhD</option>
                  </select>
                )}
              </Field>
              <Field label={t('find.filterFunding')}>
                {({ id, ...rest }) => (
                  <select id={id} {...rest} className="jselect" value={catalogueFunding} onChange={(e) => { setCatalogueFunding(e.target.value); setCataloguePage(1); }}>
                    <option value="All">{t('common.allFunding') || 'All funding'}</option>
                    <option value="Fully Funded">Fully Funded</option>
                    <option value="Partially Funded">Partially Funded</option>
                    <option value="Tuition Fee Waiver">Tuition Fee Waiver</option>
                    <option value="Stipend">Stipend</option>
                  </select>
                )}
              </Field>
            </div>
          </div>

          {/* Results */}
          {catalogueLoading ? (
            <div className="jcatalogue__loading" role="status" aria-live="polite">
              {t('common.loading')}
            </div>
          ) : catalogueError ? (
            <div className="jcatalogue__error">
              <p>{t('find.catalogueError') || 'Failed to load catalogue'}</p>
              <button type="button" className="jbtn jbtn--quiet" onClick={() => loadCatalogue(cataloguePage)}>
                {t('common.retry')}
              </button>
            </div>
          ) : catalogueScholarships.length === 0 ? (
            <div className="jcatalogue__empty">
              <p>{t('find.catalogueEmpty') || 'No scholarships match your filters.'}</p>
            </div>
          ) : (
            <>
              <ul className="jcatalogue__list">
                {catalogueScholarships.map((scholarship) => (
                  <li className={`jcatalogue__card${selectedScholarshipIds.has(scholarship.id) ? ' is-selected' : ''}`} key={scholarship.id}>
                    <div className="jcatalogue__card-head">
                      <h4 className="jcatalogue__card-title">{scholarship.title}</h4>
                      <StatusChip tone={scholarship.verification_status === 'active' ? 'success' : 'info'}>
                        {scholarship.verification_status === 'active' ? t('sources.status.independently-verified') : t('sources.status.unknown')}
                      </StatusChip>
                    </div>
                    <dl className="jcatalogue__card-facts">
                      <div>
                        <dt>{t('find.country')}</dt>
                        <dd>{scholarship.country || t('common.notRecorded')}</dd>
                      </div>
                      <div>
                        <dt>{t('find.degree')}</dt>
                        <dd>{scholarship.degree || t('common.notRecorded')}</dd>
                      </div>
                      <div>
                        <dt>{t('find.funding')}</dt>
                        <dd>{scholarship.funding || t('common.notRecorded')}</dd>
                      </div>
                      <div>
                        <dt>{t('find.deadline')}</dt>
                        <dd>
                          {scholarship.deadline || scholarship.deadline_date ? (
                            <>
                              {scholarship.deadline || scholarship.deadline_date}
                              {scholarship.deadline_note ? <span className="jcard__note-inline"> · {scholarship.deadline_note}</span> : null}
                            </>
                          ) : (
                            <span className="jmuted">{t('common.checkOfficialSource')}</span>
                          )}
                        </dd>
                      </div>
                    </dl>
                    <div className="jcatalogue__card-actions">
                      <label className="jcatalogue__select">
                        <input
                          type="checkbox"
                          checked={selectedScholarshipIds.has(scholarship.id)}
                          onChange={() => toggleSelection(scholarship.id)}
                        />
                        <span>{t('find.select')}</span>
                      </label>
                      <button
                        type="button"
                        className="jbtn jbtn--primary"
                        onClick={() => addFromCatalogue(scholarship)}
                        disabled={state.shortlist.some((entry) => entry.catalogueId === scholarship.id)}
                      >
                        {state.shortlist.some((entry) => entry.catalogueId === scholarship.id) ? t('find.added') : t('find.addToJourney')}
                      </button>
                      {scholarship.official_source_url && (
                        <ExternalLink href={scholarship.official_source_url} className="jbtn jbtn--quiet">
                          {t('sources.url')}
                        </ExternalLink>
                      )}
                    </div>
                  </li>
                ))}
              </ul>

              {/* Pagination */}
              {catalogueTotalPages > 1 && (
                <div className="jcatalogue__pagination">
                  <button
                    type="button"
                    className="jbtn jbtn--quiet"
                    disabled={cataloguePage === 1}
                    onClick={() => loadCatalogue(cataloguePage - 1)}
                  >
                    {t('nav.previous')}
                  </button>
                  <span className="jcatalogue__page-info">
                    {t('find.pageOf') || 'Page'} {cataloguePage} {t('nav.of')} {catalogueTotalPages}
                  </span>
                  <button
                    type="button"
                    className="jbtn jbtn--quiet"
                    disabled={cataloguePage === catalogueTotalPages}
                    onClick={() => loadCatalogue(cataloguePage + 1)}
                  >
                    {t('nav.next')}
                  </button>
                </div>
              )}

              {/* Bulk add */}
              {selectedScholarshipIds.size > 0 && (
                <div className="jcatalogue__bulk-actions">
                  <button type="button" className="jbtn jbtn--primary" onClick={addMultipleFromCatalogue}>
                    {t('find.addSelected') || 'Add selected'} ({selectedScholarshipIds.size})
                  </button>
                  <button type="button" className="jbtn jbtn--quiet" onClick={() => setSelectedScholarshipIds(new Set())}>
                    {t('common.cancel')}
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Manual entry form */}
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

      {/* Add entry button when list has items */}
      {(state.shortlist.length > 0 || showCatalogue) && !showForm ? (
        <div className="jlist__actions">
          <button type="button" className="jbtn jbtn--quiet" onClick={() => setShowForm(true)}>
            {t('find.add')}
          </button>
          {!showCatalogue && (
            <button type="button" className="jbtn jbtn--secondary" onClick={() => setShowCatalogue(true)}>
              {t('find.browseCatalogue') || 'Browse catalogue'}
            </button>
          )}
        </div>
      ) : null}

      {/* Shortlist cards */}
      <ul className="jcards">
        {state.shortlist.map((entry) => (
          <li className={`jcard${entry.sample ? ' jcard--sample' : ''}`} key={entry.id}>
            <div className="jcard__head">
              <h3 className="jcard__title">{entry.name || t('common.unknown')}</h3>
              {entry.sample ? <StatusChip tone="warning">{t('find.sampleBadge')}</StatusChip> : null}
              {entry.catalogueId ? <StatusChip tone="info">{t('find.fromCatalogue') || 'From catalogue'}</StatusChip> : null}
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
