const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

export class StudyPlanApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'StudyPlanApiError'
    this.status = status
  }
}

export class StudyPlanUnauthenticatedError extends StudyPlanApiError {
  constructor(message) { super(message, 401); this.name = 'StudyPlanUnauthenticatedError' }
}

export class StudyPlanNotFoundError extends StudyPlanApiError {
  constructor(message) { super(message, 404); this.name = 'StudyPlanNotFoundError' }
}

async function request(path, options = {}) {
  const res = await fetch(`${apiBaseUrl}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  if (res.status === 401) throw new StudyPlanUnauthenticatedError('Sign in to continue.')
  if (res.status === 404) throw new StudyPlanNotFoundError('Not found.')
  if (!res.ok) {
    let msg = `Request failed (${res.status})`
    try { const j = await res.json(); if (j.detail) msg = j.detail } catch { /* ignore */ }
    throw new StudyPlanApiError(msg, res.status)
  }
  if (res.status === 204) return null
  return res.json()
}

export async function fetchPlans() {
  return request('/study-plans')
}

export async function createPlan(payload) {
  return request('/study-plans', { method: 'POST', body: JSON.stringify(payload) })
}

export async function updatePlan(id, payload) {
  return request(`/study-plans/${id}`, { method: 'PATCH', body: JSON.stringify(payload) })
}

export async function deletePlan(id) {
  return request(`/study-plans/${id}`, { method: 'DELETE' })
}

export async function addTask(planId, payload) {
  return request(`/study-plans/${planId}/tasks`, { method: 'POST', body: JSON.stringify(payload) })
}

export async function updateTask(taskId, payload) {
  return request(`/study-plans/tasks/${taskId}`, { method: 'PATCH', body: JSON.stringify(payload) })
}

export async function deleteTask(taskId) {
  return request(`/study-plans/tasks/${taskId}`, { method: 'DELETE' })
}
