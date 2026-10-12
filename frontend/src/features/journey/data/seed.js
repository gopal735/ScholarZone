/**
 * Seed material for the Bangladesh Applicant Journey.
 *
 * Two categories, and the boundary between them is the point of the file:
 *
 * - **Generic templates.** Items that describe a category of work every
 *   applicant does, phrased so that they make no claim about any particular
 *   programme. Every one ships as `requirement: 'unconfirmed'` and
 *   `template: true`, so nothing here can be mistaken for a confirmed
 *   requirement, and none of it counts towards progress until the student
 *   confirms it.
 *
 * - **One explicitly marked sample entry.** Provided so the workspace is never
 *   a blank room, and flagged `sample: true` so no renderer can present it as an
 *   opportunity the student chose. It carries no deadline, no fee and no
 *   eligibility claim, because inventing any of those is exactly what this
 *   feature must not do.
 *
 * Nothing here seeds a score, a GPA, a cost, a rate or an eligibility decision.
 * Those are the student's to enter.
 */

export const GENERIC_DOCUMENT_TEMPLATE = Object.freeze([
  {
    title: 'Passport',
    requirement: 'mandatory',
    note: 'Check the expiry date against your intended travel window.',
  },
  {
    title: 'Academic transcripts and certificates',
    requirement: 'unconfirmed',
    note: '',
  },
  {
    title: 'Recommendation letters',
    requirement: 'unconfirmed',
    note: '',
  },
  {
    title: 'English-language test evidence',
    requirement: 'unconfirmed',
    note: '',
  },
  {
    title: 'Financial evidence',
    requirement: 'unconfirmed',
    note: '',
  },
  {
    title: 'Translation and attestation',
    requirement: 'unconfirmed',
    note: '',
  },
  {
    title: 'Personal statement or statement of purpose',
    requirement: 'unconfirmed',
    note: '',
  },
  {
    title: 'Curriculum vitae',
    requirement: 'unconfirmed',
    note: '',
  },
])

export const GENERIC_DEPARTURE_TEMPLATE = Object.freeze([
  { title: 'Read the offer conditions in full' },
  { title: 'Confirm what the funding actually covers' },
  { title: 'Follow any further instructions from the university' },
  { title: 'Begin visa preparation' },
  { title: 'Plan accommodation' },
  { title: 'Arrange travel' },
  { title: 'Keep a copy of every document you send' },
])

/**
 * A single sample shortlist entry, explicitly flagged.
 *
 * The trust status is `needs-review` on purpose: even the sample is not allowed
 * to look verified. There is no deadline, no source URL and no country, so
 * nothing about a real opportunity is implied.
 */
export const SAMPLE_SHORTLIST_ENTRY = Object.freeze({
  name: 'Example programme (sample)',
  country: '',
  degree: '',
  deadlineDate: '',
  deadlineNote: '',
  sourceUrl: '',
  notes: 'A placeholder so the workspace is not empty. Delete it once you add a real opportunity.',
  trust: 'needs-review',
  sample: true,
})

/**
 * The template rows a Document Studio starts with when the student asks for them.
 *
 * Copies, not references, so a student editing one cannot alter the template
 * another student receives.
 */
export function buildDocumentTemplateRows() {
  return GENERIC_DOCUMENT_TEMPLATE.map((row) => ({
    title: row.title,
    requirement: row.requirement,
    note: row.note,
    progress: 'not_started',
    expiryDate: '',
    sourceUrl: '',
    template: true,
  }))
}

export function buildDepartureTemplateRows() {
  return GENERIC_DEPARTURE_TEMPLATE.map((row) => ({
    title: row.title,
    progress: 'not_started',
    note: '',
    template: true,
  }))
}
