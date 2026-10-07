/* ── Card presentation layer ───────────────────────────────────
   Every value a card shows passes through here. The rules below
   are the product's data contract, not styling choices:

   1. fully_funded is never read from a display label. The
      structured coverage columns (tuition_coverage,
      living_cost_coverage, travel_coverage, fully_funded flag)
      are the evidence; the `funding` string is marketing copy
      until the columns back it up.
   2. unknown is not none. A missing value renders as "Not
      published" with its own treatment, never as "None", "—" or
      a fabricated default.
   3. Estimated and official data are tagged separately and never
      mixed in one number.
   4. No fake dates. deadline_display + deadline_precision are the
      truth; an unknown precision never becomes a date.
   5. Match score, readiness and confidence are three different
      quantities and are never substituted for one another.
   6. Community testimony is never an official outcome.
   7. Programme-level and category-level records are labelled as
      such, so a category is never mistaken for one application.
   ─────────────────────────────────────────────────────────── */

export const DATA_PROVENANCE = {
  OFFICIAL: 'official',
  ESTIMATED: 'estimated',
  DERIVED: 'derived',
  COMMUNITY: 'community',
}

export const FUNDING_TRUTH = {
  FULL: 'full',
  PARTIAL: 'partial',
  NONE: 'none',
  UNKNOWN: 'unknown',
}

/* JSON columns arrive as JSON strings; a bare string is a real
   sentence filed in the wrong container, so it becomes a
   one-element list rather than being dropped. */
export function parseJsonColumn(value) {
  if (value == null) return []
  if (Array.isArray(value)) return value.filter(Boolean)
  if (typeof value === 'string') {
    const trimmed = value.trim()
    if (!trimmed) return []
    try {
      const parsed = JSON.parse(trimmed)
      if (Array.isArray(parsed)) return parsed.filter(Boolean)
      return [trimmed]
    } catch {
      return [trimmed]
    }
  }
  return []
}

function hasValue(value) {
  return value !== null && value !== undefined && String(value).trim() !== ''
}

/* ── Record normalization ─────────────────────────────────
   The catalogue API returns flat columns (tuition_coverage,
   fully_funded, deadline_display, ...). The premium research
   output returns the rich schema (funding.tuition.covered,
   deadlines.deadline_display, official_sources[], ...).

   normalizeRecord flattens either shape into the flat field
   set every derivation reads, so one code path serves both
   sources. A field that exists in neither shape stays null,
   which renders as "Not published" — never as a fabricated
   default. */
function readNested(source, path) {
  let current = source
  for (const key of path) {
    if (current == null || typeof current !== 'object') return null
    current = current[key]
  }
  return current ?? null
}

function coverageText(value) {
  if (value == null) return null
  if (typeof value === 'string') return value.trim() || null
  if (typeof value === 'boolean') return value ? 'Covered' : 'Not covered'
  if (typeof value === 'object') {
    if (typeof value.covered === 'string') return value.covered
    if (typeof value.coverage_note === 'string') return value.coverage_note
    if (typeof value.amount === 'string') return value.amount
    if (value.covered === true) return 'Covered'
    if (value.covered === false) return 'Not covered'
    return null
  }
  return null
}

function richEligibilityList(eligibility) {
  if (!eligibility || typeof eligibility !== 'object' || Array.isArray(eligibility)) return []
  const items = []
  const citizenship = eligibility.citizenship
  if (citizenship) {
    if (Array.isArray(citizenship.eligible_countries) && citizenship.eligible_countries.length) {
      items.push(`Open to: ${citizenship.eligible_countries.join(', ')}`)
    }
    if (citizenship.worldwide) {
      items.push('Open to all nationalities')
    }
    if (citizenship.residence_requirement) {
      items.push(`Residence: ${citizenship.residence_requirement}`)
    }
  }
  const age = eligibility.age
  if (age && (age.minimum != null || age.maximum != null)) {
    const parts = []
    if (age.minimum != null) parts.push(`min ${age.minimum}`)
    if (age.maximum != null) parts.push(`max ${age.maximum}`)
    items.push(`Age: ${parts.join(', ')}`)
  }
  const degree = eligibility.degree
  if (degree && degree.minimum_degree) {
    items.push(`Minimum degree: ${degree.minimum_degree}`)
  }
  const language = eligibility.language
  if (language && language.required) {
    const tests = Array.isArray(language.accepted_tests) ? language.accepted_tests.join(', ') : ''
    items.push(`Language required${tests ? `: ${tests}` : ''}`)
  }
  return items
}

function richEnglishRequirement(eligibility) {
  if (!eligibility || typeof eligibility !== 'object') return null
  const language = eligibility.language
  if (!language || typeof language !== 'object') return null
  const parts = []
  if (Array.isArray(language.teaching_language) && language.teaching_language.length) {
    parts.push(`Taught in ${language.teaching_language.join(', ')}`)
  }
  if (Array.isArray(language.accepted_tests) && language.accepted_tests.length) {
    parts.push(`Accepted: ${language.accepted_tests.join(', ')}`)
  }
  if (language.moi_accepted && language.moi_accepted !== 'unknown') {
    parts.push(`MOI accepted: ${language.moi_accepted}`)
  }
  return parts.length ? parts.join(' · ') : null
}

function richDocumentList(documents) {
  if (!documents || typeof documents !== 'object') return []
  const universal = Array.isArray(documents.universal_documents) ? documents.universal_documents : []
  const named = universal.map((doc) => (typeof doc === 'string' ? doc : doc?.name)).filter(Boolean)
  const academic = Array.isArray(documents.academic_documents) ? documents.academic_documents : []
  const academicNamed = academic.map((doc) => (typeof doc === 'string' ? doc : doc?.name)).filter(Boolean)
  return [...new Set([...named, ...academicNamed])]
}

function richBenefitsList(funding) {
  if (!funding || typeof funding !== 'object') return []
  const items = []
  const tuition = coverageText(funding.tuition)
  if (tuition) items.push(`Tuition: ${tuition}`)
  const living = coverageText(funding.living_costs)
  if (living) items.push(`Living costs: ${living}`)
  const travel = coverageText(funding.travel)
  if (travel) items.push(`Travel: ${travel}`)
  const monthly = funding.monthly_stipend
  if (monthly && monthly.amount != null) {
    items.push(`Monthly stipend: ${monthly.currency || ''} ${monthly.amount}`)
  }
  return items
}

function richRequirementsList(eligibility, application) {
  const items = richEligibilityList(eligibility)
  if (application && application.application_fee && application.application_fee.required) {
    items.push('Application fee required')
  }
  return items
}

function richSelectionNotes(selection) {
  if (!selection || typeof selection !== 'object') return null
  if (typeof selection.selection_process === 'string') return selection.selection_process
  return null
}

function richSupervisorCoverage(supervisor) {
  if (!supervisor || typeof supervisor !== 'object') return null
  const available = supervisor.available
  let state = 'unknown'
  if (available === true) state = 'confirmed'
  else if (available === false) state = 'not_accepting'
  return {
    state,
    available,
    programme_requires_supervisor: supervisor.programme_requires_supervisor ?? null,
    professors: Array.isArray(supervisor.professors) ? supervisor.professors : [],
  }
}

/* ── Country / degree estimation ─────────────────────
   The research records carry the country and degree only
   inside the title and provider text, not as structured
   fields. Deriving them is ESTIMATION, not official data,
   so it is tagged as such and never mixed with official
   figures. A known country name in the title is a strong
   signal; a provider name is a weaker one. */
const COUNTRY_NAMES = [
  'Denmark', 'Norway', 'Sweden', 'Finland', 'Iceland',
  'Germany', 'France', 'Netherlands', 'Belgium', 'Austria',
  'Switzerland', 'Italy', 'Spain', 'Portugal', 'Ireland',
  'United Kingdom', 'UK', 'England', 'Scotland', 'Wales',
  'Poland', 'Czech Republic', 'Czechia', 'Hungary', 'Romania',
  'Greece', 'Estonia', 'Latvia', 'Lithuania',
  'United States', 'USA', 'Canada', 'Australia', 'New Zealand',
  'Japan', 'South Korea', 'Korea', 'Singapore', 'China',
  'India', 'Brazil', 'Mexico', 'Argentina', 'Chile',
  'Turkey', 'Türkiye', 'Egypt', 'Nigeria', 'Kenya', 'Ghana',
  'Malaysia', 'Indonesia', 'Thailand', 'Vietnam', 'Philippines',
  'Luxembourg', 'Cyprus', 'Malta', 'Slovenia', 'Slovakia',
  'Croatia', 'Serbia', 'Bulgaria', 'Ukraine', 'Georgia',
]

/* Adjective forms carry the country just as strongly as the
   noun — "Danish Government Scholarship" names Denmark. */
const COUNTRY_ADJECTIVES = {
  Danish: 'Denmark',
  Norwegian: 'Norway',
  Swedish: 'Sweden',
  Finnish: 'Finland',
  Icelandic: 'Iceland',
  German: 'Germany',
  French: 'France',
  Dutch: 'Netherlands',
  Belgian: 'Belgium',
  Austrian: 'Austria',
  Swiss: 'Switzerland',
  Italian: 'Italy',
  Spanish: 'Spain',
  Portuguese: 'Portugal',
  Irish: 'Ireland',
  British: 'United Kingdom',
  English: 'England',
  Scottish: 'Scotland',
  Welsh: 'Wales',
  Polish: 'Poland',
  Czech: 'Czechia',
  Hungarian: 'Hungary',
  Romanian: 'Romania',
  Greek: 'Greece',
  Estonian: 'Estonia',
  Latvian: 'Latvia',
  Lithuanian: 'Lithuania',
  American: 'United States',
  Canadian: 'Canada',
  Australian: 'Australia',
  Japanese: 'Japan',
  Korean: 'South Korea',
  Singaporean: 'Singapore',
  Chinese: 'China',
  Indian: 'India',
  Brazilian: 'Brazil',
  Mexican: 'Mexico',
  Argentine: 'Argentina',
  Chilean: 'Chile',
  Turkish: 'Turkey',
  Egyptian: 'Egypt',
  Nigerian: 'Nigeria',
  Kenyan: 'Kenya',
  Ghanaian: 'Ghana',
  Malaysian: 'Malaysia',
  Indonesian: 'Indonesia',
  Thai: 'Thailand',
  Vietnamese: 'Vietnam',
  Filipino: 'Philippines',
  Luxembourgish: 'Luxembourg',
  Cypriot: 'Cyprus',
  Maltese: 'Malta',
  Slovenian: 'Slovenia',
  Slovak: 'Slovakia',
  Croatian: 'Croatia',
  Serbian: 'Serbia',
  Bulgarian: 'Bulgaria',
  Ukrainian: 'Ukraine',
  Georgian: 'Georgia',
}

const DEGREE_KEYWORDS = [
  { pattern: /\b(PhD|Ph\.D\.|doctorate|doctoral|DPhil)\b/i, value: 'Doctoral (PhD)' },
  { pattern: /\b(Master|MSc|MA|M\.Eng|MPhil|graduate)\b/i, value: "Master's" },
  { pattern: /\b(Bachelor|BSc|BA|B\.Eng|undergraduate|UG)\b/i, value: "Bachelor's" },
  { pattern: /\b(postdoc|post-doctoral|postdoctoral)\b/i, value: 'Postdoctoral' },
  { pattern: /\b(exchange|semester abroad)\b/i, value: 'Exchange' },
]

function estimateCountry(text) {
  if (typeof text !== 'string') return null
  for (const [adjective, country] of Object.entries(COUNTRY_ADJECTIVES)) {
    if (new RegExp(`\\b${adjective}\\b`, 'i').test(text)) {
      return country
    }
  }
  for (const name of COUNTRY_NAMES) {
    if (new RegExp(`\\b${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'i').test(text)) {
      return name === 'UK' ? 'United Kingdom' : name === 'Korea' ? 'South Korea' : name === 'Türkiye' ? 'Turkey' : name
    }
  }
  return null
}

function estimateDegree(text) {
  if (typeof text !== 'string') return null
  for (const { pattern, value } of DEGREE_KEYWORDS) {
    if (pattern.test(text)) return value
  }
  return null
}

export function normalizeRecord(scholarship) {
  if (!scholarship || typeof scholarship !== 'object') return scholarship

  const funding = scholarship.funding && typeof scholarship.funding === 'object' && !Array.isArray(scholarship.funding)
    ? scholarship.funding
    : {}
  const deadlines = scholarship.deadlines && typeof scholarship.deadlines === 'object' && !Array.isArray(scholarship.deadlines)
    ? scholarship.deadlines
    : {}
  const application = scholarship.application && typeof scholarship.application === 'object' && !Array.isArray(scholarship.application)
    ? scholarship.application
    : {}
  const documentsObj = scholarship.documents && typeof scholarship.documents === 'object' && !Array.isArray(scholarship.documents)
    ? scholarship.documents
    : {}
  const eligibilityObj = scholarship.eligibility && typeof scholarship.eligibility === 'object' && !Array.isArray(scholarship.eligibility)
    ? scholarship.eligibility
    : {}
  const officialSources = Array.isArray(scholarship.official_sources) ? scholarship.official_sources : []
  const academic = scholarship.academic_profile && typeof scholarship.academic_profile === 'object' && !Array.isArray(scholarship.academic_profile)
    ? scholarship.academic_profile
    : {}
  const location = scholarship.location && typeof scholarship.location === 'object' && !Array.isArray(scholarship.location)
    ? scholarship.location
    : {}
  const supervisorRaw = scholarship.supervisor_and_professor_connection && typeof scholarship.supervisor_and_professor_connection === 'object' && !Array.isArray(scholarship.supervisor_and_professor_connection)
    ? scholarship.supervisor_and_professor_connection
    : null

  const providerValue = scholarship.provider
  const providerName = typeof providerValue === 'string'
    ? providerValue
    : providerValue && typeof providerValue === 'object'
      ? providerValue.name
      : null

  const firstSource = officialSources[0] || {}

  const flatEligibility = parseJsonColumn(scholarship.eligibility)
  const flatDocuments = parseJsonColumn(scholarship.documents)
  const flatBenefits = parseJsonColumn(scholarship.benefits)
  const flatCoverage = parseJsonColumn(scholarship.coverage)
  const flatRequirements = parseJsonColumn(scholarship.requirements)

  const normalized = {
    ...scholarship,

    fully_funded: scholarship.fully_funded ?? funding.fully_funded ?? null,
    tuition_coverage: scholarship.tuition_coverage ?? coverageText(funding.tuition) ?? null,
    living_cost_coverage: scholarship.living_cost_coverage ?? coverageText(funding.living_costs) ?? null,
    travel_coverage: scholarship.travel_coverage ?? coverageText(funding.travel) ?? null,
    funding_amount: scholarship.funding_amount
      ?? readNested(funding, ['total_nominal_value', 'amount'])
      ?? readNested(funding, ['award_amount', 'fixed'])
      ?? readNested(funding, ['monthly_stipend', 'amount'])
      ?? null,
    funding_currency: scholarship.funding_currency
      ?? funding.currency
      ?? readNested(funding, ['total_nominal_value', 'currency'])
      ?? readNested(funding, ['monthly_stipend', 'currency'])
      ?? null,
    funding_period: scholarship.funding_period
      ?? readNested(funding, ['award_amount', 'period'])
      ?? readNested(funding, ['monthly_stipend', 'duration_months'])
      ?? null,

    deadline_display: scholarship.deadline_display ?? deadlines.deadline_display ?? null,
    deadline_date: scholarship.deadline_date ?? deadlines.deadline_date ?? null,
    deadline_precision: scholarship.deadline_precision ?? deadlines.deadline_precision ?? null,

    official_source: scholarship.official_source ?? providerName ?? firstSource.title ?? null,
    official_source_url: scholarship.official_source_url ?? firstSource.url ?? null,
    catalogue_url: scholarship.catalogue_url ?? null,
    official_updates_url: scholarship.official_updates_url ?? null,
    application_link: scholarship.application_link ?? application.official_application_url ?? scholarship.official_application_url ?? null,

    eligibility: flatEligibility.length ? flatEligibility : richEligibilityList(eligibilityObj),
    eligibility_summary: scholarship.eligibility_summary ?? null,
    documents: flatDocuments.length ? flatDocuments : richDocumentList(documentsObj),
    benefits: flatBenefits.length ? flatBenefits : richBenefitsList(funding),
    coverage: flatCoverage.length ? flatCoverage : richBenefitsList(funding),
    requirements: flatRequirements.length ? flatRequirements : richRequirementsList(eligibilityObj, application),
    english_requirement: scholarship.english_requirement ?? richEnglishRequirement(eligibilityObj) ?? null,

    duration: scholarship.duration ?? readNested(academic, ['duration', 'display']) ?? null,
    notes: scholarship.notes ?? null,
    selection_notes: scholarship.selection_notes ?? richSelectionNotes(scholarship.selection) ?? null,
    best_fit: scholarship.best_fit ?? null,

    provider: providerName,
    country: scholarship.country
      ?? location.host_country
      ?? estimateCountry(`${scholarship.title || ''} ${providerName || ''}`),
    degree: scholarship.degree
      ?? academic.primary_degree
      ?? academic.study_level
      ?? estimateDegree(scholarship.title || ''),

    supervisor_coverage: scholarship.supervisor_coverage ?? richSupervisorCoverage(supervisorRaw),

    /* Fields derived from title/provider text rather than
       read from a structured column. Surfaced in Level 4 so
       the reader knows which values are estimates. */
    _estimated_fields: [
      ...(scholarship.country || location.host_country ? [] : ['country']),
      ...(scholarship.degree || academic.primary_degree || academic.study_level ? [] : ['degree']),
    ],
  }

  return normalized
}

/* ── Rule 1: funding truth ─────────────────────────────────────
   The structured flag wins. A "Fully Funded" label with a
   fully_funded flag of 0 (Erasmus Mundus is the live example:
   50+ separate consortia, each with its own package) is reported
   as conditional, not as full. */
export function deriveFundingTruth(scholarship) {
  const flag = scholarship.fully_funded
  const tuition = (scholarship.tuition_coverage || '').toString().toLowerCase()
  const living = (scholarship.living_cost_coverage || '').toString().toLowerCase()
  const travel = (scholarship.travel_coverage || '').toString().toLowerCase()
  /* `funding` carries the provider's own funding description
     (e.g. "Full or partial tuition fee waiver"). It is a
     description, not a fully-funded claim, so it is shown
     as the label but never promotes the truth to FULL.
     The catalogue maps it to a string; the raw research
     shape keeps it as an object with a funding_type field. */
  const rawFunding = scholarship.funding
  const fundingLabel = typeof rawFunding === 'string'
    ? rawFunding.trim()
    : rawFunding && typeof rawFunding === 'object'
      ? (rawFunding.funding_type || '').toString().trim()
      : ''

  const tuitionFull = /full|100%|entire|complete/i.test(tuition)
  const livingFull = /full|100%|entire|complete|stipend|allowance/i.test(living)

  const structuredEvidence = [tuition, living, travel].some((v) => v.trim() !== '')

  if (flag === 1 || flag === true) {
    if (structuredEvidence && !tuitionFull) {
      return {
        truth: FUNDING_TRUTH.PARTIAL,
        label: 'Partially funded',
        note: 'Listed as fully funded, but the published coverage does not confirm full tuition.',
        provenance: DATA_PROVENANCE.DERIVED,
      }
    }
    return {
      truth: FUNDING_TRUTH.FULL,
      label: 'Fully funded',
      note: null,
      provenance: DATA_PROVENANCE.OFFICIAL,
    }
  }

  if (flag === 0 || flag === false) {
    /* The structured flag explicitly says NOT fully funded.
       That is evidence, so the truth is partial — never
       promoted to full, and never reported as unknown. */
    if (tuitionFull || livingFull) {
      return {
        truth: FUNDING_TRUTH.PARTIAL,
        label: 'Partially funded',
        note: 'Coverage is partial or varies by programme — check the breakdown below.',
        provenance: DATA_PROVENANCE.DERIVED,
      }
    }
    if (structuredEvidence) {
      return {
        truth: FUNDING_TRUTH.PARTIAL,
        label: 'Partial funding published',
        note: 'The provider publishes specific coverage; it is not a full package.',
        provenance: DATA_PROVENANCE.DERIVED,
      }
    }
    return {
      truth: FUNDING_TRUTH.PARTIAL,
      label: fundingLabel || 'Not fully funded',
      note: 'The provider does not list this as fully funded. Confirm the exact coverage.',
      provenance: DATA_PROVENANCE.DERIVED,
    }
  }

  /* fully_funded is null — the record does not say. */
  if (structuredEvidence) {
    return {
      truth: FUNDING_TRUTH.PARTIAL,
      label: fundingLabel || 'Partial funding published',
      note: 'The provider publishes specific coverage; the fully-funded status is not confirmed.',
      provenance: DATA_PROVENANCE.DERIVED,
    }
  }

  return {
    truth: FUNDING_TRUTH.UNKNOWN,
    label: fundingLabel || 'Funding not confirmed',
    note: 'No structured funding data published for this record. Confirm with the provider.',
    provenance: DATA_PROVENANCE.DERIVED,
  }
}

export function deriveFundingAmount(scholarship) {
  const amount = scholarship.funding_amount
  const currency = scholarship.funding_currency
  const period = scholarship.funding_period

  if (!hasValue(amount)) {
    return {
      display: null,
      amount: null,
      currency: null,
      period: null,
      provenance: DATA_PROVENANCE.DERIVED,
      missing: true,
    }
  }

  const numeric = typeof amount === 'number' ? amount : Number(amount)
  const parsed = Number.isFinite(numeric) ? numeric : null

  return {
    display: `${currency || ''} ${parsed !== null ? parsed.toLocaleString() : amount}`.trim(),
    amount: parsed,
    currency: currency || null,
    period: period || null,
    provenance: DATA_PROVENANCE.OFFICIAL,
    missing: false,
  }
}

export function deriveTuitionStatus(scholarship) {
  const tuition = (scholarship.tuition_coverage || '').toString().trim()

  if (tuition) {
    const lowered = tuition.toLowerCase()
    if (/full|100%|entire|complete|waived/i.test(lowered)) {
      return { status: 'full', label: 'Tuition fully covered', detail: tuition, provenance: DATA_PROVENANCE.OFFICIAL }
    }
    if (/partial|part|up to/i.test(lowered)) {
      return { status: 'partial', label: 'Tuition partially covered', detail: tuition, provenance: DATA_PROVENANCE.OFFICIAL }
    }
    return { status: 'other', label: tuition, detail: tuition, provenance: DATA_PROVENANCE.OFFICIAL }
  }

  /* The structured tuition column is absent. The provider's
     own funding description often states the tuition coverage
     ("Full tuition fee waiver", "100% tuition coverage").
     Reading it is legitimate — it is official provider text —
     but it is a description, not a structured field, so the
     result is tagged as derived. */
  const rawFunding = scholarship.funding
  const fundingLabel = typeof rawFunding === 'string'
    ? rawFunding
    : rawFunding && typeof rawFunding === 'object'
      ? (rawFunding.funding_type || '')
      : ''

  if (fundingLabel) {
    const lowered = fundingLabel.toLowerCase()
    const fullTuition = /full tuition|100% tuition|full.*tuition.*(waiver|coverage|covered)|tuition.*(100%|fully|full).*(waiver|coverage|covered)|tuition fully/i.test(lowered)
    const partialTuition = /partial.*tuition|tuition.*partial|partial.*waiver/i.test(lowered)
    const anyWaiver = /tuition.*(waiver|waived)|waiver.*tuition/i.test(lowered)

    if (fullTuition) {
      return { status: 'full', label: 'Tuition covered (per funding description)', detail: fundingLabel, provenance: DATA_PROVENANCE.DERIVED }
    }
    if (partialTuition) {
      return { status: 'partial', label: 'Tuition partially covered (per funding description)', detail: fundingLabel, provenance: DATA_PROVENANCE.DERIVED }
    }
    if (anyWaiver) {
      return { status: 'partial', label: 'Tuition waiver (extent not specified)', detail: fundingLabel, provenance: DATA_PROVENANCE.DERIVED }
    }
  }

  return { status: 'not_published', label: 'Tuition coverage not published', provenance: DATA_PROVENANCE.DERIVED }
}

/* ── Rule 4: deadline truth ────────────────────────────────────
   An unknown precision never becomes a date. The display text is
   shown exactly as the provider published it. */
export function deriveDeadline(scholarship) {
  const precision = scholarship.deadline_precision
  const display = scholarship.deadline_display || scholarship.deadline
  const date = scholarship.deadline_date

  if (!hasValue(display) && !hasValue(date)) {
    return {
      label: 'Deadline not published',
      display: null,
      precision: 'unknown',
      isExact: false,
      provenance: DATA_PROVENANCE.DERIVED,
    }
  }

  const isExact = precision === 'exact' && hasValue(date)

  return {
    label: display || (date ? String(date) : 'Deadline not published'),
    display: display || null,
    date: date || null,
    precision: precision || 'unknown',
    isExact,
    provenance: isExact ? DATA_PROVENANCE.OFFICIAL : DATA_PROVENANCE.DERIVED,
  }
}

/* ── Rule 5: three separate scores ─────────────────────────────
   matchScore comes from the match engine for a specific student
   profile. readiness comes from record completeness. confidence
   comes from verification state. None implies another. */
export function deriveMatchScore(scholarship, matchResult) {
  if (!matchResult) {
    return {
      scored: false,
      label: 'Not scored for you yet',
      hint: 'Run the Match quiz to score this against your profile.',
      score: null,
      provenance: DATA_PROVENANCE.DERIVED,
    }
  }

  const score = matchResult?.match_score ?? matchResult?.score ?? null
  if (score === null || score === undefined) {
    return { scored: false, label: 'Not scored', score: null, provenance: DATA_PROVENANCE.DERIVED }
  }

  return {
    scored: true,
    score,
    label: `${Math.round(score)}% match`,
    provenance: DATA_PROVENANCE.DERIVED,
  }
}

export function deriveReadiness(scholarship) {
  const checks = [
    { key: 'deadline', present: hasValue(scholarship.deadline_display) || hasValue(scholarship.deadline_date) },
    { key: 'funding', present: hasValue(scholarship.funding_amount) || hasValue(scholarship.tuition_coverage) },
    { key: 'eligibility', present: parseJsonColumn(scholarship.eligibility).length > 0 || hasValue(scholarship.eligibility_summary) },
    { key: 'documents', present: parseJsonColumn(scholarship.documents).length > 0 },
    { key: 'application_link', present: hasValue(scholarship.application_link) },
  ]

  const present = checks.filter((c) => c.present).length
  const ratio = present / checks.length

  let level
  if (ratio >= 0.8) level = 'ready'
  else if (ratio >= 0.6) level = 'almost_ready'
  else level = 'needs_preparation'

  return {
    level,
    label:
      level === 'ready'
        ? 'Ready to apply'
        : level === 'almost_ready'
          ? 'Almost ready'
          : 'Needs preparation',
    present,
    total: checks.length,
    missing: checks.filter((c) => !c.present).map((c) => c.key),
    provenance: DATA_PROVENANCE.DERIVED,
  }
}

export function deriveConfidence(scholarship) {
  const status = scholarship.verification_status || 'needs_review'
  const daysSinceVerified = scholarship.last_verified_at
    ? Math.floor((Date.now() - new Date(`${scholarship.last_verified_at}T00:00:00`).getTime()) / 86400000)
    : null

  let level
  if (status === 'active' && daysSinceVerified !== null && daysSinceVerified <= 90) level = 'high'
  else if (status === 'active') level = 'medium'
  else level = 'low'

  return {
    level,
    label:
      level === 'high'
        ? 'High confidence'
        : level === 'medium'
          ? 'Moderate confidence'
          : 'Low confidence',
    status,
    daysSinceVerified,
    provenance: DATA_PROVENANCE.DERIVED,
  }
}

/* ── Next action ─────────────────────────────────────────────── */
export function deriveNextAction(scholarship, matchResult) {
  const deadline = deriveDeadline(scholarship)
  const readiness = deriveReadiness(scholarship)
  const status = scholarship.status

  if (status === 'closed') {
    return { code: 'watch_next_cycle', label: 'Watch for the next cycle', priority: 'low' }
  }
  if (!matchResult) {
    return { code: 'run_match', label: 'Run the Match quiz', priority: 'medium' }
  }
  if (readiness.level === 'needs_preparation') {
    return { code: 'gather_documents', label: 'Gather missing documents', priority: 'high' }
  }
  if (deadline.isExact) {
    return { code: 'apply_now', label: 'Apply now', priority: 'urgent' }
  }
  return { code: 'confirm_deadline', label: 'Confirm the exact deadline with the provider', priority: 'medium' }
}

/* ── Rule 2: unknowns are surfaced, never hidden ─────────────── */
export function deriveUnknowns(scholarship) {
  const unknowns = []

  if (!hasValue(scholarship.funding_amount) && !hasValue(scholarship.tuition_coverage)) {
    unknowns.push({ field: 'Funding amount', note: 'No award figure published on the record.' })
  }
  if (!hasValue(scholarship.deadline_date)) {
    unknowns.push({ field: 'Exact deadline', note: 'Only a display window is published; no single date.' })
  }
  if (parseJsonColumn(scholarship.documents).length === 0) {
    unknowns.push({ field: 'Document list', note: 'The provider does not publish a document checklist here.' })
  }
  if (!hasValue(scholarship.duration)) {
    unknowns.push({ field: 'Duration', note: 'Programme length not published on this record.' })
  }
  if (!hasValue(scholarship.english_requirement)) {
    unknowns.push({ field: 'Language requirement', note: 'No language requirement published.' })
  }

  return unknowns
}

/* ── Funding coverage breakdown (Level 2) ────────────────────── */
export function deriveFundingCoverage(scholarship) {
  const benefits = parseJsonColumn(scholarship.benefits)
  const coverage = parseJsonColumn(scholarship.coverage)
  const items = [...new Set([...coverage, ...benefits])]

  return {
    tuition: (scholarship.tuition_coverage || '').toString().trim() || null,
    living: (scholarship.living_cost_coverage || '').toString().trim() || null,
    travel: (scholarship.travel_coverage || '').toString().trim() || null,
    items,
    provenance: items.length > 0 ? DATA_PROVENANCE.OFFICIAL : DATA_PROVENANCE.DERIVED,
  }
}

/* ── Risk flags (Level 2) ────────────────────────────────────── */
export function deriveRiskFlags(scholarship) {
  const flags = []
  const fundingTruth = deriveFundingTruth(scholarship)
  const deadline = deriveDeadline(scholarship)
  const confidence = deriveConfidence(scholarship)

  if (fundingTruth.truth === FUNDING_TRUTH.UNKNOWN) {
    flags.push({
      severity: 'high',
      label: 'Funding unconfirmed',
      detail: 'The listing claims full funding but the structured coverage is not published.',
    })
  }
  if (!deadline.isExact) {
    flags.push({
      severity: 'medium',
      label: 'Deadline not exact',
      detail: 'The deadline is a window or varies by programme; confirm the exact date.',
    })
  }
  if (confidence.level === 'low') {
    flags.push({
      severity: 'medium',
      label: 'Record not recently verified',
      detail: 'This record has not been re-checked against the official page recently.',
    })
  }
  if (scholarship.notes) {
    flags.push({
      severity: 'info',
      label: 'Provider note',
      detail: scholarship.notes,
    })
  }

  return flags
}

/* ── Level 3 derivations ─────────────────────────────────────── */
export function deriveApplicationEffort(scholarship) {
  const documents = parseJsonColumn(scholarship.documents)
  const requirements = parseJsonColumn(scholarship.requirements)
  const essayCount = requirements.filter((r) => /essay|motivation letter|statement/i.test(r)).length
  const referenceCount = documents.filter((d) => /recommendation|reference/i.test(d)).length

  let complexity = 'low'
  if (documents.length >= 6 || essayCount >= 1) complexity = 'medium'
  if (documents.length >= 8 || essayCount >= 2) complexity = 'high'

  return {
    complexity,
    label:
      complexity === 'low'
        ? 'Low effort'
        : complexity === 'medium'
          ? 'Medium effort'
          : 'High effort',
    documentsCount: documents.length,
    essayCount,
    referenceCount,
    provenance: DATA_PROVENANCE.DERIVED,
  }
}

export function deriveCostGap(scholarship) {
  const fundingTruth = deriveFundingTruth(scholarship)
  const living = (scholarship.living_cost_coverage || '').toString().toLowerCase()

  if (fundingTruth.truth === FUNDING_TRUTH.FULL) {
    return {
      status: 'covered',
      label: 'No published gap',
      note: 'Full coverage is published; no self-funding figure is estimated.',
      provenance: DATA_PROVENANCE.DERIVED,
    }
  }

  if (/full|100%|stipend|allowance/i.test(living)) {
    return {
      status: 'partial',
      label: 'Living costs covered; other costs may remain',
      note: 'Travel, insurance and setup costs are not itemised on this record.',
      provenance: DATA_PROVENANCE.DERIVED,
    }
  }

  return {
    status: 'unknown',
    label: 'Cost gap not published',
    note: 'The record does not publish enough to estimate an uncovered cost. Do not assume zero.',
    provenance: DATA_PROVENANCE.DERIVED,
  }
}

export function deriveMobilityBurden(scholarship) {
  const country = (scholarship.country || '').toString()
  const multi = /multiple|eu \(|consortium|joint|erasmus|several/i.test(country)
  const notes = (scholarship.notes || '').toString().toLowerCase()
  const mobilityMentioned = /mobility|semester|exchange|two countr|multiple countr/i.test(notes)

  if (multi || mobilityMentioned) {
    return {
      intensity: 'high',
      label: 'Multi-country mobility',
      note: 'This programme involves more than one host country or a consortium.',
      provenance: DATA_PROVENANCE.DERIVED,
    }
  }

  return {
    intensity: 'low',
    label: 'Single destination',
    note: 'One host country is published on this record.',
    provenance: DATA_PROVENANCE.DERIVED,
  }
}

export function deriveVisaComplexity(scholarship) {
  const country = (scholarship.country || '').toString()
  const eu = /eu \(|europe|erasmus|schengen/i.test(country)

  if (eu) {
    return {
      level: 'varies',
      label: 'Varies by host country',
      note: 'EU-wide programmes: visa rules depend on the specific host country and your citizenship.',
      provenance: DATA_PROVENANCE.DERIVED,
    }
  }

  return {
    level: 'unknown',
    label: 'Not published on this record',
    note: 'Check the destination country\'s immigration authority for visa requirements.',
    provenance: DATA_PROVENANCE.DERIVED,
  }
}

export function deriveDocumentReuse(scholarship) {
  const documents = parseJsonColumn(scholarship.documents)
  const reusable = documents.filter((d) =>
    /transcript|certificate|passport|cv|photo|birth/i.test(d),
  )
  const custom = documents.filter((d) =>
    /motivation|essay|statement|proposal|research plan/i.test(d),
  )

  return {
    reusable,
    mustCustomize: custom,
    newDocumentsNeeded: documents.length - reusable.length - custom.length,
    provenance: DATA_PROVENANCE.DERIVED,
  }
}

/* ── Level 4 derivations ─────────────────────────────────────── */
export function deriveOfficialSources(scholarship) {
  const sources = []

  if (hasValue(scholarship.official_source_url)) {
    sources.push({
      url: scholarship.official_source_url,
      title: scholarship.official_source || 'Official provider page',
      source_type: 'official_provider',
      supports: ['funding', 'eligibility', 'deadline'],
    })
  }
  if (hasValue(scholarship.catalogue_url)) {
    sources.push({
      url: scholarship.catalogue_url,
      title: 'Programme catalogue',
      source_type: 'official_provider',
      supports: ['programme_list'],
    })
  }
  if (hasValue(scholarship.official_updates_url)) {
    sources.push({
      url: scholarship.official_updates_url,
      title: 'Official updates / notifications',
      source_type: 'official_provider',
      supports: ['deadline', 'status'],
    })
  }
  if (hasValue(scholarship.application_link)) {
    sources.push({
      url: scholarship.application_link,
      title: 'Application portal',
      source_type: 'official_provider',
      supports: ['application'],
    })
  }

  return sources
}

export function deriveSelectionCriteria(scholarship) {
  const selectionNotes = scholarship.selection_notes
  const bestFit = scholarship.best_fit
  const eligibilitySummary = scholarship.eligibility_summary

  const criteria = []
  if (hasValue(eligibilitySummary)) {
    criteria.push({ name: 'Eligibility', detail: eligibilitySummary, weight: null })
  }
  if (hasValue(selectionNotes)) {
    criteria.push({ name: 'Selection', detail: selectionNotes, weight: null })
  }
  if (hasValue(bestFit)) {
    criteria.push({ name: 'Best fit', detail: bestFit, weight: null })
  }

  return {
    criteria,
    officialWeightingAvailable: false,
    provenance: DATA_PROVENANCE.OFFICIAL,
  }
}

export function deriveTerms(scholarship) {
  const requirements = parseJsonColumn(scholarship.requirements)
  const coverage = parseJsonColumn(scholarship.coverage)

  return {
    academicRequirements: requirements,
    coverageConditions: coverage,
    workRestrictions: null,
    terminationConditions: null,
    provenance: DATA_PROVENANCE.OFFICIAL,
  }
}

export function deriveFAQ(scholarship) {
  const faq = []
  const fundingTruth = deriveFundingTruth(scholarship)
  const deadline = deriveDeadline(scholarship)
  const english = scholarship.english_requirement

  faq.push({
    category: 'funding',
    question: 'Is this scholarship fully funded?',
    answer:
      fundingTruth.truth === FUNDING_TRUTH.FULL
        ? 'Yes — full coverage is published on the record.'
        : fundingTruth.truth === FUNDING_TRUTH.PARTIAL
          ? `Partially. ${fundingTruth.note || 'Check the coverage breakdown.'}`
          : 'Not confirmed on this record. Ask the provider directly.',
  })

  faq.push({
    category: 'application',
    question: 'When is the deadline?',
    answer: deadline.isExact
      ? deadline.label
      : deadline.label === 'Deadline not published'
        ? 'No deadline is published on this record.'
        : `${deadline.label} — no single exact date is published.`,
  })

  if (hasValue(english)) {
    faq.push({
      category: 'programme',
      question: 'What English proof is needed?',
      answer: english,
    })
  }

  return faq
}

export function deriveContactSupport(scholarship) {
  return {
    provider: scholarship.official_source || null,
    officialUrl: scholarship.official_source_url || null,
    applicationPortal: scholarship.application_link || null,
    updatesUrl: scholarship.official_updates_url || null,
    note: 'No direct email or phone is published on this record. Use the official portal contact form.',
  }
}

/* ── Rule 7: programme vs category ───────────────────────────── */
export function deriveRecordKind(scholarship) {
  const notes = (scholarship.notes || '').toString().toLowerCase()
  const title = (scholarship.title || '').toString().toLowerCase()
  const isCategory =
    /category of|not one application|50\+|consortium|varies by (consortium|programme|university)/.test(notes) ||
    /joint masters|erasmus mundus/.test(title)

  return {
    kind: isCategory ? 'category' : 'programme',
    label: isCategory ? 'Programme category' : 'Single programme',
    note: isCategory
      ? 'This is a category of separate programmes, each with its own application and deadline — not one application.'
      : null,
  }
}

/* ── Supervisor availability (Level 3) ─────────────────────────
   Never claims a response rate or acceptance probability. Only
   explicit states with sources are shown. */
export function deriveSupervisorAvailability(scholarship) {
  const coverage = scholarship.supervisor_coverage
  if (!coverage) {
    return {
      available: 'unknown',
      label: 'Supervisor data not on this record',
      note: 'Supervisor discovery is available for research degrees on the Supervisor panel.',
      provenance: DATA_PROVENANCE.DERIVED,
    }
  }
  return {
    available: coverage.state || 'unknown',
    label: coverage.state || 'Unknown',
    sourceUrl: coverage.source_url || null,
    verifiedAt: coverage.verified_at || null,
    provenance: DATA_PROVENANCE.OFFICIAL,
  }
}

/* ── Country career snapshot (Level 3) ─────────────────────────
   Only shown when country intelligence exists for the host
   country. Salary and employment figures are never invented. */
export function deriveCountrySnapshot(scholarship, countryIntelligence) {
  if (!countryIntelligence) {
    return {
      available: false,
      label: 'Country intelligence not loaded',
      note: null,
    }
  }

  return {
    available: true,
    country: countryIntelligence.country || scholarship.country,
    overallScore: countryIntelligence.overall_score ?? null,
    scores: countryIntelligence.scores || null,
    expectedSalary: countryIntelligence.expected_salary || null,
    careerDataNote: 'Figures are estimates unless marked official. See the Country page for sources.',
    provenance: DATA_PROVENANCE.ESTIMATED,
  }
}
