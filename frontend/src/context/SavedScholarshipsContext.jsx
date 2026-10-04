import { useCallback, useEffect, useState } from 'react'
import { clientPreferenceStorage } from '../services/clientPreferenceStorage'
import { removeSavedScholarship, saveScholarship } from '../services/dashboardService'
import { useAuth } from '../hooks/useAuth'
import { SavedScholarshipsContext } from './savedScholarshipsContext'

/**
 * The shortlist, with a server of record when there is one.
 *
 * This context originally stored ids in localStorage and nothing else. That is
 * still exactly what happens for a signed-out visitor, because the shortlist is
 * on the public directory and an anonymous reader must be able to use it. What
 * changed is that a signed-in student's shortlist is authoritative on the
 * server: localStorage becomes a cache so the public pages stay instant, and it
 * is reconciled from the server on sign-in.
 *
 * The three original members - `savedIds`, `isSaved`, `toggleSaved` - keep their
 * meaning and their signatures. `isSaved` still answers for a local id, and
 * `toggleSaved` still returns a boolean success flag, so every existing consumer
 * (the card toggle, the detail page, the navigation count, /saved) works
 * unchanged whether or not anyone is signed in.
 *
 * A failed server write is rolled back rather than left as a lie: the button
 * would otherwise show "Saved" for something the account has not saved, and the
 * next page load would silently drop it.
 */
export function SavedScholarshipsProvider({ children }) {
  const [savedIds, setSavedIds] = useState(() => clientPreferenceStorage.readSavedIds())
  // Null means "no account to sync with". The visible sync state is derived from
  // it rather than written by the effect, so signing out cannot leave a stale
  // "syncing" behind and the effect body performs no synchronous setState.
  const [remoteSync, setRemoteSync] = useState(null)
  const { status } = useAuth()
  const isAuthenticated = status === 'authenticated'
  const syncState = isAuthenticated ? remoteSync || 'syncing' : 'idle'

  // localStorage keeps being written either way: it is the only store an
  // anonymous visitor has, and it is what makes the public pages instant for a
  // signed-in one.
  useEffect(() => {
    clientPreferenceStorage.writeSavedIds(savedIds)
  }, [savedIds])

  // Reconcile from the server when an account appears. This is the point where
  // localStorage stops being the source of truth: the server's list replaces it,
  // so signing in on a second device shows that device's shortlist rather than
  // whatever this browser happened to have cached.
  useEffect(() => {
    if (!isAuthenticated) {
      return
    }

    const controller = new AbortController()
    let cancelled = false

    fetch(`${import.meta.env.VITE_API_BASE_URL || '/api'}/dashboard/saved`, {
      credentials: 'include',
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    })
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error('unavailable'))))
      .then((payload) => {
        if (cancelled) return
        const ids = Array.isArray(payload.scholarship_ids) ? payload.scholarship_ids : []
        setSavedIds(ids.map((id) => clientPreferenceStorage.normalizeId(id)).filter(Boolean))
        setRemoteSync('synced')
      })
      .catch((error) => {
        if (cancelled || error.name === 'AbortError') return
        // Keep whatever is cached rather than blanking a shortlist because the
        // network blipped. It is clearly not authoritative, so say so.
        setRemoteSync('error')
      })

    return () => {
      cancelled = true
      controller.abort()
    }
  }, [isAuthenticated])

  const isSaved = useCallback(
    (id) => {
      const normalizedId = clientPreferenceStorage.normalizeId(id)
      return normalizedId ? savedIds.includes(normalizedId) : false
    },
    [savedIds],
  )

  const toggleSaved = useCallback(
    (id) => {
      const normalizedId = clientPreferenceStorage.normalizeId(id)

      if (!normalizedId) {
        return false
      }

      const willBeSaved = !savedIds.includes(normalizedId)

      // Optimistic, so the toggle stays instant on the public pages. The server
      // write below is what makes it durable, and it rolls back on failure.
      setSavedIds((currentIds) => (
        currentIds.includes(normalizedId)
          ? currentIds.filter((currentId) => currentId !== normalizedId)
          : [...currentIds, normalizedId]
      ))

      if (isAuthenticated) {
        setRemoteSync('syncing')
        const operation = willBeSaved ? saveScholarship(normalizedId) : removeSavedScholarship(normalizedId)

        operation
          .then(() => setRemoteSync('synced'))
          .catch(() => {
            setSavedIds((currentIds) => (
              willBeSaved
                ? currentIds.filter((currentId) => currentId !== normalizedId)
                : [...currentIds, normalizedId]
            ))
            setRemoteSync('error')
          })
      }

      return true
    },
    [savedIds, isAuthenticated],
  )

  const value = {
    savedIds,
    isSaved,
    toggleSaved,
    // Additive only. Existing consumers destructure the three members above and
    // ignore these.
    syncState,
  }

  return <SavedScholarshipsContext.Provider value={value}>{children}</SavedScholarshipsContext.Provider>
}