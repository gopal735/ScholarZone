/**
 * The supervisor API client's failure taxonomy.
 *
 * The behaviour worth pinning here is what happens when the response is a
 * success but not the JSON the caller asked for. A misrouted API base URL -
 * the frontend defaults to `/api` and a host that rewrites unknown paths to its
 * SPA shell answers 200 with `Content-Type: text/html` - used to reach
 * `response.json()` and throw a raw `SyntaxError: Unexpected token '<'`. That
 * became the message a student saw, attached to a panel that said only
 * "Supervisor information is unavailable right now.", with nothing naming the
 * cause and nothing an operator could act on.
 *
 * So the taxonomy distinguishes three things a page cannot afford to confuse:
 * a lost session, a server-side refusal, and a response that is not JSON at
 * all. The third carries the URL and the content type, because those are the
 * two facts that identify a routing or deployment defect rather than a bug.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  SupervisorApiError,
  SupervisorAuthRequired,
  fetchSupervisors,
  fetchSupervisorSummary,
} from './supervisorService'

/* A response shaped like the SPA shell a catch-all rewrite serves: HTTP 200,
   an HTML content type, and a body that is not JSON. */
function htmlResponse() {
  return {
    ok: true,
    status: 200,
    headers: {
      get: (name) =>
        String(name).toLowerCase() === 'content-type' ? 'text/html; charset=UTF-8' : null,
    },
    json: async () => {
      throw new SyntaxError("Unexpected token '<', \"<!doctype \"... is not valid JSON")
    },
    text: async () =>
      '<!doctype html><html><head></head><body><div id="root"></div></body></html>',
  }
}

function jsonResponse(body, { status = 200, contentType = 'application/json' } = {}) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: (name) => (String(name).toLowerCase() === 'content-type' ? contentType : null) },
    json: async () => body,
    text: async () => JSON.stringify(body),
  }
}

describe('supervisorService', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('reads the public list and keeps its credentials policy', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ scholarship_id: 7, coverage: {}, supervisors: [] }))
    vi.stubGlobal('fetch', fetchMock)

    const payload = await fetchSupervisors(7)

    expect(payload.scholarship_id).toBe(7)
    const [url, options] = fetchMock.mock.calls[0]
    // The public routes are unauthenticated, but the cookie still rides along
    // so a signed-in student's session is not silently dropped.
    expect(options.credentials).toBe('include')
    expect(url.pathname).toBe('/api/scholarships/7/supervisors')
    expect(options.headers.Accept).toBe('application/json')
  })

  it('names the request URL when the API answers with the SPA shell', async () => {
    /* The defect: a 200 that is not JSON was treated as success and surfaced a
       raw SyntaxError. The replacement error has to carry the URL and the
       content type, because those are what tell an operator the request never
       reached the API at all. */
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(htmlResponse()))

    await expect(fetchSupervisors(7)).rejects.toBeInstanceOf(SupervisorApiError)
    await expect(fetchSupervisors(7)).rejects.toThrow(/scholarships\/7\/supervisors/)
    await expect(fetchSupervisors(7)).rejects.toThrow(/text\/html/)
  })

  it('treats a missing content type as JSON and still parses', async () => {
    /* The tolerant half. A server that omits Content-Type on a valid JSON body
       must not be reported as misrouted, so the check is for a body that
       *fails to parse* rather than for a header alone. */
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ ok: true }, { contentType: null })),
    )

    await expect(fetchSupervisorSummary(7)).resolves.toEqual({ ok: true })
  })

  it('does not raise a spurious routing error when the body parses cleanly', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ ok: true })))

    await expect(fetchSupervisorSummary(7)).resolves.toEqual({ ok: true })
  })

  it('reports a server refusal as its own class, not as a routing failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse({ detail: 'An unexpected server error occurred.' }, { status: 500 }),
        ),
    )

    const error = await fetchSupervisors(7).catch((caught) => caught)

    expect(error).toBeInstanceOf(SupervisorApiError)
    expect(error.status).toBe(500)
    expect(error.message).toBe('An unexpected server error occurred.')
    // A real 500 from the API is not the same defect as an HTML 200, and the
    // message must not claim the request was misrouted.
    expect(error.message).not.toMatch(/text\/html/)
  })

  it('keeps a lost session as a sign-in state', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ detail: 'nope' }, { status: 401 })))

    await expect(fetchSupervisors(7)).rejects.toBeInstanceOf(SupervisorAuthRequired)
  })
})
