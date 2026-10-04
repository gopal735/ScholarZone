/**
 * The student dashboard's API client.
 *
 * One request per page load, not one per section. The backend already returns
 * every section together, because a dashboard whose sections were fetched
 * separately could disagree with each other: a shortlist that loaded before a
 * save would show a stale count next to a fresh list.
 *
 * Nothing here computes a number. No total is summed, no fit score is derived,
 * no deadline is counted down and no verification label is chosen - those all
 * arrive from the server, which took them from the matching engine and the
 * verification contract. Anything this module did arithmetic on would be a
 * second, unchecked implementation of a rule that already exists.
 */

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

export class DashboardApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'DashboardApiError'
    this.status = status
  }
}

/** Raised when the session is gone, so a view can send the student to sign in. */
export class DashboardUnauthenticatedError extends DashboardApiError {
  constructor(message) {
    super(message, 401)
    this.name = 'DashboardUnauthenticatedError'
  }
}

async function readError(response, fallback) {
  try {
    const payload = await response.json()
    if (typeof payload.detail === 'string') {
      return payload.detail
    }
  } catch {
    // Fall through to the generic message.
  }
  return fallback
}

async function request(path, options = {}) {
  let response
  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      ...options,
      credentials: 'include',
      headers: {
        Accept: 'application/json',
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...(options.headers || {}),
      },
    })
  } catch {
    throw new DashboardApiError('We could not reach ScholarZone. Please try again.', 0)
  }

  if (response.status === 401) {
    throw new DashboardUnauthenticatedError(await readError(response, 'Sign in to continue.'))
  }

  if (!response.ok) {
    throw new DashboardApiError(await readError(response, 'Something went wrong.'), response.status)
  }

  if (response.status === 204) {
    return null
  }

  return response.json()
}

/**
 * The whole dashboard in one call.
 *
 * Concurrent callers share one in-flight request rather than each issuing their
 * own, and the shared promise is dropped as soon as it settles so a later caller
 * always gets fresh data. Nothing is cached between page loads, so freshness is
 * exactly what it was before this existed.
 */
let inFlightDashboard = null

export function fetchDashboard({ asOf, signal } = {}) {
  if (inFlightDashboard) {
    return raceAbort(inFlightDashboard, signal)
  }

  const query = asOf ? `?as_of=${encodeURIComponent(asOf)}` : ''
  inFlightDashboard = request(`/dashboard${query}`).finally(() => {
    inFlightDashboard = null
  })

  return raceAbort(inFlightDashboard, signal)
}

/**
 * Race a shared request against the caller's own abort.
 *
 * The abort is deliberately not forwarded into the shared fetch: an unmounting
 * component must not cancel data another part of the page is still reading.
 */
function raceAbort(promise, signal) {
  if (!signal) {
    return promise
  }
  if (signal.aborted) {
    return Promise.reject(new DOMException('Aborted', 'AbortError'))
  }
  return Promise.race([
    promise,
    new Promise((_, reject) => {
      signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), {
        once: true,
      })
    }),
  ])
}

export function saveScholarship(scholarshipId) {
  return request(`/dashboard/saved?scholarship_id=${encodeURIComponent(scholarshipId)}`, {
    method: 'POST',
  })
}

export function removeSavedScholarship(scholarshipId) {
  return request(`/dashboard/saved/${encodeURIComponent(scholarshipId)}`, { method: 'DELETE' })
}

export function setApplicationState(scholarshipId, state) {
  return request(`/dashboard/applications/${encodeURIComponent(scholarshipId)}`, {
    method: 'PUT',
    body: JSON.stringify({ state }),
  })
}

export function saveProfile(profile) {
  return request('/dashboard/profile', {
    method: 'PUT',
    body: JSON.stringify({ profile }),
  })
}