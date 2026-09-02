import { useEffect, useState } from 'react'
import { clientPreferenceStorage } from '../services/clientPreferenceStorage'
import { SavedScholarshipsContext } from './savedScholarshipsContext'

export function SavedScholarshipsProvider({ children }) {
  const [savedIds, setSavedIds] = useState(() => clientPreferenceStorage.readSavedIds())

  useEffect(() => {
    clientPreferenceStorage.writeSavedIds(savedIds)
  }, [savedIds])

  function isSaved(id) {
    const normalizedId = clientPreferenceStorage.normalizeId(id)
    return normalizedId ? savedIds.includes(normalizedId) : false
  }

  function toggleSaved(id) {
    const normalizedId = clientPreferenceStorage.normalizeId(id)

    if (!normalizedId) {
      return false
    }

    setSavedIds((currentIds) => (
      currentIds.includes(normalizedId)
        ? currentIds.filter((currentId) => currentId !== normalizedId)
        : [...currentIds, normalizedId]
    ))

    return true
  }

  const value = {
    savedIds,
    isSaved,
    toggleSaved,
  }

  return <SavedScholarshipsContext.Provider value={value}>{children}</SavedScholarshipsContext.Provider>
}
