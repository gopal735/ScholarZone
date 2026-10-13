# Rollout: what merging this PR does, and the order of the rest

## The one sentence that matters

**Merging this PR applies nothing.** It changes no database record and changes no
environment variable. `SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED` stays `false`
wherever it is deployed, because the default in `app/core/config.py` is `false`
and the variable is not set in any environment.

What merging *does* do is wire a setting that previously did nothing. After the
merge, setting `SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED=true` will start hiding
records whose `verification_status` is not `active`. That is a real change of
behaviour, and it reads the **database**, not this campaign's evidence.

## Why the flag must not be switched on yet

The flag filters on the current database `verification_status`. So does the
catalogue's own trust labelling. This campaign changed neither. The two statuses
are therefore different in both directions, today:

**Records the evidence says are wrong, still `active` in the database.** The
five spot-checked records that did not survive re-reading:

| id | programme | evidence | still in the database as |
| --- | --- | --- | --- |
| 131 | Rotary Peace Fellowship | `needs_review` — the 15 May deadline is not on the official page | `active` |
| 189 | Umeå University Scholarship for International Students | `needs_review` | `active` |
| 245 | UCAS Chinese Government Scholarship (University of Cambridge) | `needs_review` | `active` |
| 303 | Camões, I.P. Portuguese Language and Culture Scholarship | `conflicting` | `active` |
| 422 | UNESCO/Poland Co-Sponsored Fellowships in Engineering | `conflicting` | `active` |

**Records the evidence supports, not `active` in the database.** 58 of the 91
newly researched records came back `active` — the evidence says they are correct,
but the database still says `needs_review`, so the catalogue still labels them
"Confirm with provider".

Switching the flag on **before a reviewed status update** produces exactly the
wrong catalogue:

- the five known-bad records above stay visible **as verified** — the flag
  actively endorses them, which is worse than the current state, where they are
  at least labelled with a date of last check;
- the 58 records with fresh confirming evidence stay **hidden** — they are
  labelled "Confirm with provider" today and disappear entirely under the flag.

That is the one combination nobody wants: bad records promoted to "verified" and
good records removed from the catalogue.

## The order the decisions have to be made in

1. **Review the proposals, record by record.** `RECONCILIATION-PLAN.md` lists
   all 45, with the evidence file each one rests on. A verdict label is not a
   promotion: read the memo before changing a status. In particular the 29
   `needs_review` proposals include records whose round has already closed — see
   the "closed rounds" section of the plan.
2. **Apply the reviewed updates to the database.** This campaign produces the
   evidence, not the updates. Whoever applies them should cite the evidence file
   as the source of the change, the way this repository already does for every
   other status change. Not my call to make here, and not done by this PR.
3. **Downgrade the five spot-check failures.** 131, 189, 245, 303 and 422 need a
   status that matches the evidence before the flag can mean anything. Two of
   them (`303`, `422`) are material contradictions: the official page disagrees
   with the record.
4. **Re-check a proper sample of the remaining 518 `active` records.** Five of
   nine failed, so `active` is not a reliable input for a visibility gate. The
   full catalogue, not this PR, decides how deep that goes.
5. **Only then set `SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED=true`.** At that point
   the flag expresses a decision about a population that has actually been
   checked, and it can be reversed by unsetting the variable.

Step 5 needs no redeploy. The setting is read from the process environment on
every call to `public_visibility_conditions()` — not captured at import, and
there is a test pinning that — so a restart with the variable unset returns the
previous behaviour immediately.

## What the flag does not do

- it does not re-check anything. It filters on a status someone wrote;
- it does not hide quarantined, closed or archived records any differently —
  those exclusions are applied before it and are unaffected;
- it does not change the homepage statistics' source: the stats delegates to the
  same predicate, so both numbers move together, which is the reason that
  predicate was made single in the first place.

## Risks if this is skipped

| risk | consequence |
| --- | --- |
| flag on before reconciliation | 5 records shown as verified with contradicting evidence; 58 correct records hidden |
| flag on after only the promotions, not the downgrades | the five stay endorsed as verified |
| promoting on a verdict label without reading the memo | a `needs_review` verdict can still carry a corrected deadline worth keeping; a `conflicting` verdict needs the field replaced, not just the status changed |
| treating `active` as verified without re-checking | the flag gates on a state with a known failure rate in this sample |

## Verification of this document's numbers

`backend/tests/test_campaign_report_consistency.py` recomputes every count
quoted here from the evidence files and fails CI if this document or
`README.md` disagrees with them.
