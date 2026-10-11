# PHASE 3 REPORT — ADDENDUM (autonomous pass of 2026-10-12)

This addendum records what the autonomous pass added and resolved on top of
the Phase 3 report above, and the verified delivery.

## Delivery

| | |
|---|---|
| PR | https://github.com/gopal735/ScholarZone/pull/38 — **MERGED** (merge commit `f14248f`, 2026-10-11T19:28:09Z) |
| Branch | `phase3/catalogue-accuracy-2026-10-11`, 8 commits over base `03c8c2b` |
| CI | all checks green (`backend-tests` pass 9m33s, `frontend-tests`, `frontend-lint`, `build-and-smoke`, `git-integrity`, `env-config`, `schema-compat`, `import-smoke`, `preflight`, Vercel, Netlify redirect rules) |
| Production frontend | **https://schollarzone.netlify.app** (Netlify project `schollarzone`) — the URL in the task brief, `visionary-cactus-600b38.netlify.app`, 404s on every path and is a decommissioned site; the S+S hint found in the repository's deploy checks identified the live one |
| The Vercel mirror `scholarzone-fwzj.vercel.app` also serves the frontend and the same snapshot |

**Live verification (observed, not expected):**
- live `/scholarships-snapshot.json`: **618 records** (was 623 before this change), same ids as the generated snapshot, 0 records differing, meta identical to the generated artifact (`generated_at 2026-10-11T18:56:17.625268Z`) — the deployed artifact is the generated artifact (static-snapshot architecture; the only difference is CRLF line-endings in the Windows working copy).
- status distribution live: open 312, closed 147, upcoming 107, closing-soon 51, null 1.
- the 6 removed/archived ids (279, 729, 182, 185, 374, 565) are absent from the live snapshot and from `/sitemap.xml` (621 locs: 3 static + 618 detail, detail set == live id set).
- live detail page `/scholarships/730` renders the new record (Open / Verified listing / Verified active badges, Hong Kong · Asia · PhD, provider, eligibility, step-by-step application), console 0 errors.
- 0 published records labelled open with a past deadline.

## Resolution of the previously-unresolved items

1. **ESKAS 565/727 — same programme, merged.** Both cited the official SBFI/SERI page, fetched live 2026-10-12 and titled "Swiss Government Excellence Scholarships 2027 – 2028": "Applications are open starting August 20, 2026", research scholarships "max. age: 35 / funding: CHF 2450.--/month", decisions "by the end of May at the latest". Canonical 727 (its degree text matches the official restriction: research scholarships and an initial artistic Master's only); 565 archived. Ledger: `open_items_ledger.json`.
2. **MEXT stipend — resolved as course-dependent, not a typo.** Official 2027 English guidelines PDF (extracted with pypdf): "143,000 yen per month" preparatory/non-regular, "144,000 yen per month" master's/professional, "145,000 yen per month" doctoral, plus "a supplemental regional allowance of 2,000 yen or 3,000 yen per month". `funding_amount` set to null (a single number misrepresents a category-dependent stipend), currency JPY retained, official wording in `funding`/`funding_period`.
3. **SUSS 449 — live page still HTTP 403.** The legitimate Wayback Machine snapshot of the official page is attached as supplementary provenance (eligibility, tenure up to four years, merit nomination at admissions interview, quoted in the ledger). The unverifiable 31 August 2026 deadline is left exactly as it was; no value was invented.
4. **Eiffel — not added.** The official Campus France page (redirect target verified) still publishes only the 2026 campaign: "Deadline for the reception of applications by Campus France: January 8, 2026 included" — passed, and no 2027 dates are announced. No future intake was invented.
5. **HKPFS — added as id 730.** The RGC/UGC official site (cerg1.ugc.edu.hk/hkpfs) is live for the 2027/28 round: "Open for applications: 1 September 2026 at 12:00 noon Hong Kong Time", Initial Application deadline "1 December 2026 at Hong Kong Time", university deadlines "1 December 2026 (11:59pm Hong Kong Time)", "400 PhD Fellowships will be awarded in the 2027/28 academic year", stipend "HK$344,400 (approximately US$44,150)" + "HK$14,400" travel allowance per year up to three years (2026/27 figures), open to "new full time PhD students in the following eight universities, irrespective of their country of origin". Logo deliberately unset: the official site publishes no administering-body crest, and the participating universities' crests hosted there are not the scheme's own logo.
6. **Phase 3 merges re-verified.** 382 (VUFP), 452 (KTH) and 514 (MEXT) canonical records all re-resolve HTTP 200; their corrected fields trace to the official pages quoted in the ledgers; merged-away rows (182, 185, 374) remain archived with reversal instructions.

## Research avenues that did not yield additions (and why)

- web search quota was exhausted for the whole session (Exa 402), so research ran on direct official URLs only.
- Commonwealth (CSC UK) pages are JS-rendered; the /funding paths 404 and no current window could be verified — not added.
- Australia Awards (dfat.gov.au) connection-reset/timeout on every attempt — not added.
- Stipendium Hungaricum banner says "Application is On for the 2026/27" while its recorded window closed 2026-01-15; the call page does not disambiguate — not added, the stale banner is reported rather than followed.
- HKPFS was previously "not added" for 404 because the working URL (`/hkpfs/index.html`, not `/hkpfsc/`) had not been tried; it is the one verified addition of this pass.
- Catalogue coverage was deduplicated first: JJ/WBGSP (475/564), ADB-JSP (656), Türkiye (568/621/692), Belgium (40/280/282/508/571/629), SH (285), JSPS (377/378/379/551/552) and the Dutch/German/Swedish scholarship families are already present with current dates; the insertion gate refused the only other verified candidate (Eiffel: "deadline is in the past").

## Production database gate (unchanged, and the only remaining blocker)

- `database-backup.yml` has **never run** (`gh api .../database-backup.yml/runs` → total_count 0).
- `vars.SZ_BACKUP_ALLOWED_HOSTS` is **not set** (the only repo variable is `SCHOLARZONE_API_URL`), so the workflow would stop with missing configuration rather than produce a backup; it also refuses known production endpoints by design.
- No destructive production operation was performed and none may be, because no verified restorable production backup exists. **What clears the gate**: (1) an actually-executed backup job with the allow-list correctly configured, producing a real dump artifact; (2) integrity verification of that artifact; (3) restoration proven on a non-production database with comparable schema and expected data; (4) explicit authorization for the run. Until then, all removals/merges are archive-flag operations in the repository's own database path, reversible from the ledgers.

## Safety

- Main working tree untouched throughout: 408 dirty entries before and after, corpus hash `312883c96141dc3b…` unchanged, `frontend/public/research/` preserved, no snapshot file created there.
- No secrets printed; no provider configuration changed; no paid services; no production writes.
