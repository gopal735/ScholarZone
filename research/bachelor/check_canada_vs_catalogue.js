const fs = require('fs');
const idx = JSON.parse(fs.readFileSync('research/bachelor/EXISTING_AWARDS.json', 'utf8'));
const awards = idx.awards || [];
const byReg = {};
awards.forEach(a => (a.reg_domains || []).forEach(d => (byReg[d] ||= []).push(a)));
const byName = idx.byName || {};

const CANADIAN = [
  ['brocku.ca', 'International Brock Scholars Award'],
  ['carleton.ca', 'President’s Welcome Award for International Students'],
  ['dal.ca', 'General Entrance Award program (GEA)'],
  ['lakeheadu.ca', 'International Undergraduate Entrance Scholarships'],
  ['queensu.ca', "Dean's International Award Program"],
  ['trentu.ca', 'Trent University International Entrance Scholarships'],
  ['ualberta.ca', "President's International Distinction Scholarship"],
  ['umanitoba.ca', 'International Excellence Entrance Scholarship'],
  ['uoguelph.ca', "President's International Entrance Scholarship"],
  ['uottawa.ca', 'International English Admission Scholarship'],
  ['usask.ca', 'University of Saskatchewan International Excellence Award'],
  ['utoronto.ca', 'Lester B. Pearson International Student Scholarships'],
  ['uwindsor.ca', 'International Student Entrance Awards/Scholarships (University of Windsor)'],
  ['uwo.ca', 'Welcome to Canada Admission Scholarship'],
];

console.log('CANADIAN RECORDS vs FULL EXISTING CATALOGUE');
console.log('='.repeat(70));
let collisions = 0;
CANADIAN.forEach(([reg, name]) => {
  const dom = (byReg[reg] || []);
  const nm = (byName[String(name).toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()] || []);
  const nmPartial = awards.filter(a => {
    const an = String(a.name || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
    const bn = name.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
    return an && bn && (an.includes(bn) || bn.includes(an));
  });
  const hit = dom.length || nm.length || nmPartial.length;
  if (hit) collisions++;
  console.log(`${hit ? 'COLLISION' : 'clear   '}  ${reg.padEnd(14)} ${name.slice(0, 46)}`);
  dom.forEach(a => console.log(`     domain ${a.state}/id${a.id}: ${a.name} [${JSON.stringify(a.degrees || null)}]`));
  nm.forEach(a => console.log(`     name   ${a.state}/id${a.id}: ${a.name}`));
  nmPartial.forEach(a => console.log(`     fuzzy  ${a.state}/id${a.id}: ${a.name}`));
});
console.log('='.repeat(70));
console.log('Canadian records with an existing-catalogue collision: ' + collisions);
console.log('');

// ---- item 7: is the b18-swansea skeleton flag truly stale? ----
const swan = JSON.parse(fs.readFileSync('research/bachelor/b18-international-scholarship-ug-students-swansea.json', 'utf8'));
const v = swan.programme_detail_verification || {};
const off = swan.programme_detail_official || {};
const au = swan.programme_detail_applicant_utility || {};
console.log('ITEM 7 - b18-swansea stale skeleton flag check');
const checks = {
  has_official_source_url: !!(swan.new_scholarship || {}).official_source_url,
  citations: (v.source_citations || []).length,
  confirmed_fields: (v.official_fields_confirmed || []).length,
  degree_level_evidence: !!((swan.research_notes || {}).degree_level_confirmed || ''),
  funding_evidence: !!(swan.new_scholarship || {}).funding_amount || (off.benefits || []).length > 0,
  eligibility: (off.eligibility || []).length,
  alerts_complete: Array.isArray(au.alerts) && au.alerts.every(a => a && typeof a === 'object' && 'trigger' in a && 'message' in a),
  skeleton_flag: (swan.research_notes || {}).skeleton,
};
Object.entries(checks).forEach(([k, val]) => console.log('  ' + k.padEnd(28) + JSON.stringify(val)));
const substantive = checks.has_official_source_url && checks.citations >= 2 && checks.confirmed_fields > 0
  && checks.degree_level_evidence && checks.funding_evidence && checks.eligibility > 0 && checks.alerts_complete;
console.log('  => record is substantively complete: ' + substantive);
console.log('  => clearing the flag is justified  : ' + (substantive && checks.skeleton_flag === true));