# Raw research archive

Research documents land here before anything becomes a corpus figure.

## The rule this directory exists to enforce

**A figure is ingested only when its source document and its source ids can be
pointed at.** Everything else stays out.

This sounds severe until you look at what it prevents. In the build that produced
this archive, eighteen country research passes reported findings directly into a
chat transcript. Those findings are not in the repository, and for two countries
the output was truncated mid-document. The temptation is to carry the numbers
forward anyway: they were reported confidently, several were sourced from official
pages, and reconstructing them by hand would take an afternoon.

It would also produce a corpus nobody could audit. A figure whose source is "an
agent said so in a session that no longer exists" is indistinguishable, to every
future reader, from a figure read off a ministry page last month. That is the
whole failure mode this feature was built to prevent, and it would enter through
the easiest door available — the door where someone is trying to be helpful.

So `manifest.json` records the tracking honestly: which countries were
researched, which task ids did it, and that the raw document is
`RAW_SOURCE_UNAVAILABLE`. Absence is recorded as absence.

## What is here

| File | What it is |
| --- | --- |
| `manifest.json` | Per-country tracking: task ids, raw source status, truncation, transformation and validation state. |

No raw research documents are currently archived. Every entry records that
absence explicitly rather than leaving a blank where a document should be.

## Status vocabulary

`raw_source` — where the original document is:

- `ARCHIVED` — stored under this directory, eligible for ingestion.
- `TRUNCATED` — retrieved but incomplete. Only the complete portion may be
  ingested, and only after review.
- `RAW_SOURCE_UNAVAILABLE` — not retrievable. **No figure from this country may
  be ingested.**

`transformation_status` — what ingestion has done with it:

- `NOT_STARTED` — raw material exists, not yet ingested.
- `INCOMPLETE` — attempted and rejected; nothing was written.
- `REJECTED` — inspected and deliberately not converted, reason recorded.
- `CANONICAL_PRESENT` — a validated file exists in `config/country_intelligence/`.

`validation_status` — `NOT_VALIDATED`, `VALIDATED`, or `FAILED`.

## Adding a country

1. Drop the raw research document in this directory, unmodified. Do not
   hand-edit it to fix a typo — a corrected document is a new document, and the
   original is the evidence of what was actually read.
2. Add a manifest entry with the task id, the file name, and the retrieval date.
   Leave `retrieved_at` unset rather than inventing one.
3. Run `python backend/scripts/ingest_country_intelligence.py --country XX`.
4. Read the report. A country that fails a gate is not written; the reason is
   printed and the file is left untouched.

Ingestion is deterministic. The same raw document and the same contract version
produce byte-identical output, so re-running it is safe and a diff shows only
real changes. The one exception is `retrieved_at`, which is carried from the
source document rather than taken from the clock — the pipeline deliberately has
no source of "now", so a re-run cannot quietly restamp an old figure as fresh.

## A note on `pending_claims`

Several figures were asserted in a later pass and are recorded there as
`UNAVAILABLE_FOR_INGESTION`. They are deliberately **not** in the corpus. A claim
in this manifest is a to-do item with a named field and a reason; it is not a
figure, and `ingest_country_intelligence.py` does not read this file when
building corpus data. If a claim here were treated as ingestible, the manifest
would become a second, unvalidated source of truth — the exact thing the data
contract exists to prevent.