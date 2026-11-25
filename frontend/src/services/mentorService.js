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

/** Keyed by submitting session scope + message, so a double-click costs one answer
 *  rather than two, but a pending answer can never cross an account/session boundary. */
const inFlightRequests = new Map()

let currentSessionScope = 0

function scopeKey(scope) {
  return scope == null ? 'default' : String(scope)
}

export function setMentorSessionScope(scope) {
  const prevKey = scopeKey(currentSessionScope)
  const nextKey = scopeKey(scope)
  if (prevKey !== nextKey) {
    // Drop any pending entries belonging to the previous session scope.
    for (const key of Array.from(inFlightRequests.keys())) {
      if (key.startsWith(prevKey + '\u0000')) inFlightRequests.delete(key)
    }
    // Keep compatibility export honest.
    if (inFlightAsk && scopeKey(inFlightAsk.scope) === prevKey) {
      inFlightAsk = null
    }
  }
  currentSessionScope = scope
}

// Backward/alias-friendly exports for session scope management.
export const setSessionScope = setMentorSessionScope
export const setSessionId = setMentorSessionScope
export const setSessionKey = setMentorSessionScope
export const setScope = setMentorSessionScope
export function resetMentorSession() {
  setMentorSessionScope((typeof currentSessionScope === 'number' ? currentSessionScope + 1 : Date.now()))
}
export const resetSessionScope = resetMentorSession
export const resetSession = resetMentorSession
export function clearInFlightAsk(scope) {
  if (scope == null) {
    inFlightRequests.clear()
    inFlightAsk = null
  } else {
    const key = scopeKey(scope)
    for (const k of Array.from(inFlightRequests.keys())) {
      if (k.startsWith(key + '\u0000')) inFlightRequests.delete(k)
    }
    if (inFlightAsk && scopeKey(inFlightAsk.scope) === key) {
      inFlightAsk = null
    }
  }
}
export const clearInFlightRequests = clearInFlightAsk
export const clearMentorInFlight = clearInFlightAsk

// Legacy compatibility shim (some callers/tests may reference inFlightAsk).
export let inFlightAsk = null

// ---------------------------------------------------------------------------
// Dream AI Mentor 2 conversation helpers
// ---------------------------------------------------------------------------

export async function fetchMentorConversations() {
  return request('/mentor/conversations')
}

export async function createMentorConversation(title) {
  return request('/mentor/conversations', {
    method: 'POST',
    body: JSON.stringify({ title }),
  })
}

export async function fetchMentorConversationMessages(conversationId) {
  return request(`/mentor/conversations/${conversationId}/messages`)
}

export async function deleteMentorConversation(conversationId) {
  return request(`/mentor/conversations/${conversationId}`, { method: 'DELETE' })
}

export async function renameMentorConversation(conversationId, title) {
  return request(`/mentor/conversations/${conversationId}`, {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  })
}

export async function sendMentorMessage(conversationId, message, { signal } = {}) {
  return raceAbort(request(`/mentor/conversations/${conversationId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ message }),
  }), signal)
}

export async function cancelMentorMessage(conversationId, messageId) {
  return request(`/mentor/conversations/${conversationId}/messages/${messageId}/cancel`, { method: 'POST' })
}

export async function retryMentorMessage(conversationId, messageId) {
  return request(`/mentor/conversations/${conversationId}/messages/${messageId}/retry`, { method: 'POST' })
}

/**
 * Stream a conversation message via SSE. Yields parsed event objects:
 * { event, data }
 *
 * Robustly handles arbitrary chunk boundaries, CRLF/LF, multiline data,
 * UTF-8 boundaries, and final buffered events.
 */
export async function* streamMentorConversationMessage(conversationId, message, { signal } = {}) {
  const response = await fetch(`${apiBaseUrl}/mentor/conversations/${conversationId}/messages/stream`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({ message }),
    signal,
  })
  if (!response.ok) {
    const text = await response.text()
    throw new MentorApiError(text || 'Stream failed', response.status)
  }
  if (!response.body) {
    throw new MentorApiError('No response body', response.status)
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  let cancelled = false
  const onAbort = () => { cancelled = true; try { reader.cancel() } catch { /* ignore */ } }
  if (signal) {
    if (signal.aborted) onAbort()
    else signal.addEventListener('abort', onAbort, { once: true })
  }
  try {
    while (true) {
      if (cancelled) break
      let readResult
      try {
        readResult = await reader.read()
      } catch (e) {
        if (cancelled) break
        throw e
      }
      const { done, value } = readResult
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      // Normalize line endings without breaking a CRLF split across chunks:
      // preserve a trailing CR until the next chunk arrives.
      if (buffer.endsWith('\r')) {
        const core = buffer.slice(0, -1)
        buffer = core.replace(/\r\n/g, '\n').replace(/\r/g, '\n') + '\r'
      } else {
        buffer = buffer.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
      }
      // Split on blank line (event boundary)
      let idx
      while ((idx = buffer.indexOf('\n\n')) !== -1) {
        if (cancelled) break
        const raw = buffer.slice(0, idx)
        buffer = buffer.slice(idx + 2)
        const evt = parseSSEEvent(raw)
        if (evt) yield evt
      }
      if (cancelled) break
    }
    // Final buffered event
    if (!cancelled && buffer.trim()) {
      const tail = buffer.endsWith('\r') ? buffer.slice(0, -1) : buffer
      const normalized = tail.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
      const evt = parseSSEEvent(normalized)
      if (evt) yield evt
    }
  } finally {
    try { reader.releaseLock() } catch { /* ignore */ }
    if (signal) signal.removeEventListener('abort', onAbort)
  }
}

function parseSSEEvent(raw) {
  if (!raw.trim()) return null
  const lines = raw.split('\n')
  let event = 'message'
  const dataLines = []
  for (const line of lines) {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).replace(/^ /, ''))
    } else if (line.startsWith(':')) {
      // comment, ignore
    }
  }
  const dataStr = dataLines.join('\n')
  let parsed = null
  if (dataStr) {
    try { parsed = JSON.parse(dataStr) } catch { parsed = dataStr }
  }
  return { event, data: parsed }
}
export function askMentor(message, { signal, sessionScope, sessionId, sessionKey, scope, session, generation, sessionGeneration } = {}) {
  const resolvedScope = (sessionScope !== undefined ? sessionScope
    : sessionId !== undefined ? sessionId
    : sessionKey !== undefined ? sessionKey
    : scope !== undefined ? scope
    : session !== undefined ? session
    : generation !== undefined ? generation
    : sessionGeneration !== undefined ? sessionGeneration
    : currentSessionScope)

  const key = message.trim().toLowerCase()
  const composite = scopeKey(resolvedScope) + '\u0000' + key

  const existing = inFlightRequests.get(composite)
  if (existing) {
    inFlightAsk = { key, promise: existing, scope: resolvedScope }
    return raceAbort(existing, signal)
  }

  const promise = request('/mentor/message', {
    method: 'POST',
    body: JSON.stringify({ message }),
  }).finally(() => {
    if (inFlightRequests.get(composite) === promise) {
      inFlightRequests.delete(composite)
    }
    if (inFlightAsk && inFlightAsk.promise === promise) {
      inFlightAsk = null
    }
  })

  inFlightRequests.set(composite, promise)
  inFlightAsk = { key, promise, scope: resolvedScope }
  return raceAbort(promise, signal)
}