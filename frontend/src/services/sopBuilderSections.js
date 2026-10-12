/**
 * The section-by-section writing school.
 *
 * This is the *pedagogical* half of the SOP Builder. It is deliberately data, not
 * code, so the guidance a student reads can be reviewed on its own without
 * reading the review engine, and so a future change to a section's instructions
 * cannot accidentally change how a draft is checked.
 *
 * Three rules hold for every entry, and they are the reason this module exists as
 * data rather than as prose inline in a component:
 *
 *   1. The guidance never names a specific institution's prompt. It explains
 *      what a section of a statement is *for* and what a reader is looking for.
 *      Anything a student pastes from a provider is labelled as theirs and is
 *      treated as unverified by this module - see `SopBuilderPage`.
 *   2. Nothing here writes, rewrites, or completes a student's text. The builder
 *      asks questions and shows where a draft is thin. It does not author.
 *   3. No section claims that following the guidance improves a selection
 *      outcome. "How to improve it" means improve the writing, and the wording
 *      says so, because the reader of this file is the person who would have to
 *      defend that claim later.
 *
 * `minimumWords` is a floor for "this section has been started in earnest", not
 * a target. It is used by the review engine to distinguish an empty section from
 * a thin one, and it is never presented to a student as a quota to fill.
 */

/** The six sections a statement of purpose is read in, in reading order. */
export const SOP_SECTIONS = Object.freeze([
  {
    id: 'opening',
    order: 1,
    title: 'Opening and motivation',
    whatToWrite:
      'Open with the concrete thing that led you here: a question you could not let go of, a problem you saw up close, a course or a period of work that changed what you wanted to do. Then connect it to what you are applying to study, in one or two sentences.',
    whyItMatters:
      'The opening is the part a reader remembers and the part most drafts lose them in. A generic opening ("I have always been passionate about…") tells a reader nothing they could not have written themselves, so it does the work of a placeholder. A specific opening does two jobs at once: it shows you can identify what matters, and it gives the rest of the statement something to be measured against.',
    howToImprove: [
      'Cut the first sentence if it would work for any applicant at any university. If it survives the swap, it is not yet doing its job.',
      'Name the moment rather than the sentiment. "I rebuilt the sensor rig after the flood" is checkable; "I developed a strong interest in engineering" is not.',
      'Keep the opening to a single thread. A reader who is given three unrelated reasons in one paragraph will trust none of them.',
      'Do not promise what the rest of the statement will not deliver. If the opening raises a question, the body has to answer it.',
    ],
    prompts: [
      'What is the specific event, project or observation that made you decide to apply?',
      'What did you think before that, and what do you think now?',
      'Which one of your experiences makes the rest of this statement make sense?',
    ],
    minimumWords: 60,
  },
  {
    id: 'academic-preparation',
    order: 2,
    title: 'Academic preparation',
    whatToWrite:
      'The coursework, grades, methods and disciplinary grounding you actually have. Say what you studied, what you learned to do, and what you can now do without being taught it.',
    whyItMatters:
      'This is the section a selection committee uses to answer one question: are you ready for the work, or will the first semester be remedial? It is also the section where invented achievement is easiest to spot and most expensive, because a transcript will contradict it. Writing what you actually did, including what you were not good at yet, reads as confidence; inventing more reads as neither.',
    howToImprove: [
      'Attach evidence to each claim: a course, a grade, a project, a supervisor, a piece of kit you used. A claim with nothing behind it is an opinion about yourself.',
      'Describe capability, not sentiment. "Fitted a mixed-effects model to noisy count data" beats "I have strong analytical skills".',
      'Leave in the difficult parts honestly — a subject you had to work at, a method you got wrong the first time. A preparation story with no friction is not a preparation story.',
      'Do not list every course. Choose the ones that bear on what you are applying to do.',
    ],
    prompts: [
      'Which specific courses or training prepared you for this?',
      'What can you now do independently that you could not do when you started?',
      'Where were you weakest academically, and what did you do about it?',
    ],
    minimumWords: 80,
  },
  {
    id: 'projects',
    order: 3,
    title: 'Relevant projects and experience',
    whatToWrite:
      'The things you built, ran, tested, measured, organised or wrote. For each: what the problem was, what you personally did, what came out, and what you took from it.',
    whyItMatters:
      'This is the evidence section. Everything in the opening and the academic section is a claim about you; this is where a reader decides whether to believe any of it. It is also the section most vulnerable to the drafting temptation of inflating your own role, so the discipline here is to describe your own contribution precisely and let the size of the work carry the weight.',
    howToImprove: [
      'Use "we did X; I did Y" when it was a group project. Claiming a whole team’s role as your own is the most common credibility loss in this section.',
      'Give at least one result per project: a number, a finding, a decision that changed, an artefact that shipped. One is enough; zero makes the whole section read as intention rather than work.',
      'Order projects by relevance to what you are applying for, not by how impressive they sound.',
      'If a project failed, say what it taught you. A failed project described accurately is far stronger than a successful one described vaguely.',
    ],
    prompts: [
      'What did you personally build, run or write — not what the team did?',
      'What was the hardest technical or practical problem in it, and how did you approach it?',
      'What is one concrete outcome: a number, a finding, a decision, an artefact?',
    ],
    minimumWords: 120,
  },
  {
    id: 'why-programme',
    order: 4,
    title: 'Why this specific programme',
    whatToWrite:
      'What this programme offers that you do not already have: named groups, supervisors, courses, labs, methods, field sites, or a specific curriculum structure. Then say what you would bring to it.',
    whyItMatters:
      'This section is what separates a statement from a template. A reader is deciding whether you are applying to *this* programme or to forty of them, and the answer is visible in the level of specificity. It is also the section where a student is most tempted to write a paragraph that would fit any institution — because it is faster, and because it is true of all of them.',
    howToImprove: [
      'Name at least two specific things: a research group, a supervisor, a course, a method, a facility, a partnership. If you cannot, you have not finished your homework, and the reader will recognise that.',
      'Explain the connection, not just the list. Why does *this* group’s work need *your* particular background?',
      'Say what you bring, not only what you want. A programme admits people it wants, not only people who want it.',
      'Check the prompt you pasted against this section. If the provider asked a specific question and this section answers a different one, that is a problem with the draft, not the prompt.',
    ],
    prompts: [
      'Which two specific people, groups, courses or facilities here, and why those?',
      'What can you do that this programme does not already have?',
      'What will you do in your first year here that you could not do elsewhere?',
    ],
    minimumWords: 100,
  },
  {
    id: 'goals',
    order: 5,
    title: 'Future goals',
    whatToWrite:
      'What you want to be able to do afterwards, and how this programme is the step that gets you there. Be concrete about the direction and honest about the uncertainty.',
    whyItMatters:
      'A reader uses this section to decide whether the programme will actually be useful to you — whether completing it would change what you can do. A goal stated as a job title alone gives them nothing to assess; a goal stated as a capability or a problem you want to be able to work on gives them something. Overstated goals are as costly as vague ones, because they read as a plan you will abandon when it gets hard.',
    howToImprove: [
      'State the capability or the problem, then the role if you have one in mind. "I want to be able to evaluate X at scale" survives; "I want to be a data scientist" does not.',
      'Name the specific thing this programme gives you that the goal requires. That is the whole argument of this section.',
      'It is acceptable, and stronger, to say you are weighing two directions and what would settle it. Certainty you do not have is visible.',
      'Avoid goals that assume an outcome this selection cannot deliver. Nothing in your draft can guarantee a result.',
    ],
    prompts: [
      'What do you want to be able to do afterwards that you cannot do now?',
      'What is the one thing this programme must give you for that to be possible?',
      'What are you unsure about, and how would you resolve it here?',
    ],
    minimumWords: 70,
  },
  {
    id: 'conclusion',
    order: 6,
    title: 'Conclusion',
    whatToWrite:
      'One paragraph that closes the loop back to the opening, states plainly what you are asking for, and stops. It should add no new material.',
    whyItMatters:
      'The conclusion is where a reader decides what you are actually asking of them, and it is the section most often padded. A conclusion that summarises the whole statement line by line tells a reader you did not trust them to read it, and it spends the last words on repetition instead of on the ask.',
    howToImprove: [
      'Do not introduce a new example, a new achievement or a new ambition here. If it is new, it belongs in the body.',
      'Return to the opening on purpose. A reader who sees the same thread closed is far more likely to remember you.',
      'State what you are asking for in plain words: to be considered for a place on this programme.',
      'Cut it to one paragraph. If the conclusion is longer than the opening, it is a second body.',
    ],
    prompts: [
      'What is the single sentence you want the reader to carry away?',
      'How does this connect back to how you opened?',
      'What are you asking for, in one plain sentence?',
    ],
    minimumWords: 45,
  },
])

/** Sections in reading order, for anything that walks the whole statement. */
export const SOP_SECTION_IDS = Object.freeze(SOP_SECTIONS.map((section) => section.id))

/** The section record for one id, or null. */
export function getSection(id) {
  return SOP_SECTIONS.find((section) => section.id === id) || null
}

/** The section before and after one id, for the stepper's next/previous. */
export function siblingSections(id) {
  const index = SOP_SECTIONS.findIndex((section) => section.id === id)
  if (index === -1) {
    return { previous: null, next: null }
  }
  return {
    previous: index > 0 ? SOP_SECTIONS[index - 1].id : null,
    next: index < SOP_SECTIONS.length - 1 ? SOP_SECTIONS[index + 1].id : null,
  }
}

/**
 * The review dimensions, named in one place.
 *
 * These are the six the review engine checks and the six the review panel
 * reports. They are kept as data so the engine, the panel and the tests cannot
 * disagree about what "relevance" means, and so a new dimension has to be added
 * deliberately in all three.
 */
export const REVIEW_DIMENSIONS = Object.freeze([
  { id: 'structure', label: 'Structure', summary: 'Which sections have real text in them.' },
  { id: 'clarity', label: 'Clarity', summary: 'Sentences a reader has to work to get through.' },
  { id: 'specificity', label: 'Specificity', summary: 'Whether the writing names things.' },
  { id: 'relevance', label: 'Relevance', summary: 'Whether the draft answers what you applied to.' },
  { id: 'repetition', label: 'Repetition', summary: 'The same content written more than once.' },
  { id: 'unsupported-claims', label: 'Unsupported claims', summary: 'Statements you would need evidence for.' },
])

/**
 * What the review is and is not.
 *
 * Surfaced verbatim wherever a review is shown, because a student who cannot see
 * the limit of a check will read it as a judgement. This is the single most
 * important string in the feature.
 */
export const REVIEW_DISCLAIMER =
  'These are deterministic checks run over your own words. No language model ' +
  'generated, rewrote, scored or approved any part of your draft, and no check ' +
  'here predicts an admission, a scholarship award, or a selection committee’s ' +
  'opinion. A finding is a question to ask yourself, not a verdict.'

/**
 * The application types offered.
 *
 * A free list rather than a fixed one, because a student applying anywhere
 * ScholarZone does not list must still be able to use the builder. The common
 * values are there so the field needs no typing in the usual case.
 */
export const APPLICATION_TYPES = Object.freeze([
  'Scholarship',
  'PhD / doctoral',
  "Master's",
  "Bachelor's",
  'Postdoctoral fellowship',
  'Exchange / visiting',
  'Something else',
])
