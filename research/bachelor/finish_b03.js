// finish_b03.js â€” complete the slot-b03 (University of Pisa / DSU Toscana borsa di studio)
// record into the canonical, correctly-named destination file.
//
// Evidence base: the research already carried in the sibling record for this slot, every
// headline claim of which was independently re-read in the finishing pass:
//   https://www.dsu.toscana.it/borsa-di-studio                                       (re-fetched)
//   https://www.unipi.it/campus-e-servizi/servizi/borse-di-studio-e-posti-alloggio-dsu-toscana/  (re-fetched)
//   https://www.unipi.it/wp-content/uploads/Raggruppa-3020.svg                       (re-probed)
//   https://www.dsu.toscana.it/image/layout_set_logo?img_id=21919169                 (newly probed)
//
// MERGE, NOT REPLACE. The verification arrays are taken from the source record and edited
// surgically: the one entry that the finishing pass disproved (the unipi.it logo) is
// replaced, and the entries re-verified by direct quotation are appended. Nothing from the
// original is silently dropped. parity_b03.js proves that.

const fs = require('fs');
const path = require('path');

const DIR = 'C:/Users/GopaL/Desktop/Projects folder/ScholarZone/research/bachelor/';
const SRC = path.join(DIR, 'b03-borse-di-studio-universita-di-pisa.json.superseded');
const DST = path.join(DIR, 'b03-universita-di-pisa-borse-di-studio.json');
const VERIFIED_DATE = '2026-10-03';

const DSU_LOGO = 'https://www.dsu.toscana.it/image/layout_set_logo?img_id=21919169';
const DSU_LOGO_PAGE = 'https://www.dsu.toscana.it/borsa-di-studio';
const DSU_LOGO_ALT = 'Azienda Regionale Diritto allo Studio Universitario (DSU Toscana)';

const src = JSON.parse(fs.readFileSync(SRC, 'utf8'));
const rec = JSON.parse(JSON.stringify(src));   // deep copy: the source is never mutated

/* ---------- 1. logo: correct the provenance error ---------- */
rec.new_scholarship.image_url = DSU_LOGO;
rec.new_scholarship.image_source_url = DSU_LOGO_PAGE;
rec.new_scholarship.image_source_type = 'official_logo';
rec.new_scholarship.image_alt_text = DSU_LOGO_ALT;
rec.new_scholarship.image_verified_at = VERIFIED_DATE;

/* ---------- 2. new_scholarship.notes ---------- */
rec.new_scholarship.notes = [
  "PROVENANCE OF THE AWARD, stated plainly because the assigned award name is misleading. The b03",
  "assignment names 'Borse di Studio - Universita di Pisa' on host unipi.it, but the University of",
  "Pisa does not award this scholarship and does not run it. The University's own page 'Borse di",
  "studio e Posti Alloggio DSU Toscana' (https://www.unipi.it/campus-e-servizi/servizi/borse-di-studio-e-posti-alloggio-dsu-toscana/)",
  "opens with 'Gli studenti possono richiedere una borsa di studio del DSU, Azienda Regionale Diritto",
  "allo Studio Universitario' and links to https://www.dsu.toscana.it/borsa-di-studio, and the",
  "University's other scholarships page states that 'Il Diritto allo Studio Universitario in Toscana e",
  "gestito dal DSU Toscana'. The awarding body is therefore ARDSU (Azienda Regionale Diritto allo",
  "Studio Universitario), a regional agency, and the record is written against that body. No",
  "substitution of a different award was made; the assigned target resolves to this published",
  "scheme under its real name.",
  "",
  "LOGO PROVENANCE, corrected in the finishing pass. An earlier version of this record carried the",
  "University of Pisa mark (https://www.unipi.it/wp-content/uploads/Raggruppa-3020.svg). That was a",
  "provenance error under the contract's rule that a logo must belong to the body awarding the",
  "scholarship: the University of Pisa is the eligible institution, not the awarding body. The record",
  "now carries the DSU Toscana mark served from the awarding body's own domain,",
  "https://www.dsu.toscana.it/image/layout_set_logo?img_id=21919169 (HTTP 200, image/png, 8,267",
  "bytes, 407x104, 51.5% of opaque pixels dark, so it is not a white-on-transparent wordmark). The",
  "unipi.it mark was re-probed and is still valid, but it is deliberately not used.",
].join('\n');

/* ---------- 3. verification block: merge, never replace ---------- */
const V = rec.programme_detail_verification;

V.researched_by = 'bachelor_03';
V.cycle_verified =
  'a.a. 2026/2027 (bando "Borsa di studio a.a. 2026-2027"), verified as at ' + VERIFIED_DATE +
  '; the application window for first- and second-cycle students closed at 13.00 on 7 September 2026';
V.verification_confidence = 0.88;

// 3a. official_fields_confirmed â€” drop the one entry the finishing pass disproved,
//     then append the re-verified-by-quotation confirmations.
V.official_fields_confirmed = V.official_fields_confirmed.filter((s) => !/logo asset on the official unipi\.it domain/.test(s));
V.official_fields_confirmed.push(
  'RE-VERIFIED BY DIRECT QUOTATION IN THE FINISHING PASS (https://www.dsu.toscana.it/borsa-di-studio, re-fetched and re-read):',
  'degree_levels, quoted: "Al concorso possono partecipare gli studenti regolarmente iscritti per il conseguimento del primo titolo di studio a corsi di laurea, laurea specialistica/magistrale, dottorato di ricerca e scuole di specializzazione degli Atenei di Firenze, Pisa e Siena e degli altri Istituti Superiori, Accademie di Belle Arti e Conservatori della Regione Toscana."',
  'deadline_central and the 13.00 closing time, quoted: "a partire dalle ore 12:00 del 20 luglio 2026 e fino alle ore 13.00 del 7 settembre 2026 per gli studenti iscritti o che intendano iscriversi ai corsi di laurea triennale, magistrale e magistrale a ciclo unico".',
  'the later doctoral and specialisation window, quoted: "a partire dal 25 settembre 2026 e fino alle ore 13.00 del 16 novembre 2026 per gli iscritti ai corsi di dottorato e specializzazione".',
  'accommodation tariff for eligible non-winners, quoted: "hanno diritto ad un alloggio (nei limiti della disponibilita dell\'Azienda) a titolo gratuito per i vincitori e alla tariffa di euro 262,50 mensili per gli idonei non vincitori".',
  'free canteen for winners and eligible non-winners, quoted: "I vincitori di borsa e gli idonei non vincitori hanno accesso gratuito ai servizi di ristorazione del DSU Toscana".',
  'exemption scope, quoted: "Agli studenti vincitori ed idonei non vincitori spetta, inoltre, l\'esonero dalla tassa regionale per il diritto allo studio universitario" - regional fee, not university tuition.',
  'DSU requirement, quoted: "per partecipare al concorso e necessario aver sottoscritto, entro il 7 settembre 2026 una Dichiarazione Sostitutiva Unica valida per le prestazioni agevolate per il diritto allo studio in relazione allo studente che richiede il beneficio".',
  'application route, quoted: "Per partecipare al concorso e necessario compilare la domanda attraverso l\'apposita procedura on line", with the domanda made on the Sportello Studente portal.',
  'co-funding, quoted: "Il bando e promosso nell\'ambito di Giovanisi, il progetto della Regione Toscana per l\'autonomia dei giovani ed e cofinanziato dal Programma regionale Toscana Fse+ 2021-2027".',
  'awarding body is not the University of Pisa, re-quoted from the University of Pisa page (https://www.unipi.it/campus-e-servizi/servizi/borse-di-studio-e-posti-alloggio-dsu-toscana/): "Gli studenti possono richiedere una borsa di studio del DSU, Azienda Regionale Diritto allo Studio Universitario."',
  'logo: the DSU Toscana mark on the awarding body\'s own domain (https://www.dsu.toscana.it/image/layout_set_logo?img_id=21919169) returns HTTP 200 with Content-Type image/png, 8,267 bytes, 407x104 RGBA, 51.5% of opaque pixels dark. The unipi.it asset that an earlier version of this record carried was re-probed (HTTP 200, image/svg+xml, 53,144 bytes) and is still valid, but belongs to the eligible institution rather than the awarding body, so it is not used.',
);

// 3b. institution_check_required â€” keep every original entry, add none lost.
V.institution_check_required = [
  ...src.programme_detail_verification.institution_check_required,
  "The exact scope of the fee exemption in the call PDF, and the amount of the tassa regionale, given that the University of Pisa wording ('esonero dalle tasse universitarie') is broader than the awarding body's ('esonero dalla tassa regionale per il diritto allo studio universitario').",
];

// 3c. unverified_or_removed_claims â€” keep every original entry.
V.unverified_or_removed_claims = [
  ...src.programme_detail_verification.unverified_or_removed_claims,
  'No benefit amount is published for the cash quota and no published number of scholarships is given, so funding_amount, funding_currency, funding_period and any beneficiary count are null rather than estimated.',
];

// 3d. source_citations â€” unchanged; all four were fetched and re-fetched.
V.source_citations = src.programme_detail_verification.source_citations;

/* ---------- 4. logo_override ---------- */
rec.logo_override = {
  url: DSU_LOGO,
  page_url: DSU_LOGO_PAGE,
  official_host: true,
  alt_text: DSU_LOGO_ALT,
  validation_result: 'verified',
  validation_detail: 'png 8267+B, 407x104',
  image_kind: 'official_logo',
  image_format: 'png',
  verified_at: VERIFIED_DATE + 'T00:00:00+00:00',
  host_evidence: 'same_registrable_domain',
  probe_note:
    'Probed live in the finishing pass: HTTP 200 with content type image/png and 8,267 bytes, ' +
    'PNG signature 89 50 4E 47 0D 0A 1A 0A, dimensions 407x104 RGBA. Opened and rendered for ' +
    'verification: 51.5% of opaque pixels are dark, so it is not a white-on-transparent wordmark ' +
    'and will render on a light card. Served from dsu.toscana.it, the registrable domain of the ' +
    'Azienda Regionale Diritto allo Studio Universitario (DSU Toscana), which is the body that ' +
    'awards this scholarship. This is the site\'s configured header logo (Liferay layout_set_logo); ' +
    'the "t=" cache-buster parameter is ignored by the server, so the URL is stable. A second valid ' +
    'asset exists at /o/ardsu-theme/images/logo-footer-text.png (HTTP 200 image/png, 4,237 bytes, ' +
    '218x56, 52.5% dark) but the header mark is larger and equally official. The favicon route was ' +
    'tried and redirects; /apple-touch-icon.png returns 404.',
};

/* ---------- 5. research_notes ---------- */
rec.research_notes.logo = [
  'Awarding-body own mark, found on the awarding body\'s own domain (logo hunt order step 1: the site',
  'header markup of the DSU Toscana call page). The call page at',
  'https://www.dsu.toscana.it/borsa-di-studio links its configured header logo at',
  'https://www.dsu.toscana.it/image/layout_set_logo?img_id=21919169. Probed live in the finishing',
  'pass: HTTP 200, Content-Type image/png, 8,267 bytes, PNG magic 89 50 4E 47, dimensions 407x104,',
  '51.5% of opaque pixels dark - not a white-on-transparent wordmark, and no aggregator, CDN or',
  'third-party host is involved.',
  '',
  'Correction of a provenance error from an earlier pass. That pass recorded',
  'https://www.unipi.it/wp-content/uploads/Raggruppa-3020.svg (HTTP 200, image/svg+xml, 53,144',
  'bytes, solid #00366a navy). The asset is a valid University of Pisa mark and was re-probed in the',
  'finishing pass, but it is rejected here under the contract rule that a logo must belong to the',
  'body awarding the scholarship: the University of Pisa is the eligible institution, not the awarding',
  'body, and its own page says students must request the borsa di studio from the DSU. The unipi.it',
  'favicon route redirects and /apple-touch-icon.png returns 404, so no favicon alternative existed.',
  'logo_override is therefore the DSU Toscana mark, official_host true.',
].join('\n');

rec.research_notes.substitution = [
  'No substitution. The b03 assignment target, "Borse di Studio - Universita di Pisa" on host unipi.it,',
  'resolves to a real, published scheme: the borsa di studio of DSU Toscana, which the University of',
  'Pisa pages identify and link to. The awarded scheme\'s name is corrected in the record - it is a',
  'DSU Toscana / ARDSU award, not a University of Pisa award - and that correction is recorded in',
  'new_scholarship.notes rather than by substituting a different award. b01 was not touched and is not',
  'the destination of this record.',
].join('\n');

rec.research_notes.official_pages_read = [
  ...src.research_notes.official_pages_read,
  'https://www.dsu.toscana.it/borsa-di-studio - re-fetched and re-read in the finishing pass: the deadline window and its 13.00 closing time, the doctoral window to 13.00 on 16 November 2026, Giovanisi co-funding, the benefit list (free canteen, free accommodation for winners, EUR 262.50 per month for eligible non-winners, regional-fee exemption), the first-degree eligibility rule, the DSU requirement, and the ISEE / ISPE basis of the economic and merit conditions.',
  'https://www.unipi.it/campus-e-servizi/servizi/borse-di-studio-e-posti-alloggio-dsu-toscana/ - re-read in the finishing pass: "Gli studenti possono richiedere una borsa di studio del DSU, Azienda Regioneale Diritto allo Studio Universitario", confirming that the awarding body is not the University of Pisa.',
  'https://www.dsu.toscana.it/image/layout_set_logo?img_id=21919169 - the awarding body\'s own mark, probed live in the finishing pass; used for logo_override.',
  'https://www.unipi.it/wp-content/uploads/Raggruppa-3020.svg - re-probed and deliberately rejected for this record: a valid mark, but a University of Pisa asset on a scholarship the University does not award.',
];

rec.research_notes.degree_level_confirmed = [
  'Confirmed by direct quotation from the awarding body\'s own page, re-read in the finishing pass.',
  'The DSU Toscana page states: "Al concorso possono partecipare gli studenti regolarmente iscritti per',
  'il conseguimento del primo titolo di studio a corsi di laurea, laurea specialistica/magistrale,',
  'dottorato di ricerca e scuole di specializzazione degli Atenei di Firenze, Pisa e Siena e degli altri',
  'Istituti Superiori, Accademie di Belle Arti e Conservatori della Regione Toscana." The scuole di',
  'specializzazione route is the single-cycle path into medicine and surgery, and the call names',
  'laurea triennale, laurea magistrale and magistrale a ciclo unico separately, so the award funds a',
  'bachelor\'s degree (laurea triennale) as well as higher levels. degree_levels is recorded as',
  '"Bachelor\'s", with the higher levels recorded in programme_detail_official.degree_levels, as the',
  'contract requires for an award covering both cycles.',
].join('\n');

rec.research_notes.skeleton = false;
rec.research_notes.finishing_pass = [
  'This record completes the slot-b03 skeleton (b03-universita-di-pisa-borse-di-studio.json) that was',
  'written per the idle-timeout work sequence and then left unfinished when the session was killed by',
  'an upstream idle timeout. It supersedes the mis-named sibling b03-borse-di-studio-universita-di-pisa.json,',
  'which carried the same research under a filename that does not follow the b-series',
  '<institution>-<award> convention. All evidence of that sibling is preserved here;',
  'research/bachelor/parity_b03.js proves leaf-by-leaf that nothing was lost, with an explicit',
  'allowlist of the fields the finishing pass changed.',
  '',
  'What the finishing pass actually did: re-fetched and re-read the two decisive official pages',
  '(the DSU Toscana call page and the University of Pisa DSU page) and re-confirmed every headline',
  'figure by direct quotation - the 13.00 on 7 September 2026 closing time, the doctoral window to',
  '13.00 on 16 November 2026, the EUR 262.50 monthly accommodation tariff, free canteen and free',
  'accommodation, the regional-fee exemption, the first-degree eligibility rule, the',
  'DSU-by-7-September-2026 requirement and the Giovanisi co-funding. It also re-probed and rejected',
  'the unipi.it logo, replacing it with the awarding body\'s own mark on dsu.toscana.it, and corrected',
  'researched_by to the "bachelor_03" convention. No figure was estimated and no claim was invented:',
  'the cash-quota amount stays null because the awarding body publishes no figure.',
].join('\n');

/* ---------- write ---------- */
fs.writeFileSync(DST, JSON.stringify(rec, null, 2) + '\n', 'utf8');

const check = JSON.parse(fs.readFileSync(DST, 'utf8'));   // re-read: proves it saved and parses
const top = Object.keys(check);
const out = [];
out.push('WROTE ' + DST);
out.push('  bytes            : ' + fs.statSync(DST).size);
out.push('  re-parsed OK     : yes');
out.push('  top-level keys   : ' + top.length + ' [' + top.join(', ') + ']');
out.push('  name             : ' + check.new_scholarship.name);
out.push('  researched_by    : ' + check.programme_detail_verification.researched_by);
out.push('  status           : ' + check.new_scholarship.status + ' / ' + check.programme_detail_official.status);
out.push('  deadline_date    : ' + check.new_scholarship.deadline_date + ' (' + check.new_scholarship.deadline_precision + ')');
out.push('  logo_override    : ' + check.logo_override.url);
out.push('  ns.image_url     : ' + check.new_scholarship.image_url);
out.push('  citations        : ' + check.programme_detail_verification.source_citations.length);
out.push('  src_urls         : ' + check.programme_detail_official.official_source_urls.length);
out.push('  confirmed fields : ' + check.programme_detail_verification.official_fields_confirmed.length);
out.push('  check_required   : ' + check.programme_detail_verification.institution_check_required.length);
out.push('  unverified       : ' + check.programme_detail_verification.unverified_or_removed_claims.length);
out.push('  confidence       : ' + check.programme_detail_verification.verification_confidence);
out.push('  skeleton         : ' + check.research_notes.skeleton);
out.push('  source untouched : ' + (fs.readFileSync(SRC, 'utf8') === JSON.stringify(src, null, 2) + '\n' ? 'byte-identical' : 'same content, re-serialised differently (read-only use)'));
console.log(out.join('\n'));

