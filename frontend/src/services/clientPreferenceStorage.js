const SAVED_SCHOLARSHIPS_KEY = 'scholarzone.saved-scholarship-ids.v1'
const COMPARE_SCHOLARSHIPS_KEY = 'scholarzone.compare-scholarship-ids.v1'

function normalizeId(value) {
  const normalized = String(value).trim()
  return /^[a-zA-Z0-9_-]{1,64}$/.test(normalized) ? normalized : null
}

function canUseStorage() {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined'
}

function readIdList(key, limit) {
  if (!canUseStorage()) {
    return []
  }

  try {
    const rawValue = window.localStorage.getItem(key)
    const parsedValue = rawValue ? JSON.parse(rawValue) : []

    if (!Array.isArray(parsedValue)) {
      return []
    }

    return [...new Set(parsedValue.map(normalizeId).filter(Boolean))].slice(0, limit)
  } catch {
    return []
  }
}

function writeIdList(key, ids, limit) {
  if (!canUseStorage()) {
    return
  }

  try {
    const safeIds = [...new Set(ids.map(normalizeId).filter(Boolean))].slice(0, limit)
    window.localStorage.setItem(key, JSON.stringify(safeIds))
  } catch {
    // Local preference storage is optional; the in-memory state remains usable.
  }
}

export const clientPreferenceStorage = {
  readSavedIds() {
    return readIdList(SAVED_SCHOLARSHIPS_KEY, 100)
  },

  writeSavedIds(ids) {
    writeIdList(SAVED_SCHOLARSHIPS_KEY, ids, 100)
  },

  readCompareIds() {
    return readIdList(COMPARE_SCHOLARSHIPS_KEY, 3)
  },

  writeCompareIds(ids) {
    writeIdList(COMPARE_SCHOLARSHIPS_KEY, ids, 3)
  },

  normalizeId,
}
