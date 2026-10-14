const fs = require('fs');
const file = process.argv[2] || 'research/bachelor/03-italy-maeci-ire-scholarships.json';
const d = JSON.parse(fs.readFileSync(file, 'utf8'));
const gaps = [];
function audit(obj, prefix) {
  for (const k of Object.keys(obj)) {
    const v = obj[k];
    const p = prefix + '.' + k;
    if (v === null) gaps.push(p + ' = null');
    else if (typeof v === 'string' && v.trim() === '') gaps.push(p + ' = empty string');
    else if (Array.isArray(v) && v.length === 0) gaps.push(p + ' = []');
    else if (typeof v === 'object') audit(v, p);
  }
}
audit(d, '');
console.log('FILE: ' + file);
console.log('TOTAL GAPS (null / empty string / empty array): ' + gaps.length);
gaps.forEach((g) => console.log('  ' + g));
