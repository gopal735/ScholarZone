# Live-upcoming data patch

A version-controlled, reviewable record of the scholarship additions made on
2026-10-15: **15 new scholarships** and **141 backfilled official logos**. The
database itself is gitignored, so without this patch the change exists only as
an opaque 18 MB file nobody can read or review.

## What is here

| File | Contents |
| --- | --- |
| `manifest.json` | Counts, source checksums, reserved ids, and the post-insertion correction applied to id 737. |
| `new_records.json` | The 15 new scholarships, in the order a fresh apply inserts them. |
| `logo_updates.json` | The 141 logo updates with before/after values. |
| `README.md` | This file. |

## How to apply it

```
# dry run — the default; writes nothing
backend/.venv/Scripts/python.exe backend/app/data/apply_live_upcoming_patch.py

# apply
backend/.venv/Scripts/python.exe backend/app/data/apply_live_upcoming_patch.py --apply
```

The script is dry-run by default and refuses to write without `--apply`. It
refuses to run under `SCHOLARZONE_ENVIRONMENT=production` and refuses any
non-SQLite target without an explicit `--allow-remote`. It applies everything in
one transaction, refuses duplicate or conflicting records rather than
overwriting them, and validates the result against the application's own public
visibility predicate afterwards.

Nothing calls this script automatically and nothing should: it is a one-shot,
human-reviewed import, not a scheduled task.

## Evidence limitations

Read these before treating the data as more certain than it is.

**Medium confidence (1 record).** Only `Yenching Academy of Peking University`
(id 738) is recorded as `medium`. Its English pages returned 404; the programme
was confirmed only on the Chinese-language official site.

**High confidence with published gaps (2 records).** `Churchill Scholarship`
(id 732) and `Kyoto University International Undergraduate Program` (id 735)
are recorded as `high` but carry explicit caveats: Churchill's stipend is not
published in monetary terms, and Kyoto iUP's deadline and monthly stipend live
in a PDF guidelines document rather than on the landing page. Their
`funding_amount` and `funding_period` are null because nothing was published,
not because the figures were missed.

**No invented figures.** 24 fields across the 15 records are null. Each was
checked against the research artifact and is null there too — the awarding
bodies did not publish those values. Nothing was estimated or carried over from
a third-party site.

**No Middle East.** A hard blocklist of 17 Middle East country names is enforced
by both the research validator and the apply script.

**Logo provenance.** 133 of the 141 logo URLs are hosted on the same domain as
the record's `official_source_url`. The remaining 8 come from a second official
domain of the same awarding body, or from the host institution of a co-funded
award:

| id | Logo domain | Official domain | Note |
| --- | --- | --- | --- |
| 78 | registryservices.ed.ac.uk | study-uk.britishcouncil.org | GREAT Scholarships at Edinburgh; Edinburgh is the co-funder |
| 115 | icar.org.in | icar.gov.in | ICAR operates both domains |
| 360 | studyinjapan.go.jp | in.emb-japan.go.jp | MEXT study portal and embassy page |
| 524 | nawa.gov.pl | westminster.ac.uk | **Known data defect — see below** |
| 568 | turkiyeburslari.gov.tr | scholarship.turkiye.gov.tr | Both are Türkiye Scholarships domains |
| 622 | welcometoserbia.gov.rs | prosveta.gov.rs | Both Serbian government education domains |
| 683 | ubd.edu.bn | mfa.gov.bn | BDGS is tenable at UBD; the logo comes from UBD's own scholarship page |
| 715 | studyinazerbaijan.edu.az | edu.gov.az | Study in Azerbaijan is the Azerbaijani education ministry's portal |

**Known data defect on id 524.** The University of Westminster's Postgraduate
Sanctuary Scholarship record carries a NAWA (Polish National Agency for Academic
Exchange) logo because that record's own `catalogue_url` field points at a NAWA
page. The attribution is wrong for a Westminster award. It is recorded here as
an unresolved issue: the logo was not fabricated, but it is the wrong awarding
body's brand mark. It should be replaced with a Westminster logo in a follow-up
pass.

**Logo verification method.** URLs were verified with an HTTP GET returning
`200` and an `image/*` content type. Many official servers return `403` to
`HEAD` while serving the same asset fine over `GET`, so `HEAD` alone is not a
sufficient check. 33 of the 184 originally-missing rows had a candidate that
still failed verification (bot-blocked, redirect to HTML, or an asset behind
JavaScript); those 33, plus 11 with no candidate at all, remain without a logo
and nothing was fabricated for them.

**Web search was unavailable.** The research provider's free allowance was
exhausted (HTTP 402). All research was done by fetching official
awarding-body pages directly. The original plan covered additional countries
(Ukraine, Greece, Romania, Bulgaria, Croatia, Slovenia, Lithuania, Iceland,
Malta, Cyprus, Georgia, Armenia, Nepal, Mongolia, Cambodia, Macau, Kenya,
Tanzania, Uruguay, Paraguay and others); that work is deferred, not complete,
because the scope was narrowed to top-demand countries.

## Reconciliation

| | Before (2026-10-14 baseline) | After |
| --- | --- | --- |
| Total scholarship rows | 695 | 710 |
| Active (not archived) | 643 | 658 |
| Public-eligible | 516 | 531 |
| Active rows with a logo | 459 | 615 |

The public-eligible count increased by exactly 15, and the added ids are exactly
730–744 with none removed. 10 of the 141 logo updates landed on rows that are
closed or archived, so the public "rows with a logo" figure rises by 131 rather
than 141.

Applying this patch onto the 2026-10-14 baseline reproduces the live database
state exactly — verified field by field across all 57 comparable columns for
each of the 15 records, and across every `image_url` for all 695 shared rows.
