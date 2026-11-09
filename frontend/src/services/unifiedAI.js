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
import { askAIAssistant, checkAIAvailability, isLocalAIEnabled } from './aiAssistant'

// Re-export for backward compatibility
export { askMentor, MentorUnauthenticatedError, MentorRateLimitedError, MentorValidationError, MentorUnavailableError, fetchMentorOverview }
export { askAIAssistant, checkAIAvailability, isLocalAIEnabled }
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
 * Unified ask function that routes to the appropriate provider
 * based on authentication state and AI availability.
 */
export async function askUnifiedAI(message, options = {}) {
  const { 
    mode = 'auto', 
    signal, 
    context = {},
    conversationHistory = [] 
  } = options

  // Auto-detect best mode
  if (mode === 'auto') {
    // Check if user is authenticated and has mentor access
    try {
      await fetchMentorOverview({ signal: AbortSignal.timeout(2000) })
      // If we get here, user is authenticated - use mentor for personalized guidance
      return askMentor(message, { signal })
    } catch (error) {
      if (error instanceof MentorUnauthenticatedError) {
        // Not authenticated - fall through to AI Assistant
      } else if (error instanceof MentorRateLimitedError) {
        throw error
      } else if (error instanceof MentorValidationError) {
        throw error
      }
      // Network or other error - fall through
    }
  }

  // Use AI Assistant (grounded + optional AI)
  return askAIAssistant({
    question: message,
    context: {
      ...context,
      conversationHistory,
    },
  }, { signal })
}

/**
 * Get AI status for UI display
 */
export async function getAIStatus() {
  const mentorAvailable = await checkMentorAccess()
  const aiAvailable = await checkAIAvailability()
  const localAIEnabled = isLocalAIEnabled()
  
  // Local AI requires actual model loading capability (Transformers.js)
  // Currently not implemented - returns false until Transformers.js is integrated
  const localAIModelReady = await checkLocalAIModelReady()
  
  // Mode priority: mentor > grounded (always available) > local/remote (not implemented)
  let activeMode = 'grounded'
  if (mentorAvailable) activeMode = 'mentor'
  else if (localAIEnabled && localAIModelReady) activeMode = 'local_ai'
  else if (aiAvailable) activeMode = 'remote_ai'
  
  return {
    mentor: mentorAvailable,
    remoteAI: aiAvailable,
    localAI: localAIEnabled && localAIModelReady,
    localAIEnabled: localAIEnabled,
    localAIModelReady,
    grounded: true, // Always available
    activeMode,
  }
}

async function checkLocalAIModelReady() {
  // Transformers.js not yet implemented - returns false
  // When implemented, this would check if the model is actually loaded
  return false
}

async function checkMentorAccess() {
  try {
    await fetchMentorOverview({ signal: AbortSignal.timeout(2000) })
    return true
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
  const base = {
    answer: response.answer,
    sources: response.sources || [],
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