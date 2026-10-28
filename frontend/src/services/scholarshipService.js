const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

/**
 * Static-first mode: when true, the version-controlled snapshot is the
 * primary source for public catalogue reads. The API is not called at all.
 *
 * This is controlled by VITE_STATIC_CATALOGUE=true at build time, or by
 * setting localStorage.scholarzone.staticCatalogue = 'true' at runtime.
 * When the snapshot loads successfully, public browsing never needs the
 * database. A distinct "static mode" indicator is shown instead of the
 * degraded "fallback" notice.
 */
const STATIC_CATALOGUE =
  import.meta.env.VITE_STATIC_CATALOGUE === 'true' ||
  (typeof window !== 'undefined' && window.localStorage.getItem('scholarzone.staticCatalogue') === 'true')

// The API-independent catalogue. Imported here so the static source is a
// property of this service rather than something each page has to remember
// to do: a caller that asks for scholarships gets scholarships, and the
// provenance travels with the result.
import {
  fetchScholarshipsFromSnapshot,
  fetchScholarshipStatsFromSnapshot,
} from './staticScholarshipService'

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

export async function fetchScholarships(query = {}, options) {
  // Static-first: when enabled, the snapshot is the primary source.
  // The API is not called at all for public catalogue reads.
  if (STATIC_CATALOGUE) {
    const key = `list:${JSON.stringify(query, Object.keys(query).sort())}`
    const send = () => fetchScholarshipsFromSnapshot(query).then((fallback) => ({
      ...fallback,
      fromSnapshot: true,
      staticMode: true,
    }))
    return dedupe(key, send, options?.signal)
  }

  // The key is the resolved query, so two callers asking for the same page
  // share a request and two callers asking for different pages do not.
  const key = `list:${JSON.stringify(query, Object.keys(query).sort())}`
  const send = () =>
    request('/scholarships', query)
      .then((payload) => ({
        items: Array.isArray(payload.items) ? payload.items.map(normalizeScholarship) : [],
        pagination: payload.pagination,
      }))
      // The API is the source of truth. When it cannot answer at all, the
      // catalogue is still readable from the version-controlled snapshot,
      // so browsing does not stop just because the database is —
      // and the caller is told it is reading the snapshot, because a
      // directory that quietly changes its provenance is worse than one
      // that announces it.
      .catch(async (error) => {
        const fallback = await fetchScholarshipsFromSnapshot(query)
        if (!fallback || fallback.items.length === 0) throw error
        return { ...fallback, fromSnapshot: true }
      })

  return dedupe(key, send, options?.signal)
}

export async function fetchScholarshipById(id, options) {
  // Static-first: try snapshot first for detail pages too.
  if (STATIC_CATALOGUE) {
    const snapshot = await fetchScholarshipsFromSnapshot({ limit: 1000 })
    const record = snapshot.items.find((s) => String(s.id) === String(id))
    if (record) return normalizeScholarship(record)
    // If not in snapshot, fall through to API (will 404 if also not there)
  }
  const payload = await request(`/scholarships/${encodeURIComponent(id)}`, undefined, options)
  return normalizeScholarship(payload)
}

export async function fetchScholarshipStats(options) {
  if (STATIC_CATALOGUE) {
    return dedupe('stats', async () => {
      const fallback = await fetchScholarshipStatsFromSnapshot()
      if (!fallback || fallback.total === 0) throw new Error('Empty snapshot stats')
      return { ...fallback, fromSnapshot: true, staticMode: true }
    }, options?.signal)
  }

  return dedupe('stats', async () => {
    try {
      return await request('/scholarships/stats')
    } catch (error) {
      const fallback = await fetchScholarshipStatsFromSnapshot()
      if (!fallback || fallback.total === 0) throw error
      return { ...fallback, fromSnapshot: true }
    }
  }, options?.signal)
}

/**
 * Enable or disable static-first catalogue mode at runtime.
 * Persists to localStorage so the preference survives page loads.
 * When enabled, public browsing uses the version-controlled snapshot
 * exclusively and never calls the database-backed API.
 */
export function setStaticCatalogueMode(enabled) {
  if (typeof window !== 'undefined') {
    if (enabled) {
      window.localStorage.setItem('scholarzone.staticCatalogue', 'true')
    } else {
      window.localStorage.removeItem('scholarzone.staticCatalogue')
    }
  }
}

/**
 * Check if static-first catalogue mode is currently active.
 */
export function isStaticCatalogueMode() {
  return STATIC_CATALOGUE
}
