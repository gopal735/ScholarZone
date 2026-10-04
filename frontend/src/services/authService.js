/**
 * The FastAPI adapter for ScholarZone accounts.
 *
 * This module was written as a deliberate no-op: every method returned null or
 * threw, and the comment above it said to replace these methods "when the
 * authentication API exists". That is now the case, so the methods are real and
 * the contract above them - `AuthContext` reading `{ user } | null` from
 * `checkSession()` - is unchanged.
 *
 * Credentials travel in an httpOnly cookie the server sets, so there is no
 * token in JavaScript to read, copy or leak through an XSS payload. That is why
 * this module holds no token and no user id: the browser's only job is to ask
 * the server who it is, and to send cookies with the request.
 *
 * `credentials: 'include'` is required. Same-origin it is the default, but a
 * cross-origin API base needs it stated, and a silently unauthenticated request
 * would look like a signed-out user rather than a bug.
 */

export class AuthServiceUnavailableError extends Error {
  constructor() {
    super('ScholarZone authentication is not connected yet.')
    this.name = 'AuthServiceUnavailableError'
  }
}

export class AuthError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'AuthError'
    this.status = status
  }
}

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

/** Turn a failed response into a message the form can show as-is. */
async function readError(response, fallback) {
  try {
    const payload = await response.json()
    if (typeof payload.detail === 'string') {
      return payload.detail
    }
  } catch {
    // A non-JSON failure still needs to surface something safe and useful.
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
    // Network-level failure. Reported as such rather than as a wrong password,
    // because telling a student their password is wrong when the network is down
    // sends them to change a password that was never the problem.
    throw new AuthError('We could not reach ScholarZone. Please check your connection and try again.', 0)
  }

  if (!response.ok) {
    throw new AuthError(await readError(response, 'We could not complete that request.'), response.status)
  }

  if (response.status === 204) {
    return null
  }

  return response.json()
}

export const authService = {
  /** `{ user }` when signed in, `{ user: null }` when not. Never throws for a signed-out visitor. */
  async checkSession() {
    try {
      return await request('/auth/session')
    } catch {
      // An unreachable session check must not look like a signed-in user, and
      // must not leave the app stuck on "checking".
      return { user: null }
    }
  },

  async login(credentials) {
    return request('/auth/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
    })
  },

  async register(credentials) {
    return request('/auth/register', {
      method: 'POST',
      body: JSON.stringify(credentials),
    })
  },

  async logout() {
    // The server revokes the session, so this genuinely ends it rather than
    // only asking the browser to forget a token that would still work.
    try {
      return await request('/auth/logout', { method: 'POST' })
    } catch {
      return null
    }
  },
}