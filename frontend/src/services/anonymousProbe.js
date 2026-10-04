/**
 * Probes that must be genuinely anonymous.
 *
 * A previous release check reported "the protected endpoint is not refusing
 * anonymous callers" when the caller was in fact signed in: the test registered
 * a user first, the session cookie was attached to the next request, and the
 * 200 that followed looked like a missing auth guard.
 *
 * Every anonymous probe therefore goes through here, which pins
 * `credentials: 'omit'` so no cookie can travel with the request regardless of
 * what the session currently holds.
 */

const ANON_CREDENTIALS = 'omit'

/**
 * Fetch JSON without ever sending credentials.
 *
 * @param {string} path   path beginning with '/'
 * @param {RequestInit} [options]
 * @returns {Promise<{status: number, body: any}>}
 */
export async function anonymousJson(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    credentials: ANON_CREDENTIALS,
  })
  const text = await response.text()
  let body
  try {
    body = text ? JSON.parse(text) : null
  } catch {
    body = text
  }
  return { status: response.status, body }
}

/**
 * POST JSON without ever sending credentials.
 *
 * @param {string} path
 * @param {unknown} payload
 * @param {RequestInit} [options]
 * @returns {Promise<{status: number, body: any}>}
 */
export async function anonymousPostJson(path, payload, options = {}) {
  return anonymousJson(path, {
    ...options,
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    body: JSON.stringify(payload),
  })
}

/** Statuses that mean "this surface correctly refused an anonymous caller". */
export function isRefused(status) {
  return status === 401 || status === 403
}