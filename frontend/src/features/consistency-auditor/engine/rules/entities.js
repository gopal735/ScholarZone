/**
 * Rule group B — entity and wording differences.
 *
 * The comparison is deliberately conservative. Similarity alone never
 * proves two names are the same institution: "University of Dhaka" and
 * "University of Taiwan" share most of their characters and are not the
 * same university. So the rules only fire when normalised names match
 * exactly, or when they are near-identical AND their distinguishing
 * words (the parts that differ) are not in a small list of words that
 * actually identify an institution ("of", "the", "at", "university",
 * "college", "institute").
 *
 * Rules:
 *
 * NAME-01  Same entity, different formatting (Formatting or naming variation)
 *          Names that normalise to the same thing, or differ only by an
 *          abbreviation the README documents.
 * NAME-02  Same project, different title (Possible factual inconsistency)
 *          A project named in both documents whose titles differ by more
 *          than punctuation and abbreviation.
 * NAME-03  Comparable numbers differ (Possible factual inconsistency)
 *          The same labelled number (CGPA, publications, years of
 *          experience) stated with different values.
 * NAME-04  Numbers on different scales (Needs human review)
 *          Two CGPA/GPA values that may use different scales, so their
 *          difference may not be a conflict at all.
 */

import { normaliseEntityName, similarity } from '../normalize.js';
import { CATEGORIES, CONFIDENCE, makeFindingId } from '../findings.js';

/** Words that do not distinguish one institution from another. */
const STRUCTURAL_WORDS = new Set([
  'of', 'the', 'at', 'and', 'for', 'in', 'a', 'an', 'university', 'college',
  'institute', 'school', 'academy', 'faculty', 'department', 'dept', 'campus',
]);

/**
 * The similarity thresholds. Documented so a reader can argue with them:
 * at or above NEAR_IDENTICAL two names are offered as a formatting
 * variation; below it nothing is merged at all.
 */
export const SIMILARITY_THRESHOLDS = {
  /** Names at or above this are called the same entity for formatting checks. */
  exactOrNear: 0.94,
  /** Below this, no comparison is made. */
  floor: 0.72,
  /** At or above this a differing name is offered as a naming variation. */
  variation: 0.78,
};

/**
 * Do two names mean the same institution? Conservative by construction:
 * they must be at or above the threshold AND every word that differs must
 * be a word that does not identify the institution.
 *
 * @param {string} left
 * @param {string} right
 * @returns {boolean}
 */
export function namesAreEquivalent(left, right) {
  const a = normaliseEntityName(left);
  const b = normaliseEntityName(right);
  if (a === '' || b === '') return false;
  if (a === b) return true;
  const score = similarity(left, right);
  if (score < SIMILARITY_THRESHOLDS.exactOrNear) return false;
  const distinguishing = distinguishingWords(a, b);
  return distinguishing.every((word) => STRUCTURAL_WORDS.has(word));
}

/**
 * The words in either name that the other does not have.
 *
 * @param {string} a normalised already
 * @param {string} b normalised already
 * @returns {string[]}
 */
function distinguishingWords(a, b) {
  const left = a.split(' ').filter(Boolean);
  const right = new Set(b.split(' ').filter(Boolean));
  const differing = new Set();
  for (const word of left) if (!right.has(word)) differing.add(word);
  const leftSet = new Set(left);
  for (const word of right) if (!leftSet.has(word)) differing.add(word);
  return [...differing];
}

const UNIVERSITY_PATTERN = /\b((?:[A-Z][A-Za-z.'-]+\s+){0,4}(?:University|College|Institute|School|Academy)\b[^,.\n]{0,60})/g;
const PROJECT_PATTERN = /\b(?:project|thesis|capstone)\s*(?:titled|called|on|named)?\s*[:"']?\s*([A-Z0-9][^,.\n;]{3,80})/gi;

/**
 * @param {import('../validator.js').Document[]} documents
 * @returns {import('../findings.js').Finding[]}
 */
export function runEntityRules(documents) {
  const findings = [];

  const perDocument = documents.map((document) => ({
    document,
    universities: extract(document.text, UNIVERSITY_PATTERN),
    projects: extract(document.text, PROJECT_PATTERN),
  }));

  // NAME-01: the same institution named differently across documents.
  for (let i = 0; i < perDocument.length; i += 1) {
    for (let j = i + 1; j < perDocument.length; j += 1) {
      const left = perDocument[i];
      const right = perDocument[j];
      for (const a of left.universities) {
        for (const b of right.universities) {
          if (namesAreEquivalent(a.value.trim(), b.value.trim()) && a.value.trim() !== b.value.trim()) {
            findings.push({
              id: makeFindingId('NAME-01', [left.document.id, right.document.id, a.value.trim(), b.value.trim()]),
              ruleId: 'NAME-01',
              ruleName: 'Same institution, different formatting',
              category: CATEGORIES.variation,
              confidence: CONFIDENCE.weak,
              reason: 'These look like the same institution written differently. Pick whichever form the official transcript uses.',
              excerpts: [excerptOf(left.document, a), excerptOf(right.document, b)],
            });
          }
        }
      }
    }
  }

  // NAME-02: the same project with different titles across documents.
  for (let i = 0; i < perDocument.length; i += 1) {
    for (let j = i + 1; j < perDocument.length; j += 1) {
      const left = perDocument[i];
      const right = perDocument[j];
      for (const a of left.projects) {
        for (const b of right.projects) {
          const score = similarity(a.value.trim(), b.value.trim());
          if (a.value.trim() !== b.value.trim() && score >= SIMILARITY_THRESHOLDS.variation) {
            findings.push({
              id: makeFindingId('NAME-02', [left.document.id, right.document.id, a.value.trim(), b.value.trim()]),
              ruleId: 'NAME-02',
              ruleName: 'Same project, different title',
              category: CATEGORIES.inconsistency,
              confidence: score >= SIMILARITY_THRESHOLDS.exactOrNear ? CONFIDENCE.moderate : CONFIDENCE.weak,
              reason: 'These two lines look like the same project with different titles. Check they describe the same work, and which title is the official one.',
              excerpts: [excerptOf(left.document, a), excerptOf(right.document, b)],
            });
          }
        }
      }
    }
  }

  findings.push(...runNumberRules(documents));
  return findings;
}

/**
 * Labelled comparable numbers: "CGPA 3.42", "GPA: 3.4/4.0", "5 publications".
 */
const NUMBER_PATTERNS = [
  { label: 'CGPA', re: /\b(?:c\.?g\.?p\.?a\.?|grade point average)\D{0,12}(\d\.\d{1,3})/gi },
  { label: 'GPA', re: /\b(?:g\.?p\.?a\.?)\D{0,12}(\d\.\d{1,3})/gi },
  { label: 'publications', re: /\b(\d{1,3})\s+(?:publications|published papers|papers)/gi },
  { label: 'years of experience', re: /\b(\d{1,2})\s*(?:\+)?\s*years?\s+of\s+(?:experience|work experience|professional experience)/gi },
  { label: 'team size', re: /\bteam\s+of\s+(\d{1,3})\b/gi },
];

/**
 * Comparable facts, read from the RAW text (normalisation folds a decimal
 * point into nothing, so "3.5/4.0" would normalise to "3540" and the
 * scale comparison would be nonsense). Values are parsed as numbers here
 * and never re-formatted for display: the excerpt shows the original line.
 *
 * @param {import('../validator.js').Document} document
 */
function labelledNumbers(document) {
  const found = [];
  for (const { label, re } of NUMBER_PATTERNS) {
    re.lastIndex = 0;
    let match = re.exec(document.text);
    let guard = 0;
    while (match !== null && guard < 400) {
      guard += 1;
      const value = Number(match[1]);
      const scale = scaleAfter(document.text, match.index + match[0].length);
      found.push({
        label,
        value,
        scale,
        start: match.index,
        end: match.index + match[0].length,
        line: lineAt(document.text, match.index),
      });
      match = re.exec(document.text);
    }
  }
  return found;
}

/**
 * The scale a document states for a number: "3.61/4.00", "3.61 out of 4.00"
 * and "on a 4.0 scale" all count. Read from the RAW text because the
 * comparison normalisation removes the decimal point.
 *
 * @param {string} text
 * @param {number} offset
 * @returns {number|null}
 */
function scaleAfter(text, offset) {
  const window = text.slice(offset, offset + 24);
  const slash = /^\s*\/\s*(\d(?:\.\d)?)/.exec(window);
  if (slash) return Number(slash[1]);
  const words = /^\s*out\s+of\s+(\d(?:\.\d)?)/i.exec(window);
  if (words) return Number(words[1]);
  const scale = /\b(?:on\s+a\s+)?(\d(?:\.\d)?)\s*scale\b/i.exec(text.slice(offset - 24, offset + 24));
  return scale ? Number(scale[1]) : null;
}

/** The whole line around an offset, for a readable excerpt. */
function lineAt(text, offset) {
  const start = text.lastIndexOf('\n', offset - 1) + 1;
  const endIndex = text.indexOf('\n', offset);
  return text.slice(start, endIndex === -1 ? undefined : endIndex);
}

/**
 * NAME-03 and NAME-04. Same label, different values across documents.
 */
function runNumberRules(documents) {
  const findings = [];
  const perDocument = documents.map((document) => ({
    document,
    numbers: labelledNumbers(document),
  }));

  for (const label of new Set(perDocument.flatMap((entry) => entry.numbers.map((n) => n.label)))) {
    const labelled = perDocument
      .map((entry) => ({ document: entry.document, numbers: entry.numbers.filter((n) => n.label === label) }))
      .filter((entry) => entry.numbers.length > 0);

    for (let i = 0; i < labelled.length; i += 1) {
      for (let j = i + 1; j < labelled.length; j += 1) {
        const a = labelled[i].numbers[0];
        const b = labelled[j].numbers[0];
        if (a.value === b.value && (a.scale ?? b.scale) === (b.scale ?? a.scale)) continue;

        const isGpa = label === 'CGPA' || label === 'GPA';
        const scales = [a.scale, b.scale].filter((value) => value !== null && value !== undefined);

        if (isGpa && scales.length === 2 && new Set(scales).size > 1) {
          findings.push({
            id: makeFindingId('NAME-04', [labelled[i].document.id, labelled[j].document.id, label, a.value, b.value, scales.join('-')]),
            ruleId: 'NAME-04',
            ruleName: 'Same number, possibly different scales',
            category: CATEGORIES.humanReview,
            confidence: CONFIDENCE.weak,
            reason: 'These documents may use different scales (for example 4.0 and 5.0). The numbers may not conflict at all — check the scale each document states.',
            excerpts: [excerptOf(labelled[i].document, a), excerptOf(labelled[j].document, b)],
          });
          continue;
        }

        findings.push({
          id: makeFindingId('NAME-03', [labelled[i].document.id, labelled[j].document.id, label, String(a.value), String(b.value)]),
          ruleId: 'NAME-03',
          ruleName: 'Comparable numbers differ',
          category: isGpa ? CATEGORIES.humanReview : CATEGORIES.inconsistency,
          confidence: CONFIDENCE.moderate,
          reason: `Both documents state a ${label.toLowerCase()}, with different values. Confirm which is current.`,
          excerpts: [excerptOf(labelled[i].document, a), excerptOf(labelled[j].document, b)],
        });
      }
    }
  }
  return findings;
}

/** @param {import('../validator.js').Document} document @param {{start:number,end:number}} entry */
function excerptOf(document, entry) {
  return {
    documentId: document.id,
    documentLabel: document.label,
    start: entry.start,
    end: entry.end,
    text: entry.line,
  };
}

/**
 * @param {string} text
 * @param {RegExp} pattern
 */
function extract(text, pattern) {
  pattern.lastIndex = 0;
  const found = [];
  let match = pattern.exec(text);
  let guard = 0;
  while (match !== null && guard < 600) {
    guard += 1;
    found.push({ value: match[1].trim(), start: match.index, end: match.index + match[0].length, line: match[0].trim() });
    match = pattern.exec(text);
  }
  return found;
}
