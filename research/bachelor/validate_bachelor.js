#!/usr/bin/env node
/**
 * validate_bachelor.js  —  ScholarZone bachelor's batch validator / merger
 *
 * Reads every research/bachelor/NN-*.json produced by the research agents,
 * validates it against research/bachelor/SCHEMA_CONTRACT.md AND against the real
 * invariants enforced by backend/tests/test_programme_details.py and
 * backend/config/programme_details.json `_rules`, then merges into:
 *
 *   1. research/bachelor/_merged/new_scholarships.new.json
 *   2. research/bachelor/_merged/programme_details.pending.json
 *   3. research/bachelor/_merged/official_logo_overrides.new.json
 *
 * Usage:
 *   node research/bachelor/validate_bachelor.js           # report only
 *   node research/bachelor/validate_bachelor.js --write   # report + write merged
 */

const fs = require('fs');
const path = require('path');

const DIR = __dirname;
const MERGED = path.join(DIR, '_merged');
const WRITE = process.argv.includes('--write');
const TODAY = '2026-10-03';

// ---- contract shape ----
const TOP_KEYS = [
  'new_scholarship', 'programme_detail_official', 'programme_detail_applicant_utility',
  'programme_detail_verification', 'logo_override', 'research_notes',
];
const NS_REQUIRED = ['name', 'country', 'region', 'degree_levels', 'funding_type', 'official_source_url', 'status'];
const PD_REQUIRED = [
  'official_source_urls', 'application_cycle', 'deadline_central_display', 'deadline_note',
  'status', 'status_note', 'funding_currency', 'funding_period', 'funding_duration',
  'tuition_coverage', 'tuition_coverage_note', 'fully_funded', 'funding_label', 'benefits',
  'eligibility', 'citizenship_residency', 'international_eligibility', 'degree_levels',
  'application_method', 'application_route', 'requirements', 'documents',
  'english_requirement_note', 'selection_criteria', 'duration', 'award_holder_conditions',
  'description', 'program_type', 'region', 'coverage', 'last_verified_date',
];
const AU_REQUIRED = [
  'application_readiness_checklist', 'common_rejection_risks', 'estimated_uncovered_costs',
  'document_audit', 'alerts', 'submission_workflow',
];
const V_REQUIRED = [
  'cycle_verified', 'verification_confidence', 'official_fields_confirmed',
  'institution_check_required', 'unverified_or_removed_claims', 'source_citations', 'researched_by',
];

// ---- repo-enforced invariants ----
const UTILITY_ONLY_BANNED_IN_OFFICIAL = [
  'application_readiness_checklist', 'common_rejection_risks', 'estimated_uncovered_costs',
  'document_audit', 'alerts', 'submission_workflow',
];
const PLACEHOLDER_BANNED = new Set(['', 'n/a', 'na', '-', 'none', 'tbd', 'unknown', 'null']);
const PLACEHOLDER_FIELDS = ['funding_currency', 'funding_period', 'deadline_central', 'application_route', 'study_mode'];
const VALID_REGIONS = new Set(['Europe', 'United States', 'Canada', 'Australia', 'Singapore', 'Malaysia']);
const VALID_STATUS = new Set(['OPEN', 'UPCOMING', 'CLOSED', 'ONGOING', 'DISCONTINUED', 'PROGRAMME_SPECIFIC']);

// logo ban list — same spirit as the repo's official_logo_overrides rules
const LOGO_BANNED_HOSTS = [
  'scholarshipsinstitute.com', 'brightscholarship.com', 'nspscholarships.com', 'crispng.com',
  'careerglobalconnect', 'wemakescholars', 'wikipedia.org', 'wikimedia.org', 'commons.wikimedia',
  'shutterstock', 'gettyimages', 'istockphoto', 'imgur.com', 'pinterest', 'pinimg',
  'facebook.com', 'twitter.com', 'x.com', 'linkedin.com', 'youtube.com', 'instagram.com',
  'reddit.com', 'blogspot', 'medium.com', 'statically.io', 'googleusercontent', 'cloudfront',
  'freepik', 'vecteezy', 'dreamstime', 'canva', 'brandfetch', 'logowik', 'seeklogo', 'deviantart',
];

const errors = [];
const warnings = [];
const err = (f, m) => errors.push(`${f}: ${m}`);
const warn = (f, m) => warnings.push(`${f}: ${m}`);
const isArr = Array.isArray;
const missingKeys = (obj, keys) => keys.filter(k => !(k in (obj || {})));

const records = [];
const incomplete = [];
// Record discovery is by CONTENT, never by filename. Matching on a slot prefix
// has now twice hidden finished work: `b\d\d-` skipped every slot past b09, and
// then `^(\d\d|b\d{2,3})-` skipped every wave whose prefix was not a slot
// (w4-*), so eight new files were invisible and the run still reported
// "23 complete, 0 incomplete". A file is a record if it carries a
// new_scholarship block, whatever it is called.
const RECORD_KEY = 'new_scholarship';
// Slots are two digits (21) or two-to-three with a b prefix (b01..b150). One
// helper for every call site: a hard slice(0,2) turned "b134" into "b1", and
// because refreshSlots is compared against this value, refresh exclusion
// silently stopped working for every slot past b09.
const slotOfFile = (f) => (String(f).match(/^(\d\d|b\d{2,3})(?:-|_)/) || [, String(f)])[1];
const slotOf = slotOfFile;

// Unparseable research files are collected, not discarded. The first version of
// this filter caught the parse error and returned false, which made a malformed
// record disappear completely: it counted as neither complete nor incomplete and
// the run still reported success. A file that cannot be parsed is a defect in
// the record, and the run must say so.
const unreadable = [];
const files = fs.readdirSync(DIR)
  .filter(f => f.endsWith('.json') && !f.startsWith('_') && !f.startsWith('.'))
  .filter(f => {
    let o;
    try {
      o = JSON.parse(fs.readFileSync(path.join(DIR, f), 'utf8'));
    } catch (e) {
      unreadable.push({ file: f, detail: String(e.message).slice(0, 200) });
      return false;
    }
    return o && typeof o === 'object' && RECORD_KEY in o;
  })
  .sort();
const SLOT_RE = /^(\d\d|b\d{2,3})-/;
const seenNames = new Map();
const seenUrls = new Map();
const seenLogos = new Map();
const allCitations = new Set();

/**
 * Repair pass: an agent that means "not published" sometimes writes the literal
 * STRING "null" instead of JSON null. The repo test rejects placeholder strings,
 * so this is a hard error — but the mapping is unambiguous, so fix it in place
 * and record the repair rather than failing the record over it.
 */
const repairs = [];
function repairNullStrings(obj, f, blockName) {
  if (!obj || typeof obj !== 'object') return;
  for (const k of Object.keys(obj)) {
    if (obj[k] === 'null') {
      obj[k] = null;
      repairs.push(`${f}: ${blockName}.${k}  "null" -> null`);
    } else if (Array.isArray(obj[k])) {
      obj[k] = obj[k].map(v => (v === 'null' ? null : v));
    } else if (obj[k] && typeof obj[k] === 'object') {
      repairNullStrings(obj[k], f, `${blockName}.${k}`);
    }
  }
}

for (const f of files) {
  let o;
  try {
    o = JSON.parse(fs.readFileSync(path.join(DIR, f), 'utf8'));
  } catch (e) {
    err(f, `INVALID JSON — ${e.message}`);
    continue;
  }
  repairNullStrings(o.new_scholarship, f, 'new_scholarship');
  repairNullStrings(o.programme_detail_official, f, 'programme_detail_official');
  repairNullStrings(o.programme_detail_applicant_utility, f, 'applicant_utility');
  repairNullStrings(o.programme_detail_verification, f, 'verification');
  repairNullStrings(o.logo_override, f, 'logo_override');
  if (o.research_notes && typeof o.research_notes === 'object') {
    for (const k of Object.keys(o.research_notes)) {
      if (o.research_notes[k] === 'null') o.research_notes[k] = null;
    }
  }

  const mk = missingKeys(o, TOP_KEYS);
  if (mk.length) err(f, `missing top-level keys: ${mk.join(', ')}`);
  const extra = Object.keys(o).filter(k => !TOP_KEYS.includes(k));
  if (extra.length) warn(f, `unexpected top-level keys: ${extra.join(', ')}`);

  const ns = o.new_scholarship || {};
  const pd = o.programme_detail_official || {};
  const au = o.programme_detail_applicant_utility || {};
  const v = o.programme_detail_verification || {};

  // ---------- insertion record ----------
  const nsMiss = missingKeys(ns, NS_REQUIRED);
  if (nsMiss.length) err(f, `new_scholarship missing: ${nsMiss.join(', ')}`);

  if (ns.region && !VALID_REGIONS.has(ns.region)) {
    err(f, `new_scholarship.region "${ns.region}" not in {${[...VALID_REGIONS].join(', ')}}`);
  }
  if (ns.degree_levels && !/bachelor|undergraduate|foundation/i.test(String(ns.degree_levels))) {
    err(f, `new_scholarship.degree_levels "${ns.degree_levels}" does not mention Bachelor's/Undergraduate — out of scope`);
  }
  if (ns.official_source_url && !/^https:\/\//.test(ns.official_source_url)) {
    err(f, `official_source_url not https: ${ns.official_source_url}`);
  }
if (ns.name) {
    const key = ns.name.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
    // Provisional only — title_overrides may still disambiguate this later, so the
    // authoritative collision check runs after retitling, further down.
    if (seenNames.has(key)) warn(f, `shares the award name "${ns.name}" with ${seenNames.get(key)} (checked again after title overrides)`);
    else seenNames.set(key, f);
  }
  if (ns.official_source_url) {
    if (seenUrls.has(ns.official_source_url)) {
      warn(f, `same official_source_url as ${seenUrls.get(ns.official_source_url)} — possible duplicate`);
    } else seenUrls.set(ns.official_source_url, f);
  }
  if (ns.last_verified_date && ns.last_verified_date !== TODAY) {
    warn(f, `new_scholarship.last_verified_date "${ns.last_verified_date}" expected ${TODAY}`);
  }
  // exact date only if officially stated
  if (ns.deadline_date && !/^\d{4}-\d{2}-\d{2}$/.test(ns.deadline_date)) {
    err(f, `deadline_date not ISO YYYY-MM-DD: ${ns.deadline_date}`);
  }
  if (ns.deadline_date && ns.deadline_date < TODAY && !/closed/i.test(String(ns.status))) {
    err(f, `deadline_date ${ns.deadline_date} is past but status is "${ns.status}"`);
  }
  // placeholder strings
  for (const k of ['funding_currency', 'funding_period']) {
    // only a NON-NULL STRING can be a placeholder; a real null is the correct answer
    if (typeof ns[k] === 'string' && PLACEHOLDER_BANNED.has(ns[k].toLowerCase().trim())) {
      err(f, `new_scholarship.${k} is placeholder "${ns[k]}" — use null`);
    }
  }
  if (ns.funding_amount != null && !ns.funding_currency) {
    err(f, 'funding_amount present without funding_currency');
  }

  // ---------- enrichment block ----------
  const pdMiss = missingKeys(pd, PD_REQUIRED);
  if (pdMiss.length) err(f, `programme_detail_official missing: ${pdMiss.join(', ')}`);
  for (const k of UTILITY_ONLY_BANNED_IN_OFFICIAL) {
    if (k in pd) err(f, `utility key "${k}" must NOT appear in programme_detail_official (repo rule)`);
  }
  for (const k of PLACEHOLDER_FIELDS) {
    if (typeof pd[k] === 'string' && PLACEHOLDER_BANNED.has(pd[k].toLowerCase().trim())) {
      err(f, `programme_detail_official.${k} is placeholder "${pd[k]}" — use null`);
    }
  }
  if (pd.status && !VALID_STATUS.has(pd.status)) {
    warn(f, `programme_detail_official.status "${pd.status}" not in the canonical set`);
  }
  // THE hard repo invariant
  if (pd.fully_funded === true && pd.tuition_coverage !== true) {
    err(f, 'VIOLATES repo rule: fully_funded=true requires tuition_coverage=true');
  }
  // bond + fully_funded sanity.
  // A published service obligation disqualifies fully_funded. But a record that
  // explicitly states that NO bond exists also contains the word "bond" — matching
  // the keyword alone produced false positives on correct records, so scan for an
  // AFFIRMATIVE obligation and ignore negated clauses.
  if (pd.fully_funded === true) {
    const clauses = []
      .concat(pd.award_holder_conditions || [], pd.coverage ? [pd.coverage] : [],
        pd.tuition_coverage_note ? [pd.tuition_coverage_note] : [])
      .flatMap(s => String(s).split(/[.;]\s+/));
    const AFFIRMATIVE = /\b(bond|service obligation|repay\w*|repayment|work bond|return home|must serve|obligat\w+)\b/i;
    const NEGATED = /\b(no|not|without|neither|nor|free of|exempt from|waive[sd]?|zero)\b/i;
    const hits = clauses.filter(c => AFFIRMATIVE.test(c) && !NEGATED.test(c));
    if (hits.length) {
      // Heuristic, not proof: reading "rather than as binding obligations" is a
      // DENIAL that still contains the keyword. Flag for human review instead of
      // failing a record whose underlying facts may be correct.
      warn(f, 'fully_funded=true and this clause mentions an obligation — confirm by reading it: "' +
        hits[0].slice(0, 200) + '"');
    }
  }
  if (!isArr(pd.official_source_urls) || !pd.official_source_urls.length) {
    err(f, 'official_source_urls must be a non-empty array');
  } else {
    pd.official_source_urls.forEach(u => {
      if (!/^https:\/\//.test(u)) err(f, `official_source_urls entry not https: ${u}`);
      else allCitations.add(u);
    });
  }
  if (pd.last_verified_date && pd.last_verified_date !== TODAY) {
    warn(f, `programme_detail_official.last_verified_date "${pd.last_verified_date}" expected ${TODAY}`);
  }

  // ---------- utility block ----------
  const auMiss = missingKeys(au, AU_REQUIRED);
  if (auMiss.length) err(f, `programme_detail_applicant_utility missing: ${auMiss.join(', ')}`);
  for (const k of ['application_readiness_checklist', 'common_rejection_risks', 'estimated_uncovered_costs', 'document_audit', 'submission_workflow']) {
    if (k in au && !isArr(au[k])) err(f, `applicant_utility.${k} must be an array`);
  }
if (kSafe(au.alerts)) {
    au.alerts.forEach((a, i) => {
      // A bare string is a contract violation, but it must be REPORTED, not
      // crashed on: `in` on a string throws, and one malformed record must
      // never take down the run that is supposed to audit it.
      if (!a || typeof a !== 'object' || !('trigger' in a) || !('message' in a)) {
        err(f, `applicant_utility.alerts[${i}] must be {trigger, message} — ${typeof a === 'string' ? 'got a bare string' : 'missing trigger/message'}`);
      }
    });
  }

  // ---------- verification block ----------
  const vMiss = missingKeys(v, V_REQUIRED);
  if (vMiss.length) err(f, `programme_detail_verification missing: ${vMiss.join(', ')}`);
  if (!isArr(v.source_citations) || !v.source_citations.length) {
    err(f, 'REPO RULE: source_citations is mandatory and non-empty — stage would skip this record');
  } else {
    v.source_citations.forEach(u => {
      if (!/^https:\/\//.test(u)) err(f, `source_citations entry not https: ${u}`);
    });
  }
  const conf = v.verification_confidence;
  if (typeof conf !== 'number' || conf < 0 || conf > 1) {
    err(f, `verification_confidence must be a number 0..1, got ${conf}`);
  } else if (conf > 0.9) {
    warn(f, `verification_confidence ${conf} is high — confirm every field came from the awarding body`);
  }
  if (!isArr(v.official_fields_confirmed) || !v.official_fields_confirmed.length) {
    err(f, 'official_fields_confirmed must be a non-empty array');
  }
  if (!isArr(v.unverified_or_removed_claims) || !v.unverified_or_removed_claims.length) {
    warn(f, 'unverified_or_removed_claims is empty — should state what could not be confirmed');
  }

  // ---------- logo ----------
  const lo = o.logo_override;
  if (lo != null) {
    const lMiss = missingKeys(lo, ['url', 'page_url', 'official_host', 'alt_text', 'image_kind', 'image_format', 'verified_at', 'host_evidence']);
    if (lMiss.length) err(f, `logo_override missing: ${lMiss.join(', ')}`);
    if (lo.url && !/^https:\/\//.test(lo.url)) err(f, `logo_override.url not https: ${lo.url}`);
    if (lo.url) {
      let host = '';
      try { host = new URL(lo.url).hostname; } catch { }
      const bad = LOGO_BANNED_HOSTS.find(b => host.includes(b));
      if (bad) err(f, `logo_override.url host "${host}" is a banned aggregator/CDN domain (${bad})`);
      if (/\.svg($|\?)/i.test(lo.url) === false && !/logo|brand|wordmark|favicon|icon/i.test(lo.url)) {
        warn(f, `logo_override.url does not look like a logo asset: ${lo.url}`);
      }
      const key = lo.url.split('#')[0];
      if (seenLogos.has(key)) warn(f, `logo URL reused from ${seenLogos.get(key)} — key overrides by HOST, so these merge into one entry`);
      else seenLogos.set(key, f);
    }
    if (lo.official_host === true) {
      let lh = '', ph = '';
      try { lh = new URL(lo.url).hostname; ph = new URL(lo.page_url).hostname; } catch { }
      const reg = h => h.split('.').slice(-2).join('.');
      if (lh && ph && reg(lh) !== reg(ph)) {
        err(f, `official_host=true but logo host "${lh}" != page host "${ph}" (repo rule 3)`);
      }
    }
    if (lo.image_format === 'svg' && /white/i.test(String(lo.alt_text))) {
      warn(f, `alt_text mentions white — repo rule 6 excludes white-on-transparent wordmarks`);
    }
  }

// ---------- completion gate ----------
  // PART F tells agents to write a skeleton first so an idle timeout cannot destroy
  // their work. Gate on substance, not on the agent's own flag: a record that has
  // real citations AND confirmed fields is usable even if it forgot to clear
  // research_notes.skeleton. The flag is logged, not trusted.
  const hasCitations = isArr(v.source_citations) && v.source_citations.length > 0;
  const hasConfirmed = isArr(v.official_fields_confirmed) && v.official_fields_confirmed.length > 0;
  const hasUrls = isArr(pd.official_source_urls) && pd.official_source_urls.length > 0;

  // Citations, confirmed fields and URLs prove a record was STARTED, not that it
  // was FINISHED. b18-swansea had all three while its eligibility, requirements
  // and benefits were empty arrays and eleven fields literally read "INTERIM",
  // and it was merging into the catalogue as complete. So the gate also requires
  // the fact-bearing fields to hold real values.
  const UNFINISHED = /^(interim|interim write|draft|tbd|wip|unknown|pending|in progress|not started|placeholder|null|n\/a|-)$/i;
  const FACT_BEARING_ARRAYS = new Set(['eligibility', 'requirements', 'benefits']);
  function unfinishedFields(obj, prefix, out) {
    const acc = out || [];
    if (!obj || typeof obj !== 'object') return acc;
    for (const [k, val] of Object.entries(obj)) {
      const p = prefix ? prefix + '.' + k : k;
      if (typeof val === 'string' && UNFINISHED.test(val.trim())) acc.push(p);
      else if (Array.isArray(val)) {
        if (!val.length && FACT_BEARING_ARRAYS.has(k)) acc.push(p + '[]');
        val.forEach(x => { if (x && typeof x === 'object') unfinishedFields(x, p + '[]', acc); });
      } else if (val && typeof val === 'object') unfinishedFields(val, p, acc);
    }
    return acc;
  }
  const unfinished = [...unfinishedFields(ns, 'new_scholarship'), ...unfinishedFields(pd, 'programme_detail_official')];
const isSkeleton = !(hasCitations && hasConfirmed && hasUrls) || unfinished.length > 0;
  if (isSkeleton) {
    incomplete.push({
      file: f,
      slot: slotOfFile(f),
      name: ns.name || null,
      host: (() => { try { return new URL(ns.official_source_url).hostname; } catch { return null; } })(),
      reason: [
        !hasUrls && 'no official_source_urls',
        !hasCitations && 'no citations',
        !hasConfirmed && 'no confirmed fields',
        unfinished.length && `${unfinished.length} unfinished field(s): ${unfinished.slice(0, 4).join(', ')}${unfinished.length > 4 ? ' ...' : ''}`,
      ].filter(Boolean).join(' + '),
    });
    warn(`${f}: INCOMPLETE (${[
      !hasUrls && 'no urls', !hasCitations && 'no citations', !hasConfirmed && 'no confirmed fields',
      unfinished.length && `${unfinished.length} unfinished field(s) e.g. ${unfinished.slice(0, 3).join(', ')}`,
    ].filter(Boolean).join(' + ')}) — held out of the merge`);
  } else if (o.research_notes?.skeleton === true) {
    warn(`${f}: research_notes.skeleton is still true but the record has citations, confirmed fields and URLs — treated as complete`);
  }

  records.push({ file: f, name: ns.name, region: ns.region, status: ns.status, complete: !isSkeleton, unfinished, o, ns, pd, au, v, lo });
}

// ---------------------------------------------------------------- title disambiguation
// do_add() drops a record whose lowercased title already appeared earlier in the
// batch ("duplicate within batch"), so two genuinely distinct awards that share a
// generic published title cannot both land. Apply the repo's own convention of
// qualifying the title with the awarding body. Done AFTER loading so the duplicate
// check below sees the disambiguated names.
const OVERRIDES = { by_award_name: {}, title_overrides: [] };
try {
  Object.assign(OVERRIDES, JSON.parse(fs.readFileSync(path.join(DIR, 'REFRESH_OVERRIDES.json'), 'utf8')));
} catch { }
const retitled = [];
{
  const rules = (OVERRIDES.title_overrides || []).filter(r => r && r.title);
  for (const r of records) {
    if (!r.ns || !r.ns.name) continue;
    let h = '';
    try { h = new URL(r.ns.official_source_url).hostname.toLowerCase(); } catch { }
    for (const rule of rules) {
      const published = rule.published_title;
      if (published !== r.ns.name) continue;
      const want = String(rule._applies_to_host || '').toLowerCase().replace(/^www\./, '');
      if (want && !h.replace(/^www\./, '').includes(want)) continue;
      retitled.push({ from: r.ns.name, to: rule.title, host: h || '(no url)' });
      r.ns.name = rule.title;
      r.o.new_scholarship.name = rule.title;
      r.name = rule.title;
      break;
    }
  }
  // rebuild the name-collision view using final names
  const finalSeen = new Map();
  const titleCollisions = [];
  for (const r of records) {
    const k = String(r.ns.name || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
    if (!k) continue;
    if (finalSeen.has(k)) titleCollisions.push({ name: r.ns.name, files: [finalSeen.get(k), r.file] });
    else finalSeen.set(k, r.file);
  }
for (const c of titleCollisions) {
    err(c.files[1], `award name "${c.name}" is also used by ${c.files[0]} — do_add() would drop the second as "duplicate within batch"; disambiguate in REFRESH_OVERRIDES.title_overrides`);
  }
}

function kSafe(x) { return isArr(x); }

// ---------------------------------------------------------------- refresh routing
// A record whose awarding body is already in EXISTING_AWARDS.json is a REFRESH of
// that row, not a new insert. The programme_details stage fills EMPTY fields only,
// so a refresh must be routed to the existing id or it will never apply.
let EXISTING = null;
try {
  EXISTING = JSON.parse(fs.readFileSync(path.join(DIR, 'EXISTING_AWARDS.json'), 'utf8'));
} catch { }

const normName = (s) => String(s || '').toLowerCase()
  .replace(/&/g, 'and').replace(/[^a-z0-9]+/g, ' ')
  .replace(/\b(scholarship|scholarships|programme|program|award|awards|fund|funded|the|for|of|and|international)\b/g, ' ')
  .replace(/\s+/g, ' ').trim();

/**
 * Routing decision.
 *
 * A host match is NOT enough to declare a refresh: one host legitimately carries
 * several distinct programmes. The repo says this itself, in
 * retired_records.json _rules: "One host legitimately carries several programmes —
 * studyinjapan.go.jp serves the seven MEXT scholarship types plus a USA-only
 * edition — so a single row among them can be wrong while its neighbours are
 * correct." monash.edu and nus.edu.sg are exactly that case.
 *
 * So: a normalised NAME match auto-routes to REFRESH; a host-only match is flagged
 * for a human to confirm award identity, and is NOT auto-routed.
 */
function findExisting(r) {
  if (!EXISTING) return null;
  let host = null;
  try { host = new URL(r.ns.official_source_url).hostname.toLowerCase(); } catch { }
  const hostHits = host ? (EXISTING.byHost[host] || []) : [];

  const nk = normName(r.ns.name);
  const nameHits = nk ? (EXISTING.byName[nk] || []) : [];
  if (nameHits.length) {
    return { match: 'name', confidence: 'auto', host, ...nameHits[0] };
  }
  if (hostHits.length) {
    const live = hostHits.find(a => a.state === 'LIVE') || hostHits[0];
    return { match: 'host_only', confidence: 'review', host, ...live, siblings: hostHits.length };
  }
  return null;
}

// Coordinator adjudication overrides win over mechanical matching. They exist
// because neither host nor normalised name can settle every case: "Karsh
// International Scholars Program" and "Karsh International Scholarship" are the
// same award, while two awards on monash.edu are not.

// slotOfFile is defined once at the top of this file, next to record
// discovery, because all three call sites must agree on it.

const refreshes = [];
const siblingFlags = [];
for (const r of records) {
  const slot = slotOfFile(r.file);
  const name = r.ns.name || '';

  const ov = (OVERRIDES.by_award_name || {})[name];
  if (ov) {
    if (ov.route === 'REFRESH_EXISTING_ID') {
      refreshes.push({
        slot, name, matched_by: 'override', host: null,
        existing_id: ov.existing_id, existing_state: ov.existing_state,
        existing_name: ov.existing_name || null, why: ov.why,
      });
      console.log(`  [override] slot ${slot} "${name}" -> REFRESH id ${ov.existing_id}`);
      continue;
    }
    if (ov.route === 'INSERT_NEW') {
      console.log(`  [override] slot ${slot} "${name}" -> INSERT_NEW (${(ov.why || '').slice(0, 90)}...)`);
      continue;
    }
  }

  const hit = findExisting(r);
  if (!hit) continue;
  if (hit.confidence === 'auto') {
    refreshes.push({
      slot, name, matched_by: hit.match, host: hit.host || null,
      existing_id: hit.id, existing_state: hit.state, existing_name: hit.name || null,
    });
    warn(`${r.file} (${name}): award NAME matches existing ${hit.state} id ${hit.id} — route as REFRESH to that id, not INSERT`);
  } else {
    siblingFlags.push({
      slot, name, host: hit.host, sibling_count: hit.siblings,
      nearest: { id: hit.id, state: hit.state, name: hit.name || null },
    });
    warn(`${r.file} (${name}): ${hit.siblings} record(s) already exist on host ${hit.host} `
      + `(nearest: ${hit.state} id ${hit.id} "${hit.name || 'untitled'}"). Confirm this is a DISTINCT award — `
      + 'host overlap alone does not make it a duplicate. Add a decision to REFRESH_OVERRIDES.json to settle it.');
  }
}

// ---------------------------------------------------------------- stats
const done = records.filter(r => r.complete);
const byRegion = {}, byStatus = {};
let logoOk = 0, logoNull = 0, ffTrue = 0, pastDeadline = 0;
for (const r of done) {
  byRegion[r.region || 'MISSING'] = (byRegion[r.region || 'MISSING'] || 0) + 1;
  byStatus[r.status || 'MISSING'] = (byStatus[r.status || 'MISSING'] || 0) + 1;
  if (r.lo) logoOk++; else logoNull++;
  if (r.pd.fully_funded === true) ffTrue++;
  if (r.ns.deadline_date && r.ns.deadline_date < TODAY) pastDeadline++;
}
const avg = (fn) => done.length ? (done.reduce((s, r) => s + (fn(r) || 0), 0) / done.length) : 0;

console.log('='.repeat(74));
console.log('SCHOLARZONE BACHELOR BATCH — VALIDATION');
console.log('='.repeat(74));
console.log(`expected slots       : 60`);
console.log(`files on disk       : ${files.length}`);
console.log(`UNPARSEABLE files   : ${unreadable.length}`);
console.log(`COMPLETE records    : ${done.length}`);
console.log(`incomplete (skeleton): ${incomplete.length}`);
console.log(`ERRORS (complete)   : ${errors.filter(e => !incomplete.some(i => e.startsWith(i.file))).length}`);
console.log(`warnings            : ${warnings.length}`);
if (unreadable.length) {
  console.log('');
  console.log('*** UNPARSEABLE JSON — these files are NOT counted anywhere above ***');
  for (const u of unreadable) console.log(`  x ${u.file}: ${u.detail}`);
}
console.log('');
console.log('by region   :', JSON.stringify(byRegion));
console.log('by status   :', JSON.stringify(byStatus));
console.log('');
console.log(`verified logos       : ${logoOk}`);
console.log(`null logos           : ${logoNull}`);
console.log(`fully_funded = true  : ${ffTrue}`);
console.log(`past deadline_date   : ${pastDeadline}`);
console.log(`avg confidence       : ${avg(r => r.v.verification_confidence).toFixed(3)}`);
console.log(`unique citations     : ${allCitations.size}`);
console.log(`null-string repairs  : ${repairs.length}`);
console.log('');
if (incomplete.length) {
  console.log('INCOMPLETE — held out of the merge, need a finishing pass:');
  incomplete.forEach(i => console.log(`  ${i.file}  ${i.name || '(unnamed)'}  [${i.host || 'no url'}]  ${i.reason}`));
  console.log('');
}
const missing = [];
for (let i = 1; i <= 60; i++) {
  const nn = String(i).padStart(2, '0');
  if (!files.some(f => f.startsWith(nn + '-'))) missing.push(nn);
}
if (missing.length) console.log('MISSING SLOTS: ' + missing.join(', ') + '\n');

if (warnings.length) {
  console.log('--- WARNINGS ---');
  warnings.forEach(w => console.log('  ! ' + w));
  console.log('');
}
if (errors.length) {
  const held = errors.filter(e => incomplete.some(i => e.startsWith(i.file)));
  const real = errors.filter(e => !incomplete.some(i => e.startsWith(i.file)));
  if (real.length) {
    console.log('--- ERRORS on COMPLETE records ---');
    real.forEach(e => console.log('  x ' + e));
    console.log('');
  }
  if (held.length) {
    console.log(`--- ERRORS on INCOMPLETE records (${held.length}) — held out of the merge, shown for the finishing pass ---`);
    held.forEach(e => console.log('  . ' + e));
    console.log('');
  }
}

if (WRITE) {
  fs.mkdirSync(MERGED, { recursive: true });

// 1. insertion records — EXCLUDE refreshes (existing rows) and incomplete skeletons
  // (titles were already disambiguated at load time above)
  const slotOf = slotOfFile;
  const refreshSlots = new Set(refreshes.map(r => r.slot));
  const inserts = done.filter(r => !refreshSlots.has(slotOf(r.file)));
  const newRecs = inserts.map(r => r.ns).sort((a, b) => String(a.name).localeCompare(String(b.name)));
  fs.writeFileSync(
    path.join(MERGED, 'new_scholarships.new.json'),
    JSON.stringify({ generated_for: TODAY, count: newRecs.length, records: newRecs }, null, 2)
  );
  fs.writeFileSync(path.join(MERGED, 'refreshes.json'), JSON.stringify(refreshes, null, 2));
  fs.writeFileSync(path.join(MERGED, 'incomplete.json'), JSON.stringify(incomplete, null, 2));

  // 2. enrichment blocks — id supplied ONLY where an existing row was matched
  const pend = done.map(r => {
    const slot = slotOf(r.file);
    const hit = refreshes.find(x => x.slot === slot);
    return {
      _slot: slot,
_route: hit ? 'REFRESH_EXISTING_ID' : 'INSERT_THEN_ENRICH',
      _target_id: hit ? hit.existing_id : null,
      _match_by: hit ? hit.matched_by : null,
      // Always populated, not just for refreshes: the applier pairs an insertion
      // record with its enrichment block by name, and leaving this null for
      // inserts silently broke that pairing.
      _match_name: r.ns.name || null,
      _researched_by: r.v.researched_by,
      official: r.pd,
      applicant_utility: r.au,
      verification: r.v,
    };
  }).sort((a, b) => a._slot.localeCompare(b._slot));
  fs.writeFileSync(path.join(MERGED, 'programme_details.pending.json'), JSON.stringify(pend, null, 2));

  // 3. logo overrides keyed by OFFICIAL HOST (repo rule 1)
  const logos = {};
  const dropped = [];
  for (const r of records) {
    if (!r.lo || !r.lo.url) { dropped.push(r.file + ' (null logo)'); continue; }
    let host;
    try { host = new URL(r.lo.url).hostname; } catch { host = null; }
    if (!host) { dropped.push(r.file + ' (unparseable url)'); continue; }
    if (logos[host]) { dropped.push(r.file + ` (host ${host} already taken by ${logos[host]._from})`); continue; }
    logos[host] = { ...r.lo, _from: r.file, _award: r.ns.name };
  }
  fs.writeFileSync(path.join(MERGED, 'official_logo_overrides.new.json'), JSON.stringify(logos, null, 2));

  console.log(`WROTE ${newRecs.length} INSERTION records    -> _merged/new_scholarships.new.json`);
  if (retitled.length) {
    console.log('\nTITLES DISAMBIGUATED (do_add() drops same-title records as "duplicate within batch"):');
    retitled.forEach(t => console.log(`  ~ "${t.from}"  ->  "${t.to}"   [${t.host}]`));
  }
  console.log(`WROTE ${pend.length} enrichment payloads   -> _merged/programme_details.pending.json`);
  console.log(`WROTE ${Object.keys(logos).length} logo overrides         -> _merged/official_logo_overrides.new.json`);
console.log(`WROTE ${refreshes.length} REFRESH routings        -> _merged/refreshes.json`);
  console.log(`WROTE ${incomplete.length} INCOMPLETE (held out)    -> _merged/incomplete.json`);
  fs.writeFileSync(path.join(MERGED, 'sibling_host_flags.json'), JSON.stringify(siblingFlags, null, 2));
  if (refreshes.length) {
    console.log('\nREFRESHES (must NOT be inserted as new rows):');
    refreshes.forEach(r => console.log(`  slot ${r.slot}  name match  -> ${r.existing_state} id ${r.existing_id}  (${r.name})`));
  }
  if (siblingFlags.length) {
    console.log('\nSAME-HOST SIBLINGS (confirm DISTINCT award — host overlap alone is not duplication):');
    siblingFlags.forEach(s => console.log(`  slot ${s.slot}  ${s.sibling_count} record(s) on ${s.host}  nearest: ${s.nearest.state} id ${s.nearest.id} "${s.nearest.name}"  |  ours: ${s.name}`));
  }
  if (dropped.length) console.log(`logo entries not written (${dropped.length}): ${dropped.join('; ')}`);
  if (repairs.length) {
    console.log(`\nREPAIRS APPLIED (${repairs.length}):`);
    repairs.forEach(r => console.log('  ~ ' + r));
    // persist the repaired source files so agents re-reading them see clean data
    for (const r of done) {
      const p = path.join(DIR, r.file);
      fs.writeFileSync(p, JSON.stringify(r.o, null, 2));
    }
    console.log(`\nREPAIRED SOURCE FILES WRITTEN BACK (${done.length}) so agents re-reading them see clean data.`);
  }
  const realErrors = errors.filter(e => !incomplete.some(i => e.startsWith(i.file)));
  if (realErrors.length) console.log(`\nNOTE: merged output written despite ${realErrors.length} error(s) on COMPLETE records — review the error list.`);

// A file that cannot be parsed is invisible to every count above, so the run
// must not exit clean while that is true. Silent absence is the failure mode
// this whole file keeps having to defend against.
if (unreadable.length) {
  console.log(`\nFAILED: ${unreadable.length} research file(s) could not be parsed and were excluded from every count.`);
  process.exitCode = 1;
}
} else {
  console.log('Dry run. Re-run with --write to emit merged files.');
}

process.exit(errors.length ? 1 : 0);