/**
 * Route classification: DISCOVERY vs PRIVATE_MENTOR
 * This is a deterministic classifier, not a model.
 */

const DISCOVERY_PHRASES = [
  'find scholarship',
  'find scholarships',
  'search scholarship',
  'search scholarships',
  'browse scholarship',
  'browse scholarships',
  'show scholarship',
  'show scholarships',
  'which scholarships',
  'which scholarship',
  'list scholarship',
  'list scholarships',
  'phd scholarships',
  'phd scholarship',
  'doctoral scholarships',
  'doctoral scholarship',
  'doctorate scholarships',
  'master scholarships',
  'master scholarship',
  'masters scholarships',
  'masters scholarship',
  'bachelor scholarships',
  'bachelor scholarship',
  'undergraduate scholarships',
  'undergraduate scholarship',
  'fully funded',
  'with stipend',
  'stipend in',
  'scholarships in',
  'scholarships for',
  'scholarships with',
  'scholarship in',
  'scholarship for',
  'scholarship with',
  'opportunities in',
  'opportunities for',
  'opportunities with',
  'funding in',
  'grants in',
  'grants for',
  'deadlines in',
  'upcoming scholarship',
  'upcoming scholarships',
  'find opportunities',
  'search opportunities',
  'browse opportunities',
  'scholarships europe',
  'scholarships germany',
  'scholarships uk',
  'scholarships usa',
  'scholarships canada',
  'scholarships australia',
  'scholarships japan',
  'scholarships korea',
  'scholarships china',
  'scholarships india',
  'scholarships italy',
  'scholarships france',
  'scholarships spain',
  'scholarships netherlands',
  'scholarships sweden',
  'scholarships norway',
  'scholarships finland',
  'scholarships denmark',
  'scholarships switzerland',
  'scholarships austria',
  'scholarships belgium',
  'scholarships portugal',
  'scholarships poland',
  'scholarships czech',
  'scholarships hungary',
  'scholarships greece',
  'scholarships turkey',
  'scholarships taiwan',
  'scholarships singapore',
  'scholarships new zealand',
  'scholarships ireland',
];

const PRIVATE_MENTOR_PHRASES = [
  'am i eligible',
  'am i qualified',
  'do i qualify',
  'my eligibility',
  'my profile',
  'my application',
  'my progress',
  'my readiness',
  'my match',
  'my score',
  'my fit',
  'what should i do',
  'what do i do',
  'what should i work on',
  'what are my next steps',
  'my next step',
  'my next steps',
  'should i apply',
  'is this a good fit for me',
  'why is my',
  'improve my profile',
  'profile gaps',
  'strengthen my profile',
  'my scholarship',
  'my saved',
  'my shortlist',
  'compare my',
  'help me decide',
  'which should i',
  'what is missing',
  'what am i missing',
  'missing before',
  'what is blocking',
  'blocked',
  'application progress',
  'checklist',
  'remaining tasks',
  'how far through',
  'tasks left',
  'explain this scholarship',
  'tell me about this',
  'why is this',
  'good match for me',
  'is this worth',
  'why this scholarship',
];

// First-person eligibility patterns that indicate private mentor intent.
// These take precedence over discovery phrases.
const PRIVATE_ELIGIBILITY_PATTERNS = [
  /\bcan\s+i\s+apply\b/i,
  /\bam\s+i\s+eligible\b/i,
  /\bam\s+i\s+qualified\b/i,
  /\bdo\s+i\s+qualify\b/i,
  /\bwith\s+my\s+(gpa|grades?|score|ielts|toefl|profile|academic)\b/i,
  /\bmy\s+(gpa|grades?|score|ielts|toefl|profile|academic)\b/i,
  /\bbased\s+on\s+my\b/i,
  /\bwith\s+my\s+current\b/i,
  /\bqualify\s+with\s+my\b/i,
  /\bmatch\s+my\s+profile\b/i,
  /\bscholarships?\s+match\s+my\b/i,
  /\bwhich\s+scholarships?\s+match\s+(my|me)\b/i,
  /\bwhich\s+scholarships?\s+fit\s+(my|me)\b/i,
];

export function classifyRoute(message) {
  if (!message || typeof message !== 'string') {
    return 'mentor'; // default to private for safety
  }

  const lower = message.toLowerCase().trim();
  if (!lower) {
    return 'mentor';
  }

  // Phase 1: Check first-person eligibility patterns (highest priority)
  // These indicate private mentor intent even when discovery words are present
  for (const pattern of PRIVATE_ELIGIBILITY_PATTERNS) {
    if (pattern.test(message)) {
      return 'mentor';
    }
  }

  // Phase 2: Check private mentor phrases (more specific)
  for (const phrase of PRIVATE_MENTOR_PHRASES) {
    if (lower.includes(phrase)) {
      return 'mentor';
    }
  }

  // Phase 3: Check discovery phrases
  for (const phrase of DISCOVERY_PHRASES) {
    if (lower.includes(phrase)) {
      return 'discovery';
    }
  }

  // Phase 4: Check for discovery keywords combined with scholarship/opportunity
  const hasDiscoveryVerb = /\b(find|search|browse|show|list|discover|explore|look for|looking for|which)\b/.test(lower);
  const hasScholarshipNoun = /\b(scholarship|scholarships|opportunity|opportunities|grant|grants|funding)\b/.test(lower);
  if (hasDiscoveryVerb && hasScholarshipNoun) {
    return 'discovery';
  }

  // Phase 5: Check for degree + funding/country patterns (common discovery phrasing)
  const hasDegree = /\b(phd|doctoral|doctorate|master|masters|bachelor|undergraduate)\b/.test(lower);
  const hasFundingOrLocation = /\b(stipend|funded|funding|europe|germany|uk|usa|canada|australia|japan|korea|china|india|france|italy|spain|netherlands|sweden|norway|finland|denmark|switzerland|austria|belgium|portugal|poland|ireland|singapore|taiwan|new zealand)\b/.test(lower);
  if (hasDegree && hasFundingOrLocation && hasScholarshipNoun) {
    return 'discovery';
  }

  // Default to mentor for safety (private by default)
  return 'mentor';
}

// Export for testing
export { PRIVATE_ELIGIBILITY_PATTERNS, PRIVATE_MENTOR_PHRASES, DISCOVERY_PHRASES };
