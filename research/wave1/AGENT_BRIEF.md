# WAVE 1 BRIEF — live official re-verification of existing ScholarZone records

You are one of 50 parallel research agents. Your shard file lists ~10 scholarship
records that already exist in the ScholarZone database. For **each** record you must
re-verify it against the awarding body's **own live website**, correct every field
that is wrong or missing, and find the awarding body's **official logo**.

Today is **2026-10-04**.

---

## 1. Your assignment

Read your shard file (given in your prompt). It is JSON:

```
{
  "shard": "w1-07",
  "agent_id": "w1_07",
  "today": "2026-10-04",
  "record_count": 10,
  "records": [
    {
      "target_id": 62,                    <-- the database id. NEVER change it.
      "current_title": "...",
      "official_source": "...",
      "current_official_source_url": "...",<-- the DB identity. NEVER change it.
      "current_application_link": "...",
      "official_host": "example.org",
      "country": "...", "degree": "...", "funding": "...", "region": "...",
      "status": "open",
      "deadline_date": null, "deadline_display": "...", "deadline_precision": "varies",
      "verification_status": "needs_review",
      "current_image_url": null, "current_image_kind": null,
      "current_funding_amount": null, "current_funding_currency": null,
      "research_focus": ["NO_IMAGE_AT_ALL", "NO_EXACT_DEADLINE_DATE", ...]
    }
  ]
}
```

Work through the records **in order**. `research_focus` tells you what is weakest, but
verify **everything** — the point of this wave is a deep refresh, not a patch.

---

## 2. Non-negotiable rules

1. **Live official sources only.** The awarding body's own domain, or an official
   government/ministry page for a government award. Never a scholarship aggregator,
   blog, news site, Wikipedia, or a "top scholarships" list. If you cannot reach an
   official page, say so honestly — a record with honest gaps beats an invented one.
2. **Never invent a fact, a date, an amount or a URL.** Unpublished values are real
   JSON `null`. Never the strings `"n/a"`, `"tbd"`, `"unknown"`, `""` or `"null"`.
3. **Never change `target_id`, `current_official_source_url` or `legacy_titles`.**
   - `official_source_url` in your output must be **exactly** the shard's
     `current_official_source_url` (the value it has in the shard), because that URL
     is the record's identity in the database. If the official page has genuinely
     moved or been renamed, keep the stored URL and report the new one in
     `research_notes.url_observed` — a URL change would create a duplicate row.
   - `legacy_titles` must be `[ "<the shard's current_title, verbatim>" ]` so the
     merge can find the existing row even by title.
4. **Never write to any file except your one output file.** Do not edit repo code,
   config, or another agent's output.
5. **Do not delete or archive anything.** Report problems in `research_notes`; a human
   decides on retirement.
6. **Citations are mandatory.** `programme_detail_verification.source_citations` must
   contain at least the URLs you actually opened for that record (2+ when you opened
   2+). A record with zero citations is discarded by the pipeline.
7. **Budget: at most 6 web fetches per record.** If a page is blocked by a WAF or
   times out, move on. Never retry a blocked page more than twice.
8. **Write early, write often.** After every 2 records, rewrite your output file with
   everything confirmed so far. A partial file with real citations is worth far more
   than a perfect file you never write. If you run short on time, stop fetching and
   save what you have.

---

## 3. The logo — mandatory, and it must be the awarding body's own mark

Every record needs the **official logo of the awarding body**, not a photo, not a
campus banner, not a programme hero image.

Search order:
1. A logo file on the awarding body's own domain. Check the page header/footer markup,
   `/favicon.ico`, `/apple-touch-icon.png`, `<meta property="og:image">`, or
   schema.org `logo`. Also try common paths: `/logo.svg`, `/assets/logo.svg`,
   `/sites/default/files/logo.svg`, `/images/logo.png`.
2. An official brand / press / media / "about us" page on that same domain.
3. An official verified social profile asset (only if the bytes are the body's own).

**You must probe the URL before you report it.** Fetch it and confirm it returns
**HTTP 200 with an image content type** (`image/svg+xml`, `image/png`, `image/jpeg`,
`image/x-icon`, `image/webp`). A URL that returns HTML is a WAF interstitial or an
error page — reject it.

**Hard bans — a violation is a failure:**
- Any third-party host (aggregator, blog, Wikipedia/Wikimedia, news, stock site,
  CDN mirror, imgur, pinterest, a screenshot).
- A logo belonging to a body other than the one awarding this scholarship. A
  university logo on a ministry-awarded scholarship is a provenance error.
- A **white-on-transparent** wordmark: invisible on a light card. If the only variant
  is white, look for a dark/coloured variant; if there is none, report `null`.
- An unprobed or guessed URL.

**`null` is a correct, acceptable result.** Say in `research_notes.logo` exactly what
you tried and why it failed.

`logo_override` shape:

```json
{
  "url": "https://official-domain/path/logo.svg",
  "page_url": "https://official-domain/official/page",
  "official_host": true,
  "alt_text": "Awarding body name",
  "validation_result": "verified",
  "validation_detail": "svg 11931+B",
  "image_kind": "official_logo",
  "image_format": "svg",
  "verified_at": "2026-10-04T00:00:00+00:00",
  "host_evidence": "same_registrable_domain",
  "_award": "<award name this logo belongs to>"
}
```

- `host_evidence`: `same_registrable_domain` (normal), or `official_social_asset`.
- `validation_detail`: `"{format} {bytes}B"` plus what you saw, e.g. `"svg 11931+B, dark wordmark"`.
- The key in the merged logo file is the **awarding body's host**, not the title.

---

## 4. Output file

Write **exactly one** file: `research/wave1/out/<your shard>.json` — e.g.
`research/wave1/out/w1-07.json`. Create the `out` directory if needed.

```json
{
  "agent_id": "w1_07",
  "shard": "w1-07",
  "today": "2026-10-04",
  "records": [ { ...one object per assigned record, same order... } ]
}
```

Each record object — exactly these keys:

```json
{
  "target_id": 62,
  "outcome": "refreshed",
  "confirm": true,
  "confirmation_evidence": "One or two sentences naming the official page you read and what it confirmed, with a quoted phrase from the page.",
  "new_scholarship": { ... },
  "programme_detail_official": { ... },
  "programme_detail_applicant_utility": { ... },
  "programme_detail_verification": { ... },
  "logo_override": { ... } | null,
  "research_notes": { ... }
}
```

- `outcome` is one of `refreshed` (verified and corrected), `verified_no_change`,
  `unreachable` (official site could not be read), `discontinued` (the programme is
  gone for good), `duplicate` (this row duplicates a sibling award).
- `confirm` is `true` **only** if you actually read an official page for this record
  and it confirms the record is real, live and correctly attributed. It is what
  promotes the row to verified/active in the database. `false` when unsure.
- `confirmation_evidence` becomes the database's own verification note, so it must be
  specific and quotable. Never write "verified" or "confirmed" alone.

### `new_scholarship` — the fields that write to the row

Required on every record:

| field | rule |
|---|---|
| `name` | Official full award name, **max 255 characters** |
| `legacy_titles` | `[ "<shard's current_title verbatim>" ]` |
| `country` | Host country, common English name, **max 120** |
| `degree_levels` | e.g. `"Master's"`, `"Bachelor's"`, `"PhD"`, `"Master's, PhD"`, **max 255** |
| `funding_type` | e.g. `"Fully Funded"`, `"Partially Funded"`, `"Tuition Fee Waiver"`, `"Stipend"`, **max 120** |
| `official_source` | The awarding body's name, **max 255** |
| `official_source_url` | exactly the shard's `current_official_source_url` |
| `status` | `"open"` or `"upcoming"` — nothing else is accepted |
| `is_verified` | `true` if you verified from the awarding body itself |
| `last_verified_date` | `"2026-10-04"` |
| `description` | 2–4 factual sentences. No marketing language. |

Also carry these when you have real, sourced values:

`region`, `duration`, `deadline`, `deadline_date`, `deadline_precision`,
`application_period`, `eligibility_summary`, `eligibility[]`, `coverage[]`,
`required_documents[]`, `catalogue_url`, `official_updates_url`,
`english_requirement`, `requirements[]`, `application_method[]`, `selection_notes`,
`program_type` (**max 255**), `best_fit`, `notes`, `benefits[]`,
`funding_amount`, `funding_currency`, `funding_period`.

Rules for the tricky ones:

- **`deadline`** — human sentence quoting the official wording.
- **`deadline_date`** — ISO `YYYY-MM-DD` **only** if the official page states an exact
  calendar date for the **next still-applicable** cycle. Else `null`. Never guess.
- **`deadline_precision`** — exactly one of
  `"exact"`, `"month"`, `"year"`, `"rolling"`, `"recurring"`, `"varies"`,
  `"approximate"`, `"unknown"`.
  `exact` = a real calendar date; `month` = only a month; `recurring` = an annual
  cycle with no fixed date; `rolling` = always open; `varies` = per-applicant/per-programme;
  `unknown` = the official site states nothing usable.
- **`funding_amount`** — one number only, `null` if not published.
  **`funding_currency`** — uppercase ISO code. **`funding_period`** — e.g. `"per month"`.
- **`required_documents`** — array of document strings (the merge renames it).
- **`coverage[]` / `benefits[]`** — what the money actually pays for. A living stipend
  is **not** a tuition waiver; never claim tuition is covered unless the official page
  says so.
- **`status`** — if the current cycle has closed but the award runs every year, use
  `"upcoming"` and put the next-cycle expectation in
  `programme_detail_official.status_note`. If the programme has genuinely lapsed for
  good, use `outcome: "discontinued"`.
- **`official_source_url` / `catalogue_url` / `official_updates_url`** must be `https://`.

### `programme_detail_official` — official facts only

Official facts here; advice goes in the applicant-utility block. Never mix them.
Required keys:

```
official_source_urls        array of the https pages you actually read
application_link            string|null
official_updates_url        string|null
catalogue_url               string|null
application_cycle           e.g. "2027 entry; applications open Oct 2026"
deadline_central            string|null   ISO "YYYY-MM-DDTHH:MM" or "YYYY-MM-DD"
deadline_central_display    string        human deadline, official wording
deadline_central_timezone   string|null   e.g. "Europe/Paris"
deadline_note               string        explains the deadline situation
status                      "OPEN"|"UPCOMING"|"CLOSED"|"ONGOING"|"DISCONTINUED"
status_note                 string
funding_amount              number|null
funding_currency            string|null
funding_period              string|null
funding_duration            string
tuition_coverage            boolean
tuition_coverage_note       string
living_cost_coverage        boolean|null
travel_coverage             boolean|null
fully_funded                boolean
funding_label               string        one-line money summary
benefits                    array of strings
eligibility                 array of strings
citizenship_residency       string
international_eligibility   string
degree_levels               array of strings
study_mode                  string|null
research_requirement        string|null
subject_or_agency_requirement string|null
application_method          string
application_route           string
requirements                array of strings
documents                   array of strings
english_requirement         string|null
english_requirement_note    string
selection_criteria          array of strings
selection_weighting         string|null
duration                    string
award_holder_conditions     array of strings
supplements_or_initiatives  array of strings
official_contacts           object e.g. {"general": "...", "email": "..."}
description                 string
program_type                string
region                      string
coverage                    string
last_verified_date          "2026-10-04"
```

Banned inside this block: `application_readiness_checklist`,
`common_rejection_risks`, `estimated_uncovered_costs`, `document_audit`, `alerts`,
`submission_workflow`. Banned as placeholder strings anywhere: `""`, `"n/a"`, `"na"`,
`"-"`, `"none"`, `"tbd"`, `"unknown"`, `"null"` — use `null`.

**Funding invariant:** `fully_funded: true` is allowed **only** when
`tuition_coverage: true`. A stipend alone means `fully_funded: false`. Any bond or
service obligation goes in `award_holder_conditions` **and** forces
`fully_funded: false`, and must be named in `funding_label`.

### `programme_detail_applicant_utility` — exactly 6 arrays

```json
{
  "application_readiness_checklist": ["..."],
  "common_rejection_risks": ["..."],
  "estimated_uncovered_costs": ["..."],
  "document_audit": ["..."],
  "alerts": [{"trigger": "short label", "message": "..."}],
  "submission_workflow": ["..."]
}
```

Guidance derived from the official facts — what the applicant should *do*.

### `programme_detail_verification`

```json
{
  "cycle_verified": "2027 entry cycle, verified 2026-10-04",
  "verification_confidence": 0.9,
  "official_fields_confirmed": ["funding_amount", "deadline_central", "..."],
  "institution_check_required": ["..."],
  "unverified_or_removed_claims": ["..."],
  "source_citations": ["https://...", "https://..."],
  "researched_by": "w1_07"
}
```

- `source_citations` — **mandatory, non-empty**, only URLs you actually fetched.
- `verification_confidence` 0–1: `0.9+` only when every field came from the awarding
  body; `0.6–0.8` if any official page was unreachable; below `0.6` if most of it was.
- `unverified_or_removed_claims` — list every field you could **not** confirm, and any
  claim in the stored record that the official site contradicts.
- `researched_by` — your `agent_id`.

### `research_notes`

```json
{
  "logo": "how you found and verified the logo, or exactly what you tried and why it is null",
  "unverified": ["..."],
  "substitution": null,
  "official_pages_read": ["https://..."],
  "degree_level_confirmed": "quoted evidence that this award funds this degree level",
  "url_observed": null,
  "contradictions": ["stored value X is wrong; the official page says Y"],
  "skeleton": false
}
```

---

## 5. Report back (final message, short)

- how many records: `refreshed` / `verified_no_change` / `unreachable` / `discontinued`
- logos found vs `null` (with reasons for the nulls)
- any record where the official site contradicted the stored data
- confirm you wrote `research/wave1/out/<shard>.json`

Be honest about gaps. **An accurate record with nulls is worth more than a
complete-looking one with invented values.**