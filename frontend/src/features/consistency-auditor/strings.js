/**
 * Every string the feature shows.
 *
 * The repo has no i18n system, so strings live in one module rather than
 * being scattered through components: when an i18n system is introduced,
 * this is the single file to move. New user-facing copy belongs here.
 *
 * The wording rules are part of the product contract, not style: no message
 * may call a document wrong, false, fraudulent or AI-written; no message may
 * claim a probability of anything.
 */

export const STRINGS = {
  pageTitle: 'Application consistency review',
  pageIntro:
    'Check your own documents for things that may conflict before you submit. This is a reading aid for your own text — it does not judge whether a statement is true, does not predict an admissions outcome, and does not write anything for you.',

  persistentNotice: 'Suggestions, not verdicts. These rules match text patterns; they cannot tell whether a statement is true.',

  inputs: {
    heading: 'Your documents',
    sop: {
      label: 'SOP / motivation letter',
      hint: 'Optional if you are only checking your CV.',
    },
    cv: {
      label: 'CV / resume text',
      hint: 'Paste the text of your CV or resume.',
    },
    answers: {
      label: 'Additional answers / academic history',
      hint: 'Application answers, academic history or anything else you want compared.',
    },
    charactersLabel: (used, limit) => `${used.toLocaleString()} / ${limit.toLocaleString()} characters`,
  },

  actions: {
    run: 'Run review',
    running: 'Reviewing…',
    rerun: 'Run a fresh review',
  },

  summary: {
    heading: 'What this review found',
    total: (count) => `${count} ${count === 1 ? 'item' : 'items'}`,
    byCategory: 'By category',
    empty: 'Nothing to review yet. Paste a document and run a review.',
  },

  notice: {
    cleaned: 'This device’s saved review data was cleared.',
    saved: 'Saving on this device is on. Your review decisions are stored in this browser only.',
    notSaved: 'Nothing is saved on this device. Review decisions last for this tab only.',
    stale: 'Documents changed — run a fresh review',
    dismiss: 'Item dismissed.',
    dismissUndone: 'Dismiss undone.',
    reviewed: 'Item marked as reviewed.',
  },

  findings: {
    heading: 'Items to look at',
    none: 'No possible inconsistencies detected by these rules — this does not guarantee your documents are consistent.',
    filterLabel: 'Filter by category',
    filterAll: 'All categories',
    sortNote: 'Grouped by category, then in the order each item appears.',
    review: 'Mark as reviewed',
    reviewed: 'Reviewed',
    dismiss: 'Dismiss',
    undo: 'Undo dismiss',
    dismissLabel: (id) => `Dismiss item ${id}`,
    why: 'Why this is shown',
    excerpts: 'What the documents say',
    question: 'Question to answer',
    support: 'Support found nearby',
    rule: 'Rule',
    confidence: 'Text comparison',
    dismissedHeading: 'Dismissed items',
    showDismissed: 'Show dismissed items',
    hideDismissed: 'Hide dismissed items',
    reviewedHeading: 'Reviewed items',
    categoryOf: {
      'Possible factual inconsistency': 'Possible factual inconsistency',
      'Formatting or naming variation': 'Formatting or naming variation',
      'Claim to substantiate': 'Claim to substantiate',
      'Needs human review': 'Needs human review',
    },
  },

  limits: {
    heading: 'How this works and its limits',
    body: [
      'These checks are written ahead of time and compare the words, dates and numbers in your documents. They do not understand meaning, do not read anything you have not pasted, and do not know the truth of any statement.',
      'A difference it flags is a prompt to check, not a finding against you. Many flagged items turn out to be a formatting difference or a fine explanation.',
      'It cannot verify anything against an official record, cannot tell whether a document was written with help, and cannot predict an admissions decision.',
      'Overlapping study and work is treated as something to confirm, never as a problem.',
    ],
    languageNote: 'Nothing here says a document is wrong or false. The strongest wording used is "may conflict", and only where the two texts state different facts.',
  },

  privacy: {
    heading: 'Your text stays on this device',
    beforeSave: [
      'By default your documents exist only in this browser tab’s memory and disappear when you leave.',
      'If you choose "Save on this device", your review decisions — which items you dismissed — are kept in this browser’s localStorage, under the keys sz.consistencyAuditor.v1.*. The documents themselves are never saved or sent anywhere.',
      'Anyone using this browser profile could read what is stored. Clear all data below removes only this feature’s keys.',
    ],
    saveOn: 'Save on this device',
    clear: 'Clear all data',
    clearConfirm: 'Removes this feature’s saved data from this device. Other ScholarZone data is not touched.',
  },

  states: {
    overLimit: 'This is more text than one review can check. Nothing was sent anywhere — the limit exists so the review stays fast.',
    empty: 'Nothing to check yet. Paste at least one document above.',
    engineError: 'The review could not run on this input. Your documents are untouched and nothing was sent anywhere.',
    loading: 'Working through your documents…',
  },
};

/** The category descriptions used in filters and summaries. */
export const CATEGORY_DESCRIPTIONS = {
  'Possible factual inconsistency': 'The documents state different facts about the same thing.',
  'Formatting or naming variation': 'The same thing written differently.',
  'Claim to substantiate': 'A broad claim a reader may want a specific example for.',
  'Needs human review': 'Something a person should look at, not a rule decision.',
};
