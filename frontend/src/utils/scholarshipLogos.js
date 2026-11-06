import officialProviderLogos from '../data/officialProviderLogos.json'

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
  const imageKind = scholarship.image_kind || scholarship.imageKind
  const sourceType = scholarship.image_source_type || scholarship.imageSourceType

  // A verified image or official scholarship page can still be a banner or
  // programme photo. Only explicit logo metadata identifies an identity mark.
  if (
    typeof imageUrl === 'string' &&
    imageUrl.trim() &&
    (imageKind === 'official_logo' || sourceType === 'official_page_logo')
  ) {
    return {
      url: imageUrl.trim(),
      altText: scholarship.image_alt_text || `${scholarship.title || 'Scholarship'} official provider logo`,
    }
  }

  const sourceUrl = scholarship.official_source_url || scholarship.officialSourceUrl
  if (typeof sourceUrl !== 'string') return null

  try {
    const host = new URL(sourceUrl).hostname.toLowerCase().replace(/^www\./, '')
    const logo = officialProviderLogos[host]
    return logo ? { url: logo.url, altText: logo.altText || `${scholarship.title || 'Scholarship'} provider logo` } : null
  } catch {
    return null
  }
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
