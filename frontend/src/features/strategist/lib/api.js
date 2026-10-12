// Client for the Study-to-Career Strategist API.
//
// Same contract as the other feature services in the app: API_BASE from
// VITE_API_BASE_URL defaulting to /api, no secrets, JSON in/out. A VITE_STRATEGIST_FIXTURE
// switch makes it read a bundled, captured fixture instead of the network, so the
// interface can be reviewed and screenshotted deterministically without the
// feature-flag-gated backend running.
import captured from './fixture.json'

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')
// Fixture mode lets the interface render deterministically without the
// flag-gated backend, for review and for screenshots. It can be turned on at build
// time (VITE_STRATEGIST_FIXTURE) or at runtime with ?fixture=1, so a reviewer never
// has to rebuild to preview it.
function _fixtureMode() {
  if (typeof window !== 'undefined') {
    const q = new URLSearchParams(window.location.search).get('fixture')
    if (q === '1' || q === 'true') return true
  }
  return String(import.meta.env.VITE_STATEGIST_FIXTURE || '').toLowerCase() === 'true'
}
const FIXTURE = _fixtureMode()

async function handle(response) {
  if (!response.ok) {
    let detail = `Request failed (${response.status})`
    try {
      const body = await response.json()
      if (body && body.detail) detail = Array.isArray(body.detail) ? JSON.stringify(body.detail) : body.detail
    } catch {
      /* leave the generic message */
    }
    throw new Error(detail)
  }
  return response.json()
}

export async function fetchSubjects() {
  if (FIXTURE) return { subjects: captured.subjects }
  return handle(await fetch(`${API_BASE}/v2/strategist/subjects`))
}

export async function fetchPlan(payload) {
  if (FIXTURE) {
    // The fixture captured two concrete plans; pick by subject.
    if (payload.subject_key === 'civil_engineering') return captured.plan_civil
    return captured.plan_cs
  }
  return handle(await fetch(`${API_BASE}/v2/strategist/plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }))
}

export async function fetchPathway(iso2) {
  if (FIXTURE) return iso2 === 'DE' ? captured.pathway_de : { iso2, steps: [], reason: 'Fixture only has DE.' }
  return handle(await fetch(`${API_BASE}/v2/strategist/pathway/${iso2}`))
}

export async function fetchGaps() {
  if (FIXTURE) {
    const gaps = []
    for (const plan of [captured.plan_cs, captured.plan_civil]) {
      for (const entry of plan.insufficient_data || []) {
        gaps.push({ country_iso2: entry.iso2 })
      }
    }
    return { gaps, subjects: ['computer_science', 'data_science', 'civil_engineering'], matrix: [] }
  }
  return handle(await fetch(`${API_BASE}/v2/strategist/gaps`))
}
