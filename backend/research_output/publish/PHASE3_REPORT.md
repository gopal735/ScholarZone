# PHASE 3 REPORT — catalogue accuracy: discontinued removals, dedupe merges, deadline corrections

Task: exclude genuinely discontinued opportunities, correct duplicate/incorrect data, research genuine additions — non-production only.
Branch: `phase3/catalogue-accuracy-2026-10-11`
Worktree: `C:/Users/GopaL/AppData/Local/Temp/kilo/phase1-audit` (main working tree untouched throughout)
Date of work: 2026-10-11 to 2026-10-12 (UTC)

## 0. Exact SHAs

| | SHA |
|---|---|
| Branch point (correct current base: `origin/master` = the deployed live site) | `03c8c2b` |
| Audit commit (carried into this branch) | `52d5aa8` |
| Commit 1 — discontinued removals + derived sitemap | `f74af10` |
| Commit 2 — URL contamination cleanup + sitemap/ledger tests | `a9bdaac` |
| Commit 3 — duplicate pair merges (D) | `65da8e4` |
| Commit 4 — deadline corrections (C, first batch) | `b75d813` |
| Commit 5 — deadline corrections (C, batch 2) + report | `28140aa` |
| Final PR head | see §12 |

Base choice: `origin/master` is the only branch whose committed `frontend/public/scholarships-snapshot.json` matches the live deployment (623 records, byte-identical — verified in Phase 1/2). The local checkout on `fix/public-catalogue-non-closed-visibility` (`9a6805c`) is an ancestor of master and does not carry the snapshot, and `master`'s older tip `de0e31c` has public-count regressions, so either would have silently dropped legitimate records on regeneration; both were rejected.

## 1. HEAD counts, before → after

| Measure | Before | After | Δ |
|---|---|---|---|
| Published records in snapshot | 623 (live site) | 618 | −5 |
| Archived in local DB | 52 | 57 | +5 (279, 729 discontinued; 182, 185, 374 merged away) |
| Sitemap detail URLs | 346 (stale, hand-maintained) | 618 (derived) | +272 |
| Closed-labelled records retained (published) | 153 | 147 | −3 merged away, −2 discontinued, −1 corrected to an open window (302) |
| New records added | — | <TBD, section B> | <TBD> |

The 623 → 618 breakdown: −2 discontinued (279, 729) and −3 merged-away duplicate rows (182, 185, 374). Nothing else changed membership: 0 records added, 0 retained records lost, verified by the diff and by `verify_snapshot_parity.py`.

## 2. Removals (A)

Both re-fetched **live on 2026-10-11** immediately before implementation; both evidence quotes re-confirmed:

**id 279 — NORPART** — https://hkdir.no/en/programmer-og-tilskuddsordninger/norpart
- "Grants you can apply for now: 0"
- "The Norwegian government has proposed to end support for the NORPART-programme in the 2025 National Budget."
- confidence 0.85; replaced by `removals_scholarships_ledger.json`.

**id 729 — Vanier Canada Graduate Scholarships** — https://vanier.gc.ca/en/home-accueil.html
- "We are no longer accepting applications for the Vanier Canada Graduate Scholarships. Please refer to the Canada Graduate Research Scholarship - Doctoral program web page for information regarding the new harmonized program."
- confidence 0.95; successor already published as active record **id 306**, so no replacement record was invented.

Mechanism (repository's own): `archive_discontinued.py` sets `is_archived=1`, `archived_at`, `archived_reason` (evidence-carrying) on the LOCAL sqlite copy, then the supported `generate_snapshot.py` (baseline-preserving default) removes exactly those ids from the public set. **No hard deletes, no production access.** The remaining 151 closed-labelled records are untouched (verified: 148 after merges).

Ledger: `backend/research_output/publish/removals_scholarships_ledger.json` (verbatim quote, confidence, check date, superseded_by for Vanier, policy statement).

## 3. Duplicate investigation (D) — all three pairs resolved with proof

Each pair was compared record-to-record and verified against the awarding body's live page on 2026-10-11; verdicts, canonical choices, field-level reconciliation and unresolved items in `dedupe_merges_ledger.json`; merges applied by `merge_duplicate_pairs.py` (merged-away rows archived, never deleted; merges reversible from the DB).

**182 / 382 — VU Fellowship Programme (VUFP)** — verdict: same programme, same intake.
- Canonical: **382** (its page is live: "Our own VU Fellowship Programme (VUFP) is a merit-based tuition fee waiver… Applications are welcome from November 1st 2026… Deadline VUFP application: 1 February 2027 (23:59 CET)"); 182's own page 404s.
- Corrections on 382: deadline_date `2027-02-01`, deadline_display from the page's wording, program_type replaced the eligibility sentence with "Merit-based tuition fee waiver for non-EU/EEA students". 182 archived.

**185 / 452 — KTH Scholarship** — verdict: same programme, same intake.
- Canonical: **452** (live page: "1 December 2026: Application opens / 15 January 2027: Application closes / 1 April 2027: Scholarship results announced… covers the full tuition fee of a one or two year master's programme"); 185's own page 404s.
- Corrections on 452: deadline_display verbatim from the page, program_type replaced the pasted student testimonial ("Julian, KTH Scholarship awardee") with "Merit-based tuition fee scholarship for fee-paying international students". 185 archived.

**374 / 514 — MEXT 2027 Research Students (Embassy Recommendation)** — verdict: same programme, same intake.
- Canonical: **514** (mext.go.jp's own announcement hub: "JAPANESE GOVERNMENT (MEXT) SCHOLARSHIP FOR 2027 (RESEARCH STUDENTS)", which links the same English guidelines PDF 374 points at); 374's guidelines URL carried onto the canonical record. 374 archived.
- **Unresolved (reported, not guessed):** stipend disagrees between records (143,000 vs 144,000 JPY/month) — the deciding page is the English guidelines PDF, which does not resolve as fetchable text — and region tags disagree (Global vs Asia). Canonical record's existing values kept for the next verification pass; ledger records both.

## 4. Existing data quality (C)

**Cross-programme URL contamination removed.** One earlier research wave pasted four URLs across unrelated records (SUTD pages in 132+121, an ANR call in 118, a Chinese-embassy news item in 116; 21 distinct URLs total — e.g. the DAAD row listed a French research call and SUTD's own scholarship page beside daad.de). 484 entries removed from 131 records by `clean_url_contamination.py` with a per-record ledger; the owning records keep their own pages (SUTD 109/446/447; the ANR call records; the embassy-track CSC records 243/322/323/324, for which embassy pages are the official channel). The research corpus is NOT modified — the contamination there is reported for its owners.

**Deadline corrections from official pages (first batch):**
- **id 302 U.Porto**: official pre-registration window "14 August 2026 to 31 May 2027"; SASUP carousel "BOLSA DE ESTUDO DO IES 26/27 - CANDIDATURAS ABERTAS" (live 2026-10-12). deadline 2026-10-02 → **2027-05-31**, status open.
- **id 516 GKS Undergraduate**: studyinkorea.go.kr re-fetched 2026-10-12 — "Embassy Track: September / University Track: September - November"; the recorded 30 Sep 2026 was the Embassy Track's online deadline (passed), the University Track window is open. deadline → **2026-11-30** at month precision (page states the month range).
- Second batch (ids 196 ANU, 301 Nova SBE, 423 Erasmus+, 449 SUSS, 517 ICSSR): verdicts from official pages recorded in `research_agents/corrections_deadlines.json` with verbatim quotes; applied through the same evidence-gated path (see §B/§6).

## 5. New record research (B) — verified, honest outcome: ZERO additions

Method: eleven autonomous research agents (one per region) plus three targeted verifications, all official-source-only. The first wave of eleven stalled when the environment's web-search quota hit its limit mid-run (an infrastructure failure, not an evidence failure), so the lead re-drove the research directly with live page fetches. Three named candidates were checked thoroughly (`research_agents/lead_candidates.json`):

| Candidate | Official URL | Outcome |
|---|---|---|
| Hong Kong PhD Fellowship Scheme (HKPFS) | cerg1.ugc.edu.hk (2 known paths) | **Not added** — official page returns HTTP 404 on every known path (verified twice). No verifiable page, no addition. |
| Swiss Government Excellence Scholarships (ESKAS) | sbfi.admin.ch | **Not added — duplicate**: already published as ids 565 and 727. (Their duplication is itself reported in §9.) |
| France Excellence / Eiffel Excellence Scholarship | campusfrance.org | **Not added — no open window**: verbatim "Only applications submitted by French higher education institutions are accepted", "Call for application 2026 is open", "Deadline for the reception of applications by Campus France: January 8, 2026 included". The 2026 window closed 2026-01-08 and no 2027 dates are published, so it fails the insertion gate (no future deadline and no official open status). Recorded in `research_agents/lead_candidates.json` and `research_additions_2026-10-11.json` for the next research pass, when the 2027 campaign opens (historically October). |

Result: **0 records added. No arbitrary count, no fabricated opportunity.** The catalogue's remaining covered majors were checked first (dedupe against the 618-record snapshot + the 656-record research corpus); the genuinely uncovered ones either had no reachable official page (HKPFS) or no open/announced window (Eiffel). The insertion gate `add_research_records.py` refuses, by design, any candidate lacking: an awarding-domain `official_source_url`, evidence entries with url+verbatim quote+check date, a dedupe statement, and a future deadline or official open status. Dry run output: `accepted 0, refused 1` for the Eiffel candidate ("deadline is in the past").

## 5a. Logo provenance (B)

No record was added, so no logo was published. The gate carries the logo rule unchanged: `image_url` is only accepted for an image URL that was fetched and confirmed to be a real image on the awarding body's own domain or its official CDN; otherwise the field stays null with the reason recorded in `logo_provenance`. No image was inferred, guessed or hotlinked anywhere in this change.

## 6. Validation (F)

| Check | Result |
|---|---|
| Backend suite (pytest, worktree) | 6514 passed, 3 failed + 1 error — **all 4 pre-existing environmental failures** (assert the gitignored local `backend/scholarzone.db` is absent, and one script needing a running server). Proved by moving the DB aside: all 4 pass. Content of this change never touched those paths. |
| New regression tests | `test_removal_ledger.py`, `test_sitemap_generation.py` — 81 passed |
| Frontend vitest | 418/418 passed (contract + seo suites included) |
| Frontend lint | clean |
| Frontend build | success (`npm run build`) |
| Snapshot parity | `verify_snapshot_parity.py` — 49/49 checks, OK at every regeneration |
| Snapshot diff vs base | removed ids exactly {279, 729, 182, 185, 374}; 0 added; 0 retained records lost; per-field changes only where an official page supports them (listed in `field_corrections_ledger.json` and `dedupe_merges_ledger.json`) |
| Sitemap | detail URL set == published id set exactly; all 5 removed ids absent from snapshot and sitemap; static routes preserved |
| Snapshot contract invariant | frontend test now subtracts the snapshot's declared `baseline_removed`, so ledger-declared removals pass and undeclared vanishings fail |
| Every changed record's official source resolves | 382 (vu.nl), 452 (kth.se), 514 (mext.go.jp) — merged/corrected; 302 (up.pt + sas.up.pt), 516 (studyinkorea.go.kr), 196 (study.anu.edu.au), 301 (novasbe.unl.pt), 423 (erasmus-plus.ec.europa.eu), 517 (icssr.org) — deadline-corrected. All fetched HTTP 200 on the check dates recorded in the ledgers. |
| New published records resolve | n/a — zero records added |
| Merged-away/discontinued absent | 279, 729, 182, 185, 374 all absent from snapshot and sitemap |
| Legitimate recurring opportunities retained | all 147 remaining closed-labelled records stay published with their Closed badge (baseline-preserving mode; 0 silently dropped) |

## 7. Logo provenance

See §5a: zero records added, therefore zero logos published. No image was invented, inferred or hotlinked anywhere in this change.

## 8. Safety (E)

- No production database access at any point; no writes outside the gitignored local sqlite copy in the worktree; no backup workflow run; no deploy, no merge, no PR opened.
- Main working tree untouched (408 pre-existing dirty entries verified before and after; corpus hash `312883c96141dc3b…` unchanged; `frontend/public/research/`, `research/premium_card/` and every untracked agent file preserved in place).
- The main tree's snapshot file does not exist and was NOT created; all snapshot work happened in the worktree.

## 9. Unresolved issues

1. MEXT stipend 143,000 vs 144,000 JPY and region tag (Global vs Asia) — see §3; referred to the next verification pass (deciding page is a PDF that does not resolve as text).
2. **Swiss Government Excellence Scholarships appears twice in the catalogue** — ids 565 and 727 (same programme identity, both published, both surfaced while deduping research candidates). Not in the authorized pair list (§3), so NOT merged and NOT changed; reported for the same treatment.
3. id 449 SUSS Research Scholarship — official URL returns HTTP 403 (as in the audit); its deadline stays as-is and re-research is queued once SUSS is reachable. No value was guessed.
4. Hong Kong PhD Fellowship Scheme has no reachable official page today (404 on every known path): excluded from additions until a live page exists.
5. Eiffel 2027 call not yet announced on the official page (the 2026 window closed 2026-01-08): the verified candidate is parked in `research_agents/lead_candidates.json` for the next pass.
6. The research corpus carries the same URL contamination found in §4; it is a dirty working-tree file in the main checkout (hash preserved) and is deliberately not modified in this branch.
7. The sitemap hostname is the Netlify deploy origin, taken from the file it replaced; a custom-domain move is one deliberate line in `generate_sitemap.py`.
8. Production DB sync is **not** part of this branch and remains gated on a proven, restorable production backup (Phase 2 finding: the backup workflow has never run and refuses the production host by design).

## 10. Rollback plan

Every change is a commit on top of `03c8c2b`; nothing is merged or deployed.
1. `git revert` the five commits (or `git checkout 03c8c2b -- frontend/public/scholarships-snapshot.json frontend/public/sitemap.xml` to restore the published artifacts directly).
2. The DB-side changes are archival flags and value corrections only: to restore any removed or merged record, `UPDATE scholarships SET is_archived=0, archived_at=NULL, archived_reason=NULL WHERE id IN (279,729,182,185,374)` on the database copy, then regenerate. The records were never hard-deleted, so the ids and all fields survive.
3. Every corrected value is individually listed with from/to in `field_corrections_ledger.json` (26 field changes across 6 records) and `dedupe_merges_ledger.json` (7 changes across 3 canonical records), so reverse application is mechanical.
4. Verification after rollback: regenerate with baseline 623 (the pre-PR file) and run `verify_snapshot_parity.py`; re-run `pytest backend/tests`, `vitest`, lint and build.

## 11. Changed files

Committed on `phase3/catalogue-accuracy-2026-10-11` (5 commits over `03c8c2b`):

| File | What |
|---|---|
| `frontend/public/scholarships-snapshot.json` | regenerated (623 → 618) with the supported `generate_snapshot.py`, baseline-preserving |
| `frontend/public/sitemap.xml` | regenerated: 3 static routes + 618 detail URLs |
| `generate_sitemap.py` | new: sitemap derived from the snapshot |
| `frontend/src/services/snapshotContract.test.js` | the no-silent-shrinkage invariant now honours the declared `baseline_removed` |
| `backend/research_output/publish/removals_scholarships_ledger.json` | discontinued-record ledger (279, 729) with verbatim evidence |
| `backend/research_output/publish/archive_discontinued.py` | applies the ledger to the local DB (archival flags only) |
| `backend/research_output/publish/url_contamination_cleanup_ledger.json` | per-record ledger of the 484 removed pasted URLs |
| `backend/research_output/publish/clean_url_contamination.py` | applies that cleanup (21-URL scope, owners keep their own) |
| `backend/research_output/publish/dedupe_merges_ledger.json` | per-pair verdict, canonical choice, corrections, unresolved items |
| `backend/research_output/publish/merge_duplicate_pairs.py` | applies the three merges (archival, reversible) |
| `backend/research_output/publish/field_corrections_ledger.json` | per-field from/to with evidence for every correction |
| `backend/research_output/publish/apply_field_corrections.py` | evidence-gated correction applier |
| `backend/research_output/publish/add_research_records.py` | evidence-gated new-record inserter (the gate; accepted nothing in this change) |
| `backend/research_output/publish/research_agents/*.json` | research work files and live-verification evidence |
| `backend/tests/test_removal_ledger.py`, `backend/tests/test_sitemap_generation.py` | new regression tests (81 passed) |

## 12. Base/head for review

- Base: `03c8c2b` (origin/master, the deployed live catalogue)
- Head: the tip of `phase3/catalogue-accuracy-2026-10-11` (6 commits over base incl. the audit artifacts commit `52d5aa8`; verify with `git rev-parse phase3/catalogue-accuracy-2026-10-11`)
- No push, no PR opened, no deploy, no production change — stopping here for review as instructed.
