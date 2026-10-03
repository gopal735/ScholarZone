import { useCallback, useMemo, useRef, useState } from 'react'

import {
  MatchApiError,
  calculateMatches,
  fetchMatchProfileOptions,
  parseMatchProfileText,
} from '../services/matchService'

/**
 * The Match page has exactly six states, and they are named rather than implied
 * by which fields happen to be populated. An implicit machine - "results exist,
 * so we are done; results are undefined, so we are still loading" - is how a
 * page ends up showing an empty state while a request is in flight, or keeps a
 * stale result set after a failure.
 *
 *   idle        nothing entered yet
 *   editing     the student is changing the profile
 *   validating  the profile is being checked locally before it is sent
 *   calculating the request is in flight
 *   success     a result set came back, with at least one card
 *   empty       a result set came back, with no cards
 *   error       the request failed, and the previous result set is gone
 */
export const MATCH_STATUS = Object.freeze({
  IDLE: 'idle',
  EDITING: 'editing',
  VALIDATING: 'validating',
  CALCULATING: 'calculating',
  SUCCESS: 'success',
  EMPTY: 'empty',
  ERROR: 'error',
})

export const MATCH_MODE = Object.freeze({
  QUICK: 'quick',
  DEEP: 'deep',
})

const DRAFT_STORAGE_KEY = 'scholarzone.match.draft.v2'

export const EMPTY_PROFILE = Object.freeze({
  age: '',
  citizenship: '',
  countryOfResidence: '',
  highestQualification: '',
  graduationYear: '',
  resultScale: '',
  resultValue: '',
  subjectResults: [],
  intendedDegreeLevel: '',
  intendedField: '',
  studyMode: '',
  preferredCountries: [],
  languageTest: '',
  languageScore: '',
  fundingRequirement: '',
  livingCostSupportRequired: '',
  maxSelfContribution: '',
  intendedIntakeYear: '',
  countryFilter: '',
  includeIneligible: true,
  limit: 60,
})

/**
 * The six fields Quick Match asks for. Everything else is opt-in and lives in
 * Deep Match, so the default path stays short without hiding anything.
 */
export const QUICK_FIELDS = Object.freeze([
  'citizenship',
  'intendedField',
  'intendedDegreeLevel',
  'resultScale',
  'languageTest',
  'fundingRequirement',
])

function readDraft() {
  try {
    const raw = window.sessionStorage.getItem(DRAFT_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object' || !parsed.profile) return null
    return parsed
  } catch {
    // A corrupt or unreadable draft must never block the page.
    return null
  }
}

function writeDraft(profile, mode, description) {
  try {
    window.sessionStorage.setItem(
      DRAFT_STORAGE_KEY,
      JSON.stringify({ profile, mode, description, savedAt: new Date().toISOString() }),
    )
  } catch {
    // sessionStorage can be unavailable in private modes. Draft persistence is a
    // convenience, never a requirement, so a failure here is silent by design.
  }
}

function clearDraft() {
  try {
    window.sessionStorage.removeItem(DRAFT_STORAGE_KEY)
  } catch {
    // Nothing to do: the draft was never stored.
  }
}

/**
 * Local validation, before anything is sent.
 *
 * Deliberately thin. The engine treats every absent field as unknown rather than
 * as a value, so an incomplete profile is a legitimate request and blocking it
 * here would hide results the student could legitimately have. What this does
 * reject is a value that is present but impossible, which would otherwise come
 * back as a 422 the student cannot act on.
 */
export function validateProfile(profile) {
  const errors = {}

  if (profile.age !== '' && profile.age !== undefined && profile.age !== null) {
    const age = Number(profile.age)
    if (!Number.isFinite(age) || age < 13 || age > 100) {
      errors.age = 'Enter an age between 13 and 100, or leave it blank.'
    }
  }

  if (profile.resultValue !== '' && profile.resultValue !== undefined && profile.resultValue !== null) {
    const value = Number(profile.resultValue)
    if (!Number.isFinite(value) || value < 0) {
      errors.resultValue = 'Enter a number for your result, or leave it blank.'
    } else if (profile.resultScale === 'PERCENTAGE' && value > 100) {
      errors.resultValue = 'A percentage result cannot be above 100.'
    } else if (profile.resultScale === 'GPA_4' && value > 4) {
      errors.resultValue = 'A 4.0-scale GPA cannot be above 4.0.'
    } else if (profile.resultScale === 'GPA_5' && value > 5) {
      errors.resultValue = 'A 5.0-scale GPA cannot be above 5.0.'
    } else if (profile.resultScale === 'GPA_10' && value > 10) {
      errors.resultValue = 'A 10-point GPA cannot be above 10.'
    }
  }

  if (profile.languageScore !== '' && profile.languageScore !== undefined && profile.languageScore !== null) {
    const score = Number(profile.languageScore)
    if (!Number.isFinite(score) || score < 0 || score > 200) {
      errors.languageScore = 'Enter a language score between 0 and 200, or leave it blank.'
    }
  }

  if (
    profile.maxSelfContribution !== '' &&
    profile.maxSelfContribution !== undefined &&
    profile.maxSelfContribution !== null &&
    Number(profile.maxSelfContribution) < 0
  ) {
    errors.maxSelfContribution = 'A contribution cannot be negative. Leave it blank if you are unsure.'
  }

  // Free-text bounds are checked here as well as on the server. A 400 the student
  // cannot see the cause of is a worse experience than a sentence that says which
  // field is too long, and the browser already knows how long the field is.
  const textBounds = [
    ['citizenship', 80],
    ['countryOfResidence', 80],
    ['intendedField', 120],
    ['countryFilter', 120],
  ]
  for (const [name, limit] of textBounds) {
    const value = profile[name]
    if (typeof value === 'string' && value.length > limit) {
      errors[name] = `That is longer than ${limit} characters. Use a short name, or leave it blank.`
    }
  }

  return errors
}

/**
 * Translate an API profile payload into the form shape.
 *
 * Only keys the engine actually resolved are mapped. An unresolved value is
 * deliberately dropped rather than guessed, so a form field is never populated
 * with something the parser was not sure about.
 */
export function applyParsedProfile(profile, parsed) {
  const next = { ...profile }
  const payload = parsed?.profile ?? {}

  if (typeof payload.citizenship === 'string') next.citizenship = payload.citizenship
  if (typeof payload.intended_degree_level === 'string') {
    next.intendedDegreeLevel = payload.intended_degree_level
  }
  if (typeof payload.intended_field === 'string') next.intendedField = payload.intended_field
  if (typeof payload.funding_requirement === 'string') {
    next.fundingRequirement = payload.funding_requirement
  }
  if (typeof payload.study_mode === 'string') next.studyMode = payload.study_mode
  if (Array.isArray(payload.preferred_countries) && payload.preferred_countries.length > 0) {
    next.preferredCountries = [...payload.preferred_countries]
  }
  if (Array.isArray(payload.language_credentials) && payload.language_credentials.length > 0) {
    const [first] = payload.language_credentials
    if (typeof first?.test === 'string') next.languageTest = first.test.toUpperCase()
    if (typeof first?.score === 'number') next.languageScore = String(first.score)
  }

  return next
}

export function useMatchProfile() {
  const draft = useMemo(() => readDraft(), [])

  const [status, setStatus] = useState(
    draft ? MATCH_STATUS.EDITING : MATCH_STATUS.IDLE,
  )
  const [mode, setModeState] = useState(draft?.mode ?? MATCH_MODE.QUICK)
  const [profile, setProfile] = useState(() => ({ ...EMPTY_PROFILE, ...(draft?.profile ?? {}) }))
  const [description, setDescription] = useState(draft?.description ?? '')
  const [parsed, setParsed] = useState(null)
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)
  const [fieldErrors, setFieldErrors] = useState({})
  const [isParsing, setIsParsing] = useState(false)
  const [parseError, setParseError] = useState(null)

  // The in-flight request is tracked so a second submit, or a reset, can abort
  // the first instead of racing it.
  const inFlight = useRef(null)

  const persist = useCallback((nextProfile, nextMode, nextDescription) => {
    writeDraft(nextProfile, nextMode, nextDescription)
  }, [])

  const changeMode = useCallback(
    (nextMode) => {
      setModeState(nextMode)
      persist(profile, nextMode, description)
    },
    [description, persist, profile],
  )

  const setField = useCallback(
    (name, value) => {
      setProfile((current) => {
        const next = { ...current, [name]: value }
        persist(next, mode, description)
        return next
      })
      setFieldErrors((current) => {
        if (!current[name]) return current
        const next = { ...current }
        delete next[name]
        return next
      })
      // Editing after a result set means that set is no longer the answer to the
      // profile on screen, so it is cleared rather than left to look current.
      setStatus((current) =>
        current === MATCH_STATUS.SUCCESS || current === MATCH_STATUS.EMPTY
          ? MATCH_STATUS.EDITING
          : current,
      )
    },
    [description, mode, persist],
  )

  const togglePreferredCountry = useCallback(
    (country) => {
      setProfile((current) => {
        const list = current.preferredCountries ?? []
        const next = list.includes(country)
          ? list.filter((item) => item !== country)
          : [...list, country]
        const updated = { ...current, preferredCountries: next }
        persist(updated, mode, description)
        return updated
      })
      setStatus((current) =>
        current === MATCH_STATUS.SUCCESS || current === MATCH_STATUS.EMPTY
          ? MATCH_STATUS.EDITING
          : current,
      )
    },
    [description, mode, persist],
  )

  const updateDescription = useCallback(
    (value) => {
      setDescription(value)
      persist(profile, mode, value)
    },
    [mode, persist, profile],
  )

  const parseDescription = useCallback(
    async (text) => {
      const trimmed = (text ?? description).trim()
      setIsParsing(true)
      setParseError(null)
      try {
        const result = await parseMatchProfileText(trimmed)
        setParsed(result)
        // Nothing is calculated here. The parsed values land in the form and the
        // student confirms them, so an uncertain reading can never become a score.
        setProfile((current) => {
          const next = applyParsedProfile(current, result)
          persist(next, mode, description)
          return next
        })
        setStatus(MATCH_STATUS.EDITING)
        return result
      } catch (caught) {
        setParseError(
          caught instanceof MatchApiError
            ? caught.message
            : 'We could not reach ScholarZone. You can still fill in the form.',
        )
        return null
      } finally {
        setIsParsing(false)
      }
    },
    [description, mode, persist],
  )

  const dismissParsed = useCallback(() => {
    setParsed(null)
    setParseError(null)
  }, [])

  const submit = useCallback(
    async (override) => {
      const nextProfile = override ?? profile
      setStatus(MATCH_STATUS.VALIDATING)

      const errors = validateProfile(nextProfile)
      if (Object.keys(errors).length > 0) {
        setFieldErrors(errors)
        setStatus(MATCH_STATUS.EDITING)
        return
      }
      setFieldErrors({})
      setError(null)

      inFlight.current?.abort()
      const controller = new AbortController()
      inFlight.current = controller
      setStatus(MATCH_STATUS.CALCULATING)

      try {
        const payload = await calculateMatches(nextProfile, { signal: controller.signal })
        const rows = payload?.results ?? []
        setResults(payload)
        setStatus(rows.length > 0 ? MATCH_STATUS.SUCCESS : MATCH_STATUS.EMPTY)
      } catch (caught) {
        if (controller.signal.aborted) {
          setStatus(MATCH_STATUS.EDITING)
          return
        }
        // A failed request must not leave the previous result set on screen,
        // because it answers a profile the student has already changed.
        setResults(null)
        setError(
          caught instanceof MatchApiError
            ? { message: caught.message, status: caught.status }
            : {
                message:
                  'We could not reach ScholarZone. Check your connection and try again.',
                status: 0,
              },
        )
        setStatus(MATCH_STATUS.ERROR)
      } finally {
        if (inFlight.current === controller) inFlight.current = null
      }
    },
    [profile],
  )

  const reset = useCallback(() => {
    inFlight.current?.abort()
    inFlight.current = null
    clearDraft()
    setProfile({ ...EMPTY_PROFILE })
    setModeState(MATCH_MODE.QUICK)
    setDescription('')
    setParsed(null)
    setParseError(null)
    setResults(null)
    setError(null)
    setFieldErrors({})
    setStatus(MATCH_STATUS.IDLE)
  }, [])

  const restore = useCallback(() => {
    setResults(null)
    setError(null)
    setStatus(MATCH_STATUS.EDITING)
  }, [])

  const isBusy = status === MATCH_STATUS.CALCULATING || status === MATCH_STATUS.VALIDATING
  const hasResults = status === MATCH_STATUS.SUCCESS || status === MATCH_STATUS.EMPTY

  return {
    // Explicit machine
    status,
    mode,
    isBusy,
    hasResults,

    // Profile
    profile,
    fieldErrors,
    changeMode,
    setField,
    togglePreferredCountry,

    // Optional free-text description
    description,
    updateDescription,
    parsed,
    isParsing,
    parseError,
    parseDescription,
    dismissParsed,

    // Result
    results,
    error,
    submit,
    reset,
    restore,
  }
}

export { EMPTY_PROFILE as DEFAULT_PROFILE, fetchMatchProfileOptions, calculateMatches }