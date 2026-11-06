/**
 * AI Assistant Service
 *
 * Connects to the ScholarZone AI backend endpoint.
 * If no AI backend is configured, falls back to grounded retrieval from local data.
 *
 * Backend API contract (when AI is enabled):
 * POST /api/ai/assistant
 * Body: { question: string, context?: { scholarships?: number[], userProfile?: object } }
 * Response: { answer: string, sources: Array<{ type: 'scholarship'|'general', id: string|number, title: string }>, grounded: boolean }
 */

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
    return localStorage.getItem('sz-local-ai-enabled') === 'true'
  } catch {
    return false
  }
}

/**
 * Check if AI backend is available by calling a health endpoint.
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
 * Falls back to grounded retrieval if AI is not available.
 */
export async function askAIAssistant(request) {
  // If AI is not enabled, use grounded fallback
  if (!aiEnabled) {
    return groundedFallback(request.question);
  }

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout

    const response = await fetch(AI_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));

      if (response.status === 429) {
        throw { error: 'AI service quota exceeded. Please try again later.', code: 'QUOTA_EXCEEDED', retryable: true };
      }
      if (response.status === 503) {
        throw { error: 'AI service temporarily unavailable.', code: 'UNAVAILABLE', retryable: true };
      }
      if (response.status >= 500) {
        throw { error: 'AI service error. Please try again.', code: 'SERVER_ERROR', retryable: true };
      }

      throw { error: errorData.error || 'AI request failed.', code: 'SERVER_ERROR', retryable: false };
    }

    const data = await response.json();

    // Validate response structure
    if (!data.answer || !Array.isArray(data.sources)) {
      throw { error: 'Invalid AI response format.', code: 'SERVER_ERROR', retryable: false };
    }

    return {
      answer: data.answer,
      sources: data.sources,
      grounded: data.grounded ?? true,
      model: data.model,
      tokensUsed: data.tokens_used,
    };
  } catch (error) {
    // If it's our structured error, rethrow
    if (error && typeof error === 'object' && 'code' in error) {
      throw error;
    }

    // Network error or timeout
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw { error: 'AI request timed out. Please try again.', code: 'TIMEOUT', retryable: true };
    }

    // Network error - fall back to grounded
    console.warn('AI Assistant unavailable, falling back to grounded retrieval:', error);
    return groundedFallback(request.question);
  }
}

/**
 * Grounded fallback - uses local scholarship data to answer questions.
 * This is NOT AI - it's a deterministic retrieval and composition.
 */
async function groundedFallback(question) {
  // Import dynamically to avoid circular dependencies
  const { fetchScholarships } = await import('./scholarshipService');

  // Simple keyword extraction for scholarship search
  const keywords = extractKeywords(question);

  try {
    const directory = await fetchScholarships({
      search: keywords.join(' '),
      limit: 5,
    });

    const scholarships = directory.items || [];

    if (scholarships.length === 0) {
      return {
        answer: "I couldn't find specific scholarships matching your question in the ScholarZone catalogue. Try browsing the directory with broader filters, or ask about general application guidance.",
        sources: [],
        grounded: true,
      };
    }

    // Compose a grounded answer from scholarship data
    const answer = composeGroundedAnswer(question, scholarships);
    const sources = scholarships.map(s => ({
      type: 'scholarship',
      id: s.id,
      title: s.title,
      url: s.official_source_url || s.official_url,
    }));

    return {
      answer,
      sources,
      grounded: true,
    };
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