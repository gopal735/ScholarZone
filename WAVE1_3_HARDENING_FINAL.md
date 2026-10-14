# WAVE 1-3 HARDENING — FINAL

**Date:** 2026-10-04 · **Mode:** code hardening + local data repair
**Neon:** untouched. No production credential exists in this environment and none was obtained (§12).
**Local release gate:** **PASS** — 0 RED, 4 YELLOW, each with an explicit disposition (§11).

Every claim below is labelled **OBSERVED FACT**, **PROVEN**, **DISPROVEN**, **PLAUSIBLE BUT UNPROVEN** or **UNKNOWN**.

---

## 1. Executive Summary

All six proven release blockers were traced to a specific missing guard, fixed at the write path, and re-measured. Two of the seven findings in the audit are **corrected by this pass** — one was materially larger than reported, one was not a defect at all.

| # | Blocker | Root cause found | Status |
|---|---|---|---|
| 1 | 6 duplicate pairs | no guard; `do_add` dedupes on exact URL only, and `/SITOIYT/` ≠ `/SitoIYT/` | **RESOLVED** — all 6 retired via the canonical mechanism |
| 2 | 400 image mutations | no guard; the evidence gate existed but only the *discovery* path called it | **RESOLVED** — gate now runs on every caller-supplied image |
| 3 | favicon/app-icon assets | same missing gate | **RESOLVED** — 109 rows corrected |
| 4 | white-on-transparent wordmarks | same missing gate | **PARTLY** — 4 of 8 cleared, 4 survive on evidence (§5.7) |
| 5 | cross-host images | no policy check on the write path | **RESOLVED** — canonical domain policy now enforced |
| 6 | 25 archived + active | `do_reverify` had **no archive check** | **RESOLVED** — guard added; data already reconciled to 0 |
| 7 | 73 + 299 enum violations | **the code itself wrote the invalid values** | **RESOLVED** — both writers fixed, all rows normalised |
| **8** | *(found here)* | the wave **wiped 33 populated URLs to NULL** across 28 pre-existing rows | **RESOLVED** — all 33 restored from the pre-wave snapshot |
| **9** | *(found here)* | `do_reverify` promoted **124 pre-existing rows** from `needs_review`/`quarantined` to `active` | guard added; promotions retained — see §7.3 |

**The three corrections:**

- **DISPROVEN — the enum blocker was bigger than reported.** The audit counted 74 rows with a non-canonical `image_source_type`. The true figure is **299**. The audit's 74 counted only the invented strings the wave introduced (`official_page_logo`, `official_ngo`, …) and missed **`official_logo` on 228 rows** — an *image kind* written into the *provenance* column by `_issuer_kind`'s fallback. Nothing in the codebase could interpret those 228 values.
- **DISPROVEN — "deadline_precision needs a validator".** No validator was missing at the ingestion boundary; the ingestion model already had a code path that would have used one. The invalid values were written **downstream of it**, by two maintenance stages that hardcoded `"day"` and `"day_and_time"` — neither of which is a member of the vocabulary.
- **DISPROVEN — id 14's URL loss is not unique.** The audit reported `official_updates_url` regressing to `None` on id 14 as a single record. It is the visible case of **33 wiped URL fields on 28 pre-existing rows**. All restored.

**The single most consequential finding:** `assess_image_evidence` does not exist because the non-content detectors were never given a caller other than the discovery pipeline. Every write path that received an image URL — ingestion, `do_add`, the admin review queue — had nowhere to ask whether the asset was a favicon. The detectors were fine. Nothing called them.

---

## 2. Proven Release Blockers — disposition

### 2.1 Duplicates — RESOLVED

**PROVEN.** All six pairs survived field-by-field comparison; none was a false
positive. All six were retired through the repository's canonical mechanism.

| Pair | Retired | Survivor | Deciding criterion |
|---|---|---|---|
| 133 / 570 | **133** | 570 | neither holds reviews; 570 holds 20,115 chars of research, 133 holds none |
| 438 / 530 | **438** | 530 | neither holds reviews; identical canonical URLs, 530 holds 18,931 chars |
| 68 / 532 | **532** | 68 | 68 holds 5 reviews; **both rows carry a byte-identical image URL** |
| 10 / 501 | **501** | 10 | 10 holds 7 reviews + 3 history rows |
| 107 / 531 | **531** | 107 | 107 holds 7 reviews; 531 is a child page of 107's hub |
| 13 / 553 | **553** | 13 | 13 holds 7 reviews; **`13.catalogue_url` == `553.official_source_url`** |

Full reasoning: **§6** and `DUPLICATE_RESOLUTION_MANIFEST.md`.

### 2.2 Image mutations — RESOLVED

**PROVEN.** 451 existing rows had at least one image column changed by the wave, classified A–I per §5.5. 400 changed `image_url` and `image_kind`.

### 2.3 Favicon / app-icon / UI assets — RESOLVED

**PROVEN.** 109 rows carry a decisive UI signal; **102 of them were public**. All 109 were corrected: 31 had their pre-wave asset restored, the rest had the asset block cleared.

### 2.4 White-on-transparent wordmarks — PARTLY RESOLVED

See §5.7. **Not** decided by filename. 4 of 8 cleared, 4 retained on evidence.

### 2.5 Cross-host images — RESOLVED

**PROVEN.** The repository already had the answer in `is_official_domain()` — a suffix allowlist of government, education and academic namespaces, **not** a same-host rule. 134 stored images failed it. Per §5.6 no blanket same-host rule was invented.

### 2.6 Archived + active — RESOLVED

**PROVEN.** `do_reverify` contained no archive check whatsoever: it skipped only rows already `active`, then set `active` and `is_verified=True` on everything else in the confirmation file. Guard added; the 26 affected rows are now `0`.

### 2.7 Enum violations — RESOLVED

**PROVEN.** `deadline_precision` 73 → **0**. `image_source_type` 299 → **0**.

---

## 3. Code-Level Guards

Six guards. Each reuses a definition the repository already had.

### 3.1 `image_url` transport — `scholarship_ingestion.py`

`official_source_url`, `catalogue_url` and `official_updates_url` all required https. `image_url` did not, which is how `http://calas.lat/…` became verified evidence.

**Why https at this boundary is not an invented rule:** `image_validator._validate_url_scheme()` deliberately accepts `http` because *discovery* must be able to reach a legacy http source before judging it. That is a reachability rule, not a trust rule. Storing an image asserts it was read and checked; asserting that over plaintext is not a check. The sibling URL fields in the same model already draw that line.

### 3.2 `image_source_type` vocabulary — `scholarship_ingestion.py`

`is_valid_source_type()` already existed and was used by `approve_image_review` and the verification router. The ingestion model never called it. Now a `field_validator` rejects anything outside `ImageSourceType`.

### 3.3 `deadline_precision` vocabulary — `scholarship_ingestion.py` + two stage writers

`coerce_deadline_precision()` already existed and already maps an unrecognised token to `"unknown"`. Three fixes:

| Site | Was | Now |
|---|---|---|
| `ScholarshipIngestionRecord` | passed the extractor's token through verbatim | `field_validator` → `coerce_deadline_precision` |
| `do_facts` | `"day_and_time" if "T" in s else "day"` | `"exact"` |
| `do_programme_details` | `"day"` | `"exact"` |

The two stage writers were the actual source. Both now write `exact`, which is what `normalise_deadline_precision(parsed_date_is_exact=True)` returns for a parsed calendar date. Whether the page gave a time as well is recorded in `deadline_display`, which is free text.

### 3.4 `do_add` image attachment — `scholarzone_maintenance.py`

`do_add` wrote `image_url`, `image_source_url`, `image_source_type`, `image_alt_text` and `image_verified_at` onto an **already-existing** row with no check at all, and never wrote `image_kind` — which is exactly how **id 596** ended up with an image and a null kind. Both fixed: the gate now runs, and `image_kind` is set from the record.

### 3.5 `reverify` retirement protection — `scholarzone_maintenance.py`

Now reads `retired_records.json` alongside the confirmations and skips, with a reason, any row that is archived **or** listed there. Reported as `protected_retired` in both the dry-run and the committed result.

### 3.6 `admin_image_review` archived protection — service + router

`approve_image_review` now refuses an archived row. It previously wrote `image_evaluation_status = verified` and a stored verified image onto a record whose round was closed — invisible while `is_archived` held, and fully trusted the moment anything cleared it.

`review_queue_counts` also now excludes archived `needs_review` rows, which previously sent operators to queue entries whose decision would now be refused.

---

## 4. Validator Changes

### 4.1 New: `assess_image_evidence` (`image_validator.py`)

One function, five checks, all reusing existing definitions:

| Check | Reuses | Rejects |
|---|---|---|
| transport | `EVIDENCE_REQUIRED_URL_SCHEMES` (new; see §3.1) | `http://`, no host |
| provenance vocabulary | `is_valid_source_type` | invented source types |
| kind coherence | — | `image_url` with no `image_kind` |
| non-content | `_detect_non_content_signals` + `NON_CONTENT_REJECTION_THRESHOLD` | favicon, app icon, UI glyph |
| provenance host | `is_official_domain` | commercial CDNs |

`None` is accepted and means "this record has no image" — the honest state for a programme whose source publishes no citable mark.

### 4.2 One correction the detectors needed

Applying the full detector set to a caller-supplied image initially rejected **568 of 714** stored images. Two of those signals were being read as safety signals when they are **kind** signals:

- **`logo/emblem/brand` family** — 265 rejections were legitimate logos rejected purely for having "logo" in the filename.
- **`banner/divider/hero` family** — rejected audited `official_banner` assets for having "banner" in it.

Fixed by discounting a declared kind's own naming family and nothing else (`PROGRAMME_IMAGE_KINDS` added next to `LOGO_IDENTITY_KINDS`). Favicon, UI, nav-icon, placeholder, error, social, og-thumbnail and infrastructure signals stay fully weighted, because a favicon is not a valid image of any kind.

### 4.3 One genuine detector defect found and fixed

`_detect_document_image_signals` listed the bare substring **`"bann"`** alongside `"ejubann"` — it was meant for the Japanese `ejubann` convention, which is separately present. As a standalone keyword it matched every ordinary `...banner.jpg`, so a correctly-named official programme banner was rejected as a scanned document. Removed.

### 4.4 Test fixture that had to change, and why it is not a weakened test

Five seed records in `app/data/verified_scholarships.py` carried an `image_url` with no `image_kind`. That is the exact state the coherence check forbids. Each was given the kind it actually is — `program_image` for the two photographs, `official_banner` for the three named banners — read off the asset itself, not guessed.

Four tests in `test_official_logo_overrides.py` asserted `_issuer_kind()` falls back to `"official_logo"`. They now assert `"official_provider"` **and additionally assert the result is a canonical `ImageSourceType` member** — a stricter test than before, since the old one permitted a value no code could interpret.

---

## 5. Image Safety

### 5.1 What the gate does and does not do

It does **not** reach the network. It applies the same detectors and the same threshold discovery uses, without fetching bytes. That is deliberate: it is a *write-path* guard, and the discovery pipeline remains the only thing that measures an image.

### 5.2 Measured effect across the whole catalogue

| Tier | Rows | Meaning | Action |
|---|---|---|---|
| accepted | **284 → 0 defects** | passes every check | kept |
| decisive UI / favicon | **109** | `/icons/`, `favicon`, `apple-touch-icon`, nav glyph | corrected |
| weak provenance only | **167** | `/themes/`, `/common/` — where real logos live | **left alone** |
| cross-host | 134 | image host outside the official-domain policy | evaluated per row |

### 5.3 The four named ids

| id | Wave state | Verdict | Action taken |
|---|---|---|---|
| **14** | ETH 192px app icon stored as `official_logo`; `official_updates_url` and `catalogue_url` wiped to `None` | **PROVEN UNSAFE** on three independent grounds | asset cleared; `image_evaluation_status` → `invalid_candidates`; both URLs restored from the pre-wave snapshot |
| **130** | `favicon.svg`; `source_blocked → verified` in the same write | **PROVEN UNSAFE** — verification laundering | asset cleared |
| **564** | `wbg-favicon.png` as `official_logo`, verified, public | **PROVEN UNSAFE** | asset cleared |
| **596** | `http://` URL, `image_kind = NULL`, cross-host | **PROVEN UNSAFE** on two grounds | asset cleared; kind invariant now closed |

**Nothing was invented.** No replacement URL was fabricated for any of the four. Where a trustworthy pre-wave asset existed it was restored verbatim from the snapshot; where none existed the asset block was cleared and the row's terminal evaluation state set to `invalid_candidates` — an audited negative, not "never looked".

### 5.4 The URL wipe — 33 fields on 28 rows

**PROVEN.** A row the wave touched had its `catalogue_url` and `official_updates_url` **cleared to NULL**, destroying an authoritative value the pre-wave snapshot still held:

| Column | Fields wiped | Rows |
|---|---|---|
| `catalogue_url` | 26 | incl. 14, 24, 92, 97, 101, 132, 210, 211, 217, 272, 288, 296, 314, 325, 327, 328, 385, 388, 437, 440, 441, 477, 478 |
| `official_updates_url` | 7 | 14, 93, 97, 153, 154, 191, 450 |

**All 33 restored verbatim** from `scholarzone.pre_wave1_20261004_133109.db`. Only fields where the snapshot holds a populated **https** URL were restored; no URL was reconstructed, substituted or guessed.

Id 14's `verification_status` change (`needs_review → active`) was **not** reverted — see §7.3 for why trust state is never rewritten by this pass.

---

### 5.5 Image mutation manifest (A–I)

### 5.6 Cross-host policy — what was implemented, and what was not

**PROVEN:** the repository already answers this, in `is_official_domain()`. It is a suffix allowlist of government (`.gov.*`, `.gouv.fr`), education (`.edu`, `.ac.uk`, `.ac.jp`, …) and academic namespaces. It is **not** a same-host rule.

The gate therefore requires the **image host or the publishing page host** to satisfy that existing policy. Consequences:

| Host | Result | Correct? |
|---|---|---|
| `cdn.ox.ac.uk` | accepted | yes — official CDN for an official institution |
| `d2.cloudfront.net` | rejected | yes — commercial CDN, bytes not from the institution |
| `images.squarespace-cdn.com` | rejected | yes — same |
| `www.gov.uk`, `media.ox.ac.uk` | accepted | yes |

**Deliberately not implemented:** a blanket same-host rule. It would have rejected every legitimate case in the table above.

---

### 5.7 White-on-transparent wordmarks — 8 inspected individually

Neither of the two easy rules was applied: transparency alone does not disqualify, and a filename containing "logo" does not qualify.

| id | Asset | Finding | Action |
|---|---|---|---|
| 14 | `ETH-APP-Icons-Theme-white/192-…png` | **PROVEN UNSAFE** — `/img/icons/`, 192px app icon | cleared |
| 68 | `GC-logo-positive_…_WHITE_OUT.png` | **PROVEN INVALID** — byte-identical to id 532's, and the Gates Cambridge white wordmark is the inverse mark | cleared |
| 532 | same asset | duplicate, retired in the same pass | cleared |
| 97 | `logo_horizontal_white.BORGvD08.svg` | passes the gate; the white is a legitimate brand variant on an official host | **retained, YELLOW** |
| 342 | `gbsn-white.png` | passes; Finnish government site, own host | **retained, YELLOW** |
| 458 | `…-type-white-….svg` | passes; official university host | **retained, YELLOW** |
| 540 | `TEF_Logo_White_Bg.png` | passes; own host, non-white background despite the name | **retained, YELLOW** |
| 559 | `logo-white.svg` | passes; official university theme path | **retained, YELLOW** |

**4 cleared, 4 retained.** The four retained are honest reads of the canonical detectors, not filename judgements. Whether a white wordmark should render on a dark or light card is a **design** question this pass has no evidence to answer, so they are reported for a human rather than silently deleted or silently blessed.

---


---

## 6. Duplicate Resolution

All six pairs were proven duplicates in the audit and re-verified field by field
during this pass. **None was a false positive.**

**Survivor rule**, applied in order, because these are the only two criteria
that cannot be argued with:

1. **A row holding reviews is not retirable.** Reviews are the one relationship
   in this schema that cannot be recreated. In four pairs the older row holds
   5–7 reviews and the wave-created row holds none, so the older row survives
   even when the newer one carries more research text.
2. **Where neither side holds reviews, the researched row survives.**
   Completeness and verification evidence both point the same way.

| Pair | Retired | Survivor | Reviews on survivor | Deciding evidence |
|---|---|---|---|---|
| 133 / 570 | **133** | 570 | 0 | neither side holds reviews; 570 carries 20,115 chars of `official_details`, 133 carries none |
| 438 / 530 | **438** | 530 | 0 | canonical URLs byte-identical after percent-encoding; 530 carries 18,931 chars |
| 68 / 532 | **532** | 68 | 5 | **both rows carry a byte-identical image URL**; 68 also holds 10,215 chars |
| 10 / 501 | **501** | 10 | 7 | 501's page is a child of 10's site; 10 also holds 3 history rows |
| 107 / 531 | **531** | 107 | 7 | 531 is a programme page under 107's financial-aid hub |
| 13 / 553 | **553** | 13 | 7 | **`13.catalogue_url` == `553.official_source_url`** |

**Mechanism — the repository's own, not a DELETE.** Six entries were appended to
`backend/config/retired_records.json` with `flag: DUPLICATE` and `duplicate_of`,
then the `retire` stage was run. The stage quarantines and archives; the row
keeps its id, so every review, verification-history entry and image review keeps
pointing at something addressable. This is how the 48 pre-existing retirements
work.

**Four confirmations were removed.** Ids 133, 438, 531 and 532 appeared in both
`retired_records.json` and `verification_confirmations.json`. The repository's
own invariant test caught this — a retired record must not also be asserted as
currently verified — so those four entries were dropped from the confirmations.
The other two were never in that file.

**Where research text would have been lost, it was copied first.** Ids 10 and 13
received the retired row's `official_details` block before retirement. Where both
sides already held a block (107 / 531, 68 / 532) **nothing was merged**: there is
no evidence that one supersedes the other, and asserting a merge would be a
guess. Id 531's 24,643-character block therefore stays in the source config
rather than being asserted as id 107's.

Full per-field comparison: **`DUPLICATE_RESOLUTION_MANIFEST.md`**.

**Result: 0 duplicate pairs still live. 0 duplicate pairs publicly visible.**

## 7. Archived/Active Semantics

**PROVEN — this was never a semantic contradiction.** `public_visibility_conditions()` states it directly: *"`is_archived` is not a trust question at all."* Archive is an unconditional public exclusion; trust is orthogonal.

**PROVEN — the defect was in `do_reverify`**, which had no archive check and promoted any non-`active` row in the confirmation file to `active` + `is_verified=True`. A confirmation asserts that a page was re-read; it says nothing about whether the record belongs in the catalogue.

**Data disposition — no verification state was rewritten.** Canonical policy does not require `active` to be prevented on an archived row, so no `verification_status` was altered on trust grounds. The 26 rows were reconciled by the **`retire` stage**, which re-applied quarantine to rows already listed in `retired_records.json` — the correct mechanism, not a manual edit.

**Result: archived + active = 0. Rows that would become public if unarchived = 0.**

**Code guard documented separately from the data change**, as required: `do_reverify` now skips archived and retired rows with a stated reason; `approve_image_review` refuses archived rows.

### 7.3 The wider finding: 124 promotions on rows that were never retired

**PROVEN.** The same `do_reverify` defect — promoting purely on the presence of a confirmation — also promoted **124 pre-existing rows** from `needs_review` or `quarantined` to `active`. Unlike the 26 archived rows, these are not archived, so they are **live and publicly visible now**.

**These were NOT reverted, and that is deliberate.**

`do_reverify` is the repository's canonical re-verification mechanism, and each promotion is backed by a per-row entry in `verification_confirmations.json` carrying its own `evidence` note. Reverting them would destroy verification evidence and assert something the database does not support — which is precisely what this pass was told not to do.

What *was* wrong is the mechanism, not these particular outcomes: `do_reverify` had no way to distinguish "a row someone researched and confirmed" from "a row that happened to appear in a config file". The archive check now makes the retired case explicit, and the retirement check makes the retired-by-id case explicit.

**This remains an open review item.** Whether 124 promotions made on one bulk run should each stand is a human judgement, and it is listed in §13.

**Residual trust-state change on id 14:** `needs_review → active` remains. Reverting it would be a trust-state rewrite, which §7.1 forbids. The three *data* regressions on that row — the app-icon asset, the two wiped URLs — are repaired.

---

## 8. Enum Normalization

### 8.1 `deadline_precision` — 73 rows

| Value | Rows | Mapping | Basis |
|---|---|---|---|
| `day` | 59 | `exact` | **all 59 carry a `deadline_date`** — a parsed calendar date is the one genuinely exact case |
| `application_dead` | 14 | `exact` (5) / `unknown` (9) | 5 carry a real date; the other 9 have only a display statement |

Every value passes through the existing `coerce_deadline_precision`. **No enum mapping was invented.**

### 8.2 `image_source_type` — 299 rows

| Value | Rows | Mapping |
|---|---|---|
| `official_logo` | 225 | re-derived from host + alt text via `_issuer_kind` |
| `official_page_logo` | 60 | re-derived |
| `official_ngo` | 10 | re-derived |
| `official_organization` / `official_charity` / `official_institution` | 4 | re-derived |

Re-derivation is deterministic and host-based, not a guess: `_issuer_kind` returns `official_government`, `official_university`, or — after this pass's fix — `official_provider`. Rows whose host yields no canonical classification have the value **cleared** rather than left as an invented token.

Both columns now contain **0** out-of-vocabulary values.

---


---

## 9. Local Sanitization

**Backup taken before the first write:** `backend/scholarzone.pre_wave13_hardening_20261004_171847.db`.
The manifest is a diff against that snapshot, so it is complete regardless of how
many repair passes ran.

| | |
|---|---|
| Field-level changes | **1,957** |
| Distinct rows touched | **452** |
| `deadline_precision` normalised | 73 |
| `image_source_type` re-derived | 406 |
| Asset cleared | 180 rows |
| Asset restored from pre-wave snapshot | 31 rows |
| URLs restored | 33 fields on 28 rows |
| `image_evaluation_status` set to a terminal negative | 180 |
| List-column shape repaired | 6 rows |
| Rows retired | 6 |
| Catalogue rows | 722 (unchanged — no row was created or deleted) |
| Publicly visible | **666 → 482** |

The public count fell by 184. That is the honest result: 180 rows lost an asset
they could not defend, and a row with no image is not listed.

### 9.1 What was done per row

| Case | Rows | Action |
|---|---|---|
| Decisive UI / favicon asset, pre-wave asset passes the gate | 31 | pre-wave asset restored verbatim |
| Decisive UI / favicon asset, no trustworthy prior | 78 | asset block cleared, status → `invalid_candidates` |
| `http://` image | 2 | asset block cleared |
| Image host outside the official-domain policy | 100 | asset block cleared |
| `image_url` with no `image_kind` | 1 (id 596) | asset block cleared |
| Enum violation only | 372 | value re-derived by a canonical classifier; image untouched |
| URL wiped by the wave | 28 | value restored from the pre-wave snapshot |
| List column stored as a bare JSON string | 6 | repaired by the existing `normalize_list_column` stage |
| Duplicate | 6 | retired via `retired_records.json` + `retire` stage |

### 9.2 What was deliberately **not** done

- **No image URL was invented, substituted or guessed.** Not for the 180 cleared
  rows, not for ids 14, 130, 564 or 596, and not for any of the 234 wave-created
  rows.
- **No `verification_status` was rewritten.** Including id 14's
  `needs_review → active` and the 124 bulk `reverify` promotions (§7.3).
- **No `image_kind` was manufactured.** Where no classification was supportable,
  the whole asset block was cleared rather than given an invented kind.
- **No deadline, funding figure, requirement list or verification note was
  fabricated.** Enum values were re-derived from evidence already in the row.
- **No maintenance stage was run against Neon**, and no stage other than
  `repair_list_columns` and `retire` was run against the local database at all —
  both through the real CLI, dry-run first.

## 10. Test Results

### 10.1 New: `tests/test_wave13_hardening.py` — **50 passed**

Every case drives the function that actually writes or reads the field.

| Group | Cases | Driven through |
|---|---|---|
| image | 12 | `assess_image_evidence` — the gate both write paths call |
| ingestion | 5 | `ScholarshipIngestionRecord` + `upsert_verified_scholarships` |
| enums | 14 | the model that builds every record; `_issuer_kind` |
| reverify | 3 | **`do_reverify` itself**, via `main()`, against a temp database and temp config dir |
| admin review | 3 | **`approve_image_review`**, the service the endpoint calls |
| public visibility | 2 | **`public_visibility_conditions`**, the function the catalogue counts through |

Verified end-to-end: app icon, favicon, UI asset, social asset, `http://`, commercial CDN, and legitimate official CDN all rejected; `official_logo`, `official_banner`, `program_image` and https assets accepted; valid precisions accepted and invalid coerced; valid source types accepted and invented ones rejected; **an archived record cannot be promoted by `reverify`**; **an archived record cannot be approved through the admin queue** while a live one still can.

### 10.2 Full suite

```
1 failed, 4828 passed, 2 skipped, 22 warnings in 602.42s
```

The single failure is **pre-existing, network-dependent, and unrelated to this pass**:

`tests/test_image_discovery.py::TestHumanReviewRouting::test_non_content_image_with_license_still_rejected`
asserts `non_content_total_weight >= 1.5` for `daad.de/images/header-banner.jpg`.
`validate_candidate` returns early when the fetch fails, leaving the weight at 0,
so the assertion depends on reaching `daad.de` from the test environment.
Verified directly that the detectors still score that URL at **6.0** — the banner
family fires four times — so the `"bann"` removal in §4.3 is not implicated.

An earlier full-suite run in this session also reported 8 failures in
`test_supervisor_worker.py`. Those **pass in isolation (41 passed)** and did not
recur on a clean re-run, so they are ordering-dependent flakiness in a module
about professor crawling that this pass does not touch. Recorded here rather than
discarded, because a flaky suite is worth knowing about.

**No test was weakened to reach this result.**

---

## 11. Local Release Gate

`backend/wave13_release_gate.py` — read-only, 12 checks, importing `public_visibility_conditions` rather than re-implementing it.

```
rows=722  public=482  gate=PASS  red=0  yellow=4
```

| # | Invariant | Result |
|---|---|---|
| 1 | `image_url` transport | **0** non-https |
| 2 | `image_url` / `image_kind` coherence | **0** violations |
| 3 | `image_source_type` vocabulary | **0** violations |
| 4 | `deadline_precision` vocabulary | **0** violations |
| 5 | decisive UI/favicon assets stored | **0** |
| 6 | official source (release set) | **0** |
| 7 | terminal image-evaluation status | **0** |
| 8 | list-column shape | **0** |
| 9 | orphan references | 1 — see Y4 |
| 10 | duplicate `official_source_url` | 1 — see Y4 |
| 11 | archived rows public | **0** |
| 12 | duplicate pairs still live | **0** |

**No PROVEN RED blocker remains in the proposed release set. No test was weakened.**

### 11.1 YELLOW items — explicit disposition

| # | Item | Disposition |
|---|---|---|
| **Y1** | **id 398** — `1200x630-jpg/…/gallery/…unsplash_.jpg` | The wave had replaced this with `apple-touch-icon.png`; the repair correctly restored the genuine UvA photograph. The residual `social thumbnail dimensions` signal is an **OpenGraph size transform**, not proof of a UI asset — the path is the university's own `/content/gallery/`. **Retained. Needs a human eye, not an automatic clear.** |
| **Y2** | **ids 346, 347** — `http://` official source | **Pre-existing**, present in the pre-wave snapshot, unchanged by Wave 1–3. Both rows have **no image**, so neither is public and neither is in the apply manifest. Correcting them means re-researching the programme page, which no code change and no data edit can supply. **Excluded from the release set; needs a research pass.** |
| **Y3** | orphan `scholarship_verification_history → id 358` | The wave **purged** id 358 rather than retiring it. Purge is the one mechanism in this schema that loses its id, and it was not used for the six duplicates in this pass. Documented, not repaired — repairing it would mean re-creating a row the wave deliberately removed. |
| **Y4** | duplicate URL on ids 133 / 570 | Expected and correct: both rows still exist, one archived and one live. The public gate excludes archived rows unconditionally, so only 570 is visible. Retained for the audit trail. |

---

## 12. Production Readiness

**NOT READY. No production change is proposed for apply until §12 of the apply manifest is satisfied.**

| Precondition | Status |
|---|---|
| Code guards implemented and tested | **MET** |
| Local data repaired, 0 RED | **MET** |
| 6 duplicates resolved | **MET** |
| Enum violations cleared | **MET** |
| Neon reachable read-only | **NOT MET** — §12 below |
| ID-level production delta known | **NOT MET** — depends on the above |
| 234 wave-created rows dispositioned | **NOT MET** — deliberately excluded |

### 12.1 Neon connectivity — **UNKNOWN**, and provably so

| Path attempted | Result |
|---|---|
| `SCHOLARZONE_DATABASE_URL` / `DATABASE_URL` / `PG*` in the process | **absent** |
| `backend/.env` | only `RESEND_API_KEY`, `NOTIFICATION_EMAIL`, `SCHOLARZONE_VERIFICATION_SECRET` |
| Application as `SCHOLARZONE_ENVIRONMENT=production` | `RuntimeError: SCHOLARZONE_DATABASE_URL is required in production.` |
| GitHub Actions secret `SCHOLARZONE_DATABASE_URL` | **exists** (set 2026-09-06) — GitHub returns names and timestamps, never values |
| Vercel CLI | installed; no linked project directory present |

**UNKNOWN: the contents of Neon.** Every "old value" in the apply manifest is the local post-wave value, not the production value. The manifest therefore **cannot** be diffed against production and must not be applied.

---

## 13. Remaining Unknowns

| # | Unknown | Why it matters | Class |
|---|---|---|---|
| 1 | Neon contents and the exact production delta | determines whether the manifest is applicable at all | **UNKNOWN** |
| 2 | Disposition of the 234 wave-created rows | they are excluded from the manifest; they cannot be separated from their image claims | **UNKNOWN** |
| 3 | Whether the four retained white wordmarks render acceptably | a design question; 4 rows depend on it | **PLAUSIBLE BUT UNPROVEN** |
| 4 | Whether id 398's OG derivative is acceptable as a programme image | genuine photograph, OG-sized; 1 row | **PLAUSIBLE BUT UNPROVEN** |
| 5 | Correct official URLs for ids 346, 347 | 2 rows permanently non-public until researched | **UNKNOWN** |
| 6 | Whether the 194 class-B replacements are the *best* available asset | they pass the gate; nothing compares them to alternatives | **PLAUSIBLE BUT UNPROVEN** |
| 7 | Production schema parity with local | migrations were not compared against Neon | **UNKNOWN** |
| 8 | Whether 124 bulk `reverify` promotions should each stand (§7.3) | they are live and public; reverting would destroy verification evidence | **UNKNOWN** |

---

## 14. Exact Next Action

**In order. Nothing after step 3 may start before step 2 completes.**

1. **Deploy the six code guards.** Until they are live, the next `add`, `logos` or `reverify` run can reintroduce every value this pass corrected. Files: `image_validator.py`, `scholarship_ingestion.py`, `scholarzone_maintenance.py`, `admin_image_review.py` (service and router), `image_discovery_orchestrator.py`.

2. **Provision a read-only Neon role** and prove it with a successful read. Then run the ID-level comparison of `WAVE1_3_PRODUCTION_APPLY_MANIFEST_FINAL.md` against Neon, row by row. **Any row whose production value differs from the manifest's "old value" must be re-decided, not applied.**

3. **Decide the four YELLOW items** (§11) and the 234 wave-created rows. Both need a human; neither can be settled from the evidence available here.

4. Only then: dry-run every stage against Neon, review the run log, and — as a **separate, separately-approved operation** — apply.

**Never copy `scholarzone.db` into Neon.** The apply mechanism is the repository's own stages driven by `backend/config/*.json`, one stage at a time.

---

