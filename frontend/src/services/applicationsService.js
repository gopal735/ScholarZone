/**
 * The Application Workspace API client.
 *
 * Two things are enforced here rather than in the components, because they are
 * protocol rules and one place is easier to keep honest than six.
 *
 * **Version travels with every write.** Each mutation carries the
 * `expected_version` it was built from. A 409 is therefore a real answer about
 * someone else having edited the same application, not something a component
 * has to reconstruct. The client never retries a write on its own: a silent
 * retry is how a lost update turns into a duplicate one.
 *
 * **Failures are distinguishable.** Authentication, missing resource, conflict,
 * validation and transient server failure are separate classes, because the
 * interface responds differently to each - a conflict offers a reload, a missing
 * resource removes the view, and a network blip offers a retry.
 */

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

export class ApplicationApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApplicationApiError'
    this.status = status
  }
}

/** The session is gone. The workspace cannot render anything private. */
export class ApplicationUnauthenticatedError extends ApplicationApiError {
  constructor(message) {
    super(message, 401)
    this.name = 'ApplicationUnauthenticatedError'
  }
}

/** Someone else changed this application. Presenting new data without warning
 *  would silently discard the edit the reader was making. */
export class ApplicationConflictError extends ApplicationApiError {
  constructor(message, currentVersion) {
    super(message, 409)
    this.name = 'ApplicationConflictError'
    this.currentVersion = currentVersion
  }
}

export class ApplicationNotFoundError extends ApplicationApiError {
  constructor(message) {
    super(message, 404)
    this.name = 'ApplicationNotFoundError'
  }
}

export class ApplicationValidationError extends ApplicationApiError {
  constructor(message) {
    super(message, 422)
    this.name = 'ApplicationValidationError'
  }
}

async function readError(response, fallback) {
  try {
    const payload = await response.json()
    if (typeof payload.detail === 'string') return payload.detail
  } catch {
    // Fall through: a non-JSON failure still needs a safe message.
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
    // Reported as a network failure rather than a server one, so the interface
    // can offer a retry instead of telling the student their application is gone.
    throw new ApplicationApiError('We could not reach ScholarZone. Check your connection and try again.', 0)
  }

  if (response.status === 204) return null

  if (!response.ok) {
    const message = await readError(response, 'Something went wrong.')
    if (response.status === 401) throw new ApplicationUnauthenticatedError(message)
    if (response.status === 404) throw new ApplicationNotFoundError(message)
    if (response.status === 409) throw new ApplicationConflictError(message)
    if (response.status === 422) throw new ApplicationValidationError(message)
    throw new ApplicationApiError(message, response.status)
  }

  return response.json()
}

let inFlightList = null

/** Shared in-flight read, dropped as soon as it settles. Never cached between
 *  loads, so a later caller cannot be served stale data. */
function raceAbort(promise, signal) {
  if (!signal) return promise
  if (signal.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'))
  return Promise.race([
    promise,
    new Promise((_, reject) => {
      signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), {
        once: true,
      })
    }),
  ])
}

export function fetchApplications({ signal } = {}) {
  if (inFlightList) return raceAbort(inFlightList, signal)
  inFlightList = request('/applications').finally(() => {
    inFlightList = null
  })
  return raceAbort(inFlightList, signal)
}

export function fetchApplication(applicationId, { signal } = {}) {
  return raceAbort(request(`/applications/${encodeURIComponent(applicationId)}`), signal)
}

export function startApplication(scholarshipId) {
  return request('/applications', {
    method: 'POST',
    body: JSON.stringify({ scholarship_id: scholarshipId }),
  })
}

/** `expectedVersion` is required, not optional: a write that cannot be checked
 *  for staleness is the write this whole mechanism exists to prevent. */
export function updateApplication(applicationId, { expectedVersion, state, outcome, notes }) {
  const body = { expected_version: expectedVersion }
  if (state !== undefined) body.state = state
  if (outcome !== undefined) body.outcome = outcome
  if (notes !== undefined) body.notes = notes
  return request(`/applications/${encodeURIComponent(applicationId)}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
}

/** Idempotent server-side, so a double-clicked checkbox is harmless. */
export function setChecklistItem(applicationId, itemKey, { completed, expectedVersion }) {
  return request(
    `/applications/${encodeURIComponent(applicationId)}/checklist/${encodeURIComponent(itemKey)}`,
    { method: 'PATCH', body: JSON.stringify({ completed, expected_version: expectedVersion }) },
  )
}

export function discardApplication(applicationId) {
  return request(`/applications/${encodeURIComponent(applicationId)}`, { method: 'DELETE' })
}