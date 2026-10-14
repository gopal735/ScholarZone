const fs = require('fs');
const { execSync } = require('child_process');

const idsAtHead = (f) => JSON.parse(execSync(`git show HEAD:${f}`, { encoding: 'utf8', maxBuffer: 64e6 })).records.map(r => r.id);
const idsNow = (f) => JSON.parse(fs.readFileSync(f, 'utf8')).records.map(r => r.id);

const F = 'backend/config/verification_confirmations.json';
const C = 'backend/config/record_corrections.json';
const R = 'backend/config/retired_records.json';

const sets = {
  'verification_confirmations': [new Set(idsAtHead(F)), new Set(idsNow(F))],
  'record_corrections': [new Set(idsAtHead(C)), new Set(idsNow(C))],
  'retired_records': [new Set(idsAtHead(R)), new Set(idsNow(R))],
};

console.log('ID CHURN PER FILE');
Object.entries(sets).forEach(([name, [a, b]]) => {
  const added = [...b].filter(x => !a.has(x));
  const removed = [...a].filter(x => !b.has(x));
  console.log(`  ${name}: +${added.length} / -${removed.length}`);
  if (added.length) console.log('      added ids  : ' + added.join(', '));
  if (removed.length) console.log('      removed ids: ' + removed.join(', '));
});
console.log('');

// My three REFRESH targets and the MAECI comparison record.
const MINE = { 122: 'Duke Karsh (my REFRESH target)', 39: 'Toronto Pearson (my REFRESH target)', 447: 'SUTD Trailblazers (my REFRESH target)', 133: 'Invest Your Talent in Italy (MAECI comparison)' };
console.log('CROSS-REFERENCE: do any of MY referenced existing records appear in the changed set?');
Object.entries(sets).forEach(([name, [a, b]]) => {
  const changed = new Set([...b].filter(x => !a.has(x)).concat([...a].filter(x => !b.has(x))));
  Object.entries(MINE).forEach(([id, label]) => {
    if (changed.has(Number(id))) console.log(`  !! id ${id} (${label}) CHANGED in ${name}`);
  });
});
console.log('  (no output above = none of my referenced records were touched)');
console.log('');

// Which countries/regions do the newly ADDED confirmations cover? Do they include my countries?
const nowConf = JSON.parse(fs.readFileSync(F, 'utf8')).records;
const addedIds = [...sets['verification_confirmations'][1]].filter(x => !sets['verification_confirmations'][0].has(x));
const addedRecs = nowConf.filter(r => addedIds.includes(r.id));
console.log('NEWLY CONFIRMED RECORDS: ' + addedRecs.length);
const hosts = new Set();
addedRecs.forEach(r => { try { hosts.add(new URL(r.source_url).hostname.replace(/^www\./, '')); } catch {} });
console.log('  their hosts: ' + [...hosts].sort().join(', '));
console.log('');
const MY_HOSTS = ['bowdoin.edu','oberlin.edu','denison.edu','trentu.ca','uottawa.ca','brocku.ca','dal.ca','lakeheadu.ca','carleton.ca','umanitoba.ca','usask.ca'];
const overlap = [...hosts].filter(h => MY_HOSTS.includes(h));
console.log('  overlap with MY research hosts: ' + (overlap.length ? overlap.join(', ') : 'NONE'));