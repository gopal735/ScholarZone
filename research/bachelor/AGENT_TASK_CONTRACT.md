# Agent task contract — bachelor scholarship record

Read `SCHEMA_CONTRACT.md` for exact field names. Model the shape on an existing
good record: `b46-university-of-ljubljana.json`.

## Hard rules

1. **ONE target per session.** Finish it, then stop. Do not batch.
2. **Write the file EARLY and WRITE IT ONCE.** After your first successful
   official fetch, write a valid file immediately, then improve it in place.
   Upstream idle timeouts kill sessions that research for a long time before
   writing. A thin valid record beats a good record that is never written.
3. **Fetch budget: 5 fetches maximum.** If the page is blocked, a WAF
   interstitial, or unreachable, report that honestly. Never retry endlessly.
4. **Duplicate check first, and it needs no network.** Grep
   `EXISTING_AWARDS.md` for the awarding body. If the award is already indexed,
   do not write a file — report `DUPLICATE` with the id.
5. **If the assigned target name does not exist on the official site, use the
   real published name.** Record the removal in
   `programme_detail_verification.unverified_or_removed_claims`. Never invent an
   award to fill the slot.
6. **region must be exactly one of:** `Europe`, `United States`, `Canada`,
   `Australia`, `Singapore`, `Malaysia`. A continent is invalid.
7. **Unpublished values are real JSON `null`.** Never `"null"`, `"tbd"`,
   `"n/a"`, `"unknown"`, `""`.
8. **status is `open` or `upcoming` only.** If the current cycle has closed,
   write `closed` and say so in your report. Never fake it to pass.
9. **Citations:** `programme_detail_verification.source_citations` needs at
   least 2 real URLs you actually fetched, and `official_fields_confirmed` must
   list the fields you actually confirmed. A record with zero citations is
   worthless and will be held out of the merge.
10. **Logo:** `logo_override.url` may only be an official-domain image that you
    verified returns HTTP 200 with an image content-type. Otherwise `null`.
    Never guess, never use an aggregator, CDN or third-party image. A `null`
    logo is a correct and acceptable result. Reject a white/transparent
    wordmark — it renders as nothing on a light card.

## Schema — exactly six top-level keys, nothing else

```
new_scholarship
programme_detail_official
programme_detail_applicant_utility
programme_detail_verification
logo_override
research_notes
```

## Report back

- award name written, or `REJECTED` / `DUPLICATE`
- degree-level evidence, **quoted** from the official page
- status | citations count | logo url or `null` | filename
- any place the official site contradicted the assigned target

Be honest about gaps. An accurate record with nulls is worth more than a
complete-looking one with invented values.