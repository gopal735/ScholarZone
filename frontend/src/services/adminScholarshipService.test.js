/**
 * The admin CRUD client fails closed and names its failures.
 *
 * Two properties matter and are not the same: a call without a secret must
 * be refused locally (never sent), and a refusal from the server must
 * arrive with the dependency list attached when the server gave one - the
 * delete dialog shows the blocking tables instead of guessing.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'

import {
  archiveScholarship,
  createScholarship,
  deleteScholarship,
  EDITABLE_FIELDS,
  emptyDraft,
  fetchScholarshipAudit,
  fetchScholarshipList,
  updateScholarship,
} from './adminScholarshipService'

const originalFetch = globalThis.fetch

beforeEach(() => {
  globalThis.fetch = vi.fn()
})

afterEach(() => {
  globalThis.fetch = originalFetch
  delete import.meta.env.VITE_API_BASE_URL
})

function okResponse(payload) {
  return Promise.resolve({ ok: true, status: 200, text: () => Promise.resolve(JSON.stringify(payload)) })
}

function errorResponse(status, detail) {
  return Promise.resolve({
    ok: false,
    status,
    text: () => Promise.resolve(JSON.stringify({ detail })),
  })
}

describe('fail closed', () => {
  it('refuses every call without a secret, locally', async () => {
    const calls = [
      () => fetchScholarshipList(''),
      () => fetchScholarshipAudit('', 1),
      () => createScholarship('', { title: 'x' }),
      () => updateScholarship('', 1, { fields: {} }),
      () => archiveScholarship('', 1, 'gone'),
      () => deleteScholarship('', 1, 'DELETE 1', 'because'),
    ]
    for (const call of calls) {
      await expect(call()).rejects.toThrow(/authentication required/i)
    }
    expect(globalThis.fetch).not.toHaveBeenCalled()
  })

  it('sends the admin header on every request', async () => {
    globalThis.fetch.mockReturnValueOnce(okResponse({ items: [], total: 0 }))
    await fetchScholarshipList('the-secret', { q: 'hong kong' })
    const [url, init] = globalThis.fetch.mock.calls[0]
    expect(String(url)).toContain('/admin/scholarships')
    expect(String(url)).toContain('q=hong+kong')
    expect(init.headers['X-Admin-Secret']).toBe('the-secret')
  })

  it('surfaces the delete confirmation requirement', async () => {
    globalThis.fetch.mockReturnValueOnce(
      errorResponse(400, 'Refused: confirm must be exactly "DELETE 7".'),
    )
    await expect(deleteScholarship('the-secret', 7, 'DELETE', 'typo')).rejects.toThrow(/DELETE 7/)
  })

  it('attaches the blocking dependencies to the error', async () => {
    globalThis.fetch.mockReturnValueOnce(
      errorResponse(409, {
        message: 'depended upon',
        blocked_by: ['SavedScholarship', 'Application'],
      }),
    )
    const error = await deleteScholarship('the-secret', 7, 'DELETE 7', 'test').catch((e) => e)
    expect(error.message).toBe('depended upon')
    expect(error.blocked_by).toEqual(['SavedScholarship', 'Application'])
  })
})

describe('form shape', () => {
  it('marks the server whitelist in the editor', () => {
    const keys = EDITABLE_FIELDS.map((field) => field.key)
    expect(keys).toContain('title')
    expect(keys).toContain('country')
    expect(keys).toContain('official_source_url')
    expect(keys).not.toContain('id')
    expect(keys).not.toContain('verification_status')
  })

  it('starts from the required fields only', () => {
    expect(emptyDraft()).toEqual({ title: '', country: '' })
  })
})
