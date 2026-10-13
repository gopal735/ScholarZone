// i18n for the Study-to-Career Strategist, mirroring features/journey/i18n.
//
// Three modes: `en`, `bn`, `both`. `t(key)` returns the { en, bn } pair; `both`
// renders Bangla with English beneath. Bangla digits used for displayed BDT and
// counts in Bangla mode, following the same normalisation the journey uses.
import { useCallback, useMemo, useState } from 'react'
import STRINGS from './strings.js'

export const LANGUAGE_MODES = ['en', 'bn', 'both']

const BN_DIGITS = ['০', '১', '২', '৩', '৪', '৫', '৬', '৭', '৮', '৯']

export function normalizeBanglaDigits(value) {
  return String(value).replace(/\d/g, (d) => BN_DIGITS[Number(d)])
}

export function useStrategistI18n(initialMode = 'both') {
  const [mode, setMode] = useState(
    LANGUAGE_MODES.includes(initialMode) ? initialMode : 'both',
  )

  const t = useCallback((key) => {
    const entry = STRINGS[key]
    if (!entry) return { en: key, bn: key }
    return entry
  }, [])

  const setLanguage = useCallback((next) => {
    setMode(LANGUAGE_MODES.includes(next) ? next : 'both')
  }, [])

  const locale = mode === 'bn' ? 'bn-BD' : mode === 'en' ? 'en-GB' : 'bn-BD'

  const formatNumber = useCallback(
    (value) => (value == null || value === '' || Number.isNaN(Number(value)) ? '' : new Intl.NumberFormat(locale).format(value)),
    [locale],
  )

  const formatBdt = useCallback(
    (value) => (value == null ? '' : new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(value)),
    [locale],
  )

  return useMemo(
    () => ({ t, both: t, mode, setMode, setLanguage, locale, formatNumber, formatBdt, normalizeBanglaDigits }),
    [t, mode, setMode, setLanguage, locale, formatNumber, formatBdt],
  )
}
