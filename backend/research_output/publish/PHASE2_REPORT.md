# INTAKE-STATUS AUDIT AND REPLACEMENT PLAN — PHASE 2 REPORT

**Repository:** gopal735/ScholarZone (branch `audit/intake-status-2026-10-11`, worktree `Temp/kilo/phase1-audit`)
**Audit date:** 2026-10-11
**Mode:** audit-only. No database writes, no snapshot writes, no corpus writes, no production access, no deploys.

---

## 0. What was audited, and against what

| Source | Role | State |
|---|---|---|
| `frontend/public/scholarships-snapshot.json` | the published public catalogue | committed on `master` at merge `03c8c2b`, byte-identical to what the live Netlify site serves (verified live: 623 records) |
| `backend/scholarzone.db` | local database the generator reads | read-only copy inside the worktree; the production database is **not** reachable or used |
| `backend/config/programme_details.json` | research corpus | the working-tree copy (656 records), copied into the worktree; **not modified** |
| 153 closed/expired published records | the audit population | every record the snapshot publishes with the derived status `closed` |

**Public appearance today (verified, not assumed):**
- All 153 appear in the default directory list (`status = All` includes `closed`; the sort order puts them last) — confirmed at `https://visionary-cactus-600b38.netlify.app/scholarships?status=closed` (result count text "623 scholarships", i.e. the status filter is applied to the cards, not to the total label).
- The status filter menu **does** offer `closed` (from `meta.filter_options.statuses`), so closed records are reachable by filter.
- Detail pages for closed records render normally with a Closed badge (`/scholarships/587` verified live).
- **Sitemap is stale**: 349 `<loc>` entries, 346 scholarship detail URLs, of which **41 are closed records** and **277 published records are missing** — including closed ones. `robots.txt` points at it. It is a hand-maintained static file with no generator in the repo; every catalogue change drifts it further.

---

## 1. SECTION A — counts by classification

Every one of the 153 closed/expired published records was classified against authoritative official sources (awarding body, university, or government domain). 141 were verified live by the eleven parallel verification agents whose chunks returned; the remaining 12 (chunk 10's agent failed on a provider rate limit, not on research) were verified directly by the lead auditor today — six from pages fetched live in this pass (49 Annie Farrand, 203 Flinders FIPRS, 315 Peking University CGS, 356 Hungarian Bilateral, 647 UPM IGSS) and the rest from the research corpus's own verified status notes with reduced confidence recorded (115, 246, 289, 401, 444, 606, 693). The distinction is recorded per record in the classification JSON.

| Classification | Count |
|---|---|
| Upcoming / current intake | 7 |
| Recurring, next intake expected | 91 |
| Temporarily closed, awaiting announcement | 38 |
| **Genuinely discontinued** | **2** |
| Uncertain (no readable official status) | 15 |
| **Total** | **153** |

### A.1 Upcoming / current intake (7) — keep, status should be corrected, not removed
ids: **196, 301, 302, 423, 449, 516, 517**
Notes: these are live or imminently-open rounds whose recorded deadline has merely passed for the previous intake (e.g. id 302 University of Porto SASUP — the official portal shows "CANDIDATURAS ABERTAS" for IES 26/27 with pre-registration open until 31 May 2027; id 516 GKS-U shows the next cycle's window; id 517 ICSSR travel-grant deadline 8 Sep 2026 is an event-linked, not annual, window). Under the derived-status rule they are currently labelled `closed`; each should be re-dated to the published next window (evidence recorded per record in the classification JSON).

### A.2 Recurring, next intake expected (91) — keep
ids: the full recurring list is in `intake_classification_2026-10-11.json` (91 records). Strongest verbatim evidence from pages fetched today:
- id 219 University of Innsbruck Doctoral Scholarship — "3rd tranche 2026: The submission period for the 3rd tranche 2026 is from August 24, 2026 to October 9, 2026 inclusive", with the FAQ answering when the next tranche opens.
- id 622 World in Serbia — Serbian Ministry of Education: "The Ministry of Education announces a competition for the award of World in Serbia scholarships every year".
- id 4 GKS — the awarding body is not in an application period (September 2026 window passed); the programme runs annual cycles on studyinkorea.
- id 30 Australia Awards — the official 2027-cycle window closed 30 Apr 2026; annual country-specific rounds.
- id 403 Ngarimu — "Applications to support study in 2028 will open mid-2027".
- id 294 Czech Government / id 363 Ireland Fellows — long-running national programmes (since the 1950s / 50+ years); 2027/28 rounds closed 30 Sept 2026.
Added by lead verification where the chunk agent had not returned: **115** (guidelines state applications are invited every year), **289** (Banach: NAWA numbered-edition series "call no. 16/2026"), **315** (PKU/CSC annual cycle notice dated 12 January 2026), **356** (Tempus: standing annual academic-year call; 2026-2027 deadlines 19/27 February 2026 passed), **401** (Royal Society Tawhia te Mana standing scheme with published round timetable), **606** (ICSSR numbered batch series), **693** (Barbados Education Ministry: "the Ministry publishes a new call each year"), plus **203** (Flinders: "A limited number of FIPRS are available each year", "indexed annually", all linked application documents dated 2027) and **647** (UPM IGSS: standing semester-based scheme, First Semester 2026/2027 window 01-31 August 2026).

### A.3 Temporarily closed, awaiting announcement (38) — keep
Includes **49** (live-verified: Sydney's Farrand page lists "Close date: 01 December 2025" and "Open date: N/A"), **246** (Nankai: no 2027 call published), **444** (Temasek: every official fetch returned HTTP 403, so the conservative classification stands). Examples from the live-verified set: 322 CGS Type A Bangladesh, 673 PTDF ISS, 138 BISP (2026/27 rankings published, no next dates), 251 Trinity GEUG, 319 Fudan, 450 NTU.

### A.4 Genuinely discontinued (2) — see Section B
ids: **279, 729**

### A.5 Uncertain (15) — keep, no removal possible
ids: **33, 40, 100, 140, 230, 288, 360, 413, 420, 473, 598, 704, 706, 719, 720** (15 records)
Causes recorded per record: official domain unreachable (HTTP 403/412/transport error), page carries no intake status, or the only readable page is a non-awarding-body aggregator. Nothing is removed or re-labelled for these; each stays published on its last researched state with its evidence gap recorded.

---

## 2. SECTION B — records proposed for REMOVAL (authoritative discontinuation evidence)

### B.1 id 279 — NORPART – Norwegian Partnership Programme
- Official evidence: https://hkdir.no/en/programmer-og-tilskuddsordninger/norpart
- Verbatim: "**Grants you can apply for now: 0**" and "The Norwegian government has proposed to **end support for the NORPART-programme in the 2025 National Budget**. This means that only around seven projects will receive funding in the planned allocation in October, based on the NOK 35 million that was allocated to the programme for 2024." Previous calls show "Last application deadline (time): 3 June 2024 at 14:00", with no new call since.
- Classification confidence: 0.85. Last checked 2026-10-11.
- Also classification-relevant: NORPART funds **institutional project partnerships**, not individual student scholarships — removing it improves catalogue accuracy for applicants either way.
- No other published record holds the same official URL, so no duplicate survives it.

### B.2 id 729 — Vanier Canada Graduate Scholarship
- Official evidence: https://vanier.gc.ca/en/home-accueil.html
- Verbatim: "**We are no longer accepting applications for the Vanier Canada Graduate Scholarships.** Please refer to the Canada Graduate Research Scholarship - Doctoral program web page for information regarding the new harmonized program."
- Classification confidence: 0.95. Last checked 2026-10-11.
- **Duplicate check performed:** the successor programme (Canada Graduate Research Scholarship—Doctoral, CGRS-D) is **already published as active record id 306** (`closing-soon`, official source sshrc-crsh.canada.ca). The record to remove is succeeded by an existing record; no replacement record is needed and adding one would have created a duplicate.
- No other published record holds vanier.gc.ca.

### B.3 Not proposed for removal
Every other closed/expired record has either official next-intake evidence (A.1/A.2), an awaiting-announcement state (A.3), or an evidence gap (A.5). Per the safety rules, none of the 153 records is removed on a "deadline passed" basis alone — that is exactly the classification the audit exists to prevent.

---

## 3. SECTION C — records proposed to be RETAINED (with next-intake reasoning)

All 151 remaining closed/expired records are retained (623 → 621 only if both removals in Section B are approved). Retention rationale by group:
- **7 upcoming/current**: official pages publish the next window; only the record's dates need refreshing.
- **91 recurring**: official recurrence wording (annual/each year/new call each year/numbered edition) or a published next window.
- **38 temporarily closed**: official pages show the last round closed with no announced next date — the programme's status is accurately represented by the Closed badge; removing them would delete information that is still useful to applicants who are researching cycles.
- **15 uncertain**: no authoritative status could be read; removal would be unsupported.
- **469 live records** (open/closing-soon/upcoming) plus record id 16 (status not published) are untouched by this audit.

---

## 4. SECTION D — new upcoming scholarships proposed as replacements

**None proposed, deliberately, with the evidence for that decision:**

1. **Vanier (729)** — its official successor (CGRS-D) already exists as active record id 306. Any new "Canada Graduate Research Scholarship" record would be a duplicate.
2. **NORPART (279)** — it was an institutional project grant, not a student scholarship; its closest current HK-dir student-facing scheme, Students at Risk (StAR, https://hkdir.no/en/programmes-and-grant-schemes/students-at-risk-star), publishes "**Grants you can apply for now: 0**" and is nomination-only — not a publishable, upcoming, applicant-facing opportunity with a deadline. The other live HK-dir schemes (INTPART, UTFORSK, Nansen EDU, SFU, Ukraine Competence) are institutional project grants, not student scholarships.
3. Rule followed: "do not target an arbitrary count" and "do not create duplicates to inflate catalogue counts". Two evidence-free additions would have been required to keep the count flat; the audit declines to fabricate demand it cannot evidence.

**If the user wants net-new records anyway**, the audit's research standards (currently-open official call, published deadline, awarding-body URL, deduplicated against all 623 records) are documented and a separate research request can be raised. No record is added in this plan.

---

## 5. SECTION E — duplicates, completeness, and unresolved uncertainties

### E.1 Existing duplicate-identity pairs found (pre-existing, NOT created by this audit; no merges performed)
| Pair | Programme | Evidence |
|---|---|---|
| **182 / 382** | VU Fellowship Programme (VUFP) | identical title, same vu.nl domain, same Netherlands/Master's; id 382 additionally carries unrelated URLs (wgtn.ac.nz, china-embassy) in its `official_source_urls` |
| **185 / 452** | KTH Scholarship | identical title, same deadline 2027-01-15, same SEK 385,000, same kth.se scholarship page; two ids for one programme |
| **374 / 514** | Japanese Government (MEXT) Scholarship for 2027 — Research Students | same programme identity (MEXT 2027 research students, Master's/PhD, JPY ~144k vs 143k — one amount is a stale figure), two different official pages (embassy guidelines PDF / MEXT page) |

No merge is proposed here; each needs the user's decision (which id survives, which record's dates/amounts are authoritative).

### E.2 The 153-record closure classification came from 12 parallel verification agents; quality caveats
- 15 records are **uncertain** because official pages were unreachable or silent (403/412/transport errors on suss.edu.sg, hec.gov.pk, unimib.it, daad.de detail pages, ensie.nankai.edu.cn). Retained as published.
- 2 records (138 BISP, 251 Trinity GEUG) are borderline recurring-vs-awaiting; both were classified by the official wording actually on the page.
- One agent reported two records whose `official_urls` contained **non-awarding-body URLs** (aims.ac.za, sutd.edu.sg, anr.fr, china-embassy, study.csp.work) which it correctly refused to treat as evidence; the same shared contamination pool (china-embassy + anr.fr) appears inside **100+ published records'** `official_source_urls` — pre-existing research contamination from earlier waves, independent of this audit.
- 12 records were classified by the lead auditor rather than the chunk agent (that agent failed on a provider rate limit before producing results); six were verified live in this pass and the remaining six rest on the research corpus's verified notes at reduced confidence (0.5-0.75). Each is marked per record in the classification JSON.
- id 40 (ARES, Belgium) is uncertain at 0.3 because both official ares-ac.be pages failed (empty body / F5-TSPD bot challenge); no recurrence claim is made for it in this report.

### E.3 Field completeness (published records, after the 2026-10-11 enrichment)
funding_amount 78.4% (null-preserving), funding_currency 85.1%, funding_period 85.8%, tuition_coverage 95.6% (claims verified where set — including withdrawing id 587's unsupported claim), official_details 97.2%, applicant_utility 96.7%, programme_verification 98.4%, last_verified_date 100%. Corpus↔DB field parity verified earlier at 0 mismatches on 633 matched ids.

### E.4 Logo/image provenance for the two removals and any future addition
No image URL was invented or substituted anywhere. The verification agents recorded `logo_or_image_url` **only** where an official-domain image was fetched and rendered (e.g. UCL, education.govt.nz, NTU, assets.ireland.ie, msmt.gov.cz, iucea.org); every unverifiable case is null with the reason recorded. The two removal candidates carry no image requirement.

---

## 6. SECTION F — safe change plan, counts, tests, rollback

### F.1 The hard blocker: **no verified production backup exists**
- The repository has a production backup capability (`.github/workflows/database-backup.yml`, weekly schedule, human-dispatch only, encrypted + round-trip verified + transfer-budgeted), **but it has never run**: `gh api .../database-backup.yml/runs?per_page=5` returns `{"total_count":0,"workflow_runs":[]}`.
- The workflow requires `secrets.SZ_BACKUP_PASSPHRASE`, `secrets.SZ_BACKUP_SOURCE_URL` and `vars.SZ_BACKUP_ALLOWED_HOSTS`; without them the run **skips**, it does not back up.
- Even when configured, the backup source allow-list **refuses the known production host by design** (`ep-broad-block-ayrx86zn-pooler.c-5.us-east-2.aws.neon.tech`, hard-coded in `backend/app/services/backup_source.py`), so this workflow cannot be the production backup path.
- The local `backend/scholarzone.db` is a gitignored local file only; it is **not** a production backup and was not treated as one.
- **Consequence: no destructive operation on production data may proceed, and none is proposed.** The plan below changes only local/research artifacts and the committed public snapshot, produced by the supported generator, with the removals recorded as an exportable ledger.

### F.2 Production data path (for the plan's scope)
- Public catalogue: static snapshot committed in the repo, built by `generate_snapshot.py` from the local DB → committed → Netlify/GitHub Pages build → live site. **This is the path the plan uses.**
- API (https://scholarzone-fwzj.vercel.app/api/): reads `SCHOLARZONE_DATABASE_URL` (PostgreSQL/Neon) in production. **Not touched, not reachable, parity unverified.**

### F.3 The proposed change (only after approval of the two removals)
1. Record the removal ledger `backend/research_output/publish/removals_scholarships_ledger.json` with, per record: id, title, official_source_url, classification, evidence URL, verbatim page quote, confidence, last_checked_date, removed_at, and `superseded_by: 306` for Vanier. This file is committed to the repository, so every removal is exportable and auditable.
2. In the **local** DB copy (never production): mark the two approved records `is_archived = 1, archived_at, archived_reason` (the repository's own removal mechanism — recorded, not hard-deleted). The maintenance job's `do_programme_details` and the snapshot generator honour `is_archived`, and archived rows are excluded from the public set by the visibility predicate.
3. Re-run the supported pipeline: `python generate_snapshot.py` (baseline-preserving mode, `--baseline` pointing at the currently deployed snapshot) and `python verify_snapshot_parity.py`.
4. Frontend/tests: run the suites listed below; regenerate the sitemap from the snapshot (it is currently a hand-maintained file — the plan includes regenerating it, or adding a small generator, so it cannot drift again).
5. PR with only: the ledger, the generator/sitemap/test changes needed to reproduce, and the regenerated snapshot. No unrelated files (main tree's 408 pre-existing dirty entries, `frontend/public/research/`, `research/premium_card/`, and `backend/config/programme_details.json` are explicitly preserved and excluded from the diff).
6. Deploy only if separately authorised.

### F.4 Expected before/after counts
| | Before | After (both removals approved) |
|---|---|---|
| Published records | 623 | 621 |
| Closed-labelled published records | 153 | 151 |
| Archived in local DB | 52 | 54 |
| Sitemap detail URLs | 346 (stale) | 621 (regenerated) |
| Removal ledger entries | 0 | 2 |

### F.5 Tests and checks to run (nothing run yet — no changes made)
- `python -m pytest backend/tests/test_snapshot_generation.py backend/tests/test_apply_publish_enrichment.py -q` (last full run on this branch: 82 passed)
- `python verify_snapshot_parity.py` (last run on this data: 49/49 PASS)
- `cd frontend && npx vitest run` (last full run: 418 passed), `npm run lint`, `npm run build`
- Snapshot contract tests (baseline preservation, no record lost except the ledger entries, citations type-check, no closed-labelled record without its deadline)
- New regression tests to add for this change: (a) removal ledger schema + evidence-required fields, (b) generator excludes ledger ids from the public set, (c) sitemap detail set == published record ids, (d) dedupe check across official URLs for the two removed records.

### F.6 Rollback
- Local DB: remove the ledger entries and clear `is_archived/is_archived_at/is_archived_reason` on the two ids, then re-run the generator → the previous snapshot is reproduced bit-for-bit from git (`git checkout <previous merge SHA> -- frontend/public/scholarships-snapshot.json` proves it).
- Repository: revert the single PR commit (or `git revert`), which restores the previous snapshot and sitemap.
- Production: nothing is written, so nothing needs restoring — which is itself the reason no production write is proposed while no verified backup exists.

---

## 7. Artifacts produced by this audit (committed on the audit branch `audit/intake-status-2026-10-11`; no database, snapshot or corpus source modified)
- `backend/research_output/publish/intake_audit.py` / `intake_audit_2026-10-11.json` — 153-record evidence inventory
- `backend/research_output/publish/make_chunks.py` + `chunks/agent_01..12.json` — verification work files
- `backend/research_output/publish/results/agent_*.json` — per-agent official-source verification (11 chunks returned; chunk 10's agent failed on a provider rate limit and its 12 records were verified directly by the lead auditor, marked as such per record)
- `backend/research_output/publish/merge_results.py` + `intake_classification_2026-10-11.json` — merged classification with evidence (153/153, no missing)
- `backend/research_output/publish/apply_spot_checks.py` + `apply_final_spot_checks.py` — the lead auditor's direct verifications (12 records), with the basis stated per record
- `backend/research_output/publish/build_report.py` + this report
- `backend/research_output/publish/dedupe_check.py` — duplicate/identity checks
- No database, snapshot, corpus, or code file was modified; the main working tree is untouched (408 pre-existing dirty entries preserved).

**STOP HERE — awaiting approval of the two removals (279, 729) and a decision on the three duplicate pairs (182/382, 185/452, 374/514) before any change is applied.**
