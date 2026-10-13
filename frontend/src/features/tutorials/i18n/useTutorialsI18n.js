import { useCallback, useMemo, useState } from 'react'
import { LANGUAGE_MODES, translate } from './strings.js'
import { useSharedTutorialState } from '../state/tutorialsContext.js'
import { loadTutorialState, saveLanguage } from '../lib/tutorialStorage.js'

/* The two local fallbacks. Named imports from the store, so the shared path and
   the standalone path are visibly different things. */
function loadLocal() {
  return loadTutorialState()
}
function saveLocalLanguage(mode) {
  return saveLanguage(mode)
}

/**
 * The display mode for the tutorials feature.
 *
 * Follows `features/journey/i18n/useJourneyI18n.js` in shape and in reasoning:
 * `t(key)` returns the string to show, `both(key)` returns `{primary, secondary}`
 * so a heading can put Bangla on the line and English underneath it without the
 * component knowing about layout.
 *
 * ## Where the mode lives
 *
 * In the shared provider when one is mounted, and in local state otherwise. The
 * provider is what makes a language choice on `/help` reach the "How to use
 * this" panel on a feature page. Local state is the fallback that lets this hook
 * be rendered on its own in a test.
 *
 * ## `t`, `both` and `prose` are three different things
 *
 * `t(key)` and `both(key)` resolve a *key* in the i18n dictionary. `prose(field)`
 * resolves an `{en, bn}` pair from the registry, which is already-translated
 * prose rather than a key. Passing a prose pair to `both` was the first render
 * bug: it returned an `{en, bn}` object as the "primary", which React then
 * tried to render as a child.
 *
 * In every mode the primary is Bangla except `en`. In `both` the secondary is
 * English, so a reader sees Bangla with the English underneath rather than a
 * duplicate of one line.
 */
export function useTutorialsI18n() {
  const shared = useSharedTutorialState()

  const [local, setLocal] = useState(() => {
    // Local fallback only: this reads the store directly, because there is no
    // provider to ask.
    const loaded = loadLocal()
    return { language: loaded.state.language, problem: loaded.problem }
  })

  const language = shared ? shared.language : local.language
  const problem = shared ? shared.problem : local.problem

  const setLanguage = useCallback(
    (mode) => {
      if (shared) return shared.setLanguage(mode)
      if (!LANGUAGE_MODES.includes(mode)) return false
      const ok = saveLocalLanguage(mode)
      // Re-read: the write's return value decides what the reader sees next.
      const loaded = loadLocal()
      setLocal({ language: loaded.state.language, problem: loaded.problem })
      return ok
    },
    [shared],
  )

  // Bangla unless explicitly English, so `both` mode resolves to Bangla through
  // `t` too. The test that guards this is the one that failed first.
  const t = useCallback((key) => translate(language === 'en' ? 'en' : 'bn', key), [language])

  const both = useCallback(
    (key) => {
      if (language === 'en') return { primary: translate('en', key), secondary: null }
      if (language === 'bn') return { primary: translate('bn', key), secondary: null }
      return { primary: translate('bn', key), secondary: translate('en', key) }
    },
    [language],
  )

  const prose = useCallback(
    (field) => {
      if (typeof field === 'string') {
        return { primary: field, secondary: null }
      }
      const en = typeof field?.en === 'string' ? field.en : ''
      const bn = typeof field?.bn === 'string' ? field.bn : ''
      if (language === 'en') return { primary: en, secondary: null }
      if (language === 'bn') return { primary: bn, secondary: null }
      return { primary: bn, secondary: en }
    },
    [language],
  )

  return useMemo(
    () => ({
      mode: language,
      lang: language === 'en' ? 'en' : 'bn',
      locale: language === 'en' ? 'en-GB' : 'bn-BD',
      t,
      both,
      prose,
      setLanguage,
      isBoth: language === 'both',
      problem,
    }),
    [language, t, both, prose, setLanguage, problem],
  )
}

export { LANGUAGE_MODES }
