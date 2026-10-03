const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

export class MatchApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'MatchApiError'
    this.status = status
  }
}

/**
 * Translate the form's profile into the engine's request shape.
 *
 * Exported because the counting endpoint accepts the same profile body. Two
 * translations of one form would drift, and the drift is silent: the raw form shape
 * is camelCase full of empty strings, the engine's is snake_case with empties
 * stripped, and sending the wrong one is a 422 that says nothing about which of the
 * two is at fault.
 */
export function profilePayload(profile) {
  // The engine treats an absent field as unknown rather than as a value, so
  // empty strings and nulls are stripped rather than sent. Sending "" for the
  // grading scale would make the request invalid, and sending a null
  // citizenship would be read as "not provided", which is the same thing but
  // expressed in a way the schema has to special-case.
  const compact = (value) => (value === '' || value === undefined ? undefined : value)

  const payload = {
    age: compact(profile.age === '' ? undefined : Number(profile.age)),
    citizenship: compact(profile.citizenship),
    country_of_residence: compact(profile.countryOfResidence),
    highest_qualification: compact(profile.highestQualification),
    graduation_year: compact(profile.graduationYear === '' ? undefined : Number(profile.graduationYear)),
    intended_degree_level: compact(profile.intendedDegreeLevel),
    intended_field: compact(profile.intendedField),
    study_mode: compact(profile.studyMode),
    preferred_countries: Array.isArray(profile.preferredCountries)
      ? profile.preferredCountries.filter(Boolean)
      : [],
    funding_requirement: compact(profile.fundingRequirement),
    living_cost_support_required:
      profile.livingCostSupportRequired === '' || profile.livingCostSupportRequired === undefined
        ? undefined
        : profile.livingCostSupportRequired === 'true',
    max_self_contribution: compact(
      profile.maxSelfContribution === '' ? undefined : Number(profile.maxSelfContribution),
    ),
    intended_intake_year: compact(
      profile.intendedIntakeYear === '' ? undefined : Number(profile.intendedIntakeYear),
    ),
    country_filter: compact(profile.countryFilter),
    include_ineligible: profile.includeIneligible !== false,
    limit: 60,
  }

  if (profile.resultScale && profile.resultValue !== '' && profile.resultValue !== undefined) {
    payload.overall_result = {
      scale: profile.resultScale,
      value: Number(profile.resultValue),
    }
  }

  if (profile.languageTest) {
    payload.language_credentials = [
      {
        test: profile.languageTest,
        score: profile.languageScore === '' || profile.languageScore === undefined
          ? undefined
          : Number(profile.languageScore),
      },
    ]
  }

  return payload
}

/**
 * Calculate matches for a profile.
 *
 * The profile is sent in the POST body rather than the query string so a
 * student's nationality, age and academic record never reach an access log or
 * a Referer header. Nothing is persisted server-side.
 */
export async function calculateMatches(profile, { signal } = {}) {
  const response = await fetch(new URL(`${apiBaseUrl}/scholarships/match`, window.location.origin), {
    method: 'POST',
    signal,
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(profilePayload(profile)),
  })

  if (!response.ok) {
    let message = 'We could not calculate your matches right now. Please try again.'
    try {
      const payload = await response.json()
      if (typeof payload.detail === 'string') {
        message = payload.detail
      }
    } catch {
      // A non-JSON failure still surfaces a safe, useful message.
    }
    throw new MatchApiError(message, response.status)
  }

  return response.json()
}

export async function fetchMatchProfileOptions(options) {
  const response = await fetch(
    new URL(`${apiBaseUrl}/scholarships/match/profile-options`, window.location.origin),
    { signal: options?.signal, headers: { Accept: 'application/json' } },
  )

  if (!response.ok) {
    throw new MatchApiError('ScholarZone Match options are unavailable.', response.status)
  }

  return response.json()
}

/**
 * Interpret one optional sentence as a profile.
 *
 * Deterministic and entirely inside ScholarZone: the API matches the text
 * against its own approved lists and reports back what it understood, including
 * anything it could NOT resolve. It is deliberately not a language model, so it
 * cannot invent a field.
 *
 * The caller must show the result for confirmation and must let the student edit
 * or remove it. Nothing calculated from a parsed profile is submitted without
 * that step, so a misreading is always visible before it becomes a score.
 */
export async function parseMatchProfileText(text, { signal } = {}) {
  const response = await fetch(
    new URL(`${apiBaseUrl}/scholarships/match/parse-profile`, window.location.origin),
    {
      method: 'POST',
      signal,
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text == null ? null : text }),
    },
  )

  if (!response.ok) {
    let message = 'We could not read that description. You can still fill in the form.'
    try {
      const payload = await response.json()
      if (typeof payload.detail === 'string') message = payload.detail
    } catch {
      // A non-JSON failure still surfaces a safe, useful message.
    }
    throw new MatchApiError(message, response.status)
  }

  return response.json()
}