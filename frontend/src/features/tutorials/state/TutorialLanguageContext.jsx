import { useCallback, useMemo, useState } from 'react'
import { LANGUAGE_MODES } from '../i18n/strings.js'
import {
  canUseStorage,
  dismissTutorial,
  loadTutorialState,
  undismissTutorial,
  saveLanguage,
} from '../lib/tutorialStorage.js'
import { TutorialsContext } from './tutorialsContext.js'

/**
 * One shared home for the tutorials feature's own state.
 *
 * ## The bug this fixes, twice over
 *
 * The feature had two self-contained hooks — one for the language, one for the
 * search and dismissals — and several components called each of them. Every call
 * therefore held its own copy:
 *
 *   - the language control on `/help` switched its own state, wrote storage, and
 *     left the guides around it on English. The store was right and the screen
 *     disagreed with it, which is exactly what a reader would report as "I
 *     clicked Bangla and nothing happened";
 *   - worse, the contextual panel's trigger and the guide it rendered each had
 *     their own dismissal state, so hiding a guide updated the copy the trigger
 *     could not see and the guide reappeared as if nothing had happened.
 *
 * A provider mounted once removes both failures by giving one place to read from
 * and one place to write to. Both hooks fall back to local state when no
 * provider is mounted, so either can still be rendered alone in a test.
 *
 * ## The rule this keeps to
 *
 * A write's return value decides what the reader sees next. Each mutation below
 * writes, then re-reads, so a refused write leaves the previous state in place
 * and sets a problem. A reader is never shown a choice the browser refused to
 * keep.
 */
export function TutorialLanguageProvider({ children }) {
  const [state, setState] = useState(() => loadTutorialState().state)
  const [problem, setProblem] = useState(() => loadTutorialState().problem)

  /**
   * Re-read from storage, so what is rendered is what persisted.
   *
   * `writeFailed` marks the call as a write rather than a read. A read problem
   * and a write problem are the same thing to a reader — the browser would not
   * keep their preference — but loadTutorialState can only detect the first, so
   * the second is set explicitly here. Without it, a quota error left `problem`
   * null and every panel said nothing at all, which is worst for the reader who
   * had just asked to hide a guide.
   */
  const refresh = useCallback((writeFailed = false) => {
    const loaded = loadTutorialState()
    setState(loaded.state)
    setProblem(writeFailed ? 'write-failed' : loaded.problem)
  }, [])

  const setLanguage = useCallback(
    (mode) => {
      if (!LANGUAGE_MODES.includes(mode)) return false
      const ok = saveLanguage(mode)
      refresh(!ok)
      return ok
    },
    [refresh],
  )

  const dismiss = useCallback(
    (tutorialId) => {
      const ok = dismissTutorial(tutorialId)
      refresh(!ok)
      return ok
    },
    [refresh],
  )

  const reopen = useCallback(
    (tutorialId) => {
      const ok = undismissTutorial(tutorialId)
      refresh(!ok)
      return ok
    },
    [refresh],
  )

  const isDismissed = useCallback(
    (tutorialId) => state.dismissed?.[tutorialId] === true,
    [state.dismissed],
  )

  const value = useMemo(
    () => ({
      language: state.language,
      problem,
      storageAvailable: canUseStorage(),
      setLanguage,
      isDismissed,
      dismiss,
      reopen,
    }),
    [state.language, problem, setLanguage, isDismissed, dismiss, reopen],
  )

  return <TutorialsContext.Provider value={value}>{children}</TutorialsContext.Provider>
}
