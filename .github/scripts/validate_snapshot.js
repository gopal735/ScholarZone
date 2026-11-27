#!/usr/bin/env node
/* Validate snapshot structure after PR #107 purge */

const fs = require('fs');
const snapshot = JSON.parse(fs.readFileSync('public/scholarships-snapshot.json', 'utf8'));

if (!snapshot.meta) throw new Error('Missing meta');
if (!snapshot.stats) throw new Error('Missing stats');
if (!snapshot.scholarships) throw new Error('Missing scholarships');
if (!Array.isArray(snapshot.scholarships)) throw new Error('scholarships must be array');

const closedCount = snapshot.scholarships.filter(s => s.status === 'closed').length;
if (closedCount > 0) {
  console.log('WARNING:', closedCount, 'CLOSED scholarships found in snapshot');
  const closed = snapshot.scholarships.filter(s => s.status === 'closed').map(s => s.id);
  console.log('Closed IDs:', closed);
} else {
  console.log('OK: No CLOSED scholarships in public snapshot');
}

console.log('Total records:', snapshot.scholarships.length);
console.log('Generated at:', snapshot.meta.generated_at);