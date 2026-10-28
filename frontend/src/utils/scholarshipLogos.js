/**
 * scholarshipLogos.js — Official Provider Logo & Provenance Validation
 *
 * Provenance Policy:
 * - Use an official provider logo ONLY when its provenance is confirmed against
 *   an authentic official source (awarding body, government ministry, or university).
 * - Unverified hand-drawn approximations must NOT be used or described as official logos.
 * - When provenance is unconfirmed or no verified asset exists, return null so the
 *   card renders a neutral tactile monogram fallback.
 */

/**
 * Returns confirmed official provider logo details if provenance is validated,
 * or null to indicate that the neutral monogram fallback should be used.
 *
 * @param {Object} scholarship - The scholarship record
 * @returns {{ url: string, altText: string } | null}
 */
export function getConfirmedOfficialLogo(scholarship) {
  if (!scholarship || typeof scholarship !== 'object') {
    return null
  }

  const imageUrl = scholarship.image_url || scholarship.imageUrl

  if (!imageUrl || typeof imageUrl !== 'string' || !imageUrl.trim()) {
    return null
  }

  const trimmedUrl = imageUrl.trim()

  // Provenance check: must be a validated official provider asset
  const imageKind = scholarship.image_kind || scholarship.imageKind
  const sourceType = scholarship.image_source_type || scholarship.imageSourceType
  const isVerifiedSource =
    imageKind === 'official_logo' ||
    sourceType === 'official_provider' ||
    sourceType === 'official_scholarship' ||
    Boolean(scholarship.image_verified_at)

  if (isVerifiedSource) {
    return {
      url: trimmedUrl,
      altText: scholarship.image_alt_text || `${scholarship.title || 'Scholarship'} official provider logo`,
    }
  }

  // If provenance is not confirmed, do not claim it as an official logo
  return null
}

/**
 * Helper to derive the neutral monogram character for a scholarship title.
 *
 * @param {string} title
 * @returns {string} Single uppercase initial character
 */
export function getMonogramInitial(title) {
  if (typeof title !== 'string' || !title.trim()) {
    return 'S'
  }
  const cleaned = title.trim().replace(/^[^a-zA-Z0-9]+/, '')
  return cleaned ? cleaned.charAt(0).toUpperCase() : 'S'
}
