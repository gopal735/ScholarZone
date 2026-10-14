// Writer for slot 49: assembles parts 1-5 and writes the JSON array.
const fs = require('fs');
const path = require('path');

const { record, VERIFIED_DATE } = require('./_build_49.part1.js');
require('./_build_49.part2.js').extend(record);
require('./_build_49.part3.js').extend(record);
require('./_build_49.part4.js').extend(record);
require('./_build_49.part5.js').extend(record);

const out = path.join(__dirname, '49-singapore-nus-scitech-undergraduate.json');
const json = JSON.stringify([record], null, 2) + '\n';
fs.writeFileSync(out, json, 'utf8');

const parsed = JSON.parse(fs.readFileSync(out, 'utf8'));
console.log('WROTE ' + out);
console.log('bytes            : ' + fs.statSync(out).size);
console.log('array length     : ' + parsed.length);
console.log('top-level keys   : ' + Object.keys(parsed[0]).length);
console.log('verification date: ' + VERIFIED_DATE);
