// Static scholarship data service - loads from version-controlled JSON snapshot
// Used when the database/API is unavailable (e.g., Neon quota exceeded)

let cachedSnapshot = null;
let snapshotLoadPromise = null;

export async function loadScholarshipSnapshot() {
  if (cachedSnapshot) {
    return cachedSnapshot;
  }

  if (!snapshotLoadPromise) {
    snapshotLoadPromise = (async () => {
      try {
        const response = await fetch('/scholarships-snapshot.json', {
          headers: { Accept: 'application/json' },
        });
        if (!response.ok) {
          throw new Error(`Failed to load snapshot: ${response.status}`);
        }
        cachedSnapshot = await response.json();
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