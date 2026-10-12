import { useCallback, useMemo } from 'react'
import { useJourney } from '../hooks/useJourney.js'
import { LANGUAGE_MODES, translate } from './strings.js'

/**
 * The display mode, resolved for the feature's components.
 *
 * `t(key)` returns the string to show in the current mode: Bangla in `bn` and
 * in `both` (where Bangla is primary), English in `en`.
 *
 * `both(key)` returns `{ primary, secondary }` so a heading can render Bangla
 * as the line and English underneath it without the translator having to know
 * about layout. In `bn` and `en` the secondary is null, because duplicating
 * every sentence in both languages is worse for reading than picking one.
 *
 * `lang` is the `lang` attribute the document should carry. In `both` mode it is
 * `bn`, since the primary line is Bangla.
 */
export function useJourneyI18n() {
  const { state } = useJourney()
  const mode = state.settings.language

  const t = useCallback((key) => translate(mode === 'en' ? 'en' : 'bn', key), [mode])

  const both = useCallback(
    (key) => {
      if (mode === 'en') return { primary: translate('en', key), secondary: null }
      if (mode === 'bn') return { primary: translate('bn', key), secondary: null }
      return { primary: translate('bn', key), secondary: translate('en', key) }
    },
    [mode],
  )

  const locale = mode === 'en' ? 'en-GB' : 'bn-BD'

  return useMemo(
    () => ({
      mode,
      lang: mode === 'en' ? 'en' : 'bn',
      locale,
      t,
      both,
      isBoth: mode === 'both',
    }),
    [mode, t, both, locale],
  )
}

export { LANGUAGE_MODES }
