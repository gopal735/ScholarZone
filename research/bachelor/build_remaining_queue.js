const fs = require('fs');
const a = JSON.parse(fs.readFileSync('research/bachelor/ASSIGNMENTS.json', 'utf8'));
const acc = a.accepted || [];
const doneHosts = new Set();

fs.readdirSync('research/bachelor')
  .filter(f => /^(\d\d|b\d{2,3})-.*[.]json$/.test(f))
  .forEach(f => {
    const o = JSON.parse(fs.readFileSync('research/bachelor/' + f, 'utf8'));
    const url = (o.new_scholarship || {}).official_source_url || '';
    if (url) doneHosts.add(url.replace(/^https?:\/\//, '').split('/')[0].toLowerCase().replace(/^www\./, ''));
  });

const norm = s => String(s || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
const remaining = [];
const doneTargets = [];
acc.forEach(r => {
  const h = String(r.host).replace(/^www\./, '').toLowerCase();
  const row = { name: r.name, host: r.host, region: r.region, note: r.note || '', logo_host_taken: !!r.logo_host_taken, shared_host_warn: r.shared_host_warn || null };
  (doneHosts.has(h) ? doneTargets : remaining).push(row);
});

const byRegion = {};
remaining.forEach(r => (byRegion[r.region] ||= []).push(r));

fs.writeFileSync('research/bachelor/_merged/remaining_targets.json', JSON.stringify({
  _generated: new Date().toISOString(),
  _keyed_by: 'host (slot numbers drifted and are not authoritative)',
  pool_total: acc.length,
  covered: doneTargets.length,
  remaining_count: remaining.length,
  remaining_by_region: Object.fromEntries(Object.entries(byRegion).map(([k, v]) => [k, v.length])),
  covered_targets: doneTargets,
  remaining,
}, null, 2));

console.log('pool total      : ' + acc.length);
console.log('covered by host : ' + doneTargets.length);
console.log('REMAINING       : ' + remaining.length);
console.log('');
Object.keys(byRegion).sort().forEach(g => {
  console.log('== ' + g + ' (' + byRegion[g].length + ')');
  byRegion[g].forEach(r => console.log('  ' + r.host.padEnd(26) + r.name.slice(0, 62)));
});