# Reconciliation plan — the 45 proposed updates

Generated from the campaign artifacts by `verification\campaign-2026-10-12\build-reconciliation-plan.mjs`.
Nothing in this plan is applied. Every row carries its evidence file, and every
number is recomputed from the evidence rather than copied from the PR text.

## What the 45 proposals are

`proposed-verification-updates.json` holds one proposal per record where the
evidence supports a status change **or** a field correction. It is not a list of
records to promote.

| group | records | what the evidence says |
| --- | --- | --- |
| `needs_review` | 29 | the official page was read but a specific claim could not be confirmed from it |
| `conflicting` | 7 | the official page contradicts the record materially |
| `active` | 7 | confirmed, but a field is wrong (a stale `official_source_url` is the usual one) |
| `quarantined` | 2 | no official page could be found |

7 of them are spot-checks of records the database already
calls `active`; 38 are newly researched records.

## Status changes vs field changes

- **16 of 45 change `verification_status`**:
  - 3 to `needs_review` — all three are downgrades of records the database currently calls `active` (131, 189, 245).
  - 6 to `conflicting`, of which 5 move (one is already `conflicting` and only its fields change).
  - 2 to `quarantined` (31 and 79).
  - **5 to `active`** — promotions of records currently `needs_review` or `partial` (23, 526, 631, 643, 657). These are what make the flag's effect real, and the reason a promotion is never applied from this file alone.
- **2 of the `active` rows change no status at all** — the record is already `active` and only a field is wrong.
- Fields proposed for change: `deadline_text` on 43 records, `verification_notes` on 45 records, `official_source_url` on 15 records, `deadline_date` on 25 records.
- Every one of the 45 proposals carries a `verification_notes` value, so a record that is applied keeps the trail of what was checked and when.

## What requires a human, and why

All 45 require a human. **Do not promote anything on a verdict label
alone** — read the memo first. Within that:

- **31 need particular care**:
  - **5 are proposed promotions to `active`** (23, 526, 631, 643, 657). Promoting a record to verified is the one change the flag then acts on, and therefore the one change that must not be made from a verdict label. Read each memo.
  - **7 are already marked `active`** (131, 189, 245, 303, 422 and two others). Downgrading a record the site presents as verified is a change a person should own; the two `conflicting` ones (303, 422) are outright contradictions.
  - **7 are `conflicting`** — these need the *field* replaced, not just the status changed. A status flip that leaves the wrong deadline text in place would be worse than no change.
  - **19 are closed or expired** — the evidence says the round is over (131, 245, 303, 31, 422, 497, 508, 510, 514, 520, 523, 525, 611, 615, 674, 684, 710, 721, 79). These must not end the reconciliation presented as open. Archive, or keep hidden with the reason recorded.
  - **2 are not `high` confidence** (131: medium, 695: low) — read the memo before acting on those at all.
  - **2 are `quarantined`** (31 and 79). They are currently visible with a `needs_review` label; the proposal is what hides them.

## The records

### `needs_review` (29)

| id | kind | current status | evidence | confidence | suggested | fields to change | open round on the evidence | evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 131 | spot-check (already active) | active | needs_review | medium | needs_review | deadline_text, verification_notes | **yes** | `131.json` |
| 189 | spot-check (already active) | active | needs_review | high | needs_review | official_source_url, deadline_text, verification_notes | no | `189.json` |
| 245 | spot-check (already active) | active | needs_review | high | needs_review | deadline_text, deadline_date, verification_notes | **yes** | `245.json` |
| 492 | new research | needs_review | needs_review | high | needs_review | deadline_text, deadline_date, verification_notes | no | `492.json` |
| 497 | new research | needs_review | needs_review | high | needs_review | deadline_text, verification_notes | **yes** | `497.json` |
| 510 | new research | needs_review | needs_review | high | needs_review | deadline_text, verification_notes | **yes** | `510.json` |
| 514 | new research | needs_review | needs_review | high | needs_review | deadline_text, verification_notes | **yes** | `514.json` |
| 520 | new research | needs_review | needs_review | high | needs_review | deadline_text, verification_notes | **yes** | `520.json` |
| 523 | new research | needs_review | needs_review | high | needs_review | official_source_url, deadline_text, verification_notes | **yes** | `523.json` |
| 525 | new research | needs_review | needs_review | high | needs_review | deadline_text, verification_notes | **yes** | `525.json` |
| 580 | new research | needs_review | needs_review | high | needs_review | deadline_text, verification_notes | no | `580.json` |
| 583 | new research | needs_review | needs_review | high | needs_review | official_source_url, deadline_text, deadline_date, verification_notes | no | `583.json` |
| 611 | new research | needs_review | needs_review | high | needs_review | deadline_text, verification_notes | **yes** | `611.json` |
| 615 | new research | needs_review | needs_review | high | needs_review | deadline_text, deadline_date, verification_notes | **yes** | `615.json` |
| 626 | new research | needs_review | needs_review | high | needs_review | deadline_text, deadline_date, verification_notes | no | `626.json` |
| 661 | new research | needs_review | needs_review | high | needs_review | deadline_text, deadline_date, verification_notes | no | `661.json` |
| 665 | new research | needs_review | needs_review | high | needs_review | deadline_text, verification_notes | no | `665.json` |
| 668 | new research | needs_review | needs_review | high | needs_review | deadline_text, verification_notes | no | `668.json` |
| 669 | new research | needs_review | needs_review | high | needs_review | deadline_text, verification_notes | no | `669.json` |
| 670 | new research | needs_review | needs_review | high | needs_review | deadline_text, verification_notes | no | `670.json` |
| 671 | new research | needs_review | needs_review | high | needs_review | deadline_text, deadline_date, verification_notes | no | `671.json` |
| 672 | new research | needs_review | needs_review | high | needs_review | deadline_text, verification_notes | no | `672.json` |
| 674 | new research | needs_review | needs_review | high | needs_review | deadline_text, deadline_date, verification_notes | **yes** | `674.json` |
| 679 | new research | needs_review | needs_review | high | needs_review | deadline_text, deadline_date, verification_notes | no | `679.json` |
| 693 | new research | needs_review | needs_review | high | needs_review | deadline_text, deadline_date, verification_notes | no | `693.json` |
| 695 | new research | needs_review | needs_review | low | needs_review | deadline_text, deadline_date, verification_notes | no | `695.json` |
| 710 | new research | needs_review | needs_review | high | needs_review | deadline_text, deadline_date, verification_notes | **yes** | `710.json` |
| 711 | new research | needs_review | needs_review | high | needs_review | deadline_text, deadline_date, verification_notes | no | `711.json` |
| 721 | new research | needs_review | needs_review | high | needs_review | deadline_text, deadline_date, verification_notes | **yes** | `721.json` |

### `conflicting` (7)

| id | kind | current status | evidence | confidence | suggested | fields to change | open round on the evidence | evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 147 | new research | needs_review | conflicting | high | conflicting | official_source_url, deadline_text, verification_notes | no | `147.json` |
| 16 | new research | outdated | conflicting | high | conflicting | deadline_text, deadline_date, verification_notes | no | `16.json` |
| 288 | new research | conflicting | conflicting | high | conflicting | official_source_url, deadline_text, deadline_date, verification_notes | no | `288.json` |
| 303 | spot-check (already active) | active | conflicting | high | conflicting | official_source_url, deadline_text, deadline_date, verification_notes | **yes** | `303.json` |
| 422 | spot-check (already active) | active | conflicting | high | conflicting | official_source_url, deadline_text, deadline_date, verification_notes | **yes** | `422.json` |
| 508 | new research | needs_review | conflicting | high | conflicting | deadline_text, verification_notes | **yes** | `508.json` |
| 684 | new research | needs_review | conflicting | high | conflicting | official_source_url, deadline_text, deadline_date, verification_notes | **yes** | `684.json` |

### `active`, field corrections only (7)

| id | kind | current status | evidence | confidence | suggested | fields to change | open round on the evidence | evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 23 | new research | partial | active | high | active | official_source_url, deadline_text, verification_notes | no | `23.json` |
| 366 | spot-check (already active) | active | active | high | active | official_source_url, deadline_text, deadline_date, verification_notes | no | `366.json` |
| 526 | new research | needs_review | active | high | active | official_source_url, deadline_text, deadline_date, verification_notes | no | `526.json` |
| 631 | new research | needs_review | active | high | active | official_source_url, deadline_text, deadline_date, verification_notes | no | `631.json` |
| 643 | new research | needs_review | active | high | active | official_source_url, deadline_text, deadline_date, verification_notes | no | `643.json` |
| 657 | new research | needs_review | active | high | active | official_source_url, deadline_text, deadline_date, verification_notes | no | `657.json` |
| 75 | spot-check (already active) | active | active | high | active | official_source_url, deadline_text, deadline_date, verification_notes | no | `75.json` |

### `quarantined` (2)

| id | kind | current status | evidence | confidence | suggested | fields to change | open round on the evidence | evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | new research | conflicting | quarantined | high | quarantined | verification_notes | **yes** | `31.json` |
| 79 | new research | unverified | quarantined | high | quarantined | verification_notes | **yes** | `79.json` |

## How to apply one record

1. Open the evidence file's row above and read `<id>.md` — the memo names the
   page and quotes the sentences the verdict rests on.
2. Decide the status change, if any. A `needs_review` verdict does not
   automatically mean "promote nothing": several carry a corrected `deadline_text`
   worth adopting even while the status stays where it is.
3. Apply the fields from `recommended_field_updates`, with `verification_notes`
   set from the evidence so the next re-check knows what was read and when.
4. Leave the evidence file in place. It is the source of the change and stays
   with the repository.
5. Do not apply anything for a record whose round has closed unless the
   intention is to close it: the catalogue's promise is that an expired round is
   not offered as live.

## What this plan is not

It is not an approval. The 45 proposals are what the evidence
supports, and the campaign records 100 checks, not a decision. Until a person
has walked this list, `SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED` must stay off — see
`ROLLOUT.md` for what switching it on early would show.
