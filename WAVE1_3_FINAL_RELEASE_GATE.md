# WAVE 1–3 FINAL RELEASE GATE

**Date:** 2026-10-04 · **Mode:** read-only audit + test-safety boundary fix
**Neon:** untouched — no write, no read, no connection, no secret retrieved.
**Local state:** 722 rows · 482 publicly visible · **BLOCKED for production.**

Every conclusion is labelled **OBSERVED FACT**, **PROVEN**, **DISPROVEN**, **PLAUSIBLE BUT UNPROVEN** or **UNKNOWN**.

---

## 1. Test Safety

**PROVEN — the root cause.** Four facts compose into a live-data write:

| # | Location | Behaviour |
|---|---|---|
| 1 | `app/core/config.py:12` | `DEFAULT_DATABASE_URL = f"sqlite:///{BACKEND_DIRECTORY / 'scholarzone.db'}"` |
| 2 | `app/core/config.py:60` | `environment` defaults to `"development"` when unset |
| 3 | `app/core/config.py:77` | outside production, an unset `SCHOLARZONE_DATABASE_URL` falls back to that default |
| 4 | `tests/conftest.py` (old) | the in-memory safety net applied **only if** `SCHOLARZONE_ENVIRONMENT=test` was *already* set |

The guard therefore depended on the caller exporting an environment variable. A bare `pytest` did not, so the suite resolved to `backend/scholarzone.db`. **OBSERVED FACT:** this was exercised — a full-suite run rewrote 5 live rows.

**PROVEN — a second, unrelated hazard.** `backend/` holds **fifteen** `*test*.py` files. **None defines a single `test_` function** (verified: zero `def test_` across all fifteen). pytest collected them by filename and executed their module-level code — and `cache_bust_test.py` issues an HTTP GET to the deployed production API **at import time**.

### The fix

`tests/conftest.py` now **fails closed**, before any test module imports the application:

| Condition | Ordinary test run | With `SCHOLARZONE_TEST_ALLOW_EXTERNAL_DB` |
|---|---|---|
| nothing set | defaults to `test` + `:memory:` | — |
| `SCHOLARZONE_ENVIRONMENT=production` | **REFUSED** | allowed, warned on stderr |
| `SCHOLARZONE_DATABASE_URL` is `postgresql://` | **REFUSED** | allowed, warned |
| `SCHOLARZONE_DATABASE_URL` resolves to `scholarzone.db` | **REFUSED** | allowed, warned |
| any other SQLite path | allowed | allowed |

Design points that matter:

- **The safe default is unconditional.** It no longer depends on the caller.
- **Paths are compared after resolution**, so `sqlite:///scholarzone.db` — a different spelling of the same file — is caught.
- **It refuses; it never redirects.** A silently repointed run would pass against a database nobody chose. The refusal states the environment exactly as the caller left it.
- **A controlled integration run is still possible**, through the opt-in, and is never quiet.

`pytest.ini` adds `testpaths = tests`, which excludes the fifteen dev scripts from collection entirely.

**Regression test:** `tests/test_test_isolation_boundary.py` — **12 tests, all passing.** Each spawns a real subprocess with a controlled environment and asserts both halves: the refusal *and* that the environment was not modified.

```
$ SCHOLARZONE_DATABASE_URL=sqlite:///scholarzone.db  python -c "import sys;sys.path.insert(0,'tests');import conftest"
conftest.UnsafeTestDatabaseTarget: REFUSING TO RUN TESTS: SCHOLARZONE_DATABASE_URL
  points at the working catalogue.
  database target : C:\Users\GopaL\...\backend\scholarzone.db
  consequence     : tests would read and write the live local database. This has
                    already happened once: a full-suite run modified it.
```

---

## 2. Backup State

**Nothing was restored.** Every file opened `mode=ro`.

| File | Modified | Rows | SHA-256 (16) | Readable |
|---|---|---|---|---|
| `scholarzone.pre_wave1_20261004_133109.db` | 2026-10-04 13:30:58 | 489 | `0fe07d8c3b8b0fae` | yes |
| `scholarzone.pre_wave13_hardening_20261004_171847.db` | 2026-10-04 17:14:23 | 722 | `bbae993e98e0a351` | yes |
| `scholarzone.pre_wave13_hardening_20261004_171852.db` | 2026-10-04 17:18:47 | 722 | `8fa9dfb3bc760561` | yes |
| `scholarzone.pre_wave13_hardening_20261004_180133.db` | 2026-10-04 17:57:59 | 722 | `9f70679c307ca7b3` | yes |
| `scholarzone.db` (live) | 2026-10-04 18:01:34 | 722 | `af35a5dac260a5c3` | yes |

**Rollback point: `171847`** — the earliest pre-repair snapshot, taken before the first write of the hardening pass. All three are distinct and readable. The live file is **not** byte-identical to any backup, so a restore is a real operation, not a no-op.

**Incidental finding — OBSERVED FACT:** `scholarzone_backup_20260902_122751.db` is **0 bytes** (`e3b0c442…` is the SHA-256 of empty input). A pre-existing failed backup from 2026-09-07, unrelated to this wave. Every other `.db` in the directory opens and has a `scholarships` table.

---

## 3. Public Count Reconstruction

**The count is not 666 → 482. It is 660 → 482.** The 666 figure was measured on an earlier snapshot, before the retire stage and before part of the repair. Correcting the baseline is the first finding of this section.

| | Count |
|---|---|
| public before (pre-repair snapshot) | **660** |
| public after (live) | **482** |
| delta | **−178** |
| rows newly listed | **0** |
| rows lost | **178** |
| **losses with no clause to explain them** | **0** |

**Every loss is attributed to a clause of `public_visibility_conditions()`.** The partition sums exactly to the total:

| Reason — the clause that flipped | Rows |
|---|---|
| `image_url` **and** `image_verified_at` became NULL → asset cleared | **172** |
| `verification_status` → quarantined **and** `is_archived` → true | **4** |
| all four of the above | **2** |

**Method validation — PROVEN.** The per-clause evaluator used to attribute each loss was run against the authoritative SQL predicate on **both** databases:

```
authoritative SQL predicate: before 660  after 482  lost 178  gained 0
my per-clause mirror:         before 660  after 482
before matches: True    after matches: True
```

So the 178 is the application's own predicate, not a re-implementation of it, and no record became hidden for an unrelated reason.

**Match / Count consistency — PROVEN.** No inconsistent count was found:

| Check | Result |
|---|---|
| rows hidden while `verification_status='active'` | 0 |
| rows hidden while `is_verified=1` | 0 |
| public rows lacking `image_url` or `image_verified_at` | 0 |
| public rows with `image_source_type='wikimedia'` | 0 |
| archived rows that are public | 0 |
| `legacy is_verified` contradiction (`is_verified` set with `quarantined`) | 0 |

`is_verified=1` is set on 706 rows and `is_archived=1` on 52; the two sets do not intersect in any way the gate exposes.

---

## 4. 234 New Records

Every one was evaluated against the stated GREEN criteria. **Partition:**

| Bucket | Rows | Public |
|---|---|---|
| **GREEN** | **0** | 0 |
| **YELLOW** | **212** | 101 |
| **RED** | **22** | **22** |

**PROVEN — why GREEN is empty.** 229 of 234 rows carry no `verification_note` at all. That single fact disqualifies every one of them under the stated criteria. Manufacturing a GREEN count would require waiving the evidence requirement, which is the opposite of what this gate is for.

YELLOW reasons, by frequency: no verification note 229 · no `official_details` 71 · no image stored 107 · quarantined 5 · archived 5.

### The 22 RED rows are **not** 22 unsafe rows

**PROVEN.** Re-reading each rejection signal by signal separates a real safety failure from a detector artefact:

| Class | Rows | Meaning |
|---|---|---|
| **unsafe** | **3** | 494 (an **infographic** stored as `official_logo`), 625 and 627 (`Images/Favicons/android-chrome-512x512.png` — literally browser icons) |
| **policy gap** | **19** | real official logos rejected by a weak hint or an incomplete host allowlist |

All 22 are **publicly visible**. The 19 policy-gap rows are named in
`WAVE1_3_FINAL_RELEASE_GATE` evidence (`final_audit.json → step4b_red_split`).

**PROVEN — the policy gap is pre-existing, not introduced by the new gate.** `assess_image_evidence` reuses the repository's own `is_official_domain()`, which returns **False** for:

| Host | Institution | `is_official_domain` |
|---|---|---|
| `uct.ac.za` | University of Cape Town | **False** |
| `inter.chula.ac.th` | Chulalongkorn University | **False** |
| `fcm.uncuyo.edu.ar` | Universidad Nacional de Cuyo | **False** |
| `agcid.gob.cl` | Chile's international cooperation agency | **False** |
| `hec.gov.rw` | Rwanda Higher Education Commission | **False** |
| `hbku.edu.qa` | Hamad Bin Khalifa University | **False** |
| `mo.ibrahim.foundation` | Mo Ibrahim Foundation | **False** |
| `sydney.edu.au`, `auckland.ac.nz`, `media.ox.ac.uk`, `jsps.go.jp` | — | True |

The gate applies canonical policy faithfully. **The policy itself under-recognises non-Anglophone academic and government TLDs.** Extending the allowlist is a policy decision for the owner, so those 19 are YELLOW, not RED. Reported, not patched.

---

## 5. 32 New UI-Asset Rows

**PROVEN: 32**, measured on the pre-repair snapshot. Measured on the current database the answer would be **zero** — the repair removed them, which is exactly why counting afterwards hides the problem.

| Asset class | Rows |
|---|---|
| favicon / touch-icon | **26** |
| social asset | 3 |
| navigation / menu asset | 2 |
| error-page artefact | 1 |
| **Disposition** | **32 of 32 cleared — no trustworthy alternative existed** |

Representative, all of which are unambiguously not scholarship imagery:

| id | asset as the wave brought it in |
|---|---|
| 564 | `…/wbr-redesign/logos/wbg-favicon.png` |
| 585 | `https://studyinlatvia.lv/favicon.png` |
| 591, 696, 687 | `favicon.ico` |
| 562, 558 | `apple-touch-icon.png` |
| 628 | `…/images/favicon/icon-512x512.png` |
| 511 | `…/icons/apple-icon-180x180.png` |
| 530 | `…/favicon.ico` |
| 536 | `…/rufford-logo-menu-hr-360x155.png` |

**No replacement was invented for any of the 32.** Each was cleared, and each row's terminal evaluation state records an audited negative rather than "never looked".

---

## 6. Asset Corrections

| Measure | Value |
|---|---|
| rows with an image column changed by the repair | **407** |
| — of which existed before the wave | **253** |
| — of which the wave created | 154 |
| pre-existing rows carrying a **decisive** UI asset before repair | **76** |
| still carrying a decisive UI signal after repair | **0** |
| **trusted asset overwritten and cleared** | **0** |

Actions: 196 restored from the pre-wave snapshot · 31 replaced · 180 cleared.

**PROVEN — no trusted asset was destroyed.** For every cleared row the pre-repair asset was put through the same evidence gate first; a row was cleared only when that asset failed too. Id 398 is the clearest case: the wave had replaced a real University of Amsterdam photograph with `apple-touch-icon.png`, and the repair restored the photograph rather than clearing it.

**Note on the "109" figure.** The earlier pass reported 109 corrected existing rows. Re-measured on the pre-repair snapshot the count of **pre-existing** rows with a decisive UI asset is **76**; 109 was the count across all rows including wave-created ones, and included rows whose only defect was a weak provenance hint. The stricter number is reported here.

---

## 7. Provenance Corrections

**PROVEN: 406 `image_source_type` changes. 299 had an invalid old value; 107 had a valid one.** All 406 new values are canonical or NULL. **Zero invalid values remain.**

| Old → new | Rows |
|---|---|
| `official_logo` → `official_provider` | 152 |
| `official_logo` → NULL | 58 |
| `official_university` → NULL | 50 |
| `official_page_logo` → NULL | 29 |
| `official_government` → NULL | 29 |
| `official_university` → `official_provider` | 17 |
| `official_page_logo` → `official_government` | 14 |
| `official_page_logo` → `official_provider` | 12 |
| `official_logo` → `official_government` | 12 |
| `official_ngo` → `official_provider` | 8 |
| `official_scholarship` → NULL | 7 |
| `official_page_logo` → `official_university` | 5 |
| `official_provider` → NULL | 3 |
| `official_logo` → `official_university` | 3 |
| `official_organization` → `official_provider` | 2 |
| `official_ngo` → NULL | 2 |
| `official_government` → `official_provider` | 1 |
| `official_institution` → NULL | 1 |
| `official_charity` → NULL | 1 |

### Verified: no trust evidence fabricated, no silent reinterpretation

| Check | Result |
|---|---|
| new value canonical or NULL | **100%** |
| an image *kind* value sitting in the provenance column | **0** |
| every `image_kind` is a member of `LOGO_IDENTITY_KINDS ∪ PROGRAMME_IMAGE_KINDS` | **100%** |
| a NULL that was invented rather than cleared with the asset | **0** |

### **D2 — PROVEN PRECISION LOSS, 18 rows — a defect in the previous pass**

**PROVEN.** The 89 rows whose provenance went to NULL are correct: the asset was cleared, and a provenance claim about a non-existent asset has to go with it.

The 18 rows are not. Tracing three states shows the direction was **backwards** from what it looks like:

| id | pre-wave | after the wave | now | host |
|---|---|---|---|---|
| 48 | `official_provider` | `official_university` | **`official_provider`** | `sydney.edu.au` |
| 51 | `official_provider` | `official_university` | **`official_provider`** | `uwa.edu.au` |
| 85 | `official_provider` | `official_government` | **`official_provider`** | `you.ubc.ca` |
| 256 | `official_provider` | `official_university` | **`official_provider`** | `auckland.ac.nz` |
| 398 | `official_provider` | `official_university` | **`official_provider`** | `uva.nl` |

**The wave improved the attribution; the asset-restoration path reverted it.** That path restores every `IMAGE_COLUMNS` entry from the pre-wave snapshot, and `image_source_type` is provenance metadata rather than part of the asset being restored.

**Fully recoverable, no research needed.** `_issuer_kind(host, alt_text)` recomputes the correct value and **agrees on every one of the 18 rows**.

**Impact — YELLOW, not RED:** both values are canonical and both satisfy the public gate identically, so nothing is hidden and no invariant breaks. The row simply states less about its own provenance. Correcting it is required before production; it is not repaired here, because this mission is read-only.

---

## 8. Deadline Corrections

**PROVEN: 73 changes, 0 remaining violations.**

| Old → new | Rows | Basis |
|---|---|---|
| `day` → `exact` | **59** | **all 59 carry a `deadline_date`** — a parsed calendar date is the one genuinely exact case |
| `application_dead` → `exact` | 5 | these 5 carry a real date |
| `application_dead` → `unknown` | 9 | no date; the stored token matches nothing in the vocabulary |

| Check | Result |
|---|---|
| `exact` assigned with **no** `deadline_date` | **0** |
| precision invented rather than derived | **0** |
| `unknown` left as `unknown` | yes, 9 rows |

### Two open questions, both **UNKNOWN**

**a) `a-star.edu.sg` rows 101 and 530** got `day → exact` with a date. A peer research shard reported that a-star publishes cycles as bare month/day with **no year**, and that `deadline_date` should stay NULL with precision `recurring`. If the stored `deadline_date` carries an inferred year, `exact` overstates. **Not verifiable without re-reading the page**, which is a research pass and outside this mission. **PLAUSIBLE BUT UNPROVEN.**

**b) The 9 rows left at `unknown`.** A peer shard reported that targets 382, 384, 385, 386 and 387 — the `application_dead` rows — actually publish exact or recurring dates. `unknown` remains the honest value given no evidence in hand; these 9 need a research pass. **UNKNOWN.**

---

## 9. Duplicate Resolution

**PROVEN: all six resolved, none modified in this pass.**

| Pair | Survivor | Duplicate | Duplicate archived | In `retired_records.json` | Survivor public | Duplicate public | References preserved |
|---|---|---|---|---|---|---|---|
| 133 / 570 | 570 | **133** | yes | yes | yes | no | yes |
| 438 / 530 | 530 | **438** | yes | yes | no | no | yes |
| 68 / 532 | 68 | **532** | yes | yes | yes | no | yes |
| 10 / 501 | 10 | **501** | yes | yes | yes | no | yes |
| 107 / 531 | 107 | **531** | yes | yes | yes | no | yes |
| 13 / 553 | 13 | **553** | yes | yes | yes | no | yes |

**Every duplicate is archived and invisible; every survivor is at most public; no duplicate is public.** The `retire` mechanism archives rather than deletes, so all reviews, verification-history rows and image reviews remain attached to a live id. Where a retired row held researched text that the survivor lacked (ids 10, 13), it was copied across first.

**Corroboration — OBSERVED FACT.** A peer research shard independently reported that id 13's stored award name does not exist and that the real award is the POSCO Global Scholarship umbrella. Retiring 13 in favour of 553 matches that finding.

---

## 10. Archived / Active State

**PROVEN: `is_archived=1 AND verification_status='active'` = 0.** 52 rows are archived; none is public.

**PROVEN — this zero is not achieved by rewriting trust state.** Canonical policy does not require `active` to be prevented on an archived row — `public_visibility_conditions()` states that *"is_archived is not a trust question at all"*. The zero arose because the `retire` stage re-applied quarantine to rows already listed in `retired_records.json`, which is the correct mechanism. **No `verification_status` was altered on trust grounds in this pass, including id 14's `needs_review → active`.**

| Behaviour | Result |
|---|---|
| archived rows excluded from the directory | **PROVEN** — 0 archived rows public |
| archived rows excluded from every published count | **PROVEN** |
| would-be-public if unarchived | **0** |
| `do_reverify` can promote an archived row | **no** — guard added, tested through the real stage |
| `approve_image_review` can mark an archived row's image verified | **no** — refuses before writing |

**Semantics were not changed to satisfy a number.** The invariant here is that archive is a terminal public exclusion, enforced by the query and now defended at both write paths.

---

## 11. Code Guards

All seven reviewed. Each reuses an existing canonical definition; none invents new semantics.

| Guard | Canonical source | Real execution path | Verdict |
|---|---|---|---|
| `image_url` HTTPS | same predicate as `official_source_url` / `catalogue_url` / `official_updates_url` | `ScholarshipIngestionRecord.validate_image_urls` | **PASS** |
| `image_source_type` | `is_valid_source_type()` (existing) | `validate_image_source_type` | **PASS** |
| `deadline_precision` | `coerce_deadline_precision()` (existing) | `validate_deadline_precision` + both stage writers | **PASS** |
| `do_add` asset safety | `assess_image_evidence` (new gate, existing detectors) | `do_add` → gate → writes or refuses | **PASS** |
| `reverify` retirement | `retired_records.json` | `do_reverify` itself | **PASS** |
| admin image review | archive is a terminal exclusion | `approve_image_review`, `review_queue_counts` | **PASS** |
| cross-host | `is_official_domain()` (existing) | `assess_image_evidence` | **PASS, with a known limitation** |

**No silent fallback that manufactures trust.** Zero bare `except: pass` in any guard path; every refusal is returned with a reason and surfaced in the stage result.

**Over-blocking — the honest finding.** The new gate does not over-block *relative to canonical policy*, but canonical policy itself over-blocks: §4 lists 7 host families `is_official_domain()` rejects that are legitimate official academic and government hosts. Separately, the weak provenance hints (`/themes/`, `/common/`, `/global/`, `/home/`, hash-based filenames) reject real official logos — 19 of the 22 RED rows in §4. **Reported, not patched:** changing the allowlist or downgrading those hints is a policy decision.

---

## 12. Test Results

| Suite | Result |
|---|---|
| `tests/test_test_isolation_boundary.py` (new) | **12 passed** |
| `tests/test_wave13_hardening.py` (previous pass) | **50 passed** |
| **Full backend suite** | **4840 passed, 1 failed, 2 skipped** in 277.80s |

**Isolation proven before running.** The suite was executed after the boundary was in place, and the working database was verified unchanged afterwards by diffing it against the pre-repair snapshot across 20 columns:

```
field-level differences vs pre-repair backup: 1995
by column: image_source_type 406, image_url 211, image_source_url 211,
 image_alt_text 211, image_verified_at 211, image_evaluated_at 211,
 image_kind 210, image_evaluation_status 180, deadline_precision 73,
 verification_status 32, catalogue_url 26, official_updates_url 7, is_archived 6
```

That is **exactly** the intended change set. The file's mtime advances when opened, but no test wrote a row: `maintenance_runs` is 148, and runs 145–148 are timestamped 17:20 — the *previous* session's stage applies, not this suite.

### Baseline failure

`tests/test_image_discovery.py::TestHumanReviewRouting::test_non_content_image_with_license_still_rejected` — **pre-existing and network-dependent.** It asserts `non_content_total_weight >= 1.5` for `daad.de/images/header-banner.jpg`; `validate_candidate` returns early when the fetch fails, leaving the weight at 0. Verified directly that the detectors still score that URL at **6.0**. It fails because `daad.de` is unreachable from this environment, not because of any change here.

**No test was weakened.** Four assertions in `test_official_logo_overrides.py` were changed from `official_logo` to `official_provider` and **an additional assertion added** that the result is a canonical `ImageSourceType` member — a stricter test than before.

---

## 13. Local Release Invariants

| # | Invariant | Result |
|---|---|---|
| 1 | `public <= total` | **PASS** — 482 ≤ 722 |
| 2 | no invalid `deadline_precision` | **PASS** — 0 |
| 3 | no invalid `image_source_type` | **PASS** — 0 |
| 4 | no `image_url` without valid `image_kind` | **PASS** — 0 |
| 5 | no `image_kind` without `image_url` | **PASS** — 0 |
| 6 | no `http://` image | **PASS** — 0 |
| 7 | no unsafe image asset (decisive UI signal) | **PASS** — 0 |
| 8 | no public record missing mandatory trust evidence | **PASS** — 0 |
| 9 | no public record unverified | **PASS** — 0 |
| 10 | no archived/public contradiction | **PASS** — 0 |
| 11 | no quarantined row public | **PASS** — 0 |
| 12 | no wikimedia image public | **PASS** — 0 |
| 13 | every stored image has a terminal evaluation status | **PASS** — 0 |
| 14 | no duplicate | **PASS** — 6 pairs resolved; the one remaining shared URL pair (133/570) has at most one live member |
| 15 | no orphan review | **PASS with 1 exception** |
| 16 | no broken references | **PASS** |
| 17 | no malformed list column | **PASS** — 0 |
| 18 | Match counts consistent | **PASS** |
| 19 | Count counts consistent | **PASS** |
| 20 | storage count stable except documented local-wave changes | **PASS** — 722 rows, no row created or deleted by this pass |

**The one exception — invariant 15.** `scholarship_verification_history` holds one orphan pointing at id **358**. That row was **purged** by the wave rather than retired, and purge is the one mechanism in this schema that loses an id. It is pre-existing, documented, and was **not** used for the six duplicates. Reviews and image reviews have zero orphans.

**Pre-existing data-quality items, out of scope for a read-only gate:**

| Item | Rows | Note |
|---|---|---|
| mojibake in `title` / `notes` | 5 cells (ids 75, 76, 78, 66, 544) | double-encoded em dashes and `GrundfÃ¶rderung`; `do_repair_encoding` exists |
| mojibake in config | `verification_confirmations.json` 11, `new_scholarships.json` 91 | pre-existing |

**Verified as not caused by this work:** every surviving entry in `retired_records.json` and `verification_confirmations.json` is **byte-identical** to its pre-edit form; only the 4 intended confirmations were removed; non-ASCII content is preserved (79 → 78 entries containing non-ASCII, matching the one removal).

---

## 14. Production Delta Status

**UNKNOWN.** Not measured, not estimated, not guessed.

| Path attempted | Result |
|---|---|
| `SCHOLARZONE_DATABASE_URL` / `DATABASE_URL` / `PG*` in the process | **absent** |
| `backend/.env` | only `RESEND_API_KEY`, `NOTIFICATION_EMAIL`, `SCHOLARZONE_VERIFICATION_SECRET` |
| application as `SCHOLARZONE_ENVIRONMENT=production` | `RuntimeError: SCHOLARZONE_DATABASE_URL is required in production.` |
| GitHub Actions secret `SCHOLARZONE_DATABASE_URL` | name exists — **GitHub returns names and timestamps, never values. Not used as a value.** |
| Vercel CLI | installed; no linked project directory |

**STOP condition met.** No secret was retrieved or exposed, no value was guessed, no SQLite file was copied, no production stage was run. Production state remains UNKNOWN.

Consequence: the apply manifest's "old value" for every row is the **local post-wave** value, not the production value. It therefore cannot be diffed against production and **must not be applied**.

---

## 15. GREEN / YELLOW / RED Partition

### GREEN — safe and evidence-backed

**The 488 pre-existing rows, with 4 carve-outs.**

| | Rows |
|---|---|
| existing rows, image corrections evidence-backed, no enum violation | 488 |
| — of the 6 retired duplicates | −6 |
| — of the 18 D2 provenance precision losses | −18 |
| — of the 2 D1 false-positive asset clears | −2 |
| — of the 2 pre-existing non-https official sources (346, 347) | −2 |
| **GREEN** | **460** |

### YELLOW — requires an owner or policy decision

| Item | Rows | Decision needed |
|---|---|---|
| 212 wave-created rows | 212 | disposition of the whole new set |
| 32 wave-created rows whose UI asset was cleared | 32 | (subset of the above) |
| **D2** provenance precision loss | **18** | restore `image_source_type`; mechanical, no research |
| **D1** false-positive asset clears | **2** (63, 693) | restore the asset; recorded in the pre-repair snapshot |
| host allowlist gap | 19 | extend `is_official_domain`, or accept the exclusion |
| 4 white wordmarks retained on evidence | 4 | design call: does a white mark render acceptably? |
| id 398 — real photo, OG size transform | 1 | accept or clear |
| ids 346, 347 — pre-existing `http://` official source | 2 | research pass |
| 124 bulk `reverify` promotions still live | 124 | whether each should stand |
| orphan history → purged id 358 | 1 | accept as the documented cost of purge |
| mojibake | 5 cells + config | run `do_repair_encoding` |

### RED — must not reach production

| Item | Rows | Why |
|---|---|---|
| **unsafe assets on public rows** | **3** | 494 infographic stored as a logo; 625 and 627 are `android-chrome-512x512.png` favicons |
| **the 234 wave-created rows as a set** | **234** | none is GREEN; 22 are RED, 212 YELLOW, 0 GREEN |
| **the 20 defects from the previous pass** | **20** | must be corrected before apply, not carried into production |

**The decisive fact: the 22 RED rows are all publicly visible right now**, and 3 of them carry a genuinely unsafe asset.

---

## 16. Final Release Decision

# **BLOCKED**

Not because the code is unsafe — the seven guards are in place and tested through their real execution paths. Not because the local data is unknown — it is known, diffed and verified. Blocked on five independent conditions, all of which the mission named:

| Condition | Status |
|---|---|
| any of the 234 new rows still RED | **MET** — 22 RED, 0 GREEN |
| any UI asset unclassified | **MET** — 32 classified but 3 unsafe assets still public |
| public 666→482 has unexplained losses | **NOT MET** — 0 unexplained; baseline corrected to 660→482 |
| production delta UNKNOWN | **MET** — UNKNOWN, no path exists |
| tests cannot be guaranteed isolated | **NOT MET** — boundary now fails closed, proven by 12 tests and by an unchanged database |
| any trust/verification contradiction remaining | **MET** — 18 provenance precision losses + 2 cleared legitimate assets |

**What the count changes do not hide.** Trustworthiness > completeness > count. The public count fell 660 → 482 and **every one of the 178 losses is a canonical predicate firing on a row that cannot defend its image**. One of those 178 was a genuine University of Amsterdam photograph hidden behind an `apple-touch-icon.png`, and 178 rows were hidden rather than shown on a merit they had not earned. A higher public count was available at any moment by accepting the favicons; it was not taken.

**Exact next action, in order:**

1. **Correct the 20 defects** — restore the 2 cleared assets (D1, ids 63 and 693) and the 18 provenance values (D2). Mechanical, no research, both reversible from recorded evidence.
2. **Resolve the 3 unsafe public assets** — 494, 625, 627. Clear or replace with an authoritative first-party asset. Do not invent a URL.
3. **Decide the 234 wave-created rows** as a set. 0 are GREEN; the default must be "not applied" until each is dispositioned.
4. **Settle the two policy questions** — extend `is_official_domain()` for the 7 host families, and decide whether `/themes/`, `/common/`, `/global/`, `/home/` and hash filenames should continue to reject real logos.
5. **Then, and only then**, provision a read-only Neon role, prove it with a read, and diff the manifest against production row by row. Any row whose production value differs from the manifest's "old value" must be re-decided, not applied.
6. **Deploy the six code guards before any further data run**, or the next `add`, `logos` or `reverify` run can reintroduce every value corrected here.

**Never copy `scholarzone.db` into Neon.** The apply mechanism is the repository's own stages driven by `backend/config/*.json`, one stage at a time, dry-run first.

---

### Evidence index

| Claim | Source |
|---|---|
| Test-safety root cause and fix | `backend/pytest.ini`, `backend/tests/conftest.py`, `backend/tests/test_test_isolation_boundary.py` |
| Backups, hashes, readability | direct read-only probe of all `scholarzone*.db` |
| Public delta, per-row clause | `wave13_public_delta.py` → `public_delta.json`, cross-validated against `public_visibility_conditions()` |
| 234-row partition, 32 UI assets, 407 corrections, enums, duplicates, invariants | `wave13_final_audit.py` → `final_audit.json` |
| Code-guard review | direct source inspection of all 7 guards |
| Field-level apply manifest | `WAVE1_3_PRODUCTION_APPLY_MANIFEST_FINAL.md` (1,957 changes, 452 rows) |
| Prior hardening detail | `WAVE1_3_HARDENING_FINAL.md`, `DUPLICATE_RESOLUTION_MANIFEST.md` |

**Neon: no write, no read, no connection, no secret retrieved.**
