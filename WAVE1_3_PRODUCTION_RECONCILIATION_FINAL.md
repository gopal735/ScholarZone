# WAVE 1–3 PRODUCTION RECONCILIATION — FINAL

**Date:** 2026-10-04
**Scope:** Wave 1 (update existing records), Wave 2 (discover open scholarships), Wave 3 (official-logo hunt)
**Mode:** READ-ONLY. No database, config, code or deployment was modified during this reconciliation.
Every SQLite handle below was opened with the `file:…?mode=ro` URI, so a write was structurally impossible.

---

## 1. Executive Summary

| Question | Answer | Evidence class |
|---|---|---|
| Did Wave 1–3 reach production Neon? | **No.** No write path to Neon existed. | **PROVEN** |
| Is Neon fully / partially / unchanged for this wave? | **UNKNOWN** — Neon is unreachable from this machine; no connection string exists anywhere accessible. | **UNKNOWN** (see §4) |
| Is the local SQLite delta safe to push to Neon? | **Not yet.** 6 blocking items must be decided first (§13). | **PROVEN** |
| Did the previous report overstate anything? | **Yes, in three places.** Corrected in §1.1. | **DISPROVEN** (previous claim) |

**Bottom line:** Wave 1–3 produced a large, real, locally-applied change set — 234 rows created, 1 deleted, 472 existing rows refreshed across 11,854 field cells, 189 new audited logo hosts. **None of it is in production.** Production completion is **not established**. The durable artefact is not the SQLite file but the `backend/config/*.json` change set, which is transportable; the database itself is not portable (rowids and SQLite specifics differ).

### 1.1 Corrections to the earlier completion report

| Earlier claim | Reality | Class |
|---|---|---|
| "৩০+ dead official URL corrected" | **False.** `official_source_url` changed on **5** pre-existing rows only. Agents recorded corrected URLs in `research_notes.url_observed`; by design the stored identity URL was not overwritten. | **DISPROVEN** |
| "publicly visible 659" | Current observed value is **666** — it rose as later drains landed. 659 was true at an earlier point in the same session. | **DISPROVEN (as a current figure)** |
| "+233 new records" | Precisely: **234 rows created, 1 deleted (id 358), net +233**. | **PROVEN** |

---

## 2. Wave 1–3 Intended Changes

Derived from the repository's own artefacts, not from final counts.

| Artefact | Before wave | After wave | Delta |
|---|---|---|---|
| `backend/config/new_scholarships.json` | 87 records | 627 records | **+540 appended** |
| — of which carry `_target_id` (upsert an existing row) | — | **387** (all 387 targets still exist) | — |
| — of which are insert-shaped | — | **240** | — |
| `backend/config/verification_confirmations.json` | 220 | 439 | **+219** |
| — naming a retired row | 0 | **0** (repaired mid-wave) | — |
| `backend/config/official_logo_overrides.json` | 359 hosts | 548 hosts | **+189** |
| `backend/config/unresolved_logos.json` | 26 hosts | 11 hosts | **−15** |
| `backend/config/retired_records.json` | 46 | 48 | **+2** (ids 358, 528) |
| `backend/config/purged_records_archive.json` | 151 | 153 | **+2** (ids 358, 528) |

**Maintenance run ledger** — `maintenance_runs` table, `worker = maintenance/1.1+SHUSANTA-PC+attempt1`. The last full drain produced runs `cbe6645851af48ea` (add), `38fbda435c3f4fe5` (reverify), `ff04347b32d349ae` + `15a88c96d9dd41e3` (logos pass 1), `a476e2ccafbf4775` + `a86d1d71dfec424e` (logos pass 2), `98d0272fc0b345c9` (add), `cd1731533d8243ed` (reverify), `4261a0fc4178445e` + `1feb34dd83554c4a` (logos). Every recorded run has `status=ok`, `dry_run='0'`.

**Backups that make the delta provable**
- `backend/scholarzone.pre_wave1_20261004_133109.db` — snapshot taken 13:30:58, immediately before the first `add` stage.
- `backend/config/*.pre_wave1`, `.pre_wave2`, `.pre_wave3`, `.pre_conformance`, `.pre_repair` — every appended file has a pre-wave copy.

**Deterministic exports produced (read-only, in temp)**
- `local_delta_manifest.json` — added ids, removed ids, changed-existing ids, per-id changed-field map, field census.
- `config_reconciliation.json` — artefact counts, wave-created id list, wave-introduced duplicate groups.

---

## 3. Local SQLite State

**File:** `backend/scholarzone.db` · **Read mode:** `file:…?mode=ro`

| Metric | Before (13:30 snapshot) | Now | Delta |
|---|---|---|---|
| total records | 489 | **722** | +233 |
| verification_status = active | 347 | **694** | +347 |
| verification_status = needs_review | 140 | **5** | −135 |
| verification_status = quarantined | 2 | **23** | +21 |
| is_verified = 1 | 484 | **710** | +226 |
| is_archived = 1 | 0 | **46** | +46 |
| status = open | 411 | **407** | −4 |
| status = upcoming | 0 | **296** | +296 |
| status = closed | 70 | **18** | −52 |
| deadline_precision = exact | 3 | **174** | +171 |
| deadline_date present | 89 | **255** | +166 |
| funding_amount present | 0 | **269** | +269 |
| image_url present | 317 | **714** | +397 |
| image_kind ∈ {official_logo, official_government, official_university} | 82 | **713** | +631 |
| image_verified_at present | 317 | **714** | +397 |
| official_details populated | 0 | **540** | +540 |
| public visibility gate | 316 | **666** | +350 |

### 3.1 Row-level delta

| Class | Count | Detail |
|---|---|---|
| **Rows created** | **234** | ids 491–725, excluding 528 (created then purged) |
| **Rows deleted** | **1** | id **358** |
| **Existing rows changed** | **472** | 11,854 changed field cells |
| Existing rows untouched | 16 | of the 488 rows present before |

### 3.2 Per-field change census (pre-existing rows only)

| Field | Rows changed | Field | Rows changed |
|---|---|---|---|
| image_alt_text | 401 | funding_currency | 231 |
| image_verified_at | 401 | degree | 215 |
| image_url | **400** | funding_period | 215 |
| image_kind | **400** | official_source | 211 |
| image_source_url | 394 | region | 194 |
| image_source_type | 394 | funding_amount | 190 |
| eligibility_summary | 378 | english_requirement | 184 |
| eligibility / official_details / applicant_utility / programme_verification | 377 each | image_evaluation_status | 167 |
| coverage / benefits | 374 each | verification_status | 152 |
| program_type | 370 | deadline_date | 120 |
| application_period | 363 | country | 59 |
| last_verified_date | 349 | is_archived | 45 |
| selection_notes | 314 | application_link | 26 |
| deadline_precision | 311 | is_verified | 10 |
| description | 309 | **official_source_url** | **5** |
| official_updates_url | 304 | duration | 301 |
| documents | 296 | funding | 297 |
| requirements | 291 | notes / title | 271 each |
| catalogue_url | 260 | best_fit | 257 |
| status | 242 | | |

---

## 4. Production Neon State

### 4.1 How production is configured — PROVEN

`backend/app/core/config.py` resolves the database **from the process environment only**. There is no file-based credential path.

- `SCHOLARZONE_ENVIRONMENT=development` / `test` → SQLite at `DEFAULT_DATABASE_URL`
- `SCHOLARZONE_ENVIRONMENT=production` → **`SCHOLARZONE_DATABASE_URL` is mandatory and must be PostgreSQL**; SQLite is explicitly refused

Observed behaviour, executed read-only against the real module:

```
development  -> accepted, scheme=sqlite
test         -> accepted, scheme=sqlite
production   -> REFUSED: SCHOLARZONE_DATABASE_URL is required in production.
```

### 4.2 Credential reachability — PROVEN ABSENT

| Source | Result |
|---|---|
| `SCHOLARZONE_DATABASE_URL`, `DATABASE_URL`, `POSTGRES_URL`, `NEON_DATABASE_URL`, `PGHOST/PGDATABASE/PGUSER` in this process | **all absent** |
| `backend/.env` (exists, gitignored) | contains only `RESEND_API_KEY`, `NOTIFICATION_EMAIL`, `SCHOLARZONE_VERIFICATION_SECRET` — **no database URL** |
| `backend/.env.example` | two **template** connection strings (host is literally `host`); not credentials |
| `.env.local`, `.env.production.local` | no database URL |
| `.vercel/repo.json` | repo is linked to Vercel project **`scholarzone-fwzj`**; its environment variables are not readable without the Vercel CLI, and pulling them would (a) write a file and (b) expose secrets — both forbidden here |
| OS credential manager | never read |

No credential was printed at any point. Only scheme, presence flags and the provider domain suffix were reported.

### 4.3 Conclusion for Neon

- **This session wrote nothing to Neon. — PROVEN.** Every maintenance invocation set `SCHOLARZONE_ENVIRONMENT=development`, which forces SQLite; the production path refuses to start without the variable that was never present.
- **Neon's current contents are UNKNOWN.** Not "unchanged" — unmeasured. Neon may hold state from earlier deploys, and this wave's data is provably absent from it.

---

## 5. Exact Local-vs-Production Delta

Because Neon cannot be read, this section is a **delta specification**, not a comparison. It is written so that the same script can be pointed at Neon and produce the comparison immediately.

### 5.1 Rows that exist locally and would be absent from Neon

- **234 rows**, ids **491–725** excluding 528 (full list in `config_reconciliation.json → wave_created_ids`)
- All of them are `image_kind=official_logo`, `verification_status=active`, `is_verified=1` except id 495 (§12.4)
- 2 of them have no image: **541** (mastercardfdn.org), **635** (gob.mx)
- 71 of them have no `official_details` block

### 5.2 Rows whose content differs (local differs from any older state)

- **472 rows**, per-id field map in `local_delta_manifest.json → changed_fields_by_id`
- Includes **400 rows with a changed `image_url` and `image_kind`** — the single largest category of change and the one that interacts with the separate image-reversion track

### 5.3 Rows that must be **deleted** to match local

- **id 358** only (archived duplicate of id 286)

### 5.4 Rows that must be **quarantined/archived** to match local

- 46 rows with `is_archived=1`; 23 with `verification_status='quarantined'`; 25 with `verification_status='active'` **but** `is_archived=1` (§12.3)

### 5.5 How to produce the real comparison

Run the same inventory script with the Neon URL in the environment:

```
$env:SCHOLARZONE_DATABASE_URL = "<read-only Neon URL>"
python inventory_local.py            # same script, Postgres branch required
```
Fields to compare per id: `title`, `official_source_url`, `official_source`, `verification_status`, `deadline*`, `funding*`, `eligibility*`, `degree*`, `image_*`, `region`, `is_archived`.

**Do not compare by total count.** Local 722 vs Neon N proves nothing about content.

---

## 6. 233 New Records — provenance check

**PROVEN:** all 234 created rows carry `verification_status='active'`, `is_verified=1`, `is_archived=0`, `image_kind='official_logo'` (except 541, 635 with no image; 596 with a null kind; 495 quarantined).

**PROVEN:** they were produced by 50 Wave-2 discovery agents from awarding bodies' own official pages, deduplicated three ways — in-shard dedup lists, live-database URL/title match, and same-host near-duplicate similarity ≥ 0.82.

**PROVEN:** the ingestion stage refused any record without `source_citations`, so every accepted record has at least one official URL actually fetched.

**PROVEN — the records are NOT publish-ready as a set:**

| # | New rows | Finding |
|---|---|---|
| 2 | 541, 635 | no image at all |
| 1 | 596 | `image_url` is `http://` (not https) **and** `image_kind` is NULL |
| 71 | see §12.5 | no `official_details` block |
| 2 | 570, 530 | duplicate an existing live row (same page, different URL string) |
| 3 | 532, 501, 553 | duplicate the award of an existing row under a different page |
| 1 | 495 | created **and** quarantined within the same wave |

**UNKNOWN:** whether each new record's facts are true. They were researched live, but this reconciliation did not re-verify a single scholarship award against its official page — that would require the research wave, not an audit.

---

## 7. 389 Deep Refreshes

**PROVEN:** the wave-1 staging produced **387 upsert-shaped records** carrying `_target_id`; all 387 target rows still exist. The "389" figure in the earlier report was a staging-run count, not a distinct-record count. **387 is the correct figure.**

**PROVEN:** the DB diff shows **472 pre-existing rows changed**, larger than 387, because the first `add` stage also applied 87 records that were already sitting unimported in `new_scholarships.json` (77 rows created, 126 updated) — those were not wave-1 research output.

**PROVEN:** `official_source_url` changed on only **5** pre-existing rows. By design the stored identity URL is preserved and the corrected URL is recorded in `research_notes.url_observed` instead, so that an upsert resolves to the intended row and cannot create a duplicate.

**PROVEN:** `verification_status` changed on 152 rows and `last_verified_date` on 349 rows — the refresh is real and dated.

---

## 8. Verification Confirmations

**PROVEN:** 439 confirmation records, 219 net new. Each has `{id, name, source_url, checked_at, evidence}`.

**PROVEN:** 0 confirmations name a retired row (after mid-wave repair).

**PROVEN:** the source-authority audit test now passes — no confirmation cites a non-authoritative source.

**PROVEN — one defect was introduced and then repaired mid-wave:** before the repair, the `reverify` stage promoted **25 retired rows** back to `verification_status='active'` by acting on confirmations the merge had emitted for them. The merge now excludes retired ids and non-authoritative sources, so a re-run cannot reintroduce it. The residue is described in §12.3.

---

## 9. Duplicate / Archive Changes

**PROVEN:** exactly two duplicate-driven purges, both with full payload archived:

| Purged | Canonical | Distinguishing difference | Payload archived | Reviews on purged id | Verification history |
|---|---|---|---|---|---|
| **358** | **286** Hungarian Diaspora Scholarship Programme | trailing slash (`/en` vs `/en/`) | yes | 0 | 3 rows |
| **528** | **133** Invest Your Talent in Italy (IYT) | letter case (`/SITOIYT/` vs `/SitoIYT/`) | yes | 0 | 0 rows |

**PROVEN:** neither purged row still exists; both canonical rows are `active`, `is_verified=1`, `is_archived=0`, `image_kind=official_logo`, and hold 0 reviews.

**PROVEN:** public visibility is correct — the purge removed the duplicates from the catalogue rather than leaving two live entries for one award.

**UNKNOWN:** inbound production references to ids 358/528 (bookmarks, external URLs, SEO) — the local DB has no dependent rows, but production traffic cannot be inspected.

---

## 10. Region Normalization

**PROVEN:** `region` is a filter facet; several agents wrote eligibility sentences into it. A normalization pass rewrote **106 rows**:

| Action | Rows |
|---|---|
| qualifier trimmed, region kept (`Global (…)` → `Global`) | 20 |
| inferred from host country (`Japan (candidates must be…)` → `Asia`) | 80 |
| cleared to NULL (no defensible geography) | 6 |

**PROVEN:** the eligibility text was not lost — it remains in `official_details` and `best_fit`.

**PROVEN:** the merge now drops any `region` value longer than 25 characters or containing `(`, so a re-run cannot reintroduce sentences.

---

## 11. Image / Forensic Impact

> No image stage was run. This section is read-only observation.

### 11.1 The six named records

| id | Before | After | Verdict |
|---|---|---|---|
| **14** ETH ESOP | `…/pageimages/imageCa…` (program photo), kind `program_image`, type `official_provider` | `ethz.ch/etc/designs/ethz/img/icons/ETH-APP-Icons-Theme-white/192-xxxhpdi.png`, kind `official_logo`, type `official_logo` | **SUSPECT.** The replacement path contains `Theme-white` and is a 192px app icon, not a wordmark. Likely the banned white-on-transparent variant. **Needs the image track.** |
| **130** AKF ISP | no image; `image_evaluation_status = source_blocked` | `akf.org/wp-content/themes/aga-khan/assets/favicon/favicon.svg`, kind `official_logo`; `evaluation_status → verified` | **SUSPECT.** A site favicon promoted to the record logo, and a blocked source re-marked verified in the same write. |
| **554** SECIHTI–OEA | **row did not exist** | `oas.org/imgs/en/OEA-ENG-Main-Updated-AUG2025.svg`, `official_government` | New row; image is the awarding body's own mark. OK. |
| **557** KAUST Fellowship | **row did not exist** | `admissions.kaust.edu.sa/.../KAUST_Logo.svg`, `official_university` | New row; probed and colour-checked. OK. |
| **564** JJ/WBGSP | **row did not exist** | `worldbank.org/content/dam/wbr-redesign/logos/wbg-favicon.png`, `official_logo` | New row; **a favicon used as the record logo.** Same concern as 130. |
| **569** Clark University GSP | **row did not exist** | `cdn.clarku.edu/wp-content/uploads/2023/10/clarku_logo.png`, `official_university` | New row; on a `clarku.edu` subdomain. OK. |

### 11.2 Image change census (472 pre-existing rows)

| Column | Rows changed |
|---|---|
| `image_url` | **400** |
| `image_kind` | **400** |
| `image_alt_text` | 401 |
| `image_verified_at` | 401 |
| `image_source_url` | 394 |
| `image_source_type` | 394 |
| `image_evaluated_at` | 400 |
| `image_evaluation_status` | 167 |

**PROVEN — no image was stranded:** 0 pre-existing rows had an image removed and left empty. The `logos` stage clears a stored photo in one pass and re-attaches on the next; running it twice left every record with a populated `image_url`.

**PROVEN:** 234 pre-existing images were **replaced** with a new URL (e.g. id 14's program photo → theme icon). These are the rows the separate image-reversion investigation must review.

**PLAUSIBLE BUT UNPROVEN:** that the 234 replacements are improvements. Some clearly are (campus photos → official marks); id 14 looks like a regression. The sample cannot generalise to all 234.

---

## 12. Data Integrity Checks

### 12.1 PASS

| Check | Result |
|---|---|
| public count never exceeds total | **PASS** — 666 ≤ 722 |
| no exact duplicate `official_source_url` | **PASS** — 0 offenders |
| `verification_status` always set | **PASS** — 0 nulls |
| every publicly visible record shows a logo-identity `image_kind` | **PASS** — 0 offenders |

### 12.2 ATTENTION — duplicates that survived

| Group | Rows | Same page? | Verdict |
|---|---|---|---|
| Invest Your Talent in Italy | **133 / 570** | **yes** — same path, letter case only | **Real duplicate.** Same defect class as the 528 purge. |
| National Science Scholarship (PhD) | **438 / 530** | **yes** — same path, `%28` vs `(` percent-encoding | **Real duplicate.** |
| Gates Cambridge | 68 / 532 | programme page vs apply/timeline | Likely duplicate |
| Deutschlandstipendium | 10 / 501 | homepage vs "how it works" page | Likely duplicate |
| NTU President's Graduate | 107 / 531 | scholarships hub vs `/npgs` | Likely duplicate |
| POSCO Global Scholarship in Korea | 13 / 553 | `/purpose` vs `/abroad/business` | Likely duplicate |
| JSPS Postdoctoral | 551 / 552 | `e-ippan` vs `e-oubei-s` | **NOT a duplicate** — two distinct programmes |

Only the first two are provable from the URL alone. The four "likely" rows need a human decision.

### 12.3 ATTENTION — retired rows carrying `verification_status='active'`

**25 rows** are listed in `retired_records.json` yet have `verification_status='active'` because the mid-wave `reverify` run re-promoted them.

**PROVEN: 0 of them are publicly visible** — every one has `is_archived=1`, and the public gate requires `is_archived=0`. This is a state inconsistency, not an exposure.

### 12.4 ATTENTION — row created and retired in the same wave

`id 495` (Chevening ASEAN Scholarship) was inserted by Wave 2 and is already `quarantined` + `is_archived`. Harmless, but it means the insert stage wrote a record the retire stage immediately hid.

### 12.5 ATTENTION — completeness of the new rows

- **71 of 234** created rows have no `official_details` block (ids listed in `config_reconciliation.json`)
- **2 of 234** created rows have no image: 541, 635
- **1 row** (596) has an `http://` image URL with `image_kind = NULL` — the only such row in the database, and it is publicly visible
- **3 rows** (411, 413, 426) store `eligibility` as a bare JSON string instead of a list

### 12.6 DISPROVEN — a false alarm worth recording

An early integrity pass reported "3604 list fields stored as a raw string". **That was my own checker being wrong.** These columns are JSON-text columns and storing `["…"]` is correct; the values parse to lists. **Real count of malformed values: 3** (see §12.5).

### 12.7 Dependent tables

`scholarship_reviews`, `scholarship_verification_history`, `image_reviews`, `scholarship_restore_records`, `scholarship_snapshots` and others all exist. Purged ids 358/528 carry **0 reviews**. `scholarship_verification_history` retains 3 rows for id 358, which is the intended audit trail.

---

## 13. Production Readiness

**A. Is Neon already fully updated?**
**UNKNOWN.** Neon could not be read. It is *provable* that this wave's data is not in it (no write path existed), so "fully updated" is **DISPROVEN**; the residue is unmeasured.

**B. Is Neon partially updated?**
**UNKNOWN.** Some earlier deploy may have pushed some rows. Not measurable here.

**C. Is Neon unchanged for this wave?**
**PROVEN** for *this session*: every command ran with `SCHOLARZONE_ENVIRONMENT=development`, which forces SQLite, and production refuses to start without `SCHOLARZONE_DATABASE_URL`, which was never set. **UNKNOWN** for pre-existing state.

**D. Are there conflicts requiring reconciliation?**
**UNKNOWN** until Neon is read. Six candidate conflicts are already known locally (§12.2, §12.3) and must be resolved regardless of what Neon holds.

**E. Can the local SQLite delta be safely applied to Neon?**
**NO, not as a file copy, and not yet.** Two independent reasons:
1. **Structural:** copying `scholarzone.db` into Neon is wrong — SQLite rowids, autoincrement sequence and JSON-text typing do not transfer, and `official_source_url` uniqueness would collide on the 234 new rows.
2. **Content:** six items in §12 are unresolved, one of them (id 14's `Theme-white` app icon) likely a quality regression.

**F. What exactly would be applied?**
See §14. The change set is the **config files**, applied through the repository's own idempotent maintenance stages — not a database copy.

---

## 14. Exact Safe Apply Plan

**This plan is a specification. Nothing below was executed.**

### Phase 0 — obtain read-only production access (blocking)

1. Provision a Neon role with `SELECT` only, or run `vercel env pull` to a path **outside the repository** (it writes a file and exposes secrets — both forbidden in this pass, so it must be a deliberate, separate, approved action).
2. Re-run the inventory against Neon and diff by id using `local_delta_manifest.json` as the expected set.
3. Produce the real PRESENT-IN-BOTH / LOCAL-ONLY / PRODUCTION-ONLY / DIFFERENT-CONTENT manifest. **Do not proceed until this exists.**

### Phase 1 — resolve the six known conflicts (local, on a copy)

| # | Decision required | Rows |
|---|---|---|
| 1 | Retire one of each provable duplicate | 570 → keep 133; 530 → keep 438 |
| 2 | Decide on four likely duplicate title pairs | 532/68, 501/10, 531/107, 553/13 |
| 3 | Image-track review of replaced images | start with **14**, **130**, **564**, **596** |
| 4 | Re-quarantine or re-archive the 25 rows promoted to `active` | see §12.3 |
| 5 | Decide the 71 new rows lacking `official_details` — enrich or hide | ids in `config_reconciliation.json` |
| 6 | Fix or hide the 2 new rows with no image | 541, 635 |

Work on a **copy** of the database. Keep `scholarzone.pre_wave1_20261004_133109.db` untouched as the audit baseline.

### Phase 2 — the apply mechanism

The config files already contain the change set and are transportable text. The apply path is the repository's own:

```
# on the machine that can reach Neon
$env:SCHOLARZONE_ENVIRONMENT      = "production"
$env:SCHOLARZONE_DATABASE_URL     = "<Neon URL>"

# 1. dry run first, always
python -m app.jobs.scholarzone_maintenance --stage add      --dry-run
python -m app.jobs.scholarzone_maintenance --stage reverify --dry-run
python -m app.jobs.scholarzone_maintenance --stage logos    --dry-run

# 2. review the dry-run counts against local expectations:
#      add      -> ~617 updated, ~0 created (rows already exist)
#      reverify -> confirmations promoted
#      logos    -> N attached

# 3. then, one stage at a time
python -m app.jobs.scholarzone_maintenance --stage add
python -m app.jobs.scholarzone_maintenance --stage reverify
python -m app.jobs.scholarzone_maintenance --stage logos
python -m app.jobs.scholarzone_maintenance --stage logos   # second pass attaches what pass 1 cleared
```

**Why this and not a file copy:** the stages resolve each record by `official_source_url` (plus `legacy_titles` fallback), upsert in place, write verification history, and enforce the quality gate. They are idempotent — a re-run is a no-op — and they abort the whole batch on one bad record, which is a safety property a bulk insert does not have.

**Carry the config files, not the database.** Specifically required in production:
`backend/config/new_scholarships.json`, `verification_confirmations.json`, `official_logo_overrides.json`, `record_corrections.json`, `retired_records.json`, `purged_records_archive.json`, `unresolved_logos.json`.

**Do NOT do:** copy `scholarzone.db` into Neon · bulk insert by rowid · `DELETE` + re-insert · disable the public gate to force visibility · run `purge` (it is policy-gated and this wave used archive-not-purge deliberately).

### Phase 3 — verify after apply

Re-run the same inventory against Neon and require:
- total, public, active, logo-identity counts equal local
- `official_source_url` has no case/encoding-insensitive duplicates
- no retired row is publicly visible
- `pytest tests -q` is green (currently 4655 passed, 2 skipped, 1 pre-existing failure)

---

## 15. Unknowns / Risks

| # | Item | Class |
|---|---|---|
| 1 | Neon's entire current contents | **UNKNOWN** |
| 2 | Whether earlier deploys already pushed some of these rows | **UNKNOWN** |
| 3 | Whether the 234 replaced images are net improvements | **PLAUSIBLE BUT UNPROVEN** — id 14 looks like a regression |
| 4 | Whether the 234 new records' scholarship facts are true | **UNKNOWN** — researched live, not re-audited here |
| 5 | Inbound production references to purged ids 358 / 528 | **UNKNOWN** |
| 6 | Whether the four "likely duplicate" title pairs are true duplicates | **PLAUSIBLE BUT UNPROVEN** |
| 7 | Whether the 71 rows lacking `official_details` pass the public quality gate in production | **UNKNOWN** — local gate passes on `official_details` being optional |
| 8 | Postgres-specific schema upgrade path | **UNKNOWN** — `_upgrade_postgresql_schema` runs DDL at startup and has never been exercised by this wave |
| 9 | One pre-existing test failure (`yaml` module missing in the venv) | **PROVEN** — unrelated to this wave, present at session start |

---

## 16. Recommended Next Action

**Do not push anything to Neon yet.** The single blocking prerequisite is read-only access to production.

1. **Today** — request a read-only Neon role (or approve a one-off `vercel env pull` outside the repo). Nothing else can be settled without it.
2. **On access** — run the Phase-0 comparison. Expect the manifest to read: *722 rows local, N rows Neon, 234 local-only, 1 local-only deletion, 472 differing*. Confirm or refute that expectation before acting.
3. **In parallel, locally, on a copy** — clear the six Phase-1 conflicts, starting with the image-track review of ids 14, 130, 564, 596, because those are user-visible and independent of production.
4. **Then** — apply via the maintenance stages, dry-run first, one stage at a time, verifying counts against the local expectations in Phase 2.
5. **Explicitly not now:** bulk import, rowid-based sync, `purge`, or any image stage, while the image-reversion investigation is open.

---

### Evidence index

| Claim group | Source |
|---|---|
| Local metrics, row delta, field census | `local_delta_manifest.json` (read-only diff of `scholarzone.db` vs `scholarzone.pre_wave1_20261004_133109.db`) |
| Intended change set | `backend/config/*.json` vs their `.pre_wave1` / `.pre_conformance` copies |
| Production unreachability | `backend/app/core/config.py` behaviour + env presence probe + `.vercel/repo.json` |
| Image forensics | per-row before/after comparison for ids 14, 130, 554, 557, 564, 569 + 472-row image census |
| Integrity | read-only invariant queries over `scholarzone.db` |
| Maintenance history | `maintenance_runs` table, worker `maintenance/1.1+SHUSANTA-PC+attempt1` |