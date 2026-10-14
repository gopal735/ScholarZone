const fs = require('fs');

// Running manifest. Every target attempted must land in exactly one bucket, so
// COMPLETE + BLOCKED + DUPLICATE + FAILED + UNVERIFIED accounts for the batch.
const routing = JSON.parse(fs.readFileSync('research/bachelor/_merged/closed_status_routing.json', 'utf8'));
const ins = JSON.parse(fs.readFileSync('research/bachelor/_merged/new_scholarships.new.json', 'utf8')).records;
const ref = JSON.parse(fs.readFileSync('research/bachelor/_merged/refreshes.json', 'utf8'));
const inc = JSON.parse(fs.readFileSync('research/bachelor/_merged/incomplete.json', 'utf8'));
const incomplete = inc.records || inc;

const DEFERRED = {};
routing.decisions.forEach(d => { DEFERRED[d.file] = d.route; });

const completeFiles = fs.readdirSync('research/bachelor')
  .filter(f => /^(\d\d|b\d{2,3}|w\d)-.*[.]json$/.test(f));

const manifest = { _generated: new Date().toISOString(), buckets: {} };

manifest.buckets.INSERT = ins.filter(r => r.status !== 'closed').map(r => ({
  name: r.name, region: r.region, status: r.status, url: r.official_source_url,
}));
manifest.buckets.REFRESH = ref.map(r => ({
  slot: r.slot, existing_id: r.existing_id, existing_name: r.existing_name, ours: r.name,
}));
manifest.buckets.HISTORICAL = Object.entries(DEFERRED)
  .filter(([, route]) => route === 'HISTORICAL')
  .map(([file]) => ({ file, reason: 'complete recurring record, current cycle closed, awaiting next cycle' }));
manifest.buckets.BLOCKED = Object.entries(DEFERRED)
  .filter(([, route]) => route === 'BLOCKED')
  .map(([file, route]) => ({ file, route }));
manifest.buckets.DUPLICATE = [];
manifest.buckets.FAILED = [];
manifest.buckets.UNVERIFIED = incomplete.map(r => ({ file: r.file, reason: r.reason || r.detail || 'skeleton with no citations' }));

const counts = {};
Object.entries(manifest.buckets).forEach(([k, v]) => { counts[k] = v.length; });
manifest.counts = counts;
manifest.accounting = {
  complete_records_on_disk: completeFiles.length,
  routed_total: counts.INSERT + counts.REFRESH + counts.HISTORICAL + counts.BLOCKED,
  unverified_placeholders: counts.UNVERIFIED,
  note: 'HISTORICAL and BLOCKED are complete research records that cannot take the INSERT route. They are counted separately from UNVERIFIED, which is placeholder work with no evidence.',
};

fs.writeFileSync('research/bachelor/MANIFEST.json', JSON.stringify(manifest, null, 2));

console.log('MANIFEST COUNTS');
console.log('----------------');
Object.entries(counts).forEach(([k, v]) => console.log('  ' + k.padEnd(12) + v));
console.log('');
console.log('complete files on disk : ' + completeFiles.length);
console.log('routed (I+R+H+B)      : ' + manifest.accounting.routed_total);
console.log('unverified placeholders: ' + counts.UNVERIFIED);
console.log('');
console.log('HISTORICAL:');
manifest.buckets.HISTORICAL.forEach(x => console.log('  ' + x.file));
console.log('BLOCKED:');
manifest.buckets.BLOCKED.forEach(x => console.log('  ' + x.file + '  (' + x.route + ')'));