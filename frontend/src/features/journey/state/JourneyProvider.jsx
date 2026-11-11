import { useCallback, useEffect, useLayoutEffect, useMemo, useReducer, useRef, useState } from 'react'
import { JourneyContext } from './journeyContext.js'
import { ACTIONS, journeyReducer } from './journeyReducer.js'
import {
  canUseStorage,
  loadJourneyState,
  saveJourneyState,
  resetJourneyStorage,
  buildExport,
} from '../lib/journeyStorage.js'
import { normalizeJourneyDocument } from '../lib/journeySchema.js'
import { LANGUAGE_MODES } from '../i18n/strings.js'

/** Debounce window for a write. Long enough to coalesce typing, short enough to
 *  bound the loss if the tab dies. */
const PERSIST_DEBOUNCE_MS = 400

/**
 * Provider for the Bangladesh Applicant Journey.
 *
 * Responsibilities:
 * 1. Hydrating from storage once on mount.
 * 2. Debounced persistence with honest failure reporting.
 * 3. Unmount-safe persistence: latest state is saved synchronously when the
 *    provider unmounts (e.g., navigating away from journey routes).
 * 4. Visibility/pagehide persistence: flushes latest state when page is hidden
 *    or about to unload.
 * 5. Cross-tab coherence via storage events.
 */
export function JourneyProvider({ children }) {
  /**
   * The one-time storage read.
   */
  const [bootstrap] = useState(() => {
    const loaded = loadJourneyState()
    return {
      state: loaded.state,
      problem: loaded.problem,
      available: canUseStorage(),
    }
  })

  const [state, dispatch] = useReducer(journeyReducer, bootstrap.state)
  const [storageProblem, setStorageProblem] = useState(bootstrap.problem)
  const [storageAvailable, setStorageAvailable] = useState(bootstrap.available)
  const [lastSavedAt, setLastSavedAt] = useState(null)

  /** Tracks whether provider is currently mounted to guard setState in unmount paths. */
  const isMountedRef = useRef(true)

  /** Always holds the latest state reference to prevent persisting stale closures. */
  const latestStateRef = useRef(state)

  useLayoutEffect(() => {
    latestStateRef.current = state
  }, [state])

  /** Tracks unpersisted edits that must be flushed on unmount/pagehide. */
  const isDirtyRef = useRef(false)

  /** Timestamp of most recent write by this tab, for cross-tab ordering. */
  const lastWriteRef = useRef(null)
  const pendingTimerRef = useRef(null)

  /**
   * Set when a deliberate action (reset) has just removed the stored data, so
   * subsequent effects/unmount do not recreate the emptied key.
   */
  const suppressPersistRef = useRef(false)

  /**
   * Synchronously persists a document to storage and updates state/ref metadata.
   * Safe to call during unmount (bypasses setState when unmounted).
   */
  const performSave = useCallback((stateToSave) => {
    if (!stateToSave) return false
    try {
      saveJourneyState(stateToSave)
      lastWriteRef.current = new Date().toISOString()
      isDirtyRef.current = false
      if (isMountedRef.current) {
        setStorageProblem(null)
        setStorageAvailable(true)
        setLastSavedAt(lastWriteRef.current)
      }
      return true
    } catch (error) {
      if (isMountedRef.current) {
        setStorageProblem(error?.reason === 'quota-exceeded' ? 'quota-exceeded' : 'unavailable')
        setStorageAvailable(false)
      }
      return false
    }
  }, [])

  /* Persist, debounced. A failed write leaves the state on screen and raises a
     notice; it never reverts what the student just entered. */
  useEffect(() => {
    if (state === bootstrap.state) return undefined
    if (suppressPersistRef.current) {
      // The state is the deliberate result of a reset, and the store has already
      // been emptied. Writing it back would recreate a key with no content.
      suppressPersistRef.current = false
      return undefined
    }

    if (pendingTimerRef.current) {
      window.clearTimeout(pendingTimerRef.current)
    }

    isDirtyRef.current = true

    pendingTimerRef.current = window.setTimeout(() => {
      pendingTimerRef.current = null
      performSave(state)
    }, PERSIST_DEBOUNCE_MS)

    return () => {
      if (pendingTimerRef.current) {
        window.clearTimeout(pendingTimerRef.current)
        pendingTimerRef.current = null
        // Only flush if we have unpersisted edits AND we're not suppressing (reset)
        if (isDirtyRef.current && !suppressPersistRef.current) {
          performSave(latestStateRef.current)
        }
      }
    }
  }, [state, bootstrap.state, performSave])

  /**
   * Flush any pending write immediately. Returns true on success.
   * Safe to call multiple times.
   */
  const doFlush = useCallback(() => {
    if (pendingTimerRef.current) {
      window.clearTimeout(pendingTimerRef.current)
      pendingTimerRef.current = null
    }
    return performSave(latestStateRef.current)
  }, [performSave])

  /**
   * Flush pending writes when the page is about to unload or become hidden.
   * This prevents data loss when the user closes the tab, navigates away,
   * or switches tabs within the debounce window.
   */
  useEffect(() => {
    if (typeof window === 'undefined') return undefined

    const handlePageHide = () => {
      doFlush()
    }

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        handlePageHide()
      }
    }

    const handleBeforeUnload = () => {
      handlePageHide()
    }

    window.addEventListener('pagehide', handlePageHide)
    document.addEventListener('visibilitychange', handleVisibilityChange)
    window.addEventListener('beforeunload', handleBeforeUnload)

    return () => {
      window.removeEventListener('pagehide', handlePageHide)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      window.removeEventListener('beforeunload', handleBeforeUnload)
    }
  }, [doFlush])

  /**
   * Reflect the display mode on the document, because the page is Bangla-first
   * in `both` and `bn` and screen readers switch dictionaries on `lang`.
   */
  useEffect(() => {
    if (typeof document === 'undefined') return undefined
    document.documentElement.lang = state.settings.language === 'en' ? 'en' : 'bn'
    return undefined
  }, [state.settings.language])

  /* Cross-tab change. Applied only when the incoming payload is newer than the
     last write this tab made, so an older tab cannot revert a newer edit. The
     ordering signal is `exportedAt`, which a save always carries and a reset
     removes entirely — the remove case is handled above it. */
  useEffect(() => {
    if (typeof window === 'undefined') return undefined

    const onStorage = (event) => {
      if (event.key !== null && !String(event.key).includes('bangladesh-journey')) return
      if (event.newValue === null || event.newValue === undefined) {
        // Another tab reset this feature. Reload our own view of it.
        const reloaded = loadJourneyState()
        dispatch({ type: ACTIONS.HYDRATE, payload: reloaded.state })
        setStorageProblem(reloaded.problem)
        return
      }
      let parsed
      try {
        parsed = JSON.parse(event.newValue)
      } catch {
        return
      }
      const incoming = new Date(parsed?.exportedAt ?? 0).getTime()
      const mine = new Date(lastWriteRef.current ?? 0).getTime()
      if (!Number.isFinite(incoming) || incoming <= mine) return
      dispatch({ type: ACTIONS.HYDRATE, payload: parsed })
    }

    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  const setLanguage = useCallback((language) => {
    dispatch({ type: ACTIONS.SET_LANGUAGE, payload: LANGUAGE_MODES.includes(language) ? language : 'both' })
  }, [])

  const reset = useCallback(() => {
    // Cancel first so a queued debounce cannot restore the state just removed.
    if (pendingTimerRef.current) {
      window.clearTimeout(pendingTimerRef.current)
      pendingTimerRef.current = null
    }
    const result = resetJourneyStorage()
    dispatch({ type: ACTIONS.RESET })
    // The post-reset state is the default document, which is what an empty store
    // means; writing it back would recreate a key the student just emptied.
    suppressPersistRef.current = true
    if (!result.ok && result.reason === 'unavailable') {
      setStorageAvailable(false)
      setStorageProblem('unavailable')
    }
    return result
  }, [])

  const replaceDocument = useCallback(
    (document) => {
      if (pendingTimerRef.current) {
        window.clearTimeout(pendingTimerRef.current)
        pendingTimerRef.current = null
      }
      const next = normalizeJourneyDocument(document)
      dispatch({ type: ACTIONS.HYDRATE, payload: next })
      return next
    },
    [],
  )

  const value = useMemo(
    () => ({
      state,
      dispatch,
      actions: ACTIONS,
      storage: {
        available: storageAvailable,
        problem: storageProblem,
        lastSavedAt,
      },
      setLanguage,
      reset,
      replaceDocument,
      flushPendingWrite: doFlush,
      exportJson: () => buildExport(state),
    }),
    [state, storageAvailable, storageProblem, lastSavedAt, setLanguage, reset, replaceDocument, doFlush],
  )

  // Track mount state for setState guards
  useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
    }
  }, [])

  return <JourneyContext.Provider value={value}>{children}</JourneyContext.Provider>
}