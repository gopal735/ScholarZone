# DUPLICATE RESOLUTION MANIFEST

**Generated:** 2026-10-04T12:02:03.836070+00:00  
**Applied to:** local SQLite only. **Neon: untouched.**  
**Mechanism:** `backend/config/retired_records.json` + the `retire` maintenance stage. Quarantine and archive, never delete.

---

## Survivor rule

Two rules, applied in order, because they are the only two that cannot be argued with:

1. **A row holding reviews is not retirable.** Reviews are the one relationship in this schema that cannot be recreated. In four of the six pairs the older row holds 5–7 reviews and the wave-created row holds none, so the older row survives and the newer one is retired even though the newer one often holds more research text.
2. **Where neither side holds reviews, the researched row survives.** Completeness and verification evidence both point the same way, and nothing is lost either way.

Where the survivor had no `official_details` and the retired row did, the retired row's block is copied into the survivor **before** the retire, so no researched text is discarded. Where both sides hold a block, nothing is merged: there is no evidence that one supersedes the other, and asserting a merge would be a guess.

## Preserved references

| Table | Behaviour on retire |
|---|---|
| `scholarship_reviews` | untouched — the row is archived, not deleted, so every review keeps pointing at a live id |
| `scholarship_verification_history` | untouched; history stays attributable to the id it was recorded against |
| `image_reviews` | untouched |

The pre-existing 48 retirements work exactly this way. One orphan exists in the whole database — `scholarship_verification_history` pointing at id 358, which the wave **purged** rather than retired. That is the one mechanism in this schema that does lose its id, and it is not the mechanism used here.

---

## 133 / 570 — Invest Your Talent in Italy (IYT)

**Decision: retire `133`, keep `570`.**

**PROVEN duplicate.** Same programme, same call page. The two official URLs differ only in the case of the path segment (/SITOIYT/ vs /SitoIYT/). Neither row holds a review, so nothing is lost by keeping the researched row; id 133 carries no official_details at all. id 528 was already retired as a duplicate of 133, so 133 is the surviving half of an already-collapsed pair.

| Field | `133` | `570` |
|---|---|---|
| title | `Invest Your Talent in Italy (IYT)` | `Invest Your Talent in Italy (IYT) — MAECI / ICE / Uni-Italia scholarship programme` |
| official_source_url | `https://investyourtalentapplication.esteri.it/SITOIYT/EN/current-call` | `https://investyourtalentapplication.esteri.it/SitoIYT/EN/current-call` **(identical after normalisation)** |
| catalogue_url | NULL | NULL |
| image_url | `https://investyourtalentapplication.esteri.it/SITOIYT/EN/images/logoIYT.jpg` | `https://investyourtalentapplication.esteri.it/SITOIYT/EN/images/logoIYT.jpg` |
| image_kind | `official_logo` | `official_logo` |
| verification_status | `quarantined` | `active` |
| status | `open` | `open` |
| deadline_date | NULL | NULL |
| created_at | `2026-09-01 18:21:44` | `2026-10-04 08:10:12` |
| `official_details` length | 0 chars | 20115 chars |
| reviews | 0 | 0 |
| verification history rows | 0 | 1 |
| in `retired_records.json` | yes | no |

**Criteria applied**

| Criterion | Reading |
|---|---|
| authoritative source | both resolve to the same awarding body; the two URLs are the same page, differing only in path casing or in one case by a parent-vs-programme relationship |
| completeness | survivor holds 20115 chars of `official_details`; the retired row holds 0 |
| verification evidence | survivor holds 0 reviews and 1 history rows |
| created/updated provenance | `133` created 2026-09-01, `570` created 2026-10-04 |
| reviews / references | reviews on `133`: 0; on `570`: 0 — this is the deciding criterion |

**Merge performed:** none. Both rows' research is either already on the survivor or has no supportable claim to replace it.

---

## 438 / 530 — National Science Scholarship (PhD)

**Decision: retire `438`, keep `530`.**

**PROVEN duplicate.** Canonical official URLs are byte-identical after percent-encoding normalisation of the parentheses. Neither row holds a review. id 530 carries 18,931 characters of official official facts; id 438 carries none and its own stored image is a favicon. id 438's two verification history rows stay in the history table, as they do for every retired row.

| Field | `438` | `530` |
|---|---|---|
| title | `National Science Scholarship (PhD)` | `National Science Scholarship (PhD)` |
| official_source_url | `https://www.a-star.edu.sg/scholarships/home/scholarships/national-science-scholarship...` | `https://www.a-star.edu.sg/scholarships/home/scholarships/national-science-scholarship...` |
| catalogue_url | `https://www.a-star.edu.sg/scholarships` | NULL |
| image_url | NULL | NULL |
| image_kind | NULL | NULL |
| verification_status | `quarantined` | `active` |
| status | `open` | `closed` |
| deadline_date | NULL | `2026-10-01` |
| created_at | `2026-09-06 14:38:29` | `2026-10-04 07:31:16` |
| `official_details` length | 0 chars | 18931 chars |
| reviews | 0 | 0 |
| verification history rows | 2 | 1 |
| in `retired_records.json` | yes | no |

**Criteria applied**

| Criterion | Reading |
|---|---|
| authoritative source | both resolve to the same awarding body; the two URLs are the same page, differing only in path casing or in one case by a parent-vs-programme relationship |
| completeness | survivor holds 18931 chars of `official_details`; the retired row holds 0 |
| verification evidence | survivor holds 0 reviews and 1 history rows |
| created/updated provenance | `438` created 2026-09-06, `530` created 2026-10-04 |
| reviews / references | reviews on `438`: 0; on `530`: 0 — this is the deciding criterion |

**Merge performed:** none. Both rows' research is either already on the survivor or has no supportable claim to replace it.

---

## 68 / 532 — Gates Cambridge Scholarship

**Decision: retire `532`, keep `68`.**

**PROVEN duplicate.** Identical image URL on both rows (GC-logo-positive...WHITE_OUT.png), identical funder and identical GBP 23,152 maintenance. id 68 holds 5 reviews and 10,215 characters of research; id 532 holds 0 reviews and 0 official_details, so retiring it discards nothing.

| Field | `68` | `532` |
|---|---|---|
| title | `Gates Cambridge Scholarship` | `Gates Cambridge Scholarship (entry in the academic year 2027/8)` |
| official_source_url | `https://www.gatescambridge.org/programme/the-scholarship` | `https://www.gatescambridge.org/apply/timeline` |
| catalogue_url | `https://www.postgraduate.study.cam.ac.uk/courses` | NULL |
| image_url | `https://www.gatescambridge.org/wp-content/uploads/2023/08/GC-logo-positive_font_updat...` | `https://www.gatescambridge.org/wp-content/uploads/2023/08/GC-logo-positive_font_updat...` |
| image_kind | `official_logo` | `official_logo` |
| verification_status | `active` | `quarantined` |
| status | `open` | `closing-soon` |
| deadline_date | NULL | `2026-10-14` |
| created_at | `2026-09-01 18:21:44` | `2026-10-04 07:31:16` |
| `official_details` length | 10215 chars | 0 chars |
| reviews | 5 | 0 |
| verification history rows | 0 | 1 |
| in `retired_records.json` | no | yes |

**Criteria applied**

| Criterion | Reading |
|---|---|
| authoritative source | both resolve to the same awarding body; the two URLs are the same page, differing only in path casing or in one case by a parent-vs-programme relationship |
| completeness | survivor holds 10215 chars of `official_details`; the retired row holds 0 |
| verification evidence | survivor holds 5 reviews and 0 history rows |
| created/updated provenance | `68` created 2026-09-01, `532` created 2026-10-04 |
| reviews / references | reviews on `68`: 5; on `532`: 0 — this is the deciding criterion |

**Merge performed:** none. Both rows' research is either already on the survivor or has no supportable claim to replace it.

---

## 10 / 501 — Deutschlandstipendium (Germany Scholarship)

**Decision: retire `501`, keep `10`.**

**PROVEN duplicate.** id 501's official URL is a child page of id 10's site (/wie-es-funktioniert describes the same scheme) and both state the same EUR 300/month split funding. id 10 holds 7 reviews and 3 verification history rows. id 501's 12,826-character official_details block is copied into id 10 first, because retiring 501 would otherwise discard it.

| Field | `10` | `501` |
|---|---|---|
| title | `Deutschlandstipendium (Germany Scholarship)` | `Deutschlandstipendium` |
| official_source_url | `https://www.deutschlandstipendium.de` | `https://www.deutschlandstipendium.de/deutschlandstipendium/de/stipendium/wie-es-funkt...` |
| catalogue_url | NULL | NULL |
| image_url | `https://www.deutschlandstipendium.de/SharedDocs/Bilder/de/deutschlandstipendium/img/b...` | NULL |
| image_kind | `official_banner` | NULL |
| verification_status | `active` | `quarantined` |
| status | `open` | `open` |
| deadline_date | NULL | NULL |
| created_at | `2026-08-30 12:05:32` | `2026-10-04 07:31:16` |
| `official_details` length | 0 chars | 12826 chars |
| reviews | 7 | 0 |
| verification history rows | 3 | 0 |
| in `retired_records.json` | no | yes |

**Criteria applied**

| Criterion | Reading |
|---|---|
| authoritative source | both resolve to the same awarding body; the two URLs are the same page, differing only in path casing or in one case by a parent-vs-programme relationship |
| completeness | survivor holds 0 chars of `official_details`; the retired row holds 12826 |
| verification evidence | survivor holds 7 reviews and 3 history rows |
| created/updated provenance | `10` created 2026-08-30, `501` created 2026-10-04 |
| reviews / references | reviews on `10`: 7; on `501`: 0 — this is the deciding criterion |

**Merge performed:** the retired row's `official_details` was copied into `10` before retirement, so the researched block survives with the reviews.

---

## 107 / 531 — Nanyang President's Graduate Scholarship

**Decision: retire `531`, keep `107`.**

**PROVEN duplicate.** id 531 is the specific NPGS programme page under id 107's financial-aid hub, quoting the same SGD 4,300/4,800/5,300 stipend matrix. id 107 holds 7 reviews. Both hold an official_details block, and there is no evidence that one supersedes the other, so nothing is merged and id 531's research stays in the source config rather than being asserted as id 107's.

| Field | `107` | `531` |
|---|---|---|
| title | `Nanyang President's Graduate Scholarship` | `Nanyang President's Graduate Scholarship (NPGS)` |
| official_source_url | `https://www.ntu.edu.sg/admissions/graduate/financialmatters/scholarships` | `https://www.ntu.edu.sg/admissions/graduate/financialmatters/scholarships/npgs` |
| catalogue_url | `https://www.ntu.edu.sg/about-us/sustainability/sustainability-education/undergraduate...` | NULL |
| image_url | `https://www.ntu.edu.sg/ResourcePackages/NTU/assets/images/NTU_Logo.png` | `https://www.ntu.edu.sg/ResourcePackages/NTU/assets/images/NTU_Logo.png` |
| image_kind | `official_logo` | `official_logo` |
| verification_status | `active` | `quarantined` |
| status | `upcoming` | `open` |
| deadline_date | NULL | NULL |
| created_at | `2026-09-01 18:21:44` | `2026-10-04 07:31:16` |
| `official_details` length | 10091 chars | 24643 chars |
| reviews | 7 | 0 |
| verification history rows | 1 | 1 |
| in `retired_records.json` | no | yes |

**Criteria applied**

| Criterion | Reading |
|---|---|
| authoritative source | both resolve to the same awarding body; the two URLs are the same page, differing only in path casing or in one case by a parent-vs-programme relationship |
| completeness | survivor holds 10091 chars of `official_details`; the retired row holds 24643 |
| verification evidence | survivor holds 7 reviews and 1 history rows |
| created/updated provenance | `107` created 2026-09-01, `531` created 2026-10-04 |
| reviews / references | reviews on `107`: 7; on `531`: 0 — this is the deciding criterion |

**Merge performed:** none. Both rows' research is either already on the survivor or has no supportable claim to replace it.

---

## 13 / 553 — POSCO TJ Park Foundation Global Scholarship

**Decision: retire `553`, keep `13`.**

**PROVEN duplicate.** id 13's catalogue_url is byte-identical to id 553's official_source_url (/en/asia/abroad/business), a direct row-to-row link between the pair. Both state KRW 1,000,000/month over the same 4+6 semester structure. id 13 holds 7 reviews. id 553's 19,434-character official_details block is copied into id 13 first.

| Field | `13` | `553` |
|---|---|---|
| title | `POSCO TJ Park Foundation Global Scholarship` | `POSCO Global Scholarship in Korea (Global Future Leaders Scholarship Program)` |
| official_source_url | `https://www.postf.org/en/asia/purpose` | `https://www.postf.org/en/asia/abroad/business` |
| catalogue_url | `https://www.postf.org/en/asia/abroad/business` | `https://www.postf.org/en/asia` |
| image_url | `https://postf.org/uploads/media/svg.svg` | `https://www.postf.org/uploads/media/svg_eng.svg` |
| image_kind | `official_logo` | `official_logo` |
| verification_status | `active` | `quarantined` |
| status | `upcoming` | `upcoming` |
| deadline_date | NULL | NULL |
| created_at | `2026-08-30 12:05:32` | `2026-10-04 07:31:16` |
| `official_details` length | 7099 chars | 19434 chars |
| reviews | 7 | 0 |
| verification history rows | 0 | 0 |
| in `retired_records.json` | no | yes |

**Criteria applied**

| Criterion | Reading |
|---|---|
| authoritative source | both resolve to the same awarding body; the two URLs are the same page, differing only in path casing or in one case by a parent-vs-programme relationship |
| completeness | survivor holds 7099 chars of `official_details`; the retired row holds 19434 |
| verification evidence | survivor holds 7 reviews and 0 history rows |
| created/updated provenance | `13` created 2026-08-30, `553` created 2026-10-04 |
| reviews / references | reviews on `13`: 7; on `553`: 0 — this is the deciding criterion |

**Merge performed:** the retired row's `official_details` was copied into `13` before retirement, so the researched block survives with the reviews.

---

## Post-resolution state

- `133`: `is_archived=1`, `verification_status=quarantined`, publicly visible: **no** · survivor `570`: `is_archived=0`, `verification_status=active`
- `438`: `is_archived=1`, `verification_status=quarantined`, publicly visible: **no** · survivor `530`: `is_archived=0`, `verification_status=active`
- `532`: `is_archived=1`, `verification_status=quarantined`, publicly visible: **no** · survivor `68`: `is_archived=0`, `verification_status=active`
- `501`: `is_archived=1`, `verification_status=quarantined`, publicly visible: **no** · survivor `10`: `is_archived=0`, `verification_status=active`
- `531`: `is_archived=1`, `verification_status=quarantined`, publicly visible: **no** · survivor `107`: `is_archived=0`, `verification_status=active`
- `553`: `is_archived=1`, `verification_status=quarantined`, publicly visible: **no** · survivor `13`: `is_archived=0`, `verification_status=active`

**Not applied to Neon.** The `retired_records.json` change is local configuration and would be applied by running the `retire` stage against production in a separate, separately-approved operation.

