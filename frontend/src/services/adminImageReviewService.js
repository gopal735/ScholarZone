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

export async function fetchReviewQueue(adminSecret) {
  return adminRequest('/admin/images/review-queue', {
    adminSecret,
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
