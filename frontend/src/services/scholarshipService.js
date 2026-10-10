const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

export class ScholarshipApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ScholarshipApiError'
    this.status = status
  }
}

function normalizeScholarship(scholarship) {
  return {
    ...scholarship,
    // The API keeps the existing display text while also returning deadline_date
    // for any future date-aware UI.
    deadline: scholarship.deadline ?? scholarship.deadline_date ?? null,
  }
}

function isAbortError(error) {
  return error instanceof DOMException && error.name === 'AbortError'
}

function isTimeoutError(error) {
  return error instanceof DOMException && error.name === 'TimeoutError'
}

/**
 * Determines if an error should trigger the static snapshot fallback.
 *
 * Every error is classified explicitly, and the classification is a total
 * function with a single answer per kind of failure. Nothing here is a
 * catch-all: an error this function does not recognise propagates unchanged
 * rather than being reported as network trouble, so a programming defect can
 * never be laundered into a successful snapshot response.
 *
 * Fall back ONLY for:
 * - Network failures (TypeError: offline, DNS, connection refused, CORS)
 * - Recognised timeout errors (TimeoutError)
 * - HTTP 5xx server errors (500, 502, 503, 504 and every other 5xx)
 *
 * Never fall back for:
 * - AbortError (the caller cancelled; it is their result, not a failure)
 * - Any other DOMException this module does not classify as a timeout
 * - HTTP 4xx client errors (400, 401, 403, 404, 422, ...)
 * - Anything else (programming, validation, snapshot-shape errors)
 */
function shouldFallbackToSnapshot(error) {
  // Caller cancellation is not a failure of the API and never a reason to
  // substitute different data. Treating every DOMException as a network
  // failure is exactly the bug that let a cancelled request fall back.
  if (isAbortError(error)) {
    return false
  }

  if (isTimeoutError(error)) {
    return true
  }

  // fetch rejects with TypeError for a genuine network failure. Nothing else
  // in this module raises TypeError.
  if (error instanceof TypeError) {
    return true
  }

  // Any remaining DOMException is unclassified, so it is not a known network
  // failure and must not trigger a fallback.
  if (error instanceof DOMException) {
    return false
  }

  if (error instanceof ScholarshipApiError) {
    return error.status >= 500 && error.status < 600
  }

  return false
}

/**
 * One HTTP request. `signal` is accepted but never supplied by a caller: the
 * three exported operations hand `request` no options, so the shared,
 * de-duplicated request is never bound to a single consumer's AbortSignal.
 * Cancellation is applied per-consumer in `dedupe` instead.
 */
async function request(path, searchParams, { signal } = {}) {
  const url = new URL(`${apiBaseUrl}${path}`, window.location.origin)

  if (searchParams) {
    Object.entries(searchParams).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '' && value !== 'All') {
        url.searchParams.set(key, value)
      }
    })
  }

  const response = await fetch(url, {
    signal,
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) {
    let message = 'Unable to load scholarships right now.'
    try {
      const payload = await response.json()
      if (typeof payload.detail === 'string') {
        message = payload.detail
      }
    } catch {
      // A non-JSON failure should still surface a safe, useful error.
    }
    throw new ScholarshipApiError(message, response.status)
  }

  return response.json()
}

/* ── In-flight de-duplication ─────────────────────────────────────────
   Three call sites on the home page want the same first page of the
   catalogue at the same moment — HomePage's directory, ScholarZoneHero's
   directory, and the featured list — plus a stats call from both HomePage and
   ScholarZoneHero. Each went straight to fetch, so one home page load issued
   six identical directory requests and two identical stats requests.
   Measured over the wire, not inferred.

   This is not a cache and not a state library. It is one module-level map
   from request key to the promise already in flight for it, cleared the
   moment that promise settles. Concurrent callers share one request; a
   caller arriving after it settles gets a fresh one. Nothing is stored
   between page loads, so freshness is unchanged.

   A caller that brings its own AbortSignal still shares the request, but
   only ever cancels its own wait for it. Handing the caller's signal to
   fetch would let one component unmounting abort the data another component
   is still reading — which is precisely the case here, since the two
   directory callers mount together and unmount at different times. So the
   shared request runs signal-less and each caller races it against its own
   abort. */
const inFlight = new Map()

function abortedError() {
  return new DOMException('The operation was aborted.', 'AbortError')
}

function dedupe(key, run, signal) {
  // An already-aborted caller is turned away before anything is created.
  //
  // `run()` is the only place a request is started, so this check has to
  // precede it. Checking after the in-flight entry is built would still reject
  // this caller promptly, but only after the request had already gone out -
  // which is the opposite of what a cancelled caller asked for, and which
  // leaves an entry in the map that no one is waiting on.
  if (signal && signal.aborted) {
    return Promise.reject(abortedError())
  }

  let shared = inFlight.get(key)

  if (!shared) {
    shared = run()
    inFlight.set(key, shared)

    // Both outcomes release, so a failure can never leave a rejected entry
    // behind for a later caller to inherit. The identity check stops a
    // replacement request - started by a caller who arrived after this one
    // settled - from being deleted by this one's late handler.
    const release = () => {
      if (inFlight.get(key) === shared) {
        inFlight.delete(key)
      }
    }

    shared.then(release, release)
  }

  if (!signal) {
    return shared
  }

  // The caller's signal guards only this caller's wait. The shared request
  // runs signal-less on purpose: handing one consumer's signal to fetch would
  // let that consumer's unmount abort the data another consumer is still
  // reading, which is the case here because the directory callers mount
  // together and unmount at different times.
  return new Promise((resolve, reject) => {
    const onAbort = () => reject(abortedError())

    if (signal.aborted) {
      onAbort()
      return
    }

    signal.addEventListener('abort', onAbort, { once: true })
    shared.then(
      (value) => {
        signal.removeEventListener('abort', onAbort)
        resolve(value)
      },
      (error) => {
        signal.removeEventListener('abort', onAbort)
        reject(error)
      },
    )
  })
}

/* ── Static snapshot fallback ──────────────────────────────────────────
   When the API is unavailable due to a server error (5xx) or network failure,
   we fall back to the version-controlled JSON snapshot. The snapshot contains
   all public scholarships (634 records) and stats, filtered by the canonical
   visibility predicate (excludes closed, archived, quarantined).
   
   CRITICAL: We do NOT fall back on 4xx errors (400, 401, 403, 404, 422).
   A stale snapshot must never resurrect a scholarship that the live API
   says is hidden, invalid, or unavailable.
   
   The snapshot is loaded once and cached in memory. Filtering, pagination,
   and sorting are performed client-side on the full dataset. */

import { loadScholarshipSnapshot } from './staticScholarshipService.js'

function filterScholarships(scholarships, query) {
  let filtered = [...scholarships]

  // Search filter
  if (query.search) {
    const search = query.search.toLowerCase()
    filtered = filtered.filter(s =>
      (s.title?.toLowerCase().includes(search)) ||
      (s.description?.toLowerCase().includes(search)) ||
      (s.country?.toLowerCase().includes(search)) ||
      (s.degree?.toLowerCase().includes(search)) ||
      (s.funding?.toLowerCase().includes(search))
    )
  }

  // Country filter
  if (query.country) {
    const country = query.country.toLowerCase()
    filtered = filtered.filter(s => s.country?.toLowerCase() === country)
  }

  // Degree filter
  if (query.degree) {
    const degree = query.degree.toLowerCase()
    filtered = filtered.filter(s => s.degree?.toLowerCase() === degree)
  }

  // Funding filter
  if (query.funding) {
    const funding = query.funding.toLowerCase()
    filtered = filtered.filter(s => s.funding?.toLowerCase() === funding)
  }

  // Deadline month filter
  if (query.deadline_month) {
    filtered = filtered.filter(s => {
      if (!s.deadline_date) return false
      const month = new Date(s.deadline_date).getMonth() + 1
      return month === query.deadline_month
    })
  }

  // Status filter
  if (query.status) {
    filtered = filtered.filter(s => s.status === query.status)
  }

  return filtered
}

/**
 * The membership test for the "fully funded" ordering, not a claim about
 * funding. It is exact equality, case-insensitively, because that is what the
 * repository's `_sort_expressions` uses to rank the live list; using a looser
 * test here would rank the same records differently during fallback.
 */
function isFullyFunded(funding) {
  return typeof funding === 'string' && funding.trim().toLowerCase() === 'fully funded'
}

function toTimestamp(value) {
  if (typeof value !== 'string' || value.trim() === '') {
    return null
  }

  const timestamp = Date.parse(value)
  return Number.isNaN(timestamp) ? null : timestamp
}

/**
 * Compare two timestamps so that a missing value sorts last, then break a
 * remaining tie by id. Both rules are deliberate: the repository's sort
 * expressions place NULL deadlines last and always finish with `id.asc()`, so
 * without them the fallback ordering would drift from the API's ordering
 * whenever a primary key ties - and `Array.prototype.sort` is stable, so the
 * tie would otherwise be settled by whatever order the snapshot happened to
 * be in rather than by anything the contract states.
 */
function compareNullableTimestamps(first, second, direction = 'asc') {
  if (first === null && second === null) {
    return 0
  }

  if (first === null) {
    return 1
  }

  if (second === null) {
    return -1
  }

  return direction === 'asc' ? first - second : second - first
}

/**
 * Place a record with no deadline after one that has it, and say nothing
 * about the order of two records that both have one.
 *
 * This must return 0 when both values are present. Delegating to
 * `compareNullableTimestamps` instead would return the difference between the
 * two dates, which silently overrides the direction the caller asked for:
 * `deadline-latest` sorted ascending because its own descending comparison
 * was never reached.
 */
function nullDeadlineLast(a, b) {
  const aHas = toTimestamp(a.deadline_date) !== null
  const bHas = toTimestamp(b.deadline_date) !== null
  if (aHas === bHas) {
    return 0
  }
  return aHas ? -1 : 1
}

function byId(a, b) {
  return a.id - b.id
}

/**
 * Comparators for the modes whose keys are public fields.
 *
 * Each mirrors the repository's `_sort_expressions` entry, key by key, in the
 * same order, with the same NULL placement and the same `id` tie-break. They
 * are the fallback used when the snapshot has no precomputed ordering for a
 * mode, so they have to stay equivalent to the SQL - but they are not the
 * preferred path, and a difference between them and the generated order is a
 * defect rather than something to paper over.
 */
const COMPARATORS = {}

/** Status priority for the recommended ordering: open, then closing-soon, then the rest. */
function statusPriority(status) {
  const order = { open: 0, 'closing-soon': 1 }
  return order[status] ?? 2
}

COMPARATORS.recommended = (a, b) => {
  // `is_verified DESC` is the legacy column. The public `verified` flag is
  // derived from `verification_status` instead and disagrees on some rows, so a
  // comparator built on it is an approximation of this ordering.
  const aVerified = a.verified === true
  const bVerified = b.verified === true
  if (aVerified !== bVerified) return bVerified - aVerified
  const aStatus = statusPriority(a.status)
  const bStatus = statusPriority(b.status)
  if (aStatus !== bStatus) return aStatus - bStatus
  return compareNullableTimestamps(toTimestamp(a.updated_at), toTimestamp(b.updated_at), 'desc')
    || byId(a, b)
}

COMPARATORS['recently-added'] = (a, b) => {
  // The API orders by `created_at DESC`. `created_at` is not a public field, so
  // when no precomputed order is available this comparator can only use a
  // timestamp the snapshot actually carries, and the resulting order is an
  // approximation - see SORT_MODES in generate_snapshot.py.
  return compareNullableTimestamps(
    toTimestamp(a.created_at || a.updated_at),
    toTimestamp(b.created_at || b.updated_at),
    'desc',
  ) || byId(a, b)
}

COMPARATORS['recently-updated'] = (a, b) =>
  compareNullableTimestamps(toTimestamp(a.updated_at), toTimestamp(b.updated_at), 'desc')
  || byId(a, b)

COMPARATORS['deadline-soon'] = (a, b) => nullDeadlineLast(a, b)
  || compareNullableTimestamps(toTimestamp(a.deadline_date), toTimestamp(b.deadline_date))
  || byId(a, b)

COMPARATORS['deadline-earliest'] = COMPARATORS['deadline-soon']

COMPARATORS['deadline-latest'] = (a, b) => nullDeadlineLast(a, b)
  || compareNullableTimestamps(toTimestamp(a.deadline_date), toTimestamp(b.deadline_date), 'desc')
  || byId(a, b)

COMPARATORS['fully-funded'] = (a, b) => {
  // Exact equality, case-insensitively - the repository's
  // `case(func.lower(funding) == "fully funded", 0, else_=1)` and the same test
  // ScholarshipList uses. A substring test would admit rows such as
  // "Fully Funded (4-year bond)" to the funded group that the API places
  // outside it.
  const aFully = isFullyFunded(a.funding)
  const bFully = isFullyFunded(b.funding)
  if (aFully !== bFully) return bFully - aFully
  return compareNullableTimestamps(toTimestamp(a.updated_at), toTimestamp(b.updated_at), 'desc')
    || byId(a, b)
}

COMPARATORS['name-asc'] = (a, b) =>
  String(a.title || '').localeCompare(String(b.title || ''), undefined, { sensitivity: 'base' })
  || byId(a, b)

COMPARATORS['name-desc'] = (a, b) =>
  String(b.title || '').localeCompare(String(a.title || ''), undefined, { sensitivity: 'base' })
  || byId(a, b)

COMPARATORS.default = COMPARATORS.recommended

/**
 * Compare by a precomputed ordering of ids.
 *
 * The ordering is a total order over the whole public set, so filtering first
 * and then applying this index yields the same relative order the API produces
 * for that filtered subset - the API applies its ORDER BY to the filtered rows,
 * and restricting a total order preserves relative position.
 *
 * An id absent from the ordering is placed after every known id and then by id
 * ascending, so a snapshot that is stale for a subset of records cannot throw
 * away those records or put them in a random position. That is deliberately
 * defensive rather than an error: the alternative is an empty page.
 */
function sortWithPrecomputedOrder(scholarships, sort, snapshot) {
  const order = snapshot && Array.isArray(snapshot?.meta?.sort_orders?.[sort])
    ? snapshot.meta.sort_orders[sort]
    : null

  if (!order) {
    return null
  }

  const rank = new Map()
  order.forEach((id, index) => {
    const numeric = Number(id)
    if (!rank.has(numeric)) {
      rank.set(numeric, index)
    }
  })

  const rankOf = (record) => {
    const numeric = Number(record.id)
    return rank.has(numeric) ? rank.get(numeric) : Number.MAX_SAFE_INTEGER
  }

  return [...scholarships].sort((a, b) => {
    const rankDelta = rankOf(a) - rankOf(b)
    if (rankDelta !== 0) {
      return rankDelta
    }
    // Both unranked, or - defensively - a duplicate id in the ordering.
    return byId(a, b)
  })
}

function sortScholarships(scholarships, sort, snapshot) {
  const mode = sort || 'default'

  // Preferred path: the ordering the generator computed with the repository's
  // own ORDER BY expressions. Using it means the fallback list is in the live
  // API's order, including for the two modes whose sort keys are not public
  // fields and could not otherwise be reproduced.
  const ordered = sortWithPrecomputedOrder(scholarships, mode, snapshot)
  if (ordered) {
    return ordered
  }

  const comparator = COMPARATORS[mode]
  if (comparator) {
    return [...scholarships].sort(comparator)
  }

  // An unrecognised mode is not silently mapped to some other order; it falls
  // through to the recommended comparator below, which is what the repository's
  // `_sort_expressions` does for an unrecognised enum value.
  return [...scholarships].sort(COMPARATORS.default)
}

function paginate(scholarships, page, limit) {
  const total = scholarships.length
  const total_pages = Math.ceil(total / limit) || 0
  const offset = (page - 1) * limit
  const items = scholarships.slice(offset, offset + limit)
  return { items, pagination: { page, limit, total, total_pages } }
}

async function tryApiThenSnapshot(key, send, fallbackFn, options) {
  try {
    return await dedupe(key, send, options?.signal)
  } catch (apiError) {
    if (!shouldFallbackToSnapshot(apiError)) {
      throw apiError
    }
    // Only network, timeout and 5xx failures reach here. A snapshot failure is
    // NOT classified as an API failure: it propagates from `fallbackFn` with
    // its own message, so a broken snapshot cannot masquerade as the API
    // being down.
    console.warn(
      'API unavailable (network/timeout/5xx), falling back to static snapshot:',
      apiError.message,
    )
    return await fallbackFn()
  }
}

export async function fetchScholarships(query = {}, options) {
  // The key is built from a sorted key list so that two callers who pass the
  // same filters in a different property order still share one request.
  const key = `list:${JSON.stringify(query, Object.keys(query).sort())}`
  
  // Try API first
  const send = () =>
    request('/scholarships', query).then((payload) => ({
      items: Array.isArray(payload.items) ? payload.items.map(normalizeScholarship) : [],
      pagination: payload.pagination,
      source: 'api',
    }))

  const fallbackFn = async () => {
    const snapshot = await loadScholarshipSnapshot()
    const allScholarships = snapshot.scholarships || []

    // Filter first, then order. The snapshot's precomputed orderings are total
    // orders over the whole public set, so restricting one to a filtered subset
    // keeps the same relative order the API gives that subset - the API applies
    // its ORDER BY to the rows its filters leave, which is the same thing.
    let filtered = filterScholarships(allScholarships, query)
    filtered = sortScholarships(filtered, query.sort || 'default', snapshot)
    const result = paginate(filtered, query.page || 1, query.limit || 12)

    return {
      items: result.items.map(normalizeScholarship),
      pagination: result.pagination,
      source: 'snapshot',
      snapshot_meta: snapshot.meta,
    }
  }

  return tryApiThenSnapshot(key, send, fallbackFn, options)
}

export async function fetchScholarshipById(id, options) {
  const key = `detail:${id}`

  const send = () =>
    request(`/scholarships/${encodeURIComponent(id)}`, undefined)
      .then(normalizeScholarship)

  const fallbackFn = async () => {
    const snapshot = await loadScholarshipSnapshot()
    // Compared numerically as well as by identity. Callers reach this from a
    // route parameter, which React Router supplies as a string, while the
    // snapshot carries integer ids exactly as the database does. Strict
    // equality alone would make a string request miss a record the live API
    // finds, and the two paths would then disagree about whether it exists.
    const numericId = Number(id)
    const scholarship = (snapshot.scholarships || []).find(
      s => s.id === id || (Number.isFinite(numericId) && s.id === numericId),
    )

    // CRITICAL: A stale snapshot must never resurrect a scholarship
    // that the live API says is hidden or unavailable.
    // If the API returned 404, we don't fall back - we propagate the 404.
    // This fallback only runs for 5xx/network errors, so by definition
    // the live API couldn't give us a definitive 404.
    if (!scholarship) {
      throw new ScholarshipApiError('Scholarship not found in snapshot', 404)
    }

    return normalizeScholarship({ ...scholarship, _source: 'snapshot' })
  }

  return tryApiThenSnapshot(key, send, fallbackFn, options)
}

export async function fetchScholarshipStats(options) {
  const key = 'stats'

  const send = () =>
    request('/scholarships/stats', undefined)

  const fallbackFn = async () => {
    const snapshot = await loadScholarshipSnapshot()
    const meta = { ...(snapshot.meta || {}) }
    // The orderings are list-shape data: nine arrays of every public id, needed
    // to reproduce the API's ordering and of no use to a counts consumer. They
    // are left out here so a stats response stays about counts, rather than
    // carrying the ordering of the whole catalogue with it.
    delete meta.sort_orders

    return {
      ...snapshot.stats,
      source: 'snapshot',
      snapshot_meta: meta,
    }
  }

  return tryApiThenSnapshot(key, send, fallbackFn, options)
}