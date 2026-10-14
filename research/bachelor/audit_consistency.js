const fs = require('fs');
const path = require('path');

const DIR = 'research/bachelor';
const files = fs.readdirSync(DIR).filter(f => /^(\d\d|b\d{2,3}|w\d)-.*[.]json$/.test(f)).sort();

const SCHEMA = ['new_scholarship', 'programme_detail_official', 'programme_detail_applicant_utility', 'programme_detail_verification', 'logo_override', 'research_notes'];
const REGIONS = ['Europe', 'United States', 'Canada', 'Australia', 'Singapore', 'Malaysia'];
const STATUSES = ['open', 'upcoming', 'closed'];
// 'interim' and friends are unfinished-work markers that the original list missed,
// which let b18-swansea and w4-windsor pass as COMPLETE with empty required arrays.
const PLACEHOLDER = new Set(['', 'n/a', 'na', '-', 'none', 'tbd', 'unknown', 'null', 'n.a.', 'not available', 'not published', 'pending', 'to be confirmed', 'interim', 'interim write', 'draft', 'wip', 'in progress', 'not started', 'placeholder']);

const regDomain = h => {
  const p = String(h || '').toLowerCase().split('.').filter(Boolean);
  if (p.length < 2) return String(h || '').toLowerCase();
  const two = ['co.uk', 'ac.uk', 'gov.uk', 'org.uk', 'edu.au', 'gov.au', 'edu.my', 'gov.my', 'edu.sg', 'gov.sg', 'ac.nz', 'co.nz', 'edu.pl'];
  const last2 = p.slice(-2).join('.');
  return two.includes(last2) ? p.slice(-3).join('.') : last2;
};
const hostOf = u => { try { return new URL(u).hostname.toLowerCase(); } catch { return null; } };

const TODAY = '2026-10-03';
const issues = [];
const add = (f, sev, code, msg) => issues.push({ file: f, sev, code, msg });

// Cross-region expected country, used only to flag a mismatch for review.
const REGION_COUNTRIES = { Europe: null, 'United States': ['United States', 'USA', 'US'], Canada: ['Canada'], Australia: ['Australia'], Singapore: ['Singapore'], Malaysia: ['Malaysia'] };

let complete = 0;
const rejectedRecords = [];

files.forEach(f => {
  let o;
  try { o = JSON.parse(fs.readFileSync(path.join(DIR, f), 'utf8')); }
  catch (e) { add(f, 'FAIL', 'UNPARSEABLE', e.message); return; }

  // A REJECTED placeholder is not a research record. It has no new_scholarship
  // block by design, and it must be audited against the rejection contract
  // instead: a verdict, at least one quoted piece of official evidence, and an
  // official URL. Reporting it as a schema failure would be a false positive.
  if (typeof o.verdict === 'string' && /REJECTED|NO APPLICABLE AWARD/i.test(o.verdict)) {
    const ev = o.official_evidence || [];
    if (!/REJECTED/i.test(o.verdict)) add(f, 'ERROR', 'REJECTION_VERDICT', o.verdict);
    if (!ev.length) add(f, 'ERROR', 'REJECTION_NO_EVIDENCE', 'no official_evidence entries');
    ev.forEach((e, i) => {
      if (!/^https:\/\//.test(String(e.url || ''))) add(f, 'ERROR', 'REJECTION_EVIDENCE_URL', `evidence[${i}].url not https`);
      if (!e.quote || String(e.quote).length < 25) add(f, 'ERROR', 'REJECTION_EVIDENCE_QUOTE', `evidence[${i}].quote missing or too short to be evidence`);
    });
    if (!o.why_not_converted_to_a_record) add(f, 'REVIEW', 'REJECTION_NO_RATIONALE', 'no why_not_converted_to_a_record explanation');
    rejectedRecords.push({ file: f, verdict: o.verdict, evidence_urls: ev.map(e => e.url) });
    return;
  }
  if (!('new_scholarship' in o)) { add(f, 'FAIL', 'NEITHER_RECORD_NOR_REJECTION', 'has neither new_scholarship nor a rejection verdict'); return; }

  const ns = o.new_scholarship || {};
  const off = o.programme_detail_official || {};
  const au = o.programme_detail_applicant_utility || {};
  const v = o.programme_detail_verification || {};
  const logo = o.logo_override || {};
  const rn = o.research_notes || {};

  // --- schema shape ---
  const keys = Object.keys(o);
  const missing = SCHEMA.filter(k => !keys.includes(k));
  const extra = keys.filter(k => !SCHEMA.includes(k));
  if (missing.length) add(f, 'FAIL', 'SCHEMA_MISSING', missing.join(','));
  if (extra.length) add(f, 'ERROR', 'SCHEMA_EXTRA', extra.join(','));

  // --- placeholder strings anywhere in fact-bearing fields ---
  const walkPlaceholders = (obj, pfx) => {
    Object.entries(obj || {}).forEach(([k, val]) => {
      const p = pfx ? pfx + '.' + k : k;
      if (typeof val === 'string' && PLACEHOLDER.has(val.trim().toLowerCase())) add(f, 'ERROR', 'PLACEHOLDER', `${p} = ${JSON.stringify(val)}`);
      else if (Array.isArray(val) && val.some(x => typeof x === 'string' && PLACEHOLDER.has(x.trim().toLowerCase()))) add(f, 'ERROR', 'PLACEHOLDER', `${p}[] contains a placeholder string`);
      else if (val && typeof val === 'object') walkPlaceholders(val, p);
    });
  };
  walkPlaceholders(ns, 'new_scholarship');
  walkPlaceholders(off, 'programme_detail_official');

  // --- enums ---
  if (!REGIONS.includes(ns.region)) add(f, 'ERROR', 'REGION_ENUM', `"${ns.region}" not in allowed set`);
  if (!STATUSES.includes(String(ns.status).toLowerCase())) add(f, 'ERROR', 'STATUS_ENUM', `"${ns.status}"`);
  if (off.region && !REGIONS.includes(off.region)) add(f, 'ERROR', 'REGION_ENUM_OFFICIAL', `programme_detail_official.region = "${off.region}"`);
  if (ns.region && off.region && ns.region !== off.region) add(f, 'ERROR', 'REGION_MISMATCH', `new_scholarship.region=${ns.region} but official.region=${off.region}`);

  // --- country vs region ---
  if (ns.country && REGION_COUNTRIES[ns.region]) {
    const expect = REGION_COUNTRIES[ns.region];
    if (expect.length && !expect.map(x => x.toLowerCase()).includes(String(ns.country).toLowerCase())) {
      add(f, 'REVIEW', 'COUNTRY_REGION', `country "${ns.country}" vs region "${ns.region}"`);
    }
  }

  // --- deadline coherence: status vs deadline_date ---
  const dd = ns.deadline_date;
  if (dd) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(String(dd))) add(f, 'ERROR', 'DEADLINE_FORMAT', `deadline_date = ${JSON.stringify(dd)}`);
    else {
      const isPast = String(dd) < TODAY;
      const st = String(ns.status).toLowerCase();
      if (isPast && (st === 'open' || st === 'upcoming')) add(f, 'REVIEW', 'STATUS_VS_DEADLINE', `status=${st} but deadline_date ${dd} is in the past`);
      if (!isPast && st === 'closed') add(f, 'ERROR', 'STATUS_VS_DEADLINE', `status=closed but deadline_date ${dd} is in the future`);
    }
  }
  if (ns.deadline_date == null && ns.deadline_precision && !['varies', 'unknown', 'n/a'].includes(String(ns.deadline_precision))) {
    add(f, 'REVIEW', 'PRECISION_WITHOUT_DATE', `deadline_date null but precision="${ns.deadline_precision}"`);
  }

  // --- funding coherence ---
  const fa = ns.funding_amount, fc = ns.funding_currency;
  const ofa = off.funding_amount, ofc = off.funding_currency;
  if (fa != null && !fc) add(f, 'ERROR', 'AMOUNT_NO_CURRENCY', `funding_amount=${fa} but funding_currency is null`);
  if (ofa != null && !ofc) add(f, 'ERROR', 'AMOUNT_NO_CURRENCY_OFFICIAL', `official.funding_amount=${ofa} but official.funding_currency is null`);
  if (fa != null && ofa != null && fa !== ofa) add(f, 'REVIEW', 'AMOUNT_MISMATCH', `new_scholarship.funding_amount=${fa} vs official.funding_amount=${ofa}`);
  if (fc && ofc && fc !== ofc) add(f, 'ERROR', 'CURRENCY_MISMATCH', `${fc} vs official ${ofc}`);
  if (String(fc || '').toUpperCase() === 'GBP') add(f, 'REVIEW', 'CURRENCY_GBP', 'GBP amount — confirm currency is real, not a source typo');
  if (fa != null && typeof fa === 'number' && fa <= 0) add(f, 'ERROR', 'AMOUNT_NONPOSITIVE', String(fa));

  // --- citations ---
  const cites = v.source_citations || [];
  if (!Array.isArray(cites) || cites.length < 2) add(f, 'ERROR', 'CITATIONS', `only ${Array.isArray(cites) ? cites.length : 0} citations`);
  cites.forEach(c => { if (!/^https:\/\//.test(String(c))) add(f, 'ERROR', 'CITATION_SCHEME', `not https: ${c}`); });
  if (!Array.isArray(v.official_fields_confirmed) || !v.official_fields_confirmed.length) add(f, 'ERROR', 'NO_CONFIRMED_FIELDS', 'official_fields_confirmed empty');

  // --- the record's own official_source_url must appear in its citations ---
  const osu = ns.official_source_url;
  if (osu) {
    if (!/^https:\/\//.test(osu)) add(f, 'ERROR', 'SOURCE_SCHEME', `official_source_url not https: ${osu}`);
    const norm = s => String(s).replace(/[#?].*$/, '').replace(/\/+$/, '').toLowerCase();
    const hit = cites.some(c => norm(c) === norm(osu) || norm(osu).startsWith(norm(c)) || norm(c).startsWith(norm(osu)));
    if (!hit) add(f, 'REVIEW', 'SOURCE_NOT_CITED', 'official_source_url does not appear in source_citations');
  } else add(f, 'ERROR', 'NO_SOURCE_URL', 'official_source_url missing');

  // --- logo must be official-domain ---
  const lu = logo.url;
  const srcHost = hostOf(osu);
  if (lu) {
    if (!/^https:\/\//.test(lu)) add(f, 'ERROR', 'LOGO_SCHEME', lu);
    else {
      const lh = hostOf(lu);
      if (srcHost && regDomain(lh) !== regDomain(srcHost)) {
        const thirdParty = /(cloudfront|sitecorecloud|cdn|akamai|fastly|cloudflare|wikipedia|wikimedia|shutterstock|gettyimages|imgur|pinimg|blogspot|storage.googleapis|azureedge|wpengine|revcdn)/i;
        add(f, thirdParty.test(lh) ? 'FAIL' : 'REVIEW', 'LOGO_HOST', `logo host ${lh} (${regDomain(lh)}) is not the awarding domain ${regDomain(srcHost)}`);
      }
      if (/white|transparent|light/i.test(lu)) add(f, 'REVIEW', 'LOGO_NAME', `asset name hints light/white: ${lu.split('/').pop()}`);
    }
  }

  // --- degree level must actually be bachelor ---
  const lvl = JSON.stringify(ns.degree_levels || off.degree_levels || '');
  if (!/bachelor|undergraduate|first.?degree/i.test(lvl)) add(f, 'REVIEW', 'LEVEL_NOT_BACHELOR', `degree_levels=${lvl}`);

  // --- confidence coherence ---
  const conf = v.verification_confidence;
  if (typeof conf !== 'number' || conf < 0 || conf > 1) add(f, 'ERROR', 'CONFIDENCE_RANGE', String(conf));
  else if (conf >= 0.75 && cites.length < 2) add(f, 'REVIEW', 'CONFIDENCE_VS_EVIDENCE', `confidence ${conf} with ${cites.length} citations`);

  // --- skeleton flag must not be stale on a finished record ---
  if (rn.skeleton === true && cites.length >= 2 && (v.official_fields_confirmed || []).length) {
    add(f, 'REVIEW', 'STALE_SKELETON_FLAG', 'skeleton=true but record has citations and confirmed fields');
  }

  // --- utility block shape ---
  ['application_readiness_checklist', 'common_rejection_risks', 'estimated_uncovered_costs', 'document_audit', 'alerts', 'submission_workflow'].forEach(k => {
    if (!Array.isArray(au[k])) add(f, 'ERROR', 'UTILITY_SHAPE', `alerts/${k} not an array`);
  });
  (au.alerts || []).forEach((a, i) => {
    if (!a || typeof a !== 'object' || !('trigger' in a) || !('message' in a)) add(f, 'ERROR', 'ALERT_SHAPE', `alerts[${i}] is not {trigger,message}`);
  });

  // --- verification honesty: conflicts must be recorded, not averaged away ---
  const unv = (v.unverified_or_removed_claims || []).join(' | ');
  if (/CONFLICT/i.test(unv)) add(f, 'REVIEW', 'DECLARED_CONFLICT', 'record declares a conflict between official pages');

  complete++;
});

const bySev = s => issues.filter(i => i.sev === s);
console.log('='.repeat(78));
console.log('INTERNAL CONSISTENCY AUDIT (no refetch)');
console.log('='.repeat(78));
console.log('records audited : ' + complete);
console.log('rejections     : ' + rejectedRecords.length);
console.log('issues          : ' + issues.length);
console.log('');
['FAIL', 'ERROR', 'REVIEW'].forEach(s => {
  const list = bySev(s);
  console.log(`--- ${s} (${list.length}) ---`);
  const byCode = {};
  list.forEach(i => (byCode[i.code] ||= []).push(i));
  Object.entries(byCode).sort((a, b) => b[1].length - a[1].length).forEach(([c, arr]) => {
    console.log(`  ${c} x${arr.length}`);
    arr.slice(0, 8).forEach(i => console.log(`      ${i.file.slice(0, 46).padEnd(48)} ${i.msg.slice(0, 92)}`));
    if (arr.length > 8) console.log(`      ... +${arr.length - 8} more`);
  });
  console.log('');
});

fs.writeFileSync('research/bachelor/_merged/consistency_audit.json', JSON.stringify({
  audited: complete, rejections: rejectedRecords, issue_count: issues.length, issues,
}, null, 2));