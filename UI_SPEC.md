# ScholarZone UI upgrade — motion & visual spec

Agreed direction. Recorded here so it survives across sessions.

## Theme: warm editorial, "The Ledger"

Provenance is the product. Every listing is read from the awarding body's own
official page and dated. The design carries that fact.

| Token | Value | Note |
|---|---|---|
| `--page-bg` | `#FBFAF6` | warm paper, replaces Tailwind `gray-50` |
| `--surface` | `#FFFFFF` | card face |
| `--surface-subtle` | `#F3F0E8` | sunk |
| `--text-primary` | `#14130F` | ink |
| `--text-muted` | `#6E6A61` | 5.03:1 on paper |
| `--accent` | `#1B3A5C` | Archive Navy, replaces `blue-600` |
| `--success` | `#3D6B4F` | verified, calm |
| `--radius` | 2–3px | JSTOR standard |
| card shadow | none | hairlines carry structure |

## Signature: the Provenance Rule

A 1px hairline under each listing title, terminating at the right edge in a
6x2px square — **filled** when the record has a validated official logo,
**hollow** when it does not. Beneath it, a monospace provenance line. The
negative state is part of the identity rather than a gap to hide, so no logo is
ever fabricated to fill it.

## Motion — full set, as specified by the user

| # | Motion | Placement | Duration |
|---|---|---|---|
| 1 | Smooth scroll + scroll-linked reveal | whole page | — |
| 2 | 3D sphere | hero, beside the text | loop |
| 3 | Parallax | hero background, section dividers | scroll-linked |
| 4 | Bounce | card hover, primary CTA | 200–400ms |
| 5 | Spin | loading state, hero ornament | 1–8s loop |
| 6 | Infinite drift | hero ornament | 8–20s loop |
| 7 | Card stagger entrance | listing | 40–60ms stagger |
| 8 | Count-up statistics | hero stats | 1000ms easeOutQuart |
| 9 | Logo blur-to-sharp fade | card | 200ms |
| 10 | Filter chip pop, drawer rise | filters | 150–180ms |
| 11 | Card FLIP re-order | sort change | 250ms |
| 12 | Section hairline centre-out | sections | 600ms |

**Rule that is not a restriction but a placement decision:** decorative motion
lives in the hero's decorative layer and behind section dividers — never behind
the listing. Scrolling content that moves with the viewport cannot be compared
across rows, and the catalogue's job is comparison.

`prefers-reduced-motion: reduce` disables all of it except the 1px press
feedback, which is not a vestibular trigger (Airbnb keeps it too).

Easing: `cubic-bezier(0.2, 0, 0, 1)` — the curve Stripe and Airbnb each ship
independently. Durations 75 / 150 / 250 / 400 / 600 / 1200ms.

## Density targets (measured, at 1440x900)

- container 1680px — the current 1200px discards 240px of the viewport and is
  the binding constraint on column count
- 4 columns at >=1260px; card height target 229px
- 12 cards visible per screen versus 4 today
- 13px value floor, 11.5px labels; density comes from column count, not from
  shrinking type
- section gap 160px → 128px (160px on both sides of a boundary is 320px of
  whitespace at 1440)

## Data truth

Four real metrics only: total, countries, fully funded, verified. No "+"
suffix — 401 is a live count. Nothing invented to pad a grid.

## Non-negotiables

- Never touch `vite.config.js` `base` or the `main.jsx` router basename. Two
  separate blank-white-page incidents came from changing those.
- List rendering keys off `image_kind`, not `image_url`. 401 records have an
  image but only 387 are `official_logo`; the rest get no image region rather
  than a monogram, glyph or country photo.
- `verification_status` is `active` for all 401 records, so it carries no
  information and must not drive the verified state.

## Typography — the measurements, not the adjectives

Instrument Serif for display, Inter for everything else. Long copy never goes in
the serif; the serif is display-only. This pairing is what JSTOR runs.

Body scale is JSTOR's 1.125 ladder with **absolute** line-heights, so every
block lands on the same rhythm: `11/16 · 12/18 · 13/20 · 14/20 · 16/24 (body
floor) · 18/26 · 21/26 · 24/28 · 30/34 · 40/40`. Hero is
`clamp(44px, 5.6vw, 68px) / 1.0`.

| Role | Spec |
|---|---|
| Hero headline | Instrument Serif 400, `clamp(44px,5.6vw,68px)/1.0`, tracking −0.035em |
| Section heading | 30/34, tracking −0.02em |
| Stat numeral | Instrument Serif 400, `clamp(2.75rem,4.4vw,4rem)/0.95`, `tabular-nums` |
| Stat label | 12px/600, `+0.085em`, uppercase, on `--surface` not the band |
| Card title | 15px/20px, 2-line clamp, −0.012em |
| Meta label | 11.5px/14px, sentence case, tracking 0 |
| Meta value | 12px/14px, weight 650, `tabular-nums`, right-aligned |
| Deadline well | 9px label + 12.5px/650 value, 2px navy left border |
| Badge | 17px tall, 10px/600, 3px radius |
| Citation line | 11px mono, `+0.04em` |

Line-height grid is 4px. Body tracking −0.02em; labels open at +0.14em.
Type floor is **13px values / 11.5px labels** — density comes from column
count, never from shrinking type.

Meta colour is `#5A6472`: measured 6.00:1 on white, 5.75 on warm paper, 5.65 on
the deadline well. The old `--text-muted #6B7684` was 4.34 on the well and
failed AA.

## Data presentation

The card is the product. Anatomy, top to bottom: official logo → verified badge
→ title → provider → provenance rule + citation line → state badges →
deadline well → paired meta rows → footer action.

Meta layout is a **hybrid** — measured at 329px, inline rows 317px, 2-column
grid 268px, bare badges 270px, hybrid 261px. Hybrid wins: each row carries a
labelled *pair*, so five facts fit in 65px instead of 156px.

Badges are for **state**, never for facts. `FULLY FUNDED` and `VERIFIED` are
state. `Postgraduate` is a fact and belongs in a meta row — which is why Google
Flights, Kayak and Indeed never badge facts.

Card budget: 229px (down from 600). The cliff is at 245px — crossing it drops
from 12 visible cards to 8, a 33% cliff for 5% height. Delete the 600px
`min-height`, drop the description paragraph, halve the horizontal padding.

Section gap: 160px → **128px**. At 1440px, 160px on both sides of a boundary
is 320px of whitespace, which is the single biggest reason the page reads as
empty. Prefer a 1px rule over padding — space without structure reads as
padding, a rule reads as composition.

## Current state

Production `16464df`, healthy. Token layer, `--brand` alias fix and the App.css
gradient fix are applied but **uncommitted**; everything else is outstanding.