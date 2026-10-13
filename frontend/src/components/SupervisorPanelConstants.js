/* Shared constants for SupervisorPanel. Kept separate so the component
   file exports only the component, satisfying the React Fast Refresh rule. */

export const BAND_LABELS = {
  strong_research_alignment: 'Strong research alignment',
  moderate_research_alignment: 'Moderate research alignment',
  related: 'Related',
  insufficient_evidence: 'Not enough evidence to compare',
}

export const AVAILABILITY_LABELS = {
  masters_supervision: "Master's supervision",
  phd_supervision: 'PhD supervision',
  postdoc_supervision: 'Postdoctoral supervision',
  funding: 'Funding',
}

/* Administrative contacts, published in place of a supervisor. The wording is
   deliberately flat: these are offices, not academics, and a label that
   flattered them into looking like professors would misrepresent them. */
export const CONTACT_KIND_LABELS = {
  scholarship_office: 'Scholarship office',
  programme_office: 'Programme office',
  admissions: 'Admissions office',
  general_enquiries: 'General enquiries',
}

export const OUTREACH_ACTIONS = [
  { value: 'draft', label: 'Save as draft' },
  { value: 'sent', label: 'Mark as sent' },
  { value: 'follow_up_due', label: 'Follow-up due' },
  { value: 'replied', label: 'A reply arrived' },
  { value: 'positive', label: 'Positive reply' },
  { value: 'negative', label: 'Negative reply' },
  { value: 'no_response', label: 'No response' },
  { value: 'closed', label: 'Close this' },
]