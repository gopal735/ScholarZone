# WAVE 1-3 PRODUCTION APPLY MANIFEST — FINAL

**Generated:** 2026-10-04T12:53:06.778883+00:00  
**Status:** NOT APPLIED. This document proposes; it does not execute.  
**Neon:** untouched. No credential for it exists in this environment (§6).

Every row below is a change this session made to the **local** database and is proposed for production. Old values are what the database held immediately before this pass, new values are what it holds now. Nothing here is inferred: each line is a diff between the pre-repair snapshot and the current file, so the manifest is complete regardless of how many repair passes produced it.

---

## 1. Scope summary

| Measure | Value |
|---|---|
| Catalogue rows (local, post-repair) | 722 |
| Rows publicly visible | 482 |
| Field-level changes proposed | 1957 |
| Distinct rows touched | 452 |
| Rows created by the wave | 234 |
| Rows retired this pass | 6 |
| Rows left without an image | 188 |
| Local release gate | **PASS** (0 RED, 4 YELLOW) |
| Local backup taken before any write | `scholarzone.pre_wave13_hardening_20261004_171847.db` |

Proposed change volume by column:

| Column | Changes | What it is |
|---|---|---|
| `image_source_type` | 406 | provenance vocabulary |
| `image_url` | 211 | asset identity |
| `image_source_url` | 211 | provenance |
| `image_alt_text` | 211 | accessibility text |
| `image_verified_at` | 211 | trust timestamp |
| `image_evaluated_at` | 211 | evaluation timestamp |
| `image_kind` | 210 | asset classification |
| `image_evaluation_status` | 180 | terminal outcome |
| `deadline_precision` | 73 | enum vocabulary |
| `catalogue_url` | 26 | official catalogue link |
| `official_updates_url` | 7 | official updates link |

Proposed change volume by risk class:

- **medium**: 1091
- **low**: 866

## 2. Rows created by Wave 1-3 (excluded from this manifest)

The wave inserted **234 rows** (ids 491–725). They are **not** proposed for production apply.

Reason — **PROVEN**: the public-visibility gate requires both `image_url` and `image_verified_at`. A new row whose image fields are omitted fails the gate and never appears, so a new row cannot be separated from its image decision. A row that arrives with an image has had that image asserted by research rather than validated by the pipeline, and the whole point of this pass is that such assertions were not trustworthy in this wave. **No replacement URL was invented for any of them.**

| Measure | Rows |
|---|---|
| Wave-created rows carrying a decisive favicon/app-icon/UI asset | 32 |
| Wave-created rows excluded from this manifest | 234 |

**Both figures are measured on the pre-repair snapshot**, not on the repaired database: after the repair there are no UI assets left to count, so measuring afterwards would report zero and hide the problem.

## 3. Duplicate resolution — proposed retire operations

Mechanism: an entry in `backend/config/retired_records.json`, then the `retire` stage. The row is quarantined and archived, not deleted, so its id stays addressable and nothing that referenced it is orphaned.

| Retired id | Surviving id | Reviews on survivor | Evidence |
|---|---|---|---|
| 133 | 570 | 0 | `Same programme, same call page. The two official URLs differ only in the case of the path seg...` |
| 438 | 530 | 0 | `Canonical official URLs are byte-identical after percent-encoding normalisation of the parent...` |
| 532 | 68 | 5 | `Identical image URL on both rows (GC-logo-positive...WHITE_OUT.png), identical funder and ide...` |
| 501 | 10 | 7 | `id 501's official URL is a child page of id 10's site (/wie-es-funktioniert describes the sam...` |
| 531 | 107 | 7 | `id 531 is the specific NPGS programme page under id 107's financial-aid hub, quoting the same...` |
| 553 | 13 | 7 | `id 13's catalogue_url is byte-identical to id 553's official_source_url (/en/asia/abroad/busi...` |

Reviews, verification history and image reviews are preserved: the retire stage archives rather than deletes, exactly as it did for the 48 pre-existing retirements. Three pairs additionally had the duplicate's `official_details` copied into the survivor first (ids 10, 13) so no researched text was discarded; where both sides already held a research block nothing was merged, because there is no evidence that one supersedes the other.

## 4. Field-level changes, row by row

Ordered by row id. `risk` is `low` for a value re-derived by a canonical classifier or restored verbatim from the pre-wave snapshot, and `medium` for an asset cleared because nothing trustworthy could be established.

| id | field | old | new | action | evidence | risk |
|---|---|---|---|---|---|---|
| 6 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 7 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 8 | `image_source_type` | `official_page_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 9 | `image_source_type` | `official_page_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 10 | `image_alt_text` | `Deutschlandstipendium (BMFTR)` | `Deutschlandstipendium (Germany Scholarship) - official Federal Ministry of Education and Rese...` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 10 | `image_kind` | `official_logo` | `official_banner` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 10 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 10 | `image_source_url` | `https://deutschlandstipendium.de/` | `https://www.deutschlandstipendium.de/deutschlandstipendium/de/home/home_node.html` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 10 | `image_url` | `https://www.deutschlandstipendium.de/SiteGlobals/Frontend/Images/icons/deutschlandstipendium/...` | `https://www.deutschlandstipendium.de/SharedDocs/Bilder/de/deutschlandstipendium/img/bmbf_dst_...` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 10 | `image_verified_at` | `2026-10-04 07:32:36.344477` | `2026-09-27 10:31:04.053380` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 10 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 12 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 13 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 14 | `catalogue_url` | NULL | `https://ethz.ch/content/dam/ethz/main/education/finanzielles/files-en/guidelines-scholarships...` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 14 | `image_alt_text` | `ETH Zurich` | `ETH Zurich Excellence Scholarship & Opportunity Programme (ESOP)` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 14 | `image_kind` | `official_logo` | `program_image` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 14 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 14 | `image_source_url` | `https://ethz.ch/` | `https://ethz.ch/students/en/studies/financial/scholarships/excellencescholarship.html` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 14 | `image_url` | `https://ethz.ch/etc/designs/ethz/img/icons/ETH-APP-Icons-Theme-white/192-xxxhpdi.png` | `https://ethz.ch/students/en/studies/financial/scholarships/excellencescholarship/_jcr_content...` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 14 | `image_verified_at` | `2026-10-04 09:43:31.806439` | `2026-09-28 20:01:12.511439` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 14 | `official_updates_url` | NULL | `https://ethz.ch/staffnet/en/news-and-events/academic-calendar.html` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 14 | `image_evaluated_at` | `2026-10-04 09:43:31.806439` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 15 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 19 | `image_source_type` | `official_page_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 21 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 22 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 23 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 24 | `catalogue_url` | NULL | `https://www.humboldt-foundation.de/en/apply/sponsorship-programmes/humboldt-research-fellowship` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 24 | `image_source_type` | `official_ngo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 25 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 26 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 26 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 26 | `image_alt_text` | `National Institute for International Education (NIIED), Ministry of Education - official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 26 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 26 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 26 | `image_source_url` | `https://www.studyinkorea.go.kr/en/plan/scholarship.do` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 26 | `image_url` | `https://www.studyinkorea.go.kr/public/v3/images/common/icon-edu-org-en.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 26 | `image_verified_at` | `2026-10-04 07:32:36.344477` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 27 | `image_source_type` | `official_page_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 28 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 29 | `image_source_type` | `official_page_logo` | `official_government` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 31 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 32 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 33 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 34 | `image_source_type` | `official_logo` | `official_government` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 35 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 35 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 35 | `image_alt_text` | `A STAR Singapore` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 35 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 35 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 35 | `image_source_url` | `https://a-star.edu.sg/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 35 | `image_url` | `https://www.a-star.edu.sg/api/media/867ab78f-c433-4489-9de0-51f3937f384c/favicon.ico` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 35 | `image_verified_at` | `2026-10-04 07:32:36.344477` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 37 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 38 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 39 | `image_evaluated_at` | `2026-10-04 07:32:05.164655` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 39 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 39 | `image_alt_text` | `University of Toronto` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 39 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 39 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 39 | `image_source_url` | `https://future.utoronto.ca/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 39 | `image_url` | `https://future.utoronto.ca/themes/utfs/images/icons/logo-svg.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 39 | `image_verified_at` | `2026-10-04 07:32:05.164655` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 40 | `image_evaluated_at` | `2026-10-04 07:53:40.473784` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 40 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 40 | `image_alt_text` | `ARES (Fédération Wallonie-Bruxelles)` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 40 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 40 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 40 | `image_source_url` | `https://www.ares-ac.be/fr/bourses` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 40 | `image_url` | `https://www.ares-ac.be/themes/custom/frontend/favicon.ico` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 40 | `image_verified_at` | `2026-10-04 07:53:40.473784` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 41 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 48 | `image_alt_text` | `University of Sydney` | `University of Sydney Vice-Chancellor's International Scholarships Scheme - official Universit...` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 48 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-09-28 18:52:48.706617` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 48 | `image_kind` | `official_logo` | `program_image` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 48 | `image_source_type` | `official_university` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 48 | `image_source_url` | `https://www.sydney.edu.au/` | `https://www.sydney.edu.au/scholarships/e/vice-chancellor-international-scholarships-scheme.html` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 48 | `image_url` | `https://www.sydney.edu.au/content/dam/icons/logos/logo-usyd-dark.svg` | `https://www.sydney.edu.au/content/dam/corporate/assets/default-hero.jpg` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 48 | `image_verified_at` | `2026-10-04 07:32:36.344477` | `2026-09-27 11:49:31.961443` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 49 | `image_alt_text` | `University of Sydney` | `Annie Farrand Scholarship in Agricultural Science (International) - official University of Sy...` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 49 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-09-28 18:52:48.706618` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 49 | `image_kind` | `official_logo` | `program_image` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 49 | `image_source_type` | `official_university` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 49 | `image_source_url` | `https://www.sydney.edu.au/` | `https://www.sydney.edu.au/scholarships/d/farrand-scholarship-in-agricultural-science--interna...` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 49 | `image_url` | `https://www.sydney.edu.au/content/dam/icons/logos/logo-usyd-dark.svg` | `https://www.sydney.edu.au/content/dam/corporate/assets/default-hero.jpg` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 49 | `image_verified_at` | `2026-10-04 07:32:36.344477` | `2026-09-27 11:49:31.610429` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 51 | `image_alt_text` | `University of Western Australia` | `UWA Global Excellence Scholarship` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 51 | `image_kind` | `official_logo` | `official_banner` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 51 | `image_source_type` | `official_university` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 51 | `image_source_url` | `https://uwa.edu.au/` | `https://www.uwa.edu.au/study/scholarships-and-fees/scholarships/international-scholarships/gl...` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 51 | `image_url` | `https://www.uwa.edu.au/_assets/favicon180.png` | `https://www.uwa.edu.au/_assets/opengraph.png` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 51 | `image_verified_at` | `2026-10-04 07:32:36.344477` | `2026-09-27 18:18:24.108775` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 51 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 53 | `image_source_type` | `official_page_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 56 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 57 | `image_alt_text` | `University of Wisconsin` | `KMSP Group Photo with UHS staff` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 57 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-09-28 18:52:48.706627` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 57 | `image_kind` | `official_logo` | `program_image` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 57 | `image_source_url` | `https://kmsp.wisc.edu/` | `https://kmsp.wisc.edu/program-support/` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 57 | `image_url` | `https://kmsp.wisc.edu/wp-content/themes/uw-theme/dist/images/favicons/apple-touch-icon.png` | `https://kmsp.wisc.edu/wp-content/uploads/sites/997/2026/01/Cohort-9-with-UHS-scaled-e17673746...` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 57 | `image_verified_at` | `2026-10-04 07:32:36.344477` | `2026-09-07 17:54:38.352486` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 63 | `image_evaluated_at` | NULL | `2026-10-04T11:18:52.082139+00:00` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 63 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 63 | `image_alt_text` | `A professor faces a circular auditorium full of students while giving a lecture at Michigan S...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 63 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 63 | `image_source_type` | `official_provider` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 63 | `image_source_url` | `https://admissions.msu.edu/scholarships` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 63 | `image_url` | `https://edge.sitecorecloud.io/michiganstab57e-msustrategi129d-prod9868-7e5e/media/project/msu...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 63 | `image_verified_at` | `2026-09-27 12:02:16.356988` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 68 | `image_source_type` | `official_page_logo` | `official_university` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 69 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 78 | `image_evaluated_at` | `2026-10-04 07:32:05.164655` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 78 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 78 | `image_alt_text` | `Study UK (British Council) — "Study UK / GREAT Scholarships" lockup, dark navy #04043F` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 78 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 78 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 78 | `image_source_url` | `https://study-uk.britishcouncil.org/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 78 | `image_url` | `https://study-uk.britishcouncil.org/images/suk-great-logo.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 78 | `image_verified_at` | `2026-10-04 07:32:05.164655` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 81 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 82 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 83 | `image_source_type` | `official_page_logo` | `official_university` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 84 | `image_alt_text` | `University of British Columbia` | `UBC International Major Entrance Scholarship (IMES) - official University of British Columbia...` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 84 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-09-28 18:52:48.706651` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 84 | `image_kind` | `official_logo` | `program_image` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 84 | `image_source_type` | `official_university` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 84 | `image_source_url` | `https://you.ubc.ca/` | `https://you.ubc.ca/financial-planning/scholarships-awards-international-students` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 84 | `image_url` | `https://you.ubc.ca/wp-content/uploads/2021/10/cropped-ubc-favicon-192x192.webp` | `https://you.ubc.ca/wp-content/uploads/2025/04/hand-holding-circle-dollar-solid.svg` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 84 | `image_verified_at` | `2026-10-04 07:32:36.344477` | `2026-09-27 12:41:53.330280` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 85 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 85 | `image_alt_text` | `University of British Columbia` | `Karen McKellin International Leader of Tomorrow Award (UBC) - official University of British ...` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 85 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-09-28 18:52:48.706653` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 85 | `image_kind` | `official_logo` | `program_image` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 85 | `image_source_type` | `official_government` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 85 | `image_source_url` | `https://you.ubc.ca/financial-planning/scholarships-awards-international-students/internationa...` | `https://you.ubc.ca/financial-planning/scholarships-awards-international-students/internationa...` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 85 | `image_url` | `https://you.ubc.ca/wp-content/uploads/2021/10/cropped-ubc-favicon-192x192.webp` | `https://you.ubc.ca/wp-content/uploads/2019/10/ISI-2019-096-YARA9377.jpg` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 85 | `image_verified_at` | `2026-10-01 00:00:00.000000` | `2026-09-27 12:42:31.516552` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 86 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 86 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 86 | `image_alt_text` | `University of British Columbia` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 86 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 86 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 86 | `image_source_url` | `https://you.ubc.ca/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 86 | `image_url` | `https://you.ubc.ca/wp-content/uploads/2021/10/cropped-ubc-favicon-192x192.webp` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 86 | `image_verified_at` | `2026-10-04 07:32:36.344477` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 91 | `image_evaluated_at` | `2026-09-27 18:19:15.877243` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 91 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 91 | `image_alt_text` | `Université Paris-Saclay (Government of France / IDEX) official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 91 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 91 | `image_source_type` | `official_page_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 91 | `image_source_url` | `https://www.universite-paris-saclay.fr/en/admission/bourses-et-aides-financieres/internationa...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 91 | `image_url` | `https://www.universite-paris-saclay.fr/sites/default/files/media/2019-12/logo-ups.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 91 | `image_verified_at` | `2026-09-28 10:28:49.715338` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 92 | `catalogue_url` | NULL | `https://www.sciencespo.fr/en/academics/phd-programmes/` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 92 | `image_evaluated_at` | `2026-09-27 18:19:18.927130` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 92 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 92 | `image_alt_text` | `Sciences Po Paris official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 92 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 92 | `image_source_type` | `official_page_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 92 | `image_source_url` | `https://www.sciencespo.fr/students/en/fees-funding/bursaries-financial-aid/emile-boutmy-schol...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 92 | `image_url` | `https://www.sciencespo.fr/students/en/static/4e8c8b615cdf25da682418334c3751b6/sciencespo_logo...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 92 | `image_verified_at` | `2026-09-28 10:28:52.292467` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 93 | `catalogue_url` | NULL | `https://www.hec.edu/en/bachelor-programs/course-content` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 93 | `official_updates_url` | NULL | `https://www.hec.edu/en/school/newsroom` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 96 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 97 | `catalogue_url` | NULL | `https://web.archive.org/web/20241114021340/https://bse.eu/study/masters-programs/upf-phd-track` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 97 | `image_evaluated_at` | `2026-09-27 18:20:01.167147` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 97 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 97 | `official_updates_url` | NULL | `https://bse.eu/news` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 97 | `image_alt_text` | `Barcelona School of Economics official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 97 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 97 | `image_source_type` | `official_page_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 97 | `image_source_url` | `https://bse.eu/masters-degrees/admissions` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 97 | `image_url` | `https://bse.eu/_nuxt/logo_horizontal_white.BORGvD08.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 97 | `image_verified_at` | `2026-09-28 10:29:14.447625` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 101 | `catalogue_url` | NULL | `https://www.a-star.edu.sg/scholarships` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 101 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 101 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 101 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 101 | `image_alt_text` | `A STAR Singapore` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 101 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 101 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 101 | `image_source_url` | `https://a-star.edu.sg/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 101 | `image_url` | `https://www.a-star.edu.sg/api/media/867ab78f-c433-4489-9de0-51f3937f384c/favicon.ico` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 101 | `image_verified_at` | `2026-10-04 07:32:36.344477` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 109 | `image_source_type` | `official_page_logo` | `official_university` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 112 | `image_evaluated_at` | `2026-09-27 18:21:34.356261` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 112 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 112 | `image_alt_text` | `Department of Science & Technology (DST), Govt. of India, via INSA official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 112 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 112 | `image_source_type` | `official_page_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 112 | `image_source_url` | `https://insaindia.res.in/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 112 | `image_url` | `https://insaindia.res.in/wp-content/uploads/2022/09/cropped-insa_logo-32x32.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 112 | `image_verified_at` | `2026-09-28 10:29:20.887571` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 114 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 115 | `image_evaluated_at` | `2026-10-04 07:32:05.164655` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 115 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 115 | `image_alt_text` | `ICAR India` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 115 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 115 | `image_source_type` | `official_government` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 115 | `image_source_url` | `https://icar.gov.in/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 115 | `image_url` | `http://www.icar.gov.in/sites/default/files/inline-images/logo.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 115 | `image_verified_at` | `2026-10-04 07:32:05.164655` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 123 | `image_source_type` | `official_page_logo` | `official_university` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 125 | `image_evaluated_at` | `2026-10-04 07:32:05.164655` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 125 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 125 | `image_alt_text` | `Harvard College` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 125 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 125 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 125 | `image_source_url` | `https://college.harvard.edu/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 125 | `image_url` | `https://www.college.harvard.edu/themes/custom/harvard_college/assets/dependencies/favicon/app...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 125 | `image_verified_at` | `2026-10-04 07:32:05.164655` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 130 | `image_evaluated_at` | `2026-10-04 09:43:31.806439` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 130 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 130 | `image_alt_text` | `Aga Khan Foundation` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 130 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 130 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 130 | `image_source_url` | `https://akf.org/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 130 | `image_url` | `https://akf.org/wp-content/themes/aga-khan/assets/favicon/favicon.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 130 | `image_verified_at` | `2026-10-04 09:43:31.806439` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 131 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 132 | `catalogue_url` | NULL | `https://sites.newpaltz.edu/news/2019/12/center-for-international-programs-congratulates-first...` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 132 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 133 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 134 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 135 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 136 | `image_evaluated_at` | NULL | `2026-10-04T11:18:52.082139+00:00` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 136 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 136 | `image_alt_text` | `Università degli Studi di Padova official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 136 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 136 | `image_source_type` | `official_page_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 136 | `image_source_url` | `https://www.unipd.it/en/padua-international-excellence-scholarship-programme` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 136 | `image_url` | `https://www.unipd.it/favicon.ico?favicon.fe08e1ad.ico` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 136 | `image_verified_at` | `2026-09-28 10:29:35.123078` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 137 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 138 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 143 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 152 | `image_alt_text` | `University of Geneva` | `Accreditation` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 152 | `image_evaluated_at` | `2026-10-04 08:53:40.036011` | `2026-09-28 18:52:48.706711` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 152 | `image_kind` | `official_logo` | `official_banner` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 152 | `image_source_type` | `official_university` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 152 | `image_source_url` | `https://www.unige.ch/en/` | `https://www.unige.ch/sciences/en/enseignements/formations/masters/excellencemasterfellowships...` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 152 | `image_url` | `https://www.unige.ch/apple-touch-icon.png` | `https://www.unige.ch/files/4416/5210/1573/SAR-Label_Institutionen_22-29_EN.png` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 152 | `image_verified_at` | `2026-10-04 08:53:40.036011` | `2026-09-27 14:29:13.542427` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 153 | `official_updates_url` | NULL | `https://www.unil.ch/news/en/home/unil.html` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 154 | `catalogue_url` | NULL | `https://www.unisg.ch/en/studying/orientation/advice-and-support/financing-your-studies/hsg-fu...` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 154 | `official_updates_url` | NULL | `https://www.unisg.ch/de/newsroom/` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 156 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 157 | `image_evaluated_at` | `2026-09-27 18:23:58.920037` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 157 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 157 | `image_alt_text` | `CERN official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 157 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 157 | `image_source_type` | `official_page_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 157 | `image_source_url` | `https://careers.cern/programmes/doctoral-studentship/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 157 | `image_url` | `https://careers.cern/wp-content/uploads/2025/08/cropped-logo-menu-32x32.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 157 | `image_verified_at` | `2026-09-28 10:29:43.689447` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 158 | `image_evaluated_at` | `2026-09-27 18:23:59.121167` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 158 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 158 | `image_alt_text` | `CERN official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 158 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 158 | `image_source_type` | `official_page_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 158 | `image_source_url` | `https://careers.cern/programmes/research-fellowship/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 158 | `image_url` | `https://careers.cern/wp-content/uploads/2025/08/cropped-logo-menu-32x32.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 158 | `image_verified_at` | `2026-09-28 10:29:45.395688` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 159 | `image_source_type` | `official_page_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 161 | `image_alt_text` | `WIPO` | `WIPO Fellowship Program - official World Intellectual Property Organization (WIPO) image` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 161 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-09-28 18:52:48.706721` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 161 | `image_kind` | `official_logo` | `program_image` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 161 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 161 | `image_source_url` | `https://wipo.int/` | `https://www.wipo.int/en/web/working-at-wipo/fellowship-program` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 161 | `image_url` | `https://www.wipo.int/web-assets/images/ulf-wipo-favicon-192.png` | `https://www.wipo.int/documents/102028/4469519/youth-expert-program-1200.jpg/1cbc52b5-d374-204...` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 161 | `image_verified_at` | `2026-10-04 07:32:36.344477` | `2026-09-27 14:38:31.470802` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 163 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 164 | `image_evaluated_at` | `2026-10-04 07:32:05.164655` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 164 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 164 | `image_alt_text` | `University of Graz (Karl-Franzens-Universität Graz)` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 164 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 164 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 164 | `image_source_url` | `https://uni-graz.at/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 164 | `image_url` | `https://static.uni-graz.at/_assets/ad3b1d899ce171dcc9754695b3eee153/Icons/UniGraz/Header/univ...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 164 | `image_verified_at` | `2026-10-04 07:32:05.164655` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 167 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 172 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 173 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 173 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 173 | `image_alt_text` | `University of Amsterdam` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 173 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 173 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 173 | `image_source_url` | `https://uva.nl/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 173 | `image_url` | `https://www.uva.nl/webfiles/1779862044324/_favicon/apple-touch-icon.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 173 | `image_verified_at` | `2026-10-04 07:32:36.344477` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 174 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 180 | `image_evaluated_at` | NULL | `2026-10-04T11:18:52.082139+00:00` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 180 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 180 | `image_alt_text` | `Maastricht University Holland High Potential Scholarship - official Maastricht University image` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 180 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 180 | `image_source_type` | `official_provider` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 180 | `image_source_url` | `https://www.maastrichtuniversity.nl/studeren/toelating-inschrijving/financing-your-studies/sc...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 180 | `image_url` | `https://www.maastrichtuniversity.nl/themes/custom/um_corporate/favicon.ico` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 180 | `image_verified_at` | `2026-09-27 15:05:09.092219` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 182 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 185 | `image_alt_text` | `KTH Royal Institute of Technology` | `KTH students walking together on campus` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 185 | `image_kind` | `official_logo` | `official_banner` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 185 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 185 | `image_source_url` | `https://kth.se/` | `https://www.kth.se/study` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 185 | `image_url` | `https://www.kth.se/polopoly_fs/1.1273722.1692876353!/image/apple-touch-icon-KTH-logo-180x180.png` | `https://www.kth.se/polopoly_fs/1.1376857.1734452256!/image/studies2.webp` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 185 | `image_verified_at` | `2026-10-04 07:32:36.344477` | `2026-09-27 14:40:20.647692` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 185 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 186 | `image_alt_text` | `Chalmers University of Technology` | `Chalmers University of Technology — IPOET Scholarship - official Chalmers University of Techn...` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 186 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-09-28 18:52:48.706748` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 186 | `image_kind` | `official_logo` | `program_image` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 186 | `image_source_type` | `official_university` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 186 | `image_source_url` | `https://chalmers.se/` | `https://www.chalmers.se/scholarships` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 186 | `image_url` | `https://www.chalmers.se/apple-touch-icon.png` | `https://www.chalmers.se/api/media/?url=https://cms.www.chalmers.se/Media/egzbsyyi/wacqt_i0a10...` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 186 | `image_verified_at` | `2026-10-04 07:32:36.344477` | `2026-09-27 14:46:08.491620` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 190 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 191 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 191 | `official_updates_url` | NULL | `https://si.se/en/about-si/subscribe-to-the-swedish-institutes-newsletters-3/` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 194 | `image_evaluated_at` | `2026-10-04 07:32:05.164655` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 194 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 194 | `image_alt_text` | `University of Queensland` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 194 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 194 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 194 | `image_source_url` | `https://scholarships.uq.edu.au/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 194 | `image_url` | `https://static.uq.net.au/v10/logos/corporate/uq-apple-touch-icon.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 194 | `image_verified_at` | `2026-10-04 07:32:05.164655` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 197 | `image_alt_text` | `University of Sydney` | `University of Sydney International Scholarship (USydIS) - official University of Sydney image` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 197 | `image_kind` | `official_logo` | `official_banner` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 197 | `image_source_type` | `official_university` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 197 | `image_source_url` | `https://www.sydney.edu.au/` | `https://www.sydney.edu.au/scholarships/international.html` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 197 | `image_url` | `https://www.sydney.edu.au/content/dam/icons/logos/logo-usyd-dark.svg` | `https://www.sydney.edu.au/content/dam/people/students/architecture-student-model.jpg` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 197 | `image_verified_at` | `2026-10-04 07:32:36.344477` | `2026-09-27 14:45:26.296601` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 197 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 202 | `catalogue_url` | NULL | `https://www.rmit.edu.au/study-with-us/international-students/programs-for-international-students` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 203 | `image_alt_text` | `Flinders University` | `Flinders International Postgraduate Research Scholarship (FIPRS) - official Flinders Universi...` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 203 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-09-28 18:52:48.706766` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 203 | `image_kind` | `official_logo` | `program_image` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 203 | `image_source_type` | `official_university` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 203 | `image_source_url` | `https://flinders.edu.au/` | `https://www.flinders.edu.au/scholarships/flinders-university-international-research-scholarship` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 203 | `image_url` | `https://www.flinders.edu.au/content/dam/images/60th/flinders-60th-navy-header.svg` | `https://www.flinders.edu.au/content/dam/images/open-graph/og-flinders-bedford-plaza.jpg` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 203 | `image_verified_at` | `2026-10-04 07:32:36.344477` | `2026-09-27 15:17:43.580458` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 210 | `catalogue_url` | NULL | `https://admission.kaist.ac.kr/intl-undergraduate/support/scholarships/kaist` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 210 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 211 | `catalogue_url` | NULL | `https://admission.kaist.ac.kr/intl-graduate/FinancialSupport/Scholarship/OtherPrograms` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 215 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 217 | `catalogue_url` | NULL | `https://www.tugraz.at/en/studying-and-teaching/degree-and-certificate-programmes/overview-deg...` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 217 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 218 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 221 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 222 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 226 | `image_alt_text` | `Austrian Academy of Sciences` | `Johann Wilhelm Ritter von Mannagetta Foundation Fellowships - official Johann Wilhelm Ritter ...` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 226 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-09-28 18:52:48.706788` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 226 | `image_kind` | `official_logo` | `program_image` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 226 | `image_source_type` | `official_university` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 226 | `image_source_url` | `https://stipendien.oeaw.ac.at/` | `https://stipendien.oeaw.ac.at/en/fellowships/mannagetta` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 226 | `image_url` | `https://stipendien.oeaw.ac.at/typo3conf/ext/oeaw_theme24/Resources/Public/Icons/OEAW-Logo-RGB...` | `https://stipendien.oeaw.ac.at/fileadmin/_processed_/a/3/csm_Mannagetta_Abschluss_romain-vigne...` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 226 | `image_verified_at` | `2026-10-04 07:32:36.344477` | `2026-09-27 15:13:42.108820` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 228 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 229 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 230 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 231 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 232 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 233 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 234 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 235 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 236 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 237 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 238 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 239 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 240 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 242 | `image_source_type` | `official_logo` | `official_government` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 243 | `image_source_type` | `official_logo` | `official_government` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 244 | `image_evaluated_at` | `2026-09-27 18:25:55.558061` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 244 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 244 | `image_alt_text` | `Tsinghua University & China Scholarship Council (CSC) official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 244 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 244 | `image_source_type` | `official_page_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 244 | `image_source_url` | `https://yz.tsinghua.edu.cn/en/info/1027/1117.htm` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 244 | `image_url` | `https://yz.tsinghua.edu.cn/en/image/logo.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 244 | `image_verified_at` | `2026-09-28 10:30:14.532352` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 246 | `image_evaluated_at` | `2026-09-27 18:26:00.263515` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 246 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 246 | `image_alt_text` | `Nankai University & China Scholarship Council (CSC) official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 246 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 246 | `image_source_type` | `official_page_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 246 | `image_source_url` | `https://ensie.nankai.edu.cn/info/1047/1347.htm` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 246 | `image_url` | `https://ensie.nankai.edu.cn/images/logo.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 246 | `image_verified_at` | `2026-09-28 10:30:15.602890` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 247 | `image_evaluated_at` | `2026-10-04 07:32:05.164655` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 247 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 247 | `image_alt_text` | `cis.chinese.cn` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 247 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 247 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 247 | `image_source_url` | `https://cis.chinese.cn/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 247 | `image_url` | `https://www.chinese.cn/page/img/celc_logo.5f1a4e00.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 247 | `image_verified_at` | `2026-10-04 07:32:05.164655` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 248 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 249 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 251 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 252 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 254 | `image_source_type` | `official_logo` | `official_government` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 255 | `image_evaluated_at` | `2026-10-04 07:32:05.164655` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 255 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 255 | `image_alt_text` | `University of Auckland` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 255 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 255 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 255 | `image_source_url` | `https://auckland.ac.nz/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 255 | `image_url` | `https://www.auckland.ac.nz/etc.clientlibs/uoa-digital/clientlibs/resources/svg/favicon.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 255 | `image_verified_at` | `2026-10-04 07:32:05.164655` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 256 | `image_alt_text` | `University of Auckland` | `Students enjoying their lunch in the sunshine.` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 256 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-09-28 18:52:48.706816` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 256 | `image_kind` | `official_logo` | `program_image` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 256 | `image_source_type` | `official_university` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 256 | `image_source_url` | `https://auckland.ac.nz/` | `https://www.auckland.ac.nz/scholarships` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 256 | `image_url` | `https://www.auckland.ac.nz/etc.clientlibs/uoa-digital/clientlibs/resources/svg/favicon.svg` | `https://www.auckland.ac.nz/content/auckland/en/study/scholarships-and-awards/_jcr_content/her...` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 256 | `image_verified_at` | `2026-10-04 07:32:36.344477` | `2026-09-27 16:14:10.538168` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 262 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 265 | `image_evaluated_at` | `2026-10-04 07:32:05.164655` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 265 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 265 | `image_alt_text` | `Tampere University` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 265 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 265 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 265 | `image_source_url` | `https://tuni.fi/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 265 | `image_url` | `https://www.tuni.fi/shared/favicon.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 265 | `image_verified_at` | `2026-10-04 07:32:05.164655` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 267 | `image_evaluated_at` | `2026-10-04 08:53:39.244242` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 267 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 267 | `image_alt_text` | `LUT University` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 267 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 267 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 267 | `image_source_url` | `https://www.lut.fi/en` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 267 | `image_url` | `https://www.lut.fi/themes/custom/lut/images/icons/favicons/android-chrome-192x192.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 267 | `image_verified_at` | `2026-10-04 08:53:39.244242` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 268 | `image_evaluated_at` | `2026-10-04 07:32:05.164655` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 268 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 268 | `image_alt_text` | `Study in Denmark` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 268 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 268 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 268 | `image_source_url` | `https://studyindenmark.dk/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 268 | `image_url` | `https://studyindenmark.dk/apple-touch-icon.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 268 | `image_verified_at` | `2026-10-04 07:32:05.164655` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 269 | `image_evaluated_at` | `2026-10-04 07:32:05.164655` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 269 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 269 | `image_alt_text` | `Technical University of Denmark` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 269 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 269 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 269 | `image_source_url` | `https://dtu.dk/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 269 | `image_url` | `https://www.dtu.dk/favicon.ico` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 269 | `image_verified_at` | `2026-10-04 07:32:05.164655` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 270 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 271 | `image_alt_text` | `University of Copenhagen` | `University of Copenhagen Danish Government Scholarship - official University of Copenhagen image` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 271 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-09-28 18:52:48.706829` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 271 | `image_kind` | `official_logo` | `program_image` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 271 | `image_source_type` | `official_university` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 271 | `image_source_url` | `https://ku.dk/` | `https://www.ku.dk/studies/admission/scholarships-for-full-degree-students` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 271 | `image_url` | `https://www.ku.dk/_assets/12a46eea25fd08a7277319b85c785b6b/Icons/Site/ucph-logo-da.svg` | `https://www.ku.dk/fileadmin/_processed_/7/b/csm_Tuition_fees_and_scholarships_NEGATIV_cb3ae2b...` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 271 | `image_verified_at` | `2026-10-04 07:32:36.344477` | `2026-09-27 16:11:15.214868` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 272 | `catalogue_url` | NULL | `https://masters.au.dk/masters-degree-programmes` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 273 | `image_alt_text` | `University of Southern Denmark` | `Syddansk Universitet Map` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 273 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-09-28 18:52:48.706831` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 273 | `image_kind` | `official_logo` | `program_image` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 273 | `image_source_type` | `official_university` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 273 | `image_source_url` | `https://sdu.dk/` | `https://www.sdu.dk/contact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 273 | `image_url` | `https://www.sdu.dk/-/media/default-website/some/sdu_logo_1200x630.jpg` | `https://www.sdu.dk/-/media/genereltsystem/p-persp-solid.png` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 273 | `image_verified_at` | `2026-10-04 07:32:36.344477` | `2026-09-27 16:56:30.480049` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 274 | `image_alt_text` | `BI Norwegian Business School` | `BI Presidential Scholarship - official BI Norwegian Business School image` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 274 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-09-28 18:52:48.706833` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 274 | `image_kind` | `official_logo` | `program_image` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 274 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 274 | `image_source_url` | `https://bi.no/` | `https://www.bi.no/en/programmes-and-individual-courses/scholarships/bi-presidential-scholarships` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 274 | `image_url` | `https://www.bi.no/public/images/Icons/apple-touch-icon-180x180.png` | `https://media.bi.no/asset/f6bf9a41-2dc4-4690-8a04-bf602df37577/Large/Marked-Heltid-internasjo...` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 274 | `image_verified_at` | `2026-10-04 07:32:36.344477` | `2026-09-25 08:38:35.018991` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 275 | `image_alt_text` | `BI Norwegian Business School` | `BI Master International Scholarship – Bergen - official BI Norwegian Business School image` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 275 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-09-28 18:52:48.706834` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 275 | `image_kind` | `official_logo` | `program_image` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 275 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 275 | `image_source_url` | `https://bi.no/` | `https://www.bi.no/en/programmes-and-individual-courses/scholarships/master-of-science-interna...` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 275 | `image_url` | `https://www.bi.no/public/images/Icons/apple-touch-icon-180x180.png` | `https://media.bi.no/asset/f6bf9a41-2dc4-4690-8a04-bf602df37577/Large/Marked-Heltid-internasjo...` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 275 | `image_verified_at` | `2026-10-04 07:32:36.344477` | `2026-09-25 08:49:13.724109` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 276 | `image_alt_text` | `BI Norwegian Business School` | `BI International Baccalaureate Scholarship - official BI Norwegian Business School image` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 276 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-09-28 18:52:48.706836` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 276 | `image_kind` | `official_logo` | `program_image` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 276 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 276 | `image_source_url` | `https://bi.no/` | `https://www.bi.no/en/programmes-and-individual-courses/scholarships/bi-international-baccalau...` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 276 | `image_url` | `https://www.bi.no/public/images/Icons/apple-touch-icon-180x180.png` | `https://media.bi.no/asset/f6bf9a41-2dc4-4690-8a04-bf602df37577/Large/Marked-Heltid-internasjo...` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 276 | `image_verified_at` | `2026-10-04 07:32:36.344477` | `2026-09-27 17:05:44.860619` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 277 | `image_alt_text` | `BI Norwegian Business School` | `BI Future African Leader Scholarship - official BI Norwegian Business School image` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 277 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-09-28 18:52:48.706837` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 277 | `image_kind` | `official_logo` | `program_image` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 277 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 277 | `image_source_url` | `https://bi.no/` | `https://www.bi.no/en/programmes-and-individual-courses/scholarships/future-african-leader-sch...` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 277 | `image_url` | `https://www.bi.no/public/images/Icons/apple-touch-icon-180x180.png` | `https://media.bi.no/asset/f6bf9a41-2dc4-4690-8a04-bf602df37577/Large/Marked-Heltid-internasjo...` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 277 | `image_verified_at` | `2026-10-04 07:32:36.344477` | `2026-09-27 16:15:07.540759` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 280 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 281 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 282 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 285 | `image_source_type` | `official_page_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 286 | `image_source_type` | `official_page_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 288 | `catalogue_url` | NULL | `https://xplore.bme.hu/available-programmes/` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 289 | `image_source_type` | `official_page_logo` | `official_government` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 291 | `image_source_type` | `official_page_logo` | `official_government` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 294 | `image_evaluated_at` | `2026-09-27 18:26:35.624523` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 294 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 294 | `image_alt_text` | `Ministry of Education, Youth and Sports (MEYS) / DZS official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 294 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 294 | `image_source_type` | `official_page_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 294 | `image_source_url` | `https://msmt.gov.cz/eu-and-international-affairs/government-scholarships-developing-countries` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 294 | `image_url` | `https://msmt.gov.cz/favicon.ico?favicon.3e-91l5itci77.ico` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 294 | `image_verified_at` | `2026-09-28 10:30:58.028400` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 295 | `image_evaluated_at` | `2026-10-04 07:32:05.164655` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 295 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 295 | `image_alt_text` | `Charles University` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 295 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 295 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 295 | `image_source_url` | `https://cuni.cz/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 295 | `image_url` | `https://cuni.cz/sablona/dist/img/UK-logo-horizontal-EN_hd.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 295 | `image_verified_at` | `2026-10-04 07:32:05.164655` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 296 | `catalogue_url` | NULL | `https://www.visegradfund.org/scholarships` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 296 | `image_evaluated_at` | `2026-09-27 18:26:49.352038` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 296 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 296 | `image_alt_text` | `International Visegrad Fund official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 296 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 296 | `image_source_type` | `official_page_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 296 | `image_source_url` | `https://www.visegradfund.org/scholarships` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 296 | `image_url` | `https://www.visegradfund.org/favicon.ico` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 296 | `image_verified_at` | `2026-09-28 10:31:02.812026` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 297 | `image_evaluated_at` | `2026-09-27 18:26:50.071864` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 297 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 297 | `image_alt_text` | `Masaryk University (Brno) official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 297 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 297 | `image_source_type` | `official_page_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 297 | `image_source_url` | `https://czs.muni.cz/en/student-from-abroad/other-possibilities/visegrad-grant` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 297 | `image_url` | `https://czs.muni.cz/templates/czsjvs/favicon.ico` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 297 | `image_verified_at` | `2026-09-28 10:31:05.112098` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 299 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 301 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 302 | `image_evaluated_at` | `2026-09-27 18:29:58.113139` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 302 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 302 | `image_alt_text` | `University of Porto (U.Porto) official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 302 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 302 | `image_source_type` | `official_page_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 302 | `image_source_url` | `https://www.up.pt/portal/en/live/student-life/scholarships-and-funding/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 302 | `image_url` | `https://www.up.pt/portal/static/images/favicons/favicon.ico` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 302 | `image_verified_at` | `2026-09-28 10:31:06.671147` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 303 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 305 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 306 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 307 | `image_evaluated_at` | `2026-10-04 07:32:05.164655` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 307 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 307 | `image_alt_text` | `University of Toronto` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 307 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 307 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 307 | `image_source_url` | `https://sgs.utoronto.ca/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 307 | `image_url` | `https://www.utoronto.ca/themes/custom/bootstrap_uoft/images/favicons/favicon.ico` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 307 | `image_verified_at` | `2026-10-04 07:32:05.164655` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 308 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 309 | `image_evaluated_at` | `2026-10-04 07:32:05.164655` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 309 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 309 | `image_alt_text` | `Fonds de recherche du Quebec` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 309 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 309 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 309 | `image_source_url` | `https://frq.gouv.qc.ca/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 309 | `image_url` | `https://frq.gouv.qc.ca/app/themes/webit/apple-touch-icon.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 309 | `image_verified_at` | `2026-10-04 07:32:05.164655` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 310 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 311 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 312 | `image_evaluated_at` | `2026-10-04 07:40:19.981705` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 312 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 312 | `image_alt_text` | `Schulich Leader Scholarships` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 312 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 312 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 312 | `image_source_url` | `https://schulichleaders.com/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 312 | `image_url` | `https://schulichleaders.com/wp-content/themes/schulichleaders/images/favicon.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 312 | `image_verified_at` | `2026-10-04 07:40:19.981705` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 314 | `catalogue_url` | NULL | `https://english.ucas.ac.cn/index.php/research/research-programs` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 315 | `image_evaluated_at` | `2026-10-04 07:32:05.164655` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 315 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 315 | `image_alt_text` | `Peking University` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 315 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 315 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 315 | `image_source_url` | `https://isd.pku.edu.cn/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 315 | `image_url` | `https://www.pku.edu.cn/pku_logo_red.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 315 | `image_verified_at` | `2026-10-04 07:32:05.164655` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 316 | `image_evaluated_at` | `2026-09-27 18:30:25.428451` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 316 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 316 | `image_alt_text` | `Tsinghua University official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 316 | `image_kind` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 316 | `image_source_type` | `official_page_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 316 | `image_source_url` | `https://international.join-tsinghua.edu.cn/Admission1/Freshmen_Scholarships1.htm` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 316 | `image_url` | `https://international.join-tsinghua.edu.cn/image/logo272.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 316 | `image_verified_at` | `2026-09-28 10:31:21.617699` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 317 | `deadline_precision` | `application_dead` | `unknown` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 317 | `image_evaluated_at` | `2026-09-27 18:30:19.471895` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 317 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 317 | `image_alt_text` | `Yz.Tsinghua University Cn official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 317 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 317 | `image_source_type` | `official_page_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 317 | `image_source_url` | `https://yz.tsinghua.edu.cn/en/info/1027/1477.htm` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 317 | `image_url` | `https://yz.tsinghua.edu.cn/en/image/logo.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 317 | `image_verified_at` | `2026-09-28 10:31:22.359666` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 318 | `deadline_precision` | `application_dead` | `unknown` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 318 | `image_evaluated_at` | `2026-09-27 18:30:19.742291` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 318 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 318 | `image_alt_text` | `Yz.Tsinghua University Cn official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 318 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 318 | `image_source_type` | `official_page_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 318 | `image_source_url` | `https://yz.tsinghua.edu.cn/en/info/1027/1391.htm` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 318 | `image_url` | `https://yz.tsinghua.edu.cn/en/image/logo.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 318 | `image_verified_at` | `2026-09-28 10:31:23.096039` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 319 | `image_evaluated_at` | `2026-09-27 18:30:54.037515` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 319 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 319 | `image_alt_text` | `Fudan University official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 319 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 319 | `image_source_type` | `official_page_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 319 | `image_source_url` | `https://iso.fudan.edu.cn/isoenglish/82/fe/c17458a754430/page.htm` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 319 | `image_url` | `https://iso.fudan.edu.cn/_upload/tpl/15/dd/5597/template5597/images/logo.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 319 | `image_verified_at` | `2026-09-28 10:31:24.399794` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 320 | `image_evaluated_at` | `2026-09-27 18:30:54.828360` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 320 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 320 | `image_alt_text` | `Fudan University official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 320 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 320 | `image_source_type` | `official_page_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 320 | `image_source_url` | `https://iso.fudan.edu.cn/isoenglish/82/fd/c17458a754429/page.htm` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 320 | `image_url` | `https://iso.fudan.edu.cn/_upload/tpl/15/dd/5597/template5597/images/logo.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 320 | `image_verified_at` | `2026-09-28 10:31:25.341567` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 321 | `image_evaluated_at` | `2026-09-27 18:30:54.759225` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 321 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 321 | `image_alt_text` | `Fudan University official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 321 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 321 | `image_source_type` | `official_page_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 321 | `image_source_url` | `https://iso.fudan.edu.cn/isoenglish/82/fb/c17458a754427/page.htm` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 321 | `image_url` | `https://iso.fudan.edu.cn/_upload/tpl/15/dd/5597/template5597/images/logo.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 321 | `image_verified_at` | `2026-09-28 10:31:26.146637` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 323 | `image_source_type` | `official_logo` | `official_government` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 324 | `image_source_type` | `official_logo` | `official_government` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 325 | `catalogue_url` | NULL | `https://study.fsv.cuni.cz/how-to-apply/scholarships` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 325 | `image_evaluated_at` | `2026-09-27 18:31:19.505868` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 325 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 325 | `image_alt_text` | `Charles University official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 325 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 325 | `image_source_type` | `official_page_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 325 | `image_source_url` | `https://study.fsv.cuni.cz/czech-government-scholarship-developing-countries-for-the-ay-2027-28` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 325 | `image_url` | `https://study.fsv.cuni.cz/wp-content/uploads/sites/16/2025/04/logo-en.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 325 | `image_verified_at` | `2026-09-28 10:31:28.284767` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 326 | `image_evaluated_at` | `2026-10-04 07:32:05.164655` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 326 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 326 | `image_alt_text` | `Charles University` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 326 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 326 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 326 | `image_source_url` | `https://cuni.cz/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 326 | `image_url` | `https://cuni.cz/sablona/dist/img/UK-logo-horizontal-EN_hd.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 326 | `image_verified_at` | `2026-10-04 07:32:05.164655` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 327 | `catalogue_url` | NULL | `https://www.visegradfund.org/scholarships` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 327 | `image_evaluated_at` | `2026-09-27 18:31:32.683451` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 327 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 327 | `image_alt_text` | `Visegradfund.Org official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 327 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 327 | `image_source_type` | `official_page_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 327 | `image_source_url` | `https://www.visegradfund.org/visegrad-scholarship-program-apply` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 327 | `image_url` | `https://www.visegradfund.org/favicon.ico` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 327 | `image_verified_at` | `2026-09-28 10:31:31.871939` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 328 | `catalogue_url` | NULL | `https://international.cvut.cz/students/incoming-students/ctu-scholarships/` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 329 | `image_evaluated_at` | `2026-10-04 07:32:05.164655` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 329 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 329 | `image_alt_text` | `University of Copenhagen` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 329 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 329 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 329 | `image_source_url` | `https://studies.ku.dk/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 329 | `image_url` | `https://www.ku.dk/_assets/12a46eea25fd08a7277319b85c785b6b/Icons/Site/ucph-logo-en.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 329 | `image_verified_at` | `2026-10-04 07:32:05.164655` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 331 | `image_evaluated_at` | `2026-10-04 07:32:05.164655` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 331 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 331 | `image_alt_text` | `Technical University of Denmark` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 331 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 331 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 331 | `image_source_url` | `https://dtu.dk/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 331 | `image_url` | `https://www.dtu.dk/favicon.ico` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 331 | `image_verified_at` | `2026-10-04 07:32:05.164655` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 332 | `image_alt_text` | `Aalborg University` | `International Student Scholarship - official Aau.Dk image` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 332 | `image_kind` | `official_logo` | `official_banner` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 332 | `image_source_type` | `official_university` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 332 | `image_source_url` | `https://en.aau.dk/` | `https://www.en.aau.dk/contact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 332 | `image_url` | `https://en.aau.dk/apple-touch-icon.png` | `https://www.aau.dk/android-chrome-512x512.png` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 332 | `image_verified_at` | `2026-10-04 07:32:36.344477` | `2026-09-27 17:32:57.082669` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 332 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 336 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 336 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 336 | `image_alt_text` | `Tampere University` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 336 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 336 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 336 | `image_source_url` | `https://tuni.fi/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 336 | `image_url` | `https://www.tuni.fi/shared/favicon.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 336 | `image_verified_at` | `2026-10-04 07:32:36.344477` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 337 | `image_alt_text` | `University of Oulu` | `University of Oulu Tuition Fee Waivers and Early Bird Discount - official Oulu.Fi image` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 337 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-09-28 18:52:48.706884` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 337 | `image_kind` | `official_logo` | `program_image` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 337 | `image_source_type` | `official_university` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 337 | `image_source_url` | `https://oulu.fi/` | `https://www.oulu.fi/en/apply/how-apply/university-oulu-tuition-fees-and-scholarships-for-inte...` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 337 | `image_url` | `https://www.oulu.fi/sites/default/files/favicons/apple-touch-icon.png` | `https://media-cdn.oulu.fi/styles/main_image/s3/images/UniOulu_0685.jpg?itok=2BinPquK` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 337 | `image_verified_at` | `2026-10-04 07:32:36.344477` | `2026-09-27 17:32:47.673252` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 338 | `image_alt_text` | `University of Eastern Finland` | `University of Eastern Finland (UEF) Tuition Waivers (30% or 50%)` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 338 | `image_kind` | `official_logo` | `program_image` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 338 | `image_source_type` | `official_university` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 338 | `image_source_url` | `https://uef.fi/` | `https://www.uef.fi/en/tuition-fees-waivers-and-scholarships` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 338 | `image_url` | `https://www.uef.fi/themes/custom/uef/images/icons/src/LOGO_vaaka.svg` | `https://www.uef.fi/sites/default/files/styles/max_920/public/2020-08/UEF-Masters-Research-che...` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 338 | `image_verified_at` | `2026-10-04 07:32:36.344477` | `2026-09-27 17:42:57.466883` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 338 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 341 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 343 | `image_evaluated_at` | `2026-10-04 07:32:05.164655` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 343 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 343 | `image_alt_text` | `Nokia Foundation` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 343 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 343 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 343 | `image_source_url` | `https://nokiafoundation.com/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 343 | `image_url` | `https://images.squarespace-cdn.com/content/v1/66cebc3e7d2ad2668e6a4ade/2828ae83-1b29-4efd-ae6...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 343 | `image_verified_at` | `2026-10-04 07:32:05.164655` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 344 | `image_evaluated_at` | `2026-10-04 07:32:05.164655` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 344 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 344 | `image_alt_text` | `Nokia Foundation` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 344 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 344 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 344 | `image_source_url` | `https://nokiafoundation.com/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 344 | `image_url` | `https://images.squarespace-cdn.com/content/v1/66cebc3e7d2ad2668e6a4ade/2828ae83-1b29-4efd-ae6...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 344 | `image_verified_at` | `2026-10-04 07:32:05.164655` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 345 | `image_evaluated_at` | `2026-10-04 07:32:05.164655` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 345 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 345 | `image_alt_text` | `Nokia Foundation` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 345 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 345 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 345 | `image_source_url` | `https://nokiafoundation.com/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 345 | `image_url` | `https://images.squarespace-cdn.com/content/v1/66cebc3e7d2ad2668e6a4ade/2828ae83-1b29-4efd-ae6...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 345 | `image_verified_at` | `2026-10-04 07:32:05.164655` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 346 | `deadline_precision` | `application_dead` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 346 | `image_evaluated_at` | `2026-09-27 18:32:57.713759` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 346 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 346 | `image_alt_text` | `Marihe.Eu official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 346 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 346 | `image_source_type` | `official_page_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 346 | `image_source_url` | `https://www.marihe.eu/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 346 | `image_url` | `https://www.marihe.eu/wp-content/uploads/2025/06/cropped-LogoMaRIHE-1-scaled-1.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 346 | `image_verified_at` | `2026-09-28 10:31:58.579374` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 347 | `deadline_precision` | `application_dead` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 347 | `image_evaluated_at` | `2026-09-27 18:32:58.957651` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 347 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 347 | `image_alt_text` | `EU EMJMD programme official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 347 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 347 | `image_source_type` | `official_page_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 347 | `image_source_url` | `http://www.master-ediss.eu/scholarship/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 347 | `image_url` | `https://www.master-ediss.eu/wp-content/uploads/2020/11/cropped-Logo_Only_Transparent.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 347 | `image_verified_at` | `2026-09-28 10:32:00.601412` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 349 | `image_evaluated_at` | `2026-10-04 07:32:05.164655` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 349 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 349 | `image_alt_text` | `EMCL — Erasmus Mundus European Master in Clinical Linguistics (successor site; recorded host ...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 349 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 349 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 349 | `image_source_url` | `https://clinical-linguistics.eu/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 349 | `image_url` | `https://emcl.eu/img/logo-petrol.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 349 | `image_verified_at` | `2026-10-04 07:32:05.164655` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 351 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 352 | `image_evaluated_at` | `2026-09-27 18:32:56.792730` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 352 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 352 | `image_alt_text` | `Unknown provider (suspicious) official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 352 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 352 | `image_source_type` | `official_page_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 352 | `image_source_url` | `https://southafrica-france-scholarships.com` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 352 | `image_url` | `https://southafrica-france-scholarships.com/uploads/files/_AUTOx75_crop_center-center_none/so...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 352 | `image_verified_at` | `2026-09-28 10:32:03.298830` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 353 | `image_evaluated_at` | `2026-09-27 18:32:56.917558` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 353 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 353 | `image_alt_text` | `Pasteur.Fr official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 353 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 353 | `image_source_type` | `official_page_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 353 | `image_source_url` | `https://www.pasteur.fr/en/about-us/our-missions/education/training-programs/doctoral-programs...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 353 | `image_url` | `https://www.pasteur.fr/sites/default/files/medias/image/2026-07/sorbonne-university-logo-vect...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 353 | `image_verified_at` | `2026-09-28 10:32:04.584276` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 354 | `image_evaluated_at` | `2026-09-27 18:32:57.786483` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 354 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 354 | `image_alt_text` | `Sorbonne Université official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 354 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 354 | `image_source_type` | `official_page_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 354 | `image_source_url` | `https://inlife.sorbonne-universite.fr/en/actualites/international-mobility-grants-2026-2027` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 354 | `image_url` | `https://inlife.sorbonne-universite.fr/sites/default/files/media/2025-01/logo_initiative_scien...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 354 | `image_verified_at` | `2026-09-28 10:32:05.937803` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 355 | `image_evaluated_at` | `2026-09-27 18:33:00.350608` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 355 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 355 | `image_alt_text` | `Sciencespo.Fr official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 355 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 355 | `image_source_type` | `official_page_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 355 | `image_source_url` | `https://www.sciencespo.fr/students/en/fees-funding/bursaries-financial-aid/mastercard-foundat...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 355 | `image_url` | `https://www.sciencespo.fr/students/en/static/4e8c8b615cdf25da682418334c3751b6/sciencespo_logo...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 355 | `image_verified_at` | `2026-09-28 10:32:08.304226` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 356 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 357 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 362 | `image_source_type` | `official_page_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 367 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 368 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 369 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 373 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 374 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 375 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 376 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 377 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 378 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 379 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 380 | `image_evaluated_at` | `2026-09-27 18:33:49.398880` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 380 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 380 | `image_alt_text` | `Rotary Yoneyama.Or.Jp official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 380 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 380 | `image_source_type` | `official_page_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 380 | `image_source_url` | `https://www.rotary-yoneyama.or.jp/english/overseas` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 380 | `image_url` | `https://www.rotary-yoneyama.or.jp/content/img/favicon.ico` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 380 | `image_verified_at` | `2026-09-28 10:32:19.020103` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 382 | `deadline_precision` | `application_dead` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 382 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 384 | `image_evaluated_at` | NULL | `2026-10-04T11:18:52.082139+00:00` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 384 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 384 | `image_alt_text` | `Erasmus Trustfonds Scholarship / TSH Changemaker Scholarship` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 384 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 384 | `image_source_type` | `official_provider` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 384 | `image_source_url` | `https://www.eur.nl/en/erasmusmc/programmes/practical-matters/scholarships/erasmus-trustfonds-...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 384 | `image_url` | `https://www.eur.nl/favicon-16x16.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 384 | `image_verified_at` | `2026-09-27 19:04:06.142735` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 385 | `catalogue_url` | NULL | `https://www.universiteitleiden.nl/en/education/admission-and-application/bachelors/admission-...` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 386 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 388 | `catalogue_url` | NULL | `https://www.nwo.nl/en/researchprogrammes` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 388 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 389 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 390 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 391 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 393 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 394 | `image_evaluated_at` | `2026-10-04 07:32:05.164655` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 394 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 394 | `image_alt_text` | `Tilburg University` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 394 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 394 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 394 | `image_source_url` | `https://tilburguniversity.edu/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 394 | `image_url` | `https://www.tilburguniversity.edu/themes/custom/tiu/images/icons/apple-touch-icon.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 394 | `image_verified_at` | `2026-10-04 07:32:05.164655` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 396 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 398 | `image_alt_text` | `University of Amsterdam` | `University of Amsterdam Scholarships` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 398 | `image_kind` | `official_logo` | `program_image` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 398 | `image_source_type` | `official_university` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 398 | `image_source_url` | `https://uva.nl/` | `https://www.uva.nl/scholarships` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 398 | `image_url` | `https://www.uva.nl/webfiles/1779862044324/_favicon/apple-touch-icon.png` | `https://www.uva.nl/binaries/_ht_1701875274174/1200x630-jpg/content/gallery/faculteiten-en-die...` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 398 | `image_verified_at` | `2026-10-04 07:32:36.344477` | `2026-09-27 19:09:02.728053` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 398 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 400 | `image_source_type` | `official_logo` | `official_government` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 401 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 405 | `image_evaluated_at` | `2026-10-04 07:32:05.164655` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 405 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 405 | `image_alt_text` | `University of Auckland` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 405 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 405 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 405 | `image_source_url` | `https://auckland.ac.nz/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 405 | `image_url` | `https://www.auckland.ac.nz/etc.clientlibs/uoa-digital/clientlibs/resources/svg/favicon.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 405 | `image_verified_at` | `2026-10-04 07:32:05.164655` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 406 | `image_evaluated_at` | `2026-10-04 07:32:05.164655` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 406 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 406 | `image_alt_text` | `University of Auckland` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 406 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 406 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 406 | `image_source_url` | `https://auckland.ac.nz/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 406 | `image_url` | `https://www.auckland.ac.nz/etc.clientlibs/uoa-digital/clientlibs/resources/svg/favicon.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 406 | `image_verified_at` | `2026-10-04 07:32:05.164655` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 407 | `image_alt_text` | `University of Waikato` | `8094e wms leadership summit photography 2` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 407 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-09-28 18:52:48.706922` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 407 | `image_kind` | `official_logo` | `program_image` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 407 | `image_source_type` | `official_university` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 407 | `image_source_url` | `https://waikato.ac.nz/` | `https://www.waikato.ac.nz/scholarships` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 407 | `image_url` | `https://www.waikato.ac.nz/_resources/themes/app/dist/icons/logo.svg` | `https://www.waikato.ac.nz/assets/Uploads/About-us/Faculties-and-schools/Waikato-Management-Sc...` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 407 | `image_verified_at` | `2026-10-04 07:32:36.344477` | `2026-09-27 19:10:47.135573` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 412 | `image_source_type` | `official_page_logo` | `official_government` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 415 | `image_source_type` | `official_page_logo` | `official_government` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 416 | `image_source_type` | `official_page_logo` | `official_government` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 417 | `image_source_type` | `official_page_logo` | `official_government` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 418 | `image_source_type` | `official_page_logo` | `official_government` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 419 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 420 | `image_source_type` | `official_page_logo` | `official_government` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 421 | `image_source_type` | `official_page_logo` | `official_government` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 422 | `image_source_type` | `official_page_logo` | `official_government` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 424 | `image_source_type` | `official_page_logo` | `official_government` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 425 | `image_source_type` | `official_page_logo` | `official_government` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 427 | `image_source_type` | `official_page_logo` | `official_government` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 437 | `catalogue_url` | NULL | `https://www.a-star.edu.sg/scholarships` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 437 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 437 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 437 | `image_alt_text` | `A STAR Singapore` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 437 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 437 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 437 | `image_source_url` | `https://a-star.edu.sg/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 437 | `image_url` | `https://www.a-star.edu.sg/api/media/867ab78f-c433-4489-9de0-51f3937f384c/favicon.ico` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 437 | `image_verified_at` | `2026-10-04 07:32:36.344477` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 438 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 438 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 438 | `image_alt_text` | `A STAR Singapore` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 438 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 438 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 438 | `image_source_url` | `https://a-star.edu.sg/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 438 | `image_url` | `https://www.a-star.edu.sg/api/media/867ab78f-c433-4489-9de0-51f3937f384c/favicon.ico` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 438 | `image_verified_at` | `2026-10-04 07:32:36.344477` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 440 | `catalogue_url` | NULL | `https://www.ntu.edu.sg/about-us/sustainability/sustainability-education/undergraduate-programmes` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 441 | `catalogue_url` | NULL | `https://www.ntu.edu.sg/about-us/sustainability/sustainability-education/undergraduate-programmes` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 444 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 445 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 447 | `image_source_type` | `official_page_logo` | `official_university` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 448 | `image_evaluated_at` | `2026-10-04 07:32:05.164655` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 448 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 448 | `image_alt_text` | `Singapore University of Social Sciences` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 448 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 448 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 448 | `image_source_url` | `https://suss.edu.sg/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 448 | `image_url` | `https://www.suss.edu.sg/assets/images/logo.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 448 | `image_verified_at` | `2026-10-04 07:32:05.164655` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 449 | `image_evaluated_at` | `2026-10-04 07:32:05.164655` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 449 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 449 | `image_alt_text` | `Singapore University of Social Sciences` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 449 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 449 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 449 | `image_source_url` | `https://suss.edu.sg/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 449 | `image_url` | `https://www.suss.edu.sg/assets/images/logo.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 449 | `image_verified_at` | `2026-10-04 07:32:05.164655` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 450 | `official_updates_url` | NULL | `https://www.ntu.edu.sg/about-us/sustainability/news-publications` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 451 | `deadline_precision` | `application_dead` | `unknown` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 451 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 452 | `image_alt_text` | `KTH Royal Institute of Technology` | `KTH Scholarship` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 452 | `image_kind` | `official_logo` | `program_image` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 452 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 452 | `image_source_url` | `https://kth.se/` | `https://www.kth.se/en/studies/master/admissions/scholarships/kth-scholarship-1.72827` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 452 | `image_url` | `https://www.kth.se/polopoly_fs/1.1273722.1692876353!/image/apple-touch-icon-KTH-logo-180x180.png` | `https://www.kth.se/polopoly_fs/1.1210960.1669889543!/image/Winter%20scholarship-16x9.jpg` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 452 | `image_verified_at` | `2026-10-04 07:32:36.344477` | `2026-09-27 19:34:59.652324` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 452 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 453 | `deadline_precision` | `application_dead` | `unknown` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 453 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 454 | `deadline_precision` | `application_dead` | `unknown` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 455 | `deadline_precision` | `application_dead` | `unknown` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 457 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 457 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 457 | `image_alt_text` | `KTH Royal Institute of Technology` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 457 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 457 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 457 | `image_source_url` | `https://kth.se/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 457 | `image_url` | `https://www.kth.se/polopoly_fs/1.1273722.1692876353!/image/apple-touch-icon-KTH-logo-180x180.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 457 | `image_verified_at` | `2026-10-04 07:32:36.344477` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 458 | `image_source_type` | `official_page_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 459 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 460 | `deadline_precision` | `application_dead` | `unknown` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 460 | `image_alt_text` | `Swiss National Science Foundation` | `SNF Postdoc.Mobility` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 460 | `image_kind` | `official_logo` | `program_image` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 460 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 460 | `image_source_url` | `https://snf.ch/` | `https://www.snf.ch/en/XIZpfY3iVS5KRRoD/funding/careers/postdoc-mobility` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 460 | `image_url` | `https://www.snf.ch/favicon/favicon-32x32.png` | `https://media.snf.ch/imgproxy/1200/rs:fit:1200:675:0/g:fp:0.5:0.5/q:75/fn:undefined/aHR0cHM6L...` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 460 | `image_verified_at` | `2026-10-04 07:32:36.344477` | `2026-09-28 05:17:16.109625` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 460 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 461 | `deadline_precision` | `application_dead` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 461 | `image_alt_text` | `Swiss National Science Foundation` | `SNF Ambizione` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 461 | `image_kind` | `official_logo` | `program_image` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 461 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 461 | `image_source_url` | `https://snf.ch/` | `https://www.snf.ch/en/N18L3oGWomTSSGkF/funding/careers/ambizione` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 461 | `image_url` | `https://www.snf.ch/favicon/favicon-32x32.png` | `https://media.snf.ch/imgproxy/1200/rs:fit:1200:675:0/g:fp:0.5:0.5/q:75/fn:undefined/aHR0cHM6L...` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 461 | `image_verified_at` | `2026-10-04 07:32:36.344477` | `2026-09-28 05:16:25.795972` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 461 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 462 | `deadline_precision` | `application_dead` | `unknown` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 462 | `image_alt_text` | `Swiss National Science Foundation` | `SNF Starting Grants` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 462 | `image_kind` | `official_logo` | `official_banner` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 462 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 462 | `image_source_url` | `https://snf.ch/` | `https://www.snf.ch/de/w728UqT1Yw256Mz2/foerderung/karrieren/snsf-starting-grants` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 462 | `image_url` | `https://www.snf.ch/favicon/favicon-32x32.png` | `https://media.snf.ch/imgproxy/1200/rs:fit:1200:675:0/g:fp:0.5:0.5/q:75/fn:undefined/aHR0cHM6L...` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 462 | `image_verified_at` | `2026-10-04 07:32:36.344477` | `2026-09-28 05:16:05.249695` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 462 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 463 | `deadline_precision` | `application_dead` | `unknown` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 464 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 465 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 469 | `image_source_type` | `official_page_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 470 | `image_source_type` | `official_page_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 471 | `deadline_precision` | `application_dead` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 472 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 474 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 475 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 475 | `image_evaluated_at` | `2026-09-28 05:16:46.247543` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 475 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 475 | `image_alt_text` | `Worldbank.Org official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 475 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 475 | `image_source_type` | `official_page_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 475 | `image_source_url` | `https://www.worldbank.org/en/programs/scholarships/jj-wbgsp` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 475 | `image_url` | `https://www.worldbank.org/content/dam/wbr-redesign/logos/wbg-favicon.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 475 | `image_verified_at` | `2026-09-28 10:33:20.058247` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 476 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 477 | `catalogue_url` | NULL | `https://www.borenawards.org/eligible-programs` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 477 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 478 | `catalogue_url` | NULL | `https://www.phikappaphi.org/about/news/2026/09/10/phi-kappa-phi-restructures-award-programs-i...` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 478 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 479 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 480 | `image_evaluated_at` | `2026-10-04 07:32:05.164655` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 480 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 480 | `image_alt_text` | `Harvard College` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 480 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 480 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 480 | `image_source_url` | `https://college.harvard.edu/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 480 | `image_url` | `https://www.college.harvard.edu/themes/custom/harvard_college/assets/dependencies/favicon/app...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 480 | `image_verified_at` | `2026-10-04 07:32:05.164655` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 482 | `image_evaluated_at` | `2026-10-04 07:32:05.164655` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 482 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 482 | `image_alt_text` | `MIT Schwarzman College` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 482 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 482 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 482 | `image_source_url` | `https://sfs.mit.edu/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 482 | `image_url` | `https://sfs.mit.edu/wp-content/themes/custom/mit-sfs-theme/static/img/social-logo.jpg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 482 | `image_verified_at` | `2026-10-04 07:32:05.164655` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 486 | `image_evaluated_at` | `2026-10-04 07:32:05.164655` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 486 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 486 | `image_alt_text` | `Google Research` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 486 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 486 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 486 | `image_source_url` | `https://research.google/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 486 | `image_url` | `https://www.gstatic.com/images/branding/googleg_gradient/1x/googleg_gradient_standard_20dp.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 486 | `image_verified_at` | `2026-10-04 07:32:05.164655` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 490 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 491 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 492 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 493 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 494 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 495 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 496 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 497 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 498 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 498 | `image_source_type` | `official_organization` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 500 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 500 | `image_source_type` | `official_ngo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 501 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 501 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 501 | `image_alt_text` | `Deutschlandstipendium` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 501 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 501 | `image_source_type` | `official_government` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 501 | `image_source_url` | `https://www.deutschlandstipendium.de/deutschlandstipendium/de/home/home_node.html` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 501 | `image_url` | `https://www.deutschlandstipendium.de/SiteGlobals/Frontend/Images/icons/deutschlandstipendium/...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 501 | `image_verified_at` | `2026-10-01 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 502 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 502 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 502 | `image_alt_text` | `Friedrich-Ebert-Stiftung` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 502 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 502 | `image_source_type` | `official_ngo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 502 | `image_source_url` | `https://www.fes.de/studienfoerderung` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 502 | `image_url` | `https://www.fes.de/_assets/9cec337f7d9b8a112ff7bc4a21068e10/Icons/General/logo-fes.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 502 | `image_verified_at` | `2026-10-01 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 503 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 503 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 503 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 503 | `image_alt_text` | `Agence nationale de la recherche (ANR)` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 503 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 503 | `image_source_type` | `official_government` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 503 | `image_source_url` | `https://anr.fr/fr/france-2030/france2030/call/france-2030-pepr-gfm-grands-fonds-marins-appel-...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 503 | `image_url` | `https://anr.fr/typo3conf/ext/anr_skin/Resources/Public/assets/img/anr-logo-2021-complet.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 503 | `image_verified_at` | `2026-10-01 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 504 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 504 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 504 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 504 | `image_alt_text` | `Agence nationale de la recherche (ANR)` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 504 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 504 | `image_source_type` | `official_government` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 504 | `image_source_url` | `https://anr.fr/fr/france-2030/france2030/call/france-2030-pepr-propsy-psychiatrie-de-precisio...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 504 | `image_url` | `https://anr.fr/typo3conf/ext/anr_skin/Resources/Public/assets/img/anr-logo-2021-complet.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 504 | `image_verified_at` | `2026-10-01 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 505 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 505 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 505 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 505 | `image_alt_text` | `M-ERA.NET programme logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 505 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 505 | `image_source_type` | `official_government` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 505 | `image_source_url` | `https://anr.fr/fr/detail/call/appel-a-projets-m-eranet-202627-science-et-ingenierie-des-mater...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 505 | `image_url` | `https://anr.fr/fileadmin/images/logos/m-era.net-2022.jpg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 505 | `image_verified_at` | `2026-10-01 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 506 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 507 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 507 | `image_evaluated_at` | `2026-10-04 09:36:50.791193` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 507 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 507 | `image_alt_text` | `Fonds National de la Recherche (Luxembourg National Research Fund)` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 507 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 507 | `image_source_type` | `official_government` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 507 | `image_source_url` | `https://www.fnr.lu/logo/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 507 | `image_url` | `https://www.fnr.lu/wp-content/uploads/2023/07/FNR_LOGO.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 507 | `image_verified_at` | `2026-10-01 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 509 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 509 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 509 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 509 | `image_alt_text` | `Estonian Education and Youth Board (Haridus- ja Noorteamet)` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 509 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 509 | `image_source_type` | `official_government` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 509 | `image_source_url` | `https://www.harno.ee/en/scholarships-and-grants/scholarships-studying-and-working-estonia/sch...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 509 | `image_url` | `https://www.harno.ee/sites/default/files/HARNO%20ENG.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 509 | `image_verified_at` | `2026-10-01 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 510 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 511 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 511 | `image_evaluated_at` | `2026-10-04 08:53:39.244242` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 511 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 511 | `image_alt_text` | `University of Canterbury (UC)` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 511 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 511 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 511 | `image_source_url` | `https://www.canterbury.ac.nz/study/getting-started/scholarships/doctoral-scholarships/uc-doct...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 511 | `image_url` | `https://www.canterbury.ac.nz/content/dam/uoc-restricted/icons/apple-icon-180x180.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 511 | `image_verified_at` | `2026-10-04 08:53:39.244242` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 512 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 512 | `image_evaluated_at` | `2026-10-04 08:53:39.244242` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 512 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 512 | `image_alt_text` | `Charles Darwin University crest` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 512 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 512 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 512 | `image_source_url` | `https://www.cdu.edu.au/international/how-apply/scholarships` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 512 | `image_url` | `https://www.cdu.edu.au/themes/cdu_theme/favicon/apple-touch-icon.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 512 | `image_verified_at` | `2026-10-04 08:53:39.244242` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 517 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 517 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 517 | `image_alt_text` | `Indian Council of Social Science Research emblem` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 517 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 517 | `image_source_type` | `official_government` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 517 | `image_source_url` | `https://icssr.org/participation-international-seminar-abroad` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 517 | `image_url` | `https://www.icssr.org/themes/custom/icssr/images/Emblem.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 517 | `image_verified_at` | `2026-10-01 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 518 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 518 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 518 | `image_alt_text` | `Indian Council of Social Science Research emblem` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 518 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 518 | `image_source_type` | `official_government` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 518 | `image_source_url` | `https://icssr.org/data-collection-abroad` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 518 | `image_url` | `https://www.icssr.org/themes/custom/icssr/images/Emblem.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 518 | `image_verified_at` | `2026-10-01 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 519 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 519 | `image_evaluated_at` | `2026-10-04 07:32:05.164655` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 519 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 519 | `image_alt_text` | `University of Sharjah official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 519 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 519 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 519 | `image_source_url` | `https://www.sharjah.ac.ae/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 519 | `image_url` | `https://www.sharjah.ac.ae/-/media/project/uos/sites/uos/others/navigation-logos/brand-logo-bl...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 519 | `image_verified_at` | `2026-10-04 07:32:05.164655` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 521 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 521 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 522 | `image_evaluated_at` | `2026-10-04 08:53:40.036011` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 522 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 522 | `image_alt_text` | `African Institute for Mathematical Sciences (AIMS) South Africa` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 522 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 522 | `image_source_type` | `official_institution` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 522 | `image_source_url` | `https://aims.ac.za/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 522 | `image_url` | `https://aims.ac.za/images/logo_hu4600616865369929826.webp` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 522 | `image_verified_at` | `2026-10-01 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 524 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 524 | `image_evaluated_at` | `2026-10-04 09:43:31.806439` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 524 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 524 | `image_alt_text` | `University of Westminster` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 524 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 524 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 524 | `image_source_url` | `https://www.westminster.ac.uk/study/fees-and-funding/scholarships/postgraduate-sanctuary-scho...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 524 | `image_url` | `https://www.westminster.ac.uk/themes/uow_theme/images/navbar-westminster-logo.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 524 | `image_verified_at` | `2026-10-04 09:43:31.806439` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 526 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 527 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 529 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 530 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 530 | `image_evaluated_at` | `2026-10-04 07:32:05.164655` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 530 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 530 | `image_alt_text` | `A STAR Singapore` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 530 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 530 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 530 | `image_source_url` | `https://a-star.edu.sg/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 530 | `image_url` | `https://www.a-star.edu.sg/api/media/867ab78f-c433-4489-9de0-51f3937f384c/favicon.ico` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 530 | `image_verified_at` | `2026-10-04 07:32:05.164655` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 532 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 532 | `image_source_type` | `official_organization` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 533 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 534 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 535 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 535 | `image_evaluated_at` | `2026-10-04 09:36:50.058479` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 535 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 535 | `image_alt_text` | `Conservation Leadership Programme` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 535 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 535 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 535 | `image_source_url` | `https://www.conservationleadershipprogramme.org/awards-opportunities/team-awards/future-conse...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 535 | `image_url` | `https://www.conservationleadershipprogramme.org/wp-content/uploads/2025/01/clp-icon-200x200.jpg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 535 | `image_verified_at` | `2026-10-04 09:36:50.058479` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 536 | `image_evaluated_at` | `2026-10-04 08:53:40.036011` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 536 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 536 | `image_alt_text` | `The Rufford Foundation` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 536 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 536 | `image_source_type` | `official_charity` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 536 | `image_source_url` | `https://www.rufford.org/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 536 | `image_url` | `https://www.rufford.org/static/images/rufford-logo-menu-hr-360x155.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 536 | `image_verified_at` | `2026-10-01 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 537 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 537 | `image_evaluated_at` | `2026-10-04 09:36:50.058479` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 537 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 537 | `image_alt_text` | `Whitley Fund for Nature` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 537 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 537 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 537 | `image_source_url` | `https://whitleyaward.org/apply-for-conservation-funding/apply-for-a-whitley-award/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 537 | `image_url` | `https://whitleyaward.org/content/themes/whitleyaward.org/touch-icon-iphone-retina.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 537 | `image_verified_at` | `2026-10-04 09:36:50.058479` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 538 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 538 | `image_source_type` | `official_ngo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 539 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 539 | `image_source_type` | `official_ngo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 540 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 540 | `image_source_type` | `official_ngo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 542 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 542 | `image_source_type` | `official_ngo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 543 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 544 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 544 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 544 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 544 | `image_alt_text` | `Friedrich Ebert Stiftung` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 544 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 544 | `image_source_type` | `official_government` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 544 | `image_source_url` | `https://www.fes.de/studienfoerderung/bewerbung` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 544 | `image_url` | `https://www.fes.de/_assets/9cec337f7d9b8a112ff7bc4a21068e10/Icons/General/logo-fes.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 544 | `image_verified_at` | `2026-10-01 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 545 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 547 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 548 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 548 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 548 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 548 | `image_alt_text` | `Agence nationale de la recherche` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 548 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 548 | `image_source_type` | `official_government` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 548 | `image_source_url` | `https://anr.fr/fr/detail/call/aapg-appel-a-projets-generique-2027/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 548 | `image_url` | `https://anr.fr/typo3conf/ext/anr_skin/Resources/Public/img/anr-logo-2021-complet.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 548 | `image_verified_at` | `2026-10-01 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 549 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 549 | `image_evaluated_at` | `2026-10-04 08:53:40.036011` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 549 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 549 | `image_alt_text` | `Inria` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 549 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 549 | `image_source_type` | `official_government` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 549 | `image_source_url` | `https://jobs.inria.fr/public/classic/en/offres/2026-10352` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 549 | `image_url` | `https://jobs.inria.fr/images/inr_logo_blanc.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 549 | `image_verified_at` | `2026-10-01 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 550 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 550 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 550 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 550 | `image_alt_text` | `Institut Pascal` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 550 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 550 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 550 | `image_source_url` | `https://www.institut-pascal.universite-paris-saclay.fr/en/proposal-submissions` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 550 | `image_url` | `https://www.institut-pascal.universite-paris-saclay.fr/sites/default/files/2021-07/Pascal-h.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 550 | `image_verified_at` | `2026-10-01 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 551 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 552 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 553 | `image_source_type` | `official_ngo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 554 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 555 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 556 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 557 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 557 | `image_evaluated_at` | `2026-10-04 08:53:40.036011` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 557 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 557 | `image_alt_text` | `King Abdullah University of Science and Technology` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 557 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 557 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 557 | `image_source_url` | `https://admissions.kaust.edu.sa/fees-funding` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 557 | `image_url` | `https://admissions.kaust.edu.sa/images/default-source/interface/site-branding/KAUST_Logo.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 557 | `image_verified_at` | `2026-10-01 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 558 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 558 | `image_evaluated_at` | `2026-10-04 09:36:50.058479` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 558 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 558 | `image_alt_text` | `MBZUAI` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 558 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 558 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 558 | `image_source_url` | `https://mbzuai.ac.ae/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 558 | `image_url` | `https://mbzuai.ac.ae/apple-touch-icon.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 558 | `image_verified_at` | `2026-10-04 09:36:50.058479` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 559 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 560 | `image_evaluated_at` | `2026-10-04 07:32:36.344477` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 560 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 560 | `image_alt_text` | `United Arab Emirates Ministry of Foreign Affairs` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 560 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 560 | `image_source_type` | `official_government` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 560 | `image_source_url` | `https://www.mofa.gov.ae/en/Scholarship` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 560 | `image_url` | `https://www.mofa.gov.ae/MOFAAssets/images/logo.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 560 | `image_verified_at` | `2026-10-01 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 561 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 561 | `image_source_type` | `official_ngo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 562 | `image_evaluated_at` | `2026-10-04 09:36:50.058479` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 562 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 562 | `image_alt_text` | `Wellcome` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 562 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 562 | `image_source_type` | `official_ngo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 562 | `image_source_url` | `https://wellcome.org/grant-funding/schemes/early-career-awards` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 562 | `image_url` | `https://wellcome.org/icons/apple-touch-icon.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 562 | `image_verified_at` | `2026-10-01 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 563 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 564 | `deadline_precision` | `day` | `exact` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 564 | `image_evaluated_at` | `2026-10-04 07:32:05.164655` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 564 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 564 | `image_alt_text` | `World Bank` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 564 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 564 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 564 | `image_source_url` | `https://worldbank.org/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 564 | `image_url` | `https://www.worldbank.org/content/dam/wbr-redesign/logos/wbg-favicon.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 564 | `image_verified_at` | `2026-10-04 07:32:05.164655` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 565 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 566 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 567 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 568 | `image_evaluated_at` | `2026-10-04 08:04:50.624382` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 568 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 568 | `image_alt_text` | `Türkiye Scholarships (Türkiye Bursları) official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 568 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 568 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 568 | `image_source_url` | `https://www.turkiyeburslari.gov.tr/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 568 | `image_url` | `https://www.turkiyeburslari.gov.tr/YTB/images/logo/tb-logo.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 568 | `image_verified_at` | `2026-10-04 08:04:50.624382` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 570 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 571 | `image_evaluated_at` | `2026-10-04 08:18:50.422113` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 571 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 571 | `image_alt_text` | `ARES (Fédération Wallonie-Bruxelles)` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 571 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 571 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 571 | `image_source_url` | `https://www.ares-ac.be/fr/bourses` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 571 | `image_url` | `https://www.ares-ac.be/themes/custom/frontend/favicon.ico` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 571 | `image_verified_at` | `2026-10-04 08:18:50.422113` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 572 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 574 | `image_evaluated_at` | `2026-10-04 08:18:50.422113` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 574 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 574 | `image_alt_text` | `University of Leeds` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 574 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 574 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 574 | `image_source_url` | `https://www.leeds.ac.uk/scholarship/12/masters-international-excellence-scholarships` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 574 | `image_url` | `https://jaducdn.leeds.ac.uk/uol-ds/1.0.21/favicons/favicon.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 574 | `image_verified_at` | `2026-10-04 08:18:50.422113` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 577 | `image_evaluated_at` | `2026-10-04 08:18:50.422113` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 577 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 577 | `image_alt_text` | `European University Institute logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 577 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 577 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 577 | `image_source_url` | `https://www.eui.eu/apply?id=max-weber-fellowships` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 577 | `image_url` | `https://www.eui.eu/web-production/code/assets/img/logo-eui.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 577 | `image_verified_at` | `2026-10-04 08:18:50.422113` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 578 | `image_evaluated_at` | `2026-10-04 08:18:50.422113` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 578 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 578 | `image_alt_text` | `European Association for the Study of the Liver (EASL) logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 578 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 578 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 578 | `image_source_url` | `https://easl.eu/fellowship/mobility-research-fellowship-programme/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 578 | `image_url` | `https://easl.eu/wp-content/uploads/2025/10/logo.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 578 | `image_verified_at` | `2026-10-04 08:18:50.422113` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 579 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 580 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 581 | `image_evaluated_at` | `2026-10-04 08:18:50.422113` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 581 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 581 | `image_alt_text` | `European University Institute logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 581 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 581 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 581 | `image_source_url` | `https://www.eui.eu/apply?id=max-weber-fellowships` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 581 | `image_url` | `https://www.eui.eu/web-production/code/assets/img/logo-eui.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 581 | `image_verified_at` | `2026-10-04 08:18:50.422113` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 582 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 583 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 584 | `image_evaluated_at` | `2026-10-04 08:18:50.422113` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 584 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 584 | `image_alt_text` | `Maastricht University` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 584 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 584 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 584 | `image_source_url` | `https://maastrichtuniversity.nl/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 584 | `image_url` | `https://www.maastrichtuniversity.nl/themes/custom/um_corporate/favicon.ico` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 584 | `image_verified_at` | `2026-10-04 08:18:50.422113` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 585 | `image_evaluated_at` | `2026-10-04 08:18:50.422113` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 585 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 585 | `image_alt_text` | `Study in Latvia` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 585 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 585 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 585 | `image_source_url` | `https://studyinlatvia.lv/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 585 | `image_url` | `https://studyinlatvia.lv/favicon.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 585 | `image_verified_at` | `2026-10-04 08:18:50.422113` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 589 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 590 | `image_evaluated_at` | `2026-10-04 09:43:31.806439` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 590 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 590 | `image_alt_text` | `SECIHTI - Secretaría de Ciencia, Humanidades y Tecnología` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 590 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 590 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 590 | `image_source_url` | `https://secihti.mx/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 590 | `image_url` | `https://secihti.mx/wp-content/uploads/2025/03/logo_secihti_vertical_color.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 590 | `image_verified_at` | `2026-10-04 09:43:31.806439` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 591 | `image_evaluated_at` | `2026-10-04 08:18:51.116404` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 591 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 591 | `image_alt_text` | `Horatio Alger Association of Distinguished Americans` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 591 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 591 | `image_source_type` | `official_scholarship` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 591 | `image_source_url` | `https://horatioalger.org/scholarships-and-services/undergraduate-scholarships/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 591 | `image_url` | `https://horatioalger.org/favicon.ico` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 591 | `image_verified_at` | `2026-10-04 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 594 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 595 | `image_evaluated_at` | `2026-10-04 08:18:51.116404` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 595 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 595 | `image_alt_text` | `Fundacao Oswaldo Cruz (Fiocruz) emblem - white Maltese cross on a red field` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 595 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 595 | `image_source_type` | `official_scholarship` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 595 | `image_source_url` | `https://fiocruz.br/sites/fiocruz.br/files/marca-fiocruz-redes-sociais.jpg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 595 | `image_url` | `https://fiocruz.br/sites/fiocruz.br/files/marca-fiocruz-redes-sociais.jpg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 595 | `image_verified_at` | `2026-10-04 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 596 | `image_evaluated_at` | NULL | `2026-10-04T11:18:52.082139+00:00` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 596 | `image_evaluation_status` | NULL | `invalid_candidates` | restored pre-repair value | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 596 | `image_alt_text` | `CALAS - Maria Sibylla Merian Center wordmark with the interlocked cross mark` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 596 | `image_source_type` | `official_scholarship` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 596 | `image_source_url` | `http://calas.lat/sites/default/files/imagotipo_color.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 596 | `image_url` | `http://calas.lat/sites/default/files/imagotipo_color.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 596 | `image_verified_at` | `2026-10-04 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 597 | `image_evaluated_at` | `2026-10-04 09:43:31.806439` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 597 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 597 | `image_alt_text` | `PRONABEC - Programa Nacional de Becas y Crédito Educativo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 597 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 597 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 597 | `image_source_url` | `https://www.pronabec.gob.pe/beca-generacion-bicentenario/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 597 | `image_url` | `https://www.pronabec.gob.pe/wp-content/uploads/2022/07/Pronabec-Logo-2020.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 597 | `image_verified_at` | `2026-10-04 09:43:31.806439` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 598 | `image_evaluated_at` | `2026-10-04 09:43:31.806439` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 598 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 598 | `image_alt_text` | `Banco de la República de Colombia` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 598 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 598 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 598 | `image_source_url` | `https://www.banrep.gov.co/es/contenidos/programas-estudios-el-exterior` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 598 | `image_url` | `https://www.banrep.gov.co/sites/default/files/favicon.ico` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 598 | `image_verified_at` | `2026-10-04 09:43:31.806439` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 599 | `image_evaluated_at` | `2026-10-04 09:43:31.806439` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 599 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 599 | `image_alt_text` | `Instituto Riva-Aguero wordmark with the house and column device` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 599 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 599 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 599 | `image_source_url` | `https://ira.pucp.edu.pe/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 599 | `image_url` | `https://ira.pucp.edu.pe/wp-content/uploads/2020/04/logo-ira.jpg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 599 | `image_verified_at` | `2026-10-04 09:43:31.806439` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 600 | `image_evaluated_at` | `2026-10-04 09:43:31.806439` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 600 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 600 | `image_alt_text` | `Becas Colombia Biodiversa - Fundación Alejandro Ángel Escobar` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 600 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 600 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 600 | `image_source_url` | `https://www.faae.org.co/colombiabiodiversa/instrucciones-para-la-aplicacion/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 600 | `image_url` | `https://www.faae.org.co/colombiabiodiversa/wp-content/uploads/2025/09/Becas-Colombia-Biodiver...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 600 | `image_verified_at` | `2026-10-04 09:43:31.806439` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 601 | `image_evaluated_at` | `2026-10-04 09:43:31.806439` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 601 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 601 | `image_alt_text` | `CONICET - Consejo Nacional de Investigaciones Científicas y Técnicas` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 601 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 601 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 601 | `image_source_url` | `https://convocatorias.conicet.gov.ar/becas/convocatoria-vigente/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 601 | `image_url` | `https://convocatorias.conicet.gov.ar/wp-content/uploads/logo-CONICET_opt.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 601 | `image_verified_at` | `2026-10-04 09:43:31.806439` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 602 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 603 | `image_evaluated_at` | `2026-10-04 09:43:31.806439` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 603 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 603 | `image_alt_text` | `gov.br - Governo Federal do Brasil` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 603 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 603 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 603 | `image_source_url` | `https://www.gov.br/mre/en/subjects/culture-and-education/educational-themes/study-opportuniti...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 603 | `image_url` | `https://www.gov.br/mre/logo.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 603 | `image_verified_at` | `2026-10-04 09:43:31.806439` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 604 | `image_evaluated_at` | `2026-10-04 08:18:50.422113` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 604 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 604 | `image_alt_text` | `Universidad de Chile` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 604 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 604 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 604 | `image_source_url` | `https://uchile.cl/convocatorias/37944/beca-universidad-de-chile` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 604 | `image_url` | `https://uchile.cl/.resources/portal-uchile/images/escudo-uchile-horizontal-color.jpg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 604 | `image_verified_at` | `2026-10-04 08:18:50.422113` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 605 | `image_evaluated_at` | `2026-10-04 08:18:50.422113` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 605 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 605 | `image_alt_text` | `Banco de la República de Colombia` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 605 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 605 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 605 | `image_source_url` | `https://www.banrep.gov.co/es/contenidos/programas-estudios-el-exterior` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 605 | `image_url` | `https://www.banrep.gov.co/sites/default/files/favicon.ico` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 605 | `image_verified_at` | `2026-10-04 08:18:50.422113` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 606 | `image_evaluated_at` | `2026-10-04 08:18:51.116404` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 606 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 606 | `image_alt_text` | `Higher Education Commission of Pakistan logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 606 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 606 | `image_source_type` | `official_government` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 606 | `image_source_url` | `https://www.hec.gov.pk/english/scholarshipsgrants/OSSPhase-III/Pages/default.aspx` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 606 | `image_url` | `https://www.hec.gov.pk/Style%20Library/HEC/images/header-logo.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 606 | `image_verified_at` | `2026-10-04 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 609 | `image_source_type` | `official_logo` | `official_university` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 614 | `image_source_type` | `official_logo` | `official_government` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 617 | `image_evaluated_at` | `2026-10-04 08:18:51.116404` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 617 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 617 | `image_alt_text` | `Ministry of Education, Kingdom of Saudi Arabia emblem` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 617 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 617 | `image_source_type` | `official_government` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 617 | `image_source_url` | `https://www.moe.gov.sa/en/education/ResidentsAndvisitors/pages/publicuniversitiesscholarships...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 617 | `image_url` | `https://www.moe.gov.sa/_layouts/15/Portal/favicon/favicon-32x32.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 617 | `image_verified_at` | `2026-10-04 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 618 | `image_evaluated_at` | `2026-10-04 08:18:51.116404` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 618 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 618 | `image_alt_text` | `Ghana Scholarships Authority` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 618 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 618 | `image_source_type` | `official_government` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 618 | `image_source_url` | `https://scholarships.gov.gh/opportunities/presidential-west-african-scholarship-initiative-pw...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 618 | `image_url` | `https://scholarships.gov.gh/images/logo.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 618 | `image_verified_at` | `2026-10-04 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 619 | `image_evaluated_at` | `2026-10-04 08:18:51.116404` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 619 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 619 | `image_alt_text` | `Ministry of Education, Kingdom of Saudi Arabia` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 619 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 619 | `image_source_type` | `official_government` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 619 | `image_source_url` | `https://studyinsaudi.sa/en/VisaOptions` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 619 | `image_url` | `https://studyinsaudi.sa/images/logos/header-logo-right-colored.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 619 | `image_verified_at` | `2026-10-04 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 621 | `image_evaluated_at` | `2026-10-04 08:18:51.116404` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 621 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 621 | `image_alt_text` | `Türkiye Scholarships (Türkiye Bursları) official logo — crimson tulip mark with dark charcoal...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 621 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 621 | `image_source_type` | `official_government` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 621 | `image_source_url` | `https://www.turkiyeburslari.gov.tr/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 621 | `image_url` | `https://www.turkiyeburslari.gov.tr/YTB/images/logo/tb-logo.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 621 | `image_verified_at` | `2026-10-04 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 622 | `image_evaluated_at` | `2026-10-04 08:18:50.422113` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 622 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 622 | `image_alt_text` | `Ministry of Education, Science and Technological Development of the Republic of Serbia` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 622 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 622 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 622 | `image_source_url` | `https://www.prosveta.gov.rs/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 622 | `image_url` | `https://prosveta.gov.rs/wp-content/uploads/2021/09/Logo.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 622 | `image_verified_at` | `2026-10-04 08:18:50.422113` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 623 | `image_evaluated_at` | `2026-10-04 08:18:51.116404` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 623 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 623 | `image_alt_text` | `Petroleum Technology Development Fund official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 623 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 623 | `image_source_type` | `official_government` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 623 | `image_source_url` | `https://ptdf.gov.ng/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 623 | `image_url` | `https://ptdf.gov.ng/logo.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 623 | `image_verified_at` | `2026-10-04 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 625 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 626 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 627 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 628 | `image_evaluated_at` | `2026-10-04 09:43:31.806439` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 628 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 628 | `image_alt_text` | `Fundacao Calouste Gulbenkian` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 628 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 628 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 628 | `image_source_url` | `https://gulbenkian.pt/en/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 628 | `image_url` | `https://gulbenkian.pt/wp-content/themes/fcg-common/public/images/favicon/icon-512x512.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 628 | `image_verified_at` | `2026-10-04 09:43:31.806439` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 629 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 631 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 632 | `image_evaluated_at` | `2026-10-04 08:24:15.568239` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 632 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 632 | `image_alt_text` | `United Negro College Fund` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 632 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 632 | `image_source_type` | `official_scholarship` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 632 | `image_source_url` | `https://uncf.org/scholarships` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 632 | `image_url` | `https://uncf.org/favicon.ico` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 632 | `image_verified_at` | `2026-10-04 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 633 | `image_evaluated_at` | `2026-10-04 08:24:15.568239` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 633 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 633 | `image_alt_text` | `United Negro College Fund` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 633 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 633 | `image_source_type` | `official_scholarship` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 633 | `image_source_url` | `https://uncf.org/pages/the-frederick-douglass-bicentennial-scholarship-program` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 633 | `image_url` | `https://uncf.org/favicon.ico` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 633 | `image_verified_at` | `2026-10-04 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 637 | `image_evaluated_at` | `2026-10-04 08:24:15.568239` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 637 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 637 | `image_alt_text` | `Fundacao Oswaldo Cruz (Fiocruz) emblem - white Maltese cross on a red field` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 637 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 637 | `image_source_type` | `official_scholarship` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 637 | `image_source_url` | `https://fiocruz.br/sites/fiocruz.br/files/marca-fiocruz-redes-sociais.jpg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 637 | `image_url` | `https://fiocruz.br/sites/fiocruz.br/files/marca-fiocruz-redes-sociais.jpg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 637 | `image_verified_at` | `2026-10-04 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 639 | `image_evaluated_at` | `2026-10-04 08:24:15.568239` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 639 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 639 | `image_alt_text` | `Instituto Riva-Aguero wordmark with the house and column device` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 639 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 639 | `image_source_type` | `official_scholarship` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 639 | `image_source_url` | `https://ira.pucp.edu.pe/wp-content/uploads/2020/04/logo-ira.jpg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 639 | `image_url` | `https://ira.pucp.edu.pe/wp-content/uploads/2020/04/logo-ira.jpg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 639 | `image_verified_at` | `2026-10-04 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 640 | `image_evaluated_at` | `2026-10-04 09:43:31.806439` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 640 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 640 | `image_alt_text` | `Instituto Riva-Aguero wordmark with the house and column device` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 640 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 640 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 640 | `image_source_url` | `https://ira.pucp.edu.pe/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 640 | `image_url` | `https://ira.pucp.edu.pe/wp-content/uploads/2020/04/logo-ira.jpg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 640 | `image_verified_at` | `2026-10-04 09:43:31.806439` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 641 | `image_evaluated_at` | `2026-10-04 08:24:14.819866` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 641 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 641 | `image_alt_text` | `Instituto Riva-Aguero wordmark with the house and column device` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 641 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 641 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 641 | `image_source_url` | `https://ira.pucp.edu.pe/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 641 | `image_url` | `https://ira.pucp.edu.pe/wp-content/uploads/2020/04/logo-ira.jpg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 641 | `image_verified_at` | `2026-10-04 08:24:14.819866` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 642 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 643 | `image_source_type` | `official_logo` | `official_university` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 644 | `image_evaluated_at` | `2026-10-04 08:24:15.568239` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 644 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 644 | `image_alt_text` | `Commission on Higher Education (CHED) seal, Office of the President of the Philippines` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 644 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 644 | `image_source_type` | `official_government` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 644 | `image_source_url` | `https://sikap.ched.gov.ph/call-for-applicants?type=sikap` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 644 | `image_url` | `https://sikap.ched.gov.ph/ched.webp` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 644 | `image_verified_at` | `2026-10-04 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 645 | `image_evaluated_at` | `2026-10-04 08:24:15.568239` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 645 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 645 | `image_alt_text` | `TaiwanICDF (International Cooperation and Development Fund) logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 645 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 645 | `image_source_type` | `official_government` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 645 | `image_source_url` | `https://www.icdf.org.tw/wSite/ct?ctNode=31562&mp=2&xItem=12505` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 645 | `image_url` | `https://www.icdf.org.tw/wSite/xslGip/style2/images/logo.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 645 | `image_verified_at` | `2026-10-04 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 646 | `image_evaluated_at` | `2026-10-04 08:24:15.568239` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 646 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 646 | `image_alt_text` | `BOLASHAK - Center for International Programs logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 646 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 646 | `image_source_type` | `official_government` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 646 | `image_source_url` | `https://bolashak.gov.kz/en/scholarship-program` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 646 | `image_url` | `https://bolashak.gov.kz/storage/app/media/logoog.jpg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 646 | `image_verified_at` | `2026-10-04 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 647 | `image_evaluated_at` | `2026-10-04 08:24:14.819866` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 647 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 647 | `image_alt_text` | `Universiti Putra Malaysia` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 647 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 647 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 647 | `image_source_url` | `https://sgs.upm.edu.my/financial_assistance_scholarships/scholarship_financial_assistance_upm...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 647 | `image_url` | `https://sgs.upm.edu.my/assets/images/logoupm.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 647 | `image_verified_at` | `2026-10-04 08:24:14.819866` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 648 | `image_evaluated_at` | `2026-10-04 08:24:14.819866` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 648 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 648 | `image_alt_text` | `Universiti Putra Malaysia` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 648 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 648 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 648 | `image_source_url` | `https://sgs.upm.edu.my/financial_assistance_scholarships/scholarship_financial_assistance_upm...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 648 | `image_url` | `https://sgs.upm.edu.my/assets/images/logoupm.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 648 | `image_verified_at` | `2026-10-04 08:24:14.819866` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 649 | `image_source_type` | `official_logo` | `official_university` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 650 | `image_evaluated_at` | `2026-10-04 08:24:14.819866` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 650 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 650 | `image_alt_text` | `Tsinghua University logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 650 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 650 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 650 | `image_source_url` | `https://yz.tsinghua.edu.cn/en/info/1027/1117.htm` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 650 | `image_url` | `https://yz.tsinghua.edu.cn/en/image/logo.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 650 | `image_verified_at` | `2026-10-04 08:24:14.819866` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 653 | `image_evaluated_at` | `2026-10-04 08:24:14.819866` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 653 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 653 | `image_alt_text` | `Ton Duc Thang University` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 653 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 653 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 653 | `image_source_url` | `https://admission.tdtu.edu.vn/en/undergraduate/Scholarships` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 653 | `image_url` | `https://www.tdtu.edu.vn/sites/www/files/logo-dh_0.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 653 | `image_verified_at` | `2026-10-04 08:24:14.819866` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 654 | `image_evaluated_at` | `2026-10-04 08:24:14.819866` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 654 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 654 | `image_alt_text` | `TaiwanICDF (International Cooperation and Development Fund) logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 654 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 654 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 654 | `image_source_url` | `https://www.icdf.org.tw/wSite/ct?ctNode=31562&mp=2&xItem=12505` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 654 | `image_url` | `https://www.icdf.org.tw/wSite/xslGip/style2/images/logo.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 654 | `image_verified_at` | `2026-10-04 08:24:14.819866` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 655 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 656 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 657 | `image_source_type` | `official_logo` | `official_government` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 660 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 661 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 663 | `image_evaluated_at` | `2026-10-04 08:24:14.819866` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 663 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 663 | `image_alt_text` | `Fiji National University logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 663 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 663 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 663 | `image_source_url` | `https://www.fnu.ac.fj/research/scholarships/pass-cr/pacific-agriculture-scholarship-support-a...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 663 | `image_url` | `https://www.fnu.ac.fj/wp-content/uploads/2019/12/fnu_logo_resized.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 663 | `image_verified_at` | `2026-10-04 08:24:14.819866` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 664 | `image_evaluated_at` | `2026-10-04 08:53:39.244242` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 664 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 664 | `image_alt_text` | `Bond University coat of arms` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 664 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 664 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 664 | `image_source_url` | `https://bond.edu.au/our-university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 664 | `image_url` | `https://bond.edu.au/themes/custom/bond_theme/favicon/apple-touch-icon.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 664 | `image_verified_at` | `2026-10-04 08:53:39.244242` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 667 | `image_evaluated_at` | `2026-10-04 08:53:39.244242` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 667 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 667 | `image_alt_text` | `Arab Fund for Economic and Social Development` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 667 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 667 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 667 | `image_source_url` | `https://www.arabfund.org/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 667 | `image_url` | `https://www.arabfund.org/wp-content/uploads/2023/10/Logo-1ldpi-Copy.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 667 | `image_verified_at` | `2026-10-04 08:53:39.244242` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 673 | `image_evaluated_at` | `2026-10-04 08:24:15.568239` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 673 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 673 | `image_alt_text` | `Petroleum Technology Development Fund (PTDF)` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 673 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 673 | `image_source_type` | `official_government` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 673 | `image_source_url` | `https://ptdf.gov.ng/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 673 | `image_url` | `https://ptdf.gov.ng/logo.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 673 | `image_verified_at` | `2026-10-04 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 674 | `image_source_type` | `official_logo` | `official_government` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 675 | `image_evaluated_at` | `2026-10-04 09:43:31.806439` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 675 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 675 | `image_alt_text` | `Ministry of Higher Education and Scientific Research, Egypt (وزارة التعليم العالي والبحث العلمي)` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 675 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 675 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 675 | `image_source_url` | `https://mohesr.gov.eg/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 675 | `image_url` | `https://mohesr.gov.eg/images/logo.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 675 | `image_verified_at` | `2026-10-04 09:43:31.806439` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 676 | `image_evaluated_at` | `2026-10-04 09:43:31.806439` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 676 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 676 | `image_alt_text` | `Iraq Ministry of Higher Education and Scientific Research emblem (وزارة التعليم العالي والبحث...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 676 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 676 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 676 | `image_source_url` | `https://mohesr.gov.iq/ar/post/%D8%A7%D9%84%D8%AA%D8%B9%D9%84%D9%8A%D9%85-%D8%AA%D8%B9%D9%84%D...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 676 | `image_url` | `https://mohesr.gov.iq/ar/assets/viewApp/imgs/mohser_logo/symbol.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 676 | `image_verified_at` | `2026-10-04 09:43:31.806439` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 678 | `image_evaluated_at` | `2026-10-04 09:43:31.806439` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 678 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 678 | `image_alt_text` | `Egypt-Japan University of Science and Technology (E-JUST)` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 678 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 678 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 678 | `image_source_url` | `https://ejust.edu.eg/international-scholarships` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 678 | `image_url` | `https://ejust.edu.eg/assets/img/logo.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 678 | `image_verified_at` | `2026-10-04 09:43:31.806439` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 679 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 680 | `image_evaluated_at` | `2026-10-04 08:24:15.568239` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 680 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 680 | `image_alt_text` | `Qatar University official logo — maroon emblem with Arabic and English wordmark` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 680 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 680 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 680 | `image_source_url` | `https://www.qu.edu.qa/en-us/students/admission/scholarships/types` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 680 | `image_url` | `https://www.qu.edu.qa/Style%20Library/assets/images/favicon.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 680 | `image_verified_at` | `2026-10-04 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 681 | `image_evaluated_at` | `2026-10-04 08:24:15.568239` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 681 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 681 | `image_alt_text` | `Brunei Darussalam national emblem as published in the Ministry of Foreign Affairs site header...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 681 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 681 | `image_source_type` | `official_government` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 681 | `image_source_url` | `https://www.mfa.gov.bn/Pages/online-bdgs.aspx` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 681 | `image_url` | `https://www.mfa.gov.bn/Shared%20Documents/Brunei%20Logo.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 681 | `image_verified_at` | `2026-10-04 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 682 | `image_evaluated_at` | `2026-10-04 08:24:15.568239` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 682 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 682 | `image_alt_text` | `Nazarbayev University official wordmark in dark olive-grey` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 682 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 682 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 682 | `image_source_url` | `https://nu.edu.kz/admissions/how-to-apply/foundation-undergraduate/financial-aid-end-scholars...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 682 | `image_url` | `https://nu.edu.kz/wp-content/uploads/2025/05/logo_nu1.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 682 | `image_verified_at` | `2026-10-04 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 683 | `image_evaluated_at` | `2026-10-04 08:24:14.819866` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 683 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 683 | `image_alt_text` | `Brunei Darussalam national emblem as published by the Ministry of Foreign Affairs` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 683 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 683 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 683 | `image_source_url` | `https://www.mfa.gov.bn/Pages/online-bdgs.aspx` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 683 | `image_url` | `https://www.mfa.gov.bn/Shared%20Documents/Brunei%20Logo.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 683 | `image_verified_at` | `2026-10-04 08:24:14.819866` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 684 | `image_source_type` | `official_logo` | `official_government` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 685 | `image_evaluated_at` | `2026-10-04 08:24:15.568239` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 685 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 685 | `image_alt_text` | `Ghana Education Trust Fund official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 685 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 685 | `image_source_type` | `official_government` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 685 | `image_source_url` | `https://www.getfund.gov.gh/scholarships/overview` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 685 | `image_url` | `https://www.getfund.gov.gh/images/logos/GETFund%20logo_200cm%20Wide%20-%20%20Black.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 685 | `image_verified_at` | `2026-10-04 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 687 | `image_evaluated_at` | `2026-10-04 08:25:40.340102` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 687 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 687 | `image_alt_text` | `COMEXUS (U.S.-Mexico Commission for Educational and Cultural Exchange) site icon` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 687 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 687 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 687 | `image_source_url` | `https://www.comexus.org.mx/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 687 | `image_url` | `https://www.comexus.org.mx/favicon.ico` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 687 | `image_verified_at` | `2026-10-04 08:25:40.340102` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 688 | `image_evaluated_at` | `2026-10-04 08:25:40.340102` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 688 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 688 | `image_alt_text` | `SECIHTI - Secretaría de Ciencia, Humanidades y Tecnología` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 688 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 688 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 688 | `image_source_url` | `https://secihti.mx/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 688 | `image_url` | `https://secihti.mx/wp-content/uploads/2025/03/logo_secihti_vertical_color.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 688 | `image_verified_at` | `2026-10-04 08:25:40.340102` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 689 | `image_evaluated_at` | `2026-10-04 08:25:40.340102` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 689 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 689 | `image_alt_text` | `SECIHTI - Secretaría de Ciencia, Humanidades y Tecnología` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 689 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 689 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 689 | `image_source_url` | `https://secihti.mx/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 689 | `image_url` | `https://secihti.mx/wp-content/uploads/2025/03/logo_secihti_vertical_color.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 689 | `image_verified_at` | `2026-10-04 08:25:40.340102` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 690 | `image_evaluated_at` | `2026-10-04 08:25:41.093442` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 690 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 690 | `image_alt_text` | `DOST Science Education Institute logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 690 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 690 | `image_source_type` | `official_government` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 690 | `image_source_url` | `https://fgs.science-scholarships.ph/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 690 | `image_url` | `https://fgs.science-scholarships.ph/assets/dost-sei-logo.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 690 | `image_verified_at` | `2026-10-04 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 691 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 692 | `image_evaluated_at` | `2026-10-04 09:43:31.806439` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 692 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 692 | `image_alt_text` | `Türkiye Scholarships (Türkiye Bursları) official logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 692 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 692 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 692 | `image_source_url` | `https://www.turkiyeburslari.gov.tr/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 692 | `image_url` | `https://www.turkiyeburslari.gov.tr/YTB/images/logo/tb-logo.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 692 | `image_verified_at` | `2026-10-04 09:43:31.806439` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 693 | `image_evaluated_at` | `2026-10-04 08:25:40.340102` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 693 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 693 | `image_alt_text` | `Ministry of Education Transformation, Barbados` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 693 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 693 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 693 | `image_source_url` | `https://education.gov.bb/2026-errol-walton-barrow-scholarships` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 693 | `image_url` | `https://education.gov.bb/wp-content/uploads/2026/04/MEdT-Logo-full-col-1-scaled-e177748400715...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 693 | `image_verified_at` | `2026-10-04 08:25:40.340102` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 696 | `image_evaluated_at` | `2026-10-04 09:43:31.806439` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 696 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 696 | `image_alt_text` | `COMEXUS (U.S.-Mexico Commission for Educational and Cultural Exchange) site icon` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 696 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 696 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 696 | `image_source_url` | `https://www.comexus.org.mx/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 696 | `image_url` | `https://www.comexus.org.mx/favicon.ico` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 696 | `image_verified_at` | `2026-10-04 09:43:31.806439` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 699 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 700 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 701 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 702 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 703 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 704 | `image_evaluated_at` | `2026-10-04 08:44:00.328053` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 704 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 704 | `image_alt_text` | `Higher Education Commission of Pakistan logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 704 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 704 | `image_source_type` | `official_government` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 704 | `image_source_url` | `https://www.hec.gov.pk/english/scholarshipsgrants/CAFC/AMIC/Pages/default.aspx` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 704 | `image_url` | `https://www.hec.gov.pk/Style%20Library/HEC/images/header-logo.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 704 | `image_verified_at` | `2026-10-04 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 705 | `image_evaluated_at` | `2026-10-04 08:44:00.328053` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 705 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 705 | `image_alt_text` | `Higher Education Commission of Pakistan logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 705 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 705 | `image_source_type` | `official_government` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 705 | `image_source_url` | `https://www.hec.gov.pk/english/scholarshipsgrants/PBKC/Pages/AISB.aspx` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 705 | `image_url` | `https://www.hec.gov.pk/Style%20Library/HEC/images/header-logo.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 705 | `image_verified_at` | `2026-10-04 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 706 | `image_evaluated_at` | `2026-10-04 08:44:00.328053` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 706 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 706 | `image_alt_text` | `Higher Education Commission of Pakistan logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 706 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 706 | `image_source_type` | `official_government` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 706 | `image_source_url` | `https://www.hec.gov.pk/english/scholarshipsgrants/pshecp/aiss/Pages/default.aspx` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 706 | `image_url` | `https://www.hec.gov.pk/Style%20Library/HEC/images/header-logo.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 706 | `image_verified_at` | `2026-10-04 00:00:00.000000` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 707 | `image_evaluated_at` | `2026-10-04 08:43:59.436183` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 707 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 707 | `image_alt_text` | `Hong Kong University of Science and Technology` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 707 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 707 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 707 | `image_source_url` | `https://hkust.edu.hk/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 707 | `image_url` | `https://www.hkust.edu.hk/sites/default/files/2024-03/HKUST_logo_1.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 707 | `image_verified_at` | `2026-10-04 08:43:59.436183` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 708 | `image_evaluated_at` | `2026-10-04 08:43:59.436183` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 708 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 708 | `image_alt_text` | `ITB` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 708 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 708 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 708 | `image_source_url` | `https://finaid.itb.ac.id/itb-international-undergraduate-scholarship` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 708 | `image_url` | `https://finaid.itb.ac.id/_ipx/h_56&q_100/assets/img/logo-bersama.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 708 | `image_verified_at` | `2026-10-04 08:43:59.436183` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 710 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 711 | `image_source_type` | `official_logo` | `official_provider` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 712 | `image_evaluated_at` | `2026-10-04 08:43:59.436183` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 712 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 712 | `image_alt_text` | `ILSC Language Schools` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 712 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 712 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 712 | `image_source_url` | `https://www.ilsc.com/humanitarian-scholarship` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 712 | `image_url` | `https://www.ilsc.com/hubfs/Language%20School-Color-Logo-Horizontal.svg` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 712 | `image_verified_at` | `2026-10-04 08:43:59.436183` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 713 | `image_evaluated_at` | `2026-10-04 09:43:31.806439` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 713 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 713 | `image_alt_text` | `Ghana Scholarships Authority` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 713 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 713 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 713 | `image_source_url` | `https://scholarships.gov.gh/opportunities/presidential-west-african-scholarship-initiative-pw...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 713 | `image_url` | `https://scholarships.gov.gh/images/logo.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 713 | `image_verified_at` | `2026-10-04 09:43:31.806439` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 714 | `image_evaluated_at` | `2026-10-04 09:43:31.806439` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 714 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 714 | `image_alt_text` | `Ghana Scholarships Authority` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 714 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 714 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 714 | `image_source_url` | `https://scholarships.gov.gh/opportunities/presidential-west-african-scholarship-initiative-pw...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 714 | `image_url` | `https://scholarships.gov.gh/images/logo.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 714 | `image_verified_at` | `2026-10-04 09:43:31.806439` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 715 | `image_evaluated_at` | `2026-10-04 09:36:50.058479` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 715 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 715 | `image_alt_text` | `Azərbaycan Respublikası Elm və Təhsil Nazirliyi - Ministry of Science and Education of the Re...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 715 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 715 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 715 | `image_source_url` | `https://edu.gov.az/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 715 | `image_url` | `https://edu.gov.az/site/views/site/images/Az-Resp-elm-tehsil-naziriyi-logo.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 715 | `image_verified_at` | `2026-10-04 09:36:50.058479` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 716 | `image_evaluated_at` | `2026-10-04 09:36:50.058479` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 716 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 716 | `image_alt_text` | `Ministry of Public Service, Government Efficiency & Implementation` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 716 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 716 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 716 | `image_source_url` | `https://mps.gov.gy/scholarships/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 716 | `image_url` | `https://mps.gov.gy/wp-content/uploads/2025/11/MPSGEI-Logo-1024x278.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 716 | `image_verified_at` | `2026-10-04 09:36:50.058479` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 717 | `image_evaluated_at` | `2026-10-04 08:43:59.436183` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 717 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 717 | `image_alt_text` | `Logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 717 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 717 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 717 | `image_source_url` | `https://www.stipendia.sk/sk/main/o-programe/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 717 | `image_url` | `https://www.stipendia.sk/_custom/img/logo_NS-SK.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 717 | `image_verified_at` | `2026-10-04 08:43:59.436183` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 718 | `image_evaluated_at` | `2026-10-04 08:43:59.436183` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 718 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 718 | `image_alt_text` | `Ghana Scholarships Authority` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 718 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 718 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 718 | `image_source_url` | `https://scholarships.gov.gh/opportunities/presidential-west-african-scholarship-initiative-pw...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 718 | `image_url` | `https://scholarships.gov.gh/images/logo.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 718 | `image_verified_at` | `2026-10-04 08:43:59.436183` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 719 | `image_evaluated_at` | `2026-10-04 08:43:59.436183` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 719 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 719 | `image_alt_text` | `Fiji National University logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 719 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 719 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 719 | `image_source_url` | `https://www.fnu.ac.fj/research/scholarships/pass-cr/pacific-agriculture-scholarship-support-a...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 719 | `image_url` | `https://www.fnu.ac.fj/wp-content/uploads/2019/12/fnu_logo_resized.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 719 | `image_verified_at` | `2026-10-04 08:43:59.436183` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 720 | `image_evaluated_at` | `2026-10-04 08:43:59.436183` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 720 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 720 | `image_alt_text` | `Tertiary Scholarships and Loans Service, Fiji` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 720 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 720 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 720 | `image_source_url` | `https://tsls.com.fj/high-achievers-higher-education-level-7-overseas-scheme/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 720 | `image_url` | `https://tsls.com.fj/wp-content/uploads/2023/04/Site-Logo-302-x-86-px.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 720 | `image_verified_at` | `2026-10-04 08:43:59.436183` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 721 | `image_source_type` | `official_logo` | `official_government` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 722 | `image_evaluated_at` | `2026-10-04 08:43:59.436183` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 722 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 722 | `image_alt_text` | `Fiji National University logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 722 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 722 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 722 | `image_source_url` | `https://www.fnu.ac.fj/research/scholarships/pass-cr/pacific-agriculture-scholarship-support-a...` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 722 | `image_url` | `https://www.fnu.ac.fj/wp-content/uploads/2019/12/fnu_logo_resized.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 722 | `image_verified_at` | `2026-10-04 08:43:59.436183` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 723 | `image_evaluated_at` | `2026-10-04 08:43:59.436183` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 723 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 723 | `image_alt_text` | `Tertiary Scholarships and Loans Service, Fiji` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 723 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 723 | `image_source_type` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 723 | `image_source_url` | `https://tsls.com.fj/high-achievers-higher-education-level-7-overseas-scheme/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 723 | `image_url` | `https://tsls.com.fj/wp-content/uploads/2023/04/Site-Logo-302-x-86-px.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 723 | `image_verified_at` | `2026-10-04 08:43:59.436183` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 725 | `image_evaluated_at` | `2026-10-04 08:53:43.069192` | `2026-10-04T11:18:52.082139+00:00` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 725 | `image_evaluation_status` | `verified` | `invalid_candidates` | normalised | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | low |
| 725 | `image_alt_text` | `University of Rwanda` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 725 | `image_kind` | `official_logo` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 725 | `image_source_type` | `official_university` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 725 | `image_source_url` | `https://www.ur.ac.rw/` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 725 | `image_url` | `https://www.ur.ac.rw/images/urlogo1.png` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |
| 725 | `image_verified_at` | `2026-10-04 08:53:43.069192` | NULL | cleared | `pre-repair snapshot scholarzone.pre_wave13_hardening_20261004_171847.db` | medium |

## 5. Validation status per change class

| Change class | Count | Validator that decided it | Status |
|---|---|---|---|
| `deadline_precision` normalised | 73 | `coerce_deadline_precision` (existing) | PASS |
| `image_source_type` re-derived | 406 | `_issuer_kind` + `is_valid_source_type` (existing) | PASS |
| asset restored from pre-wave snapshot | 0 | `assess_image_evidence` (new gate) | PASS |
| asset cleared | 1091 | `assess_image_evidence` (new gate) | PASS |
| `image_evaluation_status` set to a terminal negative | 180 | `ImageEvaluationStatus.INVALID_CANDIDATES` | PASS |
| list-column shape repaired | 6 rows | `normalize_list_column` (existing, run via `--stage repair_list_columns`) | PASS |

## 6. Production delta — UNKNOWN, and why

**PROVEN:** the local repository contains no usable production database credential, and none can be obtained from here.

| Path attempted | Result |
|---|---|
| `SCHOLARZONE_DATABASE_URL` / `DATABASE_URL` / `PG*` in the process | **absent** |
| `backend/.env` (gitignored) | contains only `RESEND_API_KEY`, `NOTIFICATION_EMAIL`, `SCHOLARZONE_VERIFICATION_SECRET` |
| `backend/.env.example` | template only |
| Application started as `SCHOLARZONE_ENVIRONMENT=production` | `RuntimeError: SCHOLARZONE_DATABASE_URL is required in production. Configure a PostgreSQL (Neon) connection string...` |
| GitHub Actions secret `SCHOLARZONE_DATABASE_URL` | **exists** (last set 2026-09-06) — GitHub never returns secret values, only names and timestamps |
| Vercel CLI | installed, but no linked project directory present |

**UNKNOWN:** the contents of Neon, and therefore the exact difference between the local proposed state and production. Every 'old value' in §4 is the local post-wave value, not the production value.

Consequence: this manifest cannot be diffed against production, and **must not be applied** until a read-only Neon role is supplied and the ID-level comparison is run.

## 7. Corrections required BEFORE this manifest may be applied

The diff above is complete and correct as a record of what changed. It is **not** a statement that every change should go to production. The final audit found defects that this manifest must not carry into Neon.


### D1 — an official logo was cleared on a detector false positive — 2 rows

*Why:* `_detect_error_signals` matched a three-digit HTTP status inside a CMS content hash in the filename and scored it 2.0. The asset was then cleared as a non-content artefact.

| scholarship_id | title | current | required | evidence |
|---|---|---|---|---|
| 63 | `Michigan State University International Merit Schola` | `image_url=NULL` | restore the asset | `ssions/images/menu/academics-small.jpg?h=232&iar=0&w=400` |
| 693 | `Errol Walton Barrow Scholarships` | `image_url=NULL` | restore the asset | `s/2026/04/MEdT-Logo-full-col-1-scaled-e1777484007158.png` |

Both families are **reversible without research**: D1 restores an asset recorded in the pre-repair snapshot, D2 recomputes from host and alt text with `_issuer_kind`, which is verified to agree on every row.


### D2 — a more specific provenance was reverted to a vaguer one — 18 rows

*Why:* The wave improved `image_source_type` on these rows. The asset-restoration path restored that column along with the image, undoing the improvement.

| scholarship_id | title | current | required | evidence |
|---|---|---|---|---|
| 48 | `University of Sydney Vice-Chancellor's International` | `official_provider` | `official_university` | host `sydney.edu.au`, alt ``University of Sydney`` |
| 49 | `Annie Farrand Scholarship in Agricultural Science (I` | `official_provider` | `official_university` | host `sydney.edu.au`, alt ``University of Sydney`` |
| 51 | `UWA Global Excellence Scholarship` | `official_provider` | `official_university` | host `uwa.edu.au`, alt ``University of Western Aust`` |
| 84 | `International Major Entrance Scholarship (IMES), Uni` | `official_provider` | `official_university` | host `you.ubc.ca`, alt ``University of British Colu`` |
| 85 | `UBC International Scholars Program` | `official_provider` | `official_government` | host `you.ubc.ca`, alt ``University of British Colu`` |
| 152 | `Excellence Master Fellowships (Faculty of Science, U` | `official_provider` | `official_university` | host `unige.ch`, alt ``University of Geneva`` |
| 186 | `Chalmers University of Technology — IPOET Scholarshi` | `official_provider` | `official_university` | host `chalmers.se`, alt ``Chalmers University of Tec`` |
| 197 | `University of Sydney International Stipend Scholarsh` | `official_provider` | `official_university` | host `sydney.edu.au`, alt ``University of Sydney`` |
| 203 | `Flinders International Postgraduate Research Scholar` | `official_provider` | `official_university` | host `flinders.edu.au`, alt ``Flinders University`` |
| 226 | `Mannagetta Fellowships (Johann Wilhelm Ritter von Ma` | `official_provider` | `official_university` | host `stipendien.oeaw.ac.at`, alt ``Austrian Academy of Scienc`` |
| 256 | `University of Auckland Doctoral Scholarship` | `official_provider` | `official_university` | host `auckland.ac.nz`, alt ``University of Auckland`` |
| 271 | `University of Copenhagen Danish Government Scholarsh` | `official_provider` | `official_university` | host `ku.dk`, alt ``University of Copenhagen`` |
| 273 | `University of Southern Denmark (SDU) Danish Governme` | `official_provider` | `official_university` | host `sdu.dk`, alt ``University of Southern Den`` |
| 332 | `Aalborg University International Student Scholarship` | `official_provider` | `official_university` | host `en.aau.dk`, alt ``Aalborg University`` |
| 337 | `University of Oulu Early Bird Discount and Tuition F` | `official_provider` | `official_university` | host `oulu.fi`, alt ``University of Oulu`` |
| 338 | `University of Eastern Finland Early Bird Discount (3` | `official_provider` | `official_university` | host `uef.fi`, alt ``University of Eastern Finl`` |
| 398 | `University of Amsterdam Scholarships` | `official_provider` | `official_university` | host `uva.nl`, alt ``University of Amsterdam`` |
| 407 | `Vice-Chancellor's International Excellence Scholarsh` | `official_provider` | `official_university` | host `waikato.ac.nz`, alt ``University of Waikato`` |

Both families are **reversible without research**: D1 restores an asset recorded in the pre-repair snapshot, D2 recomputes from host and alt text with `_issuer_kind`, which is verified to agree on every row.

## 8. Apply preconditions

All must hold before any controlled production apply is considered:

1. Read-only Neon credentials provisioned, and a successful read demonstrated.
2. ID-level comparison of this manifest against Neon, row by row. Any row whose production value differs from the 'old value' here must be re-decided, not applied.
3. The six code guards deployed, so the repaired values cannot be reintroduced by the next run.
4. A human decision on the four YELLOW items in `WAVE1_3_HARDENING_FINAL.md` §11.
5. A decision on the 234 wave-created rows, which this manifest deliberately excludes.
6. Dry run of every stage against Neon, with the run log reviewed, before any non-dry run.

**Never copy `scholarzone.db` into Neon.** The apply mechanism is the repository's own stages driven by the `backend/config/*.json` change set, one stage at a time.

