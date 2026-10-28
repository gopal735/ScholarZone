/* Supervisor discovery, outreach and drafts.
 *
 * One module for all three because they share an identity: the first two are
 * private to a signed-in student and the third needs the same session to
 * personalise. Splitting them would mean three copies of the cookie-bearing
 * request helper and three places for a credential to be dropped.
 *
 * Every request sends credentials. That is safe here and only because the
 * session cookie is HttpOnly and SameSite=Lax and the API refuses writes without
 * it — a cookie the page cannot read is a cookie that cannot be exfiltrated by
 * script on this origin.
 */

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

export class SupervisorApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'SupervisorApiError'
    this.status = status
  }
}

/* A 401 is not an error the UI should shout about. It is the ordinary state of
   a signed-out visitor, and every caller has a sensible thing to render for it,
   so it is returned as a value rather than thrown. Everything else throws. */
export class SupervisorAuthRequired extends Error {
  constructor() {
    super('Sign in to use supervisor outreach.')
    this.name = 'SupervisorAuthRequired'
    this.status = 401
  }
}

async function request(path, { method = 'GET', body, searchParams, signal } = {}) {
  const url = new URL(`${apiBaseUrl}${path}`, window.location.origin)

  if (searchParams) {
    Object.entries(searchParams).forEach(([key, value]) => {
      if (value === undefined || value === null || value === '') return
      if (Array.isArray(value)) {
        value.forEach((item) => url.searchParams.append(key, item))
      } else {
        url.searchParams.set(key, value)
      }
    })
  }

  const response = await fetch(url, {
    method,
    signal,
    credentials: 'include',
    headers: {
      Accept: 'application/json',
      ...(body ? { 'Content-Type': 'application/json' } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  })

  if (response.status === 401) {
    throw new SupervisorAuthRequired()
  }
  if (!response.ok) {
    let message = 'Something went wrong. Please try again.'
    try {
      const payload = await response.json()
      if (typeof payload.detail === 'string') {
        message = payload.detail
      }
    } catch {
      // A non-JSON failure still surfaces a safe message rather than a raw body.
    }
    throw new SupervisorApiError(message, response.status)
  }
  if (response.status === 204) {
    return null
  }
  return response.json()
}

/* ── Public ──────────────────────────────────────────────────────────────
   No session needed. These are public professional facts read from official
   university pages, so a signed-out visitor sees exactly what a signed-in one
   does. */

export function fetchSupervisors(scholarshipId, { interests = [], limit, signal } = {}) {
  return request(`/scholarships/${scholarshipId}/supervisors`, {
    signal,
    searchParams: { interests, limit },
  })
}

export function fetchSupervisorSummary(scholarshipId, { signal } = {}) {
  return request(`/scholarships/${scholarshipId}/supervisor-summary`, { signal })
}

export function fetchContactTemplates({ signal } = {}) {
  return request('/supervisor-email/templates', { signal })
}

/* ── Private ───────────────────────────────────────────────────────────── */

export function fetchOutreach({ status, signal } = {}) {
  return request('/outreach', { signal, searchParams: { status } })
}

export function fetchOutreachSummary({ signal } = {}) {
  return request('/outreach/summary', { signal })
}

export function startOutreach({ scholarshipId, professorId, draftSubject, draftBody, templateId }) {
  return request('/outreach', {
    method: 'POST',
    body: {
      scholarship_id: scholarshipId,
      professor_id: professorId,
      draft_subject: draftSubject,
      draft_body: draftBody,
      template_id: templateId ?? null,
    },
  })
}

/* `version` is the record's own optimistic-concurrency token. Sending a stale
   one is how the API answers 409 instead of silently discarding whatever was
   typed in another tab, so it is a required argument rather than an option. */
export function updateOutreach(recordId, { version, ...fields }) {
  return request(`/outreach/${recordId}`, {
    method: 'PATCH',
    body: { version, ...fields },
  })
}

export function deleteOutreach(recordId) {
  return request(`/outreach/${recordId}`, { method: 'DELETE' })
}

export function fetchEmailDraft({ scholarshipId, professorId, templateKey, interests = [] }) {
  return request('/supervisor-email/draft', {
    method: 'POST',
    body: {
      scholarship_id: scholarshipId,
      professor_id: professorId,
      template_key: templateKey ?? null,
      interests,
    },
  })
}

export default {
  fetchSupervisors,
  fetchSupervisorSummary,
  fetchContactTemplates,
  fetchOutreach,
  fetchOutreachSummary,
  startOutreach,
  updateOutreach,
  deleteOutreach,
  fetchEmailDraft,
}