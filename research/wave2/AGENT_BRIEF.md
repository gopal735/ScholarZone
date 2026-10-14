# WAVE 2 BRIEF — discover and research scholarships that are OPEN right now

You are one of 50 parallel research agents. Your shard file defines one cell of a
theme × region grid (plus two global sweeps). Your job is to **discover scholarships
that are currently open for applications, that are not already in the ScholarZone
database**, research them properly from official sources, and find each awarding
body's official logo.

Today is **2026-10-04**. Target: **8 new records** per shard. Quality beats count —
6 excellent records beat 8 thin ones.

---

## 1. Your assignment

Read your shard file (path given in your prompt):

```
{
  "shard": "w2-07", "agent_id": "w2_07",
  "theme": "university",  "region": "europe",
  "region_countries": ["United Kingdom", "France", ...],
  "theme_brief": "University-funded scholarships: ...",
  "target_records": 8,
  "dedup": { "existing_titles": [...], "existing_hosts": [...], "existing_official_source_urls": [...] }
}
```

`dedup` is the live catalogue. **Never produce a record for anything in it**, and never
produce a near-duplicate of one under a different name. Same awarding body + same
funding scheme = duplicate, even with a different page URL.

---

## 2. Discovery rules

1. **Official sources only.** The awarding body's own domain, or an official
   government/ministry page. Never an aggregator, blog, news site, Wikipedia, or a
   "top scholarships" list. Aggregators may be used to *discover* a name, but the
   record must be built from the awarding body's own page.
2. **Open means open.** The programme must accept applications now, or have a
   published application window that opens within the next ~10 months. A programme
   whose official page shows no current cycle at all is not a record — skip it.
3. **A real funding award**, not a fee-reduction scheme that nobody can apply to, not
   a loan, and not a course advertisement.
4. **Never invent a scholarship to fill a slot.** If your theme/region genuinely has
   nothing new, write fewer records and say so.
5. **Non-English official pages are fine** — and often necessary. Fetch the German,
   French, Spanish, Portuguese, Italian, Dutch, Japanese, Korean, Turkish or Arabic
   page when that is where the award is published. Quote the official wording in the
   original language where it is the authoritative wording.
6. **Budget: at most 8 web fetches per candidate record** (discovery fetches count
   separately and are not part of the 8). Never retry a blocked page more than twice.
7. **Write early, write often.** After every 2 records, rewrite your output file with
   what you have confirmed. A partial file with real citations is worth far more than
   a perfect file you never write. If you run short on time, stop and save.

---

## 3. The logo — mandatory, and it must be the awarding body's own mark

Search order:
1. A logo file on the awarding body's own domain — header/footer markup, `/favicon.ico`,
   `/apple-touch-icon.png`, `og:image`, schema.org `logo`, or common paths
   (`/logo.svg`, `/assets/logo.svg`, `/sites/default/files/logo.svg`).
2. An official brand / press / media page on that same domain.
3. An official verified social profile asset, only when the bytes are the body's own.

**Probe the URL before reporting it**: HTTP 200 **and** an image content type
(`image/svg+xml`, `image/png`, `image/jpeg`, `image/x-icon`, `image/webp`). HTML in
place of image bytes means a WAF interstitial or error page — reject it.

**Hard bans — a violation is a failure:**
- Any third-party host (aggregator, blog, Wikipedia/Wikimedia, news, stock site, CDN
  mirror, imgur, pinterest, a screenshot).
- A logo belonging to a body other than the one awarding the scholarship.
- A **white-on-transparent** wordmark (invisible on a light card) — find a dark
  variant or report `null`.
- An unprobed or invented URL.

**`null` is a correct, acceptable result.** Say in `research_notes.logo` what you tried.

```json
{
  "url": "https://official-domain/path/logo.svg",
  "page_url": "https://official-domain/official/page",
  "official_host": true,
  "alt_text": "Awarding body name",
  "validation_result": "verified",
  "validation_detail": "svg 11931+B, dark wordmark",
  "image_kind": "official_logo",
  "image_format": "svg",
  "verified_at": "2026-10-04T00:00:00+00:00",
  "host_evidence": "same_registrable_domain",
  "_award": "<award name this logo belongs to>"
}
```

---

## 4. Output file

Write **exactly one** file: `research/wave2/out/<your shard>.json` (e.g.
`research/wave2/out/w2-07.json`). Create the `out` directory if needed.

```json
{
  "agent_id": "w2_07",
  "shard": "w2-07",
  "today": "2026-10-04",
  "records": [ { ...one object per new scholarship... } ],
  "rejected": [ {"candidate": "...", "url": "...", "reason": "already in catalogue" } ]
}
```

Each record object — exactly these keys:

```json
{
  "outcome": "new",
  "new_scholarship": { ... },
  "programme_detail_official": { ... },
  "programme_detail_applicant_utility": { ... },
  "programme_detail_verification": { ... },
  "logo_override": { ... } | null,
  "research_notes": { ... }
}
```

There is **no `target_id`** — these are new rows.

### `new_scholarship`

Required:

| field | rule |
|---|---|
| `name` | Official full award name, **max 255 characters** |
| `country` | Host country, common English name, **max 120** |
| `region` | `Europe` / `United States` / `Canada` / `Australia` / `New Zealand` / `Asia` / `Latin America` / `Africa` / `Middle East` — one value |
| `degree_levels` | e.g. `"Bachelor's"`, `"Master's"`, `"PhD"`, `"Master's, PhD"`, **max 255** |
| `funding_type` | e.g. `"Fully Funded"`, `"Partially Funded"`, `"Tuition Fee Waiver"`, `"Stipend"`, **max 120** |
| `program_type` | e.g. `"Government scholarship"`, `"University merit scholarship"`, **max 255** |
| `official_source` | The awarding body's name, **max 255** |
| `official_source_url` | **Deepest verified official page for THIS award** — not a homepage, **max 2048** |
| `catalogue_url` | Official finder/catalogue URL, else `null` |
| `official_updates_url` | Official page where next-cycle updates appear, else `null` |
| `status` | `"open"` or `"upcoming"` — nothing else is accepted |
| `is_verified` | `true` only if you verified from the awarding body itself |
| `last_verified_date` | `"2026-10-04"` |
| `description` | 2–4 factual sentences. No marketing language. |

Also carry, when you have real sourced values: `duration`, `deadline`, `deadline_date`,
`deadline_precision`, `application_period`, `eligibility_summary`, `eligibility[]`,
`coverage[]`, `benefits[]`, `requirements[]`, `required_documents[]`,
`application_method[]`, `english_requirement`, `selection_notes`, `best_fit`, `notes`,
`funding_amount`, `funding_currency`, `funding_period`, `image_url`,
`image_source_url`, `image_source_type`, `image_alt_text`, `image_verified_at`.

- `official_source_url`, `catalogue_url`, `official_updates_url` must be `https://`.
- **`deadline_date`** — ISO `YYYY-MM-DD` **only** when the official page states an exact
  calendar date for the next still-applicable cycle. Else `null`. Never guess.
- **`deadline_precision`** — exactly one of `"exact"`, `"month"`, `"year"`, `"rolling"`,
  `"recurring"`, `"varies"`, `"approximate"`, `"unknown"`.
- **`funding_amount`** — one number only, `null` if not published. **`funding_currency`**
  uppercase ISO. **`funding_period`** e.g. `"per month"`.
- **`coverage[]` / `benefits[]`** — what the money actually pays for. A living stipend is
  **not** a tuition waiver; never claim tuition coverage the official page does not state.
- **`image_source_type`** — one of `official_scholarship`, `official_university`,
  `official_government`, `official_provider`. Use it only when the image really is the
  awarding body's own mark. If you have a verified `logo_override`, you may leave the
  `image_*` fields null — the logo is attached from the override at merge time.

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

Banned inside this block: `application_readiness_checklist`, `common_rejection_risks`,
`estimated_uncovered_costs`, `document_audit`, `alerts`, `submission_workflow`.
Banned as placeholder strings anywhere: `""`, `"n/a"`, `"na"`, `"-"`, `"none"`, `"tbd"`,
`"unknown"`, `"null"` — use `null`.

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

### `programme_detail_verification`

```json
{
  "cycle_verified": "2027 entry cycle, verified 2026-10-04",
  "verification_confidence": 0.9,
  "official_fields_confirmed": ["funding_amount", "deadline_central", "..."],
  "institution_check_required": ["..."],
  "unverified_or_removed_claims": ["..."],
  "source_citations": ["https://...", "https://..."],
  "researched_by": "w2_07"
}
```

- `source_citations` — **mandatory, non-empty**, only URLs you actually fetched.
- `verification_confidence` 0–1: `0.9+` only when every field came from the awarding
  body; `0.6–0.8` if any official page was unreachable.
- `unverified_or_removed_claims` — everything you could not confirm.
- `researched_by` — your `agent_id`.

### `research_notes`

```json
{
  "logo": "how you found and verified the logo, or exactly what you tried and why it is null",
  "unverified": ["..."],
  "substitution": null,
  "official_pages_read": ["https://..."],
  "degree_level_confirmed": "quoted evidence that this award funds this degree level",
  "dedup_check": "how you checked this against the dedup list",
  "skeleton": false
}
```

---

## 5. Absolute accuracy rules

1. No invented facts. Not published ⇒ `null`.
2. No invented dates. No exact calendar date ⇒ `deadline_date: null`.
3. Don't universalise a per-programme rule into a global one.
4. Separate admission from funding — say explicitly whether the award is automatic on
   admission or needs its own application.
5. Bonds are not optional information: `award_holder_conditions` + `fully_funded: false`.
6. Cite only what you read.
7. Unreachable official page ⇒ `verification_confidence` ≤ 0.7 and note it.
8. Today is 2026-10-04. A deadline earlier than that for the current cycle means the
   current cycle has closed: use `status: "upcoming"` for a recurring award and put the
   next-cycle expectation in `status_note`.

## 6. Report back (short)

- how many new records written, and how many candidates rejected as duplicates
- logos found vs `null` (with reasons)
- the countries and awarding bodies you covered
- confirmation that `research/wave2/out/<shard>.json` was written