// Static scholarship data service - loads from version-controlled JSON snapshot
// Used when the database/API is unavailable (e.g., Neon quota exceeded)

let cachedSnapshot = null;
let snapshotLoadPromise = null;

/**
 * The URL of the snapshot asset, resolved against the build's base path.
 *
 * The path was hardcoded as '/scholarships-snapshot.json', which only resolves
 * on a deployment served from the domain root. The GitHub Pages build sets
 * base to '/ScholarZone/' (see vite.config.js), so on that deployment the
 * hardcoded URL resolved to the wrong origin path and 404ed - meaning the
 * fallback that exists to keep the catalogue browsable was itself broken
 * there. Deriving it from import.meta.env.BASE_URL makes it correct on every
 * deployment target, because that is the same value Vite used to rewrite the
 * asset URLs in the bundle.
 *
 * BASE_URL is always defined by Vite and always ends in '/', but it is
 * guarded so a non-Vite host cannot turn a missing constant into a crash.
 */
function getSnapshotUrl() {
  const baseUrl = typeof import.meta !== 'undefined' && import.meta.env
    ? import.meta.env.BASE_URL
    : undefined;

  if (typeof baseUrl !== 'string' || baseUrl === '') {
    return '/scholarships-snapshot.json';
  }

  return `${baseUrl.replace(/\/+$/, '')}/scholarships-snapshot.json`;
}

/**
 * Reject a response body that is not usable as a snapshot.
 *
 * A 200 whose body is an HTML error page, an empty file or a JSON object with
 * no records would previously have been cached and returned as a valid empty
 * catalogue. Caching it made that permanent for the page's lifetime: every
 * later fallback would then report "no scholarships" rather than recovering.
 */
function assertSnapshotShape(payload) {
  if (payload === null || typeof payload !== 'object' || Array.isArray(payload)) {
    throw new Error('Snapshot payload is not an object.');
  }

  if (!Array.isArray(payload.scholarships)) {
    throw new Error('Snapshot payload has no scholarships array.');
  }

  return payload;
}

export async function loadScholarshipSnapshot() {
  if (cachedSnapshot) {
    return cachedSnapshot;
  }

  if (!snapshotLoadPromise) {
    snapshotLoadPromise = (async () => {
      try {
        const response = await fetch(getSnapshotUrl(), {
          headers: { Accept: 'application/json' },
        });
        if (!response.ok) {
          throw new Error(`Failed to load snapshot: ${response.status}`);
        }
        // Validated before it is cached, so a malformed body is never stored
        // and a later call is free to retry.
        cachedSnapshot = assertSnapshotShape(await response.json());
        return cachedSnapshot;
      } catch (error) {
        snapshotLoadPromise = null;
        throw error;
      }
    })();
  }

  return snapshotLoadPromise;
}

export function getCachedSnapshot() {
  return cachedSnapshot;
}

export function clearSnapshotCache() {
  cachedSnapshot = null;
  snapshotLoadPromise = null;
}
