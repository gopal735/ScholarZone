/**
 * Rule group C — claims to substantiate.
 *
 * These are questions, never verdicts. A phrase like "extensive research
 * experience" is flagged with the question "What project, role, or outcome
 * supports this?" — and if the documents already contain the support, the
 * finding is downgraded and the support is shown, or suppressed entirely
 * when the support is unambiguous.
 *
 * Rules:
 *
 * CLAIM-01 Broad claim without nearby support (Claim to substantiate)
 *          A broad claim phrase with no project, role or publication on
 *          the same line or the two lines around it.
 * CLAIM-02 Broad claim with support nearby (Claim to substantiate,
 *          downgraded) — the matched support is shown so the student can
 *          confirm it is the support they meant.
 * CLAIM-03 Superlative without a supporting number (Claim to substantiate)
 *          "numerous publications", "many awards" and similar phrases,
 *          offered as a question about the specific number.
 */

import { splitLines } from '../validator.js';
import { CATEGORIES, CONFIDENCE, makeFindingId } from '../findings.js';

/**
 * The phrase table. Each entry is a broad claim and the question to ask.
 * Deliberately short: a long table flags ordinary sentences, and false
 * positives are this feature's main cost. The tests pin the table.
 */
export const CLAIM_PHRASES = [
  {
    id: 'research',
    re: /\b(extensive|significant|substantial)\s+research\s+experience\b/i,
    question: 'What project, role, or outcome supports this research experience?',
  },
  {
    id: 'leadership',
    re: /\b(extensive|significant|substantial|strong)\s+leadership\s+experience\b/i,
    question: 'What role or team supports this leadership experience?',
  },
  {
    id: 'track-record',
    re: /\bproven\s+track\s+record\b/i,
    question: 'Which specific results make up this track record?',
  },
  {
    id: 'publications',
    re: /\b(numerous|several|multiple|many)\s+publications\b/i,
    question: 'How many, and which are the ones you want the reader to see?',
  },
  {
    id: 'led-projects',
    re: /\bled\s+(multiple|several|many|various)\s+(projects|teams)\b/i,
    question: 'Which projects, and what was your role in each?',
  },
  {
    id: 'awards',
    re: /\b(numerous|several|multiple|many)\s+(awards|honors|honours)\b/i,
    question: 'Which awards?',
  },
  {
    id: 'published-research',
    re: /\bpublished\s+(extensive|widely)\s+research\b/i,
    question: 'Which publications?',
  },
];

/** Words that, on the same line or nearby, count as support. */
const SUPPORT_WORDS = /\b(paper|publication|journal|conference|thesis|project|internship|assistant|researcher|scholarship|volunteer|founded|led|built|developed|designed|implemented|published|awarded|presented|worked|role|supervisor|lab|laboratory)\b/i;

/** A specific number near a claim also counts as support. */
const SUPPORT_NUMBER = /\b\d{1,4}\b/;

/** How many lines either side of a claim are searched for support. */
const SUPPORT_WINDOW = 2;

/**
 * @param {import('../validator.js').Document[]} documents
 * @returns {import('../findings.js').Finding[]}
 */
export function runClaimRules(documents) {
  const findings = [];
  for (const document of documents) {
    const lines = splitLines(document.text);
    let offset = 0;
    const lineOffsets = [];
    for (const line of lines) {
      lineOffsets.push(offset);
      offset += line.length + 1;
    }

    for (let index = 0; index < lines.length; index += 1) {
      const line = lines[index];
      if (line.length > 4000) continue;
      for (const phrase of CLAIM_PHRASES) {
        const match = phrase.re.exec(line);
        if (!match) continue;
        const support = findSupport(lines, index);
        const excerpt = {
          documentId: document.id,
          documentLabel: document.label,
          start: lineOffsets[index],
          end: lineOffsets[index] + line.length,
          text: line,
        };

        if (support) {
          findings.push({
            id: makeFindingId('CLAIM-02', [document.id, expressionOf(line), phrase.id, support.text.slice(0, 80)]),
            ruleId: 'CLAIM-02',
            ruleName: 'Broad claim with support nearby',
            category: CATEGORIES.claim,
            confidence: CONFIDENCE.weak,
            reason: 'This claim may already be supported by the line shown. Confirm the support says what you want it to.',
            question: phrase.question,
            support: [support.text],
            excerpts: [excerpt, {
              documentId: document.id,
              documentLabel: document.label,
              start: support.start,
              end: support.end,
              text: support.text,
            }],
          });
          continue;
        }

        findings.push({
          id: makeFindingId('CLAIM-01', [document.id, expressionOf(line), phrase.id]),
          ruleId: 'CLAIM-01',
          ruleName: 'Broad claim without nearby support',
          category: CATEGORIES.claim,
          confidence: CONFIDENCE.moderate,
          reason: 'This claim is broad. Adders often look for the specific project or number behind it.',
          question: phrase.question,
          excerpts: [excerpt],
        });
      }
    }
  }
  return findings;
}

/**
 * Look for support on the claim's line and its neighbours. The first hit
 * wins, so the finding is deterministic: the support shown does not depend
 * on the order in which the lines were read.
 *
 * @param {string[]} lines
 * @param {number} index the claim's line
 */
function findSupport(lines, index) {
  const from = Math.max(0, index - SUPPORT_WINDOW);
  const to = Math.min(lines.length - 1, index + SUPPORT_WINDOW);
  for (let i = from; i <= to; i += 1) {
    const line = lines[i];
    if (i === index && SUPPORT_WORDS.test(line)) {
      // A claim line that already names a role or project supports itself.
      return { text: line };
    }
    if (i !== index && (SUPPORT_WORDS.test(line) || SUPPORT_NUMBER.test(line))) {
      return { text: line };
    }
  }
  return null;
}

/**
 * A stable, text-free expression of which phrase in a line matched. The
 * full line is NOT used for the ID: a re-typed line with the same claim
 * should still be the same finding for an unchanged session, and the ID
 * must never carry text.
 *
 * @param {string} line
 */
function expressionOf(line) {
  for (const phrase of CLAIM_PHRASES) {
    if (phrase.re.test(line)) return phrase.id;
  }
  return 'unknown';
}
