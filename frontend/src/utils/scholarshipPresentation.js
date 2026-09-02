const statusMetadata = {
  open: { label: 'Open', className: 'open' },
  'closing-soon': { label: 'Closing soon', className: 'closing-soon' },
  closed: { label: 'Closed', className: 'closed' },
}

function getDerivedStatus(deadlineDate) {
  if (!deadlineDate) {
    return 'open'
  }

  const deadline = new Date(`${deadlineDate}T00:00:00`)
  if (Number.isNaN(deadline.getTime())) {
    return 'open'
  }

  const today = new Date()
  today.setHours(0, 0, 0, 0)
  if (deadline < today) {
    return 'closed'
  }

  const closingSoonThreshold = new Date(today)
  closingSoonThreshold.setDate(today.getDate() + 30)
  return deadline <= closingSoonThreshold ? 'closing-soon' : 'open'
}

export function getScholarshipStatus(scholarship) {
  const status = scholarship.status || getDerivedStatus(scholarship.deadline_date)
  return statusMetadata[status] || statusMetadata.open
}

export function getDeadlineLabel(scholarship) {
  return scholarship.deadline || scholarship.deadline_date || 'Deadline to be confirmed'
}

export function getLastVerifiedLabel(value) {
  if (!value) {
    return 'Verification date pending'
  }

  const verifiedDate = new Date(`${value}T00:00:00`)
  if (Number.isNaN(verifiedDate.getTime())) {
    return 'Verification date pending'
  }

  return `Verified ${new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' }).format(verifiedDate)}`
}
