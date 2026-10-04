/**
 * The GROUNDed AI Mentor API client.
 *
 * Built the same way as the Application Workspace client, for the same reasons.
 *
 * **Errors are distinguishable, because the interface responds differently to
 * each.** Being signed out, being rate limited, the server being unreachable and
 * the question being invalid are four different situations. A single "something
 * went wrong" would make the page offer a retry for a session that no longer
 * exists, or offer a sign-in link for a network blip.
 *
 * **A repeated identical question is sent once.** Asking twice is a real thing
 * students do - they double-click, or they are unsure whether the first click
 * landed. In flight, an identical message joins the existing request rather than
 * starting a second one. It is dropped the moment it settles, so nothing is ever
 * served from a cache and a later question always sees current data.
 *
 * **There is no streaming.** The mentor answers in one grounded response. A
 * partial answer arriving before its evidence would be worse than a short wait,
 * because a reader cannot tell an unfinished sentence from a finished claim.
 */

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

export class MentorApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'MentorApiError'
    this.status = status
  }
}

/** No session. The mentor can render nothing private, so it must not pretend. */
export class MentorUnauthenticatedError extends MentorApiError {
  constructor(message) {
    super(message, 401)
    this.name = 'MentorUnauthenticatedError'
  }
}

/**
 * Too many questions too quickly. Carries the server's own wait, so the interface
 * can say when it will be welcome back rather than guessing.
 */
export class MentorRateLimitedError extends MentorApiError {
  constructor(message, retryAfterSeconds) {
    super(message, 429)
    this.name = 'MentorRateLimitedError'
    this.retryAfterSeconds = retryAfterSeconds
  }
}

export class MentorValidationError extends MentorApiError {
  constructor(message) {
    super(message, 422)
    this.name = 'MentorValidationError'
  }
}

/** The mentor could not be reached, or answered in a way it could not use. */
export class MentorUnavailableError extends MentorApiError {
  constructor(message, status) {
    super(message, status)
    this.name = 'MentorUnavailableError'
  }
}

async function readError(response, fallback) {
  try {
    const payload = await response.json()
    if (typeof payload.detail === 'string') return payload.detail
  } catch {
    // A non-JSON failure still needs a message that is safe to show.
  }
  return fallback
}

function retryAfterSeconds(response) {
  const raw = Number(response.headers?.get?.('Retry-After'))
  return Number.isFinite(raw) && raw > 0 ? Math.ceil(raw) : 30
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
    throw new MentorApiError(
      'We could not reach ScholarZone. Check your connection and try again.',
      0,
    )
  }

  if (response.status === 204) return null

  if (!response.ok) {
    const message = await readError(response, 'Something went wrong.')
    if (response.status === 401) throw new MentorUnauthenticatedError(message)
    if (response.status === 429) {
      throw new MentorRateLimitedError(message, retryAfterSeconds(response))
    }
    if (response.status === 422) throw new MentorValidationError(message)
    if (response.status >= 500) throw new MentorUnavailableError(message, response.status)
    throw new MentorApiError(message, response.status)
  }

  return response.json()
}

/**
 * Race a shared request against one caller's own cancellation.
 *
 * The caller's signal is deliberately not handed to `fetch`: one component
 * unmounting must not abort a read another component is still waiting on.
 */
function raceAbort(promise, signal) {
  if (!signal) return promise
  if (signal.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'))
  return Promise.race([
    promise,
    new Promise((_, reject) => {
      signal.addEventListener(
        'abort',
        () => reject(new DOMException('Aborted', 'AbortError')),
        { once: true },
      )
    }),
  ])
}

/** The vocabulary the mentor understands. Public: it contains no account data. */
export function fetchMentorOverview({ signal } = {}) {
  return raceAbort(request('/mentor/overview'), signal)
}

/** Keyed by the message, so a double-click costs one answer rather than two. */
let inFlightAsk = null

export function askMentor(message, { signal } = {}) {
  const key = message.trim().toLowerCase()
  if (inFlightAsk && inFlightAsk.key === key) {
    return raceAbort(inFlightAsk.promise, signal)
  }

  const promise = request('/mentor/message', {
    method: 'POST',
    body: JSON.stringify({ message }),
  }).finally(() => {
    if (inFlightAsk && inFlightAsk.promise === promise) inFlightAsk = null
  })

  inFlightAsk = { key, promise }
  return raceAbort(promise, signal)
}