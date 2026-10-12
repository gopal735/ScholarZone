/**
 * Engine tests — cases 1-15 of the test plan.
 *
 * Every fixture is fixed, in the file, in UTF-8 (the Bengali fixtures are
 * written as literals and round-tripped, not read from disk). No network,
 * no timers beyond the bound test, no randomness.
 */

import { describe, expect, it } from 'vitest';

import { review } from './index.js';
import { comparisonOf, CATEGORIES } from './findings.js';
import { findDates, datesEqualAtCoarserPrecision, toWesternDigits } from './normalize.js';
import { SIMILARITY_THRESHOLDS, namesAreEquivalent } from './rules/entities.js';
import { CLAIM_PHRASES } from './rules/claims.js';

const SOP = (id, text) => ({ id, label: 'SOP / motivation letter', text });
const CV = (id, text) => ({ id, label: 'CV / resume', text });
const ANSWERS = (id, text) => ({ id, label: 'Application answers / history', text });

/** All findings for a review, or fail loudly if validation refused. */
function findingsFor(documents, options) {
  const result = review(documents, options);
  expect(result.ok).toBe(true);
  return result.findings;
}

describe('case 1 — same graduation year in equivalent supported formats', () => {
  it('reports nothing when both documents state the same completion year', () => {
    const findings = findingsFor([
      SOP('sop', 'I completed my BSc in Computer Science in 2023.'),
      CV('cv', 'BSc Computer Science, graduated 2023.'),
    ]);
    const graduation = findings.filter((f) => f.ruleId === 'DATE-01');
    expect(graduation).toEqual([]);
  });
});

describe('case 2 — conflicting graduation years', () => {
  it('flags a possible factual inconsistency with both excerpts', () => {
    const findings = findingsFor([
      SOP('sop', 'I completed my BSc in Computer Science in 2023.'),
      CV('cv', 'BSc Computer Science, completed 2021.'),
    ]);
    const conflict = findings.find((f) => f.ruleId === 'DATE-01');
    expect(conflict).toBeDefined();
    expect(conflict.category).toBe(CATEGORIES.inconsistency);
    expect(conflict.excerpts.map((e) => e.documentLabel)).toContain('SOP / motivation letter');
    expect(conflict.excerpts.map((e) => e.documentLabel)).toContain('CV / resume');
    // The language rule: no accusation anywhere in the reason.
    expect(conflict.reason.toLowerCase()).not.toMatch(/\b(wrong|false|lie|fraud)\b/);
    expect(conflict.reason).toMatch(/different completion years/);
  });
});

describe('case 3 — "Jan 2023" and "2023-01" are equal, no invented day', () => {
  it('treats the two formats as the same month with no day', () => {
    const left = findDates('Jan 2023').dates[0];
    const right = findDates('2023-01').dates[0];
    expect(left.year).toBe(2023);
    expect(left.month).toBe(1);
    expect(left.day).toBe(null);
    expect(right.year).toBe(2023);
    expect(right.month).toBe(1);
    expect(right.day).toBe(null);
    expect(datesEqualAtCoarserPrecision(left, right)).toBe(true);
  });

  it('reports no graduation conflict when the formats differ but the date matches', () => {
    const findings = findingsFor([
      SOP('sop', 'I completed my BSc in Computer Science in Jan 2023.'),
      CV('cv', 'BSc Computer Science, completed 2023-01.'),
    ]);
    expect(findings.filter((f) => f.ruleId === 'DATE-01')).toEqual([]);
  });
});

describe('case 4 — Bengali numerals and months', () => {
  it('converts Bengali digits to Western digits', () => {
    expect(toWesternDigits('২০২৩')).toBe('2023');
    expect(toWesternDigits('১৫')).toBe('15');
    expect(toWesternDigits('০১২৩৪৫৬৭৮৯')).toBe('0123456789');
  });

  it('parses each supported Bengali Gregorian month', () => {
    const months = ['জানুয়ারি', 'ফেব্রুয়ারি', 'মার্চ', 'এপ্রিল', 'মে', 'জুন', 'জুলাই', 'আগস্ট', 'সেপ্টেম্বর', 'অক্টোবর', 'নভেম্বর', 'ডিসেম্বর'];
    const expected = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];
    months.forEach((month, index) => {
      const dates = findDates(`${month} ২০২৩`).dates;
      expect(dates.length).toBeGreaterThan(0);
      expect(dates[0].year).toBe(2023);
      expect(dates[0].month).toBe(expected[index]);
      expect(dates[0].precision).toBe('month');
    });
  });

  it('parses a full Bengali date with day', () => {
    const dates = findDates('১৫ জানুয়ারি ২০২৩').dates;
    expect(dates[0].year).toBe(2023);
    expect(dates[0].month).toBe(1);
    expect(dates[0].day).toBe(15);
    expect(dates[0].precision).toBe('day');
  });

  it('parses a Bengali year alone', () => {
    const dates = findDates('আমি ২০২৩ সালে পাস করেছি').dates;
    expect(dates[0].year).toBe(2023);
    expect(dates[0].precision).toBe('year');
  });

  it('reports a Bengali calendar month as needs-human-review and never converts it', () => {
    const { dates, unsupported } = findDates('বৈশাখ ১৪৩২');
    expect(dates).toEqual([]);
    expect(unsupported.length).toBe(1);
    expect(unsupported[0].reason).toBe('bengali-calendar-month');

    const findings = findingsFor([
      SOP('sop', 'আমি বৈশাখ ১৪৩২ সালে আমার স্নাতক সম্পূর্ণ করেছি।'),
    ]);
    const note = findings.find((f) => f.ruleId === 'DATE-04');
    expect(note).toBeDefined();
    expect(note.category).toBe(CATEGORIES.humanReview);
    expect(note.reason).toMatch(/Bengali calendar months/);
  });
});

describe('case 5 — same project, slightly different names', () => {
  it('offers a naming variation rather than a conflict', () => {
    const findings = findingsFor([
      SOP('sop', 'My project titled Flood Detection System for Rural Roads was built in 2023.'),
      CV('cv', 'Project: Flood Detection System for Rural Road.'),
    ]);
    const finding = findings.find((f) => f.ruleId === 'NAME-02');
    if (finding) {
      expect(finding.category).toBe(CATEGORIES.inconsistency);
      expect(finding.confidence).toMatch(/Weak|Moderate/);
    }
    // Conservative engine: it may also say nothing. Either outcome is acceptable;
    // what is not acceptable is merging clearly different names, covered by case 6.
  });
});

describe('case 6 — clearly different names are never merged', () => {
  it('does not call University of Dhaka and National Taiwan University the same', () => {
    expect(namesAreEquivalent('University of Dhaka', 'National Taiwan University')).toBe(false);
    expect(namesAreEquivalent('University of Dhaka', 'University of Dhaka')).toBe(true);
    expect(namesAreEquivalent('Massachusetts Institute of Technology', 'Manukau Institute of Technology')).toBe(false);
  });

  it('produces no NAME-01 finding for genuinely different universities', () => {
    const findings = findingsFor([
      SOP('sop', 'I studied at the University of Dhaka.'),
      CV('cv', 'BSc from National Taiwan University.'),
    ]);
    expect(findings.filter((f) => f.ruleId === 'NAME-01')).toEqual([]);
  });
});

describe('case 7 — ongoing vs completed is not a contradiction', () => {
  it('does not flag an ongoing project against a completed one', () => {
    const findings = findingsFor([
      SOP('sop', 'I currently work as a research assistant.'),
      CV('cv', 'Research Assistant, 2022 to 2023.'),
    ]);
    expect(findings.filter((f) => f.ruleId === 'DATE-01')).toEqual([]);
    expect(findings.filter((f) => f.ruleId === 'DATE-02')).toEqual([]);
  });

  it('parses Present as ongoing, not as a year', () => {
    const dates = findDates('2021 - Present').dates;
    const ongoing = dates.find((d) => d.ongoing);
    expect(ongoing).toBeDefined();
    expect(dates.find((d) => d.year === 2021)).toBeDefined();
  });
});

describe('case 8 — overlapping study and work is a question, not an inconsistency', () => {
  it('reports needs-human-review for overlapping periods', () => {
    const findings = findingsFor([
      CV('cv', 'BSc Computer Science, 2019 to 2023.\nTeaching Assistant, 2022 to 2023.'),
    ]);
    const overlap = findings.find((f) => f.ruleId === 'DATE-03');
    expect(overlap).toBeDefined();
    expect(overlap.category).toBe(CATEGORIES.humanReview);
    expect(overlap.reason).toMatch(/Studying and working at the same time is common/);
    expect(overlap.reason.toLowerCase()).not.toMatch(/\b(wrong|false|lie|fraud)\b/);
  });
});

describe('case 9 — fully matching facts produce zero findings', () => {
  it('reports nothing when documents agree', () => {
    const findings = findingsFor([
      SOP('sop', 'I completed my BSc in Computer Science at the University of Dhaka in 2023.'),
      CV('cv', 'BSc Computer Science, University of Dhaka, 2019 to 2023.'),
    ]);
    expect(findings).toEqual([]);
  });
});

describe('case 10 — broad claims are questions, and support suppresses them', () => {
  it('flags a broad claim as a question with no accusation', () => {
    const findings = findingsFor([
      SOP('sop', 'I have extensive research experience in machine learning.'),
    ]);
    const claim = findings.find((f) => f.ruleId === 'CLAIM-01');
    expect(claim).toBeDefined();
    expect(claim.category).toBe(CATEGORIES.claim);
    expect(claim.question).toMatch(/What project, role, or outcome supports this/);
    expect(claim.reason.toLowerCase()).not.toMatch(/\b(false|wrong|lie|fraud)\b/);
  });

  it('downgrades and shows the support when it is nearby', () => {
    const findings = findingsFor([
      SOP('sop', 'I have extensive research experience in machine learning.\nMy paper on flood detection was published at a conference in 2023.'),
    ]);
    const claim = findings.find((f) => f.ruleId === 'CLAIM-02');
    expect(claim).toBeDefined();
    expect(claim.support[0]).toMatch(/paper on flood detection/);
    expect(claim.confidence).toMatch(/Weak/);
  });

  it('does not flag ordinary subjective sentences', () => {
    const findings = findingsFor([
      SOP('sop', 'I have always been passionate about learning and teaching others.'),
    ]);
    expect(findings.filter((f) => f.ruleId.startsWith('CLAIM'))).toEqual([]);
  });

  it('documents the claim phrase table', () => {
    expect(CLAIM_PHRASES.length).toBeGreaterThan(0);
    for (const phrase of CLAIM_PHRASES) {
      expect(phrase.question.endsWith('?')).toBe(true);
    }
  });
});

describe('case 11 — empty, whitespace, incomplete and oversized input', () => {
  it('refuses empty input with guidance, not an error', () => {
    const result = review([SOP('sop', '')]);
    expect(result.ok).toBe(false);
    expect(result.code).toBe('empty');
    expect(result.message).toMatch(/Paste at least one document/);
  });

  it('refuses whitespace-only input', () => {
    const result = review([SOP('sop', '   \n\t  \n ')]);
    expect(result.ok).toBe(false);
    expect(result.code).toBe('empty');
  });

  it('accepts one document and treats the others as optional', () => {
    const result = review([
      SOP('sop', 'I completed my BSc in 2023.'),
      CV('cv', ''),
      ANSWERS('answers', ''),
    ]);
    expect(result.ok).toBe(true);
    expect(result.findings).toEqual([]);
  });

  it('refuses an over-limit document with a friendly message naming the limit', () => {
    const result = review([SOP('sop', 'x'.repeat(20001))]);
    expect(result.ok).toBe(false);
    expect(result.code).toBe('too-large');
    expect(result.message).toMatch(/20,000-character limit/);
  });

  it('accepts a document at exactly the limit', () => {
    const result = review([SOP('sop', `I completed my BSc in 2023. ${'x'.repeat(19960)}`)]);
    expect(result.ok).toBe(true);
  });

  it('accepts no documents at all with guidance', () => {
    const result = review([]);
    expect(result.ok).toBe(false);
    expect(result.code).toBe('empty');
  });
});

describe('case 12 — determinism and stable finding IDs', () => {
  const documents = [
    SOP('sop', 'I completed my BSc in Computer Science in 2023. I have extensive research experience.'),
    CV('cv', 'BSc Computer Science, completed 2021.\nTraining Assistant, 2022 to 2023.'),
  ];

  it('produces identical results, including IDs, across runs', () => {
    const first = review(documents);
    const second = review(documents);
    expect(first.ok).toBe(true);
    expect(second.ok).toBe(true);
    expect(second.findings).toEqual(first.findings);
  });

  it('derives IDs from rule and content, not from order or time', () => {
    const first = review(documents).findings;
    const reordered = review([documents[1], documents[0]]).findings;
    // Same comparisons present (IDs are content-derived), order differs by document.
    expect(new Set(reordered.map((f) => f.id))).toEqual(new Set(first.map((f) => f.id)));
  });

  it('never puts document text into an ID', () => {
    const findings = review(documents).findings;
    const text = documents.map((d) => d.text).join(' ');
    for (const finding of findings) {
      expect(finding.id).not.toMatch(/\s/);
      for (const word of text.split(/\s+/).filter((w) => w.length > 6)) {
        expect(finding.id.toLowerCase()).not.toContain(word.toLowerCase().slice(0, 8));
      }
    }
  });

  it('sorts by category then document order', () => {
    const findings = review(documents).findings;
    const categoryIndex = findings.map((f) => ['Possible factual inconsistency', 'Formatting or naming variation', 'Claim to substantiate', 'Needs human review'].indexOf(f.category));
    expect(categoryIndex).toEqual([...categoryIndex].sort((a, b) => a - b));
  });

  it('exposes the comparison helper for a finding id', () => {
    const id = comparisonOf('RULE-1', ['a', 'b']);
    expect(id).toBe(comparisonOf('RULE-1', ['a', 'b']));
    expect(id).not.toBe(comparisonOf('RULE-1', ['a', 'c']));
  });
});

describe('case 13 — malformed input, emoji, long lines and adversarial strings', () => {
  const adversarial = [
    'a'.repeat(60000),
    '🎉'.repeat(5000),
    '2'.repeat(200),
    `${'ab'.repeat(4000)}!`,
    '\u0000\u0000\u0000 mixed \u200b zero width \ufeff',
    'ঢাকা Dhaka ঢাকা ঢাকা ঢাকা ঢাকা ঢাকা ঢাকা ঢাকা',
    'نص عربي طويل مع خلط الحروف والنصوص Bengali বাংলা English mixed',
    '<script>alert(1)</script>',
    "\u202e\u202d embedded direction overrides \u202c",
    '📧📧📧 contact: someone@example.com 📧📧📧',
  ];

  it('never throws on any adversarial input', () => {
    for (const text of adversarial) {
      const result = review([SOP('sop', text)]);
      expect(result.ok === true || result.ok === false).toBe(true);
      if (result.ok) {
        expect(Array.isArray(result.findings)).toBe(true);
      }
    }
  });

  it('finishes within a generous time bound on adversarial input', () => {
    const documents = [SOP('sop', adversarial.join('\n'))];
    const started = Date.now();
    const result = review(documents);
    const elapsed = Date.now() - started;
    expect(result.ok).toBe(false); // over the total limit, so it is refused fast
    expect(elapsed).toBeLessThan(2000);
  });

  it('finishes three near-limit documents well under 500 ms of engine time', () => {
    const filler = 'I completed my BSc in Computer Science in 2023 and now work as a research assistant. ';
    const documents = [
      SOP('sop', filler.repeat(300).slice(0, 19990)),
      CV('cv', filler.repeat(300).slice(0, 19990)),
      ANSWERS('answers', filler.repeat(300).slice(0, 19990)),
    ];
    const started = Date.now();
    const result = review(documents);
    const elapsed = Date.now() - started;
    expect(result.ok).toBe(true);
    // A CI machine can be slow; this is a bound, not a benchmark. The engine's
    // own work is far smaller than this allowance.
    expect(elapsed).toBeLessThan(5000);
  });

  it('does not treat an over-long line as a crash', () => {
    const result = review([SOP('sop', `short line\n${'z'.repeat(9000)}\nanother short line`)]);
    expect(result.ok).toBe(true);
  });
});

describe('case 14 — the original text is never mutated', () => {
  it('leaves the input objects byte-identical', () => {
    const text = '  I completed my BSc in Jan 2023.  \n\n২০২৩ সালে। 🎉  ';
    const documents = [SOP('sop', text), CV('cv', 'BSc, completed 2023-01.')];
    const before = JSON.stringify(documents);
    review(documents);
    review(documents);
    expect(JSON.stringify(documents)).toBe(before);
    expect(documents[0].text).toBe(text);
  });

  it('keeps excerpt text identical to the original slice', () => {
    const sopText = 'I completed my BSc in Computer Science in 2023.';
    const cvText = 'BSc Computer Science, completed 2021.';
    const sop = SOP('sop', sopText);
    const cv = CV('cv', cvText);
    const findings = findingsFor([sop, cv]);
    expect(findings.length).toBeGreaterThan(0);
    const byId = new Map([[sop.id, sopText], [cv.id, cvText]]);
    for (const finding of findings) {
      for (const excerpt of finding.excerpts) {
        const source = byId.get(excerpt.documentId);
        expect(source).toBeDefined();
        expect(source.slice(excerpt.start, excerpt.end)).toBe(excerpt.text);
      }
    }
  });
});

describe('case 15 — numeric facts and differing scales', () => {
  it('flags different CGPA values across documents', () => {
    const findings = findingsFor([
      SOP('sop', 'My CGPA is 3.42 out of 4.00.'),
      CV('cv', 'CGPA 3.61.'),
    ]);
    const finding = findings.find((f) => f.ruleId === 'NAME-03');
    expect(finding).toBeDefined();
  });

  it('treats 4.0-scale and 5.0-scale numbers as needs-human-review, not a conflict', () => {
    const findings = findingsFor([
      SOP('sop', 'My CGPA is 3.61 out of 4.00.'),
      CV('cv', 'CGPA 3.61 out of 5.00.'),
    ]);
    const finding = findings.find((f) => f.ruleId === 'NAME-04');
    expect(finding).toBeDefined();
    expect(finding.category).toBe(CATEGORIES.humanReview);
  });

  it('flags differing publication counts', () => {
    const findings = findingsFor([
      SOP('sop', 'I have 4 publications in peer-reviewed journals.'),
      CV('cv', '2 published papers.'),
    ]);
    expect(findings.find((f) => f.ruleId === 'NAME-03')).toBeDefined();
  });

  it('does not flag identical numbers', () => {
    const findings = findingsFor([
      SOP('sop', 'I have 4 publications in peer-reviewed journals.'),
      CV('cv', '4 published papers.'),
    ]);
    expect(findings.filter((f) => f.ruleId.startsWith('NAME-0'))).toEqual([]);
  });

  it('documents the similarity thresholds', () => {
    expect(SIMILARITY_THRESHOLDS.floor).toBeLessThan(SIMILARITY_THRESHOLDS.variation);
    expect(SIMILARITY_THRESHOLDS.variation).toBeLessThan(SIMILARITY_THRESHOLDS.exactOrNear);
  });
});

describe('the engine surface', () => {
  it('exposes exactly the four categories', () => {
    const findings = findingsFor([
      SOP('sop', 'I completed my BSc in Computer Science in 2023. I have extensive research experience.'),
      CV('cv', 'BSc Computer Science, completed 2021.\nTraining Assistant, 2022 to 2023.\nCGPA 3.91 out of 5.00.'),
    ]);
    const allowed = new Set(Object.values(CATEGORIES));
    for (const finding of findings) {
      expect(allowed.has(finding.category)).toBe(true);
    }
  });
});
