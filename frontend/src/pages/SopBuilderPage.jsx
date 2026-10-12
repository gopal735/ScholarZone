import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  APPLICATION_TYPES,
  REVIEW_DIMENSIONS,
  REVIEW_DISCLAIMER,
  SOP_SECTIONS,
} from '../services/sopBuilderSections.js'
import {
  BACKGROUND_FIELDS,
  clearAllSections,
  clearSubstantiation,
  countWords,
  eraseEverything,
  importDraft,
  normalizeWordLimit,
  readDraft,
  wordLimitIsAuthoritative,
  writeApproval,
  writeBackground,
  writeContext,
  writeSection,
  writeSubstantiation,
} from '../services/sopBuilderStorage.js'
import { SEVERITY, reviewDraft } from '../services/sopBuilderReview.js'
import { exportFileName, toMarkdown, toPlainText } from '../services/sopBuilderExport.js'
import './SopBuilderPage.css'

/**
 * The statement-of-purpose builder.
 *
 * A guided writing workspace that runs entirely in the browser. There is no
 * server, no account and no network call anywhere in this feature - which is a
 * design decision, not a limitation: a student's statement of purpose, their
 * background notes and their achievement claims are among the most sensitive
 * things this product could hold, and keeping them out of the database is the
 * cheapest possible way to be able to say, accurately, that they never left the
 * device.
 *
 * The precedent for a browser-local workspace in this codebase is `/plan`, and
 * this page follows the same three rules that page established and which
 * `planStorage.js` documents:
 *
 *   - A failed write is reported, never retried as a success. Every write in
 *     this feature returns a boolean and the status line carries it.
 *   - No control claims a cloud sync. The copy says the data is in this browser
 *     because it is, and the exported file repeats it inside the payload.
 *   - Nothing is fabricated. An empty section is empty. No starter text, no
 *     suggested sentence, no generated example appears anywhere, because the one
 *     thing this feature must never do is put words about a student's
 *     achievements into the student's own document.
 *
 * What the builder adds beyond `/plan` is the review step: six deterministic
 * checks over the student's own text, and a claim ledger that asks them to
 * substantiate the factual claims they have made before they rely on them. It is
 * explicitly not a language model, and the interface says so wherever the review
 * is shown, because a student who cannot tell the difference between a check and
 * a judgement will trust the wrong one.
 */

/* ── Small presentational pieces ───────────────────────────────────── */

/** A word count that never reads as a quota. */
function WordCount({ words }) {
  return <span className="sop-count">{words} {words === 1 ? 'word' : 'words'}</span>
}

/** The privacy statement, stated once and everywhere it matters. */
function LocalStorageNotice({ compact = false }) {
  return (
    <p className={compact ? 'sop-local sop-local--compact' : 'sop-local'}>
      <strong>Saved in this browser only.</strong>
      {' '}There is no account, no server and no sync for this workspace. If you clear this
      browser&rsquo;s data it is gone, so export a copy before you do.
    </p>
  )
}

/** A heading row with a count, used by every step panel. */
function StepHeader({ step, title, count }) {  return (
    <div className="sop-step__head">
      <p className="sop-step__eyebrow">Step {step}</p>
      <h2 className="sop-step__title">{title}</h2>
      {count ? <span className="sop-step__count">{count}</span> : null}
    </div>
  )
}

/** The write-status line. Silent on success, loud on failure. */
function StatusLine({ status }) {
  if (!status) {
    return null
  }
  return (
    <p
      role="status"
      className={status.tone === 'error' ? 'sop-status sop-status--error' : 'sop-status sop-status--ok'}
    >
      {status.text}
    </p>
  )
}

/** A finding row. States the rule, not a verdict. */
function FindingRow({ finding }) {
  const section = SOP_SECTIONS.find((entry) => entry.id === finding.sectionId)
  return (
    <li className={`sop-finding sop-finding--${finding.severity}`}>
      <p className="sop-finding__title">
        <span className="sop-finding__severity" aria-hidden="true">
          {finding.severity === SEVERITY.IMPORTANT ? '!' : finding.severity === SEVERITY.ATTENTION ? '•' : '·'}
        </span>
        {finding.title}
      </p>
      {section ? <p className="sop-finding__where">in {section.title}</p> : null}
      <p className="sop-finding__detail">{finding.detail}</p>
    </li>
  )
}

/**
 * A section-completion row.
 *
 * A sibling of `FindingRow`, deliberately not the same component: this is the
 * *guidance* channel, not a finding. It carries no severity badge, because a
 * section with nothing in it is a fact about the draft rather than a defect in
 * the writing, and printing it with a severity marker is what made an untouched
 * draft look like a failing one. The tag on the right says which of the two
 * states the section is in.
 */
function GuidanceRow({ guidance }) {
  const section = SOP_SECTIONS.find((entry) => entry.id === guidance.sectionId)
  const tag = guidance.status === 'empty' ? 'not written yet' : `${guidance.words} words`
  return (
    <li className={`sop-guidance sop-guidance--${guidance.status}`}>
      <p className="sop-guidance__title">
        {section ? section.title : guidance.sectionId}
        <span className="sop-guidance__tag">{tag}</span>
      </p>
      <p className="sop-guidance__detail">{guidance.detail}</p>
    </li>
  )
}

/** One claim in the ledger, with the student's own evidence or removal. */
function ClaimRow({ claim, record, onSubstantiate, onClear }) {
  const [draftEvidence, setDraftEvidence] = useState(
    typeof record?.evidence === 'string' ? record.evidence : '',
  )

  const state = !record
    ? 'open'
    : record.status === 'removed'
      ? 'removed'
      : typeof record.evidence === 'string' && record.evidence.trim() !== ''
        ? 'confirmed'
        : 'confirmed-without-evidence'

  const stateLabel = {
    open: 'Needs your answer',
    removed: 'You marked this for removal',
    confirmed: 'You confirmed this with your own evidence',
    'confirmed-without-evidence': 'You confirmed this, but have not given your evidence',
  }[state]

  return (
    <li className={`sop-claim sop-claim--${state}`}>
      <p className="sop-claim__kind">{claim.kindLabel}</p>
      <blockquote className="sop-claim__quote">{claim.quote}</blockquote>
      <p className="sop-claim__ask">{claim.ask}</p>
      <p className="sop-claim__state">{stateLabel}</p>

      {state !== 'removed' ? (
        <div className="sop-claim__actions">
          <label className="sop-claim__label" htmlFor={`evidence-${claim.key}`}>
            Your own evidence for this claim. Only what you can actually stand behind.
          </label>
          <textarea
            id={`evidence-${claim.key}`}
            className="sop-claim__evidence"
            rows={3}
            value={draftEvidence}
            onChange={(event) => setDraftEvidence(event.target.value)}
            placeholder="Where does this come from? A record, a result, an award, a document. Leave blank if you have not decided yet."
          />
          <div className="sop-claim__buttons">
            <button
              type="button"
              className="sop-btn"
              onClick={() => onSubstantiate(claim, 'confirmed', draftEvidence)}
            >
              Confirm with this evidence
            </button>
            <button
              type="button"
              className="sop-btn sop-btn--quiet"
              onClick={() => onSubstantiate(claim, 'removed', '')}
            >
              I will remove this claim from the draft
            </button>
          </div>
        </div>
      ) : (
          <div className="sop-claim__actions">
            <p className="sop-claim__note">
              Marked for removal. This does not edit your draft for you - the sentence is still
              in your text until you take it out.
            </p>
            <button
              type="button"
              className="sop-btn sop-btn--quiet"
              onClick={() => onSubstantiate(claim, 'confirmed', '')}
            >
              Put it back
            </button>
            <button
              type="button"
              className="sop-btn sop-btn--quiet"
              onClick={() => onClear(claim.key)}
            >
              Clear my answer to this claim
            </button>
          </div>
        )}
    </li>
  )
}

/* ── The page ──────────────────────────────────────────────────────── */

export default function SopBuilderPage() {
  const [draft, setDraft] = useState(() => readDraft())
  const [status, setStatus] = useState(null)
  const [activeSection, setActiveSection] = useState(SOP_SECTIONS[0].id)

  // The review is recomputed on every render rather than stored, so a finding can
  // never describe a draft the student is no longer looking at. It is also why
  // the review can be trusted to be current after any keystroke.
  const review = useMemo(() => reviewDraft(draft), [draft])

  /** Re-read from storage after every write, so rendered state is what persisted. */
  const refresh = useCallback(() => {
    setDraft(readDraft())
  }, [])

  useEffect(() => {
    document.title = 'Statement builder · ScholarZone'
    return () => {
      document.title = ''
    }
  }, [])

  function onContextChange(field, value) {
    const ok = writeContext({ [field]: value })
    setStatus(ok ? null : { tone: 'error', text: 'This browser would not store that change.' })
    refresh()
  }

  function onBackgroundChange(field, value) {
    const ok = writeBackground({ [field]: value })
    setStatus(ok ? null : { tone: 'error', text: 'This browser would not store that note.' })
    refresh()
  }

  function onSectionChange(sectionId, value) {
    const ok = writeSection(sectionId, value)
    setStatus(ok ? null : { tone: 'error', text: 'This browser would not store that text.' })
    refresh()
  }

  function onSubstantiate(claim, claimStatus, evidence) {
    const ok = writeSubstantiation(claim.key, claimStatus, evidence)
    setStatus(
      ok
        ? null
        : { tone: 'error', text: 'This browser would not store that answer.' },
    )
    refresh()
  }

  function onClearSubstantiation(claimKey) {
    const ok = clearSubstantiation(claimKey)
    setStatus(ok ? null : { tone: 'error', text: 'This browser would not store that change.' })
    refresh()
  }

  function onToggleApproval() {
    const next = draft.approval?.confirmed === true ? false : true
    const ok = writeApproval(next)
    setStatus(
      ok
        ? {
            tone: 'ok',
            text: next
              ? 'Recorded: you have reviewed this draft. This is your own statement, not an assessment of it.'
              : 'Approval cleared.',
          }
        : { tone: 'error', text: 'This browser would not store that.' },
    )
    refresh()
  }

  /** Trigger a download of generated text. */
  function onDownload(text, extension, label) {
    const blob = new Blob([text], { type: `text/plain;charset=utf-8` })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${exportFileName(draft)}.${extension}`
    document.body.appendChild(anchor)
    anchor.click()
    document.body.removeChild(anchor)
    // Revoked on the next tick, so the download the click started has begun -
    // the same pattern `PlanPage` uses.
    setTimeout(() => URL.revokeObjectURL(url), 0)
    setStatus({ tone: 'ok', text: `${label} exported. This is the only copy outside this browser.` })
  }

  async function onImportFile(event) {
    const file = event.target.files?.[0]
    if (!file) {
      return
    }
    try {
      const result = importDraft(JSON.parse(await file.text()))
      if (result.ok) {
        refresh()
        setStatus({ tone: 'ok', text: 'Draft restored from the file.' })
      } else {
        setStatus({ tone: 'error', text: result.reason })
      }
    } catch {
      // A file that is not JSON is the common case, and "could not be read" is
      // more useful than a parser message.
      setStatus({ tone: 'error', text: 'That file could not be read as JSON.' })
    } finally {
      event.target.value = ''
    }
  }

  function onEraseEverything() {
    const ok = eraseEverything()
    setStatus(
      ok
        ? { tone: 'ok', text: 'Erased from this browser. There is nothing on any server to erase.' }
        : { tone: 'error', text: 'This browser would not clear the workspace.' },
    )
    refresh()
    setActiveSection(SOP_SECTIONS[0].id)
  }

  const section = SOP_SECTIONS.find((entry) => entry.id === activeSection)
  const sectionText = draft.sections[section.id]?.text || ''
  const totalWords = review.summary.totalWords
  const wordLimit = normalizeWordLimit(draft.context.word_limit)
  const limitAuthoritative = wordLimitIsAuthoritative(draft)
  const approved = draft.approval?.confirmed === true

  return (
    <section className="sop-page">
      <header className="sop-page__heading">
        <div>
          <p className="sop-page__eyebrow">Statement builder</p>
          <h1>Build your statement of purpose</h1>
          <p>
            A guided workspace for writing your own statement, section by section. You write
            every word. ScholarZone checks what you wrote, tells you what it could not find,
            and asks you to stand behind the claims in it.
          </p>
        </div>
        <Link to="/plan" className="sop-page__sibling-link">
          Planning workspace &rarr;
        </Link>
      </header>

      <LocalStorageNotice />

      <StatusLine status={status} />

      {/* ── Step 1: what this statement is for ─────────────────────── */}
      <section className="sop-step" aria-labelledby="sop-context-heading">
        <StepHeader step={1} title="What this statement is for" />

        <p className="sop-step__lede">
          Everything you type here stays in this browser and is only used by the relevance
          check below. None of it is sent anywhere.
        </p>

        <div className="sop-field-grid">
          <label className="sop-field" htmlFor="sop-application-type">
            <span className="sop-field__label">Application type</span>
            <select
              id="sop-application-type"
              className="sop-input"
              value={draft.context.application_type}
              onChange={(event) => onContextChange('application_type', event.target.value)}
            >
              <option value="">Choose one</option>
              {APPLICATION_TYPES.map((type) => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
          </label>

          <label className="sop-field" htmlFor="sop-institution">
            <span className="sop-field__label">Institution</span>
            <input
              id="sop-institution"
              className="sop-input"
              type="text"
              value={draft.context.institution}
              onChange={(event) => onContextChange('institution', event.target.value)}
              placeholder="Where you are applying"
            />
          </label>

          <label className="sop-field" htmlFor="sop-programme">
            <span className="sop-field__label">Programme</span>
            <input
              id="sop-programme"
              className="sop-input"
              type="text"
              value={draft.context.programme}
              onChange={(event) => onContextChange('programme', event.target.value)}
              placeholder="MSc, PhD, fellowship, course title"
            />
          </label>

          <label className="sop-field" htmlFor="sop-scholarship-name">
            <span className="sop-field__label">Scholarship or award (optional)</span>
            <input
              id="sop-scholarship-name"
              className="sop-input"
              type="text"
              value={draft.context.scholarship_name}
              onChange={(event) => onContextChange('scholarship_name', event.target.value)}
            />
          </label>

          <label className="sop-field" htmlFor="sop-word-limit">
            <span className="sop-field__label">Word limit (optional)</span>
            <input
              id="sop-word-limit"
              className="sop-input"
              type="number"
              min="1"
              step="1"
              value={draft.context.word_limit === null ? '' : draft.context.word_limit}
              onChange={(event) => onContextChange('word_limit', normalizeWordLimit(event.target.value))}
            />
          </label>

          <label className="sop-field sop-field--wide" htmlFor="sop-word-limit-source">
            <span className="sop-field__label">Where the limit comes from</span>
            <input
              id="sop-word-limit-source"
              className="sop-input"
              type="text"
              value={draft.context.word_limit_source}
              onChange={(event) => onContextChange('word_limit_source', event.target.value)}
              placeholder="e.g. the provider's guidelines page, dated, or the application form itself"
            />
          </label>
        </div>

        {wordLimit !== null ? (
          limitAuthoritative ? (
            <p className="sop-note">
              Your limit of {wordLimit} is recorded with a source, so ScholarZone will tell you
              where your draft stands against it. The source is the authority, not this page -
              your draft is {totalWords} {totalWords === 1 ? 'word' : 'words'} right now.
            </p>
          ) : (
            <p className="sop-note sop-note--warning">
              A limit of {wordLimit} is recorded but no source is, so ScholarZone treats it as a
              note to yourself rather than an official constraint and will not tell you that you
              are over it. Add a source if you have one.
            </p>
          )
        ) : null}

        <label className="sop-field sop-field--wide" htmlFor="sop-official-prompt">
          <span className="sop-field__label">
            The prompt the provider gave you (optional, paste it yourself)
          </span>
          <textarea
            id="sop-official-prompt"
            className="sop-input sop-input--area"
            rows={5}
            value={draft.context.official_prompt}
            onChange={(event) => onContextChange('official_prompt', event.target.value)}
            placeholder="Paste the question or prompt the application asked you to answer."
          />
        </label>

        <p className="sop-note">
          This is your own paste, and it is labelled as yours: ScholarZone did not write it, has
          not checked it against the provider, and will not treat it as an official document.
          The guidance in the writing school below is general writing guidance, not the
          provider&rsquo;s prompt - when the two differ, the provider wins.
        </p>
      </section>

      {/* ── Step 2: your background ───────────────────────────────── */}
      <section className="sop-step" aria-labelledby="sop-background-heading">
        <StepHeader step={2} title="Your background" count="yours to write" />

        <p className="sop-step__lede">
          Notes to yourself, so the facts you want to draw on are in one place while you write.
          ScholarZone supplies none of this and suggests none of it: if it is not in your own
          words, it does not belong in your statement.
        </p>

        <div className="sop-field-grid">
          {BACKGROUND_FIELDS.map((field) => (
            <label className="sop-field sop-field--wide" key={field.id} htmlFor={`sop-bg-${field.id}`}>
              <span className="sop-field__label">{field.label}</span>
              <textarea
                id={`sop-bg-${field.id}`}
                className="sop-input sop-input--area"
                rows={3}
                value={draft.background[field.id]}
                onChange={(event) => onBackgroundChange(field.id, event.target.value)}
                placeholder={field.hint}
              />
            </label>
          ))}
        </div>
      </section>

      {/* ── Step 3: the writing school ────────────────────────────── */}
      <section className="sop-step" aria-labelledby="sop-school-heading">
        <StepHeader
          step={3}
          title="Write it, section by section"
          count={`${review.summary.sectionsStarted} of ${review.summary.sectionsTotal} started`}
        />

        <p className="sop-step__lede">
          Each section below explains what to write, why it matters, and how to improve it.
          The order is reading order. Write them in whatever order you can.
        </p>

        <div className="sop-school">
          <nav className="sop-school__nav" aria-label="Sections of your statement">
            <ol>
              {SOP_SECTIONS.map((entry) => {
                const words = countWords(draft.sections[entry.id]?.text || '')
                const isActive = entry.id === activeSection
                return (
                  <li key={entry.id}>
                    <button
                      type="button"
                      className={isActive ? 'sop-school__tab is-active' : 'sop-school__tab'}
                      aria-current={isActive ? 'true' : undefined}
                      onClick={() => setActiveSection(entry.id)}
                    >
                      <span className="sop-school__tab-title">{entry.title}</span>
                      <span className="sop-school__tab-count">
                        {words === 0 ? 'empty' : words}
                      </span>
                    </button>
                  </li>
                )
              })}
            </ol>
          </nav>

          <article className="sop-school__panel" aria-live="polite">
            <h3 className="sop-school__panel-title">{section.title}</h3>

            <div className="sop-guidance">
              <h4>What to write</h4>
              <p>{section.whatToWrite}</p>

              <h4>Why it matters</h4>
              <p>{section.whyItMatters}</p>

              <h4>How to improve it</h4>
              <ul>
                {section.howToImprove.map((tip) => (
                  <li key={tip}>{tip}</li>
                ))}
              </ul>

              <h4>Questions to answer before you write</h4>
              <ul>
                {section.prompts.map((prompt) => (
                  <li key={prompt}>{prompt}</li>
                ))}
              </ul>
            </div>

            <div className="sop-editor">
              <div className="sop-editor__head">
                <label className="sop-editor__label" htmlFor={`sop-text-${section.id}`}>
                  Your {section.title.toLowerCase()}
                </label>
                <WordCount words={countWords(sectionText)} />
              </div>
              <textarea
                id={`sop-text-${section.id}`}
                className="sop-input sop-input--area sop-input--draft"
                rows={16}
                value={sectionText}
                onChange={(event) => onSectionChange(section.id, event.target.value)}
                placeholder="Write here. Nothing is suggested for you and nothing is saved until you type."
              />
              <p className="sop-editor__hint">
                Saved as you type, in this browser. There is no undo beyond your own editing.
              </p>
            </div>
          </article>
        </div>
      </section>

      {/* ── Step 4: review ────────────────────────────────────────── */}
      <section className="sop-step" aria-labelledby="sop-review-heading">
        <StepHeader
          step={4}
          title="Review your draft"
          count={review.notStarted ? 'not started' : `${review.findings.length} checks flagged`}
        />

        <p className="sop-review__disclaimer">{REVIEW_DISCLAIMER}</p>

        <dl className="sop-review__summary">
          <div>
            <dt>Words</dt>
            <dd>{totalWords}</dd>
          </div>
          <div>
            <dt>Sections started</dt>
            <dd>{review.summary.sectionsStarted} of {review.summary.sectionsTotal}</dd>
          </div>
          <div>
            <dt>Checks flagged</dt>
            <dd>{review.findings.length}</dd>
          </div>
          <div>
            <dt>Claims needing your evidence</dt>
            <dd>{review.summary.claimsOutstanding}</dd>
          </div>
        </dl>

        {wordLimit !== null && limitAuthoritative ? (
          <p className="sop-note">
            Against your recorded limit of {wordLimit}: {totalWords} words
            {' '}
            {totalWords > wordLimit
              ? `— ${totalWords - wordLimit} over. Check the source before you cut.`
              : `— ${wordLimit - totalWords} to spare.`}
          </p>
        ) : null}

        {/*
          The not-started state. One sentence, no findings list, no severity
          markers: an empty draft is a draft nobody could object to yet, and the
          old behaviour reported it as seven separate problems. The section
          progress indicator is untouched by this branch - it is in Step 3 and
          in the "sections started" figure above, both of which already read
          correctly at zero.
        */}
        {review.notStarted ? (
          <div className="sop-not-started">
            <h3 className="sop-not-started__title">Your draft hasn&rsquo;t started yet</h3>
            <p className="sop-not-started__lede">
              Nothing has been written in any of the six sections, so there is no text for
              the checks to look at. Write a section in step 3 and this panel will fill in
              automatically — nothing is hidden while the draft is empty.
            </p>
            <p className="sop-not-started__hint">
              The checks below run on text you have actually written. They do not guess, fill
              in, or reword anything.
            </p>
          </div>
        ) : null}

        <h3 className="sop-review__dimensions-title">What the checks look at</h3>
        <ul className="sop-dimensions">
          {REVIEW_DIMENSIONS.map((dimension) => {
            const entries = review.byDimension[dimension.id]
            return (
              <li key={dimension.id} className="sop-dimension">
                <p className="sop-dimension__title">
                  {dimension.label}
                  <span className="sop-dimension__count">
                    {entries.length === 0 ? 'nothing flagged' : `${entries.length} flagged`}
                  </span>
                </p>
                <p className="sop-dimension__summary">{dimension.summary}</p>
              </li>
            )
          })}
        </ul>

        {/*
          Section completion, kept separate from the text-review findings. This
          is guidance about what is still to write, never a verdict on the
          writing, which is why it is its own list with its own renderer and no
          severity markers.
        */}
        {review.sectionGuidance.length > 0 ? (
          <>
            <h3 className="sop-review__dimensions-title">Sections still to write</h3>
            <ul className="sop-guidance-list">
              {review.sectionGuidance.map((guidance) => (
                <GuidanceRow guidance={guidance} key={guidance.id} />
              ))}
            </ul>
          </>
        ) : null}

        <h3 className="sop-review__dimensions-title">Findings</h3>
        {review.findings.length === 0 ? (
          <p className="sop-empty">
            {review.notStarted
              ? 'No text findings yet. These checks run over writing, and writing is what is missing rather than what is wrong.'
              : 'No findings. That is not a statement that the draft is good — it is a statement that these particular checks did not fire. Read it yourself.'}
          </p>
        ) : (
          <ul className="sop-findings">
            {review.findings.map((finding) => (
              <FindingRow finding={finding} key={finding.id} />
            ))}
          </ul>
        )}
      </section>

      {/* ── Step 5: substantiate your claims ──────────────────────── */}
      <section className="sop-step" aria-labelledby="sop-claims-heading">
        <StepHeader
          step={5}
          title="Stand behind your claims"
          count={`${review.summary.claimsOutstanding} of ${review.summary.claimsDetected} open`}
        />

        <p className="sop-step__lede">
          The checks above found statements that a reader would expect you to be able to
          evidence. For each one: confirm it with the evidence you actually have, or decide to
          take it out. Either is a complete answer, and ScholarZone will not write the answer
          for you — include only the claims you can substantiate, so that everything in the
          draft is something you can stand behind.
        </p>

        {review.claims.length === 0 ? (
          <p className="sop-empty">
            No claims were detected. If you have stated something measurable about yourself,
            check that you could evidence it anyway — this check is a fixed phrase list, not a
            reader.
          </p>
        ) : (
          <ul className="sop-claims">
            {review.claims.map((claim) => (
              <ClaimRow
                claim={claim}
                key={claim.key}
                record={draft.substantiation[claim.key]}
                onSubstantiate={onSubstantiate}
                onClear={onClearSubstantiation}
              />
            ))}
          </ul>
        )}
      </section>

      {/* ── Step 6: approve, export, manage ───────────────────────── */}
      <section className="sop-step" aria-labelledby="sop-finish-heading">
        <StepHeader step={6} title="Approve, export and manage" />

        <div className="sop-approve">
          <label className="sop-approve__label" htmlFor="sop-approval">
            <input
              id="sop-approval"
              type="checkbox"
              checked={approved}
              onChange={onToggleApproval}
            />
            <span>
              I have read this whole draft and the claims in it are mine. I understand that the
              checks above are a limited set of automated writing rules over my own words — not a
              human assessment, and not a prediction of any admission or award.
            </span>
          </label>
          {approved ? (
            <p className="sop-approve__stamp">
              Recorded as reviewed by you
              {draft.approval?.confirmed_at ? ` on ${draft.approval.confirmed_at.slice(0, 10)}` : ''}.
            </p>
          ) : null}
          {review.summary.claimsOutstanding > 0 ? (
            <p className="sop-approve__warning">
              {review.summary.claimsOutstanding} claim
              {review.summary.claimsOutstanding === 1 ? '' : 's'} above still need
              {review.summary.claimsOutstanding === 1 ? 's' : ''} your answer. You can approve
              anyway — it is your draft — but the export will say so.
            </p>
          ) : null}
        </div>

        <div className="sop-export">
          <h3 className="sop-export__title">Take a copy with you</h3>
          <p className="sop-export__lede">
            Everything here lives in this browser and nowhere else. Exporting is the only way
            to keep it. Both files state inside themselves that they are your own work and that
            nothing here predicts an outcome.
          </p>
          <div className="sop-export__buttons">
            <button type="button" className="sop-btn" onClick={() => onDownload(toMarkdown(draft), 'md', 'Markdown draft')}>
              Export as Markdown
            </button>
            <button type="button" className="sop-btn" onClick={() => onDownload(toPlainText(draft), 'txt', 'Plain-text draft')}>
              Export as plain text
            </button>
          </div>

          <label className="sop-manage__import" htmlFor="sop-import-file">
            <span>Restore a draft you exported earlier</span>
            <input id="sop-import-file" type="file" accept="application/json,.json" onChange={onImportFile} />
          </label>
          <p className="sop-note">
            Restoring replaces what is in this browser now, and only works on a file this feature
            exported. Keep the export until you have confirmed the import landed.
          </p>
          <pre className="sop-preview" aria-label="Preview of the plain-text export">
            {toPlainText(draft).slice(0, 600)}
            {toPlainText(draft).length > 600 ? '\n…' : ''}
          </pre>
        </div>

        <div className="sop-manage">
          <h3 className="sop-manage__title">Move it, or erase it</h3>
          <div className="sop-manage__row">
            <button
              type="button"
              className="sop-btn sop-btn--quiet"
              onClick={() => {
                const ok = writeApproval(false)
                setStatus(
                  ok
                    ? { tone: 'ok', text: 'Your review confirmation has been cleared.' }
                    : { tone: 'error', text: 'This browser would not store that change.' },
                )
                refresh()
              }}
            >
              Clear my review confirmation
            </button>
          </div>
          <p className="sop-note">
            A restored file replaces what is in this browser now. Keep the export until you have
            confirmed the import worked.
          </p>

          <h4 className="sop-manage__subtitle">Erase</h4>
          <p className="sop-note">
            Nothing here is on a server, so erasing here is the whole of it. This clears the
            sections, your background notes, your prompt, your word limit and your answers to
            the claim checks.
          </p>
          <div className="sop-manage__row">
            <button type="button" className="sop-btn sop-btn--quiet" onClick={() => {
              const ok = clearAllSections()
              setStatus(ok ? { tone: 'ok', text: 'All section text cleared. Your context and background are still here.' } : { tone: 'error', text: 'This browser would not clear the sections.' })
              refresh()
            }}>
              Clear all section text
            </button>
            <button type="button" className="sop-btn sop-btn--danger" onClick={onEraseEverything}>
              Erase everything from this browser
            </button>
          </div>
        </div>
      </section>

      <LocalStorageNotice compact />
    </section>
  )
}
