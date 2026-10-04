import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  fetchDetail,
  fetchQueue,
  fetchSummary,
  submitDecision,
} from '../services/adminVerificationService'
import '../styles/adminVerification.css'

/**
 * Admin Verification Center.
 *
 * Nothing here decides anything. The queue, the counts and the record being
 * reviewed are all read from the administrator API, and a decision is a request
 * the server may refuse. Hiding this page would be cosmetic: the API rejects an
 * unauthenticated caller on its own.
 */

const STATUS_LABELS = {
  active: 'Active',
  needs_review: 'Needs review',
  uncertain: 'Uncertain',
  failed: 'Failed',
  quarantined: 'Quarantined',
  inactive: 'Inactive',
}

const DECISIONS = [
  {
    value: 'verify',
    label: 'Verify',
    hint: 'Confirm the record is trustworthy and publish it as verified.',
  },
  {
    value: 'keep_under_review',
    label: 'Keep under review',
    hint: 'Leave the record unresolved so it stays out of verified claims.',
  },
  {
    value: 'reject',
    label: 'Reject',
    hint: 'Mark the record inactive. It stops being presented as a verified opportunity.',
  },
]

function formatDate(value) {
  if (!value) return '—'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

function Metric({ label, value, hint }) {
  return (
    <div className="avc-metric">
      <span className="avc-metric__value">{value === null ? '—' : value}</span>
      <span className="avc-metric__label">{label}</span>
      {hint ? <span className="avc-metric__hint">{hint}</span> : null}
    </div>
  )
}

export default function AdminVerificationPage() {
  const [adminSecret, setAdminSecret] = useState('')
  const [authError, setAuthError] = useState('')
  const [summary, setSummary] = useState(null)
  const [queue, setQueue] = useState(null)
  const [queueError, setQueueError] = useState('')
  const [settledKey, setSettledKey] = useState(null)
  const [detail, setDetail] = useState(null)
  const [detailError, setDetailError] = useState('')
  const [notice, setNotice] = useState(null)
  const [decisionBusy, setDecisionBusy] = useState(false)
  const [searchParams, setSearchParams] = useSearchParams()
  const panelRef = useRef(null)

  // Filters live in the URL so a reviewed page can be shared and survives refresh.
  const search = searchParams.get('q') || ''
  const status = searchParams.get('status') || ''
  const scope = searchParams.get('scope') || 'all'
  const sort = searchParams.get('sort') || 'next_verification_due'
  const page = Math.max(1, Number(searchParams.get('page') || 1))
  const limit = 25

  // Which record is open is a URL concern, so it is read during render instead
  // of being copied into state. Mirroring it through an effect meant the panel
  // lagged the URL by a render and re-rendered the page for a value already held.
  const recordParam = searchParams.get('record')
  const selectedId = recordParam ? Number(recordParam) : null

  // Identifies the request the current filters describe. Loading is derived from
  // whether that request has settled, so nothing is written to state while an
  // effect body is running.
  const requestKey = adminSecret ? `${adminSecret}|${search}|${status}|${scope}|${sort}|${page}` : null
  const loading = requestKey !== null && settledKey !== requestKey

  // Nothing is shown for no selection, without needing to clear state to say so.
  const activeDetail = selectedId === null ? null : detail

  const setParam = useCallback(
    (patch) => {
      const next = new URLSearchParams(searchParams)
      for (const [key, value] of Object.entries(patch)) {
        if (value === '' || value === null || value === undefined) next.delete(key)
        else next.set(key, String(value))
      }
      if (!('page' in patch)) next.set('page', '1')
      setSearchParams(next, { replace: true })
    },
    [searchParams, setSearchParams],
  )

  const requestQueue = useCallback(() => {
    return Promise.all([
      fetchSummary(adminSecret),
      fetchQueue(adminSecret, {
        search,
        verification_status: status,
        scope,
        sort,
        order: 'asc',
        limit,
        offset: (page - 1) * limit,
      }),
    ])
  }, [adminSecret, search, status, scope, sort, page])

  // Fetching the queue is genuine synchronisation with an external system. Every
  // state write happens in a promise callback, never in the effect body, and a
  // stale response is discarded when the filters change underneath it.
  useEffect(() => {
    if (!adminSecret) return undefined
    let cancelled = false
    requestQueue()
      .then(([summaryData, queueData]) => {
        if (cancelled) return
        setSummary(summaryData)
        setQueue(queueData)
        setQueueError('')
      })
      .catch((error) => {
        if (cancelled) return
        if (error.status === 401) setAuthError('That administrator secret was not accepted.')
        else setQueueError(error.message)
      })
      .finally(() => {
        if (!cancelled) setSettledKey(requestKey)
      })
    return () => {
      cancelled = true
    }
  }, [adminSecret, requestQueue, requestKey])

  // Imperative refresh, used after a decision changes a record.
  const loadQueue = useCallback(async () => {
    try {
      const [summaryData, queueData] = await requestQueue()
      setSummary(summaryData)
      setQueue(queueData)
      setQueueError('')
    } catch (error) {
      if (error.status === 401) setAuthError('That administrator secret was not accepted.')
      else setQueueError(error.message)
    } finally {
      setSettledKey(requestKey)
    }
  }, [requestQueue, requestKey])

  useEffect(() => {
    if (selectedId === null || !adminSecret) return undefined
    let cancelled = false
    fetchDetail(adminSecret, selectedId)
      .then((data) => {
        if (cancelled) return
        setDetail(data)
        setDetailError('')
      })
      .catch((error) => {
        if (!cancelled) setDetailError(error.message)
      })
    return () => {
      cancelled = true
    }
  }, [selectedId, adminSecret])

  const decide = async (decisionValue) => {
    if (!activeDetail) return
    const rationale = window.prompt('Rationale for this decision (recorded in the audit trail):')
    if (!rationale || rationale.trim().length < 3) return
    setDecisionBusy(true)
    setNotice(null)
    try {
      const result = await submitDecision(adminSecret, activeDetail.scholarship_id, {
        decision: decisionValue,
        rationale: rationale.trim(),
        expected_updated_at: activeDetail.overview.updated_at,
        expected_verification_status: activeDetail.claims.verification_status,
      })
      setNotice({
        tone: 'ok',
        text: `Recorded. Status is now ${result.verification_status}.`,
      })
      await loadQueue()
      const refreshed = await fetchDetail(adminSecret, activeDetail.scholarship_id)
      setDetail(refreshed)
    } catch (error) {
      setNotice({
        tone: 'error',
        text:
          error.status === 409
            ? 'This record changed while the panel was open. It has been reloaded; review it again before deciding.'
            : error.message,
      })
      if (error.status === 409) {
        const refreshed = await fetchDetail(adminSecret, activeDetail.scholarship_id)
        setDetail(refreshed)
      }
    } finally {
      setDecisionBusy(false)
    }
  }

  const items = queue?.items || []
  const totalPages = queue ? Math.max(1, Math.ceil(queue.total / limit)) : 1
  const metrics = useMemo(
    () => [
      { label: 'Pending review', value: summary?.storage_wide_pending, hint: 'All records awaiting a decision' },
      { label: 'Public pending', value: summary?.public_pending, hint: 'Applicants can see these today' },
      { label: 'Storage-only pending', value: summary?.storage_only_pending, hint: 'Held back, still legitimate work' },
    ],
    [summary],
  )

  return (
    <main className="avc">
      <header className="avc-header">
        <div>
          <p className="avc-eyebrow">ScholarZone administration</p>
          <h1 className="avc-title">Verification Center</h1>
          <p className="avc-sub">
            Every record awaiting a verification decision, read live from the catalogue.
            Counts are computed from the rows themselves and are never pinned in this interface.
          </p>
        </div>
        <div className="avc-metrics">
          {metrics.map((metric) => (
            <Metric key={metric.label} {...metric} />
          ))}
        </div>
      </header>

      <section className="avc-auth" aria-label="Administrator sign in">
        <label className="avc-field" htmlFor="avc-secret">
          Administrator secret
        </label>
        <input
          id="avc-secret"
          className="avc-input"
          type="password"
          autoComplete="off"
          value={adminSecret}
          onChange={(event) => {
            setAdminSecret(event.target.value)
            setAuthError('')
          }}
          placeholder="Required for every request"
        />
        <p className="avc-note">
          Held in memory for this session only. It is never stored in the browser and never
          sent anywhere except this site&rsquo;s own API.
        </p>
        {authError ? (
          <p className="avc-error" role="alert">
            {authError}
          </p>
        ) : null}
      </section>

      {adminSecret ? (
        <div className="avc-workspace">
          <section className="avc-queue" aria-label="Review queue">
            <div className="avc-filters">
              <label className="avc-visually-hidden" htmlFor="avc-search">
                Search by name or ID
              </label>
              <input
                id="avc-search"
                className="avc-input"
                type="search"
                placeholder="Search name or ID"
                defaultValue={search}
                onBlur={(event) => setParam({ q: event.target.value.trim() })}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') setParam({ q: event.currentTarget.value.trim() })
                }}
              />

              <label className="avc-visually-hidden" htmlFor="avc-status">
                Verification status
              </label>
              <select
                id="avc-status"
                className="avc-input"
                value={status}
                onChange={(event) => setParam({ status: event.target.value })}
              >
                <option value="">Any status</option>
                {Object.entries(STATUS_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>

              <label className="avc-visually-hidden" htmlFor="avc-scope">
                Visibility
              </label>
              <select
                id="avc-scope"
                className="avc-input"
                value={scope}
                onChange={(event) => setParam({ scope: event.target.value })}
              >
                <option value="all">Public and storage-only</option>
                <option value="public">Public only</option>
                <option value="storage_only">Storage-only only</option>
              </select>

              <label className="avc-visually-hidden" htmlFor="avc-sort">
                Sort
              </label>
              <select
                id="avc-sort"
                className="avc-input"
                value={sort}
                onChange={(event) => setParam({ sort: event.target.value })}
              >
                <option value="next_verification_due">Next due</option>
                <option value="updated_at">Recently updated</option>
                <option value="deadline_date">Deadline</option>
                <option value="country">Country</option>
                <option value="title">Name</option>
              </select>
            </div>

            {queueError ? (
              <p className="avc-error" role="alert">
                {queueError}
              </p>
            ) : null}

            <p className="avc-count" aria-live="polite">
              {loading ? 'Loading…' : `${queue?.total ?? 0} record(s) awaiting a decision`}
            </p>

            <ul className="avc-rows">
              {items.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    className={`avc-row${item.id === selectedId ? ' avc-row--active' : ''}`}
                    onClick={() => setParam({ record: item.id })}
                    aria-current={item.id === selectedId ? 'true' : undefined}
                  >
                    <span className="avc-row__id">{item.id}</span>
                    <span className="avc-row__title">{item.title}</span>
                    <span className="avc-row__meta">
                      {item.country} · {item.degree}
                    </span>
                    <span className="avc-row__badges">
                      <span className={`avc-badge avc-badge--${item.scope}`}>
                        {item.scope === 'public' ? 'Public' : 'Storage-only'}
                      </span>
                      <span className="avc-badge avc-badge--status">
                        {STATUS_LABELS[item.verification_status] || item.verification_status}
                      </span>
                      {item.open_conflicts > 0 ? (
                        <span className="avc-badge avc-badge--conflict">
                          {item.open_conflicts} conflict{item.open_conflicts > 1 ? 's' : ''}
                        </span>
                      ) : null}
                      {item.is_archived ? <span className="avc-badge">Archived</span> : null}
                    </span>
                    <span className="avc-row__dates">
                      Due {formatDate(item.next_verification_due)} · Updated{' '}
                      {formatDate(item.updated_at)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>

            <nav className="avc-pager" aria-label="Queue pages">
              <button
                type="button"
                className="avc-btn"
                disabled={page <= 1}
                onClick={() => setParam({ page: page - 1 })}
              >
                Previous
              </button>
              <span>
                Page {page} of {totalPages}
              </span>
              <button
                type="button"
                className="avc-btn"
                disabled={page >= totalPages}
                onClick={() => setParam({ page: page + 1 })}
              >
                Next
              </button>
            </nav>
          </section>

          <section
            className="avc-detail"
            aria-label="Review detail"
            ref={panelRef}
            tabIndex={-1}
          >
            {detailError ? (
              <p className="avc-error" role="alert">
                {detailError}
              </p>
            ) : null}

            {!activeDetail && !detailError ? (
              <p className="avc-empty">Select a record to review it.</p>
            ) : null}

            {activeDetail ? (
              <article className="avc-review">
                {notice ? (
                  <p className={`avc-notice avc-notice--${notice.tone}`} role="status">
                    {notice.text}
                  </p>
                ) : null}

                <h2 className="avc-review__title">{activeDetail.overview.title}</h2>
                <p className="avc-review__id">
                  Record {activeDetail.scholarship_id} ·{' '}
                  {activeDetail.scope === 'public' ? 'Public' : 'Storage-only'}
                </p>

                <section className="avc-block">
                  <h3>Overview</h3>
                  <dl className="avc-dl">
                    <div><dt>Country</dt><dd>{activeDetail.overview.country || '—'}</dd></div>
                    <div><dt>Degree</dt><dd>{activeDetail.overview.degree || '—'}</dd></div>
                    <div><dt>Region</dt><dd>{activeDetail.overview.region || '—'}</dd></div>
                    <div><dt>Funding</dt><dd>{activeDetail.overview.funding || '—'}</dd></div>
                    <div><dt>Deadline</dt><dd>{activeDetail.overview.deadline_display || formatDate(activeDetail.overview.deadline_date)}</dd></div>
                    <div><dt>Archived</dt><dd>{activeDetail.overview.is_archived ? 'Yes' : 'No'}</dd></div>
                  </dl>
                </section>

                <section className="avc-block">
                  <h3>Current claims</h3>
                  <dl className="avc-dl">
                    <div>
                      <dt>Verification status</dt>
                      <dd>{STATUS_LABELS[activeDetail.claims.verification_status] || activeDetail.claims.verification_status}</dd>
                    </div>
                    <div>
                      <dt>Published as verified</dt>
                      <dd>{activeDetail.claims.public_verified ? 'Yes' : 'No'}</dd>
                    </div>
                    <div>
                      <dt>Stored legacy boolean</dt>
                      <dd>
                        {activeDetail.claims.legacy_is_verified ? 'true' : 'false'}{' '}
                        <span className="avc-tag">
                          {activeDetail.claims.legacy_agrees_with_status ? 'agrees' : 'disagrees — diagnostic only'}
                        </span>
                      </dd>
                    </div>
                    <div><dt>Last verified</dt><dd>{formatDate(activeDetail.claims.last_verified_at)}</dd></div>
                    <div><dt>Next due</dt><dd>{formatDate(activeDetail.claims.next_verification_due)}</dd></div>
                    <div><dt>Image state</dt><dd>{activeDetail.claims.image_evaluation_status || 'not evaluated'}</dd></div>
                  </dl>
                </section>

                <section className="avc-block">
                  <h3>Official sources</h3>
                  <dl className="avc-dl">
                    <div><dt>Provider</dt><dd>{activeDetail.sources.official_source || '—'}</dd></div>
                    <div>
                      <dt>Source</dt>
                      <dd>
                        {activeDetail.sources.official_source_url ? (
                          <a href={activeDetail.sources.official_source_url} target="_blank" rel="noreferrer noopener">
                            {activeDetail.sources.official_source_url}
                          </a>
                        ) : (
                          '—'
                        )}
                      </dd>
                    </div>
                    <div><dt>Last verified date</dt><dd>{formatDate(activeDetail.sources.last_verified_date)}</dd></div>
                  </dl>
                </section>

                <section className="avc-block">
                  <h3>Conflicts</h3>
                  {activeDetail.conflicts.length === 0 ? (
                    <p className="avc-empty">No recorded conflicts.</p>
                  ) : (
                    activeDetail.conflicts.map((conflict) => (
                      <div className="avc-conflict" key={conflict.review_id}>
                        <p className="avc-conflict__field">{conflict.field_name}</p>
                        <p className="avc-conflict__reason">{conflict.conflict_reason}</p>
                        <div className="avc-conflict__sides">
                          <div><span>Source A</span><p>{conflict.current_value || '—'}</p></div>
                          <div><span>Source B</span><p>{conflict.proposed_value || '—'}</p></div>
                        </div>
                        {conflict.source_urls?.length ? (
                          <ul className="avc-conflict__sources">
                            {conflict.source_urls.map((u) => (
                              <li key={u}>{u}</li>
                            ))}
                          </ul>
                        ) : null}
                      </div>
                    ))
                  )}
                </section>

                <section className="avc-block">
                  <h3>Verification history</h3>
                  {activeDetail.history.length === 0 ? (
                    <p className="avc-empty">No recorded history.</p>
                  ) : (
                    <ol className="avc-history">
                      {activeDetail.history.map((entry) => (
                        <li key={entry.id}>
                          <span className="avc-history__when">{formatDate(entry.created_at)}</span>
                          <span className="avc-history__what">
                            {entry.field_name}: {entry.old_value || '—'} → {entry.new_value || '—'}
                          </span>
                          <span className="avc-history__type">{entry.change_type}</span>
                          {entry.evidence_text ? (
                            <p className="avc-history__evidence">{entry.evidence_text}</p>
                          ) : null}
                        </li>
                      ))}
                    </ol>
                  )}
                </section>

                <section className="avc-block avc-decision">
                  <h3>Decision</h3>
                  <p className="avc-note">
                    Each decision is recorded with your rationale and the version of the record
                    you were reading. If someone else decides first, this panel will refuse to
                    overwrite their work.
                  </p>
                  <div className="avc-decision__actions">
                    {DECISIONS.map((option) => (
                      <button
                        key={option.value}
                        type="button"
                        className="avc-btn avc-btn--primary"
                        disabled={decisionBusy}
                        onClick={() => decide(option.value)}
                        title={option.hint}
                      >
                        {option.label}
                      </button>
                    ))}
                  </div>
                  <p className="avc-note">No bulk action exists: a verification claim is made about a specific source.</p>
                </section>
              </article>
            ) : null}
          </section>
        </div>
      ) : (
        <p className="avc-empty">
          Enter the administrator secret to load the queue. No review data is requested before
          the server accepts it.
        </p>
      )}
    </main>
  )
}