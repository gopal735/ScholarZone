/**
 * Scholarship Lifecycle Classification
 * 
 * Classifies scholarships into six lifecycle categories based on available data:
 * - OPENING: Application opening date is approaching within the configured window
 * - UPCOMING: Future cycle - opening date is in the future and outside the opening window
 * - OPEN: Applications are currently open and deadline is not in closing-soon window
 * - CLOSING_SOON: Applications are open and the verified deadline is approaching
 * - CLOSED: The current cycle has ended and no verified future cycle supersedes it
 * - UNKNOWN: Dates are missing, ambiguous or contradictory
 * 
 * Precedence (highest first):
 * 1. CLOSED (explicit status, is_archived, or deadline passed with no future cycle)
 * 2. CLOSING_SOON (deadline within CLOSING_SOON_THRESHOLD_DAYS)
 * 3. UPCOMING (explicit status === 'upcoming' OR opening_date in future beyond window)
 * 4. OPENING (opening_date within OPENING_WINDOW_DAYS)
 * 5. OPEN (default for active scholarships with valid deadline)
 * 6. UNKNOWN (missing critical dates)
 * 
 * Configurable thresholds:
 * - CLOSING_SOON_THRESHOLD_DAYS: days before deadline to show "Closing Soon" (default: 30)
 * - OPENING_WINDOW_DAYS: days before opening date to show "Opening Soon" (default: 60)
 */

export const LIFECYCLE = {
  OPENING: 'opening',
  UPCOMING: 'upcoming',
  CLOSING_SOON: 'closing_soon',
  CLOSED: 'closed',
  OPEN: 'open',
  UNKNOWN: 'unknown',
};

const LIFECYCLE_LABELS = {
  [LIFECYCLE.OPENING]: 'Opening Soon',
  [LIFECYCLE.UPCOMING]: 'Upcoming',
  [LIFECYCLE.CLOSING_SOON]: 'Closing Soon',
  [LIFECYCLE.CLOSED]: 'Closed',
  [LIFECYCLE.OPEN]: 'Open',
  [LIFECYCLE.UNKNOWN]: 'Check deadline',
};

const LIFECYCLE_DESCRIPTIONS = {
  [LIFECYCLE.OPENING]: 'Applications open soon. Prepare your documents.',
  [LIFECYCLE.UPCOMING]: 'Future cycle. Not yet accepting applications.',
  [LIFECYCLE.CLOSING_SOON]: 'Deadline approaching. Apply now.',
  [LIFECYCLE.CLOSED]: 'This application cycle has ended.',
  [LIFECYCLE.OPEN]: 'Accepting applications.',
  [LIFECYCLE.UNKNOWN]: 'A confirmed application deadline is not available. Check the official source before applying.',
};

const LIFECYCLE_CLASSES = {
  [LIFECYCLE.OPENING]: 'lifecycle-opening',
  [LIFECYCLE.UPCOMING]: 'lifecycle-upcoming',
  [LIFECYCLE.CLOSING_SOON]: 'lifecycle-closing-soon',
  [LIFECYCLE.CLOSED]: 'lifecycle-closed',
  [LIFECYCLE.OPEN]: 'lifecycle-open',
  [LIFECYCLE.UNKNOWN]: 'lifecycle-unknown',
};

// Configurable thresholds - can be overridden via environment or config
const CLOSING_SOON_THRESHOLD_DAYS = 30;
const OPENING_WINDOW_DAYS = 60;

/**
 * Parse a date from various scholarship date fields.
 * Handles deadline_date, opening_date, deadline_display, and deadline_precision.
 * Returns { date: Date | null, isExact: boolean }
 * Uses UTC to avoid timezone issues.
 */
export function parseDate(scholarship, fieldName) {
  // Prefer explicit ISO date fields
  const explicitField = fieldName === 'opening' ? 'opening_date' : 'deadline_date';
  if (scholarship[explicitField]) {
    const parsed = parseLifecycleDate(scholarship[explicitField], {
      monthOnly: fieldName === 'deadline' && scholarship.deadline_precision === 'month',
    });
    if (parsed && !isNaN(parsed.getTime())) {
      return { date: parsed, isExact: scholarship.deadline_precision === 'exact' };
    }
  }

  // Fallback to display fields
  const displayField = fieldName === 'opening' ? 'opening_display' : 'deadline_display';
  if (scholarship[displayField] && typeof scholarship[displayField] === 'string') {
    const parsed = parseLifecycleDate(scholarship[displayField], {
      monthOnly: fieldName === 'deadline' && scholarship.deadline_precision === 'month',
    });
    if (parsed && !isNaN(parsed.getTime())) {
      return { date: parsed, isExact: scholarship.deadline_precision === 'exact' };
    }
  }

  // Fallback to legacy deadline field
  if (fieldName !== 'opening' && scholarship.deadline && typeof scholarship.deadline === 'string') {
    const parsed = parseLifecycleDate(scholarship.deadline, {
      monthOnly: scholarship.deadline_precision === 'month',
    });
    if (parsed && !isNaN(parsed.getTime())) {
      return { date: parsed, isExact: scholarship.deadline_precision === 'exact' };
    }
  }

  return { date: null, isExact: false };
}

function parseLifecycleDate(value, { monthOnly = false } = {}) {
  if (typeof value !== 'string' || !value.trim()) return null;
  const text = value.trim();
  const isoMonth = /^(\d{4})-(\d{2})$/.exec(text);
  const namedMonth = /^([a-z]+\s+\d{4})$/i.exec(text);
  let parsed;

  if (isoMonth) {
    parsed = new Date(`${text}-01T00:00:00Z`);
    monthOnly = true;
  } else if (namedMonth) {
    const [monthName, year] = namedMonth[1].split(/\s+/);
    const monthIndex = [
      'january', 'february', 'march', 'april', 'may', 'june',
      'july', 'august', 'september', 'october', 'november', 'december',
    ].indexOf(monthName.toLowerCase());
    if (monthIndex === -1) return null;
    parsed = new Date(Date.UTC(Number(year), monthIndex, 1));
    monthOnly = true;
  } else if (/^\d{4}-\d{2}-\d{2}$/.test(text)) {
    parsed = new Date(`${text}T00:00:00Z`);
  } else {
    parsed = new Date(text);
  }

  if (Number.isNaN(parsed.getTime())) return null;
  if (monthOnly) {
    parsed.setUTCMonth(parsed.getUTCMonth() + 1, 0);
  }
  return parsed;
}

/**
 * Extract opening date from application_period text.
 * This is a heuristic for records without explicit opening_date.
 * Returns { date: Date | null, isExact: boolean }
 */
export function parseOpeningDateFromPeriod(scholarship) {
  if (!scholarship.application_period || typeof scholarship.application_period !== 'string') {
    return { date: null, isExact: false };
  }

  const period = scholarship.application_period;
  
  // Pattern: "opens YYYY-MM-DD" or "opens DD Month YYYY"
  const opensPattern = /opens?\s+(?:on\s+)?(\d{4}-\d{2}-\d{2}|\d{1,2}\s+\w+\s+\d{4})/i;
  const match = period.match(opensPattern);
  if (match) {
    // Parse as UTC
    const parsed = new Date(match[1] + 'T00:00:00Z');
    if (!isNaN(parsed.getTime())) {
      return { date: parsed, isExact: true };
    }
  }

// Pattern: "call opens Month YYYY" or "applications open Month YYYY"
  const monthYearPattern = /(?:call|applications?)\s+opens?\s+(\w+\s+\d{4})/i;
  const monthMatch = period.match(monthYearPattern);
  if (monthMatch) {
    // Parse as UTC (first day of month at midnight)
    const parsed = new Date(monthMatch[1] + ' 00:00:00Z');
    if (!isNaN(parsed.getTime())) {
      return { date: parsed, isExact: false };
    }
  }

  // Pattern: "2027 cycle: call opens 2027-01-01"
  const cyclePattern = /(\d{4})\s+cycle:?.*?opens?\s+(\d{4}-\d{2}-\d{2})/i;
  const cycleMatch = period.match(cyclePattern);
  if (cycleMatch) {
    // Parse as UTC
    const parsed = new Date(cycleMatch[2] + 'T00:00:00Z');
    if (!isNaN(parsed.getTime())) {
      return { date: parsed, isExact: true };
    }
  }

  // Pattern: "re-opens in early December" or "opens in early February"
  const qualitativePattern = /(?:re-)?opens?\s+in\s+(early|mid|late)\s+(\w+)/i;
  const qualMatch = period.match(qualitativePattern);
  if (qualMatch) {
    const monthMap = { january: 0, february: 1, march: 2, april: 3, may: 4, june: 5,
                       july: 6, august: 7, september: 8, october: 9, november: 10, december: 11 };
    const month = monthMap[qualMatch[2].toLowerCase()];
    if (month !== undefined) {
      const year = new Date().getFullYear();
      const day = qualMatch[1] === 'early' ? 5 : qualMatch[1] === 'mid' ? 15 : 25;
      // Create as UTC date
      const parsed = new Date(Date.UTC(year, month, day));
      // If the date is in the past, assume next year
      if (parsed < new Date()) {
        parsed.setUTCFullYear(year + 1);
      }
      return { date: parsed, isExact: false };
    }
  }

  return { date: null, isExact: false };
}

/**
 * Calculate days between two dates (ignoring time component).
 * Positive = target is in future, Negative = target is in past.
 */
export function getDaysDifference(targetDate) {
  if (!targetDate) return null;
  
  const today = new Date();
  const todayStart = Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate());
  const target = new Date(targetDate);
  const targetStart = Date.UTC(target.getUTCFullYear(), target.getUTCMonth(), target.getUTCDate());
  const diffMs = targetStart - todayStart;
  return Math.ceil(diffMs / (1000 * 60 * 60 * 24));
}

/**
 * Check if a scholarship has a verified future cycle that supersedes a closed one.
 * This prevents marking a scholarship as CLOSED if a future cycle exists.
 */
export function hasVerifiedFutureCycle(scholarship) {
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  
  // Check for explicit opening_date in future
  if (scholarship.opening_date) {
    const openingDays = getDaysDifference(scholarship.opening_date);
    if (openingDays !== null && openingDays > 0) {
      return true;
    }
  }
  
  // Check for explicit future cycle indicators in application_period
  if (scholarship.application_period && typeof scholarship.application_period === 'string') {
    const period = scholarship.application_period;
    
    // Pattern: "opens YYYY-MM-DD" or "opens DD Month YYYY"
    const opensPattern = /opens?\s+(?:on\s+)?(\d{4}-\d{2}-\d{2}|\d{1,2}\s+\w+\s+\d{4})/i;
    const match = period.match(opensPattern);
    if (match) {
      const parsed = new Date(match[1] + 'T00:00:00Z');
      if (!isNaN(parsed.getTime()) && parsed > now) {
        return true;
      }
    }
    
    // Pattern: "2027 cycle: call opens 2027-01-01"
    const cyclePattern = /(\d{4})\s+cycle:?.*?opens?\s+(\d{4}-\d{2}-\d{2})/i;
    const cycleMatch = period.match(cyclePattern);
    if (cycleMatch) {
      const parsed = new Date(cycleMatch[2] + 'T00:00:00Z');
      if (!isNaN(parsed.getTime()) && parsed > now) {
        return true;
      }
    }
    
    // Pattern: "call opens Month YYYY" or "applications open Month YYYY"
    const monthYearPattern = /(?:call|applications?)\s+opens?\s+(\w+\s+\d{4})/i;
    const monthMatch = period.match(monthYearPattern);
    if (monthMatch) {
      const parsed = new Date(monthMatch[1] + ' 00:00:00Z');
      if (!isNaN(parsed.getTime()) && parsed > now) {
        return true;
      }
    }
    
    // Pattern: "re-opens in early December" or "opens in early February"
    const qualitativePattern = /(?:re-)?opens?\s+in\s+(early|mid|late)\s+(\w+)/i;
    const qualMatch = period.match(qualitativePattern);
    if (qualMatch) {
      const monthMap = { january: 0, february: 1, march: 2, april: 3, may: 4, june: 5,
                         july: 6, august: 7, september: 8, october: 9, november: 10, december: 11 };
      const month = monthMap[qualMatch[2].toLowerCase()];
      if (month !== undefined) {
        const year = new Date().getFullYear();
        const day = qualMatch[1] === 'early' ? 5 : qualMatch[1] === 'mid' ? 15 : 25;
        const parsed = new Date(Date.UTC(year, month, day));
        if (parsed > now) {
          return true;
        }
      }
    }
  }
  
  return false;
}

/**
 * Main lifecycle classification function.
 * Returns an object with all UI-relevant information.
 * 
 * Precedence (highest first):
 * 1. CLOSED (explicit status, is_archived, or deadline passed WITHOUT verified future cycle)
 * 2. UPCOMING (explicit status === 'upcoming' OR opening_date in future beyond window)
 * 3. CLOSING_SOON (currently open, deadline within CLOSING_SOON_THRESHOLD_DAYS)
 * 4. OPENING (opening_date within OPENING_WINDOW_DAYS)
 * 5. OPEN (default for active scholarships with valid deadline)
 * 6. UNKNOWN (missing critical dates)
 */
export function classifyLifecycle(scholarship) {
  // Parse dates
  const { date: deadlineDate, isExact: deadlineExact } = parseDate(scholarship, 'deadline');
  const { date: openingDate, isExact: openingExact } = parseDate(scholarship, 'opening');
  
  // Fallback: try to extract opening date from application_period
  let effectiveOpeningDate = openingDate;
  let effectiveOpeningExact = openingExact;
  if (!effectiveOpeningDate) {
    const extracted = parseOpeningDateFromPeriod(scholarship);
    effectiveOpeningDate = extracted.date;
    effectiveOpeningExact = extracted.isExact;
  }

  const daysUntilDeadline = getDaysDifference(deadlineDate);
  const daysUntilOpening = getDaysDifference(effectiveOpeningDate);

  // Check if there's a verified future cycle that supersedes current cycle
  const hasFutureCycle = hasVerifiedFutureCycle(scholarship);

  // Check if we have ANY date information
  const hasAnyDate = deadlineDate !== null || effectiveOpeningDate !== null;

  // 1. Check explicit closed/archived status first (highest precedence)
  if (scholarship.status === 'closed' || scholarship.is_archived) {
    // But don't mark as CLOSED if a verified future cycle exists
    if (hasFutureCycle) {
      // Fall through to other classifications
    } else {
      return {
        status: LIFECYCLE.CLOSED,
        label: LIFECYCLE_LABELS[LIFECYCLE.CLOSED],
        description: LIFECYCLE_DESCRIPTIONS[LIFECYCLE.CLOSED],
        deadlineDate,
        openingDate: effectiveOpeningDate,
        daysUntilDeadline,
        daysUntilOpening,
        isExactDeadline: deadlineExact,
        isExactOpening: effectiveOpeningExact,
        className: LIFECYCLE_CLASSES[LIFECYCLE.CLOSED],
        showCountdown: false,
        showApplyCTA: false,
        showOpeningDate: false,
      };
    }
  }

  // 2. Check deadline passed - but only CLOSED if NO future cycle
  if (deadlineDate && daysUntilDeadline !== null && daysUntilDeadline < 0) {
    if (hasFutureCycle) {
      // Don't mark as CLOSED, fall through to UPCOMING/OPENING
    } else {
      return {
        status: LIFECYCLE.CLOSED,
        label: LIFECYCLE_LABELS[LIFECYCLE.CLOSED],
        description: LIFECYCLE_DESCRIPTIONS[LIFECYCLE.CLOSED],
        deadlineDate,
        openingDate: effectiveOpeningDate,
        daysUntilDeadline,
        daysUntilOpening,
        isExactDeadline: deadlineExact,
        isExactOpening: effectiveOpeningExact,
        className: LIFECYCLE_CLASSES[LIFECYCLE.CLOSED],
        showCountdown: false,
        showApplyCTA: false,
        showOpeningDate: effectiveOpeningDate !== null,
      };
    }
  }

  // 3. Check explicit UPCOMING status (before CLOSING_SOON)
  if (scholarship.status === 'upcoming') {
    return {
      status: LIFECYCLE.UPCOMING,
      label: LIFECYCLE_LABELS[LIFECYCLE.UPCOMING],
      description: LIFECYCLE_DESCRIPTIONS[LIFECYCLE.UPCOMING],
      deadlineDate,
      openingDate: effectiveOpeningDate,
      daysUntilDeadline,
      daysUntilOpening,
      isExactDeadline: deadlineExact,
      isExactOpening: effectiveOpeningExact,
      className: LIFECYCLE_CLASSES[LIFECYCLE.UPCOMING],
      showCountdown: false,
      showApplyCTA: false,
      showOpeningDate: effectiveOpeningDate !== null,
    };
  }

  // 4. Check for UPCOMING based on opening date in future (outside window)
  // This must come BEFORE CLOSING_SOON check because a future opening supersedes a past deadline
  if (effectiveOpeningDate && daysUntilOpening !== null && daysUntilOpening > OPENING_WINDOW_DAYS) {
    return {
      status: LIFECYCLE.UPCOMING,
      label: LIFECYCLE_LABELS[LIFECYCLE.UPCOMING],
      description: LIFECYCLE_DESCRIPTIONS[LIFECYCLE.UPCOMING],
      deadlineDate,
      openingDate: effectiveOpeningDate,
      daysUntilDeadline,
      daysUntilOpening,
      isExactDeadline: deadlineExact,
      isExactOpening: effectiveOpeningExact,
      className: LIFECYCLE_CLASSES[LIFECYCLE.UPCOMING],
      showCountdown: false,
      showApplyCTA: false,
      showOpeningDate: true,
    };
  }

  // 5. Check for CLOSING_SOON (deadline within threshold)
  if (deadlineDate && daysUntilDeadline !== null && daysUntilDeadline >= 0 && daysUntilDeadline <= CLOSING_SOON_THRESHOLD_DAYS) {
    return {
      status: LIFECYCLE.CLOSING_SOON,
      label: LIFECYCLE_LABELS[LIFECYCLE.CLOSING_SOON],
      description: LIFECYCLE_DESCRIPTIONS[LIFECYCLE.CLOSING_SOON],
      deadlineDate,
      openingDate: effectiveOpeningDate,
      daysUntilDeadline,
      daysUntilOpening,
      isExactDeadline: deadlineExact,
      isExactOpening: effectiveOpeningExact,
      className: LIFECYCLE_CLASSES[LIFECYCLE.CLOSING_SOON],
      showCountdown: true,
      showApplyCTA: true,
      showOpeningDate: false,
    };
  }

  // 6. Check for OPENING phase (opening date within window)
  if (effectiveOpeningDate && daysUntilOpening !== null && daysUntilOpening >= 0 && daysUntilOpening <= OPENING_WINDOW_DAYS) {
    return {
      status: LIFECYCLE.OPENING,
      label: LIFECYCLE_LABELS[LIFECYCLE.OPENING],
      description: LIFECYCLE_DESCRIPTIONS[LIFECYCLE.OPENING],
      deadlineDate,
      openingDate: effectiveOpeningDate,
      daysUntilDeadline,
      daysUntilOpening,
      isExactDeadline: deadlineExact,
      isExactOpening: effectiveOpeningExact,
      className: LIFECYCLE_CLASSES[LIFECYCLE.OPENING],
      showCountdown: false,
      showApplyCTA: false,
      showOpeningDate: true,
    };
  }

  // 7. Default to OPEN for active scholarships WITH date information
  if (scholarship.status === 'open') {
    // If no date information at all, return UNKNOWN
    if (!hasAnyDate) {
      return {
        status: LIFECYCLE.UNKNOWN,
        label: LIFECYCLE_LABELS[LIFECYCLE.UNKNOWN],
        description: LIFECYCLE_DESCRIPTIONS[LIFECYCLE.UNKNOWN],
        deadlineDate,
        openingDate: effectiveOpeningDate,
        daysUntilDeadline,
        daysUntilOpening,
        isExactDeadline: deadlineExact,
        isExactOpening: effectiveOpeningExact,
        className: LIFECYCLE_CLASSES[LIFECYCLE.UNKNOWN],
        showCountdown: false,
        showApplyCTA: false,
        showOpeningDate: false,
      };
    }
    return {
      status: LIFECYCLE.OPEN,
      label: LIFECYCLE_LABELS[LIFECYCLE.OPEN],
      description: LIFECYCLE_DESCRIPTIONS[LIFECYCLE.OPEN],
      deadlineDate,
      openingDate: effectiveOpeningDate,
      daysUntilDeadline,
      daysUntilOpening,
      isExactDeadline: deadlineExact,
      isExactOpening: effectiveOpeningExact,
      className: LIFECYCLE_CLASSES[LIFECYCLE.OPEN],
      showCountdown: deadlineDate !== null && daysUntilDeadline !== null && daysUntilDeadline > 0,
      showApplyCTA: true,
      showOpeningDate: false,
    };
  }

  // 8. Unknown status
  return {
    status: LIFECYCLE.UNKNOWN,
    label: LIFECYCLE_LABELS[LIFECYCLE.UNKNOWN],
    description: LIFECYCLE_DESCRIPTIONS[LIFECYCLE.UNKNOWN],
    deadlineDate,
    openingDate: effectiveOpeningDate,
    daysUntilDeadline,
    daysUntilOpening,
    isExactDeadline: deadlineExact,
    isExactOpening: effectiveOpeningExact,
    className: LIFECYCLE_CLASSES[LIFECYCLE.UNKNOWN],
    showCountdown: false,
    showApplyCTA: false,
    showOpeningDate: effectiveOpeningDate !== null,
  };
}

/**
 * Get lifecycle badge component props for a scholarship.
 */
export function getLifecycleBadge(scholarship) {
  const lifecycle = classifyLifecycle(scholarship);
  return {
    label: lifecycle.label,
    className: `lifecycle-badge ${lifecycle.className}`,
    'data-lifecycle': lifecycle.status,
    'data-days-until': lifecycle.daysUntilDeadline,
  };
}

/**
 * Format deadline countdown text for display.
 */
export function formatCountdown(daysUntil, isExact) {
  if (daysUntil === null) return null;
  
  if (daysUntil < 0) return 'Deadline passed';
  if (daysUntil === 0) return 'Deadline today';
  if (daysUntil === 1) return '1 day left';
  if (daysUntil <= 7) return `${daysUntil} days left`;
  if (daysUntil <= 30) return `${daysUntil} days left`;
  if (!isExact) return `~${daysUntil} days left`;
  return `${daysUntil} days left`;
}

/**
 * Format opening date countdown text for display.
 */
export function formatOpeningCountdown(daysUntil, isExact) {
  if (daysUntil === null) return null;
  
  if (daysUntil < 0) return 'Opened';
  if (daysUntil === 0) return 'Opens today';
  if (daysUntil === 1) return 'Opens tomorrow';
  if (daysUntil <= 7) return `Opens in ${daysUntil} days`;
  if (daysUntil <= 30) return `Opens in ${daysUntil} days`;
  if (!isExact) return `Opens in ~${daysUntil} days`;
  return `Opens in ${daysUntil} days`;
}