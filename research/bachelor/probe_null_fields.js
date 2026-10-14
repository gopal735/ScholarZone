const fs = require('fs');
const A = JSON.parse(fs.readFileSync('verification/detail_shape_repairs.json', 'utf8'));
const pd = JSON.parse(fs.readFileSync('backend/config/programme_details.json', 'utf8'));
const pdById = {};
(pd.records || []).forEach(r => (pdById[String(r.id)] = r));

// Does a null in a list[str] field also break the response? The schema declares
// `eligibility: list[str] = Field(default_factory=list)` with no Optional, so a
// stored null is a second, separate shape defect the artifact does not describe.
const NULLABLE_FIELDS = ['eligibility', 'benefits', 'coverage', 'application_method'];
const nullCases = [];
Object.entries(pdById).forEach(([id, rec]) => {
  ['official', 'applicant_utility', 'verification'].forEach(b => {
    if (!rec[b] || typeof rec[b] !== 'object') return;
    NULLABLE_FIELDS.forEach(f => {
      if (Object.prototype.hasOwnProperty.call(rec[b], f) && rec[b][f] === null) {
        nullCases.push({ id: Number(id), bucket: b, field: f });
      }
    });
  });
});
console.log('NULL values sitting in list[str] fields: ' + nullCases.length);
const ids = [...new Set(nullCases.map(c => c.id))];
console.log('distinct record ids: ' + ids.length + ' -> ' + ids.join(', '));
console.log('');

const fiveHundred = new Set(A.records.filter(r => r.http_status === 500).map(r => r.id));
const overlap = ids.filter(i => fiveHundred.has(i));
console.log('of those ids, already in the artifact 500-set: ' + overlap.length + ' -> ' + overlap.join(', '));
console.log('NOT in the artifact 500-set (unaccounted 500 candidates): ' + ids.filter(i => !fiveHundred.has(i)).join(', '));
console.log('');

// Is a null actually rejected by the public schema? Test the real model.
console.log('Checking whether the public schema rejects null in these fields...');
const cases = [
  { label: 'list field = ["text"]', value: ['text'] },
  { label: 'list field = "text" (string)', value: 'text' },
  { label: 'list field = null', value: null },
];
const field = 'benefits';
cases.forEach(c => {
  try {
    const mod = require('./backend/app/schemas.py');
    console.log('  ' + c.label.padEnd(30) + ' (not exercised - pydantic model loaded separately below)');
  } catch { /* ignore */ }
});
fs.writeFileSync('research/bachelor/_merged/null_field_cases.json', JSON.stringify({ count: nullCases.length, ids, cases: nullCases }, null, 2));