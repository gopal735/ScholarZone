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

import { classifyLifecycle, LIFECYCLE } from '../utils/lifecycle'

export async function fetchScholarshipsByLifecycle(query = {}, lifecycle = 'All', options) {
  const page = Number(query.page) || 1
  const limit = Number(query.limit) || 12
  const lifecycleForStatus = {
    open: LIFECYCLE.OPEN,
    'closing-soon': LIFECYCLE.CLOSING_SOON,
    closed: LIFECYCLE.CLOSED,
  }[query.status]
  const targetLifecycle = lifecycle === 'All' ? lifecycleForStatus || lifecycle : lifecycle

  if (lifecycle !== 'All' && lifecycleForStatus && lifecycle !== lifecycleForStatus) {
    return {
      items: [],
      pagination: { page, limit, total: 0, total_pages: 1 },
    }
  }

  if (!targetLifecycle || targetLifecycle === 'All') {
    return fetchScholarships(query, options)
  }

  const filters = { ...query }
  delete filters.page
  delete filters.limit
  delete filters.lifecycle
  const apiFilters = {
    ...filters,
    status: lifecycleForStatus ? undefined : filters.status,
  }
  const firstPage = await fetchScholarships({ ...apiFilters, page: 1, limit: 100 }, options)

  const totalPages = firstPage.pagination?.total_pages || 1
  const pageNumbers = Array.from({ length: Math.max(0, totalPages - 1) }, (_, index) => index + 2)

  const remainingPages = []
  const CONCURRENCY = 4
  for (let i = 0; i < pageNumbers.length; i += CONCURRENCY) {
    if (options?.signal?.aborted) break
    const chunk = pageNumbers.slice(i, i + CONCURRENCY)
    const chunkResults = await Promise.all(
      chunk.map((pageNumber) =>
        fetchScholarships({ ...apiFilters, page: pageNumber, limit: 100 }, options),
      ),
    )
    remainingPages.push(...chunkResults)
  }

  if (options?.signal?.aborted) {
    throw new DOMException('The operation was aborted.', 'AbortError')
  }

  const allItems = [firstPage, ...remainingPages].flatMap((result) => result.items)
  const seen = new Set()
  const uniqueItems = allItems.filter((item) => {
    const key = item?.id ?? item?.title
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
  const matches = uniqueItems.filter((scholarship) => classifyLifecycle(scholarship).status === targetLifecycle)
  const total = matches.length

  return {
    items: matches.slice((page - 1) * limit, page * limit),
    pagination: {
      page,
      limit,
      total,
      total_pages: Math.max(1, Math.ceil(total / limit)),
    },
  }
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
