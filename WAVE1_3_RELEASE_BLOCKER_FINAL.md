# WAVE 1–3 RELEASE BLOCKER AUDIT — FINAL

**Date:** 2026-10-04 · **Mode:** READ-ONLY (every SQLite handle opened `file:…?mode=ro`)
**Not done:** no Neon write, no SQLite write, no maintenance stage, no image repair, no code change, no deploy.

---

## 1. Executive Summary

Wave 1–3 must **not** be applied to Neon. Seven independent release blockers are proven, and they are larger than the four items named in the audit request.

| # | Blocker | Scale | Class |
|---|---|---|---|
| 1 | All **6** suspected duplicate pairs are duplicates — none was safe to keep | 6 pairs / 12 rows | **PROVEN** |
| 2 | **400 rows** had `image_url` + `image_kind` mutated | 400 rows | **PROVEN** |
| 3 | **112 rows** now display a favicon / app-icon / UI asset as their logo — **107 are public** | 107 public | **PROVEN** |
| 4 | **8 rows** display a white-on-transparent wordmark under `image_kind=official_logo` — **all 8 public** | 8 rows | **PROVEN** |
| 5 | **26 rows** carry a cross-host image; **9 on third-party CDNs** that the wave contract bans | 22 public | **PROVEN** |
| 6 | **25 rows** are `is_archived=1` **and** `verification_status=active`; **24 would go public the instant archiving is cleared** | 24 latent | **PROVEN** |
| 7 | **75 rows** carry a `deadline_precision` outside the app vocabulary (`day` 61, `application_dead` 14); **74 rows** carry a non-enum `image_source_type` | 149 rows | **PROVEN** |

Two earlier conclusions are corrected by this audit:

- The "archived + active" state is **not a contradiction** — the repository's own docstring says `is_archived` is not a trust question and is excluded unconditionally. It is a **latent exposure**, not a current one. (DISPROVEN as "inconsistency")
- Only **1** existing trusted logo was replaced (id 477). The other 233 replacements overwrote photos, banners and UI icons — directionally correct, though the *replacement asset* is frequently a favicon. (DISPROVEN as "trusted images overwritten")

**A GREEN subset exists and is sizable: 324 rows.** See §13.

---

## 2. Current Local State

`backend/scholarzone.db` · before-state = `scholarzone.pre_wave1_20261004_133109.db` (13:30:58 snapshot)

| | before | now |
|---|---|---|
| total rows | 489 | 722 |
| created / deleted | — | **234 / 1** (id 358) |
| verification_status active | 347 | 694 |
| needs_review | 140 | 5 |
| quarantined | 2 | 23 |
| is_archived | 0 | 46 |
| logo-identity `image_kind` | 82 | 713 |
| public visibility gate | 316 | **666** |
| deadline_precision = exact | 3 | 174 |
| funding_amount populated | 0 | 269 |
| official_details populated | 0 | 540 |

Change decomposition of the 488 pre-existing rows (§7 basis):

| Bucket | Rows |
|---|---|
| metadata changed only (no image touched) | 71 |
| image changed only | 55 |
| both metadata and image changed | 346 |
| untouched | 16 |

---

## 3. Neon State — UNKNOWN / VERIFIED FACTS

**VERIFIED FACT (proven by execution):** production refuses to start without a database URL, and this machine has none.

```
production   -> REFUSED: SCHOLARZONE_DATABASE_URL is required in production.
```

| Source | Result |
|---|---|
| `SCHOLARZONE_DATABASE_URL` / `DATABASE_URL` / `PG*` in process | all absent |
| `backend/.env` (gitignored) | only `RESEND_API_KEY`, `NOTIFICATION_EMAIL`, `SCHOLARZONE_VERIFICATION_SECRET` |
| `backend/.env.example` | template only (host is literally `host`) |
| `.vercel/repo.json` | linked to project `scholarzone-fwzj`; env vars unreadable without the CLI |

**PROVEN:** Wave 1–3 wrote nothing to Neon — every run used `SCHOLARZONE_ENVIRONMENT=development`, which forces SQLite.
**UNKNOWN:** Neon's actual contents. Not "unchanged" — unmeasured.

---

## 4. True Duplicate Analysis

### Pair 133 / 570 — Invest Your Talent in Italy · **PROVEN DUPLICATE**

| | 133 | 570 |
|---|---|---|
| URL | `…esteri.it/SITOIYT/EN/current-call` | `…esteri.it/SitoIYT/EN/current-call` |
| Awarding body | MAECI, ICE Agency, Uni-Italia | MAE, DG Growth & Export Promotion, ICE, Uni-Italia |
| amount | none | EUR 10,800 / year |
| status | `open` | `upcoming` |
| official_details | **0 chars** | 20,115 chars |
| created | 2026-09-01 | **2026-10-04 (this wave)** |
| reviews / history | 0 / 0 | 0 / 0 |

Same host, same application path differing only in letter case; same programme name; same three-funder structure; the only EUR figure published for the scheme appears in 570. Canonical URL normalisation (lowercase host, trailing slash, percent-encoding) collapses them to one page.

- **Canonical survivor: 570.** **Duplicate: 133.**
- **Reason:** 570 carries the full research block; 133 has none and its URL casing is the reason the UNIQUE index could not collapse them.
- **Conflict to resolve:** 133 says `Fully Funded`, 570 says `Partial Funding`. That is a factual contradiction inside one award — **UNKNOWN** which is correct without re-reading the call.
- **Safest mechanism:** `retired_records.json` with `flag: DUPLICATE`, `duplicate_of: 570` → `retire` stage. Archive-then-delete (the 358 path) is unnecessary: nothing references either row.

### Pair 438 / 530 — A*STAR National Science Scholarship (PhD) · **PROVEN DUPLICATE**

Canonical URLs are **byte-identical after percent-encoding normalisation** (`(` ↔ `%28`). Titles identical.

| | 438 | 530 |
|---|---|---|
| official_details | 0 chars | 18,931 chars |
| verification_history | **2 rows** | 0 |
| deadline | none | 2026-10-01 |
| image | `…/api/media/867ab78f…/favicon.ico` | A*STAR logo |
| created | 2026-09-06 | **this wave** |

- **Canonical survivor: 530** (research present). **Duplicate: 438.**
- **Caution — PROVEN counter-evidence:** 438 is the older row and is the one carrying **verification history (2 rows)** and `reviews=0`. Retiring it discards that history from the live row; the history table keeps it, but the canonical row loses 438's prior audit trail. A human must accept that.
- 438's own image is a **favicon** — i.e. the older row already violated the logo contract.

### All six pairs: additional decisive evidence

| Pair | Decisive evidence | Verdict |
|---|---|---|
| **68 / 532** Gates Cambridge | **Identical image URL** on both: `GC-logo-positive_font_update_WHITE_OUT.png`. Same award, same funder, same £23,152 maintenance, both "2027/8 entry". 68 holds 5 reviews + 10,215 chars of research. | **PROVEN DUPLICATE** — survivor 68 |
| **10 / 501** Deutschlandstipendium | 501's URL is a *sub-page* of 10's site (`/wie-es-funktioniert`). Same €300/month split funding. 10 holds 7 reviews + 3 history rows. | **PROVEN DUPLICATE** — survivor 10 |
| **107 / 531** NTU NPGS | 531's URL is `/…/scholarships/npgs`; 107 is the parent **hub** page. Both titled NPGS, both quote the same S$4,300/4,800/5,300 matrix. 107 holds 7 reviews. | **PROVEN DUPLICATE** — survivor 107 |
| **13 / 553** POSCO | **`13.catalogue_url` == `553.official_source_url`** (`/en/asia/abroad/business`). Same KRW 1,000,000/month, same 4+6 semester structure. | **PROVEN DUPLICATE** — survivor 553 |

---

## 5. Likely Duplicate Analysis

All four were investigated field-by-field rather than by title. **All four are duplicates** — the classification asked for was available:

| Pair | Classification | Evidence beyond the title |
|---|---|---|
| 68 / 532 | **PROVEN DUPLICATE** | identical image asset; identical funder and amount; 68 has the research |
| 10 / 501 | **PROVEN DUPLICATE** | 501's page is a child of 10's site; identical funding split; 10 has 7 reviews + history |
| 107 / 531 | **PROVEN DUPLICATE** | 531 is a specific programme page under 107's hub; identical stipend matrix; 107 has 7 reviews |
| 13 / 553 | **PROVEN DUPLICATE** | `13.catalogue_url` **equals** `553.official_source_url` — a direct row-to-row link |

**Not duplicates (checked, correctly excluded):** 551 / 552 JSPS — `e-ippan` (Standard) vs `e-oubei-s` (Short-term, North America), different deadlines and programmes.

**Net effect:** 6 duplicate rows to retire — `570`→`133`? No: survivors are **570, 530, 68, 10, 107, 553**; duplicates to retire are **133, 438, 532, 501, 531, 13**.

> Note the pairing is counter-intuitive in four cases: the **wave-created** row holds the research, so retiring the older row discards older review/history context. That trade-off is a policy decision, not a technical one.

---

## 6. Complete Image Delta Analysis

### 6.1 Column census (pre-existing rows, 400 mutated)

| Column | Rows changed |
|---|---|
| `image_url` | **400** |
| `image_kind` | **400** |
| `image_alt_text` | 401 |
| `image_verified_at` | 401 |
| `image_evaluated_at` | 400 |
| `image_source_url` | 394 |
| `image_source_type` | 394 |
| `image_evaluation_status` | 167 |

651 rows carry at least one image-delta entry (400 existing + 234 new + overlap).

### 6.2 Direction of change

| Category | Rows | Assessment |
|---|---|---|
| **New row** (image attached at insert) | 234 | see 6.4 |
| **B** existing row gained an image where it had none | 166 | directionally correct |
| **F** replaced a non-accepted image (photo/banner/UI icon) | 233 | directionally correct; asset quality often poor |
| **C** replaced a **trusted** (logo-kind) image | **1** (id 477) | low risk |
| **G** `image_url` present, `image_kind` NULL | **1** (id 596) | defect |
| **H** no image at all | 8 | 541, 635 discussed in §11 |
| **I** source URL/type changed | 400 | follows the image swap |

**PROVEN:** the wave did **not** blanket-overwrite good logos. 233 of 234 replacements overwrote images the pipeline already classified as untrusted. The risk is in *what replaced them*, not in overwriting something better.

### 6.3 The actual defects — asset type and provenance

| Defect | Rows | Public |
|---|---|---|
| Favicon / app-icon / UI asset stored as the record logo | **112** | **107** |
| Filename says white or reversed | **8** | **8** |
| Cross-host image (image host ≠ awarding-body host) | **26** | **22** |
| — of which on a third-party CDN | **9** | — |

**Third-party CDN rows (banned by the wave contract):** 47, 50, 195, 196, **513 (new)**, 132, 343, 344, 345 — served from `cloudfront.net` and `images.squarespace-cdn.com`.

**White-on-transparent rows, all public:**
`14` (ETH app icon "Theme-white"), `68` + `532` (`GC-logo-positive_…_WHITE_OUT.png` — the Gates Cambridge white wordmark), `97` (`logo_horizontal_white`), `342` (`gbsn-white.png`), `458` (`logotype-white`), `540` (`TEF_Logo_White_Bg.png`), `559` (`logo-white.svg`).

**Cross-host rows that are *legitimate* (dead stored URL, live body elsewhere):** 596 → `calas.lat`, 349 → `emcl.eu`, 419 → `visegradfund.org`, 523 → `unhcr.org`, 526 → `oead.at`, 536 → `rufford.org`, 515 → `mext.go.jp`, 220 → `ist.ac.at`, 82 → `fondationtrudeau.ca`, 372 → `universitaly.it`, 194 → `net.au`. These are defensible; **9 CDN rows are not**.

### 6.4 New rows

234 new rows, all image-gated. 40 have a suspect or absent image; 194 have a clean one. **PROVEN:** because `public_visibility_conditions()` requires `image_url` **and** `image_verified_at`, a new row with its image fields stripped becomes invisible — so **new rows cannot be separated from image decisions**.

---

## 7. ID 14 Investigation — PROVEN UNSAFE

| Field | Before | After |
|---|---|---|
| `image_url` | `…/excellencescholarship/_jcr_content/pageimages/…` (program photo) | `/etc/designs/ethz/img/icons/ETH-APP-Icons-Theme-white/192-xxxhpdi.png` |
| `image_kind` | `program_image` | **`official_logo`** |
| `image_source_type` | `official_provider` | `official_logo` |
| `image_source_url` | the scholarship page | `https://ethz.ch/` (site root) |
| `image_alt_text` | programme name | `ETH Zurich` |
| `official_updates_url` | ETH academic calendar | **`None`** |
| `verification_status` | `needs_review` | `active` |
| `status` | `open` | `upcoming` |

**PROVEN UNSAFE, three independent grounds:**
1. The asset is a **192 px app icon**: path is `/img/icons/`, filename `ETH-APP-Icons-Theme-white`, dimensions `192x…`. It is a UI asset, not the ETH wordmark.
2. The name says **`Theme-white`** — the banned white-on-transparent class. It is now labelled `image_kind=official_logo` and is **publicly visible**.
3. `official_updates_url` was **deleted** (`None`) — a metadata regression unrelated to images, and `verification_status` moved `needs_review → active` in the same write.

Host match is correct (`ethz.ch` → `ethz.ch`), so the failure is asset selection, not provenance. **The wave research note for this record claims no logo constraint was violated — that claim is false against the stored URL.**

---

## 8. ID 130 / 564 / 596 Investigation

### ID 130 — Aga Khan Foundation · **PROVEN UNSAFE**

- `image_url` = `https://akf.org/wp-content/themes/aga-khan/assets/favicon/favicon.svg`
- Path segment is literally **`/favicon/`**. A favicon is not a logo.
- `image_evaluation_status` moved **`source_blocked` → `verified`** in the same write. The previous state recorded that the source could not be evaluated; re-marking it verified without new evidence is **verification laundering**, the exact failure mode the retired-row promotion also exhibits.
- `image_kind=official_logo`, **publicly visible**.

### ID 564 — JJ/WBGSP (World Bank) · **PROVEN UNSAFE**

- **New row.** `image_url` = `https://www.worldbank.org/content/dam/wbr-redesign/logos/wbg-favicon.png`
- Filename says **`-favicon`**; it is a 192-class site icon, not the World Bank Group lockup.
- Stored as `image_kind=official_logo`, `image_evaluation_status=verified`, **publicly visible**.

### ID 596 — CALAS Fellowships · **PROVEN UNSAFE (two grounds)**

- **New row.** `image_url` = `http://calas.lat/sites/default/files/imagotipo_color.png` — **plaintext `http://`**, the only such row in the database.
- `image_kind` is **NULL** while `image_source_type='official_scholarship'` — the only row in 722 that has an image without a kind.
- Cross-host: page `udg.mx`, image `calas.lat`.
- The wave research note explains `calas.lat` refuses HTTPS — i.e. the agent knowingly wrote an `http://` asset. The merge's `https`-only rule applied to `official_source_url`, not to `image_url`.
- **Publicly visible.**

---

## 9. Archived + Active Contradiction

### The correct invariant — PROVEN from the code

`backend/app/repositories/scholarships.py:24-73`, `public_visibility_conditions()`:

> *"`is_archived` is not a trust question at all. A record is archived when its round has closed, and it is excluded unconditionally rather than being left to the settings: archiving is a promise that expired opportunities are not offered as if they were live."*

So under the repository's documented model, **`verification_status='active'` + `is_archived=1` is consistent, not contradictory.** My previous report called it an inconsistency — **DISPROVEN**.

**PROVEN consequences:**
- `public_visibility_conditions()` includes `Scholarship.is_archived.is_(False)` → all 25 are excluded from the directory and from search.
- `services/counting/catalogue.py:86` sets `listed = and_(*public_visibility_conditions())` and every published count is `and_(listed, …)` → **all 25 are excluded from every published figure**, including `verification_status_active`.
- **Measured: 0 of 25 are public.**

### The real problem

The wave's `reverify` stage promoted these rows out of `quarantined` because the merge had emitted confirmations for **retired** ids. The retirement intent was partially undone.

| Question | Answer |
|---|---|
| When did each become active? | During the wave's `reverify` runs (`run_id cd1731533d8243ed`, `38fbda435c3f4fe5`, …) |
| Did wave 1 `reverify` cause it? | **PROVEN yes** — the merge emitted confirmations for retired ids before the guard was added |
| Does the public gate exclude them? | **PROVEN yes** |
| Can Match/Count see them? | Directory: no. Counts: no. **Adjacent finding:** `routers/admin_image_review.py:80` counts `needs_review` rows **without** the `is_archived` filter — archived rows surface in the admin image queue |
| Would un-archiving expose them? | **PROVEN yes — 24 of 25 pass the full gate the instant `is_archived` is cleared:** ids 11, 37, 50, 119, 126, 132, 187, 190, 191, 198, 221, 238, 242, 265, 287, 349, 364, 389, 404, 412, 414, 435, 469, 474 |

**Invariant to adopt:** `is_archived=1` must be a terminal public exclusion, and `verification_status` must never be advanced on a row present in `retired_records.json`. The merge now enforces the second; nothing enforces the first beyond the query.

---

## 10. Missing `official_details` — 71 new rows

| Question | Answer | Class |
|---|---|---|
| Required for public visibility? | **No.** `public_visibility_conditions()` checks only `verification_status`, `is_archived`, `is_verified`, `image_url`, `image_verified_at`, `image_source_type` | **PROVEN** |
| Required by the research contract? | Yes — it is the structured official-facts block | **PROVEN** |
| Class | **OPTIONAL for visibility, MISSING_EVIDENCE against the contract** | — |
| Publicly visible | **69 of 71** | **PROVEN** |
| Carrying a `verification_note` | **0 of 71** | **PROVEN** |
| With no `eligibility_summary` **and** no `description` | **1** (id 690) | **PROVEN** |

The 69 are not empty shells: they carry populated `eligibility_summary` (median ~300 chars), `requirements`, `documents` and `coverage`. They are public-safe by the gate but carry **no per-row verification narrative** and no official-facts block — so their factual provenance rests on the wave's research files, not on anything in the row.

**Correctly public because of a missing required field:** **0**. The gate has no `official_details` requirement. This is a contract gap, not an exposure bug.

---

## 11. Missing-Image Records — 541 / 635

Neither is a retrieval failure. Both are honest refusals.

### ID 541 — Mastercard Foundation Scholars Program

- Awarding body: Mastercard Foundation · host `mastercardfdn.org`
- `logo_override`: **null** in the source record
- Wave finding: every logo *file* on that host is **Mastercard Inc.'s** two-circles mark; the Foundation's own mark exists only as an inline SVG with no citable URL. Third-party copies banned.
- **Verdict: PROVEN — no trustworthy first-party file exists.** The `null` is correct. Row is non-public.

### ID 635 — AMEXCID / Becas de Excelencia (Mexico)

- Host `www.gob.mx` · `official_details` **present** (contact, cycle, status note all populated)
- `logo_override`: **null**
- Wave finding: the only real mark is `logo_blanco.svg` (white-on-transparent, banned); AMEXCID/SRE marks appear only inside a website banner.
- **Verdict: PROVEN — the source has a usable *brand* but no trustworthy *file*.** Discovery did not fail; it correctly refused.

Neither id is a release blocker. Both are non-public, and both are the honest outcome of the logo rules.

---

## 12. ID-Level Release Manifest

Full machine-readable manifests (temp, read-only):

| File | Contents |
|---|---|
| `local_delta_manifest.json` | added/removed/changed ids, per-id changed-field map, field census |
| `blocker_evidence.json` | duplicate-pair comparison, 651-row image manifest, archived+active list, 71-row list |
| `image_provenance.json` | 26 cross-host rows, 112 icon-like ids, 8 white-named ids |
| `release_partition.json` | the exact GREEN / YELLOW / RED id lists in §13 |

Per-id operation classes for every affected row:

| Operation | Rows | Wave | Publishable? | Blocker |
|---|---|---|---|---|
| existing: metadata refresh, image untouched | 71 | 1 | mostly | 4 excluded (dup/archived) |
| existing: metadata + clean image swap | 257 | 1/3 | **yes** | — |
| existing: metadata + suspect image swap | 68 | 1/3 | no | image |
| existing: image swap only | 55 | 1/3 | no | image |
| existing: untouched | 16 | — | n/a | — |
| new row, clean image | 194 | 2 | no | image-gated + contract |
| new row, suspect/absent image | 40 | 2 | no | image |
| removed | 1 (358) | 1 | — | archive decision |

---

## 13. GREEN / YELLOW / RED Partition

> The wave is **not** approved as one block.

### 🟢 GREEN — 324 rows

Existing rows whose metadata refresh can be published **without any image mutation** and without touching a duplicate or an archived-active row.

- **67** rows — metadata changed, image untouched
- **257** rows — metadata + image changed, but the new image passes the clean test (own host, not an icon/UI asset, not white-named, https)

**Can metadata be separated from images? PROVEN YES** — the `add` stage writes the row fields and attaches images from the record's `image_*` keys; omit them and existing images stay untouched. Do not run the `logos` stage for this subset.

### 🟡 YELLOW — 99 labelled rows (overlapping)

| Group | Rows | Decision needed |
|---|---|---|
| metadata + suspect image | 68 | re-pick the logo, or publish metadata with the image change withheld |
| duplicate pair, new side | 6 (501, 530, 531, 532, 553, 570) | retire, keeping the survivor that holds the research |
| archived + active | 25 | decide whether `verification_status` should stay `active` on a retired row |
| enum violations riding along | 75 `deadline_precision`, 74 `image_source_type` | normalise before any publish |

### 🔴 RED — 289 rows

| Group | Rows | Why |
|---|---|---|
| **all new rows** | 234 | public visibility *requires* an image — cannot be separated from the image decision |
| **image-only mutations on existing rows** | 55 | no metadata value to justify them |

**PROVEN:** the 234 new rows cannot be split out of the image decision, because stripping `image_url`/`image_verified_at` makes them fail the public gate outright.

---

## 14. Production Blockers

**A. Is ANY part safe to apply to Neon now?** **NO.** A 324-row GREEN subset is *identifiable*, but not *applyable*: Neon connectivity is unverified and the production delta is unknown. Nothing can be applied to a database that cannot be read.

**B. Is the WHOLE wave safe?** **NO.** Blockers B–H below are all unresolved.

**C. Exactly what is blocked**

| Blocked | Ids / fields |
|---|---|
| Duplicate rows | 133, 438, 501, 531, 532, 553 (survivors: 570, 530, 68, 10, 107, 553) |
| Archived+active | 11, 37, 50, 119, 126, 132, 187, 190, 191, 198, 221, 238, 242, 265, 287, 349, 364, 389, 404, 412, 414, 435, 469, 474 (+1) |
| Icon/UI asset as logo | 112 ids, 107 public (`14, 35, 40, 51, 57, 58, 84, 85, 86, 99, 101, 125, 130, 136, 152, 161, 173, …`) |
| White/reversed asset | 14, 68, 97, 342, 458, 532, 540, 559 |
| Third-party CDN image | 47, 50, 132, 195, 196, 343, 344, 345, **513** |
| `http://` image + null kind | 596 |
| `deadline_precision` out of vocabulary | 75 rows (`day` 61, `application_dead` 14) |
| `image_source_type` out of enum | 74 rows (`official_page_logo` 60, `official_ngo` 10, `official_organization` 2, `official_charity` 1, `official_institution` 1) |
| Mojibake titles | 544, 545 (`GrundfÃ¶rderung fÃ¼r AuslÃ¤nder:innen`) |
| Bare-string `eligibility` | 411, 413, 426 |
| New rows, no `official_details` | 71 (69 public) |

**D. Image-related blockers:** 400 `image_url`+`image_kind` mutations · 112 icon assets (107 public) · 8 white assets (8 public) · 26 cross-host (22 public, 9 CDN) · 596 · 55 image-only rows · 234 new rows.

**E. Verification-related blockers:** 25 archived+active rows, 24 of them latent exposures · id 130 `source_blocked → verified` without new evidence · 71 new rows with **0** verification notes · id 690 with no eligibility summary and no description.

**F. Duplicate-related blockers:** 6 pairs, all PROVEN.

**G. Schema / data-quality blockers:** 75 `deadline_precision` violations · 74 `image_source_type` violations · 2 mojibake titles · 3 bare-string list fields · 1 `http://` image · 1 image without kind.

**H. Requiring code fixes before any apply:**
1. **`image_url` is not held to the `https`-only rule that `official_source_url` is.** The merge validated one and not the other — id 596 slipped through. Needs a validator-level fix, not a data fix.
2. **`image_source_type` is not enum-validated** — 74 rows carry invented values that the ingestion model's documented enum does not include.
3. **`deadline_precision` is not enum-validated at write time** — `day` and `application_dead` persisted through 75 rows.
4. **Image trust contract is not enforced at write time.** `do_add` attaches whatever `image_*` the record carries, with no favicon/app-icon/white check. The wave relied on agent discipline plus a merge-level check that only covered `logo_override`.
5. **`reverify` has no retirement guard** — it advanced rows present in `retired_records.json`. Now guarded in the merge, but the stage itself remains unguarded for any other caller.
6. **`admin_image_review` omits the `is_archived` filter** — archived rows appear in the admin image queue.

---

## 15. Required Fixes (none applied — specification only)

| # | Fix | Type | Before apply? |
|---|---|---|---|
| 1 | Retire the 6 duplicate rows via `retired_records.json` with `duplicate_of` | data | yes |
| 2 | Decide the archived+active invariant; re-quarantine or leave `active` with a documented rule | policy + data | yes |
| 3 | Re-pick logos for the 107 public icon/UI rows and the 8 white rows | image | yes, or hold them RED |
| 4 | Replace the 9 CDN-hosted images with first-party assets, or drop them | image | yes |
| 5 | Fix id 596: https asset, `image_kind` set, cross-host justified or removed | image | yes |
| 6 | Normalise 75 `deadline_precision` and 74 `image_source_type` values | data | yes |
| 7 | Repair mojibake on 544/545; fix bare-string `eligibility` on 411/413/426 | data | yes |
| 8 | Enrich or hide the 71 rows without `official_details` | data | yes |
| 9 | Add the 6 validators in §14H to the write path | **code** | code change required before any apply |
| 10 | Read-only Neon access + id-level delta against local | access | **blocking** |

---

## 16. Safe Apply Preconditions

Apply nothing until **all** of these hold:

1. **True duplicates resolved** — 133/438/501/531/532/553 retired with `duplicate_of` recorded.
2. **Archived/active semantics resolved** — a written rule, and the 25 rows conform to it.
3. **Suspicious image changes understood** — the 107 icon rows and 8 white rows individually reviewed.
4. **Image-reversion contamination controlled** — the open image-forensics incident must be closed or its scope formally excluded from this release.
5. **Exact production delta known** — an id-level local-vs-Neon manifest exists.
6. **Production connectivity verified** — a read-only Neon role, proven by a successful read.
7. **An explicit GREEN subset exists** — it does: **324 rows**, §13.
8. **Schema violations normalised** — §14C.

The apply mechanism remains the repository's own stages against the `backend/config/*.json` change set, dry-run first, one stage at a time. **Never copy `scholarzone.db` into Neon.**

---

## 17. Final Release Decision

| | |
|---|---|
| **Apply the whole wave?** | **NO** |
| **Apply a subset?** | **NO — not yet.** A 324-row GREEN subset exists and is defensible, but Neon cannot be read, so the delta is unknown and every precondition in §16 fails. |
| **Neon touched?** | **NO.** No credential has ever been present in this process. |
| **Anything changed today?** | **NO.** Read-only throughout; only this report was written. |

**The one number that matters:** of 651 rows touched at the image layer, **400 existing rows had their image replaced and 234 new rows depend on an image to be visible at all.** While the image-forensics incident is open, that is not a data-quality question — it is an unresolved trust question. The 324-row GREEN subset exists precisely so the wave is not judged on record count; it is the maximum that can move without touching a single image decision.

### Evidence index

| Claim | Source |
|---|---|
| Local metrics, row delta, field census | `local_delta_manifest.json` (read-only diff vs the 13:30 snapshot) |
| Duplicate pairs, image manifest, archived+active, missing details | `blocker_evidence.json` |
| Cross-host / icon / white asset classification | `image_provenance.json` |
| GREEN / YELLOW / RED id lists | `release_partition.json` |
| Public visibility semantics | `backend/app/repositories/scholarships.py:24-73` |
| Count semantics | `backend/app/services/counting/catalogue.py:86-113` |
| Admin queue gap | `backend/app/routers/admin_image_review.py:80-82` |
| Production unreachability | `backend/app/core/config.py` behaviour + env probe + `.vercel/repo.json` |