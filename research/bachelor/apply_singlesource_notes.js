const fs = require('fs');

// These three records rest on a single official award page. That is legitimate
// primary evidence for the award itself, but it does not meet the two-citation
// house standard, and padding source_citations with a navigation-only page
// would be dishonest. So the limitation is recorded explicitly instead.
const SINGLE_SOURCE = [
  {
    file: '42-australia-monash-kc-kuok.json',
    note: 'SINGLE-SOURCE EVIDENCE: the award facts come from one official Monash award page. A second citation was not added because the only additional official page available is the scholarship-finder index, which carries no award-specific fact. verification_confidence lowered accordingly. Flagged for human review.',
    newConfidence: 0.8,
  },
  {
    file: 'b133-charles-sturt-university-international-student-merit-scholarship.json',
    note: 'SINGLE-SOURCE EVIDENCE: the award facts come from one official CSU award page. The other URLs in official_pages_read were read while investigating and rejecting Universiti Malaya, so they are not evidence for this award and were deliberately not added as citations. verification_confidence lowered accordingly. Flagged for human review.',
    newConfidence: 0.8,
  },
  {
    file: 'b134-sutd-trailblazers-international-scholarship.json',
    note: 'SINGLE-SOURCE EVIDENCE: the award facts come from one official SUTD award page. The other URLs in official_pages_read were read while investigating and rejecting Universiti Sains Malaysia, so they are not evidence for this award and were deliberately not added as citations. verification_confidence lowered accordingly. This record routes as a REFRESH of existing id 447, so it would not create a new row regardless. Flagged for human review.',
    newConfidence: 0.72,
  },
];

SINGLE_SOURCE.forEach(s => {
  const p = 'research/bachelor/' + s.file;
  const o = JSON.parse(fs.readFileSync(p, 'utf8'));
  const v = o.programme_detail_verification;
  v.unverified_or_removed_claims = (v.unverified_or_removed_claims || []).concat([s.note]);
  if (typeof v.verification_confidence === 'number' && v.verification_confidence > s.newConfidence) {
    v.verification_confidence = s.newConfidence;
  }
  const rn = o.research_notes;
  rn.unverified = (rn.unverified || []).concat(['Evidence rests on a single official award page; a second independent official citation is still outstanding']);
  fs.writeFileSync(p, JSON.stringify(o, null, 2));
  console.log(`ANNOTATED ${s.file} -> confidence ${v.verification_confidence}`);
});