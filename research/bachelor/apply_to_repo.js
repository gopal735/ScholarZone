#!/usr/bin/env node
/**
 * apply_to_repo.js
 *
 * Shaps the merged bachelor batch into the exact shape ScholarZone's own
 * maintenance stages will accept, and reports exactly what it would change.
 *
 * Why this exists: `do_add()` validates every insertion record against
 * `ScholarshipIngestionRecord`, which is `extra="forbid"`. A single unrecognised
 * key rejects the record with "schema: ...". It also:
 *   - accepts only status "open" or "upcoming" (a "closed" record is REJECTED)
 *   - requires official_source_url
 *   - reads citations from entry["detail"]["verification"]["source_citations"]
 *   - maps `documents` -> `required_documents`
 *   - pops status/description/benefits/funding_amount/funding_currency/funding_period
 *     to write straight to the row
 *   - drops underscore-prefixed keys
 * So a record can pass every check in validate_bachelor.js and still be rejected here.
 *
 * Read-only by default. Pass --write to emit staged copies of the repo config
 * files. It never touches backend/config/ in place — that is the maintenance
 * job's job, and it refuses to overwrite values that already exist.
 *
 * Usage:
 *   node research/bachelor/apply_to_repo.js           # report + stage to _merged/staged
 *   node research/bachelor/apply_to_repo.js --write   # same; files still land in _merged/staged
 */

const fs = require('fs');
const path = require('path');

const DIR = __dirname;
const MERGED = path.join(DIR, '_merged');
const STAGED = path.join(MERGED, 'staged');
const TODAY = '2026-10-03';

// Verbatim from backend/app/services/scholarship_ingestion.py
const INGESTION_FIELDS = [
  'name', 'country', 'degree_levels', 'funding_type', 'official_source_url',
  'is_verified', 'last_verified_date', 'region', 'duration', 'deadline',
  'deadline_date', 'deadline_precision', 'application_period', 'eligibility_summary',
  'eligibility', 'coverage', 'required_documents', 'catalogue_url',
  'official_updates_url', 'official_source', 'english_requirement', 'requirements',
  'application_method', 'selection_notes', 'program_type', 'best_fit', 'notes',
  'image_url', 'image_source_url', 'image_source_type', 'image_verified_at',
  'image_alt_text', 'legacy_titles', 'preferred_id',
];
// popped by do_add() and written to the row directly
const ROW_ONLY = ['status', 'description', 'benefits', 'funding_amount', 'funding_currency', 'funding_period'];
const INGESTION_SET = new Set(INGESTION_FIELDS);

const notes = [];
const blocked = [];

const j = (f) => JSON.parse(fs.readFileSync(path.join(MERGED, f), 'utf8'));
const has = (f) => fs.existsSync(path.join(MERGED, f));

if (!has('new_scholarships.new.json')) {
  console.error('No merged output found. Run: node research/bachelor/validate_bachelor.js --write');
  process.exit(1);
}

const inserts = j('new_scholarships.new.json').records || [];
const pending = has('programme_details.pending.json') ? j('programme_details.pending.json') : [];
const logosNew = has('official_logo_overrides.new.json') ? j('official_logo_overrides.new.json') : {};

// ------------------------------------------------------------------ insertions
const stagedInserts = [];
const insertByName = new Map();
const needsStatusDecision = [];

for (const rec of inserts) {
  const name = rec.name || '(unnamed)';

  // do_add() hard-rejects anything that is not open/upcoming.
  // This is a semantics question, not a data error: the agents recorded the honest
  // CURRENT-cycle status. do_add()'s status column means "live in the catalogue",
  // and the later stage even flips closed -> active, so a recurring annual award
  // whose window has passed belongs in the catalogue as "upcoming" with its
  // next-cycle expectation in status_note. That is a coordinator call, so these are
  // emitted separately instead of being silently rewritten.
  const status = String(rec.status || '').toLowerCase();
  if (!['open', 'upcoming'].includes(status)) {
    const enrichment = pending.find(p => p._match_name === name);
    const nextCycle = enrichment && enrichment.official && enrichment.official.status_note;
    needsStatusDecision.push({
      name,
      current_status: rec.status,
      suggested_status: 'upcoming',
      deadline_date: rec.deadline_date,
      deadline: rec.deadline,
      application_cycle: enrichment?.official?.application_cycle ?? null,
      status_note: enrichment?.official?.status_note ?? null,
      has_next_cycle_expectation: !!nextCycle,
      rationale: 'do_add() accepts only open/upcoming. If this award recurs annually, set status "upcoming" so it can be catalogued; the next-cycle expectation must already be in status_note. If it has genuinely lapsed for good, it does not belong in the catalogue at all.',
      decision: 'PENDING',
    });
    blocked.push({
      name, reason: `status="${rec.status}" — do_add() accepts only "open" or "upcoming"`,
      fix: 'see needs_status_decision.json — confirm the award recurs, then set status "upcoming"',
    });
    continue;
  }
  if (!rec.official_source_url) {
    blocked.push({ name, reason: 'no official_source_url', fix: 'required by do_add()' });
    continue;
  }

  // match the enrichment payload back to this insertion by name
  const pd = pending.find(p => p._match_name === name || (p.official && p.official.program_type && p.official.program_type === rec.program_type));
  const enrichment = pending.find(p => p._match_name === name);

  const flat = {};
  const dropped = [];

  for (const [k, v] of Object.entries(rec)) {
    if (k.startsWith('_')) { dropped.push(k); continue; }            // do_add() drops these anyway
    if (ROW_ONLY.includes(k)) { flat[k] = v; continue; }            // popped to the row
    if (k === 'documents') { flat.required_documents = v; continue; } // do_add() remaps this
    if (INGESTION_SET.has(k)) { flat[k] = v; continue; }
    dropped.push(k);
  }

  // anything the model has no field for would fail extra="forbid"
  const forbidden = dropped.filter(k => !k.startsWith('_'));
  if (forbidden.length) {
    notes.push({ name, note: `dropped ${forbidden.length} field(s) the ingestion model forbids: ${forbidden.join(', ')}` });
  }

  // citations are mandatory for do_add(); it reads them from detail.verification
  const citations = (enrichment && enrichment.verification && enrichment.verification.source_citations) || [];
  if (!citations.length) {
    blocked.push({ name, reason: 'no source_citations — do_add() would reject', fix: 'record is incomplete' });
    continue;
  }

  const out = {
    ...flat,
    detail: {
      official_details: enrichment ? enrichment.official : null,
      applicant_utility: enrichment ? enrichment.applicant_utility : null,
      verification: enrichment ? enrichment.verification : null,
    },
  };
  if (!out.detail.official_details || !out.detail.verification) {
    blocked.push({ name, reason: 'no matching enrichment payload', fix: 'merge could not pair the insertion with its programme_details block' });
    continue;
  }
  // ALLOWED_DETAIL_KEYS = {"official_details", "applicant_utility", "verification"}
  for (const k of Object.keys(out.detail)) {
    if (!['official_details', 'applicant_utility', 'verification'].includes(k)) delete out.detail[k];
  }

  stagedInserts.push(out);
  insertByName.set(name, out);
}

// ------------------------------------------------------------------ refreshes
// programme_details.json is keyed by numeric id and the stage fills EMPTY fields
// only, so a refresh must carry the id it belongs to.
const refreshByName = new Map();
if (has('refreshes.json')) {
  for (const r of j('refreshes.json').records || []) refreshByName.set(r.name, r);
}
const stagedRefreshes = pending.filter(p => p._route === 'REFRESH_EXISTING_ID').map(p => ({
  id: p._target_id,
  official: p.official,
  applicant_utility: p.applicant_utility,
  verification: p.verification,
}));

// ------------------------------------------------------------------ logos
// official_logo_overrides.json is keyed by official host and an entry is "a
// candidate, not an approval" (rule 4), so these are staged for the logo stage
// rather than treated as final.
const existingLogos = fs.existsSync(path.join(DIR, '..', '..', 'backend', 'config', 'official_logo_overrides.json'))
  ? JSON.parse(fs.readFileSync(path.join(DIR, '..', '..', 'backend', 'config', 'official_logo_overrides.json'), 'utf8'))
  : {};
const logoAdditions = {};
const logoConflicts = [];
for (const [host, e] of Object.entries(logosNew)) {
  if (existingLogos[host]) {
    logoConflicts.push({ host, existing_url: existingLogos[host].url, new_url: e.url });
    continue;
  }
  const { _from, _award, ...clean } = e;
  logoAdditions[host] = clean;
}

// ------------------------------------------------------------------ write staged
fs.mkdirSync(STAGED, { recursive: true });
if (stagedInserts.length) {
  const merged = {
    generated_for: TODAY,
    note: 'Staged bachelor-batch insertions. Append records[] to backend/config/new_scholarships.json, then run the maintenance "add" stage. Records already present by title or by official_source_url are upserted by that stage, not duplicated.',
    count: stagedInserts.length,
    records: stagedInserts,
  };
  fs.writeFileSync(path.join(STAGED, 'new_scholarships.append.json'), JSON.stringify(merged, null, 2));
}
if (stagedRefreshes.length) {
  fs.writeFileSync(path.join(STAGED, 'programme_details.refresh.json'), JSON.stringify({
    note: 'Apply each entry to its existing id in backend/config/programme_details.json. The stage fills EMPTY fields only, so a value already present is never overwritten — a correction to an existing value stays a manual decision.',
    count: stagedRefreshes.length,
    records: stagedRefreshes,
  }, null, 2));
}
if (Object.keys(logoAdditions).length) {
  const mergedLogos = {
    _comment: 'Audited official logo overrides, keyed by the institution\'s own domain.',
    _rules: existingLogos._rules || [],
    ...logoAdditions,
  };
  fs.writeFileSync(path.join(STAGED, 'official_logo_overrides.append.json'), JSON.stringify(mergedLogos, null, 2));
}
if (needsStatusDecision.length) {
  fs.writeFileSync(path.join(STAGED, 'needs_status_decision.json'), JSON.stringify({
    note: 'do_add() inserts only status open|upcoming. These records carry an honest current-cycle status of closed/upcoming-superseded, so they cannot be inserted as-is. For an award that recurs annually, setting status "upcoming" catalogues it correctly and the next-cycle expectation belongs in status_note. Confirm each award really recurs before flipping it; if it has lapsed for good, drop it instead of cataloguing it.',
    count: needsStatusDecision.length,
    records: needsStatusDecision,
  }, null, 2));
}

// ------------------------------------------------------------------ report
console.log('='.repeat(74));
console.log('APPLY-TO-REPO SHAPING REPORT');
console.log('='.repeat(74));
console.log('insertion records in   :', inserts.length);
console.log('ready for do_add()      :', stagedInserts.length);
console.log('blocked / needs a fix   :', blocked.length);
console.log('programme_details refresh:', stagedRefreshes.length);
console.log('new logo hosts          :', Object.keys(logoAdditions).length);
console.log('logo host conflicts     :', logoConflicts.length);
console.log('');

if (notes.length) {
  console.log('--- FIELD DROPS (extra="forbid" would have rejected these) ---');
  notes.forEach(n => console.log('  ~ ' + n.name + '\n      ' + n.note));
  console.log('');
}
if (blocked.length) {
  console.log('--- BLOCKED (do_add() would reject these) ---');
  blocked.forEach(b => console.log(`  x ${b.name}\n      reason: ${b.reason}\n      fix:    ${b.fix}`));
  console.log('');
}
if (logoConflicts.length) {
  console.log('--- LOGO HOST CONFLICTS (key already exists; do NOT add a second entry) ---');
  logoConflicts.forEach(c => console.log(`  ! ${c.host}\n      existing: ${c.existing_url}\n      new     : ${c.new_url}`));
  console.log('');
}

console.log('STAGED OUTPUT (nothing written to backend/config/):');
for (const f of fs.readdirSync(STAGED)) console.log('  _merged/staged/' + f);
console.log('');
console.log('To land them:');
console.log('  1. append _merged/staged/new_scholarships.append.json records[] into');
console.log('     backend/config/new_scholarships.json');
console.log('  2. python -m app.jobs.scholarzone_maintenance add --dry-run     # then without --dry-run');
console.log('  3. merge _merged/staged/programme_details.refresh.json into backend/config/programme_details.json by id');
console.log('  4. python -m app.jobs.scholarzone_maintenance programme_details --dry-run');
console.log('  5. merge _merged/staged/official_logo_overrides.append.json into');
console.log('     backend/config/official_logo_overrides.json, then run the logos stage');