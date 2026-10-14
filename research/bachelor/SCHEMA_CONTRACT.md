# ScholarZone — Bachelor's Scholarship Research Contract (v2, CORRECT)

> **v1 of this file was wrong.** It described a flat, invented record shape. The real
> pipeline is Python/FastAPI and consumes three specific files. This v2 targets the
> actual schemas. If you read v1 notes anywhere, ignore them.

---

## What you produce

ONE JSON file per scholarship:

```
research/bachelor/<NN>-<slug>.json
```

Shape:

```json
{
  "new_scholarship": { ... },
  "programme_detail_official": { ... },
  "programme_detail_applicant_utility": { ... },
  "programme_detail_verification": { ... },
  "logo_override": { ... },
  "research_notes": { ... }
}
```

The coordinator merges these into:
1. `backend/config/new_scholarships.json` — the **insertion** record (new scholarships)
2. `backend/config/programme_details.json` — the **enrichment** blocks (keyed by the numeric
   id the database assigns *after* insertion, which is why you never supply an id)
3. `backend/config/official_logo_overrides.json` — the **logo** entry (keyed by official host)

---

# PART A — `new_scholarship` (insertion record)

Model this on the existing records in `backend/config/new_scholarships.json`
(read it first). Fields, with rules:

| field | type | rule |
|---|---|---|
| `name` | string | Official full award name. Required. |
| `country` | string | Host country common English name. Required. |
| `region` | string | `"Europe"`, `"United States"`, `"Canada"`, `"Australia"`, `"Singapore"`, `"Malaysia"`. Required. |
| `degree_levels` | string | Use `"Bachelor's"` when the award funds a bachelor's degree. Required. |
| `funding_type` | string | e.g. `"Fully Funded"`, `"Partially Funded"`, `"Tuition Fee Waiver"`, `"Stipend"`. Required. |
| `program_type` | string | e.g. `"Government scholarship"`, `"University merit scholarship"`, `"Tuition-fee remission"`. |
| `official_source` | string | The awarding body's name. |
| `official_source_url` | string | **Deepest verified official page for THIS award**, https, not a homepage. Required. |
| `catalogue_url` | string\|null | Official finder/search/catalogue URL, else null. |
| `official_updates_url` | string\|null | Official page where next-cycle updates appear, else null. |
| `duration` | string | e.g. `"3 years"`, `"4 years"`. |
| `deadline` | string | Human deadline sentence, quoting the official wording. |
| `deadline_date` | string\|null | ISO `YYYY-MM-DD` **only if the official page states an exact calendar date**. Else null. Never guess. |
| `deadline_precision` | string\|null | `"day"` \| `"day_and_time"` \| `"month"` \| `"varies"` \| `"ongoing"`. |
| `application_period` | string | When applications open and close. |
| `application_method` | string\|array | How to apply. Say explicitly whether it is automatic on admission or a separate application. |
| `status` | string | Existing file uses lowercase: `"open"`, `"upcoming"`, `"closed"`. Match that. |
| `is_verified` | boolean | `true` only if you verified from the awarding body itself. |
| `last_verified_date` | string | `"2026-10-03"`. |
| `description` | string | 2–4 factual sentences. No marketing language. |
| `best_fit` | string | Who this suits. |
| `funding_amount` | number\|null | One figure only. Null if not published. |
| `funding_currency` | string\|null | ISO code, uppercase. Null if no amount. |
| `funding_period` | string\|null | e.g. `"per month"`, `"per year"`, `"one-time"`. Null if no amount. |
| `eligibility_summary` | string | Dense prose summary. |
| `eligibility` | array | Discrete conditions. |
| `coverage` | array | What the money actually pays for. |
| `benefits` | array | Itemised benefit lines. |
| `requirements` | array | Application requirements. |
| `required_documents` | array | Document checklist. |
| `english_requirement` | string\|null | Real test + real score. Null if not published. |
| `selection_notes` | string | How selection works, incl. any published weighting. |
| `image_url` | string\|null | Official-domain logo URL. See PART D. Null if unverified. |
| `image_source_url` | string\|null | Official page the logo was taken from. |
| `image_source_type` | string\|null | `"official_logo"` when it is the awarding body's own mark. |
| `image_alt_text` | string\|null | e.g. `"Duke University"`. |
| `image_verified_at` | string\|null | `"2026-10-03"`. |
| `notes` | string | Assumptions, gaps, anything unverified. |

---

# PART B — `programme_detail_official` (enrichment block)

This is the **only** block the maintenance stage maps onto DB columns, and it must mirror
the shape used by existing records in `backend/config/programme_details.json` (read it first).

**Hard separation rule** (verbatim from the repo's `_rules`):
> Official facts live in official_details; guidance derived from them lives in
> applicant_utility. They are stored apart and must never be merged.

So `programme_detail_official` = official facts only. No advice, no checklists.

### Banned in this block
The maintenance test fails a record if any of these appear in `official`:
```
application_readiness_checklist, common_rejection_risks, estimated_uncovered_costs,
document_audit, alerts, submission_workflow
```
Also banned as **placeholder strings** in `funding_currency`, `funding_period`,
`deadline_central`, `application_route`, `study_mode`:
```
"", "n/a", "na", "-", "none", "tbd", "unknown", "null"
```
Use `null` instead of any of those.

### Required keys (mirror the Eiffel/Canada-graduate exemplar)
```
official_source_urls            array of https strings, the pages you actually read
application_link                string|null
official_updates_url            string|null
catalogue_url                   string|null
application_cycle               string  e.g. "2027 entry; applications open Oct 2026"
deadline_central                string|null   ISO datetime "YYYY-MM-DDTHH:MM" or date
deadline_central_display        string        human deadline with the official wording
deadline_central_timezone       string|null   e.g. "Europe/Paris", "America/New_York"
deadline_institutional          string|null   any EARLIER university/institution date
deadline_note                   string        explains the deadline situation
status                          string        "OPEN" | "UPCOMING" | "CLOSED" | "ONGOING" | "DISCONTINUED"
status_note                     string
funding_amount                  number|null
funding_currency                string|null   uppercase ISO
funding_period                  string|null   e.g. "per month"
funding_duration                string
tuition_coverage                boolean
tuition_coverage_note           string
living_cost_coverage            boolean|null
travel_coverage                 boolean|null
fully_funded                    boolean
funding_label                   string        one-line money summary
benefits                        array of strings
eligibility                     array of strings
citizenship_residency           string
international_eligibility       string
degree_levels                   array of strings
study_mode                      string|null
research_requirement            string|null
subject_or_agency_requirement   string|null
application_method              string
application_route               string
requirements                    array of strings
documents                       array of strings
english_requirement             string|null
english_requirement_note        string
selection_criteria              array of strings
selection_weighting             string|null
duration                        string
award_holder_conditions         array of strings
supplements_or_initiatives      array of strings
official_contacts               object e.g. {"general": "...", "email": "..."}
description                     string
program_type                    string
region                          string
coverage                        string
last_verified_date              "2026-10-03"
```

### Funding invariants (repo rules — violations are hard failures)
> `fully_funded` is applied only when `tuition_coverage` is true, so a stipend can never be
> recorded as though it were a tuition waiver.

- `fully_funded: true` **requires** `tuition_coverage: true`. If there is any bond, service
  obligation, uncovered component, or the award is tuition-only, `fully_funded` must be
  `false` and you must explain in `tuition_coverage_note`.
- A living stipend is **not** a tuition waiver. `tuition_coverage: false` + `living_cost_coverage: true`
  is a common, correct combination.
- Put the bond in `award_holder_conditions` AND reflect it in `funding_label`.

---

# PART C — `programme_detail_applicant_utility` and `programme_detail_verification`

## C1 — `programme_detail_applicant_utility` (6 keys, all arrays)
```json
{
  "application_readiness_checklist": ["..."],
  "common_rejection_risks":        ["..."],
  "estimated_uncovered_costs":     ["..."],
  "document_audit":                ["..."],
  "alerts":                        [{"trigger": "short label", "message": "..."}],
  "submission_workflow":           ["..."]
}
```
Guidance derived from the official facts. Never restate an official fact here as if it were
official — this block is where you tell the applicant what to *do*.

## C2 — `programme_detail_verification`
```json
{
  "cycle_verified": "2027 entry cycle, verified 2026-10-03",
  "verification_confidence": 0.9,
  "official_fields_confirmed": ["funding_amount", "tuition_coverage", "deadline_central", "..."],
  "institution_check_required": ["..."],
  "unverified_or_removed_claims": ["..."],
  "source_citations": ["https://...", "https://..."],
  "researched_by": "bachelor_XX"
}
```

- `source_citations` is **mandatory and non-empty**. Without it the stage skips the record:
  > An amount with nothing to check it against is worse than no amount, because it looks researched.
- `verification_confidence`: number 0–1. Be honest. `0.9+` only if every key above is filled
  from the awarding body. Use `0.6–0.8` if any official page was unreachable.
- `researched_by` = `"bachelor_01"` … `"bachelor_60"` (your assigned number). It is a free-text
  provenance stamp; nothing parses it, but keep the convention.
- List every field you could NOT confirm in `unverified_or_removed_claims`.

---

# PART D — `logo_override` (the official-logo requirement)

Target file is `backend/config/official_logo_overrides.json`, **keyed by the awarding body's
own domain**. See its `_rules` — these are verbatim from the repo:

1. Keys are the official source host, not the record title, so an official rename does not
   silently orphan an entry.
2. Add an entry only when the logo is known to be the institution's own and the URL is stable.
3. `official_host` must be `true` only when the bytes are served by the institution itself.
   A third-party host (for example Wikimedia) must be `false`.
4. An entry is a candidate, not an approval: every override still goes through the ordinary
   image validator.
5. Every URL below was probed live and returned HTTP 200 with an image content type before
   being added.
6. **White-on-transparent wordmarks are deliberately excluded.** A white logo is invisible on
   a light card, so shipping one would replace a missing image with a broken one; use a dark
   variant or leave the record without a logo.
7. A host whose logo URL returns HTML rather than image bytes is excluded. That is a WAF
   interstitial or an error page, not a logo.

Shape:
```json
{
  "url": "https://official-domain/path/to/logo.svg",
  "page_url": "https://official-domain/",
  "official_host": true,
  "alt_text": "Awarding body name",
  "validation_result": "verified",
  "validation_detail": "svg 11931+B",
  "image_kind": "official_logo",
  "image_format": "svg",
  "verified_at": "2026-10-03T00:00:00+00:00",
  "host_evidence": "same_registrable_domain"
}
```
`host_evidence` observed values: `same_registrable_domain` (logo served by the body's own
domain), `official_social_asset`, `official_brand_page`.

### Logo hunt order
1. A logo file on the awarding body's own domain — check the site header/footer markup,
   `/favicon.ico`, `/apple-touch-icon.png`, `og:image`, or schema.org `logo`.
2. An official brand/press/media page on that same domain.
3. An official verified social profile asset.

### Hard bans
- **Never** a third-party aggregator, blog, scholarship-listing site, Wikipedia/Wikimedia,
  news article, stock site, CDN mirror, `imgur`/`pinterest`/`screencapture`.
- **Never** a logo belonging to a different body than the one awarding the scholarship.
  A university logo on a scholarship awarded by a ministry is a provenance error.
- **Never** a white-on-transparent wordmark (rule 6).
- **Never** an unprobed URL (rule 5) — confirm it returns image bytes.
- **Never** invent a plausible-looking URL.

**`null` is an acceptable, honest outcome. A fabricated or unverified logo URL is a FAILURE.**
If you set `"logo_override": null`, say in `research_notes.logo` exactly what you tried and
why it failed.

---

# PART E — `research_notes`

```json
{
  "logo": "how you found/verified the logo, or what you tried and why it is null",
  "unverified": ["anything you could not confirm", "..."],
  "substitution": null,
  "official_pages_read": ["https://...", "..."],
  "degree_level_confirmed": "how you confirmed this funds a bachelor's degree"
}
```

---

# PART F — SURVIVING AN IDLE TIMEOUT (MANDATORY WORK SEQUENCE)

Several research agents on this batch were killed mid-task by an upstream idle
timeout during long web-fetch chains, losing all their work. Four of ten in one wave.
**A stalled fetch must never cost you the whole record.** Follow this order exactly:

1. **Read** `SCHEMA_CONTRACT.md` and `RESEARCH_PROTOCOL.md` in full, then your target row.
2. **Immediately write a skeleton** to your output file: all 6 top-level keys present,
   `new_scholarship.name` set to the target award name, `research_notes.skeleton: true`.
   Everything else may be `null`/`[]`. This alone is a valid, salvageable file.
3. **Re-write the file after every 2–3 successful fetches**, filling in what you have
   confirmed so far. A partial file with real citations beats a complete file that
   never lands.
4. Only then complete the remaining fields.

If you are running low on time or a fetch is hanging, **stop fetching and write what
you have.** A record with `verification_confidence: 0.6` and honest `unverified_or_removed_claims`
is a good outcome. A perfect record that never gets written is worth nothing.

**Never** leave the file as a skeleton if you have real findings — but never keep
fetching past the point where writing would be safer.

---

# PART G — PICKING YOUR TARGET

The assignment table lives in **`research/bachelor/ASSIGNMENTS.md`** (and `ASSIGNMENTS.json`).
It was generated mechanically by `build_assignments.js` against `EXISTING_AWARDS.json`,
which indexes all 526 existing awards. Rows are already filtered for: allowed region,
bachelor's level, and no host/name collision with the live database.

**You are given a slot number. Read only your own row** — `name`, `host`, `region`,
`degree note`. Do not work another row.

- If `logo_host_taken = true` for your row, `official_logo_overrides.json` already has a
  key for that host: **do not add a second entry**. Still set `logo_override` in your file
  (with `official_host: true`) and say so in `research_notes.logo`, but expect it to be
  deduped at merge time.
- If your target turns out to be excluded after all — dead, master's-only, or already in
  the database under a name the filter could not match — substitute a **different row from
  `ASSIGNMENTS.md` that you have not claimed**, and record the substitution in
  `research_notes.substitution` plus your final message.
- If the awarding body publishes no bachelor's-level funding at all, say so plainly in
  `research_notes` and pick another row. **Do not invent a scholarship to fill the slot.**

---

# Absolute accuracy rules

1. **No invented facts.** If the awarding body does not publish an amount, it is `null`.
2. **No invented dates.** No exact calendar date ⇒ `deadline_date: null` +
   `deadline_precision: "varies"` + explain in `deadline_note`.
3. **Don't universalise.** A per-programme threshold must be described as per-programme.
4. **Separate admission from funding.** State explicitly whether the award is automatic on
   admission or requires its own application.
5. **Bonds are not optional information.** Any service obligation goes in
   `award_holder_conditions` and forces `fully_funded: false`.
6. **Cite only what you read.** `source_citations` must be URLs you actually fetched.
7. **Unreachable official page ⇒** `verification_confidence` ≤ 0.7, note it in
   `unverified_or_removed_claims`. Do not fabricate to fill gaps.
8. **Today is 2026-10-03.** A deadline earlier than that means `status: "closed"` /
   `"CLOSED"`, and `status_note` must carry the next-cycle expectation.