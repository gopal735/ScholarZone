# ScholarZone Live-500 Deep Research - Agent Instructions

You are ONE of 500 research agents enriching the ScholarZone scholarship catalogue.
Your job: deeply research the scholarship(s) assigned to you against the OFFICIAL
awarding body's own published pages, then write a research record file.

## Step 1 - Read your assignment

Your assignment file is named `agent_XXX.json` in:

```
C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\research_output\live500\assignments\
```

The exact filename was given in your prompt. It contains 1-2 scholarship briefs:
`id`, `title`, `country`, `degree`, `funding_label`, `official_source_url`,
`application_link`, `catalogue_url`, `official_updates_url`, `existing` (what the
DB already holds, including `missing_fields`).

## Step 2 - Research (live, official sources only)

Use `WebSearch` to find the official page, then `WebFetch` the awarding body's own
page (start from `official_source_url` / `application_link` in the brief; follow the
official updates/FAQ pages when the amount or deadline lives there).

Rules of evidence:
- Prefer the awarding body's own domain. Do not take amounts from aggregators,
  blogs, or SEO listicles; a search snippet may only be used to LOCATE the
  official page, never as the value itself.
- If the official page does not publish a figure, record `null` and list the
  field under `verification.not_confirmed`. NEVER invent, estimate, or carry over
  a figure from an unaffiliated site. A wrong amount is worse than no amount.
- If the official page is unreachable after 2 attempts, use whatever the official
  domain itself publishes via search results, mark confidence `low`, and note it.

Research per scholarship: the published award amount, its currency, its period,
what it actually covers (tuition / living costs / travel or installation), the
current cycle's deadline, application route and required documents, English
requirement, and anything unusually useful to an applicant.

## Step 3 - Write your result file

Write ONE file, named `agent_XXX.json` (same XXX as your assignment), in:

```
C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\research_output\live500\results\
```

Shape (a list, one record per assigned scholarship, in order):

```json
{
  "agent": "agent_000",
  "records": [
    {
      "id": 123,
      "official": {
        "official_source_urls": ["https://official-page-1", "https://official-page-2"],
        "application_link": "https://...",
        "catalogue_url": "https://...",
        "official_updates_url": "https://...",
        "deadline_central": "2027-01-15",
        "deadline_central_display": "15 January 2027",
        "deadline_note": "institutional deadline that differs from the programme's, if any",
        "application_cycle": "intake/cycle wording, e.g. '2027/2028 cycle'",
        "status": "OPEN",
        "status_note": "what the official page says about the current round",
        "tuition_coverage_note": "exact published wording about tuition, if any",
        "funding_amount": 1400,
        "funding_currency": "EUR",
        "funding_period": "per month",
        "tuition_coverage": true,
        "living_cost_coverage": true,
        "travel_coverage": true,
        "fully_funded": true,
        "benefits": ["published benefit wording"],
        "eligibility": ["published eligibility rule"],
        "requirements": ["published requirement"],
        "documents": ["required document"],
        "selection_criteria": ["published selection criterion"],
        "coverage": ["what the money covers, in the awarding body's own terms"],
        "application_method": ["official application route step"],
        "application_route": "how one applies, one line",
        "study_mode": "full-time / part-time / as published",
        "citizenship_residency": "citizenship or residency rule as published",
        "international_eligibility": "whether international students are eligible",
        "subject_or_agency_requirement": "field/agency restriction, if any",
        "research_requirement": "research-proposal requirement, if any",
        "duration": "as published",
        "description": "1-3 sentences, the awarding body's own framing",
        "region": "as published / catalogue region",
        "program_type": "as published",
        "english_requirement": "IELTS/TOEFL score or MOI rule as published, or null"
      },
      "verification": {
        "source_citations": ["https://exact-page-the-amount-came-from"],
        "last_verified_date": "2026-10-10",
        "verification_status": "confirmed",
        "confidence": "high",
        "not_confirmed": ["fields the official pages did not state"],
        "notes": "one line on what was checked"
      },
      "applicant_utility": {
        "summary": "2-4 ORIGINAL sentences an applicant can act on",
        "best_fit": "who this suits most, one line",
        "application_readiness_checklist": ["actionable pre-submission steps"],
        "common_rejection_risks": ["specific ways applications fail here"],
        "estimated_uncovered_costs": "what applicants must still fund themselves, or null",
        "document_audit": ["document traps specific to this programme"],
        "alerts": ["timing or eligibility traps worth warning about"],
        "submission_workflow": "how the submission actually proceeds, one line"
      }
    }
  ]
}
```

### Field rules (each one is load-bearing)

1. **Nulls stay null.** A field the official pages did not state is `null` or the
   key is absent. Never write `""`, `"N/A"`, `"-"`, `"TBD"`, `"unknown"`.
2. **`funding_amount`** is a bare number - no commas, no currency, no units
   (`1400`, not `"EUR 1,400/month"`). The currency lives in
   **`funding_currency`** (ISO code, e.g. `EUR`) and the cadence in
   **`funding_period`** (`per month`, `per year`, `one-off`, ...). Keep
   `funding_period` under 60 characters.
3. **`fully_funded`** is `true` ONLY when the official source states tuition AND
   living costs AND required expenses are covered - and then
   `tuition_coverage` must also be `true`. A fixed stipend is not full funding.
   When in doubt, leave it `false`/absent.
4. **`verification.source_citations`** must contain at least one `http(s)` URL on
   the awarding body's own domain - the page the amount actually came from.
   Without a citation the record is discarded.
5. **`verification.last_verified_date`** is always `"2026-10-10"`.
6. The `official` block holds **only what the awarding body published**. Guidance
   you write yourself goes in `applicant_utility` only. Never put a
   `applicant_utility` key inside `official`.
7. **`applicant_utility` content must be ORIGINAL writing** - your own synthesis,
   not copied sentences from the source page, and not a generic paragraph that
   could sit on any scholarship. Make it specific to this programme: its real
   rejection risks, its real documentation traps, who it genuinely suits.
8. Keep each list to the strongest 3-6 items. Quality over volume.
9. Only work on the rows in YOUR assignment file. Do not research anything else,
   and do not write any other scholarship's record.

## Step 4 - Validate before you finish

Run:

```
python -c "import json;d=json.load(open(r'<your result file path>',encoding='utf-8'));print(len(d['records']),[r['id'] for r in d['records']])"
```

It must parse and list exactly the ids from your assignment. Then confirm every
record passes: non-empty `applicant_utility.summary`, at least one `http`
citation, `last_verified_date` present, and `fully_funded` implies
`tuition_coverage: true`. Fix anything that fails, re-run, and only then finish.

## Hard boundaries

- Do NOT open, write, move or delete `scholarzone.db`, any `*.db` file, any file
  under `backend/config/`, or any other agent's assignment/result file.
- Do NOT run git commands. Do NOT commit anything.
- Write ONLY your own result file.

Your final message: one short paragraph - which ids you researched, what you
confirmed, what you could not confirm, and the result file path.
