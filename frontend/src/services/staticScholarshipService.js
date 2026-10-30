/* ═══════════════════════════════════════════════════════════════════
   Static scholarship service — the API-independent catalogue

   What it is for
   --------------
   The live directory is served by a database-backed API. When that API is
   unreachable — a database quota, an outage, a maintenance window — the
   catalogue used to disappear with it: a visitor saw an empty page and no
   explanation, which reads as "this product has no scholarships in it".

   This service reads a version-controlled JSON snapshot of the public
   catalogue instead. Public browsing keeps working. Features that need a
   database — saving, applying, the supervisor contact list — do not, and
   the application says so rather than pretending.

   The snapshot is built by backend/scripts/build_public_snapshot.py from
   the canonical public predicate, so what it contains and what the live
   directory shows are the same set of rows. It is deliberately not a
   second source of truth about who is visible; it is a transport for the
   same decision.

   Two contract rules this module enforces
   ---------------------------------------
   A snapshot body is validated before it is cached. A 200 whose body is
   an HTML error page, or a 200 with an empty records array, would
   otherwise be cached and then served to every later caller as an empty
   catalogue for the lifetime of the page.

   The path is derived from Vite's BASE_URL, not hardcoded. The GitHub
   Pages build serves from /ScholarZone/, where a hardcoded
   '/scholarships-snapshot.json' resolves to the wrong origin path and
   404s — which would make the fallback the very thing that is broken.
   ═══════════════════════════════════════════════════════════════════ */

let cachedSnapshot = null
let snapshotLoadPromise = null

/** The snapshot asset URL, resolved against the deployment's base path. */
export function getSnapshotUrl() {
  const baseUrl =
    typeof import.meta !== 'undefined' && import.meta.env
      ? import.meta.env.BASE_URL
      : undefined

  if (typeof baseUrl !== 'string' || baseUrl === '') {
    return '/scholarships-snapshot.json'
  }

  return `${baseUrl.replace(/\/+$/, '')}/scholarships-snapshot.json`
}

/** Reject a body that cannot serve as a catalogue. */
export function assertSnapshotShape(payload) {
  if (payload === null || typeof payload !== 'object' || Array.isArray(payload)) {
    throw new Error('Snapshot payload is not an object.')
  }

  if (!Array.isArray(payload.scholarships)) {
    throw new Error('Snapshot payload has no scholarships array.')
  }

  // An empty array is a valid JSON answer and an invalid catalogue. It is
  // rejected so it cannot be cached and then reported as "no results"
  // for the lifetime of the page.
  if (payload.scholarships.length === 0) {
    throw new Error('Snapshot payload contains no scholarships.')
  }

  return payload
}

/** Load the snapshot, once. */
export async function loadScholarshipSnapshot() {
  if (cachedSnapshot) {
    return cachedSnapshot
  }

  if (!snapshotLoadPromise) {
    snapshotLoadPromise = (async () => {
      try {
        const response = await fetch(getSnapshotUrl(), {
          headers: { Accept: 'application/json' },
        })
        if (!response.ok) {
          throw new Error(`Failed to load snapshot: ${response.status}`)
        }
        cachedSnapshot = assertSnapshotShape(await response.json())
        return cachedSnapshot
      } catch (error) {
        // Cleared so a later call can retry rather than re-reading a
        // rejected body forever.
        snapshotLoadPromise = null
        throw error
      }
    })()
  }

  return snapshotLoadPromise
}

/** The snapshot already loaded, or null. */
export function getCachedSnapshot() {
  return cachedSnapshot
}

export function clearSnapshotCache() {
  cachedSnapshot = null
  snapshotLoadPromise = null
}

/* ── The local read surface ───────────────────────────────────────────
   The live directory's query surface — filter, sort, page — implemented
   against the snapshot so the fallback is not a raw dump. It mirrors the
   API's semantics rather than inventing new ones: the same aspect
   matching for funding and degree, the same sorts, the same page size. */

const PAGE_SIZE = 12

const STATUS_LABELS = {
  open: 'Open',
  closed: 'Closed',
  upcoming: 'Upcoming',
}

function statusOf(record) {
  const today = new Date()
  const deadline = record.deadline_date ? new Date(record.deadline_date) : null

  if (record.status === 'closed') return { key: 'closed', label: STATUS_LABELS.closed, className: 'closed' }
  if (deadline && !Number.isNaN(deadline.getTime()) && deadline < today) {
    return { key: 'closed', label: STATUS_LABELS.closed, className: 'closed' }
  }
  if (deadline && !Number.isNaN(deadline.getTime())) {
    const days = Math.ceil((deadline - today) / (24 * 60 * 60 * 1000))
    if (days <= 60) return { key: 'closing-soon', label: `Closing in ${days}d`, className: 'closing-soon' }
  }
  if (record.status === 'upcoming') return { key: 'upcoming', label: STATUS_LABELS.upcoming, className: 'upcoming' }
  return { key: 'open', label: STATUS_LABELS.open, className: 'open' }
}

/** Extract deadline month (1-12) from a record, or null if not available. */
function getDeadlineMonth(record) {
  const dateStr = record.deadline_date || record.deadline
  if (!dateStr) return null
  const timestamp = Date.parse(dateStr)
  if (Number.isNaN(timestamp)) return null
  return new Date(timestamp).getMonth() + 1
}

/** Get status key from a record (open, closing-soon, closed, upcoming). */
function getStatusKey(record) {
  return statusOf(record).key
}

const DEGREE_WORDS = {
  bachelor: ['bachelor', 'undergraduate'],
  master: ['master'],
  phd: ['phd', 'ph.d', 'doctoral', 'doctorate'],
  postgraduate: ['master', 'phd', 'postgraduate'],
}

const FUNDING_ASPECTS = {
  'fully funded': { include: ['fully funded', 'fully-funded', 'full funding', 'full scholarship', 'full sponsorship'], exclude: ['partially', 'partial to full', 'various'] },
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

function matchesDegree(label, value) {
  if (!value || value === 'All') return true
  const words = DEGREE_WORDS[filterKey(value)]
  const haystack = typeof label === 'string' ? label.toLowerCase() : ''
  if (words) return words.some((word) => haystack.includes(word))
  return haystack === String(value).toLowerCase()
}

function matchesFunding(label, value) {
  if (!value || value === 'All') return true
  const haystack = typeof label === 'string' ? label.toLowerCase() : ''
  const aspects = FUNDING_ASPECTS[filterKey(value)]
  if (aspects) {
    if (aspects.exclude.some((word) => haystack.includes(word))) return false
    return aspects.include.some((word) => haystack.includes(word))
  }
  return haystack === String(value).toLowerCase()
}

function sortRecords(records, sortBy) {
  const sorted = [...records]
  switch (sortBy) {
    case 'recommended': {
      // Rank by verification status (active first), then by status order
      const STATUS_ORDER = { open: 0, 'closing-soon': 1, closed: 2, upcoming: 3 }
      return sorted.sort((a, b) => {
        const aVerified = a.verification_status === 'active' ? 1 : 0
        const bVerified = b.verification_status === 'active' ? 1 : 0
        if (bVerified !== aVerified) return bVerified - aVerified
        const aStatus = getStatusKey(a)
        const bStatus = getStatusKey(b)
        return (STATUS_ORDER[aStatus] ?? 99) - (STATUS_ORDER[bStatus] ?? 99)
      })
    }
    case 'recently-added':
    case 'recently-updated':
      return sorted.sort((a, b) => {
        const left = a.updated_at ? new Date(a.updated_at).getTime() : -Infinity
        const right = b.updated_at ? new Date(b.updated_at).getTime() : -Infinity
        return right - left
      })
    case 'deadline-soon':
    case 'deadline-earliest':
      return sorted.sort((a, b) => {
        const left = a.deadline_date ? new Date(a.deadline_date).getTime() : Infinity
        const right = b.deadline_date ? new Date(b.deadline_date).getTime() : Infinity
        return left - right
      })
    case 'deadline-latest':
      return sorted.sort((a, b) => {
        const left = a.deadline_date ? new Date(a.deadline_date).getTime() : -Infinity
        const right = b.deadline_date ? new Date(b.deadline_date).getTime() : -Infinity
        return right - left
      })
    case 'fully-funded':
      return sorted.sort((a, b) => Number(Boolean(b.fully_funded)) - Number(Boolean(a.fully_funded)))
    case 'name-asc':
      return sorted.sort((a, b) => a.title.localeCompare(b.title))
    case 'name-desc':
      return sorted.sort((a, b) => b.title.localeCompare(a.title))
    case 'az':
      // Legacy alias for name-asc
      return sorted.sort((a, b) => a.title.localeCompare(b.title))
    case 'deadline':
      // Legacy alias for deadline-earliest
      return sorted.sort((a, b) => {
        const left = a.deadline_date ? new Date(a.deadline_date).getTime() : Infinity
        const right = b.deadline_date ? new Date(b.deadline_date).getTime() : Infinity
        return left - right
      })
    default:
      // Default: recently updated (most recent first)
      return sorted.sort((a, b) => {
        const left = a.updated_at ? new Date(a.updated_at).getTime() : -Infinity
        const right = b.updated_at ? new Date(b.updated_at).getTime() : -Infinity
        return right - left
      })
  }
}

/** Normalise a snapshot record into the shape the components expect. */
export function toScholarship(record) {
  return {
    id: record.id,
    title: record.title || record.name,
    country: record.country,
    degree: record.degree,
    funding: record.funding,
    description: record.description,
    deadline: record.deadline || record.deadline_display,
    deadline_date: record.deadline_date,
    deadline_precision: record.deadline_precision,
    status: record.status,
    verification_status: record.verification_status,
    verified: record.verification_status === 'active',
    is_verified: record.verification_status === 'active',
    last_verified_at: record.last_verified_at,
    last_verified_date: record.last_verified_date,
    official_source: record.official_source,
    official_source_url: record.official_source_url,
    application_link: record.application_link,
    image_url: record.image_url,
    image_source_url: record.image_source_url,
    image_source_type: record.image_source_type,
    image_kind: record.image_kind,
    image_verified_at: record.image_verified_at,
    image_alt_text: record.image_alt_text,
    eligibility: record.eligibility,
    benefits: record.benefits,
    coverage: record.coverage,
    requirements: record.requirements,
    documents: record.documents,
    region: record.region,
    duration: record.duration,
    application_period: record.application_period,
    catalogue_url: record.catalogue_url,
    official_updates_url: record.official_updates_url,
    selection_notes: record.selection_notes,
    program_type: record.program_type,
    fully_funded: record.fully_funded,
    funding_amount: record.funding_amount,
    funding_currency: record.funding_currency,
    funding_period: record.funding_period,
    tuition_coverage: record.tuition_coverage,
    living_cost_coverage: record.living_cost_coverage,
    travel_coverage: record.travel_coverage,
    eligibility_summary: record.eligibility_summary,
    english_requirement: record.english_requirement,
    application_method: record.application_method,
    best_fit: record.best_fit,
    notes: record.notes,
    next_verification_due: record.next_verification_due,
    updated_at: record.updated_at,
    // Academic eligibility
    departments: record.departments,
    eligible_fields: record.eligible_fields,
    eligible_programmes: record.eligible_programmes,
    academic_provenance: record.academic_provenance,
    // Derived by the same rule the live directory uses, so a card in the
    // fallback reads exactly like a card served by the API.
    statusInfo: statusOf(record),
  }
}

/**
 * Read the catalogue from the snapshot with the live directory's query
 * semantics. Returns the same paginated envelope the API returns, so a
 * caller can swap between them without a branch.
 */
export async function fetchScholarshipsFromSnapshot(query = {}) {
  const snapshot = await loadScholarshipSnapshot()
  const {
    search = '',
    country = 'All',
    degree = 'All',
    funding = 'All',
    deadline_month = 'All',
    status = 'All',
    sort = 'default',
    page = 1,
    limit = PAGE_SIZE,
  } = query

  let records = snapshot.scholarships.map(toScholarship)

  const needle = String(search).trim().toLowerCase()
  if (needle) {
    records = records.filter((record) =>
      [record.title, record.country, record.degree, record.description, record.funding]
        .filter(Boolean)
        .some((field) => field.toLowerCase().includes(needle))
    )
  }

  if (country && country !== 'All') {
    records = records.filter((record) => record.country === country)
  }
  if (degree && degree !== 'All') {
    records = records.filter((record) => matchesDegree(record.degree, degree))
  }
  if (funding && funding !== 'All') {
    records = records.filter((record) => matchesFunding(record.funding, funding))
  }
  if (deadline_month && deadline_month !== 'All') {
    const targetMonth = Number(deadline_month)
    records = records.filter((record) => getDeadlineMonth(record) === targetMonth)
  }
  if (status && status !== 'All') {
    records = records.filter((record) => getStatusKey(record) === status)
  }

  records = sortRecords(records, sort)

  const total = records.length
  const start = (Math.max(1, Number(page) || 1) - 1) * Number(limit || PAGE_SIZE)
  const items = records.slice(start, start + Number(limit || PAGE_SIZE))

  return {
    items,
    pagination: {
      page: Number(page) || 1,
      limit: Number(limit) || PAGE_SIZE,
      total,
      total_pages: Math.max(1, Math.ceil(total / (Number(limit) || PAGE_SIZE))),
    },
  }
}

/** The snapshot's headline figures, for the home page's live indicator. */
export async function fetchScholarshipStatsFromSnapshot() {
  const snapshot = await loadScholarshipSnapshot()
  const stats = snapshot.stats || {}
  const records = snapshot.scholarships
  const fullyFunded = records.filter(
    (record) => record.fully_funded === true || record.funding_type === 'Fully Funded'
  ).length
  const verified = records.filter(
    (record) => record.verification_status === 'active'
  ).length

  return {
    total: stats.total ?? records.length,
    countries: stats.countries ?? 0,
    fullyFunded: stats.fully_funded ?? fullyFunded,
    verified: stats.verified_active ?? verified,
  }
}

/**
 * Look up a single scholarship by ID from the snapshot.
 * Returns the normalized record or null if not found.
 */
export async function fetchScholarshipByIdFromSnapshot(id) {
  const snapshot = await loadScholarshipSnapshot()
  const record = snapshot.scholarships.find((s) => String(s.id) === String(id))
  if (!record) return null
  return toScholarship(record)
}
