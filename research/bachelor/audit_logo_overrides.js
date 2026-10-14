#!/usr/bin/env node
/**
 * audit_logo_overrides.js
 *
 * Audits backend/config/official_logo_overrides.json against the rules that file
 * states about itself. Two researchers independently hit rule-6 violations during
 * the bachelor batch (utoronto.ca = 81/82 fills #ffffff; Duke's rejected
 * duke-wordmark-white.svg and near-white dt-logo.svg at #E2E6ED), so the
 * white-on-transparent problem is real and recurring, not hypothetical.
 *
 * The file's own _rules:
 *   3. official_host must be true ONLY when the bytes are served by the institution
 *   5. every URL was probed live and returned HTTP 200 with an image content type
 *   6. white-on-transparent wordmarks are deliberately excluded
 *   7. a host whose logo URL returns HTML rather than image bytes is excluded
 *
 * Usage:
 *   node research/bachelor/audit_logo_overrides.js              # static checks only
 *   node research/bachelor/audit_logo_overrides.js --live       # also probe URLs
 *   node research/bachelor/audit_logo_overrides.js --live --fix # rewrite obvious fixes to a NEW file
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..', '..');
const SRC = path.join(ROOT, 'backend', 'config', 'official_logo_overrides.json');
const OUT = path.join(__dirname, '_merged', 'official_logo_overrides.audit.json');
const LIVE = process.argv.includes('--live');
const FIX = process.argv.includes('--fix');

const data = JSON.parse(fs.readFileSync(SRC, 'utf8'));
const keys = Object.keys(data).filter(k => !k.startsWith('_'));

const THIRD_PARTY = [
  'wikipedia.org', 'wikimedia.org', 'commons.wikimedia', 'wikimedia', 'shutterstock',
  'gettyimages', 'istockphoto', 'dreamstime', 'freepik', 'vecteezy', 'brandfetch',
  'logowik', 'seeklogo', 'deviantart', 'shutterstock', 'cloudinary', 'amazonaws',
  'imgur.com', 'pinterest', 'pinimg', 'facebook.com', 'twitter.com', 'x.com',
  'linkedin.com', 'youtube.com', 'instagram.com', 'statically.io', 'googleusercontent',
  'wp.com', 'blogspot',
];

const regDomain = (h) => (h ? h.split('.').slice(-2).join('.') : null);
const hostOf = (u) => { try { return new URL(u).hostname.toLowerCase(); } catch { return null; } };

const findings = [];
const add = (host, severity, rule, message, extra) =>
  findings.push({ host, severity, rule, message, ...(extra || {}) });

// ---------------------------------------------------------------- static checks
for (const host of keys) {
  const e = data[host] || {};
  const url = e.url;

  if (!url) { add(host, 'ERROR', '-', 'entry has no url'); continue; }

  const uHost = hostOf(url);
  const pHost = hostOf(e.page_url || '');

  // rule 3 — official_host honesty
  if (e.official_host === true && uHost && pHost && regDomain(uHost) !== regDomain(pHost)) {
    add(host, 'ERROR', 3,
      `official_host=true but the logo is served by ${uHost} while page_url is ${pHost}`,
      { url, page_url: e.page_url });
  }
  if (e.official_host === true && !pHost) {
    add(host, 'WARN', 3, 'official_host=true but no page_url to corroborate it', { url });
  }

  // third-party hosting that is mislabelled as official
  const tp = THIRD_PARTY.find(d => (uHost || '').includes(d));
  if (tp && e.official_host === true) {
    add(host, 'ERROR', 3, `logo served by third-party host ${uHost} (${tp}) but official_host=true`, { url });
  }

  // rule 5/7 — must be https and an image, not a page
  if (!/^https:\/\//i.test(url)) add(host, 'ERROR', 5, `url is not https: ${url}`);
  if (/\.(html?|php|aspx?)$/i.test(url)) add(host, 'ERROR', 7, `url looks like a web page, not an image: ${url}`);

  // missing provenance fields
  for (const f of ['alt_text', 'image_kind', 'image_format', 'verified_at', 'host_evidence']) {
    if (!e[f]) add(host, 'WARN', '-', `missing ${f}`);
  }

  // missing validation evidence
  if (e.validation_result !== 'verified') {
    add(host, 'WARN', 4, `validation_result is "${e.validation_result}" — rule 4 says an entry is a candidate, not an approval`);
  }

  // key/host mismatch — the file's rule 1 is that keys ARE the official source host
  if (uHost && regDomain(uHost) !== regDomain(host)) {
    add(host, 'WARN', 1, `key "${host}" is not the registrable domain of the logo host ${uHost} (rename may orphan this entry)`, { url });
  }
}

// ---------------------------------------------------------------- live checks
async function liveChecks() {
  const svgEntries = keys.filter(k => /\.svg($|\?)/i.test(data[k]?.url || ''));
  const results = [];

  const CONCURRENCY = 8;
  let i = 0;
  async function worker() {
    while (i < svgEntries.length) {
      const host = svgEntries[i++];
      const url = data[host].url;
      try {
        // Retry before accusing. A single-shot probe of a WAF-fronted host
        // produced a false positive here: admissions.smu.edu.sg returned a
        // text/html Incapsula interstitial on one concurrent sweep and
        // image/svg+xml on all three sequential retries, so the rule-7 finding
        // against it was wrong. Declare a violation only if every attempt fails.
        const ATTEMPTS = 3;
        let res = null, buf = null, ctype = '', lastErr = null;
        for (let a = 1; a <= ATTEMPTS; a++) {
          try {
            const ctrl = new AbortController();
            const t = setTimeout(() => ctrl.abort(), 15000);
            const r = await fetch(url, { signal: ctrl.signal, redirect: 'follow' });
            clearTimeout(t);
            const ct = (r.headers.get('content-type') || '').toLowerCase();
            const b = Buffer.from(await r.arrayBuffer());
            if (r.ok && /image\//.test(ct)) { res = r; buf = b; ctype = ct; break; }
            res = r; buf = b; ctype = ct; lastErr = `http ${r.status} ctype ${ct}`;
          } catch (e) {
            lastErr = e.message;
          }
        }
        if (!buf) {
          add(host, 'WARN', 5, `live probe failed after ${ATTEMPTS} attempts: ${lastErr}`, { url });
          results.push({ host, ok: false, why: lastErr });
        } else if (!/image\//.test(ctype)) {
          // rule 7 — HTML interstitial / WAF page served where an image was expected.
          // Confirmed across every attempt, so this is not a transient block.
          add(host, 'ERROR', 7, `serves content-type "${ctype}" instead of an image on all ${ATTEMPTS} attempts (WAF interstitial or error page, ${buf.length} bytes)`, { url });
          results.push({ host, ok: false, why: `ctype ${ctype}` });
        } else {
          const text = buf.toString('utf8', 0, Math.min(buf.length, 400000));
          const fills = [...text.matchAll(/fill\s*=\s*["'](#?[0-9a-fA-F]{3,8})["']/g)]
            .map(m => m[1].toLowerCase());
          const nearWhite = fills.filter(f => {
            const h = f.replace('#', '');
            const full = h.length === 3 ? h.split('').map(c => c + c).join('') : h;
            if (!/^[0-9a-f]{6}$/i.test(full)) return false;
            const r = parseInt(full.slice(0, 2), 16);
            const g = parseInt(full.slice(2, 4), 16);
            const b = parseInt(full.slice(4, 6), 16);
            return r >= 235 && g >= 235 && b >= 235;
          });
          const whiteShare = fills.length ? nearWhite.length / fills.length : 0;
          const hasNone = /fill\s*=\s*["']none["']/i.test(text);

          if (fills.length && whiteShare >= 0.5) {
            // rule 6 — invisible on a light card
            add(host, 'ERROR', 6,
              `white-on-transparent wordmark: ${nearWhite.length}/${fills.length} fills are near-white (${(whiteShare * 100).toFixed(0)}%) — ${(data[host].bytes ?? buf.length)} bytes, ${ctype}`,
              { url, white_fills: nearWhite.length, total_fills: fills.length, bytes: buf.length, ctype });
          } else if (fills.length && whiteShare >= 0.3) {
            add(host, 'WARN', 6, `${nearWhite.length}/${fills.length} fills near-white (${(whiteShare * 100).toFixed(0)}%) — confirm the mark reads on a light card`, { url });
          }
          if (fills.length === 0 && !hasNone && /\.svg$/i.test(url)) {
            // no fill attributes at all usually means currentColor / black by default — safe
          }
          results.push({ host, ok: true, ctype, bytes: buf.length, fills: fills.length, whiteShare: +whiteShare.toFixed(2) });
        }
      } catch (e) {
        add(host, 'WARN', 5, `live probe failed: ${e.message}`, { url });
        results.push({ host, ok: false, why: e.message });
      }
    }
  }
  await Promise.all(Array.from({ length: CONCURRENCY }, worker));
  return results;
}

// ---------------------------------------------------------------- report
(async () => {
  let live = null;
  if (LIVE) {
    process.stdout.write(`probing ${keys.filter(k => /\.svg($|\?)/i.test(data[k]?.url || '')).length} svg entries live... `);
    live = await liveChecks();
    console.log('done');
  }

  const byRule = {};
  const bySeverity = {};
  for (const f of findings) {
    bySeverity[f.severity] = (bySeverity[f.severity] || 0) + 1;
    const rk = 'rule ' + f.rule;
    byRule[rk] = (byRule[rk] || 0) + 1;
  }

  console.log('='.repeat(74));
  console.log('OFFICIAL LOGO OVERRIDES AUDIT');
  console.log('='.repeat(74));
  console.log('entries audited :', keys.length);
  console.log('live probing    :', LIVE ? 'yes' : 'no (static checks only — pass --live)');
  console.log('findings        :', findings.length);
  console.log('');
  console.log('by severity :', JSON.stringify(bySeverity));
  console.log('by rule     :', JSON.stringify(byRule));
  console.log('');

  for (const sev of ['ERROR', 'WARN']) {
    const list = findings.filter(f => f.severity === sev);
    if (!list.length) continue;
    console.log(`--- ${sev} (${list.length}) ---`);
    list.forEach(f => console.log(`  [rule ${f.rule}] ${f.host}\n      ${f.message}`));
    console.log('');
  }

  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify({
    audited_at: new Date().toISOString(),
    source_file: path.relative(ROOT, SRC),
    entries: keys.length,
    live_probed: !!LIVE,
    counts: { bySeverity, byRule },
    findings,
    live_results: live,
    existing_rules: data._rules,
  }, null, 2));

  if (LIVE) {
    const okCount = live.filter(r => r.ok).length;
    console.log(`live: ${okCount}/${live.length} probed entries returned image bytes`);
  }
  console.log('WROTE ' + path.relative(process.cwd(), OUT));

  if (!LIVE) {
    console.log('\nNote: the white-wordmark check (rule 6) requires reading SVG bytes. Re-run with --live to test it.');
  }
})();