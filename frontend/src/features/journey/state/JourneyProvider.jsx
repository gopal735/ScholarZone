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
 * Origin of a state transition. Used by the persistence effect to decide
 * whether a state change represents a real user edit that should be persisted.
 * - 'user': Genuine user interaction (typing, clicking, etc.) -> PERSIST
 * - 'hydrate': Initial load or cross-tab normal hydration -> DO NOT PERSIST
 * - 'reset': Local explicit reset or cross-tab reset -> DO NOT PERSIST
 * - 'replace-document': Programmatic replaceDocument call -> DO NOT PERSIST
 */
const StateOrigin = {
  USER: 'user',
  HYDRATE: 'hydrate',
  RESET: 'reset',
  REPLACE_DOCUMENT: 'replace-document',
}

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
 *
 * Lifecycle Model:
 * - Each state change is tagged with its origin via `pendingOriginRef`.
 * - The persistence effect ONLY persists changes with origin === 'user'.
 * - All programmatic transitions (hydrate, reset, replace-document) are
 *   explicitly marked and never persisted.
 * - After a reset, the first user edit gets origin 'user' and persists normally.
 * - Cross-tab reset is treated as a 'reset' origin hydration.
 * - replaceDocument is treated as 'replace-document' origin hydration.
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

  /** Immutable initial state captured once, used in unmount comparisons. */
  const initialStateRef = useRef(bootstrap.state)

  useLayoutEffect(() => {
    latestStateRef.current = state
  }, [state])

  /** Tracks unpersisted edits that must be flushed on unmount/pagehide. */
  const isDirtyRef = useRef(false)

  /** Timestamp of most recent write by this tab, for cross-tab ordering. */
  const lastWriteRef = useRef(null)
  const pendingTimerRef = useRef(null)

  /**
   * Origin of the pending state transition. Set before dispatching an action
   * that will cause a state change. Read by the persistence effect to decide
   * whether to persist. Cleared after the effect processes the change.
   * Null means no pending transition (steady state).
   */
  const pendingOriginRef = useRef(null)

  /**
   * Tracks whether a reset has occurred and no user edit has happened since.
   * Prevents unmount/pagehide from recreating deleted storage.
   * Cleared when a user edit occurs.
   */
  const resetOccurredRef = useRef(false)

  /**
   * Synchronously persists a document to storage and updates state/ref metadata.
   * Safe to call during unmount (bypasses setState when unmounted).
   */
  const performSave = useCallback((stateToSave) => {
    if (!stateToSave) return false
    if (resetOccurredRef.current) return false
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
     notice; it never reverts what the student just entered.

     The effect runs on every state change. It reads `pendingOriginRef.current`
     to determine the origin of the transition:
     - 'user': real user edit -> persist (debounced)
     - 'hydrate', 'reset', 'replace-document': programmatic -> never persist
     - null: no explicit origin set -> treat as user edit (default for dispatch from UI)
     
     After processing, pendingOriginRef is cleared. */

  useEffect(() => {
    if (state === bootstrap.state) return undefined

    const origin = pendingOriginRef.current
    pendingOriginRef.current = null

    // Programmatic transitions never persist
    if (origin === StateOrigin.HYDRATE || origin === StateOrigin.RESET || origin === StateOrigin.REPLACE_DOCUMENT) {
      // After a reset hydration, the first user edit should persist.
      // resetOccurredRef stays true until a user edit occurs.
      // Cross-tab normal hydration does not set resetOccurredRef.
      return undefined
    }

    // Real user edit (origin === 'user' or null/undefined meaning dispatched from UI)
    // A real user edit after reset: clear reset flag so future unmount/pagehide can flush
    resetOccurredRef.current = false

    if (pendingTimerRef.current) {
      window.clearTimeout(pendingTimerRef.current)
      pendingTimerRef.current = null
    }

    isDirtyRef.current = true

    pendingTimerRef.current = window.setTimeout(() => {
      pendingTimerRef.current = null
      performSave(latestStateRef.current)
    }, PERSIST_DEBOUNCE_MS)

    return () => {
      if (pendingTimerRef.current) {
        window.clearTimeout(pendingTimerRef.current)
        pendingTimerRef.current = null
      }
    }
  }, [state, bootstrap.state, performSave])

  /**
   * Flush any pending write immediately. Returns true on success.
   * Safe to call multiple times. Does not recreate storage after reset.
   * Only flushes if the current dirty state originated from a user edit.
   */
  const doFlush = useCallback(() => {
    if (pendingTimerRef.current) {
      window.clearTimeout(pendingTimerRef.current)
      pendingTimerRef.current = null
    }
    if (!isDirtyRef.current || resetOccurredRef.current) return false
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
        doFlush()
      }
    }

    const handleBeforeUnload = () => {
      doFlush()
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
        isDirtyRef.current = false
        resetOccurredRef.current = true
        pendingOriginRef.current = StateOrigin.RESET
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
      // Cross-tab normal hydration (not a reset): treat as programmatic hydration
      pendingOriginRef.current = StateOrigin.HYDRATE
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
    // Mark clean/suppressed before dispatch so no pending or subsequent lifecycle
    // flush can recreate the deleted key.
    isDirtyRef.current = false
    resetOccurredRef.current = true
    pendingOriginRef.current = StateOrigin.RESET
    dispatch({ type: ACTIONS.RESET })
    if (!result.ok && result.reason === 'unavailable') {
      setStorageAvailable(false)
      setStorageProblem('unavailable')
    }
    return result
  }, [])

  const replaceDocument = useCallback((document) => {
    if (pendingTimerRef.current) {
      window.clearTimeout(pendingTimerRef.current)
      pendingTimerRef.current = null
    }
    isDirtyRef.current = false
    pendingOriginRef.current = StateOrigin.REPLACE_DOCUMENT
    const next = normalizeJourneyDocument(document)
    dispatch({ type: ACTIONS.HYDRATE, payload: next })
    // Schedule a debounced save for the imported document.
    // The persistence effect skips REPLACE_DOCUMENT origin, so we
    // schedule the save here. This is a programmatic save, not a
    // user edit, but the document should still be persisted.
    isDirtyRef.current = true
    pendingTimerRef.current = window.setTimeout(() => {
      pendingTimerRef.current = null
      performSave(latestStateRef.current)
    }, PERSIST_DEBOUNCE_MS)
    return next
  }, [performSave])

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

  // Track mount state and flush dirty state on actual provider unmount only.
  // This cleanup runs when the provider unmounts, not on state changes.
  useEffect(() => {
    isMountedRef.current = true
    const initialState = initialStateRef.current
    return () => {
      isMountedRef.current = false
      if (pendingTimerRef.current) {
        window.clearTimeout(pendingTimerRef.current)
        pendingTimerRef.current = null
      }
      // Flush the latest state on unmount if there are unsaved changes.
      // Never flush after an explicit reset (would recreate deleted data).
      if (!resetOccurredRef.current && latestStateRef.current && latestStateRef.current !== initialState) {
        try {
          saveJourneyState(latestStateRef.current)
          isDirtyRef.current = false
        } catch {
          // Cannot update React state after unmount; storage write is best-effort.
        }
      }
    }
  }, [])

  return <JourneyContext.Provider value={value}>{children}</JourneyContext.Provider>
}
