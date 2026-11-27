const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

/**
 * The public scholarship catalogue is served exclusively by the live backend
 * API, which reads from the authoritative production database. There is no
 * static-first mode and no silent snapshot fallback: when the API cannot
 * answer, the caller receives an error and must render an unavailable state.
 */
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
    cache: 'no-store',
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

/* In-flight de-duplication (unchanged). */
const inFlight = new Map()

function dedupe(key, run, signal) {
  let requestPromise = inFlight.get(key)

  if (!requestPromise) {
    requestPromise = run()
    inFlight.set(key, requestPromise)

    const release = () => {
      if (inFlight.get(key) === requestPromise) {
        inFlight.delete(key)
      }
    }

    requestPromise.then(release, release)
  }

  if (!signal) {
    return requestPromise
  }

  return new Promise((resolve, reject) => {
    const onAbort = () => reject(new DOMException('The operation was aborted.', 'AbortError'))

    if (signal.aborted) {
      onAbort()
      return
    }

    signal.addEventListener('abort', onAbort, { once: true })
    requestPromise.then(
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
  const key = `list:${JSON.stringify(query, Object.keys(query).sort())}`
  const send = () =>
    request('/scholarships', query).then((payload) => ({
      items: Array.isArray(payload.items) ? payload.items.map(normalizeScholarship) : [],
      pagination: payload.pagination,
    }))

  return dedupe(key, send, options?.signal)
}

export async function fetchScholarshipsByLifecycle(query = {}, lifecycle = 'All', options) {
  const page = Number(query.page) || 1
  const limit = Number(query.limit) || 12
  const lifecycleForStatus = {
    open: 'open',
    'closing-soon': 'closing_soon',
    closed: 'closed',
  }[query.status]
  const targetLifecycle = lifecycle === 'All' ? (lifecycleForStatus || 'All') : lifecycle

  if (lifecycle !== 'All' && lifecycleForStatus && lifecycle !== lifecycleForStatus) {
    return {
      items: [],
      pagination: { page, limit, total: 0, total_pages: 1 },
    }
  }

  const filters = { ...query }
  const apiFilters = {
    ...filters,
    status: lifecycleForStatus ? undefined : filters.status,
  }
  if (targetLifecycle && targetLifecycle !== 'All') {
    apiFilters.lifecycle = targetLifecycle
  }
  apiFilters.page = page
  apiFilters.limit = limit
  delete apiFilters.lifecycleFilter

  return fetchScholarships(apiFilters, options)
}

export async function fetchScholarshipById(id, options) {
  const payload = await request(`/scholarships/${encodeURIComponent(id)}`, undefined, options)
  return normalizeScholarship(payload)
}

export async function fetchScholarshipStats(options) {
  return dedupe('stats', async () => {
    return await request('/scholarships/stats')
  }, options?.signal)
}

// Deprecated compatibility shims. Static catalogue mode no longer exists.
export function setStaticCatalogueMode() {
  // no-op: retained only for backwards compatibility with older callers.
}

export function isStaticCatalogueMode() {
  return false
}
