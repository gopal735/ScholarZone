// Shortlist, share-link and export helpers.
//
// Safety rule: a shared link or an export carries only the choices the reader
// deliberately made (subject, degree, funding, weights) - never a name, email or
// any personal data. The strategist holds no PII, so a share link cannot leak one.
const SHORTLIST_KEY = 'scholarzone.strategist.shortlist'

export function buildShareURL(choices) {
  const params = new URLSearchParams()
  if (choices.subject_key) params.set('subject', choices.subject_key)
  if (choices.degree) params.set('degree', choices.degree)
  if (choices.funding_model) params.set('funding', choices.funding_model)
  if (choices.weights) params.set('w', JSON.stringify(choices.weights))
  const query = params.toString()
  const base = `${window.location.origin}${window.location.pathname}`
  return query ? `${base}?${query}` : base
}

export function readChoicesFromURL(search) {
  const params = new URLSearchParams(search)
  const choices = {}
  if (params.get('subject')) choices.subject_key = params.get('subject')
  if (params.get('degree')) choices.degree = params.get('degree')
  if (params.get('funding')) choices.funding_model = params.get('funding')
  if (params.get('w')) {
    try {
      choices.weights = JSON.parse(params.get('w'))
    } catch {
      choices.weights = null
    }
  }
  return choices
}

export function saveShortlist(iso2List) {
  try {
    sessionStorage.setItem(SHORTLIST_KEY, JSON.stringify(iso2List))
    return true
  } catch {
    return false
  }
}

export function readShortlist() {
  try {
    const raw = sessionStorage.getItem(SHORTLIST_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

export function exportPDF() {
  // No library dependency and no PII: the browser's own print view renders the
  // current comparison, and the reader saves it to PDF.
  window.print()
}
