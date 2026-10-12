/**
 * The SOP Builder's review engine.
 *
 * **What this is.** A set of deterministic checks over the student's own text.
 * Every finding is produced by a named rule in this file: a sentence-length
 * threshold, a fixed phrase list, a repetition shingle, a token overlap. Given
 * the same draft, it always produces the same findings.
 *
 * **What this is not.** It is not a language model, and it must never be
 * described as one. The repository has no model SDK in `requirements.txt`, no
 * credential in the deployment, and two tests assert that no paid AI dependency
 * is present (`test_final_hardening.py::test_no_paid_dependency_was_added`,
 * `test_autonomous_maintenance.py::test_no_paid_dependency_was_introduced`).
 * There is an optional, disabled provider seam at
 * `backend/app/services/mentor/provider.py`, whose docstring records that
 * enabling it needs both a credential and an explicit maintainer decision. This
 * feature does not touch it.
 *
 * So the review panel says what it does: it runs checks. It does not generate,
 * rewrite, score, approve, or predict. Every string the UI shows about the
 * review comes from `REVIEW_DISCLAIMER` in `sopBuilderSections.js`.
 *
 * **Why determinism is a feature here, not a compromise.** A check the student
 * can read is a check the student can argue with. A number produced by a model
 * cannot be inspected, so the student can only either trust or distrust it - and
 * for a document that decides part of their future, distrust is the rational
 * default. Every finding below points at the sentence that triggered it and says
 * what the rule was, so a student can disagree with the rule and be right.
 *
 * The four rules the engine holds to, in the order they matter:
 *
 *   1. It never says a draft is good or bad. It says what it could not find.
 *   2. It never invents content, examples or claims, and never writes into the
 *      student's draft. It returns findings; it does not edit.
 *   3. Absence is reported as absence, never as failure. A section with no
 *      specific names in it gets "no specific names found", not "weak".
 *   4. Nothing here predicts an outcome, and the dimension names avoid words
 *      that would let a reader infer one.
 */

import {
  SOP_SECTIONS,
  SOP_SECTION_IDS,
  REVIEW_DIMENSIONS,
  getSection,
} from './sopBuilderSections.js'

/** Severity levels, in the order the panel sorts them. */
export const SEVERITY = Object.freeze({
  INFO: 'info',
  ATTENTION: 'attention',
  IMPORTANT: 'important',
})

const SEVERITY_ORDER = Object.freeze({ important: 0, attention: 1, info: 2 })

/**
 * Words a relevance or repetition check ignores.
 *
 * A relevance check that counted "the" and "and" would conclude that any two
 * English documents are about the same thing. This is a stopword list, not a
 * language model, and it is deliberately short: the failure mode of a long list
 * is dropping a word that carried the meaning.
 */
const STOPWORDS = new Set([
  'the', 'a', 'an', 'and', 'or', 'but', 'if', 'then', 'than', 'that', 'this',
  'these', 'those', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'am',
  'do', 'does', 'did', 'have', 'has', 'had', 'having', 'will', 'would', 'shall',
  'should', 'can', 'could', 'may', 'might', 'must', 'of', 'to', 'in', 'on',
  'at', 'by', 'for', 'with', 'from', 'as', 'into', 'about', 'between', 'through',
  'during', 'before', 'after', 'above', 'below', 'up', 'down', 'out', 'off',
  'over', 'under', 'again', 'further', 'once', 'here', 'there', 'when', 'where',
  'why', 'how', 'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other',
  'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'too', 'very',
  's', 't', 'just', 'also', 'i', 'me', 'my', 'mine', 'you', 'your', 'yours',
  'we', 'us', 'our', 'ours', 'they', 'them', 'their', 'theirs', 'it', 'its',
  'he', 'him', 'his', 'she', 'her', 'hers', 'who', 'whom', 'which', 'what',
  'while', 'because', 'until', 'per', 'via', 'etc',
])

/**
 * British and American spellings of the same concept.
 *
 * Only used by the repetition check, which normalises a word to a single form
 * before comparing it, so "organisation" and "organization" are not reported as
 * two repetitions of one idea. Dropping a letter rather than a vowel would
 * corrupt words, so pairs are listed.
 */
const SPELLING_VARIANTS = Object.freeze([
  ['organisation', 'organization'],
  ['programme', 'program'],
  ['analyse', 'analyze'],
  ['behaviour', 'behavior'],
  ['centre', 'center'],
  ['labour', 'labor'],
  ['favour', 'favor'],
  ['recognise', 'recognize'],
])

/* ── Sentence and word helpers ─────────────────────────────────────── */

/**
 * Split text into sentences.
 *
 * Splits on sentence-ending punctuation and on paragraph breaks, so a paragraph
 * of run-on text is still analysed per sentence. An abbreviation like "Dr."
 * produces a spurious break, which is a visible limitation of a deterministic
 * sentence length check rather than a reason to add a parser: it makes the check
 * conservative, not wrong about the section as a whole.
 */
export function splitSentences(text) {
  if (typeof text !== 'string' || text.trim() === '') {
    return []
  }
  return text
    .split(/\n+/)
    .flatMap((paragraph) => paragraph.split(/(?<=[.!?])\s+/))
    .map((sentence) => sentence.trim())
    .filter((sentence) => sentence !== '')
}

/** Words in a string, as an array. */
function wordsOf(text) {
  if (typeof text !== 'string') {
    return []
  }
  const trimmed = text.trim()
  return trimmed === '' ? [] : trimmed.split(/\s+/)
}

/** The count of words in a string. */
export function wordCount(text) {
  return wordsOf(text).length
}

/**
 * A word reduced to the form repetition and relevance compare.
 *
 * Lower-cased, stripped of surrounding punctuation, and mapped through the
 * spelling variants. A one-or-two character result is dropped, because it is
 * usually an initial or a fragment and it is not worth a repetition finding.
 */
function normalizeWord(word) {
  let base = String(word).toLowerCase().replace(/^[^a-z0-9]+|[^a-z0-9]+$/g, '')
  for (const [variant, canonical] of SPELLING_VARIANTS) {
    if (base === variant) {
      base = canonical
    }
  }
  return base.length >= 3 ? base : ''
}

/** Distinct content words in a string, excluding stopwords. */
export function contentWords(text) {
  const seen = new Set()
  for (const word of wordsOf(text)) {
    const normalized = normalizeWord(word)
    if (normalized !== '' && !STOPWORDS.has(normalized)) {
      seen.add(normalized)
    }
  }
  return seen
}

/**
 * A distinctive token from a name the student typed.
 *
 * An institution is "Massachusetts Institute of Technology", and "of" appearing
 * in a draft proves nothing. This keeps tokens a draft is unlikely to contain by
 * accident: words that are not stopwords and are at least four characters. When
 * nothing distinctive remains, it returns an empty set and the relevance check
 * declines to report rather than comparing on "of".
 */
export function distinctiveTokens(text) {
  const tokens = new Set()
  for (const word of wordsOf(text)) {
    const normalized = normalizeWord(word)
    if (normalized !== '' && !STOPWORDS.has(normalized) && normalized.length >= 4) {
      tokens.add(normalized)
    }
  }
  return tokens
}

/** A stable, comparable form of a sentence for repetition detection. */
function sentenceFingerprint(sentence) {
  return wordsOf(sentence).map(normalizeWord).filter(Boolean).join(' ')
}

/** A sliding window of n-word shingles over a string. */
function shingles(text, n) {
  const words = wordsOf(text).map(normalizeWord).filter(Boolean)
  const out = new Map()
  for (let index = 0; index + n <= words.length; index += 1) {
    const key = words.slice(index, index + n).join(' ')
    out.set(key, (out.get(key) || 0) + 1)
  }
  return out
}

/* ── The check vocabularies ─────────────────────────────────────────── */

/**
 * Filler a reader skims over.
 *
 * These are not errors and the finding says so. Each is a phrase that carries no
 * information the sentence would not have without it, and a draft made of them
 * reads as length rather than content. Kept as an explicit list so a student can
 * see exactly which phrases were flagged and decide whether they care.
 */
const FILLER_PHRASES = Object.freeze([
  'it is important to note that',
  'it should be noted that',
  'needless to say',
  'at the end of the day',
  'i would like to take this opportunity to',
  'first and foremost',
  'last but not least',
  'each and every',
  'in my personal opinion',
  'as a matter of fact',
  'for all intents and purposes',
  'the fact of the matter is',
])

/**
 * Phrases that could belong to any applicant.
 *
 * A draft that reads as though it was written for the application rather than by
 * the applicant usually does so in these exact five or six phrases. Flagging
 * them is the single most useful deterministic signal in the specificity check,
 * and it is deliberately a fixed list: an open-ended classifier here would be
 * guessing at meaning, which is what this feature does not do.
 */
const GENERIC_PHRASES = Object.freeze([
  'i am passionate about',
  'i have always been passionate',
  'i have always been interested in',
  'i have always wanted to',
  'ever since i was a child',
  'i am a hard worker',
  'hardworking and dedicated',
  'team player',
  'excellent communication skills',
  'fast learner',
  'detail oriented',
  'i strive for excellence',
  'this has always been my dream',
  'words cannot describe',
])

/**
 * Claim markers, grouped by what kind of claim they introduce.
 *
 * Each pattern is a claim the student would have to be able to evidence, and the
 * finding asks them to. The three groups are separated because they need
 * different kinds of evidence: a guarantee needs a source, a superlative needs a
 * comparison, an achievement needs a record.
 */
const CLAIM_PATTERNS = Object.freeze([
  {
    kind: 'guarantee',
    label: 'A promise of an outcome',
    ask: 'This states an outcome as certain. Remove it, or show the source that says so. Nothing in a statement of purpose can guarantee a result.',
    patterns: [
      'guaranteed', 'guarantee', 'guarantees', 'guaranteeing',
      'will definitely', 'will certainly', 'assured of', 'ensures that',
      'ensure that', 'no doubt that this', 'bound to be', 'sure to be',
    ],
  },
  {
    kind: 'superlative',
    label: 'A superlative claim',
    ask: 'This is a comparison against everything else. Name what it is being compared with and where that comparison comes from, or state it plainly instead.',
    patterns: [
      'world-class', 'world class', 'world leading', 'world-leading',
      'best in the world', 'the best', 'best university', 'top tier', 'top-tier',
      'revolutionary', 'unparalleled', 'unmatched', 'unrivalled', 'exceptional',
      'outstanding', 'outstandingly', 'groundbreaking', 'ground-breaking',
      'one of a kind', 'cutting-edge', 'cutting edge', 'state-of-the-art',
      'state of the art', 'highest quality', 'world-renowned', 'world renowned',
    ],
  },
  {
    kind: 'absolute',
    label: 'An absolute statement',
    ask: 'An absolute statement is only true if nothing is an exception. Check that you mean it, and soften it if you do not.',
    patterns: [
      'undoubtedly', 'without a doubt', 'there is no question', 'no one else',
      'nobody has', 'no one has', 'absolutely certain', 'perfectly suited',
    ],
  },
  {
    kind: 'numeric-achievement',
    label: 'A factual achievement claim',
    ask: 'This states a measurable fact about you. Confirm it against your own record, and include the evidence in your notes below.',
    patterns: [
      'ranked first', 'ranked 1st', 'ranked #1', 'ranked among', 'valedictorian',
      'first in my class', 'top 1%', 'top 5%', 'top 10%', 'first place',
      'first prize', 'gold medal', 'gold-medalist', 'national champion',
      'i published', 'i have published', 'my publication', 'my paper was',
      'accepted at', 'selected for', 'won the', 'awarded the', 'recipient of the',
      'held a patent', 'my patent', 'i invented', 'founded a',
      'full scholarship to', 'scored a perfect', 'perfect score', 'cummulative gpa of',
      'gpa of 4.0', 'graduated top', 'summa cum laude', 'magna cum laude',
    ],
  },
])

/* ── The individual checks ─────────────────────────────────────────── */

/**
 * Structure: which sections have real text.
 *
 * A missing section is reported as "important" because a statement with an
 * absent part is not finitely different from one with a thin part - the reader
 * notices the hole, and the student should too before they send it.
 */
/**
 * Structure: which sections have real text, as *section-completion guidance*.
 *
 * This is deliberately **not** a review finding, and that is the whole point of
 * the check. An empty section is not something a reader could object to in a
 * draft that does not exist yet, so reporting it as a finding made an untouched
 * draft look like a draft in trouble: seven alarming "no text yet" entries for
 * a document the student had not opened the editor for. The alarm was about the
 * *screen*, not about the *writing*.
 *
 * So section completion is its own channel, `sectionGuidance`, reported to the
 * UI as its own block. It carries one entry per section that is empty or thin,
 * with a calm instruction rather than a severity, and the not-yet-started state
 * is a single boolean (`notStarted`) the UI renders as one clear sentence.
 *
 * `findings` therefore holds only what a reader could actually object to in a
 * draft that exists: clarity, specificity, relevance and repetition. The
 * 'structure' dimension in `REVIEW_DIMENSIONS` maps onto `sectionGuidance`, so
 * the dimension tile still says what it looks at.
 *
 * The distinction the check preserves, and why it matters: an absent section is
 * reported as *absent*, never as *thin*. "Too short" is a judgement about
 * writing; "not written" is a statement of fact, and only the second is true of
 * an empty draft.
 *
 * @returns {{guidance: Array, totalWords: number, notStarted: boolean}}
 */
function checkStructure(draft) {
  const guidance = []
  let totalWords = 0

  for (const section of SOP_SECTIONS) {
    const text = draft.sections?.[section.id]?.text || ''
    const words = wordCount(text)
    totalWords += words

    if (words === 0) {
      guidance.push({
        id: `structure:${section.id}:empty`,
        dimension: 'structure',
        // No severity. A severity here is what made an empty draft read as a
        // failing one, and a section with nothing in it is not a defect.
        severity: null,
        sectionId: section.id,
        status: 'empty',
        words: 0,
        title: `${section.title}: nothing written yet`,
        detail:
          'Nothing has been written here. Start with whichever section you ' +
          'already know the most about - the order on the page is reading ' +
          'order, not a requirement to write in sequence.',
      })
      continue
    }

    if (words < section.minimumWords) {
      guidance.push({
        id: `structure:${section.id}:thin`,
        dimension: 'structure',
        severity: null,
        sectionId: section.id,
        status: 'thin',
        words,
        title: `${section.title}: ${words} words so far`,
        detail:
          `${section.minimumWords} words is roughly where a section of this ` +
          'kind begins to say something, but it is a floor rather than a ' +
          'target - a short section that is complete is better than a long ' +
          'one that is padded.',
      })
    }
  }

  return {
    guidance,
    totalWords,
    // One flag, not seven findings. The UI turns this into a single sentence.
    notStarted: totalWords === 0,
  }
}

/**
 * Clarity: sentences a reader has to work to get through.
 *
 * Threshold is 34 words, which is well above normal English sentence length and
 * roughly where a reader loses the subject. It is a heuristic about readers, not
 * a rule about grammar, and the finding names the sentence.
 */
const LONG_SENTENCE_WORDS = 34

function checkClarity(draft) {
  const findings = []

  for (const section of SOP_SECTIONS) {
    const text = draft.sections[section.id]?.text || ''
    if (text.trim() === '') {
      continue
    }

    for (const sentence of splitSentences(text)) {
      const count = wordCount(sentence)
      if (count >= LONG_SENTENCE_WORDS) {
        findings.push({
          id: `clarity:${section.id}:long:${sentenceFingerprint(sentence).slice(0, 60)}`,
          dimension: 'clarity',
          severity: SEVERITY.ATTENTION,
          sectionId: section.id,
          title: 'A sentence of ' + count + ' words',
          detail: `"${truncate(sentence, 220)}" — try splitting it at the point where the subject changes.`,
        })
      }
    }

    const lowered = ' ' + text.toLowerCase().replace(/\s+/g, ' ') + ' '
    const reported = new Set()
    for (const phrase of FILLER_PHRASES) {
      if (reported.has(phrase)) {
        continue
      }
      if (lowered.includes(phrase)) {
        reported.add(phrase)
        findings.push({
          id: `clarity:${section.id}:filler:${phrase.replace(/\s+/g, '-')}`,
          dimension: 'clarity',
          severity: SEVERITY.INFO,
          sectionId: section.id,
          title: `The phrase "${phrase}"`,
          detail:
            'Not an error. This phrase carries nothing the sentence would lose ' +
            'without it, and a draft made of them reads as length rather than ' +
            'content.',
        })
      }
    }
  }

  return findings
}

/**
 * Specificity: whether the writing names things.
 *
 * Two signals, deliberately simple. A section with no digits and no
 * non-sentence-initial capitalised word is a section that names nothing. And a
 * section made of the generic phrases is a section that names nothing about
 * *this* student. Both are reported as absences with the rule stated.
 */
function checkSpecificity(draft) {
  const findings = []

  for (const section of SOP_SECTIONS) {
    const text = draft.sections[section.id]?.text || ''
    if (text.trim() === '') {
      continue
    }

    const hasNumber = /\d/.test(text)
    if (!hasNumber) {
      findings.push({
        id: `specificity:${section.id}:no-number`,
        dimension: 'specificity',
        severity: SEVERITY.INFO,
        sectionId: section.id,
        title: 'No numbers in this section',
        detail:
          'A number is one of the cheapest ways to make a claim checkable - a ' +
          'sample size, a year, a grade, a duration, a ranking. Its absence is ' +
          'not a fault; it is worth asking whether one belongs here.',
      })
    }

    const hasProperNoun = /\b[A-Z][a-z]{2,}\b/.test(text.replace(/(^|[.!?]\s+)([a-z])/g, '$1$2'))
    if (!hasProperNoun) {
      findings.push({
        id: `specificity:${section.id}:no-proper-noun`,
        dimension: 'specificity',
        severity: SEVERITY.ATTENTION,
        sectionId: section.id,
        title: 'No named entities in this section',
        detail:
          'No capitalised names, places, institutions or methods appear here. ' +
          'A course, a supervisor, a city or a technique is usually what a ' +
          'reader is looking for.',
      })
    }

    const lowered = ' ' + text.toLowerCase().replace(/\s+/g, ' ') + ' '
    const reported = new Set()
    for (const phrase of GENERIC_PHRASES) {
      if (reported.has(phrase)) {
        continue
      }
      if (lowered.includes(phrase)) {
        reported.add(phrase)
        findings.push({
          id: `specificity:${section.id}:generic:${phrase.replace(/\s+/g, '-')}`,
          dimension: 'specificity',
          severity: SEVERITY.INFO,
          sectionId: section.id,
          title: `"${phrase}"`,
          detail:
            'This is a phrase any applicant could write. It is not wrong - it ' +
            'is unfalsifiable, so it cannot help you. What specifically makes ' +
            'it true for you?',
        })
      }
    }
  }

  return findings
}

/**
 * Relevance: whether the draft answers what you applied to.
 *
 * Checks the distinctive tokens of the institution and programme the student
 * typed against the whole draft. If the student typed a name and the name's
 * distinctive word never appears, that is worth one clear finding.
 *
 * It does **not** check the prompt the student pasted for semantic coverage,
 * because a token overlap with a prompt is not an answer to it. The prompt is
 * echoed back to the student as theirs to read, which is the honest mechanism.
 */
function checkRelevance(draft) {
  const findings = []
  const allText = SOP_SECTION_IDS
    .map((id) => draft.sections[id]?.text || '')
    .join('\n')
  const draftTokens = contentWords(allText)

  const targets = [
    { field: 'institution', label: 'institution', sectionId: 'why-programme' },
    { field: 'programme', label: 'programme', sectionId: 'why-programme' },
  ]

  for (const target of targets) {
    const value = draft.context[target.field]
    if (typeof value !== 'string' || value.trim() === '') {
      continue
    }
    const tokens = distinctiveTokens(value)
    if (tokens.size === 0) {
      // The student typed something too short to have a distinctive word. The
      // check declines rather than reporting a match it did not make.
      continue
    }
    const matched = [...tokens].filter((token) => draftTokens.has(token))
    if (matched.length === 0) {
      findings.push({
        id: `relevance:${target.field}:absent`,
        dimension: 'relevance',
        severity: SEVERITY.IMPORTANT,
        sectionId: target.sectionId,
        title: `Your ${target.label} is never named`,
        detail:
          `You wrote the ${target.label} as "${clamp(value, 80)}", and none of ` +
          'its distinctive words appear anywhere in your draft. A reader ' +
          'looking for this application will notice.',
      })
    }
  }

  return findings
}

/**
 * Repetition: the same content written more than once.
 *
 * Two rules. A sentence that appears more than once anywhere in the draft is
 * reported, because a repeated sentence is always a drafting accident. And a
 * seven-word shingle that crosses two different sections is reported, because
 * that is the shape of a paragraph pasted twice.
 */
const SHINGLE_WORDS = 7

function checkRepetition(draft) {
  const findings = []
  const occurrences = new Map()

  for (const section of SOP_SECTIONS) {
    const text = draft.sections[section.id]?.text || ''
    for (const sentence of splitSentences(text)) {
      const fingerprint = sentenceFingerprint(sentence)
      if (wordCount(sentence) < 6) {
        // A short sentence repeated is usually a rhetorical device, not an
        // accident, and flagging it would train a student to distrust the check.
        continue
      }
      const list = occurrences.get(fingerprint) || []
      list.push({ sectionId: section.id, sentence })
      occurrences.set(fingerprint, list)
    }
  }

  for (const [fingerprint, list] of occurrences) {
    if (list.length < 2 || fingerprint === '') {
      continue
    }
    const sectionIds = [...new Set(list.map((entry) => entry.sectionId))]
    findings.push({
      id: `repetition:sentence:${fingerprint.slice(0, 60)}`,
      dimension: 'repetition',
      severity: SEVERITY.ATTENTION,
      sectionId: list[0].sectionId,
      title: 'A sentence appears more than once',
      detail:
        `"${truncate(list[0].sentence, 220)}" appears in ` +
        `${sectionIds.map(labelOf).join(' and ')}. Repeated material is where a ` +
        'reader decides a draft is padded.',
    })
  }

  // Cross-section shingles.
  const owner = new Map()
  for (const section of SOP_SECTIONS) {
    const text = draft.sections[section.id]?.text || ''
    for (const shingle of shingles(text, SHINGLE_WORDS).keys()) {
      const list = owner.get(shingle) || []
      if (!list.includes(section.id)) {
        list.push(section.id)
      }
      owner.set(shingle, list)
    }
  }

  const reported = new Set()
  for (const [shingle, sectionIds] of owner) {
    if (sectionIds.length < 2) {
      continue
    }
    if (reported.has(shingle)) {
      continue
    }
    reported.add(shingle)
    findings.push({
      id: `repetition:shingle:${shingle.slice(0, 60)}`,
      dimension: 'repetition',
      severity: SEVERITY.ATTENTION,
      sectionId: sectionIds[0],
      title: 'The same wording spans two sections',
      detail:
        `The ${SHINGLE_WORDS}-word phrase "${shingle}" appears in ` +
        `${sectionIds.map(labelOf).join(' and ')}.`,
    })
  }

  return findings
}

/**
 * Unsupported claims: statements the student would need evidence for.
 *
 * This is the substantiation surface. Each match is returned as a *claim* rather
 * than as a finding, because the flow differs: a claim is not a defect, it is a
 * question the student answers. They can confirm it with their own evidence or
 * remove it, and either is a complete answer. Neither writes the claim for them.
 */
function detectClaims(draft) {
  const claims = []

  for (const section of SOP_SECTIONS) {
    const text = draft.sections[section.id]?.text || ''
    if (text.trim() === '') {
      continue
    }
    const lowered = text.toLowerCase()

    for (const group of CLAIM_PATTERNS) {
      const seen = new Set()
      for (const pattern of group.patterns) {
        if (seen.has(pattern)) {
          continue
        }
        seen.add(pattern)
        if (!lowered.includes(pattern)) {
          continue
        }
        // The matched phrase as it actually appears in the text, so the panel
        // can quote the student their own words rather than a lower-cased form.
        const index = lowered.indexOf(pattern)
        const quote = truncate(text.slice(index, index + pattern.length + 60), 180)
        claims.push({
          key: `${section.id}:${group.kind}:${pattern}`,
          sectionId: section.id,
          kind: group.kind,
          kindLabel: group.label,
          pattern,
          quote,
          ask: group.ask,
        })
      }
    }
  }

  return claims
}

/**
 * Claims that have not been answered yet.
 *
 * A claim resolved as "confirmed" with empty evidence is **still** outstanding:
 * the student has asserted the claim but has not said why it holds, and the
 * whole point of the step is to put the evidence somewhere before they rely on
 * it. Reported as `confirmed_without_evidence` so the panel can say exactly
 * which state it is in.
 */
export function claimsNeedingAttention(claims, substantiation) {
  return claims.filter((claim) => {
    const record = substantiation?.[claim.key]
    if (!record) {
      return true
    }
    if (record.status === 'removed') {
      return false
    }
    return typeof record.evidence !== 'string' || record.evidence.trim() === ''
  })
}

/* ── Composition ───────────────────────────────────────────────────── */

/** Truncate at a word boundary where possible. */
function truncate(text, limit) {
  const value = String(text || '').trim().replace(/\s+/g, ' ')
  if (value.length <= limit) {
    return value
  }
  const cut = value.slice(0, limit)
  const lastSpace = cut.lastIndexOf(' ')
  return `${(lastSpace > limit * 0.6 ? cut.slice(0, lastSpace) : cut).trimEnd()}…`
}

function clamp(text, limit) {
  const value = String(text || '').trim().replace(/\s+/g, ' ')
  return value.length <= limit ? value : `${value.slice(0, limit)}…`
}

function labelOf(sectionId) {
  const section = getSection(sectionId)
  return section ? section.title : sectionId
}

/**
 * Run every check over a draft.
 *
 * Pure: the same draft always produces the same result, and nothing here reads
 * storage, the clock or the network. The determinism is testable, and it is
 * tested - `sopBuilderReview.test.js` pins the exact finding counts for a fixed
 * draft, which is the only way to be sure a future edit to a phrase list does
 * not silently change the review a student sees.
 *
 * @param {object} draft a normalised draft from `sopBuilderStorage`
 * @returns {{notStarted: boolean, findings: Array, sectionGuidance: Array,
 *            claims: Array, claimsOutstanding: Array,
 *            byDimension: Object, summary: Object}}
 */
export function reviewDraft(draft) {
  const safe = draft || {}
  const sections = safe.sections || {}
  const substantiation = safe.substantiation || {}

  // Section completion is a separate channel, not a finding. See checkStructure
  // for why: seven "no text yet" findings turn an untouched draft into a draft
  // that looks broken.
  const structure = checkStructure({ ...safe, sections })

  const findings = [
    ...checkClarity({ ...safe, sections }),
    ...checkSpecificity({ ...safe, sections }),
    ...checkRelevance({ ...safe, sections }),
    ...checkRepetition({ ...safe, sections }),
  ].sort((first, second) => {
    const bySeverity = SEVERITY_ORDER[first.severity] - SEVERITY_ORDER[second.severity]
    if (bySeverity !== 0) {
      return bySeverity
    }
    return first.title.localeCompare(second.title)
  })

  const claims = detectClaims({ ...safe, sections })
  const claimsOutstanding = claimsNeedingAttention(claims, substantiation)

  const byDimension = {}
  for (const dimension of REVIEW_DIMENSIONS) {
    // 'structure' maps onto the guidance channel, so the dimension tile still
    // reports what it looks at without those entries entering the findings list.
    byDimension[dimension.id] = dimension.id === 'structure'
      ? structure.guidance
      : findings.filter((finding) => finding.dimension === dimension.id)
  }

  const totalWords = structure.totalWords

  return {
    notStarted: structure.notStarted,
    findings,
    sectionGuidance: structure.guidance,
    claims,
    claimsOutstanding,
    byDimension,
    summary: {
      totalWords,
      sectionsStarted: SOP_SECTIONS.filter(
        (section) => wordCount(sections[section.id]?.text || '') > 0,
      ).length,
      sectionsTotal: SOP_SECTIONS.length,
      sectionsRemaining: structure.guidance.filter((entry) => entry.status === 'empty').length,
      claimsDetected: claims.length,
      claimsOutstanding: claimsOutstanding.length,
      findingsImportant: findings.filter((finding) => finding.severity === SEVERITY.IMPORTANT).length,
    },
  }
}

/** The six dimensions, exported so the panel and the engine cannot drift. */
export { REVIEW_DIMENSIONS }
