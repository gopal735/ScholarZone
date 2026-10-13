// Client for the Study-to-Career Strategist API.
//
// Same contract as the other feature services in the app: API_BASE from
// VITE_API_BASE_URL defaulting to /api, no secrets, JSON in/out. A ?fixture=1 switch
// (or VITE_STRATEGIST_FIXTURE at build) makes it read a bundled, captured fixture
// instead of the network, so the interface can be reviewed and screenshotted
// deterministically without the feature-flag-gated backend running.
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

// ---------------------------------------------------------------------------
// A small, bounded response cache.
//
// The plan is a read-only function of its request; on slow mobile networks a
// re-run (every slider move in what-if) should not hammer the API. The cache is
// bounded in entries and refreshed by a TTL; entries are keyed by the exact
// request so different questions never share an answer. On failure it serves a
// still-known (possibly stale) answer tagged for the UI to disclose, rather than
// dropping the reader to an error - but it never invents an answer it does not hold.
// ---------------------------------------------------------------------------
const PLAN_TTL_MS = 5 * 60 * 1000
const SUBJECTS_TTL_MS = 30 * 60 * 1000
const MAX_PLAN_ENTRIES = 20
const _planCache = new Map()
let _cachedSubjects = null // { ts, value }

function _planKey(payload) {
  return JSON.stringify({
    subject_key: payload.subject_key, degree: payload.degree,
    funding_model: payload.funding_model ?? null,
    budget_bdt: payload.budget_bdt ?? null,
    weights: payload.weights ?? null, iso2s: payload.iso2s ?? null,
  })
}

//: Reset all caches. For tests and a hard "re-verify" action.
export function resetStrategistCache() {
  _planCache.clear()
  _cachedSubjects = null
}

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

export async function fetchSubjects({ force = false } = {}) {
  if (FIXTURE) return { subjects: captured.subjects }
  if (!force && _cachedSubjects && Date.now() - _cachedSubjects.ts < SUBJECTS_TTL_MS) {
    return { ..._cachedSubjects.value, _cached: true }
  }
  try {
    const value = await handle(await fetch(`${API_BASE}/v2/strategist/subjects`))
    _cachedSubjects = { ts: Date.now(), value }
    return value
  } catch (error) {
    if (_cachedSubjects) {
      // Serve the last known subjects, disclosed as stale, rather than a blank list.
      return { ..._cachedSubjects.value, _cached: true, _stale: true }
    }
    throw error
  }
}

export async function fetchPlan(payload, { force = false } = {}) {
  if (FIXTURE) {
    // The fixture captured two concrete plans; pick by subject.
    if (payload.subject_key === 'civil_engineering') return captured.plan_civil
    return captured.plan_cs
  }
  const key = _planKey(payload)
  if (!force) {
    const entry = _planCache.get(key)
    if (entry && Date.now() - entry.ts < PLAN_TTL_MS) {
      return { ...entry.value, _cached: true }
    }
  }
  try {
    const value = await handle(await fetch(`${API_BASE}/v2/strategist/plan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }))
    _planCache.set(key, { ts: Date.now(), value })
    // Bounded: drop the oldest entries beyond the cap (Map preserves insertion order).
    while (_planCache.size > MAX_PLAN_ENTRIES) {
      const oldest = _planCache.keys().next().value
      _planCache.delete(oldest)
    }
    return value
  } catch (error) {
    const entry = _planCache.get(key)
    if (entry) {
      // A known (possibly stale) answer is better than none; the UI discloses it.
      return { ...entry.value, _cached: true, _stale: true }
    }
    throw error
  }
}

export async function fetchPathway(iso2) {
  if (FIXTURE) return iso2 === 'DE' ? captured.pathway_de : { iso2, steps: [], reason: 'Fixture only has DE.' }
  return handle(await fetch(`${API_BASE}/v2/strategist/pathway/${iso2}`))
}

export async function fetchGaps(adminSecret) {
  if (FIXTURE) {
    const gaps = []
    for (const plan of [captured.plan_cs, captured.plan_civil]) {
      for (const entry of plan.insufficient_data || []) {
        gaps.push({ country_iso2: entry.iso2 })
      }
    }
    return { gaps, subjects: ['computer_science', 'data_science', 'civil_engineering'], matrix: [] }
  }
  return handle(await fetch(`${API_BASE}/v2/strategist/gaps`, {
    headers: adminSecret ? { 'X-Admin-Secret': adminSecret } : {},
  }))
}
