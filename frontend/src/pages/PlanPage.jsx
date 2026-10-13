import { useCallback, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useScholarshipDirectory } from '../hooks/useScholarshipDirectory'
import { useSavedScholarships } from '../hooks/useSavedScholarships'
import {
  CHECKLIST_ITEMS,
  clearChecklist,
  clearRecentlyViewed,
  exportPlan,
  importPlan,
  MAX_NOTE_LENGTH,
  readChecklists,
  readChecklist,
  readRecentlyViewed,
  readScholarshipNotes,
  setChecklistItem,
  writeScholarshipNote,
} from '../services/planStorage.js'
import { describeFunding } from '../utils/fundingFacts.js'
import { getDeadlineLabel } from '../utils/scholarshipPresentation.js'
import { HowToUse } from '../features/tutorials'
import './PlanPage.css'

/** ISO month bucket a record's deadline falls in, or null when unknown. */
function deadlineMonthOf(scholarship) {
  if (typeof scholarship?.deadline_date !== 'string' || scholarship.deadline_date.trim() === '') {
    return null
  }
  const date = new Date(`${scholarship.deadline_date}T00:00:00`)
  if (Number.isNaN(date.getTime())) {
    return null
  }
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
}

/** A human month heading for a bucket key. */
function monthHeading(key) {
  return new Intl.DateTimeFormat(undefined, { month: 'long', year: 'numeric' })
    .format(new Date(`${key}-01T00:00:00`))
}

/**
 * The planning workspace for a signed-out student.
 *
 * The signed-in workspace is `/dashboard` and `/applications`, and it is
 * server-backed: a weighted checklist, private notes and a state machine live
 * there. This page is the anonymous half, built on browser-local storage, and
 * it does not duplicate that. It covers what has to work before an account
 * exists: what was recently opened, what to do next for each saved award, where
 * the deadlines fall, a place to write while reading, and a way to take a copy
 * of all of it.
 *
 * Three rules, each of which a broken version would violate:
 *
 *   - A failed write is reported, not retried as a success. `planStorage`
 *     returns a boolean and it is surfaced through a status line.
 *   - No control claims a cloud sync. The copy says the data is in this
 *     browser, and the exported file carries the same statement inside itself.
 *   - A record with no published deadline is excluded from the timeline rather
 *     than placed in a bucket whose contents would look like "no date".
 */
export default function PlanPage() {
  const { scholarships, isLoading, isUsingFallback } = useScholarshipDirectory()
  const { savedIds } = useSavedScholarships()

  // Local mirror of the plan store, refreshed from storage after each write so
  // the rendered state is always what was actually persisted.
  const [recentlyViewed, setRecentlyViewed] = useState(() => readRecentlyViewed())
  const [notes, setNotes] = useState(() => readScholarshipNotes())
  const [checklists, setChecklists] = useState(() => readChecklists())
  const [status, setStatus] = useState(null)
  // The one note being edited, kept out of `notes` so a half-typed sentence is
  // not written on every keystroke and a discarded edit leaves the stored note
  // alone.
  const [noteDraft, setNoteDraft] = useState({ id: null, value: '' })

  const refresh = useCallback(() => {
    setRecentlyViewed(readRecentlyViewed())
    setNotes(readScholarshipNotes())
    setChecklists(readChecklists())
  }, [])

  const byId = useMemo(
    () => new Map(scholarships.map((scholarship) => [String(scholarship.id), scholarship])),
    [scholarships],
  )

  const resolve = useCallback(
    (ids) => ids.map((id) => byId.get(id)).filter(Boolean),
    [byId],
  )

  const recentRecords = useMemo(() => resolve(recentlyViewed), [recentlyViewed, resolve])
  const savedRecords = useMemo(() => resolve(savedIds), [savedIds, resolve])

  const deadlineBuckets = useMemo(() => {
    const buckets = new Map()
    for (const scholarship of savedRecords) {
      const key = deadlineMonthOf(scholarship)
      if (!key) {
        continue
      }
      if (!buckets.has(key)) {
        buckets.set(key, [])
      }
      buckets.get(key).push(scholarship)
    }
    return [...buckets.entries()].sort(([first], [second]) => first.localeCompare(second))
  }, [savedRecords])

  const datedCount = deadlineBuckets.reduce((total, [, records]) => total + records.length, 0)
  const undatedCount = savedRecords.length - datedCount

  // Between the three views, only `resolve` depends on the catalogue arriving
  // late: it maps ids to records, and an id whose record has not loaded yet
  // resolves to nothing. The plan store itself is read by the lazy state
  // initialisers above, which is why there is no mount effect - re-reading it
  // there would be a cascading render for a value that cannot have changed.

  function onToggleChecklist(id, item) {
    const checked = checklists[id] || readChecklist(id)
    const willBeChecked = !checked.includes(item)
    const ok = setChecklistItem(id, item, willBeChecked)
    setStatus(ok ? null : { tone: 'error', text: 'This browser would not store that change.' })
    refresh()
  }

  function onResetChecklist(id) {
    const ok = clearChecklist(id)
    setStatus(ok ? null : { tone: 'error', text: 'This browser would not store that change.' })
    refresh()
  }

  function onSaveNote(id, value) {
    const ok = writeScholarshipNote(id, value)
    setStatus(ok ? null : { tone: 'error', text: 'This browser would not store that note.' })
    setNoteDraft({ id: null, value: '' })
    refresh()
  }

  function onExport() {
    const plan = exportPlan()
    const blob = new Blob([JSON.stringify(plan, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `scholarzone-plan-${new Date().toISOString().slice(0, 10)}.json`
    document.body.appendChild(anchor)
    anchor.click()
    document.body.removeChild(anchor)
    // Revoked on the next tick, so the download the click started has begun.
    setTimeout(() => URL.revokeObjectURL(url), 0)
    setStatus({ tone: 'ok', text: 'Exported. Keep the file — this is the only copy outside this browser.' })
  }

  async function onImportFile(event) {
    const file = event.target.files?.[0]
    if (!file) {
      return
    }

    try {
      const result = importPlan(JSON.parse(await file.text()))
      if (result.ok) {
        refresh()
        setStatus({ tone: 'ok', text: 'Plan restored from the file.' })
      } else {
        setStatus({ tone: 'error', text: result.reason })
      }
    } catch {
      // A file that is not JSON is the common case here, and "could not be
      // read" is more useful than a parser error message.
      setStatus({ tone: 'error', text: 'That file could not be read as JSON.' })
    } finally {
      // Reset so choosing the same file twice in a row fires again.
      event.target.value = ''
    }
  }

  return (
        <section className="plan-page">
          {/* Contextual help, before the heading and the local-storage notice.
              The notice is the load-bearing claim on this page — that nothing is
              synced — so the guide must not appear between it and the reader. */}
          <HowToUse route="/plan" />
          <header className="plan-page__heading">
            <div>
              <p className="plan-page__eyebrow">Your plan</p>
              <h1>Planning workspace</h1>
          <p>
            {/* Stated plainly, because it is the one thing a student might
                otherwise assume. A server-backed workspace exists once signed
                in, and it is linked rather than duplicated here. */}
            Saved on this device only. Nothing here is synced to an account &mdash; export a copy to keep it.
          </p>
        </div>
        <Link to="/dashboard" className="plan-page__dashboard-link">
          Signed-in workspace &rarr;
        </Link>
      </header>

      {/* ── Recently viewed ───────────────────────────────────────────── */}
      <section className="plan-page__section" aria-labelledby="plan-recent-heading">
        <div className="plan-page__section-head">
          <h2 id="plan-recent-heading">Recently viewed</h2>
          {recentlyViewed.length > 0 && (
            <button
              type="button"
              onClick={() => {
                clearRecentlyViewed()
                setRecentlyViewed([])
              }}
            >
              Clear history
            </button>
          )}
        </div>

        {recentRecords.length === 0 ? (
          <p className="plan-page__empty">
            Scholarships you open will be listed here so you can find your way back.
            {' '}
            <Link to="/scholarships">Browse the catalogue</Link>.
          </p>
        ) : (
          <ul className="plan-page__record-list">
            {recentRecords.map((scholarship) => (
              <li key={scholarship.id}>
                <Link to={`/scholarships/${scholarship.id}`}>{scholarship.title}</Link>
                <span>{getDeadlineLabel(scholarship)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* ── Saved + checklist ────────────────────────────────────────── */}
      <section className="plan-page__section" aria-labelledby="plan-saved-heading">
        <div className="plan-page__section-head">
          <h2 id="plan-saved-heading">Application checklist</h2>
          <span>{savedRecords.length} saved</span>
        </div>

        {isLoading ? (
          <p className="plan-page__empty" aria-busy="true">Loading your saved scholarships&hellip;</p>
        ) : savedRecords.length === 0 ? (
          <p className="plan-page__empty">
            Save a scholarship to build a checklist for it.
            {' '}
            <Link to="/scholarships">Browse the catalogue</Link>.
          </p>
        ) : (
          <ul className="plan-page__checklists">
            {savedRecords.map((scholarship) => {
              const id = String(scholarship.id)
              const checked = checklists[id] || []
              return (
                <li key={id} className="plan-page__checklist">
                  <div className="plan-page__checklist-head">
                    <h3>
                      <Link to={`/scholarships/${id}`}>{scholarship.title}</Link>
                    </h3>
                    <span className="plan-page__checklist-progress">
                      {checked.length} of {CHECKLIST_ITEMS.length} done
                    </span>
                  </div>
                  <p className="plan-page__checklist-funding">{describeFunding(scholarship)}</p>

                  <ul className="plan-page__checkitems">
                    {CHECKLIST_ITEMS.map((item) => (
                      <li key={item.value}>
                        <label>
                          <input
                            type="checkbox"
                            checked={checked.includes(item.value)}
                            onChange={() => onToggleChecklist(id, item.value)}
                          />
                          <span>{item.label}</span>
                        </label>
                      </li>
                    ))}
                  </ul>

                  <div className="plan-page__checklist-actions">
                    <button
                      type="button"
                      onClick={() => onResetChecklist(id)}
                      disabled={checked.length === 0}
                    >
                      Reset checklist
                    </button>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </section>

      {/* ── Deadline planning view ───────────────────────────────────── */}
      <section className="plan-page__section" aria-labelledby="plan-deadlines-heading">
        <div className="plan-page__section-head">
          <h2 id="plan-deadlines-heading">Deadline planner</h2>
          <span>
            {deadlineBuckets.length === 0
              ? 'No dated deadlines saved'
              : `${deadlineBuckets.length} month${deadlineBuckets.length === 1 ? '' : 's'}`}
          </span>
        </div>

        {deadlineBuckets.length === 0 ? (
          <p className="plan-page__empty">
            {savedRecords.length === 0
              ? 'Save a scholarship with a published deadline and it will appear here by month.'
              : 'None of your saved scholarships has a published deadline date. Their deadlines are reported as not stated rather than guessed at.'}
          </p>
        ) : (
          <ol className="plan-page__timeline">
            {deadlineBuckets.map(([bucket, records]) => (
              <li key={bucket}>
                <h3>{monthHeading(bucket)}</h3>
                <ul>
                  {records.map((scholarship) => (
                    <li key={scholarship.id}>
                      <Link to={`/scholarships/${scholarship.id}`}>{scholarship.title}</Link>
                      <span>{getDeadlineLabel(scholarship)}</span>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ol>
        )}

        {/* Said, so the count of saved awards and the count on this timeline
            can be reconciled by the reader rather than by guessing. */}
        {undatedCount > 0 && (
          <p className="plan-page__note">
            {undatedCount} of your {savedRecords.length} saved
            {savedRecords.length === 1 ? ' award has' : ' awards have'} no published deadline date,
            so {savedRecords.length === 1 ? 'it is' : 'they are'} not on this timeline.
          </p>
        )}
      </section>

      {/* ── Notes ────────────────────────────────────────────────────── */}
      <section className="plan-page__section" aria-labelledby="plan-notes-heading">
        <div className="plan-page__section-head">
          <h2 id="plan-notes-heading">Notes</h2>
          <span>{Object.keys(notes).length} saved</span>
        </div>

        {savedRecords.length === 0 ? (
          <p className="plan-page__empty">Notes appear against a saved scholarship.</p>
        ) : (
          <ul className="plan-page__notes">
            {savedRecords.map((scholarship) => {
              const id = String(scholarship.id)
              const isEditing = noteDraft.id === id
              return (
                <li key={id}>
                  <label htmlFor={`plan-note-${id}`}>
                    <Link to={`/scholarships/${id}`}>{scholarship.title}</Link>
                  </label>
                  <textarea
                    id={`plan-note-${id}`}
                    rows={3}
                    maxLength={MAX_NOTE_LENGTH}
                    placeholder="Your own note — why this one, what to ask, what is missing."
                    value={isEditing ? noteDraft.value : (notes[id] ?? '')}
                    onChange={(event) => setNoteDraft({ id, value: event.target.value })}
                    onBlur={(event) => onSaveNote(id, event.target.value)}
                  />
                </li>
              )
            })}
          </ul>
        )}
      </section>

      {/* ── Export / import ──────────────────────────────────────────── */}
      <section className="plan-page__section" aria-labelledby="plan-backup-heading">
        <div className="plan-page__section-head">
          <h2 id="plan-backup-heading">Back up or move your plan</h2>
        </div>

        <p className="plan-page__empty">
          The export holds your recently viewed list, checklists and notes. It does not sync anywhere
          on its own &mdash; it is a file you keep.
        </p>

        <div className="plan-page__backup">
          <button type="button" onClick={onExport}>Export my plan</button>

          <label className="plan-page__import">
            <span>Import a plan file</span>
            <input type="file" accept="application/json,.json" onChange={onImportFile} />
          </label>
        </div>

        {status && (
          <p
            role="status"
            className={status.tone === 'ok' ? 'plan-page__status is-ok' : 'plan-page__status is-error'}
          >
            {status.text}
          </p>
        )}

        {isUsingFallback && (
          <p className="plan-page__note">
            The catalogue snapshot could not be read, so some saved and recently viewed awards may be
            missing from the lists above.
          </p>
        )}
      </section>
    </section>
  )
}
