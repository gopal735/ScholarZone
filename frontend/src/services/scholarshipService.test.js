import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchScholarshipsByLifecycle } from './scholarshipService'

describe('fetchScholarshipsByLifecycle', () => {
  afterEach(() => {
    window.localStorage.removeItem('scholarzone.staticCatalogue')
    vi.unstubAllGlobals()
  })

  it('filters across all API pages and returns lifecycle-aware pagination', async () => {
    window.localStorage.setItem('scholarzone.staticCatalogue', 'false')
    const fetchMock = vi.fn(async (url) => {
      const page = Number(new URL(url).searchParams.get('page'))
      const items = page === 1
        ? [{ id: 1, title: 'Expired', status: 'open', deadline_date: '2000-01-01' }]
        : [{ id: 2, title: 'Still open', status: 'open', deadline_date: '2999-01-01' }]

      return {
        ok: true,
        json: async () => ({
          items,
          pagination: { page, limit: 100, total: 2, total_pages: 2 },
        }),
      }
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await fetchScholarshipsByLifecycle(
      { page: 1, limit: 1, status: 'closed' },
      'All',
    )

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(new URL(fetchMock.mock.calls[0][0]).searchParams.has('status')).toBe(false)
    expect(result.items.map((item) => item.id)).toEqual([1])
    expect(result.pagination).toEqual({ page: 1, limit: 1, total: 1, total_pages: 1 })
  })

  it('applies the status dropdown consistently with lifecycle tabs', async () => {
    window.localStorage.setItem('scholarzone.staticCatalogue', 'false')
    const fetchMock = vi.fn(async (url) => {
      const page = Number(new URL(url).searchParams.get('page'))
      return {
        ok: true,
        json: async () => ({
          items: page === 1
            ? [{ id: 1, status: 'open', deadline_date: '2000-01-01' }]
            : [{ id: 2, status: 'open', deadline_date: '2999-01-01' }],
          pagination: { page, limit: 100, total: 2, total_pages: 2 },
        }),
      }
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await fetchScholarshipsByLifecycle({ page: 1, limit: 12, status: 'open' }, 'All')

    expect(result.items.map((item) => item.id)).toEqual([2])
    expect(result.pagination.total).toBe(1)
  })

  it('sends academic and tri-state filters through the list API contract', async () => {
    window.localStorage.setItem('scholarzone.staticCatalogue', 'false')
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
