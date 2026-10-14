# ScholarZone — Editorial Visual System 2.0

This document is the contract for the redesign. It replaces `UI_SPEC.md` as the
active design reference; `UI_SPEC.md` is retained only for the non-negotiables
recorded in its final section.

Scope is visual and UX only. Match 2.0 logic, Count Intelligence, verification
contracts, scholarship data and public visibility rules are untouched.

---

## 1. The diagnosis, measured

Captured against the running app at 1440×900 before any change.

| Symptom in the brief | What is actually on screen |
|---|---|
| too card-heavy | 41 distinct bordered boxes on the home page; every fact has its own container |
| too square/boxed | the nav is itself a rounded pill box, the hero preview is a stack of four overlapping boxes |
| visually noisy | hero eyebrow + headline + subhead + 2 CTAs + a fake product preview + 4 stat chips + 3 browse tag rows, all above one fold |
| overly animated | `App.css` paints three drifting radial washes plus a 46s sheen behind every page; `ScholarZoneHero` adds a 3D sphere; `AmbientOrbs` exists |
| typography lacks hierarchy | five type treatments competing in the hero alone |
| features feel scattered | Verification, Why ScholarZone, Featured, Collections, Browse, Decide, Stats, CTA — eight equal-weight bands |
| data presentation feels cheap | stats appear twice on one page (trust bar + stats section) as four identical tiles |
| more than an education platform | the page reads as marketing chrome wrapped around a directory |

Two measurements that define the ceiling of the current build:

- **11,831px** of home page at 1440 wide. Roughly nine screens, of which a large
  share is empty: the reveal-on-scroll wrapper never fires for content already
  in view on fast scroll, leaving voids rather than sections.
- **2 of the 4** hero preview cards render overlapped and mis-clipped.

Whitespace without structure reads as padding. Structure without content reads
as a bug. Both are present.

---

## 2. Direction

**An editorial scholarship catalogue.** The reference is not a SaaS dashboard; it
is a printed prospectus and a research journal. Authority comes from typography,
proportion, evidence and rule-work — not from surfaces.

Three rules govern every decision below.

1. **A box is a claim.** Nothing gets a border and background unless it is
   physically a thing (a photograph, a record in a list, a control) or unless the
   border is a rule that composes the page. Grouping is expressed with space and
   alignment.
2. **One accent, used rarely.** Gold appears on: the active nav item, one primary
   action per view, the verified marker, and the focus ring. Nowhere else.
3. **Content is denser than the frame.** The frame gives up space so the
   catalogue can hold more, not less.

### Composition types (only three)

| Type | When | Structure |
|---|---|---|
| **Editorial section** | Anything that argues or narrates | full-bleed rule, eyebrow, display heading, optional standfirst, then content on a grid. No container. |
| **Structured data block** | Anything that is a fact table | label/value rows on a fixed 2-column grid with hairline row separators. No container. |
| **Selective card** | Only where the object is a discrete record with a physical boundary | scholarship result row, photograph, action cluster |

A card requires all three: it is a record, it is individually selectable, and it
would lose meaning flattened into a list. Nothing else qualifies.

---

## 3. Colour

Warm paper, near-black ink, one academic gold. Neutrals do all the structural
work; gold is punctuation. Navy is reserved, not competing.

Three colours carry meaning and no others do:

- **Ink** — near-black for display and body. `#14130F`.
- **Navy** `#1B3A5C` — the brand's structural colour, spent in exactly two
  places: an inverted band, and the one primary fill a viewport is allowed.
- **Gold** `#A8842C` — the accent. Four uses, nowhere else: the active nav
  item, the provenance rule's filled terminal, the eyebrow label, and the
  focus ring. `--sz-gold-ink` `#7A5F1E` is the text-safe variant (5.4:1).

That split is the load-bearing decision. If the primary button were navy *and*
the inverted band were navy, the two would compete for the same reading of
"important". So the primary fill is ink and navy is only ever a ground.

```
paper        #FBFAF7   page
paper-raised #FFFFFF   the only raised surface
paper-sunk   #F4F1EA   wells, table head
ink          #14130F   display + body
ink-2        #3E3B34   secondary text
ink-3        #6E6A61   captions, metadata   (5.0:1 on paper)
ink-4        #9A958A   rules-adjacent labels only, never body copy
rule         #E2DDD2   hairlines
rule-strong  #CFC8B9   the one structural divider
gold         #A8842C   accent — rules, active state, verified mark
gold-ink     #7A5F1E   accent text on paper
green        #3D6B4F   verified state only, calm, never neon
amber        #8A5A16   closing soon / confirm with provider
red-clay     #8C3A2E   closed
```

Dark mode is a first-class peer, not an inversion: `#0C0B09` warm near-black
ground, `#F5F1E8` ink, navy lightened to `#D8E3EF` because a dark navy fill on a
near-black ground has no contrast, and gold lifted to `#C9A24A` so it survives
on the dark field.

**Accent budget per viewport: one.** A gold nav underline and a gold eyebrow in
the same section is the practical ceiling. Everything else is ink on paper.

Three semantic colours and nothing else. No fourth state gets a colour, and
none of the three is ever used as a fill behind a whole panel.

---

## 4. Typography

Two families, no third. Instrument Serif is **display only** — it never carries
body copy, a label, or a metadata value, because a serif at 11px is worse than a
sans at 11px. Inter carries everything else.

```
Display XL   Instrument Serif 400   clamp(3.25rem, 6.4vw, 5.25rem) / 0.98   -0.035em
Display L    Instrument Serif 400   clamp(2.25rem, 3.6vw, 3.25rem) / 1.02   -0.028em
Heading      Instrument Serif 400   clamp(1.75rem, 2.4vw, 2.25rem) / 1.10   -0.022em
Subheading   Inter      600        1.0625rem / 1.55                          -0.011em
Body         Inter      400        1rem / 1.65
Body small   Inter      400        0.9375rem / 1.6
Caption      Inter      400        0.8125rem / 1.5
Metadata     Inter      500        0.75rem / 1.35      +0.055em uppercase
Citation     ui-monospace 400      0.6875rem / 1.45    +0.03em
```

Rules:

- Line-height grid is 4px. Every value above lands on it.
- Type floor is **13px for values, 11px for labels**. Density comes from column
  count and from removing containers, never from shrinking type.
- Numerals in data contexts are `tabular-nums` so columns of figures align.
- The serif is never italic except for a single emphasised word in the hero, and
  never for a scholarship name — names are read, not styled.
- Fluid sizing is used for the three display sizes only; everything below
  `Subheading` is a fixed step.

---

## 5. Spacing

4px base, named `--space-1` … `--space-24`. The scale is long because it is used
consistently, not because it is rangey: 4, 8, 12, 16, 20, 24, 28, 32, 36, 40,
48, 56, 64, 80, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384.

Section rhythm lives in its own four tokens rather than in `--space-*`, because
a section gap that is decided twice is a section gap that is wrong on one of the
pages that uses it.

| | desktop | ≤900px | ≤640px |
|---|---|---|---|
| `--sz-section-gap` — between sections | 112 | 88 | 68 |
| `--sz-section-lead` — rule to first heading | 72 | 56 | 40 |

Mobile is not the desktop ladder halved. A 112px gap on a 390px screen is a
quarter of the viewport spent on nothing, so the phone ladder is separately and
deliberately shorter.

Container: `min(100% − 2×gutter, 1320px)`, gutter 24px desktop / 20px tablet /
16px mobile. The catalogue and comparison page break out to 1560px because the
job there is comparison; nothing else does.


---

## 6. Motion

Purposeful only. The permitted list is short and every entry is a state change
the user caused:

| Allowed | Duration | Easing |
|---|---|---|
| route transition (content fade + 8px rise) | 260ms | `cubic-bezier(0.22, 0.61, 0.36, 1)` |
| filter / sort re-order | 200ms | same |
| results count change | 180ms | same |
| image reveal (blur 6px → 0, opacity 0 → 1) | 320ms | same |
| hover state (colour, 1px rule, opacity) | 140ms | `ease-out` |
| progressive loading (skeleton → content) | 240ms | same |
| press feedback (1px translate, 60ms) | 60ms | `ease-out` |

Forbidden: bounce, float, spin, pulse, glow, scale-up, parallax, count-up
number roll, staggered card cascade, animated gradient, scroll-progress bar.

Nothing on the page animates when the user is not interacting. There is no
ambient loop anywhere in the product. Under
`prefers-reduced-motion: reduce` every duration above becomes 0ms except press
feedback, which is not a vestibular trigger.

**The page must look finished and expensive with all animation removed.** That is
the test, because a reader on a low-power device, a screenshot in a university
prospectus, or a print stylesheet sees exactly that state.

---

## 7. Page hierarchy

### 7.1 Home — `1440`

```
MASTHEAD  sticky 64px (56px scrolled), hairline base, no box, no pill
           brand left · Scholarships Match Countries · Saved Compare
           Sign in · theme. Active item = 2px gold rule under the text.
─────────────────────────────────────────────────────────────────
01  HERO
    eyebrow                  VERIFIED SCHOLARSHIP DISCOVERY
    display XL               Verified scholarships.
                             Trusted information.
                             Better decisions.
                             three lines, one break each, 15ch measure
    standfirst               56ch, 17px
    SEARCH                   full content width, 1 field 56px +
                             [Search the catalogue] — the only filled
                             control in the section
    NARROW IT DOWN           Country · Degree · Funding · Deadline, on one
                             hairline, labels above, plus [View results].
                             These NAVIGATE to the catalogue; they do not
                             filter here.
    ──────────────────────────────────────────── rule
    FIGURES                  Open now · In the catalogue · Countries ·
                             With an official source — one editorial
                             numeric line, not four tiles
─────────────────────────────────────────────────────────────────
02  WHAT IS OPEN NOW         Editorial section
    eyebrow                  IN THE CATALOGUE
    heading + standfirst     action: All 481 →
    TABS                     Recently added · Closing soon · Fully funded ·
                             Everything. ONE edition open at a time —
                             four grids of three cards was the layout that
                             made this page read as a dashboard.
    5 result rows            dividers only, plus a note naming the sort
─────────────────────────────────────────────────────────────────
03  WHERE THE FUNDING IS     Editorial section
    6 lead destinations      name + count on hairlines, largest count first.
                             No flags (regional indicator pairs render as
                             letters off Apple platforms) and no
                             photographs (a stock city image is not
                             evidence).
    destination index        the remaining countries, 5-6 columns of
                             type-only rows with counts
─────────────────────────────────────────────────────────────────
04  WHERE EACH LISTING CAME FROM
    4 numbered steps         a sequence on a rule, no cards, no icons
    + one real specimen      a live record quoted, framed because it is an
                             artefact rather than an argument
─────────────────────────────────────────────────────────────────
05  ONE JOURNEY, NOT FIVE PRODUCTS
                             FULL-BLEED NAVY — the only inversion on the
                             page, and it runs edge to edge so it reads as
                             a change of room rather than a section with a
                             dark background
    DISCOVER → MATCH → UNDERSTAND → PREPARE → APPLY
    5 columns, one rule each, one CTA each. Match carries the weight:
    the only filled button in the band, because it is the only step that
    asks something of the reader before it gives anything back.
─────────────────────────────────────────────────────────────────
06  WHAT IS ACTUALLY HERE
    Figures restated with their units, because a number without its unit
    is decoration. [Browse the catalogue] + [Check what fits you]
```

Every figure above comes from `GET /scholarships/stats`. `useScholarshipStats`
declares nine fields; only those may ever be printed.

**No scroll-reveal on this page.** A section that fades in as it enters the
viewport cannot be compared, cannot be printed, cannot be screenshotted for a
university prospectus, and leaves a blank page for anyone who scrolls fast or
reads with a keyboard. Both reveal systems that existed (a module-level
IntersectionObserver writing `is-in`, and a page-local one writing
`is-visible`) are removed.

### 7.2 Home — `390`

```
MASTHEAD  56px, brand left, MENU right; sheet opens below the hairline
─────────────────────────────────────────────────────────────────
01  HERO
    display XL  clamp → ~2.9rem, three lines
    standfirst  17px/1.65
    SEARCH      full width, 52px, button stacked full-width below it
    FILTERS     2×2 grid of hairline selects + full-width [View results]
    FIGURES     2×2 numeric grid, no dividers, no tiles
─────────────────────────────────────────────────────────────────
02  WHAT IS OPEN NOW   5 rows, single column
03  DESTINATIONS       6 leads, then a 2-column index
04  PROVENANCE         numbered list, 36px index column
05  JOURNEY            vertical, 5 steps, one rule each
06  FIGURES            stacked numeric composition, full-width actions
```

No horizontal overflow at any width. No text below 13px for a value or 11px for
a label. Every touch target ≥ 44px.


### 7.3 Catalogue — `1440`

```
MASTHEAD
─────────────────────────────────────────────────────────────────
PAGE HEAD        eyebrow SCHOLARSHIP CATALOGUE
                 display L  All Scholarships
                 standfirst, then the "Looking for what fits you?" aside
                 on a hairline
─────────────────────────────────────────────────────────────────
SEARCH           full content width, 56px — above the rail, so the one
                 control a reader reaches for is never trapped in it
─────────────────────────────────────────────────────────────────
┌ RAIL 240px ─────┬ RESULTS ──────────────────────────────────────┐
│ COUNTRY         │  481 scholarships            SORT BY          │
│ All countries   │  ───────────────────────────────────────────  │
│ DEGREE          │  [logo] Erasmus Mundus Joint Masters   OPEN   │
│ All degrees     │         ── provenance rule ──               │
│ FUNDING         │         official source captured · 2026-10-04│
│ DEADLINE MONTH  │         DEADLINE FUNDING COUNTRY DEGREE      │
│ STATUS          │         27 Feb… Fully… EU… PG only    Verified│
│ Reset all       │  ─────────────────────────────────────────  │
│ (sticky)        │  [Save] [Compare]              Details →    │
└─────────────────┴──────────────────────────────────────────────┘
```

Below 1024px the rail drops above the results as a single column; below 560px
its five controls become a 2×2 grid. The rail has no background and no border
of its own — it is a column of labels and hairline selects against the page,
which is what makes it read as a table of contents rather than a panel.

The count is the largest type in the region. On a catalogue page "how many" and
"which" are the only two questions a reader has, and the count answers the
first. Page numbers are not listed: the catalogue is sorted by relevance and a
jump to page 19 is not a destination anyone chooses deliberately.

The result row, not a card:

- 88px square image region, rendered **only** when the record has an
  `image_url`. No monogram, no country photo, no placeholder glyph — an absent
  image yields no frame at all, so the region becomes alignment space and every
  title in the list still starts on the same vertical. If the URL fails to load
  the frame loses its border for the same reason: a tinted square in a column
  of logos reads as an image we hold and cannot show.
- Scholarship name: sans 17px/600, two-line clamp. The largest thing in the row.
  A scholarship name is *read*, not styled — it is not a display-serif
  treatment, because the record also has to render in a 2-line list and a serif
  set small is worse than a sans set small.
- Institution: `--text-sm`, `ink-2`, 4px beneath the name.
- Provenance rule: a 1px hairline under the title, terminating at the right edge
  in a 6×2px square — filled when a validated official logo exists, hollow when
  it does not. Beneath it, the citation line in mono.
- Facts: four labelled pairs on five equal tracks, **Deadline taking two**,
  because the deadline is the field a reader scans for first and the one most
  likely to hold a sentence rather than a date. Values clamp to two lines; the
  full text is on the detail page.
- Verification state as a sentence at the right, not a chip.
- **Badges carry state only.** `Open` / `Closing soon` / `Closed` are states of
  a listing and are badged. `Fully Funded`, `Master's`, `India` are facts about
  the award and sit in the data row in the same type as every other value — a
  chip on a fact makes it read as a selling point rather than as something the
  applicant has to check.
- One action: `Details →`, right-aligned. `Save` and `Compare` sit quiet at the
  left as 36px hairline toggles (44px on a phone).
- Row separator: 1px `--border`. Hover lifts the paper to raised and turns the
  title gold, 140ms, nothing moves.

### 7.4 Detail — `1440`

```
MASTHEAD
─────────────────────────────────────────────────────────────────
MASTHEAD BLOCK
    eyebrow      INDIA · UG/PG/PHD
    display L    ICCR Scholarship (Suborno Jayanti Scheme)
    subheading   Indian Council for Cultural Relations (ICCR)
    state        Verified · Open · Verified Oct 4, 2026
    action       [Apply on the official site]  Save  Compare
─────────────────────────────────────────────────────────────────
┌ RECORD 1fr ──────────────────────┬ ASIDE 400px ──────────────────┐
│ APPLICATION DEADLINE  27 Feb …   │ (figure, or one line saying    │
│ FUNDING              Fully Fund. │  there is no image)            │
│ STUDY LEVEL          UG/PG/PhD   │ ─────────────────────────────  │
│ COUNTRY              India       │ OFFICIAL SOURCE                │
│ …                                │  a2ascholarships.iccr.gov.in   │
│ ───────────────────────────────  │  https://…                     │
│ ABOUT · Overview                 │  [Open the official page ↗]    │
│ prose, 68ch measure              │ ─────────────────────────────  │
│ BEST FIT (gold left rule)        │ OTHER OFFICIAL PAGES           │
│ ───────────────────────────────  │ Official source      host      │
│ FUNDING SUPPORT │ WHAT IT PAYS   │ Programme catalogue  host      │
│ Benefits        │ Coverage       │ ─────────────────────────────  │
│ ───────────────────────────────  │ Supervisor discovery           │
│ ELIGIBILITY                      │                                │
│ REQUIREMENTS │ DOCUMENTS         │                                │
│ …                                │                                │
└──────────────────────────────────┴────────────────────────────────┘
CLOSING BAND — full navy, one statement, one action
```

Every band is separated by a 1px rule and 64–72px of air. There is no panel
stack, no box around eligibility, no box around requirements. `align-content:
start` on every block, because a stretched grid otherwise distributes the extra
height into its rows and pushes a heading 24px below its neighbour for no reason
a reader could name.

The aside is sticky above 900px. Below that the figure becomes a lead image and
the two columns collapse to one.

The EvidenceBlock is the **only** framed thing on the record besides a
photograph, because it is an artefact — a host, a dated citation, a link the
reader can check — rather than an argument.


---

## 8. Design system

Replaces the `Glass*` family (never imported, ~690 lines of designed-but-dead
CSS), the `AmbientOrbs` loop, the `sz-ambient` gradient field, the `Ledger.css`
override stack and the `styles/responsive.css` correction layer. In their place:
`components/ui/index.jsx` and `components/ui/primitives.css`, imported from
`main.jsx` immediately after `theme.css`.

The type ladder lives in `theme.css` as classes — `t-display`, `t-display--l`,
`t-heading`, `t-subheading`, `t-body`, `t-caption`, `t-meta`, `t-citation`,
`t-eyebrow`, `t-prose`, `t-pair`. **They are the only rules in the system that
set font-size.** There is no seventh step and no one-off value.

| Primitive | Export | Contract |
|---|---|---|
| `Button` | `Button` | `primary` (ink fill), `secondary` (hairline), `quiet`, `link`. 48px. Renders `<Link>` given `to`, `<a>` given `href`, `<button>` otherwise — so the same intent is a real link in a list and a real button in a form. One `primary` per viewport. |
| `Field` | `Field` | label above, control below, hint below, hairline base. `as="select"` draws its own 1.5px chevron because the native triangle reads as a system artefact next to line work. |
| `SearchField` | `SearchField` | 56px (52 on a phone), hairline, leading glyph, clear affordance, Escape handled by the caller. |
| `Badge` | `Badge` | **State only.** `verified`, `open`, `closing-soon`, `closed`, `funding`, `neutral`. Facts never wear badges. 11px, the label floor. |
| `StatusRule` | `StatusRule` | the provenance signature: a hairline terminating in a 6×2px square, filled or hollow. |
| `SectionHeader` | `SectionHeader` | eyebrow · heading · standfirst · optional action, on a grid so the action sits on the heading's baseline. |
| `Figure` / `Figures` | `Figure`, `Figures` | large integer + label, `tabular-nums`. No tile, no background, no border, no icon, no colour of its own. |
| `DataBlock` | `DataBlock` | label/value rows on hairlines. The system's substitute for a stack of fact containers. Filters out empty rows so it never renders a shell. |
| `EvidenceBlock` | `EvidenceBlock` | the official source: host, dated citation, one external action, and the note that ScholarZone does not host applications. Framed — it is an artefact. |
| `EmptyState` | `EmptyState` | one sentence and one action. No illustration, no icon, no encouragement. |
| `Skeleton` / `SkeletonRow` | `Skeleton`, `SkeletonRow` | static paper-sunk blocks. **No shimmer** — a looping animation on every loading state is motion spent on content that has not arrived. |
| `ArrowRight`, `ArrowUpRight`, `SearchGlyph`, `CloseGlyph` | same | the four glyphs in the product, so every "continue" is drawn with the same path. |
| `.sz-notice` | (class) | the one box on a catalogue page, and only because it is a system state: the data on screen is not live. |

`Table` (`.sz-table`) exists as a class for the comparison view: hairline rows,
no zebra, tabular numerals.

**No `Card` primitive exists.** A card is a decision, not a component. The only
bordered containers in the system are a photograph, a record in a list, a
control, and the evidence block.

Iconography: one family, 1.5px stroke, 16–20px, `currentColor`. Icons appear only
where they replace a word or mark a state — the search glyph, the close glyph,
the arrow, the shield on the evidence block. No icon beside a sentence for
emphasis, and no icon in any heading.

---

## 9. Imagery

- Crop to 4:3 always, hard. `object-fit: contain` with 12% padding for anything
  whose `image_kind` is a logo or wordmark, so the mark is letterboxed rather
  than cropped, and `cover` for photographic programme images.
- `filter: saturate(0.92)` on the detail figure so a photograph sits inside the
  palette instead of on top of it.
- **No image region at all** when there is no authentic institutional image —
  not a monogram, not a glyph, not a country stock photo presented as a
  university's campus. On the catalogue row an absent or failed image loses its
  frame and becomes alignment space. On the detail page it is one line of type:
  "No institutional image on this record".
- The hero carries no photograph. The hero is type.
- No flag emoji anywhere: regional indicator pairs render as a picture on Apple
  platforms and as the two underlying letters everywhere else, so the same index
  read "AU Australia" on a Mac and "au Australia" on Windows.


---

## 10. Verification — run and recorded

Measured against the running app with the API live, at 1440×900 and 390×844,
light and dark, motion on and off, across `/`, `/scholarships`,
`/scholarships/:id`, `/countries`, `/compare`, `/saved`, `/match`, `/login`,
`/admin` and the 404.

| Check | Result |
|---|---|
| `npm run lint` | 0 problems |
| `npm run build` | succeeds — CSS 148.9 kB / 23.7 kB gzip, JS 456.6 kB / 126.9 kB gzip |
| Horizontal overflow, `scrollWidth − clientWidth`, every public route | **0** at both widths |
| Running animations (`animation-name ≠ none`) | **0** on every public route |
| Transitions under `prefers-reduced-motion: reduce` | **0** on the detail route |
| `border-radius` above 3.5px | **none** on any public route |
| Rendered text below 10.5px | **none** on any public route |
| Decorative `box-shadow` | **none** (the only shadows are the 1px inset ring that draws the hollow provenance square) |
| Hardcoded hex in the public CSS I own | none |
| CSS bundle | 164.7 kB → 148.9 kB, and ~1,200 lines of never-imported component + ~690 lines of never-imported glass CSS removed |

The ten questions from the brief:

1. **Education platform?** Yes. Warm paper, a serif that only ever carries a
   headline, and a catalogue of real records at the centre.
2. **Trustworthy?** The verification state is on every row, the source URL and
   the date it was read are on every record, and the negative states are stated
   rather than hidden.
3. **Expensive without tricks?** The only devices are typography, a 1px rule and
   a single 6×2px square. There is no gradient, no glow and no floating element
   on any public route.
4. **One glance?** Each row is name → institution → provenance rule → four
   labelled facts → state → one action, in that order, at a fixed height.
5. **Premium with animations disabled?** It is identical. There is nothing to
   disable.
6. **Mobile intentional?** Full-bleed sections, a 2×2 filter grid, a 2×2 figure
   grid, a 64px logo column that survives, 44px targets, zero overflow.
7. **Features prioritised?** Discover → Match → Understand → Prepare → Apply is
   one band with one filled button, and it is the only step that asks something
   of the reader first.
8. **Hierarchy obvious?** Three rules carry the page: a 2px ink rule, a 1px
   `--rule-strong`, a 1px `--border`.
9. **Typography editorial?** One serif, display-only. One sans for everything
   else. One ladder, and nothing sets a size outside it.
10. **Anything still a generic AI dashboard?** No public route has a gradient, a
    glow, an orbiting object, a pulse, a count-up, or a card that is not a
    record, a photograph, a control or the evidence block.

Two answers are partial, deliberately, and are recorded in §12 rather than
papered over: the inert `?degree=` / `?funding=` deep links, and the 100-record
directory cap that silently drops saved and compare ids.


---

## 11. What was removed, and why

The redesign is mostly subtractive. Recorded so the reasoning survives the
next person who finds something missing and assumes it was an accident.

| Removed | Reason |
|---|---|
| `.app-atmosphere` — three drifting radial washes + a 46s sheen, painted behind every page | cost a composited layer on every scroll frame and bought nothing. On a page this typographic, the paper is the design; a moving field behind it reads as a template. |
| `components/ui/Glass*.jsx` + `~690 lines` of `.sz-glass*` CSS | never imported. A complete, designed, entirely unconsumed primitive layer. |
| `components/AmbientOrbs.jsx` + `.sz-ambient` | never imported; four hardcoded `%` sizes, four offsets, four px shifts, four durations and four delays, all bypassing the token layer. |
| `Ledger.css` (17KB) | an override stack on top of `theme.css`. Two stylesheets disagreeing about the same rules is how the type ladder ended up with five competing treatments. |
| `styles/responsive.css` | a third correction layer. Each page now owns its own breakpoints, so a media query lives with the thing it adjusts. |
| `styles/glass.css` | imported only by `AdminPage.jsx`, which is now self-sufficient. |
| `useScrollReveal` + both reveal class names (`is-in`, `is-visible`) | wrote `transitionDelay` onto every `.scholarship-card` from a MutationObserver on `<body>`, plus a 2.5s failsafe timer — to drive CSS that no longer exists. A section that fades in on scroll cannot be compared, printed or screenshotted. |
| `ScholarZoneHero`, `FeaturedStory`, `TrustFlow`, `SaveCompareSteps`, `ScholarshipShowcase`, `ScholarshipCardSkeleton` | five features each presented as its own section with its own visual identity, which is what made Match, Saved, Compare and Apply read as unrelated products. Replaced by one journey band on the home page and by the catalogue's own row. |
| `HomeHero`, `HomeStats`, `HomeTrust`, `HomeFeatures`, `HeroNetwork` | never imported. `HeroNetwork` had no stylesheet at all. |
| `ScholarCard` pointer-tilt custom properties | `--lg-hx/--lg-hy` were written on mousemove to drive a glow. A 140ms paper lift on hover does the same job for a fraction of the cost. |
| Scroll-reveal stagger (`Math.min(index, 12) * 40ms`) | a staggered cascade is the signature of a template, not of a catalogue. |
| Flag emoji on destinations | regional indicator pairs render as a picture on Apple platforms and as two letters everywhere else, so the same index read `AU Australia` on a Mac and `au Australia` on Windows. |
| "Every listing is checked against the awarding body's own page before it appears here" (hero) | the catalogue publishes records whose page could not be reached as "Confirm with provider". A blanket claim on the home page contradicts what the cards say. The verification section now describes the rule the cards actually apply. |

---

## 12. Known gaps, deliberately left

- **`?degree=` and `?funding=` deep links are inert.** `ScholarshipsPage` reads
  only `?country=` and passes it to `ScholarshipList` as a seed; `degree`,
  `funding`, `search` and `status` initialise to `'All'`. The home page's
  "Narrow it down" filter form therefore produces links that land on the
  unfiltered catalogue. Pre-existing and a data-contract change, so out of
  scope here — but it is a real defect and worth a ticket.
- **`DIRECTORY_LIMIT = 100` silently truncates the saved and compare joins.** A
  persisted id outside the first 100 records disappears from `/saved` and
  `/compare` with no explanation. Also pre-existing.
- **The admin console keeps its own visual language.** `pages/AdminPage.css` is
  a dense dark instrument panel with glass navigation, orbs and glow shadows —
  appropriate for an operator tool and deliberately not part of the public
  system. Its tokens (`--glass-radius-*`, `--status-*-glow`, `--orb-bg`, …)
  used to live in the shared `theme.css` and were removed with it, which left
  every `var()` in that file resolving to nothing; they are now declared on
  `.admin-page` so the console owns its whole token set.
- **The detail page's aside is sticky above 900px.** A long record scrolls
  under a fixed evidence block. It is the right trade at desktop width and the
  wrong one on a phone, which is why it is dropped below 900px.

---

## 13. Non-negotiables carried forward

- Never modify `vite.config.js` `base`, or the `main.jsx` router basename. Two
  separate blank-page incidents came from that.
- List rendering keys off `image_kind`, never `image_url`.
- `verification_status` is the verification state. The `verified` boolean is
  history and must not drive a verified badge.
- Match 2.0, Count Intelligence, verification contracts, scholarship data and
  public visibility rules are out of scope.
- The Match `?link=` deep-link keys (`citizenship`, `field`, `degree`,
  `country`) are an inbound external contract. Renaming them breaks live links.
- `useScholarshipStats` never fabricates a value on error; it renders a neutral
  unavailable state. Keep it that way.
- No new dependencies.
- No invented metrics. Every figure comes from `GET /scholarships/stats`, and
  its nine fields are the only figures permitted.
- No token gaps are to be patched in `theme.css` from a component. A colour a
  component cannot express is a report, not an addition.
