# Live verification campaign — 12 October 2026

## What was done and what it shows

ScholarZone published 618 public scholarships. 527 carried `verification_status:
active`; **91 carried a non-active status** (`needs_review`, `pending`,
`conflicting`, `partial`, `outdated`, `unverified`) and still showed to users,
each labelled with what had not been re-checked.

**One hundred research agents** verified records against the awarding bodies'
own pages: 91 records whose status was not active, plus a spot check of nine
records already marked active. Every record has an evidence file in this
directory — a machine-readable `<id>.json` following the schema in
`BRIEF.md`, and a short `<id>.md` memo naming the pages read and the exact
sentences the verdict rests on.

## Results

The 100 checks, split by what each one was. The counts are recomputed from the
`<id>.json` evidence files by `backend/tests/test_campaign_report_consistency.py`,
so a document that drifts from the data fails CI.

| verdict | meaning | all 100 | 91 newly researched | 9 spot-checks |
| --- | --- | --- | --- | --- |
| `active` | awarding body, deadline, eligibility, funding and levels all agree with the record, for a currently-open cycle | **62** | **58** | 4 |
| `needs_review` | official page read, but a claim cannot be confirmed from it | **29** | **26** | 3 |
| `conflicting` | the official page contradicts the record materially | **7** | **5** | 2 |
| `quarantined` | no official page can be found | **2** | **2** | 0 |

Confidence: 98 high, 1 medium, 1 low. No verdict was recorded from a search
snippet alone.

## The finding that matters most

**The spot check: 9 records already marked active were re-read at random. 5 of
9 did not survive.** Two contradictions and three unconfirmable deadlines were
found among records the catalogue presents as verified (ids 303 and 422
contradicted; 131, 189, 245 unconfirmed). A 5-in-9 failure rate in a small
random sample is not a rounding error — the existing `active` state should not
be treated as trustworthy, for the users who are being asked to trust it.

That cuts the other way too, and it is the reason the flag this PR wires stays
off by default:

- **Before**, an unverified record was visible with an honest label ("Confirm
  with provider") and a date.
- **If the flag is switched on today**, those 91 disappear — and **58 of those
  91**, not 62, carry fresh evidence that they are correct. (The 62 figure is
  the total across all 100 checks; 4 of them are spot-checks of records that
  were already active.)

Promoting the 58 on their evidence, and asking what the other 33 should
become, is the human decision that follows this campaign. `ROLLOUT.md` sets out
the order in which those decisions have to be made, and what happens if the flag
is switched on before them. This PR deliberately makes none of them.

## What the evidence found

Material contradictions include well-known programmes: MSCA Postdoctoral
Fellowships (16), Budapest University of Technology and Economics (288), the
Mauritius-Africa Scholarship Scheme (684), the Flanders Trainee Programme
(508), the Camões scholarship (303), the UNESCO/Poland fellowships (422).
Two records could not be traced to any official page and are marked
`quarantined`: the Netherlands Fellowship Programme (31) — the programme ended
for most countries — and the Edinburgh Global Research Scholarship (79),
which was discontinued. Both are now marked with the reasoning rather than
being quietly left as live.

## The verified-only switch

`SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED` already existed in configuration but was
never wired to the canonical predicate, so setting it did nothing. It is wired
in `app/repositories/scholarships.py`: when it is on,
`public_visibility_conditions()` also requires
`verification_status == "active"`. Default off — no behaviour change, and the
existing test suite passes unchanged for the default path.

Turning it on would show a catalogue whose every record carried `active` — the
status the catalogue writes, not the status the evidence supports. Those are not
the same thing today, and the difference is exactly the five spot-check records
that are still `active` in the database while this campaign's evidence says
otherwise. Read `ROLLOUT.md` before setting the variable: merging this PR
applies nothing, and switching the flag on before a reviewed status update
would keep those five exposed while hiding records this research just supported.

## What this PR does not do

It writes no database, changes no record, and deploys nothing. The proposed
updates are in `proposed-verification-updates.json`, per record, for review;
`RECONCILIATION-PLAN.md` is how to walk them. Applying them is a separate,
human decision, record by record — a verdict label is not a promotion.

## Files

- `BRIEF.md` — the method every agent followed
- `ROLLOUT.md` — the order in which the decisions have to be made, and what
  breaks if they are not
- `RECONCILIATION-PLAN.md` — the per-record plan for the 45 proposed updates,
  with what needs a human at each step
- `index.json` — the 100 tasks (record, kind, title, country, source URL)
- `tasks-to-verify.json` / `tasks-spot-check.json` — the record fields each
  agent was given
- `<id>.json` — one evidence file per record, same schema for all 100
- `<id>.md` — the same finding as a memo for a person to read
- `campaign-report.json` — the aggregate, including which records are missing
  evidence and which verdicts disagreed
- `proposed-verification-updates.json` — the 45 records whose status or fields
  the evidence supports changing

## Limitations

- 5 of the 100 evidence files were written by the orchestrator rather than an
  agent (508, 510, 516, 543, 131); those agents did not deliver. They follow
  the same schema and cite the same official pages.
- One evidence file (id 498) arrived with a JSON syntax error and was repaired
  — the content is the agent's, unchanged.
- A verdict is only as good as the page on its reading day. Deadlines move;
  the `checked_at` timestamp in each file is the one this campaign stands by.
- The spot-check sample is nine records. It is enough to disprove "the active
  state is reliable", not enough to measure how often it fails.
