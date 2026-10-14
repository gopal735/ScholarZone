#!/usr/bin/env node
/**
 * build_assignments.js
 *
 * Mechanically derives a duplicate-free assignment list for the bachelor batch.
 *
 * Why: the hand-written RESEARCH_PROTOCOL.md target list turned out to overlap the
 * live database badly (Toronto Pearson=id 39, American University EGLS=id 55,
 * Clark Presidential=id 61, Rochester Handler=id 120, Duke Karsh=id 122,
 * Australia Awards=id 30). This script takes a curated candidate pool and drops
 * every candidate whose official host, registrable domain, or normalised name
 * already appears in EXISTING_AWARDS.json â€” plus anything on the region /
 * degree / logo-host ban lists.
 *
 * Output: research/bachelor/ASSIGNMENTS.md + research/bachelor/ASSIGNMENTS.json
 */

const fs = require('fs');
const path = require('path');

const DIR = __dirname;
const idx = JSON.parse(fs.readFileSync(path.join(DIR, 'EXISTING_AWARDS.json'), 'utf8'));

const norm = (s) => String(s || '').toLowerCase()
  .replace(/&/g, 'and').replace(/[^a-z0-9]+/g, ' ')
  .replace(/\b(scholarship|scholarships|programme|program|award|awards|fund|funded|the|for|of|and|international)\b/g, ' ')
  // Collapse simple plurals. A researcher found "International Excellence
  // Scholarships" (candidate) duplicating "International Excellence Scholarship"
  // (already LIVE id 194) — the filter missed it on the trailing "s".
  .replace(/\b([a-z]{4,})s\b/g, '$1')
  .replace(/\s+/g, ' ').trim();

// ---------------------------------------------------------------- candidate pool
// [official name, host, region, degree confirmation note]
// Hosts must be the awarding body's OWN domain (the logo comes from it).
const POOL = [
  // ---------------- EUROPE: Italy ----------------
  ['Scholarships for Foreign Students and Italian Citizens Living Abroad (MAECI)', 'esteri.it', 'Europe', '1st cycle / bachelor included'],
  ['Borse di Studio di Merito per Studenti Stranieri - University of Bologna', 'unibo.it', 'Europe', 'undergraduate eligible'],
  ['International Students Scholarships - University of Padova', 'unipd.it', 'Europe', 'bachelor included'],
  ['International Undergraduate Scholarships - Universita degli Studi di Milano', 'unimi.it', 'Europe', 'undergraduate eligible'],
  ['International Student Scholarships - Universita degli Studi di Torino', 'unito.it', 'Europe', 'undergraduate eligible'],
  ['International Students Scholarships - Universita degli Studi di Parma', 'unipr.it', 'Europe', 'undergraduate eligible'],
  ['Borse di Studio - Universita di Pisa', 'unipi.it', 'Europe', 'undergraduate eligible'],
  ['Talent Awards - Universita degli Studi di Napoli Federico II', 'unina.it', 'Europe', 'undergraduate eligible'],
  ['International Scholarships - Universita di Catania', 'unict.it', 'Europe', 'undergraduate eligible'],
  // ---------------- EUROPE: France ----------------
  ['Bourse du Gouvernement Francais', 'diplomatie.gouv.fr', 'Europe', 'Licence track exists - verify'],
  ['Bourses du Gouvernement Francais - Campus France', 'campusfrance.org', 'Europe', 'Licence track exists - verify'],
  // ---------------- EUROPE: Belgium / Netherlands / Luxembourg ----------------
  ['KU Leuven International Scholarship', 'kuleuven.be', 'Europe', 'bachelor eligible'],
  ['University Scholarship - Ghent University', 'ugent.be', 'Europe', 'bachelor eligible'],
  ['International Students Scholarships - Vrije Universiteit Brussel', 'vub.be', 'Europe', 'bachelor eligible'],
  ['Bourse d Excellence - Universite Libre de Bruxelles', 'ulb.be', 'Europe', 'bachelor eligible'],
  ['Global Studies Scholarship - Maastricht University', 'maastrichtuniversity.nl', 'Europe', 'bachelor programme'],
  ['Excellence Scholarship - Nyenrode Business University', 'nyenrode.nl', 'Europe', 'bachelor eligible'],
  ['Holland Scholarship', 'studyinnl.org', 'Europe', 'check degree level'],
  // ---------------- EUROPE: UK / Ireland ----------------
  ['International Scholarship for UG Students - Swansea University', 'swansea.ac.uk', 'Europe', 'bachelor eligible'],
  ['International Excellence Scholarships - University of Hull', 'hull.ac.uk', 'Europe', 'bachelor eligible'],
  ['International Undergraduate Scholarships - University of Plymouth', 'plymouth.ac.uk', 'Europe', 'bachelor eligible'],
  ['International Scholarships - University of Dundee', 'dundee.ac.uk', 'Europe', 'bachelor eligible'],
  ['International Excellence Scholarship (UNDERGRADUATE round) - University of St Andrews', 'st-andrews.ac.uk', 'Europe', 'bachelor eligible - NOTE: there is NO undergraduate "Global Excellence Scholarship" at St Andrews; that name belongs to the postgraduate round. The undergraduate awards are International Undergraduate Scholarship, International Excellence Scholarship, Accommodation Award International, Davis UWC.'],
  ['International Excellence Scholarship - University of Glasgow', 'gla.ac.uk', 'Europe', 'bachelor eligible'],
  ['Beit Scholarship - University of Oxford', 'ox.ac.uk', 'Europe', 'bachelor eligible'],
  ['Gates Cambridge Scholarship', 'cam.ac.uk', 'Europe', 'bachelor eligible'],
  ['Churchill Scholarship - University of Cambridge', 'cam.ac.uk', 'Europe', 'bachelor eligible'],
  ['Duffy Companies Rugby Scholarship - University College Dublin', 'ucd.ie', 'Europe', 'bachelor eligible'],
  ['Bursaries and Scholarships - University College Cork', 'ucc.ie', 'Europe', 'bachelor eligible'],
  // ---------------- EUROPE: Nordics ----------------
  ['Admissions Scholarships - Chalmers University of Technology', 'chalmers.se', 'Europe', 'bachelor eligible'],
  ['Admissions Scholarship - KTH Royal Institute of Technology', 'kth.se', 'Europe', 'bachelor eligible'],
  ['University Scholarship - Linkoping University', 'liu.se', 'Europe', 'bachelor eligible'],
  ['University Scholarship - Umea University', 'umu.se', 'Europe', 'bachelor eligible'],
  ['Johan Sebastian Bach Scholarship - University of Gothenburg', 'gu.se', 'Europe', 'bachelor eligible'],
  ['Norwegian State Educational Loan Fund / Study Allowance - Skatteetaten', 'skatteetaten.no', 'Europe', 'study support not award - verify'],
  ['Finnish Government Scholarship for Tuition Fees', 'oph.fi', 'Europe', 'bachelor eligible'],
  ['Denmark Student Grant (SU) - Udbetaling Danmark', 'studiebolig.dk', 'Europe', 'study support not award - verify'],
  ['Study Grant / Tuition Waiver - Iceland University', 'hi.is', 'Europe', 'bachelor eligible'],
  // ---------------- EUROPE: Central / Eastern ----------------
  ['Norwegian Government Scholarship - GOG and Romania bilateral', 'gog.gov.ro', 'Europe', 'bachelor eligible'],
  ['Study in Poland Scholarships - NAWA', 'nawa.gov.pl', 'Europe', 'verify bachelor level'],
  ['Government Scholarships for Foreign Students - Ministry of Education Czech Republic', 'education.gov.cz', 'Europe', 'verify bachelor level'],
  ['Programme ambassador - Fulbright Slovakia', 'fulbright.sk', 'Europe', 'master focused - verify'],
  ['Austria Development Cooperation Scholarship - OeAD', 'oead.adam.at', 'Europe', 'verify bachelor level'],
  ['German Academic Exchange Service Scholarships', 'daad.de', 'Europe', 'verify bachelor level'],
  ['Rector Scholarship - University of Sarajevo', 'unsa.ba', 'Europe', 'local focused - verify'],
  ['Scholarship Programme - University of Tirana', 'unit.edu.al', 'Europe', 'verify eligibility'],
  ['Cyprus University of Technology International Scholarships', 'cut.ac.cy', 'Europe', 'bachelor eligible'],
  ['University of Malta International Scholarships', 'um.edu.mt', 'Europe', 'bachelor eligible'],
  ['Admissions Scholarship - University of Zagreb', 'unizg.hr', 'Europe', 'bachelor eligible'],
  ['Jasminka Scholarship - University of Ljubljana', 'uni-lj.si', 'Europe', 'bachelor eligible'],
  // ---------------- UNITED STATES ----------------
  ['Tuition Waiver for International Students - University of Tuebingen', 'uni-tuebingen.de', 'Europe', 'bachelor eligible'],
  ['Tuition and Fee Waiver for International Students - University of Freiburg', 'uni-freiburg.de', 'Europe', 'bachelor eligible'],
  ['International Tuition Waiver - Technical University of Munich', 'tum.de', 'Europe', 'bachelor eligible'],
  ['International Tuition Fee Waiver - University of Cologne', 'uni-koeln.de', 'Europe', 'bachelor eligible'],
  ['Tuition Fee Waiver - University of Hamburg', 'uni-hamburg.de', 'Europe', 'bachelor eligible'],
  ['International Student Scholarships - University of Bonn', 'uni-bonn.de', 'Europe', 'bachelor eligible'],
  ['International Tuition Fee Reduction - RWTH Aachen University', 'rwth-aachen.de', 'Europe', 'bachelor eligible'],
  ['Tuition Fee Waiver - University of Mannheim', 'uni-mannheim.de', 'Europe', 'bachelor eligible'],
  ['Scholarships for International Students - University of Amsterdam', 'uva.nl', 'Europe', 'bachelor eligible'],
  ['International Scholarship - University of Groningen', 'rug.nl', 'Europe', 'bachelor eligible'],
  ['Holland Scholarship TU Delft', 'tudelft.nl', 'Europe', 'check degree level'],
  ['Scholarships and Grants - University of Southern Denmark', 'sdu.dk', 'Europe', 'bachelor eligible'],
  ['Tuition Fee Scholarship - Technical University of Denmark', 'dtu.dk', 'Europe', 'bachelor eligible'],
  ['University International Scholarship - University of Gothenburg', 'gu.se', 'Europe', 'duplicate pool - dedupe in script'],
  ['President Scholarship - Williams College', 'williams.edu', 'United States', 'bachelor eligible'],
  ['Bowdoin College General Scholarship', 'bowdoin.edu', 'United States', 'bachelor eligible'],
  ['Middlebury College International Scholarships', 'middlebury.edu', 'United States', 'bachelor eligible'],
  ['Oberlin College International Scholarships', 'oberlin.edu', 'United States', 'bachelor eligible'],
  ['Denison University International Scholarships', 'denison.edu', 'United States', 'bachelor eligible'],
  ['Wofford College International Scholarships', 'wofford.edu', 'United States', 'bachelor eligible'],
  ['Lehigh University International Scholarships', 'lehigh.edu', 'United States', 'bachelor eligible'],
  ['Emerson College International Scholarships', 'emerson.edu', 'United States', 'bachelor eligible'],
  ['Brandeis University International Scholarship', 'brandeis.edu', 'United States', 'bachelor eligible - verify vs id 58 Wien'],
  ['New York University International Scholarships', 'nyu.edu', 'United States', 'bachelor eligible'],
  ['Johns Hopkins International Scholarships', 'jhu.edu', 'United States', 'bachelor eligible'],
  ['Tufts University International Scholarships', 'tufts.edu', 'United States', 'bachelor eligible'],
  ['University of Chicago International Scholarships - verify', 'uchicago.edu', 'United States', 'ALREADY TAKEN id 96 - exclude'],
  ['Howard University International Scholarships', 'howard.edu', 'United States', 'bachelor eligible'],
  ['George Washington University International Merit Scholarships', 'gwu.edu', 'United States', 'bachelor eligible'],
  ['Georgetown University International Scholarships', 'georgetown.edu', 'United States', 'bachelor eligible'],
  ['Santa Clara University International Scholarships', 'scu.edu', 'United States', 'bachelor eligible'],
  ['SMU International Scholarships', 'smu.edu', 'United States', 'bachelor eligible'],
  ['Arizona State University International Scholarships', 'asu.edu', 'United States', 'bachelor eligible'],
  ['University of Colorado Boulder International Scholarships', 'colorado.edu', 'United States', 'bachelor eligible'],
  ['Boston College International Scholarships - verify', 'bc.edu', 'United States', 'ALREADY TAKEN id 123 - exclude'],
  ['Fordham University International Scholarships', 'fordham.edu', 'United States', 'bachelor eligible'],
  ['Villanova University International Scholarships', 'villanova.edu', 'United States', 'bachelor eligible'],
  ['Yeshiva University International Scholarships', 'yeshiva.edu', 'United States', 'bachelor eligible'],
  ['Pace University International Scholarships', 'pace.edu', 'United States', 'bachelor eligible'],
  ['Catholic University of America International Scholarships', 'cua.edu', 'United States', 'bachelor eligible'],
  ['Pepperdine University International Scholarships', 'pepperdine.edu', 'United States', 'bachelor eligible'],
  ['Chapman University International Scholarships', 'chapman.edu', 'United States', 'bachelor eligible'],
  ['Pratt Institute International Scholarships', 'pratt.edu', 'United States', 'bachelor eligible'],
  ['ArtCenter College of Design International Scholarships', 'artcenter.edu', 'United States', 'bachelor eligible'],
  ['Ringling College of Art and Design International Scholarships', 'ringling.edu', 'United States', 'bachelor eligible'],
  ['Savannah College of Art and Design International Merit Scholarships', 'scad.edu', 'United States', 'bachelor eligible'],
  ['Berklee College of Music International Scholarships', 'berklee.edu', 'United States', 'bachelor eligible'],
  ['Juilliard School Scholarships', 'juilliard.edu', 'United States', 'verify free tuition'],
  ['Colburn Conservatory of Music', 'colburn.edu', 'United States', 'bachelor eligible'],
  // ---------------- CANADA ----------------
  ['Queen University International Scholarships', 'queensu.ca', 'Canada', 'bachelor eligible'],
  ['Western University International Scholarships', 'uwo.ca', 'Canada', 'bachelor eligible'],
  ['University of Ottawa International Scholarships', 'uottawa.ca', 'Canada', 'bachelor eligible'],
  ['Carleton University International Scholarships', 'carleton.ca', 'Canada', 'bachelor eligible'],
  ['Concordia University International Scholarships', 'concordia.ca', 'Canada', 'bachelor eligible'],
  ['University of Manitoba International Scholarships', 'umanitoba.ca', 'Canada', 'bachelor eligible'],
  ['University of Saskatchewan International Scholarships', 'usask.ca', 'Canada', 'bachelor eligible'],
  ['University of Alberta International Scholarships', 'ualberta.ca', 'Canada', 'bachelor eligible'],
  ['University of Calgary International Scholarships', 'ucalgary.ca', 'Canada', 'bachelor eligible'],
  ['Wilfrid Laurier University International Scholarships', 'wlu.ca', 'Canada', 'bachelor eligible'],
  ['University of Guelph International Scholarships', 'uoguelph.ca', 'Canada', 'bachelor eligible'],
  ['Trent University International Scholarships', 'trentu.ca', 'Canada', 'bachelor eligible'],
  ['Brock University International Scholarships', 'brocku.ca', 'Canada', 'bachelor eligible'],
  ['Lakehead University International Scholarships', 'lakeheadu.ca', 'Canada', 'bachelor eligible'],
  ['University of Windsor International Scholarships', 'uwindsor.ca', 'Canada', 'bachelor eligible'],
  ['Dalhousie University International Scholarships', 'dal.ca', 'Canada', 'bachelor eligible'],
  ['Simon Fraser University International Scholarships', 'sfu.ca', 'Canada', 'bachelor eligible'],
  ['University of Victoria International Scholarships', 'uvic.ca', 'Canada', 'bachelor eligible'],
  ['Memorial University International Scholarships', 'mun.ca', 'Canada', 'bachelor eligible'],
  ['Thompson Rivers University International Scholarships', 'tru.ca', 'Canada', 'bachelor eligible'],
  // ---------------- AUSTRALIA ----------------
  ['K.C. Kuok Scholarship - Monash University', 'monash.edu', 'Australia', 'bachelor eligible - verify vs id 52'],
  ['International Excellence Scholarships - University of Queensland', 'uq.edu.au', 'Australia', 'bachelor eligible'],
  ['Adelaide Foundation International Scholarships - University of Adelaide', 'adelaide.edu.au', 'Australia', 'bachelor eligible'],
  ['International Excellence Scholarship - University of Tasmania', 'utas.edu.au', 'Australia', 'bachelor eligible'],
  ['Curtin University International Scholarships', 'curtin.edu.au', 'Australia', 'bachelor eligible'],
  ['University of the Sunshine Coast International Scholarships', 'usc.edu.au', 'Australia', 'bachelor eligible - NOT usc.edu'],
  ['Charles Darwin University International Scholarships', 'cdu.edu.au', 'Australia', 'bachelor eligible'],
  ['Murdoch University International Scholarships', 'murdoch.edu.au', 'Australia', 'bachelor eligible'],
  ['University of Wollongong International Scholarships', 'uow.edu.au', 'Australia', 'bachelor eligible'],
  ['University of New England International Scholarships', 'une.edu.au', 'Australia', 'bachelor eligible'],
  ['Griffith University International Student Scholarships', 'griffith.edu.au', 'Australia', 'bachelor eligible - check slot 41 use'],
  ['Bond University International Scholarships', 'bond.edu.au', 'Australia', 'bachelor eligible'],
  ['Charles Sturt University International Scholarships', 'csu.edu.au', 'Australia', 'bachelor eligible'],
  ['Federation University Australia International Scholarships', 'federation.edu.au', 'Australia', 'bachelor eligible'],
  ['Deakin University International Scholarships', 'deakin.edu.au', 'Australia', 'PURGED - verify'],
  ['University of South Australia International Scholarships', 'unisa.edu.au', 'Australia', 'bachelor eligible'],
  ['Western Sydney University International Scholarships', 'westernsydney.edu.au', 'Australia', 'bachelor eligible'],
  ['University of Wollongong Dubai / RMIT - verify', 'rmit.edu.au', 'Australia', 'bachelor eligible - check slot 46'],
  // ---------------- SINGAPORE ----------------
  ['Singapore University of Social Science Undergraduate Scholarships', 'suss.edu.sg', 'Singapore', 'bachelor eligible'],
  ['NUS International Undergraduate Scholarship - verify', 'nus.edu.sg', 'Singapore', 'ALREADY TAKEN id 105 - exclude'],
  ['NTU ASEAN Undergraduate Scholarship', 'ntu.edu.sg', 'Singapore', 'bachelor eligible - check slot 51 use'],
  ['SUTD Undergraduate Scholarships', 'sutd.edu.sg', 'Singapore', 'bachelor eligible - check slot 54 use'],
  ['SMU Undergraduate Scholarships for International Students', 'smu.edu.sg', 'Singapore', 'bachelor eligible - check slot 53 use'],
  ['NUS Scholars Programme - verify', 'nus.edu.sg', 'Singapore', 'master focused - verify'],
  // ---------------- MALAYSIA ----------------
  ['Universiti Malaya International Undergraduate Scholarships', 'um.edu.my', 'Malaysia', 'NEGATIVE FINDING — do not assign. UM publishes NO international undergraduate scholarship: aasd.um.edu.my is unreachable server-side and the International Booklet PDF contains zero scholarship or waiver mentions. Recorded from two research passes.'],
  ['Universiti Sains Malaysia International Undergraduate Scholarships', 'usm.my', 'Malaysia', 'NEGATIVE FINDING — do not assign. USM publishes only a per-semester tuition-fee PDF for international undergraduates, and its own site lists international financial assistance as MIS, CSFP and IsDB, which are postgraduate external schemes. No UG scholarship exists to record.'],
  ['Universiti Putra Malaysia International Undergraduate Scholarships', 'upm.edu.my', 'Malaysia', 'bachelor eligible'],
  ['Universiti Teknologi MARA International Scholarships', 'uitm.edu.my', 'Malaysia', 'bachelor eligible'],
  ['Universiti Islam Antarabangsa Malaysia International Scholarships', 'iium.edu.my', 'Malaysia', 'bachelor eligible'],
  ['Universiti Malaysia Sarawak International Undergraduate Scholarships', 'unimas.my', 'Malaysia', 'bachelor eligible'],
  ['Universiti Malaysia Terengganu International Scholarships', 'umt.edu.my', 'Malaysia', 'bachelor eligible'],
  ['Taylor University International Undergraduate Scholarships', 'taylors.edu.my', 'Malaysia', 'bachelor eligible'],
  ['Sunway University International Undergraduate Scholarships', 'sunway.edu.my', 'Malaysia', 'bachelor eligible'],
  ['UCSI University International Undergraduate Scholarships', 'ucsi.edu.my', 'Malaysia', 'bachelor eligible'],
  ['Universiti Tunku Abdul Rahman International Undergraduate Scholarships', 'utar.edu.my', 'Malaysia', 'bachelor eligible'],
  ['Management and Science University International Scholarships', 'msu.edu.my', 'Malaysia', 'bachelor eligible'],
  ['Multimedia University International Undergraduate Scholarships', 'mmu.edu.my', 'Malaysia', 'bachelor eligible'],
  ['Universiti Kuala Lumpur International Undergraduate Scholarships', 'unimap.edu.my', 'Malaysia', 'bachelor eligible'],
  ['HELP University International Undergraduate Scholarships', 'help.edu.my', 'Malaysia', 'bachelor eligible'],
  ['SEGi University International Undergraduate Scholarships', 'segi.edu.my', 'Malaysia', 'bachelor eligible'],
  ['Universiti Sultan Zainal Abidin International Scholarships', 'unisza.edu.my', 'Malaysia', 'bachelor eligible'],
  ['Universiti Pertahanan Nasional Malaysia International Scholarships', 'upnm.edu.my', 'Malaysia', 'restricted - verify'],
];

// ---------------------------------------------------------------- filters
const ALLOWED_REGIONS = new Set(['Europe', 'United States', 'Canada', 'Australia', 'Singapore', 'Malaysia']);
const EXCLUDE_NOTE = /ALREADY TAKEN|PURGED|duplicate pool|verify vs/i;

const accepted = [], rejected = [];
const usedHosts = new Set();

for (const [name, host, region, note] of POOL) {
  const h = host.toLowerCase();

  if (!ALLOWED_REGIONS.has(region)) {
    rejected.push({ name, host, region, why: `region "${region}" not allowed` });
    continue;
  }
  if (EXCLUDE_NOTE.test(note) && /ALREADY TAKEN|PURGED/.test(note)) {
    rejected.push({ name, host, region, why: note });
    continue;
  }
  if (usedHosts.has(h)) {
    rejected.push({ name, host, region, why: 'host already used in this batch' });
    continue;
  }
const hostHits = idx.byHost[h] || [];
  // Subdomain matters: the UQ record is keyed on scholarships.uq.edu.au while the
  // obvious candidate host is uq.edu.au. Filtering on exact host alone misses it,
  // which is how "International Excellence Scholarships - University of
  // Queensland" slipped through against LIVE id 194.
  const reg = h.split('.').slice(-2).join('.');
  const domainHits = hostHits.length ? hostHits : (idx.byDomain[reg] || []);

  // Breadth is not identity. A host that carries many unrelated awards is a
  // platform or a funder directory (daad.de runs dozens of separate programmes;
  // anr.fr appears on awards it does not fund), so on its own it cannot prove a
  // duplicate. Those targets fall through to the name check, which is the signal
  // that actually distinguishes "same award" from "same website".
  const broad = (idx.shared_hosts || {})[h] || (idx.shared_hosts || {})[reg] || null;
  if (domainHits.length && !broad) {
    rejected.push({
      name, host, region,
      why: 'registrable domain already in DB: ' + domainHits.map(a => `${a.state}/id${a.id ?? '-'}/${a.name || 'untitled'}`).join(', '),
    });
    continue;
  }

  const nk = norm(name);
  const nameHits = idx.byName[nk] || [];
  if (nameHits.length) {
    rejected.push({
      name, host, region,
      why: 'name already in DB: ' + nameHits.map(a => `${a.state}/id${a.id ?? '-'}/${a.name || 'untitled'}`).join(', '),
    });
    continue;
  }
  if (broad) {
    // Accepted, but flagged: an agent must confirm the award name is not already
    // indexed under a different phrasing before writing.
    accepted.push({ name, host, region, note, logo_host_taken: (idx.logo_hosts || []).includes(h), shared_host_warn: `${broad.award_count} existing awards on this host; confirm by name before writing` });
    usedHosts.add(h);
    continue;
  }

  usedHosts.add(h);
  accepted.push({ name, host, region, note, logo_host_taken: (idx.logo_hosts || []).includes(h) });
}

// ---------------------------------------------------------------- output
accepted.forEach((a, i) => { a.slot = 'b' + String(i + 1).padStart(2, '0'); });
rejected.forEach((r, i) => { r.slot = null; });

const payload = {
  _generated: new Date().toISOString(),
  _method: 'curated pool filtered against EXISTING_AWARDS.json by official host, then normalised name, then in-batch host uniqueness',
  accepted_count: accepted.length,
  rejected_count: rejected.length,
  logo_hosts_already_taken: accepted.filter(a => a.logo_host_taken).map(a => a.host),
  accepted,
  rejected,
};
fs.writeFileSync(path.join(DIR, 'ASSIGNMENTS.json'), JSON.stringify(payload, null, 2));

const L = [];
L.push('# BACHELOR BATCH ASSIGNMENTS â€” duplicate-free');
L.push('');
L.push(`Generated ${payload._generated}`);
L.push('');
L.push(`**${accepted.length} accepted, ${rejected.length} rejected as duplicates or out of scope.**`);
L.push('');
L.push('Filter order: allowed region -> hard-exclude note -> in-batch host uniqueness -> host already in');
L.push('`EXISTING_AWARDS.json` -> normalised name already in `EXISTING_AWARDS.json`.');
L.push('');
L.push('`logo_host_taken = true` means `official_logo_overrides.json` already has a key for that host, so');
L.push('PART D must NOT add a second entry for it.');
L.push('');
L.push('L.push is wrong');
L.push('| slot | award name | official host | region | degree note | logo_host_taken |');
L.push('|---|---|---|---|---|---|');
accepted.forEach((a) => {
  L.push(`| **${a.slot}** | ${a.name} | \`${a.host}\` | ${a.region} | ${a.note} | ${a.logo_host_taken} |`);
});
L.push('');
L.push('## Rejected');
L.push('');
L.push('| name | host | why |');
L.push('|---|---|---|');
rejected.forEach(r => L.push(`| ${r.name} | \`${r.host}\` | ${r.why} |`));
L.push('');
fs.writeFileSync(path.join(DIR, 'ASSIGNMENTS.md'), L.join('\n'));

console.log('='.repeat(72));
console.log('ASSIGNMENTS BUILT');
console.log('='.repeat(72));
console.log('accepted :', accepted.length);
console.log('rejected :', rejected.length);
console.log('');
const byRegion = {};
for (const a of accepted) byRegion[a.region] = (byRegion[a.region] || 0) + 1;
console.log('by region:', JSON.stringify(byRegion));
console.log('');
console.log('REJECTED AS DUPLICATE (proof the old hand list was wrong):');
for (const r of rejected.filter(x => /already in DB/.test(x.why))) {
  console.log('  x ' + r.name + '  [' + r.host + ']');
  console.log('      ' + r.why);
}
console.log('');
console.log('WROTE ' + path.relative(process.cwd(), path.join(DIR, 'ASSIGNMENTS.json')));
console.log('WROTE ' + path.relative(process.cwd(), path.join(DIR, 'ASSIGNMENTS.md')));
