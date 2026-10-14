const fs = require('fs');
const DIR = 'research/bachelor';

// Objective corrections only. No factual claim about a scholarship is changed
// here: these are contract violations (a non-enum region, an extra top-level
// key, an invalid deadline_precision token) where the correct value is
// unambiguous from the record's own data.
const FIXES = [
  {
    file: 'b10-bourse-du-gouvernement-francais.json',
    what: 'programme_detail_official.region "France" is not an allowed region token; new_scholarship.region already holds the canonical "Europe"',
    apply: o => { o.programme_detail_official.region = o.new_scholarship.region; },
  },
  {
    file: 'b116-curtin-john-curtin-global-excellence-scholarship.json',
    what: 'programme_detail_official.region held a prose location instead of the region token',
    apply: o => { o.programme_detail_official.region = o.new_scholarship.region; },
  },
  {
    file: 'b132-smu-undergraduate-scholarships-international-students.json',
    what: 'programme_detail_official.region held an eligibility sentence instead of the region token',
    apply: o => { o.programme_detail_official.region = o.new_scholarship.region; },
  },
  {
    file: 'b134-sutd-scholarship.json',
    what: 'extra top-level "skeleton" key violates the exactly-six-key contract',
    apply: o => { delete o.skeleton; },
    realFile: 'b134-sutd-trailblazers-international-scholarship.json',
  },
  {
    file: 'b46-university-of-ljubljana.json',
    what: 'deadline_precision "ongoing" is not a precision token; the record publishes no date, so "varies" is the accurate token',
    apply: o => { o.new_scholarship.deadline_precision = 'varies'; },
  },
  {
    file: 'w4-windsor-international-scholarships.json',
    what: 'deadline_precision "ongoing" is not a precision token; the record publishes no date, so "varies" is the accurate token',
    apply: o => { o.new_scholarship.deadline_precision = 'varies'; },
  },
];

let n = 0;
FIXES.forEach(fx => {
  const name = fx.realFile || fx.file;
  const p = `${DIR}/${name}`;
  if (!fs.existsSync(p)) { console.log(`SKIP  ${name} (not found)`); return; }
  const o = JSON.parse(fs.readFileSync(p, 'utf8'));
  const before = JSON.stringify(o);
  fx.apply(o);
  if (JSON.stringify(o) === before) { console.log(`NOOP  ${name}`); return; }
  fs.writeFileSync(p, JSON.stringify(o, null, 2));
  console.log(`FIXED ${name}`);
  console.log(`      ${fx.what}`);
  n++;
});
console.log(`\ncorrections applied: ${n}`);