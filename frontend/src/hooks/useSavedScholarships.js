import { useContext } from 'react'
import { SavedScholarshipsContext } from '../context/savedScholarshipsContext'

export function useSavedScholarships() {
  const context = useContext(SavedScholarshipsContext)

  if (!context) {
    throw new Error('useSavedScholarships must be used inside a SavedScholarshipsProvider.')
  }

  return context
}
