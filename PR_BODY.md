# Catalogue accuracy: discontinued removals, one HKPFS addition, duplicate/integrity resolutions

Base: `origin/master` (03c8c2b — the only branch whose committed snapshot matches the deployed catalogue: 623 records). Head: this branch.

**Net public change: 623 → 618 (−5, +1).** The published set is regenerated through the repository's supported generator (`generate_snapshot.py`, baseline-preserving mode) with parity verified (49/49 checks at every step); the sitemap is now derived from the same id set rather than hand-maintained.

## Removals (evidence re-fetched live before implementation)
| id | record | official evidence (re-fetched 2026-10-11) |
|---|---|---|
| 279 | NORPART | hkdir.no: "Grants you can apply for now: 0"; "The Norwegian government has proposed to end support for the NORPART-programme in the 2025 National Budget." |
| 729 | Vanier CGS | vanier.gc.ca: "We are no longer accepting applications for the Vanier Canada Graduate Scholarships… new harmonized program." Successor already published as active id 306. |
| 182 | VUFP (merged into 382) | vu.nl's VUFP page live: "Deadline VUFP application: 1 February 2027 (23:59 CET)"; 182's page 404s |
| 185 | KTH Scholarship (merged into 452) | kth.se live: "1 December 2026: Application opens / 15 January 2027: Application closes"; 185's page 404s |
| 374 | MEXT 2027 Research Students (merged into 514) | mext.go.jp live announcement hub; 374's guidelines PDF URL carried onto the canonical record |
| 565 | ESKAS (merged into 727) | both cite the official SBFI/SERI page, today titled "Swiss Government Excellence Scholarships 2027 – 2028": "Applications are open starting August 20, 2026" |

All six are archived with evidence-carrying reasons and per-record ledgers (`removals_scholarships_ledger.json`, `dedupe_merges_ledger.json`, `open_items_ledger.json`) — no hard deletes, every action reversible. The other 152 closed-labelled records remain published as programme records with closed intake status; a passed deadline alone never removes a record.

## Addition (official-source verified, gate-admitted)
- **id 730 Hong Kong PhD Fellowship Scheme (HKPFS) 2027/28** — RGC/UGC. Live evidence: "Open for applications: 1 September 2026 at 12:00 noon Hong Kong Time"; Initial Application deadline 1 December 2026; "up to two programmes / departments at one or two universities… under HKPFS 2027/28"; stipend "HK$344,400 (approximately US$44,150)" + "HK$14,400" travel allowance per year up to three years; "400 PhD Fellowships will be awarded in the 2027/28 academic year". Logo left unset with the reason recorded: the official site publishes no administering-body crest, so no unrelated crest is passed off as the scheme's logo.
- Eiffel re-checked (official Campus France page still publishes only the closed 2026 campaign; no 2027 dates) — **not** added, no invented dates. HKPFS is the one verified addition this pass; the insertion gate refuses any candidate without a live official page, evidence quotes, a dedupe statement and a real open window.

## Data integrity
- **MEXT stipend** resolved as course-dependent (not a typo): official 2027 guidelines PDF — 143,000 yen/month (preparatory/non-regular), 144,000 (master's/professional), 145,000 (doctoral) + 2,000–3,000 regional allowance. `funding_amount` nulled (a single number would misrepresent), official wording in `funding`.
- **SUSS 449**: live page still HTTP 403; the legitimate archived official page is attached as provenance; unverifiable fields untouched.
- **Four deadline corrections** (196, 301, 302, 423, 516, 517) with verbatim official quotes, including clearing the fabricated "19 February 2026" Erasmus+ deadline the official page refutes ("There's no central application form…").
- **484 pasted cross-programme URLs removed** from 131 records (one earlier research wave pasted SUTD/ANR/embassy URLs across unrelated programmes); owning records keep their own pages; per-record ledger. All 618 records still carry a primary official URL.

## Invariants under test
New tests (`test_removal_ledger.py`, `test_sitemap_generation.py`) plus an updated snapshot-contract test that lets only ledger-declared records leave the public set: "no silent shrinkage" now allows removals only when `meta.baseline.baseline_removed` accounts for them.

## Validation
- backend: 6524 passed; the only failures (3 "no ambient database" isolation tests + 1 script needing a running server) are proven environmental — they pass with the gitignored local sqlite copy moved aside, and this branch's changes never touch those paths.
- frontend: 418/418 vitest, lint clean, build OK.
- sitemap detail set == published id set; 0 open-labelled records with a past deadline; every changed record's official source re-fetched HTTP 200.

Not included: production database writes/sync — no verified restorable production backup exists (the `database-backup.yml` workflow has never run and its allow-list variable is unset), and rows stay archived rather than deleted until a backup is proven.
