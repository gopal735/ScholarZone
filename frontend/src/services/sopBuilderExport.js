/**
 * Draft export: plain text and Markdown.
 *
 * Two formats, because they answer two different questions. Markdown is for a
 * student who wants to paste the draft into a notes app, an editor or a document
 * they are working in. Plain text is for the case where a provider's portal or a
 * reviewer wants no formatting at all, and where markdown's `#` characters would
 * be noise.
 *
 * Both carry the same four declarations in the file itself. A file the student
 * keeps six months from now has to be able to tell them, unaided, what it is:
 *
 *   1. that it is their own work, held on their device;
 *   2. that a word limit is authoritative only if a source was recorded;
 *   3. which claims they marked as confirmed, and which are still outstanding;
 *   4. that nothing here predicts an admission, an award, or a committee's
 *      opinion - so the sentence cannot be separated from the draft later and
 *      read on its own.
 *
 * Neither exporter writes a markdown fence, a heading style, or a single word of
 * the student's draft. The words in the file are the student's and the
 * declarations' - there is no third author.
 */

import { SOP_SECTIONS } from './sopBuilderSections.js'
import {
  wordLimitIsAuthoritative,
  normalizeWordLimit,
  countWords,
  BACKGROUND_FIELDS,
} from './sopBuilderStorage.js'
import { reviewDraft } from './sopBuilderReview.js'

/**
 * Defensive shape for a draft that is not one.
 *
 * The store always produces a normalised draft, so this is belt and braces
 * rather than an expected input. It exists because an exporter that throws on a
 * malformed input turns "I pressed export" into a crash with no file, and a
 * student who has just lost a browser tab to a quota error is exactly the person
 * who cannot afford another surprise. Missing fields render as absent, never as
 * `undefined`, which is also what the empty-draft assertions check.
 */
function safeDraft(draft) {
  if (draft === null || typeof draft !== 'object') {
    return { context: {}, background: {}, sections: {}, substantiation: {}, approval: null }
  }
  return {
    context: (draft.context && typeof draft.context === 'object') ? draft.context : {},
    background: (draft.background && typeof draft.background === 'object') ? draft.background : {},
    sections: (draft.sections && typeof draft.sections === 'object') ? draft.sections : {},
    substantiation:
      (draft.substantiation && typeof draft.substantiation === 'object') ? draft.substantiation : {},
    approval: draft.approval && typeof draft.approval === 'object' ? draft.approval : null,
  }
}

/** Read a section's text from a draft whose shape is not guaranteed. */
function sectionText(sections, id) {
  const stored = sections[id]
  if (stored && typeof stored === 'object' && typeof stored.text === 'string') {
    return stored.text
  }
  return ''
}

/** Read a background field from a draft whose shape is not guaranteed. */
function backgroundValue(background, id) {
  return typeof background[id] === 'string' ? background[id] : ''
}

/** Read a substantiation record, or undefined. */
function substantiationRecord(substantiation, key) {
  const record = substantiation[key]
  return record && typeof record === 'object' ? record : undefined
}

/**
 * The declaration block both formats open with.
 *
 * Returned as an array of lines so each exporter can decide how to render a
 * heading. Kept in one function so the two formats cannot drift apart on what
 * they promise, which is the failure mode that matters: two exports that
 * disagree about whether something is local would make both untrustworthy.
 *
 * `limit` and `authoritative` are passed in rather than recomputed, because a
 * caller that has already normalised the draft would otherwise get a second,
 * subtly different answer.
 */
function declarations(draft, limit, authoritative) {
  const review = reviewDraft(draft)
  const lines = []

  lines.push(
    'This is your own draft, exported from ScholarZone on this device. ' +
      'ScholarZone did not generate, rewrite or approve it.',
  )

  if (limit !== null) {
    if (authoritative) {
      lines.push(
        `Word limit recorded as ${limit}, with the source you gave: ` +
          `${draft.context.word_limit_source}. Treat the source as the authority, not this file.`,
      )
    } else {
      lines.push(
        `A word limit of ${limit} is recorded but no source is, so this export does ` +
          'not treat it as an official limit. ScholarZone will not report you as over a ' +
          'limit it cannot attribute.',
      )
    }
  } else {
    lines.push('No word limit is recorded. A limit without a source is not treated as official.')
  }

  lines.push(
    `Review step: ${review.summary.claimsDetected} claim(s) detected, ` +
      `${review.summary.claimsOutstanding} still needing your evidence.`,
  )

  lines.push(
    'Nothing in this document predicts an admission, a scholarship award, or a ' +
      "selection committee's decision.",
  )

  return lines
}

/** A safe filename stem from the student's own context. */
function fileStem(draft) {
  const raw = [
    draft.context?.institution || '',
    draft.context?.programme || draft.context?.scholarship_name || '',
  ]
    .join(' ')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')

  const date = new Date().toISOString().slice(0, 10)
  return `sop-builder-${raw === '' ? 'draft' : raw.slice(0, 60)}-${date}`
}

/** The student's own context, as labelled lines. */
function contextLines(context) {
  const labels = {
    application_type: 'Application type',
    institution: 'Institution',
    programme: 'Programme',
    scholarship_name: 'Scholarship or award',
    word_limit: 'Word limit recorded',
    word_limit_source: 'Word limit source',
  }

  const lines = []
  for (const [key, label] of Object.entries(labels)) {
    const value = context[key]
    if (value === null || value === undefined || value === '') {
      continue
    }
    lines.push(`${label}: ${value}`)
  }

  const prompt = context.official_prompt
  if (typeof prompt === 'string' && prompt.trim() !== '') {
    lines.push('')
    lines.push(
      'The text below is a prompt you pasted yourself. ScholarZone did not ' +
        'write it, has not verified it against the provider, and treats it as your note.',
    )
    lines.push('')
    lines.push(prompt.trim())
  }

  return lines
}

/** The student's background, in field order. */
function backgroundLines(background) {
  const lines = []
  for (const field of BACKGROUND_FIELDS) {
    const value = backgroundValue(background, field.id)
    if (value.trim() === '') {
      continue
    }
    lines.push(field.label)
    lines.push(value.trim())
    lines.push('')
  }
  return lines
}

/** The claim ledger, showing what the student confirmed and what is open. */
function claimLines(draft) {
  const safe = safeDraft(draft)
  const review = reviewDraft(draft)
  if (review.claims.length === 0) {
    return []
  }

  const lines = ['Claims you were asked to substantiate:']
  for (const claim of review.claims) {
    const record = substantiationRecord(safe.substantiation, claim.key)
    if (!record) {
      lines.push(`- UNANSWERED — ${claim.kindLabel}: "${claim.quote}"`)
      continue
    }
    if (record.status === 'removed') {
      lines.push(`- REMOVED BY YOU — ${claim.kindLabel}: "${claim.quote}"`)
      continue
    }
    const evidence = typeof record.evidence === 'string' ? record.evidence.trim() : ''
    if (evidence === '') {
      lines.push(`- CONFIRMED WITHOUT EVIDENCE — ${claim.kindLabel}: "${claim.quote}"`)
    } else {
      lines.push(`- CONFIRMED BY YOU — ${claim.kindLabel}: "${claim.quote}"`)
      lines.push(`  Your evidence: ${evidence}`)
    }
  }
  lines.push('')

  if (review.claimsOutstanding.length > 0) {
    lines.push(
      `${review.claimsOutstanding.length} claim(s) above are still outstanding. ` +
        'Read them again before you rely on this draft.',
    )
    lines.push('')
  }

  return lines
}

/** Whether the student has themselves approved the draft. */
function approvalLines(approval) {
  if (approval && approval.confirmed === true) {
    const when = typeof approval.confirmed_at === 'string' ? approval.confirmed_at.slice(0, 10) : null
    return [`You confirmed you have reviewed this draft${when ? ` on ${when}` : ''}.`]
  }
  return ['You have not yet confirmed that you have reviewed this draft.']
}

/* ── Plain text ────────────────────────────────────────────────────── */

/**
 * The draft as plain text.
 *
 * No markdown syntax, no heading markers, no formatting a portal would show as
 * literals. The structure is carried by blank lines and capitalisation, which is
 * what a plain-text importer can preserve.
 */
export function toPlainText(input) {
  const draft = safeDraft(input)
  const context = draft.context
  const limit = normalizeWordLimit(context.word_limit)
  const authoritative = wordLimitIsAuthoritative(draft)

  const lines = ['SCHOLARZONE STATEMENT DRAFT', '']

  for (const declaration of declarations(draft, limit, authoritative)) {
    lines.push(declaration)
  }
  lines.push('')

  const contextSectionLines = contextLines(context)
  if (contextSectionLines.length > 0) {
    lines.push('WHAT THIS IS FOR', '')
    lines.push(...contextSectionLines, '')
  }

  const background = backgroundLines(draft.background)
  if (background.length > 0) {
    lines.push('YOUR BACKGROUND (your own words, kept for reference)', '')
    lines.push(...background)
  }

  lines.push('DRAFT', '')
  for (const section of SOP_SECTIONS) {
    const text = sectionText(draft.sections, section.id)
    lines.push(section.title.toUpperCase())
    lines.push(`${countWords(text)} words`)
    lines.push('')
    lines.push(text.trim() === '' ? '(nothing written yet)' : text.trim())
    lines.push('')
  }

  const claims = claimLines(draft)
  if (claims.length > 0) {
    lines.push('CLAIM LEDGER', '')
    lines.push(...claims)
  }

  lines.push('YOUR CONFIRMATION', '')
  lines.push(...approvalLines(draft.approval))

  return lines.join('\n')
}

/* ── Markdown ──────────────────────────────────────────────────────── */

/**
 * The draft as Markdown.
 *
 * `#` for the title, `##` for each section. Blockquotes carry the declarations
 * because they are metadata, not part of the student's statement, and a
 * blockquote is the conventional way to say so without removing the words.
 */
export function toMarkdown(input) {
  const draft = safeDraft(input)
  const context = draft.context
  const limit = normalizeWordLimit(context.word_limit)
  const authoritative = wordLimitIsAuthoritative(draft)

  const lines = ['# ScholarZone statement draft', '']

  // Each declaration becomes one quoted paragraph, so the blockquote is a
  // single quoted block rather than a list of separate ones.
  const quoted = declarations(draft, limit, authoritative).map((line) => `> ${line}`).join('\n>\n')
  lines.push(quoted, '')

  const contextSection = contextLines(context)
  if (contextSection.length > 0) {
    lines.push('## What this is for', '')
    for (const line of contextSection) {
      lines.push(line === '' ? '' : `- ${line}`)
    }
    lines.push('')
  }

  const background = backgroundLines(draft.background)
  if (background.length > 0) {
    lines.push('## Your background', '')
    lines.push('Your own words, kept for reference. ScholarZone supplied none of them.', '')
    for (const field of BACKGROUND_FIELDS) {
      const value = backgroundValue(draft.background, field.id)
      if (value.trim() === '') {
        continue
      }
      lines.push(`### ${field.label}`, '', value.trim(), '')
    }
  }

  lines.push('## Draft', '')
  for (const section of SOP_SECTIONS) {
    const text = sectionText(draft.sections, section.id)
    lines.push(`### ${section.title}`, '')
    lines.push(`*${countWords(text)} words*`, '')
    lines.push(text.trim() === '' ? '_(nothing written yet)_' : text.trim())
    lines.push('')
  }

  // The ledger is rendered as-is: its lines are already prefixed, and re-prefixing
  // them would corrupt the student's own evidence text.
  const claims = claimLines(draft)
  if (claims.length > 0) {
    lines.push('## Claim ledger', '')
    lines.push(...claims)
  }

  lines.push('## Your confirmation', '')
  lines.push(...approvalLines(draft.approval))

  return lines.join('\n')
}

/** The filename both exports suggest, so the two are recognisably a pair. */
export function exportFileName(draft) {
  return fileStem(draft)
}
