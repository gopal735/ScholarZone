import { classifyLifecycle, LIFECYCLE } from './lifecycle'

const statusMetadata = {
  open: { label: 'Open', className: 'open' },
  'closing-soon': { label: 'Closing soon', className: 'closing-soon' },
  closed: { label: 'Closed', className: 'closed' },
  opening: { label: 'Opening soon', className: 'opening' },
  upcoming: { label: 'Upcoming', className: 'upcoming' },
  unknown: { label: 'Check deadline', className: 'unknown' },
}

export function getScholarshipStatus(scholarship) {
  const lifecycle = classifyLifecycle(scholarship)
  const status = lifecycle.status.replace('_', '-')
  return statusMetadata[status] || statusMetadata[LIFECYCLE.UNKNOWN]
}

export function getDeadlineLabel(scholarship) {
  return scholarship.deadline || scholarship.deadline_date || 'Not listed; check official source'
}

export function getLastVerifiedLabel(value) {
  if (!value) {
    return 'Verification date pending'
  }

  const verifiedDate = new Date(`${value}T00:00:00`)
  if (Number.isNaN(verifiedDate.getTime())) {
    return 'Verification date pending'
  }

  return `Verified ${new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' }).format(verifiedDate)}`
}

/* ── Filter matching ─────────────────────────────────────────────────
   The catalogue stores free-text labels: 96 distinct funding spellings
   and a dozen degree spellings. A filter is a question, not a stored
   string, so both the API and the local fallback match the aspect the
   filter asks about rather than comparing verbatim. "Master" matches
   "Master's, PhD"; "Tuition Fee Waiver" matches "Tuition + stipend";
   "Fully Funded" refuses a label that says "partially".

   These tables mirror app/services/taxonomy.py in the backend. The two
   must agree, or the same filter selects different rows depending on
   whether the API answered or the fallback did. */

const DEGREE_FILTER_WORDS = {
  bachelor: ['bachelor', 'undergraduate'],
  undergraduate: ['bachelor', 'undergraduate'],
  master: ['master'],
  phd: ['phd', 'ph.d', 'doctoral', 'doctorate'],
  doctoral: ['phd', 'ph.d', 'doctoral', 'doctorate'],
  postgraduate: ['master', 'phd', 'postgraduate'],
  postdoc: ['postdoctoral', 'post-doc'],
}

const FUNDING_LABEL_ALIASES = {
  'tuition waiver': 'tuition fee waiver',
  'partial funding': 'partially funded',
  partial: 'partially funded',
}

const FUNDING_FILTER_ASPECTS = {
  'fully funded': {
    include: ['fully funded', 'fully-funded', 'full funding', 'full scholarship', 'full sponsorship', 'full study funding'],
    exclude: ['partially', 'partial to full', 'various'],
  },
  'partially funded': { include: ['partial'], exclude: [] },
  'tuition fee waiver': { include: ['tuition', 'fee'], exclude: [] },
  stipend: { include: ['stipend', 'stipendium', 'salary', 'fellowship'], exclude: [] },
  'research funding': { include: ['research'], exclude: [] },
  'need based': { include: ['need'], exclude: [] },
}

function filterKey(value) {
  if (typeof value !== 'string') return null
  const key = value.trim().toLowerCase().replace(/['’]/g, '').replace(/[-/]/g, ' ')
  const normalised = key.split(/\s+/).filter(Boolean).join(' ')
  if (!normalised || normalised === 'all') return null
  return normalised.endsWith('s') && !normalised.endsWith('ss')
    ? normalised.slice(0, -1)
    : normalised
}

export function matchesDegreeFilter(label, value) {
  if (value === 'All' || value === undefined || value === null) return true
  const words = DEGREE_FILTER_WORDS[filterKey(value)]
  const haystack = typeof label === 'string' ? label.toLowerCase() : ''
  if (words) {
    return words.some((word) => haystack.includes(word))
  }
  return haystack === String(value).toLowerCase()
}

export function matchesFundingFilter(label, value, fullyFunded) {
  if (value === 'All' || value === undefined || value === null) return true
  const key = filterKey(value)
  const aspects = FUNDING_FILTER_ASPECTS[key] || FUNDING_FILTER_ASPECTS[filterKey(FUNDING_LABEL_ALIASES[String(value).toLowerCase().trim()] ?? '') || '']
  
  // Special handling for "Fully Funded" filter: respect the tri-state fully_funded field
  // fully_funded: true = confirmed, false = explicitly not, null = unknown
  if (key === 'fully funded') {
    if (fullyFunded === true) return true
    if (fullyFunded === false) return false
    // If fully_funded is null/undefined, fall back to text matching
  }
  
  if (aspects) {
    const haystack = typeof label === 'string' ? label.toLowerCase() : ''
    if (aspects.exclude.some((word) => haystack.includes(word))) return false
    return aspects.include.some((word) => haystack.includes(word))
  }
  return typeof label === 'string' ? label.toLowerCase() === String(value).toLowerCase() : false
}
