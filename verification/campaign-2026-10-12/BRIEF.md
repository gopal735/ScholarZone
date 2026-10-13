# Live verification campaign — 12 October 2026

ScholarZone publishes 618 public scholarships. 527 carry `verification_status:
active` (re-checked against the awarding body's own page). **91 records still
carry a non-active status** — `needs_review`, `pending`, `conflicting`,
`partial`, `outdated`, `unverified` — and this campaign verifies them against
live official sources, plus a spot check of the already-verified pool.

The catalogue is honest by design: a record that has not been re-checked says
so on the card. Your job is to move records out of that state **only** where
the evidence genuinely supports it.

---

## Your assignment

You verify **exactly one** record, given to you by `id`. Read your record's
fields from the manifest file your task names (`tasks-to-verify.json` for
unverified records, `tasks-spot-check.json` for already-active ones). Never
work on another agent's record.

## Method

1. **Fetch the record's `official_source_url`.** This is the awarding body's
   own page as last recorded.
2. **If it fails** (404, 410, connection error, a parked domain, a redirect to
   a login wall or a search page), search the web for the awarding body's
   current official page for this programme — by the awarding body name and
   the programme name. Try the institution's domain first; prefer `.edu`,
   `.ac.*`, `.gov`, and the organisation's own domain over aggregators.
3. **Adjudicate each claim below** against the page you actually read. Read
   the page content; do not judge from the URL alone.

## What must be verified

- **Awarding body** — the page is genuinely the awarding organisation's own
  (not a news article, a student blog, an aggregator, or a Wikipedia mirror).
- **Deadline** — the published deadline for the cycle that is currently open
  today (12 October 2026). If the page shows a deadline, quote it exactly.
  If the page shows rolling/unspecified, record that. If the page shows a
  past deadline, the record is not verifiable as open.
- **Eligibility summary** — the nationality, study-level, or requirement
  claims made in the catalogue record. Confirm each distinct claim, or mark
  the ones you cannot confirm.
- **Funding claim** — "Fully Funded" vs partial/unspecified, and what the
  funding actually covers. A tuition-only award is not fully funded.
- **Degree levels** — the levels the programme actually offers.

## Verdict

One of:

| verdict | meaning |
| --- | --- |
| `active` | The official page was read; awarding body, deadline, eligibility, funding and degree levels all agree with the record, and the deadline is for a currently-open cycle. |
| `needs_review` | The official page exists and was read, but at least one claim cannot be confirmed from it (ambiguous wording, no stated deadline, a link to a PDF you cannot read). |
| `conflicting` | The official page contradicts the record in a material way (different deadline, different funding, different award, different body). |
| `quarantined` | No official page can be found at all — dead link, wrong page, or the programme no longer exists. |

Set `confidence` to `high`, `medium` or `low`. Use `low` when the only
evidence is a search result snippet rather than the page itself, and never
mark `active` with `low` confidence.

## Output — exactly two files, nothing else

Write these two files and change nothing else in the repository:

`verification/campaign-2026-10-12/<id>.json`

```json
{
  "id": "<id>",
  "verdict": "active|needs_review|conflicting|quarantined",
  "confidence": "high|medium|low",
  "checked_at": "<ISO-8601 time you did the check>",
  "sources": [
    { "url": "<page you read>", "kind": "official|aggregator|news|other", "note": "<what this page is>" }
  ],
  "findings": {
    "awarding_body": { "status": "confirmed|contradicted|unconfirmed", "detail": "<one or two sentences>", "quote": "<exact text from the page, or null>" },
    "deadline": { "status": "confirmed|contradicted|unconfirmed", "detail": "<the published deadline as the page states it, or why you cannot>", "quote": "<exact text, or null>" },
    "eligibility": { "status": "confirmed|contradicted|unconfirmed", "detail": "<which eligibility claims you confirmed and which you could not>", "quote": "<exact text, or null>" },
    "funding": { "status": "confirmed|contradicted|unconfirmed", "detail": "<what the award actually covers>", "quote": "<exact text, or null>" },
    "degree_levels": { "status": "confirmed|contradicted|unconfirmed", "detail": "<levels offered, as the page states>", "quote": "<exact text, or null>" }
  },
  "recommended_field_updates": {
    "official_source_url": "<new canonical official URL, or null if unchanged>",
    "deadline_text": "<the provider's own deadline wording, or null>",
    "deadline_date": "<ISO date if the page states an exact date, else null>",
    "verification_notes": "<what the next re-check should know>"
  },
  "notes_for_reviewer": "<anything a human must decide, or null>"
}
```

`verification/campaign-2026-10-12/<id>.md` — a short human-readable memo:
the verdict, the pages you read, the exact quotes that carry it, and what a
person should know before trusting the record.

## Rules

- **Never fabricate.** If you could not read the page, the verdict is
  `needs_review` or `quarantined` and your notes say why. A guess dressed as
  a confirmation is worse than an honest failure.
- **Quote exactly.** Copy sentences from the page. A paraphrase is not
  evidence.
- **Do not write to any database, and do not run the application.** This is
  a research task.
- **Do not change code, configuration, git history, or any other file.** Your
  two files are the whole deliverable.
- **Do not run `git` commands at all** — no add, no commit, no push.
- Date your check. Today is 12 October 2026.
