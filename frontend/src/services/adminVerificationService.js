/**
 * Admin Verification Center API client.
 *
 * The administrator secret is held in component state for the lifetime of the
 * session only. It is never written to localStorage or sessionStorage, never
 * placed in a URL, and never bundled: an XSS payload cannot read what the
 * browser was never given. Authorization is still decided by the server, which
 * rejects every request without the header regardless of what this file does.
 */

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

export class AdminVerificationError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'AdminVerificationError'
    this.status = status
  }
}

function adminRequest(path, { adminSecret, method = 'GET', body } = {}) {
  if (!adminSecret) {
    return Promise.reject(new AdminVerificationError('Administrator secret required.', 401))
  }
  return fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      'X-Admin-Secret': adminSecret,
      Accept: 'application/json',
      ...(body ? { 'Content-Type': 'application/json' } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  }).then(async (response) => {
    if (!response.ok) {
      let message = 'Request failed.'
      try {
        const payload = await response.json()
        if (typeof payload.detail === 'string') message = payload.detail
      } catch {
        /* non-JSON error body */
      }
      throw new AdminVerificationError(message, response.status)
    }
    return response.json()
  })
}

export function fetchSummary(adminSecret) {
  return adminRequest('/admin/verification/summary', { adminSecret })
}

export function fetchQueue(adminSecret, params = {}) {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    query.set(key, String(value))
  }
  const suffix = query.toString() ? `?${query}` : ''
  return adminRequest(`/admin/verification/queue${suffix}`, { adminSecret })
}

export function fetchDetail(adminSecret, id) {
  return adminRequest(`/admin/verification/scholarships/${id}`, { adminSecret })
}

export function submitDecision(adminSecret, id, payload) {
  return adminRequest(`/admin/verification/scholarships/${id}/decision`, {
    adminSecret,
    method: 'POST',
    body: payload,
  })
}