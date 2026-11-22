/**
 * Unified AI Service
 *
 * Merges Mentor (personalized, authenticated) and AI Assistant (public, discovery)
 * into a single interface with mode detection.
 *
 * Modes:
 * - 'grounded': Deterministic retrieval from ScholarZone records (always works)
 * - 'mentor': Authenticated, personalized guidance using backend composer (requires login)
 * - 'local-ai': On-device inference via Transformers.js (optional, user-enabled)
 * - 'remote-ai': Remote inference via free API proxy (optional, quota-limited)
 */

import { askMentor, MentorUnauthenticatedError, MentorRateLimitedError, MentorValidationError, MentorUnavailableError, fetchMentorOverview } from './mentorService'
import { askAIAssistant, checkAIAvailability, isAIEnabled, setAIEnabled } from './aiAssistant'
import { classifyRoute } from './routeClassifier'

// Re-export for backward compatibility
export { askMentor, MentorUnauthenticatedError, MentorRateLimitedError, MentorValidationError, MentorUnavailableError, fetchMentorOverview }
export { askAIAssistant, checkAIAvailability, isAIEnabled, setAIEnabled, isLocalAIEnabled }
export { classifyRoute }
export { checkLocalAIModelReady }

export const AI_MODE = {
  GROUNDED: 'grounded',
  MENTOR: 'mentor',
  LOCAL_AI: 'local_ai',
  REMOTE_AI: 'remote_ai',
}

export function getAIMode() {
  // If user is authenticated and has access to mentor, use mentor mode
  // Otherwise use grounded + optional AI
  return AI_MODE.GROUNDED
}

/**
 * Validate and normalize a raw MentorAnswerResponse into a structured model.
 *
 * Returns null if the payload is not a valid Mentor response.
 * Returns { kind: 'mentor', mentorResponse: {...}, grounded: true } on success.
 */
export function normalizeMentorResponse(raw) {
  if (!raw || typeof raw !== 'object') return null

  // Check for MentorAnswerResponse shape (has headline field)
  if (typeof raw.headline === 'string' && raw.headline.trim() !== '') {
    // Validate required fields
    if (typeof raw.request_id !== 'string' || !raw.request_id) return null
    if (typeof raw.intent !== 'string' || !raw.intent) return null
    if (typeof raw.intent_label !== 'string') return null
    if (typeof raw.supported !== 'boolean') return null
    if (typeof raw.why !== 'string') return null
    // Validate as_of as ISO YYYY-MM-DD date
    if (typeof raw.as_of !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(raw.as_of)) return null
    const parsedDate = new Date(raw.as_of + 'T00:00:00Z')
    if (isNaN(parsedDate.getTime())) return null
    // Verify round-trip (e.g., reject 2026-13-45)
    const [y, m, d] = raw.as_of.split('-').map(Number)
    if (parsedDate.getUTCFullYear() !== y || parsedDate.getUTCMonth() + 1 !== m || parsedDate.getUTCDate() !== d) return null
    if (typeof raw.general_guidance_only !== 'boolean') return null

    // Validate arrays
    const known = Array.isArray(raw.known) ? raw.known : []
    const unknown = Array.isArray(raw.unknown) ? raw.unknown : []
    const nextSteps = Array.isArray(raw.next_steps) ? raw.next_steps : []
    const caveats = Array.isArray(raw.caveats) ? raw.caveats : []
    const notes = Array.isArray(raw.notes) ? raw.notes : []
    const redirects = Array.isArray(raw.redirects) ? raw.redirects : []
    const supportedIntents = Array.isArray(raw.supported_intents) ? raw.supported_intents : []

    // Validate evidence items
    const validatedKnown = known.filter(item =>
      item && typeof item === 'object' &&
      typeof item.label === 'string' && item.label.trim() !== '' &&
      typeof item.value === 'string' &&
      typeof item.field === 'string' &&
      typeof item.basis === 'string'
    ).map(item => ({
      key: typeof item.key === 'string' ? item.key : '',
      label: item.label,
      value: item.value,
      field: item.field,
      basis: item.basis,
      verification: typeof item.verification === 'string' ? item.verification : null,
      source_url: typeof item.source_url === 'string' ? item.source_url : null,
      scholarship_id: typeof item.scholarship_id === 'number' ? item.scholarship_id : null,
    }))

    // Validate next steps
    const validatedNextSteps = nextSteps.filter(item =>
      item && typeof item === 'object' &&
      typeof item.title === 'string' && item.title.trim() !== '' &&
      typeof item.detail === 'string' &&
      typeof item.href === 'string' &&
      typeof item.action_label === 'string' &&
      typeof item.code === 'string'
    ).map(item => ({
      code: item.code,
      title: item.title,
      detail: item.detail,
      priority: typeof item.priority === 'number' ? item.priority : 0,
      href: item.href,
      action_label: item.action_label,
    }))

    // Validate caveats/notes/unknown are strings
    const validatedCaveats = caveats.filter(item => typeof item === 'string')
    const validatedNotes = notes.filter(item => typeof item === 'string')
    const validatedUnknown = unknown.filter(item => typeof item === 'string')
    const validatedRedirects = redirects.filter(item => typeof item === 'string')
    const validatedSupportedIntents = supportedIntents.filter(item => typeof item === 'string')

    return {
      kind: 'mentor',
      mentorResponse: {
        request_id: raw.request_id,
        as_of: raw.as_of,
        intent: raw.intent,
        intent_label: raw.intent_label,
        supported: raw.supported,
        headline: raw.headline,
        why: raw.why,
        known: validatedKnown,
        unknown: validatedUnknown,
        next_steps: validatedNextSteps,
        caveats: validatedCaveats,
        notes: validatedNotes,
        general_guidance_only: raw.general_guidance_only,
        provider_mode: typeof raw.provider_mode === 'string' ? raw.provider_mode : 'disabled',
        provider_used: typeof raw.provider_used === 'boolean' ? raw.provider_used : false,
        supported_intents: validatedSupportedIntents,
        redirects: validatedRedirects,
        answer_schema_version: typeof raw.answer_schema_version === 'number' ? raw.answer_schema_version : 1,
        search_status: typeof raw.search_status === 'string' ? raw.search_status : null,
        query_summary: (raw.query_summary && typeof raw.query_summary === 'object') ? raw.query_summary : null,
        result_count: typeof raw.result_count === 'number' ? raw.result_count : 0,
        verified_matches: Array.isArray(raw.verified_matches) ? raw.verified_matches : [],
        potential_matches: Array.isArray(raw.potential_matches) ? raw.potential_matches : [],
        diagnostics: (raw.diagnostics && typeof raw.diagnostics === 'object') ? raw.diagnostics : {},
      },
      grounded: true,
    }
  }

  return null
}

/**
 * Check if a raw response is a valid MentorAnswerResponse.
 */
export function isMentorResponse(raw) {
  return normalizeMentorResponse(raw) !== null
}

/**
 * Unified ask function that routes to the appropriate provider
 * based on authentication state and AI availability.
 */
function isPrivateMessage(m) {
  if (!m || typeof m !== 'object') return false
  if (m.private === true) return true
  if (m.sourceType === 'mentor') return true
  return false
}

function sanitizePublicHistory(history) {
  if (!Array.isArray(history)) return []
  return history.filter((m) => !isPrivateMessage(m))
}

export async function askUnifiedAI(message, options = {}) {
  // If caller explicitly passes private: true, never downgrade to discovery
  const explicitPrivate = options.private === true
  const route = explicitPrivate ? 'mentor' : classifyRoute(message)
  const isDiscovery = !explicitPrivate && route === 'discovery'
  const {
    mode = 'auto',
    signal,
    context = {},
    conversationHistory = [],
    isAuthenticated = false,
    sessionScope,
    isRequestCurrent,
    private: isPrivate = false,
  } = options

  // Resolve conversation history without letting an unintended empty array
  // override a non-empty history provided via context.
  // For discovery routes, never use private conversation history.
  const resolvedHistory = isDiscovery
    ? []
    : (Array.isArray(conversationHistory) && conversationHistory.length > 0
      ? conversationHistory
      : (Array.isArray(context?.conversationHistory) ? context.conversationHistory : []))

  if (mode === 'auto' && isAuthenticated && !isDiscovery) {
    try {
      const raw = await askMentor(message, { signal, sessionScope })
      const normalized = normalizeMentorResponse(raw)
      if (normalized) {
        return normalized
      }
      // Legacy Mentor response with answer field
      if (raw && typeof raw.answer === 'string' && raw.answer.trim() !== '') {
        return { ...raw, kind: 'mentor-legacy', sources: Array.isArray(raw.sources) ? raw.sources.filter((s) => s && typeof s === 'object' && !Array.isArray(s) && typeof s.title === 'string' && (s.type === undefined || typeof s.type === 'string')) : [] }
      }
      // Malformed response - throw
      throw new MentorUnavailableError('Mentor returned an invalid response.', 500)
    } catch (error) {
      if (error instanceof MentorUnauthenticatedError) {
        if (typeof isRequestCurrent === 'function' && !isRequestCurrent()) {
          throw error
        }
        // Never forward private prompts to public fallback search.
        // Mentor routes are always private.
        const isPrivateIntent = isPrivate || route === 'mentor'
        if (isPrivateIntent && !isDiscovery) {
          throw error
        }
        try {
          const grounded = await askAIAssistant({
            question: message,
            context: { ...context, conversationHistory: sanitizePublicHistory(resolvedHistory) },
          })
          if (typeof isRequestCurrent === 'function' && !isRequestCurrent()) {
            throw error
          }
          return { ...grounded, authExpired: true, kind: 'grounded' }
        } catch (fallbackError) {
          void fallbackError
          throw error
        }
      }
      if (error instanceof MentorRateLimitedError) throw error
      if (error instanceof MentorValidationError) throw error
      if (error instanceof MentorUnavailableError) throw error
    }
  }

  // Never forward private prompts to public search.
  // Discovery routes are never private. Mentor routes are always private.
  const isPrivateIntent = isPrivate || route === 'mentor'
  if (isPrivateIntent && !isDiscovery) {
    throw new Error('Private mentor prompt cannot be forwarded to public search.')
  }
  // For discovery, whitelist only safe context fields (no private data)
  const safeContext = isDiscovery
    ? { conversationHistory: [] }
    : { ...context, conversationHistory: sanitizePublicHistory(resolvedHistory) }

  const grounded = await askAIAssistant({
    question: message,
    context: safeContext,
  })
  return { ...grounded, kind: 'grounded' }
}

/**
 * Get AI status for UI display
 */
export async function getAIStatus({ isAuthenticated = false } = {}) {
  const mentorAvailable = Boolean(isAuthenticated)
  const aiAvailable = await checkAIAvailability()
  const localAIEnabled = isLocalAIEnabled()

  const localAIModelReady = await checkLocalAIModelReady()

  return {
    mentor: mentorAvailable,
    remoteAI: aiAvailable,
    localAI: localAIEnabled && localAIModelReady,
    localAIEnabled: localAIEnabled,
    localAIModelReady,
    grounded: true,
    activeMode: mentorAvailable ? 'mentor' : (localAIEnabled && localAIModelReady ? 'local_ai' : (aiAvailable ? 'remote_ai' : 'grounded')),
  }
}

async function checkLocalAIModelReady() {
  // Transformers.js not yet implemented - returns false
  // When implemented, this would check if the model is actually loaded
  return false
}

function isLocalAIEnabled() {
  try {
    return localStorage.getItem('sz-local-ai-enabled') === 'true'
  } catch {
    return false
  }
}

export function setLocalAIEnabled(enabled) {
  try {
    localStorage.setItem('sz-local-ai-enabled', enabled ? 'true' : 'false')
  } catch (err) {
    void err
  }
}

/**
 * Format response for unified UI display
 */
export function formatUnifiedResponse(response, mode) {
  if (response.kind === 'mentor' && response.mentorResponse) {
    return {
      answer: null,
      mentorResponse: response.mentorResponse,
      sources: [],
      grounded: true,
      model: null,
      tokensUsed: null,
      sourceType: 'mentor',
      label: '📋 Grounded Mentor',
    }
  }

  // Legacy mentor response with answer
  if (response.kind === 'mentor-legacy' && typeof response.answer === 'string' && response.answer.trim() !== '') {
    return {
      answer: response.answer,
      sources: Array.isArray(response.sources)
        ? response.sources.filter((s) => s && typeof s === 'object' && !Array.isArray(s) && typeof s.title === 'string' && (s.type === undefined || typeof s.type === 'string'))
        : [],
      grounded: response.grounded ?? true,
      model: response.model,
      tokensUsed: response.tokensUsed,
      sourceType: 'mentor',
      label: '📋 Grounded Mentor',
    }
  }

  // Grounded Search responses must be identified by kind, not by mode.
  if (response.kind === 'grounded') {
    const base = {
      answer: typeof response.answer === 'string' ? response.answer : null,
      sources: Array.isArray(response.sources)
        ? response.sources.filter((s) => s && typeof s === 'object' && !Array.isArray(s) && typeof s.title === 'string' && (s.type === undefined || typeof s.type === 'string'))
        : [],
      grounded: response.grounded ?? true,
      model: response.model,
      tokensUsed: response.tokensUsed,
    }
    return { ...base, sourceType: 'grounded', label: '📋 Grounded Search' }
  }

  const base = {
    answer: typeof response.answer === 'string' ? response.answer : null,
sources: Array.isArray(response.sources)
        ? response.sources.filter((s) => s && typeof s === 'object' && !Array.isArray(s) && typeof s.title === 'string' && (s.type === undefined || typeof s.type === 'string'))
        : [],
    grounded: response.grounded ?? true,
    model: response.model,
    tokensUsed: response.tokensUsed,
  }

  if (mode === 'mentor') {
    return { ...base, sourceType: 'mentor', label: '📋 Grounded Mentor' }
  }
  if (mode === 'local_ai') {
    return { ...base, sourceType: 'local_ai', label: '🤖 Local AI', grounded: false }
  }
  if (mode === 'remote_ai') {
    return { ...base, sourceType: 'remote_ai', label: '☁️ Remote AI', grounded: false }
  }
  return { ...base, sourceType: 'grounded', label: '📋 Grounded Search' }
}
