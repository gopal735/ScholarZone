# Logo overrides audit — `backend/config/official_logo_overrides.json`

Audited 2026-10-03 by `research/bachelor/audit_logo_overrides.js` (static + live probe of
168 SVG entries). Reproduce with:

```bash
node research/bachelor/audit_logo_overrides.js --live
```

Machine-readable results: `research/bachelor/_merged/official_logo_overrides.audit.json`

## Why this audit exists

The file states seven rules in its own `_rules`, including:

> 3. `official_host` must be true only when the bytes are served by the institution itself.
> A third-party host (for example Wikimedia) must be false, because the record's provenance says so.
> 6. White-on-transparent wordmarks are deliberately excluded. A white logo is invisible on a light card.
> 7. A host whose logo URL returns HTML rather than image bytes is excluded.

During the bachelor's batch two researchers independently hit rule-6 violations
(`utoronto.ca`, and Duke's rejected `duke-wordmark-white.svg` / near-white `dt-logo.svg`).
That made the rule look aspirational rather than enforced, so all 357 entries were tested
against it.

## Result: 46 errors, 59 warnings across 357 entries

| rule | findings | what it means |
|---|---|---|
| 4 | 27 | `validation_result` is not `verified` |
| 1 | 21 | key is not the registrable domain of the logo host (rename would orphan the entry) |
| **6** | **22** | **white-on-transparent wordmarks** |
| 3 | 19 | `official_host: true` on a host the institution does not serve from |
| **7** | **10** | **serves HTML on every attempt** |
| 5 | 6 | not https, or unreachable on all 3 attempts |

---

## CORRECTION — one earlier finding was a false positive

**An earlier version of this report listed `admissions.smu.edu.sg` under rule 7. That
was wrong, and it has been withdrawn.**

A researcher on the bachelor's batch reported that the host's *asset* paths serve real
image bytes even though its *HTML pages* return an Incapsula interstitial. I re-probed it
independently, three times, sequentially:

```
run 1: 200 image/svg+xml  39153 bytes
run 2: 200 image/svg+xml  39153 bytes
run 3: 200 image/svg+xml  39153 bytes
=> 3/3 image bytes — false positive, retracted
```

The cause was my own audit method: it probed all 168 SVG URLs **once each, eight at a
time**. A WAF-fronted host will intermittently serve an interstitial, so a single concurrent
shot is not evidence. `audit_logo_overrides.js` now retries up to three times and only
declares a violation when **every** attempt fails. Two other hosts changed as a result —
`ceu.edu` dropped from ERROR to WARN, and the hard-failure count fell from 14 to 6.

**Rule 7 now stands for these 10**, each confirmed on all three attempts:
`lse.ac.uk`, `ut.ee`, `taltech.ee`, `monash.edu`, `unibs.it`, `aauw.org`, `jwu.edu`,
`unesco.org`, `en.unito.it`, `otago.ac.nz`.

A lesson worth carrying: a WAF is not evidence of a broken asset, and an audit that fires
once per URL will manufacture findings out of transient blocks. Where an agent's field
observation contradicts an automated audit, re-probe before believing either.

---

## Rule 6 — white-on-transparent wordmarks (14 errors, 8 warnings)

These render as **nothing at all on a light card**, so shipping one replaces a missing
image with a broken one — the exact outcome rule 6 forbids.

| host | near-white fills | bytes | note |
|---|---|---|---|
| `cvut.cz` | 36/36 (100%) | 18,231 | fully white |
| `utoronto.ca` | 81/81 (100%) | 119,511 | fully white — the `www.utoronto.ca` bootstrap logo |
| `uct.ac.za` | 96/97 (99%) | 30,430 | effectively fully white |
| `admissions.msu.edu` | 101/126 (80%) | 104,404 | |
| `dzs.cz` | 3/4 (75%) | 13,028 | |
| `www2.daad.de` | 2/3 (67%) | 2,006 | |
| `flinders.edu.au` | 7/11 (64%) | 8,047 | |
| `daad.de` | 2/4 (50%) | 34,715 | |
| `ku.dk` | 1/2 (50%) | 40,836 | |
| `studies.ku.dk` | 1/2 (50%) | 40,617 | |
| `jku.at` | 1/1 (100%) | 10,214 | single white fill |
| `liu.se` | 1/1 (100%) | 2,982 | single white fill |
| `education.ki.se` | 1/1 (100%) | 94,007 | single white fill |
| `jeffersonscholars.org` | 1/1 (100%) | 14,803 | single white fill |

The 100%-white cases with one fill (`jku.at`, `liu.se`, `education.ki.se`,
`jeffersonscholars.org`) are worth checking manually — a single near-white fill on a
10–94 KB file is more likely a background plate or a highlight than the whole wordmark,
which would be a false positive in this heuristic.

**Verified safe replacement exists for `utoronto.ca`:** the separate `future.utoronto.ca`
entry (`logo-svg.svg`, 143,192 bytes) has **zero** `fill` attributes, so it renders black and
is light-card safe. It was independently probed by two researchers. Recommend replacing the
`utoronto.ca` value rather than adding a second key.

## Rule 7 — serves HTML, not image bytes (10 errors)

These would render as a broken image because the URL returns a WAF interstitial or error
page on every attempt. Confirmed across three sequential probes each:

`lse.ac.uk` · `ut.ee` · `taltech.ee` · `monash.edu` · `unibs.it` · `aauw.org` · `jwu.edu` ·
`unesco.org` · `en.unito.it` · `otago.ac.nz`

Note `jwu.edu`'s stored URL is
`jwu-logo-acronym-crest-**white**.svg` — white is in the filename, so even if the WAF is
worked around this looks like a rule-6 violation too. Check it when replacing.

## Rule 3 — `official_host: true` but the institution does not serve the bytes (19 errors)

The most serious category, because it misstates provenance rather than merely rendering badly.
Served by a CDN or an unrelated host while claiming to be official:

- CDN-hosted: `scholarships.unimelb.edu.au` → `d2h9b02ioca40d.cloudfront.net`,
  `unimelb.edu.au` → `d2glwx35mhbfwf.cloudfront.net`,
  `study.anu.edu.au` → `d1blp3aor2iuhp.cloudfront.net`,
  `admissions.msu.edu` → `edge.sitecorecloud.io`,
  `youarewelcomehereusa.org` and `nokiafoundation.com` → `images.squarespace-cdn.com`,
  `momentummsca.mta.hu` → `static.wixstatic.com`,
  `international.kiit.ac.in` → `static.npfs.co`,
  `rotary.org` → `rotary.webdamdb.com`,
  `scholarships.uq.edu.au` → `static.uq.net.au`
- Different institution: `research.google` → `www.gstatic.com`,
  `cern.ch` → `careers.cern`, `ku.leuven.be` → `stijl.kuleuven.be`,
  `eu.nl` → `netherlands.representation.ec.europa.eu`,
  `ktu.lt` → `ktu.edu`, `vgtu.lt` → `vilniustech.lt`,
  `trudeaufoundation.ca` → `www.fondationtrudeau.ca`,
  `clinical-linguistics.eu` → `emcl.eu`,
  `stipendiumhungaricum.hu` → `studyinhungary.hu`

Some of these are legitimate — a university may serve its own asset from a CDN it controls —
but rule 3 requires the flag to reflect who actually serves the bytes, so each needs a
decision rather than a blanket pass.

## Rule 5 — not https, or unreachable (6)

Not https: `moe.gov.cn`, `unizg.hr`, `icar.gov.in` (all `http://`).

Unreachable on all three attempts — **treat these as unverified, not confirmed dead**:

| host | result |
|---|---|
| `ceu.edu` | fetch failed |
| `phikappaphi.org` | timed out |
| `latrobe.edu.au` | timed out |

`lse.ac.uk` moved to rule 7 after retrying: it returns an HTML page, not a 404.

---

## Recommended order of work

1. **Delete or replace the 14 rule-6 entries.** They are actively harmful: a known-invisible
   logo is worse than the placeholder the frontend already renders.
2. **Remove the 10 rule-7 entries.** They store HTML as an image URL.
3. **Fix `utoronto.ca`** using the already-verified `future.utoronto.ca` asset.
4. **Resolve the 19 rule-3 flags** — set `official_host: false` where a third party serves the
   bytes, and record why in `host_evidence`.
5. **Extend rule 4 coverage** — 27 entries are not `validation_result: verified`.

## A caveat on this audit's own limits

- The white-wordmark test reads `fill` attributes in SVG source. It cannot see a wordmark that
  is white via CSS, `currentColor`, or an embedded raster, and it may misread a large white
  background plate as a white wordmark. Treat rule-6 output as "inspect these 14", not
  "delete these 14".
- The four 100%-white single-fill entries (`jku.at`, `liu.se`, `education.ki.se`,
  `jeffersonscholars.org`) are the most likely false positives: one near-white fill on a
  10–94 KB file is more plausibly a background plate than an entire wordmark.
- **Live probing is unreliable against WAF-fronted hosts.** The first version of this audit
  fired on a false positive precisely because it probed each URL once, eight concurrently.
  It now retries three times, but a host can still block a datacenter IP while serving real
  browsers perfectly. Every live finding should be confirmed from a browser before you delete
  a working logo.
- The audit is read-only. It deliberately writes nothing back to
  `backend/config/official_logo_overrides.json`, because logo provenance is a human-audited
  surface and the file's rule 4 says an override is "a candidate, not an approval".