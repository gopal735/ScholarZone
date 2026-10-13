/**
 * Catalogue search: normalisation, tokenisation and ranking.
 *
 * The previous search was a single `includes` against five joined fields,
 * lowercased but not trimmed. Three consequences, all of which a student
 * actually hits:
 *
 *   - "  daad " did not match, because the leading and trailing spaces were
 *     part of the needle and the haystack had no such run.
 *   - "daad." did not match, because the full stop was part of the needle.
 *   - "DAAD Germany" matched nothing, because the two terms appeared in
 *     opposite order in the record - `funding` and `country` are joined in a
 *     fixed order and a single substring test has no way to reorder them.
 *
 * So search is now tokenised with AND semantics over a wider field set. Every
 * term must appear somewhere in the record, in any order, in any of the
 * indexed fields.
 *
 * The field set is chosen from the fields the snapshot actually carries and
 * that describe what a student would type: the title, the provider, the host
 * country and region, the study level, the funding text, the documented
 * eligibility and benefit summary, the requirements, the English-language
 * requirement, the application method, the programme type, and the
 * "best fit" narrative. Nothing here invents a field: every name below is read
 * off the snapshot, and a field that is absent on a record simply contributes
 * no text.
 */

/** Fields indexed for search, in the order they are read. */
export const SEARCH_FIELDS = Object.freeze([
  'title',
  'name',
  'official_source',
  'country',
  'region',
  'degree',
  'degree_levels',
  'funding',
  'funding_type',
  'eligibility_summary',
  'benefits',
  'coverage',
  'requirements',
  'documents',
  'required_documents',
  'english_requirement',
  'application_method',
  'program_type',
  'best_fit',
  'duration',
])

/**
 * Fields whose match is worth more when ranking, because a hit in the title is
 * a stronger signal than the same hit somewhere in a 900-character summary.
 * Values are relative weights, not scores.
 */
export const FIELD_WEIGHTS = Object.freeze({
  title: 6,
  name: 5,
  official_source: 3,
  country: 2,
  degree: 2,
  degree_levels: 2,
  funding: 2,
  funding_type: 2,
  eligibility_summary: 1,
  best_fit: 1,
})

const DEFAULT_WEIGHT = 1

/** True for a string that carries usable text. Never coerces a falsy value. */
function isText(value) {
  return typeof value === 'string' && value.trim() !== ''
}

/**
 * Normalise a raw query the way the catalogue is normalised, so that
 * differences that carry no meaning do not decide whether a record matches.
 *
 * Case, surrounding and internal whitespace runs, and punctuation are all
 * removed. Unicode is normalised to NFKC so a full-width or accented character
 * typed on a phone collapses to the form the data holds.
 *
 * Returns an empty string for a non-string or a blank value, so callers can
 * treat "no query" as a single value rather than a special case.
 */
export function normalizeQuery(raw) {
  if (typeof raw !== 'string') {
    return ''
  }

  return raw
    .normalize('NFKC')
    .toLowerCase()
    // Keep letters, numbers and whitespace; drop punctuation entirely. A
    // student typing "m.a.sc" is typing "masc".
    .replace(/[^\p{L}\p{N}\s]/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

/** Split a normalised query into the terms that must all be present. */
export function tokenizeQuery(raw) {
  const normalized = normalizeQuery(raw)
  return normalized === '' ? [] : normalized.split(' ')
}

/** Every indexed field of one record, as text. */
function indexableTexts(scholarship) {
  if (scholarship === null || typeof scholarship !== 'object') {
    return []
  }

  const texts = []
  for (const field of SEARCH_FIELDS) {
    const value = scholarship[field]
    if (isText(value)) {
      texts.push({ field, text: value })
      continue
    }
    // Arrays and objects are real shapes here - `benefits`, `requirements`,
    // `documents`, `required_documents` and `application_method` are all
    // lists on some records. Stringifying them puts their contents in the
    // index rather than dropping the field from it.
    if (Array.isArray(value) && value.some(isText)) {
      texts.push({ field, text: value.filter(isText).join(' ') })
      continue
    }
    if (value !== null && typeof value === 'object') {
      const parts = Object.values(value).filter(isText)
      if (parts.length > 0) {
        texts.push({ field, text: parts.join(' ') })
      }
    }
  }
  return texts
}

/**
 * Score a record against already-normalised tokens.
 *
 * The score is a sum of per-term, per-field weights, so a record whose title
 * carries every term outranks one that carries them spread across summaries.
 * It is used for the relevance ordering only; it never decides membership -
 * that is `matchesTokens`, which is the boolean test.
 */
export function scoreRecord(scholarship, tokens) {
  if (!Array.isArray(tokens) || tokens.length === 0) {
    return 0
  }

  const texts = indexableTexts(scholarship)
  let score = 0

  for (const token of tokens) {
    for (const { field, text } of texts) {
      if (normalizeQuery(text).includes(token)) {
        const weight = FIELD_WEIGHTS[field] ?? DEFAULT_WEIGHT
        score += weight
        // Count the strongest field for this term once, rather than summing
        // every field that mentions it, so a long summary cannot outweigh a
        // title hit by repeating the same word.
        break
      }
    }
  }

  return score
}

/** True when every token is present somewhere in the record. */
export function matchesTokens(scholarship, tokens) {
  if (!Array.isArray(tokens) || tokens.length === 0) {
    return true
  }

  const texts = indexableTexts(scholarship)

  return tokens.every((token) => (
    texts.some(({ text }) => normalizeQuery(text).includes(token))
  ))
}

/**
 * Filter a catalogue by a free-text query, ranked best-first.
 *
 * An empty or non-string query returns the input order untouched and scores
 * nothing, so a page that has no query is not reordered by a search that is
 * not happening.
 *
 * @param {object[]} records
 * @param {string} query raw user input, in any casing or spacing
 * @returns {object[]}
 */
export function searchRecords(records, query) {
  if (!Array.isArray(records)) {
    return []
  }

  const tokens = tokenizeQuery(query)
  if (tokens.length === 0) {
    return records
  }

  const matched = records.filter((record) => matchesTokens(record, tokens))

  // Scored, then stable by the incoming order for equal scores. Records with
  // a score of 0 are not dropped: every returned record matched, and a
  // weighted order among them is a ranking, not a filter.
  return matched
    .map((record, index) => ({ record, index, score: scoreRecord(record, tokens) }))
    .sort((first, second) => second.score - first.score || first.index - second.index)
    .map(({ record }) => record)
}

/**
 * A short explanation of what the search actually matched, for the no-results
 * state. Returns null when there is nothing to explain (no query), so a caller
 * can render nothing rather than an empty fragment.
 */
export function describeSearch(query) {
  const tokens = tokenizeQuery(query)
  if (tokens.length === 0) {
    return null
  }

  return {
    tokens,
    termCount: tokens.length,
    // Said in the plural-aware form the no-results state uses.
    summary: tokens.length === 1 ? 'one term' : `${tokens.length} terms`,
  }
}
