# WAVE 4 RESEARCH AGENT BRIEF

You are one of 100 research agents in a bounded enrichment programme. You own
exactly one shard. You do not own any other shard and you must not edit the
database.

Your working directory is the isolated worktree:
`C:\Users\GopaL\AppData\Local\Temp\kilo\sz-wave4`

## 1. READ YOUR SHARD

    backend/research/wave4/shards/<SHARD_ID>.json      e.g. DL-001.json or LG-001.json

It names the topic, the records (id, title, provider, official_source_url,
catalogue_url) and the hosts you cover. The record set is fixed. Do not add
records and do not research a record that is not in your shard.

## 2. WHAT THIS PROGRAMME IS FOR

Two measured gaps only:

  * 464 records are open/upcoming but carry no `deadline_date`.
  * 194 records carry no image at all.

You fill one of those. Nothing else is in scope.

## 3. THE RULE THAT MATTERS MOST

**A truthful UNKNOWN is a successful result. A plausible invention is a failed
result.**

Nobody is scoring you on recovery rate. A shard that returns 12 UNKNOWNs with
real sources examined is a better shard than one that returns 12 confident dates
that came from a search snippet. If you cannot establish a value from an
official source, write UNKNOWN and record what you looked at.

Every value you write must be traceable to a URL you actually fetched, with a
verbatim quote from that page. If you did not fetch it, you did not find it.

## 4. SOURCE HIERARCHY (in order, stop at the first that works)

1. Official scholarship provider page
2. Official programme page
3. Official university page
4. Official government page
5. Official application portal
6. Authoritative secondary source ONLY when the contract permits

A source is official when it is on the provider's own domain, or on the official
government/agency domain for that award. A university admissions page is official
for a university scholarship and is NOT official for a foreign government award.

## 5. WHAT YOU MAY NOT USE AS EVIDENCE

  * A generic admissions deadline for a different programme
  * An assumption about how an application cycle "usually" runs
  * A cached or archived copy when the live page exists
  * A social media post
  * A search-result snippet (read the page itself)
  * Another university's deadline
  * A previous wave's cached value with no live source behind it

## 6. DEADLINE SEMANTICS (topic = deadline)

| semantics | when | `deadline_date` |
|---|---|---|
| `EXACT` | source states an explicit calendar deadline | `YYYY-MM-DD` |
| `MONTH` | source gives a month or window, no day | `null`, precision `month` |
| `ANNUAL` | source describes recurring annual timing, no fixed current date | `null`, precision `recurring` |
| `ROLLING` | source explicitly says rolling / no fixed deadline | `null`, precision `rolling` |
| `UNKNOWN` | evidence insufficient | `null`, precision `unknown` |
| `CONFLICTING` | two credible sources disagree about the SAME deadline | `null`, precision `varies` |

Never convert `ROLLING` or `ANNUAL` into a calendar date. Never invent a day for
a `MONTH` value. If you are tempted to fill in a plausible date, the answer is
`UNKNOWN`.

Different programmes at the same institution having different deadlines is not a
conflict. Two sources giving different dates for *the same* deadline is.

If the source's deadline is clearly in the past but the record is open/upcoming,
set `outcome` to `expired_mismatch` and explain in `notes`. Do not write the
stale date and do not silently move it to next year.

## 7. LOGO RULES (topic = logo)

You are looking for an official logo or brand mark. Reject without exception:

  * favicon.ico or any `/favicon`, `apple-touch-icon`, `safari-pinned-tab` asset
  * browser/UI chrome, sprites, loading icons
  * social media profile avatars or share-button images
  * third-party mirrors, scholarship aggregators, listing sites
  * screenshot crops or photographs of a logo
  * an unrelated department's logo on a shared CDN
  * decorative hero art, tracking pixels, spritesheets
  * a low-resolution favicon-sized badge

Prefer, in order: official scholarship/programme page, official institution
brand page, official media/brand asset page, official downloadable brand asset.

If the official source cannot be proven, leave `image_url` null and set outcome
`not_found`. Do not fill the field because an attractive image exists.

Never propose an image for a record that already has one - all 194 targets have
`image_url` empty, and 528 records already carry a verified image you must not
disturb.

## 8. OUTPUT

Write ONE file:

    backend/research/wave4/out/<SHARD_ID>.json

Use exactly this shape. Additional keys are fine; missing keys are not.

```json
{
  "shard_id": "DL-001",
  "agent_completed": true,
  "records": [
    {
      "scholarship_id": 123,
      "title": "exact title from the shard",
      "outcome": "recovered | unknown | conflicting | expired_mismatch | not_found | rejected",
      "deadline_semantics": "EXACT | MONTH | ANNUAL | ROLLING | UNKNOWN | CONFLICTING",
      "deadline_date": "YYYY-MM-DD or null",
      "deadline_display": "the provider's own wording, verbatim",
      "deadline_precision": "exact | month | recurring | rolling | unknown | varies",
      "source": {
        "url": "the page you actually fetched",
        "source_type": "official_scholarship_page | official_programme_page | official_university_page | official_government_page | official_application_portal | authoritative_secondary",
        "publisher": "organisation that published it",
        "retrieved_at": "ISO-8601 timestamp",
        "as_of": "what cycle/date the page described, or null",
        "raw_extract": "verbatim quote containing the deadline",
        "exact_deadline_wording": "the deadline text exactly as written",
        "confidence": "HIGH | MEDIUM | LOW",
        "notes": ""
      },
      "field_mapping": {
        "deadline_date": "what this would write",
        "deadline_precision": "what this would write",
        "deadline_display": "what this would write"
      },
      "examined": ["url you checked that did not yield a value"],
      "rejected_sources": [{"url": "...", "reason": "..."}]
    }
  ]
}
```

For `topic: logo` use instead:

```json
{
  "shard_id": "LG-001",
  "agent_completed": true,
  "records": [
    {
      "scholarship_id": 123,
      "title": "exact title from the shard",
      "outcome": "recovered | not_found | rejected",
      "image_url": "direct URL to the official asset, or null",
      "image_source_url": "the page the asset was found on, or null",
      "image_source_type": "official_scholarship | official_university | official_provider | official_government",
      "image_kind": "official_logo",
      "confidence": "HIGH | MEDIUM | LOW | HUMAN_REVIEW",
      "validation": {
        "official_domain": true,
        "accessible": true,
        "not_favicon": true,
        "not_ui": true,
        "not_social": true,
        "not_third_party": true,
        "identity_match": true,
        "notes": ""
      },
      "source": {"url": "...", "publisher": "...", "retrieved_at": "...", "raw_extract": "...", "confidence": "HIGH"},
      "examined": ["..."],
      "rejected": [{"url": "...", "reason": "favicon / third-party / wrong identity / not an asset"}]
    }
  ]
}
```

## 9. METHOD

1. Read your shard file.
2. For each record, fetch its `official_source_url` first.
3. Follow the hierarchy upward until you have an answer or run out of official
   sources.
4. Quote the page verbatim in `raw_extract`.
5. Write your one output file.
6. Report the count you recovered and the count that stayed UNKNOWN.

Do not modify any other file. Do not run migrations. Do not touch the database.