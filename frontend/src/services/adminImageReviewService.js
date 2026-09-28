const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

export class AdminImageReviewError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'AdminImageReviewError'
    this.status = status
  }
}

async function adminRequest(path, options = {}) {
  const adminSecret = options.adminSecret
  if (!adminSecret) {
    throw new AdminImageReviewError('Admin secret is required.', 401)
  }

  const url = `${API_BASE}${path}`
  const response = await fetch(url, {
    ...options,
    headers: {
      'X-Admin-Secret': adminSecret,
      'Accept': 'application/json',
      ...(options.headers || {}),
    },
  })

  if (!response.ok) {
    let message = 'Admin image review request failed.'
    try {
      const payload = await response.json()
      if (typeof payload.detail === 'string') {
        message = payload.detail
      }
    } catch {
      // Non-JSON error response
    }
    throw new AdminImageReviewError(message, response.status)
  }

  if (response.status === 204) {
    return null
  }

  return response.json()
}

export const EMPTY_REVIEW_QUEUE = {
  items: [],
  total: 0,
  counts: {
    pending_image_reviews: 0,
    decided_image_reviews: 0,
    all_image_reviews: 0,
    pending_scholarship_reviews: 0,
    scholarships_needing_review: 0,
  },
  pagination: { page: 1, limit: 25, pages: 0, has_next: false, has_prev: false, max_page_size: 100 },
}

/**
 * Fetch the private human-review queue.
 *
 * The endpoint returns an object (items + database-wide counts + pagination).
 * An earlier response shape was a bare array with no totals, which meant the
 * dashboard could not show a real backlog size and the owner had no way to
 * know whether work remained. A non-object response is normalised rather than
 * crashing the page, so an older backend degrades instead of breaking admin.
 */
export async function fetchReviewQueue(adminSecret, options = {}) {
  const params = new URLSearchParams()
  if (options.page) params.set('page', String(options.page))
  if (options.limit) params.set('limit', String(options.limit))
  if (options.search) params.set('search', options.search)
  if (options.kind) params.set('kind', options.kind)
  if (options.confidence) params.set('confidence', options.confidence)
  if (options.sourceType) params.set('source_type', options.sourceType)
  if (options.sort) params.set('sort', options.sort)
  if (options.includeDecided) params.set('include_decided', 'true')

  const query = params.toString()
  const payload = await adminRequest(
    `/admin/images/review-queue${query ? `?${query}` : ''}`,
    { adminSecret },
  )
  if (Array.isArray(payload)) {
    return { ...EMPTY_REVIEW_QUEUE, items: payload, total: payload.length }
  }
  return {
    ...EMPTY_REVIEW_QUEUE,
    ...payload,
    items: payload?.items ?? [],
    counts: { ...EMPTY_REVIEW_QUEUE.counts, ...(payload?.counts || {}) },
    pagination: { ...EMPTY_REVIEW_QUEUE.pagination, ...(payload?.pagination || {}) },
  }
}

/**
 * Record a decision and return the refreshed database-wide counts.
 *
 * Returning the new counts with the decision is what stops the dashboard
 * showing a stale pending number until a manual reload.
 */
export async function decideReview(reviewId, approved, adminSecret, reviewerNote) {
  return adminRequest(`/admin/images/review-queue/${reviewId}/decision`, {
    adminSecret,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ approved, reviewer_note: reviewerNote || '' }),
  })
}

export async function approveReview(reviewId, adminSecret, reviewerNote) {
  return adminRequest(`/admin/images/review/${reviewId}/approve`, {
    adminSecret,
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      approved: true,
      reviewer_note: reviewerNote || '',
    }),
  })
}

export async function rejectReview(reviewId, adminSecret, reviewerNote) {
  return adminRequest(`/admin/images/review/${reviewId}/reject`, {
    adminSecret,
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      approved: false,
      reviewer_note: reviewerNote || '',
    }),
  })
}
