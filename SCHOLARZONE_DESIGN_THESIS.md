# SCHOLARZONE_DESIGN_THESIS.md

The design thesis, written after the fifty live research tracks and before the
implementation that followed. Evidence is in
`SCHOLARZONE_50_AGENT_RESEARCH_SYNTHESIS.md`.

---

## 1. What ScholarZone looks like

**A research desk, not a marketing page.** A dense, full-width catalogue on
warm paper, set in one editorial serif for identity and one neutral sans for
everything a reader has to scan. Ink-black rules, one gold accent that marks a
state and nothing else. No cards in the result list, no badges on records, no
shadow anywhere except the one panel that genuinely floats.

The register is a newspaper's data desk, not an app's dashboard: high
information density, hairline structure, a serif that only ever carries a
headline, and a single recurring micro-field — the date the record was last
read — that appears on every row in the same place.

## 2. What makes it different from every directory researched

Fifteen scholarship and education platforms were fetched live. Every one of
them makes **unverifiable claims**: visitor counts, "91% of learners achieved a
positive outcome", star ratings, "credibility scores", logo walls.

ScholarZone can publish something none of them will, because it would expose
its own staleness:

> **Every record states where it came from and when that was last true.**

`daad.de · checked 12 Aug 2026`. A hostname a reader can open, and a date they
can hold us to. That is the asset, and the design is arranged around it rather
than around decoration.

The second differentiator is honesty about what is unknown. A record with no
provider prints nothing there rather than "Unknown" — because an empty field is
not evidence of absence, and we learned that the list endpoint simply does not
return the field (0 of the first 100 records carry it, while the detail
endpoint returns it for the same records).

## 3. Primary visual rhythm

One rule, then a count, then records. That is the whole page.

```
masthead 64px ─────────────────────────────── hairline
eyebrow · All Scholarships          Looking for what fits you?
search ────────────────────────────────────────  [Filters]
REFINE              381 scholarships         SORT BY
┌────────┐ ┌────────────────────────────────────────────────────┐
│ COUNTRY│ │ title                       country │ funding │ deadline │ read │
│ DEGREE │ │ provider / country         ───────────────────────────────────  │
└────────┘ └────────────────────────────────────────────────────┘
```

The vertical rhythm is 8px for internal steps, 16–24px between blocks, and
the section gap is a single token. The horizontal rhythm is a 4px base with
1px hairlines carrying all structure.

## 4. The row system

Five fixed slots. One elastic column. This is the GOV.UK/USWDS/Primer table
contract applied to a list, and it is what makes twelve records scannable in a
screen instead of two.

| Slot | Width | Content | Rule |
|---|---|---|---|
| logo | 56px | official mark, **only when one exists** | no monogram, no glyph, no country photo |
| identity | `minmax(0,1fr)` | title (2-line clamp) + provider | the ONLY elastic track |
| facts | 240–300px | country · funding · deadline | **no labels** — the order carries the meaning |
| provenance | 128px | source host + last-read date | the trust slot; never removed for density |
| action | 44px | Save | the whole row navigates |

**No labels on the facts.** Three hanging `Country`/`Funding`/`Deadline` pairs
cost ~150px, and in a 240–300px track that is the difference between values
and ellipses — measured, not assumed.

**Zero badges.** `Open` restated a deadline already on the row; `Verified`
restated the line beneath it. A status chip is for a state that is not
otherwise visible, and no scholarship record has one.

**The deadline is the only emphasised value**, because it is the only
irreversible field.

## 5. Type system

Two families. Instrument Serif **display-only, never below 24px** — it ships
one weight, so hierarchy cannot come from weight, and its 0.510em x-height
meets 1× DPR as mush below 20px.

| Role | Size | Family | Tracking |
|---|---|---|---|
| Display | clamp(2rem → 3.5rem), **×1.07 optical** | Serif | −0.018em |
| Page title | clamp(1.5rem → 2.5rem) ×1.07 | Serif | −0.014em |
| Section | clamp(1.5rem → 2rem) ×1.07 | Serif | −0.01em |
| Lead | 18/28 | Inter | 0 |
| Card + row title | 17/24 w500 | Inter | −0.006em |
| Body | 16/26 | Inter | 0 |
| Small | 15/22 | Inter | 0 |
| Label / eyebrow | 12–13/16–18 | Inter | **+0.055em**, uppercase |
| Citation / host | 12/18 mono | — | +0.01em |

Three corrections came from reading the actual font tables and the actual CSS
of ten premium sites, not from taste:

- **Display leading is 1.10, not 1.02.** The serif's own ascender 0.990 +
  descender −0.310 gives a 1.300em box against Inter's 1.210em; at 64px on
  1.02 the descender of line one overlaps the cap of line two by 0.7px.
- **Body tracking is 0, not negative.** No measured system uses negative
  tracking between 17 and 19px — the counters close there. Negative belongs at
  display sizes only.
- **The eyebrow was tracking at 0.14em, roughly 2× the largest value found on
  any premium site.** That alone read as "uncomfortable letters" on a warm
  ground. It now uses the label token.

The **×1.07 optical factor** exists because the serif's x-height is 0.510em and
its lowercase `n` is 20.5% narrower than Inter's: at equal size it sets 1.26×
more characters per line and reads small. The factor lives in the serif rules,
not in the tokens, so a non-serif consumer of the same token is unaffected.

## 6. Shape system

Six steps, one name each. The ladder is editorial (0 / 4 / 8 / 14 / 22 / 999)
because the product's register is print, and the dense-control sub-ladder
(4 / 6 / 8 / 12 / 16) is available for small surfaces.

**Pills are for state only.** A pill on a nav item, a tab or a badge would put
the same shape on a container and a control. Bands and rules are 0. Nothing is
a card in the result list.

Elevation is **luminance, not shadow**. `--surface-raised` is lighter than
`--surface`, which is lighter than `--page-bg`. The build carries one shadow
token, used for the scrolled masthead and the mobile drawer.

## 7. Motion system

Four motifs. Five durations. Three easings.

| | |
|---|---|
| **Instrument sweep** | 1px gold rule draws once under the masthead, 640ms |
| **Ledger reveal** | rows rise **24px** + fade, 400ms, 60ms stagger capped at 360ms |
| **Mask wipe** | the headline's three lines, `clip-path` 0→100%, 700ms, 90ms stagger |
| **Hover** | luminance shift + a 2px left bar, 140ms, gated on `(hover: hover)` |
| **Count-up** | 420ms, easeOutCubic, once per mount, tabular throughout |

Every value is inside a measured band: perceived travel is 16–100px at
150–250ms, NN/g caps general transitions at 400ms and says 500ms "feels like a
real drag", press feedback must land inside 100ms, and under ~230ms nothing is
perceived at all.

**The previous pass failed this test numerically**: 12px over 420ms is 29px/s
— about one pixel per frame, inside the pre-attentive window. It read as a
layout shift. It is now 24px over 400ms with a measured stagger.

**Reduced motion substitutes rather than deletes** (Apple: "removing animations
entirely can have a negative effect on usability"): travel goes, 120ms
opacity and colour stay. Five duration tokens collapse to 1ms, so the decision
rides on variables with zero per-component overrides.

**The reveal invariant is inverted from the 2.0 failure**: CSS renders
`[data-reveal]` as **visible**, and only `html.js-motion` — added by the
observer module itself, after confirming a working IntersectionObserver — hides
anything. If the module never runs, nothing is ever hidden.

## 8–11. The four widths

| | 1920 | 1440 | 1280 | 1024 | 768 | 390 / 412 |
|---|---|---|---|---|---|---|
| Page head | 85px | 85px | 85px | 129px | 127px | 55–75px |
| First record at | y=339 | y=339 | y=339 | y=383 | y=373 | y=357–418 |
| Row height | 89px | 89px | 115px | 115px | 115px | 107px |
| **Rows visible** | **9** | **7** | **4** | **4** | **6** | **4–6** |
| Filter rail | 224px | 224px | 224px | drawer | drawer | sheet |
| Gutters dead | 6% | 7% | 7% | 7% | 5% | 0% |

**Why the rail moves to 1280 and not 1024.** M3 states that in a medium layout
"a single pane is recommended because of limited screen width"; GOV.UK adds
nothing at 1024 and centres; Bootstrap and Polaris both put their first
large step at 1040. And the arithmetic is decisive: at 1440 with a 240px rail
the results column is ~950px, which cannot hold the row's five tracks, so
every row folds and only three are visible. The rail was costing the list a
third of its width to hold five selects. Grants.gov needs 1,469 rows and
twelve facet groups to earn that space.

**Why 1280 gets 115px rows and 1440 gets 89px.** At 1280 the results column
is 855px, below the 900px the five-track row needs, so it folds to three
tracks — still two content lines, not three. At 1440 the column clears 900px
and the row takes its full form.

**Why mobile gets 107px rows and 4–6 visible.** The phone row drops the
provenance line and the save toggle and keeps logo, title, country, funding,
deadline. Research across three clusters was unanimous that a small screen
should hold **fewer navigation destinations, not smaller ones** — Khan
Academy moved search out of its tab bar, Apple News hides the channel list on
iPhone and gains a sidebar on iPad rather than columns.

**Body copy never shrinks.** GOV.UK holds 19px on both sides of its 640px
boundary and steps only display sizes down. We follow that: 16px body at 390
and at 1920.

## 12–13. Empty and error

Four causes, four copies, one component. The industry taxonomy (Prism,
Supabase, vocab.design): `no-results`, `zero`, `unavailable`, `denied`.

The rules the state research was unanimous on:

- **Never wipe the search field.** A typo is the likeliest cause and the field
  is the reader's only record of what they typed. The no-results state echoes
  the query and names the active filters as removable.
- **Name the resource, not the failure.** Not "Something went wrong" — "The
  catalogue could not be loaded", with what still works ("your filters are set
  and nothing has been lost") and one retry.
- **Never declare emptiness while loading.** NN/g: inaccurate status messages
  cause severe distrust. A refetch dims the existing rows rather than
  replacing them with an empty state.
- One primary action, at most one secondary. Recovery verbs are `Verb + Noun`
  and never "Get Started", "Continue" or "OK".

## 14. How trust is preserved

The owner's rule is absolute: **if density conflicts with trust, trust wins.**

| Trust element | Where it lives | Can it be cut for density? |
|---|---|---|
| Official-source host | row, 128px column, as a real link | **No** |
| Last-read date | row, beside the host | **No** |
| Verification status | row, in the same line as the date | **No** |
| Deadline, verbatim | row, one line, never paraphrased | **No** |
| Funding, verbatim + "stated by provider" | row, unbadged | **No** |
| Full eligibility / coverage | detail page | Yes — that is what disclosure is for |

What was cut was **duplication**, not evidence: two badges restating a fact
already on the row, and a 6×2px glyph that asserted provenance no reader could
check. Density improved because the row stopped saying the same thing three
ways.

## 15. Where Count Intelligence belongs

**Not on the home page.** The hero carries one mono line of counts and nothing
else. Count Intelligence belongs on the **Match results page**, where it
explains a specific profile against a specific set of records — that is where a
number has something to be a number *about*.

It does not currently occupy a catalogue insight rail. An empty 300px column
was measured twice and removed twice: it takes width from every row and
returns nothing. If it is ever added it must be populated with real counts, not
reserved.

## 16. Where deadlines belong

The row, once, as the only emphasised value — plus the detail page in full
verbatim. Never relative alone, never a countdown that resets, and **never
coloured when it is not a parseable date**: a deadline value of "Varies by
programme — typically Dec–Feb" is *unknown* urgency, which is strictly worse
than known-far, and colouring it calm asserts something we cannot source.

## 17. Immediately scannable, and 18. deliberately not shown

**Scannable in one vertical pass:** title → deadline → country → funding →
when it was last read.

**Deliberately not on the row:** degree level (it is a long free-text string in
this corpus and belongs on the record), full eligibility, the description,
the verification state's label as a badge, the comparison toggle, and any
second rendering of the deadline.

Every element on the row must justify its width. The test applied was simple:
**if removing it would remove a fact a reader could not get elsewhere, it
stays; if it only restates something else on the row, it goes.**
