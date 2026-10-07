/**
 * Loads premium card research output from the research/premium_card/output directory.
 * Each JSON file contains a structured scholarship record.
 *
 * The research output is mapped to the flat column format expected by
 * PremiumScholarshipCard and cardPresentation utilities.
 */

const RESEARCH_ROOT = '/research/premium_card/output'

let cachedResearch = null

async function fetchResearchEntries() {
  if (cachedResearch) return cachedResearch

  const response = await fetch(`${RESEARCH_ROOT}/index.json`, {
    headers: { Accept: 'application/json' },
  })

  if (!response.ok) {
    throw new Error(`Unable to load research output: ${response.status}`)
  }

  const entries = await response.json()
  cachedResearch = entries
  return entries
}

function flattenValue(value) {
  if (value === null || value === undefined) return null
  if (typeof value === 'string') return value.trim() || null
  if (typeof value === 'number' || typeof value === 'boolean') return value
  if (Array.isArray(value)) {
    const filtered = value.filter((item) => item !== null && item !== undefined && String(item).trim() !== '')
    return filtered.length ? JSON.stringify(filtered) : null
  }
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value).trim() || null
}

function mapResearchToFlatCard(entry) {
  const data = entry.data || entry
  const provider = typeof data.provider === 'string' ? { name: data.provider } : (data.provider || {})
  const image = data.image || {}
  const funding = data.funding || {}
  const eligibility = data.eligibility || {}
  const application = data.application || {}
  const deadlines = data.deadlines || {}
  const officialSources = Array.isArray(data.official_sources) ? data.official_sources : []
  const tuition = funding.tuition || {}
  const livingCosts = funding.living_costs || {}
  const travel = funding.travel || {}

  const benefits = []
  const coverage = []
  if (tuition.covered && tuition.covered !== 'false') coverage.push('Tuition')
  if (livingCosts.covered && livingCosts.covered !== 'false') coverage.push('Living costs')
  if (travel.covered && travel.covered !== 'false') coverage.push('Travel')

  return {
    id: data.id || entry.id,
    title: data.title || entry.source_title || '',
    provider: provider.name || entry.source_provider || '',
    country: data.location?.host_country || data.location?.study_countries?.[0] || '',
    degree: data.academic_profile?.primary_degree || data.academic_profile?.study_level || '',

    funding: flattenValue(funding.funding_type || data.funding_label),
    funding_amount: funding.award_amount?.fixed || funding.award_amount?.minimum || funding.monthly_stipend?.amount || null,
    funding_currency: flattenValue(funding.currency || funding.monthly_stipend?.currency),
    funding_period: flattenValue(funding.award_amount?.period),
    fully_funded: funding.fully_funded ?? null,

    tuition_coverage: flattenValue(tuition.covered === true ? 'Full' : tuition.covered === 'partial' ? 'Partial' : tuition.coverage_note || tuition.covered),
    living_cost_coverage: flattenValue(livingCosts.covered === true ? 'Full' : livingCosts.covered === 'partial' ? 'Partial' : livingCosts.coverage_note || livingCosts.covered),
    travel_coverage: flattenValue(travel.covered === true ? 'Full' : travel.covered === 'partial' ? 'Partial' : travel.route_or_conditions || travel.covered),

    benefits: flattenValue(benefits),
    coverage: flattenValue(coverage),

    deadline_display: deadlines.deadline_display || deadlines.deadline_date || null,
    deadline_date: deadlines.deadline_date || null,
    deadline_precision: deadlines.deadline_precision || 'unknown',

    eligibility_summary: flattenValue(eligibility.citizenship?.residence_requirement || data.practical_guidance?.eligibility_summary),
    eligibility: flattenValue(eligibility),
    documents: flattenValue(data.documents?.universal_documents || data.documents),
    requirements: flattenValue(data.selection?.criteria || data.application?.application_steps),

    image_url: image.url || null,
    image_source_url: image.source_url || (officialSources[0] && officialSources[0].url) || null,
    image_source_type: image.source_type || null,
    image_kind: image.source_type === 'official_provider' || image.source_type === 'official_logo' ? 'official_logo' : 'unknown',
    image_alt_text: image.alt_text || data.title || '',

    application_link: application.official_application_url || (officialSources[0] && officialSources[0].url) || null,
    status: deadlines.status || 'unknown',
    verification_status: data.verification?.verification_status || 'pending',
    last_verified_at: data.verification?.last_verified_date || entry.researched_at || null,
    last_verified_date: data.verification?.last_verified_date || null,
    match_score: data.match_score ?? data.analytics_and_statistics?.fit_score ?? null,

    notes: flattenValue(data.practical_guidance?.risk_summary?.flags?.join('; ') || data.research_notes?.join('; ')),
    duration: data.academic_profile?.duration?.duration_years ? `${data.academic_profile.duration.duration_years} years` : (data.academic_profile?.duration?.display || null),
    english_requirement: eligibility.language?.required ? 'Required' : (eligibility.language?.teaching_language?.join(', ') || null),

    official_sources: officialSources,
    change_log: data.change_log || [],
    data_quality: data.data_quality || {},

    _research_source: entry.source_file || 'premium_card_research',
    _researched_at: entry.researched_at || null,
  }
}

export async function loadPremiumScholarships() {
  const entries = await fetchResearchEntries()
  return entries.map(mapResearchToFlatCard)
}

export function getPremiumResearchStats() {
  const entries = cachedResearch || []
  const mapped = entries.map(mapResearchToFlatCard)
  return {
    total: mapped.length,
    withLogo: mapped.filter((s) => s.image_url).length,
    verified: mapped.filter((s) => s.verification_status === 'active').length,
    fullyFunded: mapped.filter((s) => s.fully_funded === true).length,
  }
}
