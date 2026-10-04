/* Supervisor discovery panel.
 *
 * The panel's job is to be honest about what ScholarZone knows. Every state a
 * scholarship can be in gets its own rendering, and none of them is a blank box:
 *
 *   verified supervisors   → the list
 *   none verified          → "no verified supervisors found yet", plus what that
 *                            does and does not mean
 *   discovery pending      → explicitly not searched yet
 *   source blocked         → the university page could not be read, and that this
 *                            is a retryable access failure rather than a finding
 *   stale                  → the evidence has aged out of its window
 *   unavailable            → the feature could not be loaded at all
 *
 * The one thing this component will not do is imply that a count of zero means
 * the university has no professors. It means ScholarZone has not verified any
 * on an official page, which is a much smaller claim and the only one it can make.
 *
 * No metric appears anywhere in here. There is no acceptance probability, no
 * response rate, no citation count and no ranking, because none of those can be
 * supported by anything this system has measured.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  SupervisorAuthRequired,
  fetchEmailDraft,
  fetchOutreach,
  fetchSupervisors,
  startOutreach,
  updateOutreach,
} from '../services/supervisorService'
import './SupervisorPanel.css'

const BAND_LABELS = {
  strong_research_alignment: 'Strong research alignment',
  moderate_research_alignment: 'Moderate research alignment',
  related: 'Related',
  insufficient_evidence: 'Not enough evidence to compare',
}

const AVAILABILITY_LABELS = {
  masters_supervision: "Master's supervision",
  phd_supervision: 'PhD supervision',
  postdoc_supervision: 'Postdoctoral supervision',
  funding: 'Funding',
}

/* Every non-affirmative state renders the same way: named, not implied. A page
   that simply omits funding would otherwise read as "no funding", which is a
   claim the source never made. */
const AVAILABILITY_STATES = {
  verified_yes: { label: 'Published as open', tone: 'positive' },
  verified_no: { label: 'Published as closed', tone: 'negative' },
  unknown: { label: 'Not stated', tone: 'neutral' },
  not_published: { label: 'Not published on the official page', tone: 'neutral' },
  stale: { label: 'Published earlier — needs re-checking', tone: 'warn' },
}

const OUTREACH_ACTIONS = [
  { value: 'draft', label: 'Save as draft' },
  { value: 'sent', label: 'Mark as sent' },
  { value: 'follow_up_due', label: 'Follow-up due' },
  { value: 'replied', label: 'A reply arrived' },
  { value: 'positive', label: 'Positive reply' },
  { value: 'negative', label: 'Negative reply' },
  { value: 'no_response', label: 'No response' },
  { value: 'closed', label: 'Close this' },
]

/* Research interests are typed by the student and kept in this browser only.
   They are sent with the request and never stored server-side, because an
   interest ScholarZone inferred from anything other than an explicit sentence
   would be an invented fact about a person. */
const INTEREST_STORAGE_KEY = 'sz.researchInterests'

function readInterests() {
  try {
    const raw = window.localStorage.getItem(INTEREST_STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed.filter((item) => typeof item === 'string') : []
  } catch {
    // A blocked or corrupt storage must not break the page.
    return []
  }
}

function AvailabilityRow({ claim }) {
  const state = AVAILABILITY_STATES[claim.state] || {
    label: claim.state,
    tone: 'neutral',
  }
  const scope = AVAILABILITY_LABELS[claim.scope] || claim.scope
  return (
    <li className={`sz-supervisor__availability sz-supervisor__availability--${state.tone}`}>
      <span className="sz-supervisor__availability-scope">{scope}</span>
      <span className="sz-supervisor__availability-state">
        {/* The state is spelled out as well as coloured. Colour alone would
            exclude anyone who cannot distinguish the tones. */}
        <span aria-hidden="true" className="sz-supervisor__dot" />
        {state.label}
      </span>
      <a
        href={claim.source_url}
        target="_blank"
        rel="noreferrer noopener"
        className="sz-supervisor__source-link"
      >
        Source
        <span className="sz-sr-only"> for {scope} on the official page</span>
      </a>
      {claim.verified_at ? (
        <time dateTime={claim.verified_at}>checked {claim.verified_at.slice(0, 10)}</time>
      ) : null}
    </li>
  )
}

function AlignmentNote({ alignment }) {
  const label = BAND_LABELS[alignment.band] || alignment.band
  return (
    <div className={`sz-supervisor__alignment sz-supervisor__alignment--${alignment.band}`}>
      <span className="sz-supervisor__alignment-band">{label}</span>
      <p>{alignment.explanation}</p>
    </div>
  )
}

function ProfessorCard({ professor, onTrack, tracked }) {
  const [draft, setDraft] = useState(null)
  const [draftState, setDraftState] = useState('idle')
  const [draftError, setDraftError] = useState(null)

  const interests = useMemo(() => readInterests(), [])

  const prepareDraft = useCallback(async () => {
    setDraftState('loading')
    setDraftError(null)
    try {
      const result = await fetchEmailDraft({
        scholarshipId: professor.scholarshipId,
        professorId: professor.id,
        interests,
      })
      setDraft(result)
      setDraftState('ready')
    } catch (error) {
      setDraftError(
        error instanceof SupervisorAuthRequired
          ? 'Sign in to prepare an email.'
          : error.message || 'Could not prepare a draft.',
      )
      setDraftState('error')
    }
  }, [interests, professor.id, professor.scholarshipId])

  const track = useCallback(async () => {
    setDraftState('tracking')
    setDraftError(null)
    try {
      await startOutreach({
        scholarshipId: professor.scholarshipId,
        professorId: professor.id,
        draftSubject: draft?.subject,
        draftBody: draft?.body,
      })
      onTrack(professor.id)
    } catch (error) {
      setDraftError(
        error instanceof SupervisorAuthRequired
          ? 'Sign in to track outreach.'
          : error.message || 'Could not save this record.',
      )
      setDraftState('error')
    }
  }, [draft, onTrack, professor.id, professor.scholarshipId])

  return (
    <article className="sz-supervisor">
      <header className="sz-supervisor__header">
        <div>
          <h4 className="sz-supervisor__name">{professor.name}</h4>
          <p className="sz-supervisor__affiliation">
            {[professor.title, professor.department, professor.institution]
              .filter(Boolean)
              .join(' · ')}
          </p>
        </div>
        <span className="sz-supervisor__relationship">
          {professor.relationship_type === 'potential_supervisor'
            ? 'Potential supervisor'
            : 'Research-relevant faculty'}
        </span>
      </header>

      {professor.research_areas?.length ? (
        <ul className="sz-supervisor__areas">
          {professor.research_areas.map((area) => (
            <li key={area}>{area}</li>
          ))}
        </ul>
      ) : (
        <p className="sz-supervisor__areas-empty">
          No research areas are published on the official profile.
        </p>
      )}

      <AlignmentNote alignment={professor.research_alignment} />

      <dl className="sz-supervisor__contact">
        <div>
          <dt>Official profile</dt>
          <dd>
            <a href={professor.official_profile_url} target="_blank" rel="noreferrer noopener">
              View official profile
            </a>
          </dd>
        </div>
        <div>
          <dt>Email</dt>
          <dd>
            {/* Gated on the flag here as well as on the server. The API already
                withholds an unverified address, but a component that renders
                whatever it is handed would display a guess the moment any other
                caller sent one, and an email address is the kind of wrong that
                looks like evidence. */}
            {professor.official_email_verified && professor.official_email ? (
              <>
                <a href={`mailto:${professor.official_email}`}>{professor.official_email}</a>
                <span className="sz-supervisor__verified-note">published on the official page</span>
              </>
            ) : (
              /* No verified address is a normal outcome, not a gap. The
                 instruction is to use the official contact page rather than to
                 guess one from a naming convention. */
              <span className="sz-supervisor__unverified-note">
                No verified email. Use the university profile or contact page.
              </span>
            )}
          </dd>
        </div>
        {professor.lab_url ? (
          <div>
            <dt>Research group</dt>
            <dd>
              <a href={professor.lab_url} target="_blank" rel="noreferrer noopener">
                Lab or group page
              </a>
            </dd>
          </div>
        ) : null}
      </dl>

      <div className="sz-supervisor__availability-block">
        <h5>Availability as published</h5>
        {professor.availability?.length ? (
          <ul className="sz-supervisor__availability-list">
            {professor.availability.map((claim) => (
              <AvailabilityRow key={claim.scope} claim={claim} />
            ))}
          </ul>
        ) : (
          <p className="sz-supervisor__areas-empty">
            No availability information is published for this academic.
          </p>
        )}
      </div>

      <footer className="sz-supervisor__footer">
        <div className="sz-supervisor__actions">
          <button
            type="button"
            className="sz-supervisor__button"
            onClick={prepareDraft}
            disabled={draftState === 'loading'}
          >
            {draftState === 'loading' ? 'Preparing…' : 'Prepare email'}
          </button>
          <button
            type="button"
            className="sz-supervisor__button sz-supervisor__button--quiet"
            onClick={track}
            disabled={tracked}
          >
            {tracked ? 'Tracked' : 'Track outreach'}
          </button>
        </div>

        {draftError ? (
          <p className="sz-supervisor__error" role="alert">
            {draftError}
          </p>
        ) : null}

        {draft ? (
          <div className="sz-supervisor__draft">
            <p className="sz-supervisor__draft-note">
              Review this, then send it yourself from your own mail app. ScholarZone does not
              send email on your behalf.
            </p>
            <label className="sz-supervisor__draft-field">
              <span>Subject</span>
              <input type="text" readOnly value={draft.subject} />
            </label>
            <label className="sz-supervisor__draft-field">
              <span>Message</span>
              <textarea readOnly rows={12} value={draft.body} />
            </label>
            {draft.unresolved?.length ? (
              /* Named rather than silently omitted: the student learns what the
                 system does not actually know before they send. */
              <p className="sz-supervisor__unresolved">
                Not filled in, because it is not verified: {draft.unresolved.join(', ')}. Add
                your own wording where it is missing.
              </p>
            ) : null}
          </div>
        ) : null}
      </footer>

      <details className="sz-supervisor__sources">
        <summary>Where this came from</summary>
        <p>
          Read from{' '}
          <a href={professor.evidence_source_url} target="_blank" rel="noreferrer noopener">
            the official faculty page
          </a>
          {professor.last_verified_at ? ` · last checked ${professor.last_verified_at.slice(0, 10)}` : ''}
        </p>
        {professor.sources?.length ? (
          <ul>
            {professor.sources.map((source) => (
              <li key={`${source.source_url}-${source.retrieved_at}`}>
                <a href={source.source_url} target="_blank" rel="noreferrer noopener">
                  {source.source_host}
                </a>
                {source.retrieved_at ? ` · retrieved ${source.retrieved_at.slice(0, 10)}` : ''}
              </li>
            ))}
          </ul>
        ) : null}
      </details>
    </article>
  )
}

/* The student's private tracker for this scholarship.
 *
 * Entirely separate from the public list above it: what is rendered here is the
 * signed-in student's own record, and it never leaks into any public response. A
 * 401 here is the ordinary signed-out case and renders an invitation to sign in
 * rather than an error. */
function OutreachTracker({ scholarshipId, trackedIds, onChanged }) {
  const [state, setState] = useState('loading')
  const [records, setRecords] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    const controller = new AbortController()
    fetchOutreach({ signal: controller.signal })
      .then((result) => {
        setRecords(result.filter((record) => record.scholarship_id === scholarshipId))
        setState('ready')
      })
      .catch((caught) => {
        if (caught.name === 'AbortError') return
        if (caught instanceof SupervisorAuthRequired) {
          setState('signed-out')
          return
        }
        setError(caught.message || 'Could not load your outreach records.')
        setState('error')
      })
    return () => controller.abort()
    // trackedIds changes when this panel saves a record, which is exactly when
    // the list needs re-reading.
  }, [scholarshipId, trackedIds])

  const advance = useCallback(
    async (record, nextStatus) => {
      try {
        // The version is sent back so a concurrent edit is refused rather than
        // silently overwritten.
        const updated = await updateOutreach(record.id, {
          version: record.version,
          status: nextStatus,
        })
        setRecords((previous) =>
          previous.map((item) => (item.id === updated.id ? updated : item)),
        )
        onChanged?.(updated.professor_id)
      } catch (caught) {
        if (caught instanceof SupervisorAuthRequired) {
          setState('signed-out')
          return
        }
        setError(caught.message || 'Could not update that record.')
      }
    },
    [onChanged],
  )

  if (state === 'signed-out') {
    return (
      <p className="sz-supervisor-panel__state">
        Sign in to prepare an email and keep a private record of who you contacted.
      </p>
    )
  }
  if (state === 'loading') {
    return (
      <p className="sz-supervisor-panel__state" aria-live="polite">
        Loading your outreach for this scholarship…
      </p>
    )
  }
  if (state === 'error') {
    return (
      <p className="sz-supervisor-panel__state sz-supervisor-panel__state--error" role="alert">
        {error}
      </p>
    )
  }
  if (records.length === 0) {
    return (
      <p className="sz-supervisor-panel__state">
        You have not contacted anyone about this scholarship yet.
      </p>
    )
  }

  return (
    <div className="sz-supervisor-panel__tracker">
      <h4>Your outreach</h4>
      {error ? (
        <p className="sz-supervisor__error" role="alert">
          {error}
        </p>
      ) : null}
      <ul>
        {records.map((record) => (
          <li key={record.id} className="sz-supervisor__tracker-row">
            <span className="sz-supervisor__tracker-status">{record.status.replace(/_/g, ' ')}</span>
            <label>
              <span className="sz-sr-only">Update status</span>
              <select
                value={record.status}
                onChange={(event) => advance(record, event.target.value)}
              >
                {OUTREACH_ACTIONS.map((action) => (
                  <option key={action.value} value={action.value}>
                    {action.label}
                  </option>
                ))}
              </select>
            </label>
            {record.next_action ? (
              <span className="sz-supervisor__tracker-next">{record.next_action}</span>
            ) : null}
          </li>
        ))}
      </ul>
      <p className="sz-supervisor-panel__state">
        Only you can see this. No response rate is shown, because there is not yet enough real
        data to state one honestly.
      </p>
    </div>
  )
}

export default function SupervisorPanel({ scholarshipId, initialState = 'loading' }) {
  const [state, setState] = useState(initialState)
  const [payload, setPayload] = useState(null)
  const [error, setError] = useState(null)
  const [trackedIds, setTrackedIds] = useState(() => new Set())
  const [interestsInput, setInterestsInput] = useState(() => readInterests().join(', '))

  /* Fetches and commits the result without touching state synchronously.

     Kept as one function so the initial load and a later re-run after the
     student changes their interests follow exactly the same path; two
     implementations would drift, and the drift would show up as a stale count
     that only one entry point could refresh. */
  const runFetch = useCallback(
    async (signal, interests) => {
      try {
        const result = await fetchSupervisors(scholarshipId, { interests, signal })
        setPayload(result)
        setError(null)
        setState('ready')
      } catch (caught) {
        if (caught.name === 'AbortError') return
        setError(caught.message || 'Could not load supervisor information.')
        setState('error')
      }
    },
    [scholarshipId],
  )

  useEffect(() => {
    const controller = new AbortController()
    /* Promise chain inline in the effect, matching how the rest of the app
       loads data. Naming the loader and calling it from the effect makes the
       rule about state updates inside effects fire, and the workaround - a
       wrapper that only renames the call - would obscure the real dependency. */
    fetchSupervisors(scholarshipId, { interests: readInterests(), signal: controller.signal })
      .then((result) => {
        setPayload(result)
        setError(null)
        setState('ready')
      })
      .catch((caught) => {
        if (caught.name === 'AbortError') return
        setError(caught.message || 'Could not load supervisor information.')
        setState('error')
      })
    return () => controller.abort()
  }, [scholarshipId])

  const saveInterests = useCallback(() => {
    const next = interestsInput
      .split(',')
      .map((value) => value.trim())
      .filter(Boolean)
      .slice(0, 20)
    try {
      window.localStorage.setItem(INTEREST_STORAGE_KEY, JSON.stringify(next))
    } catch {
      // Storage may be unavailable. The request below still carries the values.
    }
    setState('loading')
    setPayload(null)
    runFetch(undefined, next)
  }, [interestsInput, runFetch])

  const handleTrack = useCallback((professorId) => {
    setTrackedIds((previous) => {
      const next = new Set(previous)
      next.add(professorId)
      return next
    })
  }, [])

  const coverage = payload?.coverage
  const supervisors = (payload?.supervisors || []).map((professor) => ({
    ...professor,
    scholarshipId,
  }))

  return (
    <section className="sz-supervisor-panel" aria-labelledby="sz-supervisor-heading">
      <header className="sz-supervisor-panel__header">
        <div>
          <p className="sz-supervisor-panel__eyebrow">Supervisor discovery</p>
          <h3 id="sz-supervisor-heading">Find potential supervisors</h3>
        </div>
        {coverage ? (
          <p className="sz-supervisor-panel__count">
            {coverage.verified_supervisor_count > 0
              ? `${coverage.verified_supervisor_count} verified`
              : 'None verified yet'}
          </p>
        ) : null}
      </header>

      {/* Alignment needs the student's own words. Absent them the band is
          INSUFFICIENT EVIDENCE for everyone, which is correct rather than a
          failure, so the field is offered rather than demanded. */}
      <div className="sz-supervisor-panel__interests">
        <label htmlFor="sz-interests">Your research interests</label>
        <input
          id="sz-interests"
          type="text"
          value={interestsInput}
          placeholder="e.g. machine learning, public health"
          onChange={(event) => setInterestsInput(event.target.value)}
        />
        <button type="button" onClick={saveInterests}>
          Compare
        </button>
        <p>
          Used only to compare your words with published faculty areas. Stored in this browser,
          never inferred from anything else.
        </p>
      </div>

      {state === 'loading' ? (
        <p className="sz-supervisor-panel__state" aria-live="polite">
          Looking for published faculty information…
        </p>
      ) : null}

      {state === 'error' ? (
        <p className="sz-supervisor-panel__state sz-supervisor-panel__state--error" role="alert">
          Supervisor information is unavailable right now. {error}
        </p>
      ) : null}

      {state === 'ready' && coverage ? (
        <>
          {coverage.coverage_status === 'search_pending' ? (
            <p className="sz-supervisor-panel__state">
              Supervisor discovery has not been completed for this programme yet. This does not
              mean there are no supervisors — it means ScholarZone has not checked.
            </p>
          ) : null}

          {coverage.coverage_status === 'source_blocked' ? (
            <p className="sz-supervisor-panel__state">
              The university page could not be reached for verification. This is a temporary access
              problem, not a finding about the university.
            </p>
          ) : null}

          {coverage.coverage_status === 'source_requires_rendering' ? (
            /* A distinct state from "none found", and the distinction is the
               point. The institution publishes its faculty, but only after its
               browser runs the page's JavaScript, so ScholarZone was served a
               shell. Saying "no supervisors found" here would assert something
               about the university that nobody established. */
            <p className="sz-supervisor-panel__state">
              This university publishes its staff directory only after the page loads in a browser,
              so ScholarZone cannot read it yet. No supervisors are listed here because none could
              be verified — not because the university has none.
            </p>
          ) : null}

          {coverage.coverage_status === 'needs_verification' ? (
            <p className="sz-supervisor-panel__state">
              Some faculty were found, but only on secondary sources. They stay hidden until an
              official university page confirms the connection.
            </p>
          ) : null}

          {coverage.coverage_status === 'not_applicable' ? (
            <p className="sz-supervisor-panel__state">
              This institution does not publish faculty supervision information for this award.
            </p>
          ) : null}

          {coverage.coverage_status === 'no_verified_supervisor_found' ? (
            <p className="sz-supervisor-panel__state">
              No verified supervisors found yet. ScholarZone only lists an academic once an
              official university page confirms the connection, so this usually means the faculty
              page was not reachable or not linked from the programme page — not that no professors
              exist.
            </p>
          ) : null}

          {supervisors.length > 0 ? (
            <>
              <p className="sz-supervisor-panel__intro">
                Listed because an official university page connects them to this programme. Their
                availability is shown exactly as published, including when it is not published at
                all.
              </p>
              <div className="sz-supervisor-panel__list">
                {supervisors.map((professor) => (
                  <ProfessorCard
                    key={professor.id}
                    professor={professor}
                    onTrack={handleTrack}
                    tracked={trackedIds.has(professor.id)}
                  />
                ))}
              </div>
            </>
          ) : null}

          <OutreachTracker
            scholarshipId={scholarshipId}
            trackedIds={trackedIds}
            onChanged={handleTrack}
          />
        </>
      ) : null}
    </section>
  )
}

export { BAND_LABELS, AVAILABILITY_LABELS, OUTREACH_ACTIONS }