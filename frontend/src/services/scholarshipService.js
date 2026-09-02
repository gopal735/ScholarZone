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

export async function fetchScholarships(query = {}, options) {
  const payload = await request('/scholarships', query, options)
  return {
    items: Array.isArray(payload.items) ? payload.items.map(normalizeScholarship) : [],
    pagination: payload.pagination,
  }
}

export async function fetchScholarshipById(id, options) {
  const payload = await request(`/scholarships/${encodeURIComponent(id)}`, undefined, options)
  return normalizeScholarship(payload)
}
