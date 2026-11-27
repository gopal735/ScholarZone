import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchScholarshipsByLifecycle } from './scholarshipService'

describe('fetchScholarshipsByLifecycle', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('sends lifecycle filter to the API in a single request', async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({ items: [{ id: 1 }], pagination: { page: 1, limit: 1, total: 1, total_pages: 1 } }),
    }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await fetchScholarshipsByLifecycle({ page: 1, limit: 1, status: 'closed' }, 'All')

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const query = new URL(fetchMock.mock.calls[0][0]).searchParams
    expect(query.get('lifecycle')).toBe('closed')
    expect(result.items.map((item) => item.id)).toEqual([1])
  })

  it('applies the status dropdown consistently with lifecycle tabs', async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({ items: [{ id: 2 }], pagination: { page: 1, limit: 12, total: 1, total_pages: 1 } }),
    }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await fetchScholarshipsByLifecycle({ page: 1, limit: 12, status: 'open' }, 'All')

    const query = new URL(fetchMock.mock.calls[0][0]).searchParams
    expect(query.get('lifecycle')).toBe('open')
    expect(result.items.map((item) => item.id)).toEqual([2])
  })

  it('sends academic and tri-state filters through the list API contract', async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({ items: [], pagination: { page: 1, limit: 12, total: 0, total_pages: 0 } }),
    }))
    vi.stubGlobal('fetch', fetchMock)

    await fetchScholarshipsByLifecycle({
      page: 1,
      limit: 12,
      fully_funded: 'unknown',
      department: 'Computer Science',
      eligible_field: 'Artificial Intelligence',
      eligible_programme: 'MSc Data Science',
      programme_type: 'Research award',
    }, 'All')

    const query = new URL(fetchMock.mock.calls[0][0]).searchParams
    expect(query.get('fully_funded')).toBe('unknown')
    expect(query.get('department')).toBe('Computer Science')
    expect(query.get('eligible_field')).toBe('Artificial Intelligence')
    expect(query.get('eligible_programme')).toBe('MSc Data Science')
    expect(query.get('programme_type')).toBe('Research award')
  })
})