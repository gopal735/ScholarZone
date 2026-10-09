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
   When the API is unavailable (e.g., database quota exceeded), we fall back
   to the version-controlled JSON snapshot. The snapshot contains all public
   scholarships (634 records) and stats, filtered by the canonical visibility
   predicate (excludes closed, archived, quarantined).
   
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

export async function fetchScholarships(query = {}, options) {
  const key = `list:${JSON.stringify(query, Object.keys(query).sort())}`
  
  // Try API first
  const send = () =>
    request('/scholarships', query).then((payload) => ({
      items: Array.isArray(payload.items) ? payload.items.map(normalizeScholarship) : [],
      pagination: payload.pagination,
      source: 'api',
    }))

  try {
    return await dedupe(key, send, options?.signal)
  } catch (apiError) {
    // Fall back to static snapshot
    console.warn('API unavailable, falling back to static snapshot:', apiError.message)
    
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
}

export async function fetchScholarshipById(id, options) {
  try {
    const payload = await request(`/scholarships/${encodeURIComponent(id)}`, undefined, options)
    return normalizeScholarship(payload)
  } catch (apiError) {
    // Fall back to static snapshot
    console.warn('API unavailable, falling back to static snapshot for detail:', apiError.message)
    
    const snapshot = await loadScholarshipSnapshot()
    const scholarship = (snapshot.scholarships || []).find(s => s.id === id)
    
    if (!scholarship) {
      throw new ScholarshipApiError('Scholarship not found', 404)
    }
    
    return normalizeScholarship({ ...scholarship, _source: 'snapshot' })
  }
}

export async function fetchScholarshipStats(options) {
  try {
    return await dedupe('stats', () => request('/scholarships/stats'), options?.signal)
  } catch (apiError) {
    // Fall back to static snapshot
    console.warn('API unavailable, falling back to static snapshot for stats:', apiError.message)
    
    const snapshot = await loadScholarshipSnapshot()
    return {
      ...snapshot.stats,
      source: 'snapshot',
      snapshot_meta: snapshot.meta,
    }
  }
}