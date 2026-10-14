# Phase 2 Post-Merge Contamination Audit

**Generated** 2026-10-06T15:22:55.457272+00:00  
**Access** READ-ONLY. sqlite3 URI file:...?mode=ro&immutable=1 for the current DB, the pre-merge snapshot and both corroborating snapshots. No backup was modified or restored.

---

# Executive Summary

The previous premium-card merge **did write to the live database**, and part of what it wrote is wrong.

## What the merge actually did

`merge_verification_report.json` claims `field_updates_applied: 28` while simultaneously reporting
`db_rows_updated: 0` and `db_rows_unchanged: 691`. Those claims cannot both be true. They were resolved:

| question | answer | how it was established |
|---|---|---|
| Were 28 writes issued? | **Yes** | `backend/migrations/merge_premium_card_research.sql` contains exactly **28 `UPDATE` statements** across ids 162, 271, 272, 273, 285, 299, 356 |
| Were they executed on the current file? | **Yes** | SQL header timestamp `2026-10-06T14:07:37.943949+00:00` is **8.7 ms before** the DB file mtime `2026-10-06T14:07:37.952654` |
| Are the written values in the DB now? | **Yes, 28/28** | every current value equals the merge's `new_value` |
| Why did `db_rows_updated` report 0? | **The check was broken** | `merge_execute.py:115-118` counts updated rows with `WHERE updated_at >= :since`, but none of the 28 UPDATEs assigns `updated_at`, so the query necessarily returns 0 |
| Did 28 values actually change? | **No — only 14** | 14 of the 28 statements wrote a value byte-identical to what was already stored |

## Headline findings

1. **Coimbra data is confirmed inside the Vienna record (DB 162).** The string
   `"Varies by admission cycle (ongoing for enrolled students)"` was written into `deadline_date` of the
   **University of Vienna** row. That string exists in **exactly one** of the 70 research files —
   `research-065`, the **University of Coimbra** record. It is now impossible to tell from the row that the
   value is Portuguese data sitting in an Austrian record, except that `deadline_display` still holds the
   original Vienna text, so the row contradicts itself.
2. **Six rows now store free text inside a `DATE` column.** `deadline_date` is declared `DATE`, but ids 162,
   271, 272, 273, 285 and 356 hold prose such as `"Master's: February 1 (annually). Bachelor's: March 15"`.
   Those 6 rows are the **only** 6 non-ISO-8601 values in the entire 691-row table. Only id 299 received a
   structurally valid date.
3. **Five rows had `NULL` overwritten with the literal `'unknown'`.** `funding_period` is `NULL` in 400 rows
   and holds a real value in 286; exactly 5 rows carry the string `'unknown'`, and those 5 are precisely the
   merge-written rows. `NULL` ("not recorded") was replaced by `'unknown'` ("looked, could not find").
4. **One correct write.** `299.deadline_date = '2026-03-31'` is the only structurally sound, evidence-backed
   deadline write and should be kept.
5. **DB 356 now contradicts a verified DB finding.** The row's `deadline_display` states that *no* deadline is
   published for bilateral state scholarships, yet the merge wrote a specific deadline into `deadline_date`.
6. **The merge left no audit trail.** `scholarship_verification_history` holds 9 rows for the 7 affected ids,
   none for the three fields actually written, and all dated before the merge.

## Verdict distribution

| verdict | count | of which effective changes |
|---|---|---|
| `SAFE_CURRENT_VALUE` | 15 | 1 |
| `BAD_WRITE_REQUIRES_REPAIR` | 11 | 11 |
| `UNCERTAIN_REQUIRES_REVIEW` | 2 | 2 |
| **total** | **28** | **14** |

**`CURRENT_DB_CLEAN: NO`** — incorrect previous premium-card writes remain in the live database.

---

# 28-Write Ledger

Every write is reconstructed from three independent sources that agree exactly:

- `merge_report.json` → `matched_pairs[*].proposed_fields` (the proposals)
- `backend/migrations/merge_premium_card_research.sql` → the 28 executed `UPDATE` statements
- `backend/scholarzone.pre_integrity_repair_20261005_143934.db` → the pre-merge values

**`old_value` verified against the pre-merge snapshot: 28/28.**
**Current DB value equals the merge's `new_value`: 28/28.**

| # | research | DB | field | pre-merge | written | effective? | verdict |
|---|---|---|---|---|---|---|---|
| 1 | research-001 | 271 | `image_url` | `https://www.ku.dk/fileadmi` | `https://www.ku.dk/fileadmi` | **no (no-op)** | `SAFE_CURRENT_VALUE` |
| 2 | research-001 | 271 | `fully_funded` | `0` | `False` | **no (no-op)** | `SAFE_CURRENT_VALUE` |
| 3 | research-001 | 271 | `deadline_date` | `None` | `January 15 (September seme` | yes | `BAD_WRITE_REQUIRES_REPAIR` |
| 4 | research-002 | 272 | `official_source_url` | `https://masters.au.dk/scho` | `https://masters.au.dk/scho` | **no (no-op)** | `SAFE_CURRENT_VALUE` |
| 5 | research-002 | 272 | `funding_period` | `None` | `unknown` | yes | `BAD_WRITE_REQUIRES_REPAIR` |
| 6 | research-002 | 272 | `application_link` | `https://masters.au.dk/scho` | `https://masters.au.dk/scho` | **no (no-op)** | `SAFE_CURRENT_VALUE` |
| 7 | research-002 | 272 | `deadline_date` | `None` | `January 15 (summer/Septemb` | yes | `BAD_WRITE_REQUIRES_REPAIR` |
| 8 | research-004 | 273 | `fully_funded` | `0` | `False` | **no (no-op)** | `SAFE_CURRENT_VALUE` |
| 9 | research-004 | 273 | `funding_period` | `None` | `unknown` | yes | `BAD_WRITE_REQUIRES_REPAIR` |
| 10 | research-004 | 273 | `deadline_date` | `None` | `Master's: February 1 (annu` | yes | `BAD_WRITE_REQUIRES_REPAIR` |
| 11 | research-031 | 285 | `image_url` | `https://stipendiumhungaric` | `https://stipendiumhungaric` | **no (no-op)** | `SAFE_CURRENT_VALUE` |
| 12 | research-031 | 285 | `image_source_type` | `official_provider` | `official_provider` | **no (no-op)** | `SAFE_CURRENT_VALUE` |
| 13 | research-031 | 285 | `funding_period` | `None` | `unknown` | yes | `BAD_WRITE_REQUIRES_REPAIR` |
| 14 | research-031 | 285 | `deadline_date` | `None` | `15 January 2026, 14:00 CET` | yes | `BAD_WRITE_REQUIRES_REPAIR` |
| 15 | research-031 | 285 | `english_requirement` | `None` | `English` | yes | `UNCERTAIN_REQUIRES_REVIEW` |
| 16 | research-032 | 356 | `image_url` | `https://en.tka.hu/tka30-20` | `https://en.tka.hu/tka30-20` | **no (no-op)** | `SAFE_CURRENT_VALUE` |
| 17 | research-032 | 356 | `image_source_type` | `official_provider` | `official_provider` | **no (no-op)** | `SAFE_CURRENT_VALUE` |
| 18 | research-032 | 356 | `image_source_url` | `https://en.tka.hu/` | `https://en.tka.hu/` | **no (no-op)** | `SAFE_CURRENT_VALUE` |
| 19 | research-032 | 356 | `funding_period` | `None` | `unknown` | yes | `BAD_WRITE_REQUIRES_REPAIR` |
| 20 | research-032 | 356 | `deadline_date` | `None` | `19 February 2026, 23:00 CE` | yes | `BAD_WRITE_REQUIRES_REPAIR` |
| 21 | research-032 | 356 | `deadline_precision` | `unknown` | `unknown` | **no (no-op)** | `SAFE_CURRENT_VALUE` |
| 22 | research-058 | 299 | `official_source_url` | `https://www.fct.pt/en/conc` | `https://www.fct.pt/en/conc` | **no (no-op)** | `SAFE_CURRENT_VALUE` |
| 23 | research-058 | 299 | `image_source_type` | `official_provider` | `official_provider` | **no (no-op)** | `SAFE_CURRENT_VALUE` |
| 24 | research-058 | 299 | `application_link` | `https://www.fct.pt/en/conc` | `https://www.fct.pt/en/conc` | **no (no-op)** | `SAFE_CURRENT_VALUE` |
| 25 | research-058 | 299 | `deadline_date` | `None` | `2026-03-31` | yes | `SAFE_CURRENT_VALUE` |
| 26 | research-058 | 299 | `english_requirement` | `None` | `English` | yes | `UNCERTAIN_REQUIRES_REVIEW` |
| 27 | research-065 | 162 | `funding_period` | `None` | `unknown` | yes | `BAD_WRITE_REQUIRES_REPAIR` |
| 28 | research-065 | 162 | `deadline_date` | `None` | `Varies by admission cycle ` | yes | `BAD_WRITE_REQUIRES_REPAIR` |

### Per-write detail

#### 1. DB 271 · `image_url` — SAFE_CURRENT_VALUE

- **Research record** `research-001` — Danish Government Scholarship at the University of Copenhagen
- **Target row** 271 — University of Copenhagen Danish Government Scholarship (Denmark)
- **Phase 1 classification of this research record** `A` (HIGH)
- **Merge confidence** 0.75
- **Pre-merge value** `https://www.ku.dk/fileadmin/_processed_/7/b/csm_Tuition_fees_and_scholarships_NEGATIV_cb3ae2bdeb.png`
- **Written value** `https://www.ku.dk/fileadmin/_processed_/7/b/csm_Tuition_fees_and_scholarships_NEGATIV_cb3ae2bdeb.png`
- **Current DB value** `https://www.ku.dk/fileadmin/_processed_/7/b/csm_Tuition_fees_and_scholarships_NEGATIV_cb3ae2bdeb.png`
- **Effective change** no — value identical to what was already stored
- **Merge-time evidence** `https://www.ku.dk/studies/masters/application-and-admission/scholarships` (official_provider, checked 2026-10-06)
- **Executed SQL** `UPDATE scholarships SET image_url = 'https://www.ku.dk/fileadmin/_processed_/7/b/csm_Tuition_fees_and_scholarships_NEGATIV_cb3ae2bdeb.png' WHERE id = 271;`
- **Verdict** `SAFE_CURRENT_VALUE`
- **Reasoning** No-op. merge old_value and new_value are byte-identical; the pre-merge snapshot confirms the same URL. No value changed.

#### 2. DB 271 · `fully_funded` — SAFE_CURRENT_VALUE

- **Research record** `research-001` — Danish Government Scholarship at the University of Copenhagen
- **Target row** 271 — University of Copenhagen Danish Government Scholarship (Denmark)
- **Phase 1 classification of this research record** `A` (HIGH)
- **Merge confidence** 0.75
- **Pre-merge value** `0`
- **Written value** `False`
- **Current DB value** `0`
- **Effective change** no — value identical to what was already stored
- **Merge-time evidence** `https://www.ku.dk/studies/masters/application-and-admission/scholarships` (official_provider, checked 2026-10-06)
- **Executed SQL** `UPDATE scholarships SET fully_funded = 0 WHERE id = 271;`
- **Verdict** `SAFE_CURRENT_VALUE`
- **Reasoning** No-op. old 0, new False; in SQLite these are the same stored value 0. Pre-merge and current are both 0.

#### 3. DB 271 · `deadline_date` — BAD_WRITE_REQUIRES_REPAIR

- **Research record** `research-001` — Danish Government Scholarship at the University of Copenhagen
- **Target row** 271 — University of Copenhagen Danish Government Scholarship (Denmark)
- **Phase 1 classification of this research record** `A` (HIGH)
- **Merge confidence** 0.75
- **Pre-merge value** `None`
- **Written value** `January 15 (September semester intake); September 1 (February semester intake). For the 2027/2028 cycle: January 15, 2027 (September intake).`
- **Current DB value** `January 15 (September semester intake); September 1 (February semester intake). For the 2027/2028 cycle: January 15, 2027 (September intake).`
- **Effective change** yes
- **Merge-time evidence** `https://www.ku.dk/studies/masters/application-and-admission/scholarships` (official_provider, checked 2026-10-06)
- **Executed SQL** `UPDATE scholarships SET deadline_date = 'January 15 (September semester intake); September 1 (February semester intake). For the 2027/2028 cycle: January 15, 2027 (September intake).' WHERE id = 271;`
- **Verdict** `BAD_WRITE_REQUIRES_REPAIR`
- **Reasoning** Type violation with a defensible source. The value is free text ('January 15 (September semester intake); ...') in a DATE column, and it duplicates deadline_display which states 'No scholarship deadline is published and no application exists'. Evidence quality is acceptable: scholarship_verification_history records that the research URL ku.dk/studies/masters/application-and-admission/scholarships was the previous official_source_url for this row before it redirected, so it is the same official content. Content is plausible; the defect is the column type.
- **Recommended repair** `UPDATE scholarships SET deadline_date = NULL WHERE id = 271;` (confidence HIGH)

#### 4. DB 272 · `official_source_url` — SAFE_CURRENT_VALUE

- **Research record** `research-002` — Danish State Scholarship at Aarhus University
- **Target row** 272 — Aarhus University Danish State Scholarship (Denmark)
- **Phase 1 classification of this research record** `A` (HIGH)
- **Merge confidence** 0.8333333333333334
- **Pre-merge value** `https://masters.au.dk/scholarships-and-grants`
- **Written value** `https://masters.au.dk/scholarships-and-grants`
- **Current DB value** `https://masters.au.dk/scholarships-and-grants`
- **Effective change** no — value identical to what was already stored
- **Merge-time evidence** `https://masters.au.dk/scholarships-and-grants` (official_provider, checked 2026-10-06)
- **Executed SQL** `UPDATE scholarships SET official_source_url = 'https://masters.au.dk/scholarships-and-grants' WHERE id = 272;`
- **Verdict** `SAFE_CURRENT_VALUE`
- **Reasoning** No-op. old_value == new_value, identical to the pre-merge snapshot and to the current value.

#### 5. DB 272 · `funding_period` — BAD_WRITE_REQUIRES_REPAIR

- **Research record** `research-002` — Danish State Scholarship at Aarhus University
- **Target row** 272 — Aarhus University Danish State Scholarship (Denmark)
- **Phase 1 classification of this research record** `A` (HIGH)
- **Merge confidence** 0.8333333333333334
- **Pre-merge value** `None`
- **Written value** `unknown`
- **Current DB value** `unknown`
- **Effective change** yes
- **Merge-time evidence** `https://masters.au.dk/scholarships-and-grants` (official_provider, checked 2026-10-06)
- **Executed SQL** `UPDATE scholarships SET funding_period = 'unknown' WHERE id = 272;`
- **Verdict** `BAD_WRITE_REQUIRES_REPAIR`
- **Reasoning** Degradation of an empty field. NULL (not recorded) was replaced by the string 'unknown' (looked and failed). The rest of the table uses NULL in 400 rows; only the 5 merge-written rows use 'unknown'. No informational gain.
- **Recommended repair** `UPDATE scholarships SET funding_period = NULL WHERE id = 272;` (confidence HIGH)

#### 6. DB 272 · `application_link` — SAFE_CURRENT_VALUE

- **Research record** `research-002` — Danish State Scholarship at Aarhus University
- **Target row** 272 — Aarhus University Danish State Scholarship (Denmark)
- **Phase 1 classification of this research record** `A` (HIGH)
- **Merge confidence** 0.8333333333333334
- **Pre-merge value** `https://masters.au.dk/scholarships-and-grants`
- **Written value** `https://masters.au.dk/scholarships-and-grants`
- **Current DB value** `https://masters.au.dk/scholarships-and-grants`
- **Effective change** no — value identical to what was already stored
- **Merge-time evidence** `https://masters.au.dk/scholarships-and-grants` (official_provider, checked 2026-10-06)
- **Executed SQL** `UPDATE scholarships SET application_link = 'https://masters.au.dk/scholarships-and-grants' WHERE id = 272;`
- **Verdict** `SAFE_CURRENT_VALUE`
- **Reasoning** No-op. old_value == new_value.

#### 7. DB 272 · `deadline_date` — BAD_WRITE_REQUIRES_REPAIR

- **Research record** `research-002` — Danish State Scholarship at Aarhus University
- **Target row** 272 — Aarhus University Danish State Scholarship (Denmark)
- **Phase 1 classification of this research record** `A` (HIGH)
- **Merge confidence** 0.8333333333333334
- **Pre-merge value** `None`
- **Written value** `January 15 (summer/September intake); September 15 (winter/February intake). For 2027/2028 cycle: January 15, 2027.`
- **Current DB value** `January 15 (summer/September intake); September 15 (winter/February intake). For 2027/2028 cycle: January 15, 2027.`
- **Effective change** yes
- **Merge-time evidence** `https://masters.au.dk/scholarships-and-grants` (official_provider, checked 2026-10-06)
- **Executed SQL** `UPDATE scholarships SET deadline_date = 'January 15 (summer/September intake); September 15 (winter/February intake). For 2027/2028 cycle: January 15, 2027.' WHERE id = 272;`
- **Verdict** `BAD_WRITE_REQUIRES_REPAIR`
- **Reasoning** Type violation. Free text in a DATE column. Content matches the row's own deadline_display narrative and the source URL masters.au.dk/scholarships-and-grants is the row's own official_source_url, so the source is sound; the defect is the stored type.
- **Recommended repair** `UPDATE scholarships SET deadline_date = NULL WHERE id = 272;` (confidence HIGH)

#### 8. DB 273 · `fully_funded` — SAFE_CURRENT_VALUE

- **Research record** `research-004` — Danish Government Scholarship at the University of Southern Denmark (SDU)
- **Target row** 273 — University of Southern Denmark (SDU) Danish Government Scholarship (Denmark)
- **Phase 1 classification of this research record** `A` (HIGH)
- **Merge confidence** 0.8
- **Pre-merge value** `0`
- **Written value** `False`
- **Current DB value** `0`
- **Effective change** no — value identical to what was already stored
- **Merge-time evidence** `https://www.sdu.dk/en/uddannelse/fees_and_funding/scholarships` (official_provider, checked 2026-10-06)
- **Executed SQL** `UPDATE scholarships SET fully_funded = 0 WHERE id = 273;`
- **Verdict** `SAFE_CURRENT_VALUE`
- **Reasoning** No-op. old 0, new False - same stored value.

#### 9. DB 273 · `funding_period` — BAD_WRITE_REQUIRES_REPAIR

- **Research record** `research-004` — Danish Government Scholarship at the University of Southern Denmark (SDU)
- **Target row** 273 — University of Southern Denmark (SDU) Danish Government Scholarship (Denmark)
- **Phase 1 classification of this research record** `A` (HIGH)
- **Merge confidence** 0.8
- **Pre-merge value** `None`
- **Written value** `unknown`
- **Current DB value** `unknown`
- **Effective change** yes
- **Merge-time evidence** `https://www.sdu.dk/en/uddannelse/fees_and_funding/scholarships` (official_provider, checked 2026-10-06)
- **Executed SQL** `UPDATE scholarships SET funding_period = 'unknown' WHERE id = 273;`
- **Verdict** `BAD_WRITE_REQUIRES_REPAIR`
- **Reasoning** Same degradation as DB 272. NULL replaced by 'unknown'.
- **Recommended repair** `UPDATE scholarships SET funding_period = NULL WHERE id = 273;` (confidence HIGH)

#### 10. DB 273 · `deadline_date` — BAD_WRITE_REQUIRES_REPAIR

- **Research record** `research-004` — Danish Government Scholarship at the University of Southern Denmark (SDU)
- **Target row** 273 — University of Southern Denmark (SDU) Danish Government Scholarship (Denmark)
- **Phase 1 classification of this research record** `A` (HIGH)
- **Merge confidence** 0.8
- **Pre-merge value** `None`
- **Written value** `Master's: February 1 (annually). Bachelor's: March 15 (with uniTEST). For 2027 intake: Master's February 1, 2027.`
- **Current DB value** `Master's: February 1 (annually). Bachelor's: March 15 (with uniTEST). For 2027 intake: Master's February 1, 2027.`
- **Effective change** yes
- **Merge-time evidence** `https://www.sdu.dk/en/uddannelse/fees_and_funding/scholarships` (official_provider, checked 2026-10-06)
- **Executed SQL** `UPDATE scholarships SET deadline_date = 'Master''s: February 1 (annually). Bachelor''s: March 15 (with uniTEST). For 2027 intake: Master''s February 1, 2027.' WHERE id = 273;`
- **Verdict** `BAD_WRITE_REQUIRES_REPAIR`
- **Reasoning** Type violation. Free text in a DATE column; the row already carries the same information in deadline_display. The source URL sdu.dk/en/uddannelse/fees_and_funding/scholarships is this row's official_updates_url, so the evidence is legitimate; the defect is the stored type.
- **Recommended repair** `UPDATE scholarships SET deadline_date = NULL WHERE id = 273;` (confidence HIGH)

#### 11. DB 285 · `image_url` — SAFE_CURRENT_VALUE

- **Research record** `research-031` — Stipendium Hungaricum Scholarship
- **Target row** 285 — Stipendium Hungaricum Scholarship Programme (Hungary)
- **Phase 1 classification of this research record** `A` (HIGH)
- **Merge confidence** 0.75
- **Pre-merge value** `https://stipendiumhungaricum.hu/includes/images/SH_logo_sziv.png`
- **Written value** `https://stipendiumhungaricum.hu/includes/images/SH_logo_sziv.png`
- **Current DB value** `https://stipendiumhungaricum.hu/includes/images/SH_logo_sziv.png`
- **Effective change** no — value identical to what was already stored
- **Merge-time evidence** `https://stipendiumhungaricum.hu/` (official_provider, checked 2026-10-06)
- **Executed SQL** `UPDATE scholarships SET image_url = 'https://stipendiumhungaricum.hu/includes/images/SH_logo_sziv.png' WHERE id = 285;`
- **Verdict** `SAFE_CURRENT_VALUE`
- **Reasoning** No-op. old_value == new_value.

#### 12. DB 285 · `image_source_type` — SAFE_CURRENT_VALUE

- **Research record** `research-031` — Stipendium Hungaricum Scholarship
- **Target row** 285 — Stipendium Hungaricum Scholarship Programme (Hungary)
- **Phase 1 classification of this research record** `A` (HIGH)
- **Merge confidence** 0.75
- **Pre-merge value** `official_provider`
- **Written value** `official_provider`
- **Current DB value** `official_provider`
- **Effective change** no — value identical to what was already stored
- **Merge-time evidence** `https://stipendiumhungaricum.hu/` (official_provider, checked 2026-10-06)
- **Executed SQL** `UPDATE scholarships SET image_source_type = 'official_provider' WHERE id = 285;`
- **Verdict** `SAFE_CURRENT_VALUE`
- **Reasoning** No-op. old_value == new_value.

#### 13. DB 285 · `funding_period` — BAD_WRITE_REQUIRES_REPAIR

- **Research record** `research-031` — Stipendium Hungaricum Scholarship
- **Target row** 285 — Stipendium Hungaricum Scholarship Programme (Hungary)
- **Phase 1 classification of this research record** `A` (HIGH)
- **Merge confidence** 0.75
- **Pre-merge value** `None`
- **Written value** `unknown`
- **Current DB value** `unknown`
- **Effective change** yes
- **Merge-time evidence** `https://stipendiumhungaricum.hu/` (official_provider, checked 2026-10-06)
- **Executed SQL** `UPDATE scholarships SET funding_period = 'unknown' WHERE id = 285;`
- **Verdict** `BAD_WRITE_REQUIRES_REPAIR`
- **Reasoning** Same degradation as DB 272. NULL replaced by 'unknown'.
- **Recommended repair** `UPDATE scholarships SET funding_period = NULL WHERE id = 285;` (confidence HIGH)

#### 14. DB 285 · `deadline_date` — BAD_WRITE_REQUIRES_REPAIR

- **Research record** `research-031` — Stipendium Hungaricum Scholarship
- **Target row** 285 — Stipendium Hungaricum Scholarship Programme (Hungary)
- **Phase 1 classification of this research record** `A` (HIGH)
- **Merge confidence** 0.75
- **Pre-merge value** `None`
- **Written value** `15 January 2026, 14:00 CET`
- **Current DB value** `15 January 2026, 14:00 CET`
- **Effective change** yes
- **Merge-time evidence** `https://stipendiumhungaricum.hu/` (official_provider, checked 2026-10-06)
- **Executed SQL** `UPDATE scholarships SET deadline_date = '15 January 2026, 14:00 CET' WHERE id = 285;`
- **Verdict** `BAD_WRITE_REQUIRES_REPAIR`
- **Reasoning** Type violation plus redundancy. Free text '15 January 2026, 14:00 CET' in a DATE column, restating the same deadline the row already records in deadline_display as '15th January 2026, 2 pm (CET) - APPLICATION DEADLINE (2026/2027 cycle)'. Source URL is the row's own official_source_url, so the source is sound.
- **Recommended repair** `UPDATE scholarships SET deadline_date = NULL WHERE id = 285;` (confidence HIGH)

#### 15. DB 285 · `english_requirement` — UNCERTAIN_REQUIRES_REVIEW

- **Research record** `research-031` — Stipendium Hungaricum Scholarship
- **Target row** 285 — Stipendium Hungaricum Scholarship Programme (Hungary)
- **Phase 1 classification of this research record** `A` (HIGH)
- **Merge confidence** 0.75
- **Pre-merge value** `None`
- **Written value** `English`
- **Current DB value** `English`
- **Effective change** yes
- **Merge-time evidence** `https://stipendiumhungaricum.hu/` (official_provider, checked 2026-10-06)
- **Executed SQL** `UPDATE scholarships SET english_requirement = 'English' WHERE id = 285;`
- **Verdict** `UNCERTAIN_REQUIRES_REVIEW`
- **Reasoning** Plausible but unproven. research-031 asserts 'English' from the programme homepage stipendiumhungaricum.hu, which is the row's own official_source_url, so the source is legitimate. However no official language requirement statement was captured, and Stipendium Hungaricum is administered in several languages. Setting a populated value on an EMPTY field is the highest-risk class of merge write because it forecloses later correction - the merge would have skipped this field on any future run since old_value is now non-empty.

#### 16. DB 356 · `image_url` — SAFE_CURRENT_VALUE

- **Research record** `research-032` — Hungarian Bilateral State Scholarships
- **Target row** 356 — Hungarian Bilateral State Scholarships (Hungary)
- **Phase 1 classification of this research record** `A` (HIGH)
- **Merge confidence** 1.0
- **Pre-merge value** `https://en.tka.hu/tka30-200x80-en.svg`
- **Written value** `https://en.tka.hu/tka30-200x80-en.svg`
- **Current DB value** `https://en.tka.hu/tka30-200x80-en.svg`
- **Effective change** no — value identical to what was already stored
- **Merge-time evidence** `https://en.tka.hu/` (official_provider, checked 2026-10-06)
- **Executed SQL** `UPDATE scholarships SET image_url = 'https://en.tka.hu/tka30-200x80-en.svg' WHERE id = 356;`
- **Verdict** `SAFE_CURRENT_VALUE`
- **Reasoning** No-op. old_value == new_value.

#### 17. DB 356 · `image_source_type` — SAFE_CURRENT_VALUE

- **Research record** `research-032` — Hungarian Bilateral State Scholarships
- **Target row** 356 — Hungarian Bilateral State Scholarships (Hungary)
- **Phase 1 classification of this research record** `A` (HIGH)
- **Merge confidence** 1.0
- **Pre-merge value** `official_provider`
- **Written value** `official_provider`
- **Current DB value** `official_provider`
- **Effective change** no — value identical to what was already stored
- **Merge-time evidence** `https://en.tka.hu/` (official_provider, checked 2026-10-06)
- **Executed SQL** `UPDATE scholarships SET image_source_type = 'official_provider' WHERE id = 356;`
- **Verdict** `SAFE_CURRENT_VALUE`
- **Reasoning** No-op. old_value == new_value.

#### 18. DB 356 · `image_source_url` — SAFE_CURRENT_VALUE

- **Research record** `research-032` — Hungarian Bilateral State Scholarships
- **Target row** 356 — Hungarian Bilateral State Scholarships (Hungary)
- **Phase 1 classification of this research record** `A` (HIGH)
- **Merge confidence** 1.0
- **Pre-merge value** `https://en.tka.hu/`
- **Written value** `https://en.tka.hu/`
- **Current DB value** `https://en.tka.hu/`
- **Effective change** no — value identical to what was already stored
- **Merge-time evidence** `https://en.tka.hu/` (official_provider, checked 2026-10-06)
- **Executed SQL** `UPDATE scholarships SET image_source_url = 'https://en.tka.hu/' WHERE id = 356;`
- **Verdict** `SAFE_CURRENT_VALUE`
- **Reasoning** No-op. old_value == new_value.

#### 19. DB 356 · `funding_period` — BAD_WRITE_REQUIRES_REPAIR

- **Research record** `research-032` — Hungarian Bilateral State Scholarships
- **Target row** 356 — Hungarian Bilateral State Scholarships (Hungary)
- **Phase 1 classification of this research record** `A` (HIGH)
- **Merge confidence** 1.0
- **Pre-merge value** `None`
- **Written value** `unknown`
- **Current DB value** `unknown`
- **Effective change** yes
- **Merge-time evidence** `https://en.tka.hu/` (official_provider, checked 2026-10-06)
- **Executed SQL** `UPDATE scholarships SET funding_period = 'unknown' WHERE id = 356;`
- **Verdict** `BAD_WRITE_REQUIRES_REPAIR`
- **Reasoning** Same degradation as DB 272. NULL replaced by 'unknown'.
- **Recommended repair** `UPDATE scholarships SET funding_period = NULL WHERE id = 356;` (confidence HIGH)

#### 20. DB 356 · `deadline_date` — BAD_WRITE_REQUIRES_REPAIR

- **Research record** `research-032` — Hungarian Bilateral State Scholarships
- **Target row** 356 — Hungarian Bilateral State Scholarships (Hungary)
- **Phase 1 classification of this research record** `A` (HIGH)
- **Merge confidence** 1.0
- **Pre-merge value** `None`
- **Written value** `19 February 2026, 23:00 CET (27 February 2026, 17:00 for summer courses)`
- **Current DB value** `19 February 2026, 23:00 CET (27 February 2026, 17:00 for summer courses)`
- **Effective change** yes
- **Merge-time evidence** `https://en.tka.hu/` (official_provider, checked 2026-10-06)
- **Executed SQL** `UPDATE scholarships SET deadline_date = '19 February 2026, 23:00 CET (27 February 2026, 17:00 for summer courses)' WHERE id = 356;`
- **Verdict** `BAD_WRITE_REQUIRES_REPAIR`
- **Reasoning** Factual contradiction, the most serious defect on a correctly-matched row. The written value asserts a specific deadline '19 February 2026, 23:00 CET (27 February 2026, 17:00 for summer courses)', but the row's own verified deadline_display states: 'No application deadline is published on the Tempus Public Foundation pages for bilateral state scholarships; applications are submitted into the Foundation's online system and assessed on a rolling basis per bilateral partner.' The merge took the unverified research assertion over a verified DB finding, and did so in a DATE column. A downstream consumer filtering on deadline_date would now surface a deadline the awarding body does not publish.
- **Recommended repair** `UPDATE scholarships SET deadline_date = NULL WHERE id = 356;` (confidence HIGH)

#### 21. DB 356 · `deadline_precision` — SAFE_CURRENT_VALUE

- **Research record** `research-032` — Hungarian Bilateral State Scholarships
- **Target row** 356 — Hungarian Bilateral State Scholarships (Hungary)
- **Phase 1 classification of this research record** `A` (HIGH)
- **Merge confidence** 1.0
- **Pre-merge value** `unknown`
- **Written value** `unknown`
- **Current DB value** `unknown`
- **Effective change** no — value identical to what was already stored
- **Merge-time evidence** `https://en.tka.hu/` (official_provider, checked 2026-10-06)
- **Executed SQL** `UPDATE scholarships SET deadline_precision = 'unknown' WHERE id = 356;`
- **Verdict** `SAFE_CURRENT_VALUE`
- **Reasoning** No-op. old 'unknown', new 'unknown'.

#### 22. DB 299 · `official_source_url` — SAFE_CURRENT_VALUE

- **Research record** `research-058` — FCT PhD Studentships 2026 – Regular Line of Application
- **Target row** 299 — 2026 Call for PhD Studentships – Regular Line of Application (FCT) (Portugal)
- **Phase 1 classification of this research record** `A` (HIGH)
- **Merge confidence** 0.8
- **Pre-merge value** `https://www.fct.pt/en/concursos/concurso-bolsas-de-doutoramento-2026-linha-de-candidatura-geral`
- **Written value** `https://www.fct.pt/en/concursos/concurso-bolsas-de-doutoramento-2026-linha-de-candidatura-geral`
- **Current DB value** `https://www.fct.pt/en/concursos/concurso-bolsas-de-doutoramento-2026-linha-de-candidatura-geral`
- **Effective change** no — value identical to what was already stored
- **Merge-time evidence** `https://www.fct.pt/en/concursos/concurso-bolsas-de-doutoramento-2026-linha-de-candidatura-geral` (official_provider, checked 2026-10-06)
- **Executed SQL** `UPDATE scholarships SET official_source_url = 'https://www.fct.pt/en/concursos/concurso-bolsas-de-doutoramento-2026-linha-de-candidatura-geral' WHERE id = 299;`
- **Verdict** `SAFE_CURRENT_VALUE`
- **Reasoning** No-op. old_value == new_value.

#### 23. DB 299 · `image_source_type` — SAFE_CURRENT_VALUE

- **Research record** `research-058` — FCT PhD Studentships 2026 – Regular Line of Application
- **Target row** 299 — 2026 Call for PhD Studentships – Regular Line of Application (FCT) (Portugal)
- **Phase 1 classification of this research record** `A` (HIGH)
- **Merge confidence** 0.8
- **Pre-merge value** `official_provider`
- **Written value** `official_provider`
- **Current DB value** `official_provider`
- **Effective change** no — value identical to what was already stored
- **Merge-time evidence** `https://www.fct.pt/en/concursos/concurso-bolsas-de-doutoramento-2026-linha-de-candidatura-geral` (official_provider, checked 2026-10-06)
- **Executed SQL** `UPDATE scholarships SET image_source_type = 'official_provider' WHERE id = 299;`
- **Verdict** `SAFE_CURRENT_VALUE`
- **Reasoning** No-op. old_value == new_value.

#### 24. DB 299 · `application_link` — SAFE_CURRENT_VALUE

- **Research record** `research-058` — FCT PhD Studentships 2026 – Regular Line of Application
- **Target row** 299 — 2026 Call for PhD Studentships – Regular Line of Application (FCT) (Portugal)
- **Phase 1 classification of this research record** `A` (HIGH)
- **Merge confidence** 0.8
- **Pre-merge value** `https://www.fct.pt/en/concursos/concurso-bolsas-de-doutoramento-2026-linha-de-candidatura-geral`
- **Written value** `https://www.fct.pt/en/concursos/concurso-bolsas-de-doutoramento-2026-linha-de-candidatura-geral`
- **Current DB value** `https://www.fct.pt/en/concursos/concurso-bolsas-de-doutoramento-2026-linha-de-candidatura-geral`
- **Effective change** no — value identical to what was already stored
- **Merge-time evidence** `https://www.fct.pt/en/concursos/concurso-bolsas-de-doutoramento-2026-linha-de-candidatura-geral` (official_provider, checked 2026-10-06)
- **Executed SQL** `UPDATE scholarships SET application_link = 'https://www.fct.pt/en/concursos/concurso-bolsas-de-doutoramento-2026-linha-de-candidatura-geral' WHERE id = 299;`
- **Verdict** `SAFE_CURRENT_VALUE`
- **Reasoning** No-op. old_value == new_value.

#### 25. DB 299 · `deadline_date` — SAFE_CURRENT_VALUE

- **Research record** `research-058` — FCT PhD Studentships 2026 – Regular Line of Application
- **Target row** 299 — 2026 Call for PhD Studentships – Regular Line of Application (FCT) (Portugal)
- **Phase 1 classification of this research record** `A` (HIGH)
- **Merge confidence** 0.8
- **Pre-merge value** `None`
- **Written value** `2026-03-31`
- **Current DB value** `2026-03-31`
- **Effective change** yes
- **Merge-time evidence** `https://www.fct.pt/en/concursos/concurso-bolsas-de-doutoramento-2026-linha-de-candidatura-geral` (official_provider, checked 2026-10-06)
- **Executed SQL** `UPDATE scholarships SET deadline_date = '2026-03-31' WHERE id = 299;`
- **Verdict** `SAFE_CURRENT_VALUE`
- **Reasoning** CORRECT WRITE. '2026-03-31' is a valid ISO-8601 date - the only structurally sound deadline write of the merge. It agrees with the row's pre-existing deadline_display, which quotes the official wording: 'The Call is open from March 2nd to 5:00 pm (Lisbon time) March 31st, 2026.' The source URL is byte-identical to the row's own official_source_url. This write should be kept.

#### 26. DB 299 · `english_requirement` — UNCERTAIN_REQUIRES_REVIEW

- **Research record** `research-058` — FCT PhD Studentships 2026 – Regular Line of Application
- **Target row** 299 — 2026 Call for PhD Studentships – Regular Line of Application (FCT) (Portugal)
- **Phase 1 classification of this research record** `A` (HIGH)
- **Merge confidence** 0.8
- **Pre-merge value** `None`
- **Written value** `English`
- **Current DB value** `English`
- **Effective change** yes
- **Merge-time evidence** `https://www.fct.pt/en/concursos/concurso-bolsas-de-doutoramento-2026-linha-de-candidatura-geral` (official_provider, checked 2026-10-06)
- **Executed SQL** `UPDATE scholarships SET english_requirement = 'English' WHERE id = 299;`
- **Verdict** `UNCERTAIN_REQUIRES_REVIEW`
- **Reasoning** Plausible but unproven, and possibly incomplete. FCT publishes its calls bilingually (Portuguese and English); asserting english_requirement='English' from a single English URL does not establish the requirement. Same empty-field-foreclosure risk as DB 285.

#### 27. DB 162 · `funding_period` — BAD_WRITE_REQUIRES_REPAIR

- **Research record** `research-065` — University of Coimbra Merit Scholarships for International Students
- **Target row** 162 — University of Vienna Scholarships for International Students (Austria)
- **Phase 1 classification of this research record** `D` (HIGH)
- **Merge confidence** 0.75
- **Pre-merge value** `None`
- **Written value** `unknown`
- **Current DB value** `unknown`
- **Effective change** yes
- **Merge-time evidence** `https://www.uc.pt/en/studyatuc/international-students/bolsas-de-merito/` (official_provider, checked 2026-10-06)
- **Executed SQL** `UPDATE scholarships SET funding_period = 'unknown' WHERE id = 162;`
- **Verdict** `BAD_WRITE_REQUIRES_REPAIR`
- **Reasoning** Write was unjustified because the source research record was never about this row. research-065 is Universidade de Coimbra (Portugal); DB 162 is the University of Vienna (Austria). Country, institution, domain and provider all conflict. The literal 'unknown' carries no Coimbra content, but writing to a row that the evidence does not describe is still contamination. It is also off-convention: the DB expresses 'not recorded' as NULL in 400 of 691 rows and only these 5 merge-written rows carry the string 'unknown'.
- **Recommended repair** `UPDATE scholarships SET funding_period = NULL WHERE id = 162;` (confidence HIGH)

#### 28. DB 162 · `deadline_date` — BAD_WRITE_REQUIRES_REPAIR

- **Research record** `research-065` — University of Coimbra Merit Scholarships for International Students
- **Target row** 162 — University of Vienna Scholarships for International Students (Austria)
- **Phase 1 classification of this research record** `D` (HIGH)
- **Merge confidence** 0.75
- **Pre-merge value** `None`
- **Written value** `Varies by admission cycle (ongoing for enrolled students)`
- **Current DB value** `Varies by admission cycle (ongoing for enrolled students)`
- **Effective change** yes
- **Merge-time evidence** `https://www.uc.pt/en/studyatuc/international-students/bolsas-de-merito/` (official_provider, checked 2026-10-06)
- **Executed SQL** `UPDATE scholarships SET deadline_date = 'Varies by admission cycle (ongoing for enrolled students)' WHERE id = 162;`
- **Verdict** `BAD_WRITE_REQUIRES_REPAIR`
- **Reasoning** PROVEN Coimbra contamination. The written string 'Varies by admission cycle (ongoing for enrolled students)' occurs in exactly ONE of the 70 research files - research-065 (Coimbra) - and in no other record anywhere. It was written into the University of Vienna row. The row's own verified deadline_display still reads 'Varies (typically March-May for winter semester)', so the row now carries two contradictory deadline statements, one of them belonging to a different country's university. It is also free text inside a DATE column.
- **Recommended repair** `UPDATE scholarships SET deadline_date = NULL WHERE id = 162;` (confidence HIGH)

---

# Affected DB Rows

| DB id | title | country | research | merge conf | Phase 1 | fields written | effective | repairs needed |
|---|---|---|---|---|---|---|---|---|
| **162** | University of Vienna Scholarships for International  | Austria | research-065 | 0.75 | `D` | 2 | 2 | **2** |
| **271** | University of Copenhagen Danish Government Scholarsh | Denmark | research-001 | 0.75 | `A` | 3 | 1 | **1** |
| **272** | Aarhus University Danish State Scholarship | Denmark | research-002 | 0.8333333333333334 | `A` | 4 | 2 | **2** |
| **273** | University of Southern Denmark (SDU) Danish Governme | Denmark | research-004 | 0.8 | `A` | 3 | 2 | **2** |
| **285** | Stipendium Hungaricum Scholarship Programme | Hungary | research-031 | 0.75 | `A` | 5 | 3 | **2 +1 uncertain** |
| **299** | 2026 Call for PhD Studentships – Regular Line of App | Portugal | research-058 | 0.8 | `A` | 5 | 2 | **0 +1 uncertain** |
| **356** | Hungarian Bilateral State Scholarships | Hungary | research-032 | 1.0 | `A` | 6 | 2 | **2** |

### Systemic signature of the merge across the whole table

These are not coincidences — they are the merge's fingerprints, and each one independently corroborates that
the merge is the only writer of these value shapes:

| signature | count in table | count attributable to merge |
|---|---|---|
| `deadline_date` not matching `YYYY-MM-DD` | 6 | **6** (162, 271, 272, 273, 285, 356) |
| `funding_period = 'unknown'` | 5 | **5** (162, 272, 273, 285, 356) |
| `english_requirement = 'English'` on a merge-touched row | 2 | **2** (285, 299) |
| rows referencing Coimbra / uc.pt / Aveiro / ua.pt | 0 | 0 |

`english_requirement = 'English'` appears on only 4 rows: ids 16 and 18 (both natively verified 2026-10-06) and
ids 285 and 299, which are merge targets last verified 2026-10-04, i.e. **before** the merge.

### Deltas that are NOT merge contamination

These changed between the pre-merge snapshot and the current DB but are NOT merge proposals. They belong to the 2026-10-05T14:39:34 integrity-repair batch, identified by matching the current updated_at timestamps. They are listed so they are not misattributed to the premium-card merge, and are NOT part of this repair plan.

| DB id | non-merge changes |
|---|---|
| 162 | funding 'Partial'->'Partially Funded', region NULL->'Europe', updated_at |
| 271 | tuition_coverage NULL->1, living_cost_coverage NULL->1, travel_coverage NULL->0, updated_at |
| 272 | tuition_coverage NULL->1, travel_coverage NULL->0, updated_at |
| 273 | tuition_coverage NULL->1, living_cost_coverage NULL->0, travel_coverage NULL->0, updated_at |
| 285 | tuition_coverage NULL->1, living_cost_coverage NULL->0, updated_at |
| 299 | tuition_coverage NULL->1, living_cost_coverage NULL->0, travel_coverage NULL->0, fully_funded 0->1, updated_at |
| 356 | funding 'Fully funded'->'Fully Funded', updated_at |

---

# DB 162 Deep Audit

**No repair was executed.** Reported only.

| property | current value |
|---|---|
| Title | `University of Vienna Scholarships for International Students` |
| Provider (`official_source`) | `University of Vienna` |
| Institution | `University of Vienna (institution is stated in official_source and in the image alt text; there is no dedicated institut` |
| Country | `Austria` |
| Official source URL | `https://studieren.univie.ac.at/en/scholarships` |
| Application link | `https://studieren.univie.ac.at/en/scholarships` |
| Image URL | `https://studieren.univie.ac.at/fileadmin/templates/GLOBAL/IMG/uni_logo.png` |
| Image alt text | `University of Vienna` |
| Eligibility summary | `International students enrolled at the University of Vienna. Various scholarships available based on academic merit and ` |

## Every field the previous merge changed on DB 162

| field | pre-merge | current | merge source URL | verdict |
|---|---|---|---|---|
| `funding_period` | `None` | `unknown` | `https://www.uc.pt/en/studyatuc/international-students/bolsas-de-merito/` | `BAD_WRITE_REQUIRES_REPAIR` |
| `deadline_date` | `None` | `Varies by admission cycle (ongoing for enrolled students)` | `https://www.uc.pt/en/studyatuc/international-students/bolsas-de-merito/` | `BAD_WRITE_REQUIRES_REPAIR` |

## Was Coimbra-derived data written into the Vienna record?

### YES — confirmed.

| | research-065 | DB 162 |
|---|---|---|
| title | University of Coimbra Merit Scholarships for International Students | University of Vienna Scholarships for International Students |
| provider | Universidade de Coimbra (UC) | University of Vienna |
| country | Portugal | Austria |
| URL | `https://www.uc.pt/en/studyatuc/international-students/bolsas-de-merito/` | `https://studieren.univie.ac.at/en/scholarships` |

### Provenance of the leaked string

| property | value |
|---|---|
| leaked string | `"Varies by admission cycle (ongoing for enrolled students)"` |
| research files containing it | **1 of 70** |
| which | `scholarship_065_University_of_Coimbra_Merit_Scholarships.json` (`research-065`) |
| target field | `scholarships.deadline_date` |

### Why only this field leaked

merge_execute.py skips any field whose pre-existing old_value is non-empty and differs from the new value (line 94). DB 162's official_source_url, official_source, funding, application_link, deadline_display and deadline_precision were all already populated, so the Coimbra values were rejected as conflicts and never written. Only the two empty fields - deadline_date and funding_period - were writable, and those are exactly the two that were written.

Fields that **would** have carried Coimbra content but were correctly rejected as conflicts and never written:

- `official_source_url`
- `official_source`
- `funding`
- `application_method`
- `application_link`
- `deadline_display`
- `deadline_precision`
- `eligibility`

### The row now contradicts itself

| column | value | belongs to |
|---|---|---|
| `deadline_date` | `Varies by admission cycle (ongoing for enrolled students)` | **Coimbra, Portugal** |
| `deadline_display` | `Varies (typically March-May for winter semester)` | **Vienna, Austria** (original) |

A consumer that prefers `deadline_date` over `deadline_display` — which is the natural reading of the schema,
given `deadline_date` is the typed column — will serve the Coimbra deadline for the Vienna scholarship.

### Recommended repair for DB 162 (not executed)

```sql
UPDATE scholarships SET deadline_date = NULL WHERE id = 162;
```
```sql
UPDATE scholarships SET funding_period = NULL WHERE id = 162;
```

Confidence **HIGH - both pre-merge values are NULL and are confirmed identically in three independent snapshots.**. Both pre-merge values are `NULL` and are confirmed identically in
three independent snapshots (`pre_integrity_repair_20261005_143934.db`, `wave13_local.db`,
`pre_wave13_master_20261004_201056.db`).

---

# Incorrect Writes

**11 writes require repair.** All 11 are effective changes. All pre-merge values are provable.

| # | DB | field | incorrect current value | provable pre-merge value | recommended repair | conf |
|---|---|---|---|---|---|---|
| 3 | **271** | `deadline_date` | `January 15 (September semester intake); Sept` | `None` | `deadline_date = NULL` | HIGH |
| 5 | **272** | `funding_period` | `unknown` | `None` | `funding_period = NULL` | HIGH |
| 7 | **272** | `deadline_date` | `January 15 (summer/September intake); Septem` | `None` | `deadline_date = NULL` | HIGH |
| 9 | **273** | `funding_period` | `unknown` | `None` | `funding_period = NULL` | HIGH |
| 10 | **273** | `deadline_date` | `Master's: February 1 (annually). Bachelor's:` | `None` | `deadline_date = NULL` | HIGH |
| 13 | **285** | `funding_period` | `unknown` | `None` | `funding_period = NULL` | HIGH |
| 14 | **285** | `deadline_date` | `15 January 2026, 14:00 CET` | `None` | `deadline_date = NULL` | HIGH |
| 19 | **356** | `funding_period` | `unknown` | `None` | `funding_period = NULL` | HIGH |
| 20 | **356** | `deadline_date` | `19 February 2026, 23:00 CET (27 February 202` | `None` | `deadline_date = NULL` | HIGH |
| 27 | **162** | `funding_period` | `unknown` | `None` | `funding_period = NULL` | HIGH |
| 28 | **162** | `deadline_date` | `Varies by admission cycle (ongoing for enrol` | `None` | `deadline_date = NULL` | HIGH |

### Grouped by defect class

**Class A — cross-institution contamination (2 writes, DB 162).** Source record described a different
university in a different country. Unjustified regardless of value content.

- `162.funding_period` — was `None`, now `unknown`
- `162.deadline_date` — was `None`, now `Varies by admission cycle (ongoing for enrolled students)`

**Class B — type violation: prose in a `DATE` column (6 writes).** `deadline_date` is `DATE`; these 6 rows hold
free text. Source URLs are legitimate (each is the row's own official or updates URL) and the content is
plausible, but the value cannot be parsed, compared or sorted as a date.

- `271.deadline_date` (from `research-001`) — now `January 15 (September semester intake); September 1 (February semester`
- `272.deadline_date` (from `research-002`) — now `January 15 (summer/September intake); September 15 (winter/February in`
- `273.deadline_date` (from `research-004`) — now `Master's: February 1 (annually). Bachelor's: March 15 (with uniTEST). `
- `285.deadline_date` (from `research-031`) — now `15 January 2026, 14:00 CET`
- `356.deadline_date` (from `research-032`) — now `19 February 2026, 23:00 CET (27 February 2026, 17:00 for summer course`
- `162.deadline_date` (from `research-065`) — now `Varies by admission cycle (ongoing for enrolled students)`

**Class C — `NULL` degraded to `'unknown'` (5 writes).** No informational gain; loses the distinction between
"never recorded" and "recorded as unknown".

- `272.funding_period` (from `research-002`) — was `NULL`, now `'unknown'`
- `273.funding_period` (from `research-004`) — was `NULL`, now `'unknown'`
- `285.funding_period` (from `research-031`) — was `NULL`, now `'unknown'`
- `356.funding_period` (from `research-032`) — was `NULL`, now `'unknown'`
- `162.funding_period` (from `research-065`) — was `NULL`, now `'unknown'`

### The most damaging non-162 write: DB 356

`356.deadline_date` was written on a **correctly matched** row (Phase 1: class **A**, confidence HIGH) and is still
wrong. The row's own verified `deadline_display` says:

> "No application deadline is published on the Tempus Public Foundation pages for bilateral state scholarships;
> applications are submitted into the Foundation's online system and assessed on a rolling basis per bilateral partner."

The merge replaced that verified finding with the research record's asserted date
`19 February 2026, 23:00 CET (27 February 2026, 17:00 for summer courses)`. A deadline-filtering query would now
return a deadline the awarding body does not publish. This is worse than the 162 case, because 356 had a
trustworthy pre-existing value that the merge discarded without recording that it had done so.

---

# Uncertain Writes

**2 writes cannot be adjudicated from available evidence.**

| # | DB | field | current value | provable pre-merge |
|---|---|---|---|---|
| 15 | **285** | `english_requirement` | `English` | `None` |
| 26 | **299** | `english_requirement` | `English` | `None` |

### Exactly what evidence is missing

Both writes set `english_requirement` on a field that was previously `NULL`. Both cite the row's own official
URL as the source, so the *provenance* is legitimate. What is missing is:

**DB 285 — `english_requirement = 'English'`**

- No captured statement from `stipendiumhungaricum.hu` describing a language **requirement**. The research pass
  recorded `eligibility.language.required: true` and `teaching_language: ["English"]`, but the underlying page
  text was not preserved, so the claim cannot be checked against a quote.
- Stipendium Hungaricum is administered in Hungarian and English and is channelled through Sending Partners; a
  blanket `'English'` requirement is not obviously right and may be an over-generalisation.
- **Missing:** the official language-requirement clause, with a retrievable quote and its source anchor.

**DB 299 — `english_requirement = 'English'`**

- FCT publishes its calls **bilingually** (Portuguese and English). The evidence is a single English-language URL.
- Asserting `'English'` may be incomplete rather than wrong; the field has no vocabulary for "Portuguese and
  English", so any value is a lossy approximation.
- **Missing:** confirmation of whether the DB intends `english_requirement` to mean "English required",
  "English available", or "page language". These three readings give different correct values.

### Why these two are riskier than the clearly-wrong writes

`merge_execute.py:94` skips any field whose `old_value` is populated and differs from the new value. Writing a
value into a previously **empty** field means every future merge run will treat that field as *already
populated* and skip it. A wrong value planted in an empty field therefore becomes self-perpetuating: no
subsequent premium-card run can correct it. That is precisely how `'unknown'` in `funding_period` and prose in
`deadline_date` are now permanently stuck.

**Recommended disposition:** restore both to `NULL` and re-research with quote capture before writing.

---

# Recoverable Pre-Merge Values

## Authoritative pre-merge snapshot

| property | value |
|---|---|
| path | `backend/scholarzone.pre_integrity_repair_20261005_143934.db` |
| mtime (UTC) | 2026-10-05T14:39:34.875155 |
| row count | 722 |
| contains all 7 affected rows | yes |

**Why this one:** It is the newest snapshot that predates the merge (2026-10-06T14:07:26Z) and it is the direct predecessor of the 2026-10-05T14:39:34 batch whose timestamps are the current updated_at values on all 7 affected rows. It contains all 7 affected rows.

## Corroboration

| snapshot | mtime (UTC) | rows | agrees on all 14 fields to restore |
|---|---|---|---|
| `backend/wave13_local.db` | 2026-10-04T14:10:57.118168 | 722 | **True** |
| `backend/scholarzone.pre_wave13_master_20261004_201056.db` | 2026-10-04T14:09:11.131116 | 722 | **True** |

Three snapshots taken at different times on 2026-10-04 and 2026-10-05 return **identical** values for all 14
fields that must be restored. The pre-merge state is therefore well established and not an artefact of one file.

## Candidates rejected — filename alone proves nothing

| candidate | why rejected |
|---|---|
| `backend/scholarzone_backup_20260902_122751.db` | 0 bytes and contains no tables at all despite the 'final_backup' style name. Filename is misleading; unusable. |
| `backend/dev.db` | 0 bytes, no tables. |
| `backend/app.db` | 0 bytes, no tables. |
| `backend/scholarzone_backup_20260902_022135.db and scholarzone_final_backup_20260902_122751.db` | 303 rows and only 6 of the 7 target rows. Predates the DB schema as it is now; not the same database state. |
| `root-level scholarzone.db` | Not opened. Out of scope by instruction, and it is a divergent 802 KB file, not the authoritative database. |

## Recoverability verdict

**All 14 fields that require repair have a provable pre-merge value: True.**

## Critical operational warning

Pre-merge snapshots hold 722 rows and the current DB holds 691. The 31-row difference is the retention engine deletion that ran between 2026-10-05 and the merge, NOT the premium-card merge (db_rows_created=0). Restoring any field from a snapshot must therefore be a targeted single-column UPDATE, never a whole-file restore.

> A whole-file restore from any pre-merge snapshot would **re-add 31 already-deleted rows** and undo the
> retention engine's work. Repair must be performed as **targeted single-column `UPDATE` statements inside a
> transaction**, against a fresh copy, with a verified before/after diff.

---

# Recommended Repairs

**NOTHING WAS EXECUTED.** The statements below are proposals for human approval.

## Ordered repair set

Preconditions for all of them:

1. Take a fresh filesystem copy of `backend/scholarzone.db` and record its sha256 and row count (691).
2. Run inside a single transaction; abort on any error.
3. Do **not** restore any backup file over the live database.
4. Afterwards assert: `SELECT COUNT(*) FROM scholarships` = 691, and
   `SELECT COUNT(*) FROM scholarships WHERE deadline_date IS NOT NULL AND deadline_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'` = **0**.

```sql
BEGIN TRANSACTION;

-- Step 1 (HIGHEST SEVERITY): remove Coimbra-derived data from the University of Vienna row.
--   funding_period: was None, currently holds 'unknown'
UPDATE scholarships SET funding_period = NULL WHERE id = 162;;
--   deadline_date: was None, currently holds 'Varies by admission cycle (ongoing for enrolled students)'
UPDATE scholarships SET deadline_date = NULL WHERE id = 162;;

-- Step 2: remove free text from the DATE column (6 rows).

-- Step 3: restore NULL semantics lost to the literal 'unknown' (5 rows).
UPDATE scholarships SET funding_period = NULL WHERE id = 272;;
UPDATE scholarships SET funding_period = NULL WHERE id = 273;;
UPDATE scholarships SET funding_period = NULL WHERE id = 285;;
UPDATE scholarships SET funding_period = NULL WHERE id = 356;;
UPDATE scholarships SET funding_period = NULL WHERE id = 162;;

-- Step 4 (REQUIRES A DECISION FIRST): the 2 uncertain english_requirement writes.
--   285.english_requirement = 'English' is unproven; restore only if re-research does not confirm it.
--   299.english_requirement = 'English' is unproven; restore only if re-research does not confirm it.

COMMIT;
```

## Do NOT repair

| DB | field | current value | why keep |
|---|---|---|---|
| **299** | `deadline_date` | `2026-03-31` | the one correct write of the merge: valid ISO date, agrees with the row's own verified `deadline_display`, source URL is byte-identical to the row's `official_source_url` |

## Not part of this repair plan

The 14 no-op writes (values byte-identical to what was already stored) require no action — they left no trace.
The non-merge deltas listed earlier belong to the 2026-10-05 integrity-repair batch and are out of scope.

---

# Current DB Safety Verdict

## Verification gaps found in the merge pipeline itself

- merge_verification_report.json is self-contradictory: field_updates_applied=28 while db_rows_updated=0 and db_rows_unchanged=691.
- Root cause located in research/premium_card/merge_execute.py lines 115-118: it counts updated rows with 'SELECT COUNT(*) FROM scholarships WHERE updated_at >= :since'. The 28 UPDATE statements never assign updated_at, so the query necessarily returns 0. The verification was structurally incapable of detecting its own writes.
- No row-level audit trail exists for the merge: scholarship_verification_history holds 9 rows for the 7 affected IDs, none of them for deadline_date, funding_period or english_requirement, and all of them predate the merge (2026-09-06 to 2026-09-27).
- The migration SQL header timestamp 2026-10-06T14:07:37.943949+00:00 sits 8.7 ms before the current DB file mtime 2026-10-06T14:07:37.952654, independently confirming the SQL was executed against the current file.
- The merge only ever wrote into EMPTY fields. merge_execute.py line 94 skips any field whose old_value is populated and differs, which is why conflicts_skipped=0 and why all 28 writes targeted NULL or already-equal fields.

## Per-write safety classification

| verdict | count | meaning |
|---|---|---|
| `SAFE_CURRENT_VALUE` | 15 | current value is correct; nothing to do |
| `BAD_WRITE_REQUIRES_REPAIR` | 11 | current value is wrong and must be reverted |
| `UNCERTAIN_REQUIRES_REVIEW` | 2 | cannot be adjudicated from available evidence |

```
CURRENT_DB_CLEAN: NO
```

The database is **not** clean. Three independent classes of incorrect previous premium-card write remain:

1. **Cross-institution contamination** — Portuguese Coimbra data inside the Austrian Vienna row (DB 162).
2. **Schema-type contamination** — 6 rows carry free text in a `DATE` column; these are the only 6 such rows
   in the table and every one of them was written by this merge.
3. **Semantic degradation** — 5 rows had `NULL` overwritten with `'unknown'`.

All 14 fields requiring repair have provable pre-merge values, confirmed by three independent snapshots.

---

# FINAL VERDICT

```
REPAIR_REQUIRED
```

Incorrect premium-card writes remain in the live 691-row database: 11 confirmed bad writes needing repair and
2 uncertain writes pending evidence. DB 162 contains data belonging to a different university's country.
Every repair is a targeted single-column revert to a value proven by three independent pre-merge snapshots.
Nothing was repaired, restored or written by this audit.

---

## Files

**Created (new only):**

| file | bytes |
|---|---|
| `research/premium_card/phase2_contamination_audit.json` | 75,009 |
| `research/premium_card/phase2_contamination_audit.md` | (this file) |

**Modified:** none. `backend/scholarzone.db` was opened read-only and not written. The root-level
`scholarzone.db`, all timestamped backups, all prior reports, the 5 unstaged frontend modifications and the
384 untracked entries are untouched.

```
DATABASE WRITES: 0
FILES MODIFIED: 0
GIT MUTATIONS: 0
```
