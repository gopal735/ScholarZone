const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

/**
 * The admin CRUD client. Every call carries the admin secret in the
 * X-Admin-Secret header, which is the repository's single administrator
 * authentication model; the server refuses the call without it (there is no
 * unauthenticated variant to fall back to).
 */
function adminRequest(path, { method = 'GET', body, adminSecret }) {
  if (!adminSecret) {
    return Promise.reject(new Error('Administrator authentication required.'))
  }
  return fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      'X-Admin-Secret': adminSecret,
    },
    body: body ? JSON.stringify(body) : undefined,
  }).then(async (response) => {
    const text = await response.text()
    const payload = text ? JSON.parse(text) : {}
    if (!response.ok) {
      const detail = payload?.detail
      const message =
        typeof detail === 'string' ? detail : detail?.message || 'The request was refused.'
      const error = new Error(message)
      error.blocked_by = detail?.blocked_by
      throw error
    }
    return payload
  })
}

export function fetchScholarshipList(adminSecret, params = {}) {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') query.set(key, String(value))
  }
  const suffix = query.toString() ? `?${query}` : ''
  return adminRequest(`/admin/scholarships${suffix}`, { adminSecret })
}

export function fetchScholarship(adminSecret, id) {
  return adminRequest(`/admin/scholarships/${id}`, { adminSecret })
}

export function createScholarship(adminSecret, payload) {
  return adminRequest('/admin/scholarships', { method: 'POST', body: payload, adminSecret })
}

export function updateScholarship(adminSecret, id, payload) {
  return adminRequest(`/admin/scholarships/${id}`, { method: 'PATCH', body: payload, adminSecret })
}

export function archiveScholarship(adminSecret, id, reason) {
  return adminRequest(`/admin/scholarships/${id}/archive`, { method: 'POST', body: { reason }, adminSecret })
}

export function deleteScholarship(adminSecret, id, confirm, reason) {
  return adminRequest(`/admin/scholarships/${id}`, { method: 'DELETE', body: { confirm, reason }, adminSecret })
}

export function fetchScholarshipAudit(adminSecret, id) {
  return adminRequest(`/admin/scholarships/${id}/audit`, { adminSecret })
}

/**
 * The fields an administrator may set, in the order the form shows them.
 * This mirrors the server's whitelist: a key that is not here is refused
 * there with a 422 rather than silently ignored, which is the behaviour we
 * want, so the form and the server stay in step by construction.
 */
export const EDITABLE_FIELDS = [
  { key: 'title', label: 'Title', required: true },
  { key: 'country', label: 'Country', required: true },
  { key: 'degree', label: 'Degree level' },
  { key: 'best_fit', label: 'Best fit / field' },
  { key: 'program_type', label: 'Programme type' },
  { key: 'funding', label: 'Funding' },
  { key: 'funding_amount', label: 'Funding amount' },
  { key: 'funding_currency', label: 'Currency' },
  { key: 'funding_period', label: 'Funding period' },
  { key: 'deadline_date', label: 'Deadline date (YYYY-MM-DD)' },
  { key: 'deadline_display', label: 'Deadline display' },
  { key: 'status', label: 'Status (open / upcoming / closed)' },
  { key: 'official_source', label: 'Official source' },
  { key: 'official_source_url', label: 'Official source URL' },
  { key: 'tuition_coverage', label: 'Tuition coverage (true/false)' },
  { key: 'fully_funded', label: 'Fully funded (true/false)' },
]

export function emptyDraft() {
  const draft = {}
  for (const field of EDITABLE_FIELDS) {
    if (field.required) draft[field.key] = ''
  }
  return draft
}
