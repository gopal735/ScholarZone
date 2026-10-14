#!/usr/bin/env node
/**
 * build_exclusion_index.js
 *
 * Builds an authoritative duplicate-detection index for the bachelor's batch by
 * joining EVERY source in the repo that identifies an existing scholarship.
 *
 * Emits:
 *   research/bachelor/EXISTING_AWARDS.json     machine-readable index
 *   research/bachelor/EXISTING_AWARDS.md       greppable summary for agents
 *
 * Why this exists: RESEARCH_PROTOCOL.md was hand-written from repo-root JSON only
 * and turned out to be materially incomplete — Duke Karsh is already id 122 and
 * Australia Awards is already id 30 (live AND purged). Agents must be able to check
 * mechanically instead of trusting a prose list.
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..', '..');
const CFG = path.join(ROOT, 'backend', 'config');
const OUT = path.join(__dirname, 'EXISTING_AWARDS.json');
const OUT_MD = path.join(__dirname, 'EXISTING_AWARDS.md');

const read = (p) => JSON.parse(fs.readFileSync(p, 'utf8'));
const safe = (p) => { try { return read(p); } catch { return null; } };

function hostOf(u) {
  if (!u || typeof u !== 'string') return null;
  try { return new URL(u).hostname.toLowerCase(); } catch { return null; }
}
// Multi-part public suffixes common in this catalogue's regions. Without these,
// taking the last two labels collapses every .ac.uk domain to "ac.uk", every
// .edu.au to "edu.au", and so on -- which made swansea.ac.uk match Clarendon,
// LSE and UCL records that live on entirely different domains.
const MULTI_SUFFIX = new Set([
  'ac.uk', 'co.uk', 'gov.uk', 'ac.jp', 'or.jp', 'edu.au', 'gov.au', 'edu.my',
  'gov.my', 'edu.sg', 'gov.sg', 'edu.hk', 'ac.nz', 'co.nz', 'edu.pl', 'ac.at',
]);
function regDomain(h) {
  if (!h) return null;
  const p = h.toLowerCase().split('.');
  if (p.length <= 2) return p.join('.');
  const last2 = p.slice(-2).join('.');
  if (MULTI_SUFFIX.has(last2) && p.length >= 3) return p.slice(-3).join('.');
  return last2;
}
function norm(s) {
  return String(s || '').toLowerCase()
    .replace(/&/g, 'and')
    .replace(/[^a-z0-9]+/g, ' ')
    .replace(/\b(scholarship|scholarships|programme|program|award|awards|fund|funded|the|for|of|and)\b/g, ' ')
    .replace(/\s+/g, ' ').trim();
}

// ---------------------------------------------------------------- sources
const pd = safe(path.join(CFG, 'programme_details.json'));
const ns = safe(path.join(CFG, 'new_scholarships.json'));
const purged = safe(path.join(CFG, 'purged_records_archive.json'));
const retired = safe(path.join(CFG, 'retired_records.json'));
const corrections = safe(path.join(CFG, 'record_corrections.json'));
const logos = safe(path.join(CFG, 'official_logo_overrides.json'));
const conf = safe(path.join(CFG, 'verification_confirmations.json'));
const audit = safe(path.join(__dirname, '..', '..', 'phase2_audit_report.json'));
const facts = safe(path.join(CFG, 'official_programme_facts.json'));

// id -> title, harvested from every file that carries both
const titleById = new Map();
const harvest = (arr, tf) => {
  if (!Array.isArray(arr)) return;
  for (const r of arr) {
    if (!r) continue;
    const id = Number(r.id ?? r.scholarship_id);
    if (!Number.isFinite(id)) continue;
    const t = tf(r);
    if (t && !titleById.has(id)) titleById.set(id, t);
  }
};
harvest(audit && Object.values(audit.categories || {}).flat(), r => r.name);
harvest(audit && audit.records, r => r.name);
harvest(conf && conf.records, r => r.name);
harvest(purged && purged.records, r => r.title || (r.payload && r.payload.title));
harvest(ns && ns.records, r => r.name);
harvest(pd && pd.records, r => r.official && r.official.title);
harvest(facts && Object.values(facts).flat && Object.values(facts).flat(), r => r && r.title);

// ---------------------------------------------------------------- build
const awards = [];
const seen = new Set();

function add(entry) {
  const key = `${entry.id}|${norm(entry.name)}`;
  if (seen.has(key)) return;
  seen.add(key);
  awards.push(entry);
}

// A. programme_details.json — the live enrichment table
//
// `official_source_urls` in the committed config is NOT a list of the award's
// own pages. 312 of 368 records carry more than one entry, and 122 of them
// include third-party URLs that merely appear in the record's prose — anr.fr
// sits on 126 awards, sutd.edu.sg on 127, bs.china-embassy.gov.cn on 121.
// Treating that array as the award's identity made unrelated awards look like
// they shared a host, which is how a duplicate check starts rejecting things
// that were never duplicates.
//
// So the award's own host is taken from the singular fields only. The wide
// array is still indexed, but as citation_urls, which the duplicate filter
// never reads.
for (const r of (pd && pd.records) || []) {
  const ownUrls = [
    r.official?.official_source_url,
    r.official?.application_link,
    r.official?.catalogue_url,
    r.official?.official_updates_url,
  ].filter(u => typeof u === 'string' && u.startsWith('http'));
  const citedUrls = (r.official?.official_source_urls || [])
    .filter(u => typeof u === 'string' && u.startsWith('http'));
  add({
    id: r.id,
    name: titleById.get(Number(r.id)) || null,
    degrees: r.official?.degree_levels || null,
    status: r.official?.status || null,
    source: 'programme_details.json',
    state: 'LIVE',
    hosts: [...new Set(ownUrls.map(hostOf).filter(Boolean))],
    reg_domains: [...new Set(ownUrls.map(u => regDomain(hostOf(u))).filter(Boolean))],
    citation_urls: [...new Set(citedUrls)],
    urls: ownUrls,
  });
}

// B. new_scholarships.json — pending inserts, no id yet
for (const r of (ns && ns.records) || []) {
  const urls = [r.official_source_url, r.catalogue_url, r.official_updates_url]
    .filter(u => typeof u === 'string' && u.startsWith('http'));
  add({
    id: null,
    name: r.name,
    degrees: r.degree_levels,
    status: r.status,
    source: 'new_scholarships.json',
    state: 'PENDING_INSERT',
    hosts: [...new Set(urls.map(hostOf).filter(Boolean))],
    reg_domains: [...new Set(urls.map(u => regDomain(hostOf(u))).filter(Boolean))],
    urls,
  });
}

// C. purged — disproved rows, must not be resurrected
for (const r of (purged && purged.records) || []) {
  const urls = [r.official_source_url, r.payload?.official_source_url]
    .filter(u => typeof u === 'string' && u.startsWith('http'));
  add({
    id: r.id,
    name: r.title || titleById.get(Number(r.id)) || null,
    degrees: r.payload?.degree_levels || null,
    status: r.status,
    source: 'purged_records_archive.json',
    state: 'PURGED',
    reasons: r.reasons || [],
    hosts: [...new Set(urls.map(hostOf).filter(Boolean))],
    reg_domains: [...new Set(urls.map(u => regDomain(hostOf(u))).filter(Boolean))],
    urls,
  });
}

// D. retired / corrections — id-only files
for (const r of (retired && retired.records) || []) {
  add({
    id: r.id, name: titleById.get(Number(r.id)) || null, degrees: null, status: 'RETIRED',
    source: 'retired_records.json', state: 'RETIRED', flag: r.flag, reasons: [r.reason],
    hosts: [], reg_domains: [], urls: [],
  });
}
for (const r of (corrections && corrections.records) || []) {
  add({
    id: r.id, name: titleById.get(Number(r.id)) || null, degrees: null, status: 'CORRECTED',
    source: 'record_corrections.json', state: 'CORRECTED', reasons: [r.reason],
    hosts: hostOf(r.official_source_url) ? [hostOf(r.official_source_url)] : [],
    reg_domains: hostOf(r.official_source_url) ? [regDomain(hostOf(r.official_source_url))] : [],
    urls: r.official_source_url ? [r.official_source_url] : [],
  });
}

// ---------------------------------------------------------------- logo hosts
const logoHosts = logos ? Object.keys(logos).filter(k => !k.startsWith('_')) : [];

// ---------------------------------------------------------------- indexes
const byHost = {}, byDomain = {}, byName = {};
for (const a of awards) {
  for (const h of a.hosts) (byHost[h] ||= []).push(a);
  for (const d of a.reg_domains) (byDomain[d] ||= []).push(a);
  if (a.name) (byName[norm(a.name)] ||= []).push(a);
}

// A host on a large share of the catalogue is not one awarding body. daad.de
// legitimately runs dozens of distinct programmes, and a funder directory like
// anr.fr appears on awards it does not fund at all. Breadth is reported so the
// duplicate filter can refuse to read it as identity.
const SHARED_HOST_MIN = 6;
const sharedHosts = Object.fromEntries(
  Object.entries(byHost)
    .filter(([, v]) => v.length >= SHARED_HOST_MIN)
    .map(([h, v]) => [h, { award_count: v.length, ids: v.map(a => a.id ?? null).slice(0, 12) }])
    .sort((x, y) => y[1].award_count - x[1].award_count)
);

const payload = {
  _generated: new Date().toISOString(),
  _how_to_use: [
    'BEFORE writing a record, grep this index for your target awarding body.',
    'byDomain -> any existing award on the same registrable domain (weakest signal, but a strong prompt to look closer).',
    'byHost -> a specific official host already present (strong duplicate signal).',
    'byName -> a normalised award name match.',
    'If your target is LIVE, PENDING_INSERT or PURGED for your awarding body, you are duplicating. Substitute, or report it as a REFRESH if the cycle genuinely changed.',
    'PURGED rows must never be resurrected regardless of the reason recorded.',
    'Logo overrides are keyed by HOST, so a host already in logo_hosts must NOT get a second entry.',
    'A host listed in shared_hosts carries many unrelated awards. It is a platform, a funder directory or citation leakage, NOT one awarding body, so a shared host alone must never be treated as proof of duplication - fall back to byName.',
  ],
  counts: {
    awards_indexed: awards.length,
    live: awards.filter(a => a.state === 'LIVE').length,
    pending_insert: awards.filter(a => a.state === 'PENDING_INSERT').length,
    purged: awards.filter(a => a.state === 'PURGED').length,
    retired: awards.filter(a => a.state === 'RETIRED').length,
    corrected: awards.filter(a => a.state === 'CORRECTED').length,
    distinct_hosts: Object.keys(byHost).length,
    distinct_reg_domains: Object.keys(byDomain).length,
    logo_hosts: logoHosts.length,
    titled: awards.filter(a => a.name).length,
    untitled: awards.filter(a => !a.name).length,
  },
  logo_hosts: logoHosts.sort(),
  // A host carried by many unrelated awards is a shared platform or a citation
  // that leaked into identity, not a body that runs one award per institution.
  // Recorded so build_assignments can refuse to treat breadth as proof.
  shared_hosts: sharedHosts,
  byHost, byDomain, byName,
  awards: awards.sort((a, b) => (Number(a.id) || 1e9) - (Number(b.id) || 1e9)),
};

fs.writeFileSync(OUT, JSON.stringify(payload, null, 2));

// ---------------------------------------------------------------- markdown
const degBach = awards.filter(a => {
  const d = Array.isArray(a.degrees) ? a.degrees.join(' ') : String(a.degrees || '');
  return /bachelor|undergraduate/i.test(d);
});
const L = [];
L.push('# EXISTING AWARDS INDEX — duplicate check for the bachelor batch');
L.push('');
L.push(`Generated ${payload._generated} from programme_details.json, new_scholarships.json,`);
L.push('purged_records_archive.json, retired_records.json, record_corrections.json,');
L.push('official_logo_overrides.json, verification_confirmations.json, official_programme_facts.json, phase2_audit_report.json.');
L.push('');
L.push('**Run this check BEFORE writing any record.**');
L.push('');
L.push('```bash');
L.push('# is the awarding body already indexed?');
L.push('node -e "const i=require(\'./research/bachelor/EXISTING_AWARDS.json\');');
L.push('const d=process.argv[1];const h=i.byDomain[d]||[];');
L.push('console.log(h.length?h.map(a=>[a.state,a.id,a.name||\'(untitled)\'].join(\' | \')).join(\'\\n\'):\'CLEAR - no existing award on this domain\')" \\');
L.push('  duke.edu');
L.push('```');
L.push('');
L.push('| metric | count |');
L.push('|---|---|');
for (const [k, v] of Object.entries(payload.counts)) L.push(`| ${k} | ${v} |`);
L.push('');
L.push(`## Awards that already include Bachelor's level (${degBach.length})`);
L.push('');
L.push('| id | state | name | source |');
L.push('|---|---|---|---|');
for (const a of degBach.sort((x, y) => (Number(x.id) || 1e9) - (Number(y.id) || 1e9))) {
  L.push(`| ${a.id ?? '-'} | ${a.state} | ${a.name || '_(untitled — check by host)_'} | ${a.source} |`);
}
L.push('');
L.push(`## Logo override hosts already taken (${logoHosts.length})`);
L.push('');
L.push('Do **not** add a second entry for any of these hosts:');
L.push('');
L.push('```');
logoHosts.forEach(h => L.push(h));
L.push('```');
L.push('');
fs.writeFileSync(OUT_MD, L.join('\n'));

// ---------------------------------------------------------------- report
console.log('='.repeat(72));
console.log('EXISTING AWARDS INDEX BUILT');
console.log('='.repeat(72));
for (const [k, v] of Object.entries(payload.counts)) {
  console.log(k.padEnd(22) + ': ' + v);
}
console.log('');
console.log(`awards including Bachelor's : ${degBach.length}`);
console.log('');
console.log('Bachelor-level records already live (id | name):');
for (const a of degBach.filter(a => a.state === 'LIVE' && a.name).slice(0, 40)) {
  console.log('  ' + String(a.id).padEnd(5) + a.name);
}
console.log('');
console.log('WROTE ' + path.relative(process.cwd(), OUT));
console.log('WROTE ' + path.relative(process.cwd(), OUT_MD));