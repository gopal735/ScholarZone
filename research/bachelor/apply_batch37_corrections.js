const fs = require('fs');
const D = 'research/bachelor';

// ---- 1. teach the audit that "INTERIM" is an unfinished-work marker ----
const ap = 'research/bachelor/audit_consistency.js';
let src = fs.readFileSync(ap, 'utf8');
const before = src;
src = src.replace(
  "const PLACEHOLDER = new Set(['', 'n/a', 'na', '-', 'none', 'tbd', 'unknown', 'null', 'n.a.', 'not available', 'not published', 'pending', 'to be confirmed']);",
  "// 'interim' and friends are unfinished-work markers that the original list missed,\n" +
  "// which let b18-swansea and w4-windsor pass as COMPLETE with empty required arrays.\n" +
  "const PLACEHOLDER = new Set(['', 'n/a', 'na', '-', 'none', 'tbd', 'unknown', 'null', 'n.a.', 'not available', 'not published', 'pending', 'to be confirmed', 'interim', 'interim write', 'draft', 'wip', 'in progress', 'not started', 'placeholder']);"
);
if (src === before) throw new Error('PLACEHOLDER line not matched - audit edit failed');
fs.writeFileSync(ap, src);
console.log('1. audit_consistency.js: interim/draft added to the placeholder set');

// ---- 2. downgrade the two genuinely incomplete records ----
const DOWNGRADE = [
  {
    file: 'b18-international-scholarship-ug-students-swansea.json',
    why: 'Not substantively complete. programme_detail_official.eligibility, requirements and benefits are all empty arrays, and citizenship_residency, international_eligibility and research_notes.degree_level_confirmed literally contain "INTERIM" / "INTERIM - record not yet complete". It was counted COMPLETE because it had citations and an official_source_url, but the fact-bearing fields are placeholders.',
  },
  {
    file: 'w4-windsor-international-scholarships.json',
    why: 'Self-declared interim. Its own text records "INTERIM WRITE" and repeatedly states fields are "deliberately null rather than estimated" and "not yet read from an official page for this interim write", including funding_amount, tuition_coverage and duration.',
  },
];
DOWNGRADE.forEach(d => {
  const p = `${D}/${d.file}`;
  const o = JSON.parse(fs.readFileSync(p, 'utf8'));
  const v = o.programme_detail_verification;
  v.unverified_or_removed_claims = (v.unverified_or_removed_claims || []).concat([
    'DOWNGRADED TO UNVERIFIED during the batch-37 reconciliation: ' + d.why,
  ]);
  if (typeof v.verification_confidence === 'number') {
    v.verification_confidence = Math.min(v.verification_confidence, 0.4);
  }
  fs.writeFileSync(p, JSON.stringify(o, null, 2));
  console.log(`2. downgraded ${d.file} -> UNVERIFIED`);
});

// ---- 3. record the PTE-UM logo-host resolution ----
{
  const p = `${D}/57-pte-universiti-malaya-scholarship.json`;
  const o = JSON.parse(fs.readFileSync(p, 'utf8'));
  o.logo_override.host_mismatch_resolution = {
    status: 'RESOLVED - ACCEPTABLE',
    source_host: 'www.pearsonpte.com',
    logo_host: 'www.um.edu.my',
    reasoning: 'This is a dual-party award. Pearson sponsors and publishes the terms and conditions, while Universiti Malaya administers the scholarship and awards the degree. The logo is hosted on the administering institution\'s own domain and is referenced from a um.edu.my news page announcing this specific scholarship partnership, so it is an official-domain asset for one of the two official parties.',
    verified: 'HTTP 200, Content-Type image/png, 11483 bytes, PNG magic bytes 89-50-4E-47 confirmed by a live probe on 2026-10-03.',
    note: 'logo_override.official_host is retained as true on the basis that UM is a co-awarding party. This is a judgement call, not an arithmetic fact, so it is recorded here rather than silently accepted.',
    still_for_human_review: 'funding_amount is recorded as 3000 GBP for a Malaysian award. The figure comes from the Pearson/UM terms, but GBP for a UM programme is unusual and has not been independently confirmed. Flagged, not corrected.',
  };
  fs.writeFileSync(p, JSON.stringify(o, null, 2));
  console.log('3. 57-pte-um: logo host mismatch resolved and recorded; GBP flagged');
}

console.log('');
console.log('corrections applied');