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

## Current state

Production `16464df`, healthy. Token layer, `--brand` alias fix and the App.css
gradient fix are applied but **uncommitted**; everything else is outstanding.