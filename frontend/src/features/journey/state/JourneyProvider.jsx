import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react'
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
 * Three responsibilities live here and nowhere else:
 *
 * 1. **Hydrating from storage exactly once.** The initial state comes from
 *    `loadJourneyState`, which normalises or falls back to defaults. A bad read
 *    becomes a `problem`, never a crash.
 * 2. **Debounced persistence with honest failure reporting.** A write that is
 *    refused is surfaced as `storageNotice` rather than swallowed, so the
 *    workspace can say "progress cannot be saved" instead of implying otherwise.
 * 3. **Cross-tab coherence.** The `storage` event is the only signal that
 *    another tab changed this feature's key. It is applied only when the payload
 *    is newer than the last write this tab performed, which is what stops a
 *    reload of an older tab from reverting a newer edit.
 */
export function JourneyProvider({ children }) {
  /**
   * The one-time storage read.
   *
   * A lazy `useState` initialiser rather than a `useRef` populated during
   * render: React's rules treat reading a ref during render as unsafe, and the
   * provider would otherwise read the store twice under StrictMode while
   * reporting the same values. The initialiser runs once, on mount, and its
   * result is ordinary state afterwards.
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
  /** The timestamp of the most recent payload this tab observed, for cross-tab ordering. */
  const lastWriteRef = useRef(null)
  const pendingTimerRef = useRef(null)
  /**
   * Set when a deliberate action (reset) has just removed the stored data, so
   * the effect that would otherwise write the resulting default document does
   * not recreate the key the student just emptied.
   */
  const suppressPersistRef = useRef(false)

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

    pendingTimerRef.current = window.setTimeout(() => {
      pendingTimerRef.current = null
      try {
        saveJourneyState(state)
        lastWriteRef.current = new Date().toISOString()
        setStorageProblem(null)
        setStorageAvailable(true)
        setLastSavedAt(lastWriteRef.current)
      } catch (error) {
        // A steady inability to write is a notice, not an error state: the
        // workspace stays usable and the student can still export.
        setStorageProblem(error?.reason === 'quota-exceeded' ? 'quota-exceeded' : 'unavailable')
        setStorageAvailable(false)
      }
    }, PERSIST_DEBOUNCE_MS)

    return () => {
      if (pendingTimerRef.current) {
        window.clearTimeout(pendingTimerRef.current)
        pendingTimerRef.current = null
      }
    }
    // `bootstrap.state` is a lazy-initialiser result that never changes, so it
    // is stable across renders by construction rather than by the dep array.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state])

  /**
   * Cancel a pending write without performing it.
   *
   * Deliberately does not write the current state first. A write would be
   * pointless work, and a queued write firing after a delete would resurrect
   * data the student just removed — the classic debounce race, where the old
   * payload lands after the deliberate action.
   */
  const cancelPendingWrite = useCallback(() => {
    if (pendingTimerRef.current) {
      window.clearTimeout(pendingTimerRef.current)
      pendingTimerRef.current = null
    }
  }, [])

  /** Persist immediately, reporting failure rather than swallowing it. */
  const flushPendingWrite = useCallback(() => {
    cancelPendingWrite()
    try {
      saveJourneyState(state)
      lastWriteRef.current = new Date().toISOString()
      setStorageProblem(null)
      setStorageAvailable(true)
      setLastSavedAt(lastWriteRef.current)
      return true
    } catch (error) {
      setStorageProblem(error?.reason === 'quota-exceeded' ? 'quota-exceeded' : 'unavailable')
      setStorageAvailable(false)
      return false
    }
  }, [cancelPendingWrite, state])

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
    cancelPendingWrite()
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
  }, [cancelPendingWrite])

  const replaceDocument = useCallback(
    (document) => {
      cancelPendingWrite()
      const next = normalizeJourneyDocument(document)
      dispatch({ type: ACTIONS.HYDRATE, payload: next })
      return next
    },
    [cancelPendingWrite],
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
      flushPendingWrite,
      exportJson: () => buildExport(state),
    }),
    [state, storageAvailable, storageProblem, lastSavedAt, setLanguage, reset, replaceDocument, flushPendingWrite],
  )

  return <JourneyContext.Provider value={value}>{children}</JourneyContext.Provider>
}
