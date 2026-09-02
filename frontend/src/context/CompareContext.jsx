import { useEffect, useState } from 'react'
import { clientPreferenceStorage } from '../services/clientPreferenceStorage'
import { CompareContext, MAX_COMPARE_ITEMS } from './compareContext'

export function CompareProvider({ children }) {
  const [compareIds, setCompareIds] = useState(() => clientPreferenceStorage.readCompareIds())

  useEffect(() => {
    clientPreferenceStorage.writeCompareIds(compareIds)
  }, [compareIds])

  function isCompared(id) {
    const normalizedId = clientPreferenceStorage.normalizeId(id)
    return normalizedId ? compareIds.includes(normalizedId) : false
  }

  function toggleCompare(id) {
    const normalizedId = clientPreferenceStorage.normalizeId(id)

    if (!normalizedId) {
      return { action: 'invalid' }
    }

    if (compareIds.includes(normalizedId)) {
      setCompareIds((currentIds) => currentIds.filter((currentId) => currentId !== normalizedId))
      return { action: 'removed' }
    }

    if (compareIds.length >= MAX_COMPARE_ITEMS) {
      return { action: 'limit' }
    }

    setCompareIds((currentIds) => [...currentIds, normalizedId])
    return { action: 'added' }
  }

  function clearCompare() {
    setCompareIds([])
  }

  const value = {
    compareIds,
    isCompared,
    toggleCompare,
    clearCompare,
    maxItems: MAX_COMPARE_ITEMS,
  }

  return <CompareContext.Provider value={value}>{children}</CompareContext.Provider>
}
