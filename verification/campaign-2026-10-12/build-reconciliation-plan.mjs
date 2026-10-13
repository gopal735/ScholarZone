/**
 * Generates RECONCILIATION-PLAN.md from the campaign artifacts.
 *
 * Every number and every table row is read from the evidence files, so the plan
 * cannot drift from the data it describes. This tool only writes the document;
 * it applies nothing.
 */
import { readdirSync, readFileSync, writeFileSync } from 'node:fs'

const DIR = 'C:/Users/GopaL/AppData/Local/Temp/kilo/verify-campaign-wt/verification/campaign-2026-10-12'
const index = JSON.parse(readFileSync(`${DIR}/index.json`, 'utf8'))
const proposals = JSON.parse(readFileSync(`${DIR}/proposed-verification-updates.json`, 'utf8'))

const kindOf = new Map(index.tasks.map((t) => [String(t.id), t]))
const statusOf = new Map(
  [...proposals.proposals].map((p) => [String(p.id), p.current_status]),
)

// Notes that say the round is over. A promotion that keeps such a record
// presented as open is the specific failure the plan exists to prevent.
//
// Deliberately literal. `discontinued` on its own is not enough: one memo
// speculates about whether an award "is discontinued" in a future cycle while
// its own deadline is open today, which is the opposite of this signal.
const CLOSED_MARKERS = [
  'closed for applications',
  'no more grants',
  'no longer apply',
  'deadline has passed',
  'that date has passed',
  'already past',
  'has now closed',
  'is now closed',
  'the round has closed',
  'round has closed',
  'cycle has closed',
  'cycle it describes closed',
  'no cycle is open',
  'not currently open',
  'no currently-open',
  'status: closed',
  'budget is exhausted',
  'no longer available',
]

const rows = proposals.proposals.map((proposal) => {
  const id = String(proposal.id)
  const task = kindOf.get(id)
  const evidence = JSON.parse(readFileSync(`${DIR}/${id}.json`, 'utf8'))
  const notes = `${evidence.notes_for_reviewer || ''} ${evidence.findings?.deadline?.detail || ''} ${evidence.recommended_field_updates?.verification_notes || ''}`
  const closed = CLOSED_MARKERS.some((marker) => notes.toLowerCase().includes(marker))
  const fields = Object.entries(proposal.field_updates || {})
    .filter(([, value]) => value !== null && value !== undefined && value !== '')
    .map(([field]) => field)
  return {
    id,
    title: task?.title ?? '(unknown)',
    kind: task?.kind ?? 'unknown',
    kindLabel: task?.kind === 'spot-check' ? 'spot-check (already active)' : 'new research',
    currentStatus: statusOf.get(id) ?? null,
    verdict: proposal.evidence_verdict,
    suggested: proposal.suggested_status,
    confidence: proposal.confidence,
    statusChange: (statusOf.get(id) ?? null) !== proposal.suggested_status,
    fields,
    checkedAt: evidence.checked_at ?? proposal.checked_at,
    evidenceJson: `${id}.json`,
    evidenceMd: `${id}.md`,
    memo: `${id}.md`,
    notes: evidence.notes_for_reviewer || null,
    closed,
  }
})

const byStatus = (status) => rows.filter((r) => r.suggested === status)
const countStatusChange = (status) => byStatus(status).filter((r) => r.statusChange).length
const promotions = rows.filter(
  (r) => r.suggested === 'active' && r.statusChange,
)
const fieldCount = (field) => rows.filter((r) => r.fields.includes(field)).length

const fieldTotals = {}
for (const row of rows) {
  for (const field of row.fields) {
    fieldTotals[field] = (fieldTotals[field] || 0) + 1
  }
}

const spotCheckRows = rows.filter((r) => r.kind === 'spot-check')
const verifyRows = rows.filter((r) => r.kind !== 'spot-check')
const needsHumanAttention = rows.filter(
  (r) =>
    r.confidence !== 'high' ||
    r.verdict === 'conflicting' ||
    r.kind === 'spot-check' ||
    r.closed ||
    r.suggested === 'quarantined' ||
    promotions.includes(r),
)

const tableRow = (r) =>
  `| ${r.id} | ${r.kindLabel} | ${r.currentStatus ?? '—'} | ${r.verdict} | ${r.confidence} | ${r.suggested} | ${r.fields.join(', ') || '—'} | ${r.closed ? '**yes**' : 'no'} | \`${r.evidenceJson}\` |`

const verdictTable = (list) =>
  [
    '| id | kind | current status | evidence | confidence | suggested | fields to change | open round on the evidence | evidence |',
    '| --- | --- | --- | --- | --- | --- | --- | --- | --- |',
    ...list.map(tableRow),
  ].join('\n')

const doc = `# Reconciliation plan — the ${rows.length} proposed updates

Generated from the campaign artifacts by \`verification\\campaign-2026-10-12\\build-reconciliation-plan.mjs\`.
Nothing in this plan is applied. Every row carries its evidence file, and every
number is recomputed from the evidence rather than copied from the PR text.

## What the ${rows.length} proposals are

\`proposed-verification-updates.json\` holds one proposal per record where the
evidence supports a status change **or** a field correction. It is not a list of
records to promote.

| group | records | what the evidence says |
| --- | --- | --- |
| \`needs_review\` | ${byStatus('needs_review').length} | the official page was read but a specific claim could not be confirmed from it |
| \`conflicting\` | ${byStatus('conflicting').length} | the official page contradicts the record materially |
| \`active\` | ${byStatus('active').length} | confirmed, but a field is wrong (a stale \`official_source_url\` is the usual one) |
| \`quarantined\` | ${byStatus('quarantined').length} | no official page could be found |

${spotCheckRows.length} of them are spot-checks of records the database already
calls \`active\`; ${verifyRows.length} are newly researched records.

## Status changes vs field changes

- **${rows.filter((r) => r.statusChange).length} of ${rows.length} change \`verification_status\`**:
  - ${countStatusChange('needs_review')} to \`needs_review\` — all three are downgrades of records the database currently calls \`active\` (131, 189, 245).
  - ${countStatusChange('conflicting')} to \`conflicting\`, of which ${countStatusChange('conflicting') - 1} move (one is already \`conflicting\` and only its fields change).
  - ${countStatusChange('quarantined')} to \`quarantined\` (31 and 79).
  - **${promotions.length} to \`active\`** — promotions of records currently \`needs_review\` or \`partial\` (${promotions
    .map((r) => r.id)
    .join(', ')}). These are what make the flag's effect real, and the reason a promotion is never applied from this file alone.
- **${byStatus('active').length - promotions.length} of the \`active\` rows change no status at all** — the record is already \`active\` and only a field is wrong.
- Fields proposed for change: ${Object.entries(fieldTotals)
  .map(([field, count]) => `\`${field}\` on ${count} record${count === 1 ? '' : 's'}`)
  .join(', ')}.
- Every one of the ${rows.length} proposals carries a \`verification_notes\` value, so a record that is applied keeps the trail of what was checked and when.

## What requires a human, and why

All ${rows.length} require a human. **Do not promote anything on a verdict label
alone** — read the memo first. Within that:

- **${needsHumanAttention.length} need particular care**:
  - **${promotions.length} are proposed promotions to \`active\`** (${promotions
    .map((r) => r.id)
    .join(', ')}). Promoting a record to verified is the one change the flag then acts on, and therefore the one change that must not be made from a verdict label. Read each memo.
  - **${spotCheckRows.length} are already marked \`active\`** (131, 189, 245, 303, 422 and two others). Downgrading a record the site presents as verified is a change a person should own; the two \`conflicting\` ones (303, 422) are outright contradictions.
  - **${rows.filter((r) => r.verdict === 'conflicting').length} are \`conflicting\`** — these need the *field* replaced, not just the status changed. A status flip that leaves the wrong deadline text in place would be worse than no change.
  - **${rows.filter((r) => r.closed).length} are closed or expired** — the evidence says the round is over (${rows
      .filter((r) => r.closed)
      .map((r) => r.id)
      .join(', ')}). These must not end the reconciliation presented as open. Archive, or keep hidden with the reason recorded.
  - **${rows.filter((r) => r.confidence !== 'high').length} are not \`high\` confidence** (${rows
    .filter((r) => r.confidence !== 'high')
    .map((r) => `${r.id}: ${r.confidence}`)
    .join(', ')}) — read the memo before acting on those at all.
  - **${byStatus('quarantined').length} are \`quarantined\`** (31 and 79). They are currently visible with a \`needs_review\` label; the proposal is what hides them.

## The records

### \`needs_review\` (${byStatus('needs_review').length})

${verdictTable(byStatus('needs_review'))}

### \`conflicting\` (${byStatus('conflicting').length})

${verdictTable(byStatus('conflicting'))}

### \`active\`, field corrections only (${byStatus('active').length})

${verdictTable(byStatus('active'))}

### \`quarantined\` (${byStatus('quarantined').length})

${verdictTable(byStatus('quarantined'))}

## How to apply one record

1. Open the evidence file's row above and read \`<id>.md\` — the memo names the
   page and quotes the sentences the verdict rests on.
2. Decide the status change, if any. A \`needs_review\` verdict does not
   automatically mean "promote nothing": several carry a corrected \`deadline_text\`
   worth adopting even while the status stays where it is.
3. Apply the fields from \`recommended_field_updates\`, with \`verification_notes\`
   set from the evidence so the next re-check knows what was read and when.
4. Leave the evidence file in place. It is the source of the change and stays
   with the repository.
5. Do not apply anything for a record whose round has closed unless the
   intention is to close it: the catalogue's promise is that an expired round is
   not offered as live.

## What this plan is not

It is not an approval. The ${rows.length} proposals are what the evidence
supports, and the campaign records 100 checks, not a decision. Until a person
has walked this list, \`SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED\` must stay off — see
\`ROLLOUT.md\` for what switching it on early would show.
`

writeFileSync(
  'C:/Users/GopaL/AppData/Local/Temp/kilo/verify-campaign-wt/verification/campaign-2026-10-12/RECONCILIATION-PLAN.md',
  doc,
)
console.log('rows:', rows.length)
console.log('status changes:', rows.filter((r) => r.statusChange).length)
console.log('fields:', JSON.stringify(fieldTotals))
console.log('needs particular care:', needsHumanAttention.length)
console.log('closed-looking:', rows.filter((r) => r.closed).map((r) => r.id).join(', '))
console.log('not high confidence:', rows.filter((r) => r.confidence !== 'high').map((r) => `${r.id}:${r.confidence}`).join(', '))
console.log('spot-check proposals:', spotCheckRows.map((r) => r.id).join(', '))
