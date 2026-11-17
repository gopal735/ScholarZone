/**
 * AI Assistant Service
 *
 * Connects to the ScholarZone AI backend endpoint when configured.
 * Falls back to deterministic, grounded retrieval from the public catalogue
 * when no remote AI provider is available or when remote requests fail.
 *
 * Backend API contract (optional remote AI):
 * POST /api/ai/assistant
 * Body: { question: string, context?: object }
 * Response: { answer: string, sources: Array<{ type: string, id?: string|number, title: string, url?: string }>, grounded: boolean }
 */

import { fetchScholarships } from './scholarshipService';
import { fetchScholarshipsFromSnapshot } from './staticScholarshipService';
import { parseDate } from '../utils/lifecycle';

const AI_ENDPOINT = '/api/ai/assistant';

let aiEnabled = false;

export function setAIEnabled(enabled) {
  aiEnabled = enabled;
}

export function isAIEnabled() {
  return aiEnabled;
}

/**
 * Check if local AI (on-device) is enabled by user.
 */
export function isLocalAIEnabled() {
  try {
    return localStorage.getItem('sz-local-ai-enabled') === 'true';
  } catch {
    return false;
  }
}

/**
 * Check if AI backend is available by calling a health endpoint.
 * Any non-2xx response (including 503 "not configured") means unavailable.
 */
export async function checkAIAvailability() {
  try {
    const response = await fetch('/api/ai/health', { method: 'HEAD' });
    return response.ok;
  } catch {
    return false;
  }
}

/**
 * Send a question to the AI Assistant.
 * Falls back to grounded retrieval when remote AI is unavailable/fails.
 */
export async function askAIAssistant(request) {
  const question = typeof request?.question === 'string' ? request.question : '';

  if (!aiEnabled) {
    return groundedFallback(question);
  }

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);

    const response = await fetch(AI_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request || {}),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      // Fallback is reserved for explicitly transient/provider-unavailable
      // failures. A generic 500 (internal/database error) is surfaced as a
      // structured error so it is never misclassified as "AI unavailable".
      const transientProviderStatuses = new Set([429, 502, 503, 504]);
      if (transientProviderStatuses.has(response.status)) {
        return groundedFallback(question);
      }

      const errorData = await response.json().catch(() => ({}));
      throw {
        error: errorData?.error || errorData?.detail || 'AI request failed.',
        code: 'SERVER_ERROR',
        retryable: response.status >= 500,
        status: response.status,
      };
    }

    const data = await response.json().catch(() => null);

    if (!data || typeof data.answer !== 'string' || !Array.isArray(data.sources)) {
      return groundedFallback(question);
    }

    return {
      answer: data.answer,
      sources: data.sources,
      grounded: data.grounded ?? true,
      model: data.model,
      tokensUsed: data.tokens_used ?? data.tokensUsed,
    };
  } catch (error) {
    // AbortError (including timeouts) must reach grounded fallback before the
    // generic structured-error guard, because AbortError may carry a legacy
    // numeric `code` property that would otherwise be rethrown.
    if (error instanceof DOMException && error.name === 'AbortError') {
      return groundedFallback(question);
    }

    // Only rethrow genuine structured service errors with a string code.
    if (
      error &&
      typeof error === 'object' &&
      'code' in error &&
      typeof error.code === 'string'
    ) {
      throw error;
    }

    console.warn('AI Assistant unavailable, falling back to grounded retrieval:', error);
    return groundedFallback(question);
  }
}

function normalizeQuestion(question) {
  return typeof question === 'string' ? question.trim().toLowerCase() : '';
}

function parseDeadlineWindowDays(question) {
  const q = normalizeQuestion(question);
  if (!q) return null;

  const explicit = q.match(/\b(?:within|in|next|coming)\s+(\d+)\s+days?\b/);
  if (explicit) {
    const days = Number(explicit[1]);
    return Number.isFinite(days) && days > 0 ? days : null;
  }

  const reversed = q.match(/\b(\d+)\s+days?\b/);
  if (reversed && (q.includes('deadline') || q.includes('closing') || q.includes('due'))) {
    const days = Number(reversed[1]);
    return Number.isFinite(days) && days > 0 ? days : null;
  }

  if ((q.includes('next month') || q.includes('coming month')) && q.includes('deadline')) {
    return 30;
  }

  return null;
}

function isDeadlineWindowQuestion(question) {
  const q = normalizeQuestion(question);
  if (!q) return false;

  // Deadline intent must be explicit. A bare duration ("in the next 30 days")
  // is not enough, otherwise application/document/eligibility questions that
  // happen to mention a timeframe get misrouted to deadline retrieval.
  const hasDeadlineIntent =
    q.includes('deadline') ||
    q.includes('closing') ||
    q.includes('due') ||
    q.includes('expires') ||
    q.includes('expiry') ||
    q.includes('last date') ||
    q.includes('final date') ||
    q.includes('submission date') ||
    q.includes('apply by');

  if (!hasDeadlineIntent) return false;

  if (parseDeadlineWindowDays(q) != null) return true;

  return (
    q.includes('upcoming') ||
    q.includes('soon') ||
    q.includes('next') ||
    q.includes('within') ||
    q.includes('coming') ||
    q.includes('this month') ||
    q.includes('next month')
  );
}

function toUtcDateStart(date) {
  return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
}

function getDeadlineDateUtc(scholarship) {
  const parsed = parseDate(scholarship, 'deadline')?.date;
  if (!parsed) return null;
  return toUtcDateStart(parsed);
}

function getRawDeadlineDateUtc(scholarship) {
  const raw = scholarship?.deadline_date;
  if (!raw) return null;
  const parsed = new Date(`${raw}T00:00:00Z`);
  if (isNaN(parsed.getTime())) return null;
  return toUtcDateStart(parsed);
}

function formatDeadline(scholarship) {
  if (typeof scholarship?.deadline === 'string' && scholarship.deadline.trim()) return scholarship.deadline;
  const parsed = getDeadlineDateUtc(scholarship);
  if (!parsed) return 'Not specified';
  return parsed.toISOString().slice(0, 10);
}

function compareByDeadlineThenTitle(a, b) {
  const ad = getDeadlineDateUtc(a)?.getTime() ?? Number.POSITIVE_INFINITY;
  const bd = getDeadlineDateUtc(b)?.getTime() ?? Number.POSITIVE_INFINITY;
  if (ad !== bd) return ad - bd;
  return String(a?.title || '').localeCompare(String(b?.title || ''), undefined, { sensitivity: 'base' });
}

async function fetchDeadlineWindowScholarships(days, question = '') {
  const timeframeNumber = String(days);
  const constraintKeywords = extractKeywords(question || '').filter((word) => {
    const lower = String(word).toLowerCase();
    if (/^\d+$/.test(lower) && lower === timeframeNumber) return false;
    return ![
      'deadline', 'deadlines', 'closing', 'close', 'due', 'expires', 'expiry',
      'days', 'day', 'within', 'next', 'upcoming', 'soon', 'coming',
      'scholarship', 'scholarships', 'month', 'months', 'week', 'weeks',
    ].includes(lower);
  });
  const search = constraintKeywords.length > 0 ? constraintKeywords.join(' ') : undefined;

  const boundedDays = Math.min(Math.max(days, 1), 365);

  // Prefer API contract with deadline_within_days (works for live DB and for
  // static-first/snapshot-backed fetchScholarships implementations).
  try {
    const directory = await fetchScholarships({
      ...(search ? { search } : {}),
      deadline_within_days: boundedDays,
      sort: 'deadline-soon',
      page: 1,
      limit: 20,
    });
    const items = Array.isArray(directory?.items) ? directory.items : [];
    if (items.length > 0 || directory?.pagination) {
      return items.sort(compareByDeadlineThenTitle);
    }
  } catch {
    // fall through to deterministic snapshot scan
  }

  const snapshot = await fetchScholarshipsFromSnapshot({
    ...(search ? { search } : {}),
    deadline_within_days: boundedDays,
    page: 1,
    limit: 10000,
    sort: 'deadline-soon',
  });
  const allItems = Array.isArray(snapshot?.items) ? snapshot.items : [];
  const now = new Date();
  const todayUtc = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
  const cutoff = new Date(todayUtc);
  cutoff.setUTCDate(cutoff.getUTCDate() + boundedDays);

  return allItems
    .filter((s) => {
      const d = getRawDeadlineDateUtc(s);
      return d && d >= todayUtc && d <= cutoff;
    })
    .sort((a, b) => {
      const ad = getRawDeadlineDateUtc(a)?.getTime() ?? Number.POSITIVE_INFINITY;
      const bd = getRawDeadlineDateUtc(b)?.getTime() ?? Number.POSITIVE_INFINITY;
      if (ad !== bd) return ad - bd;
      return String(a?.title || '').localeCompare(String(b?.title || ''), undefined, { sensitivity: 'base' });
    });
}

/**
 * Grounded fallback - uses local scholarship data to answer questions.
 * This is NOT AI - it is deterministic retrieval and composition.
 */
async function groundedFallback(question) {
  const safeQuestion = typeof question === 'string' ? question : '';

  try {
    let scholarships = [];

    if (isDeadlineWindowQuestion(safeQuestion)) {
      const days = parseDeadlineWindowDays(safeQuestion) ?? 30;
      if (days > 365) {
        return {
          answer: 'Deadline windows above 365 days are not supported. Please use 365 days or fewer.',
          sources: [],
          grounded: true,
        };
      }
      scholarships = (await fetchDeadlineWindowScholarships(days, safeQuestion)).slice(0, 10);

      if (scholarships.length === 0) {
        return {
          answer: `No scholarships with known deadlines in the next ${days} days were found in the public ScholarZone catalogue. Deadlines can change; check official provider pages for the latest updates.`,
          sources: [],
          grounded: true,
        };
      }

      const lines = [
        `Scholarships with deadlines in the next ${days} days (grounded in ScholarZone catalogue records):`,
        '',
      ];
      scholarships.slice(0, 10).forEach((s, i) => {
        lines.push(`${i + 1}. **${s.title}** (${s.country || 'Country not listed'}) — ${formatDeadline(s)}`);
        if (s.funding) lines.push(`   Funding: ${s.funding}`);
        if (s.degree) lines.push(`   Degree: ${s.degree}`);
        if (s.official_source_url) lines.push(`   Official: ${s.official_source_url}`);
        lines.push('');
      });
      lines.push('This answer is deterministic and grounded in catalogue data. Verify details on the official provider website before applying.');

      return {
        answer: lines.join('\n'),
        sources: scholarships.map((s) => ({
          type: 'scholarship',
          id: s.id,
          title: s.title,
          url: s.official_source_url || s.official_url,
        })),
        grounded: true,
      };
    }

    const keywords = extractKeywords(safeQuestion);
    const directory = await fetchScholarships({
      search: keywords.join(' '),
      limit: 5,
    });
    scholarships = Array.isArray(directory?.items) ? directory.items : [];

    if (scholarships.length === 0) {
      return {
        answer: "I couldn't find specific scholarships matching your question in the ScholarZone catalogue. Try browsing the directory with broader filters, or ask about general application guidance.",
        sources: [],
        grounded: true,
      };
    }

    const answer = composeGroundedAnswer(safeQuestion, scholarships);
    const sources = scholarships.map((s) => ({
      type: 'scholarship',
      id: s.id,
      title: s.title,
      url: s.official_source_url || s.official_url,
    }));

    return { answer, sources, grounded: true };
  } catch {
    return {
      answer: "I'm unable to search the scholarship catalogue right now. You can browse the directory directly at /scholarships or try again later.",
      sources: [],
      grounded: true,
    };
  }
}

/**
 * Extract search keywords from a natural language question.
 */
function extractKeywords(question) {
  const stopWords = new Set([
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
    'by', 'from', 'about', 'into', 'through', 'during', 'before', 'after', 'above',
    'below', 'up', 'down', 'out', 'off', 'over', 'under', 'again', 'further', 'then',
    'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'each', 'few',
    'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own',
    'same', 'so', 'than', 'too', 'very', 'can', 'will', 'just', 'should', 'now',
    'what', 'which', 'who', 'whom', 'this', 'that', 'these', 'those', 'am', 'is',
    'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'having',
    'do', 'does', 'did', 'doing', 'i', 'me', 'my', 'myself', 'we', 'our', 'ours',
    'ourselves', 'you', 'your', 'yours', 'yourself', 'yourselves', 'he', 'him',
    'his', 'himself', 'she', 'her', 'hers', 'herself', 'it', 'its', 'itself',
    'they', 'them', 'their', 'theirs', 'themselves', 'my', 'your', 'his', 'her',
    'its', 'our', 'their', 'i', 'me', 'we', 'us', 'you', 'he', 'him', 'she', 'her',
    'it', 'they', 'them', 'what', 'which', 'who', 'whom', 'this', 'that', 'these',
    'those', 'am', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have',
    'has', 'had', 'having', 'do', 'does', 'did', 'doing', 'a', 'an', 'the', 'and',
    'but', 'if', 'or', 'because', 'as', 'until', 'while', 'of', 'at', 'by', 'for',
    'with', 'about', 'against', 'between', 'into', 'through', 'during', 'before',
    'after', 'above', 'below', 'to', 'from', 'up', 'down', 'in', 'out', 'on',
    'off', 'over', 'under', 'again', 'further', 'then', 'once', 'here', 'there',
    'when', 'where', 'why', 'how', 'all', 'any', 'both', 'each', 'few', 'more',
    'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same',
    'so', 'than', 'too', 'very', 's', 't', 'can', 'will', 'just', 'don', 'should',
    'now', "i'm", "you're", "he's", "she's", "it's", "we're", "they're",
    "i've", "you've", "we've", "they've", "i'd", "you'd", "he'd", "she'd",
    "we'd", "they'd", "i'll", "you'll", "he'll", "she'll", "we'll", "they'll",
    "isn't", "aren't", "wasn't", "weren't", "hasn't", "haven't", "hadn't",
    "doesn't", "don't", "didn't", "won't", "wouldn't", "shan't", "shouldn't",
    "can't", "cannot", "couldn't", "mustn't", "let's", "that's", "who's",
    "what's", "here's", "there's", "when's", "where's", "why's", "how's"
  ]);
  
  return question
    .toLowerCase()
    .replace(/[^\w\s]/g, ' ')
    .split(/\s+/)
    .filter(word => word.length > 2 && !stopWords.has(word))
    .slice(0, 10);
}

/**
 * Compose a grounded answer from scholarship records.
 */
function composeGroundedAnswer(question, scholarships) {
  const lowerQuestion = question.toLowerCase();
  
  // Check question type and compose appropriate answer
  if (lowerQuestion.includes('compare') || lowerQuestion.includes('difference') || lowerQuestion.includes('vs')) {
    return composeComparisonAnswer(scholarships);
  }
  
  if (lowerQuestion.includes('deadline') || lowerQuestion.includes('when') || lowerQuestion.includes('closing') || lowerQuestion.includes('open')) {
    return composeDeadlineAnswer(scholarships);
  }
  
  if (lowerQuestion.includes('eligib') || lowerQuestion.includes('qualify') || lowerQuestion.includes('require') || lowerQuestion.includes('gpa') || lowerQuestion.includes('ielts') || lowerQuestion.includes('score')) {
    return composeEligibilityAnswer(scholarships);
  }
  
  if (lowerQuestion.includes('apply') || lowerQuestion.includes('application') || lowerQuestion.includes('document') || lowerQuestion.includes('sop') || lowerQuestion.includes('statement') || lowerQuestion.includes('essay') || lowerQuestion.includes('reference') || lowerQuestion.includes('letter')) {
    return composeApplicationAnswer(scholarships);
  }
  
  if (lowerQuestion.includes('fund') || lowerQuestion.includes('money') || lowerQuestion.includes('stipend') || lowerQuestion.includes('tuition') || lowerQuestion.includes('cost') || lowerQuestion.includes('coverage') || lowerQuestion.includes('fully funded')) {
    return composeFundingAnswer(scholarships);
  }
  
  // General answer
  return composeGeneralAnswer(scholarships);
}

function composeGeneralAnswer(scholarships) {
  const top = scholarships.slice(0, 3);
  const lines = [
    `Based on the ScholarZone catalogue, here are relevant scholarships for your question:`,
    '',
  ];
  
  top.forEach((s, i) => {
    lines.push(`${i + 1}. **${s.title}** (${s.country}) — ${s.funding}`);
    if (s.degree) lines.push(`   Degree: ${s.degree}`);
    if (s.deadline) lines.push(`   Deadline: ${s.deadline}`);
    if (s.official_source_url) lines.push(`   Official: ${s.official_source_url}`);
    lines.push('');
  });
  
  lines.push('Answers are grounded in ScholarZone data. Always verify details on the official provider website.');
  return lines.join('\n');
}

function composeComparisonAnswer(scholarships) {
  const top = scholarships.slice(0, 4);
  const lines = ['Here is a comparison of the top matching scholarships:', ''];
  
  top.forEach((s, i) => {
    lines.push(`**${i + 1}. ${s.title}** (${s.country})`);
    lines.push(`   Funding: ${s.funding}`);
    if (s.coverage) lines.push(`   Coverage: ${Array.isArray(s.coverage) ? s.coverage.join('; ') : s.coverage}`);
    if (s.degree) lines.push(`   Degree: ${s.degree}`);
    if (s.deadline) lines.push(`   Deadline: ${s.deadline}`);
    lines.push('');
  });
  
  lines.push('Use the Compare page (/compare) for detailed side-by-side analysis.');
  return lines.join('\n');
}

function composeDeadlineAnswer(scholarships) {
  const lines = ['Application deadlines for matching scholarships:', ''];
  
  scholarships.slice(0, 5).forEach(s => {
    const deadline = s.deadline || s.deadline_display || 'Not specified';
    lines.push(`• **${s.title}** (${s.country}): ${deadline}`);
  });
  
  lines.push('');
  lines.push('Deadlines are subject to change. Always confirm on the official website before applying.');
  return lines.join('\n');
}

function composeEligibilityAnswer(scholarships) {
  const lines = ['Eligibility information from ScholarZone records:', ''];
  
  scholarships.slice(0, 3).forEach(s => {
    lines.push(`**${s.title}** (${s.country})`);
    if (s.eligibility && Array.isArray(s.eligibility)) {
      lines.push(`   Requirements: ${s.eligibility.slice(0, 3).join('; ')}`);
    } else if (s.eligibility_summary) {
      lines.push(`   Summary: ${s.eligibility_summary}`);
    }
    if (s.english_requirement) lines.push(`   English: ${s.english_requirement}`);
    lines.push('');
  });
  
  lines.push('Eligibility criteria vary by programme and track. Check the official page for complete requirements.');
  return lines.join('\n');
}

function composeApplicationAnswer(scholarships) {
  const lines = ['Application guidance based on ScholarZone records:', ''];
  
  scholarships.slice(0, 3).forEach(s => {
    lines.push(`**${s.title}** (${s.country})`);
    if (s.application_method && Array.isArray(s.application_method)) {
      lines.push(`   Method: ${s.application_method.join(', ')}`);
    }
    if (s.documents && Array.isArray(s.documents)) {
      lines.push(`   Documents: ${s.documents.slice(0, 5).join(', ')}`);
    }
    if (s.application_link) lines.push(`   Apply: ${s.application_link}`);
    lines.push('');
  });
  
  lines.push('For personalized document coaching, use the Grounded Mentor (/mentor) after signing in.');
  return lines.join('\n');
}

function composeFundingAnswer(scholarships) {
  const lines = ['Funding details from ScholarZone records:', ''];
  
  scholarships.slice(0, 4).forEach(s => {
    lines.push(`**${s.title}** (${s.country}) — ${s.funding}`);
    if (s.coverage) {
      const coverage = Array.isArray(s.coverage) ? s.coverage.join('; ') : s.coverage;
      lines.push(`   Coverage: ${coverage}`);
    }
    if (s.funding_amount && s.funding_currency) {
      lines.push(`   Amount: ${s.funding_amount.toLocaleString()} ${s.funding_currency}${s.funding_period ? ` / ${s.funding_period}` : ''}`);
    }
    if (s.tuition_coverage !== null && s.tuition_coverage !== undefined) {
      lines.push(`   Tuition: ${s.tuition_coverage ? 'Covered' : 'Not covered'}`);
    }
    if (s.living_cost_coverage !== null && s.living_cost_coverage !== undefined) {
      lines.push(`   Living costs: ${s.living_cost_coverage ? 'Covered' : 'Not covered'}`);
    }
    lines.push('');
  });
  
  lines.push('Funding details are from official sources. Always confirm exact amounts and conditions on the provider website.');
  return lines.join('\n');
}