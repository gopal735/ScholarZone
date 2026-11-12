/**
 * Data-Driven Filter Facets
 *
 * Derives filter options from the complete public catalogue rather than
 * using hardcoded values. This ensures every advertised option returns
 * results and no represented value is missing.
 */

import { canonicalCountry, isRealCountry } from './countryTaxonomy';

/**
 * Normalise a country value using the shared canonical taxonomy.
 * Returns the canonical country name, or special values for non-countries.
 */
function normaliseCountry(value) {
  if (!value || typeof value !== 'string') return null;
  const canonical = canonicalCountry(value.trim());
  return canonical;
}

/**
 * Derive country filter options from a list of scholarship records.
 * Returns sorted array of { value, label, count } objects.
 */
export function deriveCountryFacets(scholarships) {
  const counts = new Map();

  for (const s of scholarships) {
    const canonical = normaliseCountry(s.country);
    if (!canonical) continue;

    // Count under the canonical name
    const existing = counts.get(canonical) || { count: 0 };
    existing.count++;
    counts.set(canonical, existing);
  }

  // Filter to real countries only, sort alphabetically by label
  const facets = Array.from(counts.entries())
    .filter(([canonical]) => isRealCountry(canonical))
    .map(([value, { count }]) => ({ value, label: value, count }))
    .sort((a, b) => a.label.localeCompare(b.label, undefined, { sensitivity: 'base' }));

  return facets;
}

/**
 * Derive degree filter options from a list of scholarship records.
 * Returns sorted array of { value, label, count } objects.
 */
export function deriveDegreeFacets(scholarships) {
  // The canonical degree levels we support as filter buckets
  const degreeBuckets = [
    { value: 'Bachelor', label: 'Bachelor / Undergraduate', keywords: ['bachelor', 'undergraduate'] },
    { value: 'Master', label: 'Master', keywords: ['master'] },
    { value: 'PhD', label: 'PhD / Doctoral', keywords: ['phd', 'ph.d', 'doctoral', 'doctorate'] },
    { value: 'Postgraduate', label: 'Postgraduate', keywords: ['postgraduate'] },
    { value: 'Postdoctoral', label: 'Postdoctoral', keywords: ['postdoctoral', 'post-doc'] },
    { value: 'Associate', label: 'Associate', keywords: ['associate'] },
  ];

  const counts = new Map();
  degreeBuckets.forEach(b => counts.set(b.value, { ...b, count: 0 }));

  for (const s of scholarships) {
    const degreeText = (s.degree || '').toLowerCase();
    if (!degreeText) continue;

    // A scholarship can match multiple buckets (joint degrees)
    for (const bucket of degreeBuckets) {
      if (bucket.keywords.some(k => degreeText.includes(k))) {
        const entry = counts.get(bucket.value);
        if (entry) entry.count++;
      }
    }
  }

  // Filter to buckets with at least one record, sort by label
  return Array.from(counts.values())
    .filter(b => b.count > 0)
    .sort((a, b) => a.label.localeCompare(b.label, undefined, { sensitivity: 'base' }));
}

/**
 * Derive funding filter options from a list of scholarship records.
 * Returns sorted array of { value, label, count } objects.
 */
export function deriveFundingFacets(scholarships) {
  // The canonical funding aspects we support as filter buckets
  const fundingBuckets = [
    { value: 'Fully Funded', label: 'Fully funded', keywords: ['fully funded', 'fully-funded', 'full funding', 'full scholarship', 'full sponsorship', 'full study funding'], exclude: ['partially', 'partial to full', 'various'] },
    { value: 'Partially Funded', label: 'Partial funding', keywords: ['partial'], exclude: [] },
    { value: 'Tuition Fee Waiver', label: 'Tuition waiver', keywords: ['tuition', 'fee'], exclude: [] },
    { value: 'Stipend', label: 'Stipend', keywords: ['stipend', 'stipendium', 'salary', 'fellowship'], exclude: [] },
    { value: 'Research Funding', label: 'Research funding', keywords: ['research'], exclude: [] },
    { value: 'Need Based', label: 'Need-based', keywords: ['need'], exclude: [] },
  ];

  const counts = new Map();
  fundingBuckets.forEach(b => counts.set(b.value, { ...b, count: 0 }));

  for (const s of scholarships) {
    const fundingText = (s.funding || '').toLowerCase();
    const fullyFunded = s.fully_funded;
    
    for (const bucket of fundingBuckets) {
      const excluded = bucket.exclude.some(e => fundingText.includes(e));
      if (excluded) continue;
      
      // For "Fully Funded", use the authoritative boolean
      if (bucket.value === 'Fully Funded') {
        if (fullyFunded === true) {
          const entry = counts.get(bucket.value);
          if (entry) entry.count++;
        }
        continue;
      }
      
      const included = bucket.keywords.some(k => fundingText.includes(k));
      if (included) {
        const entry = counts.get(bucket.value);
        if (entry) entry.count++;
      }
    }
  }

  // Filter to buckets with at least one record, sort by label
  return Array.from(counts.values())
    .filter(b => b.count > 0)
    .sort((a, b) => a.label.localeCompare(b.label, undefined, { sensitivity: 'base' }));
}

/**
 * Derive deadline month facets from scholarship records.
 * Returns array of { value: number, label: string, count: number }
 * for months 1-12 that have records.
 */
export function deriveDeadlineMonthFacets(scholarships) {
  const counts = new Array(13).fill(0); // 1-12

  for (const s of scholarships) {
    if (s.deadline_date) {
      const month = parseMonthFromDate(s.deadline_date);
      if (month >= 1 && month <= 12) {
        counts[month]++;
      }
    }
  }

  const monthNames = [
    '', 'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];

  return counts
    .map((count, month) => ({ value: month, label: monthNames[month], count }))
    .slice(1)
    .filter(f => f.count > 0);
}

/**
 * Parse month (1-12) from a deadline_date string (YYYY-MM-DD or YYYY-MM).
 */
function parseMonthFromDate(dateStr) {
  if (!dateStr || typeof dateStr !== 'string') return 0;
  const match = dateStr.match(/^\d{4}-(\d{2})/);
  if (match) return parseInt(match[1], 10);
  return 0;
}

/**
 * Get all filter facets in one call.
 */
export function deriveAllFacets(scholarships) {
  return {
    country: deriveCountryFacets(scholarships),
    degree: deriveDegreeFacets(scholarships),
    funding: deriveFundingFacets(scholarships),
    deadlineMonth: deriveDeadlineMonthFacets(scholarships),
  };
}