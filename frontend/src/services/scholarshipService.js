const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

export class ScholarshipApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ScholarshipApiError'
    this.status = status
  }
}

function normalizeScholarship(scholarship) {
  return {
    ...scholarship,
    // The API keeps the existing display text while also returning deadline_date
    // for any future date-aware UI.
    deadline: scholarship.deadline ?? scholarship.deadline_date ?? null,
  }
}

/**
 * Determines if an error should trigger the static snapshot fallback.
 * Fallback ONLY for:
 * - Network failures (TypeError, fetch aborted)
 * - HTTP 5xx server errors (500, 502, 503, 504)
 * NO fallback for 4xx client errors (400, 401, 403, 404, 422, etc.)
 */
function shouldFallbackToSnapshot(error) {
  // Network failures (offline, DNS, connection refused, etc.)
  if (error instanceof TypeError || error instanceof DOMException) {
    return true
  }
  // Our custom API error with status
  if (error instanceof ScholarshipApiError) {
    return error.status >= 500 && error.status < 600
  }
  return false
}

async function request(path, searchParams, { signal } = {}) {
  const url = new URL(`${apiBaseUrl}${path}`, window.location.origin)

  if (searchParams) {
    Object.entries(searchParams).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '' && value !== 'All') {
        url.searchParams.set(key, value)
      }
    })
  }

  const response = await fetch(url, {
    signal,
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) {
    let message = 'Unable to load scholarships right now.'
    try {
      const payload = await response.json()
      if (typeof payload.detail === 'string') {
        message = payload.detail
      }
    } catch {
      // A non-JSON failure should still surface a safe, useful error.
    }
    throw new ScholarshipApiError(message, response.status)
  }

  return response.json()
}

/* ── In-flight de-duplication ─────────────────────────────────────────
   Three call sites on the home page want the same first page of the
   catalogue at the same moment — HomePage's directory, ScholarZoneHero's
   directory, and the featured list — plus a stats call from both HomePage and
   ScholarZoneHero. Each went straight to fetch, so one home page load issued
   six identical directory requests and two identical stats requests.
   Measured over the wire, not inferred.

   This is not a cache and not a state library. It is one module-level map
   from request key to the promise already in flight for it, cleared the
   moment that promise settles. Concurrent callers share one request; a
   caller arriving after it settles gets a fresh one. Nothing is stored
   between page loads, so freshness is unchanged.

   A caller that brings its own AbortSignal still shares the request, but
   only ever cancels its own wait for it. Handing the caller's signal to
   fetch would let one component unmounting abort the data another component
   is still reading — which is precisely the case here, since the two
   directory callers mount together and unmount at different times. So the
   shared request runs signal-less and each caller races it against its own
   abort. */
const inFlight = new Map()

function dedupe(key, run, signal) {
  let request = inFlight.get(key)

  if (!request) {
    request = run()
    inFlight.set(key, request)

    const release = () => {
      if (inFlight.get(key) === request) {
        inFlight.delete(key)
      }
    }

    request.then(release, release)
  }

  if (!signal) {
    return request
  }

  return new Promise((resolve, reject) => {
    const onAbort = () => reject(new DOMException('The operation was aborted.', 'AbortError'))

    if (signal.aborted) {
      onAbort()
      return
    }

    signal.addEventListener('abort', onAbort, { once: true })
    request.then(
      (value) => {
        signal.removeEventListener('abort', onAbort)
        resolve(value)
      },
      (error) => {
        signal.removeEventListener('abort', onAbort)
        reject(error)
      },
    )
  })
}

/* ── Static snapshot fallback ──────────────────────────────────────────
   When the API is unavailable due to a server error (5xx) or network failure,
   we fall back to the version-controlled JSON snapshot. The snapshot contains
   all public scholarships (634 records) and stats, filtered by the canonical
   visibility predicate (excludes closed, archived, quarantined).
   
   CRITICAL: We do NOT fall back on 4xx errors (400, 401, 403, 404, 422).
   A stale snapshot must never resurrect a scholarship that the live API
   says is hidden, invalid, or unavailable.
   
   The snapshot is loaded once and cached in memory. Filtering, pagination,
   and sorting are performed client-side on the full dataset. */

import { loadScholarshipSnapshot } from './staticScholarshipService.js'

function filterScholarships(scholarships, query) {
  let filtered = [...scholarships]

  // Search filter
  if (query.search) {
    const search = query.search.toLowerCase()
    filtered = filtered.filter(s =>
      (s.title?.toLowerCase().includes(search)) ||
      (s.description?.toLowerCase().includes(search)) ||
      (s.country?.toLowerCase().includes(search)) ||
      (s.degree?.toLowerCase().includes(search)) ||
      (s.funding?.toLowerCase().includes(search))
    )
  }

  // Country filter
  if (query.country) {
    const country = query.country.toLowerCase()
    filtered = filtered.filter(s => s.country?.toLowerCase() === country)
  }

  // Degree filter
  if (query.degree) {
    const degree = query.degree.toLowerCase()
    filtered = filtered.filter(s => s.degree?.toLowerCase() === degree)
  }

  // Funding filter
  if (query.funding) {
    const funding = query.funding.toLowerCase()
    filtered = filtered.filter(s => s.funding?.toLowerCase() === funding)
  }

  // Deadline month filter
  if (query.deadline_month) {
    filtered = filtered.filter(s => {
      if (!s.deadline_date) return false
      const month = new Date(s.deadline_date).getMonth() + 1
      return month === query.deadline_month
    })
  }

  // Status filter
  if (query.status) {
    filtered = filtered.filter(s => s.status === query.status)
  }

  return filtered
}

function sortScholarships(scholarships, sort) {
  const sorted = [...scholarships]

  const nullDeadlineLast = (a, b) => {
    const aNull = !a.deadline_date
    const bNull = !b.deadline_date
    if (aNull && !bNull) return 1
    if (!aNull && bNull) return -1
    return 0
  }

  switch (sort) {
    case 'recommended':
      sorted.sort((a, b) => {
        // Verified first
        if (a.verified !== b.verified) return b.verified - a.verified
        // Status priority: open > closing-soon > others
        const statusOrder = { open: 0, 'closing-soon': 1 }
        const aStatus = statusOrder[a.status] ?? 2
        const bStatus = statusOrder[b.status] ?? 2
        if (aStatus !== bStatus) return aStatus - bStatus
        // Recently updated
        return new Date(b.updated_at) - new Date(a.updated_at)
      })
      break
    case 'recently-added':
      sorted.sort((a, b) => new Date(b.created_at || b.updated_at) - new Date(a.created_at || a.updated_at))
      break
    case 'recently-updated':
      sorted.sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at))
      break
    case 'deadline-soon':
      sorted.sort((a, b) => {
        const nullFirst = nullDeadlineLast(a, b)
        if (nullFirst !== 0) return nullFirst
        return new Date(a.deadline_date) - new Date(b.deadline_date)
      })
      break
    case 'fully-funded':
      sorted.sort((a, b) => {
        const aFully = a.funding?.toLowerCase().includes('fully funded') && !a.funding?.toLowerCase().includes('partial')
        const bFully = b.funding?.toLowerCase().includes('fully funded') && !b.funding?.toLowerCase().includes('partial')
        if (aFully !== bFully) return bFully - aFully
        return new Date(b.updated_at) - new Date(a.updated_at)
      })
      break
    case 'deadline-earliest':
      sorted.sort((a, b) => {
        const nullFirst = nullDeadlineLast(a, b)
        if (nullFirst !== 0) return nullFirst
        return new Date(a.deadline_date) - new Date(b.deadline_date)
      })
      break
    case 'deadline-latest':
      sorted.sort((a, b) => {
        const nullFirst = nullDeadlineLast(a, b)
        if (nullFirst !== 0) return nullFirst
        return new Date(b.deadline_date) - new Date(a.deadline_date)
      })
      break
    case 'name-asc':
      sorted.sort((a, b) => a.title.localeCompare(b.title))
      break
    case 'name-desc':
      sorted.sort((a, b) => b.title.localeCompare(a.title))
      break
    default:
      // default = recommended
      sorted.sort((a, b) => {
        if (a.verified !== b.verified) return b.verified - a.verified
        const statusOrder = { open: 0, 'closing-soon': 1 }
        const aStatus = statusOrder[a.status] ?? 2
        const bStatus = statusOrder[b.status] ?? 2
        if (aStatus !== bStatus) return aStatus - bStatus
        return new Date(b.updated_at) - new Date(a.updated_at)
      })
  }

  return sorted
}

function paginate(scholarships, page, limit) {
  const total = scholarships.length
  const total_pages = Math.ceil(total / limit) || 0
  const offset = (page - 1) * limit
  const items = scholarships.slice(offset, offset + limit)
  return { items, pagination: { page, limit, total, total_pages } }
}

async function tryApiThenSnapshot(key, send, fallbackFn, options) {
  try {
    return await dedupe(key, send, options?.signal)
  } catch (apiError) {
    if (!shouldFallbackToSnapshot(apiError)) {
      throw apiError
    }
    // Fall back to static snapshot for 5xx or network failures
    console.warn('API unavailable (5xx/network), falling back to static snapshot:', apiError.message)
    return await fallbackFn()
  }
}

export async function fetchScholarships(query = {}, options) {
  const key = `list:${JSON.stringify(query, Object.keys(query).sort())}`
  
  // Try API first
  const send = () =>
    request('/scholarships', query).then((payload) => ({
      items: Array.isArray(payload.items) ? payload.items.map(normalizeScholarship) : [],
      pagination: payload.pagination,
      source: 'api',
    }))

  const fallbackFn = async () => {
    const snapshot = await loadScholarshipSnapshot()
    const allScholarships = snapshot.scholarships || []
    
    let filtered = filterScholarships(allScholarships, query)
    filtered = sortScholarships(filtered, query.sort || 'default')
    const result = paginate(filtered, query.page || 1, query.limit || 12)
    
    return {
      items: result.items.map(normalizeScholarship),
      pagination: result.pagination,
      source: 'snapshot',
      snapshot_meta: snapshot.meta,
    }
  }

  return tryApiThenSnapshot(key, send, fallbackFn, options)
}

export async function fetchScholarshipById(id, options) {
  const key = `detail:${id}`
  
  const send = () =>
    request(`/scholarships/${encodeURIComponent(id)}`, undefined, options)
      .then(normalizeScholarship)

  const fallbackFn = async () => {
    const snapshot = await loadScholarshipSnapshot()
    const scholarship = (snapshot.scholarships || []).find(s => s.id === id)
    
    // CRITICAL: A stale snapshot must never resurrect a scholarship
    // that the live API says is hidden or unavailable.
    // If the API returned 404, we don't fall back - we propagate the 404.
    // This fallback only runs for 5xx/network errors, so by definition
    // the live API couldn't give us a definitive 404.
    if (!scholarship) {
      throw new ScholarshipApiError('Scholarship not found in snapshot', 404)
    }
    
    return normalizeScholarship({ ...scholarship, _source: 'snapshot' })
  }

  return tryApiThenSnapshot(key, send, fallbackFn, options)
}

export async function fetchScholarshipStats(options) {
  const key = 'stats'
  
  const send = () =>
    request('/scholarships/stats', undefined, options)

  const fallbackFn = async () => {
    const snapshot = await loadScholarshipSnapshot()
    return {
      ...snapshot.stats,
      source: 'snapshot',
      snapshot_meta: snapshot.meta,
    }
  }

  return tryApiThenSnapshot(key, send, fallbackFn, options)
}